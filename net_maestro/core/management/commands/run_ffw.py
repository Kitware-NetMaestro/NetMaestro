"""RUN FFW simulation management command.

Execute Fluid-Flow WAN simulation with specified parameters and ingest results.
"""

from __future__ import annotations

from pathlib import Path

import djclick as click

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import Run
from net_maestro.core.services.ffw import FFW_TRAFFIC_DEFAULTS
from net_maestro.core.tasks.simulation import run_ffw_simulation
from net_maestro.core.topology import TopologyError, get_topology


def _create_or_update_run(
    name: str,
    description: str | None,
    run_id: int | None,
) -> Run:
    """Create a new Run object or update an existing one's metadata.

    Args:
        name: Run identifier
        description: Run description
        run_id: Existing run ID to update, or None to create new

    Returns:
        The Run object

    Raises:
        Run.DoesNotExist: If run_id is provided but no matching Run exists
    """
    if run_id:
        run = Run.objects.get(id=run_id)
        run.name = name
        run.description = description or ""
        run.save()
    else:
        run = Run.objects.create(
            name=name,
            description=description or "",
            status=RunStatus.PENDING,
        )
    return run


# TODO: consider adding the stats path as an option
# get help text for new options
@click.command()
@click.option(
    "-n",
    "--name",
    "name",
    type=str,
    help="Run identifier.",
    required=True,
)
@click.option(
    "--np",
    "np",
    type=int,
    default=1,
    help="Number of MPI processes.",
)
@click.option(
    "--binary-path",
    "binary_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to FFW binary.",
)
@click.option(
    "--sync",
    "sync",
    type=int,
    default=1,
    help=(
        "Synchronization protocol (1=sequential, 2=conservative, 3=optimistic, "
        "4=optimistic-debug, 5=optimistic-realtime, 6=reverse-check)."
    ),
)
@click.option(
    "--model-stats",
    "model_stats",
    type=int,
    default=4,
)
@click.option(
    "--num-gvt",
    "num_gvt",
    type=int,
    default=1,
)
@click.option(
    "--rt-interval",
    "rt_interval",
    type=int,
    default=1,
)
@click.option("--vt-interval", "vt_interval", type=int, default=1e8)
@click.option("--vt-samp-end", "vt_samp_end", type=int, default=1.7e10)
@click.option(
    "--config-path",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to FFW configuration file.",
)
@click.option(
    "--topology",
    "topology_name",
    type=str,
    required=True,
    help="Name of the topology to simulate, e.g. fluid-flow-wan-8-switch.",
)
@click.option(
    "--traffic",
    type=click.Choice(sorted(FFW_TRAFFIC_DEFAULTS)),
    default="random",
    help="Traffic mode; picks the default binary and traffic config.",
)
@click.option(
    "--description",
    "description",
    type=str,
    help="Description of the run.",
)
@click.option(
    "--run-id",
    "run_id",
    type=int,
    default=None,
    help="Existing run ID to update instead of creating a new run.",
)
def run_ffw(  # noqa: PLR0913
    name: str,
    np: int,
    binary_path: Path,
    sync: int,
    model_stats: int,
    num_gvt: int,
    rt_interval: int,
    vt_interval: int,
    vt_samp_end: int,
    config_path: Path,
    topology_name: str,
    traffic: str,
    description: str | None = None,
    run_id: int | None = None,
) -> None:
    try:
        get_topology(topology_name)
    except TopologyError as exc:
        raise click.ClickException(str(exc)) from exc

    # Create or update Run object
    run = _create_or_update_run(name, description, run_id)
    run_ffw_simulation.apply(
        kwargs={
            "run_id": run.id,
            "topology_name": topology_name,
            "traffic": traffic,
            "np": np,
            "sync": sync,
            "model_stats": model_stats,
            "num_gvt": num_gvt,
            "rt_interval": rt_interval,
            "vt_interval": vt_interval,
            "vt_samp_end": vt_samp_end,
            "config_path": str(config_path) if config_path else "",
            "binary_path": str(binary_path) if binary_path else "",
        }
    )
