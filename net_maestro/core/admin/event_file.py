from django.contrib import admin

from net_maestro.core.models import EventFile


@admin.register(EventFile)
class EventFileAdmin(admin.ModelAdmin):
    list_select_related = ['run']
    list_display = ['id', 'run__name', 'uploaded', 'file']
    list_filter = ['run', 'uploaded']
