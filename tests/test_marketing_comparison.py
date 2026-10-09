"""Hermetic unit tests for marketing_comparison_service."""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.tables import (
    Base,
    Batch,
    InsuranceCompany,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.marketing_comparison_service import (
    delete_comparison_entry,
    format_whatsapp_teaser,
    get_marketing_comparison,
    save_comparison_entry,
    select_winner_and_generate_draft,
    update_tenure_fixed_costs,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _seed_tenure_with_sessions(db: Session):
    owner = User(
        id=new_id(),
        email="broker@risklocker.local",
        name="Eugene Lee",
        password_hash="mock",
        role="agent",
    )
    db.add(owner)

    vehicle = TrackedVehicle(
        id=new_id(),
        vehicle_no="JWK9488",
        car_brand="Perodua",
        car_model="Aruz 1.5 AV",
        engine_cc="1496 CC",
    )
    db.add(vehicle)

    # Current tenure (2026-2027)
    tenure_2026 = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no="JWK9488",
        customer_name="TEY SIOK BEE",
        coverage_start_date=datetime(2026, 9, 8, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 9, 7, tzinfo=timezone.utc),
        expiry_month="2027-09",
        status="sourced",
        road_tax=70.0,
        runner_fee=50.0,
        windscreen_target=1700.0,
        ncd_percentage=55.0,
    )
    db.add(tenure_2026)

    # Previous tenure (2025-2026)
    qbe_comp = InsuranceCompany(id=new_id(), name="QBE Insurance", slug="qbe")
    db.add(qbe_comp)

    tenure_2025 = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no="JWK9488",
        customer_name="TEY SIOK BEE",
        coverage_start_date=datetime(2025, 9, 8, tzinfo=timezone.utc),
        coverage_end_date=datetime(2026, 9, 7, tzinfo=timezone.utc),
        expiry_month="2026-09",
        status="hit",
        winning_company_id=qbe_comp.id,
        winning_quotation_ref="RL-2025-QBE-01",
        won_premium=943.87,
    )
    db.add(tenure_2025)

    # Sourced session 1: Etiqa
    file_id_1 = new_id()
    draft_1 = QuotationDraft(
        id=new_id(),
        uploaded_file_id=file_id_1,
        owner_id=owner.id,
        fields={
            "sum_insured": "56000.00",
            "basic_premium": "1110.40",
            "agreed_value": False,
            "towing_limit": "Unlimited",
            "waiver_of_betterment": False,
            "excess": 0.0,
        },
    )
    session_1 = SessionModel(
        id=new_id(),
        owner_id=owner.id,
        uploaded_file_id=file_id_1,
        draft_id=draft_1.id,
        tenure_id=tenure_2026.id,
        detected_company="Etiqa Insurance",
        tenure_version=1,
        is_tenure_active=True,
    )
    db.add_all([draft_1, session_1])

    # Sourced session 2: STMB
    file_id_2 = new_id()
    draft_2 = QuotationDraft(
        id=new_id(),
        uploaded_file_id=file_id_2,
        owner_id=owner.id,
        fields={
            "sum_insured": "57000.00",
            "basic_premium": "1064.10",
            "agreed_value": True,
            "towing_limit": "Unlimited",
            "waiver_of_betterment": True,
            "excess": 0.0,
        },
    )
    session_2 = SessionModel(
        id=new_id(),
        owner_id=owner.id,
        uploaded_file_id=file_id_2,
        draft_id=draft_2.id,
        tenure_id=tenure_2026.id,
        detected_company="STMB Insurance",
        tenure_version=1,
        is_tenure_active=True,
    )
    db.add_all([draft_2, session_2])

    db.commit()
    return tenure_2026, session_1, session_2, owner


def test_get_marketing_comparison_auto_hydration(db_session: Session):
    tenure, s1, s2, _ = _seed_tenure_with_sessions(db_session)

    res = get_marketing_comparison(db_session, tenure.id)

    # Check tenure metadata & fixed costs
    assert res["tenure"]["vehicle_no"] == "JWK9488"
    assert res["tenure"]["customer_name"] == "TEY SIOK BEE"
    assert res["tenure"]["fixed_costs_total"] == 120.0  # 70 road tax + 50 runner fee

    # Check auto-hydrated entries
    entries = res["entries"]
    assert len(entries) == 2

    etiqa = next(e for e in entries if "Etiqa" in e["company_name"])
    assert etiqa["sum_insured"] == 56000.0
    assert etiqa["motor_premium"] == 1110.40
    assert etiqa["total_payable"] == 1110.40 + 120.0  # 1230.40
    assert etiqa["agreed_value"] is False
    assert etiqa["waiver_betterment"] is False
    assert round(etiqa["rate_percentage"], 2) == 1.98

    stmb = next(e for e in entries if "STMB" in e["company_name"])
    assert stmb["sum_insured"] == 57000.0
    assert stmb["motor_premium"] == 1064.10
    assert stmb["total_payable"] == 1064.10 + 120.0  # 1184.10
    assert stmb["agreed_value"] is True
    assert stmb["waiver_betterment"] is True
    assert round(stmb["rate_percentage"], 2) == 1.87

    # Check previous policy linkage (2025 tenure)
    prev = res["previous_policy"]
    assert prev is not None
    assert prev["year"] == 2025
    assert prev["insurance_premium"] == 943.87
    assert prev["insurer"] == "QBE Insurance"


def test_update_tenure_fixed_costs(db_session: Session):
    tenure, _, _, _ = _seed_tenure_with_sessions(db_session)

    # Initial auto-hydration
    get_marketing_comparison(db_session, tenure.id)

    # Update road tax to 100, runner fee to 60 (total fixed = 160)
    res = update_tenure_fixed_costs(db_session, tenure.id, road_tax=100.0, runner_fee=60.0)

    assert res["tenure"]["road_tax"] == 100.0
    assert res["tenure"]["runner_fee"] == 60.0
    assert res["tenure"]["fixed_costs_total"] == 160.0

    # Ensure all entries have updated total payable
    for e in res["entries"]:
        assert e["total_payable"] == e["motor_premium"] + 160.0


def test_update_tenure_coverage_dates(db_session: Session):
    tenure, s1, s2, _ = _seed_tenure_with_sessions(db_session)

    res = update_tenure_fixed_costs(
        db_session,
        tenure.id,
        road_tax=70.0,
        runner_fee=50.0,
        coverage_start_date="2026-11-01",
        coverage_end_date="2027-10-31",
    )

    assert res["tenure"]["coverage_period_formatted"] == "01/11/2026 - 31/10/2027"
    assert tenure.coverage_start_date.strftime("%Y-%m-%d") == "2026-11-01"
    assert tenure.coverage_end_date.strftime("%Y-%m-%d") == "2027-10-31"
    assert tenure.expiry_month == "2027-10"

    # Verify dates propagated to linked sessions and drafts
    db_session.refresh(s1)
    db_session.refresh(s2)
    assert s1.coverage_start_date is not None and s1.coverage_start_date.strftime("%Y-%m-%d") == "2026-11-01"
    assert s1.coverage_end_date is not None and s1.coverage_end_date.strftime("%Y-%m-%d") == "2027-10-31"
    assert s1.draft.fields["coverage_start_date"].startswith("2026-11-01")
    assert s1.draft.fields["coverage_end_date"].startswith("2027-10-31")



def test_save_and_delete_comparison_entry(db_session: Session):
    tenure, _, _, _ = _seed_tenure_with_sessions(db_session)

    # Initial auto-hydration from sessions
    get_marketing_comparison(db_session, tenure.id)

    # Add a manual quote for QBE Insurance
    manual_payload = {
        "company_name": "QBE Insurance",
        "sum_insured": 57000.0,
        "valuation_type": "agreed_value",
        "motor_premium": 1104.75,
        "towing_limit": "Unlimited",
        "agreed_value": True,
        "waiver_betterment": True,
        "excess": 0.0,
        "is_recommended": True,
        "is_manual": True,
    }

    res = save_comparison_entry(db_session, tenure.id, manual_payload)
    assert len(res["entries"]) == 3

    qbe = next(e for e in res["entries"] if "QBE" in e["company_name"])
    assert qbe["sum_insured"] == 57000.0
    assert qbe["total_payable"] == 1104.75 + 120.0  # 1224.75 matching Excel!
    assert qbe["is_recommended"] is True

    # Delete the QBE entry
    res_del = delete_comparison_entry(db_session, tenure.id, qbe["id"])
    assert len(res_del["entries"]) == 2
    assert not any("QBE" in e["company_name"] for e in res_del["entries"])


def test_select_winner_and_generate_draft(db_session: Session):
    tenure, s1, s2, user = _seed_tenure_with_sessions(db_session)

    res = get_marketing_comparison(db_session, tenure.id)
    stmb_entry = next(e for e in res["entries"] if "STMB" in e["company_name"])

    win_res = select_winner_and_generate_draft(db_session, tenure.id, stmb_entry["id"], user.id)

    assert win_res["status"] == "success"
    assert win_res["winning_company"] == "STMB Insurance"
    assert win_res["total_payable"] == 1184.10
    assert win_res["session_id"] == s2.id
    assert win_res["quotation_ref"].startswith("RL-")

    # Check tenure record updated
    assert tenure.status == "quoted"
    assert tenure.won_premium is not None and float(tenure.won_premium) == 1184.10


def test_format_whatsapp_teaser(db_session: Session):
    tenure, _, _, _ = _seed_tenure_with_sessions(db_session)

    teaser = format_whatsapp_teaser(db_session, tenure.id)
    assert "JWK9488" in teaser
    assert "TEY SIOK BEE" in teaser
    assert "Etiqa Insurance" in teaser
    assert "Roadtax and Runner fee : RM 120.00" in teaser


def test_multi_winner_selection_coexistence_and_deselection(db_session: Session):
    tenure, s1, s2, user = _seed_tenure_with_sessions(db_session)

    res = get_marketing_comparison(db_session, tenure.id)
    etiqa = next(e for e in res["entries"] if "Etiqa" in e["company_name"])
    stmb = next(e for e in res["entries"] if "STMB" in e["company_name"])

    # 1. Select Etiqa as winner
    res1 = select_winner_and_generate_draft(db_session, tenure.id, etiqa["id"], user.id)
    assert res1["status"] == "success"
    assert res1["is_recommended"] is True
    assert res1["selected_count"] == 1

    # 2. Select STMB as second winner (coexistence!)
    res2 = select_winner_and_generate_draft(db_session, tenure.id, stmb["id"], user.id)
    assert res2["status"] == "success"
    assert res2["is_recommended"] is True
    assert res2["selected_count"] == 2

    # Check both are recommended in comparison matrix
    res_both = get_marketing_comparison(db_session, tenure.id)
    rec_both = [e for e in res_both["entries"] if e["is_recommended"]]
    assert len(rec_both) == 2, "Both selected underwriters must coexist as winners"

    # 3. WhatsApp teaser reflects both shortlisted options
    teaser = format_whatsapp_teaser(db_session, tenure.id)
    assert "Shortlisted Options (2)" in teaser

    # 4. Deselect Etiqa (click to deselect)
    res_unpick = select_winner_and_generate_draft(db_session, tenure.id, etiqa["id"], user.id)
    assert res_unpick["is_recommended"] is False
    assert res_unpick["selected_count"] == 1

    # Check only STMB remains recommended
    res_after = get_marketing_comparison(db_session, tenure.id)
    rec_after = [e for e in res_after["entries"] if e["is_recommended"]]
    assert len(rec_after) == 1
    assert "STMB" in rec_after[0]["company_name"]

    # 5. Deselect STMB too (now 0 winners)
    res_zero = select_winner_and_generate_draft(db_session, tenure.id, stmb["id"], user.id)
    assert res_zero["is_recommended"] is False
    assert res_zero["selected_count"] == 0
    assert tenure.winning_company_id is None


def test_dict_wrapped_extraction_fields_and_auto_healing(db_session: Session):
    owner = User(
        id=new_id(),
        email="porsche@risklocker.local",
        name="Eugene Lee",
        password_hash="mock",
        role="agent",
    )
    db_session.add(owner)

    vehicle = TrackedVehicle(
        id=new_id(),
        vehicle_no="JRC3838",
        car_brand="Porsche",
        car_model="911",
        engine_cc="3596 CC",
    )
    db_session.add(vehicle)

    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no="JRC3838",
        customer_name="JEYARATNAM S/O PANCHARATNAM",
        coverage_start_date=datetime(2026, 10, 30, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 10, 29, tzinfo=timezone.utc),
        expiry_month="2027-10",
        status="sourced",
        road_tax=0.0,
        runner_fee=50.0,
        windscreen_target=1700.0,
        ncd_percentage=55.0,
    )
    db_session.add(tenure)

    # Session with dict-wrapped ExtractionField values (mimicking real Gemini extraction)
    f_id = new_id()
    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=f_id,
        owner_id=owner.id,
        fields={
            "sum_insured": {"value": "4000.00", "status": "ready"},
            "coverage_amount": {"value": "115,000.00", "status": "ready"},
            "total_amount": {"value": "2881.70", "status": "ready"},
            "gross_premium": {"value": "2658.98", "status": "ready"},
            "roadtax": {"value": "4812.00", "status": "ready"},
            "valuation_type": {"value": "Agreed Value", "status": "ready"},
            "agreed_value": {"value": "115000.00", "status": "ready"},
            "compulsory_excess": {"value": "400.00", "status": "ready"},
            "windscreen_coverage": {"value": "4000.00", "status": "ready"},
        },
    )
    session = SessionModel(
        id=new_id(),
        owner_id=owner.id,
        uploaded_file_id=f_id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        detected_company="Berjaya Sompo",
        tenure_version=1,
        is_tenure_active=True,
    )
    db_session.add_all([draft, session])

    # Pre-populate a corrupted zeroed entry as happened before
    stale_entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        session_id=session.id,
        company_name="Berjaya Sompo",
        sum_insured=0.0,
        motor_premium=0.0,
        road_tax=0.0,
        runner_fee=50.0,
        total_payable=50.0,
        valuation_type="market_value",
        agreed_value=False,
    )
    db_session.add(stale_entry)
    db_session.commit()

    # Call get_marketing_comparison which triggers auto-healing
    res = get_marketing_comparison(db_session, tenure.id)

    # Verify road tax was auto-detected and synced
    assert res["tenure"]["road_tax"] == 4812.0
    assert res["tenure"]["fixed_costs_total"] == 4862.0  # 4812 + 50

    # Verify entry was auto-healed with real values
    entries = res["entries"]
    assert len(entries) == 1
    healed = entries[0]
    assert healed["sum_insured"] == 115000.0  # Chose car sum insured over 4k windscreen
    assert healed["motor_premium"] == 2881.70  # Chose total_amount
    assert healed["road_tax"] == 4812.0
    assert healed["total_payable"] == 2881.70 + 4862.0
    assert healed["agreed_value"] is True
    assert healed["excess"] == 0.0  # Statutory compulsory excess (RM 400) excluded per Task A2.3
    assert healed["windscreen_sum_insured"] == 4000.0

    # Verify recommended sum insured is non-zero
    assert res["recommended_sum_insured"]["Berjaya"] == 115000.0


def test_detect_runner_fee_from_id_helper():
    from app.services.marketing_comparison_service import detect_runner_fee_from_id

    # Passport tests -> RM 20.00
    assert detect_runner_fee_from_id("K1584766Z") == 20.0
    assert detect_runner_fee_from_id("A12345678") == 20.0
    assert detect_runner_fee_from_id("p9876543") == 20.0

    # Malaysian MyKad tests -> RM 10.00
    assert detect_runner_fee_from_id("881205015522") == 10.0
    assert detect_runner_fee_from_id("900101-14-5567") == 10.0
    assert detect_runner_fee_from_id("020304011234") == 10.0

    # Default fallback
    assert detect_runner_fee_from_id(None) == 10.0
    assert detect_runner_fee_from_id("") == 10.0
    assert detect_runner_fee_from_id("   ") == 10.0


def test_runner_fee_auto_assignment_in_tenure(db_session: Session):
    from app.models.tables import InsuranceTenure, TrackedVehicle, User, Session as SessionModel, QuotationDraft, UploadedFile, Batch
    from app.services.marketing_comparison_service import get_marketing_comparison

    user = User(name="Agent", email="agent_rf@test.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    vehicle = TrackedVehicle(vehicle_no="KAY1234", car_model="Honda Civic")
    db_session.add(vehicle)
    db_session.flush()

    tenure = InsuranceTenure(
        tracked_vehicle_id=vehicle.id,
        vehicle_no="KAY1234",
        customer_name="JEYARATNAM S/O PANCHARATNAM",
        coverage_start_date=datetime(2026, 9, 28, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 9, 27, tzinfo=timezone.utc),
        expiry_month="2027-09",
        status="draft",
        road_tax=4812.00,
        runner_fee=0.00,  # Initially unassigned
    )
    db_session.add(tenure)
    db_session.flush()

    batch = Batch(owner_id=user.id, name="Test Batch")
    db_session.add(batch)
    db_session.flush()

    uf = UploadedFile(
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="amassurance_passport.pdf",
        content_type="application/pdf",
        storage_path=".qc-tmp/test.pdf",
    )
    db_session.add(uf)
    db_session.flush()

    # Draft has passport IC: K1584766Z
    draft = QuotationDraft(
        owner_id=user.id,
        uploaded_file_id=uf.id,
        fields={
            "ic_no": "K1584766Z",
            "sum_insured": 85000.0,
            "total_payable": 1850.0,
        },
    )
    db_session.add(draft)
    db_session.flush()

    sess = SessionModel(
        owner_id=user.id,
        uploaded_file_id=uf.id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        detected_company="AmAssurance",
        is_tenure_active=True,
    )
    db_session.add(sess)
    db_session.commit()

    # Call get_marketing_comparison
    res = get_marketing_comparison(db_session, tenure.id)

    # Runner fee should have been auto-assigned to 20.00 (Passport)
    assert res["tenure"]["runner_fee"] == 20.0
    assert res["tenure"]["runner_fee_type"] == "passport"
    assert res["tenure"]["fixed_costs_total"] == 4812.0 + 20.0

    # Entry should have runner fee 20.00
    entry = res["entries"][0]
    assert entry["runner_fee"] == 20.0
    assert entry["total_payable"] == entry["motor_premium"] + 4812.0 + 20.0


def test_manual_quote_winner_selection_creates_session_and_uploaded_file(db_session: Session):
    """Verify manual quote winner selection creates valid UploadedFile and Session without FK violation."""
    user = User(id=new_id(), email="agent@risklocker.local", name="Agent 007", password_hash="x")
    db_session.add(user)

    vehicle = TrackedVehicle(vehicle_no="WXY9999", car_model="Proton X50")
    db_session.add(vehicle)
    db_session.flush()

    tenure = InsuranceTenure(
        tracked_vehicle_id=vehicle.id,
        vehicle_no="WXY9999",
        customer_name="Tan Ah Kow",
        coverage_start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 9, 30, tzinfo=timezone.utc),
        expiry_month="2027-09",
        status="draft",
        road_tax=90.0,
        runner_fee=50.0,
    )
    db_session.add(tenure)
    db_session.flush()

    # Manual entry has session_id=None
    entry = TenureComparisonEntry(
        tenure_id=tenure.id,
        session_id=None,
        company_name="AmAssurance",
        sum_insured=65000.0,
        motor_premium=1350.0,
        road_tax=90.0,
        runner_fee=50.0,
        total_payable=1490.0,
        is_manual=True,
    )
    db_session.add(entry)
    db_session.commit()

    # Select manual entry as winner
    res = select_winner_and_generate_draft(
        db_session,
        tenure_id=tenure.id,
        entry_id=entry.id,
        user_id=user.id,
    )

    assert res["status"] == "success"
    assert res["is_recommended"] is True
    assert res["session_id"] is not None
    assert res["draft_id"] is not None

    # Verify session and uploaded file exist in DB
    created_sess = db_session.get(SessionModel, res["session_id"])
    assert created_sess is not None
    assert created_sess.quotation_ref is not None
    assert created_sess.quotation_ref.startswith("RL-WXY9999-")
    assert created_sess.tenure_id == tenure.id
    assert created_sess.uploaded_file is not None
    assert created_sess.uploaded_file.original_filename == "Manual Quote - AmAssurance.pdf"
    assert created_sess.draft is not None
    assert created_sess.draft.fields["sum_insured"] == 65000.0

    # Tenure state updated
    assert tenure.status == "quoted"
    assert tenure.winning_quotation_ref == created_sess.quotation_ref


def test_update_tenure_fixed_costs_persists_engine_chassis_and_customer(db_session: Session):
    """Verify editing customer IC, engine no, and chassis no persists to DB master models."""
    vehicle = TrackedVehicle(vehicle_no="ABC1122", car_model="Honda City")
    db_session.add(vehicle)
    db_session.flush()

    tenure = InsuranceTenure(
        tracked_vehicle_id=vehicle.id,
        vehicle_no="ABC1122",
        customer_name="Lee Chong Wei",
        coverage_start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 9, 30, tzinfo=timezone.utc),
        expiry_month="2027-09",
        status="draft",
        road_tax=90.0,
        runner_fee=50.0,
    )
    db_session.add(tenure)
    db_session.commit()

    # Update via service
    update_tenure_fixed_costs(
        db_session,
        tenure.id,
        road_tax=95.0,
        runner_fee=50.0,
        customer_name="Lee Chong Wei",
        ic_no="821021-08-5432",
        engine_no="ENG-HND-8899",
        chassis_no="CHS-HND-7766",
        vehicle_model="Honda City RS",
    )

    # Refresh and verify
    db_session.refresh(tenure)
    assert tenure.tracked_vehicle.engine_no == "ENG-HND-8899"
    assert tenure.tracked_vehicle.chassis_no == "CHS-HND-7766"
    assert tenure.tracked_vehicle.car_model == "Honda City RS"
    assert tenure.customer is not None
    assert tenure.customer.id_number == "821021085432"

    # Verify get_marketing_comparison returns them without any sessions
    data = get_marketing_comparison(db_session, tenure.id)
    assert data["tenure"]["engine_no"] == "ENG-HND-8899"
    assert data["tenure"]["chassis_no"] == "CHS-HND-7766"
    assert data["tenure"]["ic_no"] == "821021085432"
    assert data["tenure"]["vehicle_model"] == "Honda City RS"


def test_get_marketing_comparison_preserves_custom_road_tax(db_session: Session):
    """Verify get_marketing_comparison does not overwrite user's road tax with draft candidates."""
    user = User(id=new_id(), email="agent2@risklocker.local", name="Agent 2", password_hash="x")
    db_session.add(user)

    vehicle = TrackedVehicle(vehicle_no="TAX9999", car_model="Toyota Vios")
    db_session.add(vehicle)
    db_session.flush()

    tenure = InsuranceTenure(
        tracked_vehicle_id=vehicle.id,
        vehicle_no="TAX9999",
        customer_name="Siti Nurhaliza",
        coverage_start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 9, 30, tzinfo=timezone.utc),
        expiry_month="2027-09",
        status="draft",
        road_tax=100.0,  # Explicit custom road tax
        runner_fee=50.0,
    )
    db_session.add(tenure)
    db_session.flush()

    batch = Batch(owner_id=user.id, name="Tax Batch")
    db_session.add(batch)
    db_session.flush()

    uf = UploadedFile(
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="quote_tax.pdf",
        content_type="application/pdf",
        storage_path=".qc-tmp/quote_tax.pdf",
    )
    db_session.add(uf)
    db_session.flush()

    # Draft has higher candidate road tax 350.0
    draft = QuotationDraft(
        owner_id=user.id,
        uploaded_file_id=uf.id,
        fields={"road_tax": 350.0, "sum_insured": 50000.0, "total_payable": 1200.0},
    )
    db_session.add(draft)
    db_session.flush()

    sess = SessionModel(
        owner_id=user.id,
        uploaded_file_id=uf.id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        detected_company="Lonpac",
        is_tenure_active=True,
    )
    db_session.add(sess)
    db_session.commit()

    # Call get_marketing_comparison
    data = get_marketing_comparison(db_session, tenure.id)

    # Road tax must remain the user's 100.0, NOT overwritten to 350.0!
    assert data["tenure"]["road_tax"] == 100.0


def test_windscreen_extraction_and_auto_healing_prevents_corrupt_quotation_refs(db_session: Session):
    """Verify windscreen extraction rejects quotation ref numbers, calendar years, and heals corrupt entries."""
    from app.services.marketing_comparison_service import _is_valid_windscreen_amt, _resolve_comparison_benefits
    from app.models.tables import ExtractionRecord, ExtractionBenefitLine

    # 1. Bounds verification
    assert _is_valid_windscreen_amt(4000.0) is True
    assert _is_valid_windscreen_amt(1700.0) is True
    assert _is_valid_windscreen_amt(500.0) is True
    assert _is_valid_windscreen_amt(283233.0) is False  # Quotation number leak
    assert _is_valid_windscreen_amt(2026.0) is False    # Calendar year leak
    assert _is_valid_windscreen_amt(2024.0) is False    # Calendar year leak
    assert _is_valid_windscreen_amt(0.0) is False
    assert _is_valid_windscreen_amt(None) is False
    assert _is_valid_windscreen_amt(99999.0) is False   # Exceeds max windscreen

    # 2. Setup user and vehicle tenure
    user = User(id=new_id(), email="ws_test@example.com", name="WS Tester", password_hash="x")
    db_session.add(user)
    db_session.flush()

    vehicle = TrackedVehicle(vehicle_no="CHERY77", car_model="Chery Tiggo 7 Pro", manufacture_year=2024)
    db_session.add(vehicle)
    db_session.flush()

    start_d = datetime(2026, 3, 29, tzinfo=timezone.utc)
    end_d = datetime(2027, 3, 28, tzinfo=timezone.utc)
    tenure = InsuranceTenure(
        tracked_vehicle_id=vehicle.id,
        vehicle_no=vehicle.vehicle_no,
        customer_name="TAY HUI YIN",
        coverage_start_date=start_d,
        coverage_end_date=end_d,
        expiry_month="2027-03",
        windscreen_target=1700.0,
        road_tax=90.0,
        runner_fee=10.0,
        status="active",
    )
    db_session.add(tenure)
    db_session.flush()

    batch = Batch(owner_id=user.id, name="WS Batch")
    db_session.add(batch)
    db_session.flush()

    uf = UploadedFile(batch_id=batch.id, owner_id=user.id, original_filename="QBE_Quote.pdf", content_type="application/pdf", storage_path=".qc-tmp/qbe.pdf")
    db_session.add(uf)
    db_session.flush()

    # Draft has evidence with quotation number MPA-26-49-00283233 and year 2026
    draft = QuotationDraft(
        owner_id=user.id,
        uploaded_file_id=uf.id,
        fields={
            "sum_insured": 96000.0,
            "total_payable": 3357.0,
            "optional_covers": {
                "value": "Windscreen; Legal Liability to Passenger",
                "evidence": "Quotation No. MPA-26-49-00283233 Valid Until 22-04-2026",
            },
        },
    )
    db_session.add(draft)
    db_session.flush()

    sess = SessionModel(
        owner_id=user.id,
        uploaded_file_id=uf.id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        detected_company="QBE",
        is_tenure_active=True,
    )
    db_session.add(sess)
    db_session.flush()

    # ExtractionBenefitLine with real extracted 4000.0
    rec = ExtractionRecord(uploaded_file_id=uf.id, reading_quality="good")
    db_session.add(rec)
    db_session.flush()

    ebl = ExtractionBenefitLine(
        extraction_record_id=rec.id,
        line_id="line_ws",
        raw_label="Windscreen Damage",
        normalized_label="windscreen damage",
        extracted_value={"type": "money", "value": "4000", "currency": "MYR"},
        candidate_mappings=[{"name": "Windscreen Damage", "coverage_limit": "4,000", "concept_key": "windscreen"}],
    )
    db_session.add(ebl)
    db_session.flush()

    # Verify _resolve_comparison_benefits resolves to 4000.0, NOT 283233.0 or 2026.0
    b_res = _resolve_comparison_benefits(db_session, sess, None, draft.fields, windscreen_target=1700.0)
    assert b_res["windscreen_sum_insured"] == 4000.0

    # Simulate existing corrupt comparison entry in DB with 283233.0
    corrupt_entry = TenureComparisonEntry(
        tenure_id=tenure.id,
        session_id=sess.id,
        company_name="QBE",
        sum_insured=96000.0,
        motor_premium=3256.80,
        total_payable=3356.80,
        windscreen_sum_insured=283233.0,  # Old corrupt number
        special_perils=None,
        towing_km="Unlimited",
    )
    db_session.add(corrupt_entry)
    db_session.commit()

    # Calling get_marketing_comparison auto-heals the corrupt entry
    res = get_marketing_comparison(db_session, tenure.id)
    entry_res = next(e for e in res["entries"] if e["session_id"] == sess.id)
    assert entry_res["windscreen_sum_insured"] == 4000.0
    assert entry_res["towing_km"] == "100 km"

    # Verify persisted in database
    db_session.refresh(corrupt_entry)
    assert corrupt_entry.windscreen_sum_insured == 4000.0


def test_marketing_comparison_overhaul_features(db_session: Session):
    from datetime import date
    from app.services.marketing_comparison_service import (
        _extract_exact_basic_figure,
        calculate_exact_rate,
        format_canonical_perils,
    )

    # 1. Exact Basic Figure Detection
    etiqa_fields = {"basic_contribution": {"value": 2450.50}}
    amt, label = _extract_exact_basic_figure(etiqa_fields, "Etiqa General Takaful")
    assert label == "Basic Contribution"
    assert amt == 2450.50

    sompo_fields = {"basic_premium": {"value": 3120.00}}
    amt2, label2 = _extract_exact_basic_figure(sompo_fields, "Berjaya Sompo")
    assert label2 == "Basic Premium"
    assert amt2 == 3120.00

    # 2. Rate Formula = Basic Figure / Sum Insured (6 decimal places)
    rate_str, rate_val = calculate_exact_rate(2450.50, 96000.0)
    assert rate_str == "0.025526"
    assert round(rate_val, 6) == 0.025526

    # 3. Canonical Short Perils
    raw_text = "Includes legal liability to passengers (LLP) and towing assistance plus flood"
    perils = format_canonical_perils(raw_text)
    assert "LLP" in perils
    assert "TOWING" in perils
    assert "FLOOD" in perils

    # 4. Strictly Prior Calendar Year Policy Check
    tenure_2026, _, _, _ = _seed_tenure_with_sessions(db_session)
    tenure_2026.coverage_start_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
    tenure_2026.coverage_end_date = datetime(2027, 2, 28, tzinfo=timezone.utc)

    # Add a same-year 2026 prior tenure (e.g. from an earlier quote in Jan 2026)
    same_year_tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=tenure_2026.tracked_vehicle_id,
        customer_id=tenure_2026.customer_id,
        vehicle_no=tenure_2026.vehicle_no,
        customer_name=tenure_2026.customer_name,
        coverage_start_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 1, 14, tzinfo=timezone.utc),
        status="completed",
        expiry_month="January",
    )
    db_session.add(same_year_tenure)
    db_session.commit()

    res = get_marketing_comparison(db_session, tenure_2026.id)
    prev = res.get("previous_policy")
    assert prev is not None
    assert prev["year"] == 2025
    assert prev["year"] != 2026


def test_ev_kw_road_tax_calculation_and_ledger_update(db_session: Session):
    from app.services.road_tax_service import calculate_road_tax
    from app.extraction.entity_classifier import classify_client_entity
    from app.services.marketing_comparison_service import update_tenure_fixed_costs, rescan_comparison_tenure

    # 1. EV 9.4 kW (= 9400 Watts) calculation check
    # Motorcycle 9.4 kW -> RM 9.00
    moto_tax = calculate_road_tax("9.4 kW", vehicle_type="EVMotorcycle")
    assert moto_tax == 9.00
    moto_tax_num = calculate_road_tax(9.4, vehicle_type="EVMotorcycle")
    assert moto_tax_num == 9.00

    # Car 9.4 kW (<= 50 kW) -> RM 20.00
    car_tax = calculate_road_tax("9.4 kW", vehicle_type="EVSaloonCar")
    assert car_tax == 20.00

    # Auto-detect EV from kW token even if passed as Car
    auto_ev_tax = calculate_road_tax("9.4 kW", vehicle_type="Motorcycle")
    assert auto_ev_tax == 9.00

    # Entity classification preserves EV with kW capacity
    entity_type, resolved_vtype = classify_client_entity(
        customer_name="Ahmad Razak",
        ic_or_brn="950505-14-5555",
        ai_client_type="Individual",
        current_vehicle_type="Motorcycle",
        car_model="Blueshark R1 Lite",
        capacity_str="9.4 kW",
    )
    assert resolved_vtype == "EVMotorcycle"

    # 2. Test Customer & Vehicle Ledger persistence and windscreen target preservation
    tenure, s1, s2, user = _seed_tenure_with_sessions(db_session)
    updated = update_tenure_fixed_costs(
        db=db_session,
        tenure_id=tenure.id,
        road_tax=9.00,
        runner_fee=10.00,
        windscreen_target=2500.00,
        customer_name="DATO SRI TAN",
        ic_no="800101-14-1111",
        engine_cc="9.4 kW",
        engine_no="ENG-9988",
        chassis_no="CHAS-7766",
        vehicle_model="Blueshark Electric 9.4kW",
        manufacture_year=2024,
    )

    t_data = updated["tenure"]
    assert t_data["customer_name"] == "DATO SRI TAN"
    assert t_data["windscreen_target"] == 2500.00
    assert t_data["engine_cc"] == "9.4 kW"
    assert t_data["vehicle_model"] == "Blueshark Electric 9.4kW"
    assert t_data["road_tax"] == 9.00
    assert t_data["fixed_costs_total"] == 19.00

    # 3. Test that Rescan does NOT overwrite manual windscreen target
    rescanned = rescan_comparison_tenure(db_session, tenure.id)
    assert rescanned["tenure"]["windscreen_target"] == 2500.00
    assert rescanned["tenure"]["customer_name"] == "DATO SRI TAN"
    assert rescanned["tenure"]["vehicle_model"] == "Blueshark Electric 9.4kW"


def test_extract_source_quotation_no():
    """Verify source quotation extraction extracts true underwriter quotation references and rejects internal RL26 sequence."""
    from app.services.marketing_comparison_service import _extract_source_quotation_no

    # 1. Draft fields containing quotation_no
    assert _extract_source_quotation_no(None, {"quotation_no": "QM12351901"}) == "QM12351901"
    assert _extract_source_quotation_no(None, {"quotation_number": "FL22026M-00867209-001"}) == "FL22026M-00867209-001"
    assert _extract_source_quotation_no(None, {"quote_no": {"value": "MPA-25-49-00274660"}}) == "MPA-25-49-00274660"

    # 2. Reject internal RL26 reference numbers
    assert _extract_source_quotation_no(None, {"quotation_no": "RL260000315"}) is None
    assert _extract_source_quotation_no(None, {"quotation_no": "RL-2026-999"}) is None


def test_refresh_tenure_ledger_and_plate_undetected_chassis_tracking(db_session: Session):
    """Verify refresh_tenure_ledger recalculates EV roadtax dynamically, resolves plate undetected to N/A, and tracks by chassis."""
    from app.services.marketing_comparison_service import refresh_tenure_ledger, get_marketing_comparison
    from app.models.tables import User, UploadedFile, QuotationDraft, Session as SessionModel, InsuranceTenure, TrackedVehicle

    user = User(email="ref_test@risklocker.com", password_hash="pw", role="agent")
    db_session.add(user)
    db_session.flush()

    tv = TrackedVehicle(vehicle_no="UNREGISTERED", chassis_no="LRW3F7ET6SC548056")
    db_session.add(tv)
    db_session.flush()

    # Tenure created without plate number (unregistered / new car)
    tenure = InsuranceTenure(
        tracked_vehicle_id=tv.id,
        vehicle_no="UNREGISTERED",
        customer_name="CHENG TECK KIONG",
        coverage_start_date=datetime(2026, 6, 4, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 6, 3, tzinfo=timezone.utc),
        expiry_month="JUN",
        status="active",
        road_tax=60.00,  # Old stale value
        runner_fee=10.00,
    )
    db_session.add(tenure)
    db_session.flush()

    file_id = new_id()
    draft = QuotationDraft(
        owner_id=user.id,
        uploaded_file_id=file_id,
        fields={
            "customer_name": "CHENG TECK KIONG",
            "ic_no": "841204-01-5885",
            "car_model": "Tesla Model 3 Performance",
            "car_brand": "Tesla",
            "engine_cc": "9.4 kW",
            "chassis_number": "LRW3F7ET6SC548056",
            "engine_number": "LRW3F7ET6SC548056",
            "manufacture_year": "2025",
            "quotation_no": "FL22026M-00867209-001",
            "sum_insured": 250000.0,
            "motor_premium": 3200.0,
            "total_payable": 3230.0,
        },
    )
    db_session.add(draft)
    db_session.flush()

    sess = SessionModel(
        owner_id=user.id,
        uploaded_file_id=file_id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        detected_company="Tune Protect",
        is_tenure_active=True,
    )
    db_session.add(sess)
    db_session.commit()

    # 1. Calling refresh_tenure_ledger forces full re-calculation
    refreshed = refresh_tenure_ledger(db_session, tenure.id)
    t = refreshed["tenure"]

    # Plate undetected handled with N/A and tracked by chassis
    assert t["vehicle_no"] == "N/A"
    assert t["is_plate_undetected"] is True
    assert t["tracking_by_chassis"] is True
    assert t["chassis_no"] == "LRW3F7ET6SC548056"

    # EV road tax dynamically calculated: for 9.4 kW EV Saloon Car -> RM 20.00
    assert t["road_tax"] == 20.00
    assert t["runner_fee"] == 10.00
    assert t["fixed_costs_total"] == 30.00  # Roadtax + Runner fee = RM 30.00 (NOT 60.00)

    # Quotation ref populated with true underwriter reference
    assert len(refreshed["entries"]) == 1
    entry = refreshed["entries"][0]
    assert entry["source_quotation_no"] == "FL22026M-00867209-001"
    assert entry["quotation_ref"] == "FL22026M-00867209-001"


def test_insurer_aware_quotation_extraction_across_insurers():
    """Verify smart quotation extractor catches Berjaya Sompo, AmGen, QBE, Etiqa, Lonpac, Tune, STMB and rejects dates/stopwords."""
    from app.services.marketing_comparison_service import _extract_source_quotation_no, _is_valid_extracted_qno

    # Strict validator checks
    assert _is_valid_extracted_qno("QM12390133") is True
    assert _is_valid_extracted_qno("QC590226-001") is True
    assert _is_valid_extracted_qno("MPA-21-49-00175224") is True
    assert _is_valid_extracted_qno("FL22026M-00867209-001") is True
    assert _is_valid_extracted_qno("QJV26040103JHR") is True
    assert _is_valid_extracted_qno("1000191773") is True
    assert _is_valid_extracted_qno("QF2328664-001") is True

    # Rejection of invalid candidates
    assert _is_valid_extracted_qno("04-04-2025") is False
    assert _is_valid_extracted_qno("2026-05-07") is False
    assert _is_valid_extracted_qno("Liberty") is False
    assert _is_valid_extracted_qno("Insured") is False
    assert _is_valid_extracted_qno("TAKAFUL") is False
    assert _is_valid_extracted_qno("RL260000315") is False

    # Berjaya Sompo: number printed above 'Quotation no.'
    class DummyExtractionRecord:
        def __init__(self, text):
            self.raw_text = text
            self.ocr_text = ""

    class DummySession:
        def __init__(self, text):
            self.uploaded_file = type("DummyFile", (), {"extraction_record": DummyExtractionRecord(text)})()
            self.draft = type("Draft", (), {"fields": {}})()
            self.quotation_ref = None

    qno = _extract_source_quotation_no(DummySession("QM12390133\nQuotation no.\n07-05-2026\nIssued date\nMOTOR QUOTATION"))
    assert qno == "QM12390133"

    # AmGen: fused 'Quotation Ref No.QC590226-001'
    assert _extract_source_quotation_no(DummySession("QUOTATION\nQuotation Ref No.QC590226-001\nAmGeneral Insurance Berhad")) == "QC590226-001"


def test_save_comparison_entry_dynamic_rating_and_quotation_sync(db_session: Session):
    """Verify save_comparison_entry dynamically updates rate_factor and synchronizes quotation_ref."""
    from app.services.marketing_comparison_service import save_comparison_entry, get_marketing_comparison

    veh = TrackedVehicle(vehicle_no="ANY368", car_model="Tesla Model 3", manufacture_year=2024)
    db_session.add(veh)
    db_session.flush()

    tenure = InsuranceTenure(
        tracked_vehicle_id=veh.id,
        vehicle_no="ANY368",
        customer_name="Cheng Teck Kiong",
        coverage_start_date=datetime(2026, 6, 4, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 6, 3, tzinfo=timezone.utc),
        expiry_month="2027-06",
        status="draft",
        road_tax=20.0,
        runner_fee=10.0,
    )
    db_session.add(tenure)
    db_session.flush()

    entry = TenureComparisonEntry(
        tenure_id=tenure.id,
        company_name="Berjaya Sompo",
        sum_insured=199000.0,
        motor_premium=4483.21,
        road_tax=20.0,
        runner_fee=10.0,
        total_payable=4513.21,
        is_manual=True,
    )
    db_session.add(entry)
    db_session.commit()

    # Save with basic_figure_amount and source_quotation_no
    res = save_comparison_entry(db_session, tenure.id, {
        "id": entry.id,
        "sum_insured": 199000.0,
        "motor_premium": 4483.21,
        "basic_figure_amount": 5436.88,
        "source_quotation_no": "QM12390133",
    })

    updated_entries = res["entries"]
    assert len(updated_entries) == 1
    e = updated_entries[0]
    assert e["basic_figure_amount"] == 5436.88
    # 5436.88 / 199000 = 0.027321
    assert round(e["rate_factor"], 6) == 0.027321
    assert e["source_quotation_no"] == "QM12390133"
    assert e["quotation_ref"] == "QM12390133"


def test_covernote_separation_and_matrix_payload(db_session: Session):
    """Ensure cover note sessions are excluded from matrix columns and populated in covernote_policy."""
    tenure, sess_quote, sess_covernote, _ = _seed_tenure_with_sessions(db_session)

    # Mark second session as covernote
    sess_covernote.document_type = "covernote"
    sess_covernote.detected_company = "Etiqa Takaful"
    sess_covernote.policy_number = "POL-ETIQA-88219"
    sess_covernote.coverage_start_date = datetime(2026, 5, 1, tzinfo=timezone.utc)
    sess_covernote.coverage_end_date = datetime(2027, 4, 30, tzinfo=timezone.utc)
    sess_covernote.draft.fields = {
        **sess_covernote.draft.fields,
        "sum_insured": "85000.00",
        "company_name": "Etiqa Takaful",
    }
    sess_covernote.extracted_data = {
        "company_name": "Etiqa Takaful",
        "sum_insured": 85000.0,
        "total_payable": 2150.0,
        "coverage_start_date": "2026-05-01",
        "coverage_end_date": "2027-04-30",
        "coverage_period_formatted": "01/05/2026 - 30/04/2027",
        "canonical_perils_formatted": "Comprehensive · Windscreen · Flood",
    }
    tenure.covernote_session_id = sess_covernote.id
    tenure.policy_number = "POL-ETIQA-88219"
    tenure.stage = "Issue Policy"
    db_session.commit()

    # Query marketing comparison
    matrix = get_marketing_comparison(db_session, tenure.id)

    # Matrix entries must ONLY contain quotation sessions, NEVER covernote sessions
    matrix_session_ids = [e["session_id"] for e in matrix["entries"]]
    assert str(sess_covernote.id) not in matrix_session_ids
    assert str(sess_quote.id) in matrix_session_ids

    # Cover note policy must be properly returned in payload
    assert matrix["covernote_policy"] is not None
    assert matrix["covernote_policy"]["session_id"] == str(sess_covernote.id)
    assert matrix["covernote_policy"]["company_name"] == "Etiqa Takaful"
    assert matrix["covernote_policy"]["policy_number"] == "POL-ETIQA-88219"
    assert matrix["covernote_policy"]["sum_insured"] == 85000.0
    assert matrix["covernote_policy"]["coverage_period_formatted"] == "01/05/2026 - 30/04/2027"
    assert "Comprehensive" in matrix["covernote_policy"]["canonical_perils_formatted"]


def test_convert_session_and_unlink_covernote(db_session: Session):
    """Ensure convert_session_document_type and unlink_tenure_covernote operate cleanly."""
    from app.api.routers.comparison import (
        convert_session_document_type,
        unlink_tenure_covernote,
        ConvertDocumentTypeRequest,
    )

    tenure, sess_quote, sess_2, owner = _seed_tenure_with_sessions(db_session)

    # 1. Promote sess_quote to covernote
    res_promote = convert_session_document_type(
        tenure_id=tenure.id,
        session_id=sess_quote.id,
        payload=ConvertDocumentTypeRequest(document_type="covernote"),
        db=db_session,
        user=owner,
    )
    assert res_promote["status"] == "success"
    assert tenure.covernote_session_id == sess_quote.id
    assert sess_quote.document_type == "covernote"
    assert tenure.stage == "Issue Policy"

    # Verify marketing comparison now treats sess_quote as covernote, excluded from columns
    matrix = get_marketing_comparison(db_session, tenure.id)
    matrix_session_ids = [e["session_id"] for e in matrix["entries"]]
    assert str(sess_quote.id) not in matrix_session_ids
    assert matrix["covernote_policy"] is not None
    assert matrix["covernote_policy"]["session_id"] == str(sess_quote.id)

    # 2. Unlink covernote
    res_unlink = unlink_tenure_covernote(
        tenure_id=tenure.id,
        db=db_session,
        user=owner,
    )
    assert res_unlink["status"] == "success"
    assert tenure.covernote_session_id is None
    assert tenure.stage == "Quotations"

    # Matrix no longer has covernote_policy
    matrix_after = get_marketing_comparison(db_session, tenure.id)
    assert matrix_after["covernote_policy"] is None


def test_target_windscreen_isolation_and_preservation(db_session):
    """
    Verify that:
    1. Setting windscreen_target to 0.0 ("No windscreen") persists and is not overwritten by entries.
    2. Editing underwriter quotes with windscreen values does not mutate tenure.windscreen_target.
    3. Saving fixed costs does not tamper with individual underwriter quotes' windscreen.
    """
    from app.services.marketing_comparison_service import (
        update_tenure_fixed_costs,
        save_comparison_entry,
        get_marketing_comparison,
    )

    tenure, sess_1, sess_2, owner = _seed_tenure_with_sessions(db_session)

    # Explicitly set windscreen target to 0.0 ("No")
    update_tenure_fixed_costs(
        db_session,
        tenure.id,
        road_tax=90.0,
        runner_fee=50.0,
        windscreen_target=0.0,
    )
    assert float(tenure.windscreen_target) == 0.0

    # Fetch comparison — must NOT overwrite windscreen_target even though quotes may have windscreen
    matrix = get_marketing_comparison(db_session, tenure.id)
    assert float(tenure.windscreen_target) == 0.0
    assert matrix["tenure"]["windscreen_target"] == 0.0 or matrix["tenure"]["windscreen_target"] is None

    # Save/edit an underwriter entry with a high windscreen sum insured
    first_entry = matrix["entries"][0]
    updated_matrix = save_comparison_entry(
        db_session,
        tenure.id,
        {
            "id": first_entry["id"],
            "company_name": "Etiqa",
            "sum_insured": 50000.0,
            "motor_premium": 1200.0,
            "windscreen_sum_insured": 2000.0,
        },
    )

    # Target windscreen on tenure must still be 0.0 (untouched by company quote edit)
    assert float(tenure.windscreen_target) == 0.0

    # Verify the edited entry kept its 2000.0 windscreen
    saved_e = next(e for e in updated_matrix["entries"] if e["id"] == first_entry["id"])
    assert saved_e["windscreen_sum_insured"] == 2000.0




