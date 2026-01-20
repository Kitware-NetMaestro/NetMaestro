"""Smoke tests for data API endpoints.

Note: Tests require sample data files to be present in data/ directories.
If files are missing, endpoints will return 404 (which will fail these tests).
"""

from __future__ import annotations

import json

import pytest
from rest_framework.test import APIClient


@pytest.mark.parametrize('category', ['event', 'model', 'ross'])
@pytest.mark.django_db
def test_data_endpoints_smoke(api_client: APIClient, category: str) -> None:
    """Smoke test for data API endpoints (event, model, ross).

    Verifies that each data endpoint:
    1. Returns HTTP 200 OK
    2. Returns valid JSON
    3. Has 'columns' list in response
    4. Has 'data' list in response

    This test is parametrized to run once for each category (event, model, ross).

    Args:
        api_client: Authenticated API client fixture from conftest.py
        category: Data category to test ('event', 'model', or 'ross')

    Raises:
        AssertionError: If endpoint returns non-200 status, invalid JSON,
            or missing expected structure
    """
    url = f'/api/v1/data/{category}'
    resp = api_client.get(url)

    assert resp.status_code == 200, f'{url} -> {resp.status_code}'

    try:
        payload = json.loads(resp.content.decode('utf-8'))
    except Exception as e:  # noqa: BLE001
        pytest.fail(f'{url} -> 200 but invalid JSON: {e}')

    assert isinstance(payload.get('columns'), list), 'missing/invalid "columns" list'
    assert isinstance(payload.get('data'), list), 'missing/invalid "data" list'
