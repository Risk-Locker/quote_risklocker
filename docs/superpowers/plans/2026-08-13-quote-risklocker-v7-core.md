# Quote Risklocker v7 Core Implementation Plan

Checkpoint 2026-08-14: the bounded WP7/WP8 connection is implemented—immutable Builder publication, fixed A4/custom profiles, dynamic-grid controls/scenarios, published-revision selection with confirmed impact, exact layout reset/pinning, and the canonical renderer/version pipeline. Work pauses here by owner request; this checkpoint does not approve or begin WP6 expansion, WP9+, authentication, or Resend.

> **For agentic workers:** Implement each work package test-first and stop after the core acceptance checkpoint. Authentication redesign and Resend remain blocked until the owner explicitly approves WP12.

**Goal:** Deliver the production-ready core quotation workflow, catalog, assets, templates, deterministic renderer, records, security baseline, operations, and release gates defined in the owner-approved v7 plan.

**Architecture:** Next.js uses one same-origin `/api` surface backed by FastAPI, Supabase/Postgres, private Supabase Storage, and a Postgres-leased heavy-job worker. Catalog and template data are immutable revisions pinned by each quotation; generation resolves one immutable render-context snapshot.

**Tech stack:** Next.js 15/React 19/TypeScript, FastAPI/Pydantic/SQLAlchemy, PostgreSQL/Supabase Storage, Playwright/Chromium, pytest, and Coolify-managed Linux containers.

## Global Constraints

- Preserve `Upload -> Check Values -> Preview / Generate PDF`; new uploads contain exactly one PDF.
- Companies, products, benefits, aliases, packages, upgrades, and extraction rules are data, with no fixed insurer count.
- Templates are insurer-independent and use fixed page profiles; benefit cards uniformly shrink inside fixed grid bounds as count grows.
- Never infer uncertain values, benefits, catalog facts, product tiers, upgrade order, or cost state.
- Source and generated PDFs remain until manual deletion; automatic PDF expiry and automatic trash purge are disabled.
- Existing drafts, templates, assets, and generated versions remain readable through compatibility paths.
- Core support begins at 768px; canvas editing begins at 1024px with pointer and keyboard.
- Do not implement authentication redesign or Resend before the owner approves the completed core system.
- Do not commit or push unless the owner explicitly asks.

## Execution Checklist

- [ ] **WP0 — Contract and regression baseline:** reconcile canonical documentation, preserve the dirty worktree, create anonymized fixtures, and encode every confirmed issue as a failing behavioral test before its fix.
- [ ] **WP1 — Security and database foundation:** strict environment validation, same-origin/API security, CSRF, limits, read-only startup, safe Primary Admin bootstrap, canonical authorization, migration ledger/lock, and RLS/revokes.
- [ ] **WP2 — Additive schema and compatibility:** revisioned catalog/template/selection/job/audit/render tables, optimistic concurrency, revision pinning, idempotent dry-run backfill, legacy adapters, and manual-only retention.
- [ ] **WP3 — Assets and verified catalogs:** validate the supplied source set, create a stable manifest and derivatives, import the DOCX as unpublished reference data, model provenance/product tiers/packages/facets/upgrades, and retire old assets only after reference analysis.
- [ ] **WP4 — Upload/jobs/extraction:** one-file uploads, durable leased jobs, bounded worker, validation/scanning/reconciliation, native-first extraction, functioning OCR fallback, database-driven company resolution, and structured benefit-line extraction.
- [ ] **WP5 — Canonical workspace:** persistent session provider, lazy resources, explicit field/benefit decisions, impact previews, optimistic saves, navigation guards, valid layout hydration, and complete recoverable states.
- [ ] **WP6 — Business Setup:** paginated company/product/catalog/benefit/asset/source management, typed variables, publication/revision history, safe import/export, detection testing, and compatibility visibility.
- [ ] **WP7 — Templates and grids:** immutable template revisions, fixed A4/custom profiles, procedural current-benefit/add-on grids, uniform shrink behavior through 1,000 cards, scenario validation, constrained session editing, and reliable pointer/history/keyboard behavior.
- [ ] **WP8 — Deterministic generation:** one render-context builder, preview/PDF parity, pinned Chromium, no fallback PDF, exact-revision idempotency, immutable snapshots, stale-version state, caching, privacy, and persistent binaries.
- [ ] **WP9 — Records/audit/operations:** shared Staff records, scalable filters/bulk actions, reference-aware purge, immutable audit events, real operational health, and separately locked maintenance.
- [ ] **WP10 — UX/accessibility/performance:** semantic primitives, focus/reduced-motion/live-region rules, tablet/desktop behavior, fallbacks, working-edit resilience, performance optimization, smoke repair, and production-like budgets.
- [ ] **WP11 — Runtime/release/DR:** pinned Linux services, Coolify topology, readiness/liveness, redacted telemetry/alerts, checked-in CI and E2E, backups, restore/rollback drills, and runbooks.
- [ ] **WP12 — Core acceptance:** close I-01 through I-27, run every automated and operational gate, obtain template/workflow owner approval, and stop before auth/Resend.

## Test-First Rule

For every runtime behavior: write a focused test naming the production break, run it and confirm the expected failure, implement the minimum behavior, rerun the narrow test, then run the affected suite. Complete the repository-wide verification chain only after each work package's narrow checks are green.

## Final Core Verification

```powershell
$env:TEMP=(Resolve-Path '.qc-tmp').Path
$env:TMP=$env:TEMP
.\.venv\Scripts\python.exe -m pytest -q
Set-Location frontend
npx.cmd tsc --noEmit
npm.cmd run build
npx.cmd playwright test --reporter=list
Set-Location ..
.\.venv\Scripts\python.exe commands\update-code-map.py --write
.\.venv\Scripts\python.exe commands\update-code-map.py --check
```

Production certification additionally requires fresh/upgrade migration tests, RLS denial tests, asset/backfill idempotency, accessibility scans, load/soak checks, and documented staging backup/restore/rollback drills.
