"""
ฟอร์มของแอป accounts
ใช้ email เป็น username ภายใน (แต่ผู้ใช้กรอกแค่ช่องอีเมลช่องเดียว ไม่ต้องคิดชื่อผู้ใช้แยก)
กฎรหัสผ่านขั้นต่ำ 8 ตัวอักษร ถูกบังคับผ่าน AUTH_PASSWORD_VALIDATORS ใน settings.py แล้ว
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

User = get_user_model()

INPUT_CLASS = (
    "w-full rounded-md border border-slate-300 px-3 py-2 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
)


class RegisterForm(UserCreationForm):
    display_name = forms.CharField(
        label="ชื่อที่แสดง",
        max_length=100,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "เช่น ณภัทร"}),
    )
    email = forms.EmailField(
        label="อีเมล",
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "you@example.com"}),
    )

    class Meta:
        model = User
        fields = ("display_name", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"class": INPUT_CLASS})
        self.fields["password2"].widget.attrs.update({"class": INPUT_CLASS})
        self.fields["password1"].label = "รหัสผ่าน"
        self.fields["password2"].label = "ยืนยันรหัสผ่าน"
        # ตัด help text แบบยาวของ Django ออก ใช้ข้อความสั้นแทนใน template
        self.fields["password1"].help_text = None
        self.fields["password2"].help_text = None

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("อีเมลนี้ถูกใช้สมัครไปแล้ว")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]  # ใช้ email แทน username ภายใน
        user.first_name = self.cleaned_data["display_name"]
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(AuthenticationForm):
    """ฟอร์ม login ที่ผู้ใช้กรอกอีเมลแทนชื่อผู้ใช้ (ภายในยัง map ไปที่ username เดิม)"""

    username = forms.EmailField(
        label="อีเมล",
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "you@example.com", "autofocus": True}),
    )
    password = forms.CharField(
        label="รหัสผ่าน",
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": "รหัสผ่าน"}),
    )

    error_messages = {
        "invalid_login": "อีเมลหรือรหัสผ่านไม่ถูกต้อง",
        "inactive": "บัญชีนี้ถูกระงับการใช้งาน",
    }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "email")
        labels = {"first_name": "ชื่อที่แสดง", "email": "อีเมล"}
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASS}),
        }
