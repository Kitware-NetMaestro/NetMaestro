from __future__ import annotations

from django.db import models

from net_maestro.core.models.run import Run


class Topology(models.Model):
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="topologies")

    def __str__(self) -> str:
        return f"Topology - {self.run.name}"
