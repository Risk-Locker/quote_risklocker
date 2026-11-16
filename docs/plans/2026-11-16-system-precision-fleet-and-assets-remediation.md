# System Precision, AI Fleet Quota Window & Assets Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development`, `systematic-debugging`, and `Rule 06 (Serialized Milestones)` to execute this plan cleanly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve 5 critical system defects: (1) align AI Studio fleet management with Google's Pacific Time midnight reset window (4:00 PM MYT winter / 3:00 PM MYT summer) with interactive timeline & batch task assigner; (2) implement an autonomous Extraction & Post-Processing Referee to catch company vs private and commercial vehicle / lorry contradictions; (3) fix vehicle naming capitalization and duplicate brand rendering; (4) fix stuck "analyzing/ranking" state in Marketing Comparison; and (5) overhaul the Assets Library in `/builder/assets` with sticky toolbar, S3-style Inspector modal, and removal of test debris.

**Architecture:** 
1. **Extraction Referee (`app/extraction/referee.py`):** Authoritative cross-field fact-checking gate running pre- and post-extraction. Validates `customer_name` (corporate flags like `SDN BHD`), `ic_or_brn` (SSM/BRN vs NRIC), `vehicle_type` (lorries, goods vehicles, BDM/BTM KG vs saloon cars), and overrides contradictory product/coverage strings (e.g. converting `Private Car Comprehensive` to `Commercial Vehicle Comprehensive` for lorries/companies).
2. **AI Fleet Management (`app/services/gemini_account_service.py` & `pacer_sentinel.py`):** Strictly track Google AI Studio's 24-hour calendar window resetting at 12:00 AM Pacific Time (US/Pacific), translating to 4:00 PM MYT during PST and 3:00 PM MYT during PDT. Record historical calls per cycle, and enforce batch scheduling (~9–10 PDFs per model, capping <= 200k TPM and 13 RPM, staggering by 70s between chunks).
3. **Fleet Monitoring UI (`frontend/src/app/settings/ai-engine/page.tsx` & `components/gemini-timeline-calendar.tsx`):** Interactive timeline and calendar showing calls, timestamps, users, purpose, tokens/min, and tokens/call with clean animated charts.
4. **Vehicle Naming & Clean Ledger (`vehicle_simplifier_service.py` & `CustomerVehicleLedgerPane.tsx`):** Fix regex capitalization preserving uppercase alphanumeric model codes (e.g. `V116-HA`, `BLM`, `XLE`) and deduplicate brand prefixing when `vehicle_model` already contains the brand.
5. **Assets Library UX (`frontend/src/app/builder/assets/page.tsx`):** Make filter/sort toolbar sticky (`sticky top-0 z-20`), provide an S3-style detail inspection modal, and clean dummy test records from `business_assets`.
6. **Comparison UI State Hardening (`comparison-matrix.tsx` & `UnderwriterQuoteCard.tsx`):** Add auto-dismiss timeouts to `operationStatus` loading states to prevent stuck "analyzing/ranking" banners.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Python `zoneinfo`, Next.js 15, React 19, TypeScript, Tailwind CSS, `@phosphor-icons/react`.

---

## Serialized Milestones Roadmap

| Milestone | Title | Net LOC Budget | Primary Touched Subsystems | Plan Document |
| :--- | :--- | :--- | :--- | :--- |
| **M1** | **Extraction Referee Gate & Vehicle Naming Fixes** | ~350 LOC | `backend/app/extraction/`, `backend/app/services/vehicle_simplifier_service.py`, `frontend/src/components/comparison/` | `docs/plans/milestone-1-extraction-referee-and-naming.md` |
| **M2** | **AI Fleet Google PT Quota Window & Batch Assigner** | ~380 LOC | `backend/app/services/gemini_account_service.py`, `backend/app/extraction/pacer_sentinel.py`, `backend/app/services/token_preflight_service.py` | `docs/plans/milestone-2-ai-fleet-pt-calendar-and-pacing.md` |
| **M3** | **AI Fleet Monitoring Dashboard (Calendar & Timeline)** | ~400 LOC | `frontend/src/app/settings/ai-engine/`, `frontend/src/components/` | `docs/plans/milestone-3-ai-fleet-monitoring-dashboard.md` |
| **M4** | **Assets Library UX (Sticky Toolbar, Inspector Modal & Cleanup)** | ~450 LOC | `frontend/src/app/builder/assets/page.tsx`, `backend/app/services/business_asset_service.py` | `docs/plans/milestone-4-assets-library-ux-and-cleanup.md` |
| **M5** | **Marketing Comparison State Hardening & Auto-Dismiss** | ~200 LOC | `frontend/src/components/comparison/comparison-matrix.tsx`, `UnderwriterQuoteCard.tsx` | `docs/plans/milestone-5-marketing-comparison-state-hardening.md` |
| **M6** | **Design 2 Quotation Typography & Exact Font Pairing** | ~220 LOC | `backend/app/rendering/template_renderer_design2.py`, `benefit_schedule_renderer.py`, `frontend/src/components/template-canvas/design2-canvas.tsx` | `docs/plans/milestone-6-design2-typography-and-fonts.md` |

---

## Milestone Execution Contract

Per **Rule 06**, each milestone:
1. Begins with a Red-First failing unit test (`test-driven-development`).
2. Implements the minimal cohesive changes within its bounded Net LOC budget.
3. Passes full authentic verification (hermetic `pytest`, TypeScript `npx tsc --noEmit`).
4. Updates Knowledge Base & tests before human checkpoint for the next milestone.
