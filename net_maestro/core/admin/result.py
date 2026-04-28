from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import Result


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "created"]
    list_filter = ["status", "created"]
    ordering = ["-created"]
