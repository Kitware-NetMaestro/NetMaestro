from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import PHOLDSimulationLpRecord


@admin.register(PHOLDSimulationLpRecord)
class PHOLDSimulationLpRecordAdmin(admin.ModelAdmin):
    list_select_related = ["simulation_file"]
    list_display = ["id", "simulation_file", "KP_ID", "LP_ID", "events_abort", "s_process_event"]
    list_filter = ["simulation_file__run__status"]
    search_fields = ["simulation_file__run__name"]
    readonly_fields = ["id"]
