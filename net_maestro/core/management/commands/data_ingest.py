"""Data ingestion management command.

Create a new Run object in the database.
"""

from pathlib import Path

from django.core.files import File
import djclick as click

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import EventFile, Run
from net_maestro.core.tasks.events import run_event_task


@click.command()
@click.option(
    '-n',
    '--name',
    'name',
    type=str,
    help='Name of the run.',
    required=True,
)
@click.option(
    '-d',
    '--description',
    'description',
    type=str,
    help='Description of the run.',
)
@click.option(
    '-e',
    '--event-file',
    'event_file',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help='Event file(s) to ingest. Can be provided multiple times.',
)
@click.option(
    '-s',
    '--simulation-file',
    'simulation_file',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help='Simulation file(s) to ingest. Can be provided multiple times.',
)
@click.option(
    '-m',
    '--model-file',
    'model_file',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help='Model file(s) to ingest. Can be provided multiple times.',
)
@click.option('--immediate', is_flag=True, help='Run the task immediately.')
def data_ingest(
    name: str,
    description: str,
    event_file: Path | None = None,
    simulation_file: Path | None = None,
    model_file: Path | None = None,
    immediate: bool = False,
) -> None:
    """Create a new Run object in the database."""
    status = (
        RunStatus.PENDING
        if not (event_file and simulation_file and model_file)
        else RunStatus.COMPLETED
    )

    new_run = Run.objects.create(
        name=name,
        description=description,
        status=status,
    )

    if event_file:
        with event_file.open('rb') as file_handle:
            event_file_obj = EventFile.objects.create(
                run=new_run,
                file=File(file_handle),
            )

        task = run_event_task.s(event_file_pk=event_file_obj.pk)
        if immediate:
            task.apply()
        else:
            task.delay()
