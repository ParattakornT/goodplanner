import json
from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import BusySlot, Meeting, Membership, PlanningGroup, Task, User


@override_settings(ALLOWED_HOSTS=['testserver'])
class SchedulingRoundTests(TestCase):
    def setUp(self):
        cache.clear()
        self.users = [User.objects.create_user(f'round{i}@example.com', 'Test-password-123', display_name=name)
                      for i, name in enumerate(['หัวหน้า', 'สมาชิก', 'มาช้า'])]
        self.clients = []
        for user in self.users:
            client = Client(enforce_csrf_checks=True)
            client.force_login(user)
            client.get('/groups.html')
            self.clients.append(client)
        self.owner, self.member, self.late = self.clients
        self.start = timezone.localdate() + timedelta(days=3)
        self.deadline = timezone.make_aware(datetime.combine(self.start - timedelta(days=1), time(18)))
        self.body = dict(name='นัดทำงาน 3 ชั่วโมง', startDate=self.start.isoformat(),
                         endDate=(self.start + timedelta(days=6)).isoformat(), start=540, end=1260,
                         durationMinutes=180, availabilityDeadline=self.deadline.isoformat())
        response = self.send(self.owner, '/api/groups', self.body)
        self.assertEqual(response.status_code, 201, response.content)
        self.group = PlanningGroup.objects.get(pk=response.json()['group']['id'])
        self.base = f'/api/groups/{self.group.pk}'
        self.send(self.member, '/api/groups/join', {'code': self.group.invite_code})
        self.members = list(self.group.members.order_by('pk'))
        self.meeting = dict(title='ทำงานด้วยกัน', date=self.start.isoformat(), start=600, end=780,
                            participants=[m.pk for m in self.members])

    def send(self, client, url, body=None, method='post'):
        return getattr(client, method)(url, data=json.dumps(body or {}), content_type='application/json',
            HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value, HTTP_ORIGIN='http://testserver')

    def test_creation_requires_valid_deadline_and_duration(self):
        for changes in [dict(durationMinutes=0), dict(durationMinutes=True), dict(durationMinutes=181),
                        dict(durationMinutes=735), dict(end=660), dict(availabilityDeadline='invalid'),
                        dict(availabilityDeadline='2026-02-30T12:00:00+07:00'),
                        dict(availabilityDeadline=self.deadline.replace(tzinfo=None).isoformat()),
                        dict(availabilityDeadline=timezone.now().isoformat()),
                        dict(availabilityDeadline=self.start.isoformat()+'T00:00:00+07:00')]:
            response = self.send(self.owner, '/api/groups', {**self.body, **changes})
            self.assertEqual(response.status_code, 400, response.content)
        missing = {k: v for k, v in self.body.items() if k != 'availabilityDeadline'}
        self.assertEqual(self.send(self.owner, '/api/groups', missing).status_code, 400)
        self.group.refresh_from_db()
        self.assertEqual(self.group.duration_minutes, 180)
        self.assertEqual(self.group.availability_deadline, self.deadline)

    def test_cutoff_locks_every_availability_write_and_new_join_at_exact_instant(self):
        body = dict(date=self.start.isoformat(), start=600, end=660)
        response = self.send(self.member, self.base+'/busy', body)
        self.assertEqual(response.status_code, 201)
        slot_id = response.json()['id']
        self.assertEqual(self.send(self.owner, self.base+'/meetings', self.meeting).status_code, 409)
        with patch('django.utils.timezone.now', return_value=self.deadline - timedelta(microseconds=1)):
            self.assertFalse(self.owner.get(self.base).json()['group']['availabilityClosed'])
            self.assertEqual(self.send(self.member, self.base+'/preferences', {'confirmed': True}, 'patch').status_code, 200)
        with patch('django.utils.timezone.now', return_value=self.deadline):
            self.assertTrue(self.owner.get(self.base).json()['group']['availabilityClosed'])
            self.assertEqual(self.send(self.member, self.base+'/busy', {**body, 'start': 700, 'end': 750}).status_code, 409)
            self.assertEqual(self.send(self.member, self.base+f'/busy/{slot_id}', method='delete').status_code, 409)
            for change in [{'confirmed': False}, {'sharePersonal': True}]:
                self.assertEqual(self.send(self.member, self.base+'/preferences', change, 'patch').status_code, 409)
            self.assertEqual(self.send(self.late, '/api/groups/join', {'code': self.group.invite_code}).status_code, 409)
            self.assertEqual(self.send(self.member, '/api/groups/join', {'code': self.group.invite_code}).status_code, 200)
            self.assertEqual(self.send(self.owner, self.base+'/remind').status_code, 409)
            self.assertEqual(self.owner.get(self.base+'/availability').status_code, 200)
        self.assertEqual(BusySlot.objects.count(), 1)
        self.assertEqual(self.group.members.count(), 2)

    def test_new_group_without_daily_window_allows_evening_meeting_to_midnight(self):
        body = {k: v for k, v in self.body.items() if k not in ('start', 'end')}
        response = self.send(self.owner, '/api/groups', body)
        self.assertEqual(response.status_code, 201, response.content)
        group = PlanningGroup.objects.get(pk=response.json()['group']['id'])
        self.assertEqual((group.window_start, group.window_end), (0, 1440))
        member = group.members.get(user=self.users[0])
        member.availability_confirmed = True
        member.save()
        with patch('django.utils.timezone.now', return_value=self.deadline):
            meeting = self.send(self.owner, f'/api/groups/{group.pk}/meetings', {
                **self.meeting, 'start': 1260, 'end': 1440, 'participants': [member.pk]})
            self.assertEqual(meeting.status_code, 201, meeting.content)
            self.assertEqual(meeting.json()['meeting']['end'], 1440)
        self.assertEqual(self.send(self.owner, '/api/groups', {**body, 'start': 540}).status_code, 400)

    def test_unconfirmed_member_is_unsure_not_missing(self):
        """A slot added before pressing confirm must still shape the result."""
        confirmed = self.members[0]
        confirmed.availability_confirmed = True
        confirmed.save()
        BusySlot.objects.create(member=self.members[1], date=self.start, start=540, end=1260)
        result = self.owner.get(self.base + '/availability').json()
        day = next(d for d in result['days'] if d['date'] == self.start.isoformat())
        self.assertEqual(day['status'], 'maybe')
        self.assertEqual(day['best']['free'], [confirmed.pk])
        self.assertEqual(day['best']['unsure'], [self.members[1].pk])
        self.assertEqual(result['summary']['reason'], 'partial')
        self.assertEqual(result['summary']['confirmedCount'], 1)

    def test_no_common_slot_reports_the_blockers(self):
        """Nobody free anywhere returns a reason and who blocks the most."""
        self.group.members.update(availability_confirmed=True)
        day = self.group.start_date
        while day <= self.group.end_date:
            for member in self.members:
                BusySlot.objects.create(member=member, date=day, start=0, end=1440)
            day += timedelta(days=1)
        result = self.owner.get(self.base + '/availability').json()
        self.assertEqual(result['recommendations'], [])
        self.assertEqual(result['summary']['reason'], 'conflict')
        self.assertEqual(result['summary']['bestCount'], 0)
        self.assertTrue(result['summary']['blockers'])
        self.assertEqual({b['memberId'] for b in result['summary']['blockers']},
                         {m.pk for m in self.members})
        self.assertTrue(all(d['status'] == 'none' for d in result['days']))

    def test_everyone_free_is_reported_as_certain(self):
        self.group.members.update(availability_confirmed=True)
        result = self.owner.get(self.base + '/availability').json()
        day = next(d for d in result['days'] if d['date'] == self.start.isoformat())
        self.assertEqual(day['status'], 'all-free')
        self.assertEqual(day['best']['unsureCount'], 0)
        self.assertEqual(result['summary']['reason'], 'full')

    def test_three_hour_search_and_meeting_duration_are_fixed(self):
        self.group.members.update(availability_confirmed=True)
        result = self.owner.get(self.base+'/availability').json()
        self.assertEqual(result['duration'], 180)
        self.assertEqual(result['days'][0]['best']['end'] - result['days'][0]['best']['start'], 180)
        self.assertEqual(self.owner.get(self.base+'/availability?duration=60').status_code, 400)
        with patch('django.utils.timezone.now', return_value=self.deadline):
            self.assertEqual(self.send(self.owner, self.base+'/meetings', {**self.meeting, 'end': 660}).status_code, 400)
            self.assertEqual(self.send(self.owner, self.base+'/meetings', self.meeting).status_code, 201)

    def test_conflict_requires_bound_acknowledgement_and_is_saved(self):
        self.group.members.update(availability_confirmed=True)
        BusySlot.objects.create(member=self.members[1], date=self.start, start=600, end=660)
        with patch('django.utils.timezone.now', return_value=self.deadline):
            warning = self.send(self.owner, self.base+'/meetings', self.meeting)
            self.assertEqual(warning.status_code, 409)
            self.assertEqual(Meeting.objects.count(), 0)
            data = warning.json()
            self.assertEqual(data['conflicts'][0]['name'], 'สมาชิก')
            self.assertEqual(data['conflicts'][0]['slots'], [{'start': 600, 'end': 660}])
            accepted = {**self.meeting, 'confirmationToken': data['confirmationToken']}
            self.assertEqual(self.send(self.member, self.base+'/meetings', accepted).status_code, 403)
            self.assertEqual(self.send(self.owner, self.base+'/meetings', {**accepted, 'confirmationToken': 'forged'}).status_code, 409)
            self.assertEqual(self.send(self.owner, self.base+'/meetings', {**accepted, 'start': 615, 'end': 795}).status_code, 409)
            # Another member's new conflicting meeting invalidates the old acknowledgement.
            other = PlanningGroup.objects.create(name='Other', owner=self.users[0], start_date=self.start, end_date=self.start)
            participant = Membership.objects.create(group=other, user=self.users[0])
            conflict = Meeting.objects.create(group=other, title='PRIVATE TITLE', date=self.start, start=660, end=720)
            conflict.participants.add(participant)
            refreshed = self.send(self.owner, self.base+'/meetings', accepted)
            self.assertEqual(refreshed.status_code, 409)
            self.assertEqual(len(refreshed.json()['conflicts']), 2)
            self.assertNotIn('PRIVATE TITLE', refreshed.content.decode())
            accepted['confirmationToken'] = refreshed.json()['confirmationToken']
            saved = self.send(self.owner, self.base+'/meetings', accepted)
            self.assertEqual(saved.status_code, 201, saved.content)
            self.assertEqual(len(saved.json()['meeting']['acknowledgement']['conflicts']), 2)
            self.assertEqual(self.member.get('/api/group-feed?month='+self.start.strftime('%Y-%m')).json()['tasks'][0]['kind'], 'นัดหมายกลุ่ม')

    def test_unknown_member_needs_warning_and_adjacent_times_do_not_conflict(self):
        BusySlot.objects.create(member=self.members[1], date=self.start, start=540, end=600)
        with patch('django.utils.timezone.now', return_value=self.deadline):
            result = self.send(self.owner, self.base+'/meetings', self.meeting)
            self.assertEqual(result.status_code, 409)
            self.assertEqual(result.json()['conflicts'], [])
            self.assertEqual(len(result.json()['unconfirmed']), 2)
            self.assertEqual(self.send(self.owner, self.base+'/meetings', {
                **self.meeting, 'confirmationToken': result.json()['confirmationToken']}).status_code, 201)

    def test_imported_personal_times_do_not_drift_after_cutoff(self):
        task = Task.objects.create(user=self.users[1], title='PRIVATE', task_date=self.start, task_time='10:00', end_time='11:00')
        self.assertEqual(self.send(self.member, self.base+'/preferences', {'sharePersonal': True, 'confirmed': True}, 'patch').status_code, 200)
        with patch('django.utils.timezone.now', return_value=self.deadline):
            task.task_time='15:00'; task.end_time='16:00'; task.save()
            response = self.owner.get(self.base+'/availability')
            self.assertNotIn('PRIVATE', response.content.decode())
            slots = response.json()['days'][0]['busy'][1]['slots']
            self.assertEqual(slots, [{'start': 600, 'end': 660, 'source': 'personal'}])
