# Autonomous AI Fleet Engine, Staging Token Pacer & Template Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate Google AI Studio account suspension risks by strictly enforcing a two-model pool (`gemini-3.1-flash-lite` and `gemini-3.5-flash-lite`), pre-flight token weighing for staged uploads, an adaptive 24/7 "Living Eye" mesh dispatcher, Google AI Studio rate-limit analytics parity, and unified Design 1/Design 2 template logic with dynamic Towing and actuarial Betterment math.

**Architecture:** 
Decomposes the system into 5 serialized milestones:
1. Hard model lockdown purging high-risk `gemini-3.8-flash` (which has a dangerous 20 RPD cap) and pinning strictly to `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite` with 13 RPM / 200k TPM / 480 RPD safety ceilings.
2. Pre-flight staging token estimation that calculates token weights as staff stage PDFs and rejects over-capacity files (>200k tokens) before dispatch.
3. An adaptive, closed-loop "Living Eye" pacer that senses Google latency and staff urgency (interactive single quote vs. 240-file KFC lunch batch) to interleave calls evenly via $S = 2N$ round-robin.
4. Full Google AI Studio Rate Limit dashboard parity in the UI (`/settings/ai-engine`), querying persisted `GeminiApiCallLog` across 1-day, 7-day, and 28-day intervals.
5. Standardizing Design 1 (Bilingual Agency) and Design 2 (Modern Matrix) with in-place Towing dynamic upgrade and exact calendar-day Betterment age math.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL (`gemini_api_call_logs`, `jobs`), Google Generative Language API (HTTP/2 httpx), Next.js 15, React 19, Tailwind CSS, `@phosphor-icons/react`.

**Spec:** Built from user requirements on 2026-11-13, live Google AI Studio Rate Limit table (`gen-lang-client-0587737993`), `malaysian_motor_towing_reference.md`, and PIAM Motor Tariff rules.

## Global Constraints

- **STRICT TWO-MODEL IMMUTABILITY:** The system MUST NOT under any circumstances invoke or fallback to any model other than `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite`. `gemini-3.8-flash` (20 RPD cap), Pro models, and preview models are strictly forbidden in production.
- **HARD SAFETY CEILINGS PER SLOT:**
  - Max RPM: **13 requests per minute** (Google limit: 15).
  - Max TPM: **200,000 tokens per minute** (Google limit: 250,000).
  - Max RPD: **480 requests per day** (Google limit: 500).
- **STRICT EQUILIBRIUM SERIALIZATION:** Requests must be distributed in round-robin order across all $S = 2N$ slots ($i \pmod S$). No single account or model may be starved at 0 while another is overloaded.
- **ZERO CLIENT-SIDE FINANCIAL/DATE MATH:** Betterment age calculations and towing entitlements are authoritative only in backend Python `relativedelta` services.
- **NO DESTRUCTIVE KEY MUTATIONS:** Existing stored API keys and custom labels must not be editable in place to prevent accidental credential corruption. A non-destructive "Pause / Rest Key" operational toggle must be provided.

## Review Focus

- Input with >200k tokens (e.g. 150-page manual) must be rejected immediately in the staging area with a friendly warning, never reaching the Google API.
- Burst upload of 240 staged PDFs must be paced across the rolling 60-second window, never exceeding 13 RPM per slot, completing in ~4.6 minutes without a single 429 error.
- Selecting Rider Plan 4 or OTO 360 must upgrade the Top-Right Towing card to "UNLIMITED TOWING ASSISTANCE" in-place, without generating a duplicate towing card in the bottom matrix.
- Betterment calculation for 9 years 11 months 29 days must resolve to 9 completed years (35% scale), not 10 years (40%).
- Historical call analytics must persist across server restarts and correctly display peak RPM, peak TPM, and total RPD across 1-day, 7-day, and 28-day views matching Google AI Studio.

---

### Task 1: Complete Model Lockdown & Emergency Purge of `gemini-3.8-flash`

**Files:**
- Modify: `backend/app/extraction/ai_sharded_pool.py:20-40`
- Modify: `backend/app/services/gemini_account_service.py:120-145`
- Modify: `backend/app/core/config.py:65,310`
- Modify: `backend/app/extraction/gemini_extractor.py:415-430,520-535`
- Test: `tests/unit/test_gemini_model_lockdown.py`

- [x] **Step 1: Write failing test asserting complete ban of `gemini-3.8-flash` and unverified models**
  Create `tests/unit/test_gemini_model_lockdown.py` asserting that:
  - `ai_sharded_pool.VERIFIED_ACTIVE_MODELS` equals exactly `("gemini-3.1-flash-lite", "gemini-3.5-flash-lite")`.
  - `gemini_account_service.PARALLEL_MODELS` equals exactly `("gemini-3.1-flash-lite", "gemini-3.5-flash-lite")`.
  - Any attempt to acquire a slot or instantiate a model with `gemini-3.8-flash` raises `ValueError("Forbidden model tier")`.
  - Safe limits are enforced: `SAFE_RPM_PER_SLOT == 13`, `SAFE_RPD_PER_SLOT == 480`, `SAFE_TPM_PER_SLOT == 200_000`.

- [x] **Step 2: Run test to confirm failure**
  Run `pytest tests/unit/test_gemini_model_lockdown.py` and verify it fails due to existing `gemini-3.8-flash` in `ai_sharded_pool.py` and `gemini_account_service.py`.

- [x] **Step 3: Purge `gemini-3.8-flash` from `ai_sharded_pool.py` and `gemini_account_service.py`**
  - Update `VERIFIED_ACTIVE_MODELS` in `ai_sharded_pool.py` to `("gemini-3.1-flash-lite", "gemini-3.5-flash-lite")`.
  - Update `PARALLEL_MODELS` in `gemini_account_service.py` to `("gemini-3.1-flash-lite", "gemini-3.5-flash-lite")`.
  - Update `backend/app/core/config.py` default `gemini_model` from `gemini-3.1-flash-lite-preview` to `gemini-3.1-flash-lite`.
  - Update `SAFE_RPM_LIMIT_PER_SLOT = 13`, `SAFE_RPD_LIMIT_PER_SLOT = 480`, `SAFE_TPM_LIMIT_PER_SLOT = 200_000`.

- [x] **Step 4: Update fallback cascade in `gemini_extractor.py`**
  Ensure the primary model is `gemini-3.1-flash-lite` and the secondary model is `gemini-3.5-flash-lite`. Remove all references to `gemini-3.8-flash` and deprecated preview strings.

- [x] **Step 5: Run tests and verify 100% pass**
  Run `pytest tests/unit/test_gemini_model_lockdown.py`.

---

### Task 2: Pre-Flight Staging Token Weigher & Over-Capacity Disqualifier

**Files:**
- Create: `backend/app/services/token_preflight_service.py`
- Modify: `backend/app/services/upload_intake_service.py:80-120`
- Modify: `frontend/src/components/upload/upload-workspace.tsx:110-250`
- Modify: `frontend/src/lib/staged-uploads-storage.ts`
- Test: `tests/unit/test_token_preflight.py`

- [x] **Step 1: Write failing test for token pre-flight estimation and rejection**
  Create `tests/unit/test_token_preflight.py` asserting:
  - A 1-page PDF (~300 words) estimates ~8,000–15,000 tokens (eligible).
  - A 4-page PDF estimates ~45,000–60,000 tokens (eligible).
  - A 150-page PDF (~350,000 tokens) is flagged with `eligible=False`, `reason="Exceeds safe 200k TPM quota window"`.

- [x] **Step 2: Implement `token_preflight_service.py`**
  - Extract page count and character density using lightweight PDF header parser (PyMuPDF / pdfminer).
  - Heuristic formula: $\text{Tokens} = 1200 \times \text{page\_count} + \frac{\text{raw\_chars}}{3.8}$.
  - Return `{ "estimated_tokens": int, "is_eligible": bool, "page_count": int, "warning": str | None }`.

- [x] **Step 3: Integrate Pre-Flight Check in `upload_intake_service.py`**
  Add pre-flight validation before a PDF is committed to `jobs`. If `estimated_tokens > 200_000`, set job status to `rejected_oversize` and do not dispatch to Google AI Studio.

- [x] **Step 4: Update Frontend Staging Workspace (`upload-workspace.tsx`)**
  - Display a live token weight badge on each staged card: e.g. `~12k tokens (1 page)`.
  - If a file is oversized, show a red warning chip: `Disqualified: ~240k tokens exceeds 200k/min safe ceiling`. Disable the "Process" toggle for that file.
  - Add the **Live Staging Fleet Meter** at the top of the staging area:
    - `Total Staged: X files`
    - `Estimated Batch Tokens: Y k`
    - `Safe Processing Cadence: Z min`

- [x] **Step 5: Verify tests pass**
  Run `pytest tests/unit/test_token_preflight.py`.

---

### Task 3: The "Living Eye" Autonomous Pacer & Strict Mesh Equilibrium Dispatcher

**Files:**
- Create: `backend/app/extraction/pacer_sentinel.py`
- Modify: `backend/app/services/gemini_account_service.py:375-450`
- Modify: `backend/app/api/routers/system.py:400-450`
- Test: `tests/unit/test_pacer_sentinel.py`

- [x] **Step 1: Write failing test for strict $i \pmod S$ round-robin equilibrium and adaptive pacing**
  Create `tests/unit/test_pacer_sentinel.py` asserting:
  - Given 2 API keys (4 slots), dispatching 20 requests assigns exactly 5 requests to Slot 0, 5 to Slot 1, 5 to Slot 2, 5 to Slot 3 in sequence.
  - Given 4 API keys (8 slots), dispatching 24 requests assigns exactly 3 requests to each of the 8 slots in sequence.
  - When latency spikes (>4.0s), the sentinel delay between requests automatically stretches from 2.0s to 5.0s.
  - Rolling 60s request count never exceeds 13 on any slot; rolling 60s token count never exceeds 200,000.

- [x] **Step 2: Implement `PacerSentinel` in `pacer_sentinel.py`**
  - Manages global ticket sequence counter `ticket_seq` atomically.
  - Calculates target slot: `slot_idx = ticket_seq % len(active_slots)`.
  - Dynamically calculates inter-request breathing delay based on queue depth and latency:
    - Interactive mode (1-3 files): 2.0s delay.
    - Large batch / KFC mode (>20 files): 3.5s delay (~8-9 requests/min per slot, stress-free).
    - Congestion backoff: If Google average latency > 4.0s, back off to 6.0s.

- [x] **Step 3: Update `acquire_parallel_slot` in `gemini_account_service.py`**
  Ensure slot acquisition strictly matches the serialized ticket order and verifies:
  $$\text{requests}_{60\text{s}} < 13 \quad \text{and} \quad \text{tokens}_{60\text{s}} + \text{est\_tokens} < 200{,}000 \quad \text{and} \quad \text{daily\_count} < 480$$

- [x] **Step 4: Run tests and verify pass**
  Run `pytest tests/unit/test_pacer_sentinel.py`.

---

### Task 4: Google AI Studio Rate Limit Dashboard Parity & Historical Analytics

**Files:**
- Modify: `backend/app/services/gemini_account_service.py:950-1030`
- Modify: `backend/app/api/routers/system.py:420-470`
- Modify: `frontend/src/app/settings/ai-engine/page.tsx:1-400`
- Create: `frontend/src/components/gemini-analytics-chart.tsx`
- Test: `tests/unit/test_gemini_analytics_api.py`

- [x] **Step 1: Write failing test for historical analytics query endpoint**
  Create `tests/unit/test_gemini_analytics_api.py` asserting:
  - `GET /settings/gemini/analytics?time_range=today` returns accurate call counts, peak RPM, peak TPM, and total tokens from `gemini_api_call_logs`.
  - Supports `time_range` parameters: `today`, `last-1-day`, `last-7-days`, `last-28-days`.
  - Groups metrics by `(account_id, model)` matching Google AI Studio's rate limit page layout.

- [x] **Step 2: Implement analytics aggregation in `gemini_account_service.py`**
  Write `get_historical_analytics(db, time_range: str)` querying `GeminiApiCallLog` grouped by `account_id` and `model`:
  - Calculate `peak_rpm` (max requests in any 60-second window in that period).
  - Calculate `peak_tpm` (max tokens in any 60-second window in that period).
  - Calculate `total_calls_today` and `total_tokens`.

- [x] **Step 3: Expose API endpoint in `system.py`**
  Add `GET /settings/gemini/analytics` with RBAC protection (`Role.ADMIN`, `Role.SUPER_ADMIN`).

- [x] **Step 4: Build Google AI Studio Rate Limit Parity UI in `ai-engine/page.tsx`**
  - Add time-range toggle buttons: `[ Today | Last 1 Day | Last 7 Days | Last 28 Days ]`.
  - Render exact rate limit table mirroring Google AI Studio:
    - Columns: `Model`, `Category`, `RPM (Peak / Limit)`, `TPM (Peak / Limit)`, `RPD (Used / Limit)`, `Status`.
    - Rows strictly for `Gemini 3.1 Flash Lite` and `Gemini 3.5 Flash Lite`.
  - Add the non-destructive **Pause / Rest Account** operational switch:
    - Allows an admin to temporarily put an API key to sleep without modifying or deleting the credential string.
    - Disable direct text editing of key strings and labels to prevent accidental corruption.

- [x] **Step 5: Verify tests pass**
  Run `pytest tests/unit/test_gemini_analytics_api.py`.

---

### Task 5: Template Standardization & Towing / Betterment Logic Integration

**Files:**
- Modify: `backend/app/rendering/unified_addon_engine.py:340-380,520-560`
- Modify: `backend/app/rendering/template_renderer_design2.py:110-160`
- Modify: `frontend/src/components/template-canvas/design2-canvas.tsx:120-180`
- Modify: `backend/app/domain/betterment_engine.py` (or `render_context.py`)
- Test: `tests/unit/test_towing_dynamic_upgrade.py`
- Test: `tests/unit/test_betterment_exact_age.py`

- [x] **Step 1: Write failing tests for Towing Dynamic Upgrade and Betterment Exact Math**
  - `test_towing_dynamic_upgrade.py`:
    - Given Etiqa + OTO 360: Top-Right Towing card title becomes `"UNLIMITED TOWING ASSISTANCE"`, limit becomes `"Unlimited Mileage"`, description notes `"Upgraded via OTO 360"`. Slot 01 in bottom matrix contains `[✔] OTO 360`. No duplicate Towing card in bottom matrix.
    - Given Takaful + Motor PA Plus Plan 4: Top-Right Towing card updates to `"UNLIMITED TOWING ASSISTANCE"`.
    - Given Takaful + Motor PA Plus Plan 3: Top-Right Towing card updates to `"EXTENDED TOWING ASSISTANCE (300 km)"`.
    - Given No Rider: Top-Right Towing card stays `"EMERGENCY TOWING ASSISTANCE (RM 200.00)"`.
  - `test_betterment_exact_age.py`:
    - Registration: `2016-06-15`, Inception: `2026-06-14` (9 years 11 months 29 days) $\rightarrow$ exactly **9 completed years (35% scale)**, eligible for Endorsement 113.

- [x] **Step 2: Implement Towing Dynamic In-Place Upgrade in `unified_addon_engine.py`**
  - Read `malaysian_motor_towing_reference.md` rules into a structured mapping table.
  - In `extract_free_coverage_items()`, if an upgrade rider (Plan 4, OTO 360, N4) is active, upgrade the `title`, `value`, and `description` of the Emergency Towing card in-place.
  - In `build_unified_matrix_cards()`, ensure the generic unselected `Unlimited Towing` card is suppressed from the bottom matrix when the top perk has already been upgraded, preventing customer billing confusion.

- [x] **Step 3: Implement Actuarial Calendar-Day Betterment in `betterment_engine.py`**
  Use `dateutil.relativedelta.relativedelta(inception_date, registration_date)`:
  - Compute `completed_years = delta.years`.
  - Assign PIAM tariff scale: `<5: 0%`, `5: 15%`, `6: 20%`, `7: 25%`, `8: 30%`, `9: 35%`, `10+: 40%`.
  - Format description: `"Waives betterment deduction on replacement parts for vehicles aged {completed_years} years."`

- [ ] **Step 4: Standardize Design 1 and Design 2 in Template Registry**
  - Name Design 1 as `Bilingual Agency Motor (Design 1)`.
  - Name Design 2 as `Modern 4-Column Grid (Design 2)`.
  - In Design 1, unify the 3 database rows into 1 template with runtime `extras_mode` toggle: `[ Itemized | Lump Sum | None ]`.

- [ ] **Step 5: Run full test suite and verify 100% pass**
  Run `pytest tests/unit/test_towing_dynamic_upgrade.py tests/unit/test_betterment_exact_age.py`.
