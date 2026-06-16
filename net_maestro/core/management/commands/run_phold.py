"""Run PHOLD simulation management command.

Execute PHOLD simulation with specified parameters and ingest results.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import TYPE_CHECKING

from celery import chain
from django.core.files import File
import djclick as click

if TYPE_CHECKING:
    from celery.canvas import Signature

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import EventFile, ModelFile, Run, SimulationFile
from net_maestro.core.tasks import run_event_task, run_model_task, run_simulation_task
from net_maestro.core.tasks.simulation import mark_run_completed, mark_run_failed


@dataclass
class PHOLDConfig:
    """PHOLD simulation configuration parameters."""

    name: str
    synch: int
    avl_size: int
    nlp: int
    remote: float
    mean: float
    mult: float
    lookahead: float
    start_events: int
    memory: int
    output_dir: Path
    stats_prefix: str
    np: int
    stagger: bool


@dataclass
class OutputFileContext:
    """Context for processing output files."""

    output_dir: Path
    stats_prefix: str
    run: Run


def _ingest_output_file(
    file_type: str, file_path: Path, run: Run, *, immediate: bool
) -> Signature | None:
    """Create the file record for a PHOLD output file and prepare its ingestion task.

    Args:
        file_type: Type identifier for the file (evtrace, model, gvt, rt, or unknown)
        file_path: Path to the output file
        run: Run object to associate the file with
        immediate: Whether to run the task immediately (True) or queue it (False)

    Returns:
        Task signature if the file type is recognized, None otherwise

    Note:
        Unknown file types will be logged as warnings and skipped.
    """
    with file_path.open("rb") as file_handle:
        # Use immutable signatures (.si) so chained tasks don't pass their return
        # value as a positional argument to the next task in the chain.
        file_obj: EventFile | ModelFile | SimulationFile
        if file_type == "evtrace":
            file_obj = EventFile.objects.create(run=run, file=File(file_handle))
            signature = run_event_task.si(event_file_pk=file_obj.pk)
        elif file_type == "model":
            file_obj = ModelFile.objects.create(run=run, file=File(file_handle))
            signature = run_model_task.si(model_file_pk=file_obj.pk)
        elif file_type in ("gvt", "rt"):  # Explicit ROSS engine stats files
            file_obj = SimulationFile.objects.create(run=run, file=File(file_handle))
            signature = run_simulation_task.si(simulation_file_pk=file_obj.pk)
        else:
            # Unknown file type - log warning but don't fail the entire ingestion
            click.echo(
                f"Warning: Unknown file type '{file_type}' for {file_path.name}. "
                f"This file type is not currently supported and will be skipped.",
                err=True,
            )
            return None

    if immediate:
        signature.apply()
        return None

    return signature


def _prepare_ross_csv(phold_path: Path) -> None:
    """Copy ross.csv to /tmp for PHOLD to find it.

    Args:
        phold_path: Path to the PHOLD binary (ross.csv is in the same directory)
    """
    ross_csv_source = phold_path.parent / "ross.csv"
    ross_csv_target = Path("/tmp/ross.csv")  # noqa: S108
    if ross_csv_source.exists():
        shutil.copy(ross_csv_source, ross_csv_target)


def _build_phold_command(phold_path: Path, config: PHOLDConfig) -> list[str]:
    """Build the PHOLD command line arguments.

    Args:
        phold_path: Path to the PHOLD binary
        config: PHOLD configuration parameters

    Returns:
        List of command line arguments
    """
    base_args = [
        f"--synch={config.synch}",
        f"--avl-size={config.avl_size}",
        f"--nlp={config.nlp}",
        f"--remote={config.remote}",
        f"--mean={config.mean}",
        f"--mult={config.mult}",
        f"--lookahead={config.lookahead}",
        f"--start-events={config.start_events}",
        f"--memory={config.memory}",
        f"--run={config.name}",
        # Enable instrumentation
        "--engine-stats=1",
        "--event-trace=1",
        "--pe-data=1",
        "--kp-data=1",
        "--lp-data=1",
        f"--extramem={config.memory * 1000}",  # Scale for optimistic mode
        "--vt-interval=10000",
        "--vt-samp-end=100000",
        f"--stats-path={config.output_dir}",
        f"--stats-prefix={config.stats_prefix}",
    ]

    if config.np == 1:
        # Single process: run PHOLD directly without MPI
        cmd = [str(phold_path), *base_args]
    else:
        # Multi-process: use MPI
        cmd = ["mpirun", "-np", str(config.np), str(phold_path), *base_args]

    if config.stagger:
        cmd.append("--stagger=1")

    return cmd


def _execute_phold(cmd: list[str]) -> None:
    """Execute the PHOLD simulation command.

    Args:
        cmd: Command line arguments

    Raises:
        subprocess.CalledProcessError: If PHOLD fails
    """
    click.echo(f"Running PHOLD simulation: {' '.join(cmd)}")

    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
            cwd="/tmp",  # noqa: S108
        )
        click.echo("PHOLD completed successfully.")
        click.echo(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            click.echo(f"STDERR:\n{result.stderr}")
    except subprocess.CalledProcessError as e:
        click.echo(f"PHOLD failed with exit code {e.returncode}", err=True)
        click.echo(f"STDOUT:\n{e.stdout}", err=True)
        click.echo(f"STDERR:\n{e.stderr}", err=True)
        raise


def _find_output_directory(output_dir: Path) -> Path:
    """Find the actual PHOLD output directory (PHOLD creates a random suffix).

    Args:
        output_dir: The specified output directory

    Returns:
        The actual output directory (either the most recent phold_output-* or the specified dir)
    """
    phold_output_dirs = sorted(
        Path(tempfile.gettempdir()).glob("phold_output-*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if phold_output_dirs:
        actual_output_dir = phold_output_dirs[0]
        click.echo(f"Found PHOLD output directory: {actual_output_dir}")
    else:
        click.echo("Warning: No PHOLD output directory found.")
        actual_output_dir = output_dir

    return actual_output_dir


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


def _process_known_files(
    context: OutputFileContext,
    task_signatures: list[Signature],
    *,
    immediate: bool,
) -> set[str]:
    """Process known PHOLD output file types.

    Returns:
        Set of processed filenames
    """
    supported_output_files = {
        "gvt": f"{context.stats_prefix}-gvt.bin",
        "rt": f"{context.stats_prefix}-rt.bin",
        "evtrace": f"{context.stats_prefix}-evtrace.bin",
        "model": f"{context.stats_prefix}-model.bin",
    }

    processed_files = set()

    for file_type, filename in supported_output_files.items():
        file_path = context.output_dir / filename
        if file_path.exists():
            click.echo(f"Ingesting {filename} (type: {file_type})...")
            signature = _ingest_output_file(file_type, file_path, context.run, immediate=immediate)
            if signature and not immediate:
                task_signatures.append(signature)
            processed_files.add(filename)
        else:
            click.echo(f"Info: {filename} not found.")

    return processed_files


def _process_additional_files(
    context: OutputFileContext,
    processed_files: set[str],
    task_signatures: list[Signature],
    *,
    immediate: bool,
) -> None:
    """Process any additional output files not in the known list."""
    additional_files_found = False

    for file_path in context.output_dir.glob(f"{context.stats_prefix}-*.bin"):
        if file_path.name not in processed_files:
            if not additional_files_found:
                click.echo("\nAdditional output files found:")
                additional_files_found = True

            # Try to infer type from filename
            file_suffix = file_path.stem.replace(f"{context.stats_prefix}-", "")
            click.echo(f"  - {file_path.name} (type: {file_suffix})")
            signature = _ingest_output_file(
                file_suffix, file_path, context.run, immediate=immediate
            )
            if signature and not immediate:
                task_signatures.append(signature)


def _ingest_output_files(
    actual_output_dir: Path,
    stats_prefix: str,
    run: Run,
    *,
    immediate: bool,
) -> None:
    """Ingest all PHOLD output files from the output directory.

    Args:
        actual_output_dir: The actual output directory
        stats_prefix: Prefix for output files
        run: The Run object to associate files with
        immediate: Whether to run ingestion tasks immediately
    """
    task_signatures: list[Signature] = []
    context = OutputFileContext(actual_output_dir, stats_prefix, run)

    # Process known file types
    processed_files = _process_known_files(context, task_signatures, immediate=immediate)

    # Process any additional files
    _process_additional_files(context, processed_files, task_signatures, immediate=immediate)

    # Mark the run as completed once ingestion is done.
    if immediate:
        # Ingestion already ran synchronously inside _ingest_output_file; mark now.
        mark_run_completed(run.id)
    elif task_signatures:
        # Run ingestion tasks sequentially, then mark the run completed as the final
        # link. A chain (unlike a chord) needs only the broker, no result backend.
        click.echo(f"\nQueuing {len(task_signatures)} ingestion tasks...")
        workflow_tasks = [*task_signatures, mark_run_completed.si(run.id)]
        # Attach the error callback to every task so a failure anywhere in the chain
        # transitions the run to FAILED instead of leaving it stuck in RUNNING.
        for task in workflow_tasks:
            task.link_error(mark_run_failed.s(run_id=run.id))
        chain(*workflow_tasks).apply_async()
    else:
        # No ingestion tasks to run, but still need to mark as completed.
        mark_run_completed.delay(run.id)


@click.command()
@click.option(
    "-n",
    "--name",
    "name",
    type=str,
    help="Run identifier (passed to PHOLD as --run).",
    required=True,
)
@click.option(
    "--synch",
    "synch",
    type=int,
    default=3,
    help=(
        "Synchronization protocol (1=sequential, 2=conservative, 3=optimistic, "
        "4=optimistic-debug, 5=optimistic-realtime, 6=reverse-check)."
    ),
)
@click.option(
    "--avl-size",
    "avl_size",
    type=int,
    default=18,
    help="AVL tree size for event queue.",
)
@click.option(
    "--nlp",
    "nlp",
    type=int,
    default=8,
    help="Number of LPs per processor.",
)
@click.option(
    "--remote",
    "remote",
    type=float,
    default=0.25,
    help="Remote event rate (0-1).",
)
@click.option(
    "--mean",
    "mean",
    type=float,
    default=1.0,
    help="Mean timestamp for exponential distribution.",
)
@click.option(
    "--mult",
    "mult",
    type=float,
    default=1.4,
    help="Memory multiplier for event allocation.",
)
@click.option(
    "--lookahead",
    "lookahead",
    type=float,
    default=1.0,
    help="Lookahead for events.",
)
@click.option(
    "--start-events",
    "start_events",
    type=int,
    default=1,
    help="Number of initial messages per LP.",
)
@click.option(
    "--memory",
    "memory",
    type=int,
    default=100,
    help="Additional memory buffers.",
)
@click.option(
    "--stagger",
    "stagger",
    type=bool,
    default=False,
    help="Stagger events uniformly across 0 to end time.",
)
@click.option(
    "--np",
    "np",
    type=int,
    default=1,
    help="Number of MPI processes.",
)
@click.option(
    "--phold-path",
    "phold_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to PHOLD binary.",
    required=True,
)
@click.option(
    "--output-dir",
    "output_dir",
    type=click.Path(path_type=Path),
    help="Output directory for simulation results.",
    required=True,
)
@click.option(
    "--stats-prefix",
    "stats_prefix",
    type=str,
    default="phold",
    help="Prefix for output files.",
)
@click.option(
    "--description",
    "description",
    type=str,
    help="Description of the run.",
)
@click.option(
    "--immediate", is_flag=True, help="Run ingestion tasks immediately instead of queuing them."
)
@click.option(
    "--run-id",
    "run_id",
    type=int,
    default=None,
    help="Existing run ID to update instead of creating a new run.",
)
def run_phold(  # noqa: PLR0913
    *,
    name: str,
    synch: int,
    avl_size: int,
    nlp: int,
    remote: float,
    mean: float,
    mult: float,
    lookahead: float,
    start_events: int,
    memory: int,
    stagger: bool,
    np: int,
    phold_path: Path,
    output_dir: Path,
    stats_prefix: str,
    description: str | None,
    immediate: bool,
    run_id: int | None,
) -> None:
    """Run PHOLD simulation and ingest results into the database."""
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare ross.csv for PHOLD
    _prepare_ross_csv(phold_path)

    # Create configuration object
    config = PHOLDConfig(
        name=name,
        synch=synch,
        avl_size=avl_size,
        nlp=nlp,
        remote=remote,
        mean=mean,
        mult=mult,
        lookahead=lookahead,
        start_events=start_events,
        memory=memory,
        output_dir=output_dir,
        stats_prefix=stats_prefix,
        np=np,
        stagger=stagger,
    )

    # Build and execute PHOLD command
    cmd = _build_phold_command(phold_path, config)
    _execute_phold(cmd)

    # Find actual output directory
    actual_output_dir = _find_output_directory(output_dir)

    # Create or update Run object
    run = _create_or_update_run(name, description, run_id)

    # Ingest output files
    _ingest_output_files(actual_output_dir, stats_prefix, run, immediate=immediate)

    click.echo(f"\nRun {run.id} created successfully.")
