from __future__ import annotations

from django.db import models
from s3_file_field import S3FileField

from net_maestro.core.models.results import Result


class ModelFile(models.Model):
    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name="model_files")
    uploaded = models.DateTimeField(auto_now_add=True)

    file = S3FileField()

    def __str__(self) -> str:
        return f"ModelFile {self.id}"
