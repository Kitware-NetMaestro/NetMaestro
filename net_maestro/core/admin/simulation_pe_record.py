from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import SimulationPeRecord


@admin.register(SimulationPeRecord)
class SimulationPeRecordAdmin(admin.ModelAdmin):
    list_select_related = ["simulation_file"]
    list_display = [
        "id",
        "simulation_file",
        "PE_ID",
        "virtual_time",
        "real_time",
        "events_processed",
        "events_rolled_back",
        "total_rollbacks",
        "efficiency",
    ]
    list_filter = ["simulation_file", "PE_ID"]
