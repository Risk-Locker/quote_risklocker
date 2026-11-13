# Hermetic Pytest Fixtures, Mocks & Boundary Patterns

## 1. Blocking Accidental Live DB / External HTTP Calls

```python
import pytest
from decimal import Decimal
from datetime import date

def test_road_tax_monotonic_above_2500cc():
    # Pure engine test: zero DB, zero HTTP, exact Decimal equality
    saloon_2500 = calculate_peninsular_saloon_private(2500)
    saloon_2501 = calculate_peninsular_saloon_private(2501)
    assert isinstance(saloon_2501, Decimal)
    assert saloon_2501 >= saloon_2500  # Guards F-06 cliff regression

def test_gemini_extraction_handles_429_and_multipage(monkeypatch, db_session):
    calls = {"count": 0}
    def fake_post(*args, **kwargs):
        calls["count"] += 1
        # Simulate first-key 429 rate-limit, second-key clean 200 payload
        ...
    monkeypatch.setattr("httpx.Client.post", fake_post)
    # Run extractor and assert mid-document endorsement extracted + confidence calibrated (never hardcoded 0.99)
```

## 2. Read-Only HTTP `GET` Regression Pattern (`F-07`)

```python
def test_get_comparison_does_not_mutate_database(client, db_session, auth_headers):
    before_count = db_session.query(ComparisonSession).count()
    resp = client.get("/api/comparison/non-existent-id", headers=auth_headers)
    assert resp.status_code in (404, 422)
    assert db_session.query(ComparisonSession).count() == before_count
```

## 3. Mandatory Full Verification Commands

```powershell
# Targeted fast loop while developing
.\.venv\Scripts\python.exe -m pytest tests/test_target.py -q

# Full hermetic suite + schema migration version check before claiming completion
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -c "from app.db.session import verify_schema_version; verify_schema_version(); print('schema OK')"
.\.venv\Scripts\python.exe -m pytest -q
```

