from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.forms.auth import (
    EmailVerificationForm,
    LoginForm,
    RegistrationForm,
    RequestResetForm,
    ResetPasswordForm,
)
from app.models import ApiKey, User
from app.utils.email import send_reset_email, send_verification_email

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower(),
            name=form.name.data,
        )
        user.set_password(form.password.data)
        verification_code = user.generate_email_verification_code()
        db.session.add(user)
        db.session.commit()

        send_verification_email(user, verification_code)
        session["pending_email_user_id"] = user.id
        flash("We sent a verification code to your email. Enter it below to activate your account.", "info")
        return redirect(url_for("auth.verify_email"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.verify_password(form.password.data):
            if not user.is_email_verified:
                session["pending_email_user_id"] = user.id
                flash("Please verify your email before signing in.", "warning")
                return redirect(url_for("auth.verify_email"))
            if not user.is_active:
                flash("Your account is disabled. Contact support.", "danger")
            else:
                login_user(user, remember=form.remember.data)
                flash("Welcome back!", "success")
                next_url = request.args.get("next")
                return redirect(next_url or url_for("dashboard.index"))
        else:
            flash("Invalid credentials.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


def _lookup_pending_user() -> User | None:
    if current_user.is_authenticated:
        return current_user
    user_id = session.get("pending_email_user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


@auth_bp.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    if current_user.is_authenticated and current_user.is_email_verified:
        return redirect(url_for("dashboard.index"))

    user = _lookup_pending_user()
    if not user:
        flash("We couldn't find a pending verification. Please register first.", "warning")
        return redirect(url_for("auth.register"))

    form = EmailVerificationForm()
    if form.validate_on_submit():
        if user.is_email_verified:
            flash("Your email is already verified.", "info")
            return redirect(url_for("auth.login"))
        if user.is_email_verification_code_valid(form.code.data):
            user.mark_email_verified()
            if not user.api_keys:
                api_key = ApiKey(user_id=user.id, name="Default API Key")
                db.session.add(api_key)
            db.session.commit()
            session.pop("pending_email_user_id", None)
            flash("Email verified! You can now sign in.", "success")
            return redirect(url_for("auth.login"))
        flash("That verification code is invalid or expired.", "danger")

    return render_template("auth/verify_email.html", form=form, email=user.email)


@auth_bp.route("/verify-email/resend", methods=["POST"])
def resend_verification_email():
    user = _lookup_pending_user()
    if not user:
        flash("We couldn't find a pending verification.", "warning")
        return redirect(url_for("auth.register"))

    if user.is_email_verified:
        flash("Your email is already verified.", "info")
        return redirect(url_for("auth.login"))

    now = datetime.now(timezone.utc)
    if user.email_verification_sent_at and (now - user.email_verification_sent_at).total_seconds() < 60:
        flash("Please wait a moment before requesting another code.", "warning")
        return redirect(url_for("auth.verify_email"))

    code = user.generate_email_verification_code()
    db.session.commit()
    send_verification_email(user, code)
    flash("We sent a new verification code to your email.", "info")
    return redirect(url_for("auth.verify_email"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            send_reset_email(user)
        flash("If your email exists in our system, you'll receive a reset link shortly.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    user = User.verify_reset_token(token)
    if not user:
        flash("The password reset link is invalid or expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Password updated. Please sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)
