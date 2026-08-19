"""Tests for centralized API error handlers (backend/app/core/errors.py)."""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.errors import AppError, register_error_handlers


class SampleModel(BaseModel):
    name: str = Field(min_length=3)
    age: int = Field(gt=0)


def create_test_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/test/validation")
    def test_validation(body: SampleModel):
        return {"status": "ok", "data": body.model_dump()}

    @app.get("/test/app-error")
    def test_app_error():
        raise AppError("Custom business logic error", status_code=400)

    @app.get("/test/integrity-unique")
    def test_integrity_unique():
        orig_err = Exception('duplicate key value violates unique constraint "uq_benefit_concept_key"')
        raise IntegrityError("INSERT INTO ...", params={}, orig=orig_err)

    @app.get("/test/integrity-fk")
    def test_integrity_fk():
        orig_err = Exception('violates foreign key constraint "fk_catalog_company"')
        raise IntegrityError("INSERT INTO ...", params={}, orig=orig_err)

    @app.get("/test/integrity-not-null")
    def test_integrity_not_null():
        orig_err = Exception('null value in column "label" violates not-null constraint')
        raise IntegrityError("INSERT INTO ...", params={}, orig=orig_err)

    @app.get("/test/unhandled")
    def test_unhandled():
        raise RuntimeError("Unexpected server crash")

    return app


@pytest.fixture
def error_client():
    app = create_test_app()
    return TestClient(app, raise_server_exceptions=False)


def test_validation_error_returns_structured_422(error_client):
    res = error_client.post("/test/validation", json={"name": "a", "age": -5})
    assert res.status_code == 422
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "validation_error"
    assert data["error"]["message"] == "Request validation failed."
    assert isinstance(data["error"]["details"], list)
    assert len(data["error"]["details"]) >= 2
    fields = [d["field"] for d in data["error"]["details"]]
    assert any("name" in f for f in fields)
    assert any("age" in f for f in fields)


def test_app_error_returns_status_and_message(error_client):
    res = error_client.get("/test/app-error")
    assert res.status_code == 400
    data = res.json()
    assert data["error"]["message"] == "Custom business logic error"


def test_integrity_unique_constraint_returns_409_friendly_message(error_client):
    res = error_client.get("/test/integrity-unique")
    assert res.status_code == 409
    data = res.json()
    assert data["error"]["code"] == "conflict"
    assert data["error"]["message"] == "A Global Benefit with this key already exists."


def test_integrity_fk_returns_422_friendly_message(error_client):
    res = error_client.get("/test/integrity-fk")
    assert res.status_code == 422
    data = res.json()
    assert data["error"]["code"] == "invalid_reference"
    assert "references a value that does not exist" in data["error"]["message"]


def test_integrity_not_null_returns_422_friendly_message(error_client):
    res = error_client.get("/test/integrity-not-null")
    assert res.status_code == 422
    data = res.json()
    assert data["error"]["code"] == "invalid_reference"
    assert "required field is missing" in data["error"]["message"]


def test_unhandled_exception_returns_500_safe_message(error_client):
    res = error_client.get("/test/unhandled")
    assert res.status_code == 500
    data = res.json()
    assert data["error"]["message"] == "Internal server error"
