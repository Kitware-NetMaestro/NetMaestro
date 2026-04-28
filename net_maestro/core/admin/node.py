from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import Node


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_select_related = ["topology"]
    list_display = [
        "name",
        "topology",
        "model",
        "node_type",
        "ingress_bandwidth",
        "egress_bandwidth",
        "ingress_latency",
        "egress_latency",
    ]
    list_filter = ["topology", "model", "node_type"]
