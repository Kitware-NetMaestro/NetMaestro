from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import Node


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_select_related = ["topology", "config"]
    list_display = [
        "name",
        "type",
        "topology__run__name",
        "config",
        "ingress_bandwidth",
        "egress_bandwidth",
        "ingress_latency",
        "egress_latency",
    ]
    list_filter = [
        "type",
        "topology__run",
        "config__model",
    ]
