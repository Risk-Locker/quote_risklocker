"""Unit test verifying host.docker.internal fallback to 127.0.0.1 on host machines."""

import os
from unittest.mock import patch
import socket
import pytest

from app.core.config import _database_url, _storage_settings


def test_database_url_resolves_host_docker_internal_fallback(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:secret@host.docker.internal:54322/postgres")
    
    with patch("socket.gethostbyname", side_effect=socket.gaierror(-2, "Name or service not known")):
        resolved = _database_url("production")
        assert "127.0.0.1:54322" in resolved
        assert "host.docker.internal" not in resolved


def test_storage_settings_resolves_host_docker_internal_fallback(monkeypatch):
    monkeypatch.setenv("STORAGE_DRIVER", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "http://host.docker.internal:8000")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test_key_at_least_32_characters_long_12345")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "risklocker-pdfs")

    with patch("socket.gethostbyname", side_effect=socket.gaierror(-2, "Name or service not known")):
        driver, url, key, bucket = _storage_settings()
        assert url == "http://127.0.0.1:8000"
