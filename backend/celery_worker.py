"""Celery worker entry point.

Run with:
  celery -A celery_worker.celery worker --loglevel=info --beat
"""

from app import create_app
from app.extensions import celery

app = create_app()
app.app_context().push()
