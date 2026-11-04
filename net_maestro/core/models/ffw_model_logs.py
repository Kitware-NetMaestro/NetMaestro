"""The FFW model's own per-step logs, and what NetMaestro keeps of them.

The VT samples are taken every tenth of a fluid step, but the events that decide a
step's peak buffer occupancy and its link loads happen within milliseconds of the
step boundary: an arrival that crosses the PAUSE watermark is drained back down to
the low watermark mid-step, and that early drain is charged to the next step's link
capacity. Samples land after the drain and on the wrong side of the charge, so they
read peaks too low and utilizations above 100%. The model's switch and
fluid-segment logs record every egress as it happens, so they are kept, and reduced
at ingest to one row per switch per step and one per link per step, which is what
the summaries and series read when a run has them.
"""

from __future__ import annotations

from django.db import models
from s3_file_field import S3FileField

from net_maestro.core.constants import FFWModelLogKind


class FFWModelLog(models.Model):
    """One CSV log the FFW model wrote for a run, kept because the run's `/tmp` is not.

    `interval_seconds` and `num_steps` are the run's fluid-step grid, read from the
    generated traffic config at ingest: the step records only exist for steps with
    traffic, so the mean utilization needs the run's length from here.
    """

    run = models.ForeignKey("Run", on_delete=models.CASCADE, related_name="ffw_model_logs")
    kind = models.CharField(max_length=16, choices=FFWModelLogKind)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file = S3FileField()
    interval_seconds = models.FloatField()
    num_steps = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "kind"], name="unique_ffw_model_log_per_kind")
        ]

    def __str__(self) -> str:
        return f"FFWModelLog {self.id} | run={self.run_id} {self.kind}"


class FFWLinkStepRecord(models.Model):
    """What one switch port sent in one fluid step, against that step's capacity.

    `step` is the step whose capacity the volume was charged to, which for a PAUSE
    drain is the step after the one it ran in (`handle_switch_egress_drain` in the
    model). Charged this way `sent_mbit <= capacity_mbit` always holds: the model
    stops with an error otherwise. `step_start_s` is `step * interval_seconds`.
    """

    run = models.ForeignKey("Run", on_delete=models.CASCADE, related_name="ffw_link_steps")
    switch_id = models.IntegerField()
    port = models.IntegerField()
    target_is_terminal = models.BooleanField()
    target_index = models.IntegerField()
    step = models.IntegerField()
    step_start_s = models.FloatField()
    sent_mbit = models.FloatField()
    capacity_mbit = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "switch_id", "port", "step"], name="unique_ffw_link_step"
            )
        ]

    def __str__(self) -> str:
        return f"FFWLinkStepRecord {self.id} | switch={self.switch_id} port={self.port}"


class FFWSwitchStepRecord(models.Model):
    """One switch's highest shared-buffer occupancy, buffer size and drops in one step.

    `step` is the step the events ran in. `peak_occupancy_mbit` is the most the
    model's log shows queued in the shared buffer at any egress in the step, before
    or after it; `dropped_mbit` sums the step's drops.
    """

    run = models.ForeignKey("Run", on_delete=models.CASCADE, related_name="ffw_switch_steps")
    switch_id = models.IntegerField()
    step = models.IntegerField()
    step_start_s = models.FloatField()
    peak_occupancy_mbit = models.FloatField()
    buffer_mbit = models.FloatField()
    dropped_mbit = models.FloatField(default=0.0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "switch_id", "step"], name="unique_ffw_switch_step"
            )
        ]

    def __str__(self) -> str:
        return f"FFWSwitchStepRecord {self.id} | switch={self.switch_id} step={self.step}"
