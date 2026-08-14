import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings


VALID_ENV = {
    "APP_ENV": "test",
    "DATABASE_PROVIDER": "supabase_postgres",
    "DATABASE_URL": "postgresql://postgres:password@db.project.supabase.co:5432/postgres",
    "AUTH_HASH_SECRET": "test-secret-value-that-is-long-enough",
    "STORAGE_DRIVER": "supabase",
    "SUPABASE_URL": "https://project.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
}


def test_supabase_storage_is_required():
    env = {**VALID_ENV, "STORAGE_DRIVER": "local"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="must be 'supabase'"):
            get_settings()


@pytest.mark.parametrize("missing", ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"])
def test_supabase_storage_credentials_are_required(missing: str):
    env = {key: value for key, value in VALID_ENV.items() if key != missing}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match=f"{missing} is required"):
            get_settings()


def test_supabase_url_requires_https():
    env = {**VALID_ENV, "SUPABASE_URL": "http://project.supabase.co"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="must be an HTTPS"):
            get_settings()


def test_separate_production_resource_limits_are_loaded():
    env = {
        **VALID_ENV,
        "MAX_SOURCE_PDF_BYTES": "20971520",
        "MAX_PDF_PAGES": "100",
        "MAX_GENERATED_PDF_BYTES": "26214400",
        "MAX_ASSET_BYTES": "10485760",
        "MAX_ASSET_PIXELS": "32000000",
        "MAX_CATALOG_IMPORT_BYTES": "5242880",
        "MAX_CATALOG_IMPORT_ROWS": "5000",
        "MAX_TEMPLATE_JSON_BYTES": "2097152",
        "MAX_TEMPLATE_ELEMENTS": "2000",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = get_settings()
    assert settings.max_source_pdf_bytes == 20 * 1024 * 1024
    assert settings.max_pdf_pages == 100
    assert settings.max_generated_pdf_bytes == 25 * 1024 * 1024
    assert settings.max_asset_bytes == 10 * 1024 * 1024
    assert settings.max_asset_pixels == 32_000_000
    assert settings.max_catalog_import_bytes == 5 * 1024 * 1024
    assert settings.max_catalog_import_rows == 5_000
    assert settings.max_template_json_bytes == 2 * 1024 * 1024
    assert settings.max_template_elements == 2_000
    assert settings.max_upload_bytes == settings.max_source_pdf_bytes
    assert settings.max_upload_files == 1


def test_new_upload_count_is_fixed_to_one():
    env = {**VALID_ENV, "MAX_UPLOAD_FILES": "10"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="MAX_UPLOAD_FILES must be 1"):
            get_settings()


def test_invalid_max_upload_files_is_rejected():
    env = {**VALID_ENV, "MAX_UPLOAD_FILES": "200"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="MAX_UPLOAD_FILES"):
            get_settings()


def test_invalid_storage_retention_is_rejected():
    env = {**VALID_ENV, "PDF_RETENTION_DAYS": "0"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="PDF_RETENTION_DAYS"):
            get_settings()
