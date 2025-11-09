from __future__ import annotations

from functools import wraps
from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_limiter.util import get_remote_address

from app.extensions import db, limiter
from app.models import ApiKey, Monitor, MonitorCheck
from app.scheduler import schedule_monitor, unschedule_monitor

api_bp = Blueprint("api", __name__)


def authenticate_api_key():
    api_key_value = (
        request.headers.get("X-API-Key")
        or request.headers.get("Authorization", "").replace("Bearer ", "")
        or request.args.get("api_key")
    )
    if not api_key_value:
        return None
    return ApiKey.query.filter_by(key=api_key_value, is_active=True).first()


def api_key_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        api_key = authenticate_api_key()
        if not api_key:
            return jsonify({"error": "Invalid or missing API key"}), HTTPStatus.UNAUTHORIZED
        request.api_key = api_key  # type: ignore[attr-defined]
        return f(*args, **kwargs)

    return wrapper


@api_bp.before_request
def apply_rate_limit():
    limiter.check()


@api_bp.route("/monitors", methods=["GET"])
@api_key_required
@limiter.limit("60 per minute")
def list_monitors():
    api_key: ApiKey = request.api_key  # type: ignore[attr-defined]
    monitors = (
        Monitor.query.filter_by(user_id=api_key.user_id)
        .order_by(Monitor.created_at.desc())
        .all()
    )
    return jsonify([_monitor_to_dict(m) for m in monitors])


@api_bp.route("/monitors", methods=["POST"])
@api_key_required
@limiter.limit("30 per minute")
def create_monitor_api():
    api_key: ApiKey = request.api_key  # type: ignore[attr-defined]
    payload = request.get_json(force=True, silent=True) or {}

    name = (payload.get("name") or "").strip()
    url = (payload.get("url") or "").strip()
    interval = int(payload.get("interval_seconds") or 60)

    if not name or not url:
        return jsonify({"error": "name and url are required"}), HTTPStatus.BAD_REQUEST

    monitor = Monitor(
        user_id=api_key.user_id,
        name=name,
        url=url,
        interval_seconds=max(30, interval),
    )
    db.session.add(monitor)
    db.session.commit()
    schedule_monitor(monitor)

    return jsonify(_monitor_to_dict(monitor)), HTTPStatus.CREATED


@api_bp.route("/monitors/<int:monitor_id>", methods=["GET"])
@api_key_required
@limiter.limit("60 per minute")
def monitor_detail_api(monitor_id: int):
    api_key: ApiKey = request.api_key  # type: ignore[attr-defined]
    monitor = Monitor.query.filter_by(id=monitor_id, user_id=api_key.user_id).first()
    if not monitor:
        return jsonify({"error": "Monitor not found"}), HTTPStatus.NOT_FOUND
    return jsonify(_monitor_to_dict(monitor))


@api_bp.route("/monitors/<int:monitor_id>", methods=["PATCH", "PUT"])
@api_key_required
@limiter.limit("30 per minute")
def update_monitor_api(monitor_id: int):
    api_key: ApiKey = request.api_key  # type: ignore[attr-defined]
    monitor = Monitor.query.filter_by(id=monitor_id, user_id=api_key.user_id).first()
    if not monitor:
        return jsonify({"error": "Monitor not found"}), HTTPStatus.NOT_FOUND

    payload = request.get_json(force=True, silent=True) or {}

    if "name" in payload:
        monitor.name = payload["name"].strip() or monitor.name
    if "url" in payload:
        monitor.url = payload["url"].strip() or monitor.url
    if "interval_seconds" in payload:
        monitor.interval_seconds = max(30, int(payload["interval_seconds"]))
    if "is_paused" in payload:
        monitor.is_paused = bool(payload["is_paused"])

    db.session.commit()

    if monitor.is_paused:
        unschedule_monitor(monitor)
    else:
        schedule_monitor(monitor)

    return jsonify(_monitor_to_dict(monitor))


@api_bp.route("/monitors/<int:monitor_id>", methods=["DELETE"])
@api_key_required
@limiter.limit("30 per minute")
def delete_monitor_api(monitor_id: int):
    api_key: ApiKey = request.api_key  # type: ignore[attr-defined]
    monitor = Monitor.query.filter_by(id=monitor_id, user_id=api_key.user_id).first()
    if not monitor:
        return jsonify({"error": "Monitor not found"}), HTTPStatus.NOT_FOUND

    unschedule_monitor(monitor)
    MonitorCheck.query.filter_by(monitor_id=monitor.id).delete()
    db.session.delete(monitor)
    db.session.commit()
    return "", HTTPStatus.NO_CONTENT


@api_bp.route("/monitors/<int:monitor_id>/checks", methods=["GET"])
@api_key_required
@limiter.limit("60 per minute")
def list_monitor_checks(monitor_id: int):
    api_key: ApiKey = request.api_key  # type: ignore[attr-defined]
    monitor = Monitor.query.filter_by(id=monitor_id, user_id=api_key.user_id).first()
    if not monitor:
        return jsonify({"error": "Monitor not found"}), HTTPStatus.NOT_FOUND

    limit = min(int(request.args.get("limit", 100)), 500)
    checks = (
        MonitorCheck.query.filter_by(monitor_id=monitor.id)
        .order_by(MonitorCheck.checked_at.desc())
        .limit(limit)
        .all()
    )
    return jsonify([_check_to_dict(check) for check in checks])


def _monitor_to_dict(monitor: Monitor) -> dict:
    return {
        "id": monitor.id,
        "name": monitor.name,
        "url": monitor.url,
        "interval_seconds": monitor.interval_seconds,
        "last_check_at": monitor.last_check_at.isoformat() if monitor.last_check_at else None,
        "last_status_code": monitor.last_status_code,
        "last_is_up": monitor.last_is_up,
        "last_response_time_ms": monitor.last_response_time_ms,
        "is_paused": monitor.is_paused,
        "created_at": monitor.created_at.isoformat() if monitor.created_at else None,
        "updated_at": monitor.updated_at.isoformat() if monitor.updated_at else None,
    }


def _check_to_dict(check: MonitorCheck) -> dict:
    return {
        "id": check.id,
        "status_code": check.status_code,
        "is_up": check.is_up,
        "response_time_ms": check.response_time_ms,
        "message": check.message,
        "checked_at": check.checked_at.isoformat() if check.checked_at else None,
    }
