"""Authoritative preview uses the same immutable render context as PDF output."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_ENV", "test")

from app.api import routes  # noqa: E402
from app.api.deps import current_user, settings_dep  # noqa: E402
from app.core.errors import register_error_handlers  # noqa: E402
from app.db.session import get_db  # noqa: E402


def client():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="staff-1", role="staff")
    app.dependency_overrides[settings_dep] = lambda: SimpleNamespace()
    return TestClient(app)


def test_preview_request_requires_exact_saved_revision_and_returns_cached_url(monkeypatch):
    snapshot = SimpleNamespace(id="snapshot-1", context_hash="a" * 64)
    monkeypatch.setattr(routes, "request_preview_render", lambda _db, user, session_id, **kwargs: (
        snapshot if user.role == "staff" and session_id == "session-1" and kwargs["draft_revision"] == 7 else None
    ))
    response = client().post("/api/sessions/session-1/preview-render", json={"draft_revision": 7})
    assert response.status_code == 200
    assert response.json() == {
        "preview_id": "snapshot-1", "context_hash": "a" * 64,
        "preview_url": "/previews/snapshot-1/html",
    }


def test_preview_html_is_private_scriptless_and_rendered_from_frozen_snapshot(monkeypatch):
    monkeypatch.setattr(routes, "render_snapshot_preview_html", lambda *_args, **_kwargs: "<!doctype html><main>Frozen preview</main>")
    response = client().get("/api/previews/snapshot-1/html")
    assert response.status_code == 200
    assert "Frozen preview" in response.text
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-security-policy"] == "default-src 'none'; img-src data:; style-src 'unsafe-inline'"


def test_admin_template_preview_render_with_extras_cap():
    c = client()
    response = c.post(
        "/api/admin/templates/preview-render",
        json={
            "template_config": {
                "canvas": {
                    "width": 794,
                    "height": 1123,
                    "elements": [
                        {"id": "bg", "type": "rectangle", "x": 0, "y": 0, "w": 794, "h": 1123},
                        {"id": "premium_info_block", "type": "premium-info-block", "x": 40, "y": 276, "w": 530, "h": 140},
                    ],
                }
            },
            "load_profile": "high",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "html" in data
    assert "<!doctype html>" in data["html"]
    # High stress test profile has 6 extras; verifies backend +3 more... capping
    assert "+ 3 more..." in data["html"]


def test_admin_template_preview_render_with_purchased_perils():
    c = client()
    response = c.post(
        "/api/admin/templates/preview-render",
        json={
            "template_config": {
                "canvas": {
                    "width": 794,
                    "height": 1123,
                    "elements": [
                        {"id": "bg", "type": "rectangle", "x": 0, "y": 0, "w": 794, "h": 1123},
                        {"id": "specials_header_bg", "type": "rectangle", "x": 40, "y": 420, "w": 714, "h": 24},
                        {"id": "specials_header_txt", "type": "text", "text": "Our Specials", "x": 52, "y": 425, "w": 700, "h": 16},
                        {"id": "grid1", "type": "benefit-grid", "gridKind": "current_benefits", "x": 40, "y": 448, "w": 714, "h": 120},
                        {"id": "addons_header_bg", "type": "rectangle", "x": 40, "y": 580, "w": 714, "h": 24},
                        {"id": "addons_header_txt", "type": "text", "text": "Available Add-ons", "x": 52, "y": 585, "w": 700, "h": 16},
                        {"id": "grid2", "type": "benefit-grid", "gridKind": "available_addons", "x": 40, "y": 608, "w": 714, "h": 120},
                    ],
                }
            },
            "load_profile": "medium",
            "include_purchased_perils": True,
        },
    )
    assert response.status_code == 200
    html = response.json()["html"]
    # Purchased extras section is present and contains Flood & Special Perils
    assert "Purchased Extras &amp; Add-ons" in html or "Purchased Extras & Add-ons" in html
    assert "Flood &amp; Special Perils" in html or "Flood & Special Perils" in html
    assert "Windscreen Protection" in html


def test_admin_template_preview_render_without_purchased_perils():
    c = client()
    response = c.post(
        "/api/admin/templates/preview-render",
        json={
            "template_config": {
                "canvas": {
                    "width": 794,
                    "height": 1123,
                    "elements": [
                        {"id": "bg", "type": "rectangle", "x": 0, "y": 0, "w": 794, "h": 1123},
                        {"id": "specials_header_bg", "type": "rectangle", "x": 40, "y": 420, "w": 714, "h": 24},
                        {"id": "specials_header_txt", "type": "text", "text": "Our Specials", "x": 52, "y": 425, "w": 700, "h": 16},
                        {"id": "grid1", "type": "benefit-grid", "gridKind": "current_benefits", "x": 40, "y": 448, "w": 714, "h": 120},
                        {"id": "addons_header_bg", "type": "rectangle", "x": 40, "y": 580, "w": 714, "h": 24},
                        {"id": "addons_header_txt", "type": "text", "text": "Available Add-ons", "x": 52, "y": 585, "w": 700, "h": 16},
                        {"id": "grid2", "type": "benefit-grid", "gridKind": "available_addons", "x": 40, "y": 608, "w": 714, "h": 120},
                    ],
                }
            },
            "load_profile": "medium",
            "include_purchased_perils": False,
        },
    )
    assert response.status_code == 200
    html = response.json()["html"]
    # Purchased extras section is cleanly omitted when customer declined perils
    assert "Purchased Extras &amp; Add-ons" not in html
    assert "Purchased Extras & Add-ons" not in html


def test_template_no_extras_variant_preserves_purchased_addons():
    """Bilingual Agency Motor v4 (No Extras) must NOT hide the Purchased Add-ons benefit card section."""
    c = client()
    response = c.post(
        "/api/admin/templates/preview-render",
        json={
            "template_config": {
                "name": "Bilingual Agency Motor v4 (No Extras)",
                "v4_mode": True,
                "extras_mode": "none",
                "canvas": {
                    "width": 794,
                    "height": 1123,
                    "elements": [
                        {"id": "bg", "type": "rectangle", "x": 0, "y": 0, "w": 794, "h": 1123},
                        {"id": "premium_info_block", "type": "premium-info-block", "extras_mode": "none", "x": 40, "y": 276, "w": 530, "h": 140},
                        {"id": "specials_header_bg", "type": "rectangle", "x": 40, "y": 420, "w": 714, "h": 24},
                        {"id": "specials_header_txt", "type": "text", "text": "Our Specials", "x": 52, "y": 425, "w": 700, "h": 16},
                        {"id": "grid1", "type": "benefit-grid", "gridKind": "current_benefits", "x": 40, "y": 448, "w": 714, "h": 120},
                        {"id": "addons_header_bg", "type": "rectangle", "x": 40, "y": 580, "w": 714, "h": 24},
                        {"id": "addons_header_txt", "type": "text", "text": "Available Add-ons", "x": 52, "y": 585, "w": 700, "h": 16},
                        {"id": "grid2", "type": "benefit-grid", "gridKind": "available_addons", "x": 40, "y": 608, "w": 714, "h": 120},
                    ],
                }
            },
            "load_profile": "medium",
            "include_purchased_perils": True,
        },
    )
    assert response.status_code == 200
    html = response.json()["html"]
    # Even with extras_mode: "none", purchased add-ons MUST appear when perils are purchased
    assert "Purchased Extras &amp; Add-ons" in html or "Purchased Extras & Add-ons" in html
    assert "Flood &amp; Special Perils" in html or "Flood & Special Perils" in html


def test_preview_render_with_custom_benefit_preset_sizing():
    """Custom iconSize, titleSize, and descSize from benefit_preset_config must be honored without clamping."""
    c = client()
    response = c.post(
        "/api/admin/templates/preview-render",
        json={
            "template_config": {
                "name": "Bilingual Agency Motor v4",
                "v4_mode": True,
                "canvas": {
                    "width": 794,
                    "height": 1123,
                    "elements": [
                        {"id": "bg", "type": "rectangle", "x": 0, "y": 0, "w": 794, "h": 1123},
                        {"id": "specials_header_bg", "type": "rectangle", "x": 40, "y": 420, "w": 714, "h": 24},
                        {"id": "specials_header_txt", "type": "text", "text": "Our Specials", "x": 52, "y": 425, "w": 700, "h": 16},
                        {"id": "grid1", "type": "benefit-grid", "gridKind": "current_benefits", "x": 40, "y": 448, "w": 714, "h": 120},
                        {"id": "addons_header_bg", "type": "rectangle", "x": 40, "y": 580, "w": 714, "h": 24},
                        {"id": "addons_header_txt", "type": "text", "text": "Available Add-ons", "x": 52, "y": 585, "w": 700, "h": 16},
                        {"id": "grid2", "type": "benefit-grid", "gridKind": "available_addons", "x": 40, "y": 608, "w": 714, "h": 120},
                    ],
                }
            },
            "load_profile": "high",
            "include_purchased_perils": True,
            "benefit_preset_config": {
                "titleSize": 14.0,
                "iconSize": 48.0,
                "descSize": 10.0,
                "coverageSize": 12.0,
            },
        },
    )
    assert response.status_code == 200
    html = response.json()["html"]
    # Check that custom icon and typography sizes are rendered
    assert "width:48.0px" in html or "width:48px" in html
    assert "14.0px" in html or "14px" in html
    assert "font-size:10.0px" in html or "font-size:10px" in html
    assert "font-size:12.0px" in html or "font-size:12px" in html
    assert "data:image/" in html, "Preview HTML must embed authentic benefit artwork data URIs"



