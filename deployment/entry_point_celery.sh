#!/bin/sh

celery -A youtube_sentiment_analyzer worker --loglevel=info --concurrency=2