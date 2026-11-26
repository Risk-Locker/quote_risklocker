"""Hermetic tests for v30.8: RealtimeHub SSE/presence, Box 1 coverage sync, and untruncated Design 2 cards."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api.deps import current_user
from app.api.routers.realtime import router as realtime_router
from app.models.enums import AccountStatus, Role
from app.models.tables import User, new_id
from app.rendering.template_renderer_design2 import render_design2_html
from app.rendering.unified_addon_engine import extract_free_coverage_items
from app.services.realtime_hub import RealtimeHub, format_sse_message, realtime_hub


def _make_user(role: str = Role.STAFF.value, email: str = "staff@risklocker.test") -> User:
    return User(
        id=new_id(),
        email=email,
        name="Staff User",
        password_hash="x",
        role=role,
        status=AccountStatus.ACTIVE.value,
    )


def test_realtime_hub_bounded_queue_utf8_and_presence_ttl():
    async def _run() -> None:
        hub = RealtimeHub(presence_ttl=0.05, max_queue_size=3)
        loop = asyncio.get_running_loop()
        sub_id, queue = hub.subscribe("u1", loop)
        try:
            # Overflow queue past max_queue_size=3 -> drops oldest, keeps latest 3
            for idx in range(5):
                hub.publish_update(
                    scope="ledger",
                    resource_id=f"res-{idx}",
                    actor_id="u2",
                    actor_email="other@risklocker.test",
                    actor_name="Other 编辑",
                    summary=f"Update #{idx} 中文",
                )
            await asyncio.sleep(0)
            events = []
            while not queue.empty():
                events.append(queue.get_nowait())
            assert len(events) == 3
            assert [e["data"]["resource_id"] for e in events] == ["res-2", "res-3", "res-4"]
            sse_frame = format_sse_message("updated", events[-1]["data"])
            assert "Other 编辑" in sse_frame
            assert "Update #4 中文" in sse_frame

            # Worker-thread publish via call_soon_threadsafe
            import threading

            t = threading.Thread(
                target=lambda: hub.publish_update(
                    scope="comparison",
                    resource_id="ten-9",
                    actor_id="u2",
                    actor_email="other@risklocker.test",
                    actor_name="Other",
                    summary="Thread save",
                )
            )
            t.start()
            t.join(timeout=2.0)
            await asyncio.sleep(0.01)
            thread_ev = queue.get_nowait()
            assert thread_ev["data"]["scope"] == "comparison"
            assert thread_ev["data"]["resource_id"] == "ten-9"

            # Presence set, clear, and TTL expiry
            editors = hub.set_presence(
                scope="comparison",
                resource_id="ten-1",
                user_id="u2",
                user_email="other@risklocker.test",
                user_name="Other",
                field="towing",
            )
            assert len(editors) == 1
            assert editors[0]["field"] == "towing"

            await asyncio.sleep(0.08)
            assert hub.get_presence("comparison", "ten-1") == []

            hub.set_presence(
                scope="workspace",
                resource_id="d1",
                user_id="u2",
                user_email="other@risklocker.test",
                user_name="Other",
                field="premium",
            )
            assert hub.clear_presence(scope="workspace", resource_id="d1", user_id="u2") == []
        finally:
            hub.unsubscribe(sub_id)

    asyncio.run(_run())


def test_realtime_router_presence_validation_and_roundtrip():
    realtime_hub.reset_for_tests()
    app = FastAPI()
    app.include_router(realtime_router, prefix="/api")
    user = _make_user(Role.ADMIN.value, "system@risklocker.test")
    app.dependency_overrides[current_user] = lambda: user

    with TestClient(app) as client:
        # Valid presence POST + GET + DELETE
        post_res = client.post(
            "/api/realtime/presence",
            json={"scope": "comparison", "resource_id": "tenure-123", "field": "windscreen"},
        )
        assert post_res.status_code == 200
        body = post_res.json()
        assert body["ok"] is True
        assert body["active_editors"][0]["user_email"] == "system@risklocker.test"
        assert body["active_editors"][0]["field"] == "windscreen"

        get_res = client.get("/api/realtime/presence", params={"scope": "comparison", "resource_id": "tenure-123"})
        assert get_res.status_code == 200
        assert len(get_res.json()["active_editors"]) == 1

        del_res = client.delete("/api/realtime/presence", params={"scope": "comparison", "resource_id": "tenure-123"})
        assert del_res.status_code == 200
        assert del_res.json()["active_editors"] == []

        # Invalid scope / oversized field rejected by Pydantic (422)
        bad_scope = client.post("/api/realtime/presence", json={"scope": "invalid_scope", "resource_id": "x"})
        assert bad_scope.status_code == 422
        bad_field = client.post(
            "/api/realtime/presence",
            json={"scope": "ledger", "resource_id": "x", "field": "a" * 121},
        )
        assert bad_field.status_code == 422


def test_realtime_per_resource_versioning_and_first_person_priority():
    """Updates on resource A must not bump resource B's version, and earliest entrant retains priority across heartbeats."""
    realtime_hub.reset_for_tests()
    app = FastAPI()
    app.include_router(realtime_router, prefix="/api")
    user_a = _make_user(Role.STAFF.value, "first@risklocker.test")
    user_a.name = "First Editor"
    user_b = _make_user(Role.STAFF.value, "second@risklocker.test")
    user_b.name = "Second Editor"

    # Resource A update must leave Resource B at version 0
    realtime_hub.publish_update(
        scope="workspace",
        resource_id="sess-A",
        actor_id=user_a.id,
        actor_email=user_a.email,
        actor_name=user_a.name,
        origin_tab_id="tab-1",
        summary="Edited sess-A",
    )
    assert realtime_hub.get_resource_state("workspace", "sess-A")["version"] == 1
    assert realtime_hub.get_resource_state("workspace", "sess-B")["version"] == 0

    app.dependency_overrides[current_user] = lambda: user_b
    with TestClient(app) as client:
        res_b = client.get("/api/realtime/presence", params={"scope": "workspace", "resource_id": "sess-B"})
        assert res_b.status_code == 200
        assert res_b.json()["version"] == 0

    # First-person priority ordering preserved across heartbeats
    realtime_hub.set_presence(
        scope="workspace",
        resource_id="sess-B",
        user_id=user_a.id,
        user_email=user_a.email,
        user_name=user_a.name,
        tab_id="tab-a",
    )
    time.sleep(0.02)
    realtime_hub.set_presence(
        scope="workspace",
        resource_id="sess-B",
        user_id=user_b.id,
        user_email=user_b.email,
        user_name=user_b.name,
        tab_id="tab-b",
    )
    # Heartbeat from first user must keep first user at index 0
    time.sleep(0.02)
    editors = realtime_hub.set_presence(
        scope="workspace",
        resource_id="sess-B",
        user_id=user_a.id,
        user_email=user_a.email,
        user_name=user_a.name,
        field="car_model",
        tab_id="tab-a",
    )
    assert [e["user_id"] for e in editors] == [user_a.id, user_b.id]
    assert editors[0]["entered_at"] < editors[1]["entered_at"]

    # upload_runs scope must be accepted on /realtime/presence (never 422)
    with TestClient(app) as client:
        res_run = client.get("/api/realtime/presence", params={"scope": "upload_runs", "resource_id": "run-1"})
        assert res_run.status_code == 200
        assert res_run.json()["scope"] == "upload_runs"
        assert res_run.json()["resource_id"] == "run-1"


def test_box1_free_coverage_strips_365km_and_rm200_on_hide_or_override():
    # 1. Hidden or cleared coverage strips embedded (365 km) & (RM 200)
    hidden_items = extract_free_coverage_items(
        [
            {
                "id": "tow",
                "concept_key": "towing",
                "label": "Emergency Towing Assistance (365 km)",
                "value": "365 km",
                "cost_status": "included",
                "typed_value_override": {"type": "custom", "display_text": "365 km", "hide_limit": True},
            },
            {
                "id": "legal",
                "concept_key": "legal_defense",
                "label": "Legal Defense Costs (RM 200)",
                "value": "RM 200",
                "cost_status": "foc",
                "typed_value_override": {"type": "custom", "display_text": "", "hide_limit": True},
            },
        ],
        insurer_name="Etiqa",
        vehicle_type="Private Car",
    )
    assert len(hidden_items) == 2
    assert hidden_items[0]["title"] == "Emergency Towing Assistance"
    assert "365 km" not in hidden_items[0]["title"]
    assert hidden_items[1]["title"] == "Legal Defense Costs"
    assert "RM 200" not in hidden_items[1]["title"]

    # 2. Manual value override replaces embedded (365 km) & (RM 200) cleanly
    edited_items = extract_free_coverage_items(
        [
            {
                "id": "tow",
                "concept_key": "towing",
                "label": "Emergency Towing Assistance (365 km)",
                "value": "150 km",
                "cost_status": "included",
                "typed_value_override": {"type": "custom", "display_text": "150 km", "hide_limit": False},
            },
            {
                "id": "legal",
                "concept_key": "legal_defense",
                "label": "Legal Defense Costs (RM 200)",
                "value": "RM 500",
                "cost_status": "foc",
                "typed_value_override": {"type": "custom", "display_text": "RM 500", "hide_limit": False},
            },
        ],
        insurer_name="Etiqa",
        vehicle_type="Private Car",
    )
    assert edited_items[0]["title"] == "Emergency Towing Assistance (150 km)"
    assert "365 km" not in edited_items[0]["title"]
    assert edited_items[1]["title"] == "Legal Defense Costs (RM 500)"
    assert "RM 200" not in edited_items[1]["title"]


def test_design2_box2_untruncated_descriptions_and_single_page_fit(tmp_path):
    from app.rendering.pdf_generator import html_to_pdf

    long_ehailing_desc = "Permits comprehensive motor insurance coverage during registered e-hailing rides and passenger trips."
    fields = {
        "customer_name": {"value": "TAN WEI MING"},
        "quotation_reference": {"value": "RL260000999"},
        "vehicle_no": {"value": "VAB 8899"},
        "insurance_company": {"value": "ETIQA GENERAL INSURANCE BERHAD"},
        "car_model": {"value": "BYD Seal Premium"},
        "cover_period": {"value": "01-07-2026 TO 30-06-2027"},
        "coverage_type": {"value": "Comprehensive"},
        "ncd_percent": {"value": "55.00%"},
        "valuation_type": {"value": "Agreed Value"},
        "excess_amount": {"value": "0.00"},
        "coverage_amount": {"value": "150000.00"},
        "premium": {"value": "3400.00"},
        "roadtax": {"value": "90.00"},
        "runner_fee": {"value": "0.00"},
        "total_amount": {"value": "3490.00"},
    }
    addons = [
        {
            "id": "ehailing",
            "label": "Private Hire Car (E-Hailing)",
            "description": long_ehailing_desc,
            "value": "Covered",
        }
    ] + [
        {
            "id": f"addon-{i}",
            "label": f"Motor Benefit {i}",
            "description": f"Extended policy protection cover option #{i} for private vehicles.",
        }
        for i in range(2, 25)
    ]

    html = render_design2_html(
        fields,
        render_context={"current_benefits": [], "available_addons": addons, "fill_to_slots": 24},
    )
    assert long_ehailing_desc in html
    lower_part = html.split("ADDITIONAL PROTECTION FOR GREATER PEACE OF MIND")[1]
    assert "-webkit-line-clamp" not in lower_part
    assert "text-overflow: ellipsis" not in lower_part
    assert "height: 73px" not in html

    out_pdf = tmp_path / "design2_untruncated_24.pdf"
    pdf_path, _warnings = html_to_pdf(html, out_pdf, width=794, height=1123)
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF-")

    try:
        import fitz

        doc = fitz.open(str(pdf_path))
        assert doc.page_count == 1
        page_text = doc[0].get_text()
        assert "registered e-hailing rides" in page_text
        doc.close()
    except ImportError:
        pass


def test_runner_fee_never_extracted_from_pdf_and_follows_studio_default():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.errors import AppError
    from app.extraction.candidate_finder import find_candidates
    from app.extraction.draft_mapper import reconcile_vehicle_capacity_and_fees
    from app.models.tables import Base
    from app.services.admin_service import get_runner_fee_default, set_runner_fee_default
    from app.services.insurance_tenure_service import resolve_or_create_tenure

    # 1. Quotation PDF text mentioning "Service Fee: RM 10.00" or "Runner Fee: RM 25.00" must NEVER extract service_fee
    sample_pdf_text = "ETIQA MOTOR QUOTATION\nService Fee: RM 10.00\nRunner Fee: RM 25.00\nTotal Payable: RM 1250.00\n"
    cands = find_candidates(sample_pdf_text, [{"page": 1, "text": sample_pdf_text}], aliases={})
    assert cands.get("service_fee", []) == []

    # 2. Studio Runner fee (default) setting drives future drafts & new tenures regardless of MyKad or Passport
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        admin = _make_user(Role.ADMIN.value, "admin@risklocker.test")
        assert get_runner_fee_default(db) == 20.0

        with pytest.raises(AppError):
            set_runner_fee_default(db, admin, -5.0)

        set_runner_fee_default(db, admin, 20.0)
        fields_20 = {
            "customer_name": {"value": "PASSPORT HOLDER NAME"},
            "ic_no": {"value": "A12345678"},
            "car_model": {"value": "Honda City"},
            "engine_cc": {"value": "1500 CC"},
            "service_fee": {"value": "10.00"},  # stale/noise value must be overridden by Studio default
        }
        reconcile_vehicle_capacity_and_fees(fields_20, raw_text=sample_pdf_text, db=db)
        assert fields_20["service_fee"]["value"] == "20.00"

        t1 = resolve_or_create_tenure(
            db,
            vehicle_no="VAA 1122",
            customer_name="PASSPORT HOLDER NAME",
            start_date="2026-11-01",
            end_date="2027-10-31",
        )
        assert float(t1.runner_fee) == 20.0

        # Admin updates Studio default to RM 25.00 -> future tenures/quotations pick up 25.00; existing t1 stays 20.00
        set_runner_fee_default(db, admin, 25.0)
        fields_25 = {
            "customer_name": {"value": "MYKAD HOLDER"},
            "ic_no": {"value": "900101145555"},
            "car_model": {"value": "Perodua Myvi"},
            "engine_cc": {"value": "1500 CC"},
        }
        reconcile_vehicle_capacity_and_fees(fields_25, raw_text=sample_pdf_text, db=db)
        assert fields_25["service_fee"]["value"] == "25.00"

        t2 = resolve_or_create_tenure(
            db,
            vehicle_no="VBB 3344",
            customer_name="MYKAD HOLDER",
            start_date="2026-11-05",
            end_date="2027-11-04",
        )
        assert float(t2.runner_fee) == 25.0
        assert float(t1.runner_fee) == 20.0


def test_realtime_hub_multi_target_and_origin_tab_id():
    """Publishing with targets + origin_tab_id fans out across comparison/workspace/ledger without dropping same-user tabs."""
    async def _run() -> None:
        hub = RealtimeHub(max_queue_size=16)
        loop = asyncio.get_running_loop()
        sub_id, queue = hub.subscribe("u1", loop)
        try:
            hub.publish_update(
                scope="comparison",
                resource_id="ten-42",
                actor_id="u1",
                actor_email="staff@risklocker.test",
                actor_name="Staff",
                summary="Towing upgraded",
                targets=[
                    ("comparison", "ten-42"),
                    ("workspace", "sess-1"),
                    ("workspace", "draft-1"),
                    ("ledger", "ten-42"),
                ],
                origin_tab_id="tab-1-uuid",
            )
            await asyncio.sleep(0)
            events = []
            while not queue.empty():
                events.append(queue.get_nowait()["data"])
            got = {(ev["scope"], ev["resource_id"]) for ev in events}
            assert got == {
                ("comparison", "ten-42"),
                ("workspace", "sess-1"),
                ("workspace", "draft-1"),
                ("ledger", "ten-42"),
            }
            assert all(ev["origin_tab_id"] == "tab-1-uuid" for ev in events)
        finally:
            hub.unsubscribe(sub_id)

    asyncio.run(_run())

