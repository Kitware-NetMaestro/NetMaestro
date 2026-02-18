import logging

from celery import shared_task
from django.db import transaction

from net_maestro.core.models.event_file import EventFile
from net_maestro.core.models.event_record import EventRecord
from net_maestro.core.parsers.event_trace_file import EventFileParser

logger = logging.getLogger(__name__)


@shared_task
def run_event_task(event_file_pk: int) -> None:
    """Parse event file and ingest records into the database."""
    event_file_model = EventFile.objects.get(pk=event_file_pk)

    with event_file_model.file.open('rb') as f:
        content = f.read()

    with transaction.atomic():
        parser = EventFileParser(content)
        batch = [EventRecord(**rec_dict) for rec_dict in parser.parse_event_records()]
        EventRecord.objects.bulk_create(batch)
