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
    assert "STMB Insurance" in teaser
    assert "TOTAL PAYABLE" in teaser
    assert "Road Tax & Runner Fee: RM 120.00" in teaser


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
    assert healed["excess"] == 400.0
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



