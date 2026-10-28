"""Per-run summaries: the few numbers that say what a run produced and whether to trust it.

The ensemble pages compare dozens of members, and each FFW run carries hundreds of
thousands of sample rows, so the headline numbers are aggregated once, when a run
finishes, into a `RunSummary` row. This module holds the registry of those numbers
(`METRICS`), the code that computes them from a run's rows, and the health checks
that flag a run whose numbers shouldn't be trusted.

What the FFW sample fields mean (see codes-director-ml's
`doc/model-stats-binary-format.md`) drives how each one is aggregated:

- Volumes, frame counters and pause times are deltas since the previous sample of the
  same sampling mode, so they are summed.
- Backlogs and buffer occupancies are gauges, so they are read at the last sample or
  maxed, never summed.
- The GVT and RT modes share one accumulator and VT keeps its own, so summing across
  modes double-counts. One mode is chosen per run (VT, else GVT, else RT) and every
  query uses only that mode's rows.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import pairwise
import logging
from typing import TYPE_CHECKING, Any

from django.db.models import Avg, F, FloatField, Max, Sum
from django.db.models.functions import Cast

from net_maestro.core.constants import FFWStatsType, RunStatus, SimulationType
from net_maestro.core.models import (
    FFWPortRecord,
    FFWSwitchRecord,
    FFWTerminalRecord,
    RunSummary,
    SimulationPeRecord,
)
from net_maestro.core.topology import TopologyError, get_topology

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from django.db.models import QuerySet

    from net_maestro.core.models import Run
    from net_maestro.core.topology import Topology

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Metric:
    """One number a summary can carry, and how to show and rank it.

    `lower_is_better` is None for numbers that have no better direction (how much
    traffic was offered, say), which keeps them out of best/worst rankings.
    """

    key: str
    label: str
    unit: str = ""
    lower_is_better: bool | None = None
    digits: int = 1


FFW_METRICS: list[Metric] = [
    Metric("generated_mbit", "Generated", "Mbit"),
    Metric("delivered_mbit", "Delivered", "Mbit", lower_is_better=False),
    Metric("dropped_mbit", "Dropped", "Mbit", lower_is_better=True),
    Metric("delivered_frac", "Delivered fraction", "", lower_is_better=False, digits=3),
    Metric("end_backlog_mbit", "Backlog at end", "Mbit", lower_is_better=True),
    Metric(
        "peak_buffer_occupancy_frac", "Peak buffer occupancy", "", lower_is_better=True, digits=3
    ),
    Metric(
        "mean_buffer_occupancy_frac", "Mean buffer occupancy", "", lower_is_better=True, digits=3
    ),
    Metric("pause_frames_sent", "PAUSE frames sent", "", lower_is_better=True, digits=0),
    Metric("pause_time_s", "Link pause time", "s", lower_is_better=True, digits=3),
    Metric(
        "bottleneck_peak_utilization",
        "Bottleneck peak utilization",
        "",
        lower_is_better=True,
        digits=3,
    ),
    Metric(
        "bottleneck_mean_utilization",
        "Bottleneck mean utilization",
        "",
        lower_is_better=True,
        digits=3,
    ),
]

ENGINE_METRICS: list[Metric] = [
    Metric("wall_time_s", "Wall time", "s", lower_is_better=True),
    Metric("events_processed", "Events processed", "", digits=0),
    Metric("events_rolled_back", "Events rolled back", "", lower_is_better=True, digits=0),
    Metric("efficiency_pct", "Efficiency", "%", lower_is_better=False),
]

# Model metrics per simulation type. Engine metrics are appended by `metrics_for` for
# any run that has engine rows, whatever produced it.
METRICS: dict[str, list[Metric]] = {
    SimulationType.FFW: FFW_METRICS,
    SimulationType.PHOLD: [],
    SimulationType.ESNET: [],
}

# The three numbers agreed as the headline for FFW runs.
HEADLINE_METRICS = ["dropped_mbit", "peak_buffer_occupancy_frac", "bottleneck_peak_utilization"]

# Sampling modes in order of preference. VT samples are complete on their own; GVT and
# RT split one accumulator between them (see the module docstring).
_STATS_TYPE_PREFERENCE = (FFWStatsType.VT, FFWStatsType.GVT, FFWStatsType.RT)

# Tolerance for the conservation and drained checks, as a fraction of generated volume.
_TOLERANCE = 0.01

NS_PER_S = 1e9


def metrics_for(simulation_type: str, *, with_engine: bool) -> list[Metric]:
    """Return the metrics a run of this type can carry, model metrics first."""
    metrics = list(METRICS.get(simulation_type, []))
    if with_engine:
        metrics.extend(ENGINE_METRICS)
    return metrics


def metric_by_key(key: str) -> Metric | None:
    """Return the registry entry for `key`, from any simulation type."""
    for metric in [*FFW_METRICS, *ENGINE_METRICS]:
        if metric.key == key:
            return metric
    return None


def metrics_as_json(
    metrics: Iterable[Metric], values: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Return the metrics as plain dicts for templates and JSON.

    With `values` (a summary's `metrics`), each dict also carries its `value`, None
    when the summary doesn't have it.
    """
    rows = []
    for metric in metrics:
        row = asdict(metric)
        if values is not None:
            row["value"] = values.get(metric.key)
        rows.append(row)
    return rows


def compute_run_summary(run: Run) -> RunSummary | None:
    """Compute and store the run's summary, replacing any earlier one.

    Returns None, and removes any stale summary, when the run has neither FFW nor
    engine rows: there is nothing to summarize.
    """
    stats_type = _choose_stats_type(run)
    engine_rows = _engine_rows(run)
    has_engine = engine_rows.exists()
    if stats_type is None and not has_engine:
        RunSummary.objects.filter(run=run).delete()
        return None

    metrics: dict[str, float | int | None] = {}
    details: dict[str, Any] = {}
    checks: list[dict[str, Any]] = []

    if stats_type is not None:
        _ffw_metrics(run, stats_type, metrics, details, checks)
    else:
        checks.append(
            _check("has_data", "Has data", ok=True, detail=f"{engine_rows.count()} engine samples")
        )

    if has_engine:
        metrics.update(_engine_metrics(engine_rows))
    # Wall time comes from the run's own timestamps, so it is there for any run the
    # tasks timed, engine stats or not.
    metrics["wall_time_s"] = run.wall_time_s

    completed = run.status == RunStatus.COMPLETED
    checks.append(_check("completed", "Completed", ok=completed, detail=f"Status is {run.status}"))

    summary, _ = RunSummary.objects.update_or_create(
        run=run,
        defaults={
            "stats_type": stats_type or "",
            "metrics": metrics,
            "details": details,
            "health": {"ok": all(check["ok"] for check in checks), "checks": checks},
        },
    )
    return summary


def _check(key: str, label: str, *, ok: bool, detail: str) -> dict[str, Any]:
    return {"key": key, "label": label, "ok": ok, "detail": detail}


def _choose_stats_type(run: Run) -> str | None:
    """Return the sampling mode to summarize, the first in preference with any rows.

    Switch rows decide it; terminal rows only when no mode has switch rows, so a run
    with model stats but no switch data still gets its traffic totals.
    """
    for model, lookup in (
        (FFWSwitchRecord, "result_file__run"),
        (FFWTerminalRecord, "result_file__run"),
    ):
        for stats_type in _STATS_TYPE_PREFERENCE:
            if model.objects.filter(**{lookup: run}, stats_type=stats_type).exists():
                return str(stats_type)
    return None


def _ffw_metrics(
    run: Run,
    stats_type: str,
    metrics: dict[str, float | int | None],
    details: dict[str, Any],
    checks: list[dict[str, Any]],
) -> None:
    """Fill in the FFW metrics, their details and the FFW health checks."""
    terminals = FFWTerminalRecord.objects.filter(result_file__run=run, stats_type=stats_type)
    switches = FFWSwitchRecord.objects.filter(result_file__run=run, stats_type=stats_type)
    ports = FFWPortRecord.objects.filter(
        switch_record__result_file__run=run, switch_record__stats_type=stats_type
    )
    topology = _topology_for(run)
    switch_names = [switch.name for switch in topology.switches] if topology else []

    def switch_name(switch_id: int) -> str:
        return switch_names[switch_id] if 0 <= switch_id < len(switch_names) else str(switch_id)

    traffic = terminals.aggregate(
        generated=Sum("generated_mbit"),
        injected=Sum("sent_to_switch_mbit"),
        delivered=Sum("received_mbit"),
    )
    # Backlog is a gauge: each terminal's value at its last sample.
    last_backlogs = (
        terminals.order_by("terminal_id", "-ts")
        .distinct("terminal_id")
        .values_list("source_backlog_mbit", flat=True)
    )
    has_terminals = terminals.exists()
    generated = traffic["generated"]
    delivered = traffic["delivered"]
    end_backlog = sum(value or 0.0 for value in last_backlogs) if has_terminals else None

    switch_totals = switches.aggregate(
        dropped=Sum("dropped_mbit"), pause_frames=Sum("pause_frames_sent")
    )
    dropped = switch_totals["dropped"]

    # Volume that left a source but had not reached a terminal or been dropped by the
    # last sample: in switch buffers, on access links, or between fluid phases.
    in_flight = (
        traffic["injected"] - (delivered or 0.0) - (dropped or 0.0)
        if traffic["injected"] is not None
        else None
    )
    details["in_flight_mbit"] = in_flight

    metrics["generated_mbit"] = generated
    metrics["delivered_mbit"] = delivered
    metrics["dropped_mbit"] = dropped
    metrics["delivered_frac"] = (
        delivered / generated if generated and delivered is not None else None
    )
    metrics["end_backlog_mbit"] = end_backlog
    metrics["pause_frames_sent"] = switch_totals["pause_frames"]
    pause_ns = ports.aggregate(total=Sum("port_pause_time_ns"))["total"]
    metrics["pause_time_s"] = pause_ns / NS_PER_S if pause_ns is not None else None

    # Occupancy over capacity per switch sample. Capacity is static, but guarding it
    # keeps a zero-buffer switch from dividing by zero.
    occupancy = switches.filter(
        shared_buffer_capacity_mbit__gt=0, shared_buffer_occupancy_mbit__isnull=False
    ).annotate(
        frac=Cast(F("shared_buffer_occupancy_mbit"), FloatField())
        / F("shared_buffer_capacity_mbit")
    )
    buffer = occupancy.aggregate(peak=Max("frac"), mean=Avg("frac"))
    metrics["peak_buffer_occupancy_frac"] = buffer["peak"]
    metrics["mean_buffer_occupancy_frac"] = buffer["mean"]
    peak_switch = (
        occupancy.order_by(F("frac").desc(nulls_last=True), "ts")
        .values_list("switch_id", flat=True)
        .first()
    )
    details["peak_buffer_switch"] = switch_name(peak_switch) if peak_switch is not None else None

    if topology is None:
        metrics["bottleneck_peak_utilization"] = None
        metrics["bottleneck_mean_utilization"] = None
        details["bottleneck_link"] = None
        checks.append(
            _check(
                "topology",
                "Topology",
                ok=True,
                detail="Topology file not readable; link utilization not computed",
            )
        )
    else:
        _bottleneck(ports, topology, metrics, details)

    has_data = switches.exists() or has_terminals
    checks.append(
        _check(
            "has_data",
            "Has data",
            ok=has_data,
            detail=(
                f"{switches.count()} switch and {terminals.count()} terminal samples ({stats_type})"
            ),
        )
    )
    checks.extend(
        _traffic_checks(
            generated=generated,
            injected=traffic["injected"],
            delivered=delivered,
            dropped=dropped,
            end_backlog=end_backlog,
            in_flight=in_flight,
        )
    )


def _traffic_checks(  # noqa: PLR0913
    *,
    generated: float | None,
    injected: float | None,
    delivered: float | None,
    dropped: float | None,
    end_backlog: float | None,
    in_flight: float | None,
) -> list[dict[str, Any]]:
    """Check that volume is conserved and that the network drained by the last sample.

    Every generated megabit should end up delivered, dropped, still waiting at its
    source, or in flight inside the network. In-flight volume is only known as what
    the sources injected less what came out, so conservation is checked where both
    ends are measured independently: at the sources (generated = injected + backlog)
    and across the network (nothing delivered or dropped that wasn't injected).

    Draining is separate. VT sampling stops at `vt_samp_end`, which can be before
    the traffic finishes, and then backlog and in-flight volume are large; the
    totals are still right for the sampled window, but they are partial for the run.
    """
    gen = generated or 0.0
    inj = injected or 0.0
    out = (delivered or 0.0) + (dropped or 0.0)
    backlog = end_backlog or 0.0
    flight = in_flight or 0.0
    tolerance = _TOLERANCE * gen
    gbit = 1000.0
    detail = (
        f"Generated {gen / gbit:.2f} Gbit, delivered {(delivered or 0.0) / gbit:.2f}, "
        f"dropped {(dropped or 0.0) / gbit:.2f}, backlog {backlog / gbit:.2f}, "
        f"in flight {flight / gbit:.2f}"
    )
    if gen == 0:
        conserved = inj == 0 and out == 0 and backlog == 0
        drained = backlog == 0 and flight == 0
    else:
        conserved = abs(gen - (inj + backlog)) <= tolerance and out <= inj + tolerance
        drained = backlog + flight <= tolerance
    drain_detail = (
        f"Backlog {backlog / gbit:.2f} Gbit and {flight / gbit:.2f} Gbit in flight"
        " at the last sample"
    )
    if gen:
        drain_detail += f" ({(backlog + flight) / gen:.1%} of generated)"
    return [
        _check("conservation", "Volume conserved", ok=conserved, detail=detail),
        _check("drained", "Drained by end", ok=drained, detail=drain_detail),
    ]


def _bottleneck(
    ports: QuerySet[FFWPortRecord],
    topology: Topology,
    metrics: dict[str, float | int | None],
    details: dict[str, Any],
) -> None:
    """Find the switch-to-switch link that came closest to its capacity.

    A sample's utilization is the volume the port sent since the previous sample
    over what the link could carry in that time, bandwidth times dt. The fluid model
    moves a whole interval's volume at once (`interval_seconds`, 1 s for the FABRIC
    configs) while VT samples come every 0.1 s, so a sample shorter than an interval
    is measured against one interval's capacity (`port_capacity_mbit_per_interval`)
    instead; otherwise a saturated link would read as 10x its bandwidth. The first
    sample of each port is skipped since its interval start isn't sampled. The mean
    for the bottleneck link is total sent over bandwidth times the span from the
    first sample to the last, over the same samples.
    """
    bandwidth = {(link.source, link.target): link.bandwidth_gbps for link in topology.links}
    names = [switch.name for switch in topology.switches]
    rows = (
        ports.filter(is_terminal=False, target_index__gte=0)
        .order_by("switch_record__switch_id", "port_index", "switch_record__ts")
        .values_list(
            "switch_record__switch_id",
            "port_index",
            "target_index",
            "switch_record__ts",
            "port_sent_mbit",
            "port_capacity_mbit_per_interval",
        )
    )
    series: dict[tuple[int, int, int | None], list[tuple[float, float, float]]] = defaultdict(list)
    for switch_id, port_index, target_index, ts, sent, per_interval in rows:
        series[(switch_id, port_index, target_index)].append((ts, sent or 0.0, per_interval or 0.0))

    best: tuple[float, str, float] | None = None  # (peak, link label, mean)
    for (switch_id, _port, target_index), samples in series.items():
        if target_index is None or not (
            0 <= switch_id < len(names) and 0 <= target_index < len(names)
        ):
            continue
        source, target = names[switch_id], names[target_index]
        gbps = bandwidth.get((source, target))
        if not gbps:
            continue
        mbit_per_s = gbps * 1000.0
        peak = None
        sent_total = 0.0
        span_s = 0.0
        for (prev_ts, _, _), (ts, sent, per_interval) in pairwise(samples):
            dt_s = (ts - prev_ts) / NS_PER_S
            if dt_s <= 0:
                continue
            utilization = sent / max(mbit_per_s * dt_s, per_interval)
            peak = utilization if peak is None else max(peak, utilization)
            sent_total += sent
            span_s += dt_s
        if peak is None:
            continue
        mean = sent_total / (mbit_per_s * span_s)
        # Saturated links all peak at 1.0, give or take rounding, so the busier
        # one on average breaks the tie.
        if best is None or (round(peak, 6), mean) > (round(best[0], 6), best[2]):
            best = (peak, f"{source} → {target}", mean)

    metrics["bottleneck_peak_utilization"] = best[0] if best else None
    metrics["bottleneck_mean_utilization"] = best[2] if best else None
    details["bottleneck_link"] = best[1] if best else None


def _topology_for(run: Run) -> Topology | None:
    """Return the run's topology, or None when it has no FFW config or the file is gone.

    Like `rest.run_api._topology_for`, this assumes a switch's position in
    `topology.switches` is its `switch_id`, which is how the model numbers them.
    """
    config = run.ffw_configs.order_by("-id").first()
    if config is None:
        return None
    try:
        return get_topology(config.topology_name)
    except TopologyError:
        logger.warning("Run %s: topology %r is not readable", run.pk, config.topology_name)
        return None


def _engine_rows(run: Run) -> QuerySet[SimulationPeRecord]:
    """Return the run's PE rows from one sampling mode.

    PE rows carry no mode of their own; PHOLD ingests both its GVT and RT engine
    files, whose deltas cover the same work, so summing both would double-count.
    The mode is read from the file name, GVT preferred.
    """
    rows = SimulationPeRecord.objects.filter(simulation_file__run=run)
    for mode in ("gvt", "rt"):
        moded = rows.filter(simulation_file__file__contains=f"-{mode}")
        if moded.exists():
            return moded
    return rows


def _engine_metrics(rows: QuerySet[SimulationPeRecord]) -> dict[str, float | int | None]:
    """Return totals of the ROSS engine counters.

    ROSS writes each PE counter as the difference from the previous sample of the
    same mode (`st_collect_engine_data_pes` in ROSS's `st-sim-engine.c` subtracts
    `last_pe_stats[col_type]`), so the counts are summed. Efficiency is recomputed
    from those totals with ROSS's own formula, `100 * (1 - rolled_back / (processed
    - rolled_back))`, rather than averaged across samples, which would weight a
    nearly empty interval like a busy one.

    `real_time` is not used for wall time: it is a raw hardware cycle counter over
    the clock rate (time since boot, not since the run began), so neither its
    maximum nor its spread is the run's duration.
    """
    totals = rows.aggregate(
        processed=Sum("events_processed"), rolled_back=Sum("events_rolled_back")
    )
    processed = totals["processed"]
    rolled_back = totals["rolled_back"]
    efficiency = None
    if processed is not None and rolled_back is not None:
        net = processed - rolled_back
        efficiency = 100.0 * (1.0 - rolled_back / net) if net > 0 else 0.0
    return {
        "events_processed": processed,
        "events_rolled_back": rolled_back,
        "efficiency_pct": efficiency,
    }


__all__ = [
    "ENGINE_METRICS",
    "FFW_METRICS",
    "HEADLINE_METRICS",
    "METRICS",
    "Metric",
    "compute_run_summary",
    "metric_by_key",
    "metrics_as_json",
    "metrics_for",
]
