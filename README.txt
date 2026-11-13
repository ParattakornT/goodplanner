GoodPlanner — Django / Python / SQLite

เริ่มใช้งาน
1. Django 5.2.18 รองรับ Python 3.10–3.14; โปรเจกต์นี้ทดสอบด้วย Python 3.13
   แนะนำ Python 3.13 หรือ 3.14 รุ่นแพตช์ล่าสุดสำหรับการติดตั้งใหม่
2. ดับเบิลคลิก start.cmd แล้วเปิด http://localhost:3000/login.html
   ครั้งแรกจะติดตั้งแพ็กเกจจาก requirements.txt ใน .venv จึงต้องต่ออินเทอร์เน็ต
   เรียก setup.cmd แยกได้เมื่อต้องติดตั้งใหม่; ถ้า .venv เดิมเสียหรือคัดลอกมาจากเครื่องอื่น
   setup.cmd จะสร้าง environment ใหม่จาก Python ที่ติดตั้งอยู่ ไม่ต้องใช้ Node.js
3. เปิดหน้าต่างเซิร์ฟเวอร์ค้างไว้ระหว่างใช้งาน กด Ctrl+C เพื่อหยุด
4. สมัครสมาชิกแล้วเข้าสู่ระบบ เลือกวันและเพิ่ม/แก้ไข/ลบ/ทำเครื่องหมายงานเสร็จได้
   การเปิด HTML แบบ file:// หรือ Live Server อย่างเดียวจะเรียก backend ไม่ได้

เปิดใช้ Google Login
1. สร้าง OAuth Client ID แบบ Web application ใน Google Cloud Console
   เพิ่ม Authorized redirect URI: http://localhost:3000/auth/google/callback
2. เปิด PowerShell ในโฟลเดอร์โปรเจกต์ แล้วกำหนดค่าก่อนเปิดเซิร์ฟเวอร์:
   $env:GOOGLE_CLIENT_SECRET="ค่า Client Secret"
   .\start.cmd
   Client ID ที่ตั้งไว้ในโปรเจกต์แล้ว; กำหนด GOOGLE_CLIENT_ID เฉพาะเมื่อต้องการเปลี่ยน
   Client Secret อยู่ในหน้าต่าง PowerShell ปัจจุบันเท่านั้น และห้ามใส่ในไฟล์โค้ด
3. เปิด http://localhost:3000/login.html แล้วกด “ดำเนินการต่อด้วย Google”
   สำหรับโดเมน/HTTPS ที่ไม่ใช่ localhost ให้กำหนด GOOGLE_REDIRECT_URI ให้ตรงกับ
   Authorized redirect URI ใน Google Cloud Console ด้วย

เปิดด้วยคำสั่งเองบน Windows (ไม่ต้องใช้ start.cmd หรือ setup.cmd)
1. ติดตั้ง Python จาก https://www.python.org/downloads/windows/
   ใช้ Python 3.13 ตามรุ่นที่ทดสอบไว้ หรือ 3.14 ได้ ไม่ได้จำกัดเฉพาะ 3.13
   ถ้าตัวติดตั้งมีตัวเลือก Add Python to PATH ให้เลือกด้วย
2. แตก ZIP แล้วเปิดโฟลเดอร์ที่มี manage.py และ requirements.txt ใน VS Code
   เลือก Terminal > New Terminal และใช้ PowerShell
3. รันทีละบรรทัด รอให้แต่ละคำสั่งสำเร็จก่อนทำบรรทัดถัดไป
   python --version
   python -m venv .venv-local
   .\.venv-local\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv-local\Scripts\python.exe manage.py migrate --noinput
   .\.venv-local\Scripts\python.exe manage.py import_legacy
   .\.venv-local\Scripts\python.exe manage.py runserver 127.0.0.1:3000
4. เปิด http://localhost:3000/login.html แล้วเข้าสู่ระบบ
   เปิด Terminal ค้างไว้ระหว่างใช้งาน กด Ctrl+C เมื่อจะหยุด

คำสั่งติดตั้งจาก requirements.txt จะดาวน์โหลด Django และแพ็กเกจที่ต้องใช้ให้ครบ
SQLite มากับ Python อยู่แล้ว ไม่ต้องติดตั้งฐานข้อมูลแยก
หากเครื่องใช้คำสั่ง py แทน python ได้ ให้ใช้ py -3.13 --version และ
py -3.13 -m venv .venv-local แทนสองบรรทัดแรก ที่เหลือใช้คำสั่งเดิม
ถ้าติดตั้ง Python 3.14 ให้เปลี่ยน -3.13 เป็น -3.14 ในคำสั่ง py
สร้าง .venv-local ใหม่บนเครื่องเพื่อนเสมอ ไม่ใช้ .venv ที่คัดลอกมาจากเครื่องอื่น
ไม่ต้อง activate สภาพแวดล้อมหรือเปลี่ยน Execution Policy สำหรับวิธีนี้
ถ้านำข้อมูล Django ที่ย้ายแล้วมาด้วย import_legacy จะข้ามการนำเข้าให้อัตโนมัติ
ถ้าไม่มี data ระบบจะสร้างฐานข้อมูลใหม่ แล้วสมัครบัญชีเพื่อใช้งานได้
ครั้งต่อไปเปิด Terminal ในโฟลเดอร์เดิมแล้วรันเฉพาะบรรทัด runserver
หลังรับโค้ดรุ่นใหม่ ให้ติดตั้ง requirements.txt และรัน migrate อีกครั้งก่อนเปิดเว็บ
ส่งต่อโปรเจกต์ได้โดยเว้น .venv/, .venv-local/ และ __pycache__/
start.cmd และ setup.cmd เป็นตัวช่วยเสริม จะไม่แนบไปกับ ZIP ก็ได้

ย้ายจากระบบ Node เดิม
- start.cmd เรียก migrate และ import_legacy อัตโนมัติก่อนเปิดเว็บ
- ฐานข้อมูลที่ใช้งานจริงหลังย้าย: data/goodplanner-django.sqlite3
- data/goodplanner.sqlite คือฐานข้อมูล Node เดิม เก็บไว้และไม่มีการเขียนทับ
- สำรองข้อมูลเดิมรวมข้อมูลที่อยู่ใน WAL ด้วย SQLite backup ที่ data/backups/
- คัดลอกบัญชี แผน รหัสเจ้าของ วันที่ เวลา สถานะ และเวลาสร้าง/แก้ไขเดิม
- ใช้อีเมลและรหัสผ่านเดิมได้ แต่ต้องเข้าสู่ระบบใหม่หลังเปลี่ยน backend
- ตรวจรหัสผ่าน scrypt เดิมได้ เมื่อเข้าสู่ระบบสำเร็จ Django เปลี่ยนเป็น PBKDF2
- นำเข้าเพียงครั้งเดียว มีบันทึก LegacyImport ป้องกันการนำเข้าทับแผนที่แก้ไขใหม่
- หากฐาน Django มีบัญชีแล้วแต่ยังไม่เคยนำเข้า คำสั่งจะหยุดเพื่อไม่ทับข้อมูล
- ไฟล์ backend และชุดทดสอบ Node เดิมถูกลบแล้ว ใช้ Django เป็น backend เดียว

โครงสร้างสำหรับพัฒนาต่อ
- manage.py: คำสั่งจัดการ Django
- goodplanner/settings.py: การตั้งค่า Django, SQLite, session และ CSRF
- goodplanner/urls.py: เส้นทางหน้าเว็บและ API
- planner/models.py: บัญชี แผนส่วนตัว กลุ่ม สมาชิก เวลาไม่ว่าง งานกลุ่ม นัดหมาย และการแจ้งเตือน ผ่าน Django ORM
- planner/views.py: สมัครสมาชิก เข้าสู่ระบบ และ API จัดการแผนส่วนตัว
- planner/group_views.py: API กลุ่มและตรวจสิทธิ์เจ้าของ/สมาชิก
- planner/group_services.py: รวมเวลาไม่ว่างและคำนวณเวลาว่างร่วมตลอดช่วงนัด
- planner/migrations/: ประวัติการสร้าง/เปลี่ยนตารางฐานข้อมูล
- planner/hashers.py: รองรับรหัสผ่านจากระบบ Node เดิม
- planner/management/commands/import_legacy.py: สำรองและนำเข้าฐานเดิม
- planner/tests.py: ทดสอบระบบบัญชี แผน สิทธิ์เจ้าของ CSRF และการย้ายข้อมูล
- planner/test_groups.py: ทดสอบสมาชิก สิทธิ์งาน เวลาว่าง นัดชนกัน และข้อมูลส่วนตัว
- planner/test_scheduling.py: ทดสอบรอบการนัด สถานะว่างแน่/ไม่แน่ใจ/ไม่ว่าง และกรณีไม่มีวันว่างตรงกัน
- web/pages/: login.html, register.html, dashboard.html, groups.html หน้าเว็บที่ Django render
- web/partials/workspace-sidebar.html: เมนูร่วมของแผนส่วนตัวและแผนงานกลุ่ม
- web/partials/auth-story.html: ส่วนแนะนำเว็บที่ใช้ร่วมกันในหน้าล็อกอินและสมัครสมาชิก
- web/css/workspace.css: สี ตัวอักษร และเมนูที่ใช้ร่วมกันทั้งเว็บ
- web/css/ และ web/js/: ตกแต่งและการทำงานแต่ละหน้า (login, planner, dashboard, groups)
- web/js/theme.js และ web/css/theme-dark.css: สลับโหมดมืด/สว่าง ไฟล์ theme-dark.css สร้างอัตโนมัติ ห้ามแก้มือ
- tools/make_dark_theme.py: สร้าง theme-dark.css ใหม่หลังแก้สีในไฟล์ css อื่น
- DEPLOY.txt, Procfile, requirements-prod.txt: สำหรับนำเว็บขึ้นใช้งานจริง
  URL ของเว็บไม่เปลี่ยน (/login.html, /groups.css ฯลฯ) views.py เป็นตัวจับคู่ไปยังโฟลเดอร์ web/
  ทีม frontend แก้ไฟล์เหล่านี้ได้ โดยคง id, data-* และรูปแบบ API ที่ใช้ร่วมกัน
  หลังแก้ HTML ให้เริ่มเซิร์ฟเวอร์ใหม่เพื่อเคลียร์ template cache

คำสั่งใน PowerShell (จากโฟลเดอร์โปรเจกต์)
  .\.venv\Scripts\python.exe manage.py check
  .\.venv\Scripts\python.exe manage.py test planner
  .\.venv\Scripts\python.exe manage.py makemigrations
  .\.venv\Scripts\python.exe manage.py migrate
  .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:3000
การทดสอบใช้ฐานข้อมูลชั่วคราวของ Django แยกจากบัญชีจริง
GOODPLANNER_DB ใช้ระบุฐานข้อมูลอื่นสำหรับการทดสอบ/พัฒนาได้

API เดิม (JSON)
POST /api/register: displayName, email, password, confirmPassword
POST /api/login: email, password
GET /api/me: บัญชีที่เข้าสู่ระบบ
POST /api/logout: {}
GET /api/tasks?month=2026-10: งานของบัญชีปัจจุบันในเดือนที่เลือก
POST /api/tasks: title, date, notes, time, endTime, priority, completed
PATCH /api/tasks/:id: ฟิลด์ที่ต้องการแก้ไข
DELETE /api/tasks/:id: ลบงาน
ทุกคำขอที่แก้ข้อมูลต้องส่ง X-CSRFToken จากคุกกี้ goodplanner_csrftoken
หน้า login/register/dashboard/groups จะตั้งคุกกี้ให้อัตโนมัติ เปิดหน้าเว็บก่อนเรียก API
session เก็บในฐานข้อมูล คุกกี้ HttpOnly / SameSite Strict อายุ 7 วัน
รหัสเจ้าของงานอิงจากผู้ใช้ที่ล็อกอิน ไม่รับ user_id จากหน้าเว็บ
วันที่งาน YYYY-MM-DD (ค.ศ. 1900–2100), เวลา HH:mm หรือว่าง; หน้าจอแสดงปี พ.ศ.

แผนงานกลุ่ม
1. เข้าสู่ระบบด้วยบัญชีเดิม แล้วกดเมนูแผนงานกลุ่ม หรือเปิด http://localhost:3000/groups.html
2. สร้างกลุ่ม ระบุช่วงวันที่นัด (ไม่เกิน 366 วัน) ระยะเวลาทำงาน และวัน/เวลาปิดรับ
   เช่น นัดช่วง 1–7 พ.ย. ทำงานครั้งละ 180 นาที (3 ชั่วโมง) ปิดรับ 29 ต.ค. เวลา 23:59
   ระยะเวลา 30–720 นาที เพิ่มครั้งละ 15 นาที หัวหน้าเลือกเวลาเริ่มภายหลังจากดูเวลาของสมาชิก
   กลุ่มใหม่เลือกนัดได้ตลอดวัน โดยนัดต้องจบภายในวันเดียวกัน (จบ 24:00 ได้)
   วันปิดรับต้องอยู่ในอนาคตและก่อนวันแรกที่นัดได้ โดยใช้เวลา Asia/Bangkok
3. ส่งรหัสกลุ่ม 10 ตัวให้เพื่อน เพื่อนสมัคร/เข้าสู่ระบบแล้วกรอกรหัสเข้าร่วม (สูงสุด 50 สมาชิก)
4. ในแท็บเวลาที่ไม่ว่าง สมาชิกกรอกช่วงเวลาหรือเลือกทั้งวัน แล้วกดยืนยันว่ากรอกครบแล้ว
   คนที่ยังไม่ยืนยันจะแสดงว่ายังไม่ทราบเวลา ไม่ถือว่าเป็นคนว่าง
   เมื่อถึงวันปิดรับ ระบบห้ามเพิ่ม/ลบ/เปลี่ยนเวลาและการยืนยัน รวมถึงรับสมาชิกใหม่ที่ API ด้วย
   สมาชิกเดิมยังเข้าอ่านข้อมูลได้ และหัวหน้าจะเริ่มสร้างนัดได้หลังปิดรับ
   เลือกนำเวลาแผนส่วนตัวมาคิดได้เป็นรายกลุ่ม โดยไม่แสดงชื่องานหรือรายละเอียดให้สมาชิกอื่นเห็น
   กลุ่มที่มีวันปิดรับจะนำเข้าช่วงเวลาส่วนตัว ณ ตอนเปิดแชร์หรือยืนยันว่ากรอกครบ
   ถ้าแผนส่วนตัวเปลี่ยน ต้องยืนยันอีกครั้งก่อนปิดรับ ข้อมูลที่ส่งแล้วไม่เปลี่ยนตามภายหลัง
   งานส่วนตัวที่ระบุเวลาเริ่มแต่ไม่มีเวลาจบจะนับเป็นเวลาไม่ว่าง 30 นาที (ไม่ข้ามเที่ยงคืน)
5. ปฏิทินแสดงวันที่มีคนไม่ว่าง กดแต่ละวันเพื่อดูรายชื่อ ช่วงเวลาแบบละเอียด และเส้นเวลา
   คนที่ไม่ยืนยันยังถือว่าไม่ทราบเวลา ไม่ใช่คนว่าง
6. แท็บวันนัดของกลุ่มแสดงวันและเวลาปิดรับ ขณะยังเปิดรับเวลาไม่ว่าง
   หลังปิดรับ หัวหน้ามีปุ่มเลือกวันและเวลานัด สมาชิกเห็นสถานะรอหัวหน้าเลือก
   หัวหน้าเลือกวัน เวลาเริ่ม และผู้เข้าร่วมได้ เวลาสิ้นสุดคำนวณตามระยะเวลาของกลุ่ม
   เมื่อบันทึกแล้ว ทุกคนเห็นสถานะหัวหน้าเลือกวันนัดแล้ว พร้อมวัน เวลา และผู้เข้าร่วมแต่ละนัด
   ระบบตรวจเวลาชนก่อนบันทึก ถ้าชนจะแสดงรายชื่อและช่วงเวลา หากยังไม่ยืนยันเวลาจะเตือนด้วย
   หัวหน้าติ๊กยอมรับคำเตือน แล้วกดยืนยันอีกครั้งเพื่อสร้างนัดได้
   การยืนยันผูกกับนัดและข้อมูลที่ตรวจล่าสุด มีอายุ 5 นาที หากข้อมูลเปลี่ยนจะต้องยืนยันคำเตือนใหม่
   นัดหมายในกลุ่มอื่นของผู้เข้าร่วมจะถูกนับเป็นเวลาไม่ว่างด้วย โดยไม่เปิดเผยรายละเอียดกลุ่มอื่น
7. กระดานงานแบ่งเป็น รอเริ่ม / กำลังทำ / เสร็จแล้ว เจ้าของมอบหมาย แก้ไข หรือลบงานได้
   สมาชิกเปลี่ยนสถานะได้เฉพาะงานที่ตัวเองได้รับ งานและนัดแสดงในแผนส่วนตัวโดยอัตโนมัติ
   รายการเหล่านี้อ้างอิงต้นฉบับในกลุ่ม ไม่สร้างสำเนา Task; กดกลับไปแก้ที่หน้ากลุ่ม
8. ปุ่มแจ้งเตือนแสดงงานที่ได้รับ นัดหมาย และคำเตือนให้กรอกเวลา เจ้าของส่งเตือนได้ชั่วโมงละครั้ง
   เป็นการแจ้งเตือนในเว็บ ไม่มีอีเมลหรือ push; กดอัปเดตข้อมูลเพื่อโหลดการเปลี่ยนแปลงของเพื่อน

ทุกคนต้องเชื่อมต่อเซิร์ฟเวอร์และฐานข้อมูลเดียวกันจึงจะวางแผนร่วมกันได้
localhost หมายถึงเครื่องของแต่ละคน การส่ง ZIP แล้วต่างคนต่างเปิดจะได้ฐานข้อมูลแยกกัน ไม่ซิงก์ข้ามเครื่อง
รุ่นนี้เปิดใช้งานในเครื่อง หากจะใช้ร่วมกันต่างเครื่องต้องตั้งค่าเซิร์ฟเวอร์เพิ่มเติม

ตาราง SQLite ที่เพิ่มใน data/goodplanner-django.sqlite3
- planner_planninggroup: กลุ่ม ช่วงวันที่ เวลานัด รหัสเชิญ เจ้าของ duration_minutes และ availability_deadline
- planner_membership: สมาชิกกลุ่ม การยืนยันเวลา และการแชร์เวลาจากแผนส่วนตัว
- planner_busyslot: เวลาไม่ว่างของสมาชิกแต่ละวัน
- planner_grouptask: งานที่มอบหมาย กำหนดส่ง และสถานะ
- planner_meeting / planner_meeting_participants: นัดหมายและผู้เข้าร่วม
- planner_notification: การแจ้งเตือนและเวลาอ่าน
- planner_task เพิ่ม end_time สำหรับเวลาสิ้นสุดงานส่วนตัว
migration 0002 เพิ่มตารางกลุ่ม; 0003 เพิ่มระยะเวลา วันปิดรับ สำเนาช่วงเวลาส่วนตัว และประวัติยืนยันคำเตือน
ใช้ manage.py migrate เพื่ออัปเดต SQLite โดยคงบัญชีและข้อมูลเดิมไว้
กลุ่มเดิมก่อน 0003 ยังไม่มีวันปิดรับและคงระยะเวลาเริ่มต้น 60 นาที สร้างกลุ่มใหม่เพื่อใช้รอบนัดแบบมีวันปิดรับ

API กลุ่ม (JSON, ต้องเข้าสู่ระบบ และคำขอแก้ไขต้องมี CSRF)
GET /api/groups: กลุ่มที่ผู้ใช้เป็นสมาชิก
POST /api/groups: name, startDate, endDate, durationMinutes, availabilityDeadline
ไม่ต้องส่ง start/end; ค่าเริ่มต้นเป็นทั้งวัน 0–1440 นาที (ยังรับ start/end คู่กันเพื่อรองรับโปรแกรมรุ่นก่อน)
availabilityDeadline เป็น ISO 8601 พร้อม offset เช่น 2026-10-29T23:59:00+07:00
POST /api/groups/join: code
GET /api/groups/:id: รายละเอียดกลุ่ม สมาชิก งาน และนัดหมาย
DELETE /api/groups/:id: เจ้าของลบกลุ่ม รวมข้อมูลภายในกลุ่ม
GET /api/groups/:id/availability: ปฏิทินและช่วงว่างร่วม ใช้ durationMinutes ของกลุ่ม
เฉพาะกลุ่มเก่าที่ไม่มีวันปิดรับ ยังรับ ?duration=60 แบบเดิมได้
PATCH /api/groups/:id/preferences: sharePersonal และ/หรือ confirmed (boolean)
POST /api/groups/:id/busy: date, start, end
DELETE /api/groups/:id/busy/:slotId: ลบช่วงเวลาไม่ว่างของตัวเอง
POST /api/groups/:id/tasks: title, notes, date, time, assigneeId
PATCH /api/groups/:id/tasks/:taskId: เจ้าของแก้รายละเอียด; ผู้รับผิดชอบแก้ status ได้
DELETE /api/groups/:id/tasks/:taskId: เจ้าของลบงาน
POST /api/groups/:id/meetings: title, date, start, end, participants; ส่ง confirmationToken เพิ่มเมื่อยืนยันคำเตือน
ถ้าชนจะตอบ HTTP 409 พร้อม code=meeting_conflict, conflicts, unconfirmed, confirmationToken
ยังไม่สร้างนัดจนกว่าจะยืนยัน และเก็บ acknowledgement ไว้ในรายการนัดเมื่อหัวหน้ายืนยันแล้ว
DELETE /api/groups/:id/meetings/:meetingId: เจ้าของยกเลิกนัด
POST /api/groups/:id/remind: {} เจ้าของเตือนสมาชิกที่ยังไม่ยืนยันเวลา
GET /api/group-feed?month=2026-10: งานที่ได้รับและนัดที่เข้าร่วมสำหรับหน้าแผนส่วนตัว
GET /api/notifications: การแจ้งเตือนของผู้ใช้
PATCH /api/notifications: {} ทำเครื่องหมายว่าอ่านทั้งหมด
start/end เป็นจำนวนนาทีหลังเที่ยงคืน 0–1440; start < end; time เป็น HH:mm หรือว่าง
assigneeId และ participants ใช้รหัส Membership ภายในกลุ่ม ไม่ใช่รหัส User
status ใช้ todo / doing / done

ข้อมูลที่ไม่ควรส่งให้ทีม frontend หรืออัปโหลด Git
 data/ (บัญชี แผน session รหัสผ่านแฮช สำเนาฐาน และ secret key), .venv/, .env
หากสำรองงานจริง ให้หยุดเซิร์ฟเวอร์ก่อนคัดลอกทั้งโฟลเดอร์ data

ขอบเขตปัจจุบัน
ใช้ Django 5.2 LTS, Python, Django ORM และ SQLite สำหรับทำงานในเครื่อง
มีการแจ้งเตือนภายในเว็บและ Google Login (ต้องกำหนด GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET);
ยังไม่มี PostgreSQL, อีเมลแจ้งเตือน หรือส่งเมลรีเซ็ตรหัสผ่าน
จำกัดสมัคร/ล็อกอินรวม 30 ครั้งต่อ 15 นาทีต่อ IP ในหน่วยความจำของ process
ก่อนเปิดสาธารณะต้องจัดการ hosting, HTTPS, ALLOWED_HOSTS, secret จาก environment,
ฐานข้อมูล/สำรอง และ rate limit แบบใช้ร่วมกันหลาย process; ไม่ใช้ runserver เป็น production
DJANGO_SECRET_KEY กำหนด secret ผ่าน environment ได้; ค่าในเครื่องสร้างที่ data/.django-secret-key
DJANGO_HTTPS=1 เปิด Secure cookie เมื่อให้บริการผ่าน HTTPS

เอกสาร Django: https://docs.djangoproject.com/en/5.2/
