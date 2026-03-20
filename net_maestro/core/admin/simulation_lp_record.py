from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import SimulationLpRecord


@admin.register(SimulationLpRecord)
class SimulationLpRecordAdmin(admin.ModelAdmin):
    list_select_related = ["simulation_file"]
    list_display = [
        "id",
        "simulation_file__file",
        "PE_ID",
        "KP_ID",
        "LP_ID",
        "events_processed",
        "events_abort",
        "events_rolled_back",
    ]
