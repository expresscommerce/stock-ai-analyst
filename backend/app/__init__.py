"""Flask application factory."""

import os
from flask import Flask
from flask_cors import CORS

from config import config_map
from app.extensions import db, migrate, socketio, init_redis, init_celery


def create_app(config_name=None):
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    # Determine paths for split frontend/backend directory layout
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(backend_dir)

    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, "frontend", "templates"),
        static_folder=os.path.join(project_root, "frontend", "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_map.get(config_name, config_map["development"]))

    # Initialize extensions
    CORS(app)
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)
    init_redis(app)
    init_celery(app)

    # Register blueprints
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
        db.create_all()

    return app
