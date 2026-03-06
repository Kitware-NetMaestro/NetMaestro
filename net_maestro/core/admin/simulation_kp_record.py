from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import SimulationKpRecord


@admin.register(SimulationKpRecord)
class SimulationKpRecordAdmin(admin.ModelAdmin):
    list_select_related = ["simulation_file"]
    list_display = [
        "id",
        "simulation_file__file",
        "PE_ID",
        "KP_ID",
        "events_processed",
        "events_abort",
        "events_rolled_back",
        "total_rollbacks",
    ]
