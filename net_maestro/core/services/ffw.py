from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import tempfile

from django.conf import settings

logger = logging.getLogger(__name__)


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
    default_output_dir = Path(tempfile.gettempdir()) / "ffw_output"
    stats_output = getattr(settings, "FFW_OUTPUT_DIR", default_output_dir)
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
        f"--stats-path={stats_output}",
        "--",
        config_path,
    ]
    try:
        result = subprocess.run(cmd, cwd=working_dir, check=True, capture_output=True, text=True)  # noqa: S603
    except subprocess.CalledProcessError as e:
        logger.exception("FFW simulation failed with error code %s", e.returncode)
        logger.info("FFW simulation stdout: %s", e.stdout)
        logger.info("FFW simulation stderr: %s", e.stderr)
        raise
    else:
        logger.info("FFW simulation stdout: %s", result.stdout)
        return result.returncode
