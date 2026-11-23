"""Hermetic Red-First TDD suite for Milestone 2:
- Authoritative 7-insurer towing matrix & comparison evaluator
- DB-driven CatalogOffering.display_value & CompanyBenefitCondition.replacement_value precedence
- Workspace manual Box 1 edit preservation (zero immovable 'RM 200.00' stone)
- Coverage/vehicle gating (no complimentary towing on Third Party, TPFT, or Commercial Lorry)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.domain.motor.towing_matrix import resolve_towing_entitlement
from app.models.tables import (
    Base,
    Batch,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    CompanyBenefitCondition,
    CompanyBenefitProfile,
    DraftBenefitSelection,
    InsuranceCompany,
    QuotationDraft,
    UploadedFile,
    User,
    new_id,
)
from app.rendering.render_context import resolve_benefit_cards
from app.rendering.unified_addon_engine import extract_free_coverage_items
from app.services.marketing_comparison.towing_evaluator import resolve_insurer_towing_limit


@pytest.fixture()
def m2_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def test_seven_insurer_towing_matrix_and_evaluator_authoritative():
    """Verify exact CEO 7-insurer towing limits across domain matrix & comparison evaluator."""
    # 1. QBE: RM 500 standard; Unlimited - Plan 1 with DPP (N4 Unlimited Auto Assistance)
    assert resolve_towing_entitlement("QBE").formatted == "RM 500"
    assert (
        resolve_towing_entitlement(
            "QBE",
            package_or_rider="Driver & Passenger Protector N4 Unlimited Auto Assistance Plan 1",
        ).formatted
        == "Unlimited - Plan 1"
    )
    assert resolve_insurer_towing_limit("QBE", "Private Car Protector Comprehensive") == "RM 500"
    assert resolve_insurer_towing_limit("QBE", "Driver & Passenger Protector N4 Unlimited Auto Assistance Plan 1") == "Unlimited - Plan 1"

    # 2. STMB / Takaful Malaysia: 50 km standard; Motor PA Plan 1/2/3/4 -> 100/200/300/Unlimited
    assert resolve_towing_entitlement("Takaful Malaysia").formatted == "50 km"
    assert resolve_towing_entitlement("Takaful Malaysia", package_or_rider="Motor PA Plan 1").formatted == "100 km"
    assert resolve_towing_entitlement("Takaful Malaysia", package_or_rider="Motor PA Plan 2").formatted == "200 km"
    assert resolve_towing_entitlement("Takaful Malaysia", package_or_rider="Motor PA Plan 3").formatted == "300 km"
    assert resolve_towing_entitlement("Takaful Malaysia", package_or_rider="Motor PA Plan 4").formatted == "Unlimited"
    assert resolve_insurer_towing_limit("Takaful Malaysia", "Takaful myMotor Private Car") == "50 km"
    assert resolve_insurer_towing_limit("Takaful Malaysia", "Motor PA Plus Plan 1") == "100 km"
    assert resolve_insurer_towing_limit("Takaful Malaysia", "Motor PA Plus Plan 2") == "200 km"
    assert resolve_insurer_towing_limit("Takaful Malaysia", "Motor PA Plus Plan 3") == "300 km"
    assert resolve_insurer_towing_limit("Takaful Malaysia", "Motor PA Plus Plan 4") == "Unlimited"

    # 3. Etiqa: 200 km standard; Unlimited - Driver Plan 1 with OTO 360
    assert resolve_towing_entitlement("Etiqa").formatted == "200 km"
    assert resolve_towing_entitlement("Etiqa", package_or_rider="OTO 360 Plan 1").formatted == "Unlimited - Driver Plan 1"
    assert resolve_insurer_towing_limit("Etiqa", "Private Car Comprehensive") == "200 km"
    assert resolve_insurer_towing_limit("Etiqa", "OTO 360 Driver Plan 1") == "Unlimited - Driver Plan 1"

    # 4. Lonpac: RM 400 standard; E-Assist Smart Driver Plan 1 -> RM 600, Plan 2 / EV Plan -> Unlimited
    assert resolve_towing_entitlement("Lonpac").formatted == "RM 400"
    assert resolve_towing_entitlement("Lonpac", package_or_rider="E-Assist Smart Driver Plan 1").formatted == "RM 600"
    assert resolve_towing_entitlement("Lonpac", package_or_rider="E-Assist Smart Driver Plan 2").formatted == "Unlimited"
    assert resolve_towing_entitlement("Lonpac", package_or_rider="E-Assist Smart Driver EV Plan").formatted == "Unlimited"
    assert resolve_insurer_towing_limit("Lonpac", "Private Car Secure") == "RM 400"
    assert resolve_insurer_towing_limit("Lonpac", "E-Assist Smart Driver Plan 1") == "RM 600"
    assert resolve_insurer_towing_limit("Lonpac", "E-Assist Smart Driver Plan 2") == "Unlimited"

    # 5. Berjaya Sompo: Unlimited by default (no upgrade required)
    assert resolve_towing_entitlement("Berjaya Sompo").formatted == "Unlimited"
    assert resolve_insurer_towing_limit("Berjaya Sompo", "Private Car Comprehensive") == "Unlimited"

    # 6. Tune Protect: RM 300 standard; Motor Easy Bundle / AutoBuddy / Motor Shield -> Unlimited
    assert resolve_towing_entitlement("Tune Protect").formatted == "RM 300"
    assert resolve_towing_entitlement("Tune Protect", package_or_rider="Motor Shield").formatted == "Unlimited"
    assert resolve_towing_entitlement("Tune Protect", package_or_rider="AutoBuddy").formatted == "Unlimited"
    assert resolve_towing_entitlement("Tune Protect", package_or_rider="Motor Easy Bundle").formatted == "Unlimited"
    assert resolve_insurer_towing_limit("Tune Protect", "Motor Easy Private Car Comprehensive") == "RM 300"
    assert resolve_insurer_towing_limit("Tune Protect", "MotorShield Bundle") == "Unlimited"

    # 7. AmAssurance: Lite = 50 km, Plus = 100 km, Premier = 365 km, TPFT Premier = 200 km;
    #    Private Car 365 Plan 1 -> 600 km, Plan 2/3/4 -> Unlimited across all packages
    assert resolve_towing_entitlement("AmAssurance", product_name="auto365 Comprehensive Lite").formatted == "50 km"
    assert resolve_towing_entitlement("AmAssurance", product_name="auto365 Comprehensive Plus").formatted == "100 km"
    assert resolve_towing_entitlement("AmAssurance", product_name="auto365 Comprehensive Premier").formatted == "365 km"
    assert resolve_towing_entitlement("AmAssurance", product_name="auto365 TPFT Premier").formatted == "200 km"
    assert resolve_towing_entitlement("AmAssurance", product_name="auto365 TPFT Premier", package_or_rider="Private Car 365 Plan 1").formatted == "600 km"
    assert resolve_towing_entitlement("AmAssurance", product_name="auto365 TPFT Premier", package_or_rider="Private Car 365 Plan 2").formatted == "Unlimited"
    assert resolve_insurer_towing_limit("AmAssurance", "auto365 Comprehensive Lite") == "50 km"
    assert resolve_insurer_towing_limit("AmAssurance", "auto365 Comprehensive Plus") == "100 km"
    assert resolve_insurer_towing_limit("AmAssurance", "auto365 Comprehensive Premier") == "365 km"
    assert resolve_insurer_towing_limit("AmAssurance", "auto365 TPFT Premier") == "200 km"
    assert resolve_insurer_towing_limit("AmAssurance", "auto365 TPFT Premier Private Car 365 Plan 1") == "600 km"
    assert resolve_insurer_towing_limit("AmAssurance", "auto365 TPFT Premier Private Car 365 Plan 4") == "Unlimited"
    assert resolve_insurer_towing_limit("AmAssurance", "Third Party Only") == "-"
    assert resolve_insurer_towing_limit("AmAssurance", "Auto365 Comprehensive Lite (TPFT)") == "-"


def test_db_condition_replacement_value_and_manual_edit_flow_to_design2(m2_db: Session):
    """DB offering display_value, CompanyBenefitCondition.replacement_value, AND manual Box 1 edits
    must flow directly into Box 1 Design 2 unified add-ons — zero hardcoded 'RM 200.00' stone.
    """
    owner = User(id=new_id(), email="m2@risklocker.test", name="Tester", password_hash="x", role="admin")
    company = InsuranceCompany(id=new_id(), slug="takaful-malaysia", name="Takaful Malaysia", category="Motor", status="active")
    profile = CompanyBenefitProfile(id=new_id(), name="Master Unified Profile", is_active=True)
    c_towing = BenefitConcept(id=new_id(), concept_key="towing", label="Emergency Towing Assistance", status="active")
    c_pa = BenefitConcept(id=new_id(), concept_key="motor-pa-plus", label="Motor PA Plus", status="active")

    catalog = BenefitCatalog(id=new_id(), company_id=company.id, name="Takaful myMotor (Private Car)", status="published")
    rev = BenefitCatalogRevision(id=new_id(), catalog_id=catalog.id, revision_number=1, state="published", content_hash="m2-stmb")
    off_tow = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev.id,
        concept_id=c_towing.id,
        offering_key="stmb-tow",
        offering_kind="base",
        role="included",
        display_value="50 km",
        description_override="24/7 breakdown and accident towing assistance up to 50 km round trip.",
        status="active",
    )
    off_pa = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev.id,
        concept_id=c_pa.id,
        offering_key="stmb-pa",
        offering_kind="optional",
        role="addon_option",
        display_value="Plan 1",
        status="active",
    )
    cond_p1 = CompanyBenefitCondition(
        id=new_id(),
        company_id=company.id,
        profile_id=profile.id,
        name="Motor PA PLUS (Plan 1) -> 100 km Towing",
        trigger_concept_id=c_pa.id,
        trigger_plan_filter="Plan 1",
        target_concept_id=c_towing.id,
        action_type="replace_description",
        replacement_title="Extended Towing Assistance",
        replacement_value="100 km",
        replacement_description="24/7 emergency towing assistance up to 100 km (Motor PA Plan 1).",
        is_active=True,
    )
    batch = Batch(id=new_id(), owner_id=owner.id, name="M2 Batch")
    uploaded = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=owner.id,
        original_filename="stmb.pdf",
        content_type="application/pdf",
        storage_path="s/stmb.pdf",
    )
    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=uploaded.id,
        owner_id=owner.id,
        company_id=company.id,
        catalog_revision_id=rev.id,
        fields={
            "insurance_company": {"value": "Takaful Malaysia"},
            "vehicle_no": {"value": "JPQ6655"},
            "coverage_type": {"value": "Comprehensive"},
            "vehicle_type": {"value": "NonSaloonCar"},
        },
        scalar_decisions={},
        warnings=[],
    )
    sel_tow = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="base-towing",
        catalog_offering_id=off_tow.id,
        concept_id=c_towing.id,
        item_kind="base",
        state="current",
    )
    m2_db.add_all([owner, batch, company, profile, c_towing, c_pa, catalog, rev, off_tow, off_pa, cond_p1, uploaded, draft, sel_tow])
    m2_db.commit()

    concepts = [c_towing, c_pa]
    offerings = [off_tow, off_pa]
    conds = list(m2_db.scalars(select(CompanyBenefitCondition).where(CompanyBenefitCondition.company_id == company.id)).all())

    # Case A: Standard DB value (50 km) -> Box 1 & Unified Add-on Engine show 50 km, NOT RM 200.00!
    cards_std = resolve_benefit_cards(
        selections=[sel_tow],
        offerings=offerings,
        concepts=concepts,
        relations=[],
        facets=[],
        company_conditions=conds,
        company_configs=[],
    )
    tow_card_std = next(b for b in cards_std["current_benefits"] if b["concept_key"] == "towing")
    assert tow_card_std["value"] == "50 km"
    complimentary_std = extract_free_coverage_items(
        cards_std["current_benefits"],
        insurer_name="Takaful Malaysia",
        vehicle_type="NonSaloonCar",
        car_model="CR-V",
        fields=draft.fields,
    )
    complimentary_titles = [item["title"] for item in complimentary_std]
    assert "Emergency Towing Assistance (RM 200.00)" not in complimentary_titles
    assert any("50 km" in t for t in complimentary_titles)

    # Case B: Trigger Motor PA Plus Plan 1 -> Condition replacement_value ('100 km') upgrades Box 1 cleanly
    sel_pa = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="addon-motor-pa-plus",
        catalog_offering_id=off_pa.id,
        concept_id=c_pa.id,
        item_kind="addon",
        state="current",
        typed_value_override={"type": "string", "display_text": "Plan 1"},
    )
    m2_db.add(sel_pa)
    m2_db.commit()
    cards_p1 = resolve_benefit_cards(
        selections=[sel_tow, sel_pa],
        offerings=offerings,
        concepts=concepts,
        relations=[],
        facets=[],
        company_conditions=conds,
        company_configs=[],
    )
    tow_card_p1 = next(b for b in cards_p1["current_benefits"] if b["concept_key"] == "towing")
    assert tow_card_p1["value"] == "100 km"
    complimentary_p1 = extract_free_coverage_items(
        cards_p1["current_benefits"],
        insurer_name="Takaful Malaysia",
        vehicle_type="NonSaloonCar",
        car_model="CR-V",
        fields=draft.fields,
    )
    assert any("100 km" in item["title"] for item in complimentary_p1)

    # Case C: Staff manually overrides Box 1 towing -> custom edit wins over everything
    sel_tow.label_override = "Custom Flatbed Towing"
    sel_tow.typed_value_override = {
        "type": "string",
        "display_text": "750 km",
        "description": "VIP flatbed towing up to 750 km edited manually.",
    }
    m2_db.commit()
    cards_man = resolve_benefit_cards(
        selections=[sel_tow, sel_pa],
        offerings=offerings,
        concepts=concepts,
        relations=[],
        facets=[],
        company_conditions=conds,
        company_configs=[],
    )
    tow_card_man = next(b for b in cards_man["current_benefits"] if b["concept_key"] == "towing")
    assert tow_card_man["label"] == "Custom Flatbed Towing"
    assert tow_card_man["value"] == "750 km"
    complimentary_man = extract_free_coverage_items(
        cards_man["current_benefits"],
        insurer_name="Takaful Malaysia",
        vehicle_type="NonSaloonCar",
        car_model="CR-V",
        fields=draft.fields,
    )
    assert "Custom Flatbed Towing (750 km)" in [item["title"] for item in complimentary_man]

    # Case D: Third Party / Commercial Lorry must NEVER inject complimentary towing
    complimentary_tp = extract_free_coverage_items(
        [],
        insurer_name="Etiqa",
        vehicle_type="Car",
        car_model="Myvi",
        fields={"coverage_type": {"value": "Third Party"}, "vehicle_type": {"value": "Car"}},
    )
    assert not any("towing" in item["title"].lower() for item in complimentary_tp)


def test_auto_apply_flushes_last_source_decision_when_autoflush_disabled():
    """auto_apply_extracted_benefits must see pending DraftSourceLineDecision rows even with autoflush=False."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models.tables import (
        Base,
        BenefitCatalog,
        BenefitCatalogRevision,
        BenefitConcept,
        DraftSourceLineDecision,
        ExtractionBenefitLine,
        ExtractionRecord,
        InsuranceCompany,
        QuotationDraft,
    )
    from app.services.catalog_review_service import auto_apply_extracted_benefits

    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    LocalSession = sessionmaker(bind=eng, autocommit=False, autoflush=False)
    with LocalSession() as db:
        owner = User(id=new_id(), email="autoflush@risklocker.test", name="Tester", password_hash="x", role="admin")
        comp = InsuranceCompany(id=new_id(), slug="takaful-malaysia", name="Takaful Malaysia", category="Motor", status="active")
        cat = BenefitCatalog(id=new_id(), company_id=comp.id, name="Takaful myMotor", status="published")
        rev = BenefitCatalogRevision(id=new_id(), catalog_id=cat.id, revision_number=1, state="published", content_hash="m2-autoflush")
        concept = BenefitConcept(id=new_id(), concept_key="all-drivers", label="All Drivers", status="active", match_dataset=["all drivers"])
        batch = Batch(id=new_id(), owner_id=owner.id, name="Autoflush Batch")
        uploaded = UploadedFile(
            id=new_id(),
            batch_id=batch.id,
            owner_id=owner.id,
            original_filename="stmb.pdf",
            content_type="application/pdf",
            storage_path="s/stmb.pdf",
        )
        draft = QuotationDraft(
            id=new_id(),
            uploaded_file_id=uploaded.id,
            owner_id=owner.id,
            company_id=comp.id,
            catalog_revision_id=rev.id,
            fields={},
            scalar_decisions={},
            warnings=[],
        )
        rec = ExtractionRecord(
            id=new_id(),
            uploaded_file_id=uploaded.id,
            raw_text="ALL DRIVERS RM 0.00",
            ocr_text="",
            words=[],
            blocks=[],
            tables=[],
            images=[],
            regions=[],
            candidates={},
            benefit_lines=[],
            company_resolution={},
            warnings=[],
            reading_quality="ready",
        )
        db.add_all([owner, comp, cat, rev, concept, batch, uploaded, draft, rec])
        db.flush()

        line = ExtractionBenefitLine(
            id=new_id(),
            extraction_record_id=rec.id,
            line_id="line_last_all_drivers",
            raw_label="ALL DRIVERS",
            normalized_label="all drivers",
            page_number=1,
            section="Optional Covers",
            source_scope="selected",
            line_kind="benefit_candidate",
            inclusion_state="selected",
            evidence={"value": "RM 0.00", "premium_cost": "0.00"},
            candidate_mappings=[{"concept_id": concept.id, "concept_key": "all-drivers"}],
            extracted_value={"type": "money", "value": "0.00", "currency": "MYR"},
        )
        db.add(line)
        db.flush()

        # Deliberately omit db.flush() after DraftSourceLineDecision to reproduce autoflush=False last-item skip
        pending_decision = DraftSourceLineDecision(
            id=new_id(),
            draft_id=draft.id,
            source_line_id=line.id,
            disposition="unresolved",
        )
        db.add(pending_decision)

        auto_apply_extracted_benefits(db, draft)
        db.commit()

        saved = db.scalars(select(DraftSourceLineDecision).where(DraftSourceLineDecision.draft_id == draft.id)).all()
        assert len(saved) == 1
        assert saved[0].disposition != "unresolved"


