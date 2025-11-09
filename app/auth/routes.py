from __future__ import annotations

from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db, limiter
from app.forms.auth import LoginForm, RegistrationForm, RequestResetForm, ResetPasswordForm
from app.models import ApiKey, User
from app.utils.email import send_reset_email

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"], error_message="Too many registration attempts. Please try again later.")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower(),
            name=form.name.data,
            is_email_verified=True,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        if not user.api_keys:
            db.session.add(ApiKey(user_id=user.id, name="Default API Key"))

        db.session.commit()

        login_user(user)
        flash("Account created! You are now signed in.", "success")
        next_url = _get_safe_redirect_target(request.args.get("next"))
        return redirect(next_url or url_for("dashboard.index"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"], error_message="Too many login attempts. Please try again later.")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.verify_password(form.password.data):
            if not user.is_active:
                flash("Your account is disabled. Contact support.", "danger")
            else:
                login_user(user, remember=form.remember.data)
                flash("Welcome back!", "success")
                next_url = _get_safe_redirect_target(request.args.get("next"))
                return redirect(next_url or url_for("dashboard.index"))
        else:
            flash("Invalid credentials.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))




@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per hour", methods=["POST"], error_message="Too many reset attempts. Please try again later.")
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


def _get_safe_redirect_target(target: str | None) -> str | None:
    if not target:
        return None
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    if test_url.scheme not in {"http", "https"}:
        return None
    if ref_url.netloc != test_url.netloc:
        return None
    return target
