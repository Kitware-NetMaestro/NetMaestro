from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction

from net_maestro.core.models import (
    FFWPortRecord,
    FFWResultFile,
    FFWSwitchRecord,
    FFWTerminalRecord,
)
from net_maestro.core.parsers.ffw_file import parse_ffw_files

logger = logging.getLogger(__name__)


@shared_task
def run_ffw_ingest_task(
    ffw_result_files: list[int],
    num_rails: int = 1,
    num_qos: int = 1,
    radix: int = 7,
    model_family: str = "fluid-flow-wan",
) -> None:
    # TODO: Adjust to be able to pass list of files
    for result_file in ffw_result_files:
        ffw_result_file = FFWResultFile.objects.get(pk=result_file)
        rows, unknown = parse_ffw_files(
            files=[ffw_result_file.pk],
            num_rails=num_rails,
            num_qos=num_qos,
            radix=radix,
            model_family=model_family,
        )

        switch_records: list[FFWSwitchRecord] = []
        port_records: list[FFWPortRecord] = []
        terminal_records: list[FFWTerminalRecord] = []

        with transaction.atomic():
            for lp_type, entries in rows.items():
                for row in entries:
                    sample = {
                        "result_file": ffw_result_file,
                        "stats_type": row["stats_type"],
                        "ts": row["ts"],
                        "real_time": row.get("real_time"),
                        "gvt": row.get("gvt"),
                        "end_time": row.get("end_time"),
                        "peid": row["peid"],
                        "kpid": row["kpid"],
                        "lpid": row["lpid"],
                    }

                    if lp_type == "ffw-switch":
                        switch_row = FFWSwitchRecord(
                            **sample,
                            switch_id=row.get("switch_id"),
                            num_ports=row.get("num_ports"),
                            shared_buffer_capacity_mbit=row.get("shared_buffer_capacity_mbit"),
                            shared_buffer_occupancy_mbit=row.get("shared_buffer_occupancy_mbit"),
                            buffered_residual_mbit=row.get("buffered_residual_mbit"),
                            sent_mbit=row.get("sent_mbit"),
                            delivered_local_mbit=row.get("delivered_local_mbit"),
                            dropped_mbit=row.get("dropped_mbit"),
                            pause_frames_sent=row.get("pause_frames_sent", 0),
                            resume_frames_sent=row.get("resume_frames_sent", 0),
                            pause_updates_sent=row.get("pause_updates_sent", 0),
                            pause_frames_received=row.get("pause_frames_received", 0),
                            resume_frames_received=row.get("resume_frames_received", 0),
                            pause_updates_received=row.get("pause_updates_received", 0),
                        )
                        switch_records.append(switch_row)

                        num_ports = row.get("num_ports") or 0
                        for port_index in range(num_ports):
                            port_records.append(
                                FFWPortRecord(
                                    switch_record=switch_row,
                                    port_index=port_index,
                                    is_terminal=bool(
                                        row.get(f"port_target_is_terminal_p{port_index}", 0)
                                    ),
                                    target_index=row.get(f"port_target_index_p{port_index}"),
                                    port_capacity_mbit_per_interval=row.get(
                                        f"port_capacity_mbit_per_interval_p{port_index}"
                                    ),
                                    port_queued_mbit=row.get(f"port_queued_mbit_p{port_index}"),
                                    port_sent_mbit=row.get(f"port_sent_mbit_p{port_index}"),
                                    port_pause_time_ns=row.get(f"port_pause_time_ns_p{port_index}"),
                                    port_output_paused=bool(
                                        row.get(f"port_output_paused_p{port_index}", 0)
                                    ),
                                    port_queued_segments=row.get(
                                        f"port_queued_segments_p{port_index}"
                                    ),
                                )
                            )

                    elif lp_type == "ffw-terminal":
                        terminal_records.append(
                            FFWTerminalRecord(
                                **sample,
                                terminal_id=row.get("terminal_id"),
                                attached_switch=row.get("attached_switch"),
                                active_flows=row.get("active_flows"),
                                link_paused=bool(row.get("link_paused", 0)),
                                generated_mbit=row.get("generated_mbit"),
                                sent_to_switch_mbit=row.get("sent_to_switch_mbit"),
                                received_mbit=row.get("received_mbit"),
                                source_backlog_mbit=row.get("source_backlog_mbit"),
                                send_rate_sum_mbps=row.get("send_rate_sum_mbps"),
                                pause_time_ns=row.get("pause_time_ns", 0),
                                pause_frames_received=row.get("pause_frames_received", 0),
                                resume_frames_received=row.get("resume_frames_received", 0),
                                pause_updates_received=row.get("pause_updates_received", 0),
                                rate_updates_received=row.get("rate_updates_received", 0),
                            )
                        )

            if switch_records:
                FFWSwitchRecord.objects.bulk_create(switch_records)

            if port_records:
                FFWPortRecord.objects.bulk_create(port_records)

            if terminal_records:
                FFWTerminalRecord.objects.bulk_create(terminal_records)

        if unknown:
            logger.warning("FFW ingest had %s unknown payloads", len(unknown))
