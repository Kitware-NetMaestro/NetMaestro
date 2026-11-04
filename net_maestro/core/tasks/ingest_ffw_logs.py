"""Keep an FFW run's model logs and reduce them to per-step records.

Called by `run_ffw_simulation` once the model has run and its binary stats are
ingested, before the summary is computed, so the summary can read the step records.
The logs are a refinement of the samples rather than a requirement: a run whose
logs are missing still has every sampled number, so a missing log is a warning.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.core.files import File
from django.db import transaction

from net_maestro.core.constants import FFWModelLogKind
from net_maestro.core.models import FFWLinkStepRecord, FFWModelLog, FFWSwitchStepRecord
from net_maestro.core.parsers.ffw_event_log import link_steps, switch_steps
from net_maestro.core.services.ffw import model_logs_for

if TYPE_CHECKING:
    from pathlib import Path

    from net_maestro.core.models import Run

logger = logging.getLogger(__name__)


def ingest_ffw_logs(run: Run, config_path: Path) -> dict[str, int]:
    """Store the run's model logs and replace its step records with ones built from them.

    `config_path` is the generated traffic config the model ran with; it names the
    logs and gives the step length. Earlier logs and step records of the run are
    replaced, as a re-run replaces the stats files.

    Returns how many records of each kind were created.
    """
    logs = model_logs_for(config_path)
    counts = {"switch_steps": 0, "link_steps": 0}
    with transaction.atomic():
        run.ffw_model_logs.all().delete()
        run.ffw_switch_steps.all().delete()
        run.ffw_link_steps.all().delete()
        for kind in FFWModelLogKind:
            path = logs.paths.get(str(kind))
            if path is None or not path.is_file():
                logger.warning("Run %s: no %s log at %s", run.pk, kind.label.lower(), path)
                continue
            with path.open("rb") as stream:
                FFWModelLog.objects.create(
                    run=run,
                    kind=kind,
                    file=File(stream, name=path.name),
                    interval_seconds=logs.interval_seconds,
                    num_steps=logs.num_steps,
                )
            with path.open(newline="", encoding="utf-8") as lines:
                if kind == FFWModelLogKind.SWITCH:
                    switch_records = [
                        FFWSwitchStepRecord(
                            run=run,
                            switch_id=step.switch_id,
                            step=step.step,
                            step_start_s=step.step * logs.interval_seconds,
                            peak_occupancy_mbit=step.peak_occupancy_mbit,
                            buffer_mbit=step.buffer_mbit,
                            dropped_mbit=step.dropped_mbit,
                        )
                        for step in switch_steps(lines)
                    ]
                    FFWSwitchStepRecord.objects.bulk_create(switch_records)
                    counts["switch_steps"] = len(switch_records)
                else:
                    link_records = [
                        FFWLinkStepRecord(
                            run=run,
                            switch_id=step.switch_id,
                            port=step.port,
                            target_is_terminal=step.target_is_terminal,
                            target_index=step.target_index,
                            step=step.step,
                            step_start_s=step.step * logs.interval_seconds,
                            sent_mbit=step.sent_mbit,
                            capacity_mbit=step.capacity_mbit,
                        )
                        for step in link_steps(lines)
                    ]
                    FFWLinkStepRecord.objects.bulk_create(link_records)
                    counts["link_steps"] = len(link_records)
    return counts


__all__ = ["ingest_ffw_logs"]
