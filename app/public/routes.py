from __future__ import annotations

from flask import Blueprint, abort, render_template

from app.models import Monitor, StatusPage

public_bp = Blueprint("public", __name__, template_folder="../templates/status")


@public_bp.route("/<slug>")
def status_page(slug: str):
    page = StatusPage.query.filter_by(slug=slug, is_public=True).first()
    if not page:
        abort(404)

    monitors = [pivot.monitor for pivot in page.monitors if pivot.monitor.last_is_up is not None]
    return render_template("status/status_page.html", page=page, monitors=monitors)
