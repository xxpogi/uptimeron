from __future__ import annotations

import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

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

        host = _resolve_host(monitor.url)
        if not host:
            message = "Unable to resolve host"
            logger.warning("Monitor %s has invalid host from url %s", monitor.id, monitor.url)
        else:
            ping_cmd = _build_ping_command(host, monitor.timeout_seconds)
            try:
                completed = subprocess.run(
                    ping_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=max(monitor.timeout_seconds, 1) + 2,
                    check=False,
                )
                elapsed_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                response_time_ms = _extract_latency_ms(completed.stdout) or elapsed_ms
                is_up = completed.returncode == 0
                status_code = 0 if is_up else -1
                if not is_up:
                    message = completed.stderr.strip() or completed.stdout.strip() or "Ping failed"
            except subprocess.TimeoutExpired:
                response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                message = "Ping timed out"
            except OSError as exc:
                response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                message = str(exc)
                logger.exception("Monitor %s ping failed: %s", monitor.id, exc)

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


def _resolve_host(target: str) -> str | None:
    parsed = urlparse(target)
    if parsed.scheme:
        return parsed.hostname
    parsed = urlparse(f"//{target}")
    return parsed.hostname or (parsed.path.split("/")[0] if parsed.path else None)


def _build_ping_command(host: str, timeout_seconds: int) -> list[str]:
    timeout_seconds = max(timeout_seconds, 1)
    if os.name == "nt":
        return ["ping", "-n", "1", "-w", str(timeout_seconds * 1000), host]
    return ["ping", "-c", "1", "-W", str(timeout_seconds), host]


def _extract_latency_ms(output: str) -> Optional[float]:
    match = re.search(r"time[=<]([0-9.]+)\s*ms", output)
    if match:
        try:
            return float(match.group(1))
        except ValueError:  # pragma: no cover - defensive
            return None
    return None
