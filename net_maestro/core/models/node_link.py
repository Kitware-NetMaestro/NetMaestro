from __future__ import annotations

from django.db import models

from net_maestro.core.models.node import Node
from net_maestro.core.models.topology import Topology


class NodeLink(models.Model):
    topology = models.ForeignKey(Topology, on_delete=models.CASCADE, related_name="node_links")
    source = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="source_links")
    target = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="target_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["topology", "source", "target"],
                name="unique_link_per_topology",
            ),
            models.CheckConstraint(
                condition=~models.Q(source=models.F("target")),
                name="no_self_links",
            ),
        ]

    def __str__(self) -> str:
        return f"NodeLink {self.source.name} -> {self.target.name}"
