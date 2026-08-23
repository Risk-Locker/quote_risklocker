"""HTTP contract for the company-first v7 Business Setup workspace."""

from __future__ import annotations

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


def client():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="staff-1", role="staff")
    return TestClient(app)


def test_paginated_company_list_and_company_workspace(monkeypatch):
    monkeypatch.setattr(
        routes,
        "list_business_companies",
        lambda _db, _user, **kwargs: {"items": [{"id": "c1", "name": "QBE"}], "total": 1, **kwargs},
    )
    monkeypatch.setattr(
        routes,
        "get_business_company_workspace",
        lambda _db, _user, company_id: {"company": {"id": company_id}, "products": [], "tiers": [], "catalogs": []},
    )

    response = client().get("/api/business/companies?search=qbe&page=2&page_size=20")
    assert response.status_code == 200
    assert response.json()["companies"]["items"][0]["name"] == "QBE"
    assert response.json()["companies"]["page"] == 2

    workspace = client().get("/api/business/companies/c1/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["workspace"]["company"]["id"] == "c1"


def test_staff_can_create_company_product_tier_and_typed_concept(monkeypatch):
    monkeypatch.setattr(routes, "save_business_company", lambda _db, _user, payload: {"id": "c1", **payload})
    monkeypatch.setattr(routes, "save_business_product", lambda _db, _user, payload: {"id": "p1", **payload})
    monkeypatch.setattr(routes, "save_business_tier", lambda _db, _user, payload: {"id": "t1", **payload})
    monkeypatch.setattr(routes, "save_benefit_concept", lambda _db, _user, payload: {"id": "b1", **payload})

    company = client().post("/api/business/companies", json={"name": "New Insurer"})
    assert company.status_code == 200
    assert company.json()["company"]["id"] == "c1"

    product = client().post("/api/business/products", json={"company_id": "c1", "name": "Motor Plus"})
    assert product.status_code == 200
    tier = client().post("/api/business/tiers", json={"product_id": "p1", "name": "Premier"})
    assert tier.status_code == 200

    concept = client().post(
        "/api/business/benefit-concepts",
        json={
            "concept_key": "towing",
            "label": "Towing",
            "value_schema": {"type": "distance"},
            "display_template": "{value} {unit}",
            "required_variables": ["value", "unit"],
        },
    )
    assert concept.status_code == 200
    assert concept.json()["benefit_concept"]["concept_key"] == "towing"


def test_catalog_offering_requires_typed_value_and_base_revision(monkeypatch):
    captured = {}

    def save(_db, _user, catalog_id, payload):
        captured.update(catalog_id=catalog_id, payload=payload)
        return {"id": "offering-1", **payload}

    monkeypatch.setattr(routes, "save_catalog_offering", save)
    response = client().post(
        "/api/business/catalogs/catalog-1/offerings",
        json={
            "base_revision": 3,
            "offering_key": "towing-300",
            "concept_id": "benefit-1",
            "offering_kind": "upgrade",
            "typed_value": {"type": "distance", "value": 300, "unit": "km"},
            "source_document_id": "source-1",
            "source_citation": {"page": 2},
        },
    )
    assert response.status_code == 200
    # Decimal values cross the JSON boundary as exact strings so values such
    # as 999 or 1,200 are never rounded by binary floating-point conversion.
    assert captured["payload"]["typed_value"]["value"] == "300"

    missing_revision = client().post(
        "/api/business/catalogs/catalog-1/offerings",
        json={"offering_key": "x", "concept_id": "b", "offering_kind": "base"},
    )
    assert missing_revision.status_code == 422


def test_catalog_publish_requires_base_revision_and_returns_published_catalog(monkeypatch):
    captured = {}

    def publish(_db, _user, catalog_id, *, base_revision):
        captured.update(catalog_id=catalog_id, base_revision=base_revision)
        return {"id": catalog_id, "name": "Premier", "revision": base_revision + 1, "status": "published"}

    monkeypatch.setattr(routes, "publish_catalog_revision", publish)
    response = client().post(
        "/api/business/catalogs/catalog-1/publish",
        json={"base_revision": 3},
    )
    assert response.status_code == 200
    assert response.json()["catalog"]["status"] == "published"
    assert captured == {"catalog_id": "catalog-1", "base_revision": 3}

    missing = client().post("/api/business/catalogs/catalog-1/publish", json={})
    assert missing.status_code == 422


def test_company_detection_aliases_live_under_business_api(monkeypatch):
    monkeypatch.setattr(
        routes,
        "list_company_aliases",
        lambda _db, _user, **kwargs: {
            "items": [{"id": "a1", "company_id": "c1", "company_name": "QBE", "alias": "QBE Insurance"}],
            "total": 1,
            **kwargs,
        },
        raising=False,
    )
    monkeypatch.setattr(
        routes,
        "save_company_alias",
        lambda _db, _user, payload: {"id": "a1", **payload, "normalized_alias": "qbe insurance"},
        raising=False,
    )

    response = client().get("/api/business/company-aliases?search=qbe&page=1&page_size=25")
    assert response.status_code == 200
    assert response.json()["aliases"]["items"][0]["company_name"] == "QBE"

    saved = client().post(
        "/api/business/company-aliases",
        json={"company_id": "c1", "alias": "QBE Insurance", "alias_kind": "detection"},
    )
    assert saved.status_code == 200
    assert saved.json()["company_alias"]["normalized_alias"] == "qbe insurance"


def test_crud_lifecycle_operations_contract(monkeypatch):
    monkeypatch.setattr(routes, "save_business_product", lambda _db, _user, payload: {"id": payload.get("id", "p1"), "name": payload["name"]})
    monkeypatch.setattr(routes, "delete_business_product", lambda _db, _user, product_id: None)
    monkeypatch.setattr(routes, "save_business_tier", lambda _db, _user, payload: {"id": payload.get("id", "t1"), "name": payload["name"]})
    monkeypatch.setattr(routes, "delete_business_tier", lambda _db, _user, tier_id: None)
    monkeypatch.setattr(routes, "retire_benefit_concept", lambda _db, _user, concept_id: None)
    monkeypatch.setattr(routes, "save_company_alias", lambda _db, _user, payload: {"id": payload.get("id", "a1"), "alias": payload["alias"]})
    monkeypatch.setattr(routes, "save_benefit_alias", lambda _db, _user, payload: {"id": payload.get("id", "ba1"), "phrase": payload["phrase"]})
    monkeypatch.setattr(routes, "retire_benefit_catalog", lambda _db, _user, catalog_id: None)
    monkeypatch.setattr(routes, "save_plan", lambda _db, _user, cat_id, pkg_id, payload: {"id": payload.get("id", "pl1"), "name": payload["name"]})

    # 1. Product PUT & DELETE
    put_prod = client().put("/api/business/products/p1", json={"name": "Motor Plus Updated"})
    assert put_prod.status_code == 200
    assert put_prod.json()["product"]["id"] == "p1"
    assert put_prod.json()["product"]["name"] == "Motor Plus Updated"

    del_prod = client().delete("/api/business/products/p1")
    assert del_prod.status_code == 204

    # 2. Tier PUT & DELETE
    put_tier = client().put("/api/business/tiers/t1", json={"name": "Premier Plus"})
    assert put_tier.status_code == 200
    assert put_tier.json()["tier"]["id"] == "t1"

    del_tier = client().delete("/api/business/tiers/t1")
    assert del_tier.status_code == 204

    # 3. Concept DELETE (retire)
    del_concept = client().delete("/api/business/benefit-concepts/b1")
    assert del_concept.status_code == 204

    # 4. Company alias PUT
    put_alias = client().put("/api/business/company-aliases/a1", json={"alias": "QBE Malaysia"})
    assert put_alias.status_code == 200
    assert put_alias.json()["company_alias"]["alias"] == "QBE Malaysia"

    # 5. Benefit alias PUT
    put_balias = client().put("/api/business/benefit-aliases/ba1", json={"benefit_id": "b1", "phrase": "24/7 Towing"})
    assert put_balias.status_code == 200
    assert put_balias.json()["benefit_alias"]["phrase"] == "24/7 Towing"

    # 6. Catalog DELETE (retire)
    del_catalog = client().delete("/api/business/catalogs/cat-1")
    assert del_catalog.status_code == 204

    # 7. Plan PUT
    put_plan = client().put("/api/business/catalogs/cat-1/packages/pkg-1/plans/pl1", json={"name": "Plan B", "base_revision": 1})
    assert put_plan.status_code == 200
    assert put_plan.json()["plan"]["id"] == "pl1"
