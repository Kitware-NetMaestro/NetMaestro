from __future__ import annotations

from collections import defaultdict
import logging
from pathlib import Path
import tempfile

from celery import shared_task
from django.conf import settings
from django.core.management import call_command
from django.db import transaction

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import Run
from net_maestro.core.models.simulation_file import SimulationFile
from net_maestro.core.models.simulation_kp_record import SimulationKpRecord
from net_maestro.core.models.simulation_lp_record import PHOLDSimulationLpRecord, SimulationLpRecord
from net_maestro.core.models.simulation_pe_record import SimulationPeRecord
from net_maestro.core.parsers.ross_binary_file import RecordType
from net_maestro.core.parsers.ross_binary_file import ROSSFile as SimulationFileParser

logger = logging.getLogger(__name__)


@shared_task
def mark_run_completed(run_id: int) -> None:
    """Mark a run as completed after all ingestion tasks finish.

    This task is the final link in the ingestion chain, ensuring the run is only
    marked as completed once all data ingestion is done and available in the database.
    """
    try:
        run = Run.objects.get(pk=run_id)
        run.status = RunStatus.COMPLETED
        run.save()
        logger.info("Marked run %s as completed", run_id)
    except Run.DoesNotExist:
        logger.exception("Run %s not found when trying to mark as completed", run_id)


@shared_task
def mark_run_failed(request: object, exc: Exception, traceback: object, *, run_id: int) -> None:
    """Mark a run as failed when an ingestion task in the chain errors.

    Attached as an error callback (``link_error``) to each task in the ingestion
    chain so that a failure anywhere transitions the run to FAILED rather than
    leaving it stuck in RUNNING. Celery invokes error callbacks with the failed
    task's ``request``, the raised ``exc``, and its ``traceback``; ``run_id`` is
    bound as a keyword argument when the callback is attached.
    """
    logger.error(
        "Run %s ingestion task %s failed: %r",
        run_id,
        getattr(request, "id", "unknown"),
        exc,
    )
    try:
        run = Run.objects.get(pk=run_id)
        run.status = RunStatus.FAILED
        run.save()
    except Run.DoesNotExist:
        logger.exception("Run %s not found when trying to mark as failed", run_id)


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
            # Extract format metadata if present
            format_type = record_data.pop("_format", None)

            # Filter out padding fields that don't exist in the model
            filtered_data = {k: v for k, v in record_data.items() if not k.startswith("padding_")}

            # For LP records, choose the appropriate model based on format metadata.
            # The parser determines the format from binary payload size (36 vs 48 bytes).
            if record_type == RecordType.LP and format_type == "phold":
                model_class: type[
                    SimulationKpRecord
                    | SimulationLpRecord
                    | SimulationPeRecord
                    | PHOLDSimulationLpRecord
                ] = PHOLDSimulationLpRecord
            else:
                model = models[record_type]

            record = model(simulation_file=simulation_file, **filtered_data)
            record_batches[model].append(record)

        # Bulk create batches for each model type
        for model, batch in record_batches.items():
            # PHOLDSimulationLpRecord uses multi-table inheritance and can't use bulk_create
            if model == PHOLDSimulationLpRecord:
                for record in batch:
                    record.save()
            else:
                model.objects.bulk_create(batch)  # type: ignore[arg-type]


@shared_task
def run_phold_simulation(  # noqa: PLR0913
    *,
    run_id: int,
    synch: int,
    avl_size: int,
    nlp: int,
    remote: float,
    mean: float,
    mult: float,
    lookahead: float,
    start_events: int,
    memory: int,
    stagger: bool,
) -> None:
    """Execute PHOLD simulation with given parameters and update run status."""
    run = Run.objects.get(pk=run_id)

    # Update status to RUNNING
    run.status = RunStatus.RUNNING
    run.save()

    # Get configuration values (these should be set in Django settings)
    phold_path = getattr(settings, "PHOLD_BINARY_PATH", "")
    default_output_dir = Path(tempfile.gettempdir()) / "phold_output"
    output_dir = Path(getattr(settings, "PHOLD_OUTPUT_DIR", default_output_dir))
    np = getattr(settings, "PHOLD_MPI_PROCESSES", 1)

    if not phold_path:
        logger.error("PHOLD_BINARY_PATH not configured in settings")
        run.status = RunStatus.FAILED
        run.save()
        return

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build arguments for call_command
    # For djclick commands, we need to pass options as positional arguments
    command_args = [
        "--name",
        run.name,
        "--synch",
        str(synch),
        "--avl-size",
        str(avl_size),
        "--nlp",
        str(nlp),
        "--remote",
        str(remote),
        "--mean",
        str(mean),
        "--mult",
        str(mult),
        "--lookahead",
        str(lookahead),
        "--start-events",
        str(start_events),
        "--memory",
        str(memory),
        "--np",
        str(np),
        "--phold-path",
        str(Path(phold_path)) if phold_path else "",
        "--output-dir",
        str(output_dir),
        "--run-id",
        str(run_id),
    ]

    if stagger:
        command_args.extend(["--stagger", "True"])

    logger.info("Running PHOLD simulation for run %s", run_id)

    try:
        # Execute the management command using Django's call_command
        call_command("run_phold", *command_args)
        logger.info("PHOLD simulation finished for run %s; ingestion queued", run_id)

        # Status stays RUNNING. The management command queues a chain of ingestion
        # tasks ending in mark_run_completed, which sets COMPLETED once the data is
        # actually available in the database.

    except Exception:
        logger.exception(
            "PHOLD failed for run %s",
            run_id,
        )

        # Update status to FAILED
        run.status = RunStatus.FAILED
        run.save()
