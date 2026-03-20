from __future__ import annotations

from django.db import models


class SimulationBaseRecord(models.Model):
    PE_ID = models.IntegerField()
    events_processed = models.IntegerField()
    events_rolled_back = models.IntegerField()
    network_sends = models.IntegerField()
    network_reads = models.IntegerField()
    efficiency = models.FloatField()
    virtual_time = models.FloatField()
    real_time = models.FloatField()

    class Meta:
        abstract = True
