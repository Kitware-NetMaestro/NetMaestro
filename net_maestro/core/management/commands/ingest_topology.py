"""Ingest switch components from a fluid-flow WAN topology YAML file.

Parses the topology and creates ComponentModel records for each unique
switch configuration (terminal_bandwidth, switch_buffer pair) that does
not already exist in the database.
"""

from __future__ import annotations

from pathlib import Path

import djclick as click
import yaml

from net_maestro.core.models import ComponentModel


@click.command()
@click.argument(
    "path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def command(*, path: Path) -> None:
    """Create switch components from a topology YAML file.

    Parses the topology, identifies unique switch configurations, and creates
    ComponentModel records for any that don't already exist.
    """
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise click.ClickException(f"Could not read {path.name}: {exc}") from exc

    if not isinstance(document, dict):
        raise click.ClickException(f"{path.name} is not a YAML mapping")
    switch_entries = (document.get("topology") or {}).get("switches")
    if not isinstance(switch_entries, dict):
        raise click.ClickException(f"{path.name} has no topology.switches mapping")

    # Collect unique (terminal_bandwidth, switch_buffer) pairs
    seen: set[tuple[str, str]] = set()
    unique_configs: list[tuple[str, str, str]] = []
    for name, entry in switch_entries.items():
        if not isinstance(entry, dict):
            raise click.ClickException(f"Switch {name} is not a mapping")
        bw = _parse_value(entry.get("terminal_bandwidth", "0"), "Gbps")
        buf = _parse_value(entry.get("switch_buffer", "0"), "Gb")
        sig = (bw, buf)
        if sig not in seen:
            seen.add(sig)
            unique_configs.append((str(name), bw, buf))

    created = 0
    skipped = 0
    for switch_name, bw, buf in unique_configs:
        exists = ComponentModel.objects.filter(
            base_model="fluid-flow-wan-switch-lp",
            parameters__terminal_bandwidth=bw,
            parameters__switch_buffer=buf,
        ).exists()
        if exists:
            click.echo(f"Skipped: switch config ({bw} Gbps, {buf} Gb) already exists")
            skipped += 1
        else:
            ComponentModel.objects.create(
                name=f"Switch {switch_name}",
                base_model="fluid-flow-wan-switch-lp",
                component_type="switch",
                engine="PDES (CODES)",
                description=f"{buf} Gb buffer, {bw} Gbps terminal bandwidth",
                parameters={
                    "terminal_bandwidth": bw,
                    "switch_buffer": buf,
                },
            )
            click.echo(f"Created: Switch {switch_name} ({bw} Gbps, {buf} Gb)")
            created += 1

    click.echo(f"Done: {created} created, {skipped} skipped")


def _parse_value(raw: object, expected_unit: str) -> str:
    """Parse a value like '100 Gbps' or '64 Gb' into a plain number string."""
    text = str(raw).strip()
    if text.endswith(f" {expected_unit}"):
        text = text[: -len(expected_unit) - 1].strip()
    # Remove trailing .0 for clean integer display
    try:
        num = float(text)
        return str(int(num)) if num == int(num) else str(num)
    except (ValueError, OverflowError):
        return text
