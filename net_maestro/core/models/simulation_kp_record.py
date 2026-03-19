from __future__ import annotations

from django.db import models

from net_maestro.core.models import SimulationBaseRecord, SimulationFile


class SimulationKpRecord(SimulationBaseRecord):
    simulation_file = models.ForeignKey(
        SimulationFile, on_delete=models.CASCADE, related_name="kp_records"
    )

    KP_ID = models.IntegerField()
    events_abort = models.IntegerField()
    total_rollbacks = models.IntegerField()
    secondary_rollbacks = models.IntegerField()
    time_ahead_gvt = models.FloatField()

    def __str__(self) -> str:
        return f"KpRecord {self.id}"
