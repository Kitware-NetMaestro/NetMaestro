from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import (
    FFWPortRecord,
    FFWResultFile,
    FFWSwitchRecord,
    FFWTerminalRecord,
)


@admin.register(FFWResultFile)
class FFWResultFileAdmin(admin.ModelAdmin):
    list_display = ("id", "uploaded_at", "run", "file")
    search_fields = ("id", "uploaded_at", "run", "file")


@admin.register(FFWPortRecord)
class FFWPortRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "port_index",
        "is_terminal",
        "target_index",
        "port_capacity_mbit_per_interval",
    )
    search_fields = ("port_index", "is_terminal", "target_index", "port_capacity_mbit_per_interval")


@admin.register(FFWSwitchRecord)
class FFWSwitchRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lpid",
        "switch_id",
        "stats_type",
        "ts",
        "peid",
        "kpid",
        "num_ports",
        "shared_buffer_capacity_mbit",
        "shared_buffer_occupancy_mbit",
    )
    search_fields = (
        "id",
        "lpid",
        "switch_id",
        "peid",
        "kpid",
        "num_ports",
        "shared_buffer_capacity_mbit",
        "shared_buffer_occupancy_mbit",
    )
    list_filter = ("stats_type",)


@admin.register(FFWTerminalRecord)
class FFWTerminalRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "terminal_id",
        "peid",
        "kpid",
        "lpid",
        "stats_type",
        "ts",
        "attached_switch",
        "active_flows",
        "link_paused",
    )
    search_fields = (
        "id",
        "terminal_id",
        "peid",
        "kpid",
        "lpid",
        "attached_switch",
        "active_flows",
        "link_paused",
    )
    list_filter = ("stats_type",)
