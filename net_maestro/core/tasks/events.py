import logging

from celery import shared_task
from django.db import transaction

from net_maestro.core.models.event_file import EventFile
from net_maestro.core.models.event_record import EventRecord
from net_maestro.core.parsers.event_trace_file import EventFile as EventFileParser

logger = logging.getLogger(__name__)


@shared_task
def run_event_task(event_file_pk: int) -> dict:
    """Parse event file and ingest records into the database."""
    event_file_model = EventFile.objects.get(pk=event_file_pk)

    with event_file_model.file.open('rb') as f:
        content = f.read()

    with transaction.atomic():
        parser = EventFileParser(content)
        batch = []
        for record_dict in parser.parse_event_records():
            # Create EventRecord instance (not saved yet)
            event_record = EventRecord(
                event_file=event_file_model,
                source_lp=str(record_dict['source_lp']),
                dest_lp=str(record_dict['dest_lp']),
                time_step=record_dict['time_step'],
                virtual_send=str(record_dict['virtual_send']),
                virtual_receive=str(record_dict['virtual_receive']),
                event_type=str(record_dict['event_type']),
            )
            batch.append(event_record)
        EventRecord.objects.bulk_create(batch)
