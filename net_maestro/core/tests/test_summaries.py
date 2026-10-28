"""Tests for per-run summaries and the task hooks that compute them."""

from __future__ import annotations

from datetime import timedelta
import subprocess
from typing import TYPE_CHECKING
from unittest import mock

from django.core.files.base import ContentFile
from django.utils import timezone
import pytest

from net_maestro.core.constants import FFWStatsType, RunStatus, SimulationType
from net_maestro.core.models import Run, RunSummary, SimulationFile
from net_maestro.core.services.ffw import FFW_STATS_FILES
from net_maestro.core.summaries import (
    ENGINE_METRICS,
    FFW_METRICS,
    HEADLINE_METRICS,
    compute_run_summary,
    metrics_as_json,
    metrics_for,
)
from net_maestro.core.tasks.simulation import fail_run, mark_run_completed, run_ffw_simulation
from net_maestro.core.tests.factories import (
    FFWPortRecordFactory,
    FFWResultFileFactory,
    FFWSimulationConfigFactory,
    FFWSwitchRecordFactory,
    FFWTerminalRecordFactory,
    RunFactory,
    SimulationPeRecordFactory,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper

    from net_maestro.core.models import FFWResultFile

pytestmark = pytest.mark.django_db

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

# Three VT samples 0.1 s apart, in ns.
TS = [1e8, 2e8, 3e8]


@pytest.fixture
def preset(tmp_path: Path, settings: SettingsWrapper) -> str:
    """Write one topology preset (switch 0 is A, switch 1 is B) and point at it."""
    settings.TOPOLOGY_DIR = tmp_path
    name = "ffw-fabric-2-site"
    (tmp_path / f"{name}.yaml").write_text(TOPOLOGY_YAML, encoding="utf-8")
    return name


def _ffw_run(topology_name: str, **run_fields: object) -> tuple[Run, FFWResultFile]:
    fields: dict[str, object] = {
        "status": RunStatus.COMPLETED,
        "simulation_type": SimulationType.FFW,
        **run_fields,
    }
    run = RunFactory.create(**fields)
    FFWSimulationConfigFactory.create(run=run, topology_name=topology_name)
    return run, FFWResultFileFactory.create(run=run)


def _switch_samples(
    result_file: FFWResultFile,
    switch_id: int,
    *,
    port_sent: Sequence[float],
    occupancy: Sequence[float] = (0, 0, 0),
    dropped: Sequence[float] = (0, 0, 0),
    pause_frames: Sequence[int] = (0, 0, 0),
    per_interval: float = 0.0,
    pause_ns: Sequence[float] = (0, 0, 0),
) -> None:
    """Add one switch's VT samples with a switch-facing port to the other switch."""
    for i, ts in enumerate(TS):
        record = FFWSwitchRecordFactory.create(
            result_file=result_file,
            switch_id=switch_id,
            ts=ts,
            shared_buffer_capacity_mbit=1000.0,
            shared_buffer_occupancy_mbit=occupancy[i],
            dropped_mbit=dropped[i],
            pause_frames_sent=pause_frames[i],
        )
        FFWPortRecordFactory.create(
            switch_record=record,
            port_index=0,
            is_terminal=False,
            target_index=1 - switch_id,
            port_sent_mbit=port_sent[i],
            port_capacity_mbit_per_interval=per_interval,
            port_pause_time_ns=pause_ns[i],
        )
        # A terminal-facing port sending far more than any link could: must be ignored.
        FFWPortRecordFactory.create(
            switch_record=record,
            port_index=1,
            is_terminal=True,
            target_index=0,
            port_sent_mbit=1e9,
        )


def _terminal_samples(
    result_file: FFWResultFile,
    terminal_id: int,
    *,
    generated: list[float],
    injected: list[float],
    received: list[float],
    backlog: list[float],
) -> None:
    for i, ts in enumerate(TS):
        FFWTerminalRecordFactory.create(
            result_file=result_file,
            terminal_id=terminal_id,
            ts=ts,
            generated_mbit=generated[i],
            sent_to_switch_mbit=injected[i],
            received_mbit=received[i],
            source_backlog_mbit=backlog[i],
        )


def _healthy_run(topology_name: str, **run_fields: object) -> Run:
    """Build a run whose volume balances and whose network drained.

    Generated 1501 = injected 1500 + final backlog 1; delivered 1490 + dropped 10 =
    injected, so nothing is in flight.
    """
    run, result_file = _ffw_run(topology_name, **run_fields)
    _terminal_samples(
        result_file,
        0,
        generated=[1000, 500, 1],
        injected=[800, 600, 100],
        received=[0, 600, 890],
        backlog=[200, 100, 1],
    )
    _switch_samples(
        result_file,
        0,
        occupancy=[100, 500, 0],
        dropped=[0, 10, 0],
        pause_frames=[1, 0, 2],
        port_sent=[0, 5000, 2000],
        pause_ns=[0, 5e8, 0],
    )
    _switch_samples(
        result_file,
        1,
        occupancy=[200, 0, 0],
        dropped=[0, 0, 0],
        pause_frames=[0, 0, 0],
        port_sent=[0, 1000, 1000],
    )
    return run


def _checks(summary: RunSummary) -> dict[str, bool]:
    return {check["key"]: check["ok"] for check in summary.health["checks"]}


class TestFFWMetrics:
    def test_sums_deltas_and_reads_gauges(self, preset: str) -> None:
        summary = compute_run_summary(_healthy_run(preset))

        assert summary is not None
        metrics = summary.metrics
        assert metrics["generated_mbit"] == 1501
        assert metrics["delivered_mbit"] == 1490
        assert metrics["dropped_mbit"] == 10
        assert metrics["delivered_frac"] == pytest.approx(1490 / 1501)
        # Backlog is a gauge: the last sample's value, not the sum (301) or max (200).
        assert metrics["end_backlog_mbit"] == 1
        assert metrics["pause_frames_sent"] == 3
        assert metrics["pause_time_s"] == pytest.approx(0.5)

    def test_buffer_occupancy_is_max_and_mean_of_the_ratio(self, preset: str) -> None:
        summary = compute_run_summary(_healthy_run(preset))

        assert summary is not None
        assert summary.metrics["peak_buffer_occupancy_frac"] == pytest.approx(0.5)
        assert summary.metrics["mean_buffer_occupancy_frac"] == pytest.approx(0.8 / 6)
        assert summary.details["peak_buffer_switch"] == "A"

    def test_bottleneck_is_the_busiest_switch_link(self, preset: str) -> None:
        summary = compute_run_summary(_healthy_run(preset))

        assert summary is not None
        # A → B sent 5000 Mbit in 0.1 s on a 100 Gbps link: half its capacity.
        assert summary.metrics["bottleneck_peak_utilization"] == pytest.approx(0.5)
        # 7000 Mbit over the 0.2 s from the first sample to the last.
        assert summary.metrics["bottleneck_mean_utilization"] == pytest.approx(0.35)
        assert summary.details["bottleneck_link"] == "A → B"

    def test_samples_shorter_than_a_fluid_interval_use_its_capacity(self, preset: str) -> None:
        """A whole 1 s interval's volume lands in one 0.1 s sample; that isn't 10x."""
        run, result_file = _ffw_run(preset)
        _switch_samples(result_file, 0, port_sent=[0, 50000, 0], per_interval=100000)
        _switch_samples(result_file, 1, port_sent=[0, 1000, 0])

        summary = compute_run_summary(run)

        assert summary is not None
        assert summary.metrics["bottleneck_peak_utilization"] == pytest.approx(0.5)
        assert summary.details["bottleneck_link"] == "A → B"

    def test_prefers_vt_over_gvt(self, preset: str) -> None:
        run = _healthy_run(preset)
        result_file = run.ffw_result_files.get()
        FFWSwitchRecordFactory.create(
            result_file=result_file, stats_type=FFWStatsType.GVT, dropped_mbit=999.0
        )
        FFWTerminalRecordFactory.create(
            result_file=result_file, stats_type=FFWStatsType.GVT, generated_mbit=999.0
        )

        summary = compute_run_summary(run)

        assert summary is not None
        assert summary.stats_type == FFWStatsType.VT
        assert summary.metrics["dropped_mbit"] == 10
        assert summary.metrics["generated_mbit"] == 1501

    def test_falls_back_to_gvt(self, preset: str) -> None:
        run, result_file = _ffw_run(preset)
        FFWSwitchRecordFactory.create(
            result_file=result_file, stats_type=FFWStatsType.GVT, dropped_mbit=7.0
        )
        FFWSwitchRecordFactory.create(
            result_file=result_file, stats_type=FFWStatsType.RT, dropped_mbit=5.0
        )

        summary = compute_run_summary(run)

        assert summary is not None
        assert summary.stats_type == FFWStatsType.GVT
        assert summary.metrics["dropped_mbit"] == 7

    def test_unreadable_topology_skips_links_without_failing(self, preset: str) -> None:
        run = _healthy_run(preset)
        run.ffw_configs.update(topology_name="gone")

        summary = compute_run_summary(run)

        assert summary is not None
        assert summary.metrics["bottleneck_peak_utilization"] is None
        assert summary.details["bottleneck_link"] is None
        assert summary.details["peak_buffer_switch"] == "0"
        topology_check = next(c for c in summary.health["checks"] if c["key"] == "topology")
        assert topology_check["ok"]
        assert "not readable" in topology_check["detail"]
        assert summary.health["ok"]


class TestHealth:
    def test_healthy_run_passes_every_check(self, preset: str) -> None:
        summary = compute_run_summary(_healthy_run(preset))

        assert summary is not None
        assert _checks(summary) == {
            "has_data": True,
            "conservation": True,
            "drained": True,
            "completed": True,
        }
        assert summary.health["ok"]
        conservation = next(c for c in summary.health["checks"] if c["key"] == "conservation")
        assert conservation["detail"].startswith("Generated 1.50 Gbit, delivered 1.49")

    def test_unbalanced_volume_and_backlog_fail(self, preset: str) -> None:
        run = _healthy_run(preset, status=RunStatus.FAILED)
        # Generated volume that neither left the source nor shows as backlog.
        _terminal_samples(
            run.ffw_result_files.get(),
            1,
            generated=[0, 0, 1000],
            injected=[0, 0, 0],
            received=[0, 0, 0],
            backlog=[0, 0, 500],
        )

        summary = compute_run_summary(run)

        assert summary is not None
        assert _checks(summary) == {
            "has_data": True,
            "conservation": False,
            "drained": False,
            "completed": False,
        }
        assert not summary.health["ok"]

    def test_volume_in_flight_means_not_drained(self, preset: str) -> None:
        run, result_file = _ffw_run(preset)
        _terminal_samples(
            result_file,
            0,
            generated=[100, 0, 0],
            injected=[100, 0, 0],
            received=[0, 50, 0],
            backlog=[0, 0, 0],
        )

        summary = compute_run_summary(run)

        assert summary is not None
        assert summary.details["in_flight_mbit"] == 50
        assert _checks(summary)["conservation"]
        assert not _checks(summary)["drained"]


class TestEngineMetrics:
    def test_absent_without_engine_rows(self, preset: str) -> None:
        summary = compute_run_summary(_healthy_run(preset))

        assert summary is not None
        assert "events_processed" not in summary.metrics
        assert summary.metrics["wall_time_s"] is None

    def test_sums_one_modes_deltas(self) -> None:
        start = timezone.now()
        run = RunFactory.create(
            status=RunStatus.COMPLETED,
            simulation_type=SimulationType.PHOLD,
            started_at=start,
            finished_at=start + timedelta(seconds=42),
        )
        gvt = SimulationFile.objects.create(run=run, file=ContentFile(b"", name="phold-gvt.bin"))
        rt = SimulationFile.objects.create(run=run, file=ContentFile(b"", name="phold-rt.bin"))
        SimulationPeRecordFactory.create(
            simulation_file=gvt, events_processed=100, events_rolled_back=10
        )
        SimulationPeRecordFactory.create(
            simulation_file=gvt, events_processed=50, events_rolled_back=0
        )
        # The RT file covers the same work; summing it too would double-count.
        SimulationPeRecordFactory.create(
            simulation_file=rt, events_processed=1000, events_rolled_back=500
        )

        summary = compute_run_summary(run)

        assert summary is not None
        assert summary.stats_type == ""
        assert summary.metrics["events_processed"] == 150
        assert summary.metrics["events_rolled_back"] == 10
        assert summary.metrics["efficiency_pct"] == pytest.approx(100 * (1 - 10 / 140))
        assert summary.metrics["wall_time_s"] == pytest.approx(42)
        assert _checks(summary) == {"has_data": True, "completed": True}


class TestComputeRunSummary:
    def test_empty_run_has_no_summary(self) -> None:
        run = RunFactory.create(status=RunStatus.COMPLETED)
        RunSummary.objects.create(run=run, metrics={"stale": 1})

        assert compute_run_summary(run) is None
        assert not RunSummary.objects.filter(run=run).exists()

    def test_recomputing_updates_the_one_row(self, preset: str) -> None:
        run = _healthy_run(preset)
        first = compute_run_summary(run)
        run.ffw_result_files.get().ffwswitchrecord_set.filter(ts=TS[1], switch_id=0).update(
            dropped_mbit=20
        )

        second = compute_run_summary(run)

        assert first is not None
        assert second is not None
        assert second.pk == first.pk
        assert RunSummary.objects.filter(run=run).count() == 1
        assert second.metrics["dropped_mbit"] == 20


class TestRegistry:
    def test_metrics_for_appends_engine_metrics(self) -> None:
        assert metrics_for(SimulationType.FFW, with_engine=False) == FFW_METRICS
        assert metrics_for(SimulationType.FFW, with_engine=True) == FFW_METRICS + ENGINE_METRICS
        assert metrics_for(SimulationType.PHOLD, with_engine=True) == ENGINE_METRICS

    def test_headline_metrics_are_registered(self) -> None:
        keys = {metric.key for metric in FFW_METRICS}
        assert set(HEADLINE_METRICS) <= keys

    def test_metrics_as_json(self) -> None:
        rows = metrics_as_json(FFW_METRICS[:2], {"generated_mbit": 5.0})

        assert rows[0] == {
            "key": "generated_mbit",
            "label": "Generated",
            "unit": "Mbit",
            "lower_is_better": None,
            "digits": 1,
            "value": 5.0,
        }
        assert rows[1]["value"] is None
        assert "value" not in metrics_as_json(FFW_METRICS[:1])[0]


class TestTaskHooks:
    @pytest.fixture(autouse=True)
    def _output_dir(self, tmp_path: Path, settings: SettingsWrapper) -> None:
        settings.FFW_OUTPUT_DIR = str(tmp_path / "out")

    def test_mark_run_completed_times_and_summarizes(self, preset: str) -> None:
        run = _healthy_run(preset, status=RunStatus.RUNNING, started_at=timezone.now())

        mark_run_completed(run.id)

        run.refresh_from_db()
        assert run.status == RunStatus.COMPLETED
        assert run.finished_at is not None
        assert run.wall_time_s is not None
        assert run.summary.health["ok"]

    def test_fail_run_records_the_reason(self) -> None:
        run = RunFactory.create(status=RunStatus.RUNNING)

        fail_run(run.id, "ingestion task 7 failed: boom")

        run.refresh_from_db()
        assert run.status == RunStatus.FAILED
        assert run.finished_at is not None
        assert run.failure_reason == "ingestion task 7 failed: boom"

    @mock.patch(
        "net_maestro.core.tasks.simulation.vt_sampling_for",
        mock.Mock(return_value=mock.Mock(interval_ns=100_000_000, end_ns=42_000_000_000)),
    )
    @mock.patch("net_maestro.core.tasks.simulation.write_run_inputs", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model")
    def test_ffw_failure_keeps_the_stderr_tail(self, execute: mock.Mock, preset: str) -> None:
        stderr = "\n".join(f"line {i}" for i in range(30))
        execute.side_effect = subprocess.CalledProcessError(1, ["mpirun"], stderr=stderr)
        run = RunFactory.create(status=RunStatus.PENDING, failure_reason="old")

        run_ffw_simulation(run_id=run.id, topology_name=preset)

        run.refresh_from_db()
        assert run.status == RunStatus.FAILED
        assert run.started_at is not None
        assert run.finished_at is not None
        assert run.finished_at >= run.started_at
        assert "line 29" in run.failure_reason
        assert "line 10" in run.failure_reason
        assert "line 9\n" not in run.failure_reason
        assert run.failure_reason.startswith("Exited with code 1")

    @mock.patch(
        "net_maestro.core.tasks.simulation.vt_sampling_for",
        mock.Mock(return_value=mock.Mock(interval_ns=100_000_000, end_ns=42_000_000_000)),
    )
    @mock.patch("net_maestro.core.tasks.simulation.write_run_inputs", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model")
    def test_ffw_other_errors_keep_the_repr(self, execute: mock.Mock, preset: str) -> None:
        execute.side_effect = FileNotFoundError("no ross-stats-model.bin")
        run = RunFactory.create(status=RunStatus.PENDING)

        run_ffw_simulation(run_id=run.id, topology_name=preset)

        run.refresh_from_db()
        assert run.status == RunStatus.FAILED
        assert run.failure_reason == "FileNotFoundError('no ross-stats-model.bin')"

    @mock.patch("net_maestro.core.tasks.simulation.compute_run_summary")
    @mock.patch("net_maestro.core.tasks.simulation.run_ffw_ingest_task", mock.Mock())
    @mock.patch(
        "net_maestro.core.tasks.simulation.vt_sampling_for",
        mock.Mock(return_value=mock.Mock(interval_ns=100_000_000, end_ns=42_000_000_000)),
    )
    @mock.patch("net_maestro.core.tasks.simulation.write_run_inputs", mock.Mock())
    @mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model")
    def test_ffw_success_summarizes_and_survives_a_summary_error(
        self,
        execute: mock.Mock,
        summarize: mock.Mock,
        preset: str,
        tmp_path: Path,
    ) -> None:
        stats_dir = tmp_path / "stats"
        stats_dir.mkdir()
        for name in FFW_STATS_FILES:
            (stats_dir / name).write_bytes(b"")
        execute.return_value = stats_dir
        summarize.side_effect = ValueError("stats bug")
        run = RunFactory.create(status=RunStatus.PENDING)

        run_ffw_simulation(run_id=run.id, topology_name=preset)

        run.refresh_from_db()
        summarize.assert_called_once()
        assert run.status == RunStatus.COMPLETED
        assert run.failure_reason == ""
        assert run.wall_time_s is not None
