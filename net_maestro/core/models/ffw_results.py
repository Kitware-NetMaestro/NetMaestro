from __future__ import annotations

from django.db import models
from s3_file_field import S3FileField


class FFWResultFile(models.Model):
    """
    One uploaded FFW result set.
    This is the source-of-truth container for the binary files produced by the run.
    """

    run = models.ForeignKey("Run", on_delete=models.CASCADE, related_name="ffw_result_files")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    file = S3FileField()

    def __str__(self) -> str:
        return f"FFWResultFile {self.id}"


class FFWSnapshot(models.Model):
    """
    A time-slice of parsed FFW data (state snapshot at ts).
    """

    result_file = models.ForeignKey(
        FFWResultFile,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    stats_type = models.CharField(max_length=16)  # rt / vt / gvt
    ts = models.BigIntegerField()
    real_time = models.FloatField(null=True, blank=True)
    gvt = models.FloatField(null=True, blank=True)
    end_time = models.BigIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f"FFWSnapshot {self.id} @ ts={self.ts}"


class FFWSwitchSnapshot(models.Model):
    """
    One switch row from the FFW switch data.
    Holds the switch-level state for a single snapshot.
    """

    snapshot = models.ForeignKey(
        FFWSnapshot,
        on_delete=models.CASCADE,
        related_name="switch_rows",
    )
    lpid = models.IntegerField()
    switch_id = models.IntegerField()
    peid = models.IntegerField(null=True, blank=True)
    kpid = models.IntegerField(null=True, blank=True)

    num_ports = models.IntegerField(null=True, blank=True)
    shared_buffer_capacity_mbit = models.FloatField(null=True, blank=True)
    shared_buffer_occupancy_mbit = models.FloatField(null=True, blank=True)
    buffered_residual_mbit = models.FloatField(null=True, blank=True)
    sent_mbit = models.FloatField(null=True, blank=True)
    delivered_local_mbit = models.FloatField(null=True, blank=True)
    dropped_mbit = models.FloatField(null=True, blank=True)

    pause_frames_sent = models.BigIntegerField(default=0)
    resume_frames_sent = models.BigIntegerField(default=0)
    pause_updates_sent = models.BigIntegerField(default=0)
    pause_frames_received = models.BigIntegerField(default=0)
    resume_frames_received = models.BigIntegerField(default=0)
    pause_updates_received = models.BigIntegerField(default=0)

    end_time = models.FloatField(null=True, blank=True)

    def __str__(self) -> str:
        return f"FFWSwitchSnapshot {self.id} | lpid={self.lpid}"


class FFWPortSnapshot(models.Model):
    """
    One port entry from a switch snapshot.
    This model captures the per-port topology and queue state.
    """

    switch_snapshot = models.ForeignKey(
        FFWSwitchSnapshot,
        on_delete=models.CASCADE,
        related_name="ports",
    )
    port_index = models.IntegerField()
    is_terminal = models.BooleanField()
    target_index = models.IntegerField(null=True, blank=True)

    port_capacity_mbit_per_interval = models.FloatField(null=True, blank=True)
    port_queued_mbit = models.FloatField(null=True, blank=True)
    port_sent_mbit = models.FloatField(null=True, blank=True)
    port_pause_time_ns = models.BigIntegerField(null=True, blank=True)
    port_output_paused = models.BooleanField(default=False)
    port_queued_segments = models.IntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["switch_snapshot", "port_index"],
                name="unique_ffw_port_per_switch",
            )
        ]

    def __str__(self) -> str:
        return (
            f"FFWPortSnapshot {self.id} | switch={self.switch_snapshot_id} port={self.port_index}"
        )


class FFWTerminalSnapshot(models.Model):
    """
    One terminal row from the analysis-LP / terminal snapshot data.
    """

    snapshot = models.ForeignKey(
        FFWSnapshot,
        on_delete=models.CASCADE,
        related_name="terminal_rows",
    )

    peid = models.IntegerField()
    kpid = models.IntegerField()
    lpid = models.IntegerField()
    terminal_id = models.IntegerField()
    attached_switch = models.IntegerField(null=True, blank=True)

    active_flows = models.IntegerField(null=True, blank=True)
    link_paused = models.BooleanField(default=False)
    generated_mbit = models.FloatField(null=True, blank=True)
    sent_to_switch_mbit = models.FloatField(null=True, blank=True)
    received_mbit = models.FloatField(null=True, blank=True)
    source_backlog_mbit = models.FloatField(null=True, blank=True)
    send_rate_sum_mbps = models.FloatField(null=True, blank=True)

    pause_time_ns = models.FloatField(default=0.0)
    pause_frames_received = models.BigIntegerField(default=0)
    resume_frames_received = models.BigIntegerField(default=0)
    pause_updates_received = models.BigIntegerField(default=0)
    rate_updates_received = models.BigIntegerField(default=0)
    end_time = models.FloatField(null=True, blank=True)

    def __str__(self) -> str:
        return f"FFWTerminalSnapshot {self.id} | terminal={self.terminal_id}"
