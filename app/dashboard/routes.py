from __future__ import annotations

from collections import defaultdict

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Monitor, MonitorCheck
from app.scheduler import schedule_monitor, unschedule_monitor


dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates/dashboard")


@dashboard_bp.route("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return render_template("landing.html")


@dashboard_bp.route("/dashboard")
@login_required
def index():
    monitors = Monitor.query.filter_by(user_id=current_user.id).order_by(Monitor.created_at.desc()).all()
    monitor_ids = [m.id for m in monitors]

    checks_by_monitor: dict[int, list[MonitorCheck]] = defaultdict(list)
    if monitor_ids:
        checks = (
            MonitorCheck.query.filter(MonitorCheck.monitor_id.in_(monitor_ids))
            .order_by(MonitorCheck.monitor_id, MonitorCheck.checked_at.desc())
            .all()
        )
        for check in checks:
            if len(checks_by_monitor[check.monitor_id]) < 200:
                checks_by_monitor[check.monitor_id].append(check)

    summary = []
    for monitor in monitors:
        checks = checks_by_monitor.get(monitor.id, [])
        total_checks = len(checks)
        up_checks = sum(1 for c in checks if c.is_up)
        downtime_events = sum(1 for c in checks if not c.is_up)
        avg_response = (
            sum(c.response_time_ms for c in checks if c.response_time_ms) / len([c for c in checks if c.response_time_ms])
            if any(c.response_time_ms for c in checks)
            else None
        )
        uptime_pct = round((up_checks / total_checks) * 100, 2) if total_checks else None

        response_chart = [
            {
                "x": c.checked_at.isoformat(),
                "y": round(c.response_time_ms, 2) if c.response_time_ms else None,
            }
            for c in reversed(checks[:50])
        ]

        summary.append(
            {
                "monitor": monitor,
                "uptime_pct": uptime_pct,
                "avg_response": avg_response,
                "downtime_events": downtime_events,
                "checks": checks[:20],
                "response_chart": response_chart,
            }
        )

    return render_template("dashboard/index.html", summaries=summary)


@dashboard_bp.route("/dashboard/monitors/create", methods=["POST"])
@login_required
def create_monitor():
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    interval = int(request.form.get("interval", 60))

    if not name or not url:
        flash("Monitor name and URL are required.", "danger")
        return redirect(url_for("dashboard.index"))

    monitor = Monitor(
        user_id=current_user.id,
        name=name,
        url=url,
        interval_seconds=max(30, interval),
    )
    db.session.add(monitor)
    db.session.commit()

    schedule_monitor(monitor)

    flash("Monitor created and scheduled.", "success")
    return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/dashboard/monitors/<int:monitor_id>/toggle", methods=["POST"])
@login_required
def toggle_monitor(monitor_id: int):
    monitor = Monitor.query.filter_by(id=monitor_id, user_id=current_user.id).first_or_404()
    monitor.is_paused = not monitor.is_paused
    db.session.commit()

    if monitor.is_paused:
        unschedule_monitor(monitor)
        flash("Monitor paused.", "info")
    else:
        schedule_monitor(monitor)
        flash("Monitor resumed.", "success")

    return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/dashboard/monitors/<int:monitor_id>/delete", methods=["POST"])
@login_required
def delete_monitor(monitor_id: int):
    monitor = Monitor.query.filter_by(id=monitor_id, user_id=current_user.id).first()
    if not monitor:
        abort(404)

    unschedule_monitor(monitor)
    MonitorCheck.query.filter_by(monitor_id=monitor.id).delete()
    db.session.delete(monitor)
    db.session.commit()
    flash("Monitor deleted.", "info")
    return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/dashboard/monitors/<int:monitor_id>")
@login_required
def monitor_detail(monitor_id: int):
    monitor = Monitor.query.filter_by(id=monitor_id, user_id=current_user.id).first_or_404()
    checks = (
        MonitorCheck.query.filter_by(monitor_id=monitor.id)
        .order_by(MonitorCheck.checked_at.desc())
        .limit(200)
        .all()
    )

    total_checks = len(checks)
    up_checks = sum(1 for c in checks if c.is_up)
    avg_response = None
    latency_values = [c.response_time_ms for c in checks if c.response_time_ms]
    if latency_values:
        avg_response = sum(latency_values) / len(latency_values)
    uptime_pct = round((up_checks / total_checks) * 100, 2) if total_checks else None

    response_chart = [
        {
            "x": c.checked_at.isoformat(),
            "y": round(c.response_time_ms, 2) if c.response_time_ms else None,
        }
        for c in reversed(checks[:100])
    ]

    return render_template(
        "dashboard/monitor_detail.html",
        monitor=monitor,
        checks=checks,
        avg_response=avg_response,
        uptime_pct=uptime_pct,
        response_chart=response_chart,
    )
