# Domain Module Audit: Motor Quotation Comparison Engine & Renewal Lifecycle

> **Module Scope**: Multi-insurer motor quotation comparison matrix, underwriter benefit normalizers (towing, NCD, betterment, excess), vehicle tracking, and annual renewal chaining (`comparison.py`, `tenures.py`, `marketing_comparison_service.py`, `marketing_comparison/*.py`, `insurance_tenure_service.py`, `vehicle_tracking_service.py`, `customer_account_service.py`, `app/comparison/`).

---

## 1. Systemic Workflow & REST Violations

### Issue MC-01 [P0]: Navigating to `/comparison` Auto-Mutates the Database
- **Where**: [`comparison/page.tsx:19-45`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/comparison/page.tsx#L19-L45) -> [`tenures.py:153-233`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/api/routers/tenures.py#L153-L233).
- **Trace**: Opening `/comparison` without `?tenure_id=` automatically fires `POST /tenures` with `{ customer_name: "New Quotation Intake", vehicle_no: "UNPLATED" }`. Meanwhile `TrackedVehicle.vehicle_no` has `unique=True` ([`tables.py:415`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/models/tables.py#L415)). Two advisors opening `/comparison` collide on `"UNPLATED"`, and orphaned intake tenures clutter `/ledger`!
- **Cure**: Render a clean read-only selector on `/comparison` when `tenure_id` is missing, creating a tenure **only** on explicit form submit / file drop, backed by partial unique plate indexing (`NULL` / provisional IDs exempt).

### Issue MC-02 [P0]: HTTP `GET /api/comparison/{tenure_id}` Commits Silent DB Mutations
- **Where**: [`comparison.py:124-132`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/api/routers/comparison.py#L124-L132) -> [`marketing_comparison_service.py:770-909`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/marketing_comparison_service.py#L770-L909).
- **Trace**: On every `GET` page load, `get_marketing_comparison()` silently rewrites `tenure.customer_name`, `tenure.customer.id_number`, `tenure.vehicle_no`, `tracked_vehicle.*`, and `tenure.ncd_percentage`, executing `db.commit()` at `:908-909`. Concurrent browser tabs or React StrictMode double-mounts race on the same row and trigger dirty lost updates!
- **Cure**: Enforce strict HTTP `GET` read-only invariant. Perform comparison hydration atomically inside the upload/extraction completion worker or via explicit idempotent `POST /api/comparison/{tenure_id}/reconcile`.

---

## 2. Domain Logic Bugs in Underwriter Evaluation

### Issue MC-03 [P0]: STMB Motor PA Plus Towing False Promotion (`"4" in text`)
- **Where**: [`towing_evaluator.py:222-242`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/marketing_comparison/towing_evaluator.py#L222-L242).
- **Exact Bug (`:231`)**:
  ```python
  if has_pa_plus:
      if any(p in text for p in ("plan 4", "pelan 4", "plan d", "unlimited", "4")):
          return "Unlimited"
  ```
- **Why this corrupts sales comparisons**: Substring `"4"` matches `"2024"`, `"04-06-2026"`, `"RM 400"`, `"4 doors"`, or `"1,496 cc"` anywhere in the document! An STMB Plan 1 (`100 km`) quote is promoted to **`"Unlimited"`**, winning sort tie-breakers in [`ncd_evaluator.py:329-330`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/marketing_comparison/ncd_evaluator.py#L329-L330) and promising clients unlimited towing they do NOT have!

### Issue MC-04 [P0]: Unknown Towing Silently Defaults to `"Unlimited"`
- **Where**: [`ncd_evaluator.py:287`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/marketing_comparison/ncd_evaluator.py#L287) (and generic fallback at [`towing_evaluator.py:295`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/marketing_comparison/towing_evaluator.py#L295)).
- **Why this violates fiduciary accuracy**: Whenever parsing cannot recognize the towing limit, returning `"Unlimited"` gives the policy the **highest possible towing tier** (`-999999.0` sort key) instead of `"Unspecified (Verify Policy)"`!

### Issue MC-05 [P1]: Floating-Point Monetary Comparisons & Stale Rescan Side Effects
- `TenureComparisonEntry` maps PostgreSQL `Numeric(12, 2)` columns (`sum_insured`, `motor_premium`, `road_tax`, `runner_fee`, `total_payable`) as Python `float` ([`tables.py:377-389`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/models/tables.py#L377-L389)), and `marketing_comparison_service.py:2331-2335` uses `float` arithmetic for totals and rate percentages.
- Additionally, `rescan_comparison_tenure` (`marketing_comparison_service.py:2262-2373`) recalculates `entry.road_tax = float(tenure.road_tax)` and overwrites `total_payable` uniformly across all rows, yet has no discrepancy flag when an insurer quote includes optional add-ons in `motor_premium` that differ from peer quotes in the same matrix (apples-to-oranges Windscreen RM 10k vs RM 0 comparison!).

---

## 3. Vehicle Identity, Customer Deduplication & Renewal Date Drift

### Issue MC-06 [P1]: `+364` Days Renewal Date Drift Across Leap Years
- **Where**: [`insurance_tenure_service.py:126, 128, 131, 694`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/insurance_tenure_service.py#L126).
- **Trace**: `end_date = start_date + timedelta(days=364)` and `:687` (`+ timedelta(days=365)`). In a 366-day leap year (2024, 2028), `2023-03-01 + 364 days = 2024-02-28` (**loses 1 day**, ending a day early before `2024-02-29`), and compounding across 4–8 years shifts the entire renewal reminder month (`expiry_month`) backward!
- **Cure**: Always compute Malaysian annual policy windows using `relativedelta(years=1) - timedelta(days=1)`.

### Issue MC-07 [P1]: Unsafe Same-Name Customer Auto-Merge & Orphan Vehicle FK
- **Same-Name Collisions (`customer_account_service.py:51-54`)**: When a quote lacks NRIC/BRN, secondary lookup merges onto the first `CustomerAccount` matching `canonical_name`. Common names (e.g., two unrelated customers named `"AHMAD BIN ABDULLAH"` or `"TAN WEI MING"`) end up sharing vehicles, phone numbers, and confidential policy history!
- **Orphan UUID (`insurance_tenure_service.py:210`)**: `vehicle_id = veh.id if veh else new_id()` assigns a non-existent random UUID when `veh` wasn't created, failing foreign-key integrity into `tracked_vehicles.id` (`NOT NULL`).
- **Second Unplated Vehicle Crash (`vehicle_tracking_service.py:214`)**: Falls back to hardcoding `vehicle_no="UNPLATED"` on a `UNIQUE` column (`tables.py:415`), crashing on the second showroom/unplated car.

---

## 4. Target Fair-Comparison Architecture ("Apples-to-Apples Normalized Matrix")

1. **Separated Concerns in `marketing_comparison/`**:
   - `identity_resolver.py` -> strictly immutable on `GET`; provisional vs verified NRIC/Plate matching with duplicate alerts instead of blind merges.
   - `towing_and_perils_evaluator.py` -> strict regex boundaries (`r"\b(?:plan|pelan)\s*(?:4|iv|d)\b"`), insurer matrix lookup, `"Unspecified (Check Policy)"` fallback (NEVER `"Unlimited"`!).
   - `ranking_engine.py` -> Decimal 4-tier ranking + explicit **Apples-to-Apples Normalization Warning Badge** whenever one quote includes Windscreen/Special Perils/Flood and a cheaper competitor excluded it!
2. **Comparison State Purity**: Split into `GET /api/comparison/{tenure_id}` (zero DB writes) and `POST /api/comparison/{tenure_id}/reconcile` (atomic server refresh with structured diff log).

