from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import SwitchConfig


@admin.register(SwitchConfig)
class SwitchConfigAdmin(admin.ModelAdmin):
    list_select_related = ["topology"]
    list_display = [
        "id",
        "topology__run__name",
        "model",
    ]
    list_filter = [
        "model",
        "topology__run__status",
    ]
