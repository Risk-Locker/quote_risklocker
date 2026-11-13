# Milestone 1: Core Underwriter Domain, Authoritative Towing Engine & Unlocked Road Tax

> **For agentic workers:** REQUIRED SUB-SKILL: Use `company-dispatch` (`06-backend-ledger-lead` + `07-frontend-ux-lead` + `09-qa-and-janitor-gate`) to execute this plan cleanly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cleanly separate Kurnia from AmAssurance, build a table-driven Malaysian motor towing resolution engine with the STMB vs. Amgen RM 40 rule, unlock road tax and runner fee editing (allowing RM 0.00 and enable/disable toggles), and cross-connect all edits seamlessly across the Quotation Workspace, Comparison Matrix, and Renewal Ledger.

**Architecture:** Pure Domain Engine pattern. Business logic (towing matrices, company resolution, delta ranking, and road tax toggles) resides in pure, isolated Python modules accepting typed inputs and `Decimal` currencies with zero HTTP or side-effect coupling. Thin FastAPI routers persist updates to a single source of truth, propagating changes across views. Frontend components expose explicit, instant-edit toggle controls.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL (NUMERIC 12,2 / Decimal), Next.js 15.5, React 19, TypeScript, Tailwind CSS (`--rl-*` tokens), Phosphor Icons, Pytest.

**Spec:** [`docs/SDLC/SYSTEM-ANALYSIS-AND-CORE-USECASES.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/SDLC/SYSTEM-ANALYSIS-AND-CORE-USECASES.md) and User Requirements (2026-11-12).

---

## Global Constraints

- **Zero Float for Currency:** All financial math (premiums, road tax, runner fee, discounts, price deltas) MUST use Python `decimal.Decimal` and SQL `NUMERIC(12, 2)`. Python `float` is strictly prohibited.
- **Pure Core, Imperative Shell:** Towing determination and ranking rules MUST be pure functions with 100% hermetic unit test coverage before database integration.
- **Respect User Edits:** Explicit user inputs (such as Road Tax = RM 0.00) MUST NEVER be overridden or recalculated by automated heuristics.
- **Enterprise Code Quality ("Reads Like Butter"):** Function nesting depth $\le 3$, intent-revealing names (`resolveTowingEntitlement`, `applyAmgenTowingAdvantage`), zero `any` in TypeScript, modular slices $\le 400$ lines.
- **Active Code Freeze:** Plan requires explicit owner approval before lifting `.agents/.freeze.lock`.

---

## 10-Point Edge-Case & Scenario Matrix

| ID | Dimension | Specific Failure Mode Prevented in Milestone 1 |
| :--- | :--- | :--- |
| **E-01** | Null / Empty Inputs | Missing package name or raw towing string defaults cleanly to standard insurer base limit without throwing `AttributeError`. |
| **E-02** | Decimal Rounding | STMB vs Amgen price difference calculation uses `Decimal('40.00')` exact arithmetic; delta of RM 40.0001 does not trigger advantage. |
| **E-03** | Zero Bound (Road Tax) | Road Tax = `0.00` is treated as a valid chosen value, not an uninitialized/missing field, preventing unwanted JPJ auto-recalculation. |
| **E-04** | Toggle State Inversion | Toggling `include_road_tax: false` retains the previous manual amount in draft memory but zeros the active billed total and hides the row. |
| **E-05** | Company Aliasing | PDF extracts mentioning "Kurnia Auto Assist" resolve exclusively to `Kurnia`, never defaulting or aliasing to `AmAssurance` or `Liberty`. |
| **E-06** | Towing Tier Collision | STMB Motor PA Plus Plan 1 (`100km`) vs Plan 4 (`Unlimited`) are parsed with exact plan-digit regex, eliminating false `Unlimited` triggers. |
| **E-07** | Concurrency / Double Submit | Updating fixed costs uses atomic SQL transactions, preventing race conditions between simultaneous drawer and comparison edits. |
| **E-08** | Cross-View Synchronization | Editing road tax in Quotation Workspace triggers synchronous cache/draft sync so Comparison Matrix and Renewal Ledger reflect the same number immediately. |
| **E-09** | Lonpac Math Invariant | Lonpac Plan 1 calculates exactly `RM 1,000` (RM 400 base + RM 600 add-on); Plan 2 returns `Unlimited`. |
| **E-10** | Mobile / Desktop UI Bounds | Road tax enable/disable switch and RM 0 input render cleanly within `--rl-*` container boundaries without layout shifts at 80%–120% zoom. |

---

## File Structure & Decomposition Map

```
backend/app/
├── domain/
│   ├── motor/
│   │   ├── towing_matrix.py          # NEW: Pure table-driven Malaysian towing resolution engine
│   │   └── winner_ranking_rules.py   # NEW: Pure STMB vs Amgen RM 40 towing-advantage evaluator
├── services/
│   ├── company_names.py              # MODIFIED: Clean separation of Kurnia & AmAssurance (Amgen)
│   ├── marketing_comparison_service.py # MODIFIED: Delegate towing & ranking to domain engine; fix RM 0 overwrite
│   └── workspace_patch_service.py    # MODIFIED: Cross-connect fixed cost updates to tenure and sessions
frontend/src/
├── components/
│   ├── comparison/
│   │   └── comparison-matrix.tsx     # MODIFIED: Add Road Tax & Runner Fee toggle switches; wire exact RM 0 editing
│   ├── session-workspace/
│   │   └── review-phase.tsx          # MODIFIED: Remove forced auto-recalculation of RM 0 road tax
tests/
├── domain/
│   ├── test_towing_matrix.py         # NEW: 100% hermetic unit tests for all 8 insurers & plans
│   └── test_winner_ranking_rules.py  # NEW: Hermetic tests for STMB vs Amgen RM 40 boundary
```

---

## Tasks

### Task 1: Clean Separation of "AmAssurance" (Amgen) and "Kurnia" Entities

**Files:**
- Modify: `backend/app/services/company_names.py`
- Modify: `commands/seed-companies.py`
- Test: `tests/test_company_resolution.py`

**Steps:**
- [ ] **Step 1.1: Write failing tests for Kurnia & AmAssurance separation**  
  Add assertions in `tests/test_company_resolution.py` verifying that:
  - Strings `"Kurnia"`, `"Kurnia Insurans"`, `"Kurnia Auto Assist"` resolve strictly to canonical `"Kurnia Insurans"`.
  - Strings `"AmAssurance"`, `"Amgen"`, `"auto365"` resolve strictly to canonical `"AmAssurance"`.
  - Neither resolves to `"Liberty General Insurance Berhad"` as an alias or parent override.
- [ ] **Step 1.2: Run test to confirm failure**  
  Execute: `.\.venv\Scripts\python.exe -m pytest tests/test_company_resolution.py`
- [ ] **Step 1.3: Update canonical company dictionary and aliases**  
  In `backend/app/services/company_names.py`:
  - Register `"KURNIA": "Kurnia Insurans"`.
  - Register `"AMASSURANCE": "AmAssurance"`.
  - Isolate aliases so Kurnia keywords never map to AmAssurance or Liberty.
  - In `commands/seed-companies.py`, add `Kurnia Insurans` as a first-class company seed with detection phrases and slug `kurnia`.
- [ ] **Step 1.4: Run test to verify pass**  
  Verify all company resolution tests pass cleanly.

---

### Task 2: Table-Driven Malaysian Motor Towing Resolver

**Files:**
- Create: `backend/app/domain/motor/towing_matrix.py`
- Modify: `backend/app/services/marketing_comparison/ncd_evaluator.py`
- Test: `tests/domain/test_towing_matrix.py`

**Specification Table Implemented:**
- **QBE:** Base `RM500`. Upgrade with Driver/Passenger Protector (N4) $\to$ `Unlimited`.
- **STMB / Takaful Malaysia:** Base `50km`. Motor PA Plus Plan 1 $\to$ `100km`; Plan 2 $\to$ `200km`; Plan 3 $\to$ `300km`; Plan 4 $\to$ `Unlimited`.
- **Etiqa:** Base `200km`. Upgrade with OTO 360 $\to$ `Unlimited`.
- **Lonpac:** Base `RM400`. E-Assist Smart Driver Plan 1 $\to$ `RM1,000` (RM 400 + RM 600); Plan 2 / EV Plan $\to$ `Unlimited`.
- **Berjaya Sompo:** Standard / Rakan Auto $\to$ `RM300`. SOMPO Motor / MotorSafe $\to$ `Unlimited`.
- **Tune Protect:** Base `200km`. Motor Easy Bundle / AutoBuddy / Motor Shield $\to$ `Unlimited`.
- **AmAssurance (Amgen):** auto365 Lite $\to$ `RM200` (with Breakdown Towing Assistance $\to$ `150km`); auto365 Plus $\to$ `100km`; auto365 Premier $\to$ `365km`.
- **Kurnia:** Base `RM200`; Auto Assist Plus/Premier $\to$ `Unlimited`.
- **Output Constraint:** Return strictly `RM <amount>`, `<num>km`, or `Unlimited`.

**Steps:**
- [ ] **Step 2.1: Write failing comprehensive towing matrix test suite**  
  Create `tests/domain/test_towing_matrix.py` with parameterized test cases covering every single underwriter, plan tier, add-on combination, and boundary (e.g. STMB Plan 1 vs Plan 4).
- [ ] **Step 2.2: Run test to confirm failure**  
  Execute: `.\.venv\Scripts\python.exe -m pytest tests/domain/test_towing_matrix.py`
- [ ] **Step 2.3: Implement `backend/app/domain/motor/towing_matrix.py`**  
  Author the pure resolution function:
  ```python
  def resolve_towing_entitlement(
      company_name: str,
      product_name: str | None = None,
      package_or_rider: str | None = None,
      raw_document_text: str = "",
  ) -> str:
      """Deterministically resolves towing limit into RM <amount>, <num>km, or Unlimited."""
  ```
- [ ] **Step 2.4: Integrate into comparison service**  
  In `ncd_evaluator.py`, remove the dangerous `unlimited_triggers = ["motor pa plus", ...]` and route all towing evaluations through `resolve_towing_entitlement()`.
- [ ] **Step 2.5: Verify test suite passes 100%**  
  Execute: `.\.venv\Scripts\python.exe -m pytest tests/domain/test_towing_matrix.py`

---

### Task 3: STMB vs. Amgen (AmAssurance) RM 40 Towing-Advantage Ranking Rule

**Files:**
- Create: `backend/app/domain/motor/winner_ranking_rules.py`
- Modify: `backend/app/services/marketing_comparison/ncd_evaluator.py`
- Test: `tests/domain/test_winner_ranking_rules.py`

**Rule Specification:**
If STMB is currently ranked #1 on lowest total payable, check if an AmAssurance/Amgen quote with 365 km towing exists in the comparison set. If `(Amgen.total_payable - STMB.total_payable) <= Decimal("40.00")`:
- Promote Amgen to Rank #1 (`is_recommended = True`).
- Demote STMB to Rank #2.
- Set recommendation note: `"Best Value: 365km Towing (within RM 40 difference)"`.

**Steps:**
- [ ] **Step 3.1: Write failing tests for RM 40 boundary ranking**  
  In `tests/domain/test_winner_ranking_rules.py`, write test cases for:
  - Delta = RM 0.00 $\to$ Amgen wins.
  - Delta = RM 39.99 $\to$ Amgen wins.
  - Delta = RM 40.00 $\to$ Amgen wins.
  - Delta = RM 40.01 $\to$ STMB remains #1.
  - Amgen has 100km towing (not 365km) $\to$ Rule does not trigger; STMB wins.
- [ ] **Step 3.2: Run test to confirm failure**  
  Execute: `.\.venv\Scripts\python.exe -m pytest tests/domain/test_winner_ranking_rules.py`
- [ ] **Step 3.3: Implement `apply_towing_advantage_rule()`**  
  Write the pure ranking filter using `Decimal` math.
- [ ] **Step 3.4: Wire into `rank_comparison_entries()` in `ncd_evaluator.py`**  
  Apply the rule during automated ranking pass.
- [ ] **Step 3.5: Verify tests pass 100%**  
  Execute: `.\.venv\Scripts\python.exe -m pytest tests/domain/test_winner_ranking_rules.py`

---

### Task 4: Unlock Road Tax & Runner Fee (`RM 0.00` Permitted & Toggles Added)

**Files:**
- Modify: `backend/app/models/tables.py`
- Modify: `backend/app/services/marketing_comparison_service.py`
- Modify: `backend/app/extraction/draft_mapper.py`
- Modify: `frontend/src/components/session-workspace/review-phase.tsx`
- Modify: `frontend/src/components/comparison/comparison-matrix.tsx`
- Test: `tests/test_comparison_api.py`

**Steps:**
- [ ] **Step 4.1: Write failing backend regression test for RM 0.00 road tax**  
  In `tests/test_comparison_api.py`, add a test that submits `road_tax = 0.00` and verifies that subsequent reads return `0.00` without JPJ auto-overwrite.
- [ ] **Step 4.2: Add `include_road_tax` and `include_runner_fee` schema support**  
  In `backend/app/models/tables.py`, add boolean columns `include_road_tax: Mapped[bool]` (default `True`) and `include_runner_fee: Mapped[bool]` (default `True`) on `InsuranceTenure` and `TenureComparisonEntry`.
- [ ] **Step 4.3: Fix backend overwrite in `marketing_comparison_service.py`**  
  Remove lines 271–276 where `tenure.road_tax == 0.0` was triggering `calculated_jpj_road_tax` overwrites. Respect `include_road_tax: false` to force `road_tax = Decimal("0.00")`.
- [ ] **Step 4.4: Fix frontend forced overwrite in `review-phase.tsx`**  
  Remove lines 869–872 where `currentRT === 0` was forcibly re-injecting computed road tax.
- [ ] **Step 4.5: Add UI toggle switches in `comparison-matrix.tsx`**  
  Add clean, accessible toggle switches for:
  - `[x] Road Tax (RM {val})` $\to$ toggle off zeroes road tax and hides from customer output.
  - `[x] Runner Fee (RM {val})` $\to$ toggle off zeroes runner fee.
  - Allow direct numeric input of `0` in input fields without snapping back.
- [ ] **Step 4.6: Verify tests pass 100%**  
  Execute: `.\.venv\Scripts\python.exe -m pytest tests/test_comparison_api.py`

---

### Task 5: Cross-Connection of Edits Across All 3 Views

**Files:**
- Modify: `backend/app/services/workspace_patch_service.py`
- Modify: `backend/app/services/marketing_comparison_service.py`
- Test: `tests/test_enterprise_comparison_and_ledger.py`

**Steps:**
- [ ] **Step 5.1: Write failing cross-connection integration test**  
  In `tests/test_enterprise_comparison_and_ledger.py`, verify that:
  - When road tax is updated in the Quotation Workspace via `workspace_patch_service`, the linked `InsuranceTenure.road_tax` and all sibling `TenureComparisonEntry.road_tax` values update immediately.
  - When updated in `comparison-matrix`, linked quotation drafts reflect the new value on next render.
- [ ] **Step 5.2: Implement bidirectional state synchronization**  
  In `workspace_patch_service.py`, when `fields.roadtax` or `fields.service_fee` is patched, atomically update the parent tenure and comparison entries in the same database session.
- [ ] **Step 5.3: Verify cross-connection tests pass**  
  Execute: `.\.venv\Scripts\python.exe -m pytest tests/test_enterprise_comparison_and_ledger.py`

---

### Task 6: Release Verification & Quality Gate Sign-Off

**Files:**
- Update: `docs/core/STATE.md`
- Run: `.\commands\verify-deploy-gate.ps1`

**Steps:**
- [ ] **Step 6.1: Run full hermetic pytest suite**  
  Execute: `.\.venv\Scripts\python.exe -m pytest tests/`
- [ ] **Step 6.2: Run TypeScript strict check**  
  Execute: `cd frontend && npx tsc --noEmit && cd ..`
- [ ] **Step 6.3: Run security SAST tripwire check**  
  Execute: `.\.venv\Scripts\python.exe commands/security-audit.py --strict --with-external`
- [ ] **Step 6.4: Run full verification gate**  
  Execute: `.\commands\verify-deploy-gate.ps1`
- [ ] **Step 6.5: Sync Project Knowledge Base and update working memory in `STATE.md`**  
  Run `commands/verify-brain.py` and ensure 100% pass.
