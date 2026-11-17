# Milestone 4c: Kurnia as a Separate Insurance Company

> **Status:** Ready to Execute (`v30.4`), part of `docs/plans/2026-11-17-combined-master-roadmap-edit-persistence-kurnia-3c-upload.md`
> **Skills:** `malaysian-motor-insurance`, `postgres-ledger-migrations`, `test-driven-development`
> **Model Profile:** `.agents/profiles/deep.md` (Gemini 4 Argon)

## 1. Objective

Register **Kurnia** as its own first-class `InsuranceCompany` row in PostgreSQL and decouple all frontend/backend alias resolvers from folding Kurnia into AmAssurance, with zero hardcoded underwriting branches added.

## 2. Hardened Design (Covering All Verified Kurnia Touchpoints)

1. **Idempotent Migration (`migrations/` (`079_seed_kurnia_company.sql`) & `init_db.py`):**
   - Insert `Kurnia` (`category = 'Motor'`, `is_active = TRUE`) into `insurance_companies` using `WHERE NOT EXISTS (SELECT 1 FROM insurance_companies WHERE LOWER(name) IN ('kurnia', 'kurnia insurans', 'kurnia insurans (malaysia) berhad'))`.
   - Also add `"Kurnia"` to the canonical seed list in `backend/app/db/init_db.py` / `company_setup_service.py` so hermetic SQLite tests and fresh environments include Kurnia automatically.
   - Do not seed hardcoded benefit profiles or towing conditions in SQL; those are managed via `/builder` data.
2. **Frontend Decoupling (`company-names.ts` & `benefit-utils.ts`):**
   - In `frontend/src/lib/company-names.ts:20,68`, map `KURNIA` -> `"Kurnia Insurans (Malaysia) Berhad"` and return `"Kurnia"` instead of folding `"KURNIA"` into `"AmAssurance"`.
   - In `frontend/src/lib/benefit-utils.ts:117`, separate `"kurnia"` from `"amgeneral"` so Kurnia resolves to its own group key `"KURNIA"`.
3. **Backend Company Resolution (`company_resolution.py`, `company_names.py`, `candidate_finder.py`):**
   - Verify `backend/app/extraction/company_resolution.py` and `backend/app/services/company_names.py:25-26,74-75` resolve `"Kurnia Insurans (Malaysia) Berhad"` and `"Kurnia"` to the `Kurnia` `InsuranceCompany` row (`company_id`), never `AmAssurance`.
   - Ensure `backend/app/extraction/candidate_finder.py:952`, `backend/app/rendering/template_renderer_design2.py:190`, `backend/app/services/client_dossier_service.py:327`, and `backend/app/services/generation_service.py:365` treat `Kurnia` as a distinct insurer identity while preserving Auto365 format recognition where shared by Liberty/AmGeneral/Kurnia PDFs.

## 3. Files

- **Allowed:** `migrations/` (`079_seed_kurnia_company.sql`) (new), `backend/app/db/init_db.py`, `backend/app/services/company_setup_service.py`, `backend/app/extraction/company_resolution.py`, `backend/app/services/company_names.py`, `frontend/src/lib/company-names.ts`, `frontend/src/lib/benefit-utils.ts`.
- **Forbidden:** Adding new hardcoded insurer `if/elif` branches in domain calculators.

## 4. Hermetic Tests

- Migration idempotency: running `079_seed_kurnia_company.sql` twice produces exactly one active `Kurnia` row in `insurance_companies`.
- Company resolution: PDF text with `"Kurnia Insurans (Malaysia) Berhad"` or `"KURNIA"` resolves to `Kurnia` (`company_id` of Kurnia), while `"AmGeneral Insurance Berhad"` / `"AmAssurance"` still resolves to `AmAssurance`.
- Frontend unit/type verification: `normalizeCompanyName("Kurnia Insurans")` returns `"Kurnia"`, and comparison cards display `"Kurnia"`.

