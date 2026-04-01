from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from net_maestro.core.constants import ComponentType
from net_maestro.core.models.topology import Topology


class Node(models.Model):
    topology = models.ForeignKey(Topology, on_delete=models.CASCADE, related_name="nodes")
    config = models.ForeignKey("ComponentConfig", on_delete=models.CASCADE, related_name="nodes")

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255, choices=ComponentType.choices)
    ingress_bandwidth = models.FloatField(validators=[MinValueValidator(0.0)])
    egress_bandwidth = models.FloatField(validators=[MinValueValidator(0.0)])
    ingress_latency = models.FloatField(validators=[MinValueValidator(0.0)])
    egress_latency = models.FloatField(validators=[MinValueValidator(0.0)])

    def __str__(self) -> str:
        return f"Node {self.name}"
