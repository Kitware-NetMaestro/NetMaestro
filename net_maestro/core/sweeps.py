"""Parameter sweeps: which settings an ensemble can vary and how a sweep expands.

An ensemble is a base configuration plus a list of axes, each naming one
setting and the values to try. The members are the full grid of those values.
This module holds the registry of axes each simulation type supports and turns
a posted sweep spec into the per-member settings, without touching the database
or the filesystem: `services/ensembles.py` does the writing.

A sweep spec is a list of axes, in the order the user added them:

    [{"key": "switch_buffer_gb", "values": [2, 8]},
     {"key": "link_bandwidth_gbps", "link": {"source": "STAR", "target": "MICH"},
      "values": [40, 100, 400]}]

Axes that edit the topology produce a modified Topology per member. Those
members need their own topology file, because the FFW task takes a topology by
name and the analysis page looks it up the same way.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
import itertools
from math import isfinite, prod
from typing import Any, Literal

from net_maestro.core.constants import SimulationType, SynchProtocol
from net_maestro.core.topology import Topology, TopologyError, get_topology, list_topologies

# Large enough for a few axes of a handful of values each; small enough that a
# typo (a stray value, an axis added twice over) cannot queue thousands of runs
# that execute one at a time.
MAX_ENSEMBLE_MEMBERS = 64

# The (source, target) pair a link axis applies to.
type LinkRef = tuple[str, str]
type Params = dict[str, Any]
type ApplyHook = Callable[
    [Params, Topology | None, Any, LinkRef | None], tuple[Params, Topology | None]
]


class SweepError(Exception):
    """Raised for a sweep spec that cannot be expanded. The message is shown to the user."""


@dataclass(frozen=True)
class Axis:
    """One setting a sweep can vary.

    `kind` decides how values are entered and parsed: `choice` values must be
    one of `choices()`, `number` values are numbers (whole numbers when
    `integer` is set) no smaller than `minimum`. `needs_link` marks an axis
    that applies to one link the user picks from the base topology.
    `edits_topology` marks an axis whose effect lands on the Topology rather
    than the run settings, so members it touches get a derived topology file.
    """

    key: str
    label: str
    kind: Literal["choice", "number"]
    unit: str = ""
    step: float | None = None
    needs_link: bool = False
    integer: bool = False
    minimum: float | None = None
    # When set, the minimum itself is not allowed: a link or port cannot carry zero bandwidth.
    minimum_exclusive: bool = False
    edits_topology: bool = False
    choice_source: Callable[[], list[tuple[str, str]]] | None = field(
        default=None, repr=False, compare=False
    )
    # Turns a choice's posted string back into the type the setting stores.
    coerce: Callable[[str], Any] = field(default=str, repr=False, compare=False)
    apply_hook: ApplyHook | None = field(default=None, repr=False, compare=False)

    def choices(self) -> list[tuple[str, str]]:
        """Return `(value, label)` pairs for a choice axis, or `[]` for a number axis.

        Called rather than stored so the topology choices track the files on disk.
        """
        if self.kind != "choice" or self.choice_source is None:
            return []
        return self.choice_source()

    def parse(self, raw: Any) -> Any:
        """Return one posted value as the setting stores it, or raise SweepError."""
        if self.kind == "choice":
            text = str(raw).strip()
            if text not in {value for value, _ in self.choices()}:
                raise SweepError(f"{self.label}: {text} is not one of the available choices")
            return self.coerce(text)
        return self._parse_number(raw)

    def _parse_number(self, raw: Any) -> int | float:
        # bool is an int to Python, but `true` in a value list is a mistake, not a 1.
        if isinstance(raw, bool):
            raise SweepError(f"{self.label}: {raw} is not a number")
        try:
            value = float(str(raw).strip())
        except ValueError as exc:
            raise SweepError(f"{self.label}: {raw} is not a number") from exc
        if not isfinite(value):
            raise SweepError(f"{self.label}: {raw} is not a number")
        if self.integer and not value.is_integer():
            raise SweepError(f"{self.label}: {raw} is not a whole number")
        if self.minimum is not None:
            too_small = value <= self.minimum if self.minimum_exclusive else value < self.minimum
            if too_small:
                bound = "more than" if self.minimum_exclusive else "at least"
                raise SweepError(f"{self.label}: {raw} must be {bound} {self.minimum:g}")
        # Store 8 rather than 8.0 so labels, JSON, and the YAML all read the way it was typed.
        return int(value) if value.is_integer() else value

    def apply(
        self, params: Params, topology: Topology | None, value: Any, *, link: LinkRef | None = None
    ) -> tuple[Params, Topology | None]:
        """Return the settings and topology with this axis set to `value`."""
        if self.apply_hook is None:
            return {**params, self.key: value}, topology
        return self.apply_hook(params, topology, value, link)


def _require(topology: Topology | None, axis: str) -> Topology:
    # expand_sweep loads the topology before any topology-editing axis runs.
    if topology is None:
        raise SweepError(f"{axis}: no topology to apply it to")
    return topology


def _set_switch_buffer(
    params: Params, topology: Topology | None, value: Any, _link: LinkRef | None
) -> tuple[Params, Topology | None]:
    topo = _require(topology, "Switch buffer")
    switches = [replace(s, switch_buffer_gb=float(value)) for s in topo.switches]
    return params, replace(topo, switches=switches)


def _set_terminal_bandwidth(
    params: Params, topology: Topology | None, value: Any, _link: LinkRef | None
) -> tuple[Params, Topology | None]:
    topo = _require(topology, "Terminal bandwidth")
    switches = [replace(s, terminal_bandwidth_gbps=float(value)) for s in topo.switches]
    return params, replace(topo, switches=switches)


def _set_link_bandwidth(
    params: Params, topology: Topology | None, value: Any, link: LinkRef | None
) -> tuple[Params, Topology | None]:
    """Set one link's bandwidth, and its reverse when the topology has one.

    FFW links are directed, but a physical link is a pair, and that is how the
    hand-written FABRIC presets vary STAR-MICH: both directions together. A
    one-way link stays one-way.
    """
    topo = _require(topology, "Link bandwidth")
    if link is None:
        raise SweepError("Link bandwidth: choose which link to vary")
    source, target = link
    if not any((x.source, x.target) == link for x in topo.links):
        raise SweepError(f"Link bandwidth: {source} → {target} is not a link in {topo.name}")
    both = {(source, target), (target, source)}
    links = [
        replace(x, bandwidth_gbps=float(value)) if (x.source, x.target) in both else x
        for x in topo.links
    ]
    return params, replace(topo, links=links)


def _topology_choices() -> list[tuple[str, str]]:
    return [(t.name, t.label) for t in list_topologies()]


def _sync_choices() -> list[tuple[str, str]]:
    return [(str(value), str(label)) for value, label in SynchProtocol.choices]


SWEEP_AXES: dict[str, list[Axis]] = {
    SimulationType.FFW: [
        Axis(
            key="topology_name",
            label="Topology preset",
            kind="choice",
            choice_source=_topology_choices,
        ),
        Axis(
            key="switch_buffer_gb",
            label="Switch buffer",
            kind="number",
            unit="Gb",
            step=0.5,
            minimum=0,
            edits_topology=True,
            apply_hook=_set_switch_buffer,
        ),
        Axis(
            key="terminal_bandwidth_gbps",
            label="Terminal bandwidth",
            kind="number",
            unit="Gbps",
            step=1,
            minimum=0,
            minimum_exclusive=True,
            edits_topology=True,
            apply_hook=_set_terminal_bandwidth,
        ),
        Axis(
            key="link_bandwidth_gbps",
            label="Link bandwidth",
            kind="number",
            unit="Gbps",
            step=1,
            needs_link=True,
            minimum=0,
            minimum_exclusive=True,
            edits_topology=True,
            apply_hook=_set_link_bandwidth,
        ),
        Axis(key="np", label="MPI processes", kind="number", step=1, integer=True, minimum=1),
        Axis(
            key="sync",
            label="Synchronization protocol",
            kind="choice",
            choice_source=_sync_choices,
            coerce=int,
        ),
    ],
}


def axes_for(simulation_type: str) -> list[Axis]:
    """Return the axes a simulation type can sweep, or `[]` if it has none yet."""
    return SWEEP_AXES.get(simulation_type, [])


def axes_as_json(simulation_type: str) -> list[dict[str, Any]]:
    """Return the registry in the shape the sweep builder on the ensemble form reads."""
    return [
        {
            "key": axis.key,
            "label": axis.label,
            "kind": axis.kind,
            "unit": axis.unit,
            "step": axis.step,
            "integer": axis.integer,
            "minimum": axis.minimum,
            "minimum_exclusive": axis.minimum_exclusive,
            "needs_link": axis.needs_link,
            "choices": [{"value": value, "label": label} for value, label in axis.choices()],
        }
        for axis in axes_for(simulation_type)
    ]


@dataclass(frozen=True)
class Member:
    """One point of the grid.

    `member_params` holds only the values this member varied, keyed by axis.
    `params` is the full set of run settings. `topology` is the modified
    topology when an axis edited it, still under the name of the preset it was
    derived from, or None when the member runs the preset as is; the caller
    picks the derived file's name and points `params["topology_name"]` at it.
    """

    index: int
    member_params: dict[str, Any]
    params: dict[str, Any]
    topology: Topology | None


@dataclass(frozen=True)
class _ParsedAxis:
    axis: Axis
    values: list[Any]
    link: LinkRef | None


def _parse_link(axis: Axis, raw: Any) -> LinkRef | None:
    if not axis.needs_link:
        return None
    if not isinstance(raw, dict):
        raise SweepError(f"{axis.label}: choose which link to vary")
    source = str(raw.get("source") or "").strip()
    target = str(raw.get("target") or "").strip()
    if not source or not target:
        raise SweepError(f"{axis.label}: choose which link to vary")
    return source, target


def _parse_spec(simulation_type: str, sweep_spec: Any) -> list[_ParsedAxis]:
    registry = {axis.key: axis for axis in axes_for(simulation_type)}
    if not registry:
        raise SweepError(f"Sweeps are not available for {simulation_type} simulations yet")
    if not isinstance(sweep_spec, list) or not sweep_spec:
        raise SweepError("Add at least one parameter to sweep")

    parsed: list[_ParsedAxis] = []
    seen: set[str] = set()
    for entry in sweep_spec:
        if not isinstance(entry, dict):
            raise SweepError("Each swept parameter must be an object")
        key = str(entry.get("key", ""))
        axis = registry.get(key)
        if axis is None:
            raise SweepError(f"{key or 'A blank parameter'} cannot be swept")
        if key in seen:
            raise SweepError(f"{axis.label} is swept more than once")
        seen.add(key)

        raw_values = entry.get("values")
        if not isinstance(raw_values, list) or not raw_values:
            raise SweepError(f"{axis.label}: give at least one value")
        values = [axis.parse(raw) for raw in raw_values]
        # Two equal values would make two identical members.
        if len(set(map(str, values))) != len(values):
            raise SweepError(f"{axis.label}: a value is listed more than once")
        parsed.append(
            _ParsedAxis(axis=axis, values=values, link=_parse_link(axis, entry.get("link")))
        )
    return parsed


def expand_sweep(
    simulation_type: str, base_params: dict[str, Any], sweep_spec: list[dict[str, Any]]
) -> list[Member]:
    """Return every member of the sweep, in grid order, or raise SweepError.

    The grid is the product of the axes in spec order, so the last axis varies
    fastest. Members are numbered from 1.

    Within a member, the axes that pick settings (the topology preset among
    them) apply first and the topology edits after, whatever order they were
    listed in, so buffer and link edits land on that member's preset rather
    than the base one.
    """
    axes = _parse_spec(simulation_type, sweep_spec)
    count = prod(len(a.values) for a in axes)
    if count > MAX_ENSEMBLE_MEMBERS:
        raise SweepError(
            f"This sweep has {count} members; the most an ensemble can hold is "
            f"{MAX_ENSEMBLE_MEMBERS}. Remove some values."
        )

    settings_axes = [i for i, a in enumerate(axes) if not a.axis.edits_topology]
    topology_axes = [i for i, a in enumerate(axes) if a.axis.edits_topology]
    loaded: dict[str, Topology] = {}

    def load(name: Any) -> Topology:
        name = str(name or "")
        if name not in loaded:
            try:
                loaded[name] = get_topology(name)
            except TopologyError as exc:
                raise SweepError(str(exc)) from exc
        return loaded[name]

    members = []
    for index, combo in enumerate(itertools.product(*(a.values for a in axes)), start=1):
        params: Params = dict(base_params)
        for i in settings_axes:
            params, _ = axes[i].axis.apply(params, None, combo[i], link=axes[i].link)

        topology: Topology | None = None
        if topology_axes:
            preset = load(params.get("topology_name"))
            edited: Topology | None = preset
            for i in topology_axes:
                params, edited = axes[i].axis.apply(params, edited, combo[i], link=axes[i].link)
            # An edit that lands on the preset's own values needs no file of its own.
            topology = None if edited == preset else edited

        members.append(
            Member(
                index=index,
                member_params={a.axis.key: combo[i] for i, a in enumerate(axes)},
                params=params,
                topology=topology,
            )
        )
    return members


def member_label(member_params: dict[str, Any]) -> str:
    """Return a member's varied values as one line: `switch_buffer_gb=8, np=4`."""
    return ", ".join(f"{key}={value}" for key, value in member_params.items())
