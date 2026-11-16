# Milestone 3: AI Fleet Monitoring Dashboard (Calendar & Timeline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` and `systematic-debugging` to execute this plan cleanly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a visual, animated, and informative AI Fleet Monitoring Dashboard with calendar and timeline views in `/settings/ai-engine`, showing calls, timestamps, actors, purposes, token costs per minute and per request, and remaining time until the next 4:00 PM / 3:00 PM MYT Google quota reset.

**Architecture:**
1. **API Endpoint (`/settings/gemini/timeline` in `system.py`):**
   - Queries `GeminiApiCallLog` to return:
     - `current_cycle`: PT cycle date, start time, reset time in MYT, seconds remaining until reset.
     - `timeline`: Recent calls (timestamp, account_id, model, purpose, prompt_tokens, candidate_tokens, total_tokens, latency_ms, status_code).
     - `minute_buckets`: Tokens and calls per minute for the last 60 minutes.
     - `daily_history`: RPD, total tokens, peak RPM, peak TPM for past 30 days.
2. **Frontend Component (`GeminiTimelineCalendar.tsx`):**
   - Clean, lightweight SVG/Canvas animated timeline showing live calls and token intensity.
   - Cycle Countdown badge: e.g. `Cycle Resets in 2h 25m at 4:00 PM MYT`.
   - Granular call inspection table with filters by purpose and model.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, `@phosphor-icons/react`.

---

### Task 1: Timeline API Endpoint & Backend Aggregator

**Files:**
- Modify: `backend/app/services/gemini_account_service.py:1240-1350`
- Modify: `backend/app/api/routers/system.py:1060-1070`
- Test: tests/integration/test_gemini_timeline_api.py

- [ ] **Step 1: Write integration test for timeline API**

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_gemini_timeline_endpoint_returns_cycle_and_logs(client: TestClient, admin_token_headers):
    response = client.get("/api/v1/settings/gemini/timeline", headers=admin_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "current_cycle" in data
    assert "next_reset_myt" in data["current_cycle"]
    assert "timeline" in data
    assert "minute_buckets" in data
    assert "daily_history" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest.exe tests/integration/test_gemini_timeline_api.py -v`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: Implement `get_fleet_timeline_data()` and wire router**

In `gemini_account_service.py`, build `get_fleet_timeline_data(db)` querying `GeminiApiCallLog` and calculating next PT midnight in MYT. Add `@router.get("/settings/gemini/timeline")` in `system.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\pytest.exe tests/integration/test_gemini_timeline_api.py -v`
Expected: PASS

---

### Task 2: Frontend Timeline & Calendar Component

**Files:**
- Create: frontend/src/components/gemini-timeline-calendar.tsx
- Modify: `frontend/src/app/settings/ai-engine/page.tsx:30-100`

- [ ] **Step 5: Build `GeminiTimelineCalendar` component**
Render:
1. Cycle reset status card with countdown timer to 4:00 PM MYT.
2. Minute-level token cost graph (bars with animated pulse on new calls).
3. Searchable call ledger table showing exact timestamp, purpose, tokens, latency, and status.

- [ ] **Step 6: Integrate into `frontend/src/app/settings/ai-engine/page.tsx`**

- [ ] **Step 7: Verify TypeScript compilation**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS with 0 errors

- [ ] **Step 8: Commit Milestone 3 changes**

```bash
git add backend/app/services/gemini_account_service.py backend/app/api/routers/system.py frontend/src/components/gemini-timeline-calendar.tsx frontend/src/app/settings/ai-engine/page.tsx tests/integration/test_gemini_timeline_api.py
git commit -m "feat(monitoring): add AI fleet timeline, Google PT cycle countdown and calendar"
```
