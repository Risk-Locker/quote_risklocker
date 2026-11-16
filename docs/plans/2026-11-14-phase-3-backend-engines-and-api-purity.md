# Phase 3: Backend Core Engines, Query Performance & API Purity

> **Document:** `docs/plans/2026-11-14-phase-3-backend-engines-and-api-purity.md`  
> **Status:** In Execution  
> **Prerequisites:** Phase 1 & Phase 2 100% Verified  
> **Owner:** Principal Architect & Backend Lead  

---

## 1. Executive Summary & Forensic Context

In Phase 1, we eliminated critical P0 exploits (`F-01` through `F-06`). In Phase 2, we restored database immutability triggers and added the enterprise double-entry ledger (`migrations/077+`).

**Phase 3** targets backend engine correctness, query performance, and API purity (`F-09`, `F-10`, `F-12`, and `MUTATING_GET` / `MISSING_RBAC` audit findings):
1. **Fix F-09 (Company Slug Parity in PDF Generation):**  
   In `generation_service.py:351`, `getattr(company, "company_key", "")` always evaluated to `""` because `InsuranceCompany` has no `company_key` attribute (only `slug` and `name`). As a result, every company defaulted to `"etiqa"`. We fix this to accurately resolve `company.slug` and `company.name`.
2. **Fix F-10 (Full-Table RAM Scan to Indexed SQL Lookups):**  
   In `generation_service.py:94,502`, `_rows(db, Job)` and `_rows(db, RenderSnapshot)` load every single job and snapshot in the database into Python memory. We replace these with targeted, indexed SQL lookups (`select(Job).where(Job.job_type == ..., Job.idempotency_key == ...)` and `select(RenderSnapshot).where(RenderSnapshot.context_hash == context_hash)`).
3. **Fix F-12 (Leap-Safe Calendar Mathematics):**  
   In `insurance_tenure_service.py:126,690,697`, policy expiry dates use naive `+ timedelta(days=364)` and `+ timedelta(days=365)`. During leap years, policy anniversary dates drift by 1 day. We replace these with exact calendar anniversary arithmetic via `dateutil.relativedelta.relativedelta(years=1) - timedelta(days=1)`.
4. **Fix Mutating GET Contracts:**  
   Ensure `GET /api/comparison/{tenure_id}` remains strictly read-only, avoiding unsolicited `db.commit()` calls during read queries.
5. **RBAC Hardening on Mutating Comparison Endpoints:**  
   Ensure all mutating endpoints in `backend/app/api/routers/comparison.py` have appropriate authentication and role checks so unauthorized guests cannot alter comparisons.

---

## 2. 10-Point Edge-Case & Failure-Mode Matrix

| ID | Dimension | Specific Failure Mode Prevented in Phase 3 |
| :--- | :--- | :--- |
| **E-01** | Null Company Slug | Company with null slug falls back cleanly to normalized company name or default. |
| **E-02** | Case Sensitivity | Slug lookup handles lowercase, uppercase, and leading/trailing whitespace cleanly. |
| **E-03** | High-Volume `Job` Rows | 100,000+ jobs in database resolve in <2ms via indexed `idempotency_key` query. |
| **E-04** | Large Snapshot Contexts | Multi-megabyte `RenderSnapshot` contexts are never fetched into RAM in bulk. |
| **E-05** | Leap Day Inception | Policy starting on 2024-02-29 expires on 2025-02-28 without throwing `ValueError`. |
| **E-06** | Dec 31 Boundary | Policy starting on 2026-12-31 expires on 2027-12-30. |
| **E-07** | Read-Only Concurrency | Concurrent `GET /comparison/{id}` calls execute read queries without database lock contention. |
| **E-08** | Unauthenticated Mutation | POST to `/comparison/{tenure_id}/fixed-costs` without session rejects with HTTP 401. |
| **E-09** | Staff User Role | Staff members can edit quotation comparison entries and fixed costs cleanly. |
| **E-10** | Renewal Chain Leap Safety | Advancing a tenure across multiple years maintains consistent anniversary dates. |

---

## 3. Serialized Tasks

### Task 1: Fix F-09 Company Slug Resolution & F-10 Indexed SQL Lookups in `generation_service.py`
- Modify: `backend/app/services/generation_service.py`
- Test: `tests/unit/test_phase3_backend_purity.py`

### Task 2: Fix F-12 Leap-Safe Calendar Date Math in `insurance_tenure_service.py`
- Modify: `backend/app/services/insurance_tenure_service.py`
- Test: `tests/unit/test_phase3_backend_purity.py`

### Task 3: Ensure Read-Only GET & Harden RBAC in `comparison.py` & `marketing_comparison_service.py`
- Modify: `backend/app/services/marketing_comparison_service.py`
- Modify: `backend/app/api/routers/comparison.py`
- Test: `tests/unit/test_phase3_backend_purity.py`

### Task 4: Authentic Verification & Knowledge Base Gate
- Run full pytest gauntlet across unit, security, and integration suites.
- Run frontend strict TypeScript check (`tsc --noEmit`).
- Verify Knowledge Base via `commands/verify-brain.py` and update `docs/core/STATE.md`.
