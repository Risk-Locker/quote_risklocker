"""Unit tests for the Motor Quotation Extraction Referee & Fact-Checking Gate."""

import pytest
from app.extraction.referee import audit_and_reconcile_draft
from app.services.vehicle_simplifier_service import clean_vehicle_tokens_deterministic


def test_referee_detects_company_and_lorry_contradiction():
    # Scenario: An underwriter quotation for a commercial lorry owned by SDN BHD,
    # but the AI extracted 'Car' or 'Private Car Comprehensive'
    fields = {
        "customer_name": {"value": "CHIN YING TRADING SDN BHD", "status": "ready"},
        "car_brand": {"value": "DAIHATSU", "status": "ready"},
        "car_model": {"value": "Daihatsu Delta V116ha", "status": "ready"},
        "vehicle_type": {"value": "Car", "status": "ready"},  # Erroneous 'Car'
        "product_name": {"value": "Private Car Comprehensive", "status": "ready"},  # Contradiction!
        "engine_cc": {"value": "3000 KG", "status": "ready"},
        "client_type": {"value": "Private", "status": "ready"},  # Erroneous 'Private'
    }
    raw_text = (
        "QUOTATION Liberty General Insurance Berhad 197801007153 (44191-P) "
        "Insured Name Issued Date Vehicle Class Capacity Vehicle No Trailer No Named Driver "
        "CHIN YING TRADING SDN BHD 'C' PERMIT GOODS VEHICLE 3000 KG DAIHATSU DELTA V116HA"
    )

    reconciled, notices = audit_and_reconcile_draft(fields, raw_text=raw_text)

    # 1. Company entity enforcement
    assert reconciled["client_type"]["value"] == "Company"

    # 2. Lorry / Commercial vehicle enforcement
    assert reconciled["vehicle_type"]["value"] == "Lorry"

    # 3. Product name contradiction purge
    assert "Private Car" not in reconciled["product_name"]["value"]
    assert "Commercial Vehicle" in reconciled["product_name"]["value"] or "Goods Vehicle" in reconciled["product_name"]["value"]

    # 4. Audit notices generated
    assert any("Referee Fact-Check" in n for n in notices)


def test_referee_preserves_legitimate_private_car():
    # Legitimate private individual driving a Honda Civic
    fields = {
        "customer_name": {"value": "TAN AH KOW", "status": "ready"},
        "ic_or_brn": {"value": "900101-01-5555", "status": "ready"},
        "car_brand": {"value": "HONDA", "status": "ready"},
        "car_model": {"value": "Civic 1.5 TC-P", "status": "ready"},
        "vehicle_type": {"value": "Car", "status": "ready"},
        "product_name": {"value": "Private Car Comprehensive", "status": "ready"},
        "engine_cc": {"value": "1498 CC", "status": "ready"},
    }
    raw_text = "Quotation for TAN AH KOW Honda Civic 1.5 TC-P Private Car Comprehensive"

    reconciled, notices = audit_and_reconcile_draft(fields, raw_text=raw_text)

    assert reconciled["client_type"]["value"] == "Private"
    assert reconciled["vehicle_type"]["value"] == "Car"
    assert reconciled["product_name"]["value"] == "Private Car Comprehensive"
    assert len(notices) == 0


def test_vehicle_name_simplifier_preserves_alphanumeric_codes():
    # Daihatsu Delta V116HA should NOT be lowercased to V116ha
    brand, model, combined = clean_vehicle_tokens_deterministic("DAIHATSU", "DAIHATSU DELTA V116HA")
    assert "V116-HA" in combined or "V116HA" in combined
    assert "V116ha" not in combined

    # Proton Saga BLM should retain BLM uppercase
    brand2, model2, combined2 = clean_vehicle_tokens_deterministic("PROTON", "PROTON SAGA BLM 1.3")
    assert "BLM" in combined2
    assert "Blm" not in combined2


def test_referee_sanitizes_third_party_sum_insured():
    fields = {
        "coverage_type": {"value": "Third Party", "status": "ready"},
        "sum_insured": {"value": "7,906,208.00", "status": "ready"},
        "gross_premium": {"value": "334.55", "status": "ready"},
    }
    reconciled, notices = audit_and_reconcile_draft(fields)
    assert reconciled["sum_insured"]["value"] == "0.00"
    assert any("Third Party policy cannot have Own Damage sum insured" in n for n in notices)


def test_referee_sanitizes_chassis_number_contamination():
    fields = {
        "coverage_type": {"value": "Comprehensive", "status": "ready"},
        "sum_insured": {"value": "7,906,208.00", "status": "ready"},
        "chassis_no": {"value": "EJ7906208", "status": "ready"},
        "gross_premium": {"value": "334.55", "status": "ready"},
    }
    reconciled, notices = audit_and_reconcile_draft(fields)
    assert reconciled["sum_insured"]["value"] == "0.00"
    assert any("contaminated by vehicle chassis/engine digits" in n for n in notices)


def test_vision_null_plate_and_make_clears_regex_label_hallucinations(monkeypatch, tmp_path):
    """When Gemini Vision returns null for blank plate/make, raw regex labels must never backfill or pollute car_model."""
    from app.extraction.candidate_finder import find_candidates
    from app.extraction.draft_mapper import build_draft, normalize_vehicle_model_text, reconcile_vehicle_capacity_and_fees
    from app.extraction.types import ExtractionBundle
    from app.extraction.orchestrator import ExtractionOrchestrator

    raw_text = (
        "QUOTATION\n"
        "Vehicle Registration No.\n"
        "Vehicle Make\n"
        "Vehicle Model\n"
        "EEKR 7X AWD PERFORMANCE\n"
        "Chassis Number\n"
        "LRWYHCEK6TC667999\n"
        "Sum Insured: RM 200,000.00\n"
        "Total Payable: RM 5,500.00\n"
    )
    # 1. Candidate finder alone must reject label hallucinations & invalid plates
    cands = find_candidates(raw_text, [{"page": 1, "text": raw_text}], words=[])
    assert all(c.value != "VehicleMake" for c in cands.get("vehicle_no", []))
    assert all(c.value.upper() not in {"VEHICLE MODEL", "VEHICLE MAKE", "CHASSIS NUMBER"} for c in cands.get("car_brand", []))

    # 2. normalize_vehicle_model_text strips accidental label prefixes & skips blocked brands
    assert normalize_vehicle_model_text("Vehicle Model EEKR 7X AWD PERFORMANCE", "Vehicle Model") == "EEKR 7X AWD PERFORMANCE"
    assert normalize_vehicle_model_text("EEKR 7X AWD PERFORMANCE", None) == "EEKR 7X AWD PERFORMANCE"

    # 3. Full orchestrator flow with mocked native extraction + Vision returning null for vehicle_no & car_brand
    dummy_pdf = tmp_path / "zeekr_unregistered.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%fake\n")

    monkeypatch.setattr(
        "app.extraction.orchestrator.extract_native",
        lambda _p: ExtractionBundle(
            raw_text=raw_text,
            page_text=[{"page": 1, "text": raw_text, "source_method": "native"}],
            words=[],
            blocks=[],
            tables=[],
            images=[],
            method_summary=["native_pdf"],
            warnings=[],
        ),
    )

    def _fake_vision(**kwargs):
        return (
            {
                "vehicle_no": None,
                "car_brand": None,
                "car_model": "EEKR 7X AWD PERFORMANCE",
                "chassis_no": "LRWYHCEK6TC667999",
                "customer_name": "ACME EV SDN BHD",
                "sum_insured": "200000.00",
                "total_amount": "5500.00",
            },
            None,
        )

    monkeypatch.setattr("app.extraction.canonical_draft_builder.run_orchestrator_vision_step", _fake_vision)

    out = ExtractionOrchestrator().extract_file(dummy_pdf, source_filename="zeekr_unregistered.pdf")
    fields = out["draft"]["fields"]
    reconcile_vehicle_capacity_and_fees(fields, candidates=None, raw_text=raw_text)

    assert fields["car_model"]["value"] == "EEKR 7X AWD PERFORMANCE"
    assert fields["car_brand"]["value"] in ("", None)
    assert fields["vehicle_no"]["value"] != "VehicleMake"
    assert fields["chassis_no"]["value"] == "LRWYHCEK6TC667999"
    # Verify build_draft standalone also never emits blocked brand/model
    draft_fields, _w, _q = build_draft(cands, raw_text=raw_text)
    assert draft_fields["vehicle_no"]["value"] != "VehicleMake"


def test_blank_engine_no_and_not_stated_plate_never_grab_adjacent_labels(monkeypatch, tmp_path):
    """Blank Engine/Motor No followed by Chassis No and NOT STATED plate must never leak label tokens."""
    from app.extraction.candidate_finder import find_candidates
    from app.extraction.orchestrator import ExtractionOrchestrator
    from app.extraction.types import ExtractionBundle

    raw_text = (
        "QUOTATION\n"
        "Vehicle No: NOT STATED\n"
        "Engine/Motor No:\n"
        "Chassis No: LRWYHCEK6TC667999\n"
        "Car Model: EEKR 7X AWD PERFORMANCE\n"
        "Total Payable: RM 5,200.00\n"
    )
    cands = find_candidates(raw_text, [{"page": 1, "text": raw_text}], words=[])
    assert cands.get("engine_no", []) == []
    assert all(c.value.upper() != "NOTSTATED" for c in cands.get("vehicle_no", []))
    assert any(c.value == "LRWYHCEK6TC667999" for c in cands.get("chassis_no", []))

    dummy_pdf = tmp_path / "zeekr_blank_engine.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%fake\n")

    monkeypatch.setattr(
        "app.extraction.orchestrator.extract_native",
        lambda _p: ExtractionBundle(
            raw_text=raw_text,
            page_text=[{"page": 1, "text": raw_text, "source_method": "native"}],
            words=[],
            blocks=[],
            tables=[],
            images=[],
            method_summary=["native_pdf"],
            warnings=[],
        ),
    )
    monkeypatch.setattr(
        "app.extraction.canonical_draft_builder.run_orchestrator_vision_step",
        lambda **_kw: (
            {
                "vehicle_no": None,
                "engine_no": None,
                "chassis_no": "LRWYHCEK6TC667999",
                "car_brand": "ZEEKR",
                "car_model": "EEKR 7X AWD PERFORMANCE",
                "customer_name": "ACME EV SDN BHD",
                "total_amount": "5200.00",
            },
            None,
        ),
    )

    out = ExtractionOrchestrator().extract_file(dummy_pdf, source_filename="zeekr_blank_engine.pdf")
    fields = out["draft"]["fields"]
    assert fields.get("engine_no", {}).get("value", "") in ("", None)
    assert fields.get("vehicle_no", {}).get("value", "") in ("", None)
    assert fields["chassis_no"]["value"] == "LRWYHCEK6TC667999"


def test_rescan_apply_gemini_result_clears_stale_hallucinations_and_uses_chassis_fallback():
    """Re-detect (apply_gemini_result) clears stale VehicleMake/Vehicle Model/Chassis No labels and syncs TrackedVehicle & Tenure."""
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models.tables import (
        Base,
        Batch,
        CustomerAccount,
        ExtractionRecord,
        InsuranceTenure,
        QuotationDraft,
        Session as SessionModel,
        TrackedVehicle,
        UploadedFile,
        User,
        new_id,
    )
    from app.services.session_rescan_service import apply_gemini_result

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        user = User(id=new_id(), email="staff@risklocker.test", name="Staff", password_hash="x", role="staff")
        cust = CustomerAccount(id=new_id(), id_number="900101015555", canonical_name="XIAO XIAO")
        batch = Batch(id=new_id(), owner_id=user.id, name="Test Batch")
        tv = TrackedVehicle(
            id=new_id(),
            vehicle_no="VEHICLEMAKE",
            chassis_no="LRWYHCEK6TC667999",
            car_brand="Vehicle Model",
            car_model="Vehicle Model EEKR 7X AWD PERFORMANCE",
            engine_no="Chassis No",
            customer_id=cust.id,
        )
        tenure = InsuranceTenure(
            id=new_id(),
            tracked_vehicle_id=tv.id,
            customer_id=cust.id,
            vehicle_no="VEHICLEMAKE",
            customer_name="XIAO XIAO",
            coverage_start_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
            coverage_end_date=datetime(2027, 1, 31, tzinfo=timezone.utc),
            expiry_month="2027-01",
            stage="Quotations",
        )
        uf = UploadedFile(
            id=new_id(),
            batch_id=batch.id,
            owner_id=user.id,
            original_filename="zeekr.pdf",
            content_type="application/pdf",
            storage_path="local/zeekr.pdf",
            storage_sha256="a" * 64,
            size_bytes=1024,
            status="ready",
        )
        draft = QuotationDraft(
            id=new_id(),
            uploaded_file_id=uf.id,
            owner_id=user.id,
            status="ready",
            fields={
                "vehicle_no": {"value": "VehicleMake", "status": "ready"},
                "car_brand": {"value": "Vehicle Model", "status": "ready"},
                "car_model": {"value": "Vehicle Model EEKR 7X AWD PERFORMANCE", "status": "ready"},
                "engine_no": {"value": "Chassis No", "status": "ready"},
                "chassis_no": {"value": "LRWYHCEK6TC667999", "status": "ready"},
            },
            warnings=[],
        )
        ext = ExtractionRecord(
            id=new_id(),
            uploaded_file_id=uf.id,
            method_summary=[],
            raw_text="Total Payable: RM 5,500.00",
            ocr_text="",
            page_text=[],
            words=[],
            blocks=[],
            tables=[],
            images=[],
            regions=[],
            candidates={},
            warnings=[],
            reading_quality="good",
        )
        sess = SessionModel(
            id=new_id(),
            owner_id=user.id,
            uploaded_file_id=uf.id,
            draft_id=draft.id,
            tracked_vehicle_id=tv.id,
            customer_id=cust.id,
            tenure_id=tenure.id,
            status="active",
            quotation_ref="RL26TEST001",
        )
        db.add_all([user, cust, batch, tv, tenure, uf, draft, ext, sess])
        db.commit()

        apply_gemini_result(
            db=db,
            settings=SimpleNamespace(),
            draft=draft,
            session=sess,
            uploaded=uf,
            extraction=ext,
            gemini_res={
                "vehicle_no": None,
                "car_brand": None,
                "car_model": "EEKR 7X AWD PERFORMANCE",
                "engine_no": None,
                "chassis_no": "LRWYHCEK6TC667999",
                "customer_name": "XIAO XIAO",
                "total_amount": "5500.00",
            },
            quotation_ref="RL26TEST001",
            db_companies=[],
            db_benefit_concepts=[],
            raw_text="Total Payable: RM 5,500.00",
        )
        db.commit()
        db.expire_all()

        reloaded_draft = db.get(QuotationDraft, draft.id)
        reloaded_tv = db.get(TrackedVehicle, tv.id)
        reloaded_tenure = db.get(InsuranceTenure, tenure.id)
        assert reloaded_draft is not None
        assert reloaded_tv is not None
        assert reloaded_tenure is not None

        assert reloaded_draft.fields["vehicle_no"]["value"] == "LRWYHCEK6TC667999"
        assert reloaded_draft.fields["car_brand"]["value"] == ""
        assert reloaded_draft.fields["engine_no"]["value"] == ""
        assert reloaded_draft.fields["car_model"]["value"] == "EEKR 7X AWD PERFORMANCE"
        assert reloaded_tv.vehicle_no == "LRWYHCEK6TC667999"
        assert reloaded_tv.car_brand is None
        assert reloaded_tv.engine_no is None
        assert reloaded_tv.car_model == "EEKR 7X AWD PERFORMANCE"
        assert reloaded_tenure.vehicle_no == "LRWYHCEK6TC667999"



