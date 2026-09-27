"""Ingest FFW model-stats output into the database.

Attaches ross-stats-model.bin and/or ross-stats-analysis-lps.bin from a completed
fluid-flow WAN run to a new or existing Run, then parses them into FFW records.
"""

from __future__ import annotations

from pathlib import Path

from celery import chain
from django.core.files import File
import djclick as click

from net_maestro.core.constants import RunStatus, SimulationType
from net_maestro.core.models import FFWResultFile, Run
from net_maestro.core.tasks.ingest_ffw import run_ffw_ingest_task
from net_maestro.core.tasks.simulation import fail_run, mark_run_completed, mark_run_failed


def _get_or_create_run(name: str | None, run_id: int | None) -> Run:
    """Return the run to attach files to, creating a new FFW run when no ID is given."""
    if run_id is not None:
        return Run.objects.get(pk=run_id)
    if not name:
        msg = "Pass --name to create a new run, or --run-id to use an existing one."
        raise click.UsageError(msg)
    return Run.objects.create(
        name=name,
        status=RunStatus.PENDING,
        simulation_type=SimulationType.FFW,
    )


@click.command()
@click.argument(
    "files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("-n", "--name", type=str, help="Name for a new FFW run.")
@click.option("--run-id", type=int, default=None, help="Existing run to attach the files to.")
@click.option("--immediate", is_flag=True, help="Ingest now instead of queuing a Celery task.")
def ingest_ffw(
    files: tuple[Path, ...],
    name: str | None,
    run_id: int | None,
    *,
    immediate: bool,
) -> None:
    """Ingest FILES (ross-stats-model.bin and/or ross-stats-analysis-lps.bin) into a run."""
    run = _get_or_create_run(name, run_id)

    file_pks = []
    for path in files:
        with path.open("rb") as handle:
            result_file = FFWResultFile.objects.create(run=run, file=File(handle, name=path.name))
        file_pks.append(result_file.pk)

    if immediate:
        try:
            run_ffw_ingest_task(ffw_result_files=file_pks)
        except Exception:
            fail_run(run.id, "FFW ingestion failed")
            raise
        mark_run_completed(run.id)
    else:
        workflow = [
            run_ffw_ingest_task.si(ffw_result_files=file_pks),
            mark_run_completed.si(run.id),
        ]
        for task in workflow:
            task.link_error(mark_run_failed.s(run_id=run.id))
        chain(*workflow).apply_async()

    click.echo(f"Run {run.id}: ingesting {len(file_pks)} FFW file(s).")
