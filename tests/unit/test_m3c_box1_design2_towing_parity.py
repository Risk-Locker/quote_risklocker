"""Hermetic TDD suite for Milestone 3c: Commercial Catalog Pinning, Box 1 WYSIWYG Parity & In-Place Towing Conditions."""

from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import (
    Base,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    CompanyBenefitCondition,
    CompanyBenefitProfile,
    CoverageType,
    DraftBenefitSelection,
    InsuranceCompany,
    InsuranceProduct,
    QuotationDraft,
    Segment,
    Session as SessionModel,
    User,
    VehicleCategory,
    new_id,
)
from app.rendering.render_context import resolve_benefit_cards
from app.rendering.unified_addon_engine import (
    detect_towing_upgrade,
    extract_free_coverage_items,
)
from app.services.benefit_evaluation_engine import (
    BenefitEvaluationEngine,
    EvaluatedBenefit,
)
from app.services.catalog_review_service import (
    _resolve_vehicle_category,
    initialize_catalog_review,
)
from app.services.marketing_comparison.benefits_extractor import (
    _resolve_comparison_benefits,
)


@pytest.fixture()
def hermetic_db() -> Generator[Session, None, None]:
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


def test_commercial_heavy_vehicle_pins_commercial_catalog_and_seeds_box1_perks(hermetic_db: Session):
    """M3c-1: Heavy commercial vehicle (e.g. SANY 16000 KG) resolves to commercial_vehicle catalog and seeds Legal Defense + Warranty."""
    user = User(id=new_id(), email="staff-m3c@risklocker.test", password_hash="x", role="staff", status="active")
    comp = InsuranceCompany(id=new_id(), slug="berjaya-sompo", name="Berjaya Sompo", category="Motor", status="active")
    cat_car = VehicleCategory(id=new_id(), category_key="car", name="Private Car", status="active")
    cat_comm = VehicleCategory(id=new_id(), category_key="commercial_vehicle", name="Commercial Vehicle", status="active")
    seg_comm = Segment(id=new_id(), segment_key="commercial", name="Commercial", status="active")
    cov_comp = CoverageType(id=new_id(), coverage_key="comprehensive", name="Comprehensive", status="active")

    c_towing = BenefitConcept(id=new_id(), concept_key="towing", label="Emergency Towing Assistance", status="active")
    c_legal = BenefitConcept(id=new_id(), concept_key="legal-defense-costs", label="Legal Defense Costs", status="active")
    c_warranty = BenefitConcept(id=new_id(), concept_key="repair-workmanship-warranty", label="Panel Workmanship Warranty", status="active")

    prod_car = InsuranceProduct(
        id=new_id(),
        company_id=comp.id,
        product_key="sompo-private-car",
        name="Sompo MotorNow Private Car",
        status="active",
    )
    prod_comm = InsuranceProduct(
        id=new_id(),
        company_id=comp.id,
        product_key="sompo-commercial",
        name="Sompo Commercial Motor Comprehensive",
        status="active",
    )
    bcat_car = BenefitCatalog(
        id=new_id(),
        company_id=comp.id,
        product_id=prod_car.id,
        vehicle_category_id=cat_car.id,
        coverage_type_id=cov_comp.id,
        name="Car Catalog",
        status="active",
    )
    brev_car = BenefitCatalogRevision(id=new_id(), catalog_id=bcat_car.id, revision_number=1, state="published", content_hash="h-car")
    bcat_comm = BenefitCatalog(
        id=new_id(),
        company_id=comp.id,
        product_id=prod_comm.id,
        vehicle_category_id=cat_comm.id,
        segment_id=seg_comm.id,
        coverage_type_id=cov_comp.id,
        name="Commercial Catalog",
        status="active",
    )
    brev_comm = BenefitCatalogRevision(id=new_id(), catalog_id=bcat_comm.id, revision_number=1, state="published", content_hash="h-comm")

    off_car_tow = CatalogOffering(
        id=new_id(),
        catalog_revision_id=brev_car.id,
        concept_id=c_towing.id,
        offering_key="car-towing",
        offering_kind="base",
        role="included",
        status="active",
    )
    off_comm_legal = CatalogOffering(
        id=new_id(),
        catalog_revision_id=brev_comm.id,
        concept_id=c_legal.id,
        offering_key="comm-legal",
        offering_kind="base",
        role="included",
        status="active",
    )
    off_comm_warr = CatalogOffering(
        id=new_id(),
        catalog_revision_id=brev_comm.id,
        concept_id=c_warranty.id,
        offering_key="comm-warranty",
        offering_kind="base",
        role="included",
        status="active",
    )
    hermetic_db.add_all([
        user, comp, cat_car, cat_comm, seg_comm, cov_comp,
        c_towing, c_legal, c_warranty,
        prod_car, prod_comm, bcat_car, brev_car, bcat_comm, brev_comm,
        off_car_tow, off_comm_legal, off_comm_warr,
    ])
    hermetic_db.flush()

    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=new_id(),
        owner_id=user.id,
        company_id=comp.id,
        fields={
            "vehicle_no": {"value": "VRS7732"},
            "car_brand": {"value": "SANY"},
            "car_model": {"value": "SYM5410THB"},
            "engine_cc": {"value": "16000 KG"},
            "coverage_type": {"value": "Comprehensive"},
            "customer_name": {"value": "SANY CONSTRUCTION SDN BHD"},
        },
    )
    hermetic_db.add(draft)
    hermetic_db.commit()

    resolved_cat_id = _resolve_vehicle_category(hermetic_db, "", draft.fields)
    assert resolved_cat_id == cat_comm.id

    initialize_catalog_review(hermetic_db, draft)
    hermetic_db.commit()
    assert draft.catalog_revision_id == brev_comm.id

    sels = list(hermetic_db.query(DraftBenefitSelection).filter_by(draft_id=draft.id, state="current").all())
    seeded_concept_ids = {s.concept_id for s in sels}
    assert c_legal.id in seeded_concept_ids
    assert c_warranty.id in seeded_concept_ids
    assert c_towing.id not in seeded_concept_ids


def test_detect_towing_upgrade_reads_typed_value_and_plan_4_and_updates_in_place():
    """M3c-2: detect_towing_upgrade parses typed_value/value ('Plan 4') even when label is just 'Motor PA Plus'."""
    active_benefits = [
        {
            "id": "b-tow",
            "concept_key": "towing",
            "label": "Emergency Towing Assistance (RM 200.00)",
            "description": "24/7 accidental towing service to nearest panel workshop.",
            "cost_status": "included",
            "is_extra": False,
        },
        {
            "id": "b-pa",
            "concept_key": "motor-pa-plus",
            "label": "Motor PA Plus",
            "value": "",
            "typed_value": {"type": "string", "display_text": "Plan 4"},
            "cost_status": "paid",
            "is_extra": True,
            "price": {"amount": 90.0},
        },
    ]
    upgrade = detect_towing_upgrade(active_benefits, "Takaful Malaysia")
    assert upgrade is not None
    assert upgrade["title"] == "Unlimited Towing Assistance"
    assert upgrade["rider"] == "Motor PA Plus - Plan 4"

    free_items = extract_free_coverage_items(active_benefits, "Takaful Malaysia")
    assert free_items[0]["title"] == "Unlimited Towing Assistance"
    assert "Unlimited" in free_items[0]["title"]


def test_company_benefit_condition_plan_4_beats_wildcard_across_box1_and_comparison(hermetic_db: Session):
    """M3c-3: Specific Plan 4 condition overrides wildcard condition in both resolve_benefit_cards and BenefitEvaluationEngine."""
    comp = InsuranceCompany(id=new_id(), slug="takaful-malaysia", name="Takaful Malaysia", category="Motor", status="active")
    prof = CompanyBenefitProfile(id=new_id(), name="Default v1", version_number=1, status="active", is_active=True)
    c_towing = BenefitConcept(id=new_id(), concept_key="towing", label="Emergency Towing Assistance", description="Standard 100 km towing", status="active")
    c_pa_plus = BenefitConcept(id=new_id(), concept_key="motor-pa-plus", label="Motor PA Plus", description="PA Plus Rider", status="active")

    # Contradictory conditions: wildcard first or after specific Plan 4
    cond_plan4 = CompanyBenefitCondition(
        id=new_id(),
        company_id=comp.id,
        profile_id=prof.id,
        name="Motor PA Plus Plan 4 -> Unlimited Towing",
        trigger_concept_id=c_pa_plus.id,
        trigger_plan_filter="Plan 4",
        target_concept_id=c_towing.id,
        action_type="replace_description",
        replacement_title="Unlimited Towing Assistance",
        replacement_description="Unlimited breakdown and accident towing nationwide (Motor PA Plus Plan 4).",
        is_active=True,
    )
    cond_wildcard = CompanyBenefitCondition(
        id=new_id(),
        company_id=comp.id,
        profile_id=None,
        name="Motor PA Plus Wildcard -> RM 200 Towing",
        trigger_concept_id=c_pa_plus.id,
        trigger_plan_filter="",
        target_concept_id=c_towing.id,
        action_type="replace_description",
        replacement_title="Emergency Towing Assistance (RM 200.00)",
        replacement_description="Up to RM 200 per incident.",
        is_active=True,
    )
    hermetic_db.add_all([comp, prof, c_towing, c_pa_plus, cond_plan4, cond_wildcard])
    hermetic_db.commit()

    # 1. Verify resolve_benefit_cards (Box 1 UI & PDF render context)
    off_tow = SimpleNamespace(
        id="off-tow",
        offering_key="base-towing",
        concept_id=c_towing.id,
        offering_kind="base",
        role="included",
        status="active",
        cost_status="included",
        optional_price=None,
        typed_value={"type": "distance", "value": 100, "unit": "km", "unlimited": False},
        presentation_facet_ids=[],
        label_override=None,
        description_override=None,
        sort_order=1,
    )
    off_pa = SimpleNamespace(
        id="off-pa-p4",
        offering_key="motor-pa-plus-plan-4",
        concept_id=c_pa_plus.id,
        offering_kind="optional",
        role="addon_option",
        status="active",
        cost_status="paid",
        optional_price={"amount": 90.0, "currency": "MYR"},
        typed_value={"type": "string", "display_text": "Plan 4"},
        presentation_facet_ids=[],
        label_override="Motor PA Plus — Plan 4",
        description_override=None,
        sort_order=2,
    )
    sel_tow = SimpleNamespace(
        id="sel-tow",
        selection_key="default:base-towing",
        item_kind="catalog",
        sort_order=1,
        concept_id=c_towing.id,
        catalog_offering_id="off-tow",
        state="current",
        cost_status="included",
        price=None,
        typed_value_override=None,
        label_override=None,
        description_override=None,
        package_plan_id=None,
        evidence_snapshot={},
    )
    sel_pa = SimpleNamespace(
        id="sel-pa",
        selection_key="addon:motor-pa-plus-plan-4",
        item_kind="catalog",
        sort_order=2,
        concept_id=c_pa_plus.id,
        catalog_offering_id="off-pa-p4",
        state="current",
        cost_status="paid",
        price={"amount": 90.0, "currency": "MYR"},
        typed_value_override=None,
        label_override=None,
        description_override=None,
        package_plan_id=None,
        evidence_snapshot={},
    )

    # Pass wildcard AFTER specific cond_plan4 to prove specificity sorting
    cards = resolve_benefit_cards(
        selections=[sel_tow, sel_pa],
        offerings=[off_tow, off_pa],
        concepts=[c_towing, c_pa_plus],
        relations=[],
        facets=[],
        company_conditions=[cond_plan4, cond_wildcard],
    )
    tow_card = next(c for c in cards["current_benefits"] if c["concept_id"] == c_towing.id)
    assert tow_card["label"] == "Unlimited Towing Assistance"
    assert "Unlimited" in tow_card["description"]

    # 2. Verify BenefitEvaluationEngine & Comparison Extractor
    evaluated = BenefitEvaluationEngine.evaluate_benefits_for_plan(
        db=hermetic_db,
        company_id=comp.id,
        profile_id=None,
        base_benefits=[
            EvaluatedBenefit(concept_id="towing", display_title="Roadside Towing", display_description="200 KM"),
            EvaluatedBenefit(concept_id=c_pa_plus.id, display_title="Motor PA Plus", display_description="Plan 4"),
        ],
        plan_name="Motor PA Plus — Plan 4",
    )
    eval_tow = next(b for b in evaluated if b.concept_id == "towing")
    assert eval_tow.display_title == "Unlimited Towing Assistance"
    assert "Unlimited" in eval_tow.display_description
