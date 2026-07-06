from __future__ import annotations

from django.db import models


class RunStatus(models.TextChoices):
    SAVED = "saved"
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


class SynchProtocol(models.IntegerChoices):
    SEQUENTIAL = 1, "Sequential"
    CONSERVATIVE = 2, "Conservative"
    OPTIMISTIC = 3, "Optimistic"
    OPTIMISTIC_DEBUG = 4, "Optimistic Debug"
    OPTIMISTIC_REALTIME = 5, "Optimistic Realtime"
    REVERSE_HANDLER_CHECK = 6, "Reverse Handler Check"
