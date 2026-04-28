from __future__ import annotations

from django.db import models


class Topology(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return f"Topology - {self.name}"
