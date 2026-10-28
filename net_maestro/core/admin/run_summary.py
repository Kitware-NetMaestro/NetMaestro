from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import RunSummary


@admin.register(RunSummary)
class RunSummaryAdmin(admin.ModelAdmin):
    list_display = ["run", "stats_type", "computed_at"]
    list_filter = ["stats_type"]
    search_fields = ["run__name"]
    raw_id_fields = ["run"]
    readonly_fields = ["computed_at"]
