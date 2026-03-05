from __future__ import annotations

from collections import defaultdict

from celery import shared_task
from django.db import transaction

from net_maestro.core.models.simulation_file import SimulationFile
from net_maestro.core.models.simulation_kp_record import SimulationKpRecord
from net_maestro.core.models.simulation_lp_record import SimulationLpRecord
from net_maestro.core.models.simulation_pe_record import SimulationPeRecord
from net_maestro.core.parsers.ross_binary_file import RecordType
from net_maestro.core.parsers.ross_binary_file import ROSSFile as SimulationFileParser


@shared_task
def run_simulation_task(simulation_file_pk: int) -> None:
    simulation_file = SimulationFile.objects.get(pk=simulation_file_pk)

    # Mapping for three possible models
    models = {
        RecordType.PE: SimulationPeRecord,
        RecordType.KP: SimulationKpRecord,
        RecordType.LP: SimulationLpRecord,
    }

    with simulation_file.file.open("rb") as sim_file:
         content = sim_file.read()

    with transaction.atomic():
        parser = SimulationFileParser(content)
        record_batches = defaultdict(list)

        # Create batches for each model type
        for record_type, record_data in parser.parse_simulation_records():
            if record_type in models:
                model = models[record_type]
                record = model(simulation_file=simulation_file, **record_data)
                record_batches[record_type].append(record)

        # Bulk create batches for each model type
        for record_type, batch in record_batches.items():
            model = models[record_type]
            model.objects.bulk_create(batch)
