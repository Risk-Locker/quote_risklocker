# Architecture

## v7 Delivery Boundary

Risklocker v7 uses one HTTPS origin. Coolify routes `/` to Next.js and `/api` to FastAPI. The browser never falls back to a direct backend port. FastAPI plus one bounded extraction/render worker use Supabase/Postgres as the source of truth, private Supabase Storage, and a Postgres-backed job queue. Core delivery may include a disabled/test/Resend mail-provider boundary, but authentication redesign, OTP use, onboarding, and live Resend activation remain blocked until owner approval.

The selected immutable template revision owns a fixed page profile. A benefit grid recomputes rows and columns for every count and uniformly shrinks every card inside fixed bounds. Benefit count never extends or paginates the page. A longer page is a separate template page profile and revision.

Template configuration distinguishes renderable shapes from hierarchy. A visible rectangle is a shape; a layer group is a non-rendering node that owns ordering, nesting, visibility, and lock state. Legacy `group` elements remain readable through deterministic conversion and compatibility adapters.

## Benefits Hierarchy and Global Benefits (refactor, Tasks 1–2 complete)

The benefits refactor adds database-driven hierarchy dimensions — `segments` (Private, Company/Commercial), `vehicle_categories` (Car, Motorcycle, Commercial Vehicle), `vehicle_subcategories` (Lorry/Truck, Van, Bus), `coverage_types` (Comprehensive, TPFT, Third Party) — seeded by migration 033 and admin-extendable. `benefit_concepts` evolves into the Global Benefit library (description, typed demo value, match-word dataset, value-pattern dataset, ordering). `benefit_aliases` carries scoped phrases (global | company | product | package) → Global Benefit for extraction. The hierarchy is configuration, never hardcoded benefit assumptions: a benefit applies only when a product/package configuration assigns it (Tasks 3–9 extend `benefit_catalogs`/`catalog_offerings`). Services: `backend/app/services/benefit_setup_service.py` (hierarchy + alias CRUD + packages); concepts/offerings/publish stay in `business_setup_service.py`.

## Packages and Benefit Assignments (Task 3 complete)

Packages are first-class: `benefit_packages` rows live on a catalog's draft revision with `package_kind` (`comprehensive` chain | `addon_bundle`); the first comprehensive package becomes the catalog's `package_id` target (one per catalog; bundles attach to a packaged catalog). `catalog_offerings` is the Benefit Assignment: global benefit + `applies_to_type` (product | package | bundle) + `applies_to_id` + `role` (included | addon_option | bundle_component) + typed exact value + optional price + display value; legacy rows (kind base/optional/upgrade/package_component, `replaces` relations) remain readable. Products with no named packages own product-level assignments directly — no invented package. Cloning a package copies its assignments as explicit independent rows — no runtime inheritance. Published catalogs reopen through `POST /business/catalogs/{id}/new-draft` (copy-forward, packages re-created and re-linked). The publish content hash freezes offerings + packages + package-scoped aliases. Backfill (`commands/backfill-assignments.py`) maps base→included, optional→addon_option, package_component→bundle_component on draft revisions only (published rows are immutable; apply deferred to Task 10).

Template Builder saves an optimistic mutable draft in `output_template_configs`. Publication row-locks that draft, validates page geometry and dynamic-grid schema, resolves an explicit page profile, removes legacy insurer identity from the snapshot, and writes an immutable `template_revisions` row. Check Values lists the latest published revision per active template, previews switch impact, and persists the confirmed exact revision through the canonical workspace operation queue. A switch never reuses a layout override from another revision.

## System Boundaries

| Layer | Responsibility | Location |
| --- | --- | --- |
| Frontend | Upload, review workspace, business setup, template/session editors, records | `frontend/src/` |
| API | Typed HTTP contracts, authentication, capabilities, authorization | `backend/app/api/` |
| Services | Catalogs, review decisions, jobs, render context, audit, manual purge | `backend/app/services/` |
| Extraction | Native/OCR reading, layout, company/product resolution, benefit lines | `backend/app/extraction/` |
| Rendering | One deterministic HTML/preview/PDF pipeline | `backend/app/rendering/` |
| Data | SQLAlchemy models and ordered Postgres migrations | `backend/app/models/`, `migrations/` |
| Storage | Authorized private Supabase objects and derivatives | `backend/app/storage/` |

## Core Data Flow

1. An authenticated Staff user uploads exactly one PDF with an idempotency key.
2. API transactionally records upload, quotation session, and durable job; a worker validates/scans/extracts it.
3. Extraction persists source lines and candidates without treating them as reviewed truth.
4. The canonical session workspace stores explicit scalar and benefit decisions at an optimistic revision.
5. Staff explicitly choose a published template revision; the workspace clears incompatible quotation layout state and pins that exact revision.
6. Preview and generation build one immutable render context from the exact saved revision and pinned catalog/template revisions.
7. Generated PDFs and render snapshots remain immutable and private until manual reference-aware deletion.

## Security and Database Model

- `APP_ENV` is a strict `local|test|staging|production` enum. Production requires HTTPS, exact trusted hosts/proxies, secure cookies, and malware scanning; `dev` sessions are rejected.
- Central middleware enforces trusted hosts, allowed mutation origins, session-bound CSRF, Postgres rate limits, and response security headers.
- Production serves only `/api`; OpenAPI UI and root compatibility routes are disabled.
- Web startup verifies database connectivity, the checksum migration ledger, and private storage. It never creates schema, seeds rows, resets credentials, or starts deletion jobs.
- Migrations are content-hashed, ledgered, transactionally applied, and serialized by advisory lock. RLS and Data API revocation cover application tables and future default privileges.
- Primary Admin bootstrap is interactive, transaction-locked, one-time, and constrained to one `super_admin` row.
- Staff, Admin, and Primary Admin share quotation/customer records. Capabilities distinguish business setup from security/user operations; the backend remains authoritative.
- Current password login is temporary but protected. OTP/onboarding is WP13 and Resend is WP14 only after core approval.

## Storage and Compatibility

- Supabase/Postgres and private Supabase Storage remain authoritative.
- Source objects use `source/{year}/{month}/{session_id}/{file_id}.pdf`; generated objects use `generated/{year}/{month}/{draft_id}/{version_id}.pdf`.
- Source/generated PDFs do not auto-expire. Trash has no automatic purge.
- Legacy drafts, templates, manual specials, batches, and versions remain readable through compatibility adapters until reference scans prove safe retirement.

For externally observable behavior see [API-CONTRACT.md](API-CONTRACT.md). For deployment configuration see [OPERATIONS.md](OPERATIONS.md).
