---
trigger: model_decision
description: Live reality grounding, Gemini quota caps, and upstream SDK verification when touching AI extraction, models, or external packages.
---
# Rule 05: Live Reality Grounding & AI Quota Gate

1. **Verify Runtime Config First:**
   - Never hardcode or guess AI model IDs, SDK flags, or rate limits from training memory. Read `backend/app/core/config.py` and `frontend/package.json` first, and verify external docs via Context7 or `search_web` when upgrading packages.
2. **Google AI Studio Extraction Caps:**
   - Production PDF extraction pacing (`PacerSentinel`) enforces `13 RPM`, `200k TPM`, and `480 RPD` per slot on configured `gemini-3.1-flash-lite` / `gemini-3.5-flash-lite` endpoints, with accurate token weighing (never naive byte size heuristics).
3. **Model Attribution:**
   - Keep `model: inherit` in `.agents/agents/*.md` and use verified runtime model names when dispatching `swarm` workers.
