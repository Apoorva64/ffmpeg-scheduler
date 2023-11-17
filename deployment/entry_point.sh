#!/bin/sh

python3 manage.py migrate
python3 manage.py create_admin
gunicorn ffmpeg_scheduler.wsgi:application --bind 0.0.0.0:8000 --timeout 120