from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import TopologyNode


@admin.register(TopologyNode)
class TopologyNodeAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "topology",
        "node_kind",
        "order_index",
        "terminals",
        "terminal_bandwidth",
        "switch_buffer",
    ]
    list_filter = ["node_kind"]
    search_fields = ["name", "node_kind"]
    ordering = ["order_index"]
