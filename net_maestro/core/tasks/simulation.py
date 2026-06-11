from __future__ import annotations

from collections import defaultdict
import logging

from celery import shared_task
from django.db import transaction

from net_maestro.core.models.simulation_file import SimulationFile
from net_maestro.core.models.simulation_kp_record import SimulationKpRecord
from net_maestro.core.models.simulation_lp_record import PHOLDSimulationLpRecord, SimulationLpRecord
from net_maestro.core.models.simulation_pe_record import SimulationPeRecord
from net_maestro.core.parsers.ross_binary_file import RecordType
from net_maestro.core.parsers.ross_binary_file import ROSSFile as SimulationFileParser

logger = logging.getLogger(__name__)


@shared_task
def run_simulation_task(simulation_file_pk: int) -> None:
    simulation_file = SimulationFile.objects.get(pk=simulation_file_pk)

    # Mapping for three possible models
    models: dict[RecordType, type[SimulationKpRecord | SimulationLpRecord | SimulationPeRecord]] = {
        RecordType.PE: SimulationPeRecord,
        RecordType.KP: SimulationKpRecord,
        RecordType.LP: SimulationLpRecord,
    }

    with simulation_file.file.open("rb") as sim_file:
        content = sim_file.read()

    with transaction.atomic():
        parser = SimulationFileParser(content)
        record_batches: dict[
            type,
            list[
                SimulationKpRecord
                | SimulationLpRecord
                | SimulationPeRecord
                | PHOLDSimulationLpRecord
            ],
        ] = defaultdict(list)

        # Create batches for each model type
        for record_type, record_data in parser.parse_simulation_records():
            # Filter out padding fields that don't exist in the model
            filtered_data = {k: v for k, v in record_data.items() if not k.startswith("padding_")}

            # For LP records, choose the appropriate model based on presence of PHOLD-specific field
            if record_type == RecordType.LP and "s_process_event" in filtered_data:
                model = PHOLDSimulationLpRecord
            else:
                model = models[record_type]

            record = model(simulation_file=simulation_file, **filtered_data)
            record_batches[model].append(record)

        # Bulk create batches for each model type
        for model, batch in record_batches.items():
            model.objects.bulk_create(batch)  # type: ignore[arg-type]
