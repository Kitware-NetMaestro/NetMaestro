from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import TopologyLink


@admin.register(TopologyLink)
class TopologyLinkAdmin(admin.ModelAdmin):
    list_display = ["topology", "source_node", "target_node", "bandwidth"]
    list_filter = ["topology"]
    search_fields = ["source_node__name", "target_node__name"]
    ordering = ["-bandwidth"]
