celery -A ffmpeg_scheduler beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
celery -A ffmpeg_scheduler worker --loglevel=info 