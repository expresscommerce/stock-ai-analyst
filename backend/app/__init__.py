"""Flask application factory."""

import os
# pyrefly: ignore [missing-import]
import sentry_sdk
# pyrefly: ignore [missing-import]
from sentry_sdk.integrations.flask import FlaskIntegration
from flask import Flask
from flask_cors import CORS

from config import config_map
from app.extensions import db, migrate, socketio, init_limiter, init_celery


def create_app(config_name=None):
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    config_obj = config_map.get(config_name, config_map["development"])

    # Initialize Sentry if DSN is set
    if config_obj.SENTRY_DSN:
        sentry_sdk.init(
            dsn=config_obj.SENTRY_DSN,
            integrations=[FlaskIntegration()],
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )

    # Determine paths for split frontend/backend directory layout
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(backend_dir)

    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, "frontend", "templates"),
        static_folder=os.path.join(project_root, "frontend", "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_obj)

    # Initialize extensions
    CORS(app)
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)
    init_limiter(app)
    init_celery(app)

    from app.routes.dashboard import dashboard_bp
    from app.routes.stock import stock_bp
    from app.routes.query import query_bp
    from app.routes.charts import charts_bp
    from app.routes.alerts import alerts_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(query_bp, url_prefix="/api")
    app.register_blueprint(charts_bp, url_prefix="/api")
    app.register_blueprint(alerts_bp, url_prefix="/api")

    # Create database tables
    with app.app_context():
        # Enable pgvector extension (ignore if already exists)
        try:
            db.session.execute(db.text("CREATE EXTENSION IF NOT EXISTS vector"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        from app.models import stock, news, embedding, alert, report  # noqa: F401
        try:
            db.create_all()
        except Exception as e:
            db.session.rollback()
            # Suppress concurrent creation errors
            pass

    return app

