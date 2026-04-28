from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import ModelRecord


@admin.register(ModelRecord)
class ModelRecordAdmin(admin.ModelAdmin):
    list_select_related = ["model_file"]
    list_display = [
        "id",
        "model_file",
        "lp_id",
        "component_id",
        "virtual_time",
        "real_time",
        "send_count",
        "send_bytes",
        "send_time",
        "receive_count",
        "receive_bytes",
        "receive_time",
    ]
    list_filter = ["model_file", "lp_id", "component_id"]
