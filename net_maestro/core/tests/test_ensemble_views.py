"""Tests for the ensemble pages: create, list, detail, members, and run."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest import mock

from django.core.exceptions import ValidationError
from django.urls import reverse
import pytest

from net_maestro.core.constants import FFWTrafficMode, RunStatus, SimulationType, SynchProtocol
from net_maestro.core.models import Ensemble, FFWSimulationConfig, Run
from net_maestro.core.services.ensembles import create_ensemble

if TYPE_CHECKING:
    from pathlib import Path

    from django.test import Client
    from pytest_django.fixtures import SettingsWrapper

pytestmark = pytest.mark.django_db

TOPOLOGY_YAML = """
topology:
  switches:
    A:
      terminals: 2
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        B: "100 Gbps"
    B:
      terminals: 2
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        A: "100 Gbps"
"""


@pytest.fixture
def preset(tmp_path: Path, settings: SettingsWrapper) -> str:
    """Write one topology preset and point the topology directory at it."""
    settings.TOPOLOGY_DIR = tmp_path
    name = "ffw-fabric-2-site"
    (tmp_path / f"{name}.yaml").write_text(TOPOLOGY_YAML, encoding="utf-8")
    return name


def _post_data(preset: str, sweep_spec: object, action: str = "save") -> dict[str, object]:
    return {
        "name": "Buffer sweep",
        "description": "",
        "topology_name": preset,
        "traffic": FFWTrafficMode.RANDOM,
        "np": 1,
        "sync": SynchProtocol.SEQUENTIAL,
        "sweep_spec": json.dumps(sweep_spec),
        "action": action,
    }


def _ensemble(preset: str, run_status: RunStatus = RunStatus.SAVED) -> Ensemble:
    """Create a two-member ensemble that varies MPI processes."""
    return create_ensemble(
        name="NP sweep",
        description="",
        simulation_type=SimulationType.FFW,
        base_params={
            "topology_name": preset,
            "traffic": FFWTrafficMode.RANDOM,
            "np": 1,
            "sync": SynchProtocol.SEQUENTIAL,
        },
        sweep_spec=[{"key": "np", "values": [1, 2]}],
        run_status=run_status,
    )


def test_new_ensemble_form_carries_the_axis_registry(client: Client, preset: str) -> None:
    response = client.get(reverse("ensemble-create"))

    assert response.status_code == 200
    axes = response.context["sweep_axes"]
    assert "switch_buffer_gb" in {axis["key"] for axis in axes}
    assert 'id="sweep-axes"' in response.content.decode()
    assert response.context["max_members"] > 0


@mock.patch("net_maestro.core.views.launch_ensemble")
def test_save_creates_members_without_running_them(
    launch: mock.MagicMock, client: Client, preset: str
) -> None:
    spec = [{"key": "switch_buffer_gb", "values": [2, 8]}]
    response = client.post(reverse("ensemble-create"), _post_data(preset, spec))

    ensemble = Ensemble.objects.get()
    assert response.status_code == 302
    assert response["Location"] == reverse("ensemble-detail", kwargs={"ensemble_id": ensemble.pk})
    assert ensemble.members.count() == 2
    assert {run.status for run in ensemble.members} == {RunStatus.SAVED}
    launch.assert_not_called()


@mock.patch("net_maestro.core.views.launch_ensemble")
def test_save_and_run_launches_the_ensemble(
    launch: mock.MagicMock, client: Client, preset: str
) -> None:
    spec = [{"key": "np", "values": [1, 2, 4]}]
    response = client.post(reverse("ensemble-create"), _post_data(preset, spec, "save_and_run"))

    ensemble = Ensemble.objects.get()
    assert response.status_code == 302
    assert {run.status for run in ensemble.members} == {RunStatus.PENDING}
    launch.assert_called_once_with(ensemble)


@mock.patch("net_maestro.core.views.launch_ensemble")
def test_unknown_axis_rerenders_with_the_error(
    launch: mock.MagicMock, client: Client, preset: str
) -> None:
    spec = [{"key": "no_such_axis", "values": [1]}]
    response = client.post(reverse("ensemble-create"), _post_data(preset, spec, "save_and_run"))

    assert response.status_code == 200
    assert response.context["form"].non_field_errors()
    assert "alert-error" in response.content.decode()
    assert not Ensemble.objects.exists()
    launch.assert_not_called()


def test_malformed_sweep_spec_is_a_field_error(client: Client, preset: str) -> None:
    data = _post_data(preset, [])
    data["sweep_spec"] = '{"key": "np"}'
    response = client.post(reverse("ensemble-create"), data)

    assert response.status_code == 200
    assert response.context["form"].errors["sweep_spec"]
    assert not Ensemble.objects.exists()


def test_list_shows_ensembles(client: Client, preset: str) -> None:
    _ensemble(preset)
    response = client.get(reverse("ensemble-list"))

    assert response.status_code == 200
    assert "NP sweep" in response.content.decode()


def test_detail_renders_member_rows(client: Client, preset: str) -> None:
    ensemble = _ensemble(preset)
    response = client.get(reverse("ensemble-detail", kwargs={"ensemble_id": ensemble.pk}))

    assert response.status_code == 200
    rows = response.context["member_rows"]
    assert [row["values"] for row in rows] == [[1], [2]]
    # Saved members have nothing running, so the table does not poll.
    assert response.context["polling"] is False
    assert "hx-trigger" not in response.content.decode()


def test_detail_polls_while_members_are_pending(client: Client, preset: str) -> None:
    ensemble = _ensemble(preset, RunStatus.PENDING)
    response = client.get(reverse("ensemble-detail", kwargs={"ensemble_id": ensemble.pk}))

    assert response.context["polling"] is True
    assert 'hx-trigger="every 2s"' in response.content.decode()


def test_members_partial_returns_the_table(client: Client, preset: str) -> None:
    ensemble = _ensemble(preset, RunStatus.PENDING)
    response = client.get(reverse("ensemble-members", kwargs={"ensemble_id": ensemble.pk}))

    content = response.content.decode()
    assert response.status_code == 200
    assert 'id="ensemble-members"' in content
    assert "<table" in content
    assert "<html" not in content
    first = ensemble.members.first()
    assert first is not None
    assert f"?run={first.pk}" in content


def test_unknown_ensemble_is_404(client: Client) -> None:
    response = client.get(reverse("ensemble-detail", kwargs={"ensemble_id": 999}))

    assert response.status_code == 404


@mock.patch("net_maestro.core.views.launch_ensemble")
def test_run_ensemble_launches(launch: mock.MagicMock, client: Client, preset: str) -> None:
    ensemble = _ensemble(preset)
    response = client.post(reverse("run-ensemble", kwargs={"ensemble_id": ensemble.pk}))

    assert response.status_code == 302
    assert response["Location"] == reverse("ensemble-detail", kwargs={"ensemble_id": ensemble.pk})
    launch.assert_called_once_with(ensemble)


@mock.patch("net_maestro.core.views.launch_ensemble")
def test_run_ensemble_reports_an_invalid_member(
    launch: mock.MagicMock, client: Client, preset: str
) -> None:
    launch.side_effect = ValidationError("gone")
    ensemble = _ensemble(preset)
    response = client.post(
        reverse("run-ensemble", kwargs={"ensemble_id": ensemble.pk}), follow=True
    )

    assert response.status_code == 200
    assert "Unable to run" in response.content.decode()


def test_run_ensemble_requires_post(client: Client, preset: str) -> None:
    ensemble = _ensemble(preset)
    response = client.get(reverse("run-ensemble", kwargs={"ensemble_id": ensemble.pk}))

    assert response.status_code == 405


def test_analysis_preselects_the_requested_run(client: Client, preset: str) -> None:
    ensemble = _ensemble(preset, RunStatus.PENDING)
    run = ensemble.members.first()
    assert run is not None
    response = client.get(reverse("analysis-partial"), {"run": run.pk})

    assert response.context["preselect_run"] == run
    assert f"selectRun({run.pk}, 'ffw')" in response.content.decode()


def test_analysis_without_run_preselects_nothing(client: Client) -> None:
    response = client.get(reverse("analysis-partial"), {"run": "not-a-number"})

    assert response.context["preselect_run"] is None


def test_saved_simulations_leaves_out_ensemble_members(client: Client, preset: str) -> None:
    _ensemble(preset)
    standalone = Run.objects.create(name="Standalone", simulation_type=SimulationType.FFW)
    FFWSimulationConfig.objects.create(run=standalone, topology_name=preset)

    response = client.get(reverse("simulation-config"))

    assert [config.run for config in response.context["configs"]] == [standalone]
