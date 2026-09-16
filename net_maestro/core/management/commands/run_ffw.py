"""RUN FFW simulation management command.

Execute Fluid-Flow WAN simulation with specified parameters and ingest results.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
import djclick as click

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import Run
from net_maestro.core.tasks.simulation import run_ffw_simulation


def _create_or_update_run(
    name: str,
    description: str | None,
    run_id: int | None,
) -> Run:
    """Create a new Run object or update an existing one's metadata.

    Args:
        name: Run identifier
        description: Run description
        run_id: Existing run ID to update, or None to create new

    Returns:
        The Run object

    Raises:
        Run.DoesNotExist: If run_id is provided but no matching Run exists
    """
    if run_id:
        run = Run.objects.get(id=run_id)
        run.name = name
        run.description = description or ""
        run.save()
    else:
        run = Run.objects.create(
            name=name,
            description=description or "",
            status=RunStatus.PENDING,
        )
    return run


@click.command()
@click.option(
    "-n",
    "--name",
    "name",
    type=str,
    help="Run identifier.",
    required=True,
)
@click.option(
    "--np",
    "np",
    type=int,
    default=1,
    help="Number of MPI processes.",
)
@click.option(
    "--binary-path",
    "binary_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to FFW binary.",
)
@click.option(
    "--sync",
    "sync",
    type=int,
    default=1,
    help=(
        "Synchronization protocol (1=sequential, 2=conservative, 3=optimistic, "
        "4=optimistic-debug, 5=optimistic-realtime, 6=reverse-check)."
    ),
)
@click.option(
    "--config-path",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to FFW configuration file.",
)
@click.option(
    "--working-dir",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--description",
    "description",
    type=str,
    help="Description of the run.",
)
@click.option(
    "--run-id",
    "run_id",
    type=int,
    default=None,
    help="Existing run ID to update instead of creating a new run.",
)
def run_ffw(  # noqa: PLR0913
    name: str,
    np: int,
    binary_path: Path,
    sync: int,
    config_path: Path,
    working_dir: Path,
    description: str | None = None,
    run_id: int | None = None,
) -> None:

    working_dir = (
        Path(working_dir) if working_dir else Path(getattr(settings, "FFW_BUILD_PATH", "."))
    )
    # Logs dir needs to exist for the model to run
    logs_dir = working_dir / "doc" / "example" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create or update Run object
    run = _create_or_update_run(name, description, run_id)
    run_ffw_simulation.apply(
        kwargs={
            "run_id": run.id,
            "np": np,
            "sync": sync,
            "config_path": str(config_path) if config_path else None,
            "working_dir": str(working_dir),
            "binary_path": str(binary_path) if binary_path else None,
        }
    )
