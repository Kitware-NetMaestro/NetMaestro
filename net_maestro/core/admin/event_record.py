from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import EventRecord


@admin.register(EventRecord)
class EventRecordAdmin(admin.ModelAdmin):
    list_select_related = ["event_file"]
    list_display = [
        "id",
        "event_file__file",
        "source_lp",
        "dest_lp",
        "time_step",
        "virtual_send",
        "virtual_receive",
        "event_type",
    ]
    list_filter = [
        "source_lp",
        "dest_lp",
        "time_step",
        "event_type",
    ]
