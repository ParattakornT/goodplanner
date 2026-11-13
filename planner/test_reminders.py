import json
from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from . import mailer
from .models import EmailLog, GroupTask, MailSender, Meeting, Membership, PlanningGroup, Task, User

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def at(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, datetime.min.time()) + timedelta(hours=hour, minutes=minute))


@override_settings(ALLOWED_HOSTS=['testserver'], EMAIL_BACKEND=LOCMEM, EMAIL_ASYNC=False, CRON_SECRET='s3cret',
                   SITE_URL='https://planner.example')
class ReminderTests(TestCase):
    def setUp(self):
        cache.clear()
        self.today = date(2026, 11, 20)
        self.owner = User.objects.create_user('owner@example.com', 'Test-password-123', display_name='เจ้าของ')
        self.member = User.objects.create_user('member@example.com', 'Test-password-123', display_name='สมาชิก')
        self.group = PlanningGroup.objects.create(name='ทีมเอกสาร', owner=self.owner, start_date=self.today,
                                                  end_date=self.today + timedelta(days=5))
        self.own = Membership.objects.create(group=self.group, user=self.owner)
        self.mem = Membership.objects.create(group=self.group, user=self.member)

    def client_for(self, user):
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        client.get('/dashboard.html')
        return client

    def send(self, client, url, data, method='post'):
        return getattr(client, method)(url, data=json.dumps(data), content_type='application/json',
            HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value, HTTP_ORIGIN='http://testserver')

    def test_assigned_task_and_new_meeting_email_the_member_not_the_actor(self):
        owner = self.client_for(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            self.send(owner, f'/api/groups/{self.group.pk}/tasks',
                      {'title': 'สรุปบทที่ 3', 'date': (self.today + timedelta(days=1)).isoformat(), 'time': '18:00', 'assigneeId': self.mem.pk})
        with self.captureOnCommitCallbacks(execute=True):
            self.send(owner, f'/api/groups/{self.group.pk}/meetings',
                      {'title': 'ประชุมรวมงาน', 'date': self.today.isoformat(), 'start': 600, 'end': 660, 'participants': [self.own.pk, self.mem.pk]})
        self.assertEqual([m.to for m in mail.outbox], [['member@example.com'], ['member@example.com']])
        self.assertIn('สรุปบทที่ 3', mail.outbox[0].subject)
        self.assertIn('18:00', mail.outbox[0].body)
        self.assertIn('https://planner.example/dashboard.html', mail.outbox[0].body)
        self.assertIn('ประชุมรวมงาน', mail.outbox[1].subject)

    def test_opted_out_user_gets_no_email(self):
        member = self.client_for(self.member)
        response = self.send(member, '/api/me', {'emailReminders': False}, 'patch')
        self.assertFalse(response.json()['user']['emailReminders'])
        with self.captureOnCommitCallbacks(execute=True):
            self.send(self.client_for(self.owner), f'/api/groups/{self.group.pk}/tasks',
                      {'title': 'งาน', 'date': self.today.isoformat(), 'assigneeId': self.mem.pk})
        self.assertEqual(mail.outbox, [])
        self.assertEqual(self.send(member, '/api/me', {'emailReminders': 'no'}, 'patch').status_code, 400)

    def test_digest_lists_overdue_upcoming_and_meetings_once_per_day(self):
        Task.objects.create(user=self.member, title='รายงานเก่า', task_date=self.today - timedelta(days=2))
        Task.objects.create(user=self.member, title='ส่งการบ้าน', task_date=self.today, task_time='13:00')
        Task.objects.create(user=self.member, title='เสร็จแล้ว', task_date=self.today, completed=True)
        GroupTask.objects.create(group=self.group, assignee=self.mem, title='ทำสไลด์', due_date=self.today + timedelta(days=1))
        meeting = Meeting.objects.create(group=self.group, title='ซ้อมพรีเซนต์', date=self.today, start=900, end=960)
        meeting.participants.set([self.mem])
        self.assertEqual(mailer.send_digests(at(self.today, 5)), 0)  # Too early in the morning.
        self.assertEqual(mailer.send_digests(at(self.today, 7)), 1)
        self.assertEqual(mailer.send_digests(at(self.today, 8)), 0)  # Already sent today.
        body = mail.outbox[0].body
        for text in ('รายงานเก่า', 'ส่งการบ้าน', 'ทำสไลด์', 'ทีมเอกสาร', 'ซ้อมพรีเซนต์', '15:00'):
            self.assertIn(text, body)
        self.assertNotIn('เสร็จแล้ว', body)
        self.assertEqual(mail.outbox[0].to, ['member@example.com'])  # Owner has nothing due.

    def test_due_soon_alerts_once_within_two_hours(self):
        Task.objects.create(user=self.member, title='ส่งแล็บ', task_date=self.today, task_time='10:30')
        Task.objects.create(user=self.member, title='ยังอีกนาน', task_date=self.today, task_time='15:00')
        GroupTask.objects.create(group=self.group, assignee=self.mem, title='อัปโหลดไฟล์', due_date=self.today, due_time='11:00')
        GroupTask.objects.create(group=self.group, assignee=self.mem, title='ส่งไปแล้ว', due_date=self.today, due_time='11:00', status='done')
        self.assertEqual(mailer.send_due_soon(at(self.today, 9)), 2)
        self.assertEqual(mailer.send_due_soon(at(self.today, 9, 30)), 0)
        subjects = sorted(m.subject for m in mail.outbox)
        self.assertTrue(any('ส่งแล็บ' in s for s in subjects) and any('อัปโหลดไฟล์' in s for s in subjects))
        self.assertEqual(EmailLog.objects.filter(kind='due-soon').count(), 2)

    def test_cron_endpoint_requires_the_secret(self):
        client = Client()
        self.assertEqual(client.post('/api/cron/reminders').status_code, 403)
        self.assertEqual(client.post('/api/cron/reminders', HTTP_AUTHORIZATION='Bearer wrong').status_code, 403)
        response = client.post('/api/cron/reminders', HTTP_AUTHORIZATION='Bearer s3cret')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {'digest', 'dueSoon'})

    def test_gmail_api_used_when_sender_connected(self):
        MailSender.objects.create(pk=1, email='sender@gmail.com', refresh_token='refresh')
        calls = []

        def fake_post(url, data, headers):
            calls.append((url, headers.get('Authorization')))
            return {'access_token': 'token'} if 'oauth2' in url else {'id': 'msg'}
        with patch.object(mailer, '_post', side_effect=fake_post):
            self.assertTrue(mailer.deliver('member@example.com', 'หัวเรื่อง', 'เนื้อหา'))
        self.assertEqual(calls[0][0], mailer.TOKEN_ENDPOINT)
        self.assertEqual(calls[1], (mailer.SEND_ENDPOINT, 'Bearer token'))
        self.assertEqual(mail.outbox, [])
        with patch.object(mailer, '_post', side_effect=mailer.MailError('down')):
            self.assertFalse(mailer.deliver('member@example.com', 'x', 'y'))  # Failure is logged, not raised.

    @override_settings(REQUIRE_GMAIL=True)
    def test_unconnected_gmail_on_the_public_site_leaves_reminders_for_later(self):
        Task.objects.create(user=self.member, title='ส่งรายงาน', task_date=self.today, task_time='10:00')
        self.assertEqual(mailer.send_due_soon(at(self.today, 9)), 0)
        self.assertEqual(mailer.send_digests(at(self.today, 9)), 0)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(EmailLog.objects.exists())  # Nothing marked as sent, so it retries.
        MailSender.objects.create(pk=1, email='sender@gmail.com', refresh_token='refresh')
        with patch.object(mailer, '_post', return_value={'access_token': 't', 'id': 'm'}):
            self.assertEqual(mailer.send_due_soon(at(self.today, 9, 10)), 1)
            self.assertEqual(mailer.send_digests(at(self.today, 9, 10)), 1)

    @override_settings(ADMIN_EMAILS={'member@example.com'})
    def test_admin_emails_are_promoted_on_sign_in_and_others_are_kept_out(self):
        client = Client(enforce_csrf_checks=True)
        client.get('/login.html')
        self.member.set_password('Test-password-123')
        self.member.save()
        self.send(client, '/api/login', {'email': 'member@example.com', 'password': 'Test-password-123'})
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_staff and self.member.is_superuser)
        self.assertEqual(client.get('/admin/').status_code, 200)
        outsider = self.client_for(self.owner)
        self.assertNotEqual(outsider.get('/admin/').status_code, 200)
        self.assertEqual(outsider.get('/auth/gmail').status_code, 403)
