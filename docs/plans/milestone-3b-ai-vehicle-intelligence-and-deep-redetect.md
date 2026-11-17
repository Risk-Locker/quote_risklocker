# Milestone 3b: AI Vehicle Intelligence, Unit Integrity (`KG`/`W`/`CC`), Commercial Fee Defaults, Real `★ Detected` Badge & 1-Click Deep `Re-detect`

> **Status:** Completed & Verified (`v30.4`)  
> **Skills Required:** `malaysian-motor-insurance`, `system-design-and-architecture`, `edge-case-and-scenario-matrix`, `test-driven-development`, `python-testing`

## 1. Objective & Empirical Root Causes Resolved
Eliminate systematic extraction failures on new uploads AND unlock 1-click self-healing via `Re-detect` across existing quotations without manual DB edits:
1. Empower `GEMINI_EXTRACTION_SCHEMA` in `backend/app/extraction/gemini_extractor.py` to output `vehicle_type`, `vehicle_class`, `powertrain` (`ICE`/`EV`/`Hybrid`), `capacity_unit` (`CC`/`kW`/`W`/`KG`/`TON`), and clean vehicle model naming directly in Call 1 (eliminating the extra un-paced 2nd Gemini HTTP call in `vehicle_simplifier_service.py` to double RPM/RPD quota headroom).
2. Stop `draft_mapper.py`, `entity_classifier.py`, `referee.py`, `candidate_finder.py`, and `road_tax_engine.py` from destroying valid units:
   - Preserve `KG`/`TON` on Commercial Heavy/Goods Vehicles (`12000 KG` must never become `12000 CC`).
   - Stop coercing commercial tonnage `<= 35` or `Lorry` into `EVSaloonCar` (`draft_mapper.py:376`, `road_tax_engine.py:439-448`).
   - Classify modern EVs (`BYD DOLPHIN 70000 W`) to `kW` + EV category instead of `70000 CC` (`RM 303,630.00`).
   - Reject unbounded ID numbers (`411823 CC`, `10340321623029704 CC`) and strip PDF filler (`OTHER COMMERCIAL MAKE`, `ALL MODELS (COMMERCIAL)`) cleanly.
3. Auto-disable Road Tax & Runner Fee by default (`include_road_tax = False`, `include_runner_fee = False`, `RM 0.00`) for Commercial Heavy/Goods/Permit Vehicles across `extraction_worker.py`, `draft_mapper.py`, `insurance_tenure_service.py`, and `marketing_comparison_service.py` (skipping `default_runner_fee` injection).
4. Fix `render_context.py:545` `is_detected` so `"published_base"` DB catalog defaults never falsely show `★ Detected` or force `is_purchased_extra = True`.
5. Implement `engine="deep"` in `session_rescan_service.py`, `ReviewHeaderCard.tsx`, `sessions/page.tsx`, and `comparison-matrix.tsx` / `comparison.py` (with `PacerSentinel` protection, commercial/private catalog re-pinning, unedited Box 1 re-seed, and structured change diff toast).

## 2. Verification Plan & Empirical Evidence
- `tests/unit/test_m3b_ai_vehicle_classification_and_rescan.py`: 9/9 passed covering `SANY 12000 KG` (`'A' PERMIT GOODS VEHICLE`), `HOHAN CONCRETE MIXER` `11 TON`, `ISUZU NKR55UEEH` `3000 CC`, `BYD DOLPHIN STANDARD 70000 W -> 70 kW`, `411823`/`10340321623029704` capacity rejection, `MERCEDES-BENZ S 400` / `G 350` trim preservation + Company Car enabled fees, real `★ Detected` provenance (`is_detected=False` for `published_base`), zero duplicate un-paced 2nd Gemini HTTP call, `engine="deep"` rollback safety, and FastAPI `/sessions/{id}/rescan`, `/sessions/{id}/extract-gemini`, and `/comparison/{id}/rescan` routes + RBAC denial (`404`).
- Full pytest regression suite: `1,180 passed, 3 skipped` (`tests/`).
- Frontend validation: `npx tsc --noEmit` (exit 0), `npm run lint` (exit 0), and `npm run build` (`47/47` static pages compiled cleanly).
- Knowledge base check: `commands/verify-brain.py` passed.
