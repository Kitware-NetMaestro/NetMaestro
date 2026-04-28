from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import ModelFile


@admin.register(ModelFile)
class ModelFileAdmin(admin.ModelAdmin):
    list_select_related = ["result"]
    list_display = ["id", "result", "result__status", "uploaded", "file"]
    list_filter = ["result__status", "uploaded"]
