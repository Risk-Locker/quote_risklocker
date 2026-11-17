# 2026-11-17 — Saving Mechanics, Monthly Ledger UX, Cover Note Classifier, Incognito Dry-Run & Test Sample Audit Plan

> **Branch:** `v30.4` | **Mode:** Architectural Audit & Serialized Remediation Plan  
> **Scope:** Cross-stack UX/data-integrity audit covering Save & Sync mechanics, `/ledger` density & scrollability, `/comparison` vertical chrome compression, Cover Note vs Quotation classification accuracy, Incognito/Test Mode Dry-Run Ledger Checker, hidden 405/sync/UI defects, and 36 verified test PDFs from `samples/`.

---

## 1. Executive Summary of Verified Findings

During full-stack forensics across backend routers/services (`backend/app/`) and frontend components (`frontend/src/`), we verified **5 high-impact bugs** directly explaining the user's symptoms, alongside **systematic UI clutter and monolith debt**:

| # | Severity | Verified Defect | Exact Evidence | User Symptom Explained |
| :--- | :--- | :--- | :--- | :--- |
| **F-01** | **CRITICAL (Data Corruption)** | Cross-vehicle session overwrite on save | `backend/app/services/tenure_identity_sync_service.py:322-347` (`or_(SessionModel.tenure_id == tenure.id, SessionModel.customer_id == cust.id)`) | Editing Car A's workspace/comparison overwrites `vehicle_no`, `car_model`, `engine_cc`, `roadtax`, and dates on **all** sibling cars owned by the same `customer_id`. |
| **F-02** | **CRITICAL (405 Broken Mutation)** | Wrong HTTP path on `/ledger` row patch | `frontend/src/components/tenures/useLedgerState.ts:312` calls `PATCH /tenures/${tenureId}`, while `backend/app/api/routers/tenures.py:941` only defines `PATCH /tenures/{tenure_id}/ledger-fields` | Inline stage/detail edits and `Revert`/`Reopen` on `/ledger` fail with `405 Method Not Allowed`. |
| **F-03** | **HIGH (405 Broken Save)** | Wrong HTTP method on Comparison NCD modal save | `frontend/src/components/comparison/comparison-matrix.tsx:788` & `useNcdHistory.ts:47` call `PATCH /comparison/{id}/fixed-costs`, while `comparison.py:201` only accepts `POST` | Saving NCD values inside the NCD modal fails with `405 Method Not Allowed`. |
| **F-04** | **HIGH (Silent Save Loss + Dual Math)** | Auto-save drops failed ops & runs dual client rounding | `frontend/src/components/session-workspace/provider.tsx:26-67, 573-578`; `useReviewWorkspaceState.ts:108-114, 351-395`; `policy-fields-card.tsx:689` | Over-automated 800ms saves reset `dirty=false` on validation error (`"All changes saved"` lie), duplicate `Decimal` rounding logic, block nav with `window.confirm()`, and coerce EV `kW` back to `CC` on blur. |
| **F-05** | **HIGH (Classifier Misread)** | Cover Note vs Quotation misscoring without filename hint | `backend/app/extraction/candidate_finder.py:145-247`; verified on `samples/covernotes/20250212_JGA1_CoverNote_BerjayaSompo.pdf` (`+35.0` -> wrong `quotation` when renamed `upload.pdf`) & `20251002_NA_Quotation_Etiqa_Declined.pdf` | Welcome letters, `PRIVATE CAR SCHEDULE`, `Stamp Duty Paid`, multiline `Policy No`, and portal navbar text (`COVER NOTE ENQUIRY`) distort classification scores; QBE raw text lacks `"QBE"` keyword in portal exports. |
| **F-06** | **MEDIUM-HIGH (UX Clutter & Dead Space)** | Ineffective Compact mode, off-screen horizontal scroll, stacked chrome | `LedgerTable.tsx:95-138`, `TenureRow.tsx:163-775`, `comparison-matrix.tsx:1476-2050, 2245-2305`, `upload-workspace.tsx:1560-1561` | Compact mode still totals `>= 1,226px` wide; horizontal scroll buttons sit non-sticky above `<thead>`; repeated `Cli Paid`/`Agc Paid`/dates clutter `/ledger`; 7 stacked headers push `/comparison` cards and `Generated Risk-Locker Quotations` far below fold; Batch Test Mode sets `tenure_id=None` despite UI promising comparison matrix compilation. |

Static audit baseline (`commands/security-audit.py`): `CRITICAL=98` (83 `MISSING_RBAC`, 11 `STORAGE_BYPASS`, 4 `NO_DUNDER_IMPORT`), `HIGH=340` (293 `FLOAT_MONEY`, 12+ `NATIVE_DIALOG`, 10 `LEAP_YEAR_DAYS`, 8 `MUTATING_GET`, 8 `UNTYPED_ADMIN_PAYLOAD`, 3 `XSS_DOM_SINK`, 2 `FORMULA_POW_DOS`, 2 `PLAYWRIGHT_NO_SSRF_GUARD`, 2 `SSRF_*`), `MEDIUM=89` (39 `MONOLITH_PY`, 39 `MONOLITH_TS`, 11 `STDOUT_PRINT`). Notice `comparison-matrix.tsx` alone still has **19 `alert()` / `confirm()` calls**, and `comparison-matrix.tsx:2297` runs client `Math.round(gq.total_payable)` ignoring authoritative backend rounding.

---

## 2. Architecture Decisions & Trade-off Analysis

### 2.1 Saving & Confirmation UX (Workspace & Comparison)
*Question:* Should edits require confirmation per change so users see what changes without breaking synchronization or blocking quotation generation?
- **Option A (Rejected — Modal/Dialog Per Edit):** Opening a confirmation prompt every time a field blurs creates massive click fatigue and breaks fast multi-field keyboard Tab workflows.
- **Option B (Recommended — Staged Draft Buffer + Explicit Commit Strip):**
  - Keep **optimistic React working edits unpersisted until commit** (remove silent `800ms` auto-`PATCH` from `useReviewWorkspaceState.ts` and side-effecting cross-syncs on blur).
  - Show a crisp, non-blocking **Sticky Unsaved Changes Bar** (`"N unsaved edits: Road Tax, Sum Insured — Affects Comparison & Ledger [Discard] [Save & Sync]"`).
  - Highlight modified inputs with an `amber` border indicator and track real server validation failures inside `provider.tsx` (`dirty` stays `true` on error; never purge failed ops silently).
  - Allow **[Generate Quotation]** directly from an edited workspace by running an atomic pre-flight `Save & Recompute -> Poll Backend Decimal Totals -> Generate PDF/PNG` pipeline with an inline summary toast, so quotation generation is never blocked.
  - Fix `tenure_identity_sync_service.py` immediately so customer-level propagation updates **only** `customer_name` / `ic_or_brn` across `customer_id`, while vehicle/period/fee propagation scopes strictly to `tenure_id` / `tracked_vehicle_id`.

### 2.2 Monthly Motor Ledger (`/ledger`) Compression & Timeline Focus
- **True Compact Mode (`<= 960px` total width):** Condense columns to 5 core visible columns by default (`Checkbox+Vehicle/Owner`, `Period/Expiry`, `Timeline & Stage`, `Latest Quote & Link`, `Actions`) so `1280px+` screens display the entire row without horizontal scrolling. Move verbose secondary metadata (`Creation Date`, `Full Sub-Agent/Notes`) into expandable row details or `Detailed` mode.
- **Timeline Focus & Declutter:** Keep the **Timeline / Sent-to-Client pipeline** (`Quotations -> Sent -> Issued -> Hit/Miss` + `days_in_stage` + expandable activity timestamps) as compact interactive pills; remove redundant `✓ Cli Paid / Cli Unpaid` & `✓ Agc Paid / Agc Due` badges (`TenureRow.tsx:756-775`), remove duplicate `Confirm Hit ✓` in Col 4, and remove repeated coverage dates in Col 4.
- **Viewport-Sticky Horizontal Scroll Rail:** Pin subtle `<- Left | Right ->` column pan controls + floating top/bottom synced scrollbar wrapper when `scrollWidth > clientWidth`, instead of a single non-sticky strip at row 0.

### 2.3 Top Chrome & Comparison Fold Recovery
- Merge `Vehicle Info Header` (`comparison-matrix.tsx:1752-1888`), `#tour-stepper` (`1476-1568`), and `Pricing Display Toolbar` (`1891-2050`) into a **single ~84px sticky top bar**, stopping duplication of Plate, IC, Model, CC, Road Tax, and Runner Fee already shown in `CustomerVehicleLedgerPane`.
- Promote `Generated Risk-Locker Quotations` (`line 2245`) into an immediately accessible **top-bar drawer/tab pill (`Issued Quotations (N)`)** plus replace `Math.round(gq.total_payable)` (`line 2297`) with backend-formatted totals.

### 2.4 Cover Note Classifier & Incognito/Test "Dry-Run Ledger Check"
- Upgrade `score_document_type()` (`candidate_finder.py:145-247`):
  - Recognize multi-page cover note packets with p0 cover letters (`"HERE IS YOUR INSURANCE POLICY"`), `PRIVATE CAR SCHEDULE` / `JADUAL KERETA PERSENDIRIAN`, `MOTOR POLICY SCHEDULE`, `STAMP DUTY PAID` / `SETEM HASIL DIBAYAR`, and newline-separated `Policy No` values.
  - Strip portal chrome strings (`COVER NOTE ENQUIRY`, `QUOTATION/NEW BUSINESS`, `AGENDA`/`MENU`) before scoring text cues.
  - Distinguish instructional/conditional quotation prose (`"upon issuance of cover note"`, `"subject to cover note"`) from document headings on page 1–2.
  - Add QBE non-text header signatures (`PRIVATE CAR PROTECTOR QUOTATION`, account patterns `02103586`, `MPA-YY-...`) to DB `InsuranceCompany` aliases so company detection works even with blank filenames.
- **Test / Incognito "Ledger Dry-Run Check" (`GET /sessions/{id}/sandbox-ledger-check`):**
  - Strictly read-only simulation (`is_test=True` remains 100% isolated from live ledger tables).
  - Returns exact JSON breakdown:
    1. **Document Type Decision & Evidence:** `covernote` vs `quotation`, numeric score breakdown, matched/excluded cues, and test-only classification override switch to verify extraction under both modes.
    2. **Simulated Customer & Vehicle Resolution:** Matches found against live `CustomerAccount` / `TrackedVehicle` (read-only) — shows *"Would bind to existing customer/vehicle X (plate/chassis match)"* or *"Would create new record"*, flagging any NRIC/owner mismatch without writing a row.
    3. **Simulated Tenure & Expiry Month Placement:** Shows exact computed `expiry_month` (`YYYY-MM`), *"Would create new YYYY-MM tenure / Would append vN quote to existing tenure / Would flag duplicate hash"*, and Cover Note -> `"Issue Policy"` + next-year projection simulation.
    4. **Isolated Batch Test Comparison:** Fix `upload_intake_service.py` / `extraction_worker.py` so `mode=comparison` + `is_test=True` creates an isolated `is_test=True` comparison container (`InsuranceTenure.is_test = True`, excluded from all `/ledger`, `/insights`, and client lookups) instead of returning `tenure_id=None`.

---

## 3. Serialized Execution Roadmap (5 Milestones — revised 2026-11-17)

> Each milestone stays strictly within `<= 300–500` net LOC and must pass `pytest`, `npx tsc --noEmit`, `verify-brain.py`, and live browser checks before moving to the next.
>
> **Revision note:** The original M2 combined `/ledger` and `/comparison` chrome. `comparison-matrix.tsx` is 2,441 lines with 19 native dialogs, so that combination exceeded the LOC budget. It is split into M2 (`/ledger`) and M3 (`/comparison`); later milestones shift by one.

1. **Milestone 1 (Save, Sync & API Repairs) — `VERIFIED`** (`milestone-1-save-sync-and-api-repairs.md`):
   - Fix F-01 (`tenure_identity_sync_service.py` customer vs vehicle scoping), F-02 (`useLedgerState.ts` `/ledger-fields`), F-03 (`comparison-matrix.tsx` & `useNcdHistory.ts` `POST /fixed-costs`), F-04 EV `kW` coercion (`policy-fields-card.tsx:689`) & `provider.tsx` failed-op `dirty` tracking.
   - Replace silent `800ms` auto-save in Quotation Workspace with Staged Draft Buffer + Sticky Unsaved Changes Bar + atomic `[Generate Quotation]` pre-flight save; remove client `Math.round` / dual rounding math.
2. **Milestone 2 (`/ledger` Compact Layout, Sticky Pan Rail & Dialog Purge)** (`milestone-2-ledger-ux-compact-and-dialogs.md`):
   - Redesign `/ledger` `Compact` mode (`<= 960px` fit), viewport-sticky horizontal pan rail, remove repeated `Cli Paid`/`Agc Paid` & duplicate Hit/Date clutter, consolidate row actions, slice `TenureRow.tsx`, and replace `/ledger` `alert()`/`confirm()` with Radix dialogs/toasts.
3. **Milestone 3 (`/comparison` Chrome Compression & Dialog Purge):**
   - Compress `/comparison` top stacked chrome into a unified sticky bar, expose `Generated Risk-Locker Quotations` drawer pill above the fold, extract the chrome into slices out of `comparison-matrix.tsx`, and eliminate the 19 `alert()`/`confirm()` calls in `/comparison` (+ `useSnapshotExport.ts`, `useWhatsAppTester.ts`, `AdjustFeesModal.tsx`, `manual-quote-modal.tsx`).
4. **Milestone 4 (Cover Note Classifier & Incognito Sandbox Dry-Run):**
   - Harden `score_document_type()`, QBE/portal-chrome company detection, and add unit regressions for all `samples/` failure modes (`BerjayaSompo` welcome cover letter, `Etiqa Declined` portal navbar, 5p `Tune`, QBE neutral filename).
   - Build read-only `GET /sessions/{id}/sandbox-ledger-check` + Incognito/Test Dry-Run Inspector drawer + isolated `is_test=True` Comparison batch support (`InsuranceTenure.is_test`).
5. **Milestone 5 (RBAC Hardening & Live Responsive Gauntlet):**
   - Remediate top `CRITICAL` RBAC / `MUTATING_GET` / `FLOAT_MONEY` items across `comparison.py`, `tenures.py`, `catalogs.py` & execute full live API + Playwright responsive QA (`1024px`, `1280px`, `1920px` @ `80%/100%/120%` zoom).

---

## 4. Curated 36 Unique Real Test PDFs (`samples/`) for Test / Incognito QA

All 36 files below are verified SHA-256 unique within `samples/` (`107` total unique PDFs audited):

### A. Official Cover Notes (3 cases — test Cover Note vs Quotation classifier & timeline promotion)
1. `samples/covernotes/20250212_JGA1_CoverNote_BerjayaSompo.pdf` — 14p Berjaya Sompo, BMW X7 (`2998 CC`, Agreed Value RM 485k, All Drivers, Unlimited Towing). *Key test:* rename to `test_cn_1.pdf` when uploading to verify our welcome-letter + `PRIVATE CAR SCHEDULE` classifier fix.
2. `samples/covernotes/20260508_JXA5779_CoverNote_Tune.pdf` — 5p Tune Protect, Toyota Vios (`1496 CC`, RM 76k SI). Official Policy Schedule cover note.
3. `samples/covernotes/20260608_USM15_CoverNote_Lonpac.pdf` — 9p Lonpac, Mercedes-Benz C200 AMG Line (`1991 CC`, RM 103k Agreed Value, LLP, Windscreen).

### B. Multi-Insurer Same-Vehicle Comparison Batches (15 cases — test cross-insurer dedupe & ranking)
- **Batch 1 (`ANY368` — Tesla Model 3 Performance EV):**
  4. `samples/quotations/amgen-liberty/20260413_ANY368_Quotation_Amgen.pdf` (3p, RM 199k SI, EV)
  5. `samples/quotations/berjaya-sompo/20260504_ANY368_Quotation_BerjayaSompo.pdf` (1p short format, EV)
  6. `samples/quotations/etiqa/20260421_ANY368_Quotation_Etiqa.pdf` (2p, Flood, Unlimited Towing, PA)
  7. `samples/quotations/qbe/20260417_ANY368_Quotation_QBE.pdf` (1p portal summary layout; lacks `"QBE"` keyword in raw text)
- **Batch 2 (`PRV368` — Tesla Model Y RWD EV, `_PA` & `_REF` variants):**
  8. `samples/quotations/amgen-liberty/20260526_PRV368_Quotation_Amgen_PA.pdf` (3p, PA add-on)
  9. `samples/quotations/berjaya-sompo/20260526_PRV368_Quotation_BerjayaSompo_REF.pdf` (2p `_REF` referral format, EV)
  10. `samples/quotations/stmb-takaful/20260706_PRV368_Quotation_STMB_REF.pdf` (1p Takaful `_REF` format, RM 159k SI)
- **Batch 3 (`JXS2820` — Chery Tiggo 7 Pro 2024, `1598 CC`, Special Perils):**
  11. `samples/quotations/amgen-liberty/20260122_JXS2820_Quotation_Amgen_SP.pdf` (3p, Special Perils + Windscreen)
  12. `samples/quotations/qbe/20260122_JXS2820_Quotation_QBE_SP.pdf` (1p Agreed Value + Special Perils)
  13. `samples/quotations/stmb-takaful/20260122_JXS2820_Quotation_STMB_SP.pdf` (1p Takaful Special Perils)
- **Batch 4 (`JRW1813` — Mazda CX-5 `2488 CC`, Multi-Year & Legacy UCD Layouts):**
  14. `samples/quotations/amgen-liberty/20210218_JRW1813_Quotation_AmGenPRemier.pdf` (1p legacy AmGen Premier)
  15. `samples/quotations/amgen-liberty/20240710_JRW1813_Quotation_Liberty.pdf` (2p Liberty brand alias, Market Value, LLP, LLOP, Unnamed Drivers, PA)
  16. `samples/quotations/qbe/20220117_JRW1813_Quotation_QBE_UCD.pdf` (2p UCD format, LLOP, Flood, Windscreen)
  17. `samples/quotations/tune-protect/20230109_JRW1813_Quotation_Tune_UCD.pdf` (1p Tune UCD compact format)
  18. `samples/quotations/tune-protect/20230830_JRW1813_Quotation_Tune.pdf` (2p Tune standard quote)

### C. Special Vehicle Classes, Old Betterment & Unregistered `NA` Plates (11 cases)
19. `samples/quotations/lonpac/20260303_VQL5852_Quotation_Lonpac_REF.pdf` — **Commercial 10-Ton Heavy Lorry** (4p, Hino 500 GH8JL1D, RM 295k SI, RM 12,036.50 premium; tests commercial BDM/tonnage & quotation slip cues).
20. `samples/quotations/berjaya-sompo/20250404_VCC655_Quotation_Sompo_Perils.pdf` — **High-CC Sports Car** (2p, Porsche Boxster `3436 CC`, RM 161k Agreed Value, Perils, Unlimited Towing).
21. `samples/quotations/qbe/20260310_SJ8302_Quotation_QBE.pdf` — **Window Van / Non-Saloon & Sabah Plate** (1p, `SJ8302` Toyota Alphard `2493 CC`, RM 263k; tests non-saloon/East Malaysia handling).
22. `samples/quotations/qbe/20260311_JUM2709_Quotation_QBE_extras.pdf` — **Small <1000cc Compact** (1p, Perodua Ativa `998 CC`, Agreed Value RM 53k + extras).
23. `samples/quotations/qbe/20260506_VKL7831_Quotation_QBE.pdf` — **Newer Marque Normalization** (1p, Jaecoo Omoda C9 `1998 CC`, RM 146k Agreed Value).
24. `samples/quotations/amgen-liberty/20250922_ACL9613_Quotation_Amgen.pdf` — **30+ Year Old Vehicle / Max Betterment** (2p, 1994 Proton Wira `1468 CC`, RM 5k SI).
25. `samples/quotations/amgen-liberty/20260603_JJC9250_Quotation_Amgen.pdf` — **20+ Year Vehicle** (3p, 2005 Proton Waja `1584 CC`, RM 10k SI).
26. `samples/quotations/stmb-takaful/20250604_JJC9250_Quotation_STMB.pdf` — Same old Proton Waja in STMB Takaful (cross-check betterment consistency).
27. `samples/quotations/amgen-liberty/20251002_NA_Quotation_Amgen.pdf` — **Unregistered `NA` Plate (AmGen)** (3p, Tesla Model Y RWD 2025, RM 207.3k SI; tests chassis/no-plate ledger check).
28. `samples/quotations/etiqa/20250506_NA_Quotation_Etiqa_WS.pdf` — **Unregistered `NA` Plate (Etiqa Windscreen + Flood + PA)** (2p, Tesla EV).
29. `samples/quotations/etiqa/20250711_NA_Quotation_Etiqa_LLP_LLOP.pdf` — **Unregistered `NA` Plate (Etiqa LLP + LLOP)** (2p, Tesla EV).

### D. Extractor Stress Cases, Portal Chrome, Multi-Page & OCR Fallback (7 cases)
30. `samples/quotations/etiqa/20251002_NA_Quotation_Etiqa_Declined.pdf` — **Portal Chrome & Declined Banner Stress Test** (contains `"COVER NOTE ENQUIRY"` in portal navbar + Smart Key Replacement + Special Perils).
31. `samples/quotations/etiqa/20251003_NA_Quotation_Etiqa_Perils.pdf` — 2p Etiqa EV with Key Care / Smart Key Replacement + Special Perils.
32. `samples/quotations/etiqa/20260730_JXJ5711_Quotation_Etiqa.pdf` — 2p Perodua showing dual Agreed + Market Value options, Windscreen, Flood, PA.
33. `samples/quotations/etiqa/20260603_JHC9400_Quotation_etiqa.pdf` — 2p Kia minimal add-ons + lowercase `_etiqa` filename variant.
34. `samples/quotations/tune-protect/20260707_JXF8795_Quotation_Tune_28k.pdf` — **5-Page Quotation Boundary Stress Test** (Proton Saga `1332 CC`, RM 28k; scores `+35` without filename due to `"CERTIFICATE OF INSURANCE"` text).
35. `samples/quotations/amgen-liberty/20260901_JYH8773_Quotation_Amgen.pdf` — 3p Tesla Model 3 Premium RWD (pair with Etiqa/STMB `JYH8773` to verify post-refactor EV kW lock).
36. `samples/template-layouts/quotation_A9243A.pdf` — **Scanned 0-Char Image-Only PDF** (tests Vision OCR extraction fallback and graceful UI status when no selectable text exists).
