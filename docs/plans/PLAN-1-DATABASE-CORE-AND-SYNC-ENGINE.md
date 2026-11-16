# PLAN 1: Immutable Database Core & Real-Time Synchronization Engine

> **Architecture & Security Blueprint**
> **Scope:** Cleanse, normalize, and permanently lock the database foundation. Unify `TrackedVehicle`, `InsuranceTenure`, `TenureComparisonEntry`, and `QuotationDraft`. Eliminate key-name divergence, enforce ACID transactional boundaries, prevent concurrency clashes, and guarantee zero-drift extensibility for future features.

---

## 1. Security Specialist & Database Forensics Audit

### Vulnerability 1: The "Silent JSON Key Mismatch" Bug (Found in Codebase)
- In `backend/app/services/marketing_comparison_service.py` (lines 2011–2026), `save_comparison_entry` attempts to sync edits to `draft.fields` using:
  - `d_fields["premium_due"]`
  - `d_fields["insurer_name"]`
  - `d_fields["windscreen"]`
- BUT the Quotation Workspace (`policy-fields-card.tsx` and `draft_mapper.py`) reads and writes:
  - `d_fields["premium"]`
  - `d_fields["insurance_company"]`
  - `d_fields["windscreen_coverage"]` / `windscreen_sum_insured`
- **Result:** When an agent edits in the Comparison Matrix, the Quotation Workspace **never sees the updated premium or insurer**. The two tables immediately fall out of sync.

### Vulnerability 2: Concurrency & Double-Click Clashes ("The Game Button Trap")
- In interactive UIs, users click buttons rapidly (e.g. clicking "Pick as Winner", toggling Agreed Value, editing sums).
- Currently, `QuotationDraft` has an optimistic locking counter (`draft.revision`), but `TenureComparisonEntry` has **no optimistic locking or revision check**.
- If two users (or an agent and a background worker) edit at the same time, partial overwrites occur without conflict warnings.

### Vulnerability 3: IDOR & Cross-Tenant Data Isolation
- Endpoints taking `tenure_id` and `entry_id` must verify tenant ownership (`owner_id`, `customer_id`) at the database session query boundary before executing mutations, preventing unauthorized cross-tenant modifications.

### Vulnerability 4: Floating-Point Rounding & Dual-Truth Fees
- Runner Fee currently has hardcoded rules in `benefits_extractor.py` (RM 10 for MyKad, RM 20 for Passport).
- `TenureComparisonEntry` and `InsuranceTenure` both store `road_tax` and `runner_fee` independently, allowing them to drift.
- **Rule:** Universal flat `RUNNER_FEE = Decimal("20.00")` stored in `InsuranceTenure` as the single authority.

---

## 2. Database Model & Relationship Architecture

```
                       ┌───────────────────────────────┐
                       │        CustomerAccount        │
                       │   (Name, IC/BRN, Contact)     │
                       └───────────────┬───────────────┘
                                       │ 1:N
                                       ▼
                       ┌───────────────────────────────┐
                       │        TrackedVehicle         │
                       │   (Plate, Make, Model, Year,  │
                       │    CC, Powertrain, Chassis)   │
                       └───────────────┬───────────────┘
                                       │ 1:N
                                       ▼
                       ┌───────────────────────────────┐
                       │        InsuranceTenure        │
                       │   (Period, Roadtax, Runner,   │
                       │    NCD, Stage, Winning Ref)   │
                       └───────┬───────────────┬───────┘
                               │ 1:N           │ 1:N
                ┌──────────────┘               └──────────────┐
                ▼                                             ▼
 ┌─────────────────────────────┐               ┌─────────────────────────────┐
 │    TenureComparisonEntry    │               │           Session           │
 │ (Underwriter Comparison Col)│               │  (Document Intake Session)  │
 │                             │               └──────────────┬──────────────┘
 │ • company_id (FK)           │                              │ 1:1
 │ • sum_insured               │                              ▼
 │ • motor_premium             │               ┌─────────────────────────────┐
 │ • road_tax, runner_fee      │               │       QuotationDraft        │
 │ • total_payable             │ ◄───────────► │ (Quotation Workspace State) │
 │ • towing_limit              │   REAL-TIME   │                             │
 │ • excess, rate_pct          │   TWO-WAY     │ • fields: Canonical JSON    │
 │ • rank, is_recommended     │     SYNC      │ • revision: Concurrency lock│
 └─────────────────────────────┘               └──────────────┬──────────────┘
                                                              │ 1:N
                                                              ▼
                                               ┌─────────────────────────────┐
                                               │    DraftBenefitSelection    │
                                               │ • Box 1 (Free / Included)   │
                                               │ • Box 2 (Paid Add-ons)      │
                                               │ • concept_id, cost, limits  │
                                               └─────────────────────────────┘
```

---

## 3. Database Invariants & Real-Time Sync Engine

### Invariant 1: Canonical Vehicle & Customer Identity Sync
- `TrackedVehicle` is the master for: `vehicle_no`, `car_brand`, `car_model`, `engine_cc`, `manufacture_year`, `chassis_no`, `engine_no`, `powertrain` (ICE vs EV).
- `InsuranceTenure` is the master for: `customer_name`, `ic_or_brn`, `coverage_start_date`, `coverage_end_date`, `road_tax`, `runner_fee` (= RM 20.00), `ncd_percentage`.
- **Sync Service (`sync_tenure_identity_transaction`):**
  When any field above is updated in the UI:
  1. Transaction begins (`with db.begin():`).
  2. Updates `TrackedVehicle` and `InsuranceTenure`.
  3. Propagates the canonical values to all attached `QuotationDraft.fields` and `TenureComparisonEntry` records.
  4. Commits atomically. If any step fails, entire transaction rolls back.

### Invariant 2: Two-Way Bidirectional Quotation Sync
- When an underwriter quote is edited in **Comparison Matrix** (`save_comparison_entry`):
  - Updates `TenureComparisonEntry`.
  - Immediately updates the linked `QuotationDraft.fields` using the **exact canonical keys**:
    - `premium` $\leftarrow$ `entry.motor_premium`
    - `sum_insured` $\leftarrow$ `entry.sum_insured`
    - `valuation_type` $\leftarrow$ `entry.valuation_type`
    - `insurance_company` $\leftarrow$ `entry.company_name`
    - `excess_amount` $\leftarrow$ `entry.excess`
    - `towing_limit` $\leftarrow$ `entry.towing_limit`
- When edited in **Quotation Workspace** (`apply_workspace_patch`):
  - Updates `QuotationDraft.fields`.
  - Immediately updates the linked `TenureComparisonEntry`:
    - `entry.motor_premium` $\leftarrow$ `draft.fields['premium']`
    - `entry.sum_insured` $\leftarrow$ `draft.fields['sum_insured']`
    - `entry.valuation_type` $\leftarrow$ `draft.fields['valuation_type']`
    - `entry.total_payable` $\leftarrow$ `entry.motor_premium + tenure.road_tax + tenure.runner_fee`
- **Result:** Zero drift. Editing in either workspace updates both simultaneously.

### Invariant 3: Single Source for Fees
- `InsuranceTenure.road_tax` and `InsuranceTenure.runner_fee` are authoritative.
- Hardcoded RM 10.00 / RM 20.00 passport heuristic in `benefits_extractor.py` is permanently replaced with:
  `tenure.runner_fee = Decimal("20.00")` for all records.
- `TenureComparisonEntry.runner_fee` and `QuotationDraft.fields['service_fee']` read directly from `tenure.runner_fee`.

### Invariant 4: Zero-Clash Extensibility for Future Features
- **Pydantic Schema Contracts:** All API payloads (`ComparisonEntryUpsertRequest`, `WorkspacePatchOperation`) are strictly typed with Pydantic v2 schemas.
- **Partial Unique Indexes:**
  - `uq_draft_benefit_selection_concept`: Prevents duplicate benefits (e.g. double windscreen) at the PostgreSQL engine level.
  - `uq_tenure_company_entry`: Prevents duplicate entries for the same underwriter under one tenure.
- **Audit Logging:** Every financial mutation logs to `AuditEvent` with `before_state` and `after_state` JSON diffs.

---

## 4. Execution Tasks for Plan 1

- [ ] **Task 1.1: Fix Key Name Mismatch in `marketing_comparison_service.py`**
  - Change `d_fields["premium_due"]` $\rightarrow$ `d_fields["premium"]`
  - Change `d_fields["insurer_name"]` $\rightarrow$ `d_fields["insurance_company"]`
  - Change `d_fields["windscreen"]` $\rightarrow$ `d_fields["windscreen_sum_insured"]`
- [ ] **Task 1.2: Implement `sync_tenure_identity_transaction` Service**
  - Wrap updates to Vehicle No, Model, Customer Name in an atomic transaction across `TrackedVehicle`, `InsuranceTenure`, and all linked `QuotationDraft` rows.
- [ ] **Task 1.3: Enforce Universal Runner Fee = RM 20.00**
  - Delete `detect_runner_fee_from_id` in `benefits_extractor.py`.
  - Set default `runner_fee = 20.00` in `insurance_tenures`.
- [ ] **Task 1.4: Add Database Integrity Constraints & Concurrency Protection**
  - Add optimistic concurrency check on `TenureComparisonEntry`.
  - Add unique constraint preventing duplicate benefit concepts on `DraftBenefitSelection`.
