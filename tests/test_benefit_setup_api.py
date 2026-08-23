"""HTTP + service coverage for the benefits-refactor hierarchy and scoped aliases.

Covers: segments, vehicle categories/subcategories, coverage types, scoped
benefit aliases, packages (comprehensive chain | add-on bundles), assignment
context validation, the extended Global Benefit (concept) fields, RBAC, scope
validation, duplicate protection, and the 033 seed rows.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.api import routes
from app.api.deps import current_user
from app.core.errors import register_error_handlers
from app.db.session import get_db
from app.models.tables import (
    BenefitAlias,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    CatalogOffering,
    CoverageType,
    InsuranceCompany,
    InsuranceProduct,
    Segment,
    VehicleCategory,
    VehicleSubcategory,
    new_id,
)


_SQL_EQ = re.compile(r'(?:(?:"[a-z_]+"|[a-z_]+)\.)?"?([a-z_]+)"?\s*=\s*\'([^\']*)\'')
_SQL_NEQ = re.compile(r'(?:(?:"[a-z_]+"|[a-z_]+)\.)?"?([a-z_]+)"?\s*<>\s*\'([^\']*)\'')


def _norm(value) -> str:
    # SQLAlchemy's UUID literal binding strips dashes; normalize both sides.
    return str(value).replace("-", "")


def client():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="staff-1", role="staff")
    return TestClient(app)


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class FakeDb:
    """Session-like fake: select statements are matched against rows via the
    compiled WHERE literals so scoped/duplicate queries behave realistically."""

    def __init__(self, rows: dict | None = None):
        self.rows: dict[type, list] = rows or {}
        self.added: list = []
        self.commits = 0

    @staticmethod
    def _pairs(statement):
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
        return _SQL_EQ.findall(compiled), _SQL_NEQ.findall(compiled)

    @staticmethod
    def _matches(row, eq_pairs, neq_pairs):
        return (
            all(_norm(getattr(row, col, "")) == _norm(value) for col, value in eq_pairs)
            and all(_norm(getattr(row, col, "")) != _norm(value) for col, value in neq_pairs)
        )

    def scalar(self, statement):
        self.flush()
        entity = statement.column_descriptions[0].get("entity")
        if entity is None:
            return None
        eq_pairs, neq_pairs = self._pairs(statement)
        for item in self.rows.get(entity, []):
            if self._matches(item, eq_pairs, neq_pairs):
                return item
        return None

    def scalars(self, statement):
        self.flush()
        entity = statement.column_descriptions[0].get("entity")
        if entity is None:
            return _ScalarResult([])
        eq_pairs, neq_pairs = self._pairs(statement)
        if not eq_pairs and not neq_pairs:
            return _ScalarResult(self.rows.get(entity, []))
        return _ScalarResult([item for item in self.rows.get(entity, []) if self._matches(item, eq_pairs, neq_pairs)])

    def get(self, model, object_id):
        self.flush()
        for item in self.rows.get(model, []):
            if str(item.id) == str(object_id):
                return item
        return None

    def add(self, item):
        self.added.append(item)

    def add_all(self, items):
        for item in items:
            self.add(item)

    def flush(self):
        for item in self.added:
            self.rows.setdefault(type(item), []).append(item)
        self.added = []

    def commit(self):
        self.commits += 1

    def refresh(self, _item):
        pass


def _staff():
    return SimpleNamespace(id="staff-1", role="staff")


def _viewer():
    return SimpleNamespace(id="viewer-1", role="viewer")


def _catalog_row(package_id=None, tier_id=None, revision=5):
    return BenefitCatalog(
        id="catalog-1", company_id="company-1", product_id="product-1",
        package_id=package_id, tier_id=tier_id, name="Catalog", revision=revision, status="draft",
    )


def _revision_row(catalog_id="catalog-1", state="draft", number=2):
    return BenefitCatalogRevision(
        id="revision-1", catalog_id=catalog_id, revision_number=number, state=state,
        source_document_ids=[], content_hash="", published_by=None, published_at=None,
    )


# ---------------------------------------------------------------------------
# HTTP contract: hierarchy routes
# ---------------------------------------------------------------------------


def test_hierarchy_list_and_save_routes_are_wired(monkeypatch):
    monkeypatch.setattr(
        routes,
        "list_segments",
        lambda _db, _user, **kwargs: {"items": [{"id": "s1", "key": "private", "name": "Private"}], "total": 1, **kwargs},
    )
    monkeypatch.setattr(
        routes,
        "save_segment",
        lambda _db, _user, payload: {"id": "s2", "key": "fleet", **payload},
    )
    monkeypatch.setattr(
        routes,
        "list_vehicle_categories",
        lambda _db, _user, **kwargs: {"items": [{"id": "v1", "key": "car", "name": "Car"}], "total": 1, **kwargs},
    )
    monkeypatch.setattr(
        routes,
        "list_vehicle_subcategories",
        lambda _db, _user, **kwargs: {"items": [{"id": "v2", "key": "van", "name": "Van"}], "total": 1, **kwargs},
    )
    monkeypatch.setattr(
        routes,
        "list_coverage_types",
        lambda _db, _user, **kwargs: {"items": [{"id": "c1", "key": "comprehensive", "name": "Comprehensive"}], "total": 1, **kwargs},
    )

    api = client()
    assert api.get("/api/business/segments?search=pri").json()["segments"]["items"][0]["name"] == "Private"
    assert api.post("/api/business/segments", json={"name": "Fleet"}).json()["segment"]["key"] == "fleet"
    assert api.get("/api/business/vehicle-categories").json()["vehicle_categories"]["items"][0]["name"] == "Car"
    assert api.get("/api/business/vehicle-subcategories?category_id=v1").json()["vehicle_subcategories"]["items"][0]["name"] == "Van"
    assert api.get("/api/business/coverage-types").json()["coverage_types"]["items"][0]["name"] == "Comprehensive"


def test_hierarchy_save_requires_name_and_retire_returns_204(monkeypatch):
    monkeypatch.setattr(routes, "save_segment", lambda _db, _user, payload: {"id": "s1", **payload})
    monkeypatch.setattr(routes, "retire_segment", lambda _db, _user, segment_id: None)
    monkeypatch.setattr(routes, "retire_vehicle_category", lambda _db, _user, category_id: None)

    api = client()
    assert api.post("/api/business/segments", json={}).status_code == 422
    assert api.post("/api/business/segments", json={"name": "Private"}).status_code == 200
    assert api.delete("/api/business/segments/s1").status_code == 204
    assert api.delete("/api/business/vehicle-categories/v1").status_code == 204


def test_vehicle_subcategory_save_requires_category_id(monkeypatch):
    monkeypatch.setattr(routes, "save_vehicle_subcategory", lambda _db, _user, payload: {"id": "sub1", **payload})
    api = client()
    missing = api.post("/api/business/vehicle-subcategories", json={"name": "Van"})
    assert missing.status_code == 422
    saved = api.post("/api/business/vehicle-subcategories", json={"category_id": "v1", "name": "Van"})
    assert saved.status_code == 200


# ---------------------------------------------------------------------------
# HTTP contract: benefit aliases + extended concepts
# ---------------------------------------------------------------------------


def test_benefit_alias_routes_wire_scope_and_filter(monkeypatch):
    monkeypatch.setattr(
        routes,
        "list_benefit_aliases",
        lambda _db, _user, **kwargs: {
            "items": [{"id": "a1", "benefit_id": "b1", "phrase": "24/7 Towing", "scope": "global"}],
            "total": 1,
            **kwargs,
        },
    )
    monkeypatch.setattr(
        routes,
        "save_benefit_alias",
        lambda _db, _user, payload: {"id": "a2", "normalized_phrase": "24 7 towing", **payload},
    )
    monkeypatch.setattr(routes, "retire_benefit_alias", lambda _db, _user, alias_id: None)

    api = client()
    listing = api.get("/api/business/benefit-aliases?benefit_id=b1&search=tow")
    assert listing.status_code == 200
    assert listing.json()["benefit_aliases"]["items"][0]["scope"] == "global"

    saved = api.post("/api/business/benefit-aliases", json={"benefit_id": "b1", "phrase": "24/7 Towing"})
    assert saved.status_code == 200
    assert saved.json()["benefit_alias"]["normalized_phrase"] == "24 7 towing"

    assert api.post("/api/business/benefit-aliases", json={}).status_code == 422
    assert api.delete("/api/business/benefit-aliases/a1").status_code == 204


def test_benefit_concept_save_carries_global_benefit_datasets(monkeypatch):
    captured = {}

    def save(_db, _user, payload):
        captured.update(payload)
        return {"id": "b1", **payload}

    monkeypatch.setattr(routes, "save_benefit_concept", save)
    response = client().post(
        "/api/business/benefit-concepts",
        json={
            "concept_key": "towing",
            "label": "Towing",
            "description": "Towing up to the stated limit",
            "demo_value": {"type": "money", "value": "300", "currency": "MYR", "semantic_role": "insured_limit"},
            "match_dataset": ["towing", "towing assistance", "accident towing"],
            "value_pattern_dataset": ["RM {amount}", "{distance} km", "Unlimited"],
            "sort_order": 10,
        },
    )
    assert response.status_code == 200
    assert captured["match_dataset"] == ["towing", "towing assistance", "accident towing"]
    assert captured["value_pattern_dataset"][-1] == "Unlimited"
    assert captured["demo_value"]["type"] == "money"
    assert captured["sort_order"] == 10


# ---------------------------------------------------------------------------
# Service behaviour
# ---------------------------------------------------------------------------


def _segment_row():
    return Segment(id=new_id(), segment_key="private", name="Private", sort_order=10, status="active")


def _concept_row():
    return BenefitConcept(id=new_id(), concept_key="towing", label="Towing")


def test_save_segment_creates_duplicate_guarded_and_status_validated():
    from app.services.benefit_setup_service import save_segment

    existing = _segment_row()
    db = FakeDb(rows={Segment: [existing]})

    created = save_segment(db, _staff(), {"name": "Fleet"})
    assert created["key"] == "fleet"
    assert created["status"] == "active"

    duplicate = FakeDb(rows={Segment: [existing]})
    try:
        save_segment(duplicate, _staff(), {"name": "Private"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("Duplicate segment key must be rejected with 409")

    bad = FakeDb(rows={Segment: []})
    try:
        save_segment(bad, _staff(), {"name": "X", "status": "gone"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("Invalid status must be rejected with 422")


def test_hierarchy_saves_require_business_role():
    from app.services.benefit_setup_service import save_segment

    db = FakeDb(rows={Segment: []})
    try:
        save_segment(db, _viewer(), {"name": "X"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("Non-business role must be rejected with 403")


def test_vehicle_subcategory_requires_existing_category():
    from app.services.benefit_setup_service import save_vehicle_subcategory

    db = FakeDb(rows={VehicleCategory: []})
    try:
        save_vehicle_subcategory(db, _staff(), {"category_id": "missing", "name": "Van"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Missing category must be rejected with 404")


def test_benefit_alias_scopes_and_duplicates():
    from app.services.benefit_setup_service import save_benefit_alias

    concept = _concept_row()
    company = SimpleNamespace(id="c1", name="QBE")
    product = SimpleNamespace(id="p1", name="Private Car")

    db = FakeDb(rows={BenefitConcept: [concept], InsuranceCompany: [company], InsuranceProduct: [product]})
    created = save_benefit_alias(db, _staff(), {"benefit_id": concept.id, "phrase": "24/7 Towing Assistance"})
    assert created["scope"] == "global"
    assert created["normalized_phrase"] == "24 7 towing assistance"

    scoped = save_benefit_alias(
        db, _staff(), {"benefit_id": concept.id, "phrase": "24/7 Towing", "scope": "company", "company_id": "c1"}
    )
    assert scoped["scope"] == "company"
    assert scoped["company_id"] == "c1"

    # Same phrase in a different scope is allowed (global vs company).
    existing_global = BenefitAlias(
        id=new_id(), benefit_id=concept.id, phrase="24/7 Towing", normalized_phrase="24 7 towing", scope="global", status="active"
    )
    again = FakeDb(rows={BenefitConcept: [concept], BenefitAlias: [existing_global]})
    try:
        save_benefit_alias(again, _staff(), {"benefit_id": concept.id, "phrase": "24/7 Towing", "scope": "global"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("Duplicate global-scope phrase must be rejected with 409")


def test_benefit_alias_scope_requirements():
    from app.services.benefit_setup_service import save_benefit_alias

    concept = _concept_row()
    company = SimpleNamespace(id="c1")
    db = FakeDb(rows={BenefitConcept: [concept], InsuranceCompany: [company]})

    try:
        save_benefit_alias(db, _staff(), {"benefit_id": concept.id, "phrase": "X", "scope": "company"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("Company scope without a company must be rejected")

    try:
        save_benefit_alias(db, _staff(), {"benefit_id": concept.id, "phrase": "X", "scope": "product", "product_id": "p1"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("Product scope with an unknown product must be rejected")

    try:
        save_benefit_alias(db, _staff(), {"benefit_id": concept.id, "phrase": "X", "scope": "bogus"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("Unknown scope must be rejected")


def test_benefit_alias_requires_existing_global_benefit():
    from app.services.benefit_setup_service import save_benefit_alias

    db = FakeDb(rows={BenefitConcept: []})
    try:
        save_benefit_alias(db, _staff(), {"benefit_id": "missing", "phrase": "X"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Missing global benefit must be rejected with 404")


# ---------------------------------------------------------------------------
# Packages (comprehensive chain | add-on bundles) and assignment context
# ---------------------------------------------------------------------------


def test_save_package_creates_and_links_unpackaged_catalog():
    from app.services.benefit_setup_service import save_package

    catalog = _catalog_row()
    revision = _revision_row()
    db = FakeDb(rows={BenefitCatalog: [catalog], BenefitCatalogRevision: [revision]})
    created = save_package(db, _staff(), "catalog-1", {"base_revision": 5, "name": "Plus"})
    assert created["package_kind"] == "comprehensive"
    assert created["package_key"] == "plus"
    assert str(catalog.package_id) == created["id"]
    assert db.commits == 1


def test_save_package_rejects_second_comprehensive_and_orphan_bundle():
    from app.services.benefit_setup_service import save_package

    first = BenefitPackage(id="package-1", catalog_revision_id="revision-1", package_key="plus", name="Plus", package_kind="comprehensive", sort_order=0)
    catalog = _catalog_row(package_id="package-1")
    revision = _revision_row()
    db = FakeDb(rows={BenefitCatalog: [catalog], BenefitCatalogRevision: [revision], BenefitPackage: [first]})

    try:
        save_package(db, _staff(), "catalog-1", {"base_revision": 5, "name": "Premier", "package_key": "premier"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("A second comprehensive package on one catalog must be rejected")

    unpackaged = FakeDb(rows={BenefitCatalog: [_catalog_row()], BenefitCatalogRevision: [revision]})
    try:
        save_package(unpackaged, _staff(), "catalog-1", {"base_revision": 5, "name": "OTO 360", "package_kind": "addon_bundle"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("An add-on bundle without a packaged catalog must be rejected")


def test_save_package_duplicate_key_and_bundle_on_packaged_catalog():
    from app.services.benefit_setup_service import save_package

    first = BenefitPackage(id="package-1", catalog_revision_id="revision-1", package_key="plus", name="Plus", package_kind="comprehensive", sort_order=0)
    catalog = _catalog_row(package_id="package-1")
    revision = _revision_row()
    db = FakeDb(rows={BenefitCatalog: [catalog], BenefitCatalogRevision: [revision], BenefitPackage: [first]})

    bundle = save_package(db, _staff(), "catalog-1", {"base_revision": 5, "name": "OTO 360", "package_key": "oto-360", "package_kind": "addon_bundle"})
    assert bundle["package_kind"] == "addon_bundle"
    assert str(catalog.package_id) == "package-1"  # bundle never becomes the catalog target

    try:
        save_package(db, _staff(), "catalog-1", {"base_revision": 5, "name": "Plus", "package_key": "plus"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("Duplicate package key must be rejected")


def test_clone_package_copies_assignments_as_explicit_rows():
    from app.services.benefit_setup_service import clone_package

    source = BenefitPackage(id="package-1", catalog_revision_id="revision-1", package_key="lite", name="Lite", package_kind="comprehensive", sort_order=0)
    offering_rows = [
        CatalogOffering(id="o1", catalog_revision_id="revision-1", offering_key="lite-towing", concept_id="b1", offering_kind="base", applies_to_type="package", applies_to_id="package-1", role="included", typed_value={"type": "distance", "value": "50", "unit": "km"}),
        CatalogOffering(id="o2", catalog_revision_id="revision-1", offering_key="lite-keys", concept_id="b2", offering_kind="optional", applies_to_type="package", applies_to_id="package-1", role="addon_option"),
        CatalogOffering(id="o3", catalog_revision_id="revision-1", offering_key="other", concept_id="b3", offering_kind="base", applies_to_type="package", applies_to_id="package-9", role="included"),
    ]
    catalog = _catalog_row(package_id="package-1")
    revision = _revision_row()
    db = FakeDb(rows={
        BenefitCatalog: [catalog], BenefitCatalogRevision: [revision], BenefitPackage: [source],
        CatalogOffering: offering_rows,
    })
    result = clone_package(db, _staff(), "catalog-1", "package-1", {"base_revision": 5, "name": "Plus", "package_key": "plus"})
    assert result["copied_assignments"] == 2
    copied = [item for item in db.rows.get(CatalogOffering, []) if item.id not in {"o1", "o2", "o3"}]
    assert len(copied) == 2
    assert all(str(item.applies_to_id) == result["package"]["id"] for item in copied)
    assert all(item.id not in {"o1", "o2", "o3"} for item in copied)
    assert all(item.offering_key.startswith("plus:") for item in copied)
    # Explicit copy: values are carried over, never inherited at runtime.
    assert {item.role for item in copied} == {"included", "addon_option"}


def test_assignment_context_validation():
    from app.services.business_setup_service import save_catalog_offering

    concept = BenefitConcept(id="b1", concept_key="towing", label="Towing")
    revision = _revision_row()

    product_catalog = _catalog_row()
    product_db = FakeDb(rows={BenefitCatalog: [product_catalog], BenefitCatalogRevision: [revision], BenefitConcept: [concept]})
    saved = save_catalog_offering(product_db, _staff(), "catalog-1", {
        "base_revision": 5, "offering_key": "towing", "concept_id": "b1", "offering_kind": "base",
        "role": "included", "typed_value": {"type": "distance", "value": "50", "unit": "km"},
    })
    assert saved["applies_to_type"] == "product"  # product-level default

    packaged = _catalog_row(package_id="package-1")
    packaged_db = FakeDb(rows={BenefitCatalog: [packaged], BenefitCatalogRevision: [revision], BenefitConcept: [concept]})
    try:
        save_catalog_offering(packaged_db, _staff(), "catalog-1", {
            "base_revision": 5, "offering_key": "towing", "concept_id": "b1", "offering_kind": "base",
            "applies_to_type": "product", "role": "included",
        })
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("Product-level assignment on a packaged catalog must be rejected")

    try:
        save_catalog_offering(packaged_db, _staff(), "catalog-1", {
            "base_revision": 5, "offering_key": "towing", "concept_id": "b1", "offering_kind": "base",
            "applies_to_type": "bundle", "applies_to_id": "missing-bundle", "role": "bundle_component",
        })
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("Unknown bundle assignment must be rejected")


def test_retire_package_blocks_catalog_target():
    from app.services.benefit_setup_service import retire_package

    source = BenefitPackage(id="package-1", catalog_revision_id="revision-1", package_key="plus", name="Plus", package_kind="comprehensive", sort_order=0)
    catalog = _catalog_row(package_id="package-1")
    revision = _revision_row()
    db = FakeDb(rows={BenefitCatalog: [catalog], BenefitCatalogRevision: [revision], BenefitPackage: [source]})
    try:
        retire_package(db, _staff(), "catalog-1", "package-1")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("Retiring the catalog's own package must be rejected")


def test_revision_content_payload_includes_packages_and_aliases():
    from app.services.business_setup_service import _revision_content_payload
    from app.rendering.render_context import canonical_context_hash

    revision = _revision_row()
    package = BenefitPackage(id="package-1", catalog_revision_id="revision-1", package_key="plus", name="Plus", package_kind="comprehensive", sort_order=10)
    offering = CatalogOffering(id="o1", catalog_revision_id="revision-1", offering_key="towing", concept_id="b1", offering_kind="base", applies_to_type="package", applies_to_id="package-1", role="included")
    alias = BenefitAlias(id="a1", benefit_id="b1", phrase="24/7 Towing", normalized_phrase="24 7 towing", scope="package", package_id="package-1", status="active")
    db = FakeDb(rows={
        BenefitCatalogRevision: [revision], BenefitPackage: [package], CatalogOffering: [offering],
        BenefitAlias: [alias],
    })
    payload = _revision_content_payload(db, revision)
    assert len(payload["offerings"]) == 1 and payload["offerings"][0]["role"] == "included"
    assert len(payload["packages"]) == 1 and payload["packages"][0]["package_kind"] == "comprehensive"
    assert len(payload["aliases"]) == 1 and payload["aliases"][0]["scope"] == "package"
    base_hash = canonical_context_hash(payload)

    changed = FakeDb(rows={
        BenefitCatalogRevision: [revision], BenefitPackage: [package], CatalogOffering: [offering],
        BenefitAlias: [BenefitAlias(id="a2", benefit_id="b1", phrase="Towing Assistance", normalized_phrase="towing assistance", scope="package", package_id="package-1", status="active")],
    })
    assert canonical_context_hash(_revision_content_payload(changed, revision)) != base_hash


def test_package_routes_are_wired(monkeypatch):
    monkeypatch.setattr(routes, "save_package", lambda _db, _user, catalog_id, payload: {"id": "p1", "catalog_revision_id": "r1", **payload})
    monkeypatch.setattr(
        routes,
        "clone_package",
        lambda _db, _user, catalog_id, package_id, payload: {"package": {"id": "p2", **payload}, "copied_assignments": 3},
    )
    monkeypatch.setattr(routes, "retire_package", lambda _db, _user, catalog_id, package_id: None)

    api = client()
    saved = api.post("/api/business/catalogs/catalog-1/packages", json={"base_revision": 5, "name": "Plus"})
    assert saved.status_code == 200
    assert saved.json()["package"]["package_kind"] == "comprehensive"
    assert api.post("/api/business/catalogs/catalog-1/packages", json={"name": "X"}).status_code == 422

    cloned = api.post("/api/business/catalogs/catalog-1/packages/p1/clone", json={"base_revision": 5, "package_key": "plus2", "name": "Plus 2"})
    assert cloned.status_code == 200
    assert cloned.json()["package"]["copied_assignments"] == 3

    assert api.delete("/api/business/catalogs/catalog-1/packages/p1").status_code == 204


def test_offering_save_accepts_assignment_fields(monkeypatch):
    captured = {}

    def save(_db, _user, catalog_id, payload):
        captured.update(payload)
        return {"id": "o1", **payload}

    monkeypatch.setattr(routes, "save_catalog_offering", save)
    response = client().post(
        "/api/business/catalogs/catalog-1/offerings",
        json={
            "base_revision": 5,
            "offering_key": "towing",
            "concept_id": "b1",
            "offering_kind": "base",
            "applies_to_type": "package",
            "applies_to_id": "p1",
            "role": "included",
            "typed_value": {"type": "money", "value": "300", "currency": "MYR", "semantic_role": "insured_limit"},
            "display_value": "RM300",
            "optional_price": None,
        },
    )
    assert response.status_code == 200
    assert captured["role"] == "included"
    assert captured["applies_to_id"] == "p1"
    assert captured["display_value"] == "RM300"

    bad_role = client().post(
        "/api/business/catalogs/catalog-1/offerings",
        json={"base_revision": 5, "offering_key": "x", "concept_id": "b1", "offering_kind": "base", "role": "default"},
    )
    assert bad_role.status_code == 422


def test_new_draft_revision_copies_forward_and_relinks_packages():
    from app.services.business_setup_service import create_new_draft_revision

    published = BenefitCatalogRevision(
        id="revision-pub", catalog_id="catalog-1", revision_number=3, state="published",
        source_document_ids=[], content_hash="abc", published_by=None, published_at=None,
    )
    package = BenefitPackage(id="package-1", catalog_revision_id="revision-pub", package_key="plus", name="Plus", package_kind="comprehensive", sort_order=10)
    offering = CatalogOffering(id="o1", catalog_revision_id="revision-pub", offering_key="plus-towing", concept_id="b1", offering_kind="base", applies_to_type="package", applies_to_id="package-1", role="included")
    alias = BenefitAlias(id="a1", benefit_id="b1", phrase="24/7 Towing", normalized_phrase="24 7 towing", scope="package", package_id="package-1", status="active")
    catalog = _catalog_row(package_id="package-1")
    db = FakeDb(rows={
        BenefitCatalog: [catalog], BenefitCatalogRevision: [published], BenefitPackage: [package],
        CatalogOffering: [offering], BenefitAlias: [alias],
    })
    result = create_new_draft_revision(db, _staff(), "catalog-1", base_revision=5)
    drafts = [item for item in db.rows.get(BenefitCatalogRevision, []) if item.state == "draft"]
    assert len(drafts) == 1 and drafts[0].revision_number == 4
    copied_packages = [item for item in db.rows.get(BenefitPackage, []) if item.id != "package-1"]
    copied_offerings = [item for item in db.rows.get(CatalogOffering, []) if item.id != "o1"]
    assert len(copied_packages) == 1 and len(copied_offerings) == 1
    assert copied_offerings[0].applies_to_id == copied_packages[0].id
    assert str(catalog.package_id) == copied_packages[0].id
    assert str(alias.package_id) == copied_packages[0].id
    assert result["revision"] == 6

    already_draft = FakeDb(rows={BenefitCatalog: [catalog], BenefitCatalogRevision: [published, drafts[0]]})
    try:
        create_new_draft_revision(already_draft, _staff(), "catalog-1", base_revision=6)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("Opening a second draft must be rejected")


def test_new_draft_route_is_wired(monkeypatch):
    monkeypatch.setattr(
        routes,
        "create_new_draft_revision",
        lambda _db, _user, catalog_id, **kwargs: {"id": catalog_id, "revision": 4, "status": "draft"},
    )
    response = client().post("/api/business/catalogs/catalog-1/new-draft", json={"base_revision": 3})
    assert response.status_code == 200
    assert response.json()["catalog"]["revision"] == 4
    assert client().post("/api/business/catalogs/catalog-1/new-draft", json={}).status_code == 422


def test_catalog_create_and_context_update_with_hierarchy_path():
    from app.services.business_setup_service import create_benefit_catalog, update_catalog_context

    company = InsuranceCompany(id="company-1", name="Insurer", category="Motor", source_template_category="Other / Unknown")
    segment = Segment(id="seg-1", segment_key="private", name="Private", sort_order=10, status="active")
    vehicle = VehicleCategory(id="veh-1", category_key="car", name="Car", sort_order=10, status="active")
    coverage = CoverageType(id="cov-1", coverage_key="comprehensive", name="Comprehensive", sort_order=10, status="active")

    db = FakeDb(rows={
        InsuranceCompany: [company], Segment: [segment], VehicleCategory: [vehicle], CoverageType: [coverage],
    })
    created = create_benefit_catalog(db, _staff(), {
        "company_id": "company-1", "name": "Q Drive", "segment_id": "seg-1",
        "vehicle_category_id": "veh-1", "coverage_type_id": "cov-1",
    })
    assert created["segment_id"] == "seg-1"
    assert created["coverage_type_id"] == "cov-1"

    catalog = db.get(BenefitCatalog, created["id"])
    updated = update_catalog_context(db, _staff(), created["id"], {"base_revision": 1, "vehicle_category_id": "veh-1"})
    assert updated["vehicle_category_id"] == "veh-1"
    assert catalog.revision == 2

    bad = FakeDb(rows={InsuranceCompany: [company]})
    try:
        create_benefit_catalog(bad, _staff(), {"company_id": "company-1", "name": "X", "segment_id": "missing"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("Invalid path context id must be rejected")


def test_clone_package_across_catalogs_copies_from_source_revision():
    from app.services.benefit_setup_service import clone_package

    other_revision = BenefitCatalogRevision(
        id="revision-other", catalog_id="catalog-9", revision_number=2, state="published",
        source_document_ids=[], content_hash="xyz", published_by=None, published_at=None,
    )
    source = BenefitPackage(id="package-lite", catalog_revision_id="revision-other", package_key="lite", name="Lite", package_kind="comprehensive", sort_order=0)
    source_offering = CatalogOffering(id="o-lite", catalog_revision_id="revision-other", offering_key="lite-towing", concept_id="b1", offering_kind="base", applies_to_type="package", applies_to_id="package-lite", role="included")

    catalog = _catalog_row()
    revision = _revision_row()
    db = FakeDb(rows={
        BenefitCatalog: [catalog], BenefitCatalogRevision: [revision, other_revision],
        BenefitPackage: [source], CatalogOffering: [source_offering],
    })
    result = clone_package(db, _staff(), "catalog-1", "package-lite", {"base_revision": 5, "name": "Plus", "package_key": "plus"})
    assert result["copied_assignments"] == 1
    copied = [item for item in db.rows.get(CatalogOffering, []) if item.id != "o-lite"]
    assert len(copied) == 1
    assert copied[0].applies_to_id == result["package"]["id"]
    assert copied[0].catalog_revision_id == "revision-1"
    assert str(catalog.package_id) == result["package"]["id"]


def test_alias_route_accepts_scope_filters(monkeypatch):
    captured = {}

    def listing(_db, _user, **kwargs):
        captured.update(kwargs)
        return {"items": [], "total": 0, **kwargs}

    monkeypatch.setattr(routes, "list_benefit_aliases", listing)
    response = client().get("/api/business/benefit-aliases?scope=package&package_id=p1&benefit_id=b1")
    assert response.status_code == 200
    assert captured["scope"] == "package"
    assert captured["package_id"] == "p1"
    assert captured["benefit_id"] == "b1"


def test_catalog_context_route_is_wired(monkeypatch):
    monkeypatch.setattr(
        routes,
        "update_catalog_context",
        lambda _db, _user, catalog_id, payload: {"id": catalog_id, "revision": 3, **payload},
    )
    response = client().post(
        "/api/business/catalogs/catalog-1/context",
        json={"base_revision": 2, "segment_id": "seg-1", "coverage_type_id": "cov-1"},
    )
    assert response.status_code == 200
    assert response.json()["catalog"]["segment_id"] == "seg-1"
    assert client().post("/api/business/catalogs/catalog-1/context", json={}).status_code == 422


def test_description_variants_are_validated_and_serialized():
    from app.services.business_setup_service import save_benefit_concept

    def fresh():
        return BenefitConcept(id="b1", concept_key="towing", label="Towing", revision=1)

    db = FakeDb(rows={BenefitConcept: [fresh()]})

    saved = save_benefit_concept(db, _staff(), {
        "id": "b1", "base_revision": 1, "concept_key": "towing", "label": "Towing",
        "description_variants": [
            {"key": "distance", "template": "Coverage up to {value} km", "value_type": "distance", "demo_value": {"value": "50", "unit": "km"}},
            {"key": "money", "template": "Coverage up to RM {value}", "value_type": "money", "demo_value": {"value": "300"}},
        ],
    })
    assert len(saved["description_variants"]) == 2
    assert saved["description_variants"][0]["value_type"] == "distance"

    too_many = FakeDb(rows={BenefitConcept: [fresh()]})
    try:
        save_benefit_concept(too_many, _staff(), {
            "id": "b1", "base_revision": 1, "concept_key": "towing", "label": "Towing",
            "description_variants": [
                {"key": "a", "template": "X {value}", "value_type": "money"},
                {"key": "b", "template": "Y {value}", "value_type": "money"},
                {"key": "c", "template": "Z {value}", "value_type": "money"},
            ],
        })
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("More than two variants must be rejected")

    no_placeholder = FakeDb(rows={BenefitConcept: [fresh()]})
    try:
        save_benefit_concept(no_placeholder, _staff(), {
            "id": "b1", "base_revision": 1, "concept_key": "towing", "label": "Towing",
            "description_variants": [{"key": "a", "template": "Coverage up to RM 300", "value_type": "money"}],
        })
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("A template without {value} must be rejected")

    bad_type = FakeDb(rows={BenefitConcept: [fresh()]})
    try:
        save_benefit_concept(bad_type, _staff(), {
            "id": "b1", "base_revision": 1, "concept_key": "towing", "label": "Towing",
            "description_variants": [{"key": "a", "template": "X {value}", "value_type": "per_day"}],
        })
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("An unknown variant type must be rejected")


def test_concept_save_route_carries_description_variants(monkeypatch):
    captured = {}

    def save(_db, _user, payload):
        captured.update(payload)
        return {"id": "b1", **payload}

    monkeypatch.setattr(routes, "save_benefit_concept", save)
    response = client().post(
        "/api/business/benefit-concepts",
        json={
            "concept_key": "towing", "label": "Towing",
            "description_variants": [{"key": "money", "template": "Coverage up to RM {value}", "value_type": "money"}],
        },
    )
    assert response.status_code == 200
    assert captured["description_variants"][0]["template"] == "Coverage up to RM {value}"


# ---------------------------------------------------------------------------
# 033 seed rows and ledger discipline
# ---------------------------------------------------------------------------


def test_migration_033_seeds_hierarchy_defaults():
    sql = (ROOT / "migrations" / "033_benefits_package_hierarchy.sql").read_text(encoding="utf-8")
    assert "INSERT INTO public.segments" in sql and "Private" in sql and "Company / Commercial" in sql
    assert "INSERT INTO public.vehicle_categories" in sql and "Motorcycle" in sql and "Commercial Vehicle" in sql
    assert "INSERT INTO public.vehicle_subcategories" in sql and "Lorry / Truck" in sql and "Van" in sql and "Bus" in sql
    assert "INSERT INTO public.coverage_types" in sql and "Comprehensive" in sql and "Third Party Fire & Theft" in sql and "Third Party" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql and "REVOKE ALL PRIVILEGES" in sql
    assert "ON CONFLICT" in sql


def test_catalog_offering_delete_route_returns_204(monkeypatch):
    called = {}
    def mock_remove(db, user, catalog_id, offering_id, *, base_revision=None):
        called["catalog_id"] = catalog_id
        called["offering_id"] = offering_id
        called["base_revision"] = base_revision
    monkeypatch.setattr(routes, "remove_catalog_offering", mock_remove)
    response = client().delete("/api/business/catalogs/cat-1/offerings/off-1?base_revision=2")
    assert response.status_code == 204
    assert called == {"catalog_id": "cat-1", "offering_id": "off-1", "base_revision": 2}


def test_save_package_update_renames_existing_tier():
    from app.services.benefit_setup_service import save_package

    pkg = BenefitPackage(id="pkg1", catalog_revision_id="revision-1", package_key="lite", name="Lite", package_kind="comprehensive", sort_order=1)
    catalog = _catalog_row(package_id="pkg1")
    revision = _revision_row()
    db = FakeDb(rows={BenefitCatalog: [catalog], BenefitCatalogRevision: [revision], BenefitPackage: [pkg]})

    updated = save_package(
        db,
        _staff(),
        "catalog-1",
        {"base_revision": 5, "id": "pkg1", "name": "auto365 Comprehensive Lite", "package_key": "auto365-comprehensive-lite", "package_kind": "comprehensive", "sort_order": 1},
    )

    assert updated["name"] == "auto365 Comprehensive Lite"
    assert updated["package_key"] == "auto365-comprehensive-lite"
    assert pkg.name == "auto365 Comprehensive Lite"
    assert pkg.package_kind == "comprehensive"
    assert db.commits == 1


def test_package_update_route_wires_service_with_id(monkeypatch):
    captured = {}

    def fake_save(db, user, catalog_id, payload):
        captured.update(payload)
        return {"id": payload.get("id"), "name": payload.get("name")}

    monkeypatch.setattr(routes, "save_package", fake_save)
    response = client().put(
        "/api/business/catalogs/cat-1/packages/pkg-9",
        json={"base_revision": 2, "name": "Renamed Tier"},
    )

    assert response.status_code == 200
    assert captured["id"] == "pkg-9"
    assert captured["name"] == "Renamed Tier"


def test_assignment_context_keeps_explicit_package_target_for_other_tiers():
    from app.services.business_setup_service import _validate_assignment_context

    lite = BenefitPackage(id="package-1", catalog_revision_id="revision-1", package_key="lite", name="Lite", package_kind="comprehensive", sort_order=1)
    plus = BenefitPackage(id="package-2", catalog_revision_id="revision-1", package_key="plus", name="Plus", package_kind="comprehensive", sort_order=2)
    catalog = _catalog_row(package_id="package-1")
    revision = _revision_row()
    db = FakeDb(rows={BenefitCatalog: [catalog], BenefitCatalogRevision: [revision], BenefitPackage: [lite, plus]})

    payload = _validate_assignment_context(
        db,
        catalog,
        revision,
        {"applies_to_type": "package", "applies_to_id": "package-2", "role": "addon_option"},
    )

    assert payload["applies_to_id"] == "package-2"


def test_assignment_context_rejects_package_from_another_revision():
    from app.services.business_setup_service import _validate_assignment_context

    lite = BenefitPackage(id="package-1", catalog_revision_id="revision-1", package_key="lite", name="Lite", package_kind="comprehensive", sort_order=1)
    foreign = BenefitPackage(id="package-foreign", catalog_revision_id="revision-other", package_key="stray", name="Stray", package_kind="comprehensive", sort_order=1)
    catalog = _catalog_row(package_id="package-1")
    revision = _revision_row()
    db = FakeDb(rows={BenefitCatalog: [catalog], BenefitCatalogRevision: [revision], BenefitPackage: [lite, foreign]})

    try:
        _validate_assignment_context(db, catalog, revision, {"applies_to_type": "package", "applies_to_id": "package-foreign", "role": "addon_option"})
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("A package from another revision must be rejected")

