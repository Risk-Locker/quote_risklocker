# Risklocker Quotation Converter — Implementation Prompts

Execute these prompts in order. Each prompt is a single, self-contained unit. Do not move on until the current unit is verified and working.

Before every prompt:
- Read `docs/START-HERE.md`.
- Read only the files directly needed for that unit.
- Keep changes minimal and focused.
- Do not add speculative business rules, hard-coded fees, hidden formulas, or AI guessing for extracted values.
- Use Supabase/Postgres for data and Supabase Storage for PDFs; never persist PDFs in the repo or server directories.
- Update `docs/generated/CODEBASE-MAP.md` when routes, schema, env vars, or major behavior changes.

Skills: only load a skill if the unit genuinely cannot be done without it. Most units need no skills.

---

## 1. ✅ Navigation cleanup — split the mixed admin area

**Goal:** Replace the messy `/admin` mashup with a clear Builder + Settings structure. Leave login/users/roles untouched.

**Scope:**
- Rename the sidebar section "Admin" to **Builder** and route `/admin/*` to `/builder/*`:
  - `/builder/companies`
  - `/builder/our-specials`
  - `/builder/templates`
  - `/builder/templates/[id]/builder`
- Add a **Settings** section with routes:
  - `/settings/system-checks`
  - `/settings/storage`
  - `/settings/extraction/field-aliases`
  - `/settings/extraction/vehicles`
  - `/settings/extraction/road-tax`
- Add a **Client Records** sidebar section at `/client-records`.
- Keep Upload (`/upload`) and History/Trash (`/history`, `/trash`) in the main nav.
- Split the current mixed `/admin/page.tsx` into the dedicated pages above. Each page shows only its own feature.
- Remove or update `AdminNav`; add `BuilderNav`, `SettingsNav`, and a link for Client Records.
- Do not change auth, login, or role behavior. All existing roles can still see everything.
- **Quick fix included in this unit:** Auto-select the first available template and package on the review page if none is selected, so Generate PDF does not fail with "Choose a Risklocker template".

**Verification:**
- `npm run build` passes.
- All `/admin/*` links redirect or are removed.
- Each Builder/Settings/Client Records page loads and shows only its own content.
- Generate PDF on the review page works without manually picking a template.
- `npm run code-map:check` is current.

---

## 2. ✅ Insurance Companies — dedicated Builder page

**Goal:** A clean page to manage insurance companies with 6 locked defaults.

**Scope:**
- Build `/builder/companies` page.
- Seed 6 default companies on startup: **QBE, AmGen, Liberty, STMB, Tune, Etiqa**.
- Defaults can be renamed or disabled, but not deleted.
- Users can add more companies. New companies can be deleted.
- Fields: name, category (default "Motor"), detection phrases, logo, active status.
- Backend: ensure `/admin/companies` endpoints also answer at `/builder/companies` or update routes.

**Verification:**
- Backend starts, 6 defaults exist in DB.
- UI lists companies, supports create/edit/disable.
- Deleting a default company is blocked.
- Tests pass.

---

## 3. ✅ Our Specials data model

**Goal:** Replace the old "Benefits" concept with Our Specials: categories + parent specials + variants.

**Scope:**
- Add DB tables:
  - `our_specials` (parent): id, label, category ("FOC" or "Add-on"), status.
  - `our_special_variants` (child): id, special_id, label, secondary_label, value_text, icon_asset_id, shape, bg_color, text_color, status.
- Backend CRUD endpoints under `/builder/our-specials`.
- Categories "FOC" and "Add-on" are visual/grouping only; no business logic depends on them.
- A variant is what gets placed on a template canvas.
- Migration must preserve existing `benefit_options` rows by moving them into the new model or leave them inactive.

**Verification:**
- Migrations run.
- API can create parent specials and variants.
- Tests pass.

---

## 4. ✅ Our Specials mini-builder

**Goal:** UI for admins to design each variant (icon + text + value + style).

**Scope:**
- Build `/builder/our-specials` page.
- Left side: list of parent specials grouped by FOC / Add-on.
- Right side: variants of the selected special, shown as cards like the reference images.
- Create/edit variant form:
  - Label (e.g., "Windscreen Coverage")
  - Secondary label / value (e.g., "Up to RM 500")
  - Icon asset picker (from existing template assets)
  - Shape, background color, text color
- Live preview of the variant card.

**Verification:**
- Can create a parent special and multiple variants.
- Variants render like the reference cards.
- Build passes.

---

## 5. ✅ Templates dashboard

**Goal:** Clean template management grouped by company.

**Scope:**
- Build `/builder/templates` page.
- Show templates grouped/filtered by insurance company.
- Seed 6 locked default templates on startup, one for each default company.
- Default templates are locked; they must be copied before editing.
- Actions:
  - "New template" → opens the builder with a fresh blank canvas.
  - "Edit" → opens the builder with the selected template.
  - "Copy" → creates an editable copy (can be in the list or inside the builder).
- Remove old mixed template creation from the admin page.

**Verification:**
- 6 default templates exist.
- Locked templates cannot be edited directly.
- Copying works and opens the builder.
- Build passes.

---

## 6. ✅ Template builder — drag Our Specials variants

**Goal:** The existing builder can receive Our Specials variants from a left panel.

**Scope:**
- In the builder, add a left panel showing Our Specials parents and their variants.
- Allow filtering/searching variants.
- Drag a variant onto the canvas; store it as a new element type `special` referencing `variant_id`.
- Render `special` elements using the variant's icon + labels + style.
- Fix the zoom/visual glitch where the canvas breaks when zoomed too far.

**Verification:**
- Can drag a variant into the canvas.
- It renders correctly at different zoom levels.
- Saved template reloads with the special in place.
- Build passes.

---

## 7. ✅ Remove packages/cards from template config and review

**Goal:** Replace the package/card system with Our Specials and Add-ons.

**Scope:**
- Remove `packages` and `cards` from `OutputTemplateConfig.fixed_fields` / `template_config.py`.
- Update `normalize_template_config` and the PDF renderer to no longer rely on packages/cards.
- Update the review page:
  - Remove template selector.
  - Remove package selector.
  - Show "Our Specials" (auto-selected from the template/company) and "Add-ons" (selectable) as simple cards.
- Update draft generation to use the selected company template and chosen specials/add-ons.

**Verification:**
- Old package/cards code is gone.
- Review page still lets staff check values and pick add-ons.
- Generated PDF uses Our Specials correctly.
- Tests pass.

---

## 8. ✅ Upload creates a session

**Goal:** Every upload becomes a reusable session like a ChatGPT chat.

**Scope:**
- Keep `/upload` as the entry point.
- After upload, create a session and redirect to `/sessions/[id]/review`.
- Add `/sessions` page listing all sessions by date, newest first.
- A session is tied to the uploaded file and draft. Reopening it shows the last state.
- Auto-detect insurance company from filename; if unsure, let the user pick from active companies.
- The review page is only for checking/editing extracted values and selecting add-ons.
- No template selection here; the company drives the default template.

**Verification:**
- Upload creates a session and redirects to review.
- Sessions list shows past sessions.
- Reopening a session restores the last extracted values.
- Company auto-detection works; manual override works.
- Build passes.

---

## 9. ✅ Client Records — CRM dashboard for extracted quotations

**Goal:** Save every confirmed quotation as a Client Record with all extracted values, timestamps, and a unique insurer number.

**Scope:**
- Add `client_records` table:
  - `insurer_no`: unique, editable, required.
  - `session_id` / `draft_id` link.
  - Extracted fields: customer_name, vehicle_no, insurance_company, coverage_type, cover_period, car_model, ncd, coverage_amount, insurance_premium, roadtax, runner_fee, total_premium, issued_date, valid_until, vehicle_year, capacity, engine_no, chassis_no, market_value, agreed_value, excess_amount, basic_premium, ncd_amount, service_tax, stamp_duty, gross_premium, optional_covers, notes, etc.
  - Timestamps: extracted_at, confirmed_at, generated_at.
  - `raw_values`: JSON backup of the full draft fields.
- Build `/client-records` interactive dashboard:
  - Table view with sortable columns.
  - Search by insurer_no, customer name, vehicle no, insurance company.
  - Filter by date range.
  - Export to CSV/Excel.
  - Click a row to view full details and edit insurer_no or notes.
- Create/update the record automatically when the user clicks **Proceed to preview** from the review page.
- Enforce unique `insurer_no`. Show error if duplicate.

**Verification:**
- Proceeding to preview creates a Client Record.
- Dashboard lists records, supports search/filter/export.
- Duplicate insurer_no is rejected.
- Build passes.

---

## 10. ✅ Generated preview — full editor + export

**Goal:** After review, show a preview that can be edited freely and exported as PDF or PNG.

**Scope:**
- Generate a preview from the reviewed draft + selected template.
- Show the preview in a builder-like editor (same canvas component) where the user can:
  - Move/delete elements
  - Edit text/values
  - Add/remove Our Specials variants
- Changes apply only to this session; they do not change the underlying template or Our Specials.
- Add "Save as new template" button that copies the current layout as a new named template.
- Add export buttons: **Download PDF** and **Download PNG**.

**Verification:**
- Preview renders from draft + template.
- Edits stay inside the session.
- Saving as new template creates a normal template in `/builder/templates`.
- PDF and PNG exports work.
- Build passes.

---

## 11. ✅ Extraction settings — field aliases

**Goal:** Manage extraction synonyms so OCR can match more variants.

**Scope:**
- Build `/settings/extraction/field-aliases` page.
- CRUD for field aliases: field name + list of accepted variants.
- Import/export CSV with two columns: `accepted_variant`, `canonical_field`.
- Use these aliases during extraction to map unknown labels to canonical fields.

**Verification:**
- Can create/edit aliases.
- Upload uses aliases to improve extraction.
- Import/export works.
- Tests pass.

---

## 12. ✅ Extraction settings — vehicle brands/models

**Goal:** Manage vehicle reference data with aliases.

**Scope:**
- Build `/settings/extraction/vehicles` page.
- CRUD for brands and models.
- Aliases: e.g., "beza" → "Perodua Bezza".
- Import/export CSV.
- During extraction, normalize extracted brand/model using active aliases.

**Verification:**
- Brand/model aliases work.
- Extraction normalizes "beza" to "Perodua Bezza".
- Import/export works.
- Tests pass.

---

## 13. ✅ Extraction settings — road-tax reference data

**Goal:** Manage road-tax rules by jurisdiction, vehicle class, and CC range.

**Scope:**
- Build `/settings/extraction/road-tax` page.
- DB table: jurisdiction, vehicle class, subclass, min_cc, max_cc, rate, formula, source, effective dates, active status.
- Support simple flat rates or formulas like `280 + 0.50 * (cc - 1800)`.
- During extraction, if exactly one active rule matches, fill road tax automatically and show the source.
- If no unique match, mark road tax for manual review.

**Verification:**
- Can add/edit road-tax rules.
- Extraction auto-fills road tax when one rule matches.
- No-match marks for review.
- Tests pass.

---

## 14. ✅ Trash/purge cleanup and dead code removal

**Goal:** Emptying trash actually deletes PDFs from Supabase; remove leftover Manager role references.

**Scope:**
- Fix `purge_expired_trash()` to call `storage.delete_pdf()` for source and generated PDFs before deleting DB rows.
- Remove or replace dead `Role.MANAGER.value` references in `review_service.py`.
- Add tests for trash purge and storage deletion.

**Verification:**
- Empty trash deletes both DB records and Supabase objects.
- No Manager references remain.
- Tests pass.

---

## 15. ✅ Final hardening — schemas, tests, docs

**Goal:** Solid API contracts, passing tests, and up-to-date docs.

**Scope:**
- Replace remaining raw `dict` request payloads with Pydantic schemas where it improves reliability.
- Add/update backend tests for all new endpoints and flows.
- Run `npm test` (backend + frontend build).
- Run `npm run code-map:check`; update if stale.
- Fix any broken links or outdated docs.

**Verification:**
- All backend tests pass.
- Frontend production build passes.
- Code map is current.

---

## 16. ⏳ Roles, auth polish, deployment, CI/CD, OAuth (LAST — only after everything above works)

**Goal:** Optional later improvements once the core product is solid.

**Scope (do not start until prompted):**
- Refine role-based UI if needed.
- Add brute-force login protection, security logs, active-user kick, login notifications.
- SMTP / email notifications.
- Deployment scripts (`deploy.sh`), CI/CD, OAuth.
- Browser tests from login through PDF generation.

**Verification:**
- Each item is tested separately.
- Core features from prompts 1–15 still pass all tests.
