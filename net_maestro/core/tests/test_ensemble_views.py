"""Tests for the ensemble pages: create, list, detail, members, and run."""

from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING, Any
from unittest import mock

from django.core.exceptions import ValidationError
from django.urls import reverse
import pytest

from net_maestro.core.constants import FFWTrafficMode, RunStatus, SimulationType, SynchProtocol
from net_maestro.core.models import Ensemble, FFWSimulationConfig, Run, RunSummary
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


def test_list_folds_the_description_into_a_collapse(client: Client, preset: str) -> None:
    """The study's purpose is there to reread, but folded so the card stays short."""
    ensemble = _ensemble(preset)
    ensemble.description = "Does np change anything?\nIt should not."
    ensemble.save(update_fields=["description"])
    content = client.get(reverse("ensemble-list")).content.decode()

    assert "About this study" in content
    assert "Does np change anything?<br>It should not." in content
    assert content.count("collapse-title") == 1

    ensemble.description = ""
    ensemble.save(update_fields=["description"])
    assert "About this study" not in client.get(reverse("ensemble-list")).content.decode()


def test_detail_renders_member_rows(client: Client, preset: str) -> None:
    ensemble = _ensemble(preset)
    response = client.get(reverse("ensemble-detail", kwargs={"ensemble_id": ensemble.pk}))

    assert response.status_code == 200
    rows = response.context["member_rows"]
    assert [row["values"] for row in rows] == [[1], [2]]
    # Saved members have nothing running, so the table does not poll.
    assert response.context["polling"] is False
    assert 'hx-trigger="every' not in response.content.decode()


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


def test_members_partial_refreshes_the_header_badge_out_of_band(
    client: Client, preset: str
) -> None:
    """Each poll carries the roll-up badge, so the header follows the members' progress."""
    ensemble = _ensemble(preset, RunStatus.PENDING)
    partial = client.get(reverse("ensemble-members", kwargs={"ensemble_id": ensemble.pk}))
    page = client.get(reverse("ensemble-detail", kwargs={"ensemble_id": ensemble.pk}))

    partial_content = partial.content.decode()
    assert 'id="ensemble-header-status" hx-swap-oob="true"' in partial_content
    # The tiles ride along too: they sit above the comparison plot, outside the
    # region that swaps, so the poll is their only way to refresh.
    assert 'id="ensemble-stats" class="mt-6" hx-swap-oob="true"' in partial_content
    # The full page renders each once, in place, without the swap marker.
    content = page.content.decode()
    assert content.count('id="ensemble-header-status"') == 1
    assert content.count('id="ensemble-stats"') == 1
    assert "hx-swap-oob" not in content


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


# Results: tiles, deltas, extra columns, effects, export


def _with_results(preset: str) -> Ensemble:
    """Return the NP sweep with both members finished and summarized.

    Member 1 runs the base np of 1, so it is the baseline.
    """
    ensemble = _ensemble(preset, RunStatus.COMPLETED)
    first, second = ensemble.members
    RunSummary.objects.create(
        run=first,
        metrics={"dropped_mbit": 10.0, "peak_buffer_occupancy_frac": 0.5, "pause_time_s": 1.5},
        details={"peak_buffer_switch": "A"},
        health={"ok": True, "checks": []},
    )
    RunSummary.objects.create(
        run=second,
        metrics={"dropped_mbit": 15.0, "peak_buffer_occupancy_frac": 0.25},
        health={
            "ok": False,
            "checks": [{"key": "drained", "label": "Drained", "ok": False, "detail": "backlog 5%"}],
        },
    )
    return ensemble


def _detail(client: Client, ensemble: Ensemble, **params: str) -> Any:
    return client.get(reverse("ensemble-detail", kwargs={"ensemble_id": ensemble.pk}), params)


def test_detail_renders_tiles_and_effect_card(client: Client, preset: str) -> None:
    ensemble = _with_results(preset)
    response = _detail(client, ensemble)

    content = response.content.decode()
    stats = response.context["stats"]
    assert (stats["completed"], stats["failed"], stats["pending"]) == (2, 0, 0)
    dropped = stats["metrics"][0]
    assert dropped["value"] == "#1: 10.0 Mbit"
    assert dropped["desc"] == "range 10.0 \N{EN DASH} 15.0 Mbit"
    assert "Effect of each parameter" in content
    assert 'id="ensemble-effects"' in content
    assert response.context["headline"] == "dropped_mbit"
    assert response.context["effects"]["kind"] == "series"
    assert "Export CSV" in content
    # Health: member 2 failed a check, and its tooltip says which.
    assert "Drained: backlog 5%" in content


def test_detail_honours_the_effect_metric(client: Client, preset: str) -> None:
    ensemble = _with_results(preset)

    chosen = _detail(client, ensemble, metric="peak_buffer_occupancy_frac")
    unknown = _detail(client, ensemble, metric="no_such_metric")

    assert chosen.context["headline"] == "peak_buffer_occupancy_frac"
    displays = [row["display"] for row in chosen.context["effects"]["rows"]]
    assert displays == ["50.0%", "25.0%"]
    assert unknown.context["headline"] == "dropped_mbit"


def test_delta_mode_marks_the_baseline(client: Client, preset: str) -> None:
    ensemble = _with_results(preset)
    response = _detail(client, ensemble, delta="1")

    rows = response.context["member_rows"]
    content = response.content.decode()
    assert response.context["delta"] is True
    assert [row["is_baseline"] for row in rows] == [True, False]
    # The baseline keeps its own value; the other row shows the signed difference.
    assert rows[0]["metrics"][0]["display"] == "10.0 Mbit"
    assert rows[1]["metrics"][0]["display"] == "+5.0 Mbit"
    assert ">baseline</span>" in content


def test_without_delta_no_row_is_badged(client: Client, preset: str) -> None:
    response = _detail(client, _with_results(preset))

    assert response.context["delta"] is False
    assert ">baseline</span>" not in response.content.decode()


def test_extra_metrics_ignore_unknown_and_headline_keys(client: Client, preset: str) -> None:
    ensemble = _with_results(preset)
    response = _detail(client, ensemble, metrics="pause_time_s,bogus,dropped_mbit,pause_time_s")

    assert response.context["extra_metrics"] == ["pause_time_s"]
    keys = [metric.key for metric in response.context["metric_columns"]]
    assert keys == [
        "dropped_mbit",
        "peak_buffer_occupancy_frac",
        "bottleneck_peak_utilization",
        "pause_time_s",
    ]
    assert response.context["member_rows"][0]["metrics"][3]["display"] == "1.500 s"
    options = {option["key"] for option in response.context["add_metric_options"]}
    assert "pause_time_s" not in options
    assert "dropped_mbit" not in options


def test_members_partial_carries_the_query_in_its_poll(client: Client, preset: str) -> None:
    ensemble = _ensemble(preset, RunStatus.PENDING)
    url = reverse("ensemble-members", kwargs={"ensemble_id": ensemble.pk})
    response = client.get(url, {"delta": "1", "metrics": "pause_time_s"})

    content = response.content.decode()
    assert f'hx-get="{url}?delta=1&amp;metrics=pause_time_s"' in content
    assert 'id="ensemble-members-toolbar"' in content


def test_a_toolbar_change_rewrites_the_address_bar_but_a_poll_does_not(
    client: Client, preset: str
) -> None:
    ensemble = _ensemble(preset, RunStatus.PENDING)
    url = reverse("ensemble-members", kwargs={"ensemble_id": ensemble.pk})
    detail = reverse("ensemble-detail", kwargs={"ensemble_id": ensemble.pk})

    changed = client.get(
        url,
        {"delta": "1"},
        headers={"HX-Request": "true", "HX-Trigger": "ensemble-members-toolbar"},
    )
    polled = client.get(
        url, {"delta": "1"}, headers={"HX-Request": "true", "HX-Trigger": "ensemble-members"}
    )

    assert changed["HX-Replace-Url"] == f"{detail}?delta=1"
    assert "HX-Replace-Url" not in polled


def test_effects_partial_returns_the_card(client: Client, preset: str) -> None:
    ensemble = _with_results(preset)
    response = client.get(
        reverse("ensemble-effects", kwargs={"ensemble_id": ensemble.pk}),
        {"metric": "peak_buffer_occupancy_frac"},
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert 'id="ensemble-effects"' in content
    assert "<html" not in content
    assert "50.0%" in content
    assert '<option value="peak_buffer_occupancy_frac" selected>' in content


def test_export_writes_one_row_per_member(client: Client, preset: str) -> None:
    ensemble = _with_results(preset)
    response = client.get(reverse("ensemble-export", kwargs={"ensemble_id": ensemble.pk}))

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert response["Content-Disposition"] == 'attachment; filename="np-sweep.csv"'
    rows = list(csv.DictReader(io.StringIO(response.content.decode())))
    assert len(rows) == 2
    header = list(rows[0])
    assert header[:2] == ["member_index", "np"]
    assert header[-4:] == ["health_ok", "status", "run_wall_time_s", "topology_name"]
    assert len(header) == len(set(header))
    assert "dropped_mbit" in header
    assert "peak_buffer_switch" in header
    assert [row["dropped_mbit"] for row in rows] == ["10.0", "15.0"]
    assert [row["health_ok"] for row in rows] == ["True", "False"]
    assert rows[0]["peak_buffer_switch"] == "A"
    assert rows[1]["pause_time_s"] == ""
    assert rows[0]["topology_name"] == preset
    assert rows[0]["status"] == RunStatus.COMPLETED


# The comparison plot: its JSON, its card, and the hooks the table gives it


def _two_axis_ensemble(preset: str) -> Ensemble:
    """Return a 2 x 2 sweep of MPI processes by sync protocol, three members summarized.

    Member 4 has no summary yet, as if it were still running.
    """
    ensemble = create_ensemble(
        name="NP by sync",
        description="",
        simulation_type=SimulationType.FFW,
        base_params={
            "topology_name": preset,
            "traffic": FFWTrafficMode.RANDOM,
            "np": 1,
            "sync": SynchProtocol.SEQUENTIAL,
        },
        sweep_spec=[
            {"key": "np", "values": ["2", "1"]},
            {
                "key": "sync",
                "values": [str(SynchProtocol.SEQUENTIAL), str(SynchProtocol.CONSERVATIVE)],
            },
        ],
        run_status=RunStatus.COMPLETED,
    )
    for run, dropped in zip(
        ensemble.members.order_by("member_index")[:3], [4.0, 2.0, 1.0], strict=True
    ):
        RunSummary.objects.create(
            run=run,
            metrics={"dropped_mbit": dropped, "peak_buffer_occupancy_frac": 0.5},
            health={"ok": dropped < 3, "checks": []},
        )
    return ensemble


def test_members_json_describes_axes_metrics_and_members(client: Client, preset: str) -> None:
    ensemble = _two_axis_ensemble(preset)
    response = client.get(reverse("ensemble-members-json", kwargs={"ensemble_id": ensemble.pk}))

    assert response.status_code == 200
    data = response.json()
    np_axis, sync_axis = data["axes"]
    # Spec order, not sorted; number values as numbers, choices as text with their names.
    assert (np_axis["key"], np_axis["kind"]) == ("np", "number")
    assert np_axis["values"] == [2.0, 1.0]
    assert np_axis["labels"] == ["2", "1"]
    assert np_axis["link"] is None
    assert (sync_axis["key"], sync_axis["kind"]) == ("sync", "choice")
    assert sync_axis["values"] == [str(SynchProtocol.SEQUENTIAL), str(SynchProtocol.CONSERVATIVE)]
    assert sync_axis["labels"] == [SynchProtocol.SEQUENTIAL.label, SynchProtocol.CONSERVATIVE.label]

    assert data["headline"] == [
        "dropped_mbit",
        "peak_buffer_occupancy_frac",
        "bottleneck_peak_utilization",
    ]
    metrics = {metric["key"]: metric for metric in data["metrics"]}
    assert metrics["peak_buffer_occupancy_frac"]["is_fraction"] is True
    assert metrics["dropped_mbit"]["lower_is_better"] is True
    assert metrics["dropped_mbit"]["unit"] == "Mbit"
    # No member has engine stats, so engine metrics are not offered.
    assert "wall_time_s" not in metrics
    assert "pause_time_s" in metrics

    members = data["members"]
    assert [member["index"] for member in members] == [1, 2, 3, 4]
    first = members[0]
    run = ensemble.members.get(member_index=1)
    assert first["run_id"] == run.pk
    assert first["status"] == RunStatus.COMPLETED
    # Member params come back in the same form as the axis values they match.
    assert first["params"]["np"] in np_axis["values"]
    assert first["params"]["sync"] in sync_axis["values"]
    assert first["metrics"]["dropped_mbit"] == 4.0
    assert first["metrics"]["bottleneck_peak_utilization"] is None
    assert [member["health_ok"] for member in members] == [False, True, True, None]
    assert members[3]["metrics"]["dropped_mbit"] is None


def test_members_json_for_an_unknown_ensemble_is_404(client: Client) -> None:
    response = client.get(reverse("ensemble-members-json", kwargs={"ensemble_id": 999}))

    assert response.status_code == 404


def test_detail_includes_the_comparison_card_outside_the_polled_region(
    client: Client, preset: str
) -> None:
    ensemble = _ensemble(preset, RunStatus.PENDING)
    content = _detail(client, ensemble).content.decode()

    url = reverse("ensemble-members-json", kwargs={"ensemble_id": ensemble.pk})
    assert "Compare members" in content
    assert f'data-url="{url}"' in content
    assert 'id="ensembleParcoords"' in content
    # The polled region replaces itself, so the plot must come before it, not inside it,
    # and right above it: the tiles go first.
    tiles = content.index('id="ensemble-stats"')
    plot = content.index('id="ensembleParcoords"')
    members = content.index('id="ensemble-members"')
    assert tiles < plot < members


def test_members_partial_rows_carry_their_member_index(client: Client, preset: str) -> None:
    ensemble = _ensemble(preset)
    response = client.get(reverse("ensemble-members", kwargs={"ensemble_id": ensemble.pk}))

    content = response.content.decode()
    assert 'data-member="1"' in content
    assert 'data-member="2"' in content
    assert "$store.ensembleSelectionStore.hovered = 2" in content
    assert 'id="ensembleParcoords"' not in content
