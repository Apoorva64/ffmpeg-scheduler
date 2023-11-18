#!/bin/sh

celery -A ffmpeg_scheduler worker --loglevel=info --concurrency=1