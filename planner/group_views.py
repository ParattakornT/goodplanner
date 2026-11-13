import hashlib
import json
import re
from datetime import datetime, time, timedelta

from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import mailer
from .group_services import availability, busy_map, clock, is_free, minutes, personal_snapshot
from .models import BusySlot, GroupTask, Meeting, Membership, Notification, PlanningGroup
from .views import ApiError, api, parse_date, read_json


def fields(body, allowed, required=()):
    if not body or not body.keys() <= set(allowed) or not set(required) <= body.keys():
        raise ApiError(400, 'ข้อมูลไม่ครบหรือมีช่องข้อมูลที่ไม่รองรับ')


def text_field(body, key, maximum, optional=False):
    value = body.get(key, '')
    if not isinstance(value, str) or len(value.strip()) > maximum or (not optional and not value.strip()):
        raise ApiError(400, f'กรุณากรอกข้อมูลให้ครบและไม่เกิน {maximum} ตัวอักษร')
    return value.strip()


def valid_id(value):
    return type(value) is int and 1 <= value <= 9223372036854775807


def membership(request, group_id, owner=False):
    member = Membership.objects.select_related('group', 'user').filter(group_id=group_id, user=request.user).first() if valid_id(group_id) else None
    if not member:
        raise ApiError(404, 'ไม่พบกลุ่มนี้ หรือคุณยังไม่ได้เข้าร่วมกลุ่ม')
    if owner and member.group.owner_id != request.user.pk:
        raise ApiError(403, 'เฉพาะเจ้าของกลุ่มเท่านั้นที่ทำรายการนี้ได้')
    return member


def in_range(group, value):
    day = parse_date(value)
    if not group.start_date <= day <= group.end_date:
        raise ApiError(400, 'วันที่ต้องอยู่ในช่วงเวลาของกลุ่ม')
    return day


def interval(body):
    start, end = body.get('start'), body.get('end')
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= 1440:
        raise ApiError(400, 'เวลาเริ่มและสิ้นสุดไม่ถูกต้อง ต้องอยู่ในวันเดียวกัน')
    return start, end


def require_open(group):
    if group.availability_closed:
        raise ApiError(409, 'ปิดรับเวลาไม่ว่างแล้ว ข้อมูลที่ส่งไว้จะใช้ให้หัวหน้าเลือกนัดหมาย')


def planning_settings(body, start_date, window_length):
    duration = body.get('durationMinutes')
    if type(duration) is not int or not 30 <= duration <= 720 or duration % 15 or duration > window_length:
        raise ApiError(400, 'ระยะเวลาทำงานต้องเป็นช่วงละ 15 นาที ตั้งแต่ 30 นาทีถึง 12 ชั่วโมง และไม่เกินช่วงเวลานัดต่อวัน')
    try:
        deadline = parse_datetime(body.get('availabilityDeadline', ''))
    except (ValueError, TypeError, OverflowError):
        deadline = None
    if deadline is None or timezone.is_naive(deadline):
        raise ApiError(400, 'กรุณาระบุวันและเวลาปิดรับ พร้อมเขตเวลา')
    beginning = timezone.make_aware(datetime.combine(start_date, time.min))
    if not timezone.now() < deadline < beginning:
        raise ApiError(400, 'วันปิดรับต้องเป็นเวลาในอนาคต และก่อนวันแรกของช่วงวันที่นัด (เวลาไทย)')
    return duration, deadline


def task_json(task):
    return {'id': task.pk, 'title': task.title, 'notes': task.notes, 'assigneeId': task.assignee_id,
            'date': task.due_date.isoformat(), 'time': task.due_time, 'status': task.status}


def meeting_json(meeting):
    return {'id': meeting.pk, 'title': meeting.title, 'date': meeting.date.isoformat(),
            'start': meeting.start, 'end': meeting.end, 'participants': [m.pk for m in meeting.participants.all()],
            'acknowledgement': meeting.conflict_acknowledgement}


def group_json(group):
    return {'id': group.pk, 'name': group.name, 'ownerId': group.owner_id, 'inviteCode': group.invite_code,
            'startDate': group.start_date.isoformat(), 'endDate': group.end_date.isoformat(),
            'windowStart': group.window_start, 'windowEnd': group.window_end,
            'durationMinutes': group.duration_minutes,
            'availabilityDeadline': group.availability_deadline.isoformat() if group.availability_deadline else None,
            'availabilityClosed': group.availability_closed, 'serverNow': timezone.now().isoformat()}


def email_task(task, actor):
    due = f'{task.due_date:%d/%m/%Y}' + (f' เวลา {task.due_time}' if task.due_time else '')
    mailer.email_users([task.assignee.user_id], f'Good Planner: คุณได้รับงาน “{task.title}”',
        f'{actor.display_name} มอบหมายงาน “{task.title}” ในกลุ่ม {task.group.name} ให้คุณ\nกำหนดส่ง {due}'
        + (f'\n\nรายละเอียด: {task.notes}' if task.notes else ''), actor.pk)


def notify(group, user_ids, message, actor=None):
    Notification.objects.bulk_create([Notification(group=group, user_id=user_id, message=message[:300])
                                      for user_id in set(user_ids) if user_id != actor])


@api(['GET', 'POST'], authenticated=True)
def groups(request):
    if request.method == 'GET':
        result = PlanningGroup.objects.filter(members__user=request.user).annotate(member_count=Count('members')).order_by('-created_at')
        # Count all memberships, independent of the membership filter above.
        return JsonResponse({'groups': [{**group_json(g), 'memberCount': g.members.count(),
            'taskCount': g.group_tasks.count(), 'doneCount': g.group_tasks.filter(status='done').count()} for g in result]})
    body = read_json(request)
    required = ['name', 'startDate', 'endDate', 'durationMinutes', 'availabilityDeadline']
    fields(body, [*required, 'start', 'end'], required)
    name = text_field(body, 'name', 100)
    start_date, end_date = parse_date(body['startDate']), parse_date(body['endDate'])
    if not 0 <= (end_date - start_date).days <= 365:
        raise ApiError(400, 'วันสิ้นสุดต้องไม่ก่อนวันเริ่ม และช่วงกลุ่มต้องไม่เกิน 366 วัน')
    # New groups allow any time of day; older clients may still send a window.
    if ('start' in body) != ('end' in body):
        raise ApiError(400, 'หากระบุช่วงเวลาต้องส่งเวลาเริ่มและสิ้นสุดให้ครบ')
    start, end = interval(body if 'start' in body else {'start': 0, 'end': 1440})
    if end - start < 30:
        raise ApiError(400, 'ช่วงเวลานัดหมายต้องอย่างน้อย 30 นาที')
    duration, deadline = planning_settings(body, start_date, end - start)
    with transaction.atomic():
        group = PlanningGroup.objects.create(name=name, owner=request.user, start_date=start_date, end_date=end_date,
            window_start=start, window_end=end, duration_minutes=duration, availability_deadline=deadline)
        Membership.objects.create(group=group, user=request.user)
    return JsonResponse({'group': group_json(group)}, status=201)


@api(['POST'], authenticated=True)
def join(request):
    body = read_json(request)
    fields(body, ['code'], ['code'])
    code = text_field(body, 'code', 10).upper()
    key = f'group-join:{request.user.pk}'
    if not cache.add(key, 1, 900):
        try:
            if cache.incr(key) > 30:
                raise ApiError(429, 'ลองรหัสหลายครั้งเกินไป กรุณารอ 15 นาที')
        except ValueError:
            cache.add(key, 1, 900)
    with transaction.atomic():
        group = PlanningGroup.objects.filter(invite_code=code).first()
        if not group:
            raise ApiError(404, 'ไม่พบรหัสกลุ่มนี้ กรุณาตรวจสอบกับเจ้าของกลุ่ม')
        if not group.members.filter(user=request.user).exists():
            require_open(group)
        if not group.members.filter(user=request.user).exists() and group.members.count() >= 50:
            raise ApiError(409, 'กลุ่มนี้มีสมาชิกครบ 50 คนแล้ว')
        member, created = Membership.objects.get_or_create(group=group, user=request.user)
        if created:
            notify(group, [group.owner_id], f'{request.user.display_name} เข้าร่วมกลุ่ม {group.name}', request.user.pk)
    return JsonResponse({'group': group_json(group)}, status=201 if created else 200)


@api(['GET', 'DELETE'], authenticated=True)
def detail(request, group_id):
    member = membership(request, group_id, owner=request.method == 'DELETE')
    group = member.group
    if request.method == 'DELETE':
        group.delete()
        return JsonResponse({'message': 'ลบกลุ่มแล้ว'})
    result = group_json(group)
    result['myMemberId'] = member.pk
    result['members'] = [{'id': m.pk, 'userId': m.user_id, 'name': m.user.display_name,
                          'confirmed': m.availability_confirmed,
                          # Sharing preference is shown only to its owner.
                          **({'sharePersonal': m.share_personal} if m.pk == member.pk else {})}
                         for m in group.members.select_related('user').order_by('joined_at', 'id')]
    result['tasks'] = [task_json(t) for t in group.group_tasks.order_by('due_date', 'due_time', 'id')]
    result['meetings'] = [meeting_json(m) for m in group.meetings.order_by('date', 'start').prefetch_related('participants')]
    return JsonResponse({'group': result})


@api(['GET'], authenticated=True)
def free_times(request, group_id):
    member = membership(request, group_id)
    duration = request.GET.get('duration', str(member.group.duration_minutes))
    if not duration.isdecimal() or len(duration) > 3 or not 30 <= int(duration) <= 720 or int(duration) % 15:
        raise ApiError(400, 'ระยะเวลาไม่ถูกต้อง')
    if member.group.availability_deadline and int(duration) != member.group.duration_minutes:
        raise ApiError(400, 'ใช้ระยะเวลาทำงานที่หัวหน้ากำหนดตอนสร้างกลุ่ม')
    return JsonResponse(availability(member.group, list(member.group.members.all()), int(duration)))


@api(['PATCH'], authenticated=True)
def preferences(request, group_id):
    with transaction.atomic():
        member = membership(request, group_id)
        require_open(member.group)
        body = read_json(request)
        fields(body, ['sharePersonal', 'confirmed'])
        for key, field in [('sharePersonal', 'share_personal'), ('confirmed', 'availability_confirmed')]:
            if key in body:
                if type(body[key]) is not bool:
                    raise ApiError(400, 'ข้อมูลสถานะไม่ถูกต้อง')
                setattr(member, field, body[key])
        if member.group.availability_deadline:
            if not member.share_personal:
                member.personal_busy_snapshot = []
            elif body.get('sharePersonal') is True or body.get('confirmed') is True:
                member.personal_busy_snapshot = personal_snapshot(member)
        member.save()
    return JsonResponse({'message': 'บันทึกการตั้งค่าเวลาแล้ว'})


@api(['POST'], authenticated=True)
def busy_create(request, group_id):
    with transaction.atomic():
        member = membership(request, group_id)
        require_open(member.group)
        body = read_json(request)
        fields(body, ['date', 'start', 'end'], ['date', 'start', 'end'])
        day = in_range(member.group, body['date'])
        start, end = interval(body)
        if member.busy_slots.filter(date=day, start__lt=end, end__gt=start).exists():
            raise ApiError(409, 'ช่วงเวลานี้ซ้ำกับเวลาไม่ว่างที่คุณกรอกแล้ว')
        slot = BusySlot.objects.create(member=member, date=day, start=start, end=end)
    return JsonResponse({'id': slot.pk}, status=201)


@api(['DELETE'], authenticated=True)
def busy_delete(request, group_id, slot_id):
    with transaction.atomic():
        member = membership(request, group_id)
        require_open(member.group)
        slot = member.busy_slots.filter(pk=slot_id).first() if valid_id(slot_id) else None
        if not slot:
            raise ApiError(404, 'ไม่พบเวลาของคุณที่ต้องการลบ')
        slot.delete()
    return JsonResponse({'message': 'ลบช่วงเวลาแล้ว'})


def task_values(body, group):
    title = text_field(body, 'title', 120)
    notes = text_field(body, 'notes', 2000, optional=True)
    day = in_range(group, body.get('date'))
    time = body.get('time', '')
    if not isinstance(time, str) or (time and not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', time)):
        raise ApiError(400, 'เวลาส่งงานไม่ถูกต้อง')
    assignee_id = body.get('assigneeId')
    assignee = group.members.filter(pk=assignee_id).first() if valid_id(assignee_id) else None
    if not assignee:
        raise ApiError(400, 'ผู้รับผิดชอบต้องเป็นสมาชิกในกลุ่มนี้')
    status = body.get('status', 'todo')
    if status not in ('todo', 'doing', 'done'):
        raise ApiError(400, 'สถานะงานไม่ถูกต้อง')
    return dict(title=title, notes=notes, assignee=assignee, due_date=day, due_time=time, status=status)


@api(['POST'], authenticated=True)
def task_create(request, group_id):
    with transaction.atomic():
        member = membership(request, group_id, owner=True)
        body = read_json(request)
        fields(body, ['title', 'notes', 'date', 'time', 'assigneeId', 'status'], ['title', 'date', 'assigneeId'])
        task = GroupTask.objects.create(group=member.group, **task_values(body, member.group))
        notify(member.group, [task.assignee.user_id], f'คุณได้รับงาน “{task.title}” ในกลุ่ม {member.group.name}', request.user.pk)
        email_task(task, request.user)
    return JsonResponse({'task': task_json(task)}, status=201)


@api(['PATCH', 'DELETE'], authenticated=True)
def task_detail(request, group_id, task_id):
    with transaction.atomic():
        member = membership(request, group_id)
        group = member.group
        task = group.group_tasks.filter(pk=task_id).first() if valid_id(task_id) else None
        if not task:
            raise ApiError(404, 'ไม่พบงานนี้')
        owner = group.owner_id == request.user.pk
        if request.method == 'DELETE':
            if not owner:
                raise ApiError(403, 'เฉพาะเจ้าของกลุ่มเท่านั้นที่ลบงานได้')
            task.delete()
            return JsonResponse({'message': 'ลบงานแล้ว'})
        body = read_json(request)
        fields(body, ['title', 'notes', 'date', 'time', 'assigneeId', 'status'] if owner else ['status'])
        if not owner and task.assignee_id != member.pk:
            raise ApiError(403, 'คุณเปลี่ยนสถานะได้เฉพาะงานที่ได้รับมอบหมาย')
        old_assignee = task.assignee_id
        values = task_values({**task_json(task), **body}, group)
        for key, value in values.items():
            setattr(task, key, value)
        task.updated_at = timezone.now()
        task.save()
        if task.assignee_id != old_assignee:
            notify(group, [task.assignee.user_id], f'คุณได้รับงาน “{task.title}” ในกลุ่ม {group.name}', request.user.pk)
            email_task(task, request.user)
    return JsonResponse({'task': task_json(task)})


@api(['POST'], authenticated=True)
def meeting_create(request, group_id):
    with transaction.atomic():
        member = membership(request, group_id, owner=True)
        group = member.group
        if group.availability_deadline and not group.availability_closed:
            raise ApiError(409, 'ยังเปิดรับเวลาไม่ว่างอยู่ หัวหน้าจะเลือกนัดได้หลังวันปิดรับ')
        body = read_json(request)
        fields(body, ['title', 'date', 'start', 'end', 'participants', 'confirmationToken'], ['title', 'date', 'start', 'end', 'participants'])
        title = text_field(body, 'title', 120)
        day = in_range(group, body['date'])
        start, end = interval(body)
        if start < group.window_start or end > group.window_end:
            raise ApiError(400, 'เวลานัดหมายต้องอยู่ในช่วงเวลาประจำกลุ่ม')
        if group.availability_deadline and end - start != group.duration_minutes:
            raise ApiError(400, f'นัดหมายต้องใช้เวลาทำงาน {group.duration_minutes} นาที ตามที่กำหนดไว้')
        ids = body['participants']
        if not isinstance(ids, list) or not ids or len(ids) > 50 or not all(valid_id(i) for i in ids) or len(set(ids)) != len(ids):
            raise ApiError(400, 'กรุณาเลือกผู้เข้าร่วมอย่างน้อย 1 คน')
        members = list(group.members.filter(pk__in=ids).select_related('user').order_by('pk'))
        if len(members) != len(ids):
            raise ApiError(400, 'ผู้เข้าร่วมต้องเป็นสมาชิกในกลุ่มนี้')
        busy = busy_map(group, members, day, day)
        conflicts = [{'memberId': m.pk, 'name': m.user.display_name,
                      'slots': sorted([{'start': s['start'], 'end': s['end']} for s in busy[(m.pk, day)]
                                       if s['start'] < end and s['end'] > start], key=lambda s: (s['start'], s['end']))}
                     for m in members if not is_free(busy[(m.pk, day)], start, end)]
        unconfirmed = [{'memberId': m.pk, 'name': m.user.display_name} for m in members
                       if group.availability_deadline and not m.availability_confirmed]
        acknowledgement = {}
        if conflicts or unconfirmed:
            # Bind acknowledgement to this owner, exact meeting and CURRENT
            # conflicts. A changed form or new conflicting event requires consent again.
            evidence = {'group': group.pk, 'owner': request.user.pk, 'title': title, 'date': day.isoformat(),
                        'start': start, 'end': end, 'participants': sorted(ids), 'conflicts': conflicts, 'unconfirmed': unconfirmed}
            digest = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
            token = body.get('confirmationToken')
            accepted = False
            if isinstance(token, str):
                try:
                    accepted = signing.loads(token, salt='meeting-conflict', max_age=300).get('digest') == digest
                except signing.BadSignature:
                    pass
            if not accepted:
                return JsonResponse({'code': 'meeting_conflict', 'message': 'กรุณาตรวจรายชื่อและยืนยันอีกครั้งก่อนบันทึกนัด',
                    'conflicts': conflicts, 'unconfirmed': unconfirmed,
                    'confirmationToken': signing.dumps({'digest': digest}, salt='meeting-conflict')}, status=409)
            acknowledgement = {'conflicts': conflicts, 'unconfirmed': unconfirmed, 'acknowledgedAt': timezone.now().isoformat()}
        meeting = Meeting.objects.create(group=group, title=title, date=day, start=start, end=end,
            conflict_acknowledgement=acknowledgement)
        meeting.participants.set(members)
        notify(group, [m.user_id for m in members], f'นัดหมาย “{title}” วันที่ {day} เวลา {clock(start)} ในกลุ่ม {group.name}', request.user.pk)
        mailer.email_users([m.user_id for m in members], f'Good Planner: นัดหมายใหม่ “{title}”',
            f'{request.user.display_name} นัดหมาย “{title}” ของกลุ่ม {group.name}\n'
            f'วันที่ {day:%d/%m/%Y} เวลา {clock(start)}–{clock(end)}\nนัดนี้ถูกเพิ่มลงในปฏิทินของคุณแล้ว', request.user.pk)
    return JsonResponse({'meeting': meeting_json(meeting)}, status=201)


@api(['DELETE'], authenticated=True)
def meeting_delete(request, group_id, meeting_id):
    with transaction.atomic():
        member = membership(request, group_id, owner=True)
        meeting = member.group.meetings.filter(pk=meeting_id).first() if valid_id(meeting_id) else None
        if not meeting:
            raise ApiError(404, 'ไม่พบนัดหมายนี้')
        people = list(meeting.participants.values_list('user_id', flat=True))
        notify(member.group, people, f'ยกเลิกนัดหมาย “{meeting.title}” ในกลุ่ม {member.group.name}', request.user.pk)
        mailer.email_users(people, f'Good Planner: ยกเลิกนัด “{meeting.title}”',
            f'นัด “{meeting.title}” ของกลุ่ม {member.group.name} วันที่ {meeting.date:%d/%m/%Y} เวลา {clock(meeting.start)} ถูกยกเลิกแล้ว', request.user.pk)
        meeting.delete()
    return JsonResponse({'message': 'ยกเลิกนัดหมายแล้ว'})


@api(['POST'], authenticated=True)
def remind(request, group_id):
    member = membership(request, group_id, owner=True)
    require_open(member.group)
    read_json(request)
    if not cache.add(f'group-reminder:{group_id}', True, 3600):
        raise ApiError(429, 'ส่งเตือนแล้ว ส่งได้อีกครั้งใน 1 ชั่วโมง')
    ids = member.group.members.filter(availability_confirmed=False).values_list('user_id', flat=True)
    notify(member.group, ids, f'กรุณายืนยันเวลาไม่ว่างในกลุ่ม {member.group.name}', request.user.pk)
    return JsonResponse({'message': 'ส่งแจ้งเตือนในเว็บให้สมาชิกที่ยังไม่ยืนยันแล้ว'})


@api(['GET', 'PATCH'], authenticated=True)
def notifications(request):
    result = Notification.objects.filter(user=request.user)
    if request.method == 'PATCH':
        read_json(request)
        result.filter(read_at__isnull=True).update(read_at=timezone.now())
        return JsonResponse({'message': 'อ่านการแจ้งเตือนแล้ว'})
    return JsonResponse({'unread': result.filter(read_at__isnull=True).count(), 'notifications': [
        {'id': n.pk, 'groupId': n.group_id, 'message': n.message, 'read': n.read_at is not None, 'createdAt': n.created_at.isoformat()}
        for n in result.order_by('-created_at', '-id')[:50]]})


@api(['GET'], authenticated=True)
def feed(request):
    month = request.GET.get('month', '')
    if not re.fullmatch(r'\d{4}-\d{2}', month):
        raise ApiError(400, 'กรุณาระบุเดือน YYYY-MM')
    start = parse_date(month + '-01')
    tasks = GroupTask.objects.filter(assignee__user=request.user, due_date__year=start.year, due_date__month=start.month).select_related('group')
    meetings = Meeting.objects.filter(participants__user=request.user, date__year=start.year, date__month=start.month).distinct().select_related('group')
    items = [{'id': f'group-task-{t.pk}', 'title': t.title, 'notes': t.notes, 'date': t.due_date.isoformat(), 'time': t.due_time,
              'priority': 'normal', 'completed': t.status == 'done', 'readOnly': True, 'groupId': t.group_id, 'groupName': t.group.name, 'kind': 'งานกลุ่ม'} for t in tasks]
    now = timezone.localtime()
    items += [{'id': f'meeting-{m.pk}', 'title': m.title, 'notes': f'นัดหมาย {clock(m.start)}–{clock(m.end)}', 'date': m.date.isoformat(),
               'time': clock(m.start), 'priority': 'normal', 'completed': m.date < now.date() or (m.date == now.date() and m.end <= now.hour * 60 + now.minute),
               'readOnly': True, 'groupId': m.group_id, 'groupName': m.group.name, 'kind': 'นัดหมายกลุ่ม'} for m in meetings]
    return JsonResponse({'tasks': items})
