from __future__ import annotations

from django.db import models


class Topology(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Topology {self.id}: {self.name}"
