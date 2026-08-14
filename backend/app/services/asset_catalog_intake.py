"""Content-addressed registration of the owner-provided v7 asset source set."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath
from threading import Lock

from sqlalchemy import select

from app.models.enums import AccountStatus
from app.models.tables import BusinessAsset, CompanyAlias, InsuranceCompany, new_id
from app.services.asset_intake import create_derivative, validate_image_file
from app.storage.supabase import SupabaseStorage


DERIVATIVE_PROFILES = (
    ("ui", 512, 512, 85),
    ("pdf", 1_600, 1_600, 92),
)


def _extension(content_type: str) -> str:
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
    }[content_type]


def _normalized_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _company_identity_keys(company: InsuranceCompany) -> set[str]:
    values = [company.slug or "", company.name or "", *(company.detection_phrases or [])]
    return {normalized for value in values if (normalized := _normalized_alias(value))}


def _storage_path(content_hash: str, kind: str, extension: str) -> str:
    return f"assets/{kind}/{content_hash[:2]}/{content_hash}.{extension}"


def build_asset_import_plan(repository_root: Path, manifest: dict) -> dict:
    """Revalidate source bytes and build a deterministic, non-mutating plan."""

    root = repository_root.resolve()
    planned_assets: list[dict] = []
    companies: list[dict] = []
    errors: list[dict] = []
    for manifest_entry in manifest.get("assets") or []:
        source_path = (root / PurePosixPath(manifest_entry["source_path"])).resolve()
        try:
            source_path.relative_to(root)
        except ValueError:
            errors.append({"source_path": manifest_entry.get("source_path"), "error": "Source path escapes the repository."})
            continue
        try:
            technical = validate_image_file(source_path, max_bytes=10 * 1024 * 1024, max_pixels=32_000_000)
        except (OSError, ValueError) as exc:
            errors.append({"source_path": manifest_entry.get("source_path"), "error": str(exc)})
            continue
        if technical["content_hash"] != manifest_entry.get("content_hash"):
            errors.append({"source_path": manifest_entry.get("source_path"), "error": "Source content changed after manifest generation."})
            continue
        data = source_path.read_bytes()
        original_extension = _extension(technical["content_type"])
        derivatives: dict[str, dict] = {}
        for profile, max_width, max_height, quality in DERIVATIVE_PROFILES:
            derivative = create_derivative(data, max_width=max_width, max_height=max_height, quality=quality)
            derivative_extension = _extension(derivative.content_type)
            derivatives[profile] = {
                "storage_path": _storage_path(derivative.content_hash, f"derivative/{profile}", derivative_extension),
                "content_type": derivative.content_type,
                "content_hash": derivative.content_hash,
                "width_px": derivative.width_px,
                "height_px": derivative.height_px,
                "data": derivative.data,
            }
        planned = {
            **manifest_entry,
            **technical,
            "source_path_resolved": source_path,
            "data": data,
            "original_storage_path": _storage_path(technical["content_hash"], "original", original_extension),
            "derivatives": derivatives,
            "status": "active" if manifest_entry["asset_kind"] == "company_logo" else "unassigned",
        }
        planned_assets.append(planned)
        if manifest_entry["asset_kind"] == "company_logo":
            aliases = [manifest_entry["display_name"], manifest_entry["brand_key"].replace("-", " ")]
            companies.append({
                "brand_key": manifest_entry["brand_key"],
                "display_name": manifest_entry["display_name"],
                "logo_asset_key": manifest_entry["asset_key"],
                "aliases": list(dict.fromkeys(alias for alias in aliases if alias)),
            })
    return {
        "schema_version": manifest.get("schema_version", 1),
        "assets": planned_assets,
        "companies": companies,
        "errors": errors,
    }


def _upload_asset_payload(storage, path: str, data: bytes, content_type: str) -> str:
    storage.upload_asset(path, data, content_type)
    return path


def _upload_payloads(storage, payloads: list[tuple[str, bytes, str]], uploaded_paths: list[str]) -> None:
    if not payloads:
        return
    uploaded_lock = Lock()
    with ThreadPoolExecutor(max_workers=min(6, len(payloads)), thread_name_prefix="asset-intake") as executor:
        futures = [executor.submit(_upload_asset_payload, storage, *payload) for payload in payloads]
        for future in as_completed(futures):
            path = future.result()
            with uploaded_lock:
                uploaded_paths.append(path)


def _delete_uploaded_paths(storage, uploaded_paths: list[str]) -> None:
    def delete(path: str) -> None:
        try:
            storage.delete_pdf(path)
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=min(6, len(uploaded_paths) or 1), thread_name_prefix="asset-rollback") as executor:
        list(executor.map(delete, reversed(uploaded_paths)))


def apply_asset_manifest(db, plan: dict, *, storage: SupabaseStorage) -> dict:
    """Apply one validated plan idempotently without overwriting conflicts."""

    if plan.get("errors"):
        raise ValueError("Asset plan contains validation errors.")
    existing_assets = {item.asset_key: item for item in db.scalars(select(BusinessAsset)).all()}
    existing_companies: dict[str, InsuranceCompany] = {}
    for company in db.scalars(select(InsuranceCompany)).all():
        for identity in _company_identity_keys(company):
            existing_companies.setdefault(identity, company)
    existing_aliases = {_normalized_alias(item.normalized_alias): item for item in db.scalars(select(CompanyAlias)).all()}
    uploaded_paths: list[str] = []
    conflicts: list[dict] = []
    assets_created = 0
    assets_unchanged = 0
    companies_created = 0
    aliases_created = 0
    asset_by_key = dict(existing_assets)
    try:
        new_assets: list[dict] = []
        for item in plan["assets"]:
            existing = existing_assets.get(item["asset_key"])
            if existing:
                if existing.content_hash != item["content_hash"]:
                    conflicts.append({
                        "asset_key": item["asset_key"],
                        "existing_hash": existing.content_hash,
                        "incoming_hash": item["content_hash"],
                    })
                else:
                    assets_unchanged += 1
                continue
            new_assets.append(item)

        upload_payloads: list[tuple[str, bytes, str]] = []
        for item in new_assets:
            upload_payloads.append((item["original_storage_path"], item["data"], item["content_type"]))
            upload_payloads.extend(
                (derivative["storage_path"], derivative["data"], derivative["content_type"])
                for derivative in item["derivatives"].values()
            )
        _upload_payloads(storage, upload_payloads, uploaded_paths)

        for item in new_assets:
            derivative_manifest = {}
            for profile, derivative in item["derivatives"].items():
                derivative_manifest[profile] = {key: value for key, value in derivative.items() if key != "data"}
            asset = BusinessAsset(
                id=new_id(),
                asset_key=item["asset_key"],
                asset_kind=item["asset_kind"],
                label=item["display_name"],
                original_filename=item["source_filename"],
                content_type=item["content_type"],
                content_hash=item["content_hash"],
                storage_path=item["original_storage_path"],
                size_bytes=item["size_bytes"],
                width_px=item["width_px"],
                height_px=item["height_px"],
                has_transparency=item["has_transparency"],
                derivative_manifest=derivative_manifest,
                revision=1,
                status=item["status"],
            )
            db.add(asset)
            asset_by_key[asset.asset_key] = asset
            assets_created += 1
        db.flush()

        company_by_brand: dict[str, InsuranceCompany] = {}
        for item in plan["companies"]:
            identity_keys = {
                _normalized_alias(item["brand_key"]),
                _normalized_alias(item["display_name"]),
                *(_normalized_alias(alias) for alias in item["aliases"]),
            }
            company = next(
                (existing_companies[key] for key in identity_keys if key in existing_companies),
                None,
            )
            if company is None:
                company = InsuranceCompany(
                    id=new_id(),
                    slug=item["brand_key"],
                    revision=1,
                    name=item["display_name"],
                    category="Motor",
                    source_template_category="Other / Unknown",
                    logo_path=None,
                    detection_phrases=list(item["aliases"]),
                    status=AccountStatus.ACTIVE.value,
                )
                db.add(company)
                companies_created += 1
            elif not company.slug:
                company.slug = item["brand_key"]
            for identity in identity_keys:
                existing_companies[identity] = company
            company.logo_asset_id = asset_by_key[item["logo_asset_key"]].id
            company.logo_path = None
            company_by_brand[item["brand_key"]] = company

        # CompanyAlias stores the raw FK and has no ORM relationship that can
        # make SQLAlchemy infer insert order. Persist every new company first.
        db.flush()

        for item in plan["companies"]:
            company = company_by_brand[item["brand_key"]]
            for alias in item["aliases"]:
                normalized = _normalized_alias(alias)
                if not normalized or normalized in existing_aliases:
                    continue
                record = CompanyAlias(
                    id=new_id(),
                    company_id=company.id,
                    alias=alias,
                    normalized_alias=normalized,
                    alias_kind="detection",
                    status=AccountStatus.ACTIVE.value,
                )
                db.add(record)
                existing_aliases[normalized] = record
                aliases_created += 1
        db.commit()
    except Exception:
        db.rollback()
        _delete_uploaded_paths(storage, uploaded_paths)
        raise
    return {
        "assets_created": assets_created,
        "assets_unchanged": assets_unchanged,
        "companies_created": companies_created,
        "aliases_created": aliases_created,
        "conflicts": conflicts,
        "uploaded_objects": len(uploaded_paths),
    }
