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

**Status guide:** Each prompt ends with a **Status** line. A prompt is only marked ✅ once it is fully implemented, tested, and finalized. If work is queued, incomplete, or has open issues, it stays ⚠️ Pending. Prompt 16 stays ⏳ until everything before it is done.

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

**Status:** ✅ Done — implemented, verified with `npm run build` and the test suite, and the new sidebar layout is live.

---

## 2. ✅ Insurance Companies — dedicated Builder page

**Goal:** A clean page to manage insurance companies with a count-guard (at least 1 must remain).

**Scope:**

- Build `/builder/companies` page with full CRUD (create, edit, disable/enable, delete).
- Seed 1 default company on startup: **QBE**.
- Any company can be deleted as long as at least 1 remains (count guard).
- Fields: name, category (default "Motor"), detection phrases, logo, active status.
- Backend: added `DELETE /admin/companies/{company_id}` route + `delete_company` service with count guard.

**Verification:**

- Frontend build passes.
- 12/12 companies API tests pass (HTTP routes + service unit tests).
- 65/65 full test suite passes, no regressions.
- Code map is current.

**Status:** ✅ Done — implemented, verified with `npm run build`, 12 new tests, and full regression suite.

---

## 3. ✅ Our Specials data model

**Goal:** Replace the old "Benefits" concept with Our Specials: categories + parent specials + variants.

**Scope:**

- Add DB tables:
  - `our_specials` (parent): id, label, category ("FOC" or "Add-on"), status.
  - `our_special_variants` (child): id, special_id, label, secondary_label, value_text, icon_asset_id, shape, bg_color, text_color, status.
- Backend CRUD endpoints under `/admin/our-specials` + `/admin/our-special-variants`.
- Categories "FOC" and "Add-on" are visual/grouping only; no business logic depends on them.
- A variant is what gets placed on a template canvas.
- Migration preserves existing `benefit_options` rows as inactive.
- Old `BenefitOption` model, service, routes, and seeding removed entirely.

**Verification:**

- Migration `013_our_specials.sql` created.
- API supports create/update/delete parent specials and variants.
- Old `/admin/benefits` routes removed; new `/admin/our-specials` routes added.
- Frontend `/builder/our-specials` page updated to new endpoints.
- 17/17 new tests pass (HTTP routes + service unit tests).
- 47/47 full test suite passes, no regressions.
- `npm run build` passes.
- Code map current.

**Status:** ✅ Done — implemented, verified with `npm run build`, 17 new tests, and full regression suite.

---

## 4. ✅ Our Specials mini-builder

**Goal:** UI for admins to design each variant (icon + text + value + style).

**Scope:**

- Build `/builder/our-specials` page with 3-column layout.
- Left: parent specials grouped by FOC / Add-on, selectable.
- Center: variant cards displayed with live styling (icon, shape, colors, border, shadow).
- Right: create/edit variant form with 10 fields.
- Icon asset picker from `/admin/template-assets` (41 icons).
- Live preview card updates in real-time.
- Added `migrations/014_variant_styling.sql` for `border_width`, `border_color`, `shadow` columns.

**Verification:**

- Can create parent specials and multiple variants per special.
- Variants render as styled cards with icon, colors, shape, border, shadow.
- Live preview updates as form fields change.
- `npm run build` passes.
- 29/29 backend tests pass.
- Code map current.

**Status:** ✅ Done — implemented and verified.

---

## 5. ✅ Templates dashboard

**Goal:** Clean template management grouped by company.

**Scope:**

- Build `/builder/templates` page with templates grouped by insurance company.
- "New template" button with company selector → creates blank template → opens builder.
- 1 locked default template (QBE) seeded; must be copied before editing.
- `serialize_template` now returns `insurance_company_name`.
- Copy → opens builder with editable copy.
- Edit → opens builder for unlocked templates.

**Verification:**

- Templates grouped by company name (fetched via `serialize_template(db)`).
- "New template" creates blank template and opens builder.
- Locked templates show Copy button; unlocked show Edit.
- `npm run build` passes; 32/32 tests pass; code map current.

**Status:** ✅ Done — implemented and verified. Templates grouped by company, 1 locked default seeded, "New template" opens builder, Copy/Edit actions work. Build + 32 tests pass, code map current.

---

## 6. ✅ Template builder — drag Our Specials variants

**Goal:** The existing builder can receive Our Specials variants from a left panel.

**Scope:**

- Added "Our Specials" panel to builder left sidebar with search/filter.
- Click a variant → places on canvas as a new `special` element type.
- HTML5 drag from sidebar → drops at cursor position (zoom-corrected).
- Renders `special` elements using the variant's icon, labels, shape, colors, border, shadow.
- Variant styling is snapshotted onto the element at placement time.
- Properties panel shows variant info for selected special elements.
- Fixed zoom glitch — replaced marginBottom hack with minHeight container.

**Verification:**

- Can click or drag a variant into the canvas. It renders with correct styling.
- Works at all zoom levels (0.45x–1.10x).
- Saved template reloads with the special element intact.
- `npm run build` passes; 29/29 tests pass; code map current.

**Status:** ✅ Done — implemented and verified.

---

## 7. ✅ Remove packages/cards from template config and review

**Goal:** Replace the package/card system with Our Specials and Add-ons.

**Scope:**

- Removed `CARD_CATALOG`, `DEFAULT_PACKAGES`, `card_title`, `card_from_label`, `_normalize_package`, `selected_package_config`, `cards_for_ids` from `template_config.py`.
- Removed `packages`/`cards` keys from `default_template_config` and `normalize_template_config`.
- Simplified `review_schema_for` to return only groups/summary/variables (no package data).
- Removed `selected_package` param from `render_quotation_html`; simplified `_benefit_section` to empty placeholder.
- Removed "Choose a package" gate from `pdf_service.py`.
- Removed `selected_package`, `benefits_selected`, `add_ons_selected` from `review_service.py` and routes.
- Cleaned up frontend labels and extraction fields.

**Verification:**

- Old package/cards code removed (~190 lines).
- `npm run build` passes.
- 89/89 tests pass (no regressions).
- Code map current.

**Status:** ✅ Done — implemented and verified.

---

## 8. ✅ Upload creates a session

**Goal:** Every upload becomes a reusable session like a ChatGPT chat.

**Scope:**

- Created `sessions` DB table (migration 015) linking uploaded_file → draft with detected_company.
- New `/sessions` page listing all sessions grouped by date, newest first.
- New `/sessions/[id]/review` page — loads session, auto-matches template by company, renders the review workflow.
- After single-file upload → redirects to `/sessions/{session_id}/review`.
- Template auto-matched by detected insurance company (exact or partial). No manual template selector.
- Review page updated: removed template dropdown, shows read-only template name, auto-matches by company.

**Verification:**

- Upload creates a session and redirects to `/sessions/{id}/review`.
- `/sessions` page lists past sessions with filename, company, status, date.
- Template auto-selected by company name match with fallback to first template.
- `npm run build` passes; 89/89 tests pass; code map current.

**Status:** ✅ Done — implemented and verified.

---

## 9. ✅ Client Records — CRM dashboard for extracted quotations

**Goal:** Save every confirmed quotation as a Client Record with all extracted values, timestamps, and a unique insurer number.

**Scope:**

- Created `client_records` table (migration 016) with 30+ extracted field columns, `raw_values` JSONB backup, timestamps.
- Auto-generated `insurer_no` format: `{COMPANY}_{VEHICLE_NO}` with duplicate sequence fallback.
- Key matching fields indexed: `insurance_company`, `vehicle_no`, `insurer_no` for future cross-system integration.
- Full CRUD dashboard at `/client-records` with search, sort (5 columns), CSV export.
- Inline edit for insurer_no; expandable detail panel with all fields + editable notes.
- Auto-creates/updates record on every PDF generation via `pdf_service.py`.

**Verification:**

- PDF generation creates/updates a client record automatically.
- Dashboard lists records with search across insurer_no, customer, vehicle, company.
- Sortable by insurer_no, customer, vehicle, company, date.
- CSV export works.
- Duplicate insurer_no is rejected (409).
- `npm run build` passes; 89/89 tests pass; code map current.

**Status:** ✅ Done — implemented and verified.

---

## 10. ✅ Generated preview — full editor + export

**Goal:** After review, show a preview that can be edited freely and exported as PDF or PNG.

**Scope:**

- New `/sessions/[id]/preview` page with scaled A4 canvas editor.
- Canvas loads template elements + draft field values (variable substitution).
- Drag to reposition elements, click to select, Delete key to remove.
- Add Our Specials variants from left sidebar (click to place).
- "Save as Template" modal → creates new template with current canvas layout.
- Download PDF → generates via existing pipeline.
- Download PNG → new `POST /drafts/{id}/preview-png` endpoint renders via Playwright screenshot.
- "Preview" button added to session review page.
- All edits are session-local React state — no DB writes until "Save as Template".

**Verification:**

- Preview renders from draft fields + template canvas.
- Elements can be moved, deleted, and Our Specials added.
- "Save as Template" creates a new template and redirects to builder.
- PDF and PNG downloads work.
- `npm run build` passes; 89/89 tests pass; code map current.

**Status:** ✅ Done — implemented and verified.

---

## 11. ✅ Extraction settings — field aliases

**Goal:** Manage extraction synonyms so OCR can match more variants.

**Scope:**

- Full CRUD page at `/settings/extraction/field-aliases` with inline edit, create, delete.
- CSV export/import: `accepted_variant,canonical_field` format.
- Backend: added `DELETE /admin/dictionaries/field-aliases/{field_name}`, `GET .../export`, `POST .../import`.
- DB field aliases now wired into the extraction pipeline via `extract_with_limits` → `ExtractionOrchestrator` → `find_candidates`.
- Added `delete_field_alias` to admin_service.

**Verification:**

- `npm run build` passes; 89/89 tests pass; code map current.
- Frontend supports create, edit (inline), delete, CSV export/import.
- Extraction pipeline loads FieldAlias rows from DB and merges with DEFAULT_ALIASES.

**Status:** ✅ Done — implemented and verified.

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

**Status:** ✅ Done — brands/models page with CSV export, DB aliases wired into extraction.

---

## 13. ⚠️ Extraction settings — road-tax reference data

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

**Status:** ✅ Done — road-tax rules table, CRUD page, formula evaluation, grouped by vehicle/owner type.

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

**Status:** ✅ Done — trash purge deletes Supabase PDFs, Manager references removed, 4 new tests.

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

**Status:** ✅ Done — 14 Pydantic schemas added, all route payloads typed, 93/93 tests pass, build passes, code map current.

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

**Status:** ⏳ Future work — held until prompts 1–15 are all ✅ and the core product is stable.
