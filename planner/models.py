import secrets

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        user = self.model(email=email.strip().lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if not extra_fields['is_staff'] or not extra_fields['is_superuser']:
            raise ValueError('Superusers must have staff and superuser permissions')
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(max_length=254, unique=True)
    display_name = models.CharField(max_length=80)
    # Legacy Node scrypt hashes are longer than Django's default 128 characters.
    password = models.CharField(max_length=256)
    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_reminders = models.BooleanField(default=True)
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['display_name']

    class Meta:
        constraints = [models.UniqueConstraint(Lower('email'), name='user_email_case_insensitive')]


class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=120)
    notes = models.TextField(blank=True, default='', max_length=2000)
    task_date = models.DateField()
    task_time = models.CharField(max_length=5, blank=True, default='')
    end_time = models.CharField(max_length=5, blank=True, default='')
    priority = models.CharField(max_length=6, default='normal', choices=[('low', 'ไม่เร่งด่วน'), ('normal', 'ปกติ'), ('high', 'สำคัญมาก')])
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=['user', 'task_date'], name='task_owner_date')]
        constraints = [models.CheckConstraint(condition=models.Q(priority__in=['low', 'normal', 'high']), name='task_valid_priority')]


class LegacyImport(models.Model):
    """One-time marker: restarting must never overwrite plans edited in Django."""
    source = models.CharField(max_length=40, unique=True)
    imported_at = models.DateTimeField(default=timezone.now)
    user_count = models.PositiveIntegerField()
    task_count = models.PositiveIntegerField()


def invitation_code():
    return secrets.token_hex(5).upper()


class PlanningGroup(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_planning_groups')
    invite_code = models.CharField(max_length=10, unique=True, default=invitation_code)
    start_date = models.DateField()
    end_date = models.DateField()
    window_start = models.PositiveSmallIntegerField(default=540)
    window_end = models.PositiveSmallIntegerField(default=1260)
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    availability_deadline = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(end_date__gte=models.F('start_date')), name='group_date_order'),
            models.CheckConstraint(condition=models.Q(window_start__lt=models.F('window_end'), window_end__lte=1440), name='group_window_order'),
            models.CheckConstraint(condition=models.Q(duration_minutes__gte=30, duration_minutes__lte=720), name='group_duration_range'),
        ]

    @property
    def availability_closed(self):
        return self.availability_deadline is not None and timezone.now() >= self.availability_deadline


class Membership(models.Model):
    group = models.ForeignKey(PlanningGroup, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='planning_memberships')
    share_personal = models.BooleanField(default=False)
    availability_confirmed = models.BooleanField(default=False)
    personal_busy_snapshot = models.JSONField(default=list, blank=True)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['group', 'user'], name='unique_group_member')]


class BusySlot(models.Model):
    member = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name='busy_slots')
    date = models.DateField()
    start = models.PositiveSmallIntegerField()
    end = models.PositiveSmallIntegerField()

    class Meta:
        indexes = [models.Index(fields=['member', 'date'], name='busy_member_date')]
        constraints = [models.CheckConstraint(condition=models.Q(start__lt=models.F('end'), end__lte=1440), name='busy_time_order')]


class GroupTask(models.Model):
    group = models.ForeignKey(PlanningGroup, on_delete=models.CASCADE, related_name='group_tasks')
    assignee = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name='assigned_tasks')
    title = models.CharField(max_length=120)
    notes = models.TextField(blank=True, default='', max_length=2000)
    due_date = models.DateField()
    due_time = models.CharField(max_length=5, default='', blank=True)
    status = models.CharField(max_length=5, default='todo', choices=[('todo', 'รอเริ่ม'), ('doing', 'กำลังทำ'), ('done', 'เสร็จแล้ว')])
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(status__in=['todo', 'doing', 'done']), name='group_task_status')]


class Meeting(models.Model):
    group = models.ForeignKey(PlanningGroup, on_delete=models.CASCADE, related_name='meetings')
    title = models.CharField(max_length=120)
    date = models.DateField()
    start = models.PositiveSmallIntegerField()
    end = models.PositiveSmallIntegerField()
    participants = models.ManyToManyField(Membership, related_name='meetings')
    conflict_acknowledgement = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(start__lt=models.F('end'), end__lte=1440), name='meeting_time_order')]


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='planner_notifications')
    group = models.ForeignKey(PlanningGroup, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=300)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'read_at'], name='notification_user_read')]


class MailSender(models.Model):
    """The single Gmail account that sends reminders (row id is always 1)."""
    email = models.EmailField(max_length=254)
    refresh_token = models.TextField(blank=True, default='')
    connected_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.email


class EmailLog(models.Model):
    """One row per reminder sent; the unique key stops duplicate emails."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_logs')
    kind = models.CharField(max_length=10)
    key = models.CharField(max_length=40)
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'kind', 'key'], name='email_log_once')]
