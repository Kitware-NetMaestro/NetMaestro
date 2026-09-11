from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class TopologyLink(models.Model):
    """A directed link between two switches in a Topology."""

    topology = models.ForeignKey("Topology", on_delete=models.CASCADE, related_name="links")
    source_node = models.ForeignKey(
        "TopologyNode", on_delete=models.CASCADE, related_name="outgoing_links"
    )
    target_node = models.ForeignKey(
        "TopologyNode", on_delete=models.CASCADE, related_name="incoming_links"
    )
    # Stored normalized.
    bandwidth = models.BigIntegerField(
        validators=[MinValueValidator(0)], verbose_name="Bandwidth (bits/s)"
    )

    class Meta:
        constraints = [
            # Duplicate links are not allowed.
            models.UniqueConstraint(
                fields=["topology", "source_node", "target_node"],
                name="unique_link_per_topology",
            ),
            models.CheckConstraint(
                condition=Q(bandwidth__gte=0),
                name="link_bandwidth_non_negative",
            ),
        ]

    def __str__(self):
        return f"TopologyLink {self.id}: {self.source_node.name} -> {self.target_node.name}"
