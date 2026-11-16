# Architecture & Implementation Plan: Independent Multi-Key Fleet Controls

> **Goal:** Transform the Gemini AI Fleet UI and backend state from a misleading "single-active-key" radio switcher into true **independent multi-key status (`Active`, `Active`)** with individual On/Off toggles, dynamic aggregate capacity calculation, and total-fleet kill-switch capability.

---

## 1. Executive Summary & Root Cause

### The Problem
* When the 4-endpoint parallel dispatching engine was built, all keys in the pool were wired to dispatch in parallel concurrently (52 RPM, 1,920 RPD across all keys and models).
* However, the UI retained a legacy **"Switch Active Account"** section where only one key showed `Active` and the other showed `[Select]`.
* This caused a fundamental conceptual contradiction: **the backend was running both keys concurrently in parallel, but the UI made it look like a mutually exclusive single-key radio switch**.
* Furthermore, users could not easily turn off individual keys or turn off both keys together directly from the popover.

### The Target Mental Model
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Old Misleading UI (Radio Switcher):                                         │
│   Key 1 (.env Primary)  -> [Active]                                         │
│   Key 2 (Manual Key)   -> [Select] (Makes user think Key 2 is NOT working!) │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ New Correct Reality (Independent Parallel Controls):                        │
│   Key 1 (.env Primary)  -> [Active]      [Turn Off]   [Test]                │
│   Key 2 (Manual Key)   -> [Active]      [Turn Off]   [Test]                │
│                                                                             │
│ Both keys Active:  Fleet Capacity = 4 Endpoints · 52 RPM · 1,920 RPD        │
│ 1 key Active:      Fleet Capacity = 2 Endpoints · 26 RPM · 960 RPD          │
│ Both keys Off:     Fleet Capacity = 0 Endpoints · Offline · Safe Fallback   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architectural Design & System Invariants

### 2.1 Backend Domain Invariants (`backend/app/services/gemini_account_service.py`)
1. **Independent Account Status:**
   - Every unpaused key with valid status is marked `is_active: True` (not `idx == self._active_index`).
   - Status badge:
     - If `not acc.is_paused`: `status_label = "Active"`, `status_color = "green"`.
     - If `acc.is_paused`: `status_label = "Off · Paused"`, `status_color = "gray"`.
2. **Dynamic Aggregate Quota Scaling:**
   - Active capacity scales dynamically based on unpaused keys:
     - `active_keys = [a for a in self._accounts if not a.is_paused]`
     - `active_endpoints = len(active_keys) * len(PARALLEL_MODELS)`
     - `pool_rpd_limit = active_endpoints * self._max_rpd_per_key`
     - `pool_rpm_limit = active_endpoints * self._max_rpm_per_key`
   - Fleet aggregate badge:
     - All keys active: `"4/4 Endpoints Online · All Keys Active"` (Emerald)
     - Partial keys active: `f"{active_endpoints}/4 Endpoints Online ({len(active_keys)} Active)"` (Sky)
     - All keys paused / off: `"Fleet Offline · All Keys Paused"` (Gray/Amber)
3. **Graceful Fail-Safe When All Keys Are Off:**
   - If a user pauses/turns off all keys:
     - `acquire_parallel_slot()` returns `None`.
     - `gemini_extractor.py` gracefully skips Gemini AI and falls back cleanly to native OCR/regex extraction with zero crashes or 500 errors.
4. **Endpoint Level Health Parity:**
   - `get_fleet_endpoints()` checks parent account state:
     - If parent key `acc.is_paused`: endpoint displays `status_label: "Off · Paused"`, `is_ready: False`, `status_color: "gray"`.

### 2.2 API Layer (`backend/app/api/routers/system.py`)
- Leverage existing `POST /settings/gemini/keys/{key_id}/toggle-pause`:
  - Body: `{"paused": true}` (Turn Off) or `{"paused": false}` (Turn On).
  - Persists across database (`AppSetting("gemini_paused_keys")`) and memory (`GeminiKeyPool`).
  - Returns updated `gemini` quota stats so UI immediately re-renders with fresh limits.
- Update `POST /settings/gemini/probe`:
  - Support probing an explicit `key_id` or `account_index` so clicking `[Test]` next to Key 1 or Key 2 tests that exact key.

---

## 3. UI Component Specifications

### 3.1 Header Popover (`frontend/src/components/gemini-header-meter.tsx`)

#### A. Header & Aggregate Limits Card
* **Header Title**: `Gemini AI Parallel Fleet`
* **Status Badge**:
  * 2 Keys Active: `● 4/4 Endpoints Active` (Emerald)
  * 1 Key Active: `◐ 2/4 Endpoints Active` (Sky)
  * 0 Keys Active: `○ Fleet Off (All Keys Paused)` (Gray)
* **Progress Bars**: Reflect current consumption against **active** quota limits.

#### B. 4 Model Endpoints Grid
* Displays the 4 endpoints (`Key 1::3.1-flash-lite`, `Key 1::3.5-flash-lite`, `Key 2::3.1-flash-lite`, `Key 2::3.5-flash-lite`).
* If a key is paused, its 2 corresponding model slots display `Off · Paused` with a gray dot.

#### C. Fleet Keys & Independent Controls Section (Replaces Old Switcher)
```
┌────────────────────────────────────────────────────────────────────────┐
│ FLEET KEYS (INDEPENDENT CONTROLS)                                      │
│                                                                        │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ ● Key 1 (.env Primary)                          [ Active ]         │ │
│ │   0/480 RPD · AIzaSy...                                            │ │
│ │   [ Turn Off ]  [ Test Key ]                                       │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ ● Key 2 (Manual Key)                            [ Active ]         │ │
│ │   0/480 RPD · AIzaSy...                                            │ │
│ │   [ Turn Off ]  [ Test Key ]                                       │ │
│ └────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```
* **Status**: Both show `[ Active ]` in emerald green when enabled.
* **Turn Off / Turn On Button**:
  * When Active: Clicking `Turn Off` pauses the key, immediately updating fleet capacity from 4 -> 2 endpoints.
  * When Paused: Clicking `Turn On` resumes the key, restoring 2 -> 4 endpoints.
* **Test Key Button**: Probes that specific key live against Google and shows latency/verification inline.

### 3.2 AI Engine Settings Page (`frontend/src/app/settings/ai-engine/page.tsx`)
* Remove the `Make Active` / radio button column entirely.
* Clean tabular structure:
  * **Account**: Name + Source (`.env Primary` / `Manual`)
  * **Masked Key**: `AIzaSy...`
  * **Status**: `Active` (Emerald) vs `Off · Paused` (Amber)
  * **Usage**: Live RPD / RPM progress meters
  * **Actions**:
    * `[ Turn Off ]` / `[ Turn On ]` independent switch
    * `[ Test ]` probe button
    * `[ Delete ]` (manual keys only)

---

## 4. 10-Point Edge Case & Failure-Mode Analysis

| Dimension | Edge Case | Mitigation |
| :--- | :--- | :--- |
| **1. Empty / Zero Keys** | User pauses all keys or deletes manual key leaving 0 keys | Fleet status displays `Fleet Offline · All Keys Paused`. Total capacity drops to 0. PDF extraction falls back cleanly to native OCR with zero 500 errors. |
| **2. Boundary Quotas** | 1 key active (2 endpoints) vs 2 keys active (4 endpoints) | Limits dynamically update in both UI and backend rate limiter (26 RPM / 960 RPD vs 52 RPM / 1,920 RPD). |
| **3. Concurrency** | User clicks "Turn Off" while parallel extraction is running | `_lock` protects account pool. Currently in-flight HTTP request finishes; subsequent requests skip paused key immediately. |
| **4. Persistence** | Server restarts after user turns off a key | `AppSetting("gemini_paused_keys")` stores paused key IDs in PostgreSQL. State persists across server restarts. |
| **5. Partial Failure** | Key 1 valid, Key 2 revoked/invalid by Google | Key 2 displays `Invalid Key` or `Access Denied` without affecting Key 1's slots. Key 1 continues processing parallel traffic. |
| **6. Double Click** | User rapidly clicks Turn Off / Turn On | Local loading state disables action buttons until API response returns. |
| **7. Probing Isolation** | Probing Key 2 when Key 1 is paused | Probing directly tests Key 2 without requiring Key 1 to be active. |
| **8. Model Parity** | `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite` endpoints | Model tiers remain locked strictly to verified models (Rule 05). Zero calls to deprecated models. |
| **9. Zoom & Responsiveness** | Popover viewed at 80%, 100%, 120% zoom | Bounded dimensions (`w-[390px]`, `max-h-[170px]` scrollable list) ensure zero overflow or layout clipping. |
| **10. RBAC Integrity** | Non-admin attempts to pause keys | `require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.DEV)` rejects unauthorized role with 403 Forbidden. |

---

## 5. Serialized Implementation Milestones

### Milestone 1: Backend Domain & Quota Service Refinement
- Update `backend/app/services/gemini_account_service.py`:
  - Update `get_quota_stats()` to mark all unpaused keys as `is_active: True`.
  - Calculate dynamic aggregate limits based on unpaused keys (`active_endpoints`, `pool_rpd_limit`, `pool_rpm_limit`).
  - Update `get_fleet_endpoints()` to reflect parent account's paused state on individual model slots.
- Verify with `pytest tests/test_gemini_account_manager.py`.

### Milestone 2: Header Popover Modernization (`gemini-header-meter.tsx`)
- Replace "Switch Active Account" radio section with "Fleet Keys (Independent Controls)".
- Render each key with independent `Active` / `Off · Paused` badge.
- Add `[Turn Off]` / `[Turn On]` toggle and per-key `[Test]` action.
- Update fleet status badge and model endpoint grid to reflect paused keys dynamically.

### Milestone 3: AI Engine Settings Page Alignment (`page.tsx`)
- Remove radio `Make Active` column from accounts table.
- Standardize status badges to `Active` (green) and `Off · Paused` (amber).
- Connect `Turn Off` / `Turn On` toggle and per-key test triggers.

### Milestone 4: Authentic Verification & Forensics
- Run `pytest` on backend tests.
- Run `npx tsc --noEmit` in `frontend/`.
- Verify live behavior across active/paused permutations.
