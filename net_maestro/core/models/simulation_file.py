from django.db import models
from s3_file_field.fields import S3FileField

from net_maestro.core.models.run import Run


class SimulationFile(models.Model):
    run = models.ForeignKey(Run, on_delete=models.CASCADE)
    uploaded = models.DateTimeField(auto_now_add=True)

    file = S3FileField()

    def __str__(self) -> str:
        return f"SimulationFile {self.id}"
