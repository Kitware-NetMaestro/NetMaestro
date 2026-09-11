from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import Topology


@admin.register(Topology)
class TopologyAdmin(admin.ModelAdmin):
    list_display = ["name", "created", "description"]
    list_filter = ["created"]
    search_fields = ["name", "description"]
    ordering = ["-created"]
