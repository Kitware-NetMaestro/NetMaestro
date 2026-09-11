""" RUN FFW simulation management command.
Execute Fluid-Flow WAN simulation with specified parameters and ingest results.
"""
from __future__ import annotations

from pathlib import Path
import subprocess

import djclick as click



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

@click.command()
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
    default="/opt/FFW/build/local/src/model-net-fluid-flow-wan-random-traffic"
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
    default="/opt/FFW/build/local/doc/example/fluid-flow-wan-random-traffic.yaml"
)
@click.option(
    "--working-dir",
    default="/opt/FFW/build/local",
    type=click.Path(exists=True, path_type=Path),
    )

def run_FFW(
    np: int,
    binary_path: Path,
    sync: int,
    config_path: Path,
    working_dir: Path
)-> None:

    working_dir = Path(working_dir)
    # Logs dir needs to exist for the model to run
    logs_dir = working_dir/ "doc" / "example" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    cmd = _build_ffw_command(np=np, binary_path=binary_path, sync=sync, config_path=config_path)
    click.echo(f"Running FFW: {' '.join(map(str, cmd))}")

    subprocess.run(cmd, cwd=working_dir, check=True)
