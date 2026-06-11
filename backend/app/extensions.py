"""Flask extensions initialization."""

from flask_sqlalchemy import SQLAlchemy  # type: ignore
from flask_migrate import Migrate  # type: ignore
from flask_socketio import SocketIO  # type: ignore
from celery import Celery  # type: ignore
import redis as redis_lib  # type: ignore

db = SQLAlchemy()
migrate = Migrate()
socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")
celery = Celery()
redis_client = None


def init_redis(flask_app):
    """Initialize Redis client."""
    global redis_client
    redis_client = redis_lib.from_url(
        flask_app.config["REDIS_URL"], decode_responses=True
    )
    return redis_client


def init_celery(flask_app):
    """Initialize Celery with Flask app context."""
    celery.conf.update(
        {
            "broker_url": flask_app.config["CELERY_BROKER_URL"],
            "result_backend": flask_app.config["CELERY_RESULT_BACKEND"],
            "beat_schedule": flask_app.config.get("CELERY_BEAT_SCHEDULE", {}),
            "timezone": "UTC",
        }
    )

    class ContextTask(celery.Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # Import tasks to register them with Celery
    import app.tasks.fetch_prices  # noqa: F401
    import app.tasks.fetch_news  # noqa: F401
    import app.tasks.daily_report  # noqa: F401

    return celery
