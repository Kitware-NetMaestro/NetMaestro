from __future__ import annotations

from django.db import models


class RunSummary(models.Model):
    """The handful of numbers that say what one run produced and whether to trust it.

    Computed once from the run's FFW and engine rows (see `core/summaries.py`) so the
    ensemble pages can compare dozens of members without re-aggregating hundreds of
    thousands of sample rows on every request. `metrics` holds the values keyed by
    the registry in `summaries.METRICS`, `details` the labels that go with them (which
    switch, which link), and `health` the sanity checks behind the member health icon.
    """

    run = models.OneToOneField("core.Run", related_name="summary", on_delete=models.CASCADE)
    computed_at = models.DateTimeField(auto_now=True)
    # Which FFW sampling mode (vt, gvt or rt) the sums came from; blank for engine-only runs.
    stats_type = models.CharField(max_length=8, blank=True, default="")
    metrics = models.JSONField(default=dict)
    details = models.JSONField(default=dict)
    health = models.JSONField(default=dict)

    def __str__(self) -> str:
        return f"RunSummary for run {self.run_id}"
