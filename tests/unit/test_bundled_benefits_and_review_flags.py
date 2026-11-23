"""Hermetic tests for Bundled Benefits ('Mystery Box'), 7-Insurer Towing Matrix, Review Flags & Design 2 PDF."""

from __future__ import annotations

import sys
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.domain.motor.towing_matrix import resolve_towing_entitlement
from app.models.enums import Role
from app.models.tables import (
    Base,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitProfile,
    CatalogOffering,
    CompanyBenefitBundle,
    CoverageType,
    DraftBenefitSelection,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceTenure,
    QuotationDraft,
    Segment,
    Session as SessionModel,
    TenureComparisonEntry,
    TrackedVehicle,
    User,
    VehicleCategory,
    new_id,
    utcnow,
)
from app.rendering.benefit_schedule_renderer import render_benefit_schedule_html
from app.rendering.pdf_generator import PdfRendererUnavailable, html_to_pdf
from app.rendering.render_context import resolve_benefit_cards
from app.rendering.template_renderer_design2 import render_design2_html
from app.rendering.unified_addon_engine import (
    build_unified_matrix_cards,
    extract_free_coverage_items,
)
from app.services.benefit_profile_service import clone_benefit_profile, list_benefit_profiles
from app.services.bundle_plan_matcher import (
    extract_plan_tier_token,
    is_base_auto365_policy_label,
    match_bundle_for_selection,
    match_bundle_for_text,
    resolve_bundle_tier,
)
from app.services.company_benefit_bundle_service import (
    delete_company_bundle,
    list_company_bundles,
    load_active_company_bundles,
    save_company_bundle,
)
from app.services.marketing_comparison.benefits_extractor import (
    _resolve_comparison_benefits,
    extract_draft_review_flags,
    extract_tenure_review_flags,
)
from app.services.marketing_comparison.materialize import (
    clear_entry_review_flags,
    get_confirmed_review_fields,
    get_entry_review_flags,
    record_manual_overrides,
)
from app.services.marketing_comparison.towing_evaluator import (
    resolve_insurer_towing_limit,
)
from app.services.workspace_patch_service import _apply_benefit_update

TOWING_CONCEPT_ID = "47e25689-0ef1-4db5-ae8e-251e8cd94af1"


@pytest.fixture()
def hermetic_db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db:
        yield db


def _make_admin(db: Session) -> User:
    u = User(
        id=new_id(),
        email="admin@risklocker.test",
        name="Admin User",
        role=Role.ADMIN.value,
        password_hash="x",
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(u)
    db.flush()
    return u


def _seed_core(db: Session):
    admin = _make_admin(db)
    prof = BenefitProfile(
        id=new_id(),
        name="Master 2026",
        version_number=1,
        status="published",
        is_active=True,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    seg = Segment(id=new_id(), segment_key="retail", name="Retail", status="active")
    veh = VehicleCategory(id=new_id(), category_key="car", name="Car", status="active")
    cov = CoverageType(id=new_id(), coverage_key="comprehensive", name="Comprehensive", status="active")
    towing_c = BenefitConcept(
        id=TOWING_CONCEPT_ID,
        concept_key="towing",
        label="24-Hour Emergency Towing",
        description="Standard 24/7 emergency roadside towing.",
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    key_c = BenefitConcept(
        id=new_id(),
        concept_key="key-replacement",
        label="Key Replacement",
        description="Reimbursement for lost or damaged vehicle keys.",
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add_all([prof, seg, veh, cov, towing_c, key_c])
    db.flush()
    return SimpleNamespace(admin=admin, prof=prof, seg=seg, veh=veh, cov=cov, towing_c=towing_c, key_c=key_c)


def _create_company_catalog(
    db: Session,
    core,
    *,
    slug: str,
    name: str,
    catalog_name: str,
    base_towing_value: str,
    bundle_concept_key: str | None = None,
    bundle_concept_label: str | None = None,
    price_amount: str = "250.00",
):
    comp = InsuranceCompany(
        id=new_id(),
        slug=slug,
        name=name,
        category="Motor",
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    prod = InsuranceProduct(
        id=new_id(),
        company_id=comp.id,
        product_key=f"{slug}-comp",
        name=catalog_name,
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    cat = BenefitCatalog(
        id=new_id(),
        company_id=comp.id,
        product_id=prod.id,
        segment_id=core.seg.id,
        vehicle_category_id=core.veh.id,
        coverage_type_id=core.cov.id,
        name=catalog_name,
        status="published",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    rev = BenefitCatalogRevision(
        id=new_id(),
        catalog_id=cat.id,
        revision_number=1,
        state="published",
        content_hash=f"h-{slug}",
        created_at=utcnow(),
    )
    towing_off = CatalogOffering(
        id=new_id(),
        catalog_revision_id=rev.id,
        concept_id=core.towing_c.id,
        offering_key=f"{slug}-towing-base",
        offering_kind="base",
        role="included",
        display_value=base_towing_value,
        description_override=f"Base towing up to {base_towing_value}",
        status="active",
        sort_order=10,
    )
    concepts = [core.towing_c, core.key_c]
    offerings = [towing_off]
    bundle_c = None
    bundle_off = None
    if bundle_concept_key and bundle_concept_label:
        bundle_c = BenefitConcept(
            id=new_id(),
            concept_key=bundle_concept_key,
            label=bundle_concept_label,
            description=f"{bundle_concept_label} comprehensive add-on package.",
            status="active",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(bundle_c)
        db.flush()
        bundle_off = CatalogOffering(
            id=new_id(),
            catalog_revision_id=rev.id,
            concept_id=bundle_c.id,
            offering_key=f"{slug}-{bundle_concept_key}",
            offering_kind="optional",
            role="addon_option",
            optional_price={"amount": price_amount, "currency": "MYR"},
            status="active",
            sort_order=20,
        )
        concepts.append(bundle_c)
        offerings.append(bundle_off)
    db.add_all([comp, prod, cat, rev, *offerings])
    db.flush()
    return SimpleNamespace(
        comp=comp,
        prod=prod,
        cat=cat,
        rev=rev,
        towing_off=towing_off,
        bundle_c=bundle_c,
        bundle_off=bundle_off,
        concepts=concepts,
        offerings=offerings,
    )


def _create_draft(db: Session, core, ctx, *, select_bundle: bool = False, raw_text: str = "", plan_tier: str | None = None, bundle_tier_id: str | None = None, plan_uncertain: bool = False, price_amount: str = "250.00", bundle_label_override: str | None = None, bundle_typed_override: dict | None = None):
    draft = QuotationDraft(
        id=new_id(),
        uploaded_file_id=new_id(),
        owner_id=core.admin.id,
        company_id=ctx.comp.id,
        product_id=ctx.prod.id,
        catalog_revision_id=ctx.rev.id,
        fields={},
        scalar_decisions={},
        display_options={},
        revision=1,
        updated_at=utcnow(),
    )
    db.add(draft)
    db.flush()
    towing_sel = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        catalog_offering_id=ctx.towing_off.id,
        concept_id=core.towing_c.id,
        selection_key="towing-base",
        item_kind="catalog",
        state="current",
        cost_status="included",
        sort_order=10,
    )
    selections = [towing_sel]
    bundle_sel = None
    if select_bundle and ctx.bundle_off and ctx.bundle_c:
        bundle_sel = DraftBenefitSelection(
            id=new_id(),
            draft_id=draft.id,
            catalog_offering_id=ctx.bundle_off.id,
            concept_id=ctx.bundle_c.id,
            selection_key=f"bundle-{ctx.bundle_c.concept_key}",
            item_kind="catalog",
            state="current",
            cost_status="paid",
            label_override=bundle_label_override,
            typed_value_override=bundle_typed_override,
            price={"amount": price_amount, "currency": "MYR"},
            bundle_tier_id=bundle_tier_id,
            evidence_snapshot={
                "raw_text": raw_text,
                "plan_tier": plan_tier,
                "plan_tier_uncertain": plan_uncertain,
            },
            sort_order=20,
        )
        selections.append(bundle_sel)
    db.add_all(selections)
    db.flush()
    return SimpleNamespace(draft=draft, towing_sel=towing_sel, bundle_sel=bundle_sel, selections=selections)


def test_bundle_crud_and_profile_deep_clone(hermetic_db: Session):
    db = hermetic_db
    core = _seed_core(db)
    amgen = _create_company_catalog(
        db,
        core,
        slug="amassurance",
        name="AmAssurance",
        catalog_name="auto365 Plus Comprehensive",
        base_towing_value="100 km",
        bundle_concept_key="private-car-365",
        bundle_concept_label="Private Car 365",
    )

    saved = save_company_bundle(
        db,
        core.admin,
        amgen.comp.id,
        {
            "name": "Private Car 365",
            "primary_concept_id": amgen.bundle_c.id,
            "match_aliases": ["private car 365", "pc 365"],
            "force_box2": True,
            "has_plan_tiers": True,
            "tiers": [
                {
                    "tier_key": "plan_1",
                    "label": "Plan 1",
                    "match_tokens": ["plan 1"],
                    "is_default_fallback": True,
                    "effects": [
                        {
                            "target_concept_id": core.towing_c.id,
                            "effect_type": "upgrade_to_box2",
                            "display_title": "Towing Assistance (600 km)",
                            "display_value": "",
                            "comparison_value": "600 km",
                            "icon_hint": "towing",
                        }
                    ],
                },
                {
                    "tier_key": "plan_2",
                    "label": "Plan 2",
                    "match_tokens": ["plan 2"],
                    "effects": [
                        {
                            "target_concept_id": core.towing_c.id,
                            "effect_type": "upgrade_to_box2",
                            "display_title": "Unlimited Towing Assistance",
                            "display_value": "",
                            "comparison_value": "Unlimited",
                            "icon_hint": "unlimited_towing",
                        },
                        {
                            "target_concept_id": core.key_c.id,
                            "effect_type": "add_to_box2",
                            "display_title": "Key Replacement",
                            "display_value": "RM 1,000",
                            "sort_order": 20,
                        },
                    ],
                },
            ],
        },
        profile_id=core.prof.id,
    )
    assert saved["name"] == "Private Car 365"
    assert len(saved["tiers"]) == 2
    assert len(saved["tiers"][1]["effects"]) == 2
    assert len(list_company_bundles(db, core.admin, amgen.comp.id, profile_id=core.prof.id)) == 1

    cloned = clone_benefit_profile(db, core.admin, core.prof.id, {"name": "Cloned 2027"})
    profiles_after = list_benefit_profiles(db, core.admin)
    cloned_entry = next(p for p in profiles_after if p["id"] == cloned["id"])
    assert cloned_entry["bundles_count"] == 1
    cloned_bundles = list_company_bundles(db, core.admin, amgen.comp.id, profile_id=cloned["id"])
    assert len(cloned_bundles) == 1
    assert cloned_bundles[0]["id"] != saved["id"]
    assert len(cloned_bundles[0]["tiers"]) == 2

    delete_company_bundle(db, core.admin, amgen.comp.id, cloned_bundles[0]["id"])
    assert len(list_company_bundles(db, core.admin, amgen.comp.id, profile_id=cloned["id"])) == 0
    # Source profile remains untouched
    assert len(list_company_bundles(db, core.admin, amgen.comp.id, profile_id=core.prof.id)) == 1


def test_plan_matcher_auto365_non_false_positive_and_range_stripping(hermetic_db: Session):
    db = hermetic_db
    core = _seed_core(db)
    amgen = _create_company_catalog(
        db,
        core,
        slug="amassurance",
        name="AmAssurance",
        catalog_name="auto365 Premier Comprehensive",
        base_towing_value="365 km",
        bundle_concept_key="private-car-365",
        bundle_concept_label="Private Car 365",
    )
    save_company_bundle(
        db,
        core.admin,
        amgen.comp.id,
        {
            "name": "Private Car 365",
            "primary_concept_id": amgen.bundle_c.id,
            "match_aliases": ["private car 365", "pc 365", "365 plan"],
            "force_box2": True,
            "has_plan_tiers": True,
            "tiers": [
                {"tier_key": "plan_1", "label": "Plan 1", "match_tokens": ["plan 1"], "is_default_fallback": True, "effects": []},
                {"tier_key": "plan_2", "label": "Plan 2", "match_tokens": ["plan 2"], "effects": []},
                {"tier_key": "plan_3", "label": "Plan 3", "match_tokens": ["plan 3"], "effects": []},
                {"tier_key": "plan_4", "label": "Plan 4", "match_tokens": ["plan 4"], "effects": []},
            ],
        },
        profile_id=core.prof.id,
    )
    bundles = load_active_company_bundles(db, amgen.comp.id, core.prof.id)

    assert is_base_auto365_policy_label("auto365 Comprehensive Lite") is True
    assert is_base_auto365_policy_label("auto365 Comprehensive Premier") is True
    assert is_base_auto365_policy_label("Private Car 365 Plan 2") is False

    # Base auto365 labels must NEVER falsely trigger Private Car 365 bundle
    assert match_bundle_for_text("auto365 Comprehensive Plus (100 km)", bundles) is None
    assert match_bundle_for_text("auto365 Comprehensive Premier", bundles) is None
    matched = match_bundle_for_text("Private Car 365 Plan 3", bundles)
    assert matched is not None

    # Range strings ("1-4") must not match Plan 1..4 -> falls back to Plan 1 with uncertain=True
    assert extract_plan_tier_token("Private Car 365 (Plans 1-4)") is None
    tier_unc, is_unc = resolve_bundle_tier(matched, extra_text="Private Car 365 (Plans 1-4)")
    assert tier_unc is not None and tier_unc.tier_key == "plan_1" and is_unc is True

    # Explicit Plan 2 / EV Plan extraction
    assert extract_plan_tier_token("Private Car 365 Plan 2") == "Plan 2"
    assert extract_plan_tier_token("E-Assist Smart Driver EV Plan") == "EV Plan"
    tier_p2, is_unc_p2 = resolve_bundle_tier(matched, extra_text="Private Car 365 Plan 2")
    assert tier_p2 is not None and tier_p2.tier_key == "plan_2" and is_unc_p2 is False


def test_all_7_insurers_box1_suppression_box2_layout_and_key_replacement(hermetic_db: Session):
    db = hermetic_db
    core = _seed_core(db)

    # 1. QBE
    qbe = _create_company_catalog(
        db, core, slug="qbe", name="QBE Insurance", catalog_name="QBE Private Car Protector",
        base_towing_value="RM 500", bundle_concept_key="dpp-n4", bundle_concept_label="Driver & Passenger Protector (N4)",
        price_amount="180.00",
    )
    save_company_bundle(db, core.admin, qbe.comp.id, {
        "name": "Driver & Passenger Protector (N4)",
        "primary_concept_id": qbe.bundle_c.id,
        "match_aliases": ["driver & passenger protector", "dpp", "n4", "unlimited auto assistance"],
        "force_box2": True,
        "has_plan_tiers": False,
        "tiers": [{
            "tier_key": "default", "label": "Plan 1", "is_default_fallback": True,
            "effects": [{
                "target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2",
                "display_title": "Unlimited Towing Assistance", "display_value": "",
                "icon_hint": "unlimited_towing", "comparison_value": "Unlimited - Plan 1",
            }],
        }],
    }, profile_id=core.prof.id)

    # 2. STMB / Takaful Malaysia
    stmb = _create_company_catalog(
        db, core, slug="takaful-malaysia", name="Takaful Malaysia", catalog_name="STMB Private Car Comprehensive",
        base_towing_value="50 km", bundle_concept_key="motor-pa-plus", bundle_concept_label="Motor PA Plus",
        price_amount="150.00",
    )
    save_company_bundle(db, core.admin, stmb.comp.id, {
        "name": "Motor PA Plus",
        "primary_concept_id": stmb.bundle_c.id,
        "match_aliases": ["motor pa plus", "motor pa"],
        "force_box2": True,
        "has_plan_tiers": True,
        "tiers": [
            {"tier_key": "plan_1", "label": "Plan 1", "match_tokens": ["plan 1"], "is_default_fallback": True,
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Towing Assistance (100 km)", "display_value": "", "comparison_value": "100 km"}]},
            {"tier_key": "plan_2", "label": "Plan 2", "match_tokens": ["plan 2"],
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Towing Assistance (200 km)", "display_value": "", "comparison_value": "200 km"}]},
            {"tier_key": "plan_3", "label": "Plan 3", "match_tokens": ["plan 3"],
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Towing Assistance (300 km)", "display_value": "", "comparison_value": "300 km"}]},
            {"tier_key": "plan_4", "label": "Plan 4", "match_tokens": ["plan 4"],
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Unlimited Towing Assistance", "display_value": "", "icon_hint": "unlimited_towing", "comparison_value": "Unlimited"}]},
        ],
    }, profile_id=core.prof.id)

    # 3. Etiqa
    etiqa = _create_company_catalog(
        db, core, slug="etiqa", name="Etiqa General Insurance", catalog_name="Etiqa Private Car Comprehensive",
        base_towing_value="200 km", bundle_concept_key="oto-360", bundle_concept_label="OTO 360",
        price_amount="120.00",
    )
    save_company_bundle(db, core.admin, etiqa.comp.id, {
        "name": "OTO 360",
        "primary_concept_id": etiqa.bundle_c.id,
        "match_aliases": ["oto 360", "oto360"],
        "force_box2": True,
        "has_plan_tiers": False,
        "tiers": [{
            "tier_key": "default", "label": "Driver Plan 1", "is_default_fallback": True,
            "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Unlimited Towing Assistance", "display_value": "", "icon_hint": "unlimited_towing", "comparison_value": "Unlimited - Driver Plan 1"}],
        }],
    }, profile_id=core.prof.id)

    # 4. Lonpac
    lonpac = _create_company_catalog(
        db, core, slug="lonpac", name="Lonpac Insurance", catalog_name="Lonpac Private Car Comprehensive",
        base_towing_value="RM 400", bundle_concept_key="e-assist-smart-driver", bundle_concept_label="E-Assist Smart Driver",
        price_amount="140.00",
    )
    save_company_bundle(db, core.admin, lonpac.comp.id, {
        "name": "E-Assist Smart Driver",
        "primary_concept_id": lonpac.bundle_c.id,
        "match_aliases": ["e-assist smart driver", "smart driver"],
        "force_box2": True,
        "has_plan_tiers": True,
        "tiers": [
            {"tier_key": "plan_1", "label": "Plan 1", "match_tokens": ["plan 1"], "is_default_fallback": True,
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Towing Assistance (RM 600)", "display_value": "", "comparison_value": "RM 600"}]},
            {"tier_key": "ev_plan", "label": "EV Plan", "match_tokens": ["ev plan"],
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Unlimited Towing Assistance", "display_value": "", "icon_hint": "unlimited_towing", "comparison_value": "Unlimited"}]},
        ],
    }, profile_id=core.prof.id)

    # 5. Berjaya Sompo (no upgrade required)
    sompo = _create_company_catalog(
        db, core, slug="berjaya-sompo", name="Berjaya Sompo", catalog_name="SOMPO Motor",
        base_towing_value="Unlimited",
    )

    # 6. Tune Protect
    tune = _create_company_catalog(
        db, core, slug="tune-protect", name="Tune Protect", catalog_name="Tune Comprehensive",
        base_towing_value="RM 300", bundle_concept_key="motor-easy-bundle", bundle_concept_label="Motor Easy Bundle",
        price_amount="110.00",
    )
    save_company_bundle(db, core.admin, tune.comp.id, {
        "name": "Motor Easy Bundle / AutoBuddy / MotorShield",
        "primary_concept_id": tune.bundle_c.id,
        "match_aliases": ["motor easy bundle", "autobuddy", "motorshield"],
        "force_box2": True,
        "has_plan_tiers": False,
        "tiers": [{"tier_key": "default", "label": "Included", "is_default_fallback": True,
                   "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Unlimited Towing Assistance", "display_value": "", "icon_hint": "unlimited_towing", "comparison_value": "Unlimited"}]}],
    }, profile_id=core.prof.id)

    # 7. AmAssurance 4 auto365 packages (Lite=50 km, Plus=100 km, Premier=365 km, TPFT Premier=200 km) + Private Car 365 Plan 1-4
    amgen_lite = _create_company_catalog(
        db, core, slug="amassurance", name="AmAssurance", catalog_name="auto365 Comprehensive Lite",
        base_towing_value="50 km", bundle_concept_key="private-car-365", bundle_concept_label="Private Car 365",
        price_amount="250.00",
    )

    def _add_amgen_pkg(cat_name: str, prod_key: str, base_km: str):
        p = InsuranceProduct(
            id=new_id(), company_id=amgen_lite.comp.id, product_key=prod_key, name=cat_name,
            status="active", created_at=utcnow(), updated_at=utcnow(),
        )
        cat = BenefitCatalog(
            id=new_id(), company_id=amgen_lite.comp.id, product_id=p.id, segment_id=core.seg.id,
            vehicle_category_id=core.veh.id, coverage_type_id=core.cov.id, name=cat_name,
            status="published", created_at=utcnow(), updated_at=utcnow(),
        )
        rev = BenefitCatalogRevision(
            id=new_id(), catalog_id=cat.id, revision_number=1, state="published",
            content_hash=f"h-{prod_key}", created_at=utcnow(),
        )
        tow = CatalogOffering(
            id=new_id(), catalog_revision_id=rev.id, concept_id=core.towing_c.id,
            offering_key=f"{prod_key}-tow", offering_kind="base", role="included",
            display_value=base_km, status="active", sort_order=10,
        )
        pc_off = CatalogOffering(
            id=new_id(), catalog_revision_id=rev.id, concept_id=amgen_lite.bundle_c.id,
            offering_key=f"{prod_key}-pc365", offering_kind="optional", role="addon_option",
            optional_price={"amount": "250.00", "currency": "MYR"}, status="active", sort_order=20,
        )
        db.add_all([p, cat, rev, tow, pc_off])
        db.flush()
        return SimpleNamespace(
            comp=amgen_lite.comp, prod=p, cat=cat, rev=rev,
            towing_off=tow, bundle_c=amgen_lite.bundle_c, bundle_off=pc_off,
            concepts=[core.towing_c, core.key_c, amgen_lite.bundle_c], offerings=[tow, pc_off],
        )

    amgen_plus = _add_amgen_pkg("auto365 Comprehensive Plus", "amgen-plus", "100 km")
    amgen_premier = _add_amgen_pkg("auto365 Comprehensive Premier", "amgen-premier", "365 km")
    amgen_tpft_premier = _add_amgen_pkg("auto365 TPFT Premier", "amgen-tpft-premier", "200 km")

    save_company_bundle(db, core.admin, amgen_lite.comp.id, {
        "name": "Private Car 365",
        "primary_concept_id": amgen_lite.bundle_c.id,
        "match_aliases": ["private car 365", "pc 365"],
        "force_box2": True,
        "has_plan_tiers": True,
        "tiers": [
            {"tier_key": "plan_1", "label": "Plan 1", "match_tokens": ["plan 1"], "is_default_fallback": True,
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Towing Assistance (600 km)", "display_value": "", "comparison_value": "600 km"}]},
            {"tier_key": "plan_2", "label": "Plan 2", "match_tokens": ["plan 2"],
             "effects": [
                 {"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Unlimited Towing Assistance", "display_value": "", "icon_hint": "unlimited_towing", "comparison_value": "Unlimited", "sort_order": 10},
                 {"target_concept_id": core.key_c.id, "effect_type": "add_to_box2", "display_title": "Key Replacement", "display_value": "RM 1,000", "sort_order": 20},
             ]},
            {"tier_key": "plan_3", "label": "Plan 3", "match_tokens": ["plan 3"],
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Unlimited Towing Assistance", "display_value": "", "icon_hint": "unlimited_towing", "comparison_value": "Unlimited"}]},
            {"tier_key": "plan_4", "label": "Plan 4", "match_tokens": ["plan 4"],
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Unlimited Towing Assistance", "display_value": "", "icon_hint": "unlimited_towing", "comparison_value": "Unlimited"}]},
        ],
    }, profile_id=core.prof.id)

    # Check Base Box 1 limits when NO bundle is purchased
    for ctx, expected_base in [
        (qbe, "RM 500"),
        (stmb, "50 km"),
        (etiqa, "200 km"),
        (lonpac, "RM 400"),
        (sompo, "Unlimited"),
        (tune, "RM 300"),
        (amgen_lite, "50 km"),
        (amgen_plus, "100 km"),
        (amgen_premier, "365 km"),
        (amgen_tpft_premier, "200 km"),
    ]:
        d_base = _create_draft(db, core, ctx, select_bundle=False)
        cards_base = resolve_benefit_cards(
            selections=d_base.selections,
            offerings=ctx.offerings,
            concepts=ctx.concepts,
            relations=[],
            facets=[],
            company_bundles=load_active_company_bundles(db, ctx.comp.id, core.prof.id),
            catalog_name=ctx.cat.name,
        )
        free_items = extract_free_coverage_items(cards_base["current_benefits"])
        assert any(
            expected_base in f"{it.get('title', '')} {it.get('value', '')} {it.get('description', '')}"
            for it in free_items
        ), f"Expected base {expected_base} in Box 1 for {ctx.cat.name}"

    # Check Bundle Active across all bundled insurers + exact tier title + no duplicate Plan value
    cases = [
        (qbe, None, "Driver & Passenger Protector (N4)", "Unlimited Towing Assistance", "unlimited_towing", None, None),
        (stmb, "Motor PA Plan 2", "Motor PA Plus - Plan 2", "Towing Assistance (200 km)", None, "Motor PA Plus Plan 1-4", {"type": "string", "display_text": "Plan 2"}),
        (stmb, "Motor PA Plan 4", "Motor PA Plus - Plan 4", "Unlimited Towing Assistance", "unlimited_towing", None, None),
        (etiqa, None, "OTO 360", "Unlimited Towing Assistance", "unlimited_towing", None, None),
        (lonpac, "Smart Driver Plan 1", "E-Assist Smart Driver - Plan 1", "Towing Assistance (RM 600)", None, None, None),
        (lonpac, "Smart Driver EV Plan", "E-Assist Smart Driver - EV Plan", "Unlimited Towing Assistance", "unlimited_towing", None, None),
        (tune, "Motor Easy Bundle", "Motor Easy Bundle", "Unlimited Towing Assistance", "unlimited_towing", None, None),
        (amgen_lite, "Private Car 365 Plan 1", "Private Car 365 - Plan 1", "Towing Assistance (600 km)", None, None, {"type": "string", "display_text": "Plan 1"}),
        (amgen_plus, "Private Car 365 Plan 2", "Private Car 365 - Plan 2", "Unlimited Towing Assistance", "unlimited_towing", None, {"type": "string", "display_text": "Plan 2"}),
        (amgen_premier, "Private Car 365 Plan 3", "Private Car 365 - Plan 3", "Unlimited Towing Assistance", "unlimited_towing", None, None),
        (amgen_tpft_premier, "Private Car 365 Plan 4", "Private Car 365 - Plan 4", "Unlimited Towing Assistance", "unlimited_towing", None, None),
    ]
    for ctx, plan_text, expected_parent_title, expected_tow_title, expected_icon, lbl_ovr, tv_ovr in cases:
        d_b = _create_draft(
            db, core, ctx, select_bundle=True, raw_text=plan_text or "", plan_tier=plan_text,
            bundle_label_override=lbl_ovr, bundle_typed_override=tv_ovr,
        )
        cards = resolve_benefit_cards(
            selections=d_b.selections,
            offerings=ctx.offerings,
            concepts=ctx.concepts,
            relations=[],
            facets=[],
            company_bundles=load_active_company_bundles(db, ctx.comp.id, core.prof.id),
            catalog_name=ctx.cat.name,
        )
        # Box 1 MUST NOT show base towing or bundle card
        free_items = extract_free_coverage_items(cards["current_benefits"])
        assert not any("towing" in str(it.get("title") or it.get("label") or "").lower() for it in free_items), f"Box 1 should remove Towing when bundle active ({plan_text})"
        # Box 2 schedule: parent bundle has exact tier title + price + zero duplicate plan value;
        # unlocked towing beside it has NO price and blank coverage
        box2 = build_unified_matrix_cards(cards["current_benefits"], cards["available_addons"])
        selected_box2 = [m for m in box2 if m["is_selected"]]
        parent_m = next((m for m in selected_box2 if m["title"] == expected_parent_title), None)
        tow_m = next((m for m in selected_box2 if m["title"] == expected_tow_title), None)
        assert parent_m is not None and parent_m["price"] is not None, f"Parent bundle '{expected_parent_title}' missing for {plan_text}; got {[m['title'] for m in selected_box2]}"
        assert parent_m["value"] == "", f"Duplicate tier value leaked on parent bundle '{expected_parent_title}': {parent_m['value']!r}"
        assert tow_m is not None, f"Unlocked towing '{expected_tow_title}' missing from Box 2 for {plan_text}"
        assert tow_m["price"] is None
        assert tow_m["cost_status"] == "bundle_included"
        assert tow_m["value"] == ""
        if expected_icon:
            assert tow_m["icon_hint"] == expected_icon

        if plan_text == "Private Car 365 Plan 2":
            key_m = next((m for m in selected_box2 if m["title"] == "Key Replacement"), None)
            assert key_m is not None
            assert key_m["price"] is None
            assert key_m["value"] == "RM 1,000.00"


def test_workspace_patch_tier_switch_and_confirm_clears_uncertain(hermetic_db: Session):
    db = hermetic_db
    core = _seed_core(db)
    amgen = _create_company_catalog(
        db, core, slug="amassurance", name="AmAssurance", catalog_name="auto365 Plus Comprehensive",
        base_towing_value="100 km", bundle_concept_key="private-car-365", bundle_concept_label="Private Car 365",
    )
    saved = save_company_bundle(db, core.admin, amgen.comp.id, {
        "name": "Private Car 365",
        "primary_concept_id": amgen.bundle_c.id,
        "match_aliases": ["private car 365"],
        "force_box2": True,
        "has_plan_tiers": True,
        "tiers": [
            {"tier_key": "plan_1", "label": "Plan 1", "match_tokens": ["plan 1"], "is_default_fallback": True,
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Towing Assistance (600 km)", "display_value": "", "comparison_value": "600 km"}]},
            {"tier_key": "plan_2", "label": "Plan 2", "match_tokens": ["plan 2"],
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Unlimited Towing Assistance", "display_value": "", "icon_hint": "unlimited_towing", "comparison_value": "Unlimited"}]},
        ],
    }, profile_id=core.prof.id)
    p1_id = saved["tiers"][0]["id"]
    p2_id = saved["tiers"][1]["id"]
    d_obj = _create_draft(
        db, core, amgen, select_bundle=True, raw_text="Private Car 365",
        plan_tier="Plan 1", bundle_tier_id=p1_id, plan_uncertain=True,
        bundle_typed_override={"type": "string", "display_text": "Plan 1"},
    )

    # Verify confirm_plan_tier clears uncertain flag without changing tier and keeps exact Plan 1 title
    _apply_benefit_update(db, d_obj.draft, core.admin, {"selection_id": d_obj.bundle_sel.id, "confirm_plan_tier": True})
    db.flush()
    assert d_obj.bundle_sel.evidence_snapshot["plan_tier_uncertain"] is False

    # Switch tier to Plan 2
    _apply_benefit_update(db, d_obj.draft, core.admin, {"selection_id": d_obj.bundle_sel.id, "bundle_tier_id": p2_id})
    db.flush()
    assert d_obj.bundle_sel.bundle_tier_id == p2_id
    cards = resolve_benefit_cards(
        selections=list(db.scalars(select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == d_obj.draft.id)).all()),
        offerings=amgen.offerings,
        concepts=amgen.concepts,
        relations=[],
        facets=[],
        company_bundles=load_active_company_bundles(db, amgen.comp.id, core.prof.id),
        catalog_name=amgen.cat.name,
    )
    parent_c = next(c for c in cards["current_benefits"] if c["concept_id"] == amgen.bundle_c.id)
    assert parent_c["label"] == "Private Car 365 - Plan 2"
    assert parent_c["value"] == ""
    tow_c = next(c for c in cards["current_benefits"] if c["concept_id"] == core.towing_c.id)
    assert tow_c["label"] == "Unlimited Towing Assistance"
    assert tow_c["icon_hint"] == "unlimited_towing"
    assert not any("towing" in it["title"].lower() for it in extract_free_coverage_items(cards["current_benefits"]))

    # Move bundle to available_addon (untick) -> clears bundle_tier_id, drops Box 2 towing, restores Box 1 default 100 km towing
    _apply_benefit_update(db, d_obj.draft, core.admin, {"selection_id": d_obj.bundle_sel.id, "state": "available_addon"})
    db.flush()
    assert d_obj.bundle_sel.bundle_tier_id is None
    cards_after_untick = resolve_benefit_cards(
        selections=list(db.scalars(select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == d_obj.draft.id)).all()),
        offerings=amgen.offerings,
        concepts=amgen.concepts,
        relations=[],
        facets=[],
        company_bundles=load_active_company_bundles(db, amgen.comp.id, core.prof.id),
        catalog_name=amgen.cat.name,
    )
    free_after_untick = extract_free_coverage_items(cards_after_untick["current_benefits"])
    assert any("100 km" in it["title"] for it in free_after_untick)
    box2_after_untick = build_unified_matrix_cards(cards_after_untick["current_benefits"], cards_after_untick["available_addons"])
    assert not any(c["is_selected"] and c["id"] == "towing" for c in box2_after_untick)

    # Re-add with Plan 1, then remove completely -> Box 1 default 100 km towing must still reappear
    _apply_benefit_update(db, d_obj.draft, core.admin, {"selection_id": d_obj.bundle_sel.id, "state": "current", "bundle_tier_id": p1_id})
    _apply_benefit_update(db, d_obj.draft, core.admin, {"selection_id": d_obj.bundle_sel.id, "state": "removed"})
    db.flush()
    assert d_obj.bundle_sel.bundle_tier_id is None
    cards_after_remove = resolve_benefit_cards(
        selections=list(db.scalars(select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == d_obj.draft.id)).all()),
        offerings=amgen.offerings,
        concepts=amgen.concepts,
        relations=[],
        facets=[],
        company_bundles=load_active_company_bundles(db, amgen.comp.id, core.prof.id),
        catalog_name=amgen.cat.name,
    )
    free_after_remove = extract_free_coverage_items(cards_after_remove["current_benefits"])
    assert any("100 km" in it["title"] for it in free_after_remove)


def test_comparison_towing_resolution_and_review_flags_lifecycle(hermetic_db: Session):
    db = hermetic_db
    core = _seed_core(db)
    amgen = _create_company_catalog(
        db, core, slug="amassurance", name="AmAssurance", catalog_name="auto365 Plus Comprehensive",
        base_towing_value="100 km", bundle_concept_key="private-car-365", bundle_concept_label="Private Car 365",
    )
    save_company_bundle(db, core.admin, amgen.comp.id, {
        "name": "Private Car 365",
        "primary_concept_id": amgen.bundle_c.id,
        "match_aliases": ["private car 365"],
        "force_box2": True,
        "has_plan_tiers": True,
        "tiers": [
            {"tier_key": "plan_1", "label": "Plan 1", "match_tokens": ["plan 1"], "is_default_fallback": True,
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Towing Assistance (600 km)", "display_value": "", "comparison_value": "600 km"}]},
            {"tier_key": "plan_2", "label": "Plan 2", "match_tokens": ["plan 2"],
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Unlimited Towing Assistance", "display_value": "", "icon_hint": "unlimited_towing", "comparison_value": "Unlimited"}]},
        ],
    }, profile_id=core.prof.id)

    # Undetected plan defaults to Plan 1 ("600 km") and flags towing_uncertain=True
    d_unc = _create_draft(db, core, amgen, select_bundle=True, raw_text="Private Car 365", plan_tier=None, plan_uncertain=True)
    sess = SessionModel(
        id=new_id(),
        owner_id=core.admin.id,
        uploaded_file_id=d_unc.draft.uploaded_file_id,
        draft_id=d_unc.draft.id,
        detected_company="AmAssurance",
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(sess)
    db.flush()

    b_res = _resolve_comparison_benefits(db, sess, amgen.comp.id, {})
    assert b_res["towing_km"] == "600 km"
    assert b_res["towing_uncertain"] is True

    # Fallback domain & evaluator preserve lite="50 km"/"50km" while handling Private Car 365
    assert resolve_towing_entitlement("AmAssurance", "auto365 Lite").formatted == "50 km"
    assert resolve_towing_entitlement("AmAssurance", "Private Car 365 Plan 1").formatted == "600 km"
    assert resolve_towing_entitlement("AmAssurance", "Private Car 365 Plan 2").formatted == "Unlimited"
    assert resolve_insurer_towing_limit("AmAssurance", "Private Car 365") == "600 km"
    assert resolve_insurer_towing_limit("AmAssurance", "Private Car 365 Plan 2") == "Unlimited"

    flags = extract_draft_review_flags(
        {"motor_premium": {"value": "1200.00", "status": "check_needed", "message": "Verify premium"}},
        towing_uncertain=b_res["towing_uncertain"],
        towing_reason=b_res["towing_uncertain_reason"],
        sum_insured=0.0,
        motor_premium=1200.0,
        coverage_type="Comprehensive",
    )
    assert "motor_premium" in flags
    assert "towing_limit" in flags
    assert "sum_insured" in flags

    entry = TenureComparisonEntry(
        id=new_id(), tenure_id=new_id(), session_id=sess.id, company_name="AmAssurance",
        manual_overrides=[], review_flags=dict(flags), created_at=utcnow(), updated_at=utcnow(),
    )
    # Confirming towing_limit clears flag & remembers confirmation
    clear_entry_review_flags(entry, ["towing_limit"])
    assert "towing_limit" not in get_entry_review_flags(entry)
    assert "towing_limit" in get_confirmed_review_fields(entry)
    # Editing motor_premium clears its flag too
    record_manual_overrides(entry, edited_fields=["motor_premium"])
    assert "motor_premium" not in get_entry_review_flags(entry)

    # Tenure vehicle flags detect missing plate / engine_cc
    t_flags = extract_tenure_review_flags(SimpleNamespace(vehicle_no="N/A", is_plate_undetected=True, car_brand="", vehicle_model="", engine_cc=""))
    assert "vehicle_no" in t_flags and "vehicle_model" in t_flags and "engine_cc" in t_flags


def test_design2_html_and_pdf_rendering_with_unlimited_towing_bundle(hermetic_db: Session, tmp_path: Path):
    db = hermetic_db
    core = _seed_core(db)
    amgen = _create_company_catalog(
        db, core, slug="amassurance", name="AmAssurance", catalog_name="auto365 Plus Comprehensive",
        base_towing_value="100 km", bundle_concept_key="private-car-365", bundle_concept_label="Private Car 365",
        price_amount="250.00",
    )
    save_company_bundle(db, core.admin, amgen.comp.id, {
        "name": "Private Car 365",
        "primary_concept_id": amgen.bundle_c.id,
        "match_aliases": ["private car 365"],
        "force_box2": True,
        "has_plan_tiers": True,
        "tiers": [
            {"tier_key": "plan_2", "label": "Plan 2", "match_tokens": ["plan 2"], "is_default_fallback": True,
             "effects": [{"target_concept_id": core.towing_c.id, "effect_type": "upgrade_to_box2", "display_title": "Unlimited Towing Assistance", "display_value": "", "icon_hint": "unlimited_towing", "comparison_value": "Unlimited"}]},
        ],
    }, profile_id=core.prof.id)
    d_b = _create_draft(
        db, core, amgen, select_bundle=True, raw_text="Private Car 365 Plan 2", plan_tier="Plan 2",
        bundle_typed_override={"type": "string", "display_text": "Plan 2"},
    )
    cards = resolve_benefit_cards(
        selections=d_b.selections,
        offerings=amgen.offerings,
        concepts=amgen.concepts,
        relations=[],
        facets=[],
        company_bundles=load_active_company_bundles(db, amgen.comp.id, core.prof.id),
        catalog_name=amgen.cat.name,
    )
    matrix = build_unified_matrix_cards(cards["current_benefits"], cards["available_addons"])
    parent_entry = next(m for m in matrix if m["title"] == "Private Car 365 - Plan 2")
    assert parent_entry["value"] == ""
    tow_entry = next(m for m in matrix if m["title"] == "Unlimited Towing Assistance")
    assert tow_entry["is_selected"] is True
    assert tow_entry["price"] is None
    assert tow_entry["value"] == ""
    assert tow_entry["icon_hint"] == "unlimited_towing"

    html = render_design2_html(
        draft_fields={
            "customer_name": "Tan Wei Ming",
            "quotation_reference": "QT-2026-365",
            "vehicle_no": "VAA 3650",
            "insurance_company": "AMGENERAL INSURANCE BERHAD",
            "car_model": "Honda Civic 1.5L",
            "cover_period": "01-01-2026 TO 31-12-2026",
            "coverage_type": "Comprehensive",
            "ncd_percent": "55.00%",
            "valuation_type": "Agreed Value",
            "coverage_amount": "RM 110,000.00",
            "premium": "1850.00",
            "roadtax": "90.00",
            "service_fee": "15.00",
            "total_amount": "1955.00",
        },
        template_config={"language_mode": "en"},
        render_context={
            "current_benefits": cards["current_benefits"],
            "available_addons": cards["available_addons"],
            "extras_display_mode": "split",
        },
        db=db,
    )
    assert "Private Car 365 - Plan 2" in html
    assert ">Plan 2<" not in html
    assert "RM 250.00" not in html
    assert "Unlimited Towing Assistance" in html
    assert "Included in Private Car 365" not in html
    assert "24-Hour Emergency Towing" not in html
    assert "#E52320" in html

    sched_html = render_benefit_schedule_html(
        draft_fields={
            "customer_name": "Tan Wei Ming",
            "quotation_reference": "QT-2026-365",
            "vehicle_no": "VAA 3650",
            "insurance_company": "AMGENERAL INSURANCE BERHAD",
            "car_model": "Honda Civic 1.5L",
        },
        template_config={"language_mode": "en"},
        render_context={
            "current_benefits": cards["current_benefits"],
            "available_addons": cards["available_addons"],
            "extras_display_mode": "split",
        },
        db=db,
    )
    assert "Private Car 365 - Plan 2" in sched_html
    assert "RM 250.00" in sched_html
    assert "Unlimited Towing Assistance" in sched_html
    assert "INCLUDED FOC" not in sched_html

    pdf_path = tmp_path / "design2_bundle.pdf"
    try:
        out_path, warnings = html_to_pdf(html, pdf_path)
        pdf_bytes = out_path.read_bytes()
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 5000
    except PdfRendererUnavailable:
        pytest.skip("Playwright Chromium browser binary unavailable in test environment")
