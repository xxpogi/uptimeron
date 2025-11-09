from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from apscheduler.jobstores.base import JobLookupError
from flask import current_app

from .extensions import db, scheduler
from .models import Monitor, MonitorCheck
from .utils.notifications import notify_downtime, notify_recovery

logger = logging.getLogger(__name__)


def init_schedules() -> None:
    """Ensure all active monitors are scheduled."""
    with scheduler.app.app_context():  # type: ignore[attr-defined]
        monitors = Monitor.query.filter_by(is_paused=False).all()
        for monitor in monitors:
            schedule_monitor(monitor)


def schedule_monitor(monitor: Monitor) -> None:
    job_id = monitor.create_job_id()
    try:
        scheduler.remove_job(job_id)
    except JobLookupError:
        pass

    if monitor.is_paused:
        return

    scheduler.add_job(
        func=run_monitor_check,
        trigger="interval",
        seconds=max(monitor.interval_seconds, 30),
        id=job_id,
        args=[monitor.id],
        replace_existing=True,
        misfire_grace_time=15,
    )


def unschedule_monitor(monitor: Monitor) -> None:
    job_id = monitor.create_job_id()
    try:
        scheduler.remove_job(job_id)
    except JobLookupError:
        pass


def run_monitor_check(monitor_id: int) -> None:
    with scheduler.app.app_context():  # type: ignore[attr-defined]
        monitor: Optional[Monitor] = Monitor.query.get(monitor_id)
        if monitor is None:
            logger.warning("Monitor %s no longer exists; unscheduling", monitor_id)
            return
        if monitor.is_paused:
            logger.info("Monitor %s is paused; skipping", monitor_id)
            return

        start_time = datetime.now(timezone.utc)
        response_time_ms: Optional[float] = None
        status_code: Optional[int] = None
        is_up = False
        message = ""

        try:
            response = requests.get(
                monitor.url,
                timeout=monitor.timeout_seconds,
                allow_redirects=True,
            )
            response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            status_code = response.status_code
            is_up = response.ok
            if not is_up:
                message = f"Status {status_code}"
        except requests.exceptions.RequestException as exc:  # pragma: no cover - network errors
            response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            message = str(exc)
            logger.exception("Monitor %s check failed: %s", monitor.id, exc)

        check = MonitorCheck(
            monitor_id=monitor.id,
            status_code=status_code,
            is_up=is_up,
            response_time_ms=response_time_ms,
            message=message[:255],
            checked_at=datetime.now(timezone.utc),
        )
        db.session.add(check)

        previous_state = monitor.last_is_up
        monitor.last_check_at = check.checked_at
        monitor.last_status_code = status_code
        monitor.last_is_up = is_up
        monitor.last_response_time_ms = response_time_ms

        db.session.commit()

        if previous_state is None:
            return

        if previous_state and not is_up:
            notify_downtime(monitor, message)
        elif not previous_state and is_up:
            notify_recovery(monitor)
