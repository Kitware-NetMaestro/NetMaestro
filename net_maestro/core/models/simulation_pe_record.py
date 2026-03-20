from __future__ import annotations

from django.db import models

from net_maestro.core.models import SimulationBaseRecord, SimulationFile


class SimulationPeRecord(SimulationBaseRecord):
    simulation_file = models.ForeignKey(
        SimulationFile, on_delete=models.CASCADE, related_name="pe_records"
    )

    events_aborted = models.IntegerField()
    total_rollbacks = models.IntegerField()
    secondary_rollbacks = models.IntegerField()
    fossil_collection_attempts = models.IntegerField()
    pq_queue_size = models.IntegerField()
    number_gvt = models.IntegerField()
    pe_event_ties = models.IntegerField()
    all_reduce = models.IntegerField()
    network_read_time = models.FloatField()
    network_other_time = models.FloatField()
    gvt_time = models.FloatField()
    fossil_collect_time = models.FloatField()
    event_abort_time = models.FloatField()
    event_process_time = models.FloatField()
    pq_time = models.FloatField()
    rollback_time = models.FloatField()
    cancel_q_time = models.FloatField()
    avl_time = models.FloatField()
    buddy_time = models.FloatField()
    lz4_time = models.FloatField()

    def __str__(self) -> str:
        return f"PeRecord {self.id}"
