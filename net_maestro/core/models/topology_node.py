from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from net_maestro.core.constants import NodeKind


class TopologyNode(models.Model):
    topology = models.ForeignKey("Topology", on_delete=models.CASCADE, related_name="nodes")
    name = models.CharField(max_length=200)
    node_kind = models.CharField(max_length=100, choices=NodeKind.choices, default=NodeKind.SWITCH)
    # Position in the topology's LP ordering. Generated configs index LPs by this, so it
    # must stay stable across edits.
    order_index = models.IntegerField(validators=[MinValueValidator(0)])
    terminals = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Attached terminals",
    )
    # Bandwidths are stored normalized.
    terminal_bandwidth = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Terminal bandwidth (bits/s)",
    )
    switch_buffer = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Switch buffer (bits)",
    )

    class Meta:
        ordering = ["order_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["topology", "name"], name="unique_node_name_per_topology"
            ),
            models.UniqueConstraint(
                fields=["topology", "order_index"], name="unique_node_order_index_per_topology"
            ),
            models.CheckConstraint(
                condition=Q(order_index__gte=0),
                name="node_order_index_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(terminals__isnull=True) | Q(terminals__gte=0),
                name="node_terminals_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(terminal_bandwidth__isnull=True) | Q(terminal_bandwidth__gte=0),
                name="node_terminal_bandwidth_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(switch_buffer__isnull=True) | Q(switch_buffer__gte=0),
                name="node_switch_buffer_non_negative",
            ),
        ]

    def __str__(self):
        return f"TopologyNode {self.id}: {self.name}"

    def clean(self) -> None:
        super().clean()
        # Switch-only fields are meaningless on a terminal row, and required on a switch
        # because all three are needed to emit the topology YAML.
        switch_only = {
            "terminals": self.terminals,
            "terminal_bandwidth": self.terminal_bandwidth,
            "switch_buffer": self.switch_buffer,
        }
        if self.node_kind == NodeKind.SWITCH:
            missing = {
                field: "This field is required for switch nodes."
                for field, value in switch_only.items()
                if value is None
            }
            if missing:
                raise ValidationError(missing)
        elif self.node_kind == NodeKind.TERMINAL:
            populated = {
                field: "This field only applies to switch nodes."
                for field, value in switch_only.items()
                if value is not None
            }
            if populated:
                raise ValidationError(populated)
