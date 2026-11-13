import io
import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from .models import LegacyImport, Task, User

# Independently generated with the original Node crypto.scryptSync implementation.
LEGACY_HASH = ('scrypt$32768$8$3$00112233445566778899aabbccddeeff$'
               '45f0285596dae6e3740eb8744bfcf739f2e0e912085e3bba27c541f98c7c3fc2419'
               '5b4f1ca5e3404e0d00e98cb0767280363076ef7eb6a549cfd47528d96f39b')
PASSWORD = 'Planner-test-123!'


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'], DEBUG=False)
class ApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.client.get('/login.html')

    def send(self, path, data=None, method='post', client=None):
        client = client or self.client
        return getattr(client, method)(path, data=json.dumps(data or {}), content_type='application/json',
                                      HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value,
                                      HTTP_ORIGIN='http://testserver')

    def register(self, email='test@example.com'):
        return self.send('/api/register', {'displayName': 'ทดสอบ', 'email': email, 'password': PASSWORD, 'confirmPassword': PASSWORD})

    def login(self, email='test@example.com'):
        return self.send('/api/login', {'email': email, 'password': PASSWORD})

    def signed_in(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.login().status_code, 200)

    def test_registration_hash_login_cookie_and_logout(self):
        self.assertEqual(self.register(' Test@EXAMPLE.com ').status_code, 201)
        user = User.objects.get()
        self.assertEqual(user.email, 'test@example.com')
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(self.client.get('/api/me').status_code, 401)
        login = self.login('TEST@example.com')
        self.assertEqual(login.status_code, 200)
        self.assertEqual(set(login.json()['user']), {'id', 'displayName', 'email', 'emailReminders', 'isAdmin'})
        cookie = login.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(self.client.get('/dashboard.html').status_code, 200)
        resumed = Client()
        resumed.cookies = self.client.cookies.copy()
        self.assertEqual(resumed.get('/api/me').status_code, 200)
        self.assertEqual(self.send('/api/logout').status_code, 200)
        self.assertEqual(self.client.get('/api/me').status_code, 401)
        self.assertEqual(resumed.get('/api/me').status_code, 401)

    def test_duplicate_email_and_wrong_password(self):
        self.register()
        self.assertEqual(self.register('TEST@EXAMPLE.COM').status_code, 409)
        wrong = self.send('/api/login', {'email': 'test@example.com', 'password': 'wrong-pass'})
        missing = self.send('/api/login', {'email': 'missing@example.com', 'password': 'wrong-pass'})
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.json(), missing.json())

    def test_invalid_registration(self):
        payload = {'displayName': 'test', 'email': 'test@example.com', 'password': PASSWORD, 'confirmPassword': PASSWORD}
        for patch in [{'email': 'broken'}, {'password': 'short'}, {'displayName': ''}, {'confirmPassword': 'mismatch'}, {'password': 10}]:
            with self.subTest(patch=patch):
                self.assertEqual(self.send('/api/register', payload | patch).status_code, 400)
        self.assertFalse(User.objects.exists())

    def test_csrf_missing_wrong_origin_and_valid_request(self):
        self.assertEqual(self.client.post('/api/register', '{}', content_type='application/json').status_code, 403)
        token = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        response = self.client.post('/api/login', '{}', content_type='application/json',
                                    HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='https://foreign.example')
        self.assertEqual(response.status_code, 403)
        self.assertIn('message', response.json())
        self.signed_in()
        task = self.send('/api/tasks', {'title': 'งาน', 'date': '2026-10-13'}).json()['task']
        for method in ['patch', 'delete']:
            response = getattr(self.client, method)(f"/api/tasks/{task['id']}", '{}', content_type='application/json')
            self.assertEqual(response.status_code, 403)

    def test_json_errors_and_body_limit(self):
        headers = {'HTTP_X_CSRFTOKEN': self.client.cookies[settings.CSRF_COOKIE_NAME].value}
        for raw in ['[1,2]', 'null', 'broken']:
            self.assertEqual(self.client.post('/api/login', raw, content_type='application/json', **headers).status_code, 400)
        self.assertEqual(self.client.post('/api/login', '{}', content_type='text/plain', **headers).status_code, 415)
        self.assertEqual(self.client.post('/api/login', 'x' * 17000, content_type='application/json', **headers).status_code, 413)

    def test_authentication_required_and_private_files_hidden(self):
        for path in ['/api/me', '/api/tasks?month=2026-10']:
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertRedirects(self.client.get('/dashboard.html'), '/login.html')
        for path in ['/data/goodplanner.sqlite', '/data/goodplanner-django.sqlite3', '/goodplanner/settings.py', '/requirements.txt', '/server.js']:
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get('/api/register').status_code, 405)
        for path in ['/login.css', '/login.js', '/planner.css', '/workspace.css', '/dashboard.css', '/dashboard.js', '/groups.css', '/groups.js']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_auth_rate_limit(self):
        for _ in range(30):
            self.assertEqual(self.send('/api/login', {'email': 'invalid'}).status_code, 400)
        self.assertEqual(self.send('/api/login', {'email': 'invalid'}).status_code, 429)

    @override_settings(GOOGLE_CLIENT_ID='client-id', GOOGLE_CLIENT_SECRET='client-secret')
    def test_google_login_uses_state_and_pkce(self):
        response = self.client.get('/auth/google')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('https://accounts.google.com/o/oauth2/v2/auth?'))
        self.assertIn('code_challenge_method=S256', response['Location'])
        self.assertIn('response_type=code', response['Location'])
        self.assertTrue(self.client.session['google_oauth_state'])
        self.assertTrue(self.client.session['google_oauth_verifier'])

    @override_settings(GOOGLE_CLIENT_ID='', GOOGLE_CLIENT_SECRET='')
    def test_google_login_requires_oauth_configuration(self):
        response = self.client.get('/auth/google')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/login.html?google_error=configuration')

    @override_settings(GOOGLE_CLIENT_ID='client-id', GOOGLE_CLIENT_SECRET='client-secret')
    def test_google_callback_rejects_invalid_state(self):
        self.client.get('/auth/google')
        response = self.client.get('/auth/google/callback?state=incorrect&code=authorization-code')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/login.html?google_error=invalid')
        self.assertFalse(User.objects.exists())

    @override_settings(GOOGLE_CLIENT_ID='client-id', GOOGLE_CLIENT_SECRET='client-secret')
    @patch('planner.views.google_profile', return_value=('GOOGLE@example.com', 'Google User'))
    @patch('planner.views.google_token', return_value='access-token')
    def test_google_callback_creates_user_and_starts_session(self, token, profile):
        self.client.get('/auth/google')
        state = self.client.session['google_oauth_state']
        verifier = self.client.session['google_oauth_verifier']
        response = self.client.get(f'/auth/google/callback?state={state}&code=authorization-code')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/dashboard.html')
        token.assert_called_once_with('authorization-code', verifier, 'http://testserver/auth/google/callback')
        profile.assert_called_once_with('access-token')
        user = User.objects.get()
        self.assertEqual(user.email, 'google@example.com')
        self.assertEqual(user.display_name, 'Google User')
        self.assertFalse(user.has_usable_password())
        self.assertEqual(self.client.get('/api/me').json()['user']['email'], 'google@example.com')
        self.assertEqual(response.cookies[settings.SESSION_COOKIE_NAME]['samesite'], 'Lax')

    @override_settings(GOOGLE_CLIENT_ID='client-id', GOOGLE_CLIENT_SECRET='client-secret')
    @patch('planner.views.google_request', return_value={
        'sub': 'google-subject', 'email': 'unverified@example.com', 'email_verified': False,
    })
    @patch('planner.views.google_token', return_value='access-token')
    def test_google_callback_rejects_unverified_email(self, token, userinfo):
        self.client.get('/auth/google')
        state = self.client.session['google_oauth_state']
        response = self.client.get(f'/auth/google/callback?state={state}&code=authorization-code')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/login.html?google_error=provider')
        self.assertFalse(User.objects.exists())

    def test_task_crud_month_filter_and_no_cross_account_access(self):
        self.signed_in()
        task = self.send('/api/tasks', {'title': ' อ่านหนังสือ ', 'date': '2026-10-13', 'time': '09:30', 'notes': 'บทที่ 1', 'priority': 'high'})
        self.assertEqual(task.status_code, 201)
        task_id = task.json()['task']['id']
        self.assertEqual(task.json()['task']['title'], 'อ่านหนังสือ')
        path = f'/api/tasks/{task_id}'
        self.assertEqual(len(self.client.get('/api/tasks?month=2026-10').json()['tasks']), 1)
        self.assertEqual(self.client.get('/api/tasks?month=2026-11').json()['tasks'], [])
        self.assertEqual(self.send(path, {'completed': True, 'date': '2026-11-01'}, method='patch').status_code, 200)
        self.assertEqual(self.client.get('/api/tasks?month=2026-10').json()['tasks'], [])
        fresh = Client()
        fresh.cookies = self.client.cookies.copy()
        saved = fresh.get('/api/tasks?month=2026-11').json()['tasks'][0]
        self.assertTrue(saved['completed'])
        self.assertEqual(saved['notes'], 'บทที่ 1')
        other = User.objects.create_user(email='other@example.com', password=PASSWORD, display_name='other')
        stranger = Client(enforce_csrf_checks=True)
        stranger.get('/login.html')
        stranger.force_login(other)
        self.assertEqual(stranger.get('/api/tasks?month=2026-11').json()['tasks'], [])
        self.assertEqual(self.send(path, {'title': 'hijack'}, method='patch', client=stranger).status_code, 404)
        self.assertEqual(self.send(path, method='delete', client=stranger).status_code, 404)
        self.assertEqual(self.send(path, method='delete').status_code, 200)
        self.assertFalse(Task.objects.exists())

    def test_task_validation_and_calendar_boundaries(self):
        self.signed_in()
        for patch in [{'date': '2026-02-29'}, {'date': '2101-01-01'}, {'date': '1899-12-31'}, {'title': ' '},
                      {'time': '24:00'}, {'priority': 'urgent'}, {'completed': 1}, {'notes': 'x' * 2001}, {'user_id': 2}]:
            with self.subTest(patch=patch):
                self.assertEqual(self.send('/api/tasks', {'title': 'งาน', 'date': '2026-10-13'} | patch).status_code, 400)
        for valid in ['1900-01-01', '2028-02-29', '2100-12-31']:
            self.assertEqual(self.send('/api/tasks', {'title': 'งาน', 'date': valid}).status_code, 201)
        for invalid in ['2026-13', '2026-1', '2101-01']:
            self.assertEqual(self.client.get('/api/tasks', {'month': invalid}).status_code, 400)
        task = Task.objects.first()
        self.assertEqual(self.send(f'/api/tasks/{task.pk}', {}, method='patch').status_code, 400)
        self.assertEqual(self.send('/api/tasks/9999999999999999999999', method='delete').status_code, 404)

    def test_legacy_password_login_upgrades_hash(self):
        user = User.objects.create(email='legacy@example.com', display_name='เดิม', password='legacy_' + LEGACY_HASH)
        wrong = self.send('/api/login', {'email': user.email, 'password': 'wrong-pass'})
        self.assertEqual(wrong.status_code, 401)
        response = self.send('/api/login', {'email': user.email, 'password': 'LegacyPass-123!'})
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.password.startswith('pbkdf2_sha256$'))
        self.assertTrue(user.check_password('LegacyPass-123!'))


class LegacyImportTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'legacy.sqlite'
        self.backups = Path(self.temp.name) / 'backups'
        with closing(sqlite3.connect(self.source)) as db, db:
            db.executescript('''
                CREATE TABLE users (id INTEGER PRIMARY KEY, display_name TEXT, email TEXT, password_hash TEXT, created_at TEXT);
                CREATE TABLE tasks (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, notes TEXT, task_date TEXT,
                                    task_time TEXT, priority TEXT, completed INTEGER, created_at TEXT, updated_at TEXT);
            ''')
            db.execute('INSERT INTO users VALUES (?, ?, ?, ?, ?)', (7, 'บัญชีเดิม', 'old@example.com', LEGACY_HASH, '2026-10-01 08:00:00'))
            db.execute('INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (9, 7, 'งานเดิม', 'รายละเอียด', '2026-10-13', '09:00', 'high', 1, '2026-10-01 08:00:00', '2026-10-02 08:00:00'))

    def run_import(self):
        call_command('import_legacy', source=self.source, backup_dir=self.backups, stdout=io.StringIO())

    def test_backup_import_preserves_data_ids_and_can_run_again(self):
        original_bytes = self.source.read_bytes()
        self.run_import()
        self.assertEqual(self.source.read_bytes(), original_bytes)
        self.assertEqual(len(list(self.backups.glob('*.sqlite'))), 1)
        user, task = User.objects.get(), Task.objects.get()
        self.assertEqual((user.pk, task.pk, task.user_id), (7, 9, 7))
        self.assertTrue(user.check_password('LegacyPass-123!'))
        self.assertEqual(task.notes, 'รายละเอียด')
        self.assertTrue(task.completed)
        self.assertEqual(task.updated_at.isoformat(), '2026-10-02T08:00:00+00:00')
        task.title = 'แก้ไขหลังย้าย'
        task.save()
        self.run_import()
        task.refresh_from_db()
        self.assertEqual(task.title, 'แก้ไขหลังย้าย')
        self.assertEqual(LegacyImport.objects.count(), 1)
        new_user = User.objects.create_user(email='new@example.com', display_name='new')
        self.assertGreater(new_user.pk, 7)

    def test_invalid_source_rolls_back_all_rows(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("UPDATE tasks SET task_date='2026-02-30'")
        with self.assertRaises(CommandError):
            self.run_import()
        self.assertFalse(User.objects.exists())
        self.assertFalse(Task.objects.exists())
        self.assertFalse(LegacyImport.objects.exists())

    def test_nonempty_destination_refuses_overwrite(self):
        User.objects.create_user(email='existing@example.com', display_name='existing')
        with self.assertRaises(CommandError):
            self.run_import()
        self.assertEqual(User.objects.count(), 1)
