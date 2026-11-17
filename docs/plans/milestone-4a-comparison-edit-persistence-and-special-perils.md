# Milestone 4a: Comparison Edit Persistence and Special Perils Truth

> **Status:** Ready to Execute (`v30.4`), part of `docs/plans/2026-11-17-combined-master-roadmap-edit-persistence-kurnia-3c-upload.md`
> **Skills:** `systematic-debugging`, `test-driven-development`, `python-testing`, `edge-case-and-scenario-matrix`, `malaysian-motor-insurance`, `shadcn`
> **Model Profile:** `.agents/profiles/deep.md` (Gemini 4 Argon)

## 1. Objective

Make every comparison card field editable inline and via modal, guarantee edits survive reload and rescan via field-level `manual_overrides`, eliminate mutating `GET` and version drift, and self-heal false Takaful `"Contribution"` Special Perils across both new and existing sessions.

## 2. Hardened Design (with Code-Audit Corrections)

1. **Pure Read-Only `GET` & Zero Version Drift:**
   - `GET /api/comparison/{tenure_id}` (`comparison.py:169`) and `GET /api/comparison/{tenure_id}/whatsapp-teaser` (`comparison.py:360`) execute zero `db.commit()` or `db.flush()`.
   - Remove the in-memory mutation `e.version = max(e.version or 1, company_counts[key])` at `marketing_comparison_service.py:687` so the version returned by `GET` always matches the persisted database `entry.version` (preventing false `409 Conflict` errors when multiple quotes exist for the same insurer).
2. **Write-Time Materialization (`materialize.py`):**
   - Create idempotent `materialize_comparison_entries(db, tenure_id)` in `backend/app/services/marketing_comparison/` (`materialize.py`).
   - Call it from extraction worker completion, quote upload, `save_comparison_entry`, `rescan_comparison`, and a new `POST /api/comparison/{tenure_id}/materialize` endpoint that the comparison UI triggers once on mount whenever any card in the response has `id: null` (cleanly materializing the 196 legacy unlinked sessions under a per-tenure transaction lock).
3. **Field-Level `manual_overrides` (`migrations/` (`078_comparison_entry_manual_overrides.sql`)):**
   - Add `manual_overrides JSONB NOT NULL DEFAULT '[]'` to `tenure_comparison_entries` (`backend/app/models/tables.py` + idempotent migration `078`).
   - Whenever a user edits fields via `POST /api/comparison/{tenure_id}/entry` or `PATCH /api/comparison/{tenure_id}/entries/{entry_id}`, append the edited field keys (`towing_limit`, `special_perils`, `llp_llop`, `excess`, `windscreen_sum_insured`, `notes`, `sum_insured`, `motor_premium`, `valuation_type`, `waiver_betterment`) to `entry.manual_overrides` and increment `entry.version`.
   - Support `clear_override_field: str | None` on `PATCH .../entries/{entry_id}` to remove a single field from `manual_overrides` and immediately re-populate its extracted value ("Revert to extracted").
   - Legacy rows with `is_manual = True` and `manual_overrides == []` remain locked across all fields until selectively reverted.
4. **Override-Respecting Sync & Self-Healing (`marketing_comparison_service.py`):**
   - The unlinked-session matcher (`:486-505`), towing guards (`:576-613`, `:1483-1490`), and rescan loop skip any field listed in `entry.manual_overrides` (and keep `towing_limit` & `towing_km` synchronized when `towing_limit` is overridden).
   - For any non-overridden `special_perils` field on existing rows, re-evaluate using `resolve_special_perils()` during materialization/projection so the 106 existing Takaful `"Contribution"` sessions automatically self-heal to `Not Included` without manual DB edits.
5. **Single Authoritative Special Perils Resolver (`special_perils.py`):**
   - Create `resolve_special_perils(benefit_lines, endorsements, text, fields)` in `backend/app/services/marketing_comparison/` (`special_perils.py`).
   - Wire it into:
     1. `backend/app/services/marketing_comparison/benefits_extractor.py` (replacing lines `389` and `883`),
     2. `backend/app/extraction/benefit_lines.py` (where Special Perils benefit lines are detected during extraction), and
     3. `backend/app/extraction/draft_mapper.py` (ensuring quotation workspace draft benefits and comparison cards share identical truth).
   - Rules: strict word boundaries (`\bribut\b`, `\bbanjir\b`, `\bflood\b`, `\bspecial\s+perils?\b`, `\bperil\s+khas\b`, Endorsement `57`/`57A`/`57B`), negative-phrase negation (`not covered`, `tidak termasuk`, `excluded`, `nil`, `rm 0`), and explicit exclusion of `"contribution"` / `"sumbangan"`. Output is canonical `"Included"` or `"Not Included"`.
6. **Towing & Benefit Formatting Fixes:**
   - In `benefits_extractor.py:1046-1049`, append `"KM"` only when `t_val` is purely numeric (never append `"KM"` to prose like `"Emergency towing ... repairer"`).
   - In `UnderwriterQuoteCard.tsx:431`, display `quote.towing_limit || quote.towing_km` (preferring `towing_limit` when overridden).
   - In `UnderwriterQuoteCard.tsx:512-513` and `frontend/src/lib/benefit-utils.ts`, colour Special Perils green only when `=== "Included"`, and preserve `%` units in `formatBenefitCoverage` instead of prefixing `"RM"`.
7. **Extended Inline Card Editing (`comparison.py:605` & `UnderwriterQuoteCard.tsx`):**
   - Extend `UpdateComparisonEntryPatch` (`backend/app/api/routers/comparison.py:605`) to accept optional `towing_limit`, `special_perils`, `llp_llop`, `excess`, `windscreen_sum_insured`, `notes`, `expected_version`, and `clear_override_field`, raising `409 Conflict` on stale `expected_version` and `422` on values exceeding column lengths (`String(50)` for `special_perils`/`llp_llop`, `String(100)` for `towing_limit`).
   - Add keyboard-accessible inline popover editors on `UnderwriterQuoteCard.tsx` for Towing, Special Perils (`Included` / `Not Included`), LLP/LLOP, Excess, Windscreen, and Notes, with a `"Manual"` badge and one-click `"Revert to extracted"` action per overridden field.
8. **RBAC & Security Hardening (`comparison.py`):**
   - Add `require_role(user, Role.SUPER_ADMIN, Role.ADMIN, Role.STAFF, Role.DEV)` and `entry.tenure_id == tenure_id` verification to `patch_comparison_entry` (`:612`) and the other 4 routes flagged by `security-audit.py` in `comparison.py` (`:691`, `:743`, `:827`, `:872`), plus the new `POST /{tenure_id}/materialize` route.

## 3. Files

- **Allowed:** `backend/app/services/marketing_comparison_service.py`, `backend/app/services/marketing_comparison/benefits_extractor.py`, `backend/app/services/marketing_comparison/` (`materialize.py`) (new), `backend/app/services/marketing_comparison/` (`special_perils.py`) (new), `backend/app/extraction/benefit_lines.py`, `backend/app/extraction/draft_mapper.py`, `backend/app/api/routers/comparison.py`, `backend/app/models/tables.py`, `migrations/` (`078_comparison_entry_manual_overrides.sql`) (new), `frontend/src/components/comparison/components/UnderwriterQuoteCard.tsx`, `frontend/src/components/comparison/components/` (`InlineComparisonFieldEditor.tsx`) (new), `frontend/src/components/comparison/comparison-matrix.tsx`, `frontend/src/components/comparison/types.ts`, `frontend/src/lib/benefit-utils.ts`.
- **Forbidden:** Design 2 PDF renderers, upload workspace, ledger pages.

## 4. Hermetic Tests (Write First)

- `resolve_special_perils`: Takaful quote with `"Basic Contribution RM 1,200.00"` and no perils returns `"Not Included"`; real flood/Endorsement 57 returns `"Included"`; `"Special Perils: Not Covered"` returns `"Not Included"`.
- Field-level override persistence: edit `towing_limit` to `"Unlimited"` and `special_perils` to `"Not Included"` via `PATCH .../entries/{id}`; subsequent `get_marketing_comparison` and `rescan_comparison` preserve both overrides while updating un-overridden fields; `clear_override_field="towing_limit"` restores extracted towing.
- Pure `GET` & version stability: assert zero `db.commit()`/`db.flush()` on `GET /{tenure_id}` and `GET /{tenure_id}/whatsapp-teaser`, and assert `entry.version` does not drift when two quotes share the same `company_name`.
- Idempotent `POST /{tenure_id}/materialize`: materializes unlinked sessions once without duplicates under concurrent/repeated calls, and self-heals non-overridden false `"Included"` Special Perils rows.
- RBAC & concurrency: unpermitted role returns `403`; mismatched `tenure_id` returns `404`; stale `expected_version` returns `409`.

