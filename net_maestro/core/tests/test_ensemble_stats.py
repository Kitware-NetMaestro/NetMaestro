"""Tests for the cross-member numbers on the ensemble detail page."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from net_maestro.core import ensemble_stats
from net_maestro.core.constants import RunStatus, SimulationType
from net_maestro.core.models import Ensemble, FFWSimulationConfig, Run, RunSummary
from net_maestro.core.summaries import Metric
from net_maestro.core.tests.factories import EnsembleFactory, RunFactory

pytestmark = pytest.mark.django_db

BASE = {"topology_name": "fabric", "traffic": "random", "np": 1, "sync": 1}
START = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def _ensemble(sweep_spec: list[dict[str, Any]], base: dict[str, Any] | None = None) -> Ensemble:
    return EnsembleFactory.create(
        simulation_type=SimulationType.FFW,
        base_params=base if base is not None else dict(BASE),
        sweep_spec=sweep_spec,
    )


def _member(
    ensemble: Ensemble,
    index: int,
    params: dict[str, Any],
    *,
    metrics: dict[str, Any] | None = None,
    status: RunStatus = RunStatus.COMPLETED,
    topology: str = "fabric",
    wall: float | None = None,
) -> Run:
    """Create one member, its config, and (when `metrics` is given) its summary."""
    run: Run = RunFactory.create(
        ensemble=ensemble,
        member_index=index,
        member_params=params,
        status=status,
        simulation_type=SimulationType.FFW,
    )
    FFWSimulationConfig.objects.create(run=run, topology_name=topology)
    if wall is not None:
        run.started_at = START
        run.finished_at = START + timedelta(seconds=wall)
        run.save()
    if metrics is not None:
        RunSummary.objects.create(run=run, metrics=metrics, health={"ok": True, "checks": []})
    return run


# Baseline


def test_baseline_is_the_member_with_base_settings() -> None:
    ensemble = _ensemble([{"key": "np", "values": [2, 1, 4]}])
    _member(ensemble, 1, {"np": 2})
    base = _member(ensemble, 2, {"np": 1})
    _member(ensemble, 3, {"np": 4})

    assert ensemble_stats.baseline_member(ensemble) == base


def test_baseline_compares_posted_text_with_parsed_values() -> None:
    # The form may hand base params over as text; "1" and 1 are the same setting.
    ensemble = _ensemble([{"key": "sync", "values": ["2", "1"]}], {**BASE, "sync": "1"})
    _member(ensemble, 1, {"sync": 2})
    base = _member(ensemble, 2, {"sync": 1})

    assert ensemble_stats.baseline_member(ensemble) == base


def test_baseline_for_a_topology_edit_is_the_member_on_the_base_preset() -> None:
    # An edit that took effect points the member at a derived `-sweep-` file; the
    # member whose value matched the preset kept the preset's own name.
    ensemble = _ensemble([{"key": "switch_buffer_gb", "values": [8, 2]}])
    _member(ensemble, 1, {"switch_buffer_gb": 8}, topology="fabric-sweep-1-1")
    base = _member(ensemble, 2, {"switch_buffer_gb": 2}, topology="fabric")

    assert ensemble_stats.baseline_member(ensemble) == base


def test_baseline_mixes_settings_and_topology_axes() -> None:
    ensemble = _ensemble(
        [{"key": "np", "values": [1, 2]}, {"key": "switch_buffer_gb", "values": [8, 2]}]
    )
    _member(ensemble, 1, {"np": 1, "switch_buffer_gb": 8}, topology="fabric-sweep-1-1")
    base = _member(ensemble, 2, {"np": 1, "switch_buffer_gb": 2}, topology="fabric")
    _member(ensemble, 3, {"np": 2, "switch_buffer_gb": 8}, topology="fabric-sweep-1-3")
    _member(ensemble, 4, {"np": 2, "switch_buffer_gb": 2}, topology="fabric")

    assert ensemble_stats.baseline_member(ensemble) == base


def test_baseline_falls_back_to_member_one() -> None:
    ensemble = _ensemble([{"key": "np", "values": [2, 4]}])
    first = _member(ensemble, 1, {"np": 2})
    _member(ensemble, 2, {"np": 4})

    assert ensemble_stats.baseline_member(ensemble) == first


def test_baseline_of_an_empty_ensemble_is_none() -> None:
    assert ensemble_stats.baseline_member(_ensemble([{"key": "np", "values": [2]}])) is None


# Member metrics and deltas


def test_member_metrics_subtracts_the_baseline() -> None:
    ensemble = _ensemble([{"key": "np", "values": [1, 2, 4]}])
    _member(ensemble, 1, {"np": 1}, metrics={"dropped_mbit": 10.0, "delivered_mbit": 90})
    _member(ensemble, 2, {"np": 2}, metrics={"dropped_mbit": 15.5, "delivered_mbit": None})
    _member(ensemble, 3, {"np": 4}, status=RunStatus.RUNNING)  # no summary yet

    rows = ensemble_stats.member_metrics(ensemble, ["dropped_mbit", "delivered_mbit"])

    assert [row["is_baseline"] for row in rows] == [True, False, False]
    assert rows[0]["delta_vs_baseline"] == {"dropped_mbit": 0.0, "delivered_mbit": 0.0}
    assert rows[1]["values"] == {"dropped_mbit": 15.5, "delivered_mbit": None}
    assert rows[1]["delta_vs_baseline"] == {"dropped_mbit": 5.5, "delivered_mbit": None}
    assert rows[2]["values"] == {"dropped_mbit": None, "delivered_mbit": None}
    assert rows[2]["delta_vs_baseline"] == {"dropped_mbit": None, "delivered_mbit": None}
    assert rows[0]["health"] == {"ok": True, "checks": []}
    assert rows[2]["health"] is None


def test_member_metrics_without_a_baseline_value_has_no_deltas() -> None:
    ensemble = _ensemble([{"key": "np", "values": [1, 2]}])
    _member(ensemble, 1, {"np": 1}, status=RunStatus.FAILED)
    _member(ensemble, 2, {"np": 2}, metrics={"dropped_mbit": 3.0})

    rows = ensemble_stats.member_metrics(ensemble, ["dropped_mbit"])

    assert rows[1]["delta_vs_baseline"] == {"dropped_mbit": None}


def test_metric_value_ignores_non_numbers() -> None:
    ensemble = _ensemble([{"key": "np", "values": [1]}])
    _member(ensemble, 1, {"np": 1}, metrics={"dropped_mbit": "lots", "pause_frames_sent": True})
    run = ensemble_stats.load_members(ensemble)[0]

    assert ensemble_stats.metric_value(run, "dropped_mbit") is None
    assert ensemble_stats.metric_value(run, "pause_frames_sent") is None
    assert ensemble_stats.metric_value(run, "missing") is None


# Effect tables


def test_one_axis_is_a_series_in_sweep_order() -> None:
    ensemble = _ensemble([{"key": "np", "values": ["4", "1", "2"]}])
    _member(ensemble, 1, {"np": 4}, metrics={"dropped_mbit": 30.0})
    _member(ensemble, 2, {"np": 1}, metrics={"dropped_mbit": 10.0})
    _member(ensemble, 3, {"np": 2}, status=RunStatus.PENDING)

    table = ensemble_stats.effect_table(ensemble, "dropped_mbit")

    assert table["kind"] == "series"
    assert table["axis"].key == "np"
    assert [row["value"] for row in table["rows"]] == ["4", "1", "2"]
    assert [row["metric"] for row in table["rows"]] == [30.0, 10.0, None]
    assert [row["n"] for row in table["rows"]] == [1, 1, 1]
    assert table["averaged"] is False
    # Lower dropped is better: the 10 is shaded best, the 30 worst, the gap not at all.
    assert [row["class"] for row in table["rows"]] == ["bg-error/30", "bg-success/30", ""]


def test_two_axes_pivot_rows_by_the_first_and_columns_by_the_second() -> None:
    ensemble = _ensemble(
        [
            {"key": "switch_buffer_gb", "values": [2, 8]},
            {
                "key": "link_bandwidth_gbps",
                "link": {"source": "STAR", "target": "MICH"},
                "values": [40, 100, 400],
            },
        ]
    )
    index = 0
    for buffer in (2, 8):
        for bandwidth in (40, 100, 400):
            index += 1
            _member(
                ensemble,
                index,
                {"switch_buffer_gb": buffer, "link_bandwidth_gbps": bandwidth},
                metrics={"dropped_mbit": float(index * 10)},
                topology=f"fabric-sweep-1-{index}",
            )

    table = ensemble_stats.effect_table(ensemble, "dropped_mbit")

    assert table["kind"] == "pivot"
    assert table["row_axis"].key == "switch_buffer_gb"
    assert table["col_axis"].key == "link_bandwidth_gbps"
    assert [col["value"] for col in table["col_values"]] == [40, 100, 400]
    assert [row["value"] for row in table["rows"]] == [2, 8]
    assert [[cell["metric"] for cell in row["cells"]] for row in table["rows"]] == [
        [10.0, 20.0, 30.0],
        [40.0, 50.0, 60.0],
    ]
    assert table["rows"][0]["cells"][1]["member_index"] == 2
    assert table["rows"][0]["cells"][0]["class"] == "bg-success/30"
    assert table["rows"][1]["cells"][2]["class"] == "bg-error/30"
    assert table["averaged"] is False


def test_three_axes_show_main_effects() -> None:
    spec = [
        {"key": "np", "values": [1, 2]},
        {"key": "sync", "values": [1, 2]},
        {"key": "switch_buffer_gb", "values": [2, 8]},
    ]
    ensemble = _ensemble(spec)
    index = 0
    for np in (1, 2):
        for sync in (1, 2):
            for buffer in (2, 8):
                index += 1
                # dropped = 100 * np + 10 * sync + buffer, so each mean is easy to check.
                _member(
                    ensemble,
                    index,
                    {"np": np, "sync": sync, "switch_buffer_gb": buffer},
                    metrics={"dropped_mbit": float(100 * np + 10 * sync + buffer)},
                )

    table = ensemble_stats.effect_table(ensemble, "dropped_mbit")

    assert table["kind"] == "main_effects"
    assert table["averaged"] is True
    by_axis = {effect["axis"].key: effect["rows"] for effect in table["axes"]}
    assert list(by_axis) == ["np", "sync", "switch_buffer_gb"]
    assert [row["mean"] for row in by_axis["np"]] == [120.0, 220.0]
    assert [row["mean"] for row in by_axis["sync"]] == [165.0, 175.0]
    assert [row["mean"] for row in by_axis["switch_buffer_gb"]] == [167.0, 173.0]
    assert [row["n"] for row in by_axis["np"]] == [4, 4]
    assert [row["class"] for row in by_axis["np"]] == ["bg-success/30", "bg-error/30"]


def test_effect_table_without_any_summaries_is_all_gaps() -> None:
    ensemble = _ensemble([{"key": "np", "values": [1, 2]}])
    _member(ensemble, 1, {"np": 1}, status=RunStatus.PENDING)
    _member(ensemble, 2, {"np": 2}, status=RunStatus.PENDING)

    table = ensemble_stats.effect_table(ensemble, "dropped_mbit")

    assert [row["metric"] for row in table["rows"]] == [None, None]
    assert [row["class"] for row in table["rows"]] == ["", ""]


def test_metric_with_no_direction_is_not_shaded() -> None:
    ensemble = _ensemble([{"key": "np", "values": [1, 2]}])
    _member(ensemble, 1, {"np": 1}, metrics={"generated_mbit": 1.0})
    _member(ensemble, 2, {"np": 2}, metrics={"generated_mbit": 2.0})

    table = ensemble_stats.effect_table(ensemble, "generated_mbit")

    assert [row["class"] for row in table["rows"]] == ["", ""]


# Spread


def _three_members(key: str) -> Ensemble:
    ensemble = _ensemble([{"key": "np", "values": [1, 2, 4]}])
    _member(ensemble, 1, {"np": 1}, metrics={key: 5.0})
    _member(ensemble, 2, {"np": 2}, metrics={key: 1.0})
    _member(ensemble, 3, {"np": 4}, metrics={key: 9.0})
    return ensemble


def test_spread_lower_is_better() -> None:
    result = ensemble_stats.spread(_three_members("dropped_mbit"), "dropped_mbit")

    assert result is not None
    assert (result["min"], result["max"], result["range"]) == (1.0, 9.0, 8.0)
    assert result["best"]["run"].member_index == 2
    assert result["worst"]["run"].member_index == 3


def test_spread_higher_is_better() -> None:
    result = ensemble_stats.spread(_three_members("delivered_mbit"), "delivered_mbit")

    assert result is not None
    assert result["best"]["run"].member_index == 3
    assert result["best"]["value"] == 9.0
    assert result["worst"]["run"].member_index == 2


def test_spread_without_a_direction_has_no_best() -> None:
    result = ensemble_stats.spread(_three_members("generated_mbit"), "generated_mbit")

    assert result is not None
    assert result["range"] == 8.0
    assert result["best"] is None
    assert result["worst"] is None


def test_spread_needs_two_values() -> None:
    ensemble = _ensemble([{"key": "np", "values": [1, 2]}])
    _member(ensemble, 1, {"np": 1}, metrics={"dropped_mbit": 1.0})
    _member(ensemble, 2, {"np": 2}, status=RunStatus.RUNNING)

    assert ensemble_stats.spread(ensemble, "dropped_mbit") is None


# ETA


def test_eta_is_mean_wall_time_times_members_left() -> None:
    ensemble = _ensemble([{"key": "np", "values": [1, 2, 4, 8, 16]}])
    _member(ensemble, 1, {"np": 1}, wall=10)
    _member(ensemble, 2, {"np": 2}, status=RunStatus.FAILED, wall=20)
    _member(ensemble, 3, {"np": 4}, status=RunStatus.RUNNING)
    _member(ensemble, 4, {"np": 8}, status=RunStatus.PENDING)
    _member(ensemble, 5, {"np": 16}, status=RunStatus.PENDING)

    assert ensemble_stats.eta_seconds(ensemble) == pytest.approx(45.0)


def test_eta_without_finished_members_is_none() -> None:
    ensemble = _ensemble([{"key": "np", "values": [1, 2]}])
    _member(ensemble, 1, {"np": 1}, status=RunStatus.RUNNING)
    _member(ensemble, 2, {"np": 2}, status=RunStatus.PENDING)

    assert ensemble_stats.eta_seconds(ensemble) is None


def test_eta_with_nothing_left_is_none() -> None:
    ensemble = _ensemble([{"key": "np", "values": [1]}])
    _member(ensemble, 1, {"np": 1}, wall=10)

    assert ensemble_stats.eta_seconds(ensemble) is None


# Formatting


def test_fractions_are_shown_as_percentages() -> None:
    frac = Metric("peak_buffer_occupancy_frac", "Peak", "", lower_is_better=True, digits=3)

    assert ensemble_stats.format_metric(frac, 0.8734) == "87.3%"
    assert ensemble_stats.format_metric(frac, 0.05, signed=True) == "+5.0%"


def test_numbers_carry_their_unit_and_precision() -> None:
    mbit = Metric("dropped_mbit", "Dropped", "Mbit", lower_is_better=True)
    pct = Metric("efficiency_pct", "Efficiency", "%")

    assert ensemble_stats.format_metric(mbit, 1234.56) == "1,234.6 Mbit"
    assert ensemble_stats.format_metric(mbit, -0.01, signed=True) == "+0.0 Mbit"
    assert ensemble_stats.format_metric(mbit, None) == "—"
    assert ensemble_stats.format_metric(pct, 92.5) == "92.5%"


def test_format_duration() -> None:
    assert ensemble_stats.format_duration(42) == "42s"
    assert ensemble_stats.format_duration(185) == "3m 05s"
    assert ensemble_stats.format_duration(3720) == "1h 02m"
    assert ensemble_stats.format_duration(None) == "—"
