from __future__ import annotations

import logging
from typing import Iterable

import requests
from flask import current_app

from app.models import Monitor, NotificationPreference
from .email import send_email

logger = logging.getLogger(__name__)


def _get_recipients(monitor: Monitor, channel: str) -> Iterable[str]:
    prefs = NotificationPreference.query.filter_by(
        user_id=monitor.user_id, channel=channel, is_enabled=True
    )
    for pref in prefs:
        yield pref.destination


def notify_downtime(monitor: Monitor, message: str) -> None:
    subject = f"{monitor.name} is DOWN"
    body = (
        f"<p>Monitor <strong>{monitor.name}</strong> reported downtime.</p>"
        f"<p>URL: {monitor.url}</p>"
        f"<p>Details: {message}</p>"
    )
    _send_email_alert(monitor, subject, body)
    _send_telegram_alert(monitor, subject)


def notify_recovery(monitor: Monitor) -> None:
    subject = f"{monitor.name} is back UP"
    body = (
        f"<p>Monitor <strong>{monitor.name}</strong> has recovered.</p>"
        f"<p>URL: {monitor.url}</p>"
    )
    _send_email_alert(monitor, subject, body)
    _send_telegram_alert(monitor, subject)


def _send_email_alert(monitor: Monitor, subject: str, html_body: str) -> None:
    recipients = list(_get_recipients(monitor, "email"))
    if not recipients:
        recipients = [monitor.user.email]
    if not recipients:
        return
    send_email(subject, recipients, html_body)


def _send_telegram_alert(monitor: Monitor, text: str) -> None:
    token = current_app.config.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return

    chat_ids = list(_get_recipients(monitor, "telegram"))
    if monitor.user.telegram_chat_id:
        chat_ids.append(monitor.user.telegram_chat_id)

    for chat_id in chat_ids:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - network errors
            logger.exception("Failed to send Telegram alert: %s", exc)
