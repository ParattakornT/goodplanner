"""Shared availability calculations. Other members never receive personal titles."""
from collections import defaultdict
from datetime import date, timedelta

from .models import BusySlot, Meeting, Task


def minutes(value):
    hours, mins = value.split(':')
    return int(hours) * 60 + int(mins)


def clock(value):
    return f'{value // 60:02d}:{value % 60:02d}'


def busy_map(group, members, start=None, end=None):
    start, end = start or group.start_date, end or group.end_date
    result = defaultdict(list)
    by_user = {member.user_id: member for member in members}
    for slot in BusySlot.objects.filter(member__in=members, date__range=(start, end)):
        result[(slot.member_id, slot.date)].append({'id': slot.pk, 'start': slot.start, 'end': slot.end, 'source': 'manual'})
    # Deadline groups import personal times explicitly. Later personal edits
    # must not change the availability the member submitted before the cutoff.
    for member in members:
        if group.availability_deadline and member.share_personal:
            for slot in member.personal_busy_snapshot:
                day = date.fromisoformat(slot['date'])
                if start <= day <= end:
                    result[(member.pk, day)].append({'start': slot['start'], 'end': slot['end'], 'source': 'personal'})
    shared = [member.user_id for member in members if member.share_personal and not group.availability_deadline]
    for task in Task.objects.filter(user_id__in=shared, task_date__range=(start, end), completed=False).exclude(task_time=''):
        begin = minutes(task.task_time)
        finish = minutes(task.end_time) if task.end_time else min(begin + 30, 1440)
        result[(by_user[task.user_id].pk, task.task_date)].append({'start': begin, 'end': finish, 'source': 'personal'})
    # Meetings in any group block a participant's time in this group too.
    meetings = Meeting.objects.filter(participants__user_id__in=by_user, date__range=(start, end)).distinct().prefetch_related('participants')
    for meeting in meetings:
        for participant in meeting.participants.all():
            if participant.user_id in by_user:
                result[(by_user[participant.user_id].pk, meeting.date)].append({'start': meeting.start, 'end': meeting.end, 'source': 'meeting'})
    return result


def personal_snapshot(member):
    return [{'date': task.task_date.isoformat(), 'start': minutes(task.task_time),
             'end': minutes(task.end_time) if task.end_time else min(minutes(task.task_time) + 30, 1440)}
            for task in Task.objects.filter(user=member.user, completed=False,
                task_date__range=(member.group.start_date, member.group.end_date)).exclude(task_time='')]


def is_free(slots, start, end):
    return not any(slot['start'] < end and slot['end'] > start for slot in slots)


def availability(group, members, duration):
    busy = busy_map(group, members)
    days = []
    day = group.start_date
    blocked_by = defaultdict(int)
    candidate_total = 0
    total = len(members)
    unconfirmed = [member.pk for member in members if not member.availability_confirmed]
    while day <= group.end_date:
        # Consider every busy boundary, not only half-hour ticks. Participants
        # must be free for the WHOLE proposed meeting, not just at its start.
        # Boundaries come from EVERY member, not only confirmed ones, so a slot
        # added before pressing confirm still shapes the candidate times.
        starts = {group.window_start}
        for member in members:
            starts.update(slot['end'] for slot in busy[(member.pk, day)])
        candidates = []
        for start in sorted(starts):
            if start < group.window_start or start + duration > group.window_end:
                continue
            free, unsure, taken = [], [], []
            for member in members:
                # Three states, never two. A member who has not confirmed is
                # unknown, not free: counting them as free would let the group
                # book a meeting nobody checked.
                if not member.availability_confirmed:
                    unsure.append(member.pk)
                elif is_free(busy[(member.pk, day)], start, start + duration):
                    free.append(member.pk)
                else:
                    taken.append(member.pk)
            for pk in taken:
                blocked_by[pk] += 1
            candidate_total += 1
            candidates.append({'date': day.isoformat(), 'start': start, 'end': start + duration,
                               'free': free, 'unsure': unsure, 'busy': taken, 'count': len(free),
                               'unsureCount': len(unsure), 'busyCount': len(taken)})
        best = max(candidates, key=lambda slot: (slot['count'], -slot['unsureCount'], -slot['start']), default=None)
        if not best:
            status = 'no-window'
        elif best['count'] == total:
            status = 'all-free'
        elif best['count'] + best['unsureCount'] == total:
            status = 'maybe'
        elif best['count']:
            status = 'partial'
        else:
            status = 'none'
        days.append({'date': day.isoformat(), 'best': best, 'status': status, 'busy': [
            {'memberId': member.pk, 'slots': sorted(busy[(member.pk, day)], key=lambda slot: slot['start'])} for member in members
        ]})
        day += timedelta(days=1)
    ranked = sorted([day['best'] for day in days if day['best'] and day['best']['count']],
                    key=lambda slot: (-slot['count'], slot['unsureCount'], slot['date'], slot['start']))
    best_count = max((day['best']['count'] for day in days if day['best']), default=0)
    blockers = sorted([{'memberId': pk, 'blockedSlots': hits} for pk, hits in blocked_by.items()],
                      key=lambda row: -row['blockedSlots'])[:3]
    if not candidate_total:
        reason = 'no-window'
    elif total and len(unconfirmed) == total:
        reason = 'no-data'
    elif best_count == 0:
        reason = 'conflict'
    elif best_count < total:
        reason = 'partial'
    else:
        reason = 'full'
    return {'days': days, 'recommendations': ranked[:10], 'duration': duration,
            'unconfirmed': unconfirmed,
            'summary': {'memberCount': total, 'confirmedCount': total - len(unconfirmed),
                        'bestCount': best_count, 'candidateSlots': candidate_total,
                        'reason': reason, 'blockers': blockers}}
