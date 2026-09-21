"""Tests for the placeholder component models API endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from net_maestro.core.tests.factories import UserFactory

if TYPE_CHECKING:
    from rest_framework.test import APIClient


@pytest.mark.django_db
class TestComponentModelListAPI:
    url = "/api/v1/component-models/"

    @pytest.fixture(autouse=True)
    def _auth(self, api_client: APIClient) -> None:
        user = UserFactory.create()
        api_client.force_authenticate(user=user)
        self.client = api_client

    def test_returns_placeholder_switches(self) -> None:
        response = self.client.get(self.url)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = [c["name"] for c in data]
        assert "Core WAN Switch" in names
        assert "Edge WAN Switch" in names

    def test_filter_by_base_model(self) -> None:
        response = self.client.get(self.url, {"base_model": "fluid-flow-wan-switch-lp"})

        data = response.json()
        assert len(data) == 2
        assert all(c["base_model"] == "fluid-flow-wan-switch-lp" for c in data)

    def test_filter_nonexistent_base_model(self) -> None:
        response = self.client.get(self.url, {"base_model": "nonexistent"})

        assert response.status_code == 200
        assert response.json() == []

    def test_response_shape(self) -> None:
        response = self.client.get(self.url)
        item = response.json()[0]

        assert "id" in item
        assert "name" in item
        assert "base_model" in item
        assert "component_type" in item
        assert "description" in item
        assert "parameters" in item
        assert "switch_buffer" in item["parameters"]
        assert "terminal_bandwidth" in item["parameters"]
