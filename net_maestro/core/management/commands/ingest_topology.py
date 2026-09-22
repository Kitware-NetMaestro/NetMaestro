"""Ingest a fluid-flow WAN topology YAML file.

Validates the file, copies it into the topology directory so it appears in the
topology dropdown, and creates a switch ComponentModel for each unique
(terminal_bandwidth, switch_buffer) pair that does not already exist.
"""

from __future__ import annotations

from pathlib import Path

import djclick as click

from net_maestro.core.models import ComponentModel
from net_maestro.core.topology import (
    SWITCH_LP_NAME,
    DuplicateTopologyError,
    Topology,
    TopologyError,
    _parse,
    save_topology,
)


@click.command()
@click.argument(
    "path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def command(*, path: Path) -> None:
    """Ingest a topology YAML file into the application.

    Parses the file, validates it as a well-formed FFW topology, writes it into
    the topology directory, and creates switch components for any new switch
    configurations.
    """
    topo_name = path.stem

    try:
        topology = _parse(topo_name, path)
    except TopologyError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Parsed topology: {topology.label} — {topology.summary()}")

    try:
        saved = save_topology(topology)
    except DuplicateTopologyError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Saved topology: {saved.name}")

    _create_switch_components(topology)


def _create_switch_components(topology: Topology) -> None:
    seen: set[tuple[str, str]] = set()
    created = 0
    skipped = 0
    for switch in topology.switches:
        bw = _number(switch.terminal_bandwidth_gbps)
        buf = _number(switch.switch_buffer_gb)
        if (bw, buf) in seen:
            continue
        seen.add((bw, buf))

        exists = ComponentModel.objects.filter(
            base_model=SWITCH_LP_NAME,
            parameters__terminal_bandwidth=bw,
            parameters__switch_buffer=buf,
        ).exists()
        if exists:
            click.echo(f"Skipped: switch config ({bw} Gbps, {buf} Gb) already exists")
            skipped += 1
        else:
            ComponentModel.objects.create(
                name=f"Switch {switch.name}",
                base_model=SWITCH_LP_NAME,
                component_type="switch",
                engine="PDES (CODES)",
                description=f"{buf} Gb buffer, {bw} Gbps terminal bandwidth",
                parameters={
                    "terminal_bandwidth": bw,
                    "switch_buffer": buf,
                },
            )
            click.echo(f"Created: Switch {switch.name} ({bw} Gbps, {buf} Gb)")
            created += 1

    click.echo(f"Done: {created} created, {skipped} skipped")


def _number(value: float) -> str:
    """Format `100.0` as `100` and `18.5` as `18.5`."""
    return str(int(value)) if value.is_integer() else str(value)
