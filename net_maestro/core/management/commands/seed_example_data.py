"""Seed the database with example data from the data/ directory.

Creates one Run per status with the bundled example event, model, and
simulation files so developers can quickly populate a working dataset.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.files import File
import djclick as click

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import EventFile, ModelFile, Run, SimulationFile
from net_maestro.core.tasks import (
    run_event_task,
    run_model_task,
    run_simulation_task,
)

EXAMPLE_DATA_DIR = Path(settings.BASE_DIR) / "data"
EXAMPLE_RUN_PREFIX = "Example"
EXAMPLE_RUN_DESCRIPTION = "Auto-seeded from data/ directory."


def _find_example_files(subdir: str) -> list[Path]:
    """Return sorted list of .bin files in data/<subdir>/."""
    directory = EXAMPLE_DATA_DIR / subdir
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.bin"))


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="Re-seed even if example data already exists.",
)
def seed_example_data(*, force: bool) -> None:
    """Populate the database with example data for development."""
    existing = Run.objects.filter(
        name__startswith=EXAMPLE_RUN_PREFIX,
        description=EXAMPLE_RUN_DESCRIPTION,
    )
    if not force and existing.exists():
        click.secho(
            "Example data already exists. Use --force to re-seed.",
            fg="yellow",
        )
        return

    event_files = _find_example_files("events")
    model_files = _find_example_files("models")
    simulation_files = _find_example_files("simulations")

    total_files = len(event_files) + len(model_files) + len(simulation_files)
    if total_files == 0:
        click.secho(
            f"No example .bin files found in {EXAMPLE_DATA_DIR}.",
            fg="red",
        )
        return

    for status in RunStatus:
        run = Run.objects.create(
            name=f"{EXAMPLE_RUN_PREFIX} {status.label} Run",
            description=EXAMPLE_RUN_DESCRIPTION,
            status=status,
        )
        click.echo(f"Created {run}")

        if status != RunStatus.COMPLETED:
            continue

        for path in event_files:
            with path.open("rb") as fh:
                event_obj = EventFile.objects.create(run=run, file=File(fh))
            run_event_task.s(event_file_pk=event_obj.pk).apply()
            click.echo(f"  Ingested event file: {path.name}")

        for path in model_files:
            with path.open("rb") as fh:
                model_obj = ModelFile.objects.create(run=run, file=File(fh))
            run_model_task.s(model_file_pk=model_obj.pk).apply()
            click.echo(f"  Ingested model file: {path.name}")

        for path in simulation_files:
            with path.open("rb") as fh:
                sim_obj = SimulationFile.objects.create(run=run, file=File(fh))
            run_simulation_task.s(simulation_file_pk=sim_obj.pk).apply()
            click.echo(f"  Ingested simulation file: {path.name}")

    click.secho(
        f"Done — created {len(RunStatus)} runs, "
        f"ingested {total_files} file(s) into the completed run.",
        fg="green",
    )
