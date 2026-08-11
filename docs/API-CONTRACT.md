# API Contract

## Conventions

- FastAPI exposes the same router at `/api` and the root path for compatibility.
- Authenticated endpoints use the opaque `risklocker_session` HttpOnly cookie. Bearer tokens and query-string download tokens are not accepted.
- The frontend sends requests with cookie credentials and stores no authentication token in `localStorage` or `sessionStorage`.
- Cookie-authenticated mutations enforce the configured trusted frontend origins in addition to `SameSite=Lax`; production requests without a trusted `Origin` are rejected.
- PDF endpoints use the same authenticated cookie, support byte-range responses, and never return provider URLs.

## Contract Maturity

- Authentication and user create/update endpoints now accept strict Pydantic request models. Other mutable JSON endpoints still accept untyped dictionary payloads and apply validation in route/service logic.
- A future API-hardening change should extend explicit request and response models to drafts, generation, and admin writes. That work must preserve the existing staff workflow and require endpoint-level regression coverage.
- Do not describe request schemas as available until that implementation and its compatibility tests are complete.

## Endpoint Groups

| Group | Main operations | Access |
| --- | --- | --- |
| Health and authentication | health, request code, verify code, current user, logout | health and code request/verification are public; other operations require a valid session |
| User management | create, list, update users; revoke a user's sessions | Admin; Manager is limited to Staff management, while session revocation is Admin-only |
| Notifications | list notifications, unread count, mark-read, mark-all-read | authenticated user (recipient-scoped) |
| Admin mail | test SMTP connection with delivery to own address | Admin |
| Batches and uploads | upload batch, fetch batch | authenticated owner/authorized manager/admin |
| Draft review | fetch draft, save reviewed fields (+ optional `layout_override`), generate one or selected drafts | authenticated owner/authorized manager/admin |
| Sessions | list (search + limit/offset pagination), fetch session | owner-scoped |
| Trash | delete, restore, purge expired trash | owner-scoped; trash purge is Admin-only |
| Template groups | list/create/delete groups, link company, assign templates via `group_id` | Admin |
| Templates | copy (locked/default only), **`POST /admin/templates/{id}/make-master`** (single master, previous master demoted) | Admin |
| Settings imports | road-tax CSV/Excel export+import, vehicles multi-sheet Excel import, runner-fee default | Admin |
| Extraction details | fetch hidden extraction record | Admin or Manager |
| Admin configuration | companies, templates, assets, benefits, dictionaries, extraction settings, storage | Admin or Manager where allowed by service policy |
| PDF content | source-file and generated-version content | authenticated and record-authorized |

## Authentication Contract

- `POST /auth/request-code` accepts `{ "email": string }` and always returns `202` with the same message. Codes are sent only for an active, pre-created, named employee account; the response does not reveal whether an account exists, is disabled, is throttled, or failed delivery.
- `POST /auth/verify-code` accepts `{ "email": string, "code": "000000" }`. A valid unconsumed code creates a server-side session and sets the HttpOnly cookie. Invalid, expired, or attempt-limited codes return the shared `401` error shape.
- `GET /auth/me` returns the current employee account for a valid session.
- `POST /auth/logout` revokes the current server-side session, expires the cookie, and returns `{ "signed_out": true }`.
- `POST /users/{user_id}/sessions/revoke` is Admin-only and immediately revokes every active session for the target account.
- `PATCH /drafts/{draft_id}` accepts `layout_override` (template-config dict, session-scoped canvas layout) — generation and preview-png use it when present; the master template is never modified.
- `GET /sessions` accepts `search` (filename/company), `limit` (max 100), `offset`; returns `{ sessions, total }`. The legacy `GET /history` endpoint is removed.
- Creating, updating, seeding, and authenticating accounts all require a normalized named employee address with the exact `@risklocker.com` domain. Public registration does not exist.
- New accounts are created in `invited` status. The create-user endpoint returns the invited account; an invitation email with a one-time login code is delivered through the backend SMTP relay. The account auto-promotes to `active` on the first successful code verification.

## Notification Contract

- `GET /notifications` returns all notifications for the current user, ordered newest-first. Each notification includes `id`, `event_type` (invitation/role_change/status_change), `title`, `body`, `read_at` (null if unread), `delivery_state` (sent/failed), and `created_at`.
- `GET /notifications/unread-count` returns `{ "unread_count": int }` for the current user.
- `PATCH /notifications/{notification_id}/read` marks a single notification read. Returns 404 if the notification does not belong to the current user.
- `PATCH /notifications/read` marks all unread notifications read for the current user and returns the count updated.
- `POST /admin/mail/test` is Admin-only. It validates the SMTP connection, sends a test email to the Admin's own address, and returns `{ "ok": bool, "message": str }`. A failed SMTP connection does not send an email; a connected relay that fails delivery reports the delivery failure.

## Admin Mail Contract

## Workflow Contract

- Upload returns a batch identifier; the frontend routes staff to the batch review list.
- Draft updates save field values, selected template, package, benefits, and add-ons. Saving resets edited field status to ready; unresolved fields keep the draft in `Check Needed`.
- Generation requires reviewed fields, a selected template, and a selected package. It returns a new version and download-content path.
- A missing or expired source binary does not remove the draft, extracted text, or version history.

For full current routes and line locations, use [generated/CODEBASE-MAP.md](generated/CODEBASE-MAP.md). Update this document whenever the externally observable API behavior changes.
