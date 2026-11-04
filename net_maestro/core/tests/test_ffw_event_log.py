"""Tests for the FFW model's per-step logs: the parser, the ingest, and the task hook.

The fixture logs are a two-switch run (A is switch 0, B is switch 1, 100 Gbit per
step on every port) shaped like the model's output. On A's port to B, step 1 runs
60 + 30 Gbit of sends and a 20 Gbit PAUSE drain: 110 Gbit by the step it ran in, more
than the link can carry, but the drain is charged to step 2, which then holds
20 + 70 = 90.
"""

from __future__ import annotations

from dataclasses import astuple
import logging
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from net_maestro.core.constants import FFWModelLogKind, RunStatus, SimulationType
from net_maestro.core.models import FFWLinkStepRecord, FFWModelLog, FFWSwitchStepRecord
from net_maestro.core.parsers.ffw_event_log import (
    EventLogError,
    LinkStep,
    link_steps,
    sent_per_link_from_switch_log,
    switch_steps,
)
from net_maestro.core.services.ffw import FFW_STATS_FILES
from net_maestro.core.summaries import SOURCE_MODEL_LOG, compute_run_summary
from net_maestro.core.tasks.ingest_ffw_logs import ingest_ffw_logs
from net_maestro.core.tasks.simulation import run_ffw_simulation
from net_maestro.core.tests.factories import (
    FFWResultFileFactory,
    FFWSimulationConfigFactory,
    FFWSwitchRecordFactory,
    RunFactory,
)
from net_maestro.core.topology import SWITCH_LP_NAME, TERMINAL_LP_NAME

if TYPE_CHECKING:
    from pytest_django.fixtures import SettingsWrapper

    from net_maestro.core.models import Run

SEGMENT_HEADER = (
    "interval,event,switch,switch_name,port,target_type,target_index,flow_id,"
    "source_terminal,destination_terminal,creation_interval,age_intervals,capacity_gbit,"
    "queued_before_gbit,send_gbit,remaining_after_gbit,dropped_gbit\n"
)
SEGMENT_LOG = SEGMENT_HEADER + (
    "1,stage_arrival,0,A,0,switch,1,7,0,2,0,1,100,0,0,60,0\n"
    "1,allocate_send_arrival,0,A,0,switch,1,7,0,2,0,1,100,0,60,0,0\n"
    "1,allocate_send_buffered,0,A,0,switch,1,8,1,2,0,1,100,0.4,30,1.6,0\n"
    "1,enqueue_residual,0,A,0,switch,1,8,1,2,0,1,100,0.4,0,1.6,0\n"
    "1,allocate_send_pause_drain,0,A,0,switch,1,8,1,2,0,1,100,1.6,20,0,0\n"
    "1,allocate_send_arrival,0,A,1,terminal,0,9,2,0,0,1,100,0,50,0,0\n"
    "1,drop_shared_buffer_overflow,0,A,1,terminal,0,9,2,0,0,1,100,0,0,0,0.1\n"
    "1,allocate_send_arrival,1,B,0,switch,0,10,2,0,0,1,100,0,10,0,0\n"
    "1,some_future_event,0,A,0,switch,1,11,0,2,0,1,100,0,999,0,0\n"
    "2,allocate_send_buffered,0,A,0,switch,1,12,0,2,1,1,100,0,70,0,0\n"
)

SWITCH_HEADER = (
    "interval,event,switch,switch_name,port,target_type,target_index,capacity_gbit,"
    "queued_before_gbit,sent_gbit,queued_after_gbit,shared_queued_before_gbit,"
    "shared_queued_after_gbit,shared_buffer_gbit,dropped_gbit,active_queue_entries\n"
)
SWITCH_LOG = SWITCH_HEADER + (
    "1,egress,0,A,0,switch,1,100,0,90,1.6,0.4,1.6,2,0,1\n"
    "1,egress,0,A,1,terminal,0,100,0,50,0,1.6,2,2,0.1,0\n"
    "1,egress,0,A,0,switch,1,100,1.6,20,0,2,1,2,0,0\n"
    "2,egress,0,A,0,switch,1,100,0,70,0,1,0.5,2,0,0\n"
    "1,egress,1,B,0,switch,0,100,0,10,0,0.2,0.1,2,0,0\n"
    "1,drop_no_route,1,B,-1,switch,-1,0,0,0,0,0.2,0.2,2,0.05,0\n"
)

CONFIG_YAML = """sections:
  fluid_flow_wan:
    topology_yaml_file: two-site.yaml
    interval_seconds: 1
    num_send_intervals: 2
    num_drain_intervals: 2
    terminal_log_path: logs/terminal-events.csv
    switch_log_path: logs/switch-events.csv
    fluid_segment_log_path: logs/fluid-segment-events.csv
"""

TOPOLOGY_YAML = """
topology:
  switches:
    A:
      terminals: 1
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "2 Gb"
      connections:
        B: "100 Gbps"
    B:
      terminals: 1
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "2 Gb"
      connections:
        A: "100 Gbps"
"""
PRESET = "ffw-fabric-2-site"

TEMPLATE_YAML = f"""topology:
  groups:
    FLUID_FLOW_WAN_GRP:
      repetitions: 1
      lps:
        {SWITCH_LP_NAME}: 5
        {TERMINAL_LP_NAME}: 10
{CONFIG_YAML}"""


def _write_logs(inputs: Path, *, switch: bool = True, segment: bool = True) -> None:
    (inputs / "logs").mkdir(parents=True, exist_ok=True)
    if switch:
        (inputs / "logs" / "switch-events.csv").write_text(SWITCH_LOG, encoding="utf-8")
    if segment:
        (inputs / "logs" / "fluid-segment-events.csv").write_text(SEGMENT_LOG, encoding="utf-8")


def _config(tmp_path: Path, **logs: bool) -> Path:
    inputs = tmp_path / "inputs"
    _write_logs(inputs, **logs)
    path = inputs / "traffic.yaml"
    path.write_text(CONFIG_YAML, encoding="utf-8")
    return path


class TestLinkSteps:
    def test_sums_sends_per_charged_step_in_mbit(self) -> None:
        steps = link_steps(SEGMENT_LOG.splitlines(keepends=True))

        # (switch, port, to a terminal, target, step, sent, capacity)
        assert [astuple(step) for step in steps] == [
            (0, 0, False, 1, 1, 90_000.0, 100_000.0),
            # The step-1 drain lands in step 2.
            (0, 0, False, 1, 2, 90_000.0, 100_000.0),
            (0, 1, True, 0, 1, 50_000.0, 100_000.0),
            (1, 0, False, 0, 1, 10_000.0, 100_000.0),
        ]
        assert all(step.sent_mbit <= step.capacity_mbit for step in steps)

    def test_by_the_step_it_ran_in_the_link_is_over_capacity(self) -> None:
        """What the samples see: why the drain has to be moved."""
        lines = SEGMENT_LOG.replace("allocate_send_pause_drain", "allocate_send_buffered")

        by_time = link_steps(lines.splitlines(keepends=True))

        assert by_time[0].step == 1
        assert by_time[0].sent_mbit == pytest.approx(110_000.0)
        assert by_time[0].sent_mbit > by_time[0].capacity_mbit

    def test_totals_match_the_switch_logs_sent(self) -> None:
        totals: dict[tuple[int, int], float] = {}
        for step in link_steps(SEGMENT_LOG.splitlines(keepends=True)):
            key = (step.switch_id, step.port)
            totals[key] = totals.get(key, 0.0) + step.sent_mbit

        switch_totals = sent_per_link_from_switch_log(SWITCH_LOG.splitlines(keepends=True))

        assert totals.keys() == switch_totals.keys()
        for key, total in totals.items():
            assert total == pytest.approx(switch_totals[key])

    def test_rounding_overshoot_is_clamped_and_a_real_one_kept(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The log's six digits can sum past capacity; the model's charge never does."""
        header = "interval,event,switch,port,target_type,target_index,capacity_gbit,send_gbit\n"
        rows = (
            "1,allocate_send_arrival,0,0,switch,1,100,85.1890\n"
            "1,allocate_send_buffered,0,0,switch,1,100,14.8112\n"
            "1,allocate_send_arrival,1,0,switch,0,100,101\n"
        )

        with caplog.at_level(logging.WARNING):
            rounded, real = link_steps([header, *rows.splitlines(keepends=True)])

        assert rounded.sent_mbit == rounded.capacity_mbit
        assert real.sent_mbit == pytest.approx(101_000.0)
        assert "exceed capacity" in caplog.text

    def test_reads_columns_by_name_and_unit(self) -> None:
        log = (
            "event,interval,send_mbit,switch,port,capacity_mbit,target_type,target_index\n"
            "allocate_send_arrival,3,250.5,2,1,1000,switch,0\n"
        )

        assert link_steps(log.splitlines(keepends=True)) == [
            LinkStep(
                switch_id=2,
                port=1,
                target_is_terminal=False,
                target_index=0,
                step=3,
                sent_mbit=250.5,
                capacity_mbit=1000.0,
            )
        ]

    def test_empty_file_and_header_only(self) -> None:
        assert link_steps([]) == []
        assert link_steps([SEGMENT_HEADER]) == []

    def test_missing_column_is_an_error(self) -> None:
        with pytest.raises(EventLogError, match="send"):
            link_steps(["interval,event,switch,port,target_type,target_index,capacity_gbit\n"])


class TestSwitchSteps:
    def test_peak_buffer_and_drops_per_step(self) -> None:
        steps = switch_steps(SWITCH_LOG.splitlines(keepends=True))

        # (switch, step, peak, buffer, dropped)
        assert [astuple(step) for step in steps] == [
            # The terminal egress left the buffer full (after = 2 Gbit).
            (0, 1, 2000.0, 2000.0, pytest.approx(100.0)),
            (0, 2, 1000.0, 2000.0, 0.0),
            # The no-route drop counts toward the step's drops.
            (1, 1, 200.0, 2000.0, pytest.approx(50.0)),
        ]

    def test_empty_file(self) -> None:
        assert switch_steps([]) == []
        assert switch_steps([SWITCH_HEADER]) == []


@pytest.mark.django_db
class TestIngest:
    def test_builds_records_and_keeps_the_logs(self, tmp_path: Path) -> None:
        run = RunFactory.create(simulation_type=SimulationType.FFW)

        counts = ingest_ffw_logs(run, _config(tmp_path))

        assert counts == {"switch_steps": 3, "link_steps": 4}
        logs = {log.kind: log for log in run.ffw_model_logs.all()}
        assert set(logs) == {FFWModelLogKind.SWITCH, FFWModelLogKind.FLUID_SEGMENT}
        assert all(log.num_steps == 4 and log.interval_seconds == 1.0 for log in logs.values())
        drain_step = FFWLinkStepRecord.objects.get(run=run, switch_id=0, port=0, step=2)
        assert drain_step.step_start_s == 2.0
        assert drain_step.sent_mbit == pytest.approx(90_000.0)
        peak = FFWSwitchStepRecord.objects.get(run=run, switch_id=0, step=1)
        assert peak.peak_occupancy_mbit == pytest.approx(2000.0)

    def test_rerun_replaces(self, tmp_path: Path) -> None:
        run = RunFactory.create(simulation_type=SimulationType.FFW)
        config = _config(tmp_path)
        ingest_ffw_logs(run, config)

        ingest_ffw_logs(run, config)

        assert run.ffw_model_logs.count() == 2
        assert run.ffw_link_steps.count() == 4
        assert run.ffw_switch_steps.count() == 3

    def test_a_missing_log_is_a_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        run = RunFactory.create(simulation_type=SimulationType.FFW)
        config = _config(tmp_path)
        ingest_ffw_logs(run, config)
        (config.parent / "logs" / "fluid-segment-events.csv").unlink()

        with caplog.at_level(logging.WARNING):
            counts = ingest_ffw_logs(run, config)

        assert counts == {"switch_steps": 3, "link_steps": 0}
        assert "fluid-segment events" in caplog.text
        # The earlier run's link records went with it.
        assert not run.ffw_link_steps.exists()
        assert list(run.ffw_model_logs.values_list("kind", flat=True)) == [FFWModelLogKind.SWITCH]


@pytest.fixture
def preset(tmp_path: Path, settings: SettingsWrapper) -> str:
    settings.TOPOLOGY_DIR = tmp_path / "topologies"
    settings.TOPOLOGY_DIR.mkdir()
    (settings.TOPOLOGY_DIR / f"{PRESET}.yaml").write_text(TOPOLOGY_YAML, encoding="utf-8")
    template = tmp_path / "template" / "traffic.yaml"
    template.parent.mkdir()
    template.write_text(TEMPLATE_YAML, encoding="utf-8")
    settings.FFW_CONFIG_PATH = str(template)
    settings.FFW_OUTPUT_DIR = str(tmp_path / "out")
    return PRESET


@pytest.mark.django_db
def test_summary_reads_the_log_through_ingest(preset: str, tmp_path: Path) -> None:
    """From the CSVs to the summary: full buffer, utilization charged per step."""
    run = RunFactory.create(status=RunStatus.COMPLETED, simulation_type=SimulationType.FFW)
    FFWSimulationConfigFactory.create(run=run, topology_name=preset)
    # The sample the summary would otherwise go by: half full.
    FFWSwitchRecordFactory.create(
        result_file=FFWResultFileFactory.create(run=run),
        ts=1.5e9,
        shared_buffer_capacity_mbit=2000.0,
        shared_buffer_occupancy_mbit=1000.0,
    )
    ingest_ffw_logs(run, _config(tmp_path))

    summary = compute_run_summary(run)

    assert summary is not None
    assert summary.metrics["peak_buffer_occupancy_frac"] == pytest.approx(1.0)
    assert summary.details["peak_buffer_switch"] == "A"
    assert summary.details["occupancy_source"] == SOURCE_MODEL_LOG
    # 110 Gbit ran in step 1, but only 90 was charged to it; the terminal port's
    # 50 Gbit is not a switch-to-switch link.
    assert summary.metrics["bottleneck_peak_utilization"] == pytest.approx(0.9)
    assert summary.metrics["bottleneck_peak_utilization"] <= 1.0 + 1e-9
    # 180 Gbit over 4 steps of 100.
    assert summary.metrics["bottleneck_mean_utilization"] == pytest.approx(0.45)
    assert summary.details["bottleneck_link"] == "A → B"
    assert summary.details["utilization_source"] == SOURCE_MODEL_LOG


@pytest.mark.django_db
class TestTaskHook:
    @pytest.fixture
    def stats_dir(self, tmp_path: Path) -> Path:
        stats_dir = tmp_path / "stats"
        stats_dir.mkdir()
        for name in FFW_STATS_FILES:
            (stats_dir / name).write_bytes(b"")
        return stats_dir

    def _run(self, preset: str, stats_dir: Path, **logs: bool) -> Run:
        def execute(**kwargs: object) -> Path:
            _write_logs(Path(str(kwargs["working_dir"])), **logs)
            return stats_dir

        run = RunFactory.create(status=RunStatus.PENDING)
        with (
            mock.patch("net_maestro.core.tasks.simulation.run_ffw_ingest_task"),
            mock.patch("net_maestro.core.tasks.simulation.compute_run_summary"),
            mock.patch("net_maestro.core.tasks.simulation.execute_ffw_model", side_effect=execute),
        ):
            run_ffw_simulation(run_id=run.id, topology_name=preset)
        run.refresh_from_db()
        return run

    def test_stores_the_logs_and_builds_records(self, preset: str, stats_dir: Path) -> None:
        run = self._run(preset, stats_dir)

        assert run.status == RunStatus.COMPLETED
        assert FFWModelLog.objects.filter(run=run).count() == 2
        assert run.ffw_link_steps.count() == 4
        assert run.ffw_switch_steps.count() == 3

    def test_missing_logs_leave_the_run_completed(self, preset: str, stats_dir: Path) -> None:
        run = self._run(preset, stats_dir, switch=False, segment=False)

        assert run.status == RunStatus.COMPLETED
        assert not run.ffw_model_logs.exists()
        assert not run.ffw_link_steps.exists()
