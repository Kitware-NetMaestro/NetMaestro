"""Data ingestion management command.

Create a new Run object in the database.
"""

from __future__ import annotations

from pathlib import Path

from django.core.files import File
import djclick as click

from net_maestro.core.constants import ResultStatus
from net_maestro.core.models import (
    EventFile,
    ModelFile,
    Result,
    Run,
    SimulationFile,
    Topology,
)
from net_maestro.core.tasks import run_event_task, run_model_task, run_simulation_task


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
@click.option("--immediate", is_flag=True, help="Run the task immediately.")
def data_ingest(  # noqa: PLR0913
    *,
    name: str,
    description: str | None,
    event_file: Path | None,
    simulation_file: Path | None,
    model_file: Path | None,
    immediate: bool,
) -> None:
    """Create a new Run object in the database."""
    status = (
        ResultStatus.PENDING
        if not (event_file and simulation_file and model_file)
        else ResultStatus.COMPLETED
    )

    topology = Topology.objects.create(name=name)
    result = Result.objects.create(status=status)
    Run.objects.create(
        name=name,
        description=description or "",
        topology=topology,
        result=result,
    )

    if event_file:
        with event_file.open("rb") as file_handle:
            event_file_obj = EventFile.objects.create(
                result=result,
                file=File(file_handle),
            )

        run_event_signature = run_event_task.s(event_file_pk=event_file_obj.pk)
        if immediate:
            run_event_signature.apply()
        else:
            run_event_signature.delay()

    if simulation_file:
        with simulation_file.open("rb") as sim_reader:
            simulation_file_obj = SimulationFile.objects.create(
                result=result,
                file=File(sim_reader),
            )

        run_simulation_signature = run_simulation_task.s(simulation_file_pk=simulation_file_obj.pk)
        if immediate:
            run_simulation_signature.apply()
        else:
            run_simulation_signature.delay()

    if model_file:
        with model_file.open("rb") as file_handle:
            model_file_obj = ModelFile.objects.create(
                result=result,
                file=File(file_handle),
            )

        run_model_signature = run_model_task.s(model_file_pk=model_file_obj.pk)
        if immediate:
            run_model_signature.apply()
        else:
            run_model_signature.delay()
