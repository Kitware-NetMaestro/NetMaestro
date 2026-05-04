from __future__ import annotations

from django.db import models


class RunStatus(models.TextChoices):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeType(models.TextChoices):
    HOST = "host"
    ROUTER = "router"
    SWITCH = "switch"


class ModelType(models.TextChoices):
    MODELNET_SIMPLEP2P = "modelnet_simplep2p"
    SIMPLEP2P = "simplep2p"


class TrafficType(models.TextChoices):
    UNIFORM = "uniform"
