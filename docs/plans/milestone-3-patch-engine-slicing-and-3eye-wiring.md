# Milestone 3: Flatten `workspace_patch_service.py` & Wire 3-Eye Consensus Gate

> **Serialized Milestone 3 of 3 (`Rule 06`)**
> **Net Change Budget:** ~-40 lines
> **Allowed to Change:**
> - `backend/app/extraction/referee.py`
> - `backend/app/extraction/visual_referee.py`
> - `backend/app/services/marketing_comparison_service.py`
> - `backend/app/services/workspace_snapshot_service.py`
> - `backend/app/services/workspace_patch_service.py`
> - `tests/unit/test_plan2_workspace_and_3eye.py`

## 1. Non-Breaking Guarantees

1. **Wire 3-Eye Consensus Gate with Pure `Decimal` Math:**
   - Converts `audit_comparison_matrix_consensus` (`referee.py`) and `audit_pdf_visual_consensus` (`visual_referee.py`) from `float()` to `Decimal("0.01")`, respecting `include_road_tax` and `include_runner_fee` toggles.
   - Attaches `"consensus_audit"` additively to `get_marketing_comparison` and `build_workspace_snapshot` so everyexisting API consumer continues working without modification while exposing live 3-Eye consensus status.
2. **Flatten `apply_workspace_patch` (`workspace_patch_service.py`, Depth $16 \rightarrow \le 3$):**
   - Replaces the 14-branch `if/elif` pyramid with an `OPERATION_HANDLERS` dispatch table.
   - Extracts `_log_workspace_patch_activity` and `_sync_patch_to_tenure_and_comparison` into flat helper functions ($\le 60$ lines, depth $\le 3$).

## 2. Verification Gate for Milestone 3
- `.\.venv\Scripts\pytest.exe tests/unit/ tests/test_workspace_service.py tests/test_marketing_comparison.py -q`
- `cd frontend; npx tsc --noEmit`
- `.\.venv\Scripts\python.exe commands/verify-brain.py`
