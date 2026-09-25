"""RUN FFW simulation management command.

Execute Fluid-Flow WAN simulation with specified parameters and ingest results.
"""

from __future__ import annotations

from pathlib import Path

import djclick as click

from net_maestro.core.tasks.ingest_ffw import run_ffw_ingest_task



# TODO Address the dump unknown
@click.command()
@click.argument(
    "files",
    nargs=-1,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="ross-stats-model.bin and/or ross-stats-analysis-lps.bin",
)
@click.option(
    "--num-rails",
    type=int,
    default=1,
    help="dragonfly-dally num_rails (default 1)",
)
@click.option(
    "--num-qos",
    type=int,
    default=1,
    help="dragonfly-dally num_qos_levels (default 1)",
)
@click.option(
    "--radix",
    type=int,
    default=7,
    help="dragonfly-dally router radix (default 7)",
)
@click.option(
    "--model-family",
    type=click.Choice(["auto", "dragonfly", "fluid-flow-wan"]),
    default="auto",
    help="restrict payload dispatch to one model family; only needed when the "
    "dragonfly dimensions make a payload size collide (default: auto)",
)
@click.option(
    "--immediate", is_flag=True, help="Run ingestion tasks immediately instead of queuing them."
)
# @click.option(
#     "--csv-prefix",
#     type=str,
#     help="write <prefix>-<lptype>.csv files instead of stdout",
# )
# @click.option(
#     "--dump-unknown",
#     is_flag=True,
#     help="hex-dump undecodable payloads",
# )
def ingest_output(
    files: list[Path],
    num_rails: int,
    num_qos: int,
    radix: int,
    model_family: str,
    immediate: bool,
    # csv_prefix: str | None,
    # dump_unknown: bool,
) -> None:
    paths = [str(p) for p in files]
    signature = run_ffw_ingest_task.s(
        ffw_result_files=paths,
        num_rails=num_rails,
        num_qos=num_qos,
        radix=radix,
        model_family=model_family,
    )
    if immediate:
        signature.apply()
        return None
    else:
        signature.delay()
