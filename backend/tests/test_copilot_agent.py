from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import create_app
from app.core.config import get_settings
from app.core.security import csrf_token_for_session, generate_session_token, hash_password, hash_session_token
from app.db.session import get_db
from app.models.enums import AccountStatus, Role
from app.models.tables import (
    AuthSession,
    Base,
    CopilotArtifact,
    CopilotMessage,
    CopilotThread,
    CustomerAccount,
    InsuranceCompany,
    InsuranceTenure,
    PersonInCharge,
    TenureComparisonEntry,
    TrackedVehicle,
    User,
    new_id,
)
from app.services.ai_fleet_gateway import GeminiFleetGateway
from app.services.copilot_agent_service import stream_agent_turn
from app.services.copilot_excel_service import export_sql_to_excel, resolve_artifact_file_path
from app.services.copilot_sql_guard import SQLGuardError, ensure_semantic_views, execute_readonly_sql, validate_readonly_sql
from app.services.gemini_account_service import GeminiAccount


@pytest.fixture()
def sqlite_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionMaker = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    with SessionMaker() as db:
        ensure_semantic_views(db)
        db.commit()
    try:
        yield SessionMaker
    finally:
        engine.dispose()


def _seed_agency_data(SessionMaker):
    with SessionMaker() as db:
        admin = User(
            id=new_id(),
            name="Admin User",
            email="admin@risklocker.test",
            password_hash=hash_password("Pass123!"),
            role=Role.ADMIN.value,
            status=AccountStatus.ACTIVE.value,
        )
        staff_a = User(
            id=new_id(),
            name="Staff Alice",
            email="alice@risklocker.test",
            password_hash=hash_password("Pass123!"),
            role=Role.STAFF.value,
            status=AccountStatus.ACTIVE.value,
        )
        staff_b = User(
            id=new_id(),
            name="Staff Bob",
            email="bob@risklocker.test",
            password_hash=hash_password("Pass123!"),
            role=Role.STAFF.value,
            status=AccountStatus.ACTIVE.value,
        )
        db.add_all([admin, staff_a, staff_b])

        comp_stmb = InsuranceCompany(id=new_id(), name="STMB", slug="stmb", status="active")
        comp_lonpac = InsuranceCompany(id=new_id(), name="Lonpac", slug="lonpac", status="active")
        db.add_all([comp_stmb, comp_lonpac])

        pic = PersonInCharge(id=new_id(), name="Daniel Lim", type="subagent", agency_group="BNI")
        db.add(pic)

        cust = CustomerAccount(
            id=new_id(),
            entity_type="individual",
            id_type="nric",
            id_number="900101145678",
            canonical_name="Tan Ah Kow",
            is_fleet=True,
        )
        db.add(cust)

        veh1 = TrackedVehicle(
            id=new_id(),
            vehicle_no="JWX 1234",
            car_brand="Mazda",
            car_model="CX-5 2.0G",
            engine_cc="1998",
            manufacture_year=2022,
            customer_id=cust.id,
        )
        veh2 = TrackedVehicle(
            id=new_id(),
            vehicle_no="VAA 888",
            car_brand="Toyota",
            car_model="Alphard 2.5",
            engine_cc="2494",
            manufacture_year=2023,
            customer_id=cust.id,
        )
        db.add_all([veh1, veh2])

        t_2025 = InsuranceTenure(
            id=new_id(),
            tracked_vehicle_id=veh1.id,
            vehicle_no="JWX 1234",
            customer_name="Tan Ah Kow",
            customer_id=cust.id,
            coverage_start_date=datetime(2025, 12, 15, tzinfo=timezone.utc),
            coverage_end_date=datetime(2026, 12, 14, tzinfo=timezone.utc),
            expiry_month="2026-12",
            stage="Hit",
            status="active",
            winning_company_id=comp_lonpac.id,
            won_premium=Decimal("1695.00"),
            road_tax=Decimal("379.00"),
            runner_fee=Decimal("20.00"),
            ncd_percentage=Decimal("55.00"),
            pic_id=pic.id,
        )
        t_2026 = InsuranceTenure(
            id=new_id(),
            tracked_vehicle_id=veh1.id,
            vehicle_no="JWX 1234",
            customer_name="Tan Ah Kow",
            customer_id=cust.id,
            coverage_start_date=datetime(2026, 12, 15, tzinfo=timezone.utc),
            coverage_end_date=datetime(2027, 12, 14, tzinfo=timezone.utc),
            expiry_month="2027-12",
            stage="Pending",
            status="active",
            road_tax=Decimal("379.00"),
            runner_fee=Decimal("20.00"),
            ncd_percentage=Decimal("55.00"),
            pic_id=pic.id,
        )
        t_888 = InsuranceTenure(
            id=new_id(),
            tracked_vehicle_id=veh2.id,
            vehicle_no="VAA 888",
            customer_name="=CMD|' /C calc'!A0",
            customer_id=cust.id,
            coverage_start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
            coverage_end_date=datetime(2027, 9, 30, tzinfo=timezone.utc),
            expiry_month="2027-09",
            stage="Quotations",
            status="active",
            road_tax=Decimal("874.00"),
            runner_fee=Decimal("20.00"),
            pic_id=pic.id,
        )
        db.add_all([t_2025, t_2026, t_888])

        q1 = TenureComparisonEntry(
            id=new_id(),
            tenure_id=t_2026.id,
            company_name="STMB",
            company_id=comp_stmb.id,
            sum_insured=Decimal("98000.00"),
            motor_premium=Decimal("1143.30"),
            road_tax=Decimal("379.00"),
            runner_fee=Decimal("20.00"),
            total_payable=Decimal("1542.30"),
            towing_limit="365km",
            towing_km="365km",
            special_perils="Included",
            rank=1,
            is_recommended=True,
        )
        q2 = TenureComparisonEntry(
            id=new_id(),
            tenure_id=t_2026.id,
            company_name="Lonpac",
            company_id=comp_lonpac.id,
            sum_insured=Decimal("98000.00"),
            motor_premium=Decimal("1211.80"),
            road_tax=Decimal("379.00"),
            runner_fee=Decimal("20.00"),
            total_payable=Decimal("1610.80"),
            towing_limit="200km",
            towing_km="200km",
            rank=2,
            is_recommended=False,
        )
        db.add_all([q1, q2])
        db.commit()
        return {
            "admin": admin.id,
            "staff_a": staff_a.id,
            "staff_b": staff_b.id,
            "veh1": veh1.id,
            "veh2": veh2.id,
            "t_2025": t_2025.id,
            "t_2026": t_2026.id,
            "t_888": t_888.id,
        }


# ---------------------------------------------------------------------------
# 1. SQL Guard Security Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "malicious_sql",
    [
        "DROP TABLE users",
        "DELETE FROM insurance_tenures",
        "UPDATE ai_v_motor_ledger SET stage = 'Hit'",
        "INSERT INTO users (email) VALUES ('evil@x.com')",
        "SELECT * FROM users",
        "SELECT * FROM auth_sessions",
        "SELECT * FROM app_settings",
        "SELECT * FROM ai_v_motor_ledger; DROP TABLE users",
        "SELECT /* comment */ * FROM pg_catalog.pg_tables",
        "SELECT pg_sleep(5)",
        "WITH RECURSIVE r AS (SELECT 1 UNION ALL SELECT 1 FROM r) SELECT * FROM r",
        "SELECT $$hello$$ FROM ai_v_motor_ledger",
        "SELECT * FROM information_schema.tables",
    ],
)
def test_sql_guard_blocks_unsafe_queries(malicious_sql: str):
    with pytest.raises(SQLGuardError):
        validate_readonly_sql(malicious_sql, max_rows=50)


def test_sql_guard_allows_safe_views_and_masks_nric(sqlite_db):
    _seed_agency_data(sqlite_db)
    with sqlite_db() as db:
        res = execute_readonly_sql(
            db,
            "WITH cte AS (SELECT * FROM ai_v_motor_ledger WHERE REPLACE(UPPER(vehicle_no), ' ', '') LIKE '%88%') "
            "SELECT tenure_id, vehicle_no, policy_year FROM cte",
            max_rows=50,
        )
        assert res["row_count"] == 1
        assert res["rows"][0]["vehicle_no"] == "VAA 888"

        # String literal containing forbidden word in WHERE does not trigger false positive
        lit_res = execute_readonly_sql(
            db,
            "SELECT canonical_name, masked_id_number FROM ai_v_clients_fleet WHERE canonical_name != 'DROP'",
            max_rows=50,
        )
        assert lit_res["row_count"] == 1
        assert lit_res["rows"][0]["masked_id_number"].endswith("5678")
        assert "900101" not in lit_res["rows"][0]["masked_id_number"]


# ---------------------------------------------------------------------------
# 2. Dynamic N-Key Fleet Scaling & Concurrency Tests
# ---------------------------------------------------------------------------


def test_dynamic_n_key_ring_fence_and_dedicated_isolation(monkeypatch):
    gw = GeminiFleetGateway(force_memory=True)

    # Start with 2 shared keys (4 lanes * 480 = 1920 RPD -> 20% Copilot cap = 384)
    acc1 = GeminiAccount(id="k1", key="AIzaSyFakeKeyOne1111111111111", label="Key 1", status="ready", workload_scope="all")
    acc2 = GeminiAccount(id="k2", key="AIzaSyFakeKeyTwo2222222222222", label="Key 2", status="ready", workload_scope="all")
    accounts_ref = [acc1, acc2]

    fake_pool = SimpleNamespace(
        _parallel_models=("gemini-3.1-flash-lite", "gemini-3.5-flash-lite"),
        _max_rpd_per_key=480,
        _max_rpm_per_key=13,
        _max_tpm_per_key=200_000,
        sync_accounts=lambda **kw: None,
        get_accounts=lambda: list(accounts_ref),
        record_success=lambda **kw: None,
        record_failure=lambda *a, **kw: None,
    )
    monkeypatch.setattr("app.services.ai_fleet_gateway.get_key_pool", lambda: fake_pool)

    # Set policy with tight 10% shared cap over 10-RPD test lanes? Let's test via policy override:
    gw._copilot_policy_override = {"enabled": True, "shared_copilot_rpd_pct": 10, "shared_interactive_reserve_pct": 10}

    # Reserve 1 copilot slot on shared pool -> succeeds and sets interactive_yield_until
    res_c, wait_c, daily_c = gw.reserve_lane(purpose="copilot_agent", priority=10)
    assert res_c is not None
    assert wait_c == 0.0
    assert daily_c is False

    # Concurrent bulk extraction worker (priority=100) yields politely to active interactive chat!
    res_b, wait_b, daily_b = gw.reserve_lane(purpose="extraction", priority=100)
    assert res_b is None
    assert daily_b is False
    assert wait_b > 0.0

    # Add Key 3 as dedicated copilot_only & Key 4 as dedicated extraction_only (N-key auto-scaling)
    acc3 = GeminiAccount(id="k3", key="AIzaSyFakeKeyThree333333333333", label="Key 3 Copilot", status="ready", workload_scope="copilot_only")
    acc4 = GeminiAccount(id="k4", key="AIzaSyFakeKeyFour4444444444444", label="Key 4 Extract", status="ready", workload_scope="extraction_only")
    accounts_ref.extend([acc3, acc4])

    # Copilot prefers dedicated k3 lane, extraction never touches k3
    res_c2, _, _ = gw.reserve_lane(purpose="copilot_agent", priority=10)
    assert res_c2 is not None
    assert res_c2.account_id == "k3"

    res_e2, _, _ = gw.reserve_lane(purpose="extraction", priority=100)
    assert res_e2 is not None
    assert res_e2.account_id == "k4"

    # Admin kill switch blocks Copilot immediately while extraction still respects 1.8s key gap & continues
    gw._copilot_policy_override = {"enabled": False}
    res_paused, _, daily_paused = gw.reserve_lane(purpose="copilot_agent", priority=10)
    assert res_paused is None
    assert daily_paused is True
    res_wait, wait_e3, daily_e3 = gw.reserve_lane(purpose="extraction", priority=100)
    assert res_wait is None and daily_e3 is False and wait_e3 > 0.0
    # Advance k4's dispatch clock past 1.8s key spacing
    for lid, st in gw._mem_lanes.items():
        if st.account_id == "k4":
            st.last_dispatched_at -= 2.5
    res_e3, _, _ = gw.reserve_lane(purpose="extraction", priority=100)
    assert res_e3 is not None
    assert res_e3.account_id == "k4"


# ---------------------------------------------------------------------------
# 3. Zero-Token Excel Export Tests
# ---------------------------------------------------------------------------


def test_zero_token_excel_export_sanitizes_and_sums(sqlite_db):
    ids = _seed_agency_data(sqlite_db)
    with sqlite_db() as db:
        user = db.get(User, ids["staff_a"])
        thread = CopilotThread(id=new_id(), user_id=user.id, title="Excel Test")
        db.add(thread)
        db.flush()

        artifact, meta = export_sql_to_excel(
            db,
            user=user,
            thread_id=thread.id,
            message_id=None,
            sql="SELECT vehicle_no, customer_name, policy_year, stage, won_premium, road_tax FROM ai_v_motor_ledger ORDER BY vehicle_no",
            filename="agency_tenures.xlsx",
            sheet_name="Ledger",
        )
        db.commit()

        assert meta["row_count"] == 3
        assert len(meta["sample_rows"]) == 3
        assert artifact.filename == "agency_tenures.xlsx"
        fpath = resolve_artifact_file_path(artifact)
        assert fpath is not None and fpath.exists()

        wb = openpyxl.load_workbook(str(fpath))
        ws = wb["Ledger"]
        # Row 4 (VAA 888) has formula injection customer name '=CMD... -> prefixed with single quote
        customer_vals = [ws.cell(row=r, column=2).value for r in range(2, 5)]
        assert any(isinstance(v, str) and v.startswith("'=CMD") for v in customer_vals)
        # Totals row at row 5 uses Excel =SUM(...)
        assert str(ws.cell(row=5, column=1).value) == "TOTAL"
        assert str(ws.cell(row=5, column=5).value).startswith("=SUM(")


# ---------------------------------------------------------------------------
# 4. Agentic ReAct Multi-Hop Loop & Thread HTTP API Tests
# ---------------------------------------------------------------------------


def test_react_loop_multi_year_comparison_and_self_healing_sql(sqlite_db, monkeypatch):
    ids = _seed_agency_data(sqlite_db)
    gw = GeminiFleetGateway(force_memory=True)

    fake_pool = SimpleNamespace(
        _parallel_models=("gemini-3.1-flash-lite",),
        _max_rpd_per_key=480,
        _max_rpm_per_key=13,
        _max_tpm_per_key=200_000,
        sync_accounts=lambda **kw: None,
        get_accounts=lambda: [GeminiAccount(id="k1", key="AIzaSyTestKey1234567890123456", label="K1", status="ready")],
        get_all_keys=lambda: ["AIzaSyTestKey1234567890123456"],
        record_success=lambda **kw: None,
        record_failure=lambda *a, **kw: None,
    )
    monkeypatch.setattr("app.services.ai_fleet_gateway.get_key_pool", lambda: fake_pool)
    monkeypatch.setattr("app.services.copilot_agent_service.get_key_pool", lambda: fake_pool)

    call_step = {"n": 0}

    def fake_execute_gemini_request(**kwargs):
        call_step["n"] += 1
        step = call_step["n"]
        if kwargs.get("telemetry_log") is not None:
            kwargs["telemetry_log"].append(
                {"model": "gemini-3.1-flash-lite", "prompt_tokens": 300, "candidate_tokens": 80, "total_tokens": 380}
            )
        if step == 1:
            # Hop 1: intentional bad table name -> triggers self-healing error back to LLM
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "run_readonly_sql",
                                        "args": {"sql": "SELECT * FROM bad_table", "reason": "Lookup JWX1234"},
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        if step == 2:
            # Hop 2: LLM self-heals and queries ai_v_motor_ledger
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "run_readonly_sql",
                                        "args": {
                                            "sql": "SELECT tenure_id, vehicle_no, customer_name, policy_year, stage, won_premium FROM ai_v_motor_ledger WHERE REPLACE(UPPER(vehicle_no), ' ', '') LIKE '%JWX1234%'",
                                            "reason": "Fetch all policy years for JWX 1234",
                                        },
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        # Hop 3: Final multi-year conversational answer
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    "**JWX 1234** (*Tan Ah Kow*) has **2 policy years** on record:\n"
                                    "- **2026–2027 (Pending)**: STMB recommended at **RM 1,542.30**\n"
                                    "- **2025–2026 (Hit)**: Lonpac at **RM 1,695.00**\n\n"
                                    "Which year would you like to inspect in detail?"
                                )
                            }
                        ]
                    }
                }
            ]
        }

    monkeypatch.setattr(gw, "execute_gemini_request", fake_execute_gemini_request)

    with sqlite_db() as db:
        thread = CopilotThread(id=new_id(), user_id=ids["staff_a"], title="New Chat")
        db.add(thread)
        db.commit()
        tid = thread.id

    events = list(
        stream_agent_turn(
            session_factory=sqlite_db,
            user_id=ids["staff_a"],
            thread_id=tid,
            message_text="Compare the quotation for JWX1234",
            gateway=gw,
        )
    )
    event_types = [e["type"] for e in events]
    assert "step" in event_types
    assert "links" in event_types
    assert "done" in event_types

    done_evt = next(e for e in events if e["type"] == "done")
    assert "2026" in done_evt["message"]["content_markdown"]
    assert "2025" in done_evt["message"]["content_markdown"]
    assert len(done_evt["message"]["tool_trace"]) == 2
    assert done_evt["message"]["tool_trace"][0]["status"] == "error"
    assert done_evt["message"]["tool_trace"][1]["status"] == "done"
    assert len(done_evt["message"]["verified_links"]) >= 2
    assert "JWX" in done_evt["thread"]["title"]


def test_copilot_threads_privacy_and_artifact_download_api(sqlite_db, monkeypatch):
    ids = _seed_agency_data(sqlite_db)
    app = create_app()

    def override_get_db():
        with sqlite_db() as db:
            yield db

    from app.api import deps as api_deps
    from fastapi import Header

    def override_current_user(x_test_user: str = Header(default="")):
        with sqlite_db() as db:
            return db.get(User, x_test_user or ids["staff_a"])

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[api_deps.current_user] = override_current_user
    settings = get_settings()

    tok_a = generate_session_token()
    tok_b = generate_session_token()
    csrf_a = csrf_token_for_session(tok_a, settings.auth_hash_secret)
    csrf_b = csrf_token_for_session(tok_b, settings.auth_hash_secret)

    client_a = TestClient(app)
    client_a.cookies.set(settings.session_cookie_name, tok_a)
    client_a.cookies.set(settings.csrf_cookie_name, csrf_a)
    headers_a = {"X-CSRF-Token": csrf_a, "X-Test-User": ids["staff_a"]}

    client_b = TestClient(app)
    client_b.cookies.set(settings.session_cookie_name, tok_b)
    client_b.cookies.set(settings.csrf_cookie_name, csrf_b)
    headers_b = {"X-CSRF-Token": csrf_b, "X-Test-User": ids["staff_b"]}

    # Staff A creates a thread
    r_create = client_a.post("/api/copilot/threads", json={"title": "Alice Private Thread"}, headers=headers_a)
    assert r_create.status_code == 200
    thread_id = r_create.json()["thread"]["id"]

    # Staff B cannot see or access Staff A's thread
    r_list_b = client_b.get("/api/copilot/threads", headers=headers_b)
    assert r_list_b.status_code == 200
    assert r_list_b.json()["threads"] == []

    r_get_b = client_b.get(f"/api/copilot/threads/{thread_id}", headers=headers_b)
    assert r_get_b.status_code == 404

    # Staff A can pin, rename, check quota, and soft-delete
    r_patch = client_a.patch(
        f"/api/copilot/threads/{thread_id}",
        json={"title": "Pinned Q3 Analysis", "is_pinned": True},
        headers=headers_a,
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["thread"]["is_pinned"] is True

    r_quota = client_a.get("/api/copilot/quota", headers=headers_a)
    assert r_quota.status_code == 200
    assert r_quota.json()["turns_limit"] == 40

    # Artifact export & owner-only download RBAC check
    with sqlite_db() as db:
        user_a = db.get(User, ids["staff_a"])
        art, _ = export_sql_to_excel(
            db,
            user=user_a,
            thread_id=thread_id,
            message_id=None,
            sql="SELECT vehicle_no, stage FROM ai_v_motor_ledger",
            filename="rbac_check.xlsx",
        )
        db.commit()
        art_id = art.id

    r_dl_b = client_b.get(f"/api/copilot/artifacts/{art_id}/download", headers=headers_b)
    assert r_dl_b.status_code == 403
    r_dl_a = client_a.get(f"/api/copilot/artifacts/{art_id}/download", headers=headers_a)
    assert r_dl_a.status_code == 200
    assert len(r_dl_a.content) > 500

    r_del = client_a.delete(f"/api/copilot/threads/{thread_id}", headers=headers_a)
    assert r_del.status_code == 200
    assert client_a.get("/api/copilot/threads", headers=headers_a).json()["threads"] == []


# ---------------------------------------------------------------------------
# 5. Dual-Barrel 80s Reloader, Fair-Queue, Bulk 400-Plate, Admin Oversight & Ledger Deep-Link Tests
# ---------------------------------------------------------------------------


def test_dual_barrel_80s_reloader_max_headroom_and_strict_copilot_only(monkeypatch):
    import time as _t

    monkeypatch.delenv("GEMINI_MAX_TPM_PER_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MAX_RPM_PER_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MAX_RPD_PER_KEY", raising=False)

    gw = GeminiFleetGateway(force_memory=True)
    # 5-key setup: 1 dedicated copilot_only + 4 shared/extraction keys
    accounts = [
        GeminiAccount(id="k_chat", key="AIzaSyChatKey000000000000000000000", label="Chat Key", status="ready", workload_scope="copilot_only"),
        GeminiAccount(id="k_ext1", key="AIzaSyExt1Key000000000000000000000", label="Ext 1", status="ready", workload_scope="all"),
        GeminiAccount(id="k_ext2", key="AIzaSyExt2Key000000000000000000000", label="Ext 2", status="ready", workload_scope="all"),
        GeminiAccount(id="k_ext3", key="AIzaSyExt3Key000000000000000000000", label="Ext 3", status="ready", workload_scope="extraction_only"),
        GeminiAccount(id="k_ext4", key="AIzaSyExt4Key000000000000000000000", label="Ext 4", status="ready", workload_scope="extraction_only"),
    ]
    fake_pool = SimpleNamespace(
        _parallel_models=("gemini-3.1-flash-lite", "gemini-3.5-flash-lite"),
        _max_rpd_per_key=480,
        _max_rpm_per_key=13,
        _max_tpm_per_key=220_000,
        sync_accounts=lambda **kw: None,
        get_accounts=lambda: list(accounts),
        record_success=lambda **kw: None,
        record_failure=lambda *a, **kw: None,
    )
    monkeypatch.setattr("app.services.ai_fleet_gateway.get_key_pool", lambda: fake_pool)

    # 1. Small chat (~500 tok) fires on Barrel 1 (k_chat::3.1-flash-lite)
    r1, wait1, daily1 = gw.reserve_lane(estimated_tokens=500, purpose="copilot_agent", priority=10)
    assert r1 is not None and r1.account_id == "k_chat" and wait1 == 0.0 and daily1 is False
    gw.commit_lane(r1, prompt_tokens=400, candidate_tokens=100, total_tokens=500, purpose="copilot_agent")

    # Advance clock past 1.8s same-key gap
    for st in gw._mem_lanes.values():
        st.last_dispatched_at -= 2.5

    # 2. Huge prompt (218,000 tok) prefers Barrel 2 (220k > 219.5k remaining on Barrel 1)
    r2, wait2, _ = gw.reserve_lane(estimated_tokens=218_000, purpose="copilot_agent", priority=10)
    assert r2 is not None and r2.account_id == "k_chat" and r2.lane_id != r1.lane_id and wait2 == 0.0
    gw.commit_lane(r2, prompt_tokens=217_000, candidate_tokens=1_000, total_tokens=218_000, purpose="copilot_agent")

    for st in gw._mem_lanes.values():
        st.last_dispatched_at -= 2.5

    # 3. Second huge prompt (200,000 tok) switches back to Barrel 1 (219.5k >= 200k), NEVER spills onto k_ext*!
    r3, wait3, _ = gw.reserve_lane(estimated_tokens=200_000, purpose="copilot_agent", priority=10)
    assert r3 is not None and r3.account_id == "k_chat" and r3.lane_id == r1.lane_id and wait3 == 0.0
    gw.commit_lane(r3, prompt_tokens=199_000, candidate_tokens=1_000, total_tokens=200_000, purpose="copilot_agent")

    for st in gw._mem_lanes.values():
        st.last_dispatched_at -= 2.5

    # 4. Third huge prompt (200,000 tok) within 80s: both k_chat barrels TPM-saturated, MUST NOT spill to k_ext1..4!
    r4, wait4, daily4 = gw.reserve_lane(estimated_tokens=200_000, purpose="copilot_agent", priority=10)
    assert r4 is None and daily4 is False
    assert 60.0 <= wait4 <= 81.0

    # 5. Extraction never touches k_chat
    for _ in range(4):
        for st in gw._mem_lanes.values():
            st.last_dispatched_at -= 2.5
        re_lane, _, _ = gw.reserve_lane(estimated_tokens=8_000, purpose="extraction", priority=100)
        assert re_lane is not None and re_lane.account_id != "k_chat"

    # 6. Barrel snapshot exposes live remaining TPM & reload ETA
    barrels = gw.get_copilot_barrel_snapshot()
    assert len(barrels) == 2
    assert all(b["account_id"] == "k_chat" for b in barrels)
    assert all(b["tpm_remaining"] < 25_000 for b in barrels)
    assert any(b["reload_in_sec"] > 0 for b in barrels)

    # 7. After 80.5s window expires, Barrel 1 reloads back to 220k
    now_plus = _t.time() - 81.0
    for st in gw._mem_lanes.values():
        if st.account_id == "k_chat":
            st.recent_calls_json = [now_plus]
            st.recent_tokens_json = [[now_plus, 200_000]]
    r5, wait5, _ = gw.reserve_lane(estimated_tokens=200_000, purpose="copilot_agent", priority=10)
    assert r5 is not None and r5.account_id == "k_chat" and wait5 == 0.0


def test_copilot_fair_queue_orchestrator_work_conserving_and_interleaving():
    import threading
    from app.services.copilot_orchestrator import CopilotFairQueueOrchestrator

    orch = CopilotFairQueueOrchestrator(max_concurrent_turns=2)
    # Single active user gets immediate access across bursts (no idle-user splitting)
    with orch.acquire_turn_slot(user_id="u1", estimated_tokens=500) as slot1:
        assert slot1["user_id"] == "u1"
        with orch.acquire_turn_slot(user_id="u1", estimated_tokens=500) as slot2:
            assert slot2["user_id"] == "u1"

    # Multi-user contention interleaves fairly when single-concurrency slot is held
    orch_single = CopilotFairQueueOrchestrator(max_concurrent_turns=1)
    order: list[str] = []
    ready_u2 = threading.Event()
    ready_u3 = threading.Event()

    def run_user(uid: str, ev_after: threading.Event | None = None):
        with orch_single.acquire_turn_slot(user_id=uid, estimated_tokens=1_000):
            order.append(uid)
            if ev_after:
                ev_after.set()

    with orch_single.acquire_turn_slot(user_id="u1", estimated_tokens=1_000):
        t2 = threading.Thread(target=run_user, args=("u2", ready_u2))
        t3 = threading.Thread(target=run_user, args=("u3", ready_u3))
        t2.start()
        t3.start()
        # Wait briefly until both threads are queued
        import time as _t
        _t.sleep(0.08)
    t2.join(timeout=2.0)
    t3.join(timeout=2.0)
    assert set(order) == {"u2", "u3"}


def test_bulk_check_plates_400_entries_history_and_client_records(sqlite_db):
    from app.models.tables import ClientRecord, VehiclePlateHistory
    from app.services.copilot_agent_service import _collect_verified_links, _execute_bulk_check_plates

    ids = _seed_agency_data(sqlite_db)
    with sqlite_db() as db:
        # Add historical plate + ClientRecord entry
        db.add(
            VehiclePlateHistory(
                id=new_id(),
                tracked_vehicle_id=ids["veh1"],
                plate_no="OLD9999",
            )
        )
        db.add(
            ClientRecord(
                id=new_id(),
                insurer_no="INS-9901",
                vehicle_no="CR 7777 A",
                customer_name="Client Record Co",
                insurance_company="Allianz",
            )
        )
        db.commit()

        # Build 400 plates including known ledger plate, historical plate, client_record plate, and missing plates
        plates = ["JWX 1234", "VAA888", "old-9999", "CR7777A"] + [f"TEST{i:04d}" for i in range(396)]
        summary, matched_rows = _execute_bulk_check_plates(db, plates)

        assert summary["total_checked"] == 400
        assert summary["found_count"] == 4
        assert summary["missing_count"] == 396
        assert len(summary["missing_plates"]) == 396
        assert any(h["queried_plate"] == "OLD-9999" for h in summary["matched_via_history"])
        assert len(matched_rows) == 4

        # Verify links filter cleanly: when answer only lists missing plates, no unrelated vehicle links attach
        missing_only_links = _collect_verified_links(
            matched_rows,
            final_markdown="Missing entries:\n- TEST0001\n- TEST0002",
        )
        assert missing_only_links == []

        # When answer mentions 2 existing plates, a batch select & highlight ledger link is emitted
        matched_links = _collect_verified_links(
            matched_rows,
            final_markdown="Found **JWX 1234** and **VAA 888** in the ledger.",
        )
        assert any(lnk["kind"] == "ledger_batch" and "select=true" in lnk["href"] for lnk in matched_links)


def test_admin_oversight_readonly_plus_delete_and_ledger_tenure_ids(sqlite_db):
    ids = _seed_agency_data(sqlite_db)
    app = create_app()

    def override_get_db():
        with sqlite_db() as db:
            yield db

    from app.api import deps as api_deps
    from fastapi import Header

    def override_current_user(x_test_user: str = Header(default="")):
        with sqlite_db() as db:
            return db.get(User, x_test_user or ids["staff_a"])

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[api_deps.current_user] = override_current_user
    settings = get_settings()

    tok_admin = generate_session_token()
    tok_staff_a = generate_session_token()
    tok_staff_b = generate_session_token()
    csrf_admin = csrf_token_for_session(tok_admin, settings.auth_hash_secret)
    csrf_a = csrf_token_for_session(tok_staff_a, settings.auth_hash_secret)
    csrf_b = csrf_token_for_session(tok_staff_b, settings.auth_hash_secret)

    c_admin = TestClient(app)
    c_admin.cookies.set(settings.session_cookie_name, tok_admin)
    c_admin.cookies.set(settings.csrf_cookie_name, csrf_admin)
    h_admin = {"X-CSRF-Token": csrf_admin, "X-Test-User": ids["admin"]}

    c_a = TestClient(app)
    c_a.cookies.set(settings.session_cookie_name, tok_staff_a)
    c_a.cookies.set(settings.csrf_cookie_name, csrf_a)
    h_a = {"X-CSRF-Token": csrf_a, "X-Test-User": ids["staff_a"]}

    c_b = TestClient(app)
    c_b.cookies.set(settings.session_cookie_name, tok_staff_b)
    c_b.cookies.set(settings.csrf_cookie_name, csrf_b)
    h_b = {"X-CSRF-Token": csrf_b, "X-Test-User": ids["staff_b"]}

    # Staff A creates a thread
    r_th = c_a.post("/api/copilot/threads", json={"title": "Alice Oversight Thread"}, headers=h_a)
    assert r_th.status_code == 200
    tid = r_th.json()["thread"]["id"]

    # Staff B cannot list admin users or view Staff A's threads
    assert c_b.get("/api/copilot/admin/users", headers=h_b).status_code == 403
    assert c_b.get(f"/api/copilot/threads?user_id={ids['staff_a']}", headers=h_b).status_code == 403
    assert c_b.delete(f"/api/copilot/threads/{tid}", headers=h_b).status_code == 404

    # Admin can list users, view Staff A's thread read-only, CANNOT rename/stream into it, and CAN delete it
    r_users = c_admin.get("/api/copilot/admin/users", headers=h_admin)
    assert r_users.status_code == 200
    assert any(u["id"] == ids["staff_a"] and u["thread_count"] >= 1 for u in r_users.json()["users"])

    r_list = c_admin.get(f"/api/copilot/threads?user_id={ids['staff_a']}", headers=h_admin)
    assert r_list.status_code == 200
    assert any(t["id"] == tid for t in r_list.json()["threads"])

    r_det = c_admin.get(f"/api/copilot/threads/{tid}", headers=h_admin)
    assert r_det.status_code == 200
    assert r_det.json()["read_only"] is True

    # Admin cannot rename or message inside Staff A's thread
    assert c_admin.patch(f"/api/copilot/threads/{tid}", json={"title": "Hijack"}, headers=h_admin).status_code == 404
    assert c_admin.post(f"/api/copilot/threads/{tid}/stream", json={"message": "hello"}, headers=h_admin).status_code == 404

    # Admin CAN delete Staff A's thread
    r_adm_del = c_admin.delete(f"/api/copilot/threads/{tid}", headers=h_admin)
    assert r_adm_del.status_code == 200

    # Verify GET /tenures?tenure_ids=... filters cleanly to requested IDs
    r_ten = c_admin.get(f"/api/tenures?tenure_ids={ids['t_2025']},{ids['t_888']}", headers=h_admin)
    assert r_ten.status_code == 200
    returned_ids = {item["id"] for item in r_ten.json()["items"]}
    assert returned_ids == {ids["t_2025"], ids["t_888"]}


def test_extract_exact_83_user_paste_and_pure_bulk_intent():
    from app.services.copilot_agent_service import (
        _extract_bulk_plates_from_message,
        _is_pure_bulk_plate_check,
    )

    user_prompt = (
        'i need to knwo clearly if the following cars are in the motor renewal ledger or not '
        '"QBG1431 - WONG SUI PENG " JYP3000 - TAN YAO FENG JWR8053 - CSH BAKERY & CONFECTIONERY SDN BHD '
        'JUJ7091 - CSH BAKERY & CONFECTIONERY SDN BHD JUJ7218 - CSH BAKERY & CONFECTIONERY SDN BHD '
        'JPQ6655 - HOW YEOK CHIAN JSM1285 - CSH BAKERY & CONFECTIONERY SDN BHD WCM688 - CHAI KAU YEN '
        'JYP387 - TOP MIX CONCRETE (M) SDN BHD JWR9256 - LEONG JIA HAO WRP8273 - SUN WAH PROPERTY SDN BHD '
        'JUM9967 - CHUA MIN SIEW JUY4804 - CSH BAKERY & CONFECTIONERY SDN BHD AMQ9611 - ADRINA A/P ANTONY THAS '
        'JUY4805 - CSH BAKERY & CONFECTIONERY SDN BHD JSM6607 - CSH BAKERY & CONFECTIONERY SDN BHD '
        'JSK4791 - CSH BAKERY & CONFECTIONERY SDN BHD JPP6517 - CSH BAKERY & CONFECTIONERY SDN BHD '
        'JMP2272 - LIH HENG MUN JRE1098 - CHAI XINYI NEJ2232 - RAMACON ENGINEERING & CONSTRUCTION SDN BHD '
        'JXL6996 - CHAI KEAN SENG JXC4323 - MEGA MIX CONCRETE SDN BHD JRF1699 - XIN XIN TRAVEL SDN BHD '
        'JRB3583 - CSH BAKERY & CONFECTIONERY SDN BHD VED9349 - LEONG JIA HAO UG1349 - PL INKJET SDN. BHD. '
        'JTS3448 - CHEONG SEK MUN WX38 - EWE CHEE YENG JHW6819 - TAN TENG HONG JJH3338 - CHIA CHIN KOK '
        'SK6818C - A L DAKSHNAMOORTHY PGR9641 - CHUA TECK HOCK JLQ866 - MUGEN DESIGN & BUILD SDN BHD '
        'BNQ1379 - RAMACON ENGINEERING & CONSTRUCTION SDN BHD WJS7728 - LOW CHEU YUANG JMP7728 - ONG KAR ENG '
        'JRX8396 - EXA WELDING (M) SDN BHD VNM5057 - RAMACON ENGINEERING & CONSTRUCTION SDN BHD '
        'JSM6355 - KEI WEI TRADING VAA6082 - SII HAU CHIN JTE6416 - CSH BAKERY & CONFECTIONERY SDN BHD '
        'JUY6819 - LEE XIA WEI VJY8397 - RAMESH S/O PULANDARAN JXE1496 - MEGA MIX CONCRETE SDN BHD '
        'JWS8434 - OOI WEI CHUN DEW56 - YI DING ENGINEERING SDN BHD JRG9029 - HENG CHOON YANG '
        'JXE3890 - MEGA MIX CONCRETE SDN BHD JME1219 - TAN WAI HOONG TDB1001 - KEJAYA TUNNEL SDN BHD '
        'T/WC811 - KEJAYA TUNNEL SDN BHD SMU5251 - LIM WEI JIE JQQ2080 - LOW POH HEOT '
        'JPK888 - TOP OCEAN MARITIME SDN BHD JQN66 - TOP OCEAN MARITIME SDN BHD BFN2187 - LONG HIN TUANG '
        'VMD868 - SEAW CHONG YONG VFV5002 - FOO YONGHAO JKC9933 - YAP POT LIEONG WRK8482 - VICTOR TAN '
        'JRN47 - CHOO SENG HOOI VJV6336 - NEW SOGO SDN. BHD. JRA1728 - CSH BAKERY & CONFECTIONERY SDN BHD '
        'JRH1364 - CSH BAKERY & CONFECTIONERY SDN BHD JJH3366 - TAN JENN SHI JWL5813 - WONG NYUK POH '
        'WUL9396 - KOEY HOI LENG JQX3339 - CHIA CHIN KOK JXM6088 - HAU LEE HUA JLS8255 - TAN LIAN SENG '
        'JVY8361 - LEE SIEW MUI JVA9628 - CHAN YUNG FONG JVA1087 - CSH BAKERY & CONFECTIONERY SDN BHD '
        'JVB2388 - VINNIE SOH MIN MBR4649 - RAMACON ENGINEERING & CONSTRUCTION SDN BHD VFU2906 - NG WEE RONG '
        'VHD8612 - GAN AH CHONG AKM9978 - JONATHAN SINGAM JTU4043 - LAI MUN LOONG '
        'JSM6575 - CSH BAKERY & CONFECTIONERY SDN BHD JPW7198 - SUN HUP TYRE SDN. BHD. '
        'JYH2089 - MOHD RAFIQUE BIN MOHD HANIFA also a proepr table please'
    )
    entries, dup_count = _extract_bulk_plates_from_message(user_prompt)
    plates = [e["plate"] for e in entries]
    assert dup_count == 0
    assert len(entries) == 83
    assert "T/WC811" in plates
    assert "SK6818C" in plates
    assert "WX38" in plates
    assert "DEW56" in plates
    assert "UG1349" in plates
    assert entries[0]["plate"] == "QBG1431"
    assert entries[0]["pasted_name"] == "WONG SUI PENG"
    assert entries[-1]["plate"] == "JYH2089"
    assert entries[-1]["pasted_name"] == "MOHD RAFIQUE BIN MOHD HANIFA"
    assert _is_pure_bulk_plate_check(user_prompt, entries) is True

    # Non-plate noise tokens filtered cleanly & analytical requests stay in Gemini ReAct mode
    noise_entries, _ = _extract_bulk_plates_from_message("Budget RM1500 IC90 NO12 V1 Q1 A4 for WCM688 WX38 JYP387")
    assert [e["plate"] for e in noise_entries] == ["WCM688", "WX38", "JYP387"]
    assert _is_pure_bulk_plate_check("Compare insurer quotes and write a WhatsApp pitch for WCM688 WX38 JYP387 JPK888 DEW56", entries[:5]) is False


def test_bulk_check_active_ledger_vs_projected_hidden_and_comparison_counts(sqlite_db):
    from app.models.tables import ClientRecord, VehiclePlateHistory
    from app.services.copilot_agent_service import (
        _collect_verified_links,
        _execute_bulk_check_plates_full,
        _render_deterministic_bulk_report,
    )

    ids = _seed_agency_data(sqlite_db)
    with sqlite_db() as db:
        proj_veh = TrackedVehicle(id=new_id(), vehicle_no="PROJ111", car_brand="Honda", car_model="Civic")
        hid_veh = TrackedVehicle(id=new_id(), vehicle_no="HID222", car_brand="Toyota", car_model="Vios")
        db.add_all([proj_veh, hid_veh])
        db.flush()

        t_proj = InsuranceTenure(
            id=new_id(),
            tracked_vehicle_id=proj_veh.id,
            vehicle_no="PROJ111",
            customer_name="Projected Owner",
            coverage_start_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
            coverage_end_date=datetime(2027, 12, 31, tzinfo=timezone.utc),
            expiry_month="2027-12",
            stage="Quotations",
            status="active",
            is_projected=True,
        )
        t_hid = InsuranceTenure(
            id=new_id(),
            tracked_vehicle_id=hid_veh.id,
            vehicle_no="HID222",
            customer_name="Hidden Owner",
            coverage_start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            coverage_end_date=datetime(2027, 2, 28, tzinfo=timezone.utc),
            expiry_month="2027-02",
            stage="Pending",
            status="active",
            is_hidden=True,
        )
        db.add_all([t_proj, t_hid])
        db.add(VehiclePlateHistory(id=new_id(), tracked_vehicle_id=ids["veh1"], plate_no="OLD9999"))
        db.add(
            ClientRecord(
                id=new_id(),
                insurer_no="INS-100",
                vehicle_no="CR5555",
                customer_name="Client Only Enterprise",
                insurance_company="STMB",
            )
        )
        db.commit()

        summary, all_rows, matched_rows = _execute_bulk_check_plates_full(
            db, ["JWX1234", "VAA888", "OLD9999", "PROJ111", "HID222", "CR5555", "MISSING99"]
        )
        assert summary["total_checked"] == 7
        assert summary["in_ledger_count"] == 3  # JWX1234, VAA888, OLD9999 -> veh1 active ledger
        assert summary["other_record_only_count"] == 3  # PROJ111, HID222, CR5555
        assert summary["missing_count"] == 1  # MISSING99

        by_q = {r["queried_plate"]: r for r in all_rows}
        assert by_q["JWX1234"]["ledger_status"] == "In Ledger"
        assert by_q["JWX1234"]["comparison_quote_count"] == 2
        assert by_q["OLD9999"]["ledger_status"] == "In Ledger"
        assert by_q["OLD9999"]["tenure_id"] is not None
        assert by_q["PROJ111"]["ledger_status"] == "Other Record Only"
        assert by_q["PROJ111"]["tenure_id"] is None
        assert "Projected" in (by_q["PROJ111"]["other_reason"] or "")
        assert by_q["HID222"]["ledger_status"] == "Other Record Only"
        assert by_q["HID222"]["tenure_id"] is None
        assert "Hidden" in (by_q["HID222"]["other_reason"] or "")
        assert by_q["CR5555"]["ledger_status"] == "Other Record Only"
        assert by_q["MISSING99"]["ledger_status"] == "Not Found"

        md = _render_deterministic_bulk_report(summary, all_rows)
        # Escapes pipe inside =CMD|' /C calc'!A0 so table columns never corrupt
        assert r"\|" in md
        assert "/ledger?tenure_ids=" in md
        # Projected/hidden tenures must NEVER appear as /ledger?tenure_ids= links
        assert t_proj.id not in md
        assert t_hid.id not in md

        links = _collect_verified_links(matched_rows, final_markdown=md, prefer_all_ledger_rows=True)
        batch_link = next(lnk for lnk in links if lnk["kind"] == "ledger_batch")
        assert "highlight=all" in batch_link["href"]
        assert t_proj.id not in batch_link["href"]
        assert t_hid.id not in batch_link["href"]


def test_stream_agent_turn_deterministic_bulk_fastpath_and_4000_scale(sqlite_db, tmp_path, monkeypatch):
    from app.services import copilot_excel_service
    from app.services.copilot_agent_service import stream_agent_turn

    monkeypatch.setattr(copilot_excel_service, "COPILOT_EXPORTS_DIR", tmp_path.resolve())
    ids = _seed_agency_data(sqlite_db)

    with sqlite_db() as db:
        th = CopilotThread(id=new_id(), user_id=ids["admin"], title="New Chat")
        db.add(th)
        db.commit()
        tid = th.id

    class _FailIfCalledGateway:
        def get_copilot_barrel_snapshot(self, db):
            return []

        def execute_gemini_request(self, *args, **kwargs):
            raise AssertionError("Pure bulk plate verification must use 0 Gemini LLM calls")

    # 1. 60-plate batch triggers 0-token complete report + auto 0-token .xlsx artifact
    plates_60 = ["JWX 1234", "VAA 888"] + [f"MS{i:04d}" for i in range(58)]
    prompt_60 = "Check if these plates exist in the motor renewal ledger as a proper table:\n" + "\n".join(
        f"{p} - TEST CUSTOMER {idx}" for idx, p in enumerate(plates_60, start=1)
    )
    events_60 = list(
        stream_agent_turn(
            session_factory=sqlite_db,
            user_id=ids["admin"],
            thread_id=tid,
            message_text=prompt_60,
            gateway=_FailIfCalledGateway(),
        )
    )
    done_60 = next(e for e in events_60 if e["type"] == "done")
    msg_60 = done_60["message"]
    assert msg_60["model_used"] == "direct-db-verified"
    assert msg_60["total_tokens"] == 0
    assert "Complete Vehicle Status Table (60 rows)" in msg_60["content_markdown"]
    assert "MS0057" in msg_60["content_markdown"]
    assert len(msg_60["artifacts"]) == 1
    assert msg_60["artifacts"][0]["row_count"] == 60
    assert any(lnk["kind"] == "ledger_batch" and "highlight=all" in lnk["href"] for lnk in msg_60["verified_links"])

    # 2. 4,000-plate scale completes cleanly with all 4,000 rows in output
    plates_4000 = [f"ZZ{i // 1000}{(i % 1000):03d}" for i in range(4000)]
    prompt_4000 = "Check existence in ledger:\n" + " ".join(plates_4000)
    events_4000 = list(
        stream_agent_turn(
            session_factory=sqlite_db,
            user_id=ids["admin"],
            thread_id=tid,
            message_text=prompt_4000,
            gateway=_FailIfCalledGateway(),
        )
    )
    done_4000 = next(e for e in events_4000 if e["type"] == "done")
    assert done_4000["message"]["model_used"] == "direct-db-verified"
    assert done_4000["message"]["total_tokens"] == 0
    assert "Complete Vehicle Status Table (4,000 rows)" in done_4000["message"]["content_markdown"]
    assert "ZZ3999" in done_4000["message"]["content_markdown"]

    # 3. 5,001 plates fails closed cleanly instead of silently truncating
    plates_5001 = [f"Z{chr(65 + (i // 1000))}{i % 1000:03d}" for i in range(5001)]
    events_5001 = list(
        stream_agent_turn(
            session_factory=sqlite_db,
            user_id=ids["admin"],
            thread_id=tid,
            message_text="Check plates:\n" + " ".join(plates_5001),
            gateway=_FailIfCalledGateway(),
        )
    )
    done_5001 = next(e for e in events_5001 if e["type"] == "done")
    assert "5,001" in done_5001["message"]["content_markdown"]
    assert "5,000" in done_5001["message"]["content_markdown"]

