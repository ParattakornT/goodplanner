from django.contrib import admin
from django.utils.html import format_html

from .models import (BusySlot, EmailLog, GroupTask, MailSender, Meeting, Membership, Notification, PlanningGroup,
                     Task, User)

admin.site.site_header = 'Good Planner · ผู้ดูแลระบบ'
admin.site.site_title = 'Good Planner Admin'
admin.site.index_title = 'ข้อมูลในระบบ'
admin.site.site_url = '/dashboard.html'


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'display_name', 'email_reminders', 'is_staff', 'created_at')
    search_fields = ('email', 'display_name')
    list_filter = ('is_staff', 'email_reminders')
    # Password hashes are never shown or edited here.
    exclude = ('password', 'groups', 'user_permissions')
    readonly_fields = ('last_login', 'created_at')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'task_date', 'task_time', 'priority', 'completed')
    list_filter = ('completed', 'priority', 'task_date')
    search_fields = ('title', 'user__email')
    date_hierarchy = 'task_date'


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fields = ('user', 'availability_confirmed', 'share_personal', 'joined_at')
    readonly_fields = ('joined_at',)


@admin.register(PlanningGroup)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'invite_code', 'start_date', 'end_date', 'availability_deadline')
    search_fields = ('name', 'invite_code', 'owner__email')
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'availability_confirmed', 'share_personal')
    list_filter = ('availability_confirmed',)


@admin.register(BusySlot)
class BusySlotAdmin(admin.ModelAdmin):
    list_display = ('member', 'date', 'start', 'end')
    list_filter = ('date',)


@admin.register(GroupTask)
class GroupTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'group', 'assignee', 'due_date', 'due_time', 'status')
    list_filter = ('status',)


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('title', 'group', 'date', 'start', 'end')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'message', 'created_at', 'read_at')


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'kind', 'key', 'sent_at')
    list_filter = ('kind',)


@admin.register(MailSender)
class MailSenderAdmin(admin.ModelAdmin):
    list_display = ('email', 'connected_at', 'reconnect')
    fields = ('email', 'connected_at')
    readonly_fields = ('email', 'connected_at')

    @admin.display(description='เชื่อมต่อใหม่')
    def reconnect(self, obj):
        return format_html('<a href="/auth/gmail">เชื่อมต่อ Gmail ใหม่</a>')

    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = 'บัญชี Gmail ที่ใช้ส่งแจ้งเตือน (เพิ่ม/เปลี่ยนได้ที่ /auth/gmail)'
        return super().changelist_view(request, extra_context)
