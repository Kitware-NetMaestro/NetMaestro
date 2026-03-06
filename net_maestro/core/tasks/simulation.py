import logging

from celery import shared_task
from django.db import transaction

from net_maestro.core.models.simulation_file import SimulationFile
from net_maestro.core.models.simulation_pe_record import SimulationPeRecord
from net_maestro.core.parsers.ross_binary_file import RecordType
from net_maestro.core.parsers.ross_binary_file import ROSSFile as SimulationFileParser


@shared_task
def run_simulation_task(simulation_file_pk: int) -> None:
    simulation_file = SimulationFile.objects.get(pk=simulation_file_pk)

    with simulation_file.file.open("rb") as sim_file:
         content = sim_file.read()

    with transaction.atomic():
        parser = SimulationFileParser(content)
        batch = [
            SimulationPeRecord(simulation_file=simulation_file, **obj)
            for record_type, obj in parser.parse_simulation_records()
            if record_type == RecordType.PE
        ]
        SimulationPeRecord.objects.bulk_create(batch)
