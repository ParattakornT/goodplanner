web: python manage.py migrate --noinput && gunicorn goodplanner.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 60
