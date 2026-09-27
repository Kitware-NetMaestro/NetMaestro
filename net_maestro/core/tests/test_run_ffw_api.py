"""Tests for the FFW run data endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from net_maestro.core.constants import FFWStatsType, SimulationType
from net_maestro.core.models import FFWResultFile, FFWTerminalRecord, Run
from net_maestro.core.tests.factories import UserFactory

if TYPE_CHECKING:
    from rest_framework.test import APIClient


@pytest.mark.django_db
def test_infinite_gvt_is_returned_as_null(api_client: APIClient) -> None:
    """ROSS reports GVT as infinity once a run finishes; JSON has no infinity."""
    api_client.force_authenticate(user=UserFactory.create())
    run = Run.objects.create(name="ffw", simulation_type=SimulationType.FFW)
    result_file = FFWResultFile.objects.create(run=run, file="results/ross-stats-model.bin")
    FFWTerminalRecord.objects.create(
        result_file=result_file,
        stats_type=FFWStatsType.GVT,
        ts=17_000_000_000,
        gvt=float("inf"),
        peid=0,
        kpid=0,
        lpid=8,
        terminal_id=0,
    )

    resp = api_client.get(f"/api/v1/runs/{run.id}/ffw-terminals")

    assert resp.status_code == 200
    assert resp.json()["data"][0]["gvt"] is None
