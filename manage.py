#!/usr/bin/env python
"""จุดเริ่มต้นคำสั่ง Django (runserver, migrate, createsuperuser ฯลฯ)"""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "ไม่พบ Django ตรวจสอบว่าติดตั้งแล้วหรือยัง (pip install -r requirements.txt) "
            "และเปิดใช้ virtual environment แล้วหรือยัง"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
