"""Hermetic regression tests for batched comparison benefit prefetching."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models.tables import (
    Base,
    Batch,
    BenefitConcept,
    DraftBenefitSelection,
    ExtractionBenefitLine,
    ExtractionRecord,
    InsuranceCompany,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.marketing_comparison.benefits_extractor import (
    _resolve_comparison_benefits,
    prefetch_comparison_benefit_context,
)
from app.services.marketing_comparison_service import get_marketing_comparison


def _sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine, SessionLocal()


def test_prefetched_comparison_benefits_match_direct_query_without_extra_sql():
    engine, db = _sqlite_session()
    try:
        user = User(id=new_id(), email="staff@risklocker.test", name="Staff", role="staff", password_hash="x")
        comp = InsuranceCompany(id=new_id(), name="Berjaya Sompo", slug="berjaya-sompo")
        batch = Batch(id=new_id(), owner_id=user.id, name="Test Batch", status="ready")
        uf = UploadedFile(
            id=new_id(),
            batch_id=batch.id,
            owner_id=user.id,
            original_filename="quote.pdf",
            content_type="application/pdf",
            storage_path="test/quote.pdf",
            storage_provider="supabase",
            storage_status="available",
            size_bytes=1234,
            status="ready",
            insurance_company_id=comp.id,
        )
        concept = BenefitConcept(
            id=new_id(),
            concept_key="windscreen",
            label="Windscreen Protection",
            value_schema={"type": "currency"},
        )
        draft = QuotationDraft(
            id=new_id(),
            uploaded_file_id=uf.id,
            owner_id=user.id,
            company_id=comp.id,
            status="ready",
            fields={
                "vehicle_no": {"value": "VPY3366"},
                "sum_insured": {"value": "120000"},
                "total_amount": {"value": "1850.50"},
            },
        )
        sel = DraftBenefitSelection(
            id=new_id(),
            draft_id=draft.id,
            selection_key="windscreen",
            concept_id=concept.id,
            item_kind="addon",
            state="current",
            cost_status="paid",
            label_override="Windscreen RM 2,000",
            typed_value_override={"coverage_limit": 2000},
        )
        ext_rec = ExtractionRecord(
            id=new_id(),
            uploaded_file_id=uf.id,
            raw_text="Berjaya Sompo Private Car Quotation Special Perils Flood Endorsement 57 LLP",
            ocr_text="",
        )
        ext_line = ExtractionBenefitLine(
            id=new_id(),
            extraction_record_id=ext_rec.id,
            line_id="line_ws_1",
            raw_label="Windscreen Cover",
            normalized_label="Windscreen",
            candidate_mappings=[{"coverage_limit": "2000"}],
        )
        tv = TrackedVehicle(id=new_id(), vehicle_no="VPY3366")
        tenure = InsuranceTenure(
            id=new_id(),
            tracked_vehicle_id=tv.id,
            vehicle_no="VPY3366",
            customer_name="TAN TEST",
            coverage_start_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
            coverage_end_date=datetime(2027, 5, 31, tzinfo=timezone.utc),
            expiry_month="2027-05",
            road_tax=Decimal("90.00"),
            runner_fee=Decimal("20.00"),
        )
        session = SessionModel(
            id=new_id(),
            owner_id=user.id,
            uploaded_file_id=uf.id,
            draft_id=draft.id,
            tracked_vehicle_id=tv.id,
            tenure_id=tenure.id,
            detected_company="Berjaya Sompo",
            document_type="quotation",
            quotation_status="ready",
        )
        db.add_all([user, comp, batch, uf, concept, draft, sel, ext_rec, ext_line, tv, tenure, session])
        db.commit()

        direct = _resolve_comparison_benefits(db, session, comp.id, draft.fields, 2000.0)
        prefetch = prefetch_comparison_benefit_context(db, [session], [comp.id])

        query_count = 0

        @event.listens_for(engine, "before_cursor_execute")
        def _count_queries(*_args, **_kwargs):
            nonlocal query_count
            query_count += 1

        cached = _resolve_comparison_benefits(db, session, comp.id, draft.fields, 2000.0, prefetched=prefetch)
        event.remove(engine, "before_cursor_execute", _count_queries)

        assert query_count == 0
        assert cached == direct
        assert cached["windscreen_sum_insured"] == 2000.0
        assert cached["special_perils"] == "Included"
        assert cached["llp_llop"] == "Included"

        result = get_marketing_comparison(db, tenure.id)
        assert len(result["entries"]) == 1
        assert result["entries"][0]["windscreen_sum_insured"] == 2000.0
    finally:
        db.close()
        engine.dispose()
