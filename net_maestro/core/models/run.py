from __future__ import annotations

from django.db import models

from net_maestro.core.models.results import Result
from net_maestro.core.models.topology import Topology


class Run(models.Model):
    topology = models.ForeignKey(Topology, on_delete=models.CASCADE, related_name="topology")
    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name="result")

    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Run {self.id}: {self.name}"
