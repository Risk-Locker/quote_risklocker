---
name: python-testing
description: Write and maintain 100% hermetic pytest suites for FastAPI, SQLAlchemy, Decimal monetary engines, PDF extraction mocks, and RBAC security assertions using in-memory SQLite without ever touching live Postgres.
---

# Hermetic Python & FastAPI Testing Skill (`pytest`)

All backend tests inside `tests/` MUST run **100% hermetically** against in-memory SQLite (`sqlite:///:memory:`) and mocks (`AGENTS.md` Section 4). Never allow `SessionLocal()`, live Supabase calls, or live Gemini API requests inside `pytest`.

## 1. Core Testing Laws

1. **Zero Live Network / DB Calls:** Import and isolate database fixtures cleanly from `tests/conftest.py` (`db_session`, `client`, `auth_headers`, `monkeypatch`). Confirm tests pass offline with `.env` DB variables unset or pointed at SQLite `:memory:`.
2. **Red-First Regression Workflow (`test-driven-development`):**
   - For any bugfix (`F-01`..`F-09`), author the failing test reproducing the exact defect BEFORE modifying `backend/app/`.
   - Execute `.\.venv\Scripts\python.exe -m pytest tests/test_<target>.py -q` and observe the genuine expected failure first.
3. **Boundary & `Decimal` Exactness:**
   - Assert money equality with `Decimal("842.50")`, never floats (`assert result == Decimal("842.50")` rather than `842.5`).
   - Test every progressive bracket boundary (`2500cc` vs `2501cc`), EV `W -> kW` conversion (`150000` -> `150`), Feb 29 leap-year expiry (`2024-02-29 -> 2025-02-28`), null/whitespace inputs, and double-entry balance `SUM(debit) == SUM(credit)`.
4. **Security & Method Purity Assertions:**
   - Assert HTTP `GET` routes commit ZERO rows (`db.query(...).count()` unchanged before vs after `GET`).
   - Assert staff vs admin `403` RBAC (`test_http_security.py`), missing CSRF rejection, upload size/magic-byte rejection (`test_upload_limits.py`), and fail-closed behavior when `storage=None`.

## 2. Anti-Pattern vs Hermetic Pytest Standard

| Anti-Pattern (Blocked) | Risklocker Hermetic Standard |
| :--- | :--- |
| Importing real `SessionLocal()` inside test functions | Inject `db_session` SQLite in-memory fixture from `conftest.py` |
| Writing test against buggy code after already patching it | Run test on unpatched branch/code FIRST to observe red failure |
| Asserting `round(val, 2) == 842.5` with Python floats | Assert `result == Decimal("842.50")` (`ROUND_HALF_UP`) |
| Skipping RBAC / IDOR / negative-value validation cases | Test `401` unauth, `403` staff-only denial, `422` negative bounds |

## 3. Verification Commands & Detailed Patterns

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest -q
```
Load `references/hermetic-pytest-patterns.md` for FastAPI `dependency_overrides`, SQLite `transaction` rollback isolation, Gemini HTTP mocking, and CLI verification commands.
