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
| Migration ordering, checksums, drift, and readiness, incl. CRLF/LF normalization and historical (CRLF-bytes) ledger acceptance | `tests/test_migration_runner.py` |
| Alias-aware insurance company resolution (AMGEN/AmGeneral/AM General Insurance Berhad/Kurnia/auto365 → AmAssurance; no false positives on AmBank etc.) | `tests/test_company_resolution.py` |
| Shared Staff quotation/customer access | `tests/test_shared_access.py` |
| Immutable template publication, fixed profiles, template switching, and dynamic-grid schema/rendering | `tests/test_template_publication.py`, `tests/test_template_revision_validation.py`, `tests/test_dynamic_grid_renderer.py`, `tests/test_workspace_service.py` |
| Builder publication/gesture and Check Values integration contract | `tests/test_frontend_template_publication_contract.py`, `tests/test_frontend_workspace_contract.py` |

## Commands

- Run the full repository check with `npm run test`. It runs backend pytest coverage and the frontend production build.
- Run the code-map validation with `npm run code-map:check`.
- Run the smoke workflow with `./.venv/Scripts/python.exe commands/smoke-test.py` when exercising configured local services.
- Backend suite only: `.\.venv\Scripts\python.exe -m pytest -q` from the repo root.
- `tests/conftest.py` bootstraps `.qc-tmp/pytest` (the `--basetemp` from `pytest.ini`) at import time — pytest 7.x creates the basetemp with `Path.mkdir()` without parents, so the parent `.qc-tmp` must exist first, especially on clean checkouts and CI runners.
- `tests/fixtures/RiskLocker_Malaysia_Motor_Comprehensive_Packages_Benefits_Addons_2026.docx` is the tracked reference DOCX fixture for `tests/test_reference_docx_intake.py` (owner intake stays `unverified`, never catalog truth).
- The CI test job installs Playwright Chromium so `test_pdf_generation_smoke` runs instead of skipping.
- Frontend static: `npx tsc --noEmit` and `npm run build` in `frontend/`.

## Browser E2E (in-repo QA tooling)

- Scripts live in `/.qc-tmp/` (gitignored): `groups3-e2e.js` (builder group/marquee E2E), `marquee-probe.js` (marquee diagnostics). Run with `node .qc-tmp/<script>.js` while backend :8100 and frontend :3000 are up. Playwright comes from `frontend/node_modules`; screenshots go to `.qc-tmp/shots/`. See OPERATIONS.md for the full runbook.
- Verified baseline 2026-08-10: `groups3-e2e.js` green — marquee selects 3 added texts, group "Group (3)" with nested children, group drag moves members (dx=78 dy=37), ungroup removes the named group.

## Verified Baseline

On 2026-08-21 after the clean-runner fix (conftest `.qc-tmp/pytest` bootstrap, tracked DOCX fixture, CI Chromium install): 498 passed, 0 skipped, 0 errors, `npx tsc --noEmit` clean, Next.js production build green, code map current. Re-run the final checks after any subsequent code or generated-map change.

## Known Coverage Gaps

- Authentication has focused HTTP route coverage, but non-authentication routes still lack broad HTTP/RBAC integration coverage.
- Browser E2E exists only for the template builder (groups/marquee); login, upload, review, generation, history, trash, and admin flows still lack E2E scripts.
- CI/CD: `.github/workflows/deploy.yml` runs backend pytest + frontend `tsc --noEmit` + `next build` on GitHub, then deploys to the VPS on push to `main` (see `docs/SETUP.md`).
- The existing suite is valuable unit/regression coverage, but a passing result does not prove production deployment controls, browser behavior, or full authorization paths.

## Change Expectations

- Use focused tests for the subsystem changed, then run the required build or end-to-end check proportionate to risk.
- Add only anonymized, deterministic fixtures under `tests/fixtures/` for extraction regressions.
- Never depend on private customer PDFs, external process folders, generated PDFs, caches, or runtime secrets in tests.
- The two owner-material tests in `tests/test_reference_docx_intake.py` run unconditionally against the tracked fixture `tests/fixtures/RiskLocker_Malaysia_Motor_Comprehensive_Packages_Benefits_Addons_2026.docx` (previously skipped when the private owner DOCX was absent from the working tree).
- Update tests when API behavior, extraction behavior, security validation, rendering behavior, storage behavior, or business rules change.
