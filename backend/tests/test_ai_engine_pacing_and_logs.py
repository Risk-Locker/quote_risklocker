from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.extraction.pacer_sentinel import PacerSentinel
from app.services.gemini_account_service import GeminiAccountManager, get_fleet_timeline_data
from app.services.marketing_comparison_service import _build_pipeline_traces


def test_pacer_sentinel_serializes_concurrent_dispatches_and_scales_for_batch():
    pacer = PacerSentinel(slot_count=4)
    sleeps: list[float] = []
    now_ref = [1000.0]

    def fake_time() -> float:
        return now_ref[0]

    def fake_sleep(dt: float) -> None:
        sleeps.append(dt)

    # First interactive call starts immediately (0s delay), then 2.0s spacing
    _, d1 = pacer.acquire(staged_count=2, sleep_fn=fake_sleep, time_fn=fake_time)
    _, d2 = pacer.acquire(staged_count=2, sleep_fn=fake_sleep, time_fn=fake_time)
    assert d1 == 0.0
    assert d2 == 2.0

    # Batch > 20 staged files spaces at 3.5s per dispatch
    _, d3 = pacer.acquire(staged_count=100, sleep_fn=fake_sleep, time_fn=fake_time)
    assert d3 == 4.0  # 2.0 + 2.0 (previous reservation ended at +2.0, breathing_delay for batch is 3.5)
    _, d4 = pacer.acquire(staged_count=100, sleep_fn=fake_sleep, time_fn=fake_time)
    assert d4 == 7.5

    # Rate limit feedback pushes dispatch window out by 6s
    pacer.record_outcome(latency_sec=8.2, is_rate_limited=True, now=1000.0)
    _, d5 = pacer.acquire(staged_count=100, sleep_fn=fake_sleep, time_fn=fake_time)
    assert d5 >= 11.0


def test_probe_model_tests_active_accounts_and_returns_results(monkeypatch):
    mgr = GeminiAccountManager(keys=["AIzaSyTestKeyOne1234567890", "AIzaSyTestKeyTwo1234567890"])

    def fake_probe(key: str, model: str | None = None):
        if "One" in key:
            return {"ok": False, "status_code": 429, "error": "Quota exceeded for gemini-3.1-flash-lite", "latency_ms": 210, "model": model}
        return {"ok": True, "status_code": 200, "error": None, "latency_ms": 180, "model": model}

    monkeypatch.setattr(GeminiAccountManager, "probe_single_key", staticmethod(fake_probe))

    res = mgr.probe_model(model="gemini-3.1-flash-lite")
    assert res["model"] == "gemini-3.1-flash-lite"
    assert res["tested_count"] == 2
    assert res["overall_ok"] is True
    assert res["all_ok"] is False
    assert res["results"][0]["status_code"] == 429
    assert "Quota exceeded" in res["results"][0]["error"]
    assert res["results"][1]["ok"] is True


def test_get_fleet_timeline_data_labels_grounding_and_probes_and_aggregates_all_60m():
    now = datetime.now(timezone.utc)
    # Create 120 logs within the last 40 minutes (> 100 row limit of raw_logs)
    logs = []
    for i in range(120):
        logs.append(
            SimpleNamespace(
                id=f"log-{i}",
                created_at=now - timedelta(minutes=i % 40),
                account_id="env_0",
                api_key_masked="AIza••••1234",
                model="gemini-3.1-flash-lite" if i % 2 == 0 else "gemini-3.5-flash-lite",
                endpoint_slot=(
                    "grounding::env_0::gemini-3.1-flash-lite"
                    if i == 0
                    else "probe::env_0::gemini-3.5-flash-lite"
                    if i == 1
                    else "spillover::gemini-3.5-flash-lite"
                    if i == 2
                    else "env_0::gemini-3.1-flash-lite"
                ),
                status_code=429 if i % 4 == 0 else 200,
                is_success=(i % 4 != 0),
                prompt_tokens=100 if i % 4 != 0 else 0,
                candidate_tokens=50 if i % 4 != 0 else 0,
                total_tokens=150 if i % 4 != 0 else 0,
                latency_ms=250,
                error_message="429 Resource Exhausted" if i % 4 == 0 else None,
                local_date="2026-11-19",
            )
        )

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return SimpleNamespace(all=lambda: self._rows)

        def fetchall(self):
            return self._rows

    class _FakeDB:
        def __init__(self):
            self.calls = 0

        def execute(self, stmt):
            self.calls += 1
            if self.calls == 1:
                return _FakeResult(logs[:100])
            if self.calls == 2:
                return _FakeResult(logs)
            return _FakeResult([("2026-11-19", 120, 13500, 30)])

    out = get_fleet_timeline_data(_FakeDB())
    assert out["timeline"][0]["purpose"] == "Vehicle Grounding Search"
    assert out["timeline"][1]["purpose"] == "Model Health Probe"
    assert out["timeline"][2]["purpose"] == "Quotation Extraction (Fallback)"
    assert out["minute_summary"]["calls"] == 120
    assert out["minute_summary"]["errors"] == 30


def test_build_pipeline_traces_uses_recorded_and_reconstructed_steps():
    now = datetime.now(timezone.utc)
    rec_with_trace = SimpleNamespace(
        method_summary=["PyMuPDF Native Text", "Gemini AI Extraction (gemini-3.5-flash-lite)"],
        warnings=[],
        reading_quality="ready",
        company_resolution={
            "pipeline_trace": [
                {"ts": now.isoformat(), "progress": 0, "stage": "staged", "message": "Staged test.pdf"},
                {"ts": now.isoformat(), "progress": 55, "stage": "gemini_ai_call", "message": "Gemini succeeded"},
                {"ts": now.isoformat(), "progress": 100, "stage": "completed", "message": "Done"},
            ]
        },
    )
    sess = SimpleNamespace(
        id="sess-1",
        created_at=now,
        uploaded_file=SimpleNamespace(original_filename="quote.pdf", extraction_record=rec_with_trace),
    )

    class _FakeDB:
        def scalars(self, stmt):
            return SimpleNamespace(all=lambda: [])

    traces = _build_pipeline_traces(
        _FakeDB(),
        [{"session_id": "sess-1", "uploaded_file_id": None, "company_name": "Etiqa", "version": 1, "total_payable": 1000.0}],
        {"sess-1": sess},
    )
    assert len(traces) == 1
    assert traces[0]["steps"][0]["stage"] == "staged"
    assert traces[0]["steps"][1]["stage"] == "gemini_ai_call"
    assert traces[0]["steps"][-1]["stage"] == "comparison_rendered"
