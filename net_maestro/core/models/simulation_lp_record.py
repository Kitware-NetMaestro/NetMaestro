from django.db import models

from net_maestro.core.models import SimulationFile


class SimulationLpRecord(models.Model):
    simulation_file = models.ForeignKey(SimulationFile, on_delete=models.CASCADE)

    PE_ID = models.IntegerField()
    KP_ID = models.IntegerField()
    LP_ID = models.IntegerField()
    events_processed = models.IntegerField()
    events_abort = models.IntegerField()
    events_rolled_back = models.IntegerField()
    network_sends = models.IntegerField()
    network_reads = models.IntegerField()
    efficiency = models.FloatField()
    virtual_time = models.FloatField()
    real_time = models.FloatField()
