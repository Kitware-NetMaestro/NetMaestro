"""RUN FFW simulation management command.

Execute Fluid-Flow WAN simulation with specified parameters and ingest results.
"""

from __future__ import annotations

from pathlib import Path

import djclick as click

from net_maestro.core.parsers.ffw_file import build_dispatch, parse_model_file, parse_vt_file, write_csv, FormatError

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
    "dragonfly dimensions make a payload size collide (default: auto)"
)
@click.option(
    "--csv-prefix",
    type=str,
    help="write <prefix>-<lptype>.csv files instead of stdout",
)
@click.option(
    "--dump-unknown",
    is_flag=True,
    help="hex-dump undecodable payloads",

)
def parse_output(
    files: list[Path],
    num_rails: int,
    num_qos: int,
    radix: int,
    model_family: str,
    csv_prefix: str | None,
    dump_unknown: bool,
) -> None:

    try:
        model_dispatch, vt_dispatch = build_dispatch(
            num_rails, num_qos, radix, model_family
        )
    except FormatError as e:
        click.echo(f"error: {e}", err=True)
        raise click.Abort() from e

    rows = {}
    unknown = []
    total = 0
    try:
        for path in files:
            file = str(path)
            if "analysis-lps" in file:
                total += parse_vt_file(file, vt_dispatch, rows, unknown, model_family)
            else:
                # TODO currently doesn't seem to be parsing correctly
                total += parse_model_file(file, model_dispatch, rows, unknown, model_family)
    except (FormatError, OSError) as e:
        click.echo(f"error: {e}", err=True)
        raise click.Abort() from e


    write_csv(rows, csv_prefix)

    counts = {t: len(e) for t, e in sorted(rows.items())}
    click.echo(f"# parsed {total} records: {counts}, unknown payloads: {len(unknown)}", err=True)
    if unknown:
        sizes = sorted({sz for (_, sz, _) in unknown})
        click.echo(f"# undecoded payload sizes {sizes} -- check --num-rails/--num-qos/--radix "
                    "and --model-family against the run's network config "
                    "(see doc/model-stats-binary-format.md)"
                    ,
                    err=True)

        if dump_unknown:
            for path, sz, payload in unknown:
                click.echo(f"# {path} sz={sz}: {payload.hex()}", err=True)
    return 0
