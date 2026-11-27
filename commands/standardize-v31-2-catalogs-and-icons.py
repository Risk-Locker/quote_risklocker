#!/usr/bin/env python3
"""Standardize Design 2 vector icons and clean all 10 insurers' motor catalogs (v31.2).

Idempotent script that:
1. Un-retires `legal-liability-to-pillion`, merges duplicate TPBI/TPPD concepts,
   migrates retired `personal-accident` -> `accidental-death`, and cleans legacy conditions.
2. Renders all active BenefitConcept Design 2 SVG icons (`#1D1D1B` + `#E52320`) as
   512x512 transparent PNGs via Playwright Chromium, uploads them to Supabase Storage,
   activates the `Design 2 Vector Icons` global visual profile, updates every active
   `BenefitConcept.default_asset_id`, and archives legacy 3D/isometric `benefit_art`.
3. Enforces domain structure (TPO = MMIP only; Lorry = Commercial only; complete
   `segment_id` backfill; zero static prices or demo values; matching towing/betterment
   values and descriptions; single canonical catalog per scenario; clean AmAssurance
   cloned 1:1 to Kurnia and Liberty; full Tune Protect & Berjaya Sompo bundles; and
   clean TPFT/Motorcycle/Lorry boundaries).
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, select, text
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.tables import (
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    BenefitProfile,
    BusinessAsset,
    CatalogOffering,
    CompanyAlias,
    CompanyBenefitBundle,
    CompanyBenefitBundleEffect,
    CompanyBenefitBundleTier,
    CompanyBenefitCondition,
    CompanyBenefitConfig,
    CoverageType,
    DraftBenefitSelection,
    GlobalBenefitProfile,
    GlobalBenefitProfileAsset,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceProductTier,
    Segment,
    VehicleCategory,
    new_id,
)
from app.rendering.design2_icons import render_design2_icon_svg
from app.services.asset_intake import create_derivative, validate_image_bytes
from app.storage.supabase import SupabaseStorage


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _norm(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _slug(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def sync_design2_vector_icons(db, *, dry_run: bool = False) -> dict:
    """Render crisp 512x512 transparent PNGs from Design 2 vector SVGs and activate them."""
    from playwright.sync_api import sync_playwright

    settings = get_settings()
    storage = SupabaseStorage(settings)
    if not dry_run:
        storage.ensure_bucket()

    active_concepts = list(
        db.scalars(
            select(BenefitConcept)
            .where(BenefitConcept.status == "active")
            .order_by(BenefitConcept.sort_order.nulls_last(), BenefitConcept.concept_key)
        ).all()
    )

    profile_name = "Design 2 Vector Icons"
    profile_slug = "design-2-vector-icons"
    asset_category = "Design 2 Vector Icons"

    # Deactivate old visual profiles & create/get Design 2 Vector Icons profile
    for gp in db.scalars(select(GlobalBenefitProfile)).all():
        gp.is_active = gp.slug == profile_slug

    profile = db.scalar(select(GlobalBenefitProfile).where(GlobalBenefitProfile.slug == profile_slug))
    if profile is None:
        profile = GlobalBenefitProfile(
            id=new_id(),
            name=profile_name,
            slug=profile_slug,
            description="Crisp #1D1D1B + #E52320 flat vector icons matching Design 2 quotations.",
            asset_category=asset_category,
            is_active=True,
            status="active",
        )
        db.add(profile)
        db.flush()
    else:
        profile.name = profile_name
        profile.asset_category = asset_category
        profile.is_active = True
        profile.status = "active"

    # Archive legacy benefit_art rows so /builder/assets stays clean (keep Logos & backgrounds)
    legacy_cats = {"global benefits v3 2d no bg", "Global benefits v2 2d", "Global Benefits 3D v1"}
    archived_old = 0
    for old_asset in db.scalars(
        select(BusinessAsset).where(
            BusinessAsset.asset_kind == "benefit_art",
            BusinessAsset.category != asset_category,
            BusinessAsset.status != "archived",
        )
    ).all():
        if (old_asset.category or "") in legacy_cats or (old_asset.category or "").lower().startswith("global benefit"):
            old_asset.status = "archived"
            archived_old += 1

    # Clear existing mappings on Design 2 profile to rebuild cleanly
    db.execute(delete(GlobalBenefitProfileAsset).where(GlobalBenefitProfileAsset.profile_id == profile.id))

    existing_assets_by_key = {
        a.asset_key: a
        for a in db.scalars(
            select(BusinessAsset).where(BusinessAsset.category == asset_category)
        ).all()
    }

    uploaded_count = 0
    mapped_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=1)
        try:
            for concept in active_concepts:
                svg_markup = render_design2_icon_svg(concept.concept_key, size=512)
                html = (
                    "<!doctype html><html><body style='margin:0;padding:0;width:512px;height:512px;"
                    "background:transparent;display:flex;align-items:center;justify-content:center;'>"
                    f"{svg_markup}</body></html>"
                )
                page.set_content(html)
                png_bytes = page.screenshot(type="png", omit_background=True)
                filename = f"{concept.concept_key}.png"
                tech = validate_image_bytes(
                    png_bytes,
                    filename,
                    max_bytes=settings.max_asset_bytes,
                    max_pixels=settings.max_asset_pixels,
                )
                content_hash = tech["content_hash"]
                asset_key = f"design2-vector:{concept.concept_key}"
                existing = existing_assets_by_key.get(asset_key)

                if existing and existing.content_hash == content_hash and existing.status == "active":
                    asset = existing
                else:
                    orig_path = f"assets/original/{content_hash[:2]}/{content_hash}.png"
                    if not dry_run:
                        storage.upload_asset(orig_path, png_bytes, "image/png")
                    deriv_manifest = {}
                    for dprof, mw, mh, q in (("ui", 512, 512, 85), ("pdf", 1600, 1600, 92)):
                        d = create_derivative(png_bytes, max_width=mw, max_height=mh, quality=q)
                        d_ext = "png" if d.content_type == "image/png" else "webp"
                        d_path = f"assets/derivative/{dprof}/{d.content_hash[:2]}/{d.content_hash}.{d_ext}"
                        if not dry_run:
                            storage.upload_asset(d_path, d.data, d.content_type)
                        deriv_manifest[dprof] = {
                            "storage_path": d_path,
                            "content_type": d.content_type,
                            "content_hash": d.content_hash,
                            "width_px": d.width_px,
                            "height_px": d.height_px,
                        }
                    if existing:
                        existing.label = concept.label
                        existing.original_filename = filename
                        existing.content_type = tech["content_type"]
                        existing.content_hash = content_hash
                        existing.storage_path = orig_path
                        existing.size_bytes = tech["size_bytes"]
                        existing.width_px = tech["width_px"]
                        existing.height_px = tech["height_px"]
                        existing.has_transparency = True
                        existing.derivative_manifest = deriv_manifest
                        existing.status = "active"
                        existing.revision += 1
                        asset = existing
                    else:
                        asset = BusinessAsset(
                            id=new_id(),
                            asset_key=asset_key,
                            asset_kind="benefit_art",
                            category=asset_category,
                            label=concept.label,
                            original_filename=filename,
                            content_type=tech["content_type"],
                            content_hash=content_hash,
                            storage_path=orig_path,
                            size_bytes=tech["size_bytes"],
                            width_px=tech["width_px"],
                            height_px=tech["height_px"],
                            has_transparency=True,
                            derivative_manifest=deriv_manifest,
                            revision=1,
                            status="active",
                        )
                        db.add(asset)
                        db.flush()
                    uploaded_count += 1

                concept.default_asset_id = asset.id
                db.add(
                    GlobalBenefitProfileAsset(
                        id=new_id(),
                        profile_id=profile.id,
                        concept_id=concept.id,
                        asset_id=asset.id,
                    )
                )
                mapped_count += 1
        finally:
            browser.close()

    return {
        "active_concepts": len(active_concepts),
        "uploaded_or_updated_assets": uploaded_count,
        "mapped_profile_assets": mapped_count,
        "archived_legacy_assets": archived_old,
    }


def _latest_rev(db, catalog_id: str) -> BenefitCatalogRevision | None:
    revs = list(
        db.scalars(
            select(BenefitCatalogRevision)
            .where(BenefitCatalogRevision.catalog_id == catalog_id, BenefitCatalogRevision.is_archived.is_(False))
            .order_by(BenefitCatalogRevision.revision_number.desc())
        ).all()
    )
    return revs[0] if revs else None


def _set_catalog_offerings(
    db,
    catalog: BenefitCatalog,
    concepts_by_key: dict[str, BenefitConcept],
    *,
    box1_specs: list[tuple[str, str | None, str | None]],
    box2_specs: list[tuple[str, str | None, str | None]],
) -> None:
    """Replace offerings on catalog's latest revision cleanly with exact Box 1 & Box 2 specs.

    Each spec is (concept_key, display_value, description_override).
    For packaged catalogs (with catalog.package_id), ensures a matching `comprehensive`
    BenefitPackage exists in the latest revision and links `catalog.package_id` + `applies_to_id`.
    """
    rev = _latest_rev(db, catalog.id)
    if rev is None:
        rev = BenefitCatalogRevision(
            id=new_id(),
            catalog_id=catalog.id,
            revision_number=1,
            state="published",
            source_document_ids=[],
            content_hash="",
            published_at=utcnow(),
            is_archived=False,
        )
        db.add(rev)
        db.flush()
    rev.state = "published"
    rev.published_at = rev.published_at or utcnow()
    catalog.status = "published"

    pkg_id = None
    applies_type = None
    if catalog.package_id is not None:
        pkgs = list(
            db.scalars(
                select(BenefitPackage).where(
                    BenefitPackage.catalog_revision_id == rev.id,
                    BenefitPackage.package_kind == "comprehensive",
                    BenefitPackage.status == "active",
                )
            ).all()
        )
        if pkgs:
            pkg = next((p for p in pkgs if p.id == catalog.package_id), pkgs[0])
        else:
            pkg = BenefitPackage(
                id=new_id(),
                catalog_revision_id=rev.id,
                package_key=_slug(catalog.name) or "package",
                name=catalog.name,
                package_kind="comprehensive",
                sort_order=1,
                status="active",
            )
            db.add(pkg)
            db.flush()
        catalog.package_id = pkg.id
        pkg_id = pkg.id
        applies_type = "package"

    # Remove BenefitPackagePlanItem rows referencing offerings in this rev before deleting offerings
    old_offs = list(db.scalars(select(CatalogOffering).where(CatalogOffering.catalog_revision_id == rev.id)).all())
    old_off_ids = [o.id for o in old_offs]
    if old_off_ids:
        db.execute(delete(BenefitPackagePlanItem).where(BenefitPackagePlanItem.offering_id.in_(old_off_ids)))
        # Nullify catalog_offering_id on historical draft_benefit_selections only? No! Keep referenced rows, update in place or delete unreferenced.
        referenced_ids = set(
            db.scalars(
                select(DraftBenefitSelection.catalog_offering_id).where(
                    DraftBenefitSelection.catalog_offering_id.in_(old_off_ids)
                )
            ).all()
        )
    else:
        referenced_ids = set()

    existing_by_ck: dict[str, list[CatalogOffering]] = defaultdict(list)
    for o in old_offs:
        existing_by_ck[o.concept_id].append(o)

    desired: list[tuple[str, str, str, str | None, str | None, int]] = []
    idx = 1
    for ck, dv, desc in box1_specs:
        desired.append((ck, "base", "included", dv, desc, idx))
        idx += 1
    for ck, dv, desc in box2_specs:
        desired.append((ck, "optional", "addon_option", dv, desc, idx))
        idx += 1

    assignments: list[tuple[CatalogOffering | None, str, str, str, str, str | None, str | None, int]] = []
    kept_ids: set[str] = set()
    used_keys: set[str] = set()
    for ck, kind, role, dv, desc, sort_ord in desired:
        concept = concepts_by_key.get(ck)
        if not concept:
            continue
        off_key = f"{_slug(catalog.name)[:40]}:{ck}" if pkg_id else ck
        if off_key in used_keys:
            off_key = f"{off_key}:{sort_ord}"
        used_keys.add(off_key)
        candidates = existing_by_ck.get(concept.id) or []
        reuse = (
            next((c for c in candidates if c.id not in kept_ids and c.offering_key == off_key), None)
            or next((c for c in candidates if c.id not in kept_ids), None)
        )
        if reuse is not None:
            kept_ids.add(reuse.id)
        assignments.append((reuse, off_key, concept.id, kind, role, dv, desc, sort_ord))

    # Remove or retire unkept offerings first so their offering_keys never collide
    for o in old_offs:
        if o.id not in kept_ids:
            if o.id in referenced_ids:
                o.status = "retired"
                o.offering_key = f"retired-{o.id[:8]}-{o.offering_key}"[:120]
            else:
                db.delete(o)
    db.flush()

    # Park kept offerings whose key needs changing onto unique temporary keys first
    for reuse, off_key, *_ in assignments:
        if reuse is not None and reuse.offering_key != off_key:
            reuse.offering_key = f"tmp-{reuse.id}"[:120]
    db.flush()

    for reuse, off_key, concept_id, kind, role, dv, desc, sort_ord in assignments:
        if reuse is not None:
            reuse.offering_key = off_key
            reuse.offering_kind = kind
            reuse.role = role
            reuse.applies_to_type = applies_type
            reuse.applies_to_id = pkg_id
            reuse.display_value = dv
            reuse.typed_value = None
            reuse.optional_price = None
            reuse.description_override = desc
            reuse.label_override = None
            reuse.sort_order = sort_ord
            reuse.status = "active"
        else:
            o = CatalogOffering(
                id=new_id(),
                catalog_revision_id=rev.id,
                offering_key=off_key,
                concept_id=concept_id,
                offering_kind=kind,
                applies_to_type=applies_type,
                applies_to_id=pkg_id,
                role=role,
                label_override=None,
                description_override=desc,
                typed_value=None,
                display_value=dv,
                optional_price=None,
                source_aliases=[],
                source_citation={},
                presentation_facet_ids=[],
                sort_order=sort_ord,
                status="active",
            )
            db.add(o)
    db.flush()


def standardize_catalogs_and_rules(db) -> dict:
    """Clean concepts, conditions, rules, all 10 insurers, and clone Kurnia & Liberty."""
    stats: dict[str, int] = defaultdict(int)

    # 1. Concept hygiene
    pillion = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == "legal-liability-to-pillion"))
    if pillion:
        pillion.status = "active"
        pillion.label = "Legal Liability to Pillion"
        pillion.description = "Covers legal liability for death or bodily injury to your motorcycle pillion rider."
        pillion.sort_order = 27
        pillion.value_schema = {"category": "addon", "type": "boolean"}

    tpbi = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == "third-party-bi"))
    tpbi_dup = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == "third-party-bodily-injury"))
    tppd = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == "third-party-property"))
    tppd_dup = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == "third-party-property-damage"))
    pa_ret = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == "personal-accident"))
    pa_act = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == "accidental-death"))

    migrations_map = []
    if tpbi and tpbi_dup:
        migrations_map.append((tpbi_dup, tpbi))
    if tppd and tppd_dup:
        migrations_map.append((tppd_dup, tppd))
    if pa_act and pa_ret:
        migrations_map.append((pa_ret, pa_act))

    for old_c, new_c in migrations_map:
        for o in db.scalars(select(CatalogOffering).where(CatalogOffering.concept_id == old_c.id)).all():
            o.concept_id = new_c.id
            stats["migrated_concept_offerings"] += 1
        for sel in db.scalars(select(DraftBenefitSelection).where(DraftBenefitSelection.concept_id == old_c.id)).all():
            sel.concept_id = new_c.id
        old_c.status = "retired"

    # Mark all active concepts' value_schema.category cleanly for the UI Category 1 vs Category 2
    # Wait: preserve existing sort_order / value_schema unless missing; ensure pillion is addon.
    db.flush()

    concepts_by_key = {c.concept_key: c for c in db.scalars(select(BenefitConcept)).all()}
    companies_by_slug = {c.slug: c for c in db.scalars(select(InsuranceCompany)).all()}
    segments_by_key = {s.segment_key: s for s in db.scalars(select(Segment)).all()}
    vcats_by_key = {v.category_key: v for v in db.scalars(select(VehicleCategory)).all()}
    covs_by_key = {c.coverage_key: c for c in db.scalars(select(CoverageType)).all()}

    priv_seg = segments_by_key.get("private")
    comm_seg = segments_by_key.get("commercial")
    car_vcat = vcats_by_key.get("car")
    moto_vcat = vcats_by_key.get("motorcycle")
    lorry_vcat = vcats_by_key.get("lorry")
    comp_cov = covs_by_key.get("comprehensive")
    tpft_cov = covs_by_key.get("tpft")
    tpo_cov = covs_by_key.get("third_party")

    # 2. Delete all legacy inactive company_benefit_conditions
    del_conds = db.execute(delete(CompanyBenefitCondition).where(CompanyBenefitCondition.is_active.is_(False)))
    stats["deleted_legacy_conditions"] = del_conds.rowcount or 0

    # 3. Clear ALL baseline_cost in company_benefit_configs & standardize Betterment descriptions
    betterment_cid = concepts_by_key["betterment-protection"].id
    ten_yr_slugs = {"lonpac", "takaful-malaysia", "qbe"}
    for cfg in db.scalars(select(CompanyBenefitConfig)).all():
        cfg.baseline_cost = None
        stats["cleared_baseline_costs"] += 1

    for slug, co in companies_by_slug.items():
        if slug == "mmip":
            continue
        for cfg in db.scalars(
            select(CompanyBenefitConfig).where(
                CompanyBenefitConfig.company_id == co.id,
                CompanyBenefitConfig.concept_id == betterment_cid,
            )
        ).all():
            if slug == "qbe":
                cfg.baseline_description = "0% betterment deduction on new original replacement parts for vehicles up to 10 years old."
            elif slug in ten_yr_slugs:
                cfg.baseline_description = "Waives betterment contribution on new original replacement parts for vehicles up to 10 years old."
            else:
                cfg.baseline_description = "Waives betterment contribution on new original replacement parts for vehicles up to 15 years old."

    # 4. Enforce TPO = MMIP ONLY across catalogs and products
    if tpo_cov:
        for cat in db.scalars(
            select(BenefitCatalog).where(
                BenefitCatalog.coverage_type_id == tpo_cov.id,
                BenefitCatalog.status != "archived",
            )
        ).all():
            co_slug = next((s for s, c in companies_by_slug.items() if c.id == cat.company_id), "")
            if co_slug != "mmip":
                cat.status = "archived"
                stats["archived_non_mmip_tpo"] += 1
        for prod in db.scalars(select(InsuranceProduct).where(InsuranceProduct.status != "archived")).all():
            co_slug = next((s for s, c in companies_by_slug.items() if c.id == prod.company_id), "")
            if co_slug != "mmip" and ("third party)" in (prod.name or "").lower() or "(third party" in (prod.name or "").lower()):
                if "fire" not in (prod.name or "").lower() and "tpft" not in (prod.name or "").lower():
                    prod.status = "archived"

    # 5. Backfill segment_id on all remaining non-archived non-MMIP catalogs (Lorry = Commercial; EV Car/Moto = Private)
    for cat in db.scalars(select(BenefitCatalog).where(BenefitCatalog.status != "archived")).all():
        co_slug = next((s for s, c in companies_by_slug.items() if c.id == cat.company_id), "")
        if co_slug == "mmip":
            continue
        if lorry_vcat and cat.vehicle_category_id == lorry_vcat.id and comm_seg:
            if cat.segment_id != comm_seg.id:
                cat.segment_id = comm_seg.id
                stats["fixed_lorry_segment"] += 1
        elif cat.segment_id is None and priv_seg:
            cat.segment_id = priv_seg.id
            stats["backfilled_private_segment"] += 1

    # 6. Archive duplicate/overlapping Private Car & Motorcycle catalogs so each insurer has 1 canonical per scenario
    archive_names_by_slug: dict[str, set[str]] = {
        "amassurance": {
            "Standard Motorcycle Comprehensive",
            "Standard Motorcycle Comprehensive (TPFT)",
            "auto365 TPFT Premier",
        },
        "berjaya-sompo": {
            "SOMPO Motor Comprehensive",
            "Private Car Comprehensive (TPFT)",
            "Motorcycle Comprehensive",
            "Motorcycle Comprehensive (TPFT)",
        },
        "tune-protect": {
            "Tune Protect Motor Easy",
            "Motor Easy + Motor Bundle",
            "Tune Protect Motor Easy (TPFT)",
            "Motorcycle Policy (Private)",
            "Motorcycle Policy (Private) (TPFT)",
        },
        "takaful-malaysia": {
            "myClick Takaful Car",
        },
        "qbe": {
            "Commercial Vehicle Protector",
        },
    }
    for slug, names in archive_names_by_slug.items():
        co = companies_by_slug.get(slug)
        if not co:
            continue
        for cat in db.scalars(
            select(BenefitCatalog).where(
                BenefitCatalog.company_id == co.id,
                BenefitCatalog.status != "archived",
            )
        ).all():
            if cat.name in names:
                cat.status = "archived"
                stats["archived_duplicate_catalogs"] += 1
        for prod in db.scalars(
            select(InsuranceProduct).where(
                InsuranceProduct.company_id == co.id,
                InsuranceProduct.status != "archived",
            )
        ).all():
            if prod.name in names:
                prod.status = "archived"

    # Deduplicate exact identical AmAssurance Auto365 Comprehensive Lite (TPFT) rows
    am_co = companies_by_slug.get("amassurance")
    if am_co:
        seen_am_tpft = False
        for cat in db.scalars(
            select(BenefitCatalog).where(
                BenefitCatalog.company_id == am_co.id,
                BenefitCatalog.name == "Auto365 Comprehensive Lite (TPFT)",
                BenefitCatalog.status != "archived",
            ).order_by(BenefitCatalog.created_at)
        ).all():
            if not seen_am_tpft:
                seen_am_tpft = True
            else:
                cat.status = "archived"
                stats["archived_duplicate_catalogs"] += 1

    db.flush()

    # 7. Standardize AmAssurance Private Car Comprehensive (3 ICE + 3 EV tiers) & Motorcycle/TPFT first
    if am_co:
        am_tier_towing = {
            "auto365 Comprehensive Lite": ("50 km", "24/7 emergency accident and breakdown towing assistance up to 50 km."),
            "auto365 Comprehensive Lite (EV)": ("50 km", "24/7 emergency accident and breakdown towing assistance up to 50 km."),
            "auto365 Comprehensive Plus": ("100 km", "24/7 emergency accident and breakdown towing assistance up to 100 km."),
            "auto365 Comprehensive Plus (EV)": ("100 km", "24/7 emergency accident and breakdown towing assistance up to 100 km."),
            "auto365 Comprehensive Premier": ("365 km", "24/7 emergency accident and breakdown towing assistance up to 365 km."),
            "auto365 Comprehensive Premier (EV)": ("365 km", "24/7 emergency accident and breakdown towing assistance up to 365 km."),
        }
        am_ice_box2 = [
            ("betterment-protection", "Up to 15 Years", "Waives betterment contribution on new original replacement parts for vehicles up to 15 years old."),
            ("windscreen", None, None),
            ("special-perils", None, None),
            ("strike-riot-civil-commotion", None, None),
            ("legal-liability-to-passengers", None, None),
            ("legal-liability-of-passengers", None, None),
            ("repair-allowance", None, None),
            ("ncd-relief", None, None),
            ("e-hailing-extension", None, None),
            ("private-car-365", None, None),
            ("driver-passenger-protector", None, None),
        ]
        am_ev_box2 = am_ice_box2 + [
            ("ev-wall-charger", None, "Covers accidental damage, fire, or theft of home EV wallbox charger."),
            ("ev-home-charger-liability", None, "Third-party liability for bodily injury or property damage from home EV charger."),
            ("ev-battery-depletion-towing", None, "Emergency flatbed recovery towing to nearest public EV charging station."),
        ]
        for cat in db.scalars(
            select(BenefitCatalog).where(
                BenefitCatalog.company_id == am_co.id,
                BenefitCatalog.status != "archived",
            )
        ).all():
            if cat.name in am_tier_towing:
                lim, tow_desc = am_tier_towing[cat.name]
                b1 = [
                    ("legal-costs-defense", None, "Reimburses court legal representation and defense fees up to RM2,000."),
                    ("repair-workmanship-warranty", None, "3-year warranty on repair workmanship carried out by approved panel repairers."),
                    ("towing", lim, tow_desc),
                ]
                b2 = am_ev_box2 if cat.engine_type == "ev" else am_ice_box2
                _set_catalog_offerings(db, cat, concepts_by_key, box1_specs=b1, box2_specs=b2)
                stats["standardized_am_car"] += 1

        # Publish AmAssurance Motorcycle365 TPFT draft if present
        for cat in db.scalars(
            select(BenefitCatalog).where(
                BenefitCatalog.company_id == am_co.id,
                BenefitCatalog.status == "draft",
            )
        ).all():
            cat.status = "published"
            rev = _latest_rev(db, cat.id)
            if rev:
                rev.state = "published"
                rev.published_at = rev.published_at or utcnow()

    # 8. Standardize Private Car Comprehensive (ICE & EV) for Tune Protect, Berjaya Sompo, Lonpac, QBE, Etiqa, Takaful Malaysia
    insurer_car_specs: dict[str, dict] = {
        "tune-protect": {
            "ice_name": "Tune Protect Motor Easy (Private Car)",
            "ev_name": "Tune Protect Private Car Comprehensive (EV)",
            "box1": [
                ("legal-costs-defense", None, "Reimburses court legal representation and defense fees up to RM2,000."),
                ("payd-telematics", None, "Cash rebate up to 30% of basic premium for low annual vehicle mileage driving."),
                ("towing", "RM 300", "24/7 emergency accident towing assistance to nearest workshop up to RM 300."),
            ],
            "box2_ice": [
                ("all-drivers", None, None),
                ("betterment-protection", "Up to 15 Years", "Waives betterment contribution on new original replacement parts for vehicles up to 15 years old."),
                ("windscreen", None, None),
                ("special-perils", None, None),
                ("strike-riot-civil-commotion", None, None),
                ("legal-liability-to-passengers", None, None),
                ("legal-liability-of-passengers", None, None),
                ("repair-allowance", None, None),
                ("vehicle-accessories", None, None),
                ("cross-border", None, None),
                ("ferry-transit", None, None),
                ("motorshield-bundle", None, None),
                ("auto-buddy-malaysia", None, None),
                ("motor-easy", None, None),
            ],
            "ev_extras": [
                ("ev-wall-charger", None, "Covers accidental damage, fire, or theft of home EV wallbox charger."),
                ("ev-home-charger-liability", None, "Third-party liability for bodily injury or property damage from home EV charger."),
                ("ev-battery-depletion-towing", None, "Emergency flatbed recovery towing to nearest public EV charging station."),
            ],
        },
        "berjaya-sompo": {
            "ice_name": "SOMPO Motor (Private Car Non-Tariff)",
            "ev_name": "Berjaya Sompo Private Car Comprehensive (EV)",
            "box1": [
                ("agreed-value-market-value", None, None),
                ("all-drivers", None, None),
                ("legal-costs-defense", None, "Reimburses court legal representation and defense fees up to RM2,000."),
                ("repair-workmanship-warranty", None, None),
                ("special-perils", None, "Full protection against flood, typhoon, storm, landslide, and natural disasters built in."),
                ("towing", "Unlimited", "24/7 emergency unlimited towing assistance across Malaysia."),
            ],
            "box2_ice": [
                ("betterment-protection", "Up to 15 Years", "Waives betterment contribution on new original replacement parts for vehicles up to 15 years old."),
                ("windscreen", None, None),
                ("strike-riot-civil-commotion", None, None),
                ("legal-liability-to-passengers", None, None),
                ("legal-liability-of-passengers", None, None),
                ("repair-allowance", None, None),
                ("ncd-relief", None, None),
                ("e-hailing-extension", None, None),
                ("accidental-death", None, None),
                ("sompo-motor-nhancer", None, None),
                ("driver-passenger-protector", None, None),
            ],
            "ev_extras": [
                ("ev-wall-charger", None, "Covers accidental damage, fire, or theft of home EV wallbox charger."),
                ("ev-home-charger-liability", None, "Third-party liability for bodily injury or property damage from home EV charger."),
                ("ev-battery-depletion-towing", None, "Emergency flatbed recovery towing to nearest public EV charging station."),
            ],
        },
        "lonpac": {
            "ice_name": "Private Car Secure",
            "ev_name": "Lonpac Insurance Private Car Comprehensive (EV)",
            "box1": [
                ("all-drivers", None, None),
                ("legal-costs-defense", None, "Reimburses court legal representation and defense fees up to RM2,000."),
                ("natural-falling-objects", None, None),
                ("document-replacement", None, None),
                ("towing", "RM 200", "24/7 emergency accident towing assistance to nearest approved repairer up to RM 200."),
            ],
            "box2_ice": [
                ("betterment-protection", "Up to 10 Years", "Waives betterment contribution on new original replacement parts for vehicles up to 10 years old."),
                ("windscreen", None, None),
                ("special-perils", None, None),
                ("strike-riot-civil-commotion", None, None),
                ("legal-liability-to-passengers", None, None),
                ("legal-liability-of-passengers", None, None),
                ("repair-allowance", None, None),
                ("ncd-relief", None, None),
                ("key-replacement", None, None),
                ("car-detailing-cleanup", None, None),
                ("repaint-spray-paint", None, None),
                ("vehicle-accessories", None, None),
                ("increased-tppd", None, None),
                ("e-hailing-extension", None, None),
                ("gas-conversion-kit", None, None),
                ("smart-driver-pa", None, None),
            ],
            "ev_extras": [
                ("lonpac-ev-smart-pack", None, None),
                ("ev-wall-charger", None, "Covers accidental damage, fire, or theft of home EV wallbox charger."),
                ("ev-home-charger-liability", None, "Third-party liability for bodily injury or property damage from home EV charger."),
                ("ev-battery-depletion-towing", None, "Emergency flatbed recovery towing to nearest public EV charging station."),
            ],
        },
        "qbe": {
            "ice_name": "Private Car Protector",
            "ev_name": "QBE Private Car Comprehensive (EV)",
            "box1": [
                ("all-drivers", None, None),
                ("betterment-protection", "Up to 10 Years", "0% betterment deduction on new original replacement parts for vehicles up to 10 years old."),
                ("key-replacement", None, None),
                ("legal-costs-defense", None, None),
                ("total-loss-theft-allowance", None, None),
                ("towing", "RM 500", "24/7 emergency accident towing assistance up to RM 500."),
            ],
            "box2_ice": [
                ("windscreen", None, None),
                ("special-perils", None, None),
                ("first-loss-flood", None, None),
                ("strike-riot-civil-commotion", None, None),
                ("legal-liability-to-passengers", None, None),
                ("legal-liability-of-passengers", None, None),
                ("repair-allowance", None, None),
                ("ncd-relief", None, None),
                ("car-detailing-cleanup", None, None),
                ("out-of-pocket-allowance", None, None),
                ("vehicle-accessories", None, None),
                ("driver-passenger-protector", None, None),
            ],
            "ev_extras": [
                ("ev-wall-charger", None, "Covers accidental damage, fire, or theft of home EV wallbox charger."),
                ("ev-home-charger-liability", None, "Third-party liability for bodily injury or property damage from home EV charger."),
                ("ev-battery-depletion-towing", None, "Emergency flatbed recovery towing to nearest public EV charging station."),
            ],
        },
        "etiqa": {
            "ice_name": "Comprehensive Private Car Insurance / Takaful",
            "ev_name": "Etiqa Private Car Comprehensive (EV)",
            "box1": [
                ("all-drivers", None, None),
                ("legal-costs-defense", None, "Reimburses court legal representation and defense fees up to RM2,000."),
                ("payd-telematics", None, None),
                ("towing", "200 km", "24/7 emergency accident and breakdown towing assistance up to 200 km."),
            ],
            "box2_ice": [
                ("betterment-protection", "Up to 15 Years", "Waives betterment contribution on new original replacement parts for vehicles up to 15 years old."),
                ("windscreen", None, None),
                ("special-perils", None, None),
                ("strike-riot-civil-commotion", None, None),
                ("legal-liability-to-passengers", None, None),
                ("legal-liability-of-passengers", None, None),
                ("repair-allowance", None, None),
                ("ncd-relief", None, None),
                ("child-car-seat", None, None),
                ("key-replacement", None, None),
                ("repaint-spray-paint", None, None),
                ("driver-passenger-protector", None, None),
            ],
            "ev_extras": [
                ("ev-wall-charger", None, "Covers accidental damage, fire, or theft of home EV wallbox charger."),
                ("ev-home-charger-liability", None, "Third-party liability for bodily injury or property damage from home EV charger."),
                ("ev-battery-depletion-towing", None, "Emergency flatbed recovery towing to nearest public EV charging station."),
            ],
        },
        "takaful-malaysia": {
            "ice_name": "Takaful myMotor (Private Car)",
            "ev_name": "Takaful Malaysia Private Car Comprehensive (EV)",
            "box1": [
                ("agreed-value-market-value", None, None),
                ("all-drivers", None, None),
                ("cashback-no-claim", None, None),
                ("legal-costs-defense", None, "Reimburses court legal representation and defense fees up to RM2,000."),
                ("accidental-death", None, None),
                ("towing", "50 km", "24/7 emergency accident and breakdown towing assistance up to 50 km."),
            ],
            "box2_ice": [
                ("betterment-protection", "Up to 10 Years", "Waives betterment contribution on new original replacement parts for vehicles up to 10 years old."),
                ("windscreen", None, None),
                ("special-perils", None, None),
                ("strike-riot-civil-commotion", None, None),
                ("legal-liability-to-passengers", None, None),
                ("legal-liability-of-passengers", None, None),
                ("motor-pa-plus", None, None),
            ],
            "ev_extras": [
                ("ev-wall-charger", None, "Covers accidental damage, fire, or theft of home EV wallbox charger."),
                ("ev-home-charger-liability", None, "Third-party liability for bodily injury or property damage from home EV charger."),
                ("ev-battery-depletion-towing", None, "Emergency flatbed recovery towing to nearest public EV charging station."),
            ],
        },
    }

    for slug, spec in insurer_car_specs.items():
        co = companies_by_slug.get(slug)
        if not co:
            continue
        for eng, cname in (("ice", spec["ice_name"]), ("ev", spec["ev_name"])):
            cat = db.scalar(
                select(BenefitCatalog).where(
                    BenefitCatalog.company_id == co.id,
                    BenefitCatalog.name == cname,
                    BenefitCatalog.status != "archived",
                )
            )
            if cat:
                b2 = list(spec["box2_ice"])
                if eng == "ev":
                    # Remove gas-conversion-kit on EV
                    b2 = [x for x in b2 if x[0] != "gas-conversion-kit"] + list(spec["ev_extras"])
                _set_catalog_offerings(db, cat, concepts_by_key, box1_specs=spec["box1"], box2_specs=b2)
                stats["standardized_other_car"] += 1

    # 9. Publish QBE & Etiqa remaining draft catalogs (Commercial Car & Motorcycle Comp/TPFT)
    for slug in ("qbe", "etiqa"):
        co = companies_by_slug.get(slug)
        if not co:
            continue
        for cat in db.scalars(
            select(BenefitCatalog).where(
                BenefitCatalog.company_id == co.id,
                BenefitCatalog.status.in_(["draft", "active"]),
            )
        ).all():
            cat.status = "published"
            rev = _latest_rev(db, cat.id)
            if rev:
                rev.state = "published"
                rev.published_at = rev.published_at or utcnow()

    # Set any non-archived 'active' status catalogs to 'published'
    for cat in db.scalars(select(BenefitCatalog).where(BenefitCatalog.status == "active")).all():
        cat.status = "published"

    # 10. Sanitize ALL non-archived non-MMIP catalogs across TPFT, Motorcycle, Lorry, Commercial Car, and clear prices/retired concepts
    retired_ids = {c.id for c in db.scalars(select(BenefitConcept).where(BenefitConcept.status != "active")).all()}
    ev_only_keys = {
        "ev-battery-depletion-towing", "ev-charging-bodily-injury",
        "ev-home-charger-liability", "ev-home-content-fire",
        "ev-wall-charger", "lonpac-ev-smart-pack",
    }
    comp_only_keys = {
        "own-damage", "windscreen", "special-perils", "first-loss-flood",
        "betterment-protection", "repair-allowance", "agreed-value-market-value",
        "repaint-spray-paint", "side-mirror-protection", "car-detailing-cleanup",
        "child-car-seat", "key-replacement", "flood-relief-allowance",
        "out-of-pocket-allowance", "natural-falling-objects", "ncd-relief",
        "payd-telematics", "ev-wall-charger", "ev-battery-depletion-towing",
    }
    moto_forbidden_keys = {
        "windscreen", "e-hailing-extension", "repaint-spray-paint",
        "payd-telematics", "sompo-motor-nhancer", "child-car-seat",
        "ev-wall-charger", "ev-home-charger-liability",
        "legal-liability-to-passengers", "legal-liability-of-passengers",
        "betterment-protection", "private-car-365", "auto-buddy-malaysia",
        "oto-360", "car-detailing-cleanup", "side-mirror-protection",
    }
    lorry_forbidden_keys = {
        "e-hailing-extension", "child-car-seat", "payd-telematics",
        "sompo-motor-nhancer", "private-car-365", "auto-buddy-malaysia",
        "oto-360",
    }

    towing_cid = concepts_by_key["towing"].id
    llop_cid = concepts_by_key["legal-liability-of-passengers"].id
    pillion_cid = concepts_by_key["legal-liability-to-pillion"].id

    for cat in db.scalars(select(BenefitCatalog).where(BenefitCatalog.status != "archived")).all():
        co_slug = next((s for s, c in companies_by_slug.items() if c.id == cat.company_id), "")
        if co_slug == "mmip":
            continue
        rev = _latest_rev(db, cat.id)
        if not rev:
            continue
        cat.status = "published"
        rev.state = "published"
        rev.published_at = rev.published_at or utcnow()
        is_tpft = bool(tpft_cov and cat.coverage_type_id == tpft_cov.id)
        is_moto = bool(moto_vcat and cat.vehicle_category_id == moto_vcat.id)
        is_lorry = bool(lorry_vcat and cat.vehicle_category_id == lorry_vcat.id)
        is_ev = (cat.engine_type or "ice").lower() == "ev"

        offs = list(
            db.scalars(
                select(CatalogOffering)
                .where(CatalogOffering.catalog_revision_id == rev.id, CatalogOffering.status == "active")
                .order_by(CatalogOffering.sort_order, CatalogOffering.id)
            ).all()
        )
        ref_ids = set(
            db.scalars(
                select(DraftBenefitSelection.catalog_offering_id).where(
                    DraftBenefitSelection.catalog_offering_id.in_([o.id for o in offs])
                )
            ).all()
        ) if offs else set()

        seen_concept_ids: set[str] = set()
        has_pillion = False
        for o in offs:
            c = next((x for x in concepts_by_key.values() if x.id == o.concept_id), None)
            ck = c.concept_key if c else ""
            drop = False
            if o.concept_id in retired_ids:
                drop = True
            elif o.concept_id in seen_concept_ids:
                drop = True
            elif not is_ev and ck in ev_only_keys:
                drop = True
            elif is_ev and ck == "gas-conversion-kit":
                drop = True
            elif is_tpft and ck in comp_only_keys:
                drop = True
            elif is_moto and ck in moto_forbidden_keys:
                drop = True
            elif is_lorry and ck in lorry_forbidden_keys:
                drop = True

            if drop:
                if o.id in ref_ids:
                    o.status = "retired"
                else:
                    db.execute(delete(BenefitPackagePlanItem).where(BenefitPackagePlanItem.offering_id == o.id))
                    db.delete(o)
                stats["cleaned_invalid_offerings"] += 1
                continue

            seen_concept_ids.add(o.concept_id)
            if o.concept_id == pillion_cid:
                has_pillion = True

            # Fix QBE Lorry LLOP in Box 1 -> move to Box 2
            if o.concept_id == llop_cid and o.offering_kind == "base":
                o.offering_kind = "optional"
                o.role = "addon_option"

            # Fix Berjaya Sompo EV Lorry/Moto Special Perils in Box 1 -> move to Box 2 on Comp
            if co_slug == "berjaya-sompo" and (is_lorry or is_moto) and ck == "special-perils" and o.offering_kind == "base":
                o.offering_kind = "optional"
                o.role = "addon_option"

            # Fix non-standard `upgrade` leftover rows
            if o.offering_kind == "upgrade":
                o.offering_kind = "optional"
                o.role = "addon_option"

            # Strip ALL static prices and non-towing/non-betterment display values
            o.optional_price = None
            o.typed_value = None
            if o.concept_id == towing_cid:
                if o.offering_kind == "base":
                    # Ensure base towing display_value and description_override never contradict
                    dv = (o.display_value or "").strip()
                    if not dv or dv.lower() in {"6 months", "standard"}:
                        dv = "200 km"
                    o.display_value = dv
                    if dv.lower() == "unlimited":
                        o.description_override = "24/7 emergency unlimited towing assistance across Malaysia."
                    else:
                        o.description_override = f"24/7 emergency accident and breakdown towing assistance up to {dv}."
                else:
                    o.display_value = None
            elif o.concept_id == betterment_cid:
                if co_slug == "qbe":
                    o.display_value = "Up to 10 Years"
                    o.description_override = "0% betterment deduction on new original replacement parts for vehicles up to 10 years old."
                elif co_slug in ten_yr_slugs:
                    o.display_value = "Up to 10 Years"
                    o.description_override = "Waives betterment contribution on new original replacement parts for vehicles up to 10 years old."
                else:
                    o.display_value = "Up to 15 Years"
                    o.description_override = "Waives betterment contribution on new original replacement parts for vehicles up to 15 years old."
            else:
                o.display_value = None

        # Ensure Motorcycle catalogs have Legal Liability to Pillion in Box 2
        if is_moto and not has_pillion:
            db.add(
                CatalogOffering(
                    id=new_id(),
                    catalog_revision_id=rev.id,
                    offering_key="legal-liability-to-pillion",
                    concept_id=pillion_cid,
                    offering_kind="optional",
                    role="addon_option",
                    sort_order=50,
                    status="active",
                    source_aliases=[],
                    source_citation={},
                    presentation_facet_ids=[],
                )
            )
            stats["added_moto_pillion"] += 1

    db.flush()

    # 11. Rebuild Tune Protect & Berjaya Sompo CompanyBenefitBundles cleanly
    active_prof = db.scalar(select(BenefitProfile).where(BenefitProfile.is_active.is_(True)))
    if active_prof:
        tune_co = companies_by_slug.get("tune-protect")
        if tune_co:
            db.execute(delete(CompanyBenefitBundle).where(CompanyBenefitBundle.company_id == tune_co.id))
            tune_defs = [
                ("tune-motorshield-bundle", "MotorShield Multi-Pack", "motorshield-bundle", ["motor shield", "motorshield", "motorshield multi pack"], False, [("default", "Included", ["included", "motorshield"], True)]),
                ("tune-autobuddy-bundle", "AutoBuddy", "auto-buddy-malaysia", ["autobuddy", "auto buddy"], True, [
                    ("plan_a", "Plan A", ["plan a", "plan 1", "a"], True),
                    ("plan_b", "Plan B", ["plan b", "plan 2", "b"], False),
                    ("plan_c", "Plan C", ["plan c", "plan 3", "c"], False),
                    ("plan_d", "Plan D", ["plan d", "plan 4", "d"], False),
                    ("plan_e", "Plan E", ["plan e", "plan 5", "e"], False),
                ]),
                ("tune-motor-easy-bundle", "Motor Easy Bundle", "motor-easy", ["motor easy bundle", "motor easy"], False, [("default", "Included", ["included", "motor easy"], True)]),
            ]
            for idx, (bkey, bname, pck, aliases, has_tiers, tiers) in enumerate(tune_defs, start=1):
                pc = concepts_by_key[pck]
                bnd = CompanyBenefitBundle(
                    id=new_id(),
                    company_id=tune_co.id,
                    profile_id=active_prof.id,
                    bundle_key=bkey,
                    name=bname,
                    primary_concept_id=pc.id,
                    trigger_concept_ids=[pc.id],
                    match_aliases=aliases,
                    force_box2=True,
                    has_plan_tiers=has_tiers,
                    is_active=True,
                    sort_order=idx,
                )
                db.add(bnd)
                db.flush()
                for tidx, (tkey, tlbl, tokens, is_def) in enumerate(tiers, start=1):
                    bt = CompanyBenefitBundleTier(
                        id=new_id(),
                        bundle_id=bnd.id,
                        tier_key=tkey,
                        label=tlbl,
                        match_tokens=tokens,
                        is_default_fallback=is_def,
                        sort_order=tidx,
                    )
                    db.add(bt)
                    db.flush()
                    db.add(
                        CompanyBenefitBundleEffect(
                            id=new_id(),
                            tier_id=bt.id,
                            target_concept_id=towing_cid,
                            effect_type="upgrade_to_box2",
                            display_title="Unlimited Towing",
                            display_value="Unlimited",
                            display_description="24/7 emergency unlimited towing assistance across Malaysia.",
                            icon_hint="unlimited_towing",
                            comparison_value="Unlimited",
                            sort_order=1,
                        )
                    )

        sompo_co = companies_by_slug.get("berjaya-sompo")
        if sompo_co:
            existing_sompo_bnd = db.scalar(
                select(CompanyBenefitBundle).where(
                    CompanyBenefitBundle.company_id == sompo_co.id,
                    CompanyBenefitBundle.bundle_key == "sompo-motor-nhancer",
                )
            )
            if not existing_sompo_bnd:
                pc = concepts_by_key["sompo-motor-nhancer"]
                bnd = CompanyBenefitBundle(
                    id=new_id(),
                    company_id=sompo_co.id,
                    profile_id=active_prof.id,
                    bundle_key="sompo-motor-nhancer",
                    name="SOMPO Motor N-hancer",
                    primary_concept_id=pc.id,
                    trigger_concept_ids=[pc.id],
                    match_aliases=["sompo motor n-hancer", "sompo motor nhancer", "n-hancer", "ultima care"],
                    force_box2=True,
                    has_plan_tiers=True,
                    is_active=True,
                    sort_order=1,
                )
                db.add(bnd)
                db.flush()
                for tidx, (tkey, tlbl, tokens, is_def) in enumerate(
                    [("pack_1", "Pack 1", ["pack 1", "plan 1"], True), ("pack_2", "Pack 2", ["pack 2", "plan 2"], False)],
                    start=1,
                ):
                    bt = CompanyBenefitBundleTier(
                        id=new_id(),
                        bundle_id=bnd.id,
                        tier_key=tkey,
                        label=tlbl,
                        match_tokens=tokens,
                        is_default_fallback=is_def,
                        sort_order=tidx,
                    )
                    db.add(bt)
                    db.flush()
                    db.add(
                        CompanyBenefitBundleEffect(
                            id=new_id(),
                            tier_id=bt.id,
                            target_concept_id=towing_cid,
                            effect_type="upgrade_to_box2",
                            display_title="Unlimited Towing",
                            display_value="Unlimited",
                            display_description="24/7 emergency unlimited towing assistance across Malaysia.",
                            icon_hint="unlimited_towing",
                            comparison_value="Unlimited",
                            sort_order=1,
                        )
                    )

    # 12. Ensure AmAssurance configs are clean BEFORE cloning to Kurnia & Liberty, and enable every used concept per company
    if active_prof:
        all_concepts_list = list(concepts_by_key.values())
        for slug, co in companies_by_slug.items():
            if slug == "mmip":
                continue
            used_cids: set[str] = set()
            for cat in db.scalars(select(BenefitCatalog).where(BenefitCatalog.company_id == co.id, BenefitCatalog.status != "archived")).all():
                rev = _latest_rev(db, cat.id)
                if rev:
                    for o in db.scalars(select(CatalogOffering).where(CatalogOffering.catalog_revision_id == rev.id, CatalogOffering.status == "active")).all():
                        used_cids.add(o.concept_id)
            existing_cfgs = {
                cfg.concept_id: cfg
                for cfg in db.scalars(
                    select(CompanyBenefitConfig).where(
                        CompanyBenefitConfig.company_id == co.id,
                        CompanyBenefitConfig.profile_id == active_prof.id,
                    )
                ).all()
            }
            for c in all_concepts_list:
                if c.id in used_cids:
                    if c.id in existing_cfgs:
                        existing_cfgs[c.id].is_enabled = True
                    else:
                        db.add(
                            CompanyBenefitConfig(
                                id=new_id(),
                                profile_id=active_prof.id,
                                company_id=co.id,
                                concept_id=c.id,
                                is_enabled=True,
                                baseline_description=c.description,
                                baseline_cost=None,
                            )
                        )

    db.flush()

    # 13. Carbon-copy cleaned AmAssurance -> Kurnia and Liberty (ALL products, tiers, package-scoped & non-packaged catalogs, configs, bundles)
    if am_co:
        am_products = list(
            db.scalars(
                select(InsuranceProduct)
                .where(InsuranceProduct.company_id == am_co.id, InsuranceProduct.status == "active")
                .order_by(InsuranceProduct.name)
            ).all()
        )
        am_cats = list(
            db.scalars(
                select(BenefitCatalog)
                .where(BenefitCatalog.company_id == am_co.id, BenefitCatalog.status != "archived")
                .order_by(BenefitCatalog.name)
            ).all()
        )
        am_configs = list(
            db.scalars(
                select(CompanyBenefitConfig).where(
                    CompanyBenefitConfig.company_id == am_co.id,
                    CompanyBenefitConfig.profile_id == active_prof.id,
                )
            ).all()
        ) if active_prof else []
        am_bundles = list(
            db.scalars(
                select(CompanyBenefitBundle).where(
                    CompanyBenefitBundle.company_id == am_co.id,
                    CompanyBenefitBundle.profile_id == active_prof.id,
                )
            ).all()
        ) if active_prof else []

        for target_slug, target_name in (("kurnia", "Kurnia"), ("liberty", "Liberty")):
            t_co = companies_by_slug.get(target_slug)
            if not t_co:
                continue

            # Archive old products & catalogs on target so zero stale duplicates remain
            for p in db.scalars(select(InsuranceProduct).where(InsuranceProduct.company_id == t_co.id, InsuranceProduct.status != "archived")).all():
                p.status = "archived"
            for c in db.scalars(select(BenefitCatalog).where(BenefitCatalog.company_id == t_co.id, BenefitCatalog.status != "archived")).all():
                c.status = "archived"

            prod_map: dict[str, str] = {}
            tier_map: dict[str, str] = {}

            for sp in am_products:
                new_pname = sp.name.replace("AmAssurance", target_name)
                tp = InsuranceProduct(
                    id=new_id(),
                    company_id=t_co.id,
                    name=new_pname,
                    product_key=f"{target_slug}-{_slug(new_pname)}-{new_id()[:6]}",
                    revision=1,
                    status="active",
                )
                db.add(tp)
                db.flush()
                prod_map[sp.id] = tp.id
                for st in db.scalars(select(InsuranceProductTier).where(InsuranceProductTier.product_id == sp.id)).all():
                    tt = InsuranceProductTier(
                        id=new_id(),
                        product_id=tp.id,
                        tier_key=st.tier_key,
                        name=st.name,
                        sort_order=st.sort_order,
                        revision=1,
                        status=st.status,
                    )
                    db.add(tt)
                    db.flush()
                    tier_map[st.id] = tt.id

            for sc in am_cats:
                srev = _latest_rev(db, sc.id)
                if not srev:
                    continue
                new_cname = sc.name.replace("AmAssurance", target_name)
                tc = BenefitCatalog(
                    id=new_id(),
                    company_id=t_co.id,
                    product_id=prod_map.get(sc.product_id) if sc.product_id else None,
                    tier_id=tier_map.get(sc.tier_id) if sc.tier_id else None,
                    package_id=None,
                    segment_id=sc.segment_id,
                    vehicle_category_id=sc.vehicle_category_id,
                    vehicle_subcategory_id=sc.vehicle_subcategory_id,
                    coverage_type_id=sc.coverage_type_id,
                    engine_type=sc.engine_type,
                    name=new_cname,
                    revision=1,
                    status="published",
                )
                db.add(tc)
                db.flush()
                trev = BenefitCatalogRevision(
                    id=new_id(),
                    catalog_id=tc.id,
                    revision_number=1,
                    state="published",
                    source_document_ids=[],
                    content_hash="",
                    published_at=utcnow(),
                    is_archived=False,
                )
                db.add(trev)
                db.flush()

                pkg_map: dict[str, str] = {}
                for spkg in db.scalars(select(BenefitPackage).where(BenefitPackage.catalog_revision_id == srev.id, BenefitPackage.status == "active")).all():
                    tpkg = BenefitPackage(
                        id=new_id(),
                        catalog_revision_id=trev.id,
                        package_key=spkg.package_key,
                        name=spkg.name.replace("AmAssurance", target_name),
                        package_kind=spkg.package_kind,
                        sort_order=spkg.sort_order,
                        status="active",
                    )
                    db.add(tpkg)
                    db.flush()
                    pkg_map[spkg.id] = tpkg.id
                if sc.package_id and sc.package_id in pkg_map:
                    tc.package_id = pkg_map[sc.package_id]

                for so in db.scalars(
                    select(CatalogOffering)
                    .where(CatalogOffering.catalog_revision_id == srev.id, CatalogOffering.status == "active")
                    .order_by(CatalogOffering.sort_order)
                ).all():
                    db.add(
                        CatalogOffering(
                            id=new_id(),
                            catalog_revision_id=trev.id,
                            offering_key=so.offering_key,
                            concept_id=so.concept_id,
                            offering_kind=so.offering_kind,
                            applies_to_type=so.applies_to_type,
                            applies_to_id=pkg_map.get(so.applies_to_id) if so.applies_to_id else None,
                            role=so.role,
                            label_override=so.label_override,
                            description_override=so.description_override,
                            typed_value=so.typed_value,
                            display_value=so.display_value,
                            optional_price=None,
                            source_aliases=list(so.source_aliases or []),
                            source_citation=dict(so.source_citation or {}),
                            presentation_facet_ids=[],
                            sort_order=so.sort_order,
                            status="active",
                        )
                    )
                stats[f"cloned_cats_{target_slug}"] += 1

            # Sync CompanyBenefitConfig verbatim
            if active_prof:
                db.execute(
                    delete(CompanyBenefitConfig).where(
                        CompanyBenefitConfig.company_id == t_co.id,
                        CompanyBenefitConfig.profile_id == active_prof.id,
                    )
                )
                for cfg in am_configs:
                    db.add(
                        CompanyBenefitConfig(
                            id=new_id(),
                            profile_id=active_prof.id,
                            company_id=t_co.id,
                            concept_id=cfg.concept_id,
                            is_enabled=cfg.is_enabled,
                            baseline_description=cfg.baseline_description,
                            baseline_cost=None,
                        )
                    )
                # Sync CompanyBenefitBundle verbatim with clean brand key
                db.execute(delete(CompanyBenefitBundle).where(CompanyBenefitBundle.company_id == t_co.id))
                for sb in am_bundles:
                    tb = CompanyBenefitBundle(
                        id=new_id(),
                        company_id=t_co.id,
                        profile_id=active_prof.id,
                        bundle_key=sb.bundle_key.replace("amassurance", target_slug),
                        name=sb.name.replace("AmAssurance", target_name),
                        primary_concept_id=sb.primary_concept_id,
                        trigger_concept_ids=list(sb.trigger_concept_ids or []),
                        match_aliases=list(sb.match_aliases or []),
                        catalog_scope=sb.catalog_scope,
                        force_box2=sb.force_box2,
                        has_plan_tiers=sb.has_plan_tiers,
                        is_active=sb.is_active,
                        sort_order=sb.sort_order,
                    )
                    db.add(tb)
                    db.flush()
                    for st in db.scalars(select(CompanyBenefitBundleTier).where(CompanyBenefitBundleTier.bundle_id == sb.id)).all():
                        tt = CompanyBenefitBundleTier(
                            id=new_id(),
                            bundle_id=tb.id,
                            tier_key=st.tier_key,
                            label=st.label,
                            match_tokens=list(st.match_tokens or []),
                            is_default_fallback=st.is_default_fallback,
                            sort_order=st.sort_order,
                        )
                        db.add(tt)
                        db.flush()
                        for se in db.scalars(select(CompanyBenefitBundleEffect).where(CompanyBenefitBundleEffect.tier_id == st.id)).all():
                            db.add(
                                CompanyBenefitBundleEffect(
                                    id=new_id(),
                                    tier_id=tt.id,
                                    target_concept_id=se.target_concept_id,
                                    effect_type=se.effect_type,
                                    display_title=se.display_title,
                                    display_value=se.display_value,
                                    display_description=se.display_description,
                                    icon_hint=se.icon_hint,
                                    comparison_value=se.comparison_value,
                                    sort_order=se.sort_order,
                                )
                            )

    return dict(stats)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Commit changes to the database.")
    args = parser.parse_args()

    with SessionLocal() as db:
        cat_stats = standardize_catalogs_and_rules(db)
        icon_stats = sync_design2_vector_icons(db, dry_run=not args.apply)
        print("Catalog standardization summary:", cat_stats)
        print("Design 2 icon sync summary:", icon_stats)
        if args.apply:
            db.commit()
            print("COMMITTED SUCCESSFULLY.")
        else:
            db.rollback()
            print("DRY RUN ONLY (rolled back). Re-run with --apply to commit.")


if __name__ == "__main__":
    main()
