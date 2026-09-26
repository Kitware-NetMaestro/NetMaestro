"""Tests for custom component views and form."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from django.urls import reverse
import pytest

from net_maestro.core.models import ComponentModel

if TYPE_CHECKING:
    from django.test import Client


@pytest.mark.django_db
class TestComponentModelForm:
    """Test ComponentModelForm validation and clean logic."""

    def test_valid_switch_submission(self, client: Client) -> None:
        form_data = {
            "name": "My Switch",
            "base_model": "fluid-flow-wan-switch-lp",
            "component_type": "switch",
            "engine": "PDES (CODES)",
            "description": "",
            "parameters": json.dumps({"switch_buffer": "64", "terminal_bandwidth": "100"}),
        }

        response = client.post(reverse("custom-component-create"), data=form_data)

        assert response.status_code == 302
        component = ComponentModel.objects.get(name="My Switch")
        assert component.base_model == "fluid-flow-wan-switch-lp"
        assert component.component_type == "switch"
        assert component.parameters == {
            "switch_buffer": "64",
            "terminal_bandwidth": "100",
        }

    def test_missing_base_model_shows_error(self, client: Client) -> None:
        form_data = {
            "name": "Bad Component",
            "base_model": "",
            "component_type": "",
            "engine": "",
            "parameters": "{}",
        }

        response = client.post(reverse("custom-component-create"), data=form_data)

        assert response.status_code == 200
        assert ComponentModel.objects.count() == 0

    def test_invalid_base_model_shows_error(self, client: Client) -> None:
        form_data = {
            "name": "Bad Component",
            "base_model": "nonexistent-model",
            "component_type": "",
            "engine": "",
            "parameters": "{}",
        }

        response = client.post(reverse("custom-component-create"), data=form_data)

        assert response.status_code == 200
        assert ComponentModel.objects.count() == 0

    def test_disabled_base_model_is_rejected(self, client: Client) -> None:
        form_data = {
            "name": "Coming Soon Host",
            "base_model": "nw-lp",
            "parameters": "{}",
        }

        response = client.post(reverse("custom-component-create"), data=form_data)

        assert response.status_code == 200
        assert "base_model" in response.context["form"].errors
        assert ComponentModel.objects.count() == 0

    def test_submitted_base_model_is_passed_to_alpine_as_json(self, client: Client) -> None:
        form_data = {"name": "", "base_model": "x'}; alert(1); //", "parameters": "{}"}

        response = client.post(reverse("custom-component-create"), data=form_data)

        content = response.content.decode()
        assert "selectedBase: ''," in content
        assert '<script id="selected-base-model" type="application/json">' in content

    def test_clean_derives_component_type_and_engine(self, client: Client) -> None:
        form_data = {
            "name": "Auto-derived",
            "base_model": "fluid-flow-wan-switch-lp",
            "component_type": "",
            "engine": "",
            "parameters": "{}",
        }

        client.post(reverse("custom-component-create"), data=form_data)

        component = ComponentModel.objects.get(name="Auto-derived")
        assert component.component_type == "switch"
        assert component.engine == "PDES (CODES)"


@pytest.mark.django_db
class TestCustomComponentCreate:
    def test_get_renders_form(self, client: Client) -> None:
        response = client.get(reverse("custom-component-create"))

        assert response.status_code == 200
        assert "form" in response.context

    def test_get_htmx_returns_partial(self, client: Client) -> None:
        response = client.get(
            reverse("custom-component-create"),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        templates = [t.name for t in response.templates]
        assert "net_maestro/partials/custom_component_form.html" in templates

    def test_base_model_query_param_prepopulates(self, client: Client) -> None:
        response = client.get(
            reverse("custom-component-create") + "?base_model=fluid-flow-wan-switch-lp"
        )

        assert response.status_code == 200
        form = response.context["form"]
        assert form.initial.get("base_model") == "fluid-flow-wan-switch-lp"

    def test_invalid_base_model_query_param_ignored(self, client: Client) -> None:
        response = client.get(reverse("custom-component-create") + "?base_model=nonexistent")

        assert response.status_code == 200
        form = response.context["form"]
        assert "base_model" not in form.initial

    def test_disabled_base_model_query_param_ignored(self, client: Client) -> None:
        response = client.get(reverse("custom-component-create") + "?base_model=nw-lp")

        assert response.status_code == 200
        form = response.context["form"]
        assert "base_model" not in form.initial

    def test_successful_post_redirects(self, client: Client) -> None:
        form_data = {
            "name": "Test Component",
            "base_model": "fluid-flow-wan-switch-lp",
            "component_type": "switch",
            "engine": "PDES (CODES)",
            "parameters": "{}",
        }

        response = client.post(reverse("custom-component-create"), data=form_data)

        assert response.status_code == 302
        assert response.headers["Location"] == reverse("configuration-partial")


@pytest.mark.django_db
class TestCustomComponentEdit:
    def _create_component(self) -> ComponentModel:
        return ComponentModel.objects.create(
            name="Existing Switch",
            base_model="fluid-flow-wan-switch-lp",
            component_type="switch",
            engine="PDES (CODES)",
            parameters={"switch_buffer": "64", "terminal_bandwidth": "100"},
        )

    def test_get_loads_existing(self, client: Client) -> None:
        component = self._create_component()

        response = client.get(reverse("custom-component-edit", args=[component.pk]))

        assert response.status_code == 200
        form = response.context["form"]
        assert form.instance.pk == component.pk
        assert form.instance.name == "Existing Switch"

    def test_post_updates_component(self, client: Client) -> None:
        component = self._create_component()
        form_data = {
            "name": "Updated Switch",
            "base_model": "fluid-flow-wan-switch-lp",
            "component_type": "switch",
            "engine": "PDES (CODES)",
            "parameters": json.dumps({"switch_buffer": "128", "terminal_bandwidth": "200"}),
        }

        response = client.post(
            reverse("custom-component-edit", args=[component.pk]),
            data=form_data,
        )

        assert response.status_code == 302
        component.refresh_from_db()
        assert component.name == "Updated Switch"
        assert component.parameters == {
            "switch_buffer": "128",
            "terminal_bandwidth": "200",
        }

    def test_nonexistent_component_returns_404(self, client: Client) -> None:
        response = client.get(reverse("custom-component-edit", args=[99999]))

        assert response.status_code == 404


@pytest.mark.django_db
class TestCustomComponentList:
    def test_empty_list(self, client: Client) -> None:
        response = client.get(reverse("configuration-partial"))

        assert response.status_code == 200
        assert list(response.context["custom_components"]) == []

    def test_list_shows_db_components(self, client: Client) -> None:
        ComponentModel.objects.create(
            name="Switch A",
            base_model="fluid-flow-wan-switch-lp",
            component_type="switch",
            engine="PDES (CODES)",
        )

        response = client.get(reverse("configuration-partial"))

        assert response.status_code == 200
        names = [c["name"] for c in response.context["custom_components"]]
        assert "Switch A" in names

    def test_sidebar_base_models_disabled_sorted_last(self, client: Client) -> None:
        response = client.get(reverse("configuration-partial"))

        assert response.status_code == 200
        base_models = response.context["base_models"]
        disabled_flags = [m["disabled"] for m in base_models]
        # Enabled models come first, disabled come last
        assert disabled_flags == sorted(disabled_flags)
