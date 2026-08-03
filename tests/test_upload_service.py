"""Smoke test that upload_service imports resolve correctly."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_PROVIDER": "supabase_postgres",
        "DATABASE_URL": "postgresql://postgres:password@db.test.supabase.co:5432/postgres",
        "AUTH_HASH_SECRET": "test-auth-hash-secret-that-is-long-enough",
        "STORAGE_DRIVER": "supabase",
        "SUPABASE_URL": "https://project-ref.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    }
)

from app.services.upload_service import create_batch_from_uploads, _cannot_read_result
from app.models.tables import VehicleBrand, VehicleModel


def test_cannot_read_result_returns_expected_shape():
    result = _cannot_read_result()
    assert result["draft"]["status"] == "Cannot Read"
    assert result["full_record"]["reading_quality"] == "cannot_read"


def test_vehicle_brand_model_are_imported():
    assert VehicleBrand is not None
    assert VehicleModel is not None
    assert getattr(create_batch_from_uploads, "__name__", "") == "create_batch_from_uploads"
