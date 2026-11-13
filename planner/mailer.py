"""Email reminders sent from the owner's Gmail account through the Gmail API.

Render's free plan blocks outbound SMTP, so mail goes over HTTPS instead.
When no Gmail account is connected (local development, tests) messages fall
back to Django's EMAIL_BACKEND, which prints them to the console by default.
"""
import base64
import json
import logging
import threading
from datetime import datetime, time, timedelta
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import EmailLog, GroupTask, MailSender, Meeting, Task, User

logger = logging.getLogger(__name__)
TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'
SEND_ENDPOINT = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
DUE_SOON_WINDOW = timedelta(hours=2)
DIGEST_HOUR = 6  # Local time (Asia/Bangkok) after which the daily summary may go out.


class MailError(Exception):
    pass


def _post(url, data, headers):
    request = Request(url, data=data, headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read(65536) or b'{}')
    except HTTPError as exc:
        detail = exc.read(2048).decode('utf-8', 'replace')
        raise MailError(f'Google returned {exc.code}: {detail}') from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise MailError('Google request failed') from exc


def _access_token(sender):
    result = _post(TOKEN_ENDPOINT, urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'refresh_token': sender.refresh_token,
        'grant_type': 'refresh_token',
    }).encode(), {'Content-Type': 'application/x-www-form-urlencoded'})
    token = result.get('access_token')
    if not isinstance(token, str) or not token:
        raise MailError('Google did not return an access token')
    return token


def site_url(path=''):
    return settings.SITE_URL.rstrip('/') + path if settings.SITE_URL else path


def deliver(to, subject, body):
    """Send one message now. Returns True on success; never raises."""
    sender = MailSender.objects.filter(pk=1).exclude(refresh_token='').first()
    try:
        if sender is None:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to])
            return True
        message = EmailMessage()
        message['From'] = f'Good Planner <{sender.email}>'
        message['To'] = to
        message['Subject'] = subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')
        _post(SEND_ENDPOINT, json.dumps({'raw': raw}).encode(), {
            'Authorization': 'Bearer ' + _access_token(sender),
            'Content-Type': 'application/json',
        })
        return True
    except Exception:  # A failed email must never break the request that caused it.
        logger.exception('Email to %s failed', to)
        return False


def email_users(user_ids, subject, body, actor=None):
    """Queue a message to every opted-in user, after the database commit."""
    recipients = list(User.objects.filter(pk__in=set(user_ids), is_active=True, email_reminders=True)
                      .exclude(pk=actor).values_list('email', flat=True))
    if not recipients:
        return
    footer = f'\n\nเปิด Good Planner: {site_url("/dashboard.html")}\nปิดการแจ้งเตือนทางอีเมลได้ที่ปุ่ม ✉ บนหน้าแผนส่วนตัว'

    def send_all():
        for address in recipients:
            deliver(address, subject, body + footer)

    def schedule():
        if settings.EMAIL_ASYNC:
            threading.Thread(target=send_all, daemon=True).start()
        else:
            send_all()
    transaction.on_commit(schedule)


def _claim(user, kind, key):
    """Record a send exactly once, so a repeated cron call cannot double-send."""
    try:
        with transaction.atomic():
            EmailLog.objects.create(user=user, kind=kind, key=key)
        return True
    except IntegrityError:
        return False


def _clock(value):
    return f'{value // 60:02d}:{value % 60:02d}'


def _task_line(title, day, time_text, group=None):
    where = f' (กลุ่ม {group})' if group else ''
    when = day.strftime('%d/%m/%Y') + (f' {time_text}' if time_text else '')
    return f'• {title}{where} — {when}'


def digest_for(user, today):
    tomorrow = today + timedelta(days=1)
    personal = Task.objects.filter(user=user, completed=False)
    group = GroupTask.objects.filter(assignee__user=user).exclude(status='done').select_related('group')
    overdue = ([_task_line(t.title, t.task_date, t.task_time) for t in personal.filter(task_date__lt=today).order_by('task_date')]
               + [_task_line(t.title, t.due_date, t.due_time, t.group.name) for t in group.filter(due_date__lt=today).order_by('due_date')])
    upcoming = ([_task_line(t.title, t.task_date, t.task_time) for t in personal.filter(task_date__range=(today, tomorrow)).order_by('task_date', 'task_time')]
                + [_task_line(t.title, t.due_date, t.due_time, t.group.name) for t in group.filter(due_date__range=(today, tomorrow)).order_by('due_date', 'due_time')])
    meetings = [f'• {m.title} (กลุ่ม {m.group.name}) — {_clock(m.start)}–{_clock(m.end)}'
                for m in Meeting.objects.filter(participants__user=user, date=today).distinct().select_related('group').order_by('start')]
    if not (overdue or upcoming or meetings):
        return None
    parts = [f'สวัสดี {user.display_name}', '', f'สรุปงานของวันที่ {today.strftime("%d/%m/%Y")}']
    if overdue:
        parts += ['', f'เลยกำหนดแล้วยังไม่เสร็จ ({len(overdue)})', *overdue]
    if upcoming:
        parts += ['', f'ต้องส่งวันนี้และพรุ่งนี้ ({len(upcoming)})', *upcoming]
    if meetings:
        parts += ['', f'นัดหมายวันนี้ ({len(meetings)})', *meetings]
    subject = f'Good Planner: งานวันนี้ {len(upcoming)} รายการ' + (f', เลยกำหนด {len(overdue)}' if overdue else '')
    return subject, '\n'.join(parts)


def send_digests(now=None):
    now = timezone.localtime(now)
    if now.hour < DIGEST_HOUR:
        return 0
    sent = 0
    for user in User.objects.filter(is_active=True, email_reminders=True):
        content = digest_for(user, now.date())
        if content and _claim(user, 'digest', now.date().isoformat()):
            sent += deliver(user.email, content[0], content[1] + f'\n\nเปิด Good Planner: {site_url("/dashboard.html")}')
    return sent


def _minutes(text):
    hours, mins = text.split(':')
    return int(hours) * 60 + int(mins)


def send_due_soon(now=None):
    """Alert once per item that is due, or starts, within the next two hours."""
    now = timezone.localtime(now)
    end = now + DUE_SOON_WINDOW
    days = {now.date(), end.date()}

    def within(day, minute):
        moment = timezone.make_aware(datetime.combine(day, time()) + timedelta(minutes=minute))
        return now <= moment <= end, moment

    items = []
    for task in Task.objects.filter(task_date__in=days, completed=False, user__email_reminders=True,
                                    user__is_active=True).exclude(task_time='').select_related('user'):
        ok, moment = within(task.task_date, _minutes(task.task_time))
        if ok:
            items.append((task.user, f'task-{task.pk}', f'ใกล้ถึงเวลา: {task.title}', f'งาน "{task.title}" ถึงกำหนดเวลา {moment:%H:%M} วันนี้'))
    for task in GroupTask.objects.filter(due_date__in=days, assignee__user__email_reminders=True).exclude(status='done') \
            .exclude(due_time='').select_related('assignee__user', 'group'):
        ok, moment = within(task.due_date, _minutes(task.due_time))
        if ok:
            items.append((task.assignee.user, f'group-task-{task.pk}', f'ใกล้ถึงกำหนดส่ง: {task.title}',
                          f'งานกลุ่ม "{task.title}" ในกลุ่ม {task.group.name} ต้องส่งเวลา {moment:%H:%M}'))
    for meeting in Meeting.objects.filter(date__in=days).prefetch_related('participants__user').select_related('group'):
        ok, moment = within(meeting.date, meeting.start)
        if ok:
            for member in meeting.participants.all():
                if member.user.email_reminders and member.user.is_active:
                    items.append((member.user, f'meeting-{meeting.pk}', f'นัดหมายใกล้เริ่ม: {meeting.title}',
                                  f'นัด "{meeting.title}" ของกลุ่ม {meeting.group.name} เริ่มเวลา {moment:%H:%M}'))
    sent = 0
    for user, key, subject, body in items:
        if _claim(user, 'due-soon', key):
            sent += deliver(user.email, 'Good Planner: ' + subject, f'สวัสดี {user.display_name}\n\n{body}\n\nเปิด Good Planner: {site_url("/dashboard.html")}')
    return sent
