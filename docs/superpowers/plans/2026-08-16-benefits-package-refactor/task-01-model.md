# Task 1 — Target Domain Model & Migration 033 Design (2026-08-16)

Status: **design + draft migration, NOT applied.** Approved at checkpoint C2 → Task 2 applies it.

## 1. Target ERD (text)

```
InsuranceCompany (KEEP)
├── CompanyAlias (KEEP)                  detection phrases → company
└── benefit_catalogs (KEEP, EVOLVED)     the configuration container
      ├── segment_id → segments (NEW)
      ├── vehicle_category_id → vehicle_categories (NEW)
      ├── vehicle_subcategory_id → vehicle_subcategories (NEW)
      ├── coverage_type_id → coverage_types (NEW)
      ├── product_id → insurance_products (KEEP)
      ├── tier_id → insurance_product_tiers (DEPRECATE, legacy rows only)
      └── package_id → benefit_packages (NEW linkage; mutually exclusive with tier per row)
            └── benefit_catalog_revisions (KEEP) — draft/published, immutable when published
                  ├── catalog_offerings (KEEP, EVOLVED → Benefit Assignment)
                  │     concept_id → benefit_concepts (KEEP, EVOLVED → Global Benefit)
                  │     applies_to_type: product | package | bundle
                  │     applies_to_id: product_id | package_id | package_id(bundle)
                  │     role: included | addon_option | bundle_component
                  │     typed_value (KEEP, typed) + display_value (NEW)
                  │     optional_price (NEW) + source_document_id (KEEP)
                  ├── benefit_packages (KEEP, EVOLVED) — package_kind: comprehensive | addon_bundle
                  ├── benefit_relations (DEPRECATE for new configs; legacy reads only)
                  └── benefit_package_plans / plan_items (DEPRECATE, legacy reads only)

benefit_concepts (Global Benefit, EVOLVED)
├── name/key/label/value_schema/display_template/required_variables (KEEP)
├── default_asset_id → business_assets (KEEP)
├── description (NEW), demo_value (NEW, typed), sort_order (NEW)
├── match_dataset (NEW JSON)        words/phrases for extraction scoring
├── value_pattern_dataset (NEW JSON) value-shape vocabulary (price, km, per-day…)
└── benefit_aliases (NEW)           scoped: global | company | product | package

QuotationDraft (KEEP, EVOLVED)
├── company_id / product_id / tier_id / catalog_revision_id (KEEP)
├── segment_id, vehicle_category_id, vehicle_subcategory_id, coverage_type_id (NEW)
├── package_id (NEW, informational; catalog_revision_id remains the authoritative pin)
├── template_revision_id / layout_override (KEEP)
└── draft_benefit_selections / draft_source_line_decisions (KEEP)

GeneratedPdfVersion (KEEP) — render snapshots stay immutable; Task 9 adds hierarchy fields to the context.
```

## 2. Why reuse (per settled §4 + audit)

- **`benefit_catalogs` + revisions** already provide draft/publish/content-hash/immutability-trigger machinery; the catalog row becomes the *path-annotated configuration container* (segment/vehicle/coverage/package context), and its published revision is what quotations pin. This is the smallest change to the trusted revision system.
- **`catalog_offerings`** is already the "Global Benefit + where it applies + typed value" row; adding `applies_to_type/id`, `role`, `display_value`, `optional_price` makes it the Benefit Assignment without a parallel table (§4.4). `source_aliases` already exists and becomes one alias input (Task 6).
- **`benefit_packages`** are already per-revision rows → publishing freezes them exactly; `package_kind` distinguishes the comprehensive chain from add-on bundles (§4.3). No runtime inheritance: every saved package is explicit (clone copies).
- **Tiers** stay as legacy FK targets (`benefit_catalogs.tier_id`, `quotation_drafts.tier_id`) — old rows keep working; new rows use the package path. Task 10 backfills/retires.
- **`insurance_product_tiers` never becomes packages** — separate entities, new work uses packages (§4.3).

## 3. Migration 033 contents (draft in `migrations/033_benefits_package_hierarchy.sql`)

All additive; LF line endings; BEGIN/COMMIT; `IF NOT EXISTS`; RLS+REVOKE for every new table; seed rows `ON CONFLICT DO NOTHING` with fixed UUIDs.

### 3.1 New tables

| Table | Columns (key) | Notes |
|---|---|---|
| `segments` | id, segment_key UNIQUE, name, sort_order, status, timestamps | Seed: Private, Company / Commercial |
| `vehicle_categories` | id, category_key UNIQUE, name, sort_order, status, timestamps | Seed: Car, Motorcycle, Commercial Vehicle |
| `vehicle_subcategories` | id, category_id FK, subcategory_key, name, sort_order, status, uq(category_id, subcategory_key) | Seed: Lorry / Truck, Van, Bus → Commercial Vehicle |
| `coverage_types` | id, coverage_key UNIQUE, name, sort_order, status, timestamps | Seed: Comprehensive, Third Party Fire & Theft, Third Party |
| `benefit_aliases` | id, benefit_id FK benefit_concepts, phrase, normalized_phrase, scope CHECK (global\|company\|product\|package), company_id FK NULL, product_id FK NULL, package_id FK NULL, status, uq(benefit_id, normalized_phrase, scope, company_id, product_id, package_id) | Scoped alias → Global Benefit (Task 6 wiring) |

### 3.2 Evolve `benefit_concepts` (Global Benefit)

`ADD COLUMN IF NOT EXISTS`: `description TEXT`, `demo_value JSONB`, `match_dataset JSONB NOT NULL DEFAULT '[]'`, `value_pattern_dataset JSONB NOT NULL DEFAULT '[]'`, `sort_order INTEGER NOT NULL DEFAULT 0`.

### 3.3 Evolve `benefit_packages`

`ADD COLUMN IF NOT EXISTS package_kind VARCHAR(40) NOT NULL DEFAULT 'comprehensive' CHECK (package_kind IN ('comprehensive','addon_bundle'))`.

### 3.4 Evolve `catalog_offerings` (Benefit Assignment)

`ADD COLUMN IF NOT EXISTS`:
- `applies_to_type VARCHAR(40)` CHECK (NULL or IN ('product','package','bundle')),
- `applies_to_id UUID` (no FK constraint — polymorphic owner; validated in service),
- `role VARCHAR(40)` CHECK (NULL or IN ('included','addon_option','bundle_component')),
- `display_value VARCHAR(500)`,
- `optional_price JSONB` (typed money or null).
Partial CHECK: `(applies_to_type IS NULL AND applies_to_id IS NULL) OR (applies_to_type IS NOT NULL AND applies_to_id IS NOT NULL)`.
Existing rows stay NULL until the Task 10 backfill; legacy card resolution ignores the new columns.

### 3.5 Evolve `benefit_catalogs` (path context)

`ADD COLUMN IF NOT EXISTS`: `segment_id`, `vehicle_category_id`, `vehicle_subcategory_id`, `coverage_type_id`, `package_id` (all FK NULL-able). New partial unique index for package contexts:
`CREATE UNIQUE INDEX IF NOT EXISTS benefit_catalogs_package_context_uq ON benefit_catalogs(company_id, product_id, package_id) WHERE package_id IS NOT NULL;`
Legacy context index (`benefit_catalogs_context_uq`) untouched for tier rows. Service validation (Task 3): a row uses tier_id XOR package_id.

### 3.6 Evolve `quotation_drafts`

`ADD COLUMN IF NOT EXISTS`: `segment_id`, `vehicle_category_id`, `vehicle_subcategory_id`, `coverage_type_id`, `package_id` (FK NULL-able). `catalog_revision_id` remains the authoritative config pin; new columns are detection/pin metadata for the review banner (Task 7/8).

### 3.7 Seeds (fixed UUIDs, ON CONFLICT DO NOTHING)

- segments: `priv` Private; `com` Company / Commercial
- vehicle_categories: `car` Car; `moto` Motorcycle; `comv` Commercial Vehicle
- vehicle_subcategories: `lorry` Lorry / Truck; `van` Van; `bus` Bus (all → comv)
- coverage_types: `comp` Comprehensive; `tpft` Third Party Fire & Theft; `tp` Third Party

### 3.8 RLS / privileges

DO-loop over every new table: `ENABLE ROW LEVEL SECURITY` + `REVOKE ALL PRIVILEGES FROM anon, authenticated` (mirrors migrations 024/025).

### 3.9 Explicitly NOT in 033

- No data backfill (Task 10), no `offering_kind` change (032 still current; Task 3/10 map kinds→roles), no `benefit_relations` change, no plan/plan_item change, no Our Specials change, no package-linkage backfill.
- Migration 034 reserved for Task 3 (backend wiring discoveries only, if needed).

## 4. Backward compatibility guarantees

- Every new column is nullable or defaulted; no CHECK constraint rejects existing rows.
- Legacy card resolution path (`render_context` with `replaces` edges + `offering_kind`) unchanged — old drafts render as before.
- Migration ledger discipline: sha256 of the LF file bytes; never edit 033 after it is applied; `.gitattributes` keeps LF.
- Rollback: 033 is additive — a revert is `DROP TABLE ... CASCADE`-free column drops; no data loss. (Reversible by owner request; not planned.)

## 5. What Task 2 does with this

Applies 033 via `commands/apply-migrations.ps1`; adds ORM models + hierarchy/global-benefit CRUD (segments, vehicle categories/subcategories, coverage types, benefit concepts extended with the new fields + alias table) following `business_setup_service.py` conventions (revision 409, audit, RBAC).
