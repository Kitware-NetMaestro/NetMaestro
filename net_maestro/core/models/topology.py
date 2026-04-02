from __future__ import annotations

from django.db import models

from net_maestro.core.models.run import Run


class Topology(models.Model):
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="topologies")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run"], name="one_topology_per_run"),
        ]

    def __str__(self) -> str:
        return f"Topology - {self.run.name}"
