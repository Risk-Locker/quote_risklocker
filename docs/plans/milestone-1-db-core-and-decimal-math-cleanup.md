# Milestone 1: Database Schema Parity, Pure Decimal Math & Sync Service Slicing

> **Serialized Milestone 1 of 3 (`Rule 06`)**
> **Net Change Budget:** ~-60 lines (refactoring & bugfixes)
> **Allowed to Change:**
> - `backend/app/models/tables.py`
> - `backend/app/services/tenure_identity_sync_service.py`
> - `backend/app/services/workspace_patch_service.py` (`_recompute_total` only)
> - `backend/app/services/marketing_comparison_service.py` (`save_comparison_entry` only)
> - `tests/unit/test_plan1_database_core_and_sync.py`
> **Forbidden to Change:**
> - `backend/app/rendering/render_context.py` (`adjusted_total_text` must stay intact for legacy Bilingual template tests)
> - Frontend `.tsx`/`.ts` files (scheduled for Milestone 2)

## 1. Non-Breaking Guarantees

1. **`TenureComparisonEntry` Schema Alignment (`tables.py`):**
   - Live PostgreSQL has `tenure_comparison_entries.version`, NOT `revision`.
   - Removing the unmigrated `revision` column mapping and adding `@property def revision(self) -> int: return self.version` + `@revision.setter` restores 100% live PostgreSQL query compatibility while keeping all `.revision` and `.version` callers working identically.
2. **Partial Unique Index Fix (`DraftBenefitSelection`):**
   - Adding `AND state = 'current'` to `uq_draft_benefit_selection_concept` (`WHERE concept_id IS NOT NULL AND superseded_by_id IS NULL AND state = 'current'`) allows `removed` and `available_addon` rows to coexist with a `current` row for the same concept (verified 0 conflicts on live PostgreSQL vs 4 conflicts without `state = 'current'`).
3. **Eliminate Add-On Double-Counting in `_recompute_total`:**
   - `_recompute_total` in `workspace_patch_service.py` computes `total = base_prem + eff_rt + eff_sf` using `Decimal`, matching `TenureComparisonEntry.total_payable` and Design 2's 3-line summary (`Insurance Premium + Roadtax & Runner Fee = TOTAL PAYABLE`).
4. **Clean Slicing of `tenure_identity_sync_service.py`:**
   - Replaces `_to_float` with `_to_decimal` (`ROUND_HALF_UP`).
   - Splits `sync_tenure_identity_transaction` (270 lines, depth 5) into 5 focused helpers ($\le 45$ lines each, depth $\le 3$).

## 2. Verification Gate for Milestone 1
- `.\.venv\Scripts\pytest.exe tests/unit/test_plan1_database_core_and_sync.py tests/test_workspace_service.py tests/test_marketing_comparison.py tests/test_extraction_regression.py tests/test_package_plans.py tests/test_render_context.py -q`
- Live PostgreSQL ORM query check on `TenureComparisonEntry` and `DraftBenefitSelection`.

