from __future__ import annotations

import json

import pytest
from rest_framework.test import APIClient


@pytest.mark.parametrize('kind', ['event', 'model', 'ross'])
@pytest.mark.django_db
def test_data_endpoints_smoke(api_client: APIClient, kind: str) -> None:
    url = f'/api/v1/data/{kind}'
    resp = api_client.get(url)

    assert resp.status_code == 200, f'{url} -> {resp.status_code}'

    try:
        payload = json.loads(resp.content.decode('utf-8'))
    except Exception as e:  # noqa: BLE001
        pytest.fail(f'{url} -> 200 but invalid JSON: {e}')

    assert isinstance(payload.get('columns'), list), 'missing/invalid "columns" list'
    assert isinstance(payload.get('data'), list), 'missing/invalid "data" list'
