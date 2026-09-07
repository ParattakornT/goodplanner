from django.contrib import admin
from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "date", "start_time", "end_time", "priority", "is_done")
    list_filter = ("priority", "is_done", "date")
    search_fields = ("title", "owner__username")
