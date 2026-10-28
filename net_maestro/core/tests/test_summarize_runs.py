"""Tests for the summarize_runs management command."""

from __future__ import annotations

from django.core.management import call_command
import djclick as click
import pytest

from net_maestro.core.constants import FFWStatsType, RunStatus
from net_maestro.core.models import Run, RunSummary
from net_maestro.core.tests.factories import (
    FFWResultFileFactory,
    FFWSwitchRecordFactory,
    RunFactory,
)

pytestmark = pytest.mark.django_db


def _run_with_drops(dropped: float, status: str = RunStatus.COMPLETED) -> Run:
    run = RunFactory.create(status=status)
    FFWSwitchRecordFactory.create(
        result_file=FFWResultFileFactory.create(run=run),
        stats_type=FFWStatsType.VT,
        dropped_mbit=dropped,
    )
    return run


def test_summarizes_the_named_runs(capsys: pytest.CaptureFixture[str]) -> None:
    named = _run_with_drops(3.0)
    other = _run_with_drops(4.0)

    call_command("summarize_runs", str(named.id))

    assert RunSummary.objects.get(run=named).metrics["dropped_mbit"] == 3
    assert not RunSummary.objects.filter(run=other).exists()
    out = capsys.readouterr().out
    assert f"Run {named.id}: Dropped 3.0 Mbit" in out


def test_all_covers_completed_runs_only() -> None:
    done = _run_with_drops(1.0)
    running = _run_with_drops(1.0, status=RunStatus.RUNNING)

    call_command("summarize_runs", "--all")

    assert RunSummary.objects.filter(run=done).exists()
    assert not RunSummary.objects.filter(run=running).exists()


def test_reports_runs_without_data(capsys: pytest.CaptureFixture[str]) -> None:
    empty = RunFactory.create(status=RunStatus.COMPLETED)

    call_command("summarize_runs", str(empty.id), "999999")

    out = capsys.readouterr().out
    assert f"Run {empty.id}: no data" in out
    assert "Run 999999: not found" in out


def test_skips_existing_summaries_unless_forced(capsys: pytest.CaptureFixture[str]) -> None:
    run = _run_with_drops(2.0)
    RunSummary.objects.create(run=run, metrics={"dropped_mbit": 99})

    call_command("summarize_runs", str(run.id))
    assert RunSummary.objects.get(run=run).metrics["dropped_mbit"] == 99
    assert "already summarized" in capsys.readouterr().out

    call_command("summarize_runs", str(run.id), "--force")
    assert RunSummary.objects.get(run=run).metrics["dropped_mbit"] == 2
    assert RunSummary.objects.filter(run=run).count() == 1


def test_requires_ids_or_all() -> None:
    with pytest.raises(click.UsageError):
        call_command("summarize_runs")
