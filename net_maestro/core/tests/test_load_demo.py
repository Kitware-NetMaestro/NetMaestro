"""Tests for the load_demo management command, against the seed in data/webinar."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from django.conf import settings as django_settings
from django.core.management import call_command
import pytest

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import Ensemble, Run

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper

pytestmark = pytest.mark.django_db

FABRIC = "fluid-flow-wan-fabric-5-site"


@pytest.fixture
def topologies(tmp_path: Path, settings: SettingsWrapper) -> Path:
    """Point the topology directory at a copy holding only the FABRIC preset."""
    shutil.copy(django_settings.BASE_DIR / "data" / "topologies" / f"{FABRIC}.yaml", tmp_path)
    settings.TOPOLOGY_DIR = tmp_path
    return tmp_path


def test_loads_the_baseline_and_the_ensemble(
    topologies: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    call_command("load_demo")

    runs = Run.objects.all()
    assert runs.count() == 7
    assert {run.status for run in runs} == {RunStatus.COMPLETED}
    assert all(run.summary.health["ok"] for run in runs)
    assert all(run.ffw_switch_steps.exists() for run in runs)

    ensemble = Ensemble.objects.get()
    assert ensemble.status == RunStatus.COMPLETED
    dropped = {
        run.member_index: round(run.summary.metrics["dropped_mbit"]) for run in ensemble.members
    }
    assert dropped == {1: 188692, 2: 269693, 3: 327820, 4: 156122, 5: 193801, 6: 245625}
    # The members whose topology the sweep changed got topology files of their own.
    assert len(list(topologies.glob(f"{FABRIC}-sweep-{ensemble.id}-*.yaml"))) == 5

    out = capsys.readouterr().out
    assert "loaded 'FABRIC baseline'" in out
    assert "with 6 members" in out


def test_skips_what_is_already_loaded(
    topologies: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    call_command("load_demo")
    call_command("load_demo")

    assert Run.objects.count() == 7
    assert Ensemble.objects.count() == 1
    out = capsys.readouterr().out
    assert "Run 'FABRIC baseline': already loaded" in out
    assert "Ensemble 'FABRIC buffer vs bottleneck': already loaded" in out
