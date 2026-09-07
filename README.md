# Good Planner — Increment 1: Personal Planner

โค้ด Django ตามแผน Tools ที่ระบุไว้ (Backend: Django + Django ORM, Database: SQLite ตอนพัฒนา / PostgreSQL ตอน Production, Frontend: Django Template + Tailwind CSS + FullCalendar.js)

ครอบคลุมตามเป้าหมาย Increment 1 ในแผน: **"ผู้ใช้จัดตารางงานของตัวเองได้ครบวงจร"**
- ระบบ Authentication (สมัคร / เข้าสู่ระบบ / ออกจากระบบ / แก้โปรไฟล์)
- CRUD งานส่วนตัวครบ (สร้าง / ดู / แก้ไข / ลบ)
- หน้าปฏิทิน (เดือน/สัปดาห์) ด้วย FullCalendar.js
- รายการงานวันนี้ + งานที่เลยกำหนด

## โครงสร้างโปรเจกต์

```
goodplanner/
├── config/              ← ตั้งค่าโปรเจกต์ (settings, urls หลัก)
├── accounts/             ← แอป Authentication
│   ├── forms.py, views.py, urls.py, models.py
│   └── templates/accounts/
├── tasks/                 ← แอปงานส่วนตัว (Increment 1)
│   ├── models.py          ← Model Task
│   ├── forms.py, views.py, urls.py, admin.py
│   └── templates/tasks/
├── templates/base.html    ← Layout กลาง (Tailwind CDN)
├── requirements.txt
├── .env.example            ← คัดลอกเป็น .env แล้วแก้ค่า
└── manage.py
```

## วิธีติดตั้งและรัน (ครั้งแรก)

```bash
# 1) สร้างและเปิดใช้ virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows ใช้ .venv\Scripts\activate

# 2) ติดตั้งไลบรารี
pip install -r requirements.txt

# 3) ตั้งค่า environment
cp .env.example .env
# (ไม่ต้องแก้อะไรถ้าจะรันแบบ SQLite ตอนพัฒนา)

# 4) สร้างตารางฐานข้อมูล
python manage.py makemigrations
python manage.py migrate

# 5) สร้างบัญชี admin (ไว้เข้า /admin/ ดูข้อมูลดิบได้)
python manage.py createsuperuser

# 6) รันเซิร์ฟเวอร์
python manage.py runserver
```

เปิดเบราว์เซอร์ไปที่ `http://127.0.0.1:8000/` จะเด้งไปหน้าปฏิทิน ถ้ายังไม่ล็อกอินจะเด้งไปหน้า login อัตโนมัติ (route guard ผ่าน `@login_required`)

## ทดสอบตาม Deliverable ของ Increment 1

1. เข้า `/accounts/register/` สมัครสมาชิกด้วยอีเมล/รหัสผ่าน (รหัสต้องยาวอย่างน้อย 8 ตัว ไม่งั้น Django validator จะฟ้อง)
2. ระบบพาเข้าหน้าปฏิทินทันที (login อัตโนมัติหลังสมัคร)
3. กด **+ เพิ่มงาน** กรอกครบทุกช่อง (ชื่องาน, วันที่, เวลาเริ่ม-จบ, ความสำคัญ) → บันทึก
4. งานต้องขึ้นในปฏิทินทันที (สีต่างกันตามความสำคัญ)
5. ไปหน้า **วันนี้** ถ้าใส่วันที่เป็นวันนี้ ต้องเห็นงานนั้นในรายการ
6. กดเข้าไปในงาน → ลอง **แก้ไข** และ **ลบ** ดู ต้องทำงานได้ทั้งคู่
7. กด **ออกจากระบบ** แล้วพิมพ์ URL `/tasks/calendar/` ตรงๆ โดยไม่ล็อกอิน → ต้องถูกเด้งกลับไปหน้า login (พิสูจน์ route guard)
8. รีเฟรชหน้า / ปิดเปิดเบราว์เซอร์ใหม่ แล้วล็อกอินอีกครั้ง → งานต้องยังอยู่ครบ (พิสูจน์ว่าบันทึกจริงในฐานข้อมูล ไม่ใช่แค่ session)

## สลับไปใช้ PostgreSQL (ตอน Deploy)

แก้ค่าในไฟล์ `.env`:
```
DB_ENGINE=postgres
DB_NAME=goodplanner
DB_USER=goodplanner_user
DB_PASSWORD=รหัสผ่านของคุณ
DB_HOST=localhost
DB_PORT=5432
```
แล้วรัน `python manage.py migrate` ใหม่อีกครั้งเพื่อสร้างตารางใน PostgreSQL

## หมายเหตุสำคัญ

- โค้ดชุดนี้ยังไม่ได้รันทดสอบจริงในเครื่อง Claude เพราะแซนด์บ็อกซ์นี้เชื่อมต่อ pypi.org ไม่ได้ (เครือข่ายถูกปิด) — **ต้องรันทดสอบเองตามขั้นตอนด้านบนก่อนส่งอาจารย์**
- ไวยากรณ์ Python ทุกไฟล์ผ่านการตรวจด้วย `py_compile` แล้ว และ Django template tag ทุกไฟล์ตรวจสมดุล open/close แล้ว แต่ยังไม่เท่ากับการรันจริงผ่าน `runserver`
- ฟีเจอร์ Group / Matching / Notification (Increment 2-4 ในแผน) ยังไม่ได้ทำในชุดนี้ เพราะขอบเขตตามแผนคือ Increment 1 เท่านั้น
