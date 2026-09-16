from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def execute_ffw_model(
    *,
    np: int,
    sync: int,
    config_path: str,
    working_dir: str,
    binary_path: str,
) -> int:
    cmd = [
        "mpirun",
        "-np",
        str(np),
        binary_path,
        f"--sync={sync}",
        "--",
        config_path,
    ]
    try:
        result = subprocess.run(cmd, cwd=working_dir, check=True, capture_output=True, text=True)  # noqa: S603
        logger.info("FFW simulation stdout: %s", result.stdout)
    except subprocess.CalledProcessError as e:
        logger.exception("FFW simulation failed with error code %s", e.returncode)
        logger.info("FFW simulation stderr: %s", result.stderr)
    return result.returncode
