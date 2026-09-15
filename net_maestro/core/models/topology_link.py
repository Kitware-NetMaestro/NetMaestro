from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from net_maestro.core.constants import NodeKind


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

    def clean(self) -> None:
        super().clean()
        errors = {}
        for field_name in ("source_node", "target_node"):
            if getattr(self, f"{field_name}_id") is None:
                continue
            node = getattr(self, field_name)
            if node.node_kind != NodeKind.SWITCH:
                errors[field_name] = "A link endpoint must be a switch."
            elif self.topology_id is not None and node.topology_id != self.topology_id:
                errors[field_name] = "A link endpoint must belong to the same topology as the link."
        if errors:
            raise ValidationError(errors)
