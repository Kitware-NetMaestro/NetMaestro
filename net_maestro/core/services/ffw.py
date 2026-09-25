from __future__ import annotations

import logging
import subprocess
import tempfile

from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# TODO This might make more sense in either the simulation task or the management command in the future. revisit
def _find_output_directory(output_dir: Path) -> Path:
    """Find the actual FFW output directory (FFW creates a random suffix).

    Args:
        output_dir: The specified output directory

    Returns:
        The actual output directory (either the most recent phold_output-* or the specified dir)
    """
    ffw_output_dirs = sorted(
        Path(tempfile.gettempdir()).glob("ffw_output-*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if ffw_output_dirs:
        actual_output_dir = ffw_output_dirs[0]
    else:
        actual_output_dir = output_dir

    return actual_output_dir


def execute_ffw_model(  # noqa: PLR0913
    *,
    np: int,
    sync: int,
    model_stats: int,
    num_gvt: int,
    rt_interval: int,
    vt_interval: int,
    vt_samp_end: int,
    config_path: str,
    working_dir: str,
    binary_path: str,
) -> int:
    stats_output = settings.FFW_OUTPUT_DIR
    actual_output_dir = _find_output_directory(stats_output)
    cmd = [
        "mpirun",
        "-np",
        str(np),
        binary_path,
        f"--sync={sync}",
        f"--model-stats={model_stats}",
        f"--num-gvt={num_gvt}",
        f"--rt-interval={rt_interval}",
        f"--vt-interval={vt_interval}",
        f"--vt-samp-end={vt_samp_end}",
        f"--stats-path={actual_output_dir}",
        "--",
        config_path,
    ]
    try:
        result = subprocess.run(cmd, cwd=working_dir, check=True, capture_output=True, text=True)  # noqa: S603
        logger.info("FFW simulation stdout: %s", result.stdout)
    except subprocess.CalledProcessError as e:
        logger.exception("FFW simulation failed with error code %s", e.returncode)
        logger.info("FFW simulation stderr: %s", result.stderr)
    return actual_output_dir
