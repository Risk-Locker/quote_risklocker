"""Unit tests for Milestone 3: 534-Alias Grounding, Multi-Line Stitcher & Zero-Hallucination Benefit Engine."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.extraction.benefit_lines import _stitch_lines, extract_benefit_lines, is_spurious_benefit_line
from app.extraction.gemini_extractor import build_rag_system_prompt
from app.models.tables import (
    Base,
    Batch,
    BenefitAlias,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    DraftBenefitSelection,
    DraftSourceLineDecision,
    ExtractionBenefitLine,
    ExtractionRecord,
    InsuranceCompany,
    InsuranceProduct,
    QuotationDraft,
    UploadedFile,
    User,
    new_id,
)
from app.services.catalog_review_service import auto_apply_extracted_benefits


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_rag_prompt_includes_benefit_aliases_and_endorsement_mappings():
    prompt = build_rag_system_prompt(
        db_companies=[{"name": "QBE", "aliases": ["QBE Insurance"]}],
        db_benefit_concepts=[
            {
                "concept_key": "all-drivers",
                "label": "All Drivers Excess Waiver",
                "aliases": [
                    {"phrase": "All Rider / Semua Penunggang"},
                    {"phrase": "Any Authorised Driver"},
                ],
                "match_dataset": ["Authorised Driver(s)"],
            }
        ],
    )
    assert "All Rider / Semua Penunggang" in prompt
    assert "Any Authorised Driver" in prompt
    assert "Endorsement 89 / 89A / 97" in prompt
    assert "Endorsement 113 / 030" in prompt


def test_multiline_windscreen_stitcher_and_spurious_filter():
    raw_lines = [
        "Optional Covers Selected",
        "Windscreen Damage (Tempered/Laminated Glass Inclusive Labour",
        "Cost) RM 1,500.00 : RM 225.00",
        "AKSES RM 0.00",
        "SUM COVERED",
        "JUMLAH KECIL 3,298.44",
        "Proposer Declaration",
    ]
    stitched = _stitch_lines(raw_lines)
    assert any("Windscreen Damage (Tempered/Laminated Glass Inclusive Labour Cost) RM 1,500.00" in s for s in stitched)

    assert is_spurious_benefit_line("AKSES RM 0.00") is True
    assert is_spurious_benefit_line("SUM COVERED") is True
    assert is_spurious_benefit_line("JUMLAH KECIL 3,298.44") is True
    assert is_spurious_benefit_line("Proposer Declaration") is True

    lines = extract_benefit_lines(
        [{"page": 1, "text": "\n".join(raw_lines)}],
        concepts=[{"concept_id": "c-ws", "concept_key": "windscreen", "label": "Windscreen Coverage", "aliases": [{"phrase": "Windscreen Damage"}]}],
    )
    assert len(lines) == 1
    assert lines[0]["coverage_limit"] == "1500.00"
    assert lines[0]["premium_cost"] == "225.00"


def test_auto_apply_uses_benefit_aliases_and_never_hallucinates_price_as_limit(db_session: Session):
    user = User(id=new_id(), email="u@rl.local", password_hash="h", name="U", role="staff")
    comp = InsuranceCompany(id=new_id(), name="Lonpac", status="active")
    prod = InsuranceProduct(id=new_id(), company_id=comp.id, product_key="private-car-secure", name="Private Car Secure", status="active")
    cat = BenefitCatalog(id=new_id(), company_id=comp.id, product_id=prod.id, name="Lonpac Car Catalog", status="active")
    rev = BenefitCatalogRevision(
        id=new_id(),
        catalog_id=cat.id,
        revision_number=1,
        state="published",
        content_hash="hash1",
    )
    c_all_drv = BenefitConcept(id=new_id(), concept_key="all-drivers", label="All Drivers Excess Waiver", status="active")
    c_bet = BenefitConcept(id=new_id(), concept_key="betterment-protection", label="Betterment Waiver", status="active")
    db_session.add_all([user, comp, prod, cat, rev, c_all_drv, c_bet])
    db_session.flush()

    alias_rider = BenefitAlias(
        id=new_id(),
        benefit_id=c_all_drv.id,
        phrase="Semua Penunggang Diberi Kuasa",
        normalized_phrase="semua penunggang diberi kuasa",
        scope="global",
        status="active",
    )
    off_drv = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev.id,
        concept_id=c_all_drv.id,
        offering_key="all-drivers-opt",
        offering_kind="optional",
        role="addon_option",
        status="active",
        typed_value={"type": "boolean", "value": True},
    )
    off_bet = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev.id,
        concept_id=c_bet.id,
        offering_key="betterment-opt",
        offering_kind="optional",
        role="addon_option",
        status="active",
        typed_value={"type": "custom", "value": "Up to 10 Years", "display_text": "Up to 10 Years"},
    )
    db_session.add_all([alias_rider, off_drv, off_bet])
    db_session.flush()

    batch = Batch(id=new_id(), owner_id=user.id, name="B")
    uf = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="q.pdf", content_type="application/pdf", storage_path="/q.pdf")
    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=uf.id,
        owner_id=user.id,
        company_id=comp.id,
        product_id=prod.id,
        catalog_revision_id=rev.id,
        fields={},
    )
    rec = ExtractionRecord(id=new_id(), uploaded_file_id=uf.id)
    db_session.add_all([batch, uf, draft, rec])
    db_session.flush()

    # Line 1: Matched via BenefitAlias, has RM 20.00 fee -> must NOT set typed_value_override to RM 20.00!
    l1 = ExtractionBenefitLine(
        id=new_id(),
        extraction_record_id=rec.id,
        line_id="l1",
        raw_label="Semua Penunggang Diberi Kuasa : RM 20.00",
        normalized_label="semua penunggang diberi kuasa",
        inclusion_state="selected",
        extracted_value={"type": "money", "value": "0.00", "currency": "MYR", "semantic_role": "amount", "premium": {"amount": "20.00", "currency": "MYR"}},
        evidence={"premium_cost": "20.00"},
    )
    # Line 2: Matched via real quotation phrase map ("MAKE VEHICLE (AGED 6-10) : RM 50.00")
    l2 = ExtractionBenefitLine(
        id=new_id(),
        extraction_record_id=rec.id,
        line_id="l2",
        raw_label="MAKE VEHICLE (AGED 6-10) : RM 50.00",
        normalized_label="make vehicle aged 6 10",
        inclusion_state="selected",
        extracted_value={"type": "money", "value": "50.00", "currency": "MYR", "semantic_role": "premium"},
        evidence={"premium_cost": "50.00"},
    )
    db_session.add_all([l1, l2])
    db_session.flush()
    db_session.add_all([
        DraftSourceLineDecision(id=new_id(), draft_id=draft.id, source_line_id=l1.id, disposition="unresolved"),
        DraftSourceLineDecision(id=new_id(), draft_id=draft.id, source_line_id=l2.id, disposition="unresolved"),
    ])
    db_session.commit()

    res = auto_apply_extracted_benefits(db_session, draft)
    db_session.flush()
    assert res["applied"] == 2

    sels = list(db_session.scalars(select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft.id)).all())
    assert len(sels) == 2
    by_concept = {s.concept_id: s for s in sels}

    drv_sel = by_concept[c_all_drv.id]
    assert drv_sel.cost_status == "paid"
    assert drv_sel.price["amount"] == 20.0
    # Crucial: typed_value_override must be None (NOT hallucinated as RM 20.00 or RM 0.00!)
    assert drv_sel.typed_value_override is None

    bet_sel = by_concept[c_bet.id]
    assert bet_sel.cost_status == "paid"
    assert bet_sel.price["amount"] == 50.0
    assert bet_sel.typed_value_override is None
