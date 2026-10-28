"""Tests for creating and launching ensembles."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any
from unittest import mock

from django.core.exceptions import ValidationError
import pytest

from net_maestro.core.constants import RunStatus, SimulationType
from net_maestro.core.models import Ensemble, FFWSimulationConfig, Run
from net_maestro.core.services import ensembles
from net_maestro.core.services.ensembles import create_ensemble, launch_ensemble
from net_maestro.core.sweeps import SweepError
from net_maestro.core.tests.factories import EnsembleFactory, RunFactory
from net_maestro.core.topology import TopologyError, get_topology, list_topologies

if TYPE_CHECKING:
    from pytest_django.fixtures import SettingsWrapper

    from net_maestro.core.topology import Topology

pytestmark = pytest.mark.django_db

REPO_TOPOLOGIES = Path(__file__).resolve().parents[3] / "data" / "topologies"

TOPOLOGY_YAML = """
topology:
  switches:
    A:
      terminals: 2
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        B: "100 Gbps"
    B:
      terminals: 2
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        A: "100 Gbps"
"""

PRESET = "ffw-fabric-2-site"
BASE: dict[str, Any] = {"topology_name": PRESET, "traffic": "random", "np": 1, "sync": 1}


@pytest.fixture
def preset(tmp_path: Path, settings: SettingsWrapper) -> str:
    """Write one topology preset and point the topology directory at it."""
    settings.TOPOLOGY_DIR = tmp_path
    (tmp_path / f"{PRESET}.yaml").write_text(TOPOLOGY_YAML, encoding="utf-8")
    return PRESET


def _create(spec: list[dict[str, Any]], **overrides: Any) -> Ensemble:
    kwargs: dict[str, Any] = {
        "name": "Buffers",
        "description": "sweep",
        "simulation_type": SimulationType.FFW,
        "base_params": BASE,
        "sweep_spec": spec,
        "run_status": RunStatus.SAVED,
        **overrides,
    }
    return create_ensemble(**kwargs)


def _generated(tmp_path: Path) -> list[str]:
    return sorted(path.stem for path in tmp_path.glob("*-sweep-*.yaml"))


def test_creates_one_run_and_config_per_member(preset: str, tmp_path: Path) -> None:
    ensemble = _create(
        [{"key": "switch_buffer_gb", "values": [2, 8]}, {"key": "np", "values": [1, 4]}]
    )

    members = list(ensemble.members)
    assert [run.member_index for run in members] == [1, 2, 3, 4]
    assert [run.member_params for run in members] == [
        {"switch_buffer_gb": 2, "np": 1},
        {"switch_buffer_gb": 2, "np": 4},
        {"switch_buffer_gb": 8, "np": 1},
        {"switch_buffer_gb": 8, "np": 4},
    ]
    assert members[1].name == "Buffers · switch_buffer_gb=2, np=4"
    assert {run.status for run in members} == {RunStatus.SAVED}
    assert {run.simulation_type for run in members} == {SimulationType.FFW}
    assert {run.description for run in members} == {"sweep"}
    assert FFWSimulationConfig.objects.filter(run__ensemble=ensemble).count() == 4

    config = members[3].ffw_configs.get()
    assert config.topology_name == f"{PRESET}-sweep-{ensemble.id}-4"
    assert (config.traffic, config.np, config.sync) == ("random", 4, 1)

    assert ensemble.base_params == BASE
    assert ensemble.status == RunStatus.SAVED
    assert ensemble.status_counts() == {RunStatus.SAVED: 4}


def test_writes_a_topology_file_per_edited_member(preset: str, tmp_path: Path) -> None:
    ensemble = _create([{"key": "switch_buffer_gb", "values": [2, 8]}])

    names = [f"{PRESET}-sweep-{ensemble.id}-1", f"{PRESET}-sweep-{ensemble.id}-2"]
    assert _generated(tmp_path) == names
    assert {s.switch_buffer_gb for s in get_topology(names[1]).switches} == {8.0}


def test_member_running_the_preset_as_is_gets_no_file(preset: str, tmp_path: Path) -> None:
    ensemble = _create([{"key": "switch_buffer_gb", "values": [64, 8]}])

    first, _ = ensemble.members
    assert first.ffw_configs.get().topology_name == PRESET
    assert _generated(tmp_path) == [f"{PRESET}-sweep-{ensemble.id}-2"]


def test_settings_only_sweep_writes_no_files(preset: str, tmp_path: Path) -> None:
    ensemble = _create([{"key": "sync", "values": [1, 3]}])

    assert [run.ffw_configs.get().sync for run in ensemble.members] == [1, 3]
    assert _generated(tmp_path) == []


def test_generated_topologies_are_hidden_but_resolvable(preset: str) -> None:
    ensemble = _create([{"key": "switch_buffer_gb", "values": [8]}])
    derived = f"{PRESET}-sweep-{ensemble.id}-1"

    assert [t.name for t in list_topologies()] == [PRESET]
    assert derived in {t.name for t in list_topologies(include_generated=True)}
    assert get_topology(derived).name == derived
    # The member's config validates against it, which is what a saved-run launch checks.
    ensemble.members.get().ffw_configs.get().full_clean()


def test_failure_midway_removes_written_files_and_rows(preset: str, tmp_path: Path) -> None:
    real_save = ensembles.save_topology
    calls = 0

    def fail_on_third(topology: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise TopologyError("disk full")
        return real_save(topology)

    with (
        mock.patch.object(ensembles, "save_topology", side_effect=fail_on_third),
        pytest.raises(TopologyError, match="disk full"),
    ):
        _create([{"key": "switch_buffer_gb", "values": [1, 2, 3]}])

    assert _generated(tmp_path) == []
    assert not Ensemble.objects.exists()
    assert not Run.objects.exists()


def test_failure_after_files_are_written_removes_them(preset: str, tmp_path: Path) -> None:
    """A database error after the last file is written still cleans up every file."""
    with (
        mock.patch.object(
            ensembles.FFWSimulationConfig.objects, "create", side_effect=RuntimeError("db")
        ),
        pytest.raises(RuntimeError),
    ):
        _create([{"key": "switch_buffer_gb", "values": [1, 2]}])

    assert _generated(tmp_path) == []
    assert not Ensemble.objects.exists()


def test_failure_leaves_files_it_did_not_write(preset: str, tmp_path: Path) -> None:
    """A clash with an existing file is an error, and that file is not ours to delete."""
    real_save = ensembles.save_topology
    clashes: list[Path] = []

    def someone_else_writes_the_next_one(topology: Any) -> Any:
        # The ensemble id only exists once creation is under way, so the clash
        # for member 2 is planted while member 1 is being saved.
        if topology.name.endswith("-1"):
            clash = tmp_path / f"{topology.name.removesuffix('-1')}-2.yaml"
            clash.write_text(TOPOLOGY_YAML, encoding="utf-8")
            clashes.append(clash)
        return real_save(topology)

    with (
        mock.patch.object(ensembles, "save_topology", side_effect=someone_else_writes_the_next_one),
        pytest.raises(TopologyError, match="already exists"),
    ):
        _create([{"key": "switch_buffer_gb", "values": [1, 2]}])

    assert _generated(tmp_path) == [clash.stem for clash in clashes]


def test_bad_spec_writes_nothing(preset: str, tmp_path: Path) -> None:
    with pytest.raises(SweepError):
        _create([{"key": "np", "values": []}])

    assert not Ensemble.objects.exists()


def test_pending_status_is_recorded_without_launching(preset: str) -> None:
    with mock.patch.object(ensembles, "chain") as chain:
        ensemble = _create([{"key": "np", "values": [1, 2]}], run_status=RunStatus.PENDING)

    chain.assert_not_called()
    assert ensemble.status == RunStatus.RUNNING


def test_launch_chains_members_in_order(preset: str) -> None:
    ensemble = _create(
        [{"key": "switch_buffer_gb", "values": [8]}, {"key": "np", "values": [2, 1]}]
    )

    with mock.patch.object(ensembles, "chain") as chain:
        launch_ensemble(ensemble)

    assert {run.status for run in ensemble.members} == {RunStatus.PENDING}
    chain.assert_called_once()
    chain.return_value.apply_async.assert_called_once_with()
    signatures = chain.call_args.args
    first, second = ensemble.members
    assert [sig.kwargs for sig in signatures] == [
        {
            "run_id": first.id,
            "topology_name": f"{PRESET}-sweep-{ensemble.id}-1",
            "traffic": "random",
            "np": 2,
            "sync": 1,
        },
        {
            "run_id": second.id,
            "topology_name": f"{PRESET}-sweep-{ensemble.id}-2",
            "traffic": "random",
            "np": 1,
            "sync": 1,
        },
    ]
    # Immutable signatures: one member's return value is not passed to the next.
    assert all(sig.immutable for sig in signatures)


def test_launch_validation_error_launches_nothing(preset: str, tmp_path: Path) -> None:
    ensemble = _create([{"key": "switch_buffer_gb", "values": [4, 8]}])
    (tmp_path / f"{PRESET}-sweep-{ensemble.id}-2.yaml").unlink()

    with mock.patch.object(ensembles, "chain") as chain, pytest.raises(ValidationError) as exc:
        launch_ensemble(ensemble)

    chain.assert_not_called()
    assert "topology_name" in exc.value.message_dict
    assert {run.status for run in ensemble.members} == {RunStatus.SAVED}


def test_launch_of_empty_ensemble_does_nothing() -> None:
    ensemble = EnsembleFactory.create()

    with mock.patch.object(ensembles, "chain") as chain:
        launch_ensemble(ensemble)

    chain.assert_not_called()


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([], RunStatus.SAVED),
        ([RunStatus.SAVED, RunStatus.SAVED], RunStatus.SAVED),
        ([RunStatus.COMPLETED, RunStatus.PENDING], RunStatus.RUNNING),
        ([RunStatus.FAILED, RunStatus.RUNNING], RunStatus.RUNNING),
        ([RunStatus.FAILED, RunStatus.COMPLETED], RunStatus.FAILED),
        ([RunStatus.COMPLETED, RunStatus.COMPLETED], RunStatus.COMPLETED),
        ([RunStatus.SAVED, RunStatus.COMPLETED], RunStatus.COMPLETED),
    ],
)
def test_status_roll_up(statuses: list[RunStatus], expected: RunStatus) -> None:
    ensemble = EnsembleFactory.create()
    for index, status in enumerate(statuses, start=1):
        RunFactory(ensemble=ensemble, member_index=index, status=status)

    assert ensemble.status == expected
    assert sum(ensemble.status_counts().values()) == len(statuses)


def test_fabric_sweep_reproduces_the_hand_written_presets(
    tmp_path: Path, settings: SettingsWrapper
) -> None:
    """The FABRIC study's buffer and STAR-MICH presets come back out of the form's sweep."""
    shutil.copytree(REPO_TOPOLOGIES, tmp_path, dirs_exist_ok=True)
    settings.TOPOLOGY_DIR = tmp_path
    base = "fluid-flow-wan-fabric-5-site"

    ensemble = _create(
        [
            {"key": "switch_buffer_gb", "values": [2, 8]},
            {
                "key": "link_bandwidth_gbps",
                "link": {"source": "STAR", "target": "MICH"},
                "values": [40, 100, 400],
            },
        ],
        name="FABRIC",
        base_params={**BASE, "topology_name": base},
    )

    by_params: dict[tuple[int, int], Run] = {}
    for run in ensemble.members:
        assert run.member_params is not None
        by_params[
            run.member_params["switch_buffer_gb"], run.member_params["link_bandwidth_gbps"]
        ] = run
    assert len(by_params) == 6

    def member_topology(buffer: int, bandwidth: int) -> Topology:
        return get_topology(by_params[buffer, bandwidth].ffw_configs.get().topology_name)

    for (buffer, bandwidth), preset_name in [
        ((8, 100), f"{base}-deep-buffers"),
        ((2, 40), f"{base}-mich-40g"),
        ((2, 400), f"{base}-mich-400g"),
    ]:
        generated = member_topology(buffer, bandwidth)
        expected = get_topology(preset_name)
        assert generated.name.startswith(f"{base}-sweep-{ensemble.id}-")
        assert generated.switches == expected.switches
        assert generated.links == expected.links

    # Buffer 2 at 100 Gbps is the base preset itself, so it runs that file.
    assert by_params[2, 100].ffw_configs.get().topology_name == base
