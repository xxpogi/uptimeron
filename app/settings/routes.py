from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms.settings import ApiKeyForm, NotificationForm, ProfileForm, StatusPageForm
from app.models import ApiKey, Monitor, NotificationPreference, StatusPage, StatusPageMonitor

settings_bp = Blueprint("settings", __name__, template_folder="../templates/settings")


@settings_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings_home():
    profile_form = ProfileForm(prefix="profile")
    notification_form = NotificationForm(prefix="notification")
    api_key_form = ApiKeyForm(prefix="api")
    status_page_form = StatusPageForm(prefix="status")

    status_page_form.monitors.choices = [
        (monitor.id, monitor.name)
        for monitor in Monitor.query.filter_by(user_id=current_user.id).order_by(Monitor.name).all()
    ]

    if request.method == "GET":
        profile_form.name.data = current_user.name
        profile_form.timezone.data = current_user.timezone
        profile_form.telegram_chat_id.data = current_user.telegram_chat_id

    if profile_form.submit_profile.data and profile_form.validate_on_submit():
        current_user.name = profile_form.name.data
        current_user.timezone = profile_form.timezone.data
        current_user.telegram_chat_id = profile_form.telegram_chat_id.data
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("settings.settings_home"))

    if notification_form.submit_notification.data and notification_form.validate_on_submit():
        pref = NotificationPreference(
            user_id=current_user.id,
            channel=notification_form.channel.data,
            destination=notification_form.destination.data,
            is_enabled=notification_form.is_enabled.data,
        )
        db.session.add(pref)
        db.session.commit()
        flash("Notification preference added.", "success")
        return redirect(url_for("settings.settings_home"))

    if api_key_form.submit_api_key.data and api_key_form.validate_on_submit():
        api_key = ApiKey(
            user_id=current_user.id,
            name=api_key_form.name.data,
        )
        db.session.add(api_key)
        db.session.commit()
        flash("API key created.", "success")
        return redirect(url_for("settings.settings_home"))

    if status_page_form.submit_status_page.data and status_page_form.validate_on_submit():
        if StatusPage.query.filter_by(slug=status_page_form.slug.data).first():
            status_page_form.slug.errors.append("Slug already in use.")
        else:
            page = StatusPage(
                user_id=current_user.id,
                name=status_page_form.name.data,
                slug=status_page_form.slug.data,
                description=status_page_form.description.data,
                is_public=status_page_form.is_public.data,
            )
            db.session.add(page)
            db.session.flush()
            for monitor_id in status_page_form.monitors.data:
                pivot = StatusPageMonitor(status_page_id=page.id, monitor_id=monitor_id)
                db.session.add(pivot)
            db.session.commit()
            flash("Status page created.", "success")
            return redirect(url_for("settings.settings_home"))

    return render_template(
        "settings/index.html",
        profile_form=profile_form,
        notification_form=notification_form,
        api_key_form=api_key_form,
        status_page_form=status_page_form,
        notifications=NotificationPreference.query.filter_by(user_id=current_user.id).all(),
        api_keys=ApiKey.query.filter_by(user_id=current_user.id).all(),
        status_pages=StatusPage.query.filter_by(user_id=current_user.id).all(),
    )


@settings_bp.route("/settings/notifications/<int:pref_id>/delete", methods=["POST"])
@login_required
def delete_notification(pref_id: int):
    pref = NotificationPreference.query.filter_by(id=pref_id, user_id=current_user.id).first_or_404()
    db.session.delete(pref)
    db.session.commit()
    flash("Notification preference removed.", "info")
    return redirect(url_for("settings.settings_home"))


@settings_bp.route("/settings/api-keys/<int:key_id>/delete", methods=["POST"])
@login_required
def delete_api_key(key_id: int):
    api_key = ApiKey.query.filter_by(id=key_id, user_id=current_user.id).first_or_404()
    db.session.delete(api_key)
    db.session.commit()
    flash("API key deleted.", "info")
    return redirect(url_for("settings.settings_home"))


@settings_bp.route("/settings/status-pages/<int:page_id>/toggle", methods=["POST"])
@login_required
def toggle_status_page(page_id: int):
    page = StatusPage.query.filter_by(id=page_id, user_id=current_user.id).first_or_404()
    page.is_public = not page.is_public
    db.session.commit()
    flash("Status page visibility updated.", "success")
    return redirect(url_for("settings.settings_home"))


@settings_bp.route("/settings/status-pages/<int:page_id>/delete", methods=["POST"])
@login_required
def delete_status_page(page_id: int):
    page = StatusPage.query.filter_by(id=page_id, user_id=current_user.id).first_or_404()
    db.session.delete(page)
    db.session.commit()
    flash("Status page deleted.", "info")
    return redirect(url_for("settings.settings_home"))
