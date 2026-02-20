"""Data ingestion management command.

Create a new Run object in the database.
"""

from __future__ import annotations

from pathlib import Path

import djclick as click

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import Run


@click.command()
@click.option(
    "-n",
    "--name",
    "name",
    type=str,
    help="Name of the run.",
    required=True,
)
@click.option(
    "-d",
    "--description",
    "description",
    type=str,
    help="Description of the run.",
)
@click.option(
    "-e",
    "--event-file",
    "event_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Event file(s) to ingest. Can be provided multiple times.",
)
@click.option(
    "-s",
    "--simulation-file",
    "simulation_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Simulation file(s) to ingest. Can be provided multiple times.",
)
@click.option(
    "-m",
    "--model-file",
    "model_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Model file(s) to ingest. Can be provided multiple times.",
)
def data_ingest(
    name: str,
    description: str,
    event_file: Path | None = None,
    simulation_file: Path | None = None,
    model_file: Path | None = None,
) -> None:
    """Create a new Run object in the database."""
    if not event_file or not simulation_file or not model_file:
        status = RunStatus.PENDING

    Run.objects.create(
        name=name,
        description=description,
        status=status,
    )
