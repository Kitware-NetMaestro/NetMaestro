from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import SimulationPeRecord


@admin.register(SimulationPeRecord)
class SimulationPeRecordAdmin(admin.ModelAdmin):
    list_select_related = ["simulation_file"]
    list_display = [
        "id",
        "simulation_file__file",
        "PE_ID",
        "events_processed",
        "events_rolled_back",
        "total_rollbacks",
    ]
    list_filter = [
        # what would be a goo filter field here?
    ]
