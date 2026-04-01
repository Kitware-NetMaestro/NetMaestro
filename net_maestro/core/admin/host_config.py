from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import HostConfig


@admin.register(HostConfig)
class HostConfigAdmin(admin.ModelAdmin):
    list_select_related = ["topology"]
    list_display = [
        "id",
        "topology__run__name",
        "model",
        "traffic",
        "num_messages",
        "arrival_time",
        "payload_size",
    ]
    list_filter = [
        "model",
        "traffic",
        "topology__run__status",
    ]
