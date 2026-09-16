"""Access to the checked-in fluid-flow WAN topology presets.

The presets live in `core/data/topologies` as FFW topology YAML files, the
same format the model reads via its `topology_yaml_file` setting. This module
turns them into the flat switch/link shape the topology page renders, and
writes new presets back out in that format.

TODO: Remove this module once Topology/TopologyNode/TopologyLink models exist
and topologies are database-backed rather than files.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
from math import isfinite
from pathlib import Path
import re
from typing import Any

import yaml

logger = logging.getLogger(__name__)

TOPOLOGY_DIR = Path(__file__).parent / "data" / "topologies"

# Labels that should stay uppercase.
_LABELS = {"wan": "WAN"}

# A name is also the file stem and the detail URL segment, so hold it to what
# the `slug` URL converter accepts.
_NAME_RE = re.compile(r"^[-a-zA-Z0-9_]+$")


class TopologyError(Exception):
    """Raised when a preset file is missing or is not a valid FFW topology."""


class DuplicateTopologyError(TopologyError):
    """Raised when saving would overwrite an existing preset file."""


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


def _gigabits(raw: Any, field: str, unit: str) -> float:
    """Read a gigabit value, with or without its unit: `64 Gb` or `64`.

    Only gigabits are supported for now, so any other unit is an error rather
    than a silently misread number. The match is case sensitive.
    """
    text = str(raw).strip()
    number, _, suffix = text.partition(" ")
    if suffix and suffix.strip() != unit:
        raise TopologyError(f"{field}: expected a value in {unit}, got {text}")
    try:
        value = float(number)
    except ValueError as exc:
        raise TopologyError(f"{field}: {text} is not a number") from exc
    if not isfinite(value) or value < 0:
        raise TopologyError(f"{field}: {text} must be zero or more")
    return value


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
                terminal_bandwidth_gbps=_gigabits(
                    entry.get("terminal_bandwidth", 0),
                    f"{path.name}: {name} terminal_bandwidth",
                    "Gbps",
                ),
                switch_buffer_gb=_gigabits(
                    entry.get("switch_buffer", 0), f"{path.name}: {name} switch_buffer", "Gb"
                ),
            )
        )
        # "connections" is directed: these are this switch's outbound links only.
        for target, bandwidth in (entry.get("connections") or {}).items():
            links.append(
                Link(
                    source=str(name),
                    target=str(target),
                    bandwidth_gbps=_gigabits(bandwidth, f"{path.name}: {name} -> {target}", "Gbps"),
                )
            )

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


def _switch_from_payload(entry: Any) -> tuple[Switch, list[Link]]:
    """Build one switch and its outbound links from a posted switch entry."""
    if not isinstance(entry, dict):
        raise TopologyError("Each switch must be an object")
    name = str(entry.get("name", "")).strip()
    if not name:
        raise TopologyError("Every switch needs a name")

    try:
        terminals = int(entry.get("terminals", 0))
    except (TypeError, ValueError) as exc:
        raise TopologyError(f"Switch {name}: terminals must be a whole number") from exc
    if terminals < 0:
        raise TopologyError(f"Switch {name}: terminals cannot be negative")

    links = []
    for connection in entry.get("connections") or []:
        if not isinstance(connection, dict):
            raise TopologyError(f"Switch {name}: each connection must be an object")
        target = str(connection.get("target", "")).strip()
        if not target:
            raise TopologyError(f"Switch {name}: every connection needs a target")
        links.append(
            Link(
                source=name,
                target=target,
                bandwidth_gbps=_gigabits(
                    connection.get("bandwidth_gbps", 0), f"{name} -> {target} bandwidth", "Gbps"
                ),
            )
        )

    switch = Switch(
        name=name,
        terminals=terminals,
        terminal_bandwidth_gbps=_gigabits(
            entry.get("terminal_bandwidth_gbps", 0), f"Switch {name}: terminal bandwidth", "Gbps"
        ),
        switch_buffer_gb=_gigabits(
            entry.get("switch_buffer_gb", 0), f"Switch {name}: switch buffer", "Gb"
        ),
    )
    return switch, links


def from_payload(payload: Any) -> Topology:
    """Build a Topology from a posted payload, the inverse of `as_dict`.

    Only checks what has to hold for the file to load again afterwards: a
    usable name, unique switch names, and links that land on a known switch.
    Anything else the FFW model accepts is passed through.
    """
    if not isinstance(payload, dict):
        raise TopologyError("Expected a topology object")
    name = str(payload.get("name", "")).strip()
    if not _NAME_RE.match(name):
        raise TopologyError("Name may only contain letters, numbers, dashes, and underscores")

    entries = payload.get("switches")
    if not isinstance(entries, list) or not entries:
        raise TopologyError("A topology needs at least one switch")

    switches: list[Switch] = []
    links: list[Link] = []
    for entry in entries:
        switch, outbound = _switch_from_payload(entry)
        switches.append(switch)
        links.extend(outbound)

    known = {switch.name for switch in switches}
    if len(known) != len(switches):
        raise TopologyError("Switch names must be unique")
    unknown = sorted({link.target for link in links} - known)
    if unknown:
        raise TopologyError(f"Connections point at undefined switches: {', '.join(unknown)}")

    return Topology(name=name, label=_label_from_name(name), switches=switches, links=links)


def _with_unit(value: float, unit: str) -> str:
    """Write a gigabit value the way the FFW YAML wants it: `18.3324 Gbps`.

    Four decimals is what the CODES topology generator emits, so values read
    from a generated preset survive a round trip.
    """
    return f"{f'{value:.4f}'.rstrip('0').rstrip('.') or '0'} {unit}"


def _to_document(topology: Topology) -> dict[str, Any]:
    """Render a Topology back into the FFW topology YAML structure."""
    outbound: dict[str, dict[str, str]] = {switch.name: {} for switch in topology.switches}
    for link in topology.links:
        outbound[link.source][link.target] = _with_unit(link.bandwidth_gbps, "Gbps")
    return {
        "topology": {
            "switches": {
                switch.name: {
                    "terminals": switch.terminals,
                    "terminal_bandwidth": _with_unit(switch.terminal_bandwidth_gbps, "Gbps"),
                    "switch_buffer": _with_unit(switch.switch_buffer_gb, "Gb"),
                    **({"connections": outbound[switch.name]} if outbound[switch.name] else {}),
                }
                for switch in topology.switches
            }
        }
    }


def save_topology(topology: Topology) -> Topology:
    """Write a new preset file and return it as reparsed from disk.

    Never overwrites: an existing file with the same name is a
    DuplicateTopologyError. Reparsing keeps the caller's copy identical to what
    every later read will see.
    """
    path = TOPOLOGY_DIR / f"{topology.name}.yaml"
    body = yaml.safe_dump(_to_document(topology), sort_keys=False, default_flow_style=False)
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(body)
    except FileExistsError as exc:
        raise DuplicateTopologyError(f"A topology named {topology.name} already exists") from exc
    except OSError as exc:
        raise TopologyError(f"Could not write topology {topology.name}: {exc}") from exc

    list_topologies.cache_clear()
    return get_topology(topology.name)


def get_topology(name: str) -> Topology:
    """Return one preset by name.

    Looks the name up among the known presets rather than building a path from
    it, so a caller cannot accidentally fetch files outside `core/data/topologies`.
    """
    for topology in list_topologies():
        if topology.name == name:
            return topology
    raise TopologyError(f"Unknown topology preset: {name}")
