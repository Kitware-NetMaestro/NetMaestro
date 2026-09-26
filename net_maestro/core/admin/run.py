from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import Run


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ["name", "simulation_type", "status", "created", "description"]
    list_filter = ["status", "simulation_type", "created"]
    search_fields = ["name", "description"]
    ordering = ["-created"]
