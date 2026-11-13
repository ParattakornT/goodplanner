from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from .group_services import availability
from .models import PlanningGroup, User


class SeedDemoTests(TestCase):
    def seed(self, *args):
        call_command('seed_demo', *args, stdout=StringIO())

    def result(self, fragment):
        group = PlanningGroup.objects.get(name__contains=fragment)
        return group, availability(group, list(group.members.all()), group.duration_minutes)

    def test_every_state_appears(self):
        self.seed()
        _, srs = self.result('SRS')
        statuses = {day['status'] for day in srs['days']}
        self.assertTrue({'all-free', 'partial', 'none'} <= statuses, statuses)
        self.assertEqual(srs['summary']['reason'], 'full')

        _, rehearse = self.result('ซ้อม')
        self.assertIn('maybe', {day['status'] for day in rehearse['days']})
        self.assertEqual(rehearse['summary']['confirmedCount'], 3)
        unconfirmed_with_slot = User.objects.get(email__startswith='phuwit')
        busy_day = rehearse['days'][2]['busy']
        self.assertTrue(any(row['slots'] for row in busy_day))  # the slot entered before confirming still shows

        group, hard = self.result('นัดยาก')
        self.assertEqual(hard['summary']['reason'], 'partial')
        blocker = group.members.get(pk=hard['summary']['blockers'][0]['memberId'])
        self.assertEqual(blocker.user.display_name, 'ภูริวัฒน์')
        self.assertTrue(unconfirmed_with_slot.is_active)

    def test_rerun_replaces_instead_of_duplicating(self):
        self.seed()
        self.seed()
        self.assertEqual(PlanningGroup.objects.filter(name__startswith='ตัวอย่าง').count(), 3)
        self.assertEqual(User.objects.filter(email__endswith='@demo.goodplanner.test').count(), 5)

    def test_owner_account_is_kept_on_remove(self):
        real = User.objects.create_user('real@example.com', 'Test-password-123', display_name='ของจริง')
        self.seed('--owner', 'real@example.com')
        self.assertEqual(PlanningGroup.objects.filter(owner=real).count(), 3)
        self.seed('--remove')
        self.assertTrue(User.objects.filter(pk=real.pk).exists())
        self.assertFalse(real.tasks.exists())
        self.assertFalse(PlanningGroup.objects.filter(name__startswith='ตัวอย่าง').exists())
