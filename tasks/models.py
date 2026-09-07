from django.conf import settings
from django.db import models
from django.urls import reverse


class Task(models.Model):
    """
    งานส่วนตัว (Personal Task) — Increment 1 ตามแผน
    ฟิลด์ตรงตามที่ระบุใน Scope: ชื่องาน, วัน-เวลาเริ่ม-จบ, รายละเอียด, ระดับความสำคัญ
    """

    class Priority(models.TextChoices):
        HIGH = "high", "สูง"
        MID = "mid", "กลาง"
        LOW = "low", "ต่ำ"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField("ชื่องาน", max_length=200)
    description = models.TextField("รายละเอียด", blank=True)
    date = models.DateField("วันที่")
    start_time = models.TimeField("เวลาเริ่ม")
    end_time = models.TimeField("เวลาสิ้นสุด")
    priority = models.CharField(
        "ความสำคัญ", max_length=10, choices=Priority.choices, default=Priority.MID
    )
    is_done = models.BooleanField("ทำเสร็จแล้ว", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "start_time"]
        indexes = [
            models.Index(fields=["owner", "date"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.date})"

    def get_absolute_url(self):
        return reverse("tasks:detail", args=[self.pk])

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม"})
