"""Flask extensions initialization."""

from flask_sqlalchemy import SQLAlchemy  # type: ignore
from flask_migrate import Migrate  # type: ignore
from flask_socketio import SocketIO  # type: ignore
from flask_limiter import Limiter  # type: ignore
from flask_limiter.util import get_remote_address  # type: ignore
from celery import Celery  # type: ignore

db = SQLAlchemy()
migrate = Migrate()
socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")
celery = Celery()

# Rate limiter using client IP
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "60 per hour"]
)




def init_limiter(flask_app):
    """Initialize Limiter with Redis storage."""
    limiter.storage_uri = flask_app.config["REDIS_URL"]
    limiter.init_app(flask_app)


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
    import app.tasks.fetch_prices  # type: ignore # noqa: F401
    import app.tasks.fetch_news  # type: ignore # noqa: F401
    import app.tasks.daily_report  # type: ignore # noqa: F401

    return celery
