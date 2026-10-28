from __future__ import annotations

from django.contrib import admin

from net_maestro.core.models import Ensemble, Run


class MemberInline(admin.TabularInline):
    model = Run
    fields = ("member_index", "name", "status", "member_params")
    readonly_fields = fields
    ordering = ["member_index"]
    extra = 0
    can_delete = False
    show_change_link = True


@admin.register(Ensemble)
class EnsembleAdmin(admin.ModelAdmin):
    list_display = ["name", "simulation_type", "created"]
    list_filter = ["simulation_type", "created"]
    search_fields = ["name", "description"]
    ordering = ["-created"]
    inlines = [MemberInline]
