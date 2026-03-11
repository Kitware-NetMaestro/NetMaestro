from __future__ import annotations

from django.db import models

from net_maestro.core.models.model_file import ModelFile


class ModelRecord(models.Model):
    model_file = models.ForeignKey(ModelFile, on_delete=models.CASCADE)

    lp_id = models.IntegerField()
    component_id = models.IntegerField()
    virtual_time = models.FloatField()
    real_time = models.FloatField()
    send_count = models.IntegerField()
    send_bytes = models.BigIntegerField()
    send_time = models.FloatField()
    receive_count = models.IntegerField()
    receive_bytes = models.BigIntegerField()
    receive_time = models.FloatField()

    def __str__(self) -> str:
        return f"ModelRecord {self.id}"
