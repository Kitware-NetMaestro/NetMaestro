"""Numbers across an ensemble's members, for the results half of its detail page.

Each member's own numbers live in its `RunSummary`; this module only lines
those up across the sweep: which member is the baseline the others are
compared with, how far each moved from it, what each swept parameter did to a
metric, and how long the rest of the sweep should take. Everything here reads
the database through the members it is handed and writes nothing.

Members that have not finished have no summary yet. Every function treats
their values as missing (None) rather than failing, because the page renders
these tables while the sweep is still running.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from net_maestro.core.constants import RunStatus
from net_maestro.core.summaries import Metric, metrics_for
from net_maestro.core.sweeps import axes_for

if TYPE_CHECKING:
    from collections.abc import Sequence

    from net_maestro.core.models import Ensemble, Run, RunSummary

# A member that has stopped, with or without results; its wall time says how
# long a member of this sweep takes.
_FINISHED = frozenset({RunStatus.COMPLETED, RunStatus.FAILED})
# A member the chain has yet to finish.
_ACTIVE = frozenset({RunStatus.PENDING, RunStatus.RUNNING})

# Cell shading by rank, best first. Five steps are enough to tell good from bad
# at a glance without implying a precision a handful of members cannot carry.
_RANK_CLASSES = ("bg-success/30", "bg-success/15", "", "bg-error/15", "bg-error/30")


@dataclass(frozen=True)
class AxisInfo:
    """One swept axis as the results tables show it.

    `values` keeps the order the user entered them in the sweep spec, which is
    the order rows and columns follow. `labels` maps a stored value to what to
    show for it: a sync protocol's name rather than its number.
    """

    key: str
    label: str
    unit: str
    values: list[Any]
    link: dict[str, str] | None = None
    labels: dict[str, str] = field(default_factory=dict)

    def label_for(self, value: Any) -> str:
        return self.labels.get(str(value), str(value))


def load_members(ensemble: Ensemble) -> list[Run]:
    """Return the members with what these tables read joined in.

    The summary (absent until a member finishes) and the configs (for the
    topology a member ran) would otherwise cost a query per row.
    """
    return list(ensemble.members.select_related("summary").prefetch_related("ffw_configs"))


def _members(ensemble: Ensemble, members: Sequence[Run] | None) -> Sequence[Run]:
    return load_members(ensemble) if members is None else members


def summary_of(run: Run) -> RunSummary | None:
    """Return a member's summary, or None while it has none.

    The reverse one-to-one raises (an AttributeError subclass) rather than
    returning None when the row is missing, which `getattr` absorbs.
    """
    return getattr(run, "summary", None)


def metric_value(run: Run, key: str) -> float | None:
    """Return one metric for a member as a float, or None when it has no value."""
    summary = summary_of(run)
    if summary is None:
        return None
    value = (summary.metrics or {}).get(key)
    # bool is an int to Python, but a stored true/false is not a measurement.
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _norm(value: Any) -> Any:
    """Make a stored value comparable with the same value posted as text.

    The sweep spec keeps values as posted ("8", "1") while member params and
    base params hold them parsed (8, 1), so numbers compare as floats and
    everything else as text.
    """
    if isinstance(value, bool):
        return str(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return str(value)


def axis_infos(ensemble: Ensemble) -> list[AxisInfo]:
    """Return the ensemble's swept axes, in sweep order, labelled from the registry.

    An axis the registry no longer knows still shows, under its key.
    """
    registry = {axis.key: axis for axis in axes_for(ensemble.simulation_type)}
    infos = []
    for entry in ensemble.sweep_spec or []:
        key = str(entry.get("key", ""))
        axis = registry.get(key)
        labels = {str(value): label for value, label in axis.choices()} if axis else {}
        infos.append(
            AxisInfo(
                key=key,
                label=axis.label if axis else key,
                unit=axis.unit if axis else "",
                values=list(entry.get("values") or []),
                link=entry.get("link"),
                labels=labels,
            )
        )
    return infos


def topology_name_of(run: Run) -> str | None:
    """Return the topology a member ran, from its newest config (prefetched)."""
    configs = list(run.ffw_configs.all())
    if not configs:
        return None
    return max(configs, key=lambda config: config.pk).topology_name


def _is_base(run: Run, base_params: dict[str, Any], topology_keys: set[str]) -> bool:
    """Say whether a member ran exactly the base configuration.

    A settings axis is compared with the base value directly. A topology edit
    is not stored as a setting at all: a member whose edit changed nothing
    keeps the base preset's name, while one whose edit took effect points at a
    derived `-sweep-` file, so the topology name is what tells them apart.
    """
    for key, value in (run.member_params or {}).items():
        if key in topology_keys:
            if topology_name_of(run) != base_params.get("topology_name"):
                return False
        elif _norm(value) != _norm(base_params.get(key)):
            return False
    return True


def baseline_member(ensemble: Ensemble, *, members: Sequence[Run] | None = None) -> Run | None:
    """Return the member the others are compared with.

    That is the member that ran the base configuration unchanged, so a delta
    reads as "what this change did". A sweep whose values all differ from the
    base has no such member; member 1 stands in, because a delta needs some
    reference and the first grid point is the one the user listed first.
    """
    members = _members(ensemble, members)
    if not members:
        return None
    base_params = ensemble.base_params or {}
    topology_keys = {axis.key for axis in axes_for(ensemble.simulation_type) if axis.edits_topology}
    for run in members:
        if _is_base(run, base_params, topology_keys):
            return run
    return members[0]


def member_metrics(
    ensemble: Ensemble,
    keys: Sequence[str],
    *,
    members: Sequence[Run] | None = None,
    baseline: Run | None = None,
) -> list[dict[str, Any]]:
    """Return each member's values for `keys` and how far each is from the baseline.

    A delta is None when either side has no value, so a member still running
    shows a gap rather than a misleading difference from zero.
    """
    members = _members(ensemble, members)
    if baseline is None:
        baseline = baseline_member(ensemble, members=members)
    base_values = {key: metric_value(baseline, key) for key in keys} if baseline else {}
    rows = []
    for run in members:
        summary = summary_of(run)
        values = {key: metric_value(run, key) for key in keys}
        deltas: dict[str, float | None] = {}
        for key in keys:
            value, base = values[key], base_values.get(key)
            deltas[key] = None if value is None or base is None else value - base
        rows.append(
            {
                "run": run,
                "values": values,
                "delta_vs_baseline": deltas,
                "health": (summary.health or None) if summary else None,
                "details": (summary.details or {}) if summary else {},
                "is_baseline": baseline is not None and run.pk == baseline.pk,
            }
        )
    return rows


def find_metric(ensemble: Ensemble, key: str) -> Metric | None:
    """Return the registry entry for a metric key, engine metrics included."""
    for metric in metrics_for(ensemble.simulation_type, with_engine=True):
        if metric.key == key:
            return metric
    return None


def rank_classes(values: Sequence[float | None], *, lower_is_better: bool | None) -> list[str]:
    """Return a background class per value, shading best to worst.

    Equal values share a shade. Nothing is shaded when the metric has no
    better direction or when there is nothing to compare.
    """
    distinct = sorted({value for value in values if value is not None})
    if lower_is_better is None or len(distinct) < 2:
        return ["" for _ in values]
    if not lower_is_better:
        distinct.reverse()
    last = len(distinct) - 1
    steps = len(_RANK_CLASSES) - 1
    classes = []
    for value in values:
        if value is None:
            classes.append("")
            continue
        position = distinct.index(value) / last
        classes.append(_RANK_CLASSES[round(position * steps)])
    return classes


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _cell(
    entries: Sequence[tuple[dict[str, Any], float | None, Run]], fixed: dict[str, Any]
) -> dict[str, Any]:
    """Average the metric over the members that share the `fixed` axis values."""
    matching = [
        (value, run)
        for params, value, run in entries
        if all(params.get(key) == want for key, want in fixed.items())
    ]
    present = [value for value, _ in matching if value is not None]
    return {
        "metric": _mean(present),
        "n": len(matching),
        "member_index": matching[0][1].member_index if len(matching) == 1 else None,
    }


def effect_table(
    ensemble: Ensemble, metric_key: str, *, members: Sequence[Run] | None = None
) -> dict[str, Any]:
    """Lay one metric out against the swept parameters.

    The layout follows the number of axes, because a table can show at most
    two at once:

    - one axis, `series`: one row per value.
    - two axes, `pivot`: the first axis down, the second across, one member per cell.
    - three or more, `main_effects`: per axis, the mean over every member with
      that value, which averages the other axes away.

    Rows and columns follow the order the values were entered in. A cell that
    covers several members holds their mean, and `averaged` says so. Cells
    carry `class`, a shade by rank across the whole table (per axis for main
    effects), when the metric has a better direction.
    """
    members = _members(ensemble, members)
    axes = axis_infos(ensemble)
    metric = find_metric(ensemble, metric_key)
    lower_is_better = metric.lower_is_better if metric else None
    entries = [
        (
            {key: _norm(value) for key, value in (run.member_params or {}).items()},
            metric_value(run, metric_key),
            run,
        )
        for run in members
    ]
    table: dict[str, Any] = {"metric_key": metric_key, "metric": metric, "averaged": False}

    if not axes:
        return {**table, "kind": "empty"}

    if len(axes) == 1:
        axis = axes[0]
        rows = []
        for value in axis.values:
            cell = _cell(entries, {axis.key: _norm(value)})
            rows.append({"value": value, "label": axis.label_for(value), **cell})
        _shade(rows, lower_is_better=lower_is_better)
        return {
            **table,
            "kind": "series",
            "axis": axis,
            "rows": rows,
            "averaged": any(row["n"] > 1 for row in rows),
        }

    if len(axes) == 2:
        row_axis, col_axis = axes
        pivot_rows = []
        for row_value in row_axis.values:
            cells = [
                _cell(entries, {row_axis.key: _norm(row_value), col_axis.key: _norm(col_value)})
                for col_value in col_axis.values
            ]
            pivot_rows.append(
                {"value": row_value, "label": row_axis.label_for(row_value), "cells": cells}
            )
        _shade(
            [cell for row in pivot_rows for cell in row["cells"]], lower_is_better=lower_is_better
        )
        return {
            **table,
            "kind": "pivot",
            "row_axis": row_axis,
            "col_axis": col_axis,
            "col_values": [
                {"value": value, "label": col_axis.label_for(value)} for value in col_axis.values
            ],
            "rows": pivot_rows,
            "averaged": any(cell["n"] > 1 for row in pivot_rows for cell in row["cells"]),
        }

    effects = []
    for axis in axes:
        rows = []
        for value in axis.values:
            cell = _cell(entries, {axis.key: _norm(value)})
            rows.append(
                {"value": value, "label": axis.label_for(value), "mean": cell["metric"], **cell}
            )
        _shade(rows, lower_is_better=lower_is_better)
        effects.append({"axis": axis, "rows": rows})
    return {**table, "kind": "main_effects", "axes": effects, "averaged": True}


def _shade(cells: list[dict[str, Any]], *, lower_is_better: bool | None) -> None:
    values = [cell["metric"] for cell in cells]
    classes = rank_classes(values, lower_is_better=lower_is_better)
    for cell, css in zip(cells, classes, strict=True):
        cell["class"] = css


def spread(
    ensemble: Ensemble, metric_key: str, *, members: Sequence[Run] | None = None
) -> dict[str, Any] | None:
    """Return the range of a metric across members and its best and worst member.

    None until at least two members have the metric, since one value has no
    spread. Best and worst follow the metric's `lower_is_better` and are None
    for a metric with no better direction; ties go to the lower member number.
    """
    members = _members(ensemble, members)
    present = [
        (run, value) for run in members if (value := metric_value(run, metric_key)) is not None
    ]
    if len(present) < 2:
        return None
    low = min(present, key=lambda pair: pair[1])
    high = max(present, key=lambda pair: pair[1])
    metric = find_metric(ensemble, metric_key)
    lower_is_better = metric.lower_is_better if metric else None
    best = worst = None
    if lower_is_better is not None:
        best, worst = (low, high) if lower_is_better else (high, low)
    return {
        "min": low[1],
        "max": high[1],
        "range": high[1] - low[1],
        "count": len(present),
        "best": {"run": best[0], "value": best[1]} if best else None,
        "worst": {"run": worst[0], "value": worst[1]} if worst else None,
    }


def wall_time(run: Run) -> float | None:
    """Return a member's wall time, tolerating a Run without the timing fields."""
    value = getattr(run, "wall_time_s", None)
    return float(value) if isinstance(value, int | float) else None


def eta_seconds(ensemble: Ensemble, *, members: Sequence[Run] | None = None) -> float | None:
    """Estimate how long the members still queued or running will take.

    Members run one at a time, so the estimate is the mean wall time of the
    members that have finished times the number left. The running member's
    elapsed time is ignored: the estimate is rough either way, and ignoring it
    keeps it from jumping as members start. None when nothing is left or no
    member has finished to measure by.
    """
    members = _members(ensemble, members)
    remaining = sum(1 for run in members if run.status in _ACTIVE)
    if not remaining:
        return None
    times = [t for run in members if run.status in _FINISHED and (t := wall_time(run)) is not None]
    mean = _mean(times)
    return None if mean is None else mean * remaining


# Key endings the summary registry uses for 0-1 fractions. The registry gives
# these no unit, so the ending is what says to show them as percentages.
_FRACTION_SUFFIXES = ("_frac", "_utilization")


def is_fraction(metric: Metric | None) -> bool:
    """Say whether a metric is stored as a 0-1 fraction and shown as a percentage.

    A `%` unit on a key that is not already a percentage (`_pct`) counts too.
    """
    if metric is None or metric.key.endswith("_pct"):
        return False
    return metric.unit == "%" or (not metric.unit and metric.key.endswith(_FRACTION_SUFFIXES))


def format_number(metric: Metric | None, value: float | None, *, signed: bool = False) -> str:
    """Format a value without its unit, at the metric's precision.

    A fraction's digits count places of the fraction (0.873), so as a
    percentage it needs two fewer (87.3).
    """
    if value is None:
        return "—"
    digits = metric.digits if metric is not None else 1
    if is_fraction(metric):
        value *= 100
        digits = max(digits - 2, 0)
    # Round first, and add 0.0, so a tiny negative does not print as "-0.0".
    value = round(value, digits) + 0.0
    return f"{value:+,.{digits}f}" if signed else f"{value:,.{digits}f}"


def unit_suffix(metric: Metric | None) -> str:
    """Return what follows a formatted number: `%`, ` Mbit`, or nothing."""
    if is_fraction(metric) or (metric is not None and metric.unit == "%"):
        return "%"
    if metric is None or not metric.unit:
        return ""
    return f" {metric.unit}"


def format_metric(metric: Metric | None, value: float | None, *, signed: bool = False) -> str:
    """Format a value with its unit: `142.3 Mbit`, `87.5%`, `+3.0 Mbit`."""
    if value is None:
        return "—"
    return f"{format_number(metric, value, signed=signed)}{unit_suffix(metric)}"


def format_duration(seconds: float | None) -> str:
    """Format a wall time the way a person reads it: `42s`, `3m 05s`, `1h 02m`."""
    if seconds is None:
        return "—"
    total = round(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"
