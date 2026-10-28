"""Tests for the FFW service: the sampling settings NetMaestro derives from a traffic config."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from net_maestro.core.constants import RunStatus
from net_maestro.core.services.ffw import FFW_STATS_FILES, FFWInputError, vt_sampling_for
from net_maestro.core.tasks.simulation import run_ffw_simulation
from net_maestro.core.tests.factories import RunFactory

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper

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


def _config(tmp_path: Path, **section: object) -> Path:
    body = "sections:\n  fluid_flow_wan:\n" + "".join(
        f"    {key}: {value}\n" for key, value in section.items()
    )
    path = tmp_path / "traffic.yaml"
    path.write_text(body, encoding="utf-8")
    return path


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
class TestTaskSampling:
    """The task derives the sampling from the config it runs, unless told otherwise."""

    @pytest.fixture
    def preset(self, tmp_path: Path, settings: SettingsWrapper) -> str:
        settings.TOPOLOGY_DIR = tmp_path
        name = "ffw-two-site"
        (tmp_path / f"{name}.yaml").write_text(TOPOLOGY_YAML, encoding="utf-8")
        # The stock random-traffic config the task would rewrite; the rewrite is
        # mocked, so only the run length matters here.
        settings.FFW_CONFIG_PATH = str(
            _config(tmp_path, interval_seconds=1, num_send_intervals=12, num_drain_intervals=30)
        )
        settings.FFW_OUTPUT_DIR = str(tmp_path / "out")
        return name

    @pytest.fixture
    def stats_dir(self, tmp_path: Path) -> Path:
        stats_dir = tmp_path / "stats"
        stats_dir.mkdir()
        for name in FFW_STATS_FILES:
            (stats_dir / name).write_bytes(b"")
        return stats_dir

    @mock.patch("net_maestro.core.tasks.simulation.compute_run_summary", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.run_ffw_ingest_task", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.point_traffic_config_at_topology", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model")
    def test_defaults_come_from_the_config(
        self, execute: mock.Mock, preset: str, stats_dir: Path
    ) -> None:
        execute.return_value = stats_dir
        run = RunFactory.create(status=RunStatus.PENDING)

        run_ffw_simulation(run_id=run.id, topology_name=preset)

        kwargs = execute.call_args.kwargs
        assert kwargs["vt_interval"] == 100_000_000
        assert kwargs["vt_samp_end"] == 42_000_000_000
        run.refresh_from_db()
        assert run.status == RunStatus.COMPLETED

    @mock.patch("net_maestro.core.tasks.simulation.compute_run_summary", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.run_ffw_ingest_task", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.point_traffic_config_at_topology", mock.Mock())
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

    @mock.patch("net_maestro.core.tasks.simulation.point_traffic_config_at_topology", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model")
    def test_a_config_without_a_run_length_fails_the_run(
        self, execute: mock.Mock, preset: str, settings: SettingsWrapper, tmp_path: Path
    ) -> None:
        settings.FFW_CONFIG_PATH = str(_config(tmp_path, interval_seconds=1))
        run = RunFactory.create(status=RunStatus.PENDING)

        run_ffw_simulation(run_id=run.id, topology_name=preset)

        execute.assert_not_called()
        run.refresh_from_db()
        assert run.status == RunStatus.FAILED
        assert "num_send_intervals" in run.failure_reason
