from __future__ import annotations

from django.db import models

from net_maestro.core.constants import RunStatus


class Result(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=RunStatus, default=RunStatus.PENDING)

    def __str__(self):
        return f"Result {self.status}"
