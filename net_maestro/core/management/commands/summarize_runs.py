"""Compute per-run summaries for runs that finished before summaries existed.

New runs are summarized when they complete; this backfills older ones, and with
`--force` recomputes summaries after the summary code changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Q
import djclick as click

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import Run
from net_maestro.core.summaries import HEADLINE_METRICS, compute_run_summary, metric_by_key

if TYPE_CHECKING:
    from net_maestro.core.models import RunSummary


def _headline(summary: RunSummary) -> str:
    """Return the headline metrics as one line, with the switch and link they name."""
    parts = []
    for key in HEADLINE_METRICS:
        metric = metric_by_key(key)
        value = summary.metrics.get(key)
        label = metric.label if metric else key
        text = "n/a" if value is None else f"{value:.{metric.digits if metric else 1}f}"
        if metric and metric.unit and value is not None:
            text += f" {metric.unit}"
        parts.append(f"{label} {text}")
    where = [summary.details.get("peak_buffer_switch"), summary.details.get("bottleneck_link")]
    health = "ok" if summary.health.get("ok") else "check health"
    return f"{'; '.join(parts)} ({', '.join(w for w in where if w) or 'no locations'}; {health})"


@click.command()
@click.argument("run_ids", nargs=-1, type=int)
@click.option("--all", "all_runs", is_flag=True, help="Summarize every completed run.")
@click.option("--force", is_flag=True, help="Recompute runs that already have a summary.")
def summarize_runs(run_ids: tuple[int, ...], *, all_runs: bool, force: bool) -> None:
    """Compute summaries for RUN_IDS, or for every completed run with --all."""
    if not run_ids and not all_runs:
        raise click.UsageError("Pass run ids, or --all for every completed run.")
    selected = Q(pk__in=run_ids)
    if all_runs:
        selected |= Q(status=RunStatus.COMPLETED)
    runs = Run.objects.filter(selected).select_related("summary").order_by("id")
    found = {run.pk for run in runs}
    for run_id in sorted(set(run_ids) - found):
        click.echo(f"Run {run_id}: not found")

    for run in runs:
        if not force and hasattr(run, "summary"):
            click.echo(f"Run {run.id}: already summarized (use --force to recompute)")
            continue
        summary = compute_run_summary(run)
        if summary is None:
            click.echo(f"Run {run.id}: no data")
        else:
            click.echo(f"Run {run.id}: {_headline(summary)}")
