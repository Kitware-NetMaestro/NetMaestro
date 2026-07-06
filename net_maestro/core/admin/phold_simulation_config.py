from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import PHOLDSimulationConfig


@admin.register(PHOLDSimulationConfig)
class PHOLDSimulationConfigAdmin(admin.ModelAdmin):
    list_select_related = ["run"]
    list_display = ["id", "run", "synch", "nlp", "remote", "mean", "lookahead"]
    list_filter = ["synch", "stagger"]
    search_fields = ["run__name"]
