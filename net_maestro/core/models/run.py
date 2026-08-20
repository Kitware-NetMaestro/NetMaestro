from __future__ import annotations

from django.db import models

from net_maestro.core.constants import RunStatus


class Run(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    # Defaults to SAVED because a Run only becomes PENDING once a simulation is actually
    # queued to execute. Immediately queued simulations must pass an explicit status.
    status = models.CharField(max_length=20, choices=RunStatus, default=RunStatus.SAVED)

    def __str__(self):
        return f"Run {self.id}: {self.name} ({self.status})"
