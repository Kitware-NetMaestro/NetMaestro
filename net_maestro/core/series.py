"""Time series of one entity across an ensemble's members, for comparing a few side by side.

The per-run data endpoints return every sample row, which is fine for one run but too
much to pull for eight members at once, so the ensemble page asks for one entity (a
switch, terminal, link or PE) and one metric, and gets each member's series already
reduced to that column, cumulated if asked, and thinned.

The sampling rules are the ones `summaries` follows: deltas (volumes, frame counters,
pause times) are per-sample increments and are only meaningful cumulated or as rates,
gauges (occupancies, backlogs) are read as they are, and one sampling mode is used per
run because GVT and RT share an accumulator.

Link utilization and a switch's per-step peak buffer occupancy come from the model's
per-step logs when a member has them (see `models/ffw_model_logs.py`): one point per
fluid step, at the step's start, rather than per sample. The samples miss what happens
within milliseconds of a step boundary, so a sampled utilization reads above 100% and
a sampled occupancy misses the peaks. Members without the logs keep the sampled
utilization and have no per-step peak.

Entities are named from the ensemble's base topology. Members of a sweep that edits
the topology run on derived files that keep the base's switches, so an entity is
looked up in each member's own topology by its label: a member whose topology lacks
it (a `topology_name` sweep) has no series for it rather than some other switch's.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import accumulate
import logging
from math import ceil, isfinite
from typing import TYPE_CHECKING, Any, Literal

from django.db.models import F, Max

from net_maestro.core.models import (
    FFWLinkStepRecord,
    FFWPortRecord,
    FFWSwitchRecord,
    FFWSwitchStepRecord,
    FFWTerminalRecord,
)
from net_maestro.core.summaries import (
    _STATS_TYPE_PREFERENCE,
    NS_PER_S,
    SOURCE_MODEL_LOG,
    SOURCE_SAMPLES,
    _choose_stats_type,
    _engine_rows,
    _topology_for,
    link_utilization,
)
from net_maestro.core.topology import TopologyError, get_topology

if TYPE_CHECKING:
    from collections.abc import Sequence

    from net_maestro.core.models import Ensemble, Run
    from net_maestro.core.topology import Topology

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeriesMetric:
    """One column that can be drawn over time, and whether it is a delta or a gauge."""

    key: str
    label: str
    unit: str = ""
    kind: Literal["delta", "gauge"] = "gauge"


SERIES_METRICS: dict[str, list[SeriesMetric]] = {
    "switches": [
        SeriesMetric("shared_buffer_occupancy_mbit", "Buffer occupancy", "Mbit", "gauge"),
        SeriesMetric("buffered_residual_mbit", "Buffered residual", "Mbit", "gauge"),
        SeriesMetric("sent_mbit", "Sent", "Mbit", "delta"),
        SeriesMetric("delivered_local_mbit", "Delivered locally", "Mbit", "delta"),
        SeriesMetric("dropped_mbit", "Dropped", "Mbit", "delta"),
        SeriesMetric("pause_frames_sent", "PAUSE frames sent", "", "delta"),
        SeriesMetric("pause_frames_received", "PAUSE frames received", "", "delta"),
        # From the model's per-step log only; members without one have no points.
        SeriesMetric("peak_occupancy_frac", "Peak buffer occupancy (per step)", "", "gauge"),
    ],
    "terminals": [
        SeriesMetric("source_backlog_mbit", "Source backlog", "Mbit", "gauge"),
        SeriesMetric("send_rate_sum_mbps", "Send rate", "Mbps", "gauge"),
        SeriesMetric("active_flows", "Active flows", "", "gauge"),
        SeriesMetric("generated_mbit", "Generated", "Mbit", "delta"),
        SeriesMetric("sent_to_switch_mbit", "Sent to switch", "Mbit", "delta"),
        SeriesMetric("received_mbit", "Received", "Mbit", "delta"),
        SeriesMetric("pause_time_s", "Pause time", "s", "delta"),
    ],
    "links": [
        SeriesMetric("utilization", "Utilization", "", "gauge"),
        SeriesMetric("port_queued_mbit", "Queued", "Mbit", "gauge"),
        SeriesMetric("port_sent_mbit", "Sent", "Mbit", "delta"),
        SeriesMetric("port_pause_time_s", "Pause time", "s", "delta"),
        SeriesMetric("port_output_paused", "Output paused", "", "gauge"),
    ],
    "engine": [
        SeriesMetric("efficiency", "Efficiency", "%", "gauge"),
        SeriesMetric("events_processed", "Events processed", "", "delta"),
        SeriesMetric("events_rolled_back", "Events rolled back", "", "delta"),
        SeriesMetric("total_rollbacks", "Total rollbacks", "", "delta"),
        SeriesMetric("network_sends", "Network sends", "", "delta"),
    ],
}

X_LABEL = "Virtual time (s)"

# The utilization label when every member's points came from the model's step log.
UTILIZATION_PER_STEP_LABEL = "Utilization (per step)"

# Metrics reported in seconds whose rows hold nanoseconds, by the column they read.
_NS_COLUMNS = {"pause_time_s": "pause_time_ns", "port_pause_time_s": "port_pause_time_ns"}


def series_metric(dataset: str, key: str) -> SeriesMetric | None:
    """Return the registry entry for `key` within `dataset`, or None."""
    for metric in SERIES_METRICS.get(dataset, []):
        if metric.key == key:
            return metric
    return None


def metric_as_json(metric: SeriesMetric, sources: set[str | None]) -> dict[str, Any]:
    """Return `metric` as a dict, labelled for where the members' points came from.

    Link utilization reads "per step" only when every member that has points got
    them from the model's log; a mix is labelled as plain utilization, which both are.
    """
    row = asdict(metric)
    if metric.key == "utilization" and sources == {SOURCE_MODEL_LOG}:
        row["label"] = UTILIZATION_PER_STEP_LABEL
    return row


def series_metrics_as_json() -> dict[str, list[dict[str, Any]]]:
    """Return `SERIES_METRICS` as plain dicts for JSON."""
    return {
        dataset: [asdict(metric) for metric in metrics]
        for dataset, metrics in SERIES_METRICS.items()
    }


def base_topology(ensemble: Ensemble) -> Topology | None:
    """Return the topology the ensemble's base configuration names, or None."""
    name = (ensemble.base_params or {}).get("topology_name")
    if not name:
        return None
    try:
        return get_topology(name)
    except TopologyError:
        logger.warning("Ensemble %s: topology %r is not readable", ensemble.pk, name)
        return None


def topology_entities(topology: Topology) -> list[dict[str, Any]]:
    """Return a topology's switches, terminals and links as series entities.

    A switch's position in the file is its `switch_id`, and terminals are numbered
    by walking the switches in file order, as `Topology.simulation_inputs` does;
    a terminal is named after its switch and its place among that switch's
    terminals. Links are directed, so a pair with a reverse link appears twice.
    """
    entities: list[dict[str, Any]] = []
    names = [switch.name for switch in topology.switches]
    entities.extend(
        {"id": f"switch:{i}", "label": name, "dataset": "switches"} for i, name in enumerate(names)
    )
    terminal_id = 0
    for switch in topology.switches:
        for n in range(switch.terminals):
            entities.append(
                {
                    "id": f"terminal:{terminal_id}",
                    "label": f"{switch.name}.{n}",
                    "dataset": "terminals",
                }
            )
            terminal_id += 1
    index = {name: i for i, name in enumerate(names)}
    entities.extend(
        {
            "id": f"link:{index[link.source]}:{index[link.target]}",
            "label": f"{link.source} → {link.target}",
            "dataset": "links",
        }
        for link in topology.links
        if link.source in index and link.target in index
    )
    return entities


def entities_for(ensemble: Ensemble) -> list[dict[str, Any]]:
    """Return the entities a series can be drawn for: the base topology's, then the PEs.

    PEs come from the first member (by index) that has engine rows; members of one
    ensemble share `np`, unless they sweep it, and then the first member's PEs are
    the ones every member has.
    """
    topology = base_topology(ensemble)
    entities = topology_entities(topology) if topology is not None else []
    for run in ensemble.members:
        pe_ids = sorted(set(_engine_rows(run).values_list("PE_ID", flat=True)))
        if pe_ids:
            entities.extend(
                {"id": f"pe:{pe}", "label": f"PE {pe}", "dataset": "engine"} for pe in pe_ids
            )
            break
    return entities


def thin(points: Sequence[list[Any]], max_points: int) -> list[list[Any]]:
    """Keep every k-th point so at most `max_points` remain, always with the first and last.

    A stride rather than an average keeps gauge peaks honest where they land and
    keeps a cumulated series exact at the points it shows.
    """
    n = len(points)
    if n <= max_points or n <= 2:
        return list(points)
    stride = ceil((n - 1) / max(max_points - 1, 1))
    kept = list(points[::stride])
    if (n - 1) % stride:
        kept.append(points[-1])
    return kept


def _member_entity(
    entity: str, base: Topology | None, own: Topology | None
) -> dict[str, Any] | None:
    """Return the member's own entity matching `entity` by label, or None if it has none.

    With either topology unreadable the id is taken as is: there is nothing to
    check it against, and the rows decide.
    """
    if entity.startswith("pe:"):
        return {"id": entity, "dataset": "engine"}
    if base is None or own is None:
        dataset = {"switch": "switches", "terminal": "terminals", "link": "links"}.get(
            entity.split(":", 1)[0]
        )
        return {"id": entity, "dataset": dataset} if dataset else None
    label = next((e["label"] for e in topology_entities(base) if e["id"] == entity), None)
    if label is None:
        return None
    return next((e for e in topology_entities(own) if e["label"] == label), None)


def _stats_type_for(run: Run) -> str | None:
    """Return the run's summary's sampling mode, else the first in preference with rows."""
    summary = getattr(run, "summary", None)
    if summary is not None and summary.stats_type in _STATS_TYPE_PREFERENCE:
        return str(summary.stats_type)
    return _choose_stats_type(run)


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    value = float(value)
    return value if isfinite(value) else None


def member_series(  # noqa: C901, PLR0912, PLR0913
    run: Run,
    *,
    entity: str,
    metric: str,
    cumulative: bool,
    max_points: int = 1500,
    base: Topology | None = None,
) -> dict[str, Any]:
    """Return one member's series for `entity` and `metric` as `[[t_s, value], ...]`.

    x is the sample's virtual time in seconds: FFW rows carry `ts` in nanoseconds,
    and the engine's `virtual_time` is ROSS's virtual clock, which for the FFW model
    is the same nanoseconds. Per-step points (link utilization from the model log,
    `peak_occupancy_frac`) sit at their step's start. Deltas are cumulated when
    `cumulative`; gauges ignore it. `base` is the ensemble's base topology, passed in
    by callers that already loaded it; otherwise it is read from the run's ensemble.

    `source` says whether the points came from the model log or the samples, None
    when there are none. Points are `[]` when the run lacks the entity or has no
    rows for it.
    """
    dataset, _, _ = entity.partition(":")
    dataset = {"switch": "switches", "terminal": "terminals", "link": "links", "pe": "engine"}.get(
        dataset, ""
    )
    spec = series_metric(dataset, metric)
    stats_type = _stats_type_for(run) if dataset != "engine" else None
    empty: dict[str, Any] = {"stats_type": stats_type, "source": None, "points": []}
    if spec is None:
        return empty

    own = _topology_for(run) if dataset != "engine" else None
    if base is None and dataset != "engine" and run.ensemble is not None:
        base = base_topology(run.ensemble)
    resolved = _member_entity(entity, base, own)
    if resolved is None:
        return empty
    try:
        ids = [int(part) for part in resolved["id"].split(":")[1:]]
    except ValueError:
        return empty
    if len(ids) != (2 if dataset == "links" else 1):
        return empty

    column = _NS_COLUMNS.get(metric, metric)
    scale = 1.0 / NS_PER_S if metric in _NS_COLUMNS else 1.0
    raw: list[tuple[float, Any]]
    source = SOURCE_SAMPLES
    if dataset == "switches" and metric == "peak_occupancy_frac":
        raw = _switch_step_rows(run, ids[0])
        source = SOURCE_MODEL_LOG
    elif dataset == "links" and metric == "utilization" and _has_link_steps(run):
        raw = _link_step_rows(run, ids[0], ids[1])
        source = SOURCE_MODEL_LOG
    elif dataset == "engine":
        rows = (
            _engine_rows(run)
            .filter(PE_ID=ids[0])
            .order_by("virtual_time")
            .values_list("virtual_time", column)
        )
        raw = list(rows)
    elif stats_type is None:
        return empty
    elif dataset == "switches":
        raw = list(
            FFWSwitchRecord.objects.filter(
                result_file__run=run, stats_type=stats_type, switch_id=ids[0]
            )
            .order_by("ts")
            .values_list("ts", column)
        )
    elif dataset == "terminals":
        raw = list(
            FFWTerminalRecord.objects.filter(
                result_file__run=run, stats_type=stats_type, terminal_id=ids[0]
            )
            .order_by("ts")
            .values_list("ts", column)
        )
    else:
        raw = _link_rows(run, stats_type, ids[0], ids[1], metric, column, own or base)

    points: list[list[Any]] = []
    for ts, value in raw:
        x = _finite(ts)
        if x is None:
            continue
        points.append([x / NS_PER_S, None if value is None else _finite(value * scale)])

    if spec.kind == "delta" and cumulative:
        totals = accumulate(value or 0.0 for _, value in points)
        points = [[x, total] for (x, _), total in zip(points, totals, strict=True)]
    return {
        "stats_type": stats_type,
        "source": source if points else None,
        "points": thin(points, max_points),
    }


def _switch_step_rows(run: Run, switch_id: int) -> list[tuple[float, Any]]:
    """Return `(step start in ns, peak occupancy over buffer)` for each logged step."""
    return [
        (start_s * NS_PER_S, frac)
        for start_s, frac in FFWSwitchStepRecord.objects.filter(
            run=run, switch_id=switch_id, buffer_mbit__gt=0
        )
        .annotate(frac=F("peak_occupancy_mbit") / F("buffer_mbit"))
        .order_by("step")
        .values_list("step_start_s", "frac")
    ]


def _has_link_steps(run: Run) -> bool:
    return FFWLinkStepRecord.objects.filter(run=run).exists()


def _link_step_rows(run: Run, switch_id: int, target_index: int) -> list[tuple[float, Any]]:
    """Return `(step start in ns, utilization)` for every step of the run on one link.

    Steps are only logged when the port sent something, so the run's other steps are
    filled in as idle (the step grid is the one stored with the logs); otherwise a
    line would be drawn straight across them. As with the samples, the
    lower-numbered port is used if a switch has two to one neighbour.
    """
    steps = FFWLinkStepRecord.objects.filter(
        run=run, switch_id=switch_id, target_index=target_index, target_is_terminal=False
    )
    port = steps.order_by("port").values_list("port", flat=True).first()
    if port is None:
        return []
    logged = {
        step: (start_s, sent / capacity if capacity > 0 else None)
        for step, start_s, sent, capacity in steps.filter(port=port).values_list(
            "step", "step_start_s", "sent_mbit", "capacity_mbit"
        )
    }
    grid = run.ffw_model_logs.aggregate(interval_s=Max("interval_seconds"), n=Max("num_steps"))
    if not grid["interval_s"]:
        return [(start_s * NS_PER_S, value) for _, (start_s, value) in sorted(logged.items())]
    filled: dict[int, tuple[float, float | None]] = {
        step: (step * grid["interval_s"], 0.0) for step in range(grid["n"] or 0)
    }
    filled.update(logged)
    return [(start_s * NS_PER_S, value) for _, (start_s, value) in sorted(filled.items())]


def _link_rows(  # noqa: PLR0913
    run: Run,
    stats_type: str,
    switch_id: int,
    target_index: int,
    metric: str,
    column: str,
    topology: Topology | None,
) -> list[tuple[float, Any]]:
    """Return `(ts, value)` for the port of `switch_id` that leads to `target_index`.

    Should a switch have two ports to one neighbour, the lower-numbered one is used:
    a per-link utilization can't be summed across ports.
    """
    ports = FFWPortRecord.objects.filter(
        switch_record__result_file__run=run,
        switch_record__stats_type=stats_type,
        switch_record__switch_id=switch_id,
        is_terminal=False,
        target_index=target_index,
    )
    port_index = ports.order_by("port_index").values_list("port_index", flat=True).first()
    if port_index is None:
        return []
    ports = ports.filter(port_index=port_index).order_by("switch_record__ts")
    if metric != "utilization":
        return [
            (ts, int(value) if isinstance(value, bool) else value)
            for ts, value in ports.values_list("switch_record__ts", column)
        ]
    if topology is None:
        return []
    names = [switch.name for switch in topology.switches]
    if not (0 <= switch_id < len(names) and 0 <= target_index < len(names)):
        return []
    gbps = next(
        (
            link.bandwidth_gbps
            for link in topology.links
            if (link.source, link.target) == (names[switch_id], names[target_index])
        ),
        None,
    )
    if not gbps:
        return []
    samples = [
        (ts, sent or 0.0, per_interval or 0.0)
        for ts, sent, per_interval in ports.values_list(
            "switch_record__ts", "port_sent_mbit", "port_capacity_mbit_per_interval"
        )
    ]
    return [(ts, utilization) for ts, utilization, _, _ in link_utilization(samples, gbps * 1000.0)]


__all__ = [
    "SERIES_METRICS",
    "UTILIZATION_PER_STEP_LABEL",
    "X_LABEL",
    "SeriesMetric",
    "base_topology",
    "entities_for",
    "member_series",
    "metric_as_json",
    "series_metric",
    "series_metrics_as_json",
    "thin",
    "topology_entities",
]
