from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import NodeLink


@admin.register(NodeLink)
class NodeLinkAdmin(admin.ModelAdmin):
    list_select_related = ["topology", "source", "target"]
    list_display = [
        "id",
        "topology__run__name",
        "source__name",
        "target__name",
    ]
    list_filter = [
        "topology__run",
        "source__name",
        "target__name",
    ]
