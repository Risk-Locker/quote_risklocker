import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.services.gemini_account_service import (
    get_pt_cycle_date_for_time,
    get_current_pt_cycle_date,
    GeminiAccountManager,
    GeminiAccount,
)
from app.extraction.pacer_sentinel import PacerSentinel

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

def test_gemini_account_manager_resets_on_pt_cycle_advance(monkeypatch):
    manager = GeminiAccountManager(keys=["AIzaFakeKey123"])
    acc = manager._accounts[0]
    acc.request_count_today = 450
    acc.tokens_today = 150_000
    acc.status = "exhausted_rpd"

    # Set last reset date to yesterday's cycle
    manager._last_reset_date = "2026-11-15"

    # Mock current cycle date to "2026-11-16"
    import app.services.gemini_account_service as gas
    monkeypatch.setattr(gas, "get_current_pt_cycle_date", lambda: "2026-11-16")

    manager._check_daily_reset()

    assert acc.request_count_today == 0
    assert acc.tokens_today == 0
    assert acc.status == "ready"
    assert manager._last_reset_date == "2026-11-16"

def test_pacer_sentinel_resets_daily_counts():
    sentinel = PacerSentinel(slot_count=2)
    now = 1000.0
    sentinel.record_dispatch(slot_idx=0, now=now, tokens=15000)
    assert sentinel._slot_daily_counts[0] == 1

    sentinel.reset_daily_counters()
    assert sentinel._slot_daily_counts[0] == 0
