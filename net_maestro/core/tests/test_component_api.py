"""Tests for the component models API endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from net_maestro.core.models import ComponentModel
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

    def test_empty_list(self) -> None:
        response = self.client.get(self.url)

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_all_components(self) -> None:
        ComponentModel.objects.create(
            name="Switch A",
            base_model="fluid-flow-wan-switch-lp",
            component_type="switch",
            engine="PDES (CODES)",
            parameters={"switch_buffer": "64", "terminal_bandwidth": "100"},
        )
        ComponentModel.objects.create(
            name="Switch B",
            base_model="fluid-flow-wan-switch-lp",
            component_type="switch",
            engine="PDES (CODES)",
            parameters={"switch_buffer": "128", "terminal_bandwidth": "200"},
        )

        response = self.client.get(self.url)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = [c["name"] for c in data]
        assert names == ["Switch A", "Switch B"]

    def test_filter_by_base_model(self) -> None:
        ComponentModel.objects.create(
            name="A Switch",
            base_model="fluid-flow-wan-switch-lp",
            component_type="switch",
            engine="PDES (CODES)",
        )
        ComponentModel.objects.create(
            name="A Host",
            base_model="nw-lp",
            component_type="host",
            engine="PDES (CODES)",
        )

        response = self.client.get(self.url, {"base_model": "fluid-flow-wan-switch-lp"})

        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "A Switch"

    def test_response_shape(self) -> None:
        ComponentModel.objects.create(
            name="Core Switch",
            base_model="fluid-flow-wan-switch-lp",
            component_type="switch",
            engine="PDES (CODES)",
            description="A core switch",
            parameters={"switch_buffer": "64", "terminal_bandwidth": "100"},
        )

        response = self.client.get(self.url)
        item = response.json()[0]

        assert item["id"] is not None
        assert item["name"] == "Core Switch"
        assert item["base_model"] == "fluid-flow-wan-switch-lp"
        assert item["component_type"] == "switch"
        assert item["description"] == "A core switch"
        assert item["parameters"] == {
            "switch_buffer": "64",
            "terminal_bandwidth": "100",
        }

    def test_null_parameters_returns_empty_dict(self) -> None:
        ComponentModel.objects.create(
            name="Bare Switch",
            base_model="fluid-flow-wan-switch-lp",
            component_type="switch",
            engine="PDES (CODES)",
            parameters=None,
        )

        response = self.client.get(self.url)

        assert response.json()[0]["parameters"] == {}

    def test_ordered_by_name(self) -> None:
        ComponentModel.objects.create(
            name="Zebra",
            base_model="fluid-flow-wan-switch-lp",
            component_type="switch",
            engine="PDES (CODES)",
        )
        ComponentModel.objects.create(
            name="Alpha",
            base_model="fluid-flow-wan-switch-lp",
            component_type="switch",
            engine="PDES (CODES)",
        )

        response = self.client.get(self.url)
        names = [c["name"] for c in response.json()]
        assert names == ["Alpha", "Zebra"]
