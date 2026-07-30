from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import ComponentModel


@admin.register(ComponentModel)
class ComponentModelAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "component_type", "description", "engine", "parameters"]
    list_filter = [
        "component_type",
        "engine",
    ]
