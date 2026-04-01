from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import Topology


@admin.register(Topology)
class TopologyAdmin(admin.ModelAdmin):
    list_select_related = ["run"]
    list_display = [
        "id",
        "run__name",
        "run__status",
        "run__created",
    ]
    list_filter = [
        "run__status",
        "run__created",
    ]
