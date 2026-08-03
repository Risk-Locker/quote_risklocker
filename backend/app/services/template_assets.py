"""Safe access to local and uploaded template assets."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.models.enums import AccountStatus
from app.models.tables import TemplateAsset, User
from app.storage.supabase import SupabaseStorage


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg"}
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/svg+xml"}


def asset_root() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "template_assets"


def _local_asset_id(path: Path) -> str:
    return hashlib.sha1(path.name.encode("utf-8")).hexdigest()[:16]


def _local_label(path: Path) -> str:
    name = path.stem.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", name).strip().title()


def _local_assets() -> list[dict[str, Any]]:
    root = asset_root()
    if not root.exists():
        return []
    assets: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        asset_id = _local_asset_id(path)
        assets.append(
            {
                "id": asset_id,
                "label": _local_label(path),
                "filename": path.name,
                "extension": path.suffix.lower(),
                "url": f"/template-assets/{asset_id}",
                "size_bytes": path.stat().st_size,
                "source": "local",
            }
        )
    return assets


def _uploaded_assets(db: Session) -> list[dict[str, Any]]:
    records = db.scalars(
        select(TemplateAsset).where(TemplateAsset.status == AccountStatus.ACTIVE.value).order_by(TemplateAsset.created_at.desc())
    ).all()
    return [
        {
            "id": record.id,
            "label": record.label,
            "filename": record.filename,
            "extension": Path(record.filename).suffix.lower(),
            "url": f"/template-assets/{record.id}",
            "size_bytes": record.size_bytes,
            "source": "uploaded",
        }
        for record in records
    ]


def list_template_assets(db: Session | None = None) -> list[dict[str, Any]]:
    return _local_assets() + (_uploaded_assets(db) if db else [])


def resolve_template_asset(db: Session | None, asset_id: str) -> Path | bytes:
    if not asset_id:
        raise FileNotFoundError(asset_id)

    # Try local assets first.
    root = asset_root()
    if re.fullmatch(r"[a-f0-9]{16}", asset_id):
        for path in root.iterdir() if root.exists() else []:
            if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS and _local_asset_id(path) == asset_id:
                resolved = path.resolve()
                if root.resolve() not in resolved.parents:
                    raise FileNotFoundError(asset_id)
                return resolved

    # Try uploaded assets.
    if db is not None:
        record = db.get(TemplateAsset, asset_id)
        if record and record.status == AccountStatus.ACTIVE.value:
            try:
                settings = get_settings()
                return SupabaseStorage(settings).download_bytes(record.storage_path)
            except Exception as exc:
                raise FileNotFoundError(asset_id) from exc

    raise FileNotFoundError(asset_id)


def asset_data_uri(db: Session | None, asset_id: str | None) -> str:
    if not asset_id:
        return ""
    try:
        resolved = resolve_template_asset(db, asset_id)
    except FileNotFoundError:
        return ""
    if isinstance(resolved, Path):
        mime = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(resolved.read_bytes()).decode("ascii")
    else:
        mime = "image/png"
        encoded = base64.b64encode(resolved).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def find_asset_by_hint(db: Session | None, hints: list[str]) -> str:
    assets = list_template_assets(db)
    lowered = [(asset["id"], asset["filename"].lower(), asset["label"].lower()) for asset in assets]
    for hint in hints:
        token = hint.lower()
        for asset_id, filename, label in lowered:
            if token in filename or token in label:
                return asset_id
    return ""


def _extension_for_mime(mime: str) -> str:
    if mime == "image/svg+xml":
        return ".svg"
    if mime in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if mime == "image/png":
        return ".png"
    return ""


def _validate_asset_upload(filename: str, content_type: str | None, data: bytes) -> tuple[str, str]:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError("Only PNG, JPG, and SVG files are allowed.", 400)

    mime = content_type or mimetypes.guess_type(filename)[0] or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise AppError("Unsupported file type.", 400)

    if len(data) > 10 * 1024 * 1024:
        raise AppError("Asset must be smaller than 10 MB.", 400)

    return ext, mime


def upload_template_asset(
    db: Session,
    settings: Settings,
    user: User,
    filename: str,
    content_type: str | None,
    data: bytes,
    label: str | None = None,
) -> TemplateAsset:
    ext, mime = _validate_asset_upload(filename, content_type, data)
    asset_id = str(uuid4())
    storage_path = f"template-assets/{datetime.now(timezone.utc):%Y/%m/%d}/{asset_id}{ext}"
    stored = SupabaseStorage(settings).upload_asset(storage_path, data, mime)

    record = TemplateAsset(
        id=asset_id,
        uploaded_by=user.id,
        label=label or Path(filename).stem,
        filename=filename,
        content_type=mime,
        storage_provider=stored.provider,
        storage_bucket=stored.bucket,
        storage_path=stored.object_key,
        storage_sha256=stored.sha256,
        size_bytes=len(data),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def delete_template_asset(db: Session, user: User, asset_id: str) -> None:
    record = db.get(TemplateAsset, asset_id)
    if not record:
        raise AppError("Asset not found.", 404)
    record.status = AccountStatus.INACTIVE.value
    db.commit()
