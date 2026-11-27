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
