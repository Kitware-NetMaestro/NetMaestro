from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import (
    FFWPortSnapshot,
    FFWResultFile,
    FFWSnapshot,
    FFWSwitchSnapshot,
    FFWTerminalSnapshot,
)


@admin.register(FFWResultFile)
class FFWResultFileAdmin(admin.ModelAdmin):
    list_display = ("id", "uploaded_at", "run", "file")
    search_fields = ("id", "uploaded_at", "run", "file")


@admin.register(FFWSnapshot)
class FFWSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "stats_type", "ts", "real_time", "gvt", "end_time")
    search_fields = ("id", "stats_type", "ts", "real_time", "gvt", "end_time")


@admin.register(FFWPortSnapshot)
class FFWPortSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "port_index",
        "is_terminal",
        "target_index",
        "port_capacity_mbit_per_interval",
    )
    search_fields = ("port_index", "is_terminal", "target_index", "port_capacity_mbit_per_interval")


@admin.register(FFWSwitchSnapshot)
class FFWSwitchSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lpid",
        "switch_id",
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


@admin.register(FFWTerminalSnapshot)
class FFWTerminalSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "terminal_id",
        "peid",
        "kpid",
        "lpid",
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
