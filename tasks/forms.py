from django import forms
from .models import Task

INPUT_CLASS = (
    "w-full rounded-md border border-slate-300 px-3 py-2 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
)


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "date", "start_time", "end_time", "priority"]
        labels = {
            "title": "ชื่องาน",
            "description": "รายละเอียด",
            "date": "วันที่",
            "start_time": "เวลาเริ่ม",
            "end_time": "เวลาสิ้นสุด",
            "priority": "ความสำคัญ",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "เช่น อ่านหนังสือสอบ"}),
            "description": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
            "date": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
            "start_time": forms.TimeInput(attrs={"class": INPUT_CLASS, "type": "time"}),
            "end_time": forms.TimeInput(attrs={"class": INPUT_CLASS, "type": "time"}),
            "priority": forms.Select(attrs={"class": INPUT_CLASS}),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_time"), cleaned.get("end_time")
        if start and end and end <= start:
            self.add_error("end_time", "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม")
        return cleaned
