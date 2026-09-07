"""
Views ของแอป accounts
ครอบคลุม FR ตามเอกสาร SRS: สมัครสมาชิก, เข้าสู่ระบบ, ออกจากระบบ, แก้ไขโปรไฟล์
Route guard ("หน้าที่ต้องล็อกอินก่อน") ใช้ @login_required ของ Django ตรงๆ
"""
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy

from .forms import RegisterForm, EmailAuthenticationForm, ProfileForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect("tasks:calendar")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"สมัครสมาชิกสำเร็จ ยินดีต้อนรับ {user.first_name}")
            return redirect("tasks:calendar")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


class EmailLoginView(LoginView):
    """หน้าเข้าสู่ระบบ ใช้ template และฟอร์มที่ปรับให้กรอกอีเมล"""

    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


def logout_view(request):
    logout(request)
    messages.info(request, "ออกจากระบบแล้ว")
    return redirect("accounts:login")


@login_required
def profile_view(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "บันทึกโปรไฟล์แล้ว")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "accounts/profile.html", {"form": form})
