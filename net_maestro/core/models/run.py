from __future__ import annotations

from django.db import models

from net_maestro.core.constants import RunStatus


class Run(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=RunStatus, default=RunStatus.PENDING)

    def __str__(self):
        return f"Run {self.id}: {self.name} ({self.status})"
