from __future__ import annotations

from django.db import models

from net_maestro.core.models import SimulationBaseRecord, SimulationFile


class SimulationLpRecord(SimulationBaseRecord):
    simulation_file = models.ForeignKey(
        SimulationFile, on_delete=models.CASCADE, related_name="lp_records"
    )

    KP_ID = models.IntegerField()
    LP_ID = models.IntegerField()
    events_abort = models.IntegerField()

    def __str__(self) -> str:
        return f"LpRecord {self.id}"
