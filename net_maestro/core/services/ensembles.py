"""Creating and launching ensembles.

An ensemble's members are ordinary Runs with their own FFWSimulationConfig, so
everything downstream of creation (saved-run launch, clone, the analysis page)
treats a member like any standalone run. Members whose topology a sweep edited
also get a topology file of their own, because the FFW task and the analysis
page both look topologies up by name.
"""

from __future__ import annotations

from dataclasses import replace
import logging
from typing import TYPE_CHECKING, Any

from celery import chain
from django.core.exceptions import ValidationError
from django.db import transaction

from net_maestro.core.constants import RunStatus, SimulationType
from net_maestro.core.models import Ensemble, FFWSimulationConfig, Run
from net_maestro.core.sweeps import SweepError, expand_sweep, member_label
from net_maestro.core.tasks import run_ffw_simulation
from net_maestro.core.topology import save_topology, topology_dir

if TYPE_CHECKING:
    from pathlib import Path

    from net_maestro.core.sweeps import Member

logger = logging.getLogger(__name__)

# The config fields an FFW member takes from its resolved params.
_FFW_FIELDS = ("topology_name", "traffic", "np", "sync")

_NAME_MAX_LENGTH = Run._meta.get_field("name").max_length or 200


def _derived_topology_name(base: str, ensemble: Ensemble, member: Member) -> str:
    """Name a member's topology file.

    Carries the word `sweep`, which keeps it out of the topology pickers, and
    the ensemble id and member index, which keep it unique without checking
    what is already on disk.
    """
    return f"{base}-sweep-{ensemble.id}-{member.index}"


def create_ensemble(  # noqa: PLR0913
    *,
    name: str,
    description: str,
    simulation_type: str,
    base_params: dict[str, Any],
    sweep_spec: list[dict[str, Any]],
    run_status: RunStatus,
) -> Ensemble:
    """Create an ensemble, one Run and config per member, and any derived topologies.

    Raises SweepError for a spec that does not expand, before anything is
    written, and TopologyError when a derived topology cannot be saved.

    The database rows go in one transaction, but topology files are outside
    it, so a failure partway through also deletes the files this call wrote.
    A file that was already there is never ours to delete.

    Does not launch anything: `run_status` is only what the members are marked
    as. Call `launch_ensemble` to run them.
    """
    if simulation_type != SimulationType.FFW:
        raise SweepError(f"Sweeps are not available for {simulation_type} simulations yet")
    members = expand_sweep(simulation_type, base_params, sweep_spec)

    written: list[Path] = []
    try:
        with transaction.atomic():
            # Created first: the derived topology names carry its id.
            ensemble = Ensemble.objects.create(
                name=name,
                description=description,
                simulation_type=simulation_type,
                base_params=base_params,
                sweep_spec=sweep_spec,
            )
            for member in members:
                params = dict(member.params)
                if member.topology is not None:
                    derived = _derived_topology_name(member.topology.name, ensemble, member)
                    path = topology_dir() / f"{derived}.yaml"
                    if not path.exists():
                        written.append(path)
                    save_topology(replace(member.topology, name=derived))
                    params["topology_name"] = derived

                run = Run.objects.create(
                    name=f"{name} · {member_label(member.member_params)}"[:_NAME_MAX_LENGTH],
                    description=description,
                    status=run_status,
                    simulation_type=simulation_type,
                    ensemble=ensemble,
                    member_index=member.index,
                    member_params=member.member_params,
                )
                FFWSimulationConfig.objects.create(
                    run=run, **{key: params[key] for key in _FFW_FIELDS if key in params}
                )
    except BaseException:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return ensemble


def launch_ensemble(ensemble: Ensemble) -> None:
    """Queue every member to run, one after another, in member order.

    Members run in sequence, not in parallel, because the FFW task rewrites
    the shared stock traffic config in place; two members at once would
    overwrite each other's. A Celery chain gives that ordering without a lock,
    and one failed member does not stop the rest: the task records the failure
    on its Run rather than raising.

    Re-validates every member's config first, the way a saved standalone run
    is checked before it launches, and launches nothing if any fails: a sweep
    with a hole in it is harder to read than one that did not start.
    """
    planned: list[tuple[Run, FFWSimulationConfig]] = []
    for run in ensemble.members:
        config = run.ffw_configs.order_by("-id").first()
        if config is None:
            raise ValidationError(f"{run.name} has no saved configuration")
        try:
            config.full_clean()
        except ValidationError as exc:
            raise ValidationError(
                {
                    field: [f"{run.name}: {message}" for message in messages]
                    for field, messages in exc.message_dict.items()
                }
            ) from exc
        planned.append((run, config))
    if not planned:
        return

    Run.objects.filter(id__in=[run.id for run, _ in planned]).update(status=RunStatus.PENDING)
    chain(
        *(
            run_ffw_simulation.si(
                run_id=run.id,
                topology_name=config.topology_name,
                traffic=config.traffic,
                np=config.np,
                sync=config.sync,
            )
            for run, config in planned
        )
    ).apply_async()
    logger.info("Queued %d members of ensemble %s", len(planned), ensemble.id)
