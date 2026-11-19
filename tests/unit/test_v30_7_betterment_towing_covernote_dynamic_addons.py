"""Hermetic tests for v30.7: DB Betterment, Towing Sync Constraints, Cover Note Isolation, Conditional Add-ons, and Box 1 Parity."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api.deps import current_user, get_db
from app.api.routers.comparison import router as comparison_router
from app.core.errors import register_error_handlers
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    Base,
    DraftBenefitSelection,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    User,
    new_id,
)
from app.rendering.unified_addon_engine import (
    extract_free_coverage_items,
    format_addon_value,
)
from app.services.catalog_review_service import pin_catalog_context
from app.services.marketing_comparison.dynamic_addons import extract_dynamic_addons
from app.services.marketing_comparison.ncd_evaluator import (
    evaluate_betterment_rules,
    normalize_towing_km,
)
from app.services.marketing_comparison.workspace_sync import (
    sync_session_draft_from_comparison,
)
from app.services.marketing_comparison_service import get_marketing_comparison


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def test_db_driven_betterment_cutoffs_and_ev_guard(db: Session):
    """Betterment evaluates exact completed age against DB company_obj.policy_rules, and ICE drafts reject EV catalogs."""
    kurnia = InsuranceCompany(
        id=new_id(),
        name="Kurnia Insurans",
        slug="kurnia",
        policy_rules={
            "betterment": {
                "max_waiver_years": 15,
                "default_display": "Up to 15 Years",
                "auto_waive_regardless_of_yom": False,
            }
        },
    )
    qbe = InsuranceCompany(
        id=new_id(),
        name="QBE Insurance",
        slug="qbe",
        policy_rules={
            "betterment": {
                "max_waiver_years": 10,
                "default_display": "Up to 10 Years",
                "auto_waive_regardless_of_yom": True,
            }
        },
    )
    takaful = InsuranceCompany(
        id=new_id(),
        name="Takaful Malaysia",
        slug="takaful-malaysia",
        policy_rules={
            "betterment": {
                "max_waiver_years": 10,
                "default_display": "Up to 10 Years",
                "auto_waive_regardless_of_yom": False,
            }
        },
    )
    # Completed age 4 (<5): always waived No (0%) even without peril
    assert evaluate_betterment_rules(2022, 2026, "Takaful Malaysia", False, True, company_obj=takaful) == (True, 0.0, "No (0%)")
    # Completed age 5 without peril on non-auto company: Yes (15%)
    assert evaluate_betterment_rules(2021, 2026, "Takaful Malaysia", False, True, company_obj=takaful) == (False, 15.0, "Yes (15%)")
    # Completed age 9 (<10) WITH peril on Takaful (10-yr cap): Waived No (0%)
    assert evaluate_betterment_rules(2017, 2026, "Takaful Malaysia", True, True, company_obj=takaful) == (True, 0.0, "No (0%)")
    # Completed age 10 (not <10) WITH peril on Takaful (10-yr cap): Co-pay Yes (40%)
    assert evaluate_betterment_rules(2016, 2026, "Takaful Malaysia", True, True, company_obj=takaful) == (False, 40.0, "Yes (40%)")
    # Completed age 14 (<15) WITH peril on Kurnia (15-yr cap): Waived No (0%)
    assert evaluate_betterment_rules(2012, 2026, "Kurnia Insurans", True, True, company_obj=kurnia) == (True, 0.0, "No (0%)")
    # Completed age 15 (not <15) WITH peril on Kurnia: Co-pay Yes (40%)
    assert evaluate_betterment_rules(2011, 2026, "Kurnia Insurans", True, True, company_obj=kurnia) == (False, 40.0, "Yes (40%)")
    # QBE auto-waives Comprehensive Private without needing explicit peril inside 10 years
    assert evaluate_betterment_rules(2018, 2026, "QBE Insurance", False, True, company_obj=qbe) == (True, 0.0, "No (0%)")

    # EV/ICE catalog guard: Proton Saga ICE draft must unpin stale EV product and select ICE product
    user = User(id=new_id(), email="u@test.com", password_hash="x", role="staff", status="active")
    prod_ev = InsuranceProduct(id=new_id(), company_id=takaful.id, product_key="takaful-mymotor-ev", name="Takaful myMotor (EV)", status="active")
    prod_ice = InsuranceProduct(id=new_id(), company_id=takaful.id, product_key="takaful-mymotor", name="Takaful myMotor", status="active")
    cat_ev = BenefitCatalog(id=new_id(), company_id=takaful.id, product_id=prod_ev.id, engine_type="ev", name="EV Catalog", status="published")
    cat_ice = BenefitCatalog(id=new_id(), company_id=takaful.id, product_id=prod_ice.id, engine_type="ice", name="ICE Catalog", status="published")
    db.add_all([user, takaful, prod_ev, prod_ice, cat_ev, cat_ice])
    db.flush()
    rev_ev = BenefitCatalogRevision(id=new_id(), catalog_id=cat_ev.id, revision_number=1, state="published", content_hash="h_ev")
    rev_ice = BenefitCatalogRevision(id=new_id(), catalog_id=cat_ice.id, revision_number=1, state="published", content_hash="h_ice")
    db.add_all([rev_ev, rev_ice])
    db.flush()

    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=new_id(),
        owner_id=user.id,
        company_id=takaful.id,
        product_id=prod_ev.id,
        catalog_revision_id=rev_ev.id,
        fields={"car_model": {"value": "Proton Saga Premium AT"}, "engine_cc": {"value": "1332"}},
        display_options={},
    )
    db.add(draft)
    db.commit()

    pinned = pin_catalog_context(db, draft)
    assert draft.product_id == prod_ice.id
    assert pinned is not None and pinned.id == rev_ice.id


def test_towing_workspace_sync_prevents_check1_violation_and_preserves_custom_limits(db: Session):
    """Syncing RM 400 or 100 km towing must never violate check1 (custom + null label) or uq_draft_benefit_selection_key."""
    user = User(id=new_id(), email="staff@test.com", password_hash="x", role="staff", status="active")
    comp = InsuranceCompany(id=new_id(), name="Lonpac Insurance", slug="lonpac")
    concept_towing = BenefitConcept(
        id=new_id(),
        concept_key="towing",
        label="Emergency Towing Assistance",
    )
    db.add_all([user, comp, concept_towing])
    db.flush()

    veh = TrackedVehicle(id=new_id(), vehicle_no="JWC7711", car_brand="Perodua", car_model="Bezza", manufacture_year=2022)
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="JWC7711",
        customer_name="Lim",
        coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        expiry_month="2026-12",
    )
    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=new_id(),
        owner_id=user.id,
        company_id=comp.id,
        fields={},
        display_options={},
    )
    # Pre-existing removed row sharing the comparison:towing selection_key
    stale_sel = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="comparison:towing",
        concept_id=concept_towing.id,
        item_kind="concept",
        state="removed",
        cost_status="included",
        label_override="Unlimited",
        typed_value_override={"type": "string", "display_text": "Unlimited"},
        evidence_snapshot={},
        sort_order=60,
    )
    sess = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=draft.uploaded_file_id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        detected_company="Lonpac Insurance",
        document_type="quotation",
        status="active",
        is_tenure_active=True,
    )
    db.add_all([veh, tenure, draft, stale_sel, sess])
    db.commit()

    # Sync explicit RM 400 (with stale removed key present — must reuse row cleanly & keep valid item_kind/label!)
    sync_session_draft_from_comparison(
        db,
        tenure,
        sess.id,
        edited_fields=["towing_limit"],
        field_values={"towing_limit": "RM 400"},
    )
    db.commit()

    rows = db.scalars(select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id)).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.state == "current"
    assert not (row.item_kind == "custom" and row.label_override is None)
    assert row.label_override == "Emergency Towing Assistance"
    assert row.typed_value_override["display_text"] == "RM 400"

    # Explicit KM and RM values must not be overridden by underwriter heuristics
    assert normalize_towing_km("RM 400", company_name="Allianz General") == "RM 400"
    assert normalize_towing_km("100 KM", company_name="Lonpac Insurance") == "100 km"
    assert normalize_towing_km("Unlimited", company_name="Lonpac Insurance") == "Unlimited"


def test_covernote_strict_isolation_full_edit_and_422_guard(db: Session):
    """Editing Cover Note updates ONLY its draft + tenure/vehicle and NEVER modifies competing quote entries."""
    staff = User(id=new_id(), email="staff@rl.test", password_hash="x", role="staff", status="active")
    comp_tm = InsuranceCompany(id=new_id(), name="Takaful Malaysia", slug="takaful-malaysia")
    comp_etq = InsuranceCompany(id=new_id(), name="Etiqa Insurance", slug="etiqa")
    veh = TrackedVehicle(id=new_id(), vehicle_no="VAA8899", car_brand="Proton", car_model="Saga Standard", manufacture_year=2021)
    db.add_all([staff, comp_tm, comp_etq, veh])
    db.flush()

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="VAA8899",
        customer_name="Ali",
        road_tax=Decimal("70.00"),
        runner_fee=Decimal("20.00"),
        include_road_tax=True,
        include_runner_fee=True,
        policy_number="TMCA7642479",
        coverage_start_date=datetime(2026, 11, 24, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 11, 23, tzinfo=timezone.utc),
        expiry_month="2027-11",
    )
    cn_draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=new_id(),
        owner_id=staff.id,
        company_id=comp_tm.id,
        fields={
            "policy_number": {"value": "TMCA7642479"},
            "sum_insured": {"value": "26000.00"},
            "premium": {"value": "689.80"},
        },
        display_options={},
    )
    cn_sess = SessionModel(
        id=new_id(),
        owner_id=staff.id,
        uploaded_file_id=cn_draft.uploaded_file_id,
        draft_id=cn_draft.id,
        tenure_id=tenure.id,
        detected_company="Takaful Malaysia",
        document_type="covernote",
        status="active",
        is_tenure_active=True,
    )
    etq_draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=new_id(),
        owner_id=staff.id,
        company_id=comp_etq.id,
        fields={"sum_insured": {"value": "27000.00"}, "premium": {"value": "750.00"}},
        display_options={},
    )
    etq_sess = SessionModel(
        id=new_id(),
        owner_id=staff.id,
        uploaded_file_id=etq_draft.uploaded_file_id,
        draft_id=etq_draft.id,
        tenure_id=tenure.id,
        detected_company="Etiqa Insurance",
        document_type="quotation",
        status="active",
        is_tenure_active=True,
    )
    etq_entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        session_id=etq_sess.id,
        company_name="Etiqa Insurance",
        company_id=comp_etq.id,
        sum_insured=27000.0,
        motor_premium=750.0,
        total_payable=840.0,
        towing_limit="200 km",
        extra_addons={},
        version=1,
    )
    db.add_all([tenure, cn_draft, cn_sess, etq_draft, etq_sess, etq_entry])
    db.commit()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(comparison_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: staff
    client = TestClient(app)

    # Validation check: negative total_payable must reject with 422 cleanly
    res_bad = client.patch(f"/api/comparison/{tenure.id}/covernote", json={"total_payable": -50})
    assert res_bad.status_code == 422

    # Valid comprehensive Cover Note patch
    res = client.patch(
        f"/api/comparison/{tenure.id}/covernote",
        json={
            "total_payable": 800.00,
            "vehicle_model": "Proton Saga Premium AT",
            "manufacture_year": 2022,
            "towing_limit": "RM 500",
            "included_perils": ["TOWING", "FLOOD", "WINDSCREEN", "ALL DRIVERS"],
            "betterment_mode": "copay",
            "betterment_rate": 25.0,
            "extra_addons": {"ehailing": "Yes"},
        },
    )
    assert res.status_code == 200
    payload = res.json()
    cn_out = payload["covernote_policy"]
    assert cn_out["exact_motor_premium"] == pytest.approx(710.0)
    assert cn_out["exact_total_payable"] == pytest.approx(800.0)
    assert cn_out["towing_limit"] == "RM 500"
    assert cn_out["special_perils"] == "Included"
    assert cn_out["vehicle_model"] == "Proton Saga Premium AT"
    assert cn_out["manufacture_year"] == 2022
    assert cn_out["waiver_betterment"] is False
    assert cn_out["betterment_rate"] == pytest.approx(25.0)
    assert cn_out["extra_addons"]["ehailing"] == "Yes"
    assert any(a["key"] == "ehailing" for a in payload["active_dynamic_addons"])

    # Competing underwriter quote must be 100% isolated (untouched!)
    db.refresh(etq_entry)
    assert float(etq_entry.motor_premium) == pytest.approx(750.0)
    assert float(etq_entry.total_payable) == pytest.approx(840.0)
    assert etq_entry.towing_limit == "200 km"
    assert etq_entry.extra_addons == {}


def test_dynamic_addons_negation_guard_and_conditional_visibility(db: Session):
    """Statutory hire/reward exclusion prose must NOT trigger E-Hailing, while positive endorsement activates conditional matrix rows."""
    exclusion_text = (
        "Limitations as to Use: Use only for social, domestic and pleasure purposes. "
        "This policy does not cover use for hire or reward or e-hailing."
    )
    res_excl = extract_dynamic_addons(
        selections=[],
        concepts_by_id={},
        disabled_domains=set(),
        ext_lines=[],
        combined_text=exclusion_text,
        end_tokens=set(),
        draft_fields={},
    )
    assert res_excl == {}

    positive_text = "Additional Cover Included: Private Hire / E-Hailing Endorsement 107"
    res_pos = extract_dynamic_addons(
        selections=[],
        concepts_by_id={},
        disabled_domains=set(),
        ext_lines=[],
        combined_text=positive_text,
        end_tokens={"107"},
        draft_fields={},
    )
    assert res_pos.get("ehailing") == "Yes"

    # Full comparison returns active_dynamic_addons ONLY when >=1 quote/covernote has an addon
    user = User(id=new_id(), email="s@rl.test", password_hash="x", role="staff", status="active")
    veh = TrackedVehicle(id=new_id(), vehicle_no="QAA1122", car_brand="Honda", car_model="City", manufacture_year=2023)
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="QAA1122",
        customer_name="Tan",
        coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        expiry_month="2026-12",
    )
    entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        company_name="Allianz General",
        sum_insured=75000.0,
        motor_premium=1900.0,
        total_payable=1990.0,
        extra_addons={},
        version=1,
    )
    db.add_all([user, veh, tenure, entry])
    db.commit()

    out_empty = get_marketing_comparison(db, tenure.id)
    assert out_empty["active_dynamic_addons"] == []

    # Setting srcc="Yes" on entry makes ONLY Strike & Riot row appear
    entry.extra_addons = {"srcc": "Yes"}
    db.commit()
    out_srcc = get_marketing_comparison(db, tenure.id)
    assert out_srcc["active_dynamic_addons"] == [{"key": "srcc", "label": "Strike & Riot"}]


def test_box1_free_coverage_strips_truncated_prose_and_value_suffixes():
    """Box 1 Free Added Coverage must emit clean Title + Description without '(RM 2,000.00)' or '(Etiqa Cashback by' suffixes."""
    # Verbose prose string must clamp to empty string, never arbitrary first-4-words slice
    assert format_addon_value("Etiqa Cashback by Driving Less opt-in reward") == ""
    assert format_addon_value("Reimbursement of court legal defense representation up to RM 2,000.00") == "RM 2,000.00"

    benefits = [
        {
            "title": "Legal Defense Costs",
            "description": "Reimburses court legal representation and defense fees up to RM2,000.",
            "value": "RM 2,000.00",
            "cost_status": "included",
        },
        {
            "title": "Drive-Less Save-More",
            "description": "Cash rebate up to 30% of base premium for low annual mileage.",
            "value": "Etiqa Cashback by Driving Less opt-in reward",
            "cost_status": "included",
        },
    ]
    free_items = extract_free_coverage_items(benefits, insurer_name="Etiqa Insurance")
    by_title = {item["title"]: item["description"] for item in free_items}
    assert by_title["Legal Defense Costs"] == "Reimburses court legal representation and defense fees up to RM2,000."
    assert by_title["Drive-Less Save-More"] == "Cash rebate up to 30% of base premium for low annual mileage."
    assert "(RM 2,000.00)" not in by_title["Legal Defense Costs"]
    assert "(Etiqa Cashback" not in by_title["Drive-Less Save-More"]


def test_patch_entry_returns_extra_addons_and_betterment_is_auto(db: Session):
    """Inline PATCH /comparison/{tenure_id}/entries/{entry_id} must return extra_addons and betterment_is_auto."""
    staff = User(id=new_id(), email="staff-patch@rl.test", password_hash="x", role="staff", status="active")
    veh = TrackedVehicle(id=new_id(), vehicle_no="WXY9988", car_brand="Proton", car_model="X50", manufacture_year=2023)
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="WXY9988",
        customer_name="Ali",
        coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        expiry_month="2026-12",
    )
    entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        company_name="Allianz General",
        sum_insured=85000.0,
        motor_premium=2100.0,
        total_payable=2190.0,
        extra_addons={},
        version=1,
    )
    db.add_all([staff, veh, tenure, entry])
    db.commit()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(comparison_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: staff
    client = TestClient(app)

    res = client.patch(
        f"/api/comparison/{tenure.id}/entries/{entry.id}",
        json={"extra_addons": {"ehailing": "Yes"}, "expected_version": 1},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["extra_addons"] == {"ehailing": "Yes"}
    assert body["betterment_is_auto"] is True

    res2 = client.patch(
        f"/api/comparison/{tenure.id}/entries/{entry.id}",
        json={"betterment_mode": "copay", "betterment_rate": 20.0, "expected_version": body["version"]},
    )
    assert res2.status_code == 200
    assert res2.json()["betterment_is_auto"] is False


def test_towing_evaluator_honors_db_company_policy_rules_and_covernote_reg_date(db: Session):
    """Towing evaluator reads InsuranceCompany.policy_rules['towing'] when company_obj is provided, and covernote copay respects registration_date."""
    from app.services.marketing_comparison.towing_evaluator import resolve_insurer_towing_limit

    custom_co = InsuranceCompany(
        id=new_id(),
        name="Custom DB Insurer",
        slug="custom-db-insurer",
        policy_rules={
            "betterment": {"auto_waive_without_peril": True, "max_waiver_years": 20, "default_display": "Up to 20 Years"},
            "towing": {"metric": "RM", "base_limit": "RM 777", "unlimited_triggers": ["super vip assist"]},
        },
    )
    assert resolve_insurer_towing_limit("Custom DB Insurer", "Private Car Comprehensive", company_obj=custom_co) == "RM 777"
    assert resolve_insurer_towing_limit("Custom DB Insurer", "Super VIP Assist", company_obj=custom_co) == "Unlimited"

    staff = User(id=new_id(), email="staff-cn@rl.test", password_hash="x", role="staff", status="active")
    veh = TrackedVehicle(
        id=new_id(),
        vehicle_no="JKL4455",
        car_brand="Perodua",
        car_model="Myvi",
        manufacture_year=2020,
    )
    cn_draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=new_id(),
        owner_id=staff.id,
        company_id=custom_co.id,
        fields={"premium": {"value": 900.0}, "registration_date": {"value": "2021-06-15"}},
        display_options={},
    )
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=veh.id,
        vehicle_no="JKL4455",
        customer_name="Mei",
        winning_company_id=custom_co.id,
        coverage_start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 2, 28, tzinfo=timezone.utc),
        expiry_month="2027-02",
        won_premium=900.0,
    )
    cn_sess = SessionModel(
        id=new_id(),
        owner_id=staff.id,
        uploaded_file_id=cn_draft.uploaded_file_id,
        draft_id=cn_draft.id,
        tenure_id=tenure.id,
        document_type="covernote",
        detected_company="Custom DB Insurer",
        status="active",
        is_tenure_active=True,
    )
    tenure.covernote_session_id = cn_sess.id
    cn_entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        session_id=cn_sess.id,
        company_id=custom_co.id,
        company_name="Custom DB Insurer",
        sum_insured=45000.0,
        motor_premium=900.0,
        total_payable=900.0,
        extra_addons={},
        version=1,
    )
    db.add_all([custom_co, staff, veh, cn_sess, cn_draft, tenure, cn_entry])
    db.commit()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(comparison_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: staff
    client = TestClient(app)

    # 2021-06-15 -> 2026-03-01 = 4 completed years (<5 -> 0%), NOT 2026-2020 = 6 years (20%)!
    # Wait: copay mode applies tariff even if <5? Wait: 4 completed years -> get_standard_betterment_rate(4) = 0.0%, whereas 6 -> 20.0%.
    res_copay = client.patch(f"/api/comparison/{tenure.id}/covernote", json={"betterment_mode": "copay"})
    assert res_copay.status_code == 200
    assert res_copay.json()["covernote_policy"]["betterment_rate"] == 0.0

    # Auto mode uses custom_co.policy_rules (auto_waive_without_peril=True, max_waiver_years=20)
    res_auto = client.patch(f"/api/comparison/{tenure.id}/covernote", json={"betterment_mode": "auto"})
    assert res_auto.status_code == 200
    assert res_auto.json()["covernote_policy"]["waiver_betterment"] is True
    assert res_auto.json()["covernote_policy"]["betterment_rate"] == 0.0
