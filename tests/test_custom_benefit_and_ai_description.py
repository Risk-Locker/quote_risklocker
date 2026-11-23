"""Tests for custom benefit description/limit/icon persistence, Design 2 parity, and AI polish endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_PROVIDER", "supabase_postgres")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:password@db.test.supabase.co:5432/postgres")
os.environ.setdefault("AUTH_HASH_SECRET", "test-auth-hash-secret-that-is-long-enough")
os.environ.setdefault("STORAGE_DRIVER", "supabase")
os.environ.setdefault("SUPABASE_URL", "https://project-ref.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

from app.api import routes
from app.api.deps import current_user
from app.core.errors import register_error_handlers
from app.db.session import get_db
from app.models.enums import AccountStatus, RecordStatus, Role
from app.models.tables import (
    Batch,
    BenefitConcept,
    DraftBenefitSelection,
    InsuranceCompany,
    QuotationDraft,
    Session as QuotationSession,
    UploadedFile,
    User,
    new_id,
)
from app.rendering.template_renderer_design2 import render_design2_html
from app.services import benefit_description_ai
from app.services.workspace_patch_service import apply_workspace_patch
from app.services.workspace_snapshot_service import build_workspace_snapshot


def _seed_draft(db):
    user = User(
        id=new_id(),
        email="staff@risklocker.test",
        name="Staff User",
        role=Role.STAFF.value,
        password_hash="x",
        status=AccountStatus.ACTIVE.value,
    )
    company = InsuranceCompany(
        id=new_id(),
        name="Liberty",
        slug="liberty",
        detection_phrases=["Liberty"],
        status=AccountStatus.ACTIVE.value,
    )
    batch = Batch(id=new_id(), owner_id=user.id, name="Custom Benefit Batch", status=RecordStatus.READY.value)
    uf = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="liberty.pdf",
        content_type="application/pdf",
        storage_path=f"test/{new_id()}.pdf",
        storage_provider="local_ephemeral",
        size_bytes=128,
        status=RecordStatus.READY.value,
    )
    db.add_all([user, company, batch, uf])
    db.flush()

    draft = QuotationDraft(
        id=new_id(),
        revision=1,
        uploaded_file_id=uf.id,
        owner_id=user.id,
        company_id=company.id,
        status=RecordStatus.READY.value,
        fields={
            "customer_name": {"value": "TAN WEI MING", "status": "ready"},
            "vehicle_no": {"value": "VAA1234", "status": "ready"},
            "car_model": {"value": "HONDA CIVIC", "status": "ready"},
            "insurance_company": {"value": "Liberty", "status": "ready"},
            "premium": {"value": "1200.00", "status": "ready"},
            "total_amount": {"value": "1200.00", "status": "ready"},
        },
        display_options={"include_road_tax": False, "include_runner_fee": False},
        scalar_decisions={},
    )
    db.add(draft)
    db.flush()

    sess = QuotationSession(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uf.id,
        draft_id=draft.id,
        detected_company="Liberty",
        status=AccountStatus.ACTIVE.value,
    )
    db.add(sess)
    db.commit()
    return user, sess, draft


def test_custom_benefit_preserves_description_limit_and_design2_parity(db_session):
    user, sess, draft = _seed_draft(db_session)

    res = apply_workspace_patch(
        db_session,
        user,
        draft.id,
        base_revision=draft.revision,
        operations=[
            {
                "op": "create_custom_benefit",
                "selection_key": "custom:betterment-5yr",
                "label": "waiver of betterment",
                "typed_value": {"type": "custom", "display_text": "5 years"},
                "description": "Upto 5 years of betterment for your parts.",
                "icon_hint": "betterment",
                "cost_status": "included",
                "state": "current",
            }
        ],
    )
    assert res["revision"] == 2

    snap = build_workspace_snapshot(db_session, user, sess.id)
    curr = snap["benefit_cards"]["current_benefits"]
    card = next(c for c in curr if c["label"] == "waiver of betterment")
    assert card["value"] == "5 years"
    assert card["description"] == "Upto 5 years of betterment for your parts."
    assert card["icon_hint"] == "betterment"
    assert card["cost_status"] == "included"

    html = render_design2_html(
        draft.fields,
        template_config={"language_mode": "en"},
        render_context={
            "current_benefits": curr,
            "available_addons": snap["benefit_cards"]["available_addons"],
        },
        db=db_session,
    )
    assert "waiver of betterment (5 years)" in html
    assert "Upto 5 years of betterment for your parts." in html


def test_custom_benefit_empty_limit_never_copies_label_and_avoids_concept_collision(db_session):
    user, sess, draft = _seed_draft(db_session)

    concept = BenefitConcept(
        id=new_id(),
        concept_key="betterment-protection",
        label="Waiver of Betterment",
        description="Existing catalog concept description",
        sort_order=1,
    )
    existing_sel = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="catalog:existing-betterment",
        concept_id=concept.id,
        item_kind="catalog",
        state="current",
        cost_status="paid",
        label_override="Waiver of Betterment",
        typed_value_override={"type": "custom", "display_text": "Up to 15 Years"},
        evidence_snapshot={},
        sort_order=1,
    )
    db_session.add_all([concept, existing_sel])
    db_session.commit()

    # Custom benefit with same case-insensitive label and empty limit must NOT crash RenderContext
    # and must keep value empty ("") rather than copying label ("Waiver of Betterment")
    apply_workspace_patch(
        db_session,
        user,
        draft.id,
        base_revision=draft.revision,
        operations=[
            {
                "op": "create_custom_benefit",
                "selection_key": "custom:second-betterment",
                "label": "waiver of betterment",
                "typed_value": {"type": "text", "display_text": "", "hide_limit": True},
                "description": "Custom parts waiver note.",
                "icon_hint": "betterment",
                "cost_status": "included",
                "state": "current",
            }
        ],
    )

    snap = build_workspace_snapshot(db_session, user, sess.id)
    custom_card = next(
        c for c in snap["benefit_cards"]["current_benefits"] if c.get("description") == "Custom parts waiver note."
    )
    assert custom_card["label"] == "waiver of betterment"
    assert custom_card["value"] == ""
    assert custom_card["hide_coverage"] is True
    assert custom_card["icon_hint"] == "betterment"


def test_polish_benefit_description_auth_fallback_and_gemini(monkeypatch):
    # 1. Unauthenticated request is rejected
    unauth_app = FastAPI()
    register_error_handlers(unauth_app)
    unauth_app.include_router(routes.router, prefix="/api")
    unauth_client = TestClient(unauth_app)
    unauth_res = unauth_client.post(
        "/api/copilot/polish-benefit-description",
        json={"label": "Waiver of Betterment", "coverage_limit": "5 years"},
    )
    assert unauth_res.status_code in (401, 403)

    # 2. Authenticated client
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="staff-1", role=Role.STAFF.value)
    authed_client = TestClient(app)

    # 2a. Offline / no-keys fallback preserves limit (5 years) cleanly
    class _EmptyPool:
        def get_all_keys(self):
            return []

    monkeypatch.setattr(benefit_description_ai, "get_key_pool", lambda: _EmptyPool())
    fb_res = authed_client.post(
        "/api/copilot/polish-benefit-description",
        json={
            "label": "waiver of betterment",
            "coverage_limit": "5 years",
            "draft_description": "Upto 5 years of waiver",
            "placement": "addon",
        },
    )
    assert fb_res.status_code == 200
    fb_body = fb_res.json()
    assert fb_body["source"] == "fallback"
    assert "5 years" in fb_body["description"]

    # 2b. Mocked Gemini response returns cleaned single-sentence output
    class _MockPool:
        recorded = 0

        def get_all_keys(self):
            return ["fake-key"]

        def get_next_key(self):
            return "fake-key"

        def record_request(self):
            self.recorded += 1

    class _MockResp:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '"Covers full cost of new repair parts with zero wear-and-tear deductions for up to 5 years"'
                                }
                            ]
                        }
                    }
                ]
            }

    class _MockHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None):
            return _MockResp()

    mock_pool = _MockPool()
    monkeypatch.setattr(benefit_description_ai, "get_key_pool", lambda: mock_pool)
    monkeypatch.setattr(benefit_description_ai.httpx, "Client", _MockHttpxClient)

    gem_res = authed_client.post(
        "/api/copilot/polish-benefit-description",
        json={
            "label": "waiver of betterment",
            "coverage_limit": "5 years",
            "draft_description": "Upto 5 years of waiver",
            "placement": "addon",
            "insurer_name": "Liberty",
            "vehicle_type": "Car",
        },
    )
    assert gem_res.status_code == 200
    gem_body = gem_res.json()
    assert gem_body["source"] == "gemini"
    assert gem_body["description"] == "Covers full cost of new repair parts with zero wear-and-tear deductions for up to 5 years."
    assert mock_pool.recorded == 1
