""" RUN FFW simulation management command.
Execute Fluid-Flow WAN simulation with specified parameters and ingest results.
"""
from __future__ import annotations

from pathlib import Path
import subprocess

import djclick as click

from net_maestro import settings
from net_maestro.core.constants import RunStatus
from net_maestro.core.models import Run



def _build_ffw_command(
    np: int,
    binary_path: Path,
    sync: int,
    config_path: Path
    ) -> list[str]:
    """Build the FFW command to run the simulation."""
    return [
        "mpirun",
        "-np",
        str(np),
        str(binary_path),
        f"--sync={sync}",
        "--",
        str(config_path),
    ]

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
            status=RunStatus.RUNNING,
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
    required=True,
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
    required=True,
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
def run_FFW(
    name: str,
    np: int,
    binary_path: Path,
    sync: int,
    config_path: Path,
    working_dir: Path,
    description: str | None = None,
    run_id: int | None = None,
)-> None:

    working_dir = Path(working_dir) if working_dir else Path(getattr(settings, "FFW_BINARY_DIR", "."))
    # Logs dir needs to exist for the model to run
    logs_dir = working_dir/ "doc" / "example" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    cmd = _build_ffw_command(np=np, binary_path=binary_path, sync=sync, config_path=config_path)
    click.echo(f"Running FFW: {' '.join(map(str, cmd))}")

    # Create or update Run object
    run = _create_or_update_run(name, description, run_id)

    try:
        result = subprocess.run(cmd, cwd=working_dir, check=True, capture_output=True, text=True)
        click.echo(f"STDOUT:\n {result.stdout}")
        run.status = RunStatus.COMPLETED
        run.save()
        if result.stderr:
            click.echo(f"STDERR:\n {result.stderr}")
        click.echo("FFW simulation finished successfully.")
        click.echo(f"Logs are in {logs_dir}")
        click.echo(f"\nRun {run.id} created successfully.")
    except subprocess.CalledProcessError as e:
        click.echo(f"FFW simulation failed with error code {e.returncode}.")
        click.echo(f"STDOUT:\n {e.stdout}")
        click.echo(f"STDERR:\n {e.stderr}")
        run.status = RunStatus.FAILED
        run.save()
        raise
