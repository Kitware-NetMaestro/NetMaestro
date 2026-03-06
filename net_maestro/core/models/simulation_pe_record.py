from django.db import models

from net_maestro.core.models.simulation_file import SimulationFile


class SimulationPeRecord(models.Model):
    simulation_file = models.ForeignKey(SimulationFile, on_delete=models.CASCADE)

    PE_ID = models.IntegerField()
    events_processed = models.IntegerField()
    events_aborted = models.IntegerField()
    events_rolled_back = models.IntegerField()
    total_rollbacks = models.IntegerField()
    secondary_rollbacks = models.IntegerField()
    fossil_collection_attempts = models.IntegerField()
    pq_queue_size = models.IntegerField()
    network_sends = models.IntegerField()
    network_reads = models.IntegerField()
    number_gvt = models.IntegerField()
    pe_event_ties = models.IntegerField()
    all_reduce = models.IntegerField()
    efficiency = models.FloatField()
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
    virtual_time = models.FloatField()
    real_time = models.FloatField()
