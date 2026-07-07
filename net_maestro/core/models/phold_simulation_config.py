from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from net_maestro.core.constants import SynchProtocol
from net_maestro.core.models.run import Run


class PHOLDSimulationConfig(models.Model):
    """PHOLD simulation configuration parameters submitted for a Run.

    NOTE: This model currently handles the single PHOLD scenario. As we support more
    simulation types, this should be generalized so we can store various parameter sets
    without duplicating schema for each model.
    """

    run = models.OneToOneField(Run, on_delete=models.CASCADE, related_name="phold_config")

    synch = models.IntegerField(
        choices=SynchProtocol,
        default=SynchProtocol.OPTIMISTIC,
        verbose_name="Synchronization protocol",
    )
    avl_size = models.IntegerField(
        default=18,
        validators=[MinValueValidator(10), MaxValueValidator(24)],
        verbose_name="AVL tree size",
    )
    nlp = models.IntegerField(
        default=8, validators=[MinValueValidator(1)], verbose_name="LPs per processor"
    )
    remote = models.FloatField(
        default=0.25,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name="Remote event rate",
    )
    mean = models.FloatField(
        default=1.0, validators=[MinValueValidator(0.1)], verbose_name="Mean timestamp"
    )
    mult = models.FloatField(
        default=1.4, validators=[MinValueValidator(1.0)], verbose_name="Memory multiplier"
    )
    lookahead = models.FloatField(default=1.0, validators=[MinValueValidator(0.1)])
    start_events = models.IntegerField(
        default=1, validators=[MinValueValidator(1)], verbose_name="Start events per LP"
    )
    memory = models.IntegerField(
        default=100, validators=[MinValueValidator(0)], verbose_name="Additional memory buffers"
    )
    stagger = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"PHOLD config for Run {self.run_id}"
