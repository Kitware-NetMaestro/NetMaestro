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

    def __str__(self):
        return f"Run {self.id}: {self.name} ({self.status})"
