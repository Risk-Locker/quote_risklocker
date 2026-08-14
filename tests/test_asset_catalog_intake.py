"""Idempotent database/storage intake for owner-provided v7 assets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models.tables import BusinessAsset, CompanyAlias, InsuranceCompany
from app.services.asset_catalog_intake import apply_asset_manifest, build_asset_import_plan


def manifest():
    return json.loads((ROOT / "assets/v7-source-manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def asset_manifest():
    return manifest()


@pytest.fixture(scope="module")
def asset_plan(asset_manifest):
    return build_asset_import_plan(ROOT, asset_manifest)


class ScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class FakeDb:
    def __init__(self, assets=None, companies=None, aliases=None):
        self.assets = list(assets or [])
        self.companies = list(companies or [])
        self.aliases = list(aliases or [])
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity") if statement.column_descriptions else None
        if entity is BusinessAsset:
            return ScalarRows(self.assets)
        if entity is InsuranceCompany:
            return ScalarRows(self.companies)
        if entity is CompanyAlias:
            return ScalarRows(self.aliases)
        return ScalarRows([])

    def add(self, item):
        self.added.append(item)
        if isinstance(item, BusinessAsset):
            self.assets.append(item)
        elif isinstance(item, InsuranceCompany):
            self.companies.append(item)
        elif isinstance(item, CompanyAlias):
            self.aliases.append(item)

    def flush(self):
        self.flushes += 1

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class Storage:
    def __init__(self):
        self.uploads = []
        self.deletes = []

    def upload_asset(self, key, data, content_type):
        self.uploads.append((key, data, content_type))

    def delete_pdf(self, key):
        self.deletes.append(key)


def test_import_plan_is_dynamic_content_addressed_and_does_not_assign_benefits(asset_plan, asset_manifest):
    plan = asset_plan

    assert plan["errors"] == []
    assert len(plan["assets"]) == len(asset_manifest["assets"])
    assert len(plan["companies"]) == asset_manifest["summary"]["company_logo_count"]
    assert all(item["original_storage_path"].startswith(f"assets/original/{item['content_hash'][:2]}/{item['content_hash']}") for item in plan["assets"])
    assert all(len(item["derivatives"]) == 2 for item in plan["assets"])
    assert all(item["status"] == "unassigned" for item in plan["assets"] if item["asset_kind"] == "benefit_art")
    assert all("catalog" not in company for company in plan["companies"])


def test_apply_registers_assets_dynamic_companies_and_logo_links(asset_plan):
    plan = asset_plan
    db = FakeDb()
    storage = Storage()

    result = apply_asset_manifest(db, plan, storage=storage)

    assert result["assets_created"] == len(plan["assets"])
    assert result["companies_created"] == len(plan["companies"])
    assert result["aliases_created"] >= len(plan["companies"])
    assert db.commits == 1
    assert len(db.assets) == len(plan["assets"])
    assert all(company.logo_asset_id for company in db.companies)
    assert all(company.logo_path is None for company in db.companies)
    assert all(asset.status == ("active" if asset.asset_kind == "company_logo" else "unassigned") for asset in db.assets)
    assert len(storage.uploads) == len(plan["assets"]) * 3
    assert db.flushes == 2


def test_reapplying_same_plan_is_idempotent_and_uploads_nothing_again(asset_plan):
    plan = asset_plan
    db = FakeDb()
    first_storage = Storage()
    apply_asset_manifest(db, plan, storage=first_storage)
    second_storage = Storage()

    result = apply_asset_manifest(db, plan, storage=second_storage)

    assert result["assets_created"] == 0
    assert result["assets_unchanged"] == len(plan["assets"])
    assert result["companies_created"] == 0
    assert second_storage.uploads == []
    assert db.commits == 2


def test_existing_company_without_slug_is_merged_by_normalized_name(asset_plan):
    existing_qbe = InsuranceCompany(
        id="company-qbe-existing",
        slug=None,
        revision=1,
        name="QBE",
        category="Motor",
        source_template_category="QBE",
        logo_path="legacy/qbe.png",
        detection_phrases=["QBE Insurance (Malaysia) Berhad"],
        status="active",
    )
    db = FakeDb(companies=[existing_qbe])

    result = apply_asset_manifest(db, asset_plan, storage=Storage())

    assert result["companies_created"] == len(asset_plan["companies"]) - 1
    assert len(db.companies) == len(asset_plan["companies"])
    assert existing_qbe.slug == "qbe"
    assert existing_qbe.logo_asset_id
    assert existing_qbe.logo_path is None


def test_existing_asset_key_with_different_hash_is_reported_without_overwrite(asset_plan):
    plan = asset_plan
    entry = plan["assets"][0]
    existing = BusinessAsset(
        id="asset-existing",
        asset_key=entry["asset_key"],
        asset_kind=entry["asset_kind"],
        label="Existing",
        original_filename="existing.png",
        content_type="image/png",
        content_hash="f" * 64,
        storage_path="assets/existing.png",
        size_bytes=10,
        derivative_manifest={},
        revision=1,
        status="active",
    )
    db = FakeDb(assets=[existing])
    storage = Storage()

    result = apply_asset_manifest(db, plan, storage=storage)

    assert result["conflicts"][0]["asset_key"] == entry["asset_key"]
    assert existing.content_hash == "f" * 64
    assert all(upload[0] != entry["original_storage_path"] for upload in storage.uploads)
