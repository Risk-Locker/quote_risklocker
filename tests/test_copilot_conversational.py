"""Hermetic tests for Conversational AI Copilot, status checks, and session deduplication."""

from __future__ import annotations

from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.tables import (
    Base,
    Batch,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitProfile,
    CatalogOffering,
    CompanyBenefitCondition,
    InsuranceCompany,
    QuotationDraft,
    Session as SessionModel,
    UploadedFile,
    User,
    new_id,
    utcnow,
)
from app.services.copilot_chat_service import (
    chat_with_copilot,
    execute_session_cleanup,
    get_catalog_status_facts,
    get_session_hygiene_facts,
)


@pytest.fixture
def db_session():
    """Hermetic SQLite in-memory database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_user():
    return SimpleNamespace(
        id=new_id(),
        email="admin@risklocker.local",
        name="Business Admin",
        role="admin",
    )


@pytest.fixture
def dummy_settings():
    return SimpleNamespace(
        trash_retention_days=30,
        gemini_api_keys=["test-key"],
    )


def test_catalog_status_facts_and_towing_situation(db_session: Session):
    # Setup company with active and dummy profiles
    company = InsuranceCompany(
        id=new_id(),
        name="AmAssurance",
        slug="amassurance",
        status="active",
    )
    db_session.add(company)

    active_profile = BenefitProfile(
        id=new_id(),
        name="Auto365 Active",
        version_number=3,
        is_active=True,
        status="active",
    )
    dummy_profile = BenefitProfile(
        id=new_id(),
        name="Old Dummy Draft",
        version_number=1,
        is_active=False,
        status="draft",
    )
    db_session.add_all([active_profile, dummy_profile])

    catalog1 = BenefitCatalog(
        id=new_id(),
        company_id=company.id,
        name="Private Car Comprehensive",
        status="active",
    )
    catalog2 = BenefitCatalog(
        id=new_id(),
        company_id=company.id,
        name="Private Car EV Comprehensive",
        status="active",
    )
    db_session.add_all([catalog1, catalog2])

    rev1 = BenefitCatalogRevision(
        id=new_id(),
        catalog_id=catalog1.id,
        revision_number=1,
        state="published",
        content_hash="hash1",
    )
    rev2 = BenefitCatalogRevision(
        id=new_id(),
        catalog_id=catalog2.id,
        revision_number=1,
        state="published",
        content_hash="hash2",
    )
    db_session.add_all([rev1, rev2])

    towing_concept = BenefitConcept(
        id=new_id(),
        concept_key="towing",
        label="Towing Assistance",
        description="24/7 Breakdown Towing",
        status="active",
    )
    db_session.add(towing_concept)

    offering1 = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev1.id,
        offering_key="towing",
        concept_id=towing_concept.id,
        offering_kind="benefit",
        role="included",
        description_override="Standard Towing Description",
        status="active",
    )
    offering2 = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev2.id,
        offering_key="towing",
        concept_id=towing_concept.id,
        offering_kind="benefit",
        role="included",
        description_override="Standard Towing Description",
        status="active",
    )
    db_session.add_all([offering1, offering2])
    db_session.commit()

    # Query status facts
    facts = get_catalog_status_facts(db_session, company_id=company.id)

    assert facts["scope"] == "company"
    assert facts["total_catalogs"] == 2
    assert facts["same_towing_description_across_all"] is True
    assert facts["conditions_count"] == 0
    assert len(facts["dummy_profiles"]) == 1
    assert facts["dummy_profiles"][0]["name"] == "Old Dummy Draft"


def test_session_hygiene_exact_duplicates_vs_unique_edits(db_session: Session, mock_user):
    # Setup test user and batch
    user = User(
        id=mock_user.id,
        email="test@risklocker.local",
        password_hash="fakehash",
        role="admin",
        status="active",
    )
    batch = Batch(
        id=new_id(),
        owner_id=user.id,
        name="Batch 1",
        status="active",
    )
    db_session.add_all([user, batch])
    db_session.commit()

    # 1. Exact Duplicate Pair (Same SHA256, uploaded twice)
    sha_dup = "abcdef1234567890abcdef1234567890"
    file1 = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="quote_JRW1813_1.pdf",
        content_type="application/pdf",
        storage_path="/files/1.pdf",
        storage_sha256=sha_dup,
        status="uploaded",
    )
    file2 = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="quote_JRW1813_1_copy.pdf",
        content_type="application/pdf",
        storage_path="/files/2.pdf",
        storage_sha256=sha_dup,
        status="uploaded",
    )
    db_session.add_all([file1, file2])

    draft1 = QuotationDraft(
        id=new_id(),
        uploaded_file_id=file1.id,
        owner_id=user.id,
        status="active",
        fields={"vehicle_no": {"value": "JRW1813"}, "roadtax": {"value": "830.40"}, "gross_premium": {"value": "2060.12"}},
    )
    draft2 = QuotationDraft(
        id=new_id(),
        uploaded_file_id=file2.id,
        owner_id=user.id,
        status="active",
        fields={"vehicle_no": {"value": "JRW1813"}, "roadtax": {"value": "830.40"}, "gross_premium": {"value": "2060.12"}},
    )
    db_session.add_all([draft1, draft2])

    sess1 = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=file1.id,
        draft_id=draft1.id,
        status="active",
        detected_company="AmAssurance",
    )
    sess2 = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=file2.id,
        draft_id=draft2.id,
        status="active",
        detected_company="AmAssurance",
    )
    db_session.add_all([sess1, sess2])

    # 2. Unique Edited Quote (Same car plate ACL9613, but different Roadtax 0 vs 90)
    file3 = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="quote_ACL9613_v1.pdf",
        content_type="application/pdf",
        storage_path="/files/3.pdf",
        storage_sha256="sha_unique_1",
        status="uploaded",
    )
    file4 = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="quote_ACL9613_v2.pdf",
        content_type="application/pdf",
        storage_path="/files/4.pdf",
        storage_sha256="sha_unique_2",
        status="uploaded",
    )
    db_session.add_all([file3, file4])

    draft3 = QuotationDraft(
        id=new_id(),
        uploaded_file_id=file3.id,
        owner_id=user.id,
        status="active",
        fields={"vehicle_no": {"value": "ACL9613"}, "roadtax": {"value": "0.00"}, "gross_premium": {"value": "348.99"}},
    )
    draft4 = QuotationDraft(
        id=new_id(),
        uploaded_file_id=file4.id,
        owner_id=user.id,
        status="active",
        fields={"vehicle_no": {"value": "ACL9613"}, "roadtax": {"value": "90.00"}, "gross_premium": {"value": "348.99"}},
    )
    db_session.add_all([draft3, draft4])

    sess3 = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=file3.id,
        draft_id=draft3.id,
        status="active",
        detected_company="QBE",
    )
    sess4 = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=file4.id,
        draft_id=draft4.id,
        status="active",
        detected_company="QBE",
    )
    db_session.add_all([sess3, sess4])
    db_session.commit()

    # Query Session Hygiene facts
    facts = get_session_hygiene_facts(db_session, user)

    assert facts["total_active_sessions"] == 4
    assert facts["unique_car_plates_count"] == 2
    # Exactly 1 duplicate set (sess1 & sess2)
    assert facts["exact_duplicate_sets_count"] == 1
    assert facts["redundant_sessions_count"] == 1
    # ACL9613 must be recognized as unique variations
    assert facts["unique_quote_variations_count"] == 1
    assert facts["sample_unique_quote_variations"][0]["car_plate"] == "ACL9613"


def test_chat_with_copilot_and_duplicate_cleanup(db_session: Session, mock_user, dummy_settings):
    # Setup single session with duplicate
    user = User(
        id=mock_user.id,
        email="test2@risklocker.local",
        password_hash="fakehash",
        role="admin",
        status="active",
    )
    batch = Batch(id=new_id(), owner_id=user.id, name="B2", status="active")
    db_session.add_all([user, batch])
    db_session.commit()

    f1 = UploadedFile(
        id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="a.pdf",
        content_type="application/pdf", storage_path="/a.pdf", storage_sha256="samehash", status="uploaded",
    )
    f2 = UploadedFile(
        id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="a_dup.pdf",
        content_type="application/pdf", storage_path="/b.pdf", storage_sha256="samehash", status="uploaded",
    )
    db_session.add_all([f1, f2])

    d1 = QuotationDraft(id=new_id(), uploaded_file_id=f1.id, owner_id=user.id, status="active", fields={"vehicle_no": {"value": "WXY111"}})
    d2 = QuotationDraft(id=new_id(), uploaded_file_id=f2.id, owner_id=user.id, status="active", fields={"vehicle_no": {"value": "WXY111"}})
    db_session.add_all([d1, d2])

    s1 = SessionModel(id=new_id(), owner_id=user.id, uploaded_file_id=f1.id, draft_id=d1.id, status="active")
    s2 = SessionModel(id=new_id(), owner_id=user.id, uploaded_file_id=f2.id, draft_id=d2.id, status="active")
    db_session.add_all([s1, s2])
    db_session.commit()

    # Chat asking to check duplicates
    response = chat_with_copilot(db_session, user, message="check if there are duplicate sessions")

    assert "Session & Quotation Health Analysis" in response["reply"] or "duplicate" in response["reply"].lower()
    assert len(response["actions"]) >= 1
    session_action = next(a for a in response["actions"] if a["type"] == "session_cleanup")
    assert session_action["redundant_count"] == 1

    # Execute cleanup
    clean_res = execute_session_cleanup(db_session, dummy_settings, user, [s2.id])
    assert clean_res["cleaned_count"] == 1
    assert s2.id in clean_res["trashed_session_ids"]

    # Verify session is marked trash
    db_session.refresh(s2)
    assert s2.status == "trash"
