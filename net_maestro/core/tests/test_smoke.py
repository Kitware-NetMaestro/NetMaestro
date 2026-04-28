"""Smoke tests for run-based data API endpoints.

Tests create database records via factories and verify that the
/api/v1/runs/<run_id>/<category> endpoints return the expected structure.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from rest_framework.test import APIClient

from net_maestro.core.tests.factories import (
    EventRecordFactory,
    ModelRecordFactory,
    RunFactory,
    SimulationPeRecordFactory,
    UserFactory,
)


def _assert_data_response(resp, url: str) -> None:
    """Assert standard {columns, data} response shape."""
    assert resp.status_code == 200, f"{url} -> {resp.status_code}"
    payload = json.loads(resp.content.decode("utf-8"))
    assert isinstance(payload.get("columns"), list), 'missing/invalid "columns"'
    assert isinstance(payload.get("data"), list), 'missing/invalid "data"'
    assert len(payload["data"]) > 0, "expected at least one record"


@pytest.mark.django_db
def test_run_ross_endpoint(api_client: APIClient) -> None:
    """Smoke test: GET /api/v1/runs/<run_id>/ross returns PE records."""
    run = RunFactory.create()
    SimulationPeRecordFactory.create(simulation_file__result=run.result)
    user = UserFactory.create()
    api_client.force_authenticate(user=user)

    url = f"/api/v1/runs/{run.pk}/ross"
    _assert_data_response(api_client.get(url), url)


@pytest.mark.django_db
def test_run_event_endpoint(api_client: APIClient) -> None:
    """Smoke test: GET /api/v1/runs/<run_id>/event returns event records."""
    run = RunFactory.create()
    EventRecordFactory.create(event_file__result=run.result)
    user = UserFactory.create()
    api_client.force_authenticate(user=user)

    url = f"/api/v1/runs/{run.pk}/event"
    _assert_data_response(api_client.get(url), url)


@pytest.mark.django_db
def test_run_model_endpoint(api_client: APIClient) -> None:
    """Smoke test: GET /api/v1/runs/<run_id>/model returns model records."""
    run = RunFactory.create()
    ModelRecordFactory.create(model_file__result=run.result)
    user = UserFactory.create()
    api_client.force_authenticate(user=user)

    url = f"/api/v1/runs/{run.pk}/model"
    _assert_data_response(api_client.get(url), url)
