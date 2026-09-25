"""Ingest 11 new benefit artwork images and clean up duplicate/fluff benefits.

Tasks:
1. Ingest 11 PNG images from assets/benefits/new/ (1.png to 11.png)
2. Generate 512x512 UI and full-res PDF derivatives
3. Upload to private Supabase Storage
4. Create or update BusinessAsset records
5. Link default_asset_id on the 11 canonical BenefitConcept records
6. Retire the 16 duplicate/fluff benefits (offerings=0) and disable them in company configs

Usage:
    python commands/ingest-new-benefit-artwork.py            # Dry-run
    python commands/ingest-new-benefit-artwork.py --apply    # Execute
"""

from __future__ import annotations

import argparse
import io
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from PIL import Image
from sqlalchemy import select
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.tables import (
    BenefitConcept,
    BusinessAsset,
    CompanyBenefitConfig,
    new_id,
    utcnow,
)
from app.services.asset_intake import create_derivative
from app.storage.supabase import StorageError, SupabaseStorage

NEW_BENEFIT_IMAGES: dict[int, dict[str, str]] = {
    1: {
        "concept_key": "ev-battery-depletion-towing",
        "file": "1.png",
        "label": "EV Battery Flat Emergency Towing",
    },
    2: {
        "concept_key": "ev-charging-bodily-injury",
        "file": "2.png",
        "label": "EV Charging Bodily Injury Reimbursement",
    },
    3: {
        "concept_key": "ev-home-content-fire",
        "file": "3.png",
        "label": "EV Charging Home Content / Fire Damage",
    },
    4: {
        "concept_key": "ev-home-charger-liability",
        "file": "4.png",
        "label": "EV Home Charger Third-Party Liability",
    },
    5: {
        "concept_key": "lonpac-ev-smart-pack",
        "file": "5.png",
        "label": "Lonpac EV Smart Pack Bundle",
    },
    6: {
        "concept_key": "natural-falling-objects",
        "file": "6.png",
        "label": "Natural Falling Objects Damage Cover",
    },
    7: {
        "concept_key": "document-replacement",
        "file": "7.png",
        "label": "Vehicle Registration & Document Replacement",
    },
    8: {
        "concept_key": "motorcycle-pa-bundle",
        "file": "8.png",
        "label": "Motorcycle PA & Rider Protection Bundle",
    },
    9: {
        "concept_key": "sompo-motor-nhancer",
        "file": "9.png",
        "label": "SOMPO Motor N-hancer Multi-Pack",
    },
    10: {
        "concept_key": "motorshield-bundle",
        "file": "10.png",
        "label": "MotorShield Multi-in-1 Comprehensive Bundle",
    },
    11: {
        "concept_key": "commercial-driver-crew-pa",
        "file": "11.png",
        "label": "Commercial Vehicle Driver & Crew PA Bundle",
    },
}

FLUFF_KEYS_TO_RETIRE: list[str] = [
    "windscreen-auto-reinstatement",
    "towing-disabled-vehicle",
    "betterment-scale",
    "enhanced-special-perils",
    "ncd-entitlement",
    "pa-worldwide-extension",
    "pa-medical-evacuation",
    "pa-facial-dental-surgery",
    "pa-family-scheme",
    "pa-insect-snake-bites",
    "pa-major-surgery",
    "pa-post-hospital-recovery",
    "commercial-permitted-scope",
    "legal-representatives-indemnity",
    "loading-unloading-liability",
    "temporary-bus-excursion",
]


def ingest_artwork(db, storage: SupabaseStorage, dry_run: bool = True) -> list[str]:
    logs: list[str] = []
    assets_dir = ROOT / "assets" / "benefits" / "new"

    for idx in sorted(NEW_BENEFIT_IMAGES.keys()):
        item = NEW_BENEFIT_IMAGES[idx]
        key = item["concept_key"]
        file_path = assets_dir / item["file"]
        label = item["label"]

        if not file_path.exists():
            logs.append(f"[ERROR] Missing file: {file_path}")
            continue

        raw_bytes = file_path.read_bytes()
        with Image.open(io.BytesIO(raw_bytes)) as img:
            width, height = img.size
            has_transparency = "A" in img.getbands() or "transparency" in img.info

        content_hash = sha256(raw_bytes).hexdigest()
        original_storage_path = f"assets/original/{content_hash[:2]}/{content_hash}.png"

        # Generate UI (512x512) and PDF (1600x1600) derivatives
        ui_deriv = create_derivative(raw_bytes, max_width=512, max_height=512, quality=85)
        pdf_deriv = create_derivative(raw_bytes, max_width=1600, max_height=1600, quality=92)

        ui_storage_path = f"assets/derivative/ui/{ui_deriv.content_hash[:2]}/{ui_deriv.content_hash}.png"
        pdf_storage_path = f"assets/derivative/pdf/{pdf_deriv.content_hash[:2]}/{pdf_deriv.content_hash}.png"

        derivative_manifest = {
            "ui": {
                "storage_path": ui_storage_path,
                "content_type": ui_deriv.content_type,
                "content_hash": ui_deriv.content_hash,
                "width_px": ui_deriv.width_px,
                "height_px": ui_deriv.height_px,
            },
            "pdf": {
                "storage_path": pdf_storage_path,
                "content_type": pdf_deriv.content_type,
                "content_hash": pdf_deriv.content_hash,
                "width_px": pdf_deriv.width_px,
                "height_px": pdf_deriv.height_px,
            },
        }

        # Upload payloads to Supabase Storage if applying
        if not dry_run:
            payloads = [
                (original_storage_path, raw_bytes, "image/png"),
                (ui_storage_path, ui_deriv.data, ui_deriv.content_type),
                (pdf_storage_path, pdf_deriv.data, pdf_deriv.content_type),
            ]
            for path, data, ctype in payloads:
                try:
                    storage.upload_asset(path, data, ctype)
                except StorageError as exc:
                    if "already exists" not in str(exc).lower():
                        raise

        # Check existing asset by hash or asset_key
        asset_key = f"benefit-art:{key}"
        asset = db.scalar(
            select(BusinessAsset).where(
                (BusinessAsset.content_hash == content_hash) | (BusinessAsset.asset_key == asset_key)
            )
        )

        if not asset:
            logs.append(f"[CREATE ASSET] {asset_key} ({label}) from {item['file']} ({width}x{height})")
            if not dry_run:
                asset = BusinessAsset(
                    id=new_id(),
                    asset_key=asset_key,
                    asset_kind="benefit_art",
                    label=label,
                    original_filename=f"{key}.png",
                    content_type="image/png",
                    content_hash=content_hash,
                    storage_path=original_storage_path,
                    size_bytes=len(raw_bytes),
                    width_px=width,
                    height_px=height,
                    has_transparency=has_transparency,
                    derivative_manifest=derivative_manifest,
                    revision=1,
                    status="active",
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
                db.add(asset)
                db.flush()
        else:
            logs.append(f"[EXISTING ASSET] {asset_key} ({asset.id})")
            if not dry_run:
                asset.status = "active"
                asset.derivative_manifest = derivative_manifest
                asset.updated_at = utcnow()

        # Link to BenefitConcept
        concept = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == key))
        if concept:
            if concept.default_asset_id != (asset.id if asset else "pending"):
                logs.append(f"[LINK CONCEPT] {key} -> asset {asset.id if asset else 'NEW'}")
                if not dry_run and asset:
                    concept.default_asset_id = asset.id
                    concept.status = "active"
                    concept.updated_at = utcnow()
        else:
            logs.append(f"[WARNING] Concept not found: {key}")

    return logs


def retire_fluff_benefits(db, dry_run: bool = True) -> list[str]:
    logs: list[str] = []
    for key in FLUFF_KEYS_TO_RETIRE:
        concept = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == key))
        if not concept:
            continue

        if concept.status != "retired":
            logs.append(f"[RETIRE CONCEPT] {key} ({concept.label}) status: {concept.status} -> retired")
            if not dry_run:
                concept.status = "retired"
                concept.updated_at = utcnow()

        # Disable in CompanyBenefitConfig
        cfgs = db.scalars(select(CompanyBenefitConfig).where(CompanyBenefitConfig.concept_id == concept.id)).all()
        for cfg in cfgs:
            if cfg.is_enabled:
                logs.append(f"[DISABLE CONFIG] {key} for company {cfg.company_id}")
                if not dry_run:
                    cfg.is_enabled = False
                    cfg.updated_at = utcnow()

    return logs


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest 11 benefit artworks and retire duplicate benefits.")
    parser.add_argument("--apply", action="store_true", help="Execute DB changes and asset uploads.")
    args = parser.parse_args()

    settings = get_settings()
    storage = SupabaseStorage(settings)
    db = SessionLocal()

    try:
        print("=== Step 1: Ingesting 11 Benefit Artworks ===")
        art_logs = ingest_artwork(db, storage, dry_run=not args.apply)
        for log in art_logs:
            print("  ", log)

        print("\n=== Step 2: Retiring 16 Duplicate/Fluff Benefits ===")
        fluff_logs = retire_fluff_benefits(db, dry_run=not args.apply)
        for log in fluff_logs:
            print("  ", log)

        if not args.apply:
            print("\n[DRY RUN COMPLETE] No database changes written. Pass --apply to execute.")
        else:
            db.commit()
            print("\n[APPLY COMPLETE] Database updated and artworks linked successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    main()
