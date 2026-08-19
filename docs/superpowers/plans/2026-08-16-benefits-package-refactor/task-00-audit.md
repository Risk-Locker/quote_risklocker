# Task 0 — Codebase Audit: Benefits & Package System (2026-08-16)

Status: `KEEP` / `REFACTOR` / `MIGRATE` / `DEPRECATE` / `REMOVE-LATER` / `NEW` — every label traced with usages. Nothing was deleted or changed.

Verdict summary, then per-area detail.

## 1. Verdict summary

| Area | Verdict | One-line why |
|---|---|---|
| `insurance_companies` (InsuranceCompany) | KEEP | Full identity already: slug, logo asset, detection phrases, revision, status. |
| `legal_entities` (LegalEntity) | KEEP | Company legal/brand data; already linked. |
| `company_aliases` (CompanyAlias) | KEEP | Working detection aliases; new scoped alias system will complement, not replace. |
| `insurance_categories` (InsuranceCategory) | REMOVE-LATER | Legacy Motor category table; unused by v7 paths. |
| `insurance_products` (InsuranceProduct) | KEEP | The target product entity (benefit-owner when it has no packages). |
| `insurance_product_tiers` (InsuranceProductTier) | DEPRECATE (legacy-compat) | Target packages replace it; FKs in catalogs + drafts keep it readable. |
| `benefit_concepts` (BenefitConcept) | REFACTOR → Global Benefit | Evolve additively: description, demo value, match dataset, value-pattern dataset, ordering. |
| `benefit_aliases` | NEW | Scoped (global/company/product/package) phrase → Global Benefit. |
| `benefit_catalogs` + `benefit_catalog_revisions` | KEEP (configuration container) | Revision/publish/immutability machinery already exactly what the target needs. |
| `catalog_offerings` (CatalogOffering) | REFACTOR → Benefit Assignment | Keep table; add applies_to_type/id, role, display_value, optional_price. No parallel table. |
| `benefit_relations` (BenefitRelation) | DEPRECATE (legacy-only) | Package selection replaces upgrade-edge graph for new configs. |
| `benefit_packages` / `plans` / `plan_items` | REFACTOR | `package_kind` (comprehensive | addon_bundle); assignments hang off packages; plans/items legacy. |
| `benefit_facets` (BenefitFacet) | KEEP | Presentation facets consumed by render_context; no entitlement invention. |
| `business_assets` (BusinessAsset) | KEEP | Artwork library already exists with derivatives. |
| `source_documents` (SourceDocument) | KEEP | Provenance for offerings/assignments. |
| `our_specials` + `our_special_variants` | MIGRATE (merge into Global Benefits) | Same underlying concept; one authoritative system per §4.8. |
| `draft_benefit_selections` (DraftBenefitSelection) | KEEP | Quotation-level state machine (state/cost/typed override) is the target's selection layer. |
| `extraction_benefit_lines` + `draft_source_line_decisions` | KEEP | Evidence + disposition machinery; UI resolution missing (Task 8). |
| `quotation_drafts` pin columns | REFACTOR | Add hierarchy pin columns (segment/vehicle/coverage/package) alongside company/product/tier. |
| Extraction (benefit_lines / orchestrator / worker context) | REFACTOR | Wire match datasets + scoped aliases; value-pattern typing. |
| `catalog_review_service` (pin/seed/auto-apply) | REFACTOR | Hierarchy/product/package detection chain + role-based seeding. |
| `workspace_service` (snapshot + ops) | REFACTOR | Hierarchy banner, package pin, source-line ops, quick-custom layer. |
| `render_context.resolve_benefit_cards` | REFACTOR | Package-driven card resolution; replaces-edges → legacy-only. |
| `template_renderer` + `grid_layout` | KEEP | Deterministic grids consume cards; no change needed. |
| `generation_service` + `RenderSnapshot` | KEEP (+minor) | Immutable freeze already pins catalog/template revisions; add hierarchy/package fields. |
| `business_setup_service` + routes | REFACTOR | Extend with hierarchy CRUD, global-benefit manager, package/assignment editors. |
| `builder/benefits` page | REFACTOR | Hierarchy navigation replaces company→product→tier workspace. |
| `builder/our-specials` page | DEPRECATE (read-only after Task 10) | Merged into Global Benefits. |
| `session-workspace` (provider/review-phase) | REFACTOR | Review screen: detected hierarchy, source-line resolution, quick custom. |
| `v7_backfill.py` / `compatibility_service.py` | KEEP (pattern) | Idempotent, report-first backfill conventions reused for Tasks 3/10. |
| `trash_service.py` (Our Specials paths) | KEEP (until Task 10) | Lifecycle machinery reused for merged entities. |

## 2. Per-area traces (file:line)

### 2.1 Company hierarchy
- `InsuranceCompany` — `backend/app/models/tables.py:98-111` (slug, legal_entity_id, logo_asset_id, detection_phrases, revision, status, category).
- Detection input for extraction: `backend/app/workers/extraction_worker.py:65-87` (companies + aliases_by_company merged with detection_phrases) → `_company_resolution` `:107-116`; company_id persisted on draft/uploaded file `:228-232`.
- `CompanyAlias` — `tables.py:559-568`; CRUD `business_setup_service.py:131-202` (save/retire, normalized-alias uniqueness, 409 on duplicate phrase).
- `LegalEntity` — `tables.py:548-556`; used by company save (`business_setup_service.py:306`).
- `InsuranceCategory` — `tables.py:90-95`; no v7 consumer found (legacy). REMOVE-LATER.
- `InsuranceProduct` — `tables.py:571-581`; CRUD `business_setup_service.py:320-343`; pinned by `quotation_drafts.product_id` (`tables.py:399`); pin logic `catalog_review_service.py:49-58`.
- `InsuranceProductTier` — `tables.py:584-594`; CRUD `business_setup_service.py:346-369`; referenced by `benefit_catalogs.tier_id` (`tables.py:650`), `quotation_drafts.tier_id` (`tables.py:400`), pin logic `catalog_review_service.py:60-69`. DEPRECATE — packages replace; FKs force legacy-compat.

### 2.2 Global benefits
- `BenefitConcept` — `tables.py:614-627` (concept_key, label, value_schema, display_template, required/optional_variables, validation_rules, default_asset_id, revision, status). Serializer `business_setup_service.py:372-385`; CRUD `:388-430`; concept picker in builder `frontend/src/app/builder/benefits/page.tsx:139,275-284`.
- Consumed by extraction ONLY as label matchers with hardcoded empty aliases: `extraction_worker.py:88-97` (`aliases: []`), matched in `benefit_lines.py:85-107` (`_candidate_mappings` substring on label), and by `catalog_review_service.py` + `render_context.py` as identity.
- REFACTOR: additive columns (description, demo_value, match_dataset, value_pattern_dataset, sort_order) — migration 033 (Task 1 draft). Extraction context loader rewired in Task 6.

### 2.3 Catalogs / revisions (configuration container)
- `BenefitCatalog` — `tables.py:643-653` (unique context company+product+tier, status draft/published).
- `BenefitCatalogRevision` — `tables.py:656-667` (revision_number, state, source_document_ids, content_hash, published_by/at).
- Publish machinery: `business_setup_service.py:610-656` (draft→published, content hash, idempotent identical publish, immutable triggers `migrations/024_v7_business_catalog.sql:253-286`), workspace `get_catalog_workspace` `:659-765`.
- Pinned by `quotation_drafts.catalog_revision_id` (`tables.py:401`), frozen into generations (`generation_service.py:117-134, 216-232`).
- KEEP. Task 1 draft adds context columns (segment/vehicle/coverage/package) — §3 of task-01-model.md.

### 2.4 Offerings → assignments
- `CatalogOffering` — `tables.py:670-686` (offering_kind base|upgrade|optional|package_component, typed_value JSON, source_document_id, source_citation, source_aliases, presentation_facet_ids, sort_order, status); check constraint widened in `migrations/032_catalog_upgrade_offering_kind.sql:6-9`.
- CRUD `business_setup_service.py:546-607` (draft-revision-scoped; content hash recomputed per save); serializer includes `source_aliases` (`:557`) but nothing feeds them to extraction.
- Consumers: seeding `catalog_review_service.py:98-123` (base kind), auto-apply `:201-306` (kinds + relations), cards `render_context.py:134-237`, generation snapshot `generation_service.py:117-134`, workspace catalog overview `workspace_service.py:203-225`.
- REFACTOR per §4.4: keep table, add applies_to_type/id, role, display_value, optional_price (migration 033 draft); base→included, optional→addon_option, package_component→bundle_component backfill in Task 10; `upgrade` remains legacy-readable.

### 2.5 Relations (upgrade graph)
- `BenefitRelation` — `tables.py:689-699` (replaces etc., branch_key); CRUD surfaced only read-only in catalog workspace (`business_setup_service.py:682-688, 723-733`); consumed by auto-apply (`catalog_review_service.py:238-249`), card resolution (`render_context.py:184-205`), generation snapshot (`generation_service.py:127-132`).
- DEPRECATE for new configs (§4.4: package selection is the mechanism). Legacy revisions keep working through the same code paths (compat read).

### 2.6 Packages / plans / items (current — unwired)
- `BenefitPackage` — `tables.py:702-711`; `BenefitPackagePlan` — `:714-723`; `BenefitPackagePlanItem` — `:726-734`.
- Only surfaced read-only in catalog workspace (`business_setup_service.py:689-764`); no extraction, no card resolution, no render path. `package_plan` typed value exists in `backend/app/domain/benefits.py:70-74` but renders as plan_key string (`render_context.py:68-69`).
- REFACTOR per §4.3: `package_kind` (comprehensive | addon_bundle) + assignments owned by packages (applies_to=package); plans/items remain legacy-compat; `package_component` → `bundle_component` so bundles resolve into cards (Task 9).

### 2.7 Facets / assets / sources
- `BenefitFacet` — `tables.py:630-640`; consumed by card expansion `render_context.py:112-131` and snapshot `generation_service.py:133`. KEEP (presentation only).
- `BusinessAsset` — `tables.py:751-768`; upload + derivatives `business_setup_service.py:451-523`; consumed by snapshot freeze `generation_service.py:159-191`. KEEP.
- `SourceDocument` — `tables.py:597-611`; intake `services/reference_intake.py`; listing `business_setup_service.py:768-791`; linked by offerings. KEEP.

### 2.8 Legacy Our Specials
- Models `tables.py:139-167`; CRUD `admin_service.py:329-393` (upsert_special/variant, move, category FOC/Add-on enforced `:343`), routes `routes.py:1299-1340`; trash lifecycle `trash_service.py:91-157, 336-356, 381-400`; legacy render path `template_renderer.py:163-168, 245-267` (`_benefit_section` is RL-DISABLED compat; `_section_variants` reads Our Specials for 'specials'/'add_ons' template sections — legacy templates only); frontend `frontend/src/app/builder/our-specials/page.tsx` (709 lines, category toggle); `admin/benefits` redirects here (`frontend/src/app/admin/benefits/page.tsx:5`).
- MIGRATE per §4.8: Task 10 merges into Global Benefits (preserve rows, normalize; FOC/Add-on never stored on the Global Benefit).

### 2.9 Quotation state (selections / lines / decisions)
- `DraftBenefitSelection` — `tables.py:803-821` (state current|available_addon|removed|superseded|unresolved, cost_status included|paid|foc|unknown, item_kind catalog|custom, typed_value_override, evidence_snapshot, superseded_by_id); check constraints `migrations/025_v7_review_state.sql:40-61`.
- `ExtractionBenefitLine` — `tables.py:771-787`; produced by `benefit_lines.py:136-187` via orchestrator (`orchestrator.py:63,77`), persisted by worker `extraction_worker.py:234-268` (one DraftSourceLineDecision per line, unresolved).
- `DraftSourceLineDecision` — `tables.py:790-800`; dispositions unresolved|mapped|custom|source_only|omitted.
- Workspace serialization `workspace_service.py:241-272` (`_selection_summary`, `_decision_summary`); snapshot `:301-383`; ops `_apply_*` `:468-841`; blockers `:114-200` (unresolved_source_line / unknown_benefit_cost / missing_catalog…).
- Frontend: snapshot types `frontend/src/components/session-workspace/types.ts:41-69`; optimistic provider `provider.tsx:56-129`; review UI `review-phase.tsx` (657 lines) — cards render, but `source_lines` are NOT rendered anywhere (`grep` confirms no consumer) → the known dead-end (Task 8).

### 2.10 Extraction pipeline
- `benefit_lines.py:136-187` — heading scopes, inclusion states, stable line ids, label-only `_candidate_mappings`, `_typed_value` heuristics (money/distance/unlimited).
- `candidate_finder.py` — scalar field candidates (fields incl. product_name/product/tier_name/plan_name per `workspace_service.py:52` PIN_SENSITIVE_FIELDS); evidence/confidence stored in `extraction_records.candidates` (`tables.py:377`).
- `orchestrator.py:63,77` — benefit_lines into full_record; `sandbox.py:26-64` — bounded subprocess; worker `extraction_worker.py:138-275` — job flow, integrity, context loader.
- REFACTOR (Tasks 6–7): load match datasets + value-pattern datasets + scoped aliases into context; score lines; type values from patterns; keep conservative rules.

### 2.11 Catalog review / seeding (upload-time)
- `catalog_review_service.py` — `pin_catalog_context` `:44-91` (exact company/product/tier, never guesses; clears stale pins), `seed_base_benefits` `:94-123` (base offerings → current selections), `auto_apply_extracted_benefits` `:168-309` (upgrade replaces current, exact overrides, source_only/omitted).
- Called from worker `extraction_worker.py:34,232,269` and workspace edits `workspace_service.py:514-517, 585-617, 644-645`.
- REFACTOR (Task 7): hierarchy chain detection + package pinning + role-based seeding; individually purchased add-ons → Add-ons section (§4.6).

### 2.12 Workspace service
- `workspace_service.py` (976 lines): snapshot `build_workspace_snapshot:301-383`, patch `apply_workspace_patch:882-976`, ops `:468-841`, blockers `:114-200`, catalog pin ops `:585-653`, template selection `:396-432, 866-879`.
- REFACTOR (Task 8): detected-hierarchy banner, package pin op, source-line ops surfaced, quick-custom layer (existing `create_custom_benefit`/`benefit_update` ops `:656-808` extended).

### 2.13 Rendering
- `render_context.py` — `resolve_benefit_cards` `:134-237` (dup-current hard fail `:157-159`, replaces edges `:184-205`, first-optional-per-concept `:207-221`, facets `:112-131`), typed formatting `format_benefit_value:42-75`, canonical hash `:19-24`.
- `template_renderer.py` — dynamic grids `_dynamic_benefit_grid:171-242` (fixed-page packing, uniform shrink, empty state); legacy specials `_benefit_section:163-168` + `_section_variants:245-267` (RL-DISABLED compat).
- `grid_layout.py` — `pack_fixed_grid:113-175` deterministic packing.
- REFACTOR (Task 9): package-driven cards; replaces-edge path legacy-only; renderer/grid KEEP.

### 2.14 Generation / immutability
- `generation_service.py` — snapshot context `build_render_snapshot_context:194-233` (schema_version, renderer_version, catalog_revision_id, template revision, fields, template_config, cards, assets), freeze `request_version_generation:236-327`, preview `request_preview_render:330-362`.
- `RenderSnapshot` — `tables.py` (context_hash-keyed, immutable); versions never overwritten; download-only.
- KEEP (+Task 9: add hierarchy/package pin fields to snapshot context).

### 2.15 API surface (business + workspace)
- Business routes: `routes.py:908` (page profiles), `913` companies, `932-961` company aliases, `962` companies save, `971` company workspace, `980` products, `989` tiers, `998/1017` benefit-concepts, `1026-1101` assets, `1101` catalogs, `1110` offerings, `1127` publish, `1137` catalog workspace, `1146` sources, `1156/1161` published templates/publish, `1356/1367` dictionaries.
- Workspace routes: `routes.py:454` workspace GET, `507` PATCH, `459` template-selection-impact; generations `525`, preview-render `556`.
- Schemas: `schemas.py` (StrictRequest L8, our-specials requests L123-130, offering/business payloads ~L200-260).
- REFACTOR (Tasks 2,3): hierarchy CRUD, global-benefit manager, package/assignment endpoints, package pin op; conventions (`_require_business`, `_require_revision` 409, `_audit`) reused.

### 2.16 Frontend
- `builder/benefits/page.tsx` (483 lines): 4-column company workspace (companies | products&tiers+catalog select | tabs base/addons/packages/variations + publish | inspector). REFACTOR → hierarchy navigation (Task 5).
- `builder/our-specials/page.tsx` (709 lines): legacy FOC/Add-on manager. DEPRECATE (read-only after Task 10).
- `session-workspace/`: `types.ts` (snapshot contract), `provider.tsx` (optimistic ops), `review-phase.tsx` (Check Values UI), `preview-phase.tsx`. REFACTOR (Task 8).
- Nav/shell: `components/app-shell.tsx`, `builder-nav.tsx`. KEEP (+new Global Benefits nav entry in Task 4).

### 2.17 Migrations / backfill / tests
- Conventions: `migrations/024` (additive BEGIN/COMMIT, IF NOT EXISTS, RLS+REVOKE DO-loop, immutability triggers, unique context index `:146-147`), `025` (selection state CHECKs), `032` (constraint widening); runner `backend/app/db/migrations.py` (sha256 over bytes; LF enforced by `.gitattributes`); apply `commands/apply-migrations.ps1`.
- Backfill patterns: `v7_backfill.py` (stable_key/stable_uuid, report-first, idempotent upserts), `compatibility_service.py` (read-only adapters), `legacy_asset_inventory.py` (reference-aware retirement scans).
- Tests: `test_business_setup_api.py`, `test_catalog_review_initialization.py`, `test_render_context.py`, `test_workspace_service.py`, `test_v7_domain.py`, `test_template_publication.py`, `test_asset_catalog_intake.py`, `test_v7_backfill.py`, `test_our_specials_api.py`, `test_migration_runner.py`, `test_frontend_*_contract.py` — baseline 401 passed / 2 skipped (2026-08-16).

## 3. Terminology freeze (matches §0.7 of TASK-PLAN)

Confirmed against code: Global Benefit (= evolved `benefit_concepts`), Segment/Vehicle Category/Subcategory/Coverage Type (NEW), Product (`insurance_products`), Comprehensive Package / Add-on Bundle (`benefit_packages` + `package_kind`), Benefit Assignment (evolved `catalog_offerings`), Role (included/addon_option/bundle_component), Configuration Revision (`benefit_catalog_revisions`), Benefit Alias (NEW `benefit_aliases`), Match dataset + Value-pattern dataset (NEW columns on Global Benefit), Quotation Selection (`draft_benefit_selections`), Quick custom layer (existing custom selection path), Value priority ladder (§4.5). No synonyms introduced.

## 4. Audit findings affecting the settled register

- §4.4 "keep and simplify catalog_offerings" is fully feasible: `source_aliases` column already exists on offerings (unused by extraction — Task 6 wires it) and `typed_value` is already typed JSON (no string flattening; §4.7 satisfied).
- §4.3 no-inheritance: current `benefit_packages` are already revision-scoped rows (per-revision package definitions), which naturally gives explicit, frozen packages on publish; clone is a copy operation.
- §4.8 Our Specials merge is feasible with the existing `v7_backfill.py` conventions (stable keys, report-first); `template_renderer._section_variants` keeps legacy templates working after migration (compat path remains).
- Tier→package: `benefit_catalogs.tier_id` and `quotation_drafts.tier_id` are the only hard FKs — keep both columns; new rows use package path (Task 3 validation).
- No code changes were made in this task.
