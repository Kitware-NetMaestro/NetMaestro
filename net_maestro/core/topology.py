"""Read-only access to the checked-in fluid-flow WAN topology presets.

The presets live in `core/data/topologies` as FFW topology YAML files, the
same format the model reads via its `topology_yaml_file` setting. This module
turns them into the flat switch/link shape the topology page renders.

TODO: Remove this module once Topology/TopologyNode/TopologyLink models exist
and topologies are user-editable rather than read-only presets.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

TOPOLOGY_DIR = Path(__file__).parent / "data" / "topologies"

# Labels that should stay uppercase.
_LABELS = {"wan": "WAN"}


class TopologyError(Exception):
    """Raised when a preset file is missing or is not a valid FFW topology."""


@dataclass(frozen=True)
class Switch:
    """One switch and its parameters."""

    name: str
    terminals: int
    terminal_bandwidth: str
    switch_buffer: str


@dataclass(frozen=True)
class Link:
    """One directed link."""

    source: str
    target: str
    bandwidth: str


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
                    "terminal_bandwidth": switch.terminal_bandwidth,
                    "switch_buffer": switch.switch_buffer,
                }
                for switch in self.switches
            ],
            "links": [
                {
                    "source": link.source,
                    "target": link.target,
                    "bandwidth": link.bandwidth,
                }
                for link in self.links
            ],
        }


def _label_from_name(name: str) -> str:
    """Turn `fluid-flow-wan-8-switch` into `Fluid Flow WAN 8 Switch`."""
    return " ".join(_LABELS.get(word, word.capitalize()) for word in name.split("-"))


def _parse(topo_name: str, path: Path) -> Topology:
    """Parse one topology YAML file into a Topology."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TopologyError(f"Could not read topology preset {path.name}: {exc}") from exc

    if not isinstance(document, dict):
        raise TopologyError(f"{path.name} is not a YAML mapping")
    switch_entries = (document.get("topology") or {}).get("switches")
    if not isinstance(switch_entries, dict):
        raise TopologyError(f"{path.name} has no topology.switches mapping")

    switches: list[Switch] = []
    links: list[Link] = []
    for name, entry in switch_entries.items():
        if not isinstance(entry, dict):
            raise TopologyError(f"{path.name}: switch {name} is not a mapping")
        switches.append(
            Switch(
                name=str(name),
                terminals=int(entry.get("terminals", 0)),
                terminal_bandwidth=str(entry.get("terminal_bandwidth", "")),
                switch_buffer=str(entry.get("switch_buffer", "")),
            )
        )
        # "connections" is directed: these are this switch's outbound links only.
        for target, bandwidth in (entry.get("connections") or {}).items():
            links.append(Link(source=str(name), target=str(target), bandwidth=str(bandwidth)))

    known = {switch.name for switch in switches}
    unknown = sorted({link.target for link in links} - known)
    if unknown:
        raise TopologyError(f"{path.name}: links point at undefined switches: {', '.join(unknown)}")

    return Topology(
        name=topo_name, label=_label_from_name(topo_name), switches=switches, links=links
    )


@lru_cache(maxsize=1)
def list_topologies() -> tuple[Topology, ...]:
    """Return every available preset, ordered by switch count then name.

    Unparseable files are logged and skipped.
    """
    topologies = []
    for path in sorted(TOPOLOGY_DIR.glob("*.yaml")):
        try:
            topologies.append(_parse(path.stem, path))
        except TopologyError:
            logger.exception("Skipping unreadable topology preset %s", path.name)
    return tuple(sorted(topologies, key=lambda t: (len(t.switches), t.name)))


def get_topology(name: str) -> Topology:
    """Return one preset by name.

    Looks the name up among the known presets rather than building a path from
    it, so a caller cannot accidentally fetch files outside `core/data/topologies`.
    """
    for topology in list_topologies():
        if topology.name == name:
            return topology
    raise TopologyError(f"Unknown topology preset: {name}")
