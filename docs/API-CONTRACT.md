# API Contract

## Conventions

- Production exposes one surface under `/api`; root aliases are non-production compatibility only.
- Browser calls use relative `/api`, credentials, and no browser-stored authentication token.
- Every mutation requires an allowed `Origin`. Authenticated mutations also require `X-CSRF-Token` matching the session-bound `risklocker_csrf` cookie.
- Expensive endpoints use Postgres-backed rate limits. `429` includes `Retry-After`.
- PDF endpoints authorize every request, support byte ranges, and never return provider URLs.
- Mutations use idempotency keys where specified and optimistic `base_revision`; a `409` never overwrites newer state.
- Errors converge on `{ "error": { "code", "message", "details?", "request_id?" } }`.

## v7 Core Endpoints

| Endpoint | Contract | Delivery |
| --- | --- | --- |
| `POST /api/uploads` | Exactly one PDF plus idempotency key; `202` with `session_id`, `job_id` | WP4 |
| `GET /api/jobs/{job_id}` | queued/processing/completed/failed/cancelled, attempt, progress, safe error | WP4 |
| `GET /api/sessions/{id}/workspace` | safe snapshot, reviewed decisions, pinned revisions, blockers, capabilities | WP5 |
| `GET /api/sessions/{id}/source-pages` | lazy paginated source/evidence data | WP5 |
| `PATCH /api/drafts/{id}/workspace` | dirty operations plus mandatory `base_revision`; canonical snapshot/revision response | WP5 |
| `POST /api/sessions/{id}/template-selection-impact` | read-only impact for an exact published target and current draft revision | WP7 |
| `GET /api/business/template-page-profiles` | active fixed page profiles available to business users | WP7 |
| `GET /api/business/templates/published` | latest published revision of every active insurer-independent template | WP7 |
| `POST /api/business/templates/{id}/publish` | optimistic publish of a validated immutable revision; identical content is idempotent | WP7 |
| remaining impact-preview/apply endpoints | company/product/tier/package/catalog changes require explicit confirmation | WP5-WP6 |
| `POST /api/sessions/{id}/preview-render` | saves/uses exact revision and returns cached result or render job | WP8 |
| `POST /api/sessions/{id}/versions` | exact saved revision plus idempotency key; at most one immutable version | WP8 |
| `GET /api/versions/{id}/pdf` | stream existing authorized PDF; never generate | WP8 |
| `/api/business/*` | paginated business setup, draft/publish/revision/import/reference-aware retirement | WP6-WP7 |
| `/api/records/*` | shared paginated records, saved filters, bulk archive/trash/restore/export/purge | WP9 |

Existing `/batches`, legacy draft, old preview, and generated-content routes are compatibility-only and are removed from new UI callers as their v7 equivalents ship.

Business Setup owns company, product, tier, catalog, benefit concept, base/upgrade/optional offering, package, variation, source, asset, and alias records. The active UI never writes the legacy global Our Specials model.

Job responses include phase start/completion timestamps, heartbeat, elapsed duration, attempt, and safe retry state so the UI never infers progress from request count.

## Temporary Authentication Contract

- `POST /api/auth/login` is the protected password flow during core work. It returns generic failures, is rate-limited, rotates an opaque server session, and issues the session-bound CSRF cookie.
- `GET /api/auth/me` returns the active user and capability summary.
- `POST /api/auth/logout` revokes server state and expires both cookies.
- `dev` accounts cannot authenticate or retain a production session.
- Environment-driven owner resets are disabled. `python commands/create_admin.py <email>` is the one-time interactive Primary Admin bootstrap.
- No public signup exists. A dormant backend mail-provider boundary may exist, but the current password flow never invokes it. OTP/onboarding/recovery and live Resend activation remain post-core work.

## Access Contract

- Staff, Admin, and Primary Admin share quotation/customer records and approved business setup.
- Admin additionally manages users, security, audit, IP controls, and operations.
- Primary Admin exclusively controls Admin promotion/demotion, ownership transfer, and emergency recovery.
- Capabilities are server-issued; frontend gating is not an authorization boundary.
- A session editor never mutates a master template.
- Staff, Admin, and Primary Admin may manage template drafts/assets and publish revisions; security/user administration remains Admin-only.

## Review and Generation Contract

- Extraction candidates are suggestions. Every source line needs one explicit disposition.
- Scalar decisions are `Confirm`, `Edit`, `Clear`, or `Keep Check Needed`; editing one field cannot confirm another.
- Unknown required value/cost, unresolved lines, invalid template/layout, or stale pinned selections are generation blockers.
- Selecting a template first previews impact, then queues a confirmed `template_selection` workspace operation. A change clears any quotation layout bound to the previous template revision.
- Generation exists only in final Preview/Generate and requires an exact saved revision. Download never creates a version.
- Historical versions contain immutable render-context snapshots and remain unchanged by later catalog/template edits.
