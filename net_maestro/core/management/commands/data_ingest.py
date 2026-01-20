"""Data ingestion management command.

TODO: This is a temporary solution for getting binary data files into the application.
Once file upload functionality is implemented in the UI, this command can be deprecated
or repurposed for bulk/batch operations only.

This command supports three workflows:
1. Symlink individual files via --event-file, --simulation-file, --model-file flags
2. Symlink all files from a structured directory (--source-root with events/, models/, simulations/ subdirs)
3. Combination of both approaches

All files are symlinked (not copied) into NetMaestro/data/{events,models,simulations}/
to avoid duplicating large binary files.
"""
from pathlib import Path
from typing import Sequence

import djclick as click
from django.conf import settings


@click.command()
@click.option(
    '-e',
    '--event-file',
    'event_files',
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path, resolve_path=True),
    help='Event file(s) to ingest. Can be provided multiple times.',
)
@click.option(
    '-s',
    '--simulation-file',
    'simulation_files',
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path, resolve_path=True),
    help='Simulation file(s) to ingest. Can be provided multiple times.',
)
@click.option(
    '-m',
    '--model-file',
    'model_files',
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path, resolve_path=True),
    help='Model file(s) to ingest. Can be provided multiple times.',
)
@click.option(
    '-r',
    '--source-root',
    default=None,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path, resolve_path=True),
    help=(
        'Root directory containing events/, models/, and/or simulations/ subdirectories. '
        'All files directly under those subdirectories will be ingested.'
    ),
)
def ingest(
    event_files: tuple[Path, ...],
    simulation_files: tuple[Path, ...],
    model_files: tuple[Path, ...],
    source_root: Path | None,
) -> None:
    """Ingest data files by creating symlinks in the application data directory.

    Creates symlinks from source files to NetMaestro/data/{events,models,simulations}/
    subdirectories. Files must remain accessible at their source locations at runtime.

    Args:
        event_files: Event trace binary files to ingest
        simulation_files: ROSS simulation binary files to ingest
        model_files: Model analysis binary files to ingest
        source_root: Optional root directory containing structured subdirectories

    Raises:
        click.ClickException: If a destination file already exists and is not an
            identical symlink to the source
    """
    base_dir = Path(settings.BASE_DIR)
    data_dir = base_dir / 'data'

    def ingest_files(*, files: Sequence[Path], subdir: str) -> None:
        """Create symlinks for a sequence of files in the specified data subdirectory.

        Args:
            files: Sequence of source file paths to symlink
            subdir: Target subdirectory name (events, models, or simulations)
        """
        if not files:
            return

        dest_dir = data_dir / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)

        for file_path in files:
            # Resolve to absolute path
            source = file_path.expanduser().resolve(strict=True)
            destination = dest_dir / source.name

            # Skip if symlink already points to the same source
            if destination.exists() or destination.is_symlink():
                try:
                    if destination.is_symlink() and destination.resolve(strict=True) == source:
                        continue
                except FileNotFoundError:
                    pass
                raise click.ClickException(f'File already exists: {destination}')

            # Create symlink
            destination.symlink_to(source)

    # Ingest explicitly specified files
    ingest_files(files=event_files, subdir='events')
    ingest_files(files=simulation_files, subdir='simulations')
    ingest_files(files=model_files, subdir='models')

    # Ingest all files from structured source root if provided
    if source_root is not None:
        for subdir in ('events', 'models', 'simulations'):
            root_subdir = source_root / subdir
            if not root_subdir.exists() or not root_subdir.is_dir():
                continue

            # Ingest all files directly under the subdirectory
            files = tuple(path for path in root_subdir.iterdir() if path.is_file())
            ingest_files(files=files, subdir=subdir)
