from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from planner import views
from planner import group_views as groups

urlpatterns = [
    path('', views.page, {'name': 'login.html'}),
    path('login.html', views.page, {'name': 'login.html'}),
    path('register.html', views.page, {'name': 'register.html'}),
    path('privacy.html', views.page, {'name': 'privacy.html'}),
    path('dashboard.html', views.page, {'name': 'dashboard.html'}),
    path('groups.html', views.page, {'name': 'groups.html'}),
    *[path(name, views.asset, {'name': name}) for name in views.ASSETS],
    path('api/register', views.register),
    path('api/login', views.login),
    path('api/logout', views.logout),
    path('api/me', views.me),
    path('auth/google', views.google_login),
    path('auth/google/callback', views.google_callback),
    path('auth/gmail', views.gmail_connect),
    path('auth/gmail/callback', views.gmail_callback),
    path('api/cron/reminders', views.cron_reminders),
    # The admin uses the normal sign-in page (email or Google), not its own form.
    path('admin/login/', RedirectView.as_view(url='/login.html')),
    path('admin', RedirectView.as_view(url='/admin/')),
    path('admin/', admin.site.urls),
    path('api/tasks', views.tasks),
    path('api/tasks/<int:task_id>', views.task_detail),
    path('api/groups', groups.groups),
    path('api/groups/join', groups.join),
    path('api/groups/<int:group_id>', groups.detail),
    path('api/groups/<int:group_id>/availability', groups.free_times),
    path('api/groups/<int:group_id>/preferences', groups.preferences),
    path('api/groups/<int:group_id>/busy', groups.busy_create),
    path('api/groups/<int:group_id>/busy/<int:slot_id>', groups.busy_delete),
    path('api/groups/<int:group_id>/tasks', groups.task_create),
    path('api/groups/<int:group_id>/tasks/<int:task_id>', groups.task_detail),
    path('api/groups/<int:group_id>/meetings', groups.meeting_create),
    path('api/groups/<int:group_id>/meetings/<int:meeting_id>', groups.meeting_delete),
    path('api/groups/<int:group_id>/remind', groups.remind),
    path('api/notifications', groups.notifications),
    path('api/group-feed', groups.feed),
]
handler400 = 'planner.views.bad_request'
handler403 = 'planner.views.forbidden'
handler404 = 'planner.views.not_found'
handler500 = 'planner.views.server_error'
