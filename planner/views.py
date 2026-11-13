import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import date
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.core.cache import cache
from django.core.exceptions import RequestDataTooBig
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Value, When
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie

from . import mailer
from .models import MailSender, Task, User

ASSETS = {'login.css': 'text/css', 'planner.css': 'text/css', 'workspace.css': 'text/css', 'dashboard.css': 'text/css', 'login.js': 'text/javascript', 'dashboard.js': 'text/javascript', 'groups.css': 'text/css', 'groups.js': 'text/javascript', 'theme-dark.css': 'text/css', 'theme.js': 'text/javascript'}
logger = logging.getLogger(__name__)
GOOGLE_AUTHORIZATION_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_ENDPOINT = 'https://openidconnect.googleapis.com/v1/userinfo'


class GoogleOAuthError(Exception):
    pass


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def error(status, message):
    return JsonResponse({'message': message}, status=status)


def api(methods, authenticated=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                response = error(405, 'ไม่รองรับคำขอนี้')
                response['Allow'] = ', '.join(methods)
                return response
            if authenticated and not request.user.is_authenticated:
                return error(401, 'กรุณาเข้าสู่ระบบ')
            try:
                return view(request, *args, **kwargs)
            except ApiError as exc:
                return error(exc.status, exc.message)
            except RequestDataTooBig:
                return error(413, 'ข้อมูลยาวเกินไป')
        return wrapped
    return decorate


def read_json(request):
    if request.content_type != 'application/json':
        raise ApiError(415, 'รูปแบบข้อมูลไม่ถูกต้อง')
    raw = request.body
    if len(raw) > 16384:
        raise ApiError(413, 'ข้อมูลยาวเกินไป')
    try:
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise ValueError()
        return body
    except (ValueError, UnicodeDecodeError):
        raise ApiError(400, 'รูปแบบข้อมูลไม่ถูกต้อง')


def limit_auth(request):
    # Local single-process limit, shared safely across request threads.
    key = 'auth-attempts:' + request.META.get('REMOTE_ADDR', 'unknown')
    if cache.add(key, 1, timeout=900):
        return
    try:
        count = cache.incr(key)
    except ValueError:  # Key expired between add and incr.
        cache.add(key, 1, timeout=900)
        return
    if count > 30:
        raise ApiError(429, 'ลองหลายครั้งเกินไป กรุณารอ 15 นาทีแล้วลองใหม่')


def credentials(body):
    email = body.get('email', '')
    password = body.get('password', '')
    if not isinstance(email, str) or len(email.strip()) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email.strip()):
        raise ApiError(400, 'กรุณากรอกอีเมลให้ถูกต้อง')
    if not isinstance(password, str) or not 1 <= len(password) <= 128:
        raise ApiError(400, 'กรุณากรอกรหัสผ่านไม่เกิน 128 ตัวอักษร')
    return email.strip().lower(), password


def public_user(user):
    return {'id': user.pk, 'displayName': user.display_name, 'email': user.email,
            'emailReminders': user.email_reminders, 'isAdmin': user.is_staff}


def promote_admin(user):
    """Accounts named in ADMIN_EMAILS get the /admin site on their next sign-in."""
    if user.email.lower() in settings.ADMIN_EMAILS and not (user.is_staff and user.is_superuser):
        user.is_staff = user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])


def public_task(task):
    return {'id': task.pk, 'title': task.title, 'notes': task.notes, 'date': task.task_date.isoformat(),
            'time': task.task_time, 'endTime': task.end_time, 'priority': task.priority, 'completed': task.completed,
            'createdAt': task.created_at.isoformat(), 'updatedAt': task.updated_at.isoformat()}


def parse_date(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError()
        parsed = date.fromisoformat(value)
        if not date(1900, 1, 1) <= parsed <= date(2100, 12, 31):
            raise ValueError()
        return parsed
    except ValueError:
        raise ApiError(400, 'กรุณาเลือกวันที่ที่ถูกต้อง ระหว่างปี ค.ศ. 1900–2100')


def task_data(body, existing=None):
    allowed = {'title', 'notes', 'date', 'time', 'endTime', 'priority', 'completed'}
    if not body or not body.keys() <= allowed:
        raise ApiError(400, 'ข้อมูลแผนไม่ถูกต้อง')
    data = {'notes': '', 'time': '', 'endTime': '', 'priority': 'normal', 'completed': False}
    if existing:
        data.update({key: value for key, value in public_task(existing).items() if key in allowed})
    data.update(body)
    if not isinstance(data.get('title'), str) or not 1 <= len(data['title'].strip()) <= 120:
        raise ApiError(400, 'กรุณากรอกชื่องาน 1–120 ตัวอักษร')
    if not isinstance(data['notes'], str) or len(data['notes']) > 2000:
        raise ApiError(400, 'รายละเอียดต้องไม่เกิน 2,000 ตัวอักษร')
    task_date = parse_date(data.get('date'))
    if not isinstance(data['time'], str) or (data['time'] and not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', data['time'])):
        raise ApiError(400, 'กรุณาระบุเวลาให้ถูกต้อง')
    if data['priority'] not in ('low', 'normal', 'high'):
        raise ApiError(400, 'ระดับความสำคัญไม่ถูกต้อง')
    if not isinstance(data['endTime'], str) or (data['endTime'] and (
            not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', data['endTime']) or not data['time'] or data['endTime'] <= data['time'])):
        raise ApiError(400, 'เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มในวันเดียวกัน')
    if type(data['completed']) is not bool:
        raise ApiError(400, 'สถานะงานไม่ถูกต้อง')
    return {'title': data['title'].strip(), 'notes': data['notes'].strip(), 'task_date': task_date,
            'task_time': data['time'], 'end_time': data['endTime'], 'priority': data['priority'], 'completed': data['completed']}


@ensure_csrf_cookie
@api(['GET', 'HEAD'])
def page(request, name):
    if name in ('dashboard.html', 'groups.html') and not request.user.is_authenticated:
        return redirect('/login.html')
    return render(request, name)


@api(['GET', 'HEAD'])
def asset(request, name):
    # Explicit allowlist: never expose the project directory or database.
    folder = 'css' if name.endswith('.css') else 'js'
    return FileResponse((settings.WEB_DIR / folder / name).open('rb'), content_type=ASSETS[name])


@api(['POST'])
def register(request):
    body = read_json(request)
    limit_auth(request)
    email, password = credentials(body)
    name = body.get('displayName')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ApiError(400, 'กรุณากรอกชื่อที่แสดง 1–80 ตัวอักษร')
    if len(password) < 8:
        raise ApiError(400, 'รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร')
    if password != body.get('confirmPassword'):
        raise ApiError(400, 'รหัสผ่านทั้งสองช่องไม่ตรงกัน')
    try:
        with transaction.atomic():
            User.objects.create_user(email=email, password=password, display_name=name.strip())
    except IntegrityError:
        raise ApiError(409, 'อีเมลนี้สมัครสมาชิกแล้ว กรุณาเข้าสู่ระบบ')
    return JsonResponse({'message': 'สมัครสมาชิกสำเร็จ กรุณาเข้าสู่ระบบ'}, status=201)


@api(['POST'])
def login(request):
    body = read_json(request)
    limit_auth(request)
    email, password = credentials(body)
    user = authenticate(request, email=email, password=password)
    if user is None:
        raise ApiError(401, 'อีเมลหรือรหัสผ่านไม่ถูกต้อง')
    promote_admin(user)
    auth_login(request, user)
    response = JsonResponse({'user': public_user(user)})
    response.delete_cookie('goodplanner_session', samesite='Strict')
    return response


def google_error_redirect(code):
    return redirect('/login.html?' + urlencode({'google_error': code}))


def google_request(url, data=None, headers=None):
    request = Request(url, data=data, headers=headers or {})
    try:
        with urlopen(request, timeout=10) as response:
            payload = response.read(65537)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise GoogleOAuthError('Google provider request failed') from exc
    if len(payload) > 65536:
        raise GoogleOAuthError('Google provider response was too large')
    try:
        result = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GoogleOAuthError('Google provider returned invalid JSON') from exc
    if not isinstance(result, dict):
        raise GoogleOAuthError('Google provider returned invalid data')
    return result


def google_token(code, verifier, redirect_uri):
    result = google_request(
        GOOGLE_TOKEN_ENDPOINT,
        data=urlencode({
            'code': code,
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
            'code_verifier': verifier,
        }).encode('utf-8'),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
    )
    access_token = result.get('access_token')
    if not isinstance(access_token, str) or not access_token:
        raise GoogleOAuthError('Google token response did not contain an access token')
    return access_token


def google_profile(access_token):
    result = google_request(
        GOOGLE_USERINFO_ENDPOINT,
        headers={'Authorization': 'Bearer ' + access_token},
    )
    email = result.get('email')
    name = result.get('name')
    if (not isinstance(result.get('sub'), str) or not result['sub']
            or not isinstance(email, str) or result.get('email_verified') is not True):
        raise GoogleOAuthError('Google account email is not verified')
    return email, name


@api(['GET'])
def google_login(request):
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return google_error_redirect('configuration')
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    redirect_uri = settings.GOOGLE_REDIRECT_URI or request.build_absolute_uri('/auth/google/callback')
    request.session['google_oauth_state'] = state
    request.session['google_oauth_verifier'] = verifier
    request.session['google_oauth_redirect_uri'] = redirect_uri
    query = urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'prompt': 'select_account',
    })
    return redirect(GOOGLE_AUTHORIZATION_ENDPOINT + '?' + query)


@api(['GET'])
def google_callback(request):
    state = request.GET.get('state', '')
    expected_state = request.session.pop('google_oauth_state', '')
    verifier = request.session.pop('google_oauth_verifier', '')
    redirect_uri = request.session.pop('google_oauth_redirect_uri', '')
    if not expected_state or not state or not hmac.compare_digest(state, expected_state):
        return google_error_redirect('invalid')
    if request.GET.get('error'):
        return google_error_redirect('cancelled')
    code = request.GET.get('code', '')
    if not code or not verifier or not redirect_uri:
        return google_error_redirect('invalid')
    try:
        access_token = google_token(code, verifier, redirect_uri)
        email, name = google_profile(access_token)
        email = email.strip().lower()
        if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise GoogleOAuthError('Google returned an invalid email')
        display_name = name.strip() if isinstance(name, str) else ''
        if not display_name:
            display_name = email.split('@', 1)[0]
        display_name = display_name[:80]
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'display_name': display_name},
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=['password'])
        if not user.is_active:
            return google_error_redirect('invalid')
    except GoogleOAuthError as exc:
        logger.warning('Google sign-in was rejected: %s', exc)
        return google_error_redirect('provider')
    except IntegrityError:
        logger.exception('Google sign-in could not create or retrieve the account')
        return google_error_redirect('provider')
    promote_admin(user)
    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect('/dashboard.html')


@api(['POST'])
def logout(request):
    read_json(request)
    auth_logout(request)
    response = JsonResponse({'message': 'ออกจากระบบแล้ว'})
    response.delete_cookie('goodplanner_session', samesite='Strict')
    return response


@api(['GET', 'PATCH'], authenticated=True)
def me(request):
    if request.method == 'PATCH':
        body = read_json(request)
        if set(body) - {'emailReminders'} or type(body.get('emailReminders')) is not bool:
            raise ApiError(400, 'ข้อมูลการตั้งค่าไม่ถูกต้อง')
        request.user.email_reminders = body['emailReminders']
        request.user.save(update_fields=['email_reminders'])
    return JsonResponse({'user': public_user(request.user)})


@api(['GET'], authenticated=True)
def gmail_connect(request):
    """Admin-only: authorise the Gmail account that sends reminder emails."""
    if not request.user.is_superuser:
        return error(403, 'เฉพาะผู้ดูแลระบบ')
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return error(503, 'ยังไม่ได้ตั้งค่า GOOGLE_CLIENT_ID และ GOOGLE_CLIENT_SECRET')
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    redirect_uri = request.build_absolute_uri('/auth/gmail/callback')
    request.session['gmail_oauth'] = {'state': state, 'verifier': verifier, 'redirect_uri': redirect_uri}
    return redirect(GOOGLE_AUTHORIZATION_ENDPOINT + '?' + urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID, 'redirect_uri': redirect_uri, 'response_type': 'code',
        'scope': 'openid email ' + mailer.GMAIL_SCOPE, 'state': state, 'code_challenge': challenge,
        'code_challenge_method': 'S256', 'access_type': 'offline', 'prompt': 'consent',
    }))


@api(['GET'], authenticated=True)
def gmail_callback(request):
    saved = request.session.pop('gmail_oauth', None) or {}
    state = request.GET.get('state', '')
    if not request.user.is_superuser or not saved.get('state') or not hmac.compare_digest(state, saved['state']):
        return error(400, 'คำขอเชื่อมต่อ Gmail ไม่ถูกต้อง กรุณาเริ่มใหม่จากหน้า /auth/gmail')
    code = request.GET.get('code', '')
    if request.GET.get('error') or not code:
        return redirect('/admin/planner/mailsender/')
    try:
        result = google_request(GOOGLE_TOKEN_ENDPOINT, data=urlencode({
            'code': code, 'client_id': settings.GOOGLE_CLIENT_ID, 'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri': saved['redirect_uri'], 'grant_type': 'authorization_code', 'code_verifier': saved['verifier'],
        }).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded'})
        refresh = result.get('refresh_token')
        if mailer.GMAIL_SCOPE not in str(result.get('scope', '')) or not isinstance(refresh, str):
            return error(400, 'Google ไม่ได้ให้สิทธิ์ส่งอีเมล กรุณาติ๊กช่อง "ส่งอีเมลในนามคุณ" แล้วลองใหม่')
        email, _ = google_profile(result['access_token'])
    except GoogleOAuthError:
        logger.exception('Gmail connection failed')
        return error(502, 'เชื่อมต่อ Gmail ไม่สำเร็จ กรุณาลองใหม่')
    MailSender.objects.update_or_create(pk=1, defaults={'email': email.lower(), 'refresh_token': refresh,
                                                        'connected_at': timezone.now()})
    ok = mailer.deliver(email, 'Good Planner: เชื่อมต่อ Gmail สำเร็จ',
                        'อีเมลแจ้งเตือนของ Good Planner จะถูกส่งจากบัญชีนี้ตั้งแต่ตอนนี้')
    return redirect('/admin/planner/mailsender/?connected=' + ('1' if ok else 'send-failed'))


@csrf_exempt
@api(['POST'])
def cron_reminders(request):
    """Called hourly by GitHub Actions. Safe to call repeatedly: each email is logged once."""
    supplied = request.headers.get('Authorization', '').removeprefix('Bearer ')
    if not settings.CRON_SECRET or not hmac.compare_digest(supplied.encode(), settings.CRON_SECRET.encode()):
        return error(403, 'forbidden')
    return JsonResponse({'digest': mailer.send_digests(), 'dueSoon': mailer.send_due_soon()})


@api(['GET', 'POST'], authenticated=True)
def tasks(request):
    if request.method == 'POST':
        task = Task.objects.create(user=request.user, **task_data(read_json(request)))
        return JsonResponse({'task': public_task(task)}, status=201)
    month = request.GET.get('month', '')
    if not re.fullmatch(r'\d{4}-\d{2}', month):
        raise ApiError(400, 'กรุณาระบุเดือนในรูปแบบ YYYY-MM')
    start = parse_date(month + '-01')
    result = Task.objects.filter(user=request.user, task_date__year=start.year, task_date__month=start.month).order_by(
        'task_date', 'completed', Case(When(task_time='', then=Value(1)), default=Value(0), output_field=IntegerField()), 'task_time', 'id')
    return JsonResponse({'tasks': [public_task(task) for task in result]})


@api(['PATCH', 'DELETE'], authenticated=True)
def task_detail(request, task_id):
    if not 1 <= task_id <= 9223372036854775807:
        raise ApiError(404, 'ไม่พบงานนี้')
    try:
        task = Task.objects.get(pk=task_id, user=request.user)
    except Task.DoesNotExist:
        raise ApiError(404, 'ไม่พบงานนี้')
    if request.method == 'DELETE':
        task.delete()
        return JsonResponse({'message': 'ลบงานแล้ว'})
    for key, value in task_data(read_json(request), task).items():
        setattr(task, key, value)
    task.updated_at = timezone.now()
    task.save()
    return JsonResponse({'task': public_task(task)})


def csrf_failure(request, reason=''):
    return error(403, 'การตรวจสอบหน้าเว็บหมดอายุ กรุณารีเฟรชหน้าแล้วลองอีกครั้ง')


def bad_request(request, exception=None):
    return error(400, 'รูปแบบคำขอไม่ถูกต้อง')


def forbidden(request, exception=None):
    return error(403, 'ไม่อนุญาตให้เข้าถึง')


def not_found(request, exception=None):
    return error(404, 'ไม่พบหน้านี้')


def server_error(request):
    return error(500, 'ระบบขัดข้อง กรุณาลองอีกครั้ง')
