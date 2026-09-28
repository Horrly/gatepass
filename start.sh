#!/usr/bin/env bash
# Render start: migrate, seed the demo, then run the web server and a Celery worker.
set -o errexit
cd backend

python manage.py migrate --noinput
python manage.py seed_demo

if [ -n "$REDIS_URL" ]; then
  # One small worker (with the beat scheduler for releasing expired holds)
  # alongside the web server, so everything fits on one free Render instance.
  celery -A config worker --beat --concurrency 1 --loglevel info &
fi

exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 60 --access-logfile -
