"""Hard-coded fluid-flow WAN topologies, standing in for `wan-topology-editing`.

Same public API and data as the file-backed `topology.py` on that branch, so
callers written against this work unchanged once it merges and replaces this
module. The data is the branch's three presets in `data/topologies/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# The LP type names the model registers. A traffic config's group has to use
# these exact strings for the counts to reach the right LPs.
SWITCH_LP_NAME = "fluid-flow-wan-switch-lp"
TERMINAL_LP_NAME = "fluid-flow-wan-terminal-lp"

# Labels that should stay uppercase.
_LABELS = {"wan": "WAN"}


class TopologyError(Exception):
    """Raised when a topology is missing."""


@dataclass(frozen=True)
class Switch:
    """One switch and its parameters, in gigabits."""

    name: str
    terminals: int
    terminal_bandwidth_gbps: float
    switch_buffer_gb: float


@dataclass(frozen=True)
class Link:
    """One directed link, in gigabits."""

    source: str
    target: str
    bandwidth_gbps: float


@dataclass(frozen=True)
class Topology:
    """A preset: its name, switches, and links."""

    name: str
    label: str
    switches: list[Switch]
    links: list[Link]

    @property
    def terminal_count(self) -> int:
        return sum(switch.terminals for switch in self.switches)

    def summary(self) -> str:
        """Return a description for the preset dropdown."""
        return (
            f"{len(self.switches)} switches, "
            f"{self.terminal_count} terminals, "
            f"{len(self.links)} links"
        )

    def simulation_inputs(self) -> dict[str, Any]:
        """Return what a traffic config has to take from this topology.

        The model instantiates one LP per switch and one per terminal, so the
        traffic config's group has to declare exactly these counts, and it
        names the topology by file. Terminals are numbered by walking the
        switches in file order, which is the numbering a traffic trace's
        `source_terminal` and `destination_terminal` columns refer to; each
        switch reports where its own run of terminal ids begins.
        """
        switches = []
        first_terminal_id = 0
        for switch in self.switches:
            switches.append(
                {
                    "name": switch.name,
                    "first_terminal_id": first_terminal_id,
                    "terminal_count": switch.terminals,
                    "terminal_bandwidth_gbps": switch.terminal_bandwidth_gbps,
                }
            )
            first_terminal_id += switch.terminals

        return {
            "name": self.name,
            "topology_yaml_file": f"{self.name}.yaml",
            "switch_count": len(self.switches),
            "terminal_count": self.terminal_count,
            "lps": {
                SWITCH_LP_NAME: len(self.switches),
                TERMINAL_LP_NAME: self.terminal_count,
            },
            "switches": switches,
        }

    def as_dict(self) -> dict[str, Any]:
        """Return the JSON that the topology canvas requires."""
        return {
            "name": self.name,
            "label": self.label,
            "summary": self.summary(),
            "switches": [
                {
                    "name": switch.name,
                    "terminals": switch.terminals,
                    "terminal_bandwidth_gbps": switch.terminal_bandwidth_gbps,
                    "switch_buffer_gb": switch.switch_buffer_gb,
                }
                for switch in self.switches
            ],
            "links": [
                {
                    "source": link.source,
                    "target": link.target,
                    "bandwidth_gbps": link.bandwidth_gbps,
                    "bandwidth_label": _short_rate(link.bandwidth_gbps),
                }
                for link in self.links
            ],
        }


def _short_rate(gbps: float) -> str:
    """Round a rate for display: `18.3324` becomes `18.3 Gbps`.

    The generator emits rates to four decimals, which is more precision than a
    canvas edge label can carry.
    """
    return f"{round(gbps, 1):g} Gbps"


def _label_from_name(name: str) -> str:
    """Turn `fluid-flow-wan-8-switch` into `Fluid Flow WAN 8 Switch`."""
    return " ".join(_LABELS.get(word, word.capitalize()) for word in name.split("-"))


def _topology(name: str, *, switches: list[Switch], links: list[Link]) -> Topology:
    return Topology(name=name, label=_label_from_name(name), switches=switches, links=links)


_TOPOLOGIES: tuple[Topology, ...] = (
    _topology(
        "fluid-flow-wan-3-switch",
        switches=[
            Switch("A", 2, 100, 64),
            Switch("B", 2, 100, 64),
            Switch("C", 2, 100, 64),
        ],
        links=[
            Link("A", "B", 30),
            Link("B", "A", 30),
            Link("B", "C", 10),
            Link("C", "A", 20),
            Link("C", "B", 10),
        ],
    ),
    _topology(
        "fluid-flow-wan-8-switch",
        switches=[
            Switch("S00", 2, 100, 64),
            Switch("S01", 2, 100, 64),
            Switch("S02", 2, 100, 64),
            Switch("S03", 2, 100, 64),
            Switch("S04", 2, 100, 64),
            Switch("S05", 2, 100, 64),
            Switch("S06", 2, 100, 64),
            Switch("S07", 2, 100, 64),
        ],
        links=[
            Link("S00", "S01", 18.3324),
            Link("S00", "S06", 10.0691),
            Link("S00", "S07", 10.2034),
            Link("S01", "S00", 15.9728),
            Link("S01", "S02", 26.5041),
            Link("S02", "S01", 13.8732),
            Link("S02", "S03", 17.3682),
            Link("S03", "S02", 13.2338),
            Link("S03", "S04", 21.3202),
            Link("S03", "S05", 16.4408),
            Link("S04", "S01", 23.0508),
            Link("S04", "S03", 18.6587),
            Link("S04", "S05", 12.4853),
            Link("S05", "S04", 13.4869),
            Link("S05", "S06", 21.2416),
            Link("S06", "S02", 12.9629),
            Link("S06", "S05", 17.098),
            Link("S06", "S07", 21.0644),
            Link("S07", "S00", 29.1613),
            Link("S07", "S06", 11.8259),
        ],
    ),
    _topology(
        "fluid-flow-wan-16-switch",
        switches=[
            Switch("S00", 4, 100, 64),
            Switch("S01", 4, 100, 64),
            Switch("S02", 4, 100, 64),
            Switch("S03", 4, 100, 64),
            Switch("S04", 4, 100, 64),
            Switch("S05", 4, 100, 64),
            Switch("S06", 4, 100, 64),
            Switch("S07", 4, 100, 64),
            Switch("S08", 4, 100, 64),
            Switch("S09", 4, 100, 64),
            Switch("S10", 4, 100, 64),
            Switch("S11", 4, 100, 64),
            Switch("S12", 4, 100, 64),
            Switch("S13", 4, 100, 64),
            Switch("S14", 4, 100, 64),
            Switch("S15", 4, 100, 64),
        ],
        links=[
            Link("S00", "S01", 14.3443),
            Link("S00", "S06", 13.2298),
            Link("S00", "S15", 16.2939),
            Link("S01", "S00", 10.12),
            Link("S01", "S02", 14.1858),
            Link("S02", "S01", 23.1456),
            Link("S02", "S03", 16.6414),
            Link("S02", "S11", 12.223),
            Link("S03", "S02", 25.1861),
            Link("S03", "S04", 10.0668),
            Link("S04", "S03", 13.5568),
            Link("S04", "S05", 15.6573),
            Link("S04", "S06", 27.2667),
            Link("S04", "S12", 28.2996),
            Link("S05", "S04", 12.7346),
            Link("S05", "S06", 12.7542),
            Link("S05", "S12", 27.6106),
            Link("S05", "S14", 17.0721),
            Link("S06", "S00", 25.2518),
            Link("S06", "S01", 13.0039),
            Link("S06", "S05", 24.9571),
            Link("S06", "S07", 28.3648),
            Link("S06", "S08", 10.2275),
            Link("S06", "S09", 25.1736),
            Link("S07", "S06", 25.0448),
            Link("S07", "S08", 11.8869),
            Link("S07", "S15", 19.3918),
            Link("S08", "S07", 11.7887),
            Link("S08", "S09", 27.327),
            Link("S09", "S08", 16.7876),
            Link("S09", "S10", 12.0942),
            Link("S10", "S09", 23.4209),
            Link("S10", "S11", 14.793),
            Link("S11", "S02", 21.8699),
            Link("S11", "S04", 16.5819),
            Link("S11", "S10", 29.3853),
            Link("S11", "S12", 17.3532),
            Link("S12", "S05", 20.3732),
            Link("S12", "S08", 23.3879),
            Link("S12", "S11", 10.8492),
            Link("S12", "S13", 15.9541),
            Link("S13", "S12", 25.9734),
            Link("S13", "S14", 16.2352),
            Link("S14", "S13", 21.6147),
            Link("S14", "S15", 10.7626),
            Link("S15", "S00", 10.4723),
            Link("S15", "S07", 10.0513),
            Link("S15", "S14", 29.346),
        ],
    ),
)


def list_topologies() -> tuple[Topology, ...]:
    """Return every available topology, ordered by switch count then name."""
    return tuple(sorted(_TOPOLOGIES, key=lambda t: (len(t.switches), t.name)))


def get_topology(name: str) -> Topology:
    """Return one topology by name."""
    for topology in _TOPOLOGIES:
        if topology.name == name:
            return topology
    raise TopologyError(f"Unknown topology: {name}")
