from django.db import models

from net_maestro.core.models.event_file import EventFile


class EventRecord(models.Model):
    event_file = models.ForeignKey(EventFile, on_delete=models.CASCADE)

    source_lp = models.FloatField()
    dest_lp = models.FloatField()
    time_step = models.IntegerField()
    event_type = models.FloatField()
    virtual_send = models.FloatField()
    virtual_receive = models.FloatField()
