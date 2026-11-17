# Milestone 2: AI Fleet Google PT Quota Window & Batch Assigner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` and `systematic-debugging` to execute this plan cleanly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align Gemini API fleet management strictly with Google AI Studio's 24-hour calendar quota window (midnight Pacific Time = 4:00 PM MYT winter / 3:00 PM MYT summer), track project-wide RPD/RPM/TPM per cycle, and implement a smart batch task assigner that sizes batches to ~9â€“10 PDFs per model (capping <= 200k TPM) with a 70s stagger interval.

**Architecture:**
1. **PT Quota Cycle Window (`gemini_account_service.py`):**
   - Implements `get_current_pt_cycle_date() -> str` using `zoneinfo.ZoneInfo("America/Los_Angeles")`. When midnight strikes in California (4:00 PM MYT during PST / 3:00 PM MYT during PDT), the cycle date increments.
   - Updates `_check_daily_reset()` in `GeminiAccountManager` and `PacerSentinel` to reset `request_count_today` and `tokens_today` exactly when the PT cycle date advances.
   - Updates `GeminiApiCallLog` logging so `quota_cycle_date` stores this canonical Google AI Studio date string (e.g. `2026-11-16`).
2. **Project-Wide RPD Enforcement:**
   - Multi-account fleet aggregates RPD against the project pool ceiling (480 RPD safe ceiling / 500 hard cap).
3. **Batch Task Assigner & Staggering (`upload-workspace.tsx` & `token_preflight_service.py`):**
   - Staging assigns models evenly across active slots.
   - Batch size per model is capped at 9â€“10 PDFs per minute (~150kâ€“180k tokens), avoiding the 200k TPM limit.
   - If a batch exceeds the 1-minute capacity, a 70-second countdown stagger is enforced between chunks.

**Tech Stack:** Python 3.12, `zoneinfo`, FastAPI, SQLAlchemy, Next.js 15, TypeScript.

---

### Task 1: PT Cycle Calculation Unit Tests (Red)

**Files:**
- Create: `tests/unit/test_gemini_pt_cycle.py`

- [x] **Step 1: Write failing tests for PT cycle window calculation**

```python
import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.services.gemini_account_service import get_pt_cycle_date_for_time, get_current_pt_cycle_date

def test_pt_cycle_date_rollover_at_4pm_myt_in_winter():
    # November 16, 2026 at 1:00 PM MYT (05:00 UTC) -> 9:00 PM PT (Nov 15 in California)
    time_1pm_myt = datetime(2026, 11, 16, 13, 0, 0, tzinfo=ZoneInfo("Asia/Kuala_Lumpur"))
    cycle_1pm = get_pt_cycle_date_for_time(time_1pm_myt)
    assert cycle_1pm == "2026-11-15"

    # November 16, 2026 at 4:05 PM MYT (08:05 UTC) -> 12:05 AM PT (Nov 16 in California - NEW CYCLE!)
    time_405pm_myt = datetime(2026, 11, 16, 16, 5, 0, tzinfo=ZoneInfo("Asia/Kuala_Lumpur"))
    cycle_405pm = get_pt_cycle_date_for_time(time_405pm_myt)
    assert cycle_405pm == "2026-11-16"

def test_pt_cycle_date_rollover_at_3pm_myt_in_summer():
    # July 16, 2026 at 2:00 PM MYT (06:00 UTC) -> 11:00 PM PDT (July 15 in California)
    time_2pm_myt = datetime(2026, 7, 16, 14, 0, 0, tzinfo=ZoneInfo("Asia/Kuala_Lumpur"))
    cycle_2pm = get_pt_cycle_date_for_time(time_2pm_myt)
    assert cycle_2pm == "2026-07-15"

    # July 16, 2026 at 3:05 PM MYT (07:05 UTC) -> 12:05 AM PDT (July 16 in California - NEW CYCLE!)
    time_305pm_myt = datetime(2026, 7, 16, 15, 5, 0, tzinfo=ZoneInfo("Asia/Kuala_Lumpur"))
    cycle_305pm = get_pt_cycle_date_for_time(time_305pm_myt)
    assert cycle_305pm == "2026-07-16"
```

- [x] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest.exe tests/unit/test_gemini_pt_cycle.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_pt_cycle_date_for_time'`

---

### Task 2: Implement PT Cycle Logic in `gemini_account_service.py` & `pacer_sentinel.py`

**Files:**
- Modify: `backend/app/services/gemini_account_service.py:20-65`
- Modify: `backend/app/services/gemini_account_service.py:170-190`
- Modify: `backend/app/extraction/pacer_sentinel.py:100-115`

- [x] **Step 3: Implement `get_pt_cycle_date_for_time` and `get_current_pt_cycle_date`**

```python
PT_TZ = ZoneInfo("America/Los_Angeles")

def get_pt_cycle_date_for_time(dt: datetime) -> str:
    """Return the Google AI Studio quota cycle calendar date YYYY-MM-DD (based on Pacific Time)."""
    return dt.astimezone(PT_TZ).strftime("%Y-%m-%d")

def get_current_pt_cycle_date() -> str:
    """Return the current active Google AI Studio quota cycle date."""
    return datetime.now(PT_TZ).strftime("%Y-%m-%d")
```

- [x] **Step 4: Update `_check_daily_reset()`**

Update `_check_daily_reset()` in `GeminiAccountManager` to use `get_current_pt_cycle_date()`:
```python
    def _check_daily_reset(self) -> None:
        """Reset daily quotas and quarantines when passing 12:00 AM Pacific Time (4 PM MYT winter / 3 PM MYT summer)."""
        current_cycle = get_current_pt_cycle_date()
        if current_cycle != self._last_reset_date:
            self._last_reset_date = current_cycle
            for acc in self._accounts:
                acc.request_count_today = 0
                acc.tokens_today = 0
                if acc.status == "exhausted_rpd":
                    acc.status = "ready"
                    acc.status_label = "Ready"
                    acc.status_color = "green"
                acc.quarantine_until = None
            for slot in self._parallel_slots.values():
                slot["request_count_today"] = 0
            self._pool_cutoff_active = False
```

- [x] **Step 5: Run tests to verify they pass**

Run: `.\.venv\Scripts\pytest.exe tests/unit/test_gemini_pt_cycle.py -v`
Expected: PASS

---

### Task 3: Batch Task Assigner & Pacing Stagger in Upload Workspace

**Files:**
- Modify: `frontend/src/components/upload/upload-workspace.tsx:690-790`

- [x] **Step 6: Update batch sizing and 70-second stagger**

In `upload-workspace.tsx`:
1. Limit micro-chunk dispatch to 9â€“10 files per active model (e.g. 18â€“20 files across 2 models) per minute.
2. If remaining staged files exist and estimated tokens for the batch exceed 180k, display a countdown banner ("Waiting 70s for Google AI Studio TPM quota window to refresh...") before dispatching the next chunk.

- [x] **Step 7: Run frontend type check and verify**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS with 0 errors

- [x] **Step 8: Commit Milestone 2 changes**

```bash
git add backend/app/services/gemini_account_service.py backend/app/extraction/pacer_sentinel.py frontend/src/components/upload/upload-workspace.tsx tests/unit/test_gemini_pt_cycle.py
git commit -m "feat(fleet): implement Google PT midnight quota cycle and 70s batch stagger"
```

