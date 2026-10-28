"""Tests for the FFW service and the task that runs it.

Covers the per-run inputs NetMaestro generates from a template traffic config, the
sampling settings it derives from a config, and how `run_ffw_simulation` wires the
two together around the (mocked) model.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import TYPE_CHECKING
from unittest import mock

import pytest
import yaml

from net_maestro.core.constants import FFWTrafficMode, RunStatus
from net_maestro.core.services.ffw import (
    FFW_STATS_FILES,
    FFWInputError,
    vt_sampling_for,
    write_run_inputs,
)
from net_maestro.core.tasks.simulation import run_ffw_simulation
from net_maestro.core.tests.factories import RunFactory
from net_maestro.core.topology import SWITCH_LP_NAME, TERMINAL_LP_NAME, get_topology

if TYPE_CHECKING:
    from pytest_django.fixtures import SettingsWrapper

    from net_maestro.core.topology import Topology

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

TOPOLOGY_NAME = "ffw-two-site"

# Shaped like the stock FABRIC random-traffic example: LP counts and a topology file
# for some other topology, which the generated config must replace, and settings
# NetMaestro does not own, which it must keep.
TEMPLATE_YAML = f"""# A comment the generated copy is allowed to lose.
schema_version: 1
topology:
  format: groups
  groups:
    FLUID_FLOW_WAN_GRP:
      repetitions: 1
      lps:
        {SWITCH_LP_NAME}: 5
        {TERMINAL_LP_NAME}: 10
sections:
  fluid_flow_wan:
    topology_yaml_file: some-other-topology.yaml
    interval_seconds: 1
    num_send_intervals: 12
    num_drain_intervals: 30
    random_flow_min: 100 Gb
    future_model_setting: 7
    terminal_log_path: logs/terminal-events.csv
    switch_log_path: logs/switch-events.csv
"""

TRACE_TEMPLATE_YAML = f"""topology:
  groups:
    FLUID_FLOW_WAN_GRP:
      lps:
        {SWITCH_LP_NAME}: 5
        {TERMINAL_LP_NAME}: 10
sections:
  fluid_flow_wan:
    topology_yaml_file: some-other-topology.yaml
    interval_seconds: 10
    num_send_intervals: 37
    num_drain_intervals: 5
    traffic_trace_file: traces/ladder.csv
"""

TRACE_HEADER = "start_interval,source_terminal,destination_terminal,size\n"


@pytest.fixture
def topology(tmp_path: Path, settings: SettingsWrapper) -> Topology:
    settings.TOPOLOGY_DIR = tmp_path / "topologies"
    settings.TOPOLOGY_DIR.mkdir()
    (settings.TOPOLOGY_DIR / f"{TOPOLOGY_NAME}.yaml").write_text(TOPOLOGY_YAML, encoding="utf-8")
    return get_topology(TOPOLOGY_NAME)


def _template(directory: Path, body: str = TEMPLATE_YAML, name: str = "traffic.yaml") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


def _files_under(directory: Path) -> set[Path]:
    return set(directory.rglob("*"))


def _config(tmp_path: Path, **section: object) -> Path:
    body = "sections:\n  fluid_flow_wan:\n" + "".join(
        f"    {key}: {value}\n" for key, value in section.items()
    )
    path = tmp_path / "traffic.yaml"
    path.write_text(body, encoding="utf-8")
    return path


class TestWriteRunInputs:
    """The generated config: the template's settings, NetMaestro's on top, all in run_dir."""

    def test_generates_the_config_and_leaves_the_template_alone(
        self, tmp_path: Path, topology: Topology
    ) -> None:
        template = _template(tmp_path / "template")
        before = template.read_bytes()
        template_files = _files_under(template.parent)
        run_dir = tmp_path / "run"

        config_path = write_run_inputs(
            run_dir=run_dir,
            template_path=template,
            topology=topology,
            overrides={"num_drain_intervals": 100},
        )

        assert template.read_bytes() == before
        assert _files_under(template.parent) == template_files
        assert config_path == run_dir / "inputs" / "traffic.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert config["topology"]["groups"]["FLUID_FLOW_WAN_GRP"]["lps"] == {
            SWITCH_LP_NAME: 2,
            TERMINAL_LP_NAME: 4,
        }
        section = config["sections"]["fluid_flow_wan"]
        assert section["topology_yaml_file"] == f"{TOPOLOGY_NAME}.yaml"
        assert section["num_drain_intervals"] == 100
        # Fields NetMaestro does not own pass through.
        assert section["num_send_intervals"] == 12
        assert section["random_flow_min"] == "100 Gb"
        assert section["future_model_setting"] == 7
        assert config["schema_version"] == 1

    def test_writes_the_topology_and_log_dirs_beside_the_config(
        self, tmp_path: Path, topology: Topology
    ) -> None:
        run_dir = tmp_path / "run"

        write_run_inputs(
            run_dir=run_dir,
            template_path=_template(tmp_path / "template"),
            topology=topology,
            overrides={},
        )

        inputs = run_dir / "inputs"
        document = yaml.safe_load((inputs / f"{TOPOLOGY_NAME}.yaml").read_text(encoding="utf-8"))
        assert set(document["topology"]["switches"]) == {"A", "B"}
        assert (inputs / "logs").is_dir()
        assert _files_under(run_dir) == {
            inputs,
            inputs / "traffic.yaml",
            inputs / f"{TOPOLOGY_NAME}.yaml",
            inputs / "logs",
        }

    def test_overrides_win_over_the_topology_too(self, tmp_path: Path, topology: Topology) -> None:
        """Applied last, an override is what the model sees, whatever it names."""
        config_path = write_run_inputs(
            run_dir=tmp_path / "run",
            template_path=_template(tmp_path / "template"),
            topology=topology,
            overrides={"interval_seconds": 2, "rng_seed": 99},
        )

        section = yaml.safe_load(config_path.read_text(encoding="utf-8"))["sections"][
            "fluid_flow_wan"
        ]
        assert section["interval_seconds"] == 2
        assert section["rng_seed"] == 99

    def test_copies_the_trace_from_the_template_directory(
        self, tmp_path: Path, topology: Topology
    ) -> None:
        template = _template(tmp_path / "template", TRACE_TEMPLATE_YAML)
        trace = template.parent / "traces" / "ladder.csv"
        trace.parent.mkdir()
        trace.write_text(TRACE_HEADER + "0,0,3,10 Gb\n", encoding="utf-8")
        run_dir = tmp_path / "run"

        config_path = write_run_inputs(
            run_dir=run_dir, template_path=template, topology=topology, overrides={}
        )

        copy = run_dir / "inputs" / "traces" / "ladder.csv"
        assert copy.read_bytes() == trace.read_bytes()
        section = yaml.safe_load(config_path.read_text(encoding="utf-8"))["sections"][
            "fluid_flow_wan"
        ]
        assert section["traffic_trace_file"] == "traces/ladder.csv"

    def test_rejects_a_trace_with_terminals_the_topology_lacks(
        self, tmp_path: Path, topology: Topology
    ) -> None:
        template = _template(tmp_path / "template", TRACE_TEMPLATE_YAML)
        trace = template.parent / "traces" / "ladder.csv"
        trace.parent.mkdir()
        trace.write_text(TRACE_HEADER + "0,0,9,10 Gb\n", encoding="utf-8")

        with pytest.raises(FFWInputError, match="destination_terminal 9"):
            write_run_inputs(
                run_dir=tmp_path / "run",
                template_path=template,
                topology=topology,
                overrides={},
            )
        assert not (tmp_path / "run").exists()


def test_sampling_covers_the_random_traffic_run(tmp_path: Path) -> None:
    """The FABRIC random-traffic config: 1 s intervals, 12 send + 30 drain."""
    sampling = vt_sampling_for(
        _config(tmp_path, interval_seconds=1, num_send_intervals=12, num_drain_intervals=30)
    )

    assert sampling.interval_ns == 100_000_000
    assert sampling.end_ns == 42_000_000_000


def test_sampling_follows_the_interval_length(tmp_path: Path) -> None:
    """The trace ladder's 10 s intervals get ten samples each, not a hundred."""
    sampling = vt_sampling_for(
        _config(tmp_path, interval_seconds=10, num_send_intervals=37, num_drain_intervals=5)
    )

    assert sampling.interval_ns == 1_000_000_000
    assert sampling.end_ns == 420_000_000_000


def test_sampling_accepts_fractional_intervals(tmp_path: Path) -> None:
    sampling = vt_sampling_for(
        _config(tmp_path, interval_seconds=0.5, num_send_intervals=4, num_drain_intervals=0)
    )

    assert sampling.interval_ns == 50_000_000
    assert sampling.end_ns == 2_000_000_000


@pytest.mark.parametrize(
    "section",
    [
        {"interval_seconds": 1, "num_send_intervals": 12},
        {"interval_seconds": "soon", "num_send_intervals": 12, "num_drain_intervals": 30},
        {"interval_seconds": 0, "num_send_intervals": 12, "num_drain_intervals": 30},
        {"interval_seconds": 1, "num_send_intervals": 0, "num_drain_intervals": 0},
    ],
)
def test_sampling_rejects_a_config_without_a_run_length(
    tmp_path: Path, section: dict[str, object]
) -> None:
    with pytest.raises(FFWInputError):
        vt_sampling_for(_config(tmp_path, **section))


@pytest.mark.django_db
class TestTask:
    """The task generates the run's inputs, runs the model there, and samples the whole run."""

    @pytest.fixture
    def preset(self, tmp_path: Path, settings: SettingsWrapper) -> str:
        settings.TOPOLOGY_DIR = tmp_path
        (tmp_path / f"{TOPOLOGY_NAME}.yaml").write_text(TOPOLOGY_YAML, encoding="utf-8")
        settings.FFW_CONFIG_PATH = str(_template(tmp_path / "template"))
        settings.FFW_OUTPUT_DIR = str(tmp_path / "out")
        return TOPOLOGY_NAME

    @pytest.fixture
    def stats_dir(self, tmp_path: Path) -> Path:
        stats_dir = tmp_path / "stats"
        stats_dir.mkdir()
        for name in FFW_STATS_FILES:
            (stats_dir / name).write_bytes(b"")
        return stats_dir

    @mock.patch("net_maestro.core.tasks.simulation.compute_run_summary", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.run_ffw_ingest_task", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model")
    def test_runs_the_model_in_the_run_directory(
        self, execute: mock.Mock, preset: str, stats_dir: Path, tmp_path: Path
    ) -> None:
        execute.return_value = stats_dir
        run = RunFactory.create(status=RunStatus.PENDING)

        run_ffw_simulation(run_id=run.id, topology_name=preset)

        run.refresh_from_db()
        assert run.status == RunStatus.COMPLETED
        run_dir = tmp_path / "out" / run.work_dir.rsplit("/", 1)[-1]
        assert run.work_dir == str(run_dir)
        assert run_dir.name.startswith(f"run-{run.id}-")
        kwargs = execute.call_args.kwargs
        assert kwargs["working_dir"] == str(run_dir / "inputs")
        assert kwargs["config_path"] == str(run_dir / "inputs" / "traffic.yaml")
        assert kwargs["stats_dir"] == run_dir / "stats"
        # ROSS must create the stats directory itself.
        assert not (run_dir / "stats").exists()
        config = yaml.safe_load((run_dir / "inputs" / "traffic.yaml").read_text(encoding="utf-8"))
        assert config["sections"]["fluid_flow_wan"]["topology_yaml_file"] == f"{preset}.yaml"

    @mock.patch("net_maestro.core.tasks.simulation.compute_run_summary", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.run_ffw_ingest_task", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model")
    def test_sampling_reflects_the_random_mode_drain(
        self, execute: mock.Mock, preset: str, stats_dir: Path
    ) -> None:
        """The template's 12 + 30 intervals become 12 + 100 with NetMaestro's drain."""
        execute.return_value = stats_dir
        run = RunFactory.create(status=RunStatus.PENDING)

        run_ffw_simulation(run_id=run.id, topology_name=preset, traffic=FFWTrafficMode.RANDOM)

        kwargs = execute.call_args.kwargs
        assert kwargs["vt_interval"] == 100_000_000
        assert kwargs["vt_samp_end"] == 112_000_000_000

    @mock.patch("net_maestro.core.tasks.simulation.compute_run_summary", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.run_ffw_ingest_task", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model")
    def test_caller_overrides_win_over_the_mode(
        self, execute: mock.Mock, preset: str, stats_dir: Path
    ) -> None:
        execute.return_value = stats_dir
        run = RunFactory.create(status=RunStatus.PENDING)

        run_ffw_simulation(
            run_id=run.id,
            topology_name=preset,
            overrides={"num_drain_intervals": 8, "num_send_intervals": 2},
        )

        assert execute.call_args.kwargs["vt_samp_end"] == 10_000_000_000

    @mock.patch("net_maestro.core.tasks.simulation.compute_run_summary", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.run_ffw_ingest_task", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model")
    def test_explicit_values_are_kept(
        self, execute: mock.Mock, preset: str, stats_dir: Path
    ) -> None:
        execute.return_value = stats_dir
        run = RunFactory.create(status=RunStatus.PENDING)

        run_ffw_simulation(
            run_id=run.id, topology_name=preset, vt_interval=50_000_000, vt_samp_end=5_000_000_000
        )

        kwargs = execute.call_args.kwargs
        assert kwargs["vt_interval"] == 50_000_000
        assert kwargs["vt_samp_end"] == 5_000_000_000

    @mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model")
    def test_a_failed_run_keeps_its_work_dir(self, execute: mock.Mock, preset: str) -> None:
        execute.side_effect = subprocess.CalledProcessError(1, ["mpirun"], stderr="boom")
        run = RunFactory.create(status=RunStatus.PENDING)

        run_ffw_simulation(run_id=run.id, topology_name=preset)

        run.refresh_from_db()
        assert run.status == RunStatus.FAILED
        assert run.work_dir
        assert (Path(run.work_dir) / "inputs" / "logs").is_dir()

    @mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model")
    def test_a_config_without_a_run_length_fails_the_run(
        self, execute: mock.Mock, preset: str, settings: SettingsWrapper, tmp_path: Path
    ) -> None:
        settings.FFW_CONFIG_PATH = str(
            _template(
                tmp_path / "short",
                TEMPLATE_YAML.replace("    num_send_intervals: 12\n", ""),
            )
        )
        run = RunFactory.create(status=RunStatus.PENDING)

        run_ffw_simulation(run_id=run.id, topology_name=preset)

        execute.assert_not_called()
        run.refresh_from_db()
        assert run.status == RunStatus.FAILED
        assert "num_send_intervals" in run.failure_reason
