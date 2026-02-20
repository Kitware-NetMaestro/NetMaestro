from __future__ import annotations

from django.db import models


class RunStatus(models.TextChoices):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
