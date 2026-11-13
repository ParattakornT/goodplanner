"""Sample groups that show every availability state, for demos and screenshots.

Run again any time: it removes the previous sample data first, then rebuilds it
with dates starting tomorrow, so the demo never shows a schedule in the past.
Real accounts are never deleted. Only rows this command created are removed.
"""
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from planner.models import BusySlot, GroupTask, Membership, Notification, PlanningGroup, Task, User

DEMO_DOMAIN = '@demo.goodplanner.test'
DEMO_PASSWORD = 'GoodPlanner123'
GROUP_PREFIX = 'ตัวอย่าง · '
TASK_MARK = 'ข้อมูลตัวอย่าง (seed_demo)'
TEAM = [  # index 0 is the group owner
    ('lead', 'ปรัตถกร'),
    ('bunyapon', 'บัญญพนต์'),
    ('napat', 'ณภัทร'),
    ('phuwit', 'ภูวิศ'),
    ('phuriwat', 'ภูริวัฒน์'),
]
ALL_DAY = (0, 1440)


def h(hour, minute=0):
    return hour * 60 + minute


class Command(BaseCommand):
    help = 'Create sample groups showing certain, unsure, busy and no-common-day cases.'

    def add_arguments(self, parser):
        parser.add_argument('--owner', help='Existing account email to use as the group owner.')
        parser.add_argument('--remove', action='store_true', help='Remove the sample data and stop.')

    @transaction.atomic
    def handle(self, *args, **options):
        removed = self.remove()
        if options['remove']:
            self.stdout.write(f'Removed sample data: {removed}')
            return
        team = self.team(options.get('owner'))
        today = timezone.localdate()
        closed = timezone.make_aware(datetime.combine(today - timedelta(days=1), time(18)))
        open_until = timezone.make_aware(datetime.combine(today + timedelta(days=3), time(18)))

        # 1) Everyone confirmed: blue, orange and red days side by side.
        srs = self.group(team, 'นัดทำเอกสาร SRS', today + timedelta(days=1), 14, 60, closed, confirmed=range(5))
        self.busy(srs, team, {
            1: [(1, h(9), h(12)), (2, h(13), h(16)), (3, h(9), h(10, 30))],
            2: [(0, h(9), h(15)), (4, h(15), h(21))],
            3: [(2, h(10), h(12)), (3, h(13), h(15))],
            4: [(i, *ALL_DAY) for i in range(5)],
            5: [(1, h(9), h(21))],
            7: [(0, h(9), h(11)), (1, h(9), h(11)), (4, h(11), h(13)), (2, h(13), h(17)), (3, h(17), h(21))],
            8: [(3, h(9), h(12))],
            9: [(2, *ALL_DAY)],
            11: [(4, h(18), h(21))],
            12: [(0, h(9), h(21)), (1, h(9), h(21)), (2, h(9), h(21))],
        })
        board = [(0, 'สรุปบทที่ 1 บทนำ', -1, 'done'), (1, 'วาด Use Case Diagram', 2, 'doing'),
                 (2, 'เขียน Data Dictionary', 4, 'todo'), (3, 'ทำ Dialog Map', -1, 'doing'),
                 (4, 'จัดลำดับ Quality Attributes', 6, 'todo')]
        for index, title, days, status in board:
            GroupTask.objects.create(group=srs, assignee=self.member(srs, team[index]), title=title,
                                     due_date=today + timedelta(days=days), due_time='23:59', status=status)

        # 2) Still collecting: two members have not confirmed, so days turn yellow.
        #    ภูวิศ added one busy day but never pressed confirm: it must still count.
        rehearse = self.group(team, 'ซ้อมพรีเซนต์ (ยังรับเวลาอยู่)', today + timedelta(days=4), 7, 120, open_until,
                              confirmed=[0, 1, 2])
        self.busy(rehearse, team, {
            0: [(0, h(9), h(12))],
            1: [(1, h(13), h(17))],
            2: [(3, h(9), h(21))],
            3: [(2, *ALL_DAY)],
        })

        # 3) No day where everyone is free: one member blocks every slot.
        hard = self.group(team, 'นัดยาก (ไม่มีวันว่างตรงกัน)', today + timedelta(days=1), 5, 120, closed,
                          confirmed=[0, 1, 2, 4], members=[0, 1, 2, 4])
        plan = {day: [(4, h(9), h(21))] for day in range(5)}
        plan[0].append((1, h(9), h(10)))
        plan[2].append((2, h(18), h(21)))
        self.busy(hard, team, plan)

        owner = team[0]
        for days, at, end, title, priority, done in [
            (0, '09:00', '10:30', 'อ่านทวน SRS ก่อนส่ง', 'high', False),
            (1, '13:00', '15:00', 'ประชุมกลุ่มย่อย frontend', 'normal', False),
            (2, '19:00', '20:00', 'ออกกำลังกาย', 'low', False),
            (-1, '10:00', '11:00', 'ส่งการบ้าน Database', 'high', False),
            (-2, '14:00', '16:00', 'แก้สไลด์พรีเซนต์', 'normal', True),
        ]:
            Task.objects.create(user=owner, title=title, notes=TASK_MARK, task_date=today + timedelta(days=days),
                                task_time=at, end_time=end, priority=priority, completed=done)
        Notification.objects.create(user=owner, group=rehearse,
                                    message='ภูวิศ และ ภูริวัฒน์ ยังไม่ยืนยันเวลาว่างสำหรับ ซ้อมพรีเซนต์')
        Notification.objects.create(user=owner, group=srs, message='ทำ Dialog Map เลยกำหนดส่งแล้ว')

        self.stdout.write(self.style.SUCCESS('Sample data ready.'))
        self.stdout.write(f'  Owner account : {owner.email}')
        self.stdout.write(f'  Team accounts : {", ".join(u.email for u in team[1:])}')
        self.stdout.write(f'  Team password : {DEMO_PASSWORD}')
        self.stdout.write('  Groups        : ' + ', '.join(g.name for g in (srs, rehearse, hard)))

    def remove(self):
        groups = PlanningGroup.objects.filter(name__startswith=GROUP_PREFIX)
        counts = {'groups': groups.count(),
                  'tasks': Task.objects.filter(notes=TASK_MARK).count(),
                  'accounts': User.objects.filter(email__endswith=DEMO_DOMAIN).count()}
        groups.delete()
        Task.objects.filter(notes=TASK_MARK).delete()
        User.objects.filter(email__endswith=DEMO_DOMAIN).delete()
        return counts

    def team(self, owner_email):
        team = []
        for index, (handle, name) in enumerate(TEAM):
            if index == 0 and owner_email:
                owner = User.objects.filter(email=owner_email.strip().lower()).first()
                if owner is None:
                    raise CommandError(f'No account with email {owner_email}. Register it first.')
                team.append(owner)
                continue
            team.append(User.objects.create_user(f'{handle}{DEMO_DOMAIN}', DEMO_PASSWORD, display_name=name))
        return team

    def group(self, team, name, start, days, duration, deadline, confirmed, members=range(5)):
        group = PlanningGroup.objects.create(name=GROUP_PREFIX + name, owner=team[0], start_date=start,
                                             end_date=start + timedelta(days=days - 1), duration_minutes=duration,
                                             availability_deadline=deadline)
        for index in members:
            Membership.objects.create(group=group, user=team[index], availability_confirmed=index in confirmed)
        return group

    def member(self, group, user):
        return Membership.objects.get(group=group, user=user)

    def busy(self, group, team, plan):
        for offset, slots in plan.items():
            for index, start, end in slots:
                BusySlot.objects.create(member=self.member(group, team[index]),
                                        date=group.start_date + timedelta(days=offset), start=start, end=end)
