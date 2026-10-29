"""Tests for ensemble member time series and the endpoints that serve them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.urls import reverse
import pytest

from net_maestro.core.constants import FFWStatsType, RunStatus, SimulationType
from net_maestro.core.series import SERIES_METRICS, entities_for, member_series, thin
from net_maestro.core.summaries import compute_run_summary
from net_maestro.core.tests.factories import (
    EnsembleFactory,
    FFWPortRecordFactory,
    FFWResultFileFactory,
    FFWSimulationConfigFactory,
    FFWSwitchRecordFactory,
    FFWTerminalRecordFactory,
    RunFactory,
    SimulationFileFactory,
    SimulationPeRecordFactory,
    UserFactory,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper
    from rest_framework.test import APIClient

    from net_maestro.core.models import Ensemble, FFWResultFile, Run

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
      terminals: 1
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        A: "100 Gbps"
"""

# A different preset whose switches share no names with the first.
OTHER_YAML = """
topology:
  switches:
    X:
      terminals: 1
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        Y: "100 Gbps"
    Y:
      terminals: 1
      terminal_bandwidth: "100 Gbps"
      switch_buffer: "64 Gb"
      connections:
        X: "100 Gbps"
"""

# Four VT samples 0.1 s apart, in ns.
TS = [1e8, 2e8, 3e8, 4e8]
PRESET = "ffw-fabric-2-site"
OTHER = "ffw-other"


@pytest.fixture
def preset(tmp_path: Path, settings: SettingsWrapper) -> str:
    """Write the presets (switch 0 is A, switch 1 is B) and point the topology dir at them."""
    settings.TOPOLOGY_DIR = tmp_path
    (tmp_path / f"{PRESET}.yaml").write_text(TOPOLOGY_YAML, encoding="utf-8")
    (tmp_path / f"{OTHER}.yaml").write_text(OTHER_YAML, encoding="utf-8")
    return PRESET


def _member(
    ensemble: Ensemble, index: int, topology_name: str = PRESET
) -> tuple[Run, FFWResultFile]:
    run = RunFactory.create(
        ensemble=ensemble,
        member_index=index,
        member_params={"np": index},
        status=RunStatus.COMPLETED,
        simulation_type=SimulationType.FFW,
    )
    FFWSimulationConfigFactory.create(run=run, topology_name=topology_name)
    return run, FFWResultFileFactory.create(run=run)


def _rows(result_file: FFWResultFile, *, scale: float = 1.0) -> None:
    """Add switch A's samples, its port to B, and terminal 1's samples."""
    for i, ts in enumerate(TS):
        record = FFWSwitchRecordFactory.create(
            result_file=result_file,
            switch_id=0,
            ts=ts,
            shared_buffer_occupancy_mbit=[100, 400, 250, 0][i] * scale,
            dropped_mbit=[0, 5, 10, 0][i],
        )
        FFWPortRecordFactory.create(
            switch_record=record,
            port_index=0,
            is_terminal=False,
            target_index=1,
            port_sent_mbit=[0, 5000, 10000, 2500][i] * scale,
            port_pause_time_ns=[0, 5e8, 0, 2.5e8][i],
            port_output_paused=i == 1,
        )
        FFWTerminalRecordFactory.create(
            result_file=result_file,
            terminal_id=1,
            ts=ts,
            generated_mbit=[10, 20, 30, 40][i],
            pause_time_ns=[0, 1e9, 0, 5e8][i],
            source_backlog_mbit=[5, 4, 3, 0][i],
        )


@pytest.fixture
def client(api_client: APIClient) -> APIClient:
    """Return an API client signed in, as the API requires outside development."""
    api_client.force_authenticate(user=UserFactory.create())
    return api_client


@pytest.fixture
def ensemble(preset: str) -> Ensemble:
    """Return an ensemble on the preset: two members with rows and one with none."""
    ens = EnsembleFactory.create(base_params={"topology_name": preset, "np": 1})
    for index, scale in ((0, 1.0), (1, 0.5)):
        _, result_file = _member(ens, index)
        _rows(result_file, scale=scale)
    _member(ens, 2)
    return ens


def _points(run: Run, entity: str, metric: str, *, cumulative: bool = False) -> list[list[Any]]:
    return member_series(run, entity=entity, metric=metric, cumulative=cumulative)["points"]


class TestEntities:
    def test_names_switches_terminals_and_links_from_the_base_topology(
        self, ensemble: Ensemble
    ) -> None:
        entities = entities_for(ensemble)

        assert entities == [
            {"id": "switch:0", "label": "A", "dataset": "switches"},
            {"id": "switch:1", "label": "B", "dataset": "switches"},
            {"id": "terminal:0", "label": "A.0", "dataset": "terminals"},
            {"id": "terminal:1", "label": "A.1", "dataset": "terminals"},
            {"id": "terminal:2", "label": "B.0", "dataset": "terminals"},
            {"id": "link:0:1", "label": "A → B", "dataset": "links"},
            {"id": "link:1:0", "label": "B → A", "dataset": "links"},
        ]

    def test_engine_entities_come_from_the_first_member_with_pe_rows(
        self, ensemble: Ensemble
    ) -> None:
        run = ensemble.members.get(member_index=1)
        sim_file = SimulationFileFactory.create(run=run, file__filename="ross-stats-gvt.bin")
        for pe in (1, 0):
            SimulationPeRecordFactory.create(simulation_file=sim_file, PE_ID=pe)

        engine = [e for e in entities_for(ensemble) if e["dataset"] == "engine"]

        assert engine == [
            {"id": "pe:0", "label": "PE 0", "dataset": "engine"},
            {"id": "pe:1", "label": "PE 1", "dataset": "engine"},
        ]


class TestMemberSeries:
    def test_switch_gauge_in_seconds(self, ensemble: Ensemble) -> None:
        run = ensemble.members.get(member_index=0)

        series = member_series(
            run, entity="switch:0", metric="shared_buffer_occupancy_mbit", cumulative=True
        )

        assert series["stats_type"] == FFWStatsType.VT
        # A gauge ignores `cumulative`.
        assert series["points"] == [[0.1, 100.0], [0.2, 400.0], [0.3, 250.0], [0.4, 0.0]]

    def test_terminal_delta_raw_and_cumulative(self, ensemble: Ensemble) -> None:
        run = ensemble.members.get(member_index=0)

        assert [v for _, v in _points(run, "terminal:1", "generated_mbit")] == [10, 20, 30, 40]
        assert [v for _, v in _points(run, "terminal:1", "generated_mbit", cumulative=True)] == [
            10,
            30,
            60,
            100,
        ]

    def test_pause_times_are_reported_in_seconds(self, ensemble: Ensemble) -> None:
        run = ensemble.members.get(member_index=0)

        terminal = _points(run, "terminal:1", "pause_time_s", cumulative=True)
        port = _points(run, "link:0:1", "port_pause_time_s")

        assert [v for _, v in terminal] == [0.0, 1.0, 1.0, 1.5]
        assert [v for _, v in port] == [0.0, 0.5, 0.0, 0.25]

    def test_link_utilization_peaks_where_the_summary_says(self, ensemble: Ensemble) -> None:
        run = ensemble.members.get(member_index=0)
        summary = compute_run_summary(run)
        assert summary is not None

        points = _points(run, "link:0:1", "utilization")

        # The first sample has no interval start, so it is skipped.
        assert [x for x, _ in points] == [0.2, 0.3, 0.4]
        # 10000 Mbit over 0.1 s of a 100 Gbps link.
        assert max(v for _, v in points) == pytest.approx(1.0)
        assert max(v for _, v in points) == pytest.approx(
            summary.metrics["bottleneck_peak_utilization"]
        )

    def test_port_output_paused_reads_as_zero_or_one(self, ensemble: Ensemble) -> None:
        run = ensemble.members.get(member_index=0)

        assert [v for _, v in _points(run, "link:0:1", "port_output_paused")] == [0, 1, 0, 0]

    def test_uses_the_summarys_sampling_mode(self, ensemble: Ensemble) -> None:
        run = ensemble.members.get(member_index=0)
        result_file = run.ffw_result_files.get()
        FFWSwitchRecordFactory.create(
            result_file=result_file, switch_id=0, ts=5e8, stats_type=FFWStatsType.GVT
        )
        compute_run_summary(run)
        run.summary.stats_type = FFWStatsType.GVT
        run.summary.save()
        run.refresh_from_db()

        series = member_series(
            run, entity="switch:0", metric="shared_buffer_occupancy_mbit", cumulative=False
        )

        assert series["stats_type"] == FFWStatsType.GVT
        assert series["points"] == [[0.5, 0.0]]

    def test_member_without_rows_or_entity_is_empty(self, ensemble: Ensemble) -> None:
        empty_run = ensemble.members.get(member_index=2)
        other_run, result_file = _member(ensemble, 3, topology_name=OTHER)
        _rows(result_file)

        assert _points(empty_run, "switch:0", "shared_buffer_occupancy_mbit") == []
        # Switch 0 of the other preset is X, not A: no series rather than X's.
        assert _points(other_run, "switch:0", "shared_buffer_occupancy_mbit") == []
        assert _points(other_run, "link:0:1", "utilization") == []

    def test_engine_series(self, ensemble: Ensemble) -> None:
        run = ensemble.members.get(member_index=0)
        assert _points(run, "pe:0", "events_processed") == []

        sim_file = SimulationFileFactory.create(run=run, file__filename="ross-stats-gvt.bin")
        for vt, processed, efficiency in ((2e8, 50, 0.5), (1e8, 100, 0.9)):
            SimulationPeRecordFactory.create(
                simulation_file=sim_file,
                PE_ID=0,
                virtual_time=vt,
                events_processed=processed,
                efficiency=efficiency,
            )

        assert _points(run, "pe:0", "events_processed", cumulative=True) == [
            [0.1, 100.0],
            [0.2, 150.0],
        ]
        assert _points(run, "pe:0", "efficiency", cumulative=True) == [[0.1, 0.9], [0.2, 0.5]]


def test_thinning_keeps_first_and_last() -> None:
    points = [[float(i), float(i)] for i in range(10)]

    thinned = thin(points, 4)

    assert len(thinned) <= 4
    assert thinned[0] == points[0]
    assert thinned[-1] == points[-1]
    assert thin(points, 20) == points
    for n in range(2, 40):
        for limit in range(2, 12):
            out = thin([[i, i] for i in range(n)], limit)
            assert len(out) <= max(limit, 2)
            assert out[0] == [0, 0]
            assert out[-1] == [n - 1, n - 1]


def test_member_series_thins_to_max_points(ensemble: Ensemble) -> None:
    run = ensemble.members.get(member_index=0)

    points = member_series(
        run, entity="switch:0", metric="dropped_mbit", cumulative=True, max_points=3
    )["points"]

    assert points == [[0.1, 0.0], [0.3, 15.0], [0.4, 15.0]]


class TestSeriesEndpoint:
    def _get(self, client: APIClient, ensemble: Ensemble, **params: str) -> Any:
        return client.get(reverse("ensemble-series", args=[ensemble.pk]), params)

    def test_shape(self, client: APIClient, ensemble: Ensemble) -> None:
        response = self._get(
            client, ensemble, entity="terminal:1", metric="generated_mbit", members="1,0"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["entity"] == {"id": "terminal:1", "label": "A.1", "dataset": "terminals"}
        assert body["metric"] == {
            "key": "generated_mbit",
            "label": "Generated",
            "unit": "Mbit",
            "kind": "delta",
        }
        # Deltas are cumulated unless asked not to be.
        assert body["cumulative"] is True
        assert body["x_label"] == "Virtual time (s)"
        assert [m["index"] for m in body["members"]] == [1, 0]
        first = body["members"][0]
        assert first["label"] == "np=1"
        assert first["stats_type"] == "vt"
        assert first["points"][-1] == [0.4, 100.0]

    def test_raw_deltas_and_gauges_ignore_the_flag(
        self, client: APIClient, ensemble: Ensemble
    ) -> None:
        raw = self._get(
            client,
            ensemble,
            entity="terminal:1",
            metric="generated_mbit",
            members="0",
            cumulative="0",
        ).json()
        gauge = self._get(
            client,
            ensemble,
            entity="switch:0",
            metric="shared_buffer_occupancy_mbit",
            members="0",
            cumulative="1",
        ).json()

        assert raw["cumulative"] is False
        assert raw["members"][0]["points"][-1] == [0.4, 40.0]
        assert gauge["cumulative"] is False

    @pytest.mark.parametrize(
        ("params", "message"),
        [
            ({"entity": "switch:9", "metric": "dropped_mbit", "members": "0"}, "Unknown entity"),
            ({"entity": "switch:0", "metric": "utilization", "members": "0"}, "Unknown metric"),
            (
                {"entity": "switch:0", "metric": "dropped_mbit", "members": "0,1,2,3,4,5,6,7,8"},
                "at most 8 members",
            ),
            ({"entity": "switch:0", "metric": "dropped_mbit", "members": "0,7"}, "No member"),
            ({"entity": "switch:0", "metric": "dropped_mbit", "members": "a"}, "members"),
            ({"entity": "switch:0", "metric": "dropped_mbit", "members": ""}, "members"),
        ],
    )
    def test_rejects_bad_params(
        self, client: APIClient, ensemble: Ensemble, params: dict[str, str], message: str
    ) -> None:
        response = self._get(client, ensemble, **params)

        assert response.status_code == 400
        assert message in response.json()["error"]


def test_entities_endpoint_shape(client: APIClient, ensemble: Ensemble) -> None:
    response = client.get(reverse("ensemble-entities", args=[ensemble.pk]))

    assert response.status_code == 200
    body = response.json()
    assert body["entities"][0] == {"id": "switch:0", "label": "A", "dataset": "switches"}
    assert set(body["metrics"]) == set(SERIES_METRICS)
    assert body["metrics"]["links"][0] == {
        "key": "utilization",
        "label": "Utilization",
        "unit": "",
        "kind": "gauge",
    }
