# Phase 4: Frontend De-Monolithization, Native PDF Download & PII Cleansing

> **Document:** `docs/plans/2026-11-14-phase-4-frontend-demonolithization-and-ux.md`  
> **Status:** In Execution  
> **Prerequisites:** Phase 1, Phase 2 & Phase 3 100% Verified  
> **Owner:** Principal Designer & Frontend Lead  

---

## 1. Executive Summary & Forensic Context

In Phases 1–3, we fixed critical P0 security exploits, established the double-entry financial ledger and PostgreSQL schema triggers (`migrations/077+`), optimized backend SQL queries, and enforced leap-safe calendar arithmetic.

**Phase 4** addresses frontend architecture, user experience, compliance, and code health (`F-11`, `F-13`, and `S-07`):
1. **Purge Hardcoded PII & Bank Literals (`F-11`, `S-07`):**  
   Under Malaysia's Personal Data Protection Act (PDPA 2010), real customer names (`CHENG TECK KIONG`), registration plates (`ANY 368`, `JXS 2820`), quotation references (`RL260000314`, `RL260000341`), and company bank account numbers (`Hong Leong Bank 12300318500`) must never be hardcoded in application source code or fall back into live preview renders. We replace all hardcoded literals across frontend and backend rendering templates with neutral dynamic fields and synthetic sample placeholders (`Valued Customer`, `ABC 1234`, `QT-SAMPLE-001`, `0000000000`).
2. **Replace Client-Side 4x Raster `jsPDF` Hack with Native Playwright PDF Export (`F-11`):**  
   In `frontend/src/components/session-workspace/review-components/useQuotationExports.ts:248-268`, clicking "Download PDF" captures the DOM with `toPng` (pixelRatio: 4) and dumps a raster image into `jsPDF`. This produces bloated, non-searchable raster files rather than official vector Playwright Chromium PDFs. We update the review export to use the canonical backend Playwright generation pipeline (`POST /sessions/{id}/versions` -> `GET /versions/{version_id}/pdf?download=true`).
3. **Eliminate Hardcoded Static `<svg>` Fallback in Preview (`F-11`):**  
   In `preview-phase.tsx:607-743`, non-Design-2 preview fell back to an unmaintainable static SVG with hardcoded strings. We align the preview canvas cleanly with `Design2CanvasView` and dynamic element rendering.
4. **Modernize Native Browser Dialogs (`window.alert`, `window.confirm`, `window.prompt`) (`F-13`):**  
   Replace intrusive native browser alerts and confirms in `frontend/src/components/tenures/` and admin views with accessible Radix UI `<ConfirmDialog />` and `useToast()` notifications.
5. **Dismantle Frontend Monoliths (`F-13`):**  
   Decompose oversized React modules exceeding the 600-line budget flagged in `commands/security-audit.py`, starting with `frontend/src/components/tenures/LedgerModals.tsx` (1,234 lines) into cohesive modal slices (`IssuePolicyModal`, `ConfirmHitModal`, `RecordMissModal`, `UploadCoverNoteModal`, `NewVehicleModal`).

---

## 2. 10-Point Edge-Case & Failure-Mode Matrix

| ID | Dimension | Specific Failure Mode Prevented in Phase 4 |
| :--- | :--- | :--- |
| **E-01** | Missing Insured Name | Draft without customer name renders neutral "Valued Customer" instead of leaking real customer PII. |
| **E-02** | Unplated Vehicle | Empty plate field renders clean placeholder ("ABC 1234" / "") instead of "ANY 368" or "JXS 2820". |
| **E-03** | Missing Bank Details | Unconfigured tenant bank details display placeholder ("Bank Name", "0000000000") without leaking Hong Leong account. |
| **E-04** | Large Quotation PDF | PDF download uses streaming backend Playwright Chromium vector output instead of choking client RAM with 4x PNG blobs. |
| **E-05** | PDF Generation Failure | Export error triggers standard error banner/toast rather than unhandled Promise rejection or corrupt file download. |
| **E-06** | Dirty Workspace Export | Triggering PDF export automatically flushes and saves active dirty inputs before requesting generation. |
| **E-07** | Concurrent Download Clicks | Export button state disables while generation is pending to prevent duplicate version generation. |
| **E-08** | Browser Alert Interruption | Background automation, Playwright E2E tests, and mobile users are not blocked by modal `window.alert()` dialogs. |
| **E-09** | Ledger Modal State Slicing | Decomposed modal slices retain identical form validation, loading states, and error handling without prop drill regressions. |
| **E-10** | Zero Client Calculation Dual Truth | All road tax and premium calculations remain authoritative solely in backend services. |

---

## 3. Serialized Tasks

### Task 1: Purge Hardcoded PII and Bank Details Across Frontend and Backend Templates (F-11, S-07)
- Modify: `frontend/src/components/template-canvas/design2-canvas.tsx`
- Modify: `frontend/src/components/template-canvas/shared.tsx`
- Modify: `frontend/src/components/template-preview.tsx`
- Modify: `frontend/src/lib/template-section-compiler.ts`
- Modify: `frontend/src/components/session-workspace/preview-phase.tsx`
- Modify: `frontend/src/app/builder/templates/[id]/builder/page.tsx`
- Modify: `frontend/src/components/template-builder/live-simulator/live-simulator.tsx`
- Modify: `backend/app/rendering/template_renderer_design2.py`
- Modify: `backend/app/rendering/template_renderer.py`

### Task 2: Replace Client-Side `jsPDF` Raster Hack with Native Playwright PDF Export (F-11)
- Modify: `frontend/src/components/session-workspace/review-components/useQuotationExports.ts`
- Modify: `frontend/src/components/session-workspace/preview-phase.tsx`

### Task 3: Replace Native Browser Dialogs with Accessible Radix/shadcn UI (F-13)
- Modify: `frontend/src/components/tenures/TenureStageSelector.tsx`
- Modify: `frontend/src/components/tenures/useLedgerModals.ts`
- Modify: `frontend/src/components/tenures/useLedgerState.ts`
- Modify: `frontend/src/app/client-records/page.tsx`
- Modify: `frontend/src/components/gemini-header-meter.tsx`

### Task 4: Dismantle `LedgerModals.tsx` Monolith into Cohesive Feature Slices (F-13)
- Create modal components in `frontend/src/components/tenures/modals/`:
  - `IssuePolicyModal`
  - `ConfirmHitModal`
  - `RecordMissModal`
  - `UploadCoverNoteModal`
  - `NewVehicleModal`
- Refactor: `frontend/src/components/tenures/LedgerModals.tsx` (<250 lines)

### Task 5: Authentic Verification & Knowledge Base Gate
- Run `commands/security-audit.py` to confirm zero PII violations and reduced monolith count.
- Run `cd frontend && npx tsc --noEmit`.
- Run `.\.venv\Scripts\pytest.exe tests/`.
- Run `commands/verify-brain.py`.
- Update `docs/core/STATE.md`.
