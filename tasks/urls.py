from django.urls import path
from . import views

app_name = "tasks"

urlpatterns = [
    path("calendar/", views.calendar_view, name="calendar"),
    path("calendar/events.json", views.calendar_events_json, name="calendar_events"),
    path("today/", views.today_view, name="today"),
    path("", views.task_list, name="list"),
    path("new/", views.task_create, name="create"),
    path("<int:pk>/", views.task_detail, name="detail"),
    path("<int:pk>/edit/", views.task_update, name="update"),
    path("<int:pk>/delete/", views.task_delete, name="delete"),
    path("<int:pk>/toggle/", views.task_toggle_done, name="toggle"),
]
