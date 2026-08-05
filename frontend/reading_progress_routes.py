"""
NEW FILE — place at project root, alongside app.py: reading_progress_routes.py

A Flask Blueprint. Kept separate from app.py on purpose. Proxies browser
requests to the FastAPI backend, attaching the Authorization header from
the Flask session — this is required because navigator.sendBeacon() (used
to flush the timer on tab close) can't set custom headers, but it DOES
send same-origin cookies, so the browser -> Flask leg is authenticated via
the session cookie, and Flask -> FastAPI leg is authenticated via the
Bearer token already stored in session['token'].
"""

import httpx
from flask import Blueprint, request, jsonify, session, render_template, flash, redirect, url_for

reading_progress_bp = Blueprint("reading_progress", __name__)

API_BASE_URL = "http://127.0.0.1:8000/api"


def _auth_headers():
    return {"Authorization": f"Bearer {session.get('token', '')}"}


@reading_progress_bp.route("/papers/<int:paper_id>/progress-page")
def paper_progress_page(paper_id):
    if "token" not in session:
        return redirect(url_for("login"))

    resp = httpx.get(f"{API_BASE_URL}/papers/", headers=_auth_headers())
    papers = resp.json() if resp.status_code == 200 else []
    paper = next((p for p in papers if p["id"] == paper_id), None)

    if not paper:
        flash("Paper not found.", "error")
        return redirect(url_for("papers_library"))

    return render_template("paper_progress.html", user=session.get("user"), paper=paper)


@reading_progress_bp.route("/papers/<int:paper_id>/progress", methods=["POST"])
def update_progress_proxy(paper_id):
    if "token" not in session:
        return jsonify({"detail": "Not authenticated"}), 401

    payload = request.get_json(silent=True) or {}
    resp = httpx.patch(
        f"{API_BASE_URL}/papers/{paper_id}/progress", headers=_auth_headers(), json=payload
    )
    return jsonify(resp.json()), resp.status_code


@reading_progress_bp.route("/papers/<int:paper_id>/reading-sessions", methods=["POST"])
def start_session_proxy(paper_id):
    if "token" not in session:
        return jsonify({"detail": "Not authenticated"}), 401

    resp = httpx.post(f"{API_BASE_URL}/papers/{paper_id}/reading-sessions", headers=_auth_headers())
    return jsonify(resp.json()), resp.status_code


@reading_progress_bp.route(
    "/papers/<int:paper_id>/reading-sessions/<int:session_id>/heartbeat", methods=["POST"]
)
def heartbeat_proxy(paper_id, session_id):
    if "token" not in session:
        return jsonify({"detail": "Not authenticated"}), 401

    payload = request.get_json(silent=True) or {}
    resp = httpx.post(
        f"{API_BASE_URL}/papers/{paper_id}/reading-sessions/{session_id}/heartbeat",
        headers=_auth_headers(),
        json=payload,
    )
    return jsonify(resp.json()), resp.status_code


@reading_progress_bp.route(
    "/papers/<int:paper_id>/reading-sessions/<int:session_id>/end", methods=["POST"]
)
def end_session_proxy(paper_id, session_id):
    # sendBeacon fires on tab close — best-effort, no need to block on the response.
    if "token" not in session:
        return "", 401

    httpx.post(
        f"{API_BASE_URL}/papers/{paper_id}/reading-sessions/{session_id}/end",
        headers=_auth_headers(),
    )
    return "", 204
