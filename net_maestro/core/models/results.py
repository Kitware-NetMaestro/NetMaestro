from __future__ import annotations

from django.db import models

from net_maestro.core.constants import ResultStatus


class Result(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=ResultStatus, default=ResultStatus.PENDING)

    def __str__(self):
        return f"Result {self.status}"
