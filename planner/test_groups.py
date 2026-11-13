import json
from datetime import date

from django.conf import settings
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from .models import BusySlot, GroupTask, Meeting, Membership, Notification, PlanningGroup, Task, User


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class GroupPlanningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.users = [User.objects.create_user(f'group-{i}@example.com', 'Test-password-123', display_name=name)
                      for i, name in enumerate(['เจ้าของ', 'สมาชิก', 'บุคคลภายนอก'])]
        self.clients = []
        for user in self.users:
            client = Client(enforce_csrf_checks=True)
            client.force_login(user)
            client.get('/groups.html')
            self.clients.append(client)
        self.owner, self.member, self.outsider = self.clients
        self.group = PlanningGroup.objects.create(name='โปรเจกต์ทีม', owner=self.users[0], start_date=date(2026,10,15), end_date=date(2026,10,20))
        Membership.objects.create(group=self.group, user=self.users[0])
        self.base = f'/api/groups/{self.group.pk}'
        self.send(self.member, '/api/groups/join', {'code': self.group.invite_code})
        self.own_membership = self.group.members.get(user=self.users[0])
        self.membership = self.group.members.get(user=self.users[1])

    def send(self, client, url, data=None, method='post'):
        return getattr(client, method)(url, data=json.dumps(data or {}), content_type='application/json',
            HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value, HTTP_ORIGIN='http://testserver')

    def new_task(self, client=None, **changes):
        body = dict(title='ออกแบบหน้าเว็บ', notes='ส่งแบบร่าง', date='2026-10-16', time='15:00', assigneeId=self.membership.pk)
        body.update(changes)
        return self.send(client or self.owner, self.base + '/tasks', body)

    def new_meeting(self, client=None, **changes):
        body = dict(title='ประชุมทีม', date='2026-10-16', start=600, end=660, participants=[self.own_membership.pk, self.membership.pk])
        body.update(changes)
        return self.send(client or self.owner, self.base + '/meetings', body)

    def test_group_membership_code_and_list_are_private(self):
        self.assertEqual(self.group.members.count(), 2)
        result = self.owner.get('/api/groups').json()['groups'][0]
        self.assertEqual(result['memberCount'], 2)
        self.assertEqual(self.outsider.get('/api/groups').json()['groups'], [])
        self.assertEqual(self.outsider.get(self.base).status_code, 404)
        self.assertEqual(self.outsider.get(self.base + '/availability').status_code, 404)
        self.assertEqual(self.send(self.member, '/api/groups/join', {'code': self.group.invite_code.lower()}).status_code, 200)
        self.assertEqual(self.group.members.count(), 2)
        self.assertEqual(self.send(self.outsider, '/api/groups/join', {'code': 'XXXXXXXXXX'}).status_code, 404)
        self.assertNotIn('email', json.dumps(self.member.get(self.base).json()))
        self.assertEqual(Client().get('/groups.html').status_code, 302)
        self.assertEqual(Client().get('/api/groups').status_code, 401)

    def test_group_date_and_time_validation(self):
        for changes in [{'endDate': '2026-10-14'}, {'endDate': '2028-01-01'}, {'startDate': '2026-02-30'}, {'end': 540}, {'start': True}, {'end': 1450}, {'ownerId': self.users[1].pk}]:
            body = {'name': 'ทดสอบ', 'startDate': '2026-10-15', 'endDate': '2026-10-20', 'start': 540, 'end': 1260, **changes}
            self.assertEqual(self.send(self.owner, '/api/groups', body).status_code, 400, body)
        self.assertEqual(PlanningGroup.objects.count(), 1)

    def test_task_owner_and_assignee_permissions_with_personal_feed(self):
        self.assertEqual(self.new_task(self.member).status_code, 403)
        response = self.new_task()
        self.assertEqual(response.status_code, 201)
        url = self.base + '/tasks/' + str(response.json()['task']['id'])
        self.assertEqual(self.send(self.member, url, {'status': 'doing'}, 'patch').status_code, 200)
        self.assertEqual(self.send(self.member, url, {'title': 'แก้ไม่ได้'}, 'patch').status_code, 400)
        self.assertEqual(self.send(self.outsider, url, {'status': 'done'}, 'patch').status_code, 404)
        self.assertEqual(self.send(self.member, url, method='delete').status_code, 403)
        self.assertEqual(self.send(self.owner, url, {'status': 'done'}, 'patch').status_code, 200)
        feed = self.member.get('/api/group-feed?month=2026-10').json()['tasks']
        self.assertEqual(len(feed), 1)
        self.assertTrue(feed[0]['completed'])
        self.assertTrue(feed[0]['readOnly'])
        self.assertEqual(self.owner.get('/api/group-feed?month=2026-10').json()['tasks'], [])
        self.assertEqual(self.outsider.get('/api/group-feed?month=2026-10').json()['tasks'], [])
        self.assertEqual(Task.objects.count(), 0)  # No duplicate personal task to drift out of sync.
        self.assertEqual(self.send(self.owner, url, method='delete').status_code, 200)
        self.assertEqual(self.member.get('/api/group-feed?month=2026-10').json()['tasks'], [])

    def test_member_cannot_change_another_members_task(self):
        task = self.new_task(assigneeId=self.own_membership.pk).json()['task']
        self.assertEqual(self.send(self.member, self.base + f'/tasks/{task["id"]}', {'status': 'done'}, 'patch').status_code, 403)
        self.assertEqual(self.new_task(assigneeId=True).status_code, 400)
        self.assertEqual(self.new_task(assigneeId=99999).status_code, 400)
        self.assertEqual(self.new_task(date='2026-11-01').status_code, 400)
        self.assertEqual(self.new_task(status='invalid').status_code, 400)

    def test_busy_is_own_only_and_accepts_all_day(self):
        response = self.send(self.member, self.base+'/busy', {'date': '2026-10-16', 'start': 0, 'end': 1440})
        self.assertEqual(response.status_code, 201)
        url = self.base + '/busy/' + str(response.json()['id'])
        self.assertEqual(self.send(self.owner, url, method='delete').status_code, 404)
        self.assertEqual(self.send(self.member, self.base+'/busy', {'date': '2026-10-16', 'start': 600, 'end': 660}).status_code, 409)
        self.assertEqual(self.send(self.member, self.base+'/busy', {'date': '2026-10-21', 'start': 600, 'end': 660}).status_code, 400)
        self.assertEqual(self.send(self.member, self.base+'/busy', {'date': '2026-10-17', 'start': 600, 'end': 660, 'memberId': self.own_membership.pk}).status_code, 400)
        self.assertEqual(self.send(self.member, url, method='delete').status_code, 200)

    def test_unknown_members_are_not_claimed_available(self):
        result = self.owner.get(self.base+'/availability').json()
        self.assertEqual(len(result['unconfirmed']), 2)
        self.assertEqual(result['recommendations'], [])
        self.send(self.member, self.base+'/preferences', {'confirmed': True}, 'patch')
        result = self.owner.get(self.base+'/availability').json()
        self.assertEqual(result['recommendations'][0]['free'], [self.membership.pk])
        self.assertEqual(result['recommendations'][0]['count'], 1)

    def test_availability_requires_the_same_people_for_the_entire_interval(self):
        self.group.window_end = 600
        self.group.save()
        self.group.members.update(availability_confirmed=True)
        BusySlot.objects.create(member=self.own_membership, date='2026-10-16', start=540, end=570)
        BusySlot.objects.create(member=self.membership, date='2026-10-16', start=570, end=600)
        result = self.owner.get(self.base+'/availability?duration=60').json()
        day = next(d for d in result['days'] if d['date'] == '2026-10-16')
        self.assertEqual(day['best']['count'], 0)  # One free at any instant is not one free for 60 min.
        half_hour = self.owner.get(self.base+'/availability?duration=30').json()
        self.assertEqual(next(d for d in half_hour['days'] if d['date'] == '2026-10-16')['best']['count'], 1)
        self.assertEqual(self.owner.get(self.base+'/availability?duration=9999').status_code, 400)

    def test_personal_sharing_is_opt_in_and_never_exposes_titles(self):
        Task.objects.create(user=self.users[1], title='PRIVATE MEDICAL TITLE', notes='PRIVATE NOTES', task_date='2026-10-16', task_time='09:15', end_time='11:45')
        self.assertNotIn('personal', self.owner.get(self.base+'/availability').content.decode())
        self.send(self.member, self.base+'/preferences', {'sharePersonal': True, 'confirmed': True}, 'patch')
        response = self.owner.get(self.base+'/availability')
        self.assertNotIn('PRIVATE', response.content.decode())
        day = next(d for d in response.json()['days'] if d['date']=='2026-10-16')
        slots = next(b['slots'] for b in day['busy'] if b['memberId']==self.membership.pk)
        self.assertEqual(slots, [{'start': 555, 'end': 705, 'source': 'personal'}])
        self.assertEqual(day['best']['start'], 705)  # Non-half-hour boundary is respected.
        self.send(self.member, self.base+'/preferences', {'sharePersonal': False}, 'patch')
        self.assertNotIn('personal', self.owner.get(self.base+'/availability').content.decode())

    def test_personal_end_time_validation_and_legacy_duration(self):
        response = self.send(self.member, '/api/tasks', {'title': 'งานส่วนตัว', 'date': '2026-10-16', 'time': '23:45'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.send(self.member, '/api/tasks', {'title': 'ผิดเวลา', 'date': '2026-10-16', 'time': '11:00', 'endTime': '10:00'}).status_code, 400)
        self.send(self.member, self.base+'/preferences', {'sharePersonal': True}, 'patch')
        day = next(d for d in self.owner.get(self.base+'/availability').json()['days'] if d['date']=='2026-10-16')
        slots = next(b['slots'] for b in day['busy'] if b['memberId']==self.membership.pk)
        self.assertEqual((slots[0]['start'], slots[0]['end']), (1425, 1440))

    def test_meeting_conflict_boundary_participants_and_feed(self):
        BusySlot.objects.create(member=self.membership, date='2026-10-16', start=600, end=660)
        self.assertEqual(self.new_meeting().status_code, 409)
        self.assertEqual(Meeting.objects.count(), 0)
        self.assertEqual(self.new_meeting(self.member, start=660, end=720).status_code, 403)
        self.assertEqual(self.new_meeting(participants=[999999]).status_code, 400)
        self.assertEqual(self.new_meeting(participants=[True]).status_code, 400)
        self.assertEqual(self.new_meeting(start=0, end=60).status_code, 400)
        response = self.new_meeting(start=660, end=720)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.new_meeting(start=690, end=750).status_code, 409)
        self.assertEqual(len(self.member.get('/api/group-feed?month=2026-10').json()['tasks']), 1)
        self.assertEqual(self.outsider.get('/api/group-feed?month=2026-10').json()['tasks'], [])
        url=self.base+'/meetings/'+str(response.json()['meeting']['id'])
        self.assertEqual(self.send(self.member, url, method='delete').status_code, 403)
        self.assertEqual(self.send(self.owner, url, method='delete').status_code, 200)
        self.assertEqual(self.member.get('/api/group-feed?month=2026-10').json()['tasks'], [])

    def test_cross_group_meetings_block_times_without_leaking_details(self):
        other=PlanningGroup.objects.create(name='PRIVATE GROUP', owner=self.users[1], start_date='2026-10-15', end_date='2026-10-20')
        participant=Membership.objects.create(group=other,user=self.users[1])
        meeting=Meeting.objects.create(group=other,title='PRIVATE MEETING',date='2026-10-16',start=600,end=660)
        meeting.participants.add(participant)
        self.assertEqual(self.new_meeting().status_code, 409)
        response=self.owner.get(self.base+'/availability')
        self.assertNotIn('PRIVATE',response.content.decode())
        self.assertIn('meeting',response.content.decode())

    def test_cross_group_assignees_and_participants_are_rejected(self):
        other=PlanningGroup.objects.create(name='อื่น',owner=self.users[2],start_date='2026-10-15',end_date='2026-10-20')
        outsider=Membership.objects.create(group=other,user=self.users[2])
        self.assertEqual(self.new_task(assigneeId=outsider.pk).status_code,400)
        self.assertEqual(self.new_meeting(participants=[outsider.pk]).status_code,400)

    def test_notifications_are_scoped_and_read_state_persists(self):
        self.new_task()
        self.new_meeting()
        result=self.member.get('/api/notifications').json()
        self.assertEqual(result['unread'],2)
        self.assertEqual(self.outsider.get('/api/notifications').json()['notifications'],[])
        self.assertEqual(self.send(self.member,'/api/notifications',{},'patch').status_code,200)
        fresh=Client(); fresh.cookies=self.member.cookies.copy()
        self.assertEqual(fresh.get('/api/notifications').json()['unread'],0)
        self.assertEqual(self.send(self.member,self.base+'/remind').status_code,403)
        self.assertEqual(self.send(self.owner,self.base+'/remind').status_code,200)
        self.assertEqual(self.send(self.owner,self.base+'/remind').status_code,429)
        self.assertEqual(self.member.get('/api/notifications').json()['unread'],1)

    def test_group_delete_cascades_only_group_records(self):
        self.new_task(); self.new_meeting()
        Task.objects.create(user=self.users[0], title='Keep personal', task_date='2026-10-16')
        self.assertEqual(self.send(self.member,self.base,method='delete').status_code,403)
        self.assertEqual(self.send(self.owner,self.base,method='delete').status_code,200)
        for model in [PlanningGroup,Membership,GroupTask,Meeting,Notification]:
            self.assertEqual(model.objects.count(),0)
        self.assertEqual(Task.objects.count(),1)
        self.assertEqual(User.objects.count(),3)

    def test_csrf_and_untrusted_identifiers(self):
        for url,method in [('/api/groups','post'),('/api/groups/join','post'),(self.base,'delete'),
                           (self.base+'/preferences','patch'),(self.base+'/busy','post'),(self.base+'/tasks','post'),
                           (self.base+'/meetings','post'),(self.base+'/remind','post'),('/api/notifications','patch')]:
            response=getattr(self.owner,method)(url,data='{}',content_type='application/json')
            self.assertEqual(response.status_code,403,url)
        self.assertEqual(self.owner.get('/api/groups/9999999999999999999999999').status_code,404)
        self.assertEqual(self.send(self.owner,self.base+'/busy/9999999999999999999999999',method='delete').status_code,404)
        self.assertEqual(self.owner.get('/data/goodplanner-django.sqlite3').status_code,404)
        for path in ['/groups.html','/groups.js','/groups.css']:
            self.assertEqual(self.owner.get(path).status_code,200)
