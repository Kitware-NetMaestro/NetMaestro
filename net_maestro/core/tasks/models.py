from __future__ import annotations

import logging

from celery import shared_task

from net_maestro.core.models.model_file import ModelFile
from net_maestro.core.models.model_record import ModelRecord
from net_maestro.core.parsers.model_file import ModelFileParser

logger = logging.getLogger(__name__)


@shared_task
def run_model_task(model_file_pk: int) -> None:
    """Parse model file and ingest records into the database."""
    model_file_model = ModelFile.objects.get(pk=model_file_pk)

    with model_file_model.file.open("rb") as f:
        content = f.read()

    parser = ModelFileParser(content)
    batch = [
        ModelRecord(model_file=model_file_model, **rec_dict)
        for rec_dict in parser.parse_model_records()
    ]
    ModelRecord.objects.bulk_create(batch)
