from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from net_maestro.core.constants import FFWTrafficMode, SynchProtocol
from net_maestro.core.models.run import Run
from net_maestro.core.topology import TopologyError, get_topology


class FFWSimulationConfig(models.Model):
    """Fluid-flow WAN simulation settings submitted for a Run."""

    model_label = "FFW"

    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="ffw_configs")

    # A name rather than a foreign key until topologies are stored in the database.
    topology_name = models.CharField(max_length=200, verbose_name="Topology")
    traffic = models.CharField(max_length=20, choices=FFWTrafficMode, default=FFWTrafficMode.RANDOM)
    np = models.IntegerField(
        default=1, validators=[MinValueValidator(1)], verbose_name="MPI processes"
    )
    sync = models.IntegerField(
        choices=SynchProtocol,
        default=SynchProtocol.SEQUENTIAL,
        verbose_name="Synchronization protocol",
    )

    def __str__(self) -> str:
        return f"FFW config for Run {self.run_id}"

    def clean(self) -> None:
        super().clean()
        try:
            get_topology(self.topology_name)
        except TopologyError as exc:
            raise ValidationError({"topology_name": str(exc)}) from exc
