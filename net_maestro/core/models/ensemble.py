from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

from net_maestro.core.constants import RunStatus, SimulationType

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from net_maestro.core.models.run import Run

# Statuses that mean a member still has work ahead of it.
_ACTIVE = {RunStatus.PENDING, RunStatus.RUNNING}


class Ensemble(models.Model):
    """A parameter sweep: one base configuration and the axes varied across it.

    The members are ordinary Runs, each with its own simulation config, so the
    saved-run, clone, and analysis paths treat them like any other run. The
    ensemble keeps the inputs that produced them (`base_params` and
    `sweep_spec`) so the sweep can be read back without reverse-engineering it
    from the members.
    """

    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    simulation_type = models.CharField(
        max_length=32, choices=SimulationType, default=SimulationType.FFW
    )
    # For FFW, the simulation form's fields: topology_name, traffic, np, sync.
    base_params = models.JSONField(default=dict)
    # [{"key": ..., "values": [...], "link": {"source": ..., "target": ...}?}], see core/sweeps.py.
    sweep_spec = models.JSONField(default=list)

    class Meta:
        ordering = ["-created"]

    def __str__(self) -> str:
        return f"Ensemble {self.id}: {self.name}"

    @property
    def members(self) -> QuerySet[Run]:
        return self.runs.order_by("member_index")

    def status_counts(self) -> dict[str, int]:
        """Return how many members are in each status, leaving out zeros."""
        rows = self.runs.values("status").annotate(n=models.Count("id"))
        return {row["status"]: row["n"] for row in rows if row["n"]}

    @property
    def status(self) -> str:
        """Roll the members' statuses up into one word for the list and header.

        Running wins over failed so a sweep with one early failure still reads
        as in progress while the chain works through the rest. An ensemble with
        no members has nothing to run yet, which is what saved means.
        """
        counts = self.status_counts()
        if not counts or set(counts) == {RunStatus.SAVED}:
            return RunStatus.SAVED
        if any(status in _ACTIVE for status in counts):
            return RunStatus.RUNNING
        if RunStatus.FAILED in counts:
            return RunStatus.FAILED
        return RunStatus.COMPLETED
