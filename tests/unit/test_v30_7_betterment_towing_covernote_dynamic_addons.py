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
    # Completed age 4 (<5): always waived Yes (0%) even without peril
    assert evaluate_betterment_rules(2022, 2026, "Takaful Malaysia", False, True, company_obj=takaful) == (True, 0.0, "Yes (0%)")
    # Completed age 5 without peril on non-auto company: No (15%)
    assert evaluate_betterment_rules(2021, 2026, "Takaful Malaysia", False, True, company_obj=takaful) == (False, 15.0, "No (15%)")
    # Completed age 9 (<10) WITH peril on Takaful (10-yr cap): Waived Yes (0%)
    assert evaluate_betterment_rules(2017, 2026, "Takaful Malaysia", True, True, company_obj=takaful) == (True, 0.0, "Yes (0%)")
    # Completed age 10 (not <10) WITH peril on Takaful (10-yr cap): Co-pay No (40%)
    assert evaluate_betterment_rules(2016, 2026, "Takaful Malaysia", True, True, company_obj=takaful) == (False, 40.0, "No (40%)")
    # Completed age 14 (<15) WITH peril on Kurnia (15-yr cap): Waived Yes (0%)
    assert evaluate_betterment_rules(2012, 2026, "Kurnia Insurans", True, True, company_obj=kurnia) == (True, 0.0, "Yes (0%)")
    # Completed age 15 (not <15) WITH peril on Kurnia: Co-pay No (40%)
    assert evaluate_betterment_rules(2011, 2026, "Kurnia Insurans", True, True, company_obj=kurnia) == (False, 40.0, "No (40%)")
    # QBE auto-waives Comprehensive Private without needing explicit peril inside 10 years
    assert evaluate_betterment_rules(2018, 2026, "QBE Insurance", False, True, company_obj=qbe) == (True, 0.0, "Yes (0%)")

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


def test_v32_two_way_bundle_betterment_readonly_get_and_covernote_single_discount(db: Session):
    """Verify 2-way Comparison <-> Workspace Box 2 bundle & catalog betterment sync, read-only GET, and single discount."""
    from app.api.routers.sessions import draft_workspace_patch
    from app.api.schemas import WorkspacePatchRequest
    from app.models.tables import (
        BenefitProfile,
        CatalogOffering,
        CompanyBenefitBundle,
        CompanyBenefitBundleEffect,
        CompanyBenefitBundleTier,
    )

    staff = User(id=new_id(), email="staff-v32@rl.test", password_hash="x", role="staff", status="active")
    stmb = InsuranceCompany(
        id=new_id(),
        name="Syarikat Takaful Malaysia Am Berhad",
        slug="takaful-malaysia",
        policy_rules={
            "towing": {"metric": "km", "base_limit": "50 km", "upgrade_triggers": ["motor pa plus"], "plan_limits": {"plan 4": "Unlimited"}},
            "betterment": {"max_waiver_years": 15, "default_display": "Up to 15 Years", "auto_waive_without_peril": False},
        },
    )
    prod = InsuranceProduct(id=new_id(), company_id=stmb.id, product_key="stmb-car", name="Private Car")
    cat = BenefitCatalog(id=new_id(), company_id=stmb.id, product_id=prod.id, name="STMB Catalog")
    rev = BenefitCatalogRevision(id=new_id(), catalog_id=cat.id, revision_number=1, state="published", content_hash="h1")
    prof = BenefitProfile(id=new_id(), name="Default Profile", is_active=True, status="active")

    c_mpa = BenefitConcept(id=new_id(), concept_key="motor-pa-plus", label="Motor PA Plus", description="PA + Towing")
    c_tow = BenefitConcept(id=new_id(), concept_key="towing", label="Emergency Towing Assistance", description="Towing")
    c_bet = BenefitConcept(id=new_id(), concept_key="waiver-of-betterment", label="Waiver of Betterment", description="Waives betterment")

    off_mpa = CatalogOffering(
        id=new_id(), catalog_revision_id=rev.id, concept_id=c_mpa.id,
        offering_key="motor-pa-plus", offering_kind="benefit", sort_order=10,
    )
    off_bet = CatalogOffering(
        id=new_id(), catalog_revision_id=rev.id, concept_id=c_bet.id,
        offering_key="waiver-of-betterment", offering_kind="benefit", sort_order=20,
    )

    bundle = CompanyBenefitBundle(
        id=new_id(), company_id=stmb.id, profile_id=prof.id, bundle_key="stmb-motor-pa-plus",
        name="Motor PA Plus", primary_concept_id=c_mpa.id, trigger_concept_ids=[c_mpa.id],
        has_plan_tiers=True, is_active=True,
    )
    tier4 = CompanyBenefitBundleTier(
        id=new_id(), bundle_id=bundle.id, tier_key="plan_4", label="Plan 4",
        match_tokens=["plan 4", "p4"], sort_order=4, is_default_fallback=False,
    )
    eff4 = CompanyBenefitBundleEffect(
        id=new_id(), tier_id=tier4.id, target_concept_id=c_tow.id, effect_type="upgrade_to_box2",
        display_title="Unlimited Emergency Towing", comparison_value="Unlimited", sort_order=1,
    )

    veh = TrackedVehicle(id=new_id(), vehicle_no="VQE8", car_brand="Honda", car_model="Civic", manufacture_year=2020)
    tenure = InsuranceTenure(
        id=new_id(), tracked_vehicle_id=veh.id, vehicle_no="VQE8", customer_name="Ali",
        coverage_start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 3, 31, tzinfo=timezone.utc),
        expiry_month="2027-03", motor_discount_pct=5.0, road_tax=20.0, runner_fee=0.0,
        include_road_tax=True, include_runner_fee=False,
    )
    draft = QuotationDraft(
        id=new_id(), uploaded_file_id=new_id(), owner_id=staff.id, company_id=stmb.id,
        catalog_revision_id=rev.id, revision=1, status="ready",
        fields={"premium": {"value": "1000.00", "status": "ready"}, "motor_premium": {"value": "1000.00", "status": "ready"}, "sum_insured": {"value": "80000.00", "status": "ready"}},
        display_options={}, scalar_decisions={},
    )
    sess = SessionModel(
        id=new_id(), owner_id=staff.id, uploaded_file_id=draft.uploaded_file_id,
        draft_id=draft.id, tenure_id=tenure.id, detected_company=stmb.name, status="active", is_tenure_active=True,
    )
    entry = TenureComparisonEntry(
        id=new_id(), tenure_id=tenure.id, session_id=sess.id, company_id=stmb.id, company_name=stmb.name,
        sum_insured=80000.0, motor_premium=1000.0, total_payable=1020.0, towing_limit="50 km", towing_km="50 km",
        extra_addons={}, manual_overrides=[], review_flags={}, version=1,
    )
    db.add_all([staff, stmb, prod, cat, rev, prof, c_mpa, c_tow, c_bet, off_mpa, off_bet, bundle, tier4, eff4, veh, tenure, draft, sess, entry])
    db.commit()

    # 1. Read-only GET (service + HTTP route handler) must not dirty SQLAlchemy Session state
    from app.api.routers.comparison import get_comparison

    comp_data = get_marketing_comparison(db, tenure.id, allow_commit=False)
    assert len(comp_data["entries"]) == 1
    assert not db.new and not db.dirty and not db.deleted
    http_comp_data = get_comparison(tenure_id=tenure.id, db=db, user=staff)
    assert len(http_comp_data["entries"]) == 1
    assert not db.new and not db.dirty and not db.deleted

    # 2. Comparison -> Workspace Box 2 bundle sync ("Unlimited" towing activates Motor PA Plus Plan 4)
    sync_session_draft_from_comparison(
        db, tenure, sess.id,
        edited_fields=["towing_limit"], field_values={"towing_limit": "Unlimited"}, user_id=staff.id,
    )
    db.commit()
    mpa_sel = db.scalar(select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id, DraftBenefitSelection.concept_id == c_mpa.id))
    assert mpa_sel is not None and mpa_sel.state == "current" and mpa_sel.bundle_tier_id == tier4.id

    # 3. Workspace Box 2 -> Comparison sync (remove Motor PA Plus & add catalog Betterment with label_override=None)
    db.refresh(draft)
    bet_sel = DraftBenefitSelection(
        id=new_id(), draft_id=draft.id, selection_key=f"catalog:{off_bet.offering_key}",
        catalog_offering_id=off_bet.id, concept_id=c_bet.id, item_kind="catalog",
        state="available_addon", cost_status="included", label_override=None, evidence_snapshot={},
    )
    db.add(bet_sel)
    db.commit()

    draft_workspace_patch(
        draft_id=draft.id,
        payload=WorkspacePatchRequest(
            base_revision=draft.revision,
            operations=[
                {"op": "benefit_update", "selection_id": mpa_sel.id, "state": "removed"},
                {"op": "benefit_update", "selection_id": bet_sel.id, "state": "current"},
            ],
        ),
        db=db,
        user=staff,
    )
    db.refresh(entry)
    assert entry.towing_limit == "50 km"
    assert entry.waiver_betterment is True
    assert float(entry.betterment_rate) == 0.0

    # 4. Cover Note single-discount parity (total_payable=970 -> net_motor=950 -> gross=1000 with 5% discount, NOT double-discounted!)
    cn_draft = QuotationDraft(
        id=new_id(), uploaded_file_id=new_id(), owner_id=staff.id, company_id=stmb.id,
        fields={"premium": {"value": "1000.00", "status": "ready"}}, display_options={},
    )
    cn_sess = SessionModel(
        id=new_id(), owner_id=staff.id, uploaded_file_id=cn_draft.uploaded_file_id, draft_id=cn_draft.id,
        tenure_id=tenure.id, document_type="covernote", detected_company=stmb.name, status="active", is_tenure_active=True,
    )
    tenure.covernote_session_id = cn_sess.id
    tenure.winning_company_id = stmb.id
    db.add_all([cn_draft, cn_sess])
    db.commit()

    from app.services.marketing_comparison.covernote_sync import sync_and_update_covernote

    cn_out = sync_and_update_covernote(db, tenure.id, {"total_payable": 970.0}, user_id=staff.id)
    assert cn_out["covernote_policy"]["motor_premium"] == 1000.0
    assert cn_out["covernote_policy"]["net_motor_premium"] == 950.0
    assert cn_out["covernote_policy"]["net_total_payable"] == 970.0


def test_motor_pa_plus_unlimited_towing_removal_switch_and_revert(db: Session):
    """Verify:
    1. STMB Motor PA Plus + 'Unlimited Towing' (without literal 'Plan 4') resolves Unlimited.
    2. Removing Motor PA Plus in Workspace downgrades Comparison to 50 km even with raw PDF lines.
    3. Switching Motor PA Plus Plan 1 -> Plan 4 overrides stale manually_edited on towing card.
    4. Reverting towing_limit override via PATCH clear_override_field syncs back to Workspace.
    """
    from app.api.routers.comparison import UpdateComparisonEntryPatch, patch_comparison_entry
    from app.api.routers.sessions import draft_workspace_patch
    from app.api.schemas import WorkspacePatchRequest
    from app.models.tables import (
        Batch,
        BenefitProfile,
        CatalogOffering,
        CompanyBenefitBundle,
        CompanyBenefitBundleEffect,
        CompanyBenefitBundleTier,
        ExtractionBenefitLine,
        ExtractionRecord,
        UploadedFile,
    )
    from app.rendering.render_context import resolve_benefit_cards
    from app.services.marketing_comparison.benefits_extractor import _resolve_comparison_benefits

    staff = User(id=new_id(), email="staff-towing-fix@rl.test", password_hash="x", role="staff", status="active")
    stmb = InsuranceCompany(
        id=new_id(),
        name="Syarikat Takaful Malaysia Am Berhad",
        slug="takaful-malaysia",
        policy_rules={
            "towing": {
                "metric": "km",
                "base_limit": "50 km",
                "upgrade_triggers": ["motor pa plus", "motor pa"],
                "plan_limits": {"plan 1": "100 km", "plan 2": "200 km", "plan 3": "300 km", "plan 4": "Unlimited"},
            },
        },
    )
    prod = InsuranceProduct(id=new_id(), company_id=stmb.id, product_key="stmb-car", name="Private Car")
    cat = BenefitCatalog(id=new_id(), company_id=stmb.id, product_id=prod.id, name="STMB Catalog")
    rev = BenefitCatalogRevision(id=new_id(), catalog_id=cat.id, revision_number=1, state="published", content_hash="h-mpa")
    prof = BenefitProfile(id=new_id(), name="Default Profile", is_active=True, status="active")

    c_mpa = BenefitConcept(id=new_id(), concept_key="motor-pa-plus", label="Motor PA Plus", description="PA + Towing")
    c_tow = BenefitConcept(id=new_id(), concept_key="towing", label="Emergency Towing Assistance", description="Towing")

    off_mpa = CatalogOffering(
        id=new_id(), catalog_revision_id=rev.id, concept_id=c_mpa.id,
        offering_key="motor-pa-plus", offering_kind="optional", role="addon_option", sort_order=20,
    )
    off_tow = CatalogOffering(
        id=new_id(), catalog_revision_id=rev.id, concept_id=c_tow.id,
        offering_key="towing-base", offering_kind="base", role="included", display_value="50 km", sort_order=10,
    )

    bundle = CompanyBenefitBundle(
        id=new_id(), company_id=stmb.id, profile_id=prof.id, bundle_key="stmb-motor-pa-plus",
        name="Motor PA Plus", primary_concept_id=c_mpa.id, trigger_concept_ids=[c_mpa.id],
        match_aliases=["motor pa plus", "motor pa+", "motor pa"], has_plan_tiers=True, is_active=True,
    )
    tier1 = CompanyBenefitBundleTier(
        id=new_id(), bundle_id=bundle.id, tier_key="plan_1", label="Plan 1",
        match_tokens=["plan 1", "p1"], sort_order=10, is_default_fallback=True,
    )
    eff1 = CompanyBenefitBundleEffect(
        id=new_id(), tier_id=tier1.id, target_concept_id=c_tow.id, effect_type="upgrade_to_box2",
        display_title="Towing Assistance (100 km)", comparison_value="100 km", sort_order=10,
    )
    tier4 = CompanyBenefitBundleTier(
        id=new_id(), bundle_id=bundle.id, tier_key="plan_4", label="Plan 4",
        match_tokens=["plan 4", "p4"], sort_order=40, is_default_fallback=False,
    )
    eff4 = CompanyBenefitBundleEffect(
        id=new_id(), tier_id=tier4.id, target_concept_id=c_tow.id, effect_type="upgrade_to_box2",
        display_title="Unlimited Towing Assistance", comparison_value="Unlimited", icon_hint="unlimited_towing", sort_order=10,
    )

    batch = Batch(id=new_id(), owner_id=staff.id, name="STMB Batch", status="ready")
    ufile = UploadedFile(
        id=new_id(), batch_id=batch.id, owner_id=staff.id, original_filename="stmb.pdf",
        content_type="application/pdf", storage_path="local/stmb.pdf", insurance_company_id=stmb.id,
    )
    ext_rec = ExtractionRecord(
        id=new_id(), uploaded_file_id=ufile.id,
        raw_text="Motor PA Plus\nUnlimited Towing Assistance\n",
        benefit_lines=[{"raw_label": "Motor PA Plus"}, {"raw_label": "Unlimited Towing"}],
    )
    ext_line = ExtractionBenefitLine(
        id=new_id(), extraction_record_id=ext_rec.id, line_id="l-mpa",
        raw_label="Motor PA Plus - Unlimited Towing", normalized_label="motor pa plus unlimited towing",
        inclusion_state="included", evidence={"raw_text": "Motor PA Plus Unlimited Towing"},
    )

    veh = TrackedVehicle(id=new_id(), vehicle_no="VPA88", car_brand="Perodua", car_model="Myvi", manufacture_year=2022)
    tenure = InsuranceTenure(
        id=new_id(), tracked_vehicle_id=veh.id, vehicle_no="VPA88", customer_name="Siti",
        coverage_start_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 4, 30, tzinfo=timezone.utc),
        expiry_month="2027-04", road_tax=20.0, runner_fee=0.0, include_road_tax=True, include_runner_fee=False,
    )
    draft = QuotationDraft(
        id=new_id(), uploaded_file_id=ufile.id, owner_id=staff.id, company_id=stmb.id,
        catalog_revision_id=rev.id, revision=1, status="ready",
        fields={"premium": {"value": "900.00", "status": "ready"}, "sum_insured": {"value": "50000.00", "status": "ready"}},
        display_options={}, scalar_decisions={},
    )
    sess = SessionModel(
        id=new_id(), owner_id=staff.id, uploaded_file_id=ufile.id,
        draft_id=draft.id, tenure_id=tenure.id, detected_company=stmb.name, status="active", is_tenure_active=True,
    )
    tow_sel = DraftBenefitSelection(
        id=new_id(), draft_id=draft.id, selection_key=f"catalog:{off_tow.offering_key}",
        catalog_offering_id=off_tow.id, concept_id=c_tow.id, item_kind="catalog",
        state="current", cost_status="included", evidence_snapshot={"source": "manual", "manually_edited": True},
    )
    mpa_sel = DraftBenefitSelection(
        id=new_id(), draft_id=draft.id, selection_key=f"catalog:{off_mpa.offering_key}",
        catalog_offering_id=off_mpa.id, concept_id=c_mpa.id, item_kind="catalog",
        state="current", cost_status="paid", evidence_snapshot={"extracted_label": "Motor PA Plus - Unlimited Towing"},
    )
    entry = TenureComparisonEntry(
        id=new_id(), tenure_id=tenure.id, session_id=sess.id, company_id=stmb.id, company_name=stmb.name,
        sum_insured=50000.0, motor_premium=900.0, total_payable=920.0, towing_limit="50 km", towing_km="50 km",
        extra_addons={}, manual_overrides=[], review_flags={}, version=1,
    )
    db.add_all([
        staff, stmb, prod, cat, rev, prof, c_mpa, c_tow, off_mpa, off_tow,
        bundle, tier1, eff1, tier4, eff4, batch, ufile, ext_rec, ext_line,
        veh, tenure, draft, sess, tow_sel, mpa_sel, entry,
    ])
    db.commit()

    # 1. Unlimited Towing detected from Pass 3 effect matching even without literal 'Plan 4'
    b_res = _resolve_comparison_benefits(db, sess, stmb.id, draft.fields, None)
    assert b_res["towing_km"] == "Unlimited"
    assert b_res["towing_uncertain"] is False

    # 2. Removing Motor PA Plus in Workspace downgrades Comparison to '50 km' (no PDF text re-trigger)
    draft_workspace_patch(
        draft_id=draft.id,
        payload=WorkspacePatchRequest(
            base_revision=draft.revision,
            operations=[{"op": "benefit_update", "selection_id": mpa_sel.id, "state": "removed"}],
        ),
        db=db,
        user=staff,
    )
    db.refresh(entry)
    assert entry.towing_limit == "50 km"

    # 3. Re-add Motor PA Plus at Plan 1 then switch to Plan 4; stale manually_edited on towing card is cleared
    db.refresh(draft)
    draft_workspace_patch(
        draft_id=draft.id,
        payload=WorkspacePatchRequest(
            base_revision=draft.revision,
            operations=[{"op": "benefit_update", "selection_id": mpa_sel.id, "state": "current", "bundle_tier_id": tier1.id}],
        ),
        db=db,
        user=staff,
    )
    db.refresh(entry)
    assert entry.towing_limit == "100 km"

    db.refresh(draft)
    draft_workspace_patch(
        draft_id=draft.id,
        payload=WorkspacePatchRequest(
            base_revision=draft.revision,
            operations=[{"op": "benefit_update", "selection_id": mpa_sel.id, "bundle_tier_id": tier4.id}],
        ),
        db=db,
        user=staff,
    )
    db.refresh(entry)
    db.refresh(tow_sel)
    assert entry.towing_limit == "Unlimited"
    cards = resolve_benefit_cards(
        selections=[tow_sel, mpa_sel],
        offerings=[off_tow, off_mpa],
        concepts=[c_tow, c_mpa],
        relations=[],
        facets=[],
        company_bundles=[bundle],
    )
    towing_card = next(c for c in cards["current_benefits"] if c["concept_key"] == "towing")
    assert towing_card["label"] == "Unlimited Towing Assistance"
    assert towing_card["is_bundle_effect"] is True

    # 4. Override towing_limit to 200 km in Comparison, then revert via clear_override_field -> syncs back to Workspace
    patch_comparison_entry(
        tenure_id=tenure.id,
        entry_id=entry.id,
        payload=UpdateComparisonEntryPatch(towing_limit="200 km"),
        db=db,
        user=staff,
    )
    db.refresh(entry)
    assert entry.towing_limit == "200 km"
    assert "towing_limit" in (entry.manual_overrides or [])

    patch_comparison_entry(
        tenure_id=tenure.id,
        entry_id=entry.id,
        payload=UpdateComparisonEntryPatch(clear_override_field="towing_limit"),
        db=db,
        user=staff,
    )
    db.refresh(entry)
    db.refresh(mpa_sel)
    assert entry.towing_limit == "Unlimited"
    assert "towing_limit" not in (entry.manual_overrides or [])
    assert mpa_sel.state == "current" and mpa_sel.bundle_tier_id == tier4.id


def test_llp_and_llop_separated_across_comparison_and_workspace(db: Session):
    """Verify LLP (Endt 100) and LLOP (Endt 72 / Negligent Acts) stay independent across Comparison <-> Workspace."""
    from app.api.routers.comparison import UpdateComparisonEntryPatch, patch_comparison_entry
    from app.api.routers.sessions import draft_workspace_patch
    from app.api.schemas import WorkspacePatchRequest
    from app.models.tables import CatalogOffering
    from app.services.marketing_comparison.benefits_extractor import _resolve_comparison_benefits

    staff = User(id=new_id(), email="staff-llp-sep@rl.test", password_hash="x", role="staff", status="active")
    etiqa = InsuranceCompany(id=new_id(), name="Etiqa General Insurance", slug="etiqa", policy_rules={})
    prod = InsuranceProduct(id=new_id(), company_id=etiqa.id, product_key="etiqa-car", name="Private Car")
    cat = BenefitCatalog(id=new_id(), company_id=etiqa.id, product_id=prod.id, name="Etiqa Catalog")
    rev = BenefitCatalogRevision(id=new_id(), catalog_id=cat.id, revision_number=1, state="published", content_hash="h-llp")

    c_llp = BenefitConcept(id=new_id(), concept_key="legal-liability-to-passengers", label="Legal Liability to Passengers", description="Endt 100")
    c_llop = BenefitConcept(id=new_id(), concept_key="legal-liability-of-passengers", label="Legal Liability of Passengers", description="Endt 72")
    off_llp = CatalogOffering(
        id=new_id(), catalog_revision_id=rev.id, concept_id=c_llp.id,
        offering_key="llp-addon", offering_kind="optional", role="addon_option", sort_order=10,
    )
    off_llop = CatalogOffering(
        id=new_id(), catalog_revision_id=rev.id, concept_id=c_llop.id,
        offering_key="llop-addon", offering_kind="optional", role="addon_option", sort_order=20,
    )

    veh = TrackedVehicle(id=new_id(), vehicle_no="VLLP1", car_brand="Honda", car_model="City", manufacture_year=2023)
    tenure = InsuranceTenure(
        id=new_id(), tracked_vehicle_id=veh.id, vehicle_no="VLLP1", customer_name="Ah Chong",
        coverage_start_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 5, 31, tzinfo=timezone.utc),
        expiry_month="2027-05", road_tax=20.0, runner_fee=0.0, include_road_tax=True, include_runner_fee=False,
    )
    draft = QuotationDraft(
        id=new_id(), uploaded_file_id=new_id(), owner_id=staff.id, company_id=etiqa.id,
        catalog_revision_id=rev.id, revision=1, status="ready",
        fields={
            "premium": {"value": "1200.00", "status": "ready"},
            "sum_insured": {"value": "70000.00", "status": "ready"},
            "optional_covers": {"value": "LLP for Negligent Acts (Endorsement 72)", "status": "ready"},
        },
        display_options={}, scalar_decisions={},
    )
    sess = SessionModel(
        id=new_id(), owner_id=staff.id, uploaded_file_id=draft.uploaded_file_id,
        draft_id=draft.id, tenure_id=tenure.id, detected_company=etiqa.name, status="active", is_tenure_active=True,
    )
    llop_sel = DraftBenefitSelection(
        id=new_id(), draft_id=draft.id, selection_key=f"catalog:{off_llop.offering_key}",
        catalog_offering_id=off_llop.id, concept_id=c_llop.id, item_kind="catalog",
        state="current", cost_status="paid", label_override=None, evidence_snapshot={},
    )
    db.add_all([staff, etiqa, prod, cat, rev, c_llp, c_llop, off_llp, off_llop, veh, tenure, draft, sess, llop_sel])
    db.commit()

    # 1. 'LLP for Negligent Acts' (Endt 72) resolves LLOP='Included' and LLP=None
    b_res = _resolve_comparison_benefits(db, sess, etiqa.id, draft.fields, None)
    assert b_res["llop"] == "Included"
    assert b_res["llp"] is None

    comp = get_marketing_comparison(db, tenure.id, allow_commit=True)
    entry_id = comp["entries"][0]["id"]
    assert comp["entries"][0]["llop"] == "Included"
    assert comp["entries"][0]["llp"] is None

    # 2. Enabling LLP in Comparison activates ONLY legal-liability-to-passengers in Workspace
    patch_comparison_entry(
        tenure_id=tenure.id,
        entry_id=entry_id,
        payload=UpdateComparisonEntryPatch(llp="Included"),
        db=db,
        user=staff,
    )
    llp_sel = db.scalar(select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id, DraftBenefitSelection.concept_id == c_llp.id))
    db.refresh(llop_sel)
    assert llp_sel is not None and llp_sel.state == "current"
    assert llop_sel.state == "current"

    # 3. Disabling LLOP in Comparison deactivates ONLY LLOP while keeping LLP active
    patch_comparison_entry(
        tenure_id=tenure.id,
        entry_id=entry_id,
        payload=UpdateComparisonEntryPatch(llop="Not Included"),
        db=db,
        user=staff,
    )
    db.refresh(llp_sel)
    db.refresh(llop_sel)
    assert llp_sel.state == "current"
    assert llop_sel.state == "available_addon"

    # 4. Removing LLP in Quotation Workspace clears entry.llp without affecting entry.llop
    db.refresh(draft)
    draft_workspace_patch(
        draft_id=draft.id,
        payload=WorkspacePatchRequest(
            base_revision=draft.revision,
            operations=[
                {"op": "benefit_update", "selection_id": llp_sel.id, "state": "available_addon"},
                {"op": "benefit_update", "selection_id": llop_sel.id, "state": "current"},
            ],
        ),
        db=db,
        user=staff,
    )
    entry_row = db.get(TenureComparisonEntry, entry_id)
    assert entry_row.llp is None
    assert entry_row.llop == "Included"


