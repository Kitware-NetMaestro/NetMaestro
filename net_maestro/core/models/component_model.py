from __future__ import annotations

from django.db import models


class ComponentType(models.TextChoices):
    HOST = "host", "Host"
    ROUTER = "router", "Router"
    SWITCH = "switch", "Switch"
    TERMINAL = "terminal", "Terminal"


class ComponentModel(models.Model):
    # TODO: Revisit when we have a User model: created_by, updated_by
    name = models.CharField(max_length=255)
    base_model = models.CharField(max_length=255, blank=True)
    component_type = models.CharField(max_length=100, choices=ComponentType.choices)
    description = models.TextField(blank=True)
    engine = models.CharField(max_length=100)
    parameters = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"ComponentModel {self.name}"
