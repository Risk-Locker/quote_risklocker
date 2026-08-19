# RiskLocker Benefits & Package Refactor — Durable Master Task Plan

- Owner-approved 2026-08-16. The Decision Register (§4) is **settled — never re-ask**.
- This file is the **permanent home** of the implementation plan. `fix/` (gitignored) holds temporary/reference inputs only (the reference DOCX, the prompt, the target-architecture context).
- Each task below is a **self-sufficient prompt**: a fresh chat with zero context can open this file, read §0 + §1 + the task section (+ the outputs of any earlier tasks listed in the task), and execute correctly.

---

# §0 THE PROTOCOL — read first in every chat

## 0.1 How this plan is executed

1. Tasks run in order (Task 0 → Task 13). Each task is one work chunk sized for a single AI session.
2. Execution is **continuous by default**: do NOT stop after every task merely to reconfirm decisions. The decisions in §4 are settled.
3. **Stop conditions (the only reasons to halt and report):**
   - a genuine blocker (broken build, failing gate, missing file);
   - a destructive/irreversible action (data deletion, table drop, irreversible backfill) — propose it, wait for approval;
   - an ambiguity that **materially changes the approved architecture** — present options, wait;
   - an **explicit verification checkpoint** (C1–C5 below) — report and wait for "proceed".
4. The owner may also pace manually ("proceed with 4,5", "skip to 8") — obey, but always read the earlier task outputs first.
5. After the final task (Task 13), stop and report. Do not start unrelated work.

## 0.2 Context capture rule

At the start of EVERY task (and before resuming any task in a new chat):

1. Read `AGENTS.md`.
2. Read `docs/START-HERE.md` (routing).
3. Read `docs/MEMORY.md` (snapshot + logbook — knows what happened so far).
4. Read the task's "READ FIRST" list completely, including every earlier task output file it names.
5. Only then touch code.

Never skip context capture by assuming the chat already knows the project.

## 0.3 Docs duty after EVERY task (checkpoint or not)

- Append one ultra-short log entry to `docs/MEMORY.md` (format: `date · model · asked · done · pending`), update the Current Snapshot if a durable fact changed.
- Update the affected topic docs (BUSINESS-RULES.md, ARCHITECTURE.md, API-CONTRACT.md, TESTING.md, OPERATIONS.md, DESIGN-SYSTEM.md) when behaviour they describe changes.
- After structure changes: `python commands/update-code-map.py --write`, then `--check` before finishing. Update `docs/STRUCTURE.md` for added/removed top-level files/folders.
- Record durable decisions in BOTH MEMORY.md and the relevant topic doc.
- Undocumented work is unacceptable.

## 0.4 Verification gate (Definition of Done, every task)

- Backend: `.\.venv\Scripts\python.exe -m pytest -q` — all green (current baseline: 401 passed, 2 skipped — the owner-DOCX pair; do not regress).
- Frontend: `npx tsc --noEmit` (in `frontend/`) and `npm run build` — green.
- Code map: `npm run code-map:check` — current (run `npm run code-map` after structure changes).
- Task-specific checks are listed in each task. The backend must be able to start (`npm run backend`, `/health` → Ready) after tasks that touch services.

## 0.5 Verification checkpoints (stop + report + wait for proceed)

| Checkpoint | After task | Purpose |
|---|---|---|
| **C1** | Task 0 | Owner reviews the audit + confirms terminology freeze |
| **C2** | Task 1 | Owner reviews the domain model + migration 033 draft BEFORE any migration is applied |
| **C3** | Task 5 | Owner reviews the admin UI milestone (Global Benefits + Company Configuration) |
| **C4** | Task 9 | Owner reviews the end-to-end pipeline (extraction → resolution → cards → render) |
| **C5** | Task 12 | Certification sign-off (tests + E2E + acceptance checklist) before AI seeding |

## 0.6 Environment and operations facts (fresh chats must not rediscover these)

- Stack: FastAPI (`backend/`), Next.js 15.5 + React 19 (`frontend/`), Supabase/Postgres (`migrations/`, checksummed ledger), private Supabase Storage, Postgres job queue, one worker, Playwright/Chromium PDF.
- Python env: `.venv` on **Python 3.12** (`py -3.12 -m venv .venv`; pinned requirements predate 3.14 wheels). Never rebuild with 3.14.
- Dev servers: `npm run backend` (:8100, port file `.qc-tmp\backend-port.txt`), `npm run frontend` (:3000), `npm run full`, `npm run stop`.
- Dev login: admin@risklocker.local / admin123 (dev only).
- Migration files MUST stay LF on disk — `.gitattributes` enforces `migrations/*.sql text eol=lf`; ledger checksums sha256 of raw file bytes. Never write migrations with CRLF.
- Apply migrations with `commands/apply-migrations.ps1`. Never edit an applied migration file.
- Temp/QA work goes in `/.qc-tmp/` (gitignored) — never outside the repo.
- Current baseline (2026-08-16): 401 backend tests pass, 2 skipped; `tsc` clean; `next build` green; `/health` Ready; code map current.

## 0.7 Vocabulary freeze (use these terms everywhere; do not invent synonyms)

| Term | Meaning | Current code anchor |
|---|---|---|
| Global Benefit | ONE reusable RiskLocker benefit (Towing, Windscreen…) | evolves `BenefitConcept`/`benefit_concepts` |
| Segment | Private / Company-Commercial usage context | NEW `segments` |
| Vehicle Category / Subcategory | Car, Motorcycle, Commercial Vehicle (+ Lorry/Van/Bus…) | NEW `vehicle_categories` / `vehicle_subcategories` |
| Coverage Type | Comprehensive / TPFT / Third Party | NEW `coverage_types` |
| Product | insurer's named product (owns benefits when it has no packages) | `InsuranceProduct` |
| Comprehensive Package | named main plan (Lite/Plus/Premier; level 1 may be named `base` or the product name; NEVER invented when product has no packages) | `benefit_packages` with `package_kind` |
| Add-on Bundle | enhancement package (OTO 360, Motor PA…) | `benefit_packages` with `package_kind=addon_bundle` |
| Benefit Assignment | link Global Benefit ↔ product/package/bundle with role + exact value + price | evolves `CatalogOffering`/`catalog_offerings` |
| Role | `included` \| `addon_option` \| `bundle_component` (maps from base/optional/package_component) | on assignment |
| Configuration Revision | published, frozen benefit configuration a quotation pins | `BenefitCatalogRevision` (continues) |
| Benefit Alias | scoped (global/company/product/package) phrase → Global Benefit | NEW `benefit_aliases` |
| Match dataset | words/phrases on a Global Benefit used to count/score source lines | NEW column(s) on Global Benefit |
| Value-pattern dataset | value-shape vocabulary (price, km, per-day…) used to type extracted values | NEW column(s) on Global Benefit |
| Quotation Selection | per-quotation benefit state (current/add-on/removed/superseded/unresolved) | `DraftBenefitSelection` (continues) |
| Quick custom layer | quotation-only staff additions/overrides; never pollutes permanent data unless promoted | existing custom selection path |
| Value priority ladder | Staff correction → exact quotation value → selected package/add-on config → base product/package config → Check Needed | §4.5 |

---

# §1 UNIVERSAL CONTEXT BLOCK

Every task starts by reading, in order:

1. `AGENTS.md`
2. `docs/START-HERE.md`
3. `docs/MEMORY.md` (current snapshot + logbook)
4. `docs/STRUCTURE.md`
5. `docs/BUSINESS-RULES.md`
6. `docs/ARCHITECTURE.md`
7. `docs/API-CONTRACT.md`
8. `docs/TESTING.md`
9. `docs/OPERATIONS.md`
10. `docs/INSTRUCTIONS.md` (how the owner talks)
11. `fix/RiskLocker_Benefits_Package_Target_Architecture_Context.md` (the target behaviour — cite its sections in task requirements)
12. `fix/RiskLocker_Benefits_Package_Refactor_Plan_Prompt.md` (the planning brief)
13. THIS FILE — §0 protocol, §2 task map, §4 decisions, and the outputs of every earlier task in `docs/superpowers/plans/2026-08-16-benefits-package-refactor/` (files named `task-NN-*.md`).

Reference inputs (temporary, in `fix/`, gitignored):

- `fix/RiskLocker_Malaysia_Motor_Comprehensive_Packages_Benefits_Addons_2026.docx` — verified business reference; used ONLY in Task 13 (AI-assisted draft seeding).
- `fix/RiskLocker_Benefits_Package_Target_Architecture_Context.md` — target architecture (this plan implements it).
- `fix/RiskLocker_Benefits_Package_Refactor_Plan_Prompt.md` — the original planning brief.

Task outputs (permanent) live in `docs/superpowers/plans/2026-08-16-benefits-package-refactor/`:

- `task-00-audit.md` — codebase audit (KEEP/REFACTOR/MIGRATE/DEPRECATE/REMOVE-LATER/NEW)
- `task-01-model.md` — domain model/ERD + migration design
- later tasks append their own findings files as needed (`task-03-api.md`, `task-05-ui.md`, …)

---

# §2 TASK MAP

| Task | Phase (of 10) | Depends on | Checkpoint | One-line scope |
|---|---|---|---|---|
| 0 | 1 | — | **C1** | Codebase audit, terminology freeze, confirm register |
| 1 | 1–2 | 0 | **C2** | Domain model/ERD + migration 033 draft (not applied) |
| 2 | 2 | 1 | — | Apply 033; hierarchy + Global Benefit backend CRUD |
| 3 | 3 | 2 | — | Packages/assignments/aliases backend + migrations 034–035 |
| 4 | 4 | 2,3 | — | Admin UI: Global Benefits manager |
| 5 | 4 | 3,4 | **C3** | Admin UI: Company Configuration workspace |
| 6 | 5 | 2,3 | — | Extraction: scoped alias + value-pattern matching |
| 7 | 5 | 6 | — | Upload resolution + base seeding rework (product/package pin) |
| 8 | 6 | 7 | — | Review UI: package pinning, source-line resolution, quick custom layer |
| 9 | 7 | 7,8 | **C4** | Card resolution + render/snapshot integration |
| 10 | 8 | 9 | — | Legacy unification: Our Specials merge, offerings backfill, tier compat |
| 11 | 9 | 10 | — | Test suite + acceptance scenarios A–J |
| 12 | 9 | 11 | **C5** | Certification run + docs finalisation |
| 13 | 10 | 12 | — | AI-assisted draft seeding from the reference DOCX (draft-only) |

---

# §3 THE TASKS

> ## ROUND 2 REVISION (2026-08-16, owner-approved) — supersedes pacing; read before §3 tasks
>
> The owner reviewed Round 1 (Tasks 0–5 + replan steps) and gave final directives. This revision is binding; where it conflicts with the task text below, this block wins. The handoff prompt (provided to a fresh IDE/model) executes the ENTIRE remaining scope in ONE continuous run after plan approval — the C1–C5 checkpoint stops are suspended for that run; stop only for genuine blockers, destructive/irreversible actions, or a material ambiguity. This chat remains the owner's verifier.
>
> ### R2-1 Benefits page = the flow ONLY
> - Delete the List view and the view toggle entirely. The Benefits page IS the interactive flow: Insurance Company → Segment ℹ (tooltip; Private default) → Vehicle Type → Product → Package chain → Benefits (defaults) box + Add-ons box. Editing happens below the flow. No side panes, no "catalog" language anywhere.
> ### R2-2 Global Benefits = dead simple
> - Fields: Name · Key · Description (ONE short line containing the example value, e.g. "up to 50 km", "up to 3 years", "up to RM200" — readable in <1s; optional second line only if truly needed) · Artwork (picker from existing benefit_art assets with thumbnails) · Match words · Sort · Active.
> - Remove from the UI: description variants (badges/types/samples/auto-detect), variables tag editor, value-pattern dataset input, demo value. The value slot inside the description is handled invisibly (auto-converted to a template at save; extraction/render replace the value).
> - Aliases are NOT on this page — only a "Manage aliases" button linking to `/extraction/benefit-aliases`. One place only.
> ### R2-3 No pricing feature
> - Remove optional-price inputs from the UI everywhere (assignment editor, dialogs). The `optional_price` column stays dormant (no UI, no new pricing systems, no cost handling).
> ### R2-4 Two-box mechanic on the staff Review screen (game-like move/switch/remove/upgrade)
> - Benefits (top) and Add-ons (bottom) are two boxes; items move by CLICKING. Add-ons listed below → click to add → moves up into Benefits; click to remove → drops back to Add-ons. Full staff freedom to move either way.
> - Upgrades = multiple versions of the SAME global benefit (Towing 50 km default + 150 km option; QBE driver protection A/B/C/D). Unchosen versions sit in Add-ons; choosing one moves it up and REPLACES the current (supersedes). Purchased A → A on top, B/C/D below; not purchased → A in Add-ons.
> - Single-variant benefits (Whole Car Spray Painting RM1,500): once added → Add-ons empty for that concept; not bought → stays in Add-ons.
> - Reuses the existing selection state machine; no new data model.
> ### R2-5 Sessions flow redo — one screen, serial, kid-simple
> - The current page-hopping (upload page → review page → preview page) is WRONG. Target: ONE flow without page changes: Upload one PDF → same screen steps through: Extract text → Confirm (company/template/plan) → Values + Benefits/Add-ons with the source-PDF preview on the LEFT → Generate. Each step confirms before the next. Staff only ever need Upload and Sessions.
> ### R2-6 Staff scoping (non-technical users)
> - Staff use ONLY Upload and Sessions (they are not shown/never need Builder, Extraction & Aliases, Settings, etc. — those are admin/owner surfaces). The app must be usable by someone who "hardly knows how to use a mouse".
> ### R2-7 Extraction finalization bar (the acceptance criterion)
> - If a value EXISTS in the uploaded quotation and extraction fails to detect it → THE APPLICATION FAILED. The only acceptable miss is a value genuinely absent from the source.
> - Values must be plotted with correct spacing/format; the learning flow (dictionary learn) works; everything through Upload → Extraction → Preview is smooth.
> ### R2-8 Seed + cleanup (commands/seed-demo.py, idempotent)
> - Use the EXISTING 35 benefit_art assets (assign by label: Towing→"Towing", Windscreen→"Windscreen Coverage", Workmanship→"Repair Workmanship Warranty", Special Perils→"Special Perils", Flood→"Flood Coverage / Flood Damage Protection", Keys→"Key Replacement / Key Care"). NO generated images. Data from `fix/` docs + the reference DOCX, SIMPLIFIED to short descriptions; internet allowed for correct reference data, always simplified.
> - Seed: 3 companies (QBE, Etiqa, AmAssurance — exist), 6 benefits with artwork/descriptions/match words, real product names ("QBE Private Car", "Etiqa Motor Comprehensive", "AmAssurance Private Car"), one Lite + Plus package chain with defaults + add-ons (published), scoped aliases ("24/7 Towing Assistance" → Towing …).
> - Cleanup junk: product named "Towing" + its packaged config (Lite/OTO 360 E2E rows), legacy "Q-Drive Standard" tier config + catalog, leftover test rows.
> ### R2-9 Remaining roadmap (original plan, executed in the one-go run)
> - Task 6: extraction — scoped alias + description-template value shaping (money/distance/duration patterns from the description), worker context loader, benefit_lines rework; the R2-7 bar applies.
> - Task 7: upload resolution + seeding rework (company→segment→vehicle→product→package pinning, defaults from config, purchased add-ons → Add-ons box).
> - Task 8: review UI — the two-box mechanic (R2-4), detected flow banner, source-line resolution, quick custom layer.
> - Task 9: card resolution + render/snapshot integration (package-driven cards, legacy replaces-edges compat, snapshot pins hierarchy/config).
> - Task 10: legacy unification (Our Specials merge into Global Benefits, offerings→role backfill draft-only, tiers compat).
> - Task 11–12: full tests + acceptance A–J + certification incl. the R2-7 extraction bar; browser E2E of the complete staff flow.
> - Task 13: AI-assisted DRAFT seeding from the reference DOCX (reviewable, never auto-published).
> ### R2-10 Handoff mechanics
> - The owner will paste a full execution prompt into another IDE (Sonnet 4.6). That prompt instructs: read AGENTS.md → START-HERE → MEMORY → this TASK-PLAN (+ task outputs + fix/ docs + DOCX), present a consolidated plan in PLAN MODE, ask the owner, then execute EVERYTHING continuously (no intermediate stops), update docs after every task, keep all gates green (pytest baseline 448 passed/2 skipped → growing; tsc; build; code-map), and deliver a final certification report against R2-7 + acceptance A–J. No commits unless the owner asks.


> ## REPLAN 2026-08-16 (owner-approved — supersedes Tasks 4, 5 and parts of Tasks 1, 6, 8, 9 as written below)
>
> After the first pass, the owner re-planned the UX and the Global Benefit model:
> 1. **Global Benefits = description variants.** Each benefit carries up to TWO `description_variants` (`{key, template, value_type}`; value_type ∈ money | distance | duration, implied by the template — "RM {value}" → money, "{value} km" → distance, "{value} years" → duration). No type-first selects; the per-variant sample value replaces the old demo-value type picker. Per-day type dropped. (Migration 035, applied; backend + UI done.)
> 2. **Benefits workspace v2.** Path flow: Insurance Company → Segment (tooltip, defaults Private) → Vehicle Type (Car/Motorcycle/Commercial Vehicle; Car is the working path) → Product → Benefits & Add-ons. Coverage is implied Comprehensive for now (slot reserved after Vehicle). NO "catalog" language anywhere. Single mode (no packages) = one Benefits box + one Add-ons box; Package mode = package chain cards (add/clone/rename). List ↔ Mind-map view toggle on the same page. Revisions is its own tab. Aliases tab removed from the workspace.
> 3. **Extraction & Aliases sidebar section** (new): Company Detection, Field Aliases, Benefit Aliases (NEW page — scoped aliases, auto-synced with Global Benefits), Vehicles, Road Tax move out of Settings; Settings keeps only Users, System Checks, Storage. Old `/settings/extraction/*` paths redirect.
> 4. **Extraction handoff (Task 6):** variant templates are the value-shape rules; Lonpac "Windscreen coverage… RM 800" → money 800 via the money variant template.
> 5. **Contract tests** updated/added for the reworked pages and the new section.
>
> Implementation status: steps 1–5 complete (migrations 035, backend variants, Global Benefits UI rework, Extraction & Aliases section + Benefit Aliases page, Benefits workspace v2, contract tests, browser E2E green). Checkpoint C3 re-run follows.


---

## Task 0 — Codebase audit, terminology freeze & decision confirmation

**PHASE:** 1 · **DEPENDS ON:** nothing · **GATE:** checkpoint C1

### GOAL
Produce the verified audit of the current benefits/packages implementation (one row per table/module/endpoint with KEEP / REFACTOR / MIGRATE / DEPRECATE / REMOVE-LATER / NEW), freeze the vocabulary (§0.7), and confirm the settled register (§4). **No schema change, no UI change, no data change.**

### READ FIRST
1. Universal context block (§1) — every file listed, in order.
2. §0 (protocol), §2 (map), §4 (decisions).
3. Code to trace (read fully, do not skim):
   - `backend/app/models/tables.py` — from `InsuranceCompany` through `DraftBenefitSelection` (approx. L97–830).
   - `backend/app/services/business_setup_service.py`, `catalog_review_service.py`, `workspace_service.py`, `generation_service.py`, `v7_backfill.py`, `compatibility_service.py`, `trash_service.py`.
   - `backend/app/extraction/benefit_lines.py`, `candidate_finder.py`, `validators.py`, `backend/app/workers/extraction_worker.py`.
   - `backend/app/rendering/render_context.py`, `template_renderer.py`, `grid_layout.py`.
   - `backend/app/api/routes.py` (business + workspace + draft regions), `backend/app/api/schemas.py`.
   - `migrations/024_v7_business_catalog.sql`, `025_v7_review_state.sql`, `032_catalog_upgrade_offering_kind.sql`.
   - `frontend/src/app/builder/benefits/page.tsx`, `frontend/src/app/builder/our-specials/page.tsx`, `frontend/src/components/session-workspace/*` (types, provider, review-phase), `frontend/src/lib/api.ts`.
   - Tests touching this domain: `test_business_setup_api.py`, `test_catalog_review_initialization.py`, `test_v7_domain.py`, `test_template_publication.py`, `test_render_context.py`, `test_workspace_service.py`, `test_asset_catalog_intake.py`, `test_v7_backfill.py`.

### DELIVERABLES
A. `docs/superpowers/plans/2026-08-16-benefits-package-refactor/task-00-audit.md` containing, per area (company hierarchy, catalogs/revisions, concepts, offerings, relations, facets, packages/plans/items, aliases, extraction, workspace, card resolution, rendering, Our Specials, publishing): the current role, traced usages (file:line), and the chosen label with justification. Every REMOVE-LATER must show its traced usages. Nothing is deleted.
B. A short "terminology freeze" table (copy §0.7, confirm it matches the code findings; note any mismatch).
C. MEMORY.md log entry + snapshot update.

### VERIFICATION
- No code touched: `git status` shows no source changes (only the new doc file + MEMORY.md).
- `python -m pytest -q` green (baseline 401 passed, 2 skipped).

### STOP / CHECKPOINT C1
Report: audit summary (≤ 20 lines), any terminology mismatches found, and any §4 entry the audit proves impossible as written (with evidence). Wait for owner confirmation of the freeze before Task 1.

---

## Task 1 — Target domain model & migration 033 draft

**PHASE:** 1–2 · **DEPENDS ON:** Task 0 · **GATE:** checkpoint C2

### GOAL
Design the target domain model (ERD) and draft migration 033 (schema only, NOT applied). This is the architectural blueprint; everything after builds on it.

### READ FIRST
1. Universal context block (§1) + `task-00-audit.md`.
2. Target-architecture sections: §2 (hierarchy), §3 (level meanings), §4 (packages first-class), §5 (two kinds of package-like things), §6 (global library), §7 (exact values), §8 (roles not identities), §9 (assignment), §10 (aliases), §12 (priority), §21 (conceptual model), §22 (current→target mapping), §26 (rules).
3. Current schema: `backend/app/models/tables.py` benefit region; `migrations/024`, `025`, `026`, `032`.
4. Migration conventions: `backend/app/db/migrations.py`, `commands/apply-migrations.ps1`, `tests/test_migration_runner.py` (checksum discipline), `docs/OPERATIONS.md` (LF rule).

### TARGET BEHAVIOUR (per settled §4)
- New tables (all DB-driven, seeded defaults in the migration):
  - `segments` (Private, Company/Commercial — seed both),
  - `vehicle_categories` (Car, Motorcycle, Commercial Vehicle — seed),
  - `vehicle_subcategories` (optional, e.g. Lorry/Truck, Van, Bus — seed as defaults),
  - `coverage_types` (Comprehensive, Third Party Fire & Theft, Third Party — seed),
  - `benefit_aliases` (global_benefit_id, phrase, scope: global|company|product|package, optional scoped ids, active).
- Evolve (additive columns):
  - `benefit_concepts` → Global Benefit: + description, + demo_value (typed), + match_dataset (words/phrases for extraction scoring), + value_pattern_dataset (value-shape vocabulary), keep name/key/artwork/value_schema/display_template/required_variables.
  - `benefit_packages` → + `package_kind` (`comprehensive` | `addon_bundle`), + product linkage, + base/first-level naming rule (a level-1 package may be named `base` or carry the product name — allowed but never required/invented).
  - `catalog_offerings` → Benefit Assignment: + `applies_to_type` (`product` | `package` | `bundle`), + `applies_to_id`, + `role` (`included` | `addon_option` | `bundle_component`), + `optional_price` (typed money or null); keep `typed_value` (typed architecture preserved, §4.7) and add customer `display_value`; `offering_kind` retained for legacy compatibility only; mapping base→included, optional→addon_option, package_component→bundle_component.
- Product/package linkage: products get optional `package_id` chains via `benefit_packages`; a product with zero packages owns assignments directly (`applies_to_type=product`).
- NO runtime package inheritance (§4.3): the UI may clone; stored configuration is always explicit.
- Decided shape notes: `InsuranceProductTier` stays legacy-compat; `BenefitCatalog`/`BenefitCatalogRevision` continue as the configuration-revision mechanism (catalogs may now also scope by package path); `BenefitRelation` demoted (kept for legacy reads only).

### DELIVERABLES
A. `task-01-model.md` — ERD (text diagram), every table: purpose, key columns, FKs, status (KEEP/EVOLVE/NEW/DEPRECATE), and the migration order.
B. Draft `migrations/033_benefits_package_hierarchy.sql` (NOT applied): new tables + seeded default rows + additive columns on `benefit_concepts`, `benefit_packages`, `catalog_offerings`. LF line endings. Idempotent-friendly (IF NOT EXISTS / ON CONFLICT DO NOTHING for seeds). No data backfill yet (that is Task 10/3 scope).
C. MEMORY.md + STRUCTURE.md (migration added) updates; code map regenerate.

### VERIFICATION
- `python commands/apply-migrations.ps1 --help`-safe: migration file passes `discover_migrations` (name/format) — run `python -c` check via `discover_migrations(Path('migrations'))` OR rely on `pytest tests/test_migration_runner.py -q`.
- Full suite still green (migration unapplied, no code change).
- `npm run code-map:check` current.

### STOP / CHECKPOINT C2
Report: the ERD summary, the seeded rows, and the additive column list. Wait for owner approval **before any migration is applied**. Task 2 applies 033 only after this approval.

---

## Task 2 — Backend: hierarchy + Global Benefit library CRUD

**PHASE:** 2 · **DEPENDS ON:** Task 1 (C2 approved) · **GATE:** none

### GOAL
Apply migration 033 and implement backend CRUD for segments, vehicle categories/subcategories, coverage types, and the Global Benefit library (including match dataset + value-pattern dataset + demo value).

### READ FIRST
1. Universal context block (§1) + `task-00-audit.md` + `task-01-model.md`.
2. `backend/app/services/business_setup_service.py` (conventions: `_require_business`, `_require_revision`, `_audit`, serializers, pagination), `backend/app/api/routes.py` business region, `backend/app/api/schemas.py`.
3. `backend/app/models/tables.py` (BenefitConcept + TimestampMixin patterns), `backend/app/models/enums.py`.

### TARGET BEHAVIOUR
- REST: list/create/update/retire for segments, vehicle categories, vehicle subcategories, coverage types (active-status pattern like companies).
- Global Benefits: CRUD with name, key, description, artwork asset, display template, variable definitions (value_schema/required_variables kept), demo value, match dataset (add/remove words), value-pattern dataset (add/remove patterns), ordering, active state. Business users only.
- Every mutation: optimistic `revision` check (409 on stale), AuditEvent, no hardcoded business values.
- Serializers expose datasets as plain arrays; keep staff-safe responses (no secrets/coordinates).

### DELIVERABLES
- Migration 033 APPLIED via `commands/apply-migrations.ps1` (after C2).
- `backend/app/services/` + `api/routes.py` + `api/schemas.py` additions per conventions; tests in `tests/` (service + HTTP) for CRUD, RBAC, revision conflicts, seed rows present.
- Docs: API-CONTRACT.md (new endpoints), ARCHITECTURE.md (hierarchy), MEMORY.md.

### VERIFICATION
- `python -m pytest -q` green (new tests included); backend starts (`npm run backend`, `/health` Ready); `npx tsc --noEmit` + `npm run build` green; code map current.

---

## Task 3 — Backend: packages, assignments & aliases + draft/publish

**PHASE:** 3 · **DEPENDS ON:** Task 2 · **GATE:** none

### GOAL
Make packages, assignments and aliases first-class backend entities with draft/publish over configuration revisions.

### READ FIRST
1. Universal context block (§1) + `task-00-audit.md` + `task-01-model.md` + `task-02` outputs.
2. `backend/app/services/business_setup_service.py` (catalog publish path — the model to extend), `backend/app/services/catalog_review_service.py` (pin/seed — will change in Task 7, keep interface stable), `backend/app/services/template_revision_service.py` (publish pattern), `backend/app/rendering/render_context.py` (assignment shape it will consume).

### TARGET BEHAVIOUR (per settled §4)
- Migration 034: `benefit_packages` `package_kind` + product linkage; `catalog_offerings` becomes assignment-capable (columns from Task 1); `benefit_aliases` CRUD target; backfill script (NOT run against live data in this task — dry-run only) that maps base→included, optional→addon_option, package_component→bundle_component for EXISTING revisions and reports the plan.
- CRUD: comprehensive packages (create/rename/clone/copy-config/reorder), add-on bundles, assignments (add/remove Global Benefit to product | package | bundle with role, typed value, optional price, display value, order), aliases (scoped).
- Publish: extend the existing catalog publish flow so a published revision freezes packages/assignments/aliases with content hash; identical content publish is idempotent; drafts of packages editable, published revisions immutable.
- Products with zero packages: assignment owner = product. Products with packages: assignments owned by packages; product-level assignments disallowed (or validated) per model.
- No runtime inheritance: clone produces an explicit copy; saving a package always writes its full configuration.

### DELIVERABLES
- Migrations 034–035 (if needed) + dry-run backfill report in `task-03-api.md`.
- Services/routes/schemas for packages, bundles, assignments, aliases, publish; tests (CRUD, RBAC, clone-explicit, publish idempotency, stale 409).
- Docs: API-CONTRACT.md, ARCHITECTURE.md, MEMORY.md; code map.

### VERIFICATION
- `python -m pytest -q` green; backend starts; tsc + build green; code map current.

---

## Task 4 — Admin UI: Global Benefits manager

**PHASE:** 4 · **DEPENDS ON:** Tasks 2, 3 · **GATE:** none

### GOAL
Build the top-level Global Benefits admin page: the one reusable RiskLocker benefit library (name, key, description, artwork, template, variables, demo value, match dataset, value-pattern dataset, ordering, active state).

### READ FIRST
1. Universal context block (§1) + `task-00-audit.md` + tasks 1–3 outputs.
2. `frontend/src/app/builder/benefits/page.tsx` (layout/component conventions: AppShell, BuilderNav, dialog patterns, api/fileUrl), `frontend/src/app/builder/assets/page.tsx` (artwork picker pattern), `frontend/src/components/ui/*`.
3. Target-architecture §13.1 (Global Benefits admin) and §6 (library responsibilities).

### TARGET BEHAVIOUR
- List/search/active-filter of Global Benefits with artwork thumbnails.
- Editor dialog/page: name, stable key, description, artwork (from business assets), customer text template with `{{variable}}` placeholders, variable definitions, demo value (typed), match dataset (tag-editable list of words/phrases), value-pattern dataset (tag-editable list), ordering, active toggle.
- Follow DESIGN-SYSTEM.md rules (Apple-inspired, accessible, 768px+).
- Everything persisted through the Task 2/3 APIs; no client-side business logic.

### DELIVERABLES
- New route + components (e.g. `frontend/src/app/builder/global-benefits/`), nav entry, tests in `tests/test_frontend_*_contract.py` style (page uses the real APIs, no hardcoded benefits), docs (DESIGN-SYSTEM.md if screens change, MEMORY.md), code map.

### VERIFICATION
- tsc + build green; backend pytest green; manual smoke: create a Global Benefit with datasets, edit, deactivate.

---

## Task 5 — Admin UI: Company Configuration workspace

**PHASE:** 4 · **DEPENDS ON:** Tasks 3, 4 · **GATE:** checkpoint C3

### GOAL
Replace the current `builder/benefits` company-first workspace with the full hierarchy navigation and per-product/package configuration editor.

### READ FIRST
1. Universal context block (§1) + tasks 0–4 outputs.
2. `frontend/src/app/builder/benefits/page.tsx` (current 4-column layout to evolve), target-architecture §13.2, §14, §15, §16 (product without packages), §17 (onboarding flow).
3. Business rule: "A product may have zero named packages; the product page itself exposes Included Benefits / Available Add-ons / Add-on Bundles."

### TARGET BEHAVIOUR
- Navigation tree: Company → Segment → Vehicle Category → (Vehicle Subcategory) → Coverage Type → Product → (Comprehensive Packages chain) — DB-driven, no hardcoding.
- At the leaf (product OR package):
  - **Included Benefits** matrix: Global Benefit picker (searchable), role=included, exact typed value editor (money/distance/etc.), optional price, display value, source link, order.
  - **Available Add-ons**: role=addon_option rows with optional price.
  - **Add-on Bundles**: bundle list; each bundle's component assignments (role=bundle_component).
  - **Aliases / Source Mappings**: scoped alias management for this scope.
  - **Publish revision** button; draft vs published state; history list.
- Package editor supports: clone (explicit copy — no runtime inheritance), rename, reorder, value overrides, add/remove assignments.
- Products without packages show the same leaf editor with NO fake package name anywhere in the UI.
- The legacy Our Specials page is untouched in this task (merged later in Task 10).

### DELIVERABLES
- Reworked `builder/benefits` page (or a new builder path with redirect) implementing the above; contract tests; docs (DESIGN-SYSTEM.md, MEMORY.md, STRUCTURE.md if routes change); code map.

### VERIFICATION
- tsc + build green; pytest green; manual smoke: create New Insurer → Private → Car → Comprehensive → Product (no package) with included + add-ons; create Product with Lite/Plus/Premier, clone Plus from Lite, change values, publish; verify no fake base package appears.

### STOP / CHECKPOINT C3
Report what was built, screens summary, and any UX friction found. Wait for owner review before extraction work.

---

## Task 6 — Extraction: scoped alias + value-pattern matching

**PHASE:** 5 · **DEPENDS ON:** Tasks 2, 3 · **GATE:** none

### GOAL
Wire real extraction matching: source lines → scoped alias + match-dataset scoring → Global Benefit candidates → typed exact values via value-pattern dataset. Fix the label-only matching gap.

### READ FIRST
1. Universal context block (§1) + `task-00-audit.md` (extraction findings) + tasks 1–3 outputs.
2. `backend/app/extraction/benefit_lines.py`, `candidate_finder.py`, `backend/app/workers/extraction_worker.py` (`load_extraction_context` — currently loads concepts with empty aliases), `backend/app/extraction/types.py`.
3. Target-architecture §10 (aliases), §20.1 (alias wiring), and the settled §4.1/§4.8 (datasets, scoped aliases).

### TARGET BEHAVIOUR
- `load_extraction_context` loads: Global Benefits with match datasets + value-pattern datasets + demo values; scoped aliases (global → company → product → package, most specific scope wins); companies/products/packages as before.
- `benefit_lines.py`: score lines against match datasets + aliases (substring/token scoring, deterministic tie-break); produce `candidate_mappings` with `global_benefit_id`, matched phrase, scope used, score; still conservative: no confident match → candidate list or none.
- Value typing: use the value-pattern dataset + existing `_typed_value` logic; keep typed values (money/distance/…) + display string; never guess; evidence retained.
- Outputs stay compatible with `ExtractionBenefitLine` columns (extend only if migration 036 needed).

### DELIVERABLES
- Extraction changes + fixtures/regression tests (Scenario F: insurer-specific phrase maps through alias; Scenario C: same benefit different values; unknown phrase stays unresolved). Docs: BUSINESS-RULES.md (alias rule), ARCHITECTURE.md, MEMORY.md; code map.

### VERIFICATION
- pytest green (existing extraction regression suites must stay green); backend starts; tsc/build green.

---

## Task 7 — Upload resolution & base seeding rework

**PHASE:** 5 · **DEPENDS ON:** Task 6 · **GATE:** none

### GOAL
Rework upload-time resolution: hierarchy detection (segment/vehicle/coverage), product/package pinning, seeding of included Benefits from the published configuration, and add-on/bundle resolution — replacing the current tier-only catalog pin path.

### READ FIRST
1. Universal context block (§1) + tasks 0–6 outputs.
2. `backend/app/services/catalog_review_service.py` (`pin_catalog_context`, `seed_base_benefits`, `auto_apply_extracted_benefits`), `backend/app/services/workspace_service.py` (`_reconcile_catalog_pin`, `_apply_pin_catalog`, `_apply_select_catalog_offering`), `backend/app/workers/extraction_worker.py`.
3. Target-architecture §11 (resolution flow), §12 (priority ladder §4.5), §23 (review target), §26 rules.

### TARGET BEHAVIOUR
- Detection chain (deterministic, never guessing): company → segment (from product context/fields, Check Needed if ambiguous) → vehicle category/subcategory (from `vehicle_class` + dictionaries) → coverage type (from `coverage_type` field) → product (aliases/exact) → package (from extracted package/plan wording; skipped when the product has no packages) → pin the latest published configuration revision.
- Seed: every `included` assignment of the pinned product/package becomes a quotation selection (state=current, cost=included unless configured otherwise). `addon_option` assignments are NOT seeded.
- Quotation add-on lines: detected selected add-ons/bundles become selections with cost from config or quotation; individually purchased options land in the **Add-ons** section (never "defaults") (§4.6).
- Add-on bundles selected in the quotation resolve their `bundle_component` assignments into the quotation's Add-ons (one selection per component; bundle name kept as metadata).
- Values: apply the §4.5 ladder — quotation explicit value wins over config unless staff corrected (see Task 8).
- Ambiguous anything → Check Needed / unresolved; existing legacy path (tier-based catalogs) continues to work for old drafts.

### DELIVERABLES
- Reworked pin/seed/auto-apply services (interface-compatible where possible), worker integration, regression + new tests (Scenario A/B/D/E/H). Docs: BUSINESS-RULES.md, ARCHITECTURE.md, API-CONTRACT.md, MEMORY.md; code map.

### VERIFICATION
- pytest green; backend starts; upload smoke via `commands/smoke-test.py` if practical; tsc/build green.

---

## Task 8 — Review workspace & UI: package pinning, source-line resolution, quick custom layer

**PHASE:** 6 · **DEPENDS ON:** Task 7 · **GATE:** none

### GOAL
Give staff a proper review experience: detected hierarchy banner, package pinning, a real unresolved-source-line resolution UI, and the quotation-level quick custom layer.

### READ FIRST
1. Universal context block (§1) + tasks 0–7 outputs.
2. `frontend/src/components/session-workspace/review-phase.tsx` + `provider.tsx` + `types.ts`, `backend/app/services/workspace_service.py` (snapshot + operations), target-architecture §20.2, §23, and the settled §4.9 (quick custom layer).

### TARGET BEHAVIOUR
- Snapshot additions: detected hierarchy (`segment/vehicle/coverage/product/package` + names), pinned configuration revision, unresolved source lines list with dispositions.
- UI:
  - "Detected" banner showing the resolved chain; editable selects to correct any level (each correction re-runs Task 7 resolution deterministically; revision-guarded).
  - **Unresolved source lines panel**: each line shows raw text + page + candidate Global Benefits; actions: map to a Global Benefit (with role included/addon_option), keep source-only, omit, or create a quick custom item. No quotation is ever blocked without an available action (fixes the dead-end).
  - **Benefits / Add-ons boxes**: Benefits = seeded included selections; Add-ons = quotation-selected add-ons + configured add-on options + bundle components; same Global Benefit may appear in both boxes with different exact values (§8/Scenario C).
  - **Quick custom layer**: "Add custom benefit/add-on" + edit value + remove — quotation-only; never writes Global Benefits or configuration; existing `create_custom_benefit`/`benefit_update` ops extended where needed.
- Backend: new/updated workspace operations (`source_disposition` fully usable from UI, `pin_hierarchy`/`select_package`, `promote_custom_benefit` deferred to Task 10 — no promote UI yet).

### DELIVERABLES
- Workspace service + ops + snapshot changes; review UI rework; tests (Scenario G: no invisible dead-end; concurrency; quick-custom isolation). Docs: DESIGN-SYSTEM.md, API-CONTRACT.md, BUSINESS-RULES.md, MEMORY.md; code map.

### VERIFICATION
- pytest green; tsc/build green; manual smoke on a real uploaded quotation: unresolved line → map/omit; custom benefit added and does not appear in Business Setup.

---

## Task 9 — Card resolution & render/snapshot integration

**PHASE:** 7 · **DEPENDS ON:** Tasks 7, 8 · **GATE:** checkpoint C4

### GOAL
Make the final render derive cards from the pinned configuration (roles + typed values + ladder), demote `replaces`-edge logic to legacy-only, and freeze hierarchy/package/revision into the immutable render snapshot.

### READ FIRST
1. Universal context block (§1) + tasks 0–8 outputs.
2. `backend/app/rendering/render_context.py` (`resolve_benefit_cards` — rework), `backend/app/rendering/template_renderer.py` (grids), `backend/app/services/generation_service.py` (snapshot), `backend/app/workers/render_worker.py`.
3. Target-architecture §4, §8, §12, §20.6, §25 (revisioning), and the settled §4.3/§4.5/§4.7.

### TARGET BEHAVIOUR
- Card resolution (new canonical path): pinned configuration revision → assignments (product/package/bundle) → selections; Benefits = current selections from `included` assignments; Add-ons = `addon_option` selections + selected bundle components (deduplicated by Global Benefit where the same benefit is base + enhanced add-on: BOTH cards shown, one per box, distinct exact values).
- Typed values preserved end-to-end (money/distance/Unlimited…); `format_benefit_value` unchanged in spirit.
- Value ladder applied at render: staff override → quotation exact → selected package/add-on config → base config → Check Needed (blocker).
- Legacy revisions (old catalogs with `replaces` edges, tier-based) still resolve through the old compatibility path — never fail old drafts.
- Generation snapshot now freezes: hierarchy ids + names, product/package ids, pinned configuration revision id + hash, resolved card list, renderer version. Old versions untouched.
- `package_component`/bundle components now produce final cards (fixes §20.4).

### DELIVERABLES
- `render_context` + `generation_service` changes with tests (Scenarios B, C, E, H, I: different packages, base+enhanced same benefit, bundles, historical stability); docs (ARCHITECTURE.md, BUSINESS-RULES.md, MEMORY.md); code map.

### VERIFICATION
- pytest green (legacy render tests must stay green); tsc/build green; generate a PDF from a package-pinned quotation and a legacy-tier quotation — both render.

### STOP / CHECKPOINT C4
Report pipeline status + render samples; wait for owner review before legacy unification.

---

## Task 10 — Legacy unification: Our Specials merge, offerings backfill, tier compat

**PHASE:** 8 · **DEPENDS ON:** Task 9 · **GATE:** none (destructive steps need explicit owner approval within this task)

### GOAL
End the two-active-systems state: migrate/normalize Our Specials into Global Benefits + configuration, backfill existing catalog offerings into the assignment model, keep tiers/old revisions readable, and set the deprecation policy.

### READ FIRST
1. Universal context block (§1) + `task-00-audit.md` (Our Specials + backfill findings) + tasks 0–9 outputs.
2. `backend/app/services/trash_service.py` (Our Specials lifecycle), `backend/app/services/v7_backfill.py` (backfill conventions — idempotent, report-only where destructive), `frontend/src/app/builder/our-specials/page.tsx`, `backend/app/services/compatibility_service.py`.

### TARGET BEHAVIOUR (per settled §4.8)
- Backfill (dry-run first, then apply on approval): existing `our_specials`/`our_special_variants` rows → Global Benefits (where they represent a real reusable concept; label/artwork/values preserved) + configuration assignments; collisions reported, never silently merged. FOC/Add-on classification is NOT stored on the Global Benefit (role belongs to configuration).
- Catalog offerings backfill: existing revisions get `applies_to_type`/`role` populated from `offering_kind` mapping (base→included, optional→addon_option, package_component→bundle_component); `upgrade` offerings remain readable on legacy revisions.
- Tier compat: `insurance_product_tiers` stays readable; new work uses packages; legacy drafts keep pinning old revision ids.
- Deprecation: Our Specials page becomes read-only with a "migrated to Global Benefits" notice; write endpoints return a clear 410-style error (or are hidden from nav) AFTER the backfill is approved and verified. Nothing is deleted.
- Quick custom → promote: implement the admin "promote custom benefit to Global Benefits" action (optional selections from quotations become draft Global Benefits).

### DELIVERABLES
- Backfill scripts + reports; deprecation wiring; tests (idempotency, collision report, legacy readability, old version stability); docs (BUSINESS-RULES.md, STRUCTURE.md, ARCHITECTURE.md, MEMORY.md); code map.

### VERIFICATION
- pytest green; old generated PDF versions unchanged (spot-check via download endpoint); tsc/build green.

---

## Task 11 — Test suite + acceptance scenarios A–J

**PHASE:** 9 · **DEPENDS ON:** Task 10 · **GATE:** none

### GOAL
Comprehensive regression + acceptance coverage for the whole refactor.

### READ FIRST
1. Universal context block (§1) + all task outputs 0–10.
2. `docs/TESTING.md` (strategy/conventions), target-architecture §27 (acceptance scenarios), prompt §9 (testing list).

### REQUIRED COVERAGE (from the planning brief + scenarios A–J)
- New insurer end-to-end without code change (A).
- Product with no named package (B-part1 / §16).
- Lite/Plus/Premier with different exact values, same Global Benefits (B / C / D).
- Same TOWING: base included + enhanced purchased add-on in one quotation (C / E).
- Motorcycle and commercial vehicle configs — no private-car leakage (D / E / F).
- Alias mapping incl. scoped aliases (F / G).
- Unresolved source-line manual resolution with no dead-end (G).
- Add-on bundle component resolution into Add-ons (H).
- Historical revision immutability + old generated version stability (I / J).
- Value priority ladder (§4.5) incl. staff correction wins.
- Optimistic concurrency (409s), RBAC, publish idempotency.
- Migration/backfill idempotency + ledger discipline; Our Specials migration reports.
- Frontend contract tests for every new/changed page.

### DELIVERABLES
- New/extended test files; `docs/TESTING.md` coverage table updated; MEMORY.md.

### VERIFICATION
- `python -m pytest -q` fully green; `npx tsc --noEmit`; `npm run build`; code map current.

---

## Task 12 — Certification run + docs finalisation

**PHASE:** 9 · **DEPENDS ON:** Task 11 · **GATE:** checkpoint C5

### GOAL
Full certification: complete test run, production build, backend start, E2E smoke in `.qc-tmp/`, acceptance checklist sign-off, and final doc reconciliation.

### READ FIRST
1. Universal context block (§1) + all task outputs.
2. `docs/TESTING.md`, `docs/OPERATIONS.md`, `commands/test-all.ps1`, `.qc-tmp/` E2E runbook.

### STEPS
- `npm run test` (pytest + build) fully green; `npx tsc --noEmit`; `npm run code-map:check`.
- Backend + frontend up; run the `.qc-tmp` E2E scripts (builder + a new upload→review→generate flow script if present); verify a generated PDF downloads.
- Walk the acceptance checklist A–J (mark evidence per scenario, file:line or test name).
- Reconcile all docs (BUSINESS-RULES, ARCHITECTURE, API-CONTRACT, DESIGN-SYSTEM, TESTING, OPERATIONS, STRUCTURE, MEMORY, code map).

### DELIVERABLES
- `task-12-certification.md` with the A–J evidence table + test counts + any residual gaps.
- MEMORY.md baseline update.

### STOP / CHECKPOINT C5
Report certification results. Wait for owner sign-off. Do NOT start Task 13 without it.

---

## Task 13 — AI-assisted draft seeding from the reference DOCX (LAST)

**PHASE:** 10 · **DEPENDS ON:** Task 12 (C5 signed) · **GATE:** none — seeding creates DRAFT/UNPUBLISHED data only

### GOAL
Use the verified reference (`fix/RiskLocker_Malaysia_Motor_Comprehensive_Packages_Benefits_Addons_2026.docx`) to seed Global Benefits, hierarchy, products, packages and assignments as **draft configuration** for the known insurers — reviewable and publishable by staff/admin, never auto-published.

### READ FIRST
1. Universal context block (§1) + all task outputs 0–12.
2. `commands/import-reference-docx.py` (reference intake pattern), `backend/app/services/reference_intake.py`, `backend/app/services/v7_backfill.py` (idempotent apply conventions), target-architecture §18 (AI seeding last), §17 (onboarding workflow).

### TARGET BEHAVIOUR
- Read the DOCX (owner-private, gitignored — never commit its content).
- Build a seeding plan (dry-run report): Global Benefits (from the library section), segments/vehicles/coverage paths, products, packages (incl. level-1 "base" naming per the document), assignments with exact typed values from the document (RM300 money, 50 km distance, Unlimited… — preserve exactly; never convert).
- Apply as DRAFT/unpublished configuration only; publish requires a human.
- Collisions/uncertainties reported, never silently guessed; nothing overwrites existing published configuration.
- Output: seeding scripts + report; MEMORY.md.

### VERIFICATION
- Seeding plan dry-run reviewed; applied rows are all draft; pytest green; admin can review/edit/publish in the UI.

### STOP
Report the seeded scope and pending insurer coverage. The refactor is complete when the owner signs off.

---

# §4 DECISION REGISTER — settled 2026-08-16, never re-ask

1. **Global Benefit = full reusable presentation object** on evolved `benefit_concepts`: name, description, artwork/icon, customer text template, variable definitions, demo value — PLUS a match-word/alias dataset and a value-pattern dataset for extraction. Matching aliases/patterns scopeable by company/product/package when needed; different insurer styles never create duplicate Global Benefits.
2. **Hierarchy**: Company → Segment (Private / Company-Commercial) → Vehicle (Car / Motorcycle / Commercial Vehicle + optional subtypes Lorry/Van/Bus) → Coverage (Comprehensive / TPFT / Third Party) → Product → Package chain. Normally simple; scalable; defaults seeded by migration; companies choose which apply.
3. **Packages**: one entity, `package_kind` = comprehensive package chain | addon_bundle. **No invented mandatory "base" package** — products with no named packages own Benefits/Add-ons directly (`applies_to_type=product`). **No runtime package inheritance** — UI clone is a convenience; after save every package has an explicit resolved configuration; package selection determines the exact benefit set.
4. **Assignments**: keep + simplify `catalog_offerings` (no parallel table): global_benefit + `applies_to_type` (product|package|bundle) + `applies_to_id` + `role` (included|addon_option|bundle_component) + `exact_value` + `optional_price`. Mapping: base→included, optional→addon_option, package_component→bundle_component. Upgrade edges demoted to legacy-only; package selection is the plan-level mechanism.
5. **Value priority ladder**: Staff correction → exact quotation value → selected package/add-on configured value → base product/package configured value → Check Needed. Never infer/convert.
6. **Add-ons placement**: individually purchased options detected from a quotation belong in the final **Add-ons** section — never "defaults". A benefit enters **Benefits** only when the exact product/package includes it automatically.
7. **Typed values preserved**: exact_value keeps the typed-value architecture + customer-facing display value (RM300 = money; 50 km = distance; Unlimited = typed). No string flattening.
8. **Our Specials merged, not kept parallel**: one authoritative Global Benefits system; existing data preserved and migrated/normalized (FOC/Add-on is never stored on the Global Benefit — role belongs to configuration); quotation-level quick custom layer stays quotation-only unless an admin promotes it.
9. **Seed data**: migration 033 seeds segments, vehicle categories/subcategories, coverage types as scalable, properly-inputted rows.

---

# §5 ACCEPTANCE CHECKLIST (final validation, from the planning brief)

| # | Scenario | Evidence expected |
|---|---|---|
| A | New insurer onboarded from admin with zero code changes | Task 5/11/12 |
| B | Private → Car → Comprehensive → Product with no named package, configured Benefits/Add-ons | Tasks 5, 7, 11 |
| C | Product with Lite/Plus/Premier, same global benefits, different exact values | Tasks 3, 5, 9, 11 |
| D | One TOWING benefit/icon/template everywhere | Tasks 1, 2, 4, 9 |
| E | TOWING included in one package and enhanced add-on in another; both boxes render the same concept with different values | Tasks 8, 9, 11 |
| F | Motorcycle / Commercial Vehicle configured without private-car leakage | Tasks 5, 7, 11 |
| G | Many insurer phrases → one Global Benefit via (scoped) aliases | Tasks 6, 11 |
| H | Add-on bundle selected → components resolve into final Add-ons | Tasks 7, 9, 11 |
| I | Staff have a visible resolution path for uncertain extracted benefit lines | Task 8, 11 |
| J | Future package revision change never alters old generated versions | Tasks 9, 10, 12 |
