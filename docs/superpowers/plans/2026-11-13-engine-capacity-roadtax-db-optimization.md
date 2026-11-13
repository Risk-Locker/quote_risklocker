# Engine Capacity (CC/kW/KG), Road Tax Controls & Database Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform "Engine CC" into a unified "Engine Capacity" specification supporting CC (ICE), kW/W (EV), and KG (Commercial Lorry) with two-way vehicle class reactivity and live road tax recalculation; add direct 1-click Road Tax & Runner Fee toggle and adjustment controls to the comparison matrix; and resolve database slowness by indexing 140 unindexed foreign keys and eliminating redundant sequential N+1 network queries.

**Architecture:** 
- **Database & Performance:** Migration `076` adds high-priority B-Tree indexes on frequently joined foreign keys (`tenure_id`, `session_id`, `draft_id`, `uploaded_file_id`, `tracked_vehicle_id`). In `marketing_comparison_service.py`, batch-load benefit lines and drafts to cut query count from 24+ to <6. Remove frontend duplicate `fetchComparison()` after POST.
- **Engine Capacity Domain & Interconnectivity:** Extend `road_tax_engine.py` to handle KG commercial tariffs and kW EV tariffs alongside CC. Add `POST /comparison/calculate-road-tax` for zero-latency preview calculations. In `CustomerVehicleLedgerPane.tsx`, implement a 3-unit selector (`CC`, `kW`, `KG`) with cross-field prompt/auto-switch logic to `Lorry` or `EV` and live road tax recalculation.
- **Road Tax & Runner Fee Quick Controls:** Introduce prominent 1-click fee toggle pills (`[✓ Road Tax: RM 90.00]`, `[✓ Runner Fee: RM 10.00]`) and a quick-adjust popover directly in the comparison controls toolbar.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL (Supabase remote), Next.js 15, React 19, TypeScript, Phosphor Icons, pytest.

---

## Global Constraints

- **Single Source of Truth:** All statutory road tax calculations are authoritative ONLY in backend `road_tax_engine.py`.
- **Zero Hardcoding Invariant:** Rates, brackets, and tariffs live in DB rules and canonical rate constants.
- **Forward-Only Migrations:** Never alter historical migrations `001`–`075`. Use `migrations/076_...sql`.
- **User Edits Are Sacred:** Manual custom road tax or runner fee values must never be wiped or snapped back without explicit user confirmation.
- **Clean Architecture Modularity:** React components <= 500 lines, Python services <= 350 lines, depth <= 3.

---

## Serialized Milestones

### Milestone 1: Database Schema Indexing & Performance Optimization (Resolves Issue #3)

**Files:**
- Create: `migrations/076_add_critical_foreign_key_and_performance_indexes.sql`
- Modify: `backend/app/models/tables.py`
- Modify: `backend/app/services/marketing_comparison_service.py`
- Modify: `frontend/src/components/comparison/comparison-matrix.tsx`
- Test: `tests/test_marketing_comparison.py`

- [ ] **Step 1: Write Migration 076 for High-Traffic Foreign Keys**
  - Add indexes for:
    - `tenure_comparison_entries (tenure_id, session_id, company_id)`
    - `sessions (tenure_id, customer_id, tracked_vehicle_id, draft_id, uploaded_file_id)`
    - `insurance_tenures (tracked_vehicle_id, customer_id, covernote_session_id, winning_company_id)`
    - `draft_benefit_selections (draft_id, concept_id)`
    - `extraction_records (uploaded_file_id)`
    - `extraction_benefit_lines (extraction_record_id)`
    - `generated_pdf_versions (draft_id)`
    - `jobs (session_id)`
  - Apply migration to remote Supabase DB using `backend/app/db/migrations.py`.

- [ ] **Step 2: Optimize `marketing_comparison_service.py` Batch Querying**
  - In `get_marketing_comparison`:
    - Batch-load `DraftBenefitSelection` for all draft IDs in one query: `select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id.in_(draft_ids))`.
    - Batch-load `ExtractionRecord` and `ExtractionBenefitLine` in one query for all uploaded file IDs.
    - Batch-load `GeneratedPdfVersion` for all draft IDs in one query.
  - Pass preloaded dictionaries into `_resolve_comparison_benefits` instead of running 4 individual queries per quote card.

- [ ] **Step 3: Remove Redundant Double-Fetch in Frontend**
  - In `frontend/src/components/comparison/comparison-matrix.tsx`:
    - In `handleSaveFixedCosts`, `POST /comparison/${tenureId}/fixed-costs` returns the full fresh comparison payload. Update `setData(updated)` directly and remove `await fetchComparison(true)`.

- [ ] **Step 4: Verify Performance Benchmark**
  - Measure execution time of `get_marketing_comparison` and `update_tenure_fixed_costs`. Ensure query count drops from 24+ to <= 6 and execution latency drops below 400ms.

---

### Milestone 2: Engine Capacity (CC / kW / KG) & Two-Way Interconnectivity (Resolves Issue #1)

**Files:**
- Modify: `backend/app/services/road_tax_engine.py`
- Modify: `backend/app/api/routers/comparison.py`
- Modify: `backend/app/services/marketing_comparison_service.py`
- Modify: `frontend/src/components/comparison/components/CustomerVehicleLedgerPane.tsx`
- Modify: `frontend/src/components/comparison/comparison-matrix.tsx`
- Test: `tests/domain/test_road_tax_engine_units.py`

- [ ] **Step 1: Backend Domain Engine Unit Normalization & Calculation**
  - Extend `road_tax_engine.py`:
    - Support input string parsing for `"1496 cc"`, `"150 kw"`, `"7500 w"`, `"5000 kg"`.
    - Handle `Lorry` / Commercial vehicle road tax when unit is `KG` (BDM weight tiers: <=1000kg RM 120, <=2500kg RM 240, <=5000kg RM 480, <=7500kg RM 720).
    - Handle `EV` road tax when unit is `kW` or `W`.
  - Add API route `POST /comparison/calculate-road-tax`:
    - Payload: `{ capacity: str | float, unit: "cc" | "kw" | "kg", vehicle_type: str, owner_type: str, jurisdiction: str }`.
    - Returns: `{ road_tax: float, formatted: str, explanation: str }`.

- [ ] **Step 2: Frontend Capacity Input & 3-Way Unit Selector**
  - In `CustomerVehicleLedgerPane.tsx`:
    - Rename display label from `"Engine CC"` to **`"Engine Capacity"`**.
    - In edit mode, add a clean unit toggle/selector:
      - `[ Number Input ] [ Unit: CC | kW | KG ]`.
  - Implement two-way interconnectivity:
    - If user switches unit to **`KG`**:
      - Prompt user with confirmation modal: *"Switch vehicle class to Lorry / Commercial Goods Vehicle?"*.
      - On confirm: set `vehicleType` to `"Lorry"` and trigger road tax recalculation.
    - If user switches unit to **`kW`** (or `W`):
      - Prompt user: *"Switch vehicle class to Electric Vehicle (EV)?"*.
      - On confirm: set `vehicleType` to `"EVSaloonCar"` and trigger EV road tax recalculation.
    - If user switches unit to **`CC`**:
      - Prompt user: *"Switch vehicle class to Private Car (ICE)?"*.
      - On confirm: set `vehicleType` to `"Car"` and trigger ICE road tax recalculation.
    - If user changes `vehicleType` dropdown:
      - `"Lorry"` $\to$ auto-selects `KG`.
      - `"EVSaloonCar"` / `"EVNonSaloonCar"` $\to$ auto-selects `kW`.
      - `"Car"` / `"NonSaloonCar"` / `"Motorcycle"` $\to$ auto-selects `CC`.
  - On capacity or unit change: automatically query `POST /comparison/calculate-road-tax` and update `roadTaxInput`.

- [ ] **Step 3: Update Summary Badges and Displays**
  - Update vehicle summary lines in `comparison-matrix.tsx`, `CustomerVehicleLedgerPane.tsx`, and `SnapshotPreviewModal.tsx` to display formatted capacity with unit: e.g. `1,496 cc`, `150 kW`, `5,000 kg`.

- [ ] **Step 4: Unit Tests for 3-Unit Road Tax Engine**
  - Verify calculations across all 3 units (CC, kW, KG) across all jurisdictions (Peninsular, Sabah, Sarawak, Labuan).

---

### Milestone 3: Prominent Road Tax & Runner Fee Quick Controls Bar (Resolves Issue #2)

**Files:**
- Modify: `frontend/src/components/comparison/comparison-matrix.tsx`
- Create / Modify: `frontend/src/components/comparison/components/AdjustFeesModal.tsx`
- Modify: `frontend/src/components/comparison/components/CustomerVehicleLedgerPane.tsx`
- Test: `tests/integration/test_road_tax_and_runner_fee_controls.py`

- [ ] **Step 1: Dedicated Quick-Toggle Pills on Matrix Pricing Bar**
  - In `comparison-matrix.tsx` Pricing & Display Controls Bar:
    - Add a distinct "Fixed Costs & Fees" section:
      - **Road Tax Button:**
        - When included: `[✓ Road Tax: RM 90.00]` (Dark/Emerald accent).
        - When excluded: `[✕ Road Tax (Excluded)]` (Subtle dashed outline).
        - Single click toggles `include_road_tax` and immediately updates all comparison quote totals.
      - **Runner Fee Button:**
        - When included: `[✓ Runner Fee: RM 10.00]` (Dark/Emerald accent).
        - When excluded: `[✕ Runner Fee (Excluded)]` (Subtle dashed outline).
        - Single click toggles `include_runner_fee` and immediately updates all comparison quote totals.
      - **Quick Fee Adjustment Modal (`[⚙ Adjust Fees]`):**
        - Quick modal allowing staff to:
          1. Edit Road Tax amount.
          2. Edit Runner Fee amount.
          3. Click "Recalculate from JPJ" (uses vehicle capacity & type).
          4. Save and apply instantly.

- [ ] **Step 2: Customer Vehicle Ledger Pane Action Button**
  - In `CustomerVehicleLedgerPane.tsx`:
    - Add explicit "Recalculate Road Tax" button in edit mode.
    - Show clear visual badges for `(Included)` vs `(Excluded)` for both Road Tax and Runner Fee in the view mode.

- [ ] **Step 3: Verification**
  - Verify 1-click toggling updates all cards, recalculates Net Total Payable, and persists to backend.

---

## Verification & Pre-Commit Gate

1. `.\.venv\Scripts\pytest.exe tests/` (All unit & integration tests pass 100%).
2. `cd frontend && npx tsc --noEmit` (0 TypeScript diagnostics).
3. `cd frontend && npm run build` (Next.js production build passes).
4. `.\.venv\Scripts\python.exe commands/verify-brain.py` (Documentation links verified).

