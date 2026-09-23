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
    get_dataset_analytics_facts,
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


def test_dataset_analytics_facts_and_analytical_qa(db_session: Session, mock_user):
    user = User(
        id=mock_user.id,
        email="analyst@risklocker.local",
        password_hash="fakehash",
        role="admin",
        status="active",
    )
    batch = Batch(id=new_id(), owner_id=user.id, name="Analytics Batch", status="active")
    db_session.add_all([user, batch])
    db_session.commit()

    # Create distinct quotation drafts with varying CCs, makes, models, insurers, and benefits
    quotes_data = [
        {
            "comp": "AmAssurance",
            "cc": "998 CC",
            "brand": "PERODUA",
            "model": "PERODUA AXIA 1.0 G",
            "addons": "Windscreen coverage RM 500, Special Perils Flood",
        },
        {
            "comp": "AmAssurance",
            "cc": "1332 CC",
            "brand": "PROTON",
            "model": "PROTON SAGA 1.3 STANDARD",
            "addons": "Windscreen coverage RM 600, Legal Liability to Passengers",
        },
        {
            "comp": "QBE",
            "cc": "1496 CC",
            "brand": "TOYOTA",
            "model": "TOYOTA VIOS 1.5 G",
            "addons": "Windscreen coverage RM 1,000, CART 14 Days, Special Perils",
        },
        {
            "comp": "QBE",
            "cc": "2488 CC",
            "brand": "MAZDA",
            "model": "MAZDA CX-5 2.5 GLS HIGH",
            "addons": "Windscreen coverage RM 2,000, Key Replacement",
        },
    ]

    for qd in quotes_data:
        uf = UploadedFile(
            id=new_id(), batch_id=batch.id, owner_id=user.id,
            original_filename=f"quote_{qd['brand']}.pdf", content_type="application/pdf",
            storage_path=f"/{qd['brand']}.pdf", storage_sha256=new_id(), status="uploaded",
        )
        db_session.add(uf)
        draft = QuotationDraft(
            id=new_id(), uploaded_file_id=uf.id, owner_id=user.id, status="active",
            fields={
                "engine_cc": {"value": qd["cc"]},
                "car_brand": {"value": qd["brand"]},
                "car_model": {"value": qd["model"]},
                "optional_covers": {"value": qd["addons"]},
            },
        )
        db_session.add(draft)
        sess = SessionModel(
            id=new_id(), owner_id=user.id, uploaded_file_id=uf.id,
            draft_id=draft.id, status="active", detected_company=qd["comp"],
        )
        db_session.add(sess)

    db_session.commit()

    # 1. Test dataset analytics facts
    facts = get_dataset_analytics_facts(db_session)
    assert facts["total_quotations_analyzed"] == 4
    # Insurers
    top_insurers = facts["insurer_ranking"]
    assert len(top_insurers) == 2
    assert top_insurers[0]["quotations_count"] == 2
    # CC Brackets
    bracket_names = [b["bracket"] for b in facts["cc_brackets"]]
    assert any("<= 1,000" in b for b in bracket_names)
    assert any("1,001 – 1,500" in b for b in bracket_names)
    assert any("> 2,000" in b for b in bracket_names)
    # Benefits
    benefit_names = [b["benefit"] for b in facts["top_benefits_used"]]
    assert "Windscreen & Window Glass" in benefit_names
    assert "Inclusion of Special Perils (Flood & Storm)" in benefit_names

    # 2. Test Q&A on CCs
    cc_response = chat_with_copilot(db_session, user, message="what is the list of ccs of types of cars you found?")
    assert ("<= 1,000" in cc_response["reply"] or "998" in cc_response["reply"])
    assert ("1,001" in cc_response["reply"] or "1496" in cc_response["reply"])

    # 3. Test Q&A on Insurer Share
    comp_response = chat_with_copilot(db_session, user, message="which companies were more?")
    assert "AmAssurance" in comp_response["reply"]
    assert "QBE" in comp_response["reply"]

    # 4. Test Q&A on vehicle types / models
    models_response = chat_with_copilot(db_session, user, message="what type of cars mostly found?")
    assert any(brand in models_response["reply"].upper() for brand in ["PERODUA", "PROTON", "TOYOTA", "MAZDA", "AXIA", "SAGA", "VIOS", "CX-5"])

    # 5. Test Q&A on benefits
    benefits_response = chat_with_copilot(db_session, user, message="what benefits mostly used?")
    assert "Windscreen" in benefits_response["reply"]


def test_copilot_cancellation_abort_intent(db_session: Session, mock_user: User):
    """Ensure saying 'dont do anything' or 'cancel' immediately acknowledges cancellation without proposing mutations."""
    res1 = chat_with_copilot(db_session, mock_user, message="dont do anything")
    assert res1["facts_summary"].get("cancelled") is True
    assert "cancelled" in res1["reply"].lower() or "no changes" in res1["reply"].lower()
    assert len(res1["actions"]) == 0

    res2 = chat_with_copilot(db_session, mock_user, message="cancel request")
    assert res2["facts_summary"].get("cancelled") is True
    assert len(res2["actions"]) == 0


def test_copilot_profiles_and_image_switching_queries(db_session: Session, mock_user: User):
    """Ensure Copilot provides grounded answers for profile counts and image switching in global benefits."""
    # Test profile count query
    prof_res = chat_with_copilot(db_session, mock_user, message="how many profiles are there for the builder/benefits")
    assert "catalog profiles" in prof_res["reply"].lower()
    assert "visual" in prof_res["reply"].lower()

    # Test image switching query
    img_res = chat_with_copilot(db_session, mock_user, message="can you change images or switch images in global benefits")
    assert "yes" in img_res["reply"].lower()
    assert "global benefits" in img_res["reply"].lower()


def test_copilot_multi_turn_company_context_carryover(db_session: Session, mock_user: User):
    """Ensure conversation history carries forward the active company context across turns."""
    company = InsuranceCompany(
        id=new_id(),
        name="QBE Insurance (Malaysia) Berhad",
        slug="qbe",
        status="active",
    )
    db_session.add(company)
    db_session.commit()

    # Turn 1: User specifies company
    turn1_msg = "For QBE, how many catalogs are there?"
    turn1_res = chat_with_copilot(db_session, mock_user, message=turn1_msg)
    assert "QBE" in turn1_res["reply"]

    # Turn 2: User refers to company indirectly ("its conditions") without company name
    history = [
        {"role": "user", "content": turn1_msg},
        {"role": "assistant", "content": turn1_res["reply"]},
    ]
    turn2_res = chat_with_copilot(db_session, mock_user, message="what about its conditions?", history=history)
    # Target company should still be QBE
    assert "QBE" in turn2_res["reply"]


def test_copilot_multi_turn_proposal_refinement(db_session: Session, mock_user: User):
    """Ensure follow-up refinements (e.g. 'no not that part, just this one') filter previous operations."""
    company = InsuranceCompany(
        id=new_id(),
        name="QBE Insurance (Malaysia) Berhad",
        slug="qbe",
        status="active",
    )
    profile = BenefitProfile(
        id=new_id(),
        name="Master Unified Profile",
        version_number=1,
        is_active=True,
        status="active",
    )
    db_session.add_all([company, profile])

    catalog = BenefitCatalog(
        id=new_id(),
        company_id=company.id,
        name="Private Car Comprehensive",
        status="active",
    )
    db_session.add(catalog)

    rev = BenefitCatalogRevision(
        id=new_id(),
        catalog_id=catalog.id,
        revision_number=1,
        state="published",
        content_hash="qbehash",
    )
    db_session.add(rev)

    towing_c = BenefitConcept(
        id=new_id(),
        concept_key="towing",
        label="Emergency Towing Assistance",
        description="24/7 Breakdown Towing",
        status="active",
    )
    windscreen_c = BenefitConcept(
        id=new_id(),
        concept_key="windscreen",
        label="Windscreen & Window Glass",
        description="Windscreen protection",
        status="active",
    )
    db_session.add_all([towing_c, windscreen_c])

    offering1 = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev.id,
        offering_key="towing",
        concept_id=towing_c.id,
        offering_kind="benefit",
        role="included",
        description_override="Towing 100km",
        status="active",
    )
    db_session.add(offering1)
    db_session.commit()

    # Turn 1: Propose changing towing and adding windscreen
    turn1_msg = "For QBE, change towing limit to 300km and add windscreen 1000"
    turn1_res = chat_with_copilot(db_session, mock_user, message=turn1_msg)
    assert len(turn1_res["actions"]) > 0
    preview1 = turn1_res["actions"][0]["preview"]
    assert len(preview1["operations_preview"]) >= 2

    # Turn 2: User says "no not that part, just this one"
    history = [
        {"role": "user", "content": turn1_msg},
        {
            "role": "assistant",
            "content": turn1_res["reply"] + "\n\n[Active Proposed Changes for QBE: [Item 1] update_plan_item: Emergency Towing Assistance -> 300 km; [Item 2] add_offering: Windscreen & Window Glass -> RM 1,000]",
        },
    ]
    turn2_res = chat_with_copilot(db_session, mock_user, message="no not that part, just this one", history=history)
    assert len(turn2_res["actions"]) > 0
    preview2 = turn2_res["actions"][0]["preview"]
    # Should only keep the single confirmed item
    assert len(preview2["operations_preview"]) == 1
    assert preview2["operations_preview"][0]["concept_key"] == "towing"


def test_session_hygiene_facts_excludes_soft_deleted_files(db_session: Session, mock_user):
    """Ensure sessions whose uploaded files are soft-deleted are never treated as active."""
    user = User(id=mock_user.id, email="hygiene@risklocker.local", password_hash="fake", role="admin", status="active")
    batch = Batch(id=new_id(), owner_id=user.id, name="Hygiene Batch", status="active")
    db_session.add_all([user, batch])
    db_session.commit()

    f_active = UploadedFile(
        id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="act.pdf",
        content_type="application/pdf", storage_path="/act.pdf", storage_sha256="acthash", status="uploaded",
    )
    f_deleted = UploadedFile(
        id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="del.pdf",
        content_type="application/pdf", storage_path="/del.pdf", storage_sha256="delhash", status="deleted",
        deleted_at=utcnow(),
    )
    db_session.add_all([f_active, f_deleted])

    d1 = QuotationDraft(id=new_id(), uploaded_file_id=f_active.id, owner_id=user.id, status="active", fields={"vehicle_no": {"value": "AAA111"}})
    d2 = QuotationDraft(id=new_id(), uploaded_file_id=f_deleted.id, owner_id=user.id, status="active", fields={"vehicle_no": {"value": "BBB222"}})
    db_session.add_all([d1, d2])

    s1 = SessionModel(id=new_id(), owner_id=user.id, uploaded_file_id=f_active.id, draft_id=d1.id, status="active")
    s2 = SessionModel(id=new_id(), owner_id=user.id, uploaded_file_id=f_deleted.id, draft_id=d2.id, status="active")
    db_session.add_all([s1, s2])
    db_session.commit()

    facts = get_session_hygiene_facts(db_session, user)
    # Only s1 should be included; s2 has deleted uploaded file
    assert facts["total_active_sessions"] == 1
    assert facts["unique_car_plates_count"] == 1


def test_session_cleanup_resilient_when_uploaded_file_already_deleted(db_session: Session, mock_user, dummy_settings):
    """Ensure execute_session_cleanup cleanly marks session as trash even if uploaded file was already deleted."""
    user = User(id=mock_user.id, email="resilient@risklocker.local", password_hash="fake", role="admin", status="active")
    batch = Batch(id=new_id(), owner_id=user.id, name="Resilient Batch", status="active")
    db_session.add_all([user, batch])
    db_session.commit()

    f_already_deleted = UploadedFile(
        id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="already_del.pdf",
        content_type="application/pdf", storage_path="/already_del.pdf", storage_sha256="delhash2", status="deleted",
        deleted_at=utcnow(),
    )
    db_session.add(f_already_deleted)
    draft = QuotationDraft(id=new_id(), uploaded_file_id=f_already_deleted.id, owner_id=user.id, status="active", fields={"vehicle_no": {"value": "CCC333"}})
    db_session.add(draft)
    s = SessionModel(id=new_id(), owner_id=user.id, uploaded_file_id=f_already_deleted.id, draft_id=draft.id, status="active")
    db_session.add(s)
    db_session.commit()

    clean_res = execute_session_cleanup(db_session, dummy_settings, user, [s.id])
    assert clean_res["cleaned_count"] == 1
    assert s.id in clean_res["trashed_session_ids"]

    db_session.refresh(s)
    assert s.status == "trash"


def test_copilot_context_payload_datetime_json_serialization(db_session: Session, mock_user, monkeypatch):
    """Verify Gemini API payload serializes Python datetimes without throwing TypeError."""
    import json
    from unittest.mock import MagicMock
    import httpx

    user = User(id=mock_user.id, email="gemini_ser@risklocker.local", password_hash="fake", role="admin", status="active")
    batch = Batch(id=new_id(), owner_id=user.id, name="Gemini Batch", status="active")
    db_session.add_all([user, batch])
    db_session.commit()

    f1 = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="g1.pdf", content_type="application/pdf", storage_path="/g1.pdf", storage_sha256="hash_gemini", status="uploaded")
    f2 = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=user.id, original_filename="g2.pdf", content_type="application/pdf", storage_path="/g2.pdf", storage_sha256="hash_gemini", status="uploaded")
    db_session.add_all([f1, f2])

    d1 = QuotationDraft(id=new_id(), uploaded_file_id=f1.id, owner_id=user.id, status="active", fields={"vehicle_no": {"value": "GEM111"}})
    d2 = QuotationDraft(id=new_id(), uploaded_file_id=f2.id, owner_id=user.id, status="active", fields={"vehicle_no": {"value": "GEM111"}})
    db_session.add_all([d1, d2])

    s1 = SessionModel(id=new_id(), owner_id=user.id, uploaded_file_id=f1.id, draft_id=d1.id, status="active", last_edited_at=utcnow())
    s2 = SessionModel(id=new_id(), owner_id=user.id, uploaded_file_id=f2.id, draft_id=d2.id, status="active", last_edited_at=utcnow())
    db_session.add_all([s1, s2])
    db_session.commit()

    # Mock pool and httpx to capture the JSON payload passed
    captured_payload = {}

    def mock_post(self, url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": "Found 1 duplicate set for vehicle GEM111."}]}}
            ]
        }
        return mock_resp

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    # Calling chat_with_copilot with mock API key
    from app.extraction.gemini_extractor import get_key_pool
    pool = get_key_pool()
    pool._keys = ["fake-api-key"]
    pool._index = 0

    res = chat_with_copilot(db_session, user, message="check if there are duplicate sessions")
    assert "Found 1 duplicate set" in res["reply"]
    # Ensure ground truth context was serialized without issue
    assert captured_payload is not None
    assert "contents" in captured_payload




