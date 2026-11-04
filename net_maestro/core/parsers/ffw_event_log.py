"""Readers for the FFW model's switch and fluid-segment CSV logs, reduced per step.

The logs are written by `model-net-fluid-flow-wan.cxx` in codes-director-ml
(`append_switch_log`, `append_fluid_segment_log`; headers in its finalize). Volume
columns carry their unit in the header suffix, `_gbit` or `_mbit` depending on the
model's output setting, so columns are found by name and every volume is returned in
Mbit. A run logs a few thousand rows per step at most, so each file is reduced in one
pass to one row per (switch, port, step) or (switch, step).

Link volumes come from the fluid-segment log, not the switch log, because only the
former says which sends were PAUSE drains: the model runs a drain in step n but
charges it to step n + 1's capacity (`schedule_pause_drain`,
`handle_switch_egress_drain`), and only charged that way does a step's volume stay
within the link's capacity. The switch log logs the same sends under the step they ran
in, so its per-link totals match the fluid-segment log's; it is read for the
switch-wide buffer state instead.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# Fluid-segment events that move volume out of a port, and the one charged a step late.
SEND_EVENTS = frozenset(
    {"allocate_send_arrival", "allocate_send_buffered", "allocate_send_pause_drain"}
)
DRAIN_EVENT = "allocate_send_pause_drain"

_UNIT_SCALE = {"mbit": 1.0, "gbit": 1000.0}

# The model prints volumes with six significant digits, so a saturated step's sends,
# each rounded, can sum to a few parts per million over the port's capacity. The
# model itself never charges a step more than capacity (it stops with an error), so
# an overshoot below this fraction of capacity is rounding and is clamped away.
CAPACITY_ROUNDING = 1e-4

logger = logging.getLogger(__name__)


class EventLogError(ValueError):
    """Raised when a log's header lacks a column the reduction needs."""


@dataclass(frozen=True)
class LinkStep:
    """What one switch port sent in one charged step, in Mbit."""

    switch_id: int
    port: int
    target_is_terminal: bool
    target_index: int
    step: int
    sent_mbit: float
    capacity_mbit: float


@dataclass(frozen=True)
class SwitchStep:
    """One switch's shared-buffer peak, size and drops in one step, in Mbit."""

    switch_id: int
    step: int
    peak_occupancy_mbit: float
    buffer_mbit: float
    dropped_mbit: float


class _Volumes:
    """Find volume columns by base name in a header, whatever unit suffix they carry."""

    def __init__(self, fieldnames: Iterable[str]) -> None:
        self._columns: dict[str, tuple[str, float]] = {}
        for name in fieldnames:
            base, _, unit = name.rpartition("_")
            if base and unit in _UNIT_SCALE:
                self._columns[base] = (name, _UNIT_SCALE[unit])

    def require(self, *bases: str) -> None:
        missing = [base for base in bases if base not in self._columns]
        if missing:
            raise EventLogError(f"Log header has no {', '.join(missing)} column")

    def mbit(self, row: dict[str, str], base: str) -> float:
        column, scale = self._columns[base]
        return float(row[column] or 0.0) * scale


def _reader(lines: Iterable[str], *columns: str) -> tuple[csv.DictReader[str], _Volumes] | None:
    """Return a reader and the volume columns, or None for an empty file."""
    reader = csv.DictReader(lines)
    if reader.fieldnames is None:
        return None
    missing = [column for column in columns if column not in reader.fieldnames]
    if missing:
        raise EventLogError(f"Log header has no {', '.join(missing)} column")
    return reader, _Volumes(reader.fieldnames)


def link_steps(lines: Iterable[str]) -> list[LinkStep]:
    """Reduce a fluid-segment log to each port's volume per charged step.

    Sends are summed per (switch, port, step), with a PAUSE drain moved to the step
    after the one it ran in, and a sum over capacity by no more than the log's
    rounding is clamped to capacity (see `CAPACITY_ROUNDING`). Rows of other events
    (arrivals staged, residuals enqueued, drops) carry no send and are skipped, as
    are events this reader does not know, so a model that logs more still parses.
    """
    parsed = _reader(lines, "interval", "event", "switch", "port", "target_type", "target_index")
    if parsed is None:
        return []
    reader, volumes = parsed
    volumes.require("send", "capacity")
    # Keyed by (switch, port, charged step); meta is (to a terminal, target, capacity).
    sent: dict[tuple[int, int, int], float] = {}
    meta: dict[tuple[int, int, int], tuple[bool, int, float]] = {}
    for row in reader:
        event = row["event"]
        if event not in SEND_EVENTS:
            continue
        step = int(row["interval"]) + (1 if event == DRAIN_EVENT else 0)
        key = (int(row["switch"]), int(row["port"]), step)
        sent[key] = sent.get(key, 0.0) + volumes.mbit(row, "send")
        capacity = volumes.mbit(row, "capacity")
        previous = meta.get(key)
        meta[key] = (
            row["target_type"] == "terminal",
            int(row["target_index"]),
            capacity if previous is None else max(previous[2], capacity),
        )
    steps = []
    for key, total in sorted(sent.items()):
        target_is_terminal, target_index, capacity = meta[key]
        steps.append(
            LinkStep(
                switch_id=key[0],
                port=key[1],
                target_is_terminal=target_is_terminal,
                target_index=target_index,
                step=key[2],
                sent_mbit=_within_capacity(key, total, capacity),
                capacity_mbit=capacity,
            )
        )
    return steps


def _within_capacity(key: tuple[int, int, int], sent: float, capacity: float) -> float:
    """Clamp a step's summed sends to capacity when they exceed it only by rounding.

    A larger overshoot is kept, and logged: it would mean the drain shift or the
    log format no longer matches the model, and hiding it would hide that.
    """
    if sent <= capacity:
        return sent
    if sent <= capacity * (1 + CAPACITY_ROUNDING):
        return capacity
    logger.warning(
        "Switch %s port %s step %s: logged sends %.6g Mbit exceed capacity %.6g Mbit",
        *key,
        sent,
        capacity,
    )
    return sent


def switch_steps(lines: Iterable[str]) -> list[SwitchStep]:
    """Reduce a switch log to each switch's shared-buffer peak and drops per step.

    The peak is the most queued in the shared buffer before or after any egress the
    switch ran in the step: an egress that buffers an arrival's residual leaves more
    queued than it found, and the next egress may be a PAUSE drain that empties it
    again, so both ends count. Drops are summed over every row of the step, the
    no-route drops (logged with port -1) included; those rows also count toward the
    peak, since their occupancies are the buffer's at that moment too.
    """
    parsed = _reader(lines, "interval", "event", "switch")
    if parsed is None:
        return []
    reader, volumes = parsed
    volumes.require("shared_queued_before", "shared_queued_after", "shared_buffer", "dropped")
    steps: dict[tuple[int, int], list[float]] = {}  # [peak, buffer, dropped]
    for row in reader:
        switch_id = int(row["switch"])
        if switch_id < 0:
            continue
        key = (switch_id, int(row["interval"]))
        occupancy = max(
            volumes.mbit(row, "shared_queued_before"), volumes.mbit(row, "shared_queued_after")
        )
        state = steps.setdefault(key, [0.0, 0.0, 0.0])
        state[0] = max(state[0], occupancy)
        state[1] = max(state[1], volumes.mbit(row, "shared_buffer"))
        state[2] += volumes.mbit(row, "dropped")
    return [
        SwitchStep(
            switch_id=switch_id,
            step=step,
            peak_occupancy_mbit=peak,
            buffer_mbit=buffer,
            dropped_mbit=dropped,
        )
        for (switch_id, step), (peak, buffer, dropped) in sorted(steps.items())
    ]


def sent_per_link_from_switch_log(lines: Iterable[str]) -> dict[tuple[int, int], float]:
    """Return each port's total `egress` volume in a switch log, in Mbit.

    A cross-check: these totals equal the fluid-segment log's sends per port.
    """
    parsed = _reader(lines, "event", "switch", "port")
    if parsed is None:
        return {}
    reader, volumes = parsed
    volumes.require("sent")
    totals: dict[tuple[int, int], float] = {}
    for row in reader:
        if row["event"] != "egress":
            continue
        key = (int(row["switch"]), int(row["port"]))
        totals[key] = totals.get(key, 0.0) + volumes.mbit(row, "sent")
    return totals


__all__ = [
    "CAPACITY_ROUNDING",
    "DRAIN_EVENT",
    "SEND_EVENTS",
    "EventLogError",
    "LinkStep",
    "SwitchStep",
    "link_steps",
    "sent_per_link_from_switch_log",
    "switch_steps",
]
