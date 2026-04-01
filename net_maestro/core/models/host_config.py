from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from net_maestro.core.constants import TrafficType
from net_maestro.core.models.component_config import ComponentConfig


class HostConfig(ComponentConfig):
    traffic = models.CharField(max_length=255, choices=TrafficType.choices)
    num_messages = models.IntegerField(validators=[MinValueValidator(0)])
    arrival_time = models.FloatField(validators=[MinValueValidator(0.0)])
    payload_size = models.IntegerField(validators=[MinValueValidator(0)])

    def __str__(self) -> str:
        return f"HostConfig - {self.model}"
