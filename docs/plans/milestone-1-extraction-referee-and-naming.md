# Milestone 1: Extraction Referee Gate & Vehicle Naming Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` and `systematic-debugging` to execute this plan cleanly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the autonomous Extraction & Post-Processing Referee (`app/extraction/referee.py`) to fact-check extraction contradictions (Company vs Private, Lorry / Commercial vs Private Car), fix `customer_name=""` in comparison classifier, fix `is_comprehensive_private=True` hardcoding, fix vehicle naming capitalization (`V116-HA`), and deduplicate brand prefixing in Marketing Comparison.

**Architecture:**
1. A new pure domain referee `audit_and_reconcile_draft(fields: dict, raw_text: str = "") -> tuple[dict, list[str]]` inspects extracted fields for logical contradictions. If customer is `SDN BHD` or vehicle is a Lorry/Goods vehicle (`Daihatsu Delta`, `3000 KG`, `'C' PERMIT`), it forces `client_type = "Company"`, `vehicle_type = "Lorry"`, and purges bogus `Private Car` labels from `product_name` and `coverage_type`.
2. `backend/app/workers/extraction_worker.py` and `backend/app/extraction/draft_mapper.py` execute this referee pass right after initial candidate mapping and right before persistence.
3. `backend/app/services/marketing_comparison_service.py` is updated to pass actual `customer_name` to `classify_client_entity` and set `is_comprehensive_private = (resolved_vtype in ("Car", "NonSaloonCar", "EVSaloonCar", "EVNonSaloonCar") and entity_type == "Private")`.
4. `backend/app/services/vehicle_simplifier_service.py` regex token formatting is updated to preserve uppercase letters in alphanumeric model codes (e.g. `V116-HA`, `BLM`, `XLE`).
5. `frontend/src/components/comparison/components/CustomerVehicleLedgerPane.tsx` deduplicates `car_brand` when `vehicle_model` already starts with the brand name.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, TypeScript, React 19.

---

### Task 1: Extraction Referee Unit Tests (Red)

**Files:**
- Create: `tests/unit/test_extraction_referee.py`

- [ ] **Step 1: Write failing tests for referee fact-checker and vehicle naming**

```python
import pytest
from app.extraction.referee import audit_and_reconcile_draft
from app.services.vehicle_simplifier_service import clean_vehicle_tokens_deterministic

def test_referee_detects_company_and_lorry_contradiction():
    # Scenario: AmAssurance quotation for a lorry owned by SDN BHD, but product says 'Private Car Comprehensive'
    fields = {
        "customer_name": {"value": "CHIN YING TRADING SDN BHD", "status": "ready"},
        "car_brand": {"value": "DAIHATSU", "status": "ready"},
        "car_model": {"value": "Daihatsu Delta V116ha", "status": "ready"},
        "vehicle_type": {"value": "Car", "status": "ready"},  # Wrongly set to Car
        "product_name": {"value": "Private Car Comprehensive", "status": "ready"}, # Contradiction!
        "engine_cc": {"value": "3000 KG", "status": "ready"},
    }
    raw_text = "QUOTATION Liberty General Insurance Berhad Insured Name CHIN YING TRADING SDN BHD 'C' PERMIT GOODS VEHICLE 3000 KG DAIHATSU DELTA V116HA"
    
    reconciled, notices = audit_and_reconcile_draft(fields, raw_text=raw_text)
    
    # Assertions
    assert reconciled["client_type"]["value"] == "Company"
    assert reconciled["vehicle_type"]["value"] == "Lorry"
    assert "Private Car" not in reconciled["product_name"]["value"]
    assert "Commercial" in reconciled["product_name"]["value"] or "Goods Vehicle" in reconciled["product_name"]["value"]
    assert any("Referee Fact-Check" in n for n in notices)

def test_vehicle_name_simplifier_preserves_alphanumeric_codes():
    # Test that V116-HA or V116HA does not become lowercase V116ha
    brand, model, combined = clean_vehicle_tokens_deterministic("DAIHATSU", "DAIHATSU DELTA V116HA")
    assert "V116-HA" in combined or "V116HA" in combined
    assert "V116ha" not in combined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest.exe tests/unit/test_extraction_referee.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.extraction.referee'`

---

### Task 2: Implement Extraction Referee (`app/extraction/referee.py`)

**Files:**
- Create: `backend/app/extraction/referee.py`

**Interfaces:**
- Produces: `audit_and_reconcile_draft(fields: dict, raw_text: str = "") -> tuple[dict, list[str]]`

- [ ] **Step 3: Write minimal referee implementation**

```python
"""Referee Fact-Checking & Cross-Field Consistency Gate for Motor Quotations."""

from __future__ import annotations
import re
from typing import Any
from app.extraction.entity_classifier import is_corporate_name, is_business_registration

LORRY_INDICATORS = re.compile(
    r"\b("
    r"LORRY|TRUCK|GOODS\s*VEHICLE|PERMIT|RIGID|TRAILER|TIPPER|PRIME\s*MOVER|"
    r"DAIHATSU\s*DELTA|HINO|ISUZU\s*NPR|ISUZU\s*NQR|ISUZU\s*ELF|FUSO|CANTER|"
    r"UD\s*TRUCKS|SCANIA|SINOTRUK|TOYOTA\s*DYNA"
    r")\b",
    re.IGNORECASE,
)

def audit_and_reconcile_draft(
    fields: dict[str, Any],
    raw_text: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Audit draft fields against raw text and cross-field logic to eliminate hallucinations and contradictions."""
    notices: list[str] = []
    reconciled = dict(fields)
    
    def _get(key: str) -> str:
        v = reconciled.get(key)
        if isinstance(v, dict):
            return str(v.get("value") or "").strip()
        return str(v or "").strip()
    
    def _set(key: str, val: str, reason: str) -> None:
        if key in reconciled and isinstance(reconciled[key], dict):
            reconciled[key]["value"] = val
            reconciled[key]["status"] = "ready"
            reconciled[key].setdefault("warnings", []).append(reason)
        else:
            reconciled[key] = {"value": val, "status": "ready", "warnings": [reason]}
        notices.append(reason)

    customer = _get("customer_name")
    id_val = _get("ic_or_brn")
    model = _get("car_model")
    brand = _get("car_brand")
    cc_cap = _get("engine_cc")
    vtype = _get("vehicle_type")
    product = _get("product_name")

    combined_text = f"{customer} {model} {brand} {cc_cap} {raw_text}".upper()

    # 1. Company Detection Gate
    is_company = is_corporate_name(customer) or is_business_registration(id_val)
    if is_company:
        if _get("client_type").lower() != "company":
            _set("client_type", "Company", "Referee Fact-Check: Customer is an enterprise/SDN BHD entity")

    # 2. Commercial / Lorry Detection Gate
    is_lorry = bool(LORRY_INDICATORS.search(combined_text)) or "KG" in cc_cap.upper() or vtype.lower() in ("lorry", "commercialvehicle")
    if is_lorry:
        if vtype != "Lorry":
            _set("vehicle_type", "Lorry", "Referee Fact-Check: Vehicle model/spec indicates commercial goods vehicle / lorry")
        
        # 3. Contradiction Resolution: Commercial Lorry CANNOT be Private Car
        if "PRIVATE CAR" in product.upper() or product.upper() in ("", "COMPREHENSIVE"):
            _set("product_name", "Commercial Vehicle - Comprehensive", "Referee Fact-Check: Lorry reclassified from Private Car to Commercial Vehicle Comprehensive")

    return reconciled, notices
```

- [ ] **Step 4: Update `backend/app/services/vehicle_simplifier_service.py` token regex**

Update token formatting in `clean_vehicle_tokens_deterministic` to:
1. Detect alphanumeric model codes with letter suffixes (e.g. `V116HA` -> `V116-HA` or `V116HA`, `BLM` -> `BLM`).
2. Avoid turning uppercase suffixes into lowercase (do NOT call `tok.capitalize()` blindly if token matches `^[A-Z0-9\-]+$` with digits and letters).

- [ ] **Step 5: Run tests to verify they pass**

Run: `.\.venv\Scripts\pytest.exe tests/unit/test_extraction_referee.py -v`
Expected: PASS

---

### Task 3: Integrate Referee into Worker & Marketing Comparison

**Files:**
- Modify: `backend/app/workers/extraction_worker.py:365-385`
- Modify: `backend/app/services/marketing_comparison_service.py:270-365`
- Modify: `frontend/src/components/comparison/components/CustomerVehicleLedgerPane.tsx:695-705`

- [ ] **Step 6: Integrate referee into `extraction_worker.py`**
Run `audit_and_reconcile_draft` on draft fields right before database commit.

- [ ] **Step 7: Fix `marketing_comparison_service.py`**
1. Line 277: pass `customer_name=cand_cust` (instead of empty string `""`) to `classify_client_entity`.
2. Line 358: pass `is_comprehensive_private=(resolved_vtype in ("Car", "NonSaloonCar", "EVSaloonCar", "EVNonSaloonCar") and entity_type == "Private")`.
3. In `CustomerVehicleLedgerPane.tsx:698`:
```tsx
const brand = (tenure.car_brand || "").trim();
const model = (tenure.vehicle_model || "").trim();
const displayVehicleName = brand && model.toLowerCase().startsWith(brand.toLowerCase()) ? model : `${brand} ${model}`.trim() || model || "Motor Vehicle";
```

- [ ] **Step 8: Run all unit and integration tests**

Run: `.\.venv\Scripts\pytest.exe tests/`
Expected: ALL PASS

- [ ] **Step 9: Commit Milestone 1 changes**

```bash
git add backend/app/extraction/referee.py backend/app/services/vehicle_simplifier_service.py backend/app/services/marketing_comparison_service.py frontend/src/components/comparison/components/CustomerVehicleLedgerPane.tsx tests/unit/test_extraction_referee.py
git commit -m "feat(referee): enforce extraction consistency gate and vehicle naming parity"
```
