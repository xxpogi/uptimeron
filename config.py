import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///pulsewatch.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    WTF_CSRF_TIME_LIMIT = None
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 25))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "0") == "1"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "0") == "1"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "PulseWatch <noreply@pulsewatch.io>")
    RATELIMIT_DEFAULT = "100 per hour"
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    APSCHEDULER_JOBSTORES = {
        "default": {
            "type": "sqlalchemy",
            "url": os.environ.get("DATABASE_URL", "sqlite:///pulsewatch.db"),
        }
    }
    APSCHEDULER_EXECUTORS = {
        "default": {"type": "threadpool", "max_workers": 4},
    }
    APSCHEDULER_JOB_DEFAULTS = {"coalesce": False, "max_instances": 1}
    SCHEDULER_API_ENABLED = False
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_DEFAULT_CHAT_ID")
    SECURITY_PASSWORD_SALT = os.environ.get("SECURITY_PASSWORD_SALT", "salt-change-me")
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "https")
    PROPAGATE_EXCEPTIONS = True


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    pass
