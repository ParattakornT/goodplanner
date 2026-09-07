"""
Views ของแอป tasks — Increment 1: Personal Planner
ครอบคลุม: Create, Read (list/calendar/today), Update, Delete
ทุก view กันด้วย @login_required (route guard) และกรองเฉพาะงานของ request.user เท่านั้น
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .forms import TaskForm
from .models import Task

PRIORITY_COLOR = {
    "high": "#DB5344",
    "mid": "#E8B221",
    "low": "#8A93A6",
}


@login_required
def calendar_view(request):
    """หน้าปฏิทินรายเดือน/รายสัปดาห์ ใช้ FullCalendar.js ตามที่ระบุใน Tools"""
    return render(request, "tasks/calendar.html")


@login_required
def calendar_events_json(request):
    """
    Endpoint ให้ FullCalendar.js ดึงข้อมูลงานของผู้ใช้คนนี้เท่านั้น (JSON)
    FullCalendar เรียกด้วย query param start/end ของช่วงที่กำลังแสดงผลอยู่
    """
    tasks = Task.objects.filter(owner=request.user)
    start = request.GET.get("start")
    end = request.GET.get("end")
    if start:
        tasks = tasks.filter(date__gte=start[:10])
    if end:
        tasks = tasks.filter(date__lte=end[:10])

    events = [
        {
            "id": t.id,
            "title": t.title,
            "start": f"{t.date}T{t.start_time}",
            "end": f"{t.date}T{t.end_time}",
            "color": PRIORITY_COLOR.get(t.priority, "#4A5468"),
            "url": f"/tasks/{t.id}/",
        }
        for t in tasks
    ]
    return JsonResponse(events, safe=False)


@login_required
def today_view(request):
    """รายการงานของวันนี้ ตามที่ระบุใน Scope"""
    today = date.today()
    tasks = Task.objects.filter(owner=request.user, date=today).order_by("start_time")
    overdue = Task.objects.filter(
        owner=request.user, date__lt=today, is_done=False
    ).order_by("date", "start_time")
    return render(
        request,
        "tasks/today.html",
        {"today": today, "tasks": tasks, "overdue": overdue},
    )


@login_required
def task_list(request):
    """รายการงานทั้งหมดแบบ list ธรรมดา เรียงตามวันที่"""
    tasks = Task.objects.filter(owner=request.user)
    return render(request, "tasks/task_list.html", {"tasks": tasks})


@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    return render(request, "tasks/task_detail.html", {"task": task})


@login_required
def task_create(request):
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.owner = request.user
            task.save()
            messages.success(request, "เพิ่มงานแล้ว")
            return redirect("tasks:calendar")
    else:
        form = TaskForm()
    return render(request, "tasks/task_form.html", {"form": form, "mode": "create"})


@login_required
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "บันทึกการแก้ไขแล้ว")
            return redirect("tasks:detail", pk=task.pk)
    else:
        form = TaskForm(instance=task)
    return render(request, "tasks/task_form.html", {"form": form, "mode": "edit", "task": task})


@login_required
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    task.delete()
    messages.info(request, "ลบงานแล้ว")
    return redirect("tasks:list")


@login_required
@require_POST
def task_toggle_done(request, pk):
    """กดติ๊กว่าทำเสร็จแล้ว ใช้ทั้งในหน้า today และหน้า list"""
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    task.is_done = not task.is_done
    task.save(update_fields=["is_done", "updated_at"])
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"is_done": task.is_done})
    return redirect(request.META.get("HTTP_REFERER", "tasks:today"))
