from __future__ import annotations

from django.db import models

from net_maestro.core.constants import RunStatus, SimulationType


class Run(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    # Defaults to SAVED because a Run only becomes PENDING once a simulation is actually
    # queued to execute. Immediately queued simulations must pass an explicit status.
    status = models.CharField(max_length=20, choices=RunStatus, default=RunStatus.SAVED)
    # Which simulator produced this run. Drives how it is launched and which datasets
    # and plots apply to it.
    simulation_type = models.CharField(
        max_length=32, choices=SimulationType, default=SimulationType.ESNET
    )
    # Set only for runs created as members of a parameter sweep. `member_params`
    # holds just the values this member varied, keyed by sweep axis.
    ensemble = models.ForeignKey(
        "core.Ensemble", null=True, blank=True, on_delete=models.CASCADE, related_name="runs"
    )
    member_index = models.IntegerField(null=True, blank=True)
    member_params = models.JSONField(null=True, blank=True)
    # Set by the simulation tasks: started when the run flips to RUNNING, finished
    # when it lands in COMPLETED or FAILED. Null for runs that predate them or were
    # ingested from files, which is why `wall_time_s` may be None.
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    # Why a FAILED run failed (the tail of the simulator's stderr, or the exception),
    # so the UI can say more than "failed".
    failure_reason = models.TextField(blank=True, default="")
    # The directory a simulation task gave this run: where its generated inputs and
    # the model's own logs live, kept on failure so they can be read. Empty for runs
    # that predate it or were ingested from files.
    work_dir = models.CharField(max_length=500, blank=True, default="")

    def __str__(self):
        return f"Run {self.id}: {self.name} ({self.status})"

    @property
    def wall_time_s(self) -> float | None:
        """Seconds from start to finish, or None when either end wasn't recorded."""
        if self.started_at is None or self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()
