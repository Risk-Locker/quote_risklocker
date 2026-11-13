# Testing

## Test Coverage

| Area | Coverage location |
| --- | --- |
| Configuration and required secure settings | `tests/test_backend_config.py`, `tests/test_config.py` |
| Extraction and deterministic rendering | `tests/test_extraction_pipeline.py`, `tests/test_extraction_regression.py` |
| Upload and PDF hardening | `tests/test_hardening.py` |
| Private PDF storage, byte ranges, and retention | `tests/test_pdf_storage.py` |
| Temporary password policy, session rolling/expiry/revocation, production dev denial, bootstrap, browser-storage regression | `tests/test_security.py` |
| Authentication HTTP contract, secure cookie, login/logout, revoked and disabled sessions | `tests/test_auth_http.py` |
| Notifications, invitations, role/status notices, recipient isolation, mark-read, and Admin mail test RBAC | `tests/test_notifications.py` |
| Lifecycle mutation safety, headers, CSRF, trusted proxies, and durable rate limits | `tests/test_app_lifecycle.py`, `tests/test_http_security.py`, `tests/test_rate_limits.py` |
| Harness integrity, freeze guards, path containment, and AST tripwire scanners | `tests/harness/test_freeze_and_path_guard.py`, `tests/harness/test_security_audit_and_tripwire.py` |
| Security boundaries, RBAC route gating, hermetic storage mocks, and open exploit reproducers | `tests/security/test_security_boundaries.py`, `tests/security/test_p0_open_exploits.py` |
| PostgreSQL schema contracts, index integrity, and migration replay (opt-in live runner) | `tests/security/test_postgres_schema_contracts.py` |
| Migration ordering, checksums, drift, and readiness, incl. CRLF/LF normalization and historical (CRLF-bytes) ledger acceptance | `tests/test_migration_runner.py` |
| Alias-aware insurance company resolution (AMGEN/AmGeneral/AM General Insurance Berhad/Kurnia/auto365 → AmAssurance; no false positives on AmBank etc.) | `tests/test_company_resolution.py` |
| Package tiers: multi-package revision resolution, `select_package_tier` op, tier-scoped seeding with `draft.package_id`, rename endpoint, tier add-on scoping, stale seed fallback | `tests/test_package_plans.py`, `tests/test_benefit_setup_api.py`, `tests/test_catalog_review_initialization.py` |
| Shared Staff quotation/customer access | `tests/test_shared_access.py` |
| Immutable template publication, fixed profiles, template switching, and dynamic-grid schema/rendering | `tests/test_template_publication.py`, `tests/test_template_revision_validation.py`, `tests/test_dynamic_grid_renderer.py`, `tests/test_workspace_service.py` |
| Builder publication/gesture and Check Values integration contract | `tests/test_frontend_template_publication_contract.py`, `tests/test_frontend_workspace_contract.py` |

## Commands

- Run the full repository check with `npm run test`. It runs backend pytest coverage and the frontend production build.
- Run the code-map validation with `npm run code-map:check`.
- Run the smoke workflow with `./.venv/Scripts/python.exe commands/smoke-test.py` when exercising configured local services.
- Backend suite only: `.\.venv\Scripts\python.exe -m pytest -q` from the repo root (default offline hermetic suite).
- PostgreSQL schema suite (live runner opt-in): `$env:RL_TEST_POSTGRES_URL="postgresql://..."; .\.venv\Scripts\python.exe -m pytest -q tests/security/test_postgres_schema_contracts.py`.
- Dev toolchain:
  - Ruff lint: `.\.venv\Scripts\python.exe -m ruff check backend/app pyproject.toml`
  - Bandit security scan: `.\.venv\Scripts\python.exe -m bandit -r backend/app -q`
  - Mypy static typing: `.\.venv\Scripts\python.exe -m mypy backend/app/services/road_tax_engine.py backend/app/services/formula_evaluator.py backend/app/rendering/pdf_generator.py`
  - Dependency vulnerability scan: `.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt`
  - Frontend ESLint 9 Flat Config: `npm.cmd run lint` (inside `frontend/`, non-interactive)
  - Playwright E2E responsive & a11y: `npm.cmd run test:e2e:ci` (inside `frontend/`)
- `tests/conftest.py` bootstraps `.qc-tmp/pytest` (the `--basetemp` from `pytest.ini`) at import time — pytest 7.x creates the basetemp with `Path.mkdir()` without parents, so the parent `.qc-tmp` must exist first, especially on clean checkouts and CI runners.
- `tests/fixtures/RiskLocker_Malaysia_Motor_Comprehensive_Packages_Benefits_Addons_2026.docx` is the tracked reference DOCX fixture for `tests/test_reference_docx_intake.py` (owner intake stays `unverified`, never catalog truth).
- The CI test job installs Playwright Chromium so `test_pdf_generation_smoke` runs instead of skipping.
- Frontend static: `npx tsc --noEmit` and `npm run build` in `frontend/`.

## Pre-Commit & Pre-Push Verification Gate (deploy.yml Parity)

Whenever the owner or user prompts to **commit**, **push** (e.g. to `origin main`, `origin v18`, `origin v19`, or any branch), or **create and publish** a new branch:

> [!CAUTION]
> **NEVER touch git or execute `git commit` / `git push` immediately.**
> The agent must run the pre-deployment verification check first to guarantee that the GitHub Actions workflow (`.github/workflows/deploy.yml`) and VPS deployment pass with 100% certainty.

### Verification Checklist Before Git Commit / Push:
1. **Automated Verification Script (`10/10` Pre-Deploy Gate):**
   `.\commands\verify-deploy-gate.ps1` (add `-LiveDb` when checking against a reachable database, or `-RequireExternal` to require `pip-audit`/`bandit`)
   Steps `[1/10]`–`[3/10]` mirror `.github/workflows/deploy.yml` directly; steps `[4/10]`–`[10/10]` enforce local migration, Knowledge Base, bridge, skill-vault, SAST, and Harness gates queued for Phase B CI parity:
   - `[1/10]` Backend pytest under sealed dummy CI environment (`DATABASE_URL=postgresql://postgres:ci@db.ci.supabase.co:5432/postgres?sslmode=require`).
   - `[2/10]` Frontend `tsc --noEmit` with zero type errors.
   - `[3/10]` Frontend `npm run build` compiling all routes cleanly.
   - `[4/10]` Offline hermetic migration integrity (`001..N` contiguous, regex naming, SHA-256 checksums; `-LiveDb` runs live `verify_schema_version()`).
   - `[5/10]` Codebase map freshness (`update-code-map.py --check`).
   - `[6/10]` Project Knowledge Base integrity (`verify-brain.py`).
   - `[7/10]` Cross-IDE universal bridges sync (`sync-agent-bridges.py --check`).
   - `[8/10]` Agent Skills Vault hygiene & lockfile parity (`skills-manager.py doctor --check`).
   - `[9/10]` Automated SAST, RBAC, Middleware, Storage & PII scan (`commands/security-audit.py --strict --with-external`) + clean `.agents/logs/tripwire-alerts.log`.
   - `[10/10]` Daily Harness Freshness Radar (`python .agents/hooks/daily_radar.py --offline --dry-run --strict`).
2. **Hermetic Test Rule:**
   All unit and regression tests in `tests/` MUST be 100% hermetic (in-memory SQLite or mocks). Tests must NEVER instantiate `SessionLocal()` or attempt live network database connections, ensuring tests can never pollute or mutate production data.
3. **Zero IDE / Diagnostics on Changed Files:**
   All diagnostic errors, type warnings, or lint issues on modified files must be cleared.

If **any** check fails, **stop immediately**. Do not commit, do not push, and do not publish. Fix the issue, re-run the verification pipeline until fully green, and only then proceed with git operations.


## Browser E2E (in-repo QA tooling)

- Scripts live in `/.qc-tmp/` (gitignored): `groups3-e2e.js` (builder group/marquee E2E), `marquee-probe.js` (marquee diagnostics). Run with `node .qc-tmp/<script>.js` while backend :8100 and frontend :3000 are up. Playwright comes from `frontend/node_modules`; screenshots go to `.qc-tmp/shots/`. See OPERATIONS.md for the full runbook.
- Verified baseline 2026-08-10: `groups3-e2e.js` green — marquee selects 3 added texts, group "Group (3)" with nested children, group drag moves members (dx=78 dy=37), ungroup removes the named group.

## Verified Baseline

On 2026-08-21 after the clean-runner fix (conftest `.qc-tmp/pytest` bootstrap, tracked DOCX fixture, CI Chromium install): 498 passed, 0 skipped, 0 errors, `npx tsc --noEmit` clean, Next.js production build green, code map current. Re-run the final checks after any subsequent code or generated-map change.

## Known Coverage Gaps

- Authentication has focused HTTP route coverage, but non-authentication routes still lack broad HTTP/RBAC integration coverage.
- Browser E2E exists only for the template builder (groups/marquee); login, upload, review, generation, history, trash, and admin flows still lack E2E scripts.
- CI/CD: `.github/workflows/deploy.yml` runs backend pytest + frontend `tsc --noEmit` + `next build` on GitHub, then deploys to the VPS on push to `main` (see [SETUP.md](SETUP.md)).
- The existing suite is valuable unit/regression coverage, but a passing result does not prove production deployment controls, browser behavior, or full authorization paths.

## Change Expectations

- Use focused tests for the subsystem changed, then run the required build or end-to-end check proportionate to risk.
- Add only anonymized, deterministic fixtures under `tests/fixtures/` for extraction regressions.
- Never depend on private customer PDFs, external process folders, generated PDFs, caches, or runtime secrets in tests.
- The two owner-material tests in `tests/test_reference_docx_intake.py` run unconditionally against the tracked fixture `tests/fixtures/RiskLocker_Malaysia_Motor_Comprehensive_Packages_Benefits_Addons_2026.docx` (previously skipped when the private owner DOCX was absent from the working tree).
- Update tests when API behavior, extraction behavior, security validation, rendering behavior, storage behavior, or business rules change.
