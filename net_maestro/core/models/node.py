from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from net_maestro.core.constants import ModelType, NodeType
from net_maestro.core.models.topology import Topology


class Node(models.Model):
    topology = models.ForeignKey(Topology, on_delete=models.CASCADE, related_name="nodes")

    model = models.CharField(max_length=255, choices=ModelType.choices)
    name = models.CharField(max_length=255)
    node_type = models.CharField(max_length=255, choices=NodeType.choices)
    ingress_bandwidth = models.FloatField(validators=[MinValueValidator(0.0)])
    egress_bandwidth = models.FloatField(validators=[MinValueValidator(0.0)])
    ingress_latency = models.FloatField(validators=[MinValueValidator(0.0)])
    egress_latency = models.FloatField(validators=[MinValueValidator(0.0)])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["topology", "name"],
                name="unique_node_name_per_topology",
            )
        ]

    def __str__(self) -> str:
        return f"{self.node_type} node - {self.name}"
