# Systematic & Broken Logic: Backend, Worker & Calculation Root-Cause Forensics

> **Textbook Purpose**: When software breaks mysteriously in production, it is almost never random — it is because of specific broken assumptions in the code. Below is the complete forensic dissection of every major backend & logic defect verified in `v30.1`. For every bug, you will learn: **(1) Exact location**, **(2) Why it is amateur patchwork**, **(3) How it explodes in production**, and **(4) The exact cure**.

---

## 1. Critical Storage & Worker Pipeline Failures

### Bug B-01 [P0]: Render Worker Bypasses Supabase Storage in Production
- **Exact Issue**: Look at [`backend/app/main.py:82`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/main.py#L82): the embedded worker calls `run_one_job(db, settings, worker_id=slot_worker_id)` without passing `storage=...`, so `storage` defaults to `None`. Inside [`extraction_worker.py:791`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/workers/extraction_worker.py#L791), it forwards `storage=storage` (`None`) to `process_render_job`. Now look at [`render_worker.py:141, 195-217, 252-255`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/workers/render_worker.py#L141):
  - Line 141 instantiates `storage_client = storage or SupabaseStorage(settings)` cleanly.
  - **Line 195 checks `if storage is not None:` (the parameter, NOT `storage_client`!)**.
- **Why this is amateur patchwork**: Because the author checked the input argument `storage` instead of the initialized `storage_client`, the `if` branch is **dead code** whenever the embedded worker runs! Every production quotation falls straight into the `else:` branch (`:205-217`) and writes PDFs to `.qc-tmp/stateless_generated/` with `storage_provider = "local_ephemeral"`.
- **How it breaks in production**: On container redeploy, ephemeral disk wipe, or multi-instance scaling, **every customer's historical quotation PDF disappears (404/file missing)** even though PostgreSQL claims it exists!
- **Exact Cure**: Always initialize `storage_client = storage or SupabaseStorage(settings)`. Check `if settings.app_env != "test":` (or `storage_client.is_configured()`), upload directly to Supabase Storage (`storage_client.upload_generated_pdf`), and remove the production `.qc-tmp/stateless_generated/` fallback completely.

### Bug B-02 [P1]: Full-Table Scans of Multi-Megabyte JSON Blobs via `_rows()`
- **Exact Issue**: In [`generation_service.py:67-68`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/generation_service.py#L67-L68), `_rows(db, model)` executes `list(db.scalars(select(model)).all())` with **no `WHERE` clause**. Then:
  - [`generation_service.py:94-103`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/generation_service.py#L94-L103) loads **every `Job` row ever created** into Python RAM to check `job.idempotency_key == key`.
  - [`generation_service.py:502-505, 590`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/generation_service.py#L502-L505) loads **every `RenderSnapshot` row** (including multi-MB embedded base64 asset JSON payloads!) into Python RAM to check `item.context_hash == context_hash` — even though [`tables.py:1255`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/models/tables.py#L1255) already defines `context_hash` with `unique=True`!
- **Why this is AI slop**: Reading an entire database table into a Python list comprehension (`next(item for item in _rows(...) if ...)`) instead of using SQL `WHERE` clauses works on 5 test rows in development and turns into an O(N) memory/network bomb in production.
- **How it breaks in production**: At 5,000 quotations × ~2 MB snapshot context, a single click on **Preview** or **Generate** attempts to deserialize **10 GB of JSON** over Postgres wire into FastAPI RAM, crashing the server with `MemoryError` / OOM kill.
- **Exact Cure**: Delete `_rows()` completely. Query `select(Job).where(Job.job_type == "render_pdf", Job.idempotency_key == key)` and `select(RenderSnapshot).where(RenderSnapshot.context_hash == context_hash)` backed by a unique partial index.

### Bug B-03 [P1]: Cold Chromium Launch Per PDF Render
- **Exact Issue**: [`pdf_generator.py:36-60`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/pdf_generator.py#L36-L60) starts Playwright and spawns a brand-new `playwright.chromium.launch(headless=True)` process inside every single `html_to_pdf()` call.
- **How it breaks in production**: Combined with `WORKER_CONCURRENCY=10` ([`main.py:73`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/main.py#L73)), 10 simultaneous quotations spawn 10 full Chrome browsers at once (~350 MB × 10 = 3.5 GB RAM) + 2–3s wasted startup per PDF.
- **Exact Cure**: Run a bounded persistent Chromium pool (with isolated incognito `BrowserContext` per render and automatic recycle every 200 jobs).

---

## 2. Broken Calculation, Catalog & Extraction Pipeline Logic

### Bug B-04 [P0]: All Insurers Silently Evaluate `"etiqa"` Benefit Rules!
- **Exact Issue**: Look at [`generation_service.py:349-353`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/generation_service.py#L349-L353) and [`workspace_snapshot_service.py:262-267`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/workspace_snapshot_service.py#L262-L267):
  ```python
  insurer_key = str(getattr(company, "company_key", "") or "etiqa") if company else "etiqa"
  ```
  Now look at the `InsuranceCompany` SQLAlchemy model at [`tables.py:99-113`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/models/tables.py#L99-L113): the column is named **`slug`** (`:104`), NEVER `company_key`!
- **Why this is dangerous**: Using defensive `getattr(obj, "wrong_name", "")` silently hides a typo/bug forever — Python never raises `AttributeError`, returns `""`, and triggers `or "etiqa"`.
- **How it breaks in production**: Whether the quote is QBE (0.25% special perils, RM 200 towing), Lonpac, AmAssurance, or STMB, formula evaluation resolves **Etiqa's** matrix rules (e.g., 0.20% special perils at [`benefit_catalog_matrix.py:95`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/benefit_catalog_matrix.py#L95))!
- **Exact Cure**: Delete `getattr(..., "company_key", ...)` magic fallbacks, read `company.slug`, unify `benefit_catalog_matrix.py` into normalized DB tables, and write unit tests verifying QBE/Lonpac/STMB resolve distinct rules.

### Bug B-05 [P0]: Road Tax Drops Downward at 2501cc + Client/Server Contradiction
- **Exact Issue**: Look at Peninsular West Malaysia Private Car rates in [`road_tax_engine.py:41-42`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/road_tax_engine.py#L41-L42) and [`road_tax_service.py:187-188`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/road_tax_service.py#L187-L188):
  - Bracket `2001..2500cc`: `380 + (cc - 2000) * 1.00`. At `2500cc` -> `380 + 500 = RM 880.00`.
  - Bracket `2501..3000cc`: `840 + (cc - 2500) * 2.50`. At `2501cc` -> **`RM 842.50`** (**RM 37.50 LOWER** than a smaller 2500cc engine!). Same 50% anomaly in FT Labuan ([`road_tax_engine.py:152-153`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/road_tax_engine.py#L152-L153), `road_tax_service.py:364-365`: `440.00` drops to `421.25`).
  - Meanwhile, [`provider.tsx:116`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/provider.tsx#L116) calculates **`880`**, whereas [`policy-fields-card.tsx:251`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/review-components/policy-fields-card.tsx#L251) (in the exact same workspace!) and the backend use **`840`**.
- **Exact Cure**: One authoritative backend DB-seeded progressive bracket table (`880.00` base at `>2500cc`, Labuan `440.00`) validated by a continuous monotonicity invariant test (`rate(cc + 1) >= rate(cc)` across `1..6000cc`), removing duplicate frontend road-tax calculators completely.

### Bug B-06 [P0]: `_eval_formula` Runs `eval()` With Permissive Regex
- **Exact Issue**: [`road_tax_engine.py:18-29`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/road_tax_engine.py#L18-L29) validates formulas only with regex `^[\d\s+\-*/().,cc]*$` and executes `eval(formula, {"__builtins__": {}}, {"cc": cc})`, catching `(ValueError, TypeError, SyntaxError, NameError)` — **NOT** `ZeroDivisionError`, `OverflowError`, or CPU exhaustion (`9**9**9**9` using `*`, `*`, `9`). Notice East Malaysia/EV `ceil` formulas seeded in [`road_tax_service.py:423`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/road_tax_service.py#L423) use `ceil(...)` which doesn't even match `^[\d\s+\-*/().,cc]*$`!
- **Exact Cure**: Replace `eval()` with a whitelist AST evaluator permitting ONLY `+`, `-`, `*`, `/`, `cc`, constants, and `ceil`/`floor`/`min`/`max`.

### Bug B-07 [P1]: Three Severe Pipeline Bugs Inside `draft_mapper.py`
1. **Silent Valuation Guess (`:312-319`)**: When neither Agreed Value nor Market Value can be verified cleanly (`is_agreed = False`), [`draft_mapper.py:312-319`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/extraction/draft_mapper.py#L312-L319) blindly sets `final_val_type = "Market Value"` with **`status = "ready"`** — violating the non-negotiable business rule *never silently guess uncertain values*.
2. **Stale Pre-EV `resolved_vtype` Passed to Road Tax (`:385-425`)**: At lines `:385-390`, `draft_mapper.py` detects an EV in `kW`/`Watts` and updates `fields["vehicle_type"]["value"] = "EVSaloonCar"`, **but NEVER updates the local variable `resolved_vtype`**. At line `:422`, it calls `calculate_road_tax(cc=effective_cc, vehicle_type=resolved_vtype, ...)` with the old ICE `"Car"` type! (e.g., passing `kw=150` as `150cc` ICE car = RM 20 instead of EV kW bracket!).
3. **Insurer Total Blindly Overwrites Risklocker Total (`:555-558`)**: After computing premiums/extras, line `:556-558` sets `fields["total_amount"]["value"] = f"{tot_num:.2f}"` (the insurer's raw PDF total, which excludes Risklocker road tax, runner fee, or Risklocker add-on edits!).

### Bug B-08 [P1]: Swallowed Pricing Exceptions & Split Blocker Enforcement
- **Swallowed Exceptions**: [`workspace_patch_service.py:266-269`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/workspace_patch_service.py#L266-L269) catches `except Exception: pass` when computing add-on extra totals for `total_amount` — a bad addon string silently turns an RM 500 windscreen price into `0.00` without failing or alerting!
- **Contradictory Blockers**: [`workspace_common.py:241-250`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/workspace_common.py#L241-L250) emits `scalar_check_needed` blockers for every field lacking an explicit user decision, keeping the workspace visually stuck on `"check_needed"`, yet [`generation_service.py:494`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/generation_service.py#L494) strips `scalar_check_needed` and allows PDF generation anyway! Thus **the badge cries wolf when nothing is blocked, or masks real unresolved pricing discrepancies**.

---

## 3. Marketing Comparison, Towing, Dates & Identity Bugs

### Bug B-09 [P0]: Mutating HTTP `GET /comparison/{tenure_id}`
- **Exact Issue**: [`comparison.py:124-132`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/api/routers/comparison.py#L124-L132) delegates `GET /{tenure_id}` directly to `get_marketing_comparison(db, tenure_id)`, which writes edits to `customer.canonical_name`, `customer.id_number`, `tenure.vehicle_no`, `tracked_vehicle.*`, `tenure.ncd_percentage`, and `db.commit()` ([`marketing_comparison_service.py:770-909`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/marketing_comparison_service.py#L770-L909)).
- **Why this breaks in production**: Concurrent React StrictMode double-renders, browser tab restores, or HTTP crawlers trigger silent database writes and race-condition lost updates during simple page views!

### Bug B-10 [P0]: `"4" in text` Towing False-Positives & `"Unlimited"` Fallback
- **Exact Issue 1 (`towing_evaluator.py:231`)**:
  ```python
  if has_pa_plus:
      if any(p in text for p in ("plan 4", "pelan 4", "plan d", "unlimited", "4")):
          return "Unlimited"
  ```
  Sub-string `"4"` matches **any digit 4 anywhere** in the combined PDF/benefit text (`2024`, `2026-04-01`, `RM 400`, `4-door`, phone `012-3456789`, plate `WXY 441`) — promoting Plan 1/2/3 STMB PA Plus policies to `"Unlimited"`!
- **Exact Issue 2 (`ncd_evaluator.py:287`)**: When `normalize_towing_limit` sees an unknown/empty string, it returns **`"Unlimited"`** (the *best possible* tier, inflating sort rank at [`:293`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/marketing_comparison/ncd_evaluator.py#L293) and misleading clients into thinking non-unlimited policies have free unlimited towing!).
- **Exact Cure**: Require regex word boundaries (`r"\b(?:plan|pelan)\s*(?:4|iv|d)\b"`) and return `"Unspecified (Check Policy)"` instead of `"Unlimited"` on unknowns.

### Bug B-11 [P1]: `+364` Days Leap-Year Drift, Same-Name Identity Merges & Orphan UUIDs
- **Leap-Year Renewal Drift (`insurance_tenure_service.py:126, 131, 694`)**: Adding `timedelta(days=364)` ([`insurance_tenure_service.py:126,694`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/insurance_tenure_service.py#L126)) shifts a `2023-03-01` -> `2024-02-28` expiry early across leap day `2024-02-29`, drifting every policy anchor over multi-year tracking! Must use calendar `relativedelta(years=1) - timedelta(days=1)`.
- **Homonym Merge Bug (`customer_account_service.py:51-54`)**: When a PDF lacks NRIC/BRN, [`customer_account_service.py:51-54`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/customer_account_service.py#L51-L54) runs `select(CustomerAccount).where(CustomerAccount.canonical_name == canonical_name)`, quietly attaching different people sharing common Malaysian names to the wrong customer dossier!
- **Orphan Foreign Key (`insurance_tenure_service.py:210`)**: `vehicle_id = veh.id if veh else new_id()` generates a random UUID for `tracked_vehicle_id` even when `veh is None`, causing foreign-key violation when inserting `InsuranceTenure` (`tracked_vehicle_id` FK -> `tracked_vehicles.id` `NOT NULL`).
- **Hardcoded Demo Element IDs (`generation_service.py:260-265`)**: Checks hardcoded legacy IDs like `"text_ltaa394"`, `"text_ul2w5ka"`, `"rc_b_qr_code"` instead of semantic element roles (`assetSlot`).

