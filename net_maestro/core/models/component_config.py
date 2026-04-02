from __future__ import annotations

from django.db import models

from net_maestro.core.constants import ModelType
from net_maestro.core.models.topology import Topology


class ComponentConfig(models.Model):
    topology = models.ForeignKey(
        Topology, on_delete=models.CASCADE, related_name="component_configs"
    )

    model = models.CharField(max_length=255, choices=ModelType.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["topology", "model"],
                name="unique_config_per_model_per_topology",
            )
        ]

    def __str__(self) -> str:
        return f"ComponentConfig - {self.model}"
