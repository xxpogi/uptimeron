from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask import current_app
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from passlib.hash import pbkdf2_sha256

from .extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    timezone = db.Column(db.String(64), default="UTC")
    is_active = db.Column(db.Boolean, default=True)
    is_email_verified = db.Column(db.Boolean, default=False)
    email_verification_code = db.Column(db.String(6))
    email_verification_sent_at = db.Column(db.DateTime(timezone=True))
    telegram_chat_id = db.Column(db.String(64))

    monitors = db.relationship("Monitor", back_populates="user", cascade="all, delete-orphan")
    api_keys = db.relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    notification_preferences = db.relationship(
        "NotificationPreference", back_populates="user", cascade="all, delete-orphan"
    )
    status_pages = db.relationship("StatusPage", back_populates="user", cascade="all, delete-orphan")

    def get_id(self) -> str:
        return str(self.id)

    def set_password(self, password: str) -> None:
        self.password_hash = pbkdf2_sha256.hash(password)

    def verify_password(self, password: str) -> bool:
        return pbkdf2_sha256.verify(password, self.password_hash)

    def generate_reset_token(self, expires_in: int = 3600) -> str:
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        return serializer.dumps({"user_id": self.id}, salt=current_app.config["SECURITY_PASSWORD_SALT"])

    def generate_email_verification_code(self) -> str:
        code = f"{secrets.randbelow(10**6):06d}"
        self.email_verification_code = code
        self.email_verification_sent_at = datetime.now(timezone.utc)
        return code

    def is_email_verification_code_valid(self, code: str, expires_in: int = 3600) -> bool:
        if not code or not self.email_verification_code:
            return False
        if code.strip() != self.email_verification_code:
            return False
        if not self.email_verification_sent_at:
            return False
        elapsed = datetime.now(timezone.utc) - self.email_verification_sent_at
        if elapsed > timedelta(seconds=expires_in):
            return False
        return True

    def mark_email_verified(self) -> None:
        self.is_email_verified = True
        self.email_verification_code = None
        self.email_verification_sent_at = None

    @staticmethod
    def verify_reset_token(token: str, max_age: int = 3600) -> Optional["User"]:
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        try:
            data = serializer.loads(
                token,
                salt=current_app.config["SECURITY_PASSWORD_SALT"],
                max_age=max_age,
            )
        except (BadSignature, SignatureExpired):
            return None

        user_id = data.get("user_id")
        if user_id is None:
            return None
        return User.query.get(user_id)


class Monitor(TimestampMixin, db.Model):
    __tablename__ = "monitors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    interval_seconds = db.Column(db.Integer, default=60)
    timeout_seconds = db.Column(db.Integer, default=10)
    last_check_at = db.Column(db.DateTime(timezone=True))
    last_status_code = db.Column(db.Integer)
    last_is_up = db.Column(db.Boolean)
    last_response_time_ms = db.Column(db.Float)
    is_paused = db.Column(db.Boolean, default=False)

    user = db.relationship("User", back_populates="monitors")
    checks = db.relationship("MonitorCheck", back_populates="monitor", cascade="all, delete-orphan")
    status_pages = db.relationship(
        "StatusPageMonitor",
        back_populates="monitor",
        cascade="all, delete-orphan",
    )

    def create_job_id(self) -> str:
        return f"monitor-{self.id}"


class MonitorCheck(db.Model):
    __tablename__ = "monitor_checks"

    id = db.Column(db.Integer, primary_key=True)
    monitor_id = db.Column(db.Integer, db.ForeignKey("monitors.id"), nullable=False, index=True)
    status_code = db.Column(db.Integer)
    is_up = db.Column(db.Boolean, default=False)
    response_time_ms = db.Column(db.Float)
    message = db.Column(db.String(255))
    checked_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    monitor = db.relationship("Monitor", back_populates="checks")


class NotificationPreference(TimestampMixin, db.Model):
    __tablename__ = "notification_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    channel = db.Column(db.String(32), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    is_enabled = db.Column(db.Boolean, default=True)

    user = db.relationship("User", back_populates="notification_preferences")


class ApiKey(TimestampMixin, db.Model):
    __tablename__ = "api_keys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    key = db.Column(db.String(64), unique=True, nullable=False, default=secrets.token_hex)
    is_active = db.Column(db.Boolean, default=True)
    last_used_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User", back_populates="api_keys")

    @staticmethod
    def generate_key() -> str:
        return secrets.token_hex(24)


class StatusPage(TimestampMixin, db.Model):
    __tablename__ = "status_pages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=True)

    user = db.relationship("User", back_populates="status_pages")
    monitors = db.relationship(
        "StatusPageMonitor",
        back_populates="status_page",
        cascade="all, delete-orphan",
    )


class StatusPageMonitor(db.Model):
    __tablename__ = "status_page_monitors"

    status_page_id = db.Column(db.Integer, db.ForeignKey("status_pages.id"), primary_key=True)
    monitor_id = db.Column(db.Integer, db.ForeignKey("monitors.id"), primary_key=True)

    status_page = db.relationship("StatusPage", back_populates="monitors")
    monitor = db.relationship("Monitor", back_populates="status_pages")
