from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import Run


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_select_related = ["topology", "result"]
    list_display = ["name", "result__status", "topology", "created", "description"]
    list_filter = ["result__status", "created"]
    search_fields = ["name", "description"]
    ordering = ["-created"]
