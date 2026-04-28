from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import Topology


@admin.register(Topology)
class TopologyAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]
