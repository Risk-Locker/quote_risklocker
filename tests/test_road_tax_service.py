"""Regression tests for road-tax service edge cases."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


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

from app.services.road_tax_service import _eval_formula


def test_eval_formula_returns_none_for_empty_formula():
    assert _eval_formula("", 1800) is None


def test_eval_formula_returns_none_for_invalid_characters():
    assert _eval_formula("__import__('os').system('x')", 1800) is None


def test_eval_formula_evaluates_safe_expression():
    assert _eval_formula("280 + 0.5 * (cc - 1800)", 2000) == 380.0


def test_eval_formula_returns_none_for_syntax_error():
    assert _eval_formula("280 + * (cc - 1800)", 2000) is None


def test_eval_formula_returns_none_for_undefined_name():
    assert _eval_formula("cc + unknown", 2000) is None


def test_eval_formula_returns_none_for_type_error():
    assert _eval_formula("cc + 'text'", 2000) is None
