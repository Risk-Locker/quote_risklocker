import pytest
from pathlib import Path
from app.extraction.orchestrator import ExtractionOrchestrator

# Ensure tests have access to the mock PDF paths
COMPANY_BASED_DIR = Path(__file__).parent.parent.parent / "company_based"

@pytest.mark.skipif(not COMPANY_BASED_DIR.exists(), reason="company_based dir not found")
def test_qbe_multimodal_extraction():
    """
    E2E extraction test that verifies Gemini 1.5 Flash multimodal alignment
    for detached layout pricing in QBE documents.
    """
    qbe_pdf = COMPANY_BASED_DIR / "QBE" / "20260311_JUM2709_Quotation_QBE_extras.pdf"
    if not qbe_pdf.exists():
        pytest.skip(f"Test file {qbe_pdf} not found")

    orchestrator = ExtractionOrchestrator()
    result = orchestrator.extract_file(
        file_path=qbe_pdf,
        enhanced_reading=False,
        db_aliases={},
        db_brands=[],
        db_models=[],
        db_companies=[],
        db_benefit_concepts=[],
        db_packs=[],
        db_corrections=[]
    )
    
    draft = result.get("draft", {})
    fields = draft.get("fields", {})
    
    # Verify core NCD / premium safeguards
    assert fields.get("premium", {}).get("value") == "1130.97", "Total premium mismatch"
    assert fields.get("ncd_amount", {}).get("value") == "345.49", "NCD amount mismatch or contains negative sign"
    assert fields.get("ncd_percent", {}).get("value") == "25.00", "NCD percent mismatch or contains % sign"
    
    # Verify client records extensions
    client_type = fields.get("client_type", {}).get("value")
    # For private clients, we expect "Private"
    assert client_type in ["Private", "Company", None], "Invalid client type"

    # Verify visual multimodal benefit extraction 
    benefits = result.get("full_record", {}).get("benefit_lines", [])
    assert len(benefits) > 0, "No benefits detected, multimodal alignment failed"


def test_liberty_kurnia_amassurance_disambiguation_and_spatial_footer():
    """Verify shared boilerplate never misroutes Liberty / Kurnia / AmAssurance."""
    from app.extraction.brand_logo_scanner import (
        extract_liberty_group_spatial_brand,
        extract_page1_primary_brand_signals,
    )
    from app.extraction.company_resolution import resolve_company

    companies = [
        {
            "company_id": "c-lib",
            "name": "Liberty",
            "aliases": ["Liberty", "Liberty Insurance", "www.libertyinsurance.com.my", "www.libertyinsurance.com"],
        },
        {
            "company_id": "c-kur",
            "name": "Kurnia",
            "aliases": ["Kurnia", "www.kurnia.com", "Kurnia Insurans"],
        },
        {
            "company_id": "c-am",
            "name": "AmAssurance",
            "aliases": ["AmAssurance", "AmGen", "www.amassurance.com.my"],
        },
    ]

    shared_boilerplate = (
        "Liberty General Insurance Berhad 197801007153 (44191-P)\n"
        "auto365 Comprehensive Premier\n"
        "Head Office: Liberty Insurance Tower, CT9, Pavilion Damansara\n"
        "To enjoy this hassle-free\nconvenience,download\nKurnia One Touch Mobile App\n"
    )

    # 1. AmAssurance text with Liberty Insurance Tower + Kurnia One Touch promo
    am_text = shared_boilerplate + "Website: www.amassurance.com.my\n"
    assert extract_page1_primary_brand_signals(am_text)["winning_brand"] == "AmAssurance"
    assert resolve_company(am_text, companies)["display_name"] == "AmAssurance"

    # 2. Liberty text with www.libertyinsurance.com (no .my) AND line-wrapped .com.my
    lib_text_com = shared_boilerplate + "Website: www.libertyinsurance.com\n"
    assert extract_page1_primary_brand_signals(lib_text_com)["winning_brand"] == "Liberty"
    assert resolve_company(lib_text_com, companies)["display_name"] == "Liberty"

    lib_text_wrapped = shared_boilerplate + "Website: www.libertyinsurance.\ncom.my\n"
    assert extract_page1_primary_brand_signals(lib_text_wrapped)["winning_brand"] == "Liberty"
    assert resolve_company(lib_text_wrapped, companies)["display_name"] == "Liberty"

    # 3. Kurnia text with 'by Liberty Insurance' and 'Liberty Insurance Tower'
    kur_text = shared_boilerplate + "by Liberty Insurance\nWebsite: www.kurnia.com\n"
    assert extract_page1_primary_brand_signals(kur_text)["winning_brand"] == "Kurnia"
    assert resolve_company(kur_text, companies)["display_name"] == "Kurnia"

    # 4. In-memory PDF spatial bottom-right Website check
    import fitz

    for domain, expected in [
        ("www.amassurance.com.my", "AmAssurance"),
        ("www.libertyinsurance.com", "Liberty"),
        ("www.kurnia.com", "Kurnia"),
    ]:
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((40, 40), "Liberty General Insurance Berhad\nauto365 Comprehensive Premier")
        page.insert_text((40, 740), "Head Office: Liberty Insurance Tower, CT9, Pavilion Damansara")
        page.insert_text((40, 770), "To enjoy this hassle-free convenience, download Kurnia One Touch Mobile App")
        page.insert_text((390, 760), f"Website\n{domain}")
        pdf_bytes = doc.tobytes()
        doc.close()
        res = extract_liberty_group_spatial_brand(pdf_bytes, db_companies=companies)
        assert res is not None
        assert res["canonical_company"] == expected
        assert res["confidence"] >= 0.99


def test_zero_fake_coverage_gate_for_optional_covers_and_detected_sync():
    """Verify cost never leaks into coverage_limit and all 5 items sync into extraction.benefit_lines."""
    from types import SimpleNamespace
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.domain.benefits import is_auto_coverage_allowed_for_benefit
    from app.models.tables import Base, Batch, ExtractionBenefitLine, ExtractionRecord, QuotationDraft, Session as QuotationSession, UploadedFile, new_id
    from app.services.session_rescan_service import apply_gemini_result

    # Unit check on the strict 3-benefit rule
    assert is_auto_coverage_allowed_for_benefit("windscreen", "Windscreen Damage", "15,000.00", "2,250.00") is True
    assert is_auto_coverage_allowed_for_benefit("windscreen", "Windscreen Damage", "2,250.00", "2,250.00") is False
    assert is_auto_coverage_allowed_for_benefit("towing", "Unlimited Towing", "365 km", "0") is True
    assert is_auto_coverage_allowed_for_benefit("betterment-protection", "Waiver of Betterment", "Up to 15 Years", "0") is True
    assert is_auto_coverage_allowed_for_benefit("betterment-protection", "Waiver of Betterment", "RM 100.00", "100.00") is False
    assert is_auto_coverage_allowed_for_benefit("legal-liability-of-passengers", "Legal Liability Of Passengers", "RM 7.50", "7.50") is False
    assert is_auto_coverage_allowed_for_benefit("legal-liability-of-passengers", "Legal Liability Of Passengers", "RM 7.50", "") is False
    assert is_auto_coverage_allowed_for_benefit("private-car-365", "Private Car 365 Plan 2", "RM 130.00", "130.00") is False
    assert is_auto_coverage_allowed_for_benefit("special-perils", "Inclusion Of Special Perils", "RM 1,071.80", "1071.80") is False

    # Integration check on apply_gemini_result (Deep Re-detect path)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    u_id, b_id, uf_id, d_id, s_id, er_id = new_id(), new_id(), new_id(), new_id(), new_id(), new_id()
    with Session(engine) as db:
        batch = Batch(id=b_id, owner_id=u_id, name="Test Batch", status="ready")
        uploaded = UploadedFile(
            id=uf_id,
            batch_id=b_id,
            owner_id=u_id,
            original_filename="amassurance_test.pdf",
            content_type="application/pdf",
            storage_path="local/amassurance_test.pdf",
            storage_provider="local",
            storage_status="available",
            storage_sha256="abc",
            size_bytes=1234,
            status="ready",
        )
        draft = QuotationDraft(
            id=d_id,
            revision=1,
            uploaded_file_id=uf_id,
            owner_id=u_id,
            status="ready",
            fields={},
            scalar_decisions={},
            warnings=[],
        )
        sess = QuotationSession(
            id=s_id,
            owner_id=u_id,
            uploaded_file_id=uf_id,
            draft_id=d_id,
            quotation_ref="TEST-RL2600001",
            status="active",
            is_test=True,
        )
        rec = ExtractionRecord(
            id=er_id,
            uploaded_file_id=uf_id,
            method_summary=["native"],
            raw_text="OPTIONAL COVER LIST",
            ocr_text="",
            page_text=[],
            words=[],
            blocks=[],
            tables=[],
            images=[],
            regions=[],
            candidates={},
            benefit_lines=[{"line_id": "stale_1", "raw_label": "Old Stale Line"}],
            company_resolution={},
            warnings=[],
            reading_quality="ready",
        )
        db.add_all([batch, uploaded, draft, sess, rec])
        db.flush()

        gemini_res = {
            "insurance_company": "AmAssurance",
            "total_amount": "5441.30",
            "total_optional_cover_amount": "3501.15",
            "detected_benefits": [
                {"label": "Private Car 365 Plan 2", "value": "RM 130.00", "premium_cost": "130.00", "coverage_limit": "", "plan_tier": "Plan 2", "is_optional_cover": True},
                {"label": "Inclusion Of Special Perils / Convulsions Of Nature", "value": "RM 1,071.80", "premium_cost": "1071.80", "coverage_limit": "", "is_optional_cover": True},
                {"label": "Legal Liability Of Passengers", "value": "RM 7.50", "premium_cost": "7.50", "coverage_limit": "", "is_optional_cover": True},
                {"label": "Legal Liability To Passengers", "value": "RM 41.85", "premium_cost": "41.85", "coverage_limit": "", "is_optional_cover": True},
                {"label": "Windscreen Damage (Tempered/Laminated Glass Inclusive Labour Cost) RM 15,000.00", "value": "RM 15,000.00", "premium_cost": "2250.00", "coverage_limit": "15,000.00", "is_optional_cover": True},
            ],
        }
        apply_gemini_result(
            db=db,
            settings=SimpleNamespace(),
            draft=draft,
            session=sess,
            uploaded=uploaded,
            extraction=rec,
            gemini_res=gemini_res,
            quotation_ref="TEST-RL2600001",
            db_companies=[],
            db_benefit_concepts=[],
            raw_text="OPTIONAL COVER LIST",
        )
        db.flush()

        # All 5 detected benefits must sync to extraction.benefit_lines JSON AND SQL rows
        assert len(rec.benefit_lines) == 5
        sql_lines = list(db.scalars(select(ExtractionBenefitLine).where(ExtractionBenefitLine.extraction_record_id == er_id)).all())
        assert len(sql_lines) == 5

        by_label = {item["raw_label"]: item for item in rec.benefit_lines}
        assert by_label["Private Car 365 Plan 2"]["coverage_limit"] == ""
        assert by_label["Private Car 365 Plan 2"]["premium_cost"] == "130.00"
        assert by_label["Private Car 365 Plan 2"]["plan_tier"] == "Plan 2"
        assert by_label["Legal Liability Of Passengers"]["coverage_limit"] == ""
        assert by_label["Legal Liability Of Passengers"]["premium_cost"] == "7.50"
        assert by_label["Inclusion Of Special Perils / Convulsions Of Nature"]["coverage_limit"] == ""
        assert by_label["Windscreen Damage (Tempered/Laminated Glass Inclusive Labour Cost) RM 15,000.00"]["coverage_limit"] == "15,000.00"
        assert by_label["Windscreen Damage (Tempered/Laminated Glass Inclusive Labour Cost) RM 15,000.00"]["premium_cost"] == "2250.00"


def test_phase1_model_lock_8slot_pool_and_accounting_proof_gate():
    """Verify strict 2-model Flash-Lite lock, 8-slot pool exclusion, closed-loop Decimal gate, and no-subtraction parity."""
    from decimal import Decimal
    from types import SimpleNamespace
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.config import get_settings
    from app.extraction.accounting_proof_gate import verify_quotation_accounting
    from app.extraction.canonical_draft_builder import apply_verified_motor_pricing
    from app.extraction.model_discovery_service import ALLOWED_PRODUCTION_MODELS, evaluate_model_eligibility
    from app.models.enums import AccountStatus, RecordStatus
    from app.models.tables import (
        Base,
        Batch,
        ExtractionRecord,
        QuotationDraft,
        Session as QuotationSession,
        UploadedFile,
        User,
        new_id,
    )
    from app.services.gemini_account_service import GeminiAccountManager
    from app.services.session_rescan_service import apply_gemini_result

    # 1. Strict 2-model lock + 8-slot pool default & exclusion
    assert ALLOWED_PRODUCTION_MODELS == frozenset({"gemini-3.1-flash-lite", "gemini-3.5-flash-lite"})
    ok_31, _, _ = evaluate_model_eligibility({"name": "models/gemini-3.1-flash-lite", "supportedGenerationMethods": ["generateContent"]})
    ok_35, _, _ = evaluate_model_eligibility({"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]})
    assert ok_31 is True and ok_35 is True
    for bad_id in ("gemini-3.8-flash", "-".join(["gemini", "2.0", "flash"]), "-".join(["gemini", "1.5", "pro"])):
        bad_ok, _, _ = evaluate_model_eligibility({"name": f"models/{bad_id}", "supportedGenerationMethods": ["generateContent"]})
        assert bad_ok is False, f"{bad_id} must be rejected"

    mgr = GeminiAccountManager(tuple(f"AIzaSyTestKey0000000000000000000000{i}" for i in range(8)))
    assert mgr._max_accounts == 8
    assert len(mgr.get_accounts()) == 8
    slot1 = mgr.acquire_parallel_slot(requested_model="gemini-3.1-flash-lite")
    assert slot1 is not None
    _, _, slot1_id = slot1
    slot2 = mgr.acquire_parallel_slot(requested_model="gemini-3.5-flash-lite", exclude_slot_ids={slot1_id})
    assert slot2 is not None and slot2[2] != slot1_id

    # 2. Closed-loop Decimal accounting proof gate (AmAssurance 8,942.45 + RM 400 Clause 2(f) trap rejection)
    am_payload = {
        "insurance_company": "AmAssurance",
        "coverage_type": "Comprehensive",
        "sum_insured": "250000.00",
        "basic_premium": "9999.00",
        "ncd_amount": "2499.75",
        "gross_premium": "8428.05",
        "service_tax": "504.40",
        "stamp_duty": "10.00",
        "total_amount": "8942.45",
        "total_optional_cover_amount": "928.80",
        "detected_benefits": [
            {"label": "Special Perils", "value": "Included", "premium_cost": "741.80", "is_optional_cover": True},
            {"label": "Legal Liability to Passengers", "value": "Included", "premium_cost": "49.50", "is_optional_cover": True},
            {"label": "Legal Liability of Passengers", "value": "Included", "premium_cost": "7.50", "is_optional_cover": True},
            {"label": "Private Car 365 Plan 2", "value": "Plan 2", "premium_cost": "130.00", "is_optional_cover": True},
        ],
    }
    verdict = verify_quotation_accounting(am_payload)
    assert verdict.passed is True
    assert verdict.quarantine_reason is None
    assert verdict.authoritative_motor_premium == Decimal("8942.45")

    trap_payload = {
        "insurance_company": "Zurich",
        "coverage_type": "Comprehensive",
        "basic_premium": "1500.00",
        "ncd_amount": "0.00",
        "gross_premium": "1500.00",
        "service_tax": "120.00",
        "stamp_duty": "10.00",
        "total_amount": "400.00",
        "detected_benefits": [],
    }
    trap_verdict = verify_quotation_accounting(trap_payload)
    assert trap_verdict.passed is False
    assert trap_verdict.quarantine_reason is not None

    # 3. Upload & Re-Detect canonical pricing parity (zero extras_cost subtraction!)
    fields_direct: dict = {}
    apply_verified_motor_pricing(fields_direct, am_payload, accounting_verdict=verdict)
    assert fields_direct["premium"]["value"] == "8942.45"
    assert fields_direct["motor_premium"]["value"] == "8942.45"
    assert fields_direct["total_payable"]["value"] == "8942.45"

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as db:
        u_id, b_id, uf_id, d_id, s_id, er_id = new_id(), new_id(), new_id(), new_id(), new_id(), new_id()
        db.add(User(id=u_id, email="proof@rl.test", password_hash="x", status=AccountStatus.ACTIVE.value))
        db.add(Batch(id=b_id, owner_id=u_id, name="Proof", status=RecordStatus.READY.value))
        uf = UploadedFile(
            id=uf_id, batch_id=b_id, owner_id=u_id, original_filename="vqe8.pdf",
            content_type="application/pdf", storage_path="/tmp/vqe8.pdf",
            storage_provider="local_ephemeral", size_bytes=1234, status=RecordStatus.READY.value, is_test=True,
        )
        draft = QuotationDraft(
            id=d_id, revision=1, uploaded_file_id=uf_id, owner_id=u_id,
            status=RecordStatus.READY.value, fields={}, scalar_decisions={}, display_options={}, warnings=[],
        )
        sess = QuotationSession(
            id=s_id, owner_id=u_id, uploaded_file_id=uf_id, draft_id=d_id,
            quotation_ref="TEST-PROOF", status="active", is_test=True,
        )
        rec = ExtractionRecord(
            id=er_id, uploaded_file_id=uf_id, method_summary=["gemini_vision"], raw_text="AmAssurance",
            ocr_text="", page_text=[], words=[], blocks=[], tables=[], images=[], regions=[],
            candidates={}, benefit_lines=[], company_resolution={}, warnings=[], reading_quality="ready",
        )
        db.add_all([uf, draft, sess, rec])
        db.flush()
        apply_gemini_result(
            db=db,
            settings=SimpleNamespace(),
            draft=draft,
            session=sess,
            uploaded=uf,
            extraction=rec,
            gemini_res=am_payload,
            quotation_ref="TEST-PROOF",
            db_companies=[],
            db_benefit_concepts=[],
            raw_text="AmAssurance",
        )
        db.flush()
        assert draft.fields["premium"]["value"] == "8942.45"
        assert draft.fields["motor_premium"]["value"] == "8942.45"
        assert draft.fields["total_payable"]["value"] == "8942.45"


