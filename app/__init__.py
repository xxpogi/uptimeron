from flask import Flask
from flask_login import current_user

from config import Config, DevelopmentConfig, ProductionConfig, TestingConfig
from .extensions import (
    csrf,
    db,
    limiter,
    login_manager,
    mail,
    migrate,
    scheduler as scheduler_ext,
)
from .models import ApiKey
from .scheduler import init_schedules


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def create_app(config_name: str | None = None) -> Flask:
    """Application factory."""
    app = Flask(__name__, static_folder="static", template_folder="templates")

    config_obj = CONFIG_MAP.get(config_name or "production", Config)
    app.config.from_object(config_obj)

    register_extensions(app)
    register_blueprints(app)
    register_error_handlers(app)

    with app.app_context():
        db.create_all()
        scheduler_ext.start(paused=False)
        init_schedules()

    return app


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    scheduler_ext.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        from .models import User

        return User.query.get(int(user_id))

    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"

    @limiter.request_filter
    def api_key_whitelist():
        if not current_user.is_authenticated:
            return False
        return ApiKey.query.filter_by(user_id=current_user.id, is_active=True).count() > 0


def register_blueprints(app: Flask) -> None:
    from .auth.routes import auth_bp
    from .dashboard.routes import dashboard_bp
    from .api.routes import api_bp
    from .public.routes import public_bp
    from .settings.routes import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(public_bp, url_prefix="/status")
    app.register_blueprint(settings_bp)


def register_error_handlers(app: Flask) -> None:
    from flask import jsonify, render_template

    @app.errorhandler(404)
    def not_found(error):
        from flask import request

        if app.config.get("PREFERRED_URL_SCHEME") == "https" and request.accept_mimetypes.accept_json:
            return jsonify({"error": "Not Found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def ratelimit_handler(error):
        return (
            render_template("errors/429.html", description=getattr(error, "description", "Too Many Requests")),
            429,
        )

    @app.errorhandler(500)
    def server_error(error):
        return render_template("errors/500.html"), 500
