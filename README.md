
โปรเจกต์ส่วน Personal Planner (Increment 1) ของกลุ่มหมูบด เขียนด้วย Django ตามที่วางแผนไว้ในเอกสาร SRS

ตอนนี้ทำได้ครบตามเป้าหมายของ Increment 1 คือให้ผู้ใช้จัดตารางงานของตัวเองได้ครบวงจร มีระบบสมัคร/ล็อกอิน มีปฏิทิน เพิ่ม-แก้-ลบงานได้ และดูงานของวันนี้ได้

## ใช้อะไรทำบ้าง

- Backend: Django (Python)
- Database: SQLite ตอนพัฒนา จะสลับเป็น PostgreSQL ตอน deploy จริง
- Frontend: Django Template + Tailwind CSS
- ปฏิทิน: FullCalendar.js

## โครงสร้างไฟล์

```
goodplanner/
├── config/          → settings, urls หลักของโปรเจกต์
├── accounts/        → สมัคร/ล็อกอิน/โปรไฟล์
├── tasks/           → งานส่วนตัว, ปฏิทิน, งานวันนี้
├── templates/       → หน้าเว็บส่วนกลาง
├── requirements.txt
└── manage.py
```

## วิธีรัน

```bash
python -m venv .venv
source .venv/bin/activate      # ถ้าใช้ Windows พิมพ์ .venv\Scripts\activate แทน

pip install -r requirements.txt
cp .env.example .env

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser

python manage.py runserver
```

เปิด `http://127.0.0.1:8000/` จะเข้าหน้าปฏิทิน ถ้ายังไม่ได้ล็อกอินระบบจะพาไปหน้า login เอง

## เช็คว่าใช้ได้จริงยังไง

- สมัครสมาชิกใหม่ → เข้าปฏิทินอัตโนมัติ
- เพิ่มงาน ต้องขึ้นในปฏิทินทันที สีตามระดับความสำคัญ
- ดูหน้า "วันนี้" ต้องเห็นงานของวันนั้น
- แก้ไข/ลบงานได้
- ล็อกเอาต์แล้วพิมพ์ URL ปฏิทินตรง ๆ ต้องเด้งกลับหน้า login
- รีเฟรชหรือปิดเปิดใหม่ ข้อมูลต้องยังอยู่ (เก็บในฐานข้อมูลจริง ไม่ใช่แค่ session)

## ถ้าจะสลับเป็น PostgreSQL

แก้ใน `.env`:
```
DB_ENGINE=postgres
DB_NAME=goodplanner
DB_USER=goodplanner_user
DB_PASSWORD=...
DB_HOST=localhost
DB_PORT=5432
```
แล้วรัน `python manage.py migrate` อีกรอบ

## หมายเหตุ

ส่วน Group / Matching / Notification เป็น Increment ถัดไปตามแผน ยังไม่ได้ทำในรอบนี้ เพราะรอบนี้ scope แค่ Personal Planner ตามที่ระบุไว้
