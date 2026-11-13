# Canonical 40-Factor Domain Interrogation Checklist (`8 Axes x 5 Factors`)

Record status for **all 40 factors** (`HANDLED` / `N/A` / `BLOCKED`) inside `implementation_plan.md` before coding any core engine or migration. Do NOT reuse this checklist for low-level test assertions — map code guards to tests in [`edge-case-and-scenario-matrix`](../../edge-case-and-scenario-matrix/SKILL.md).

## Axis 1: Domain & Regulatory Truth
1. Authoritative legal/tax/actuarial source verified by date (`Rule 05` / URL).
2. Jurisdiction & product applicability boundaries (`West MY`, `Sabah/Sarawak`, `Labuan`, `Private/Company`, `ICE/EV`).
3. Effective-date cutoffs & grandfathering retention (older policies keep historical rates).
4. Statutory rounding rules & precision (`Decimal`, `ROUND_HALF_UP`, `NUMERIC(12,2)`).
5. Unknown/missing domain classification fails closed (`Check Needed` / `Unspecified`, never optimistic upgrade).

## Axis 2: Input Normalization & Format Scope
6. Unit normalization contracts (`cc` vs `kW` vs `W`, currency commas/RM prefixes).
7. Identifier parsing & strict non-confusion (plate, NRIC vs passport vs BRN; never run date formatters on IDs).
8. Empty / null / whitespace / `0` / negative / extreme ceiling policy defined before schema.
9. Document & OCR noise tolerance (multi-page endorsements, Unicode/CN labels, unmapped narrative suppression).
10. Human staff edits & manual overrides always take precedence over automated candidates.

## Axis 3: Database Architecture & Multi-Plan Contingency
11. Normalized relational schema (`NUMERIC(12,2)`, explicit FKs, partial unique indexes `WHERE deleted_at IS NULL`).
12. Immutability & double-entry integrity guards (triggers protecting published snapshots & posted ledger journals).
13. Forward idempotent migration (`migrations/075+`) with advisory lock & line-ending normalized SHA-256 checksum parity.
14. Deterministic backfill plan (`dry-run` default + explicit `--apply`) for legacy/unmigrated rows.
15. Verified rollback & failure-recovery contingency (if backfill/migration aborts mid-run, zero corrupt half-state).

## Axis 4: Concurrency & Finite State Integrity
16. Explicit finite state enum + legal transition table (ban boolean flag soup).
17. Read-only `GET` guarantee (zero DB writes, `UNPLATED` auto-creations, or silent commits on `GET`).
18. Row-level locking (`SELECT ... FOR UPDATE`) on competing sequence/status/publish mutations.
19. Double-submit & client retry idempotency keys / optimistic revision checks.
20. Worker claim atomicity & crash lease recovery (stuck jobs cleanly re-queued, never lost or double-rendered).

## Axis 5: Security & Bug-Bounty Surface
21. Endpoint authentication & exact role tier (`require_role`, admin vs staff separation).
22. Tenant / staff record scoping & indirect IDOR prevention (never trust client `user_id`/`tenant_id`/`status`).
23. Same-origin + session-bound double-submit CSRF enforcement on state mutations.
24. Injection & SSRF elimination (`eval()`/`exec()`, SQLi concatenation, `innerHTML`/XSS, unguarded outbound HTTP/Playwright requests).
25. Secret/PII hygiene & private storage fail-closed behavior (`storage=None` never leaks PDFs to temp public disk).

## Axis 6: Observability & Failure Recovery
26. Explicit upstream/worker timeouts with structured error codes (never bare `except: pass`).
27. Third-party outage degradation (e.g., AI pool fallback -> native parser + `Check Needed`, never silent corruption).
28. Audit trail / immutable event logging for sensitive admin, financial, and lifecycle mutations.
29. Masked telemetry & logging (no NRIC, bank numbers, API keys, or stack traces returned to clients).
30. Dead-letter / retryable vs terminal error classification.

## Axis 7: UX, Reporting & Export Parity
31. Single Source of Truth math (React displays backend `Decimal` API output; zero duplicated TS tax formulas).
32. Accessible interactive dialogs & state feedback (`ConfirmDialog`, `useToast`, zero native `window.alert/confirm/prompt`).
33. Complete async/UI states designed (`default`, `loading`, `empty`, `error`, `disabled`, `overflow`).
34. Responsive & zoom layout integrity (`1024px`–`1920px`, `80%`–`120%` browser zoom, keyboard `Tab`/`Esc`).
35. Print / A4 PDF parity (`Design 2` live canvas <-> Playwright Chromium PDF; zero `jsPDF` PNG raster hacks).

## Axis 8: Scale, Cost & Lifecycle Governance
36. Indexed SQL query paths (`10k+` rows, explicit pagination bounds, zero `.all()` full-table loads).
37. Elimination of `N+1` query loops via SQL joins / batching / eager loading.
38. AI token, RPM/RPD quota caps & live model lifecycle pinning (`Rule 05`).
39. Bounded file sizes, page limits, and worker memory reuse (Chromium page pooling / cleanup).
40. Retention, manual reference-aware trash purge, and safe deprecation of legacy data.

---

## Mandatory Sign-Off Output Table (`implementation_plan.md`)

| Factors | Status (`HANDLED` / `N/A` / `BLOCKED`) | Architectural Control / Owner Decision Required |
| :--- | :--- | :--- |
| `#1–#5` Regulatory | `HANDLED` | Verified JPJ 2026 schedule + monotonic `Decimal` table + effective dates |
| ... | ... | ... |

### Mini Worked Example (Prompt: *"Store road tax for cars"*)
- **Factor #2 (`Jurisdiction`)**: `HANDLED` -> Split `West Malaysia`, `Sabah/Sarawak`, `Labuan`, `Private/Company`, `Saloon/NonSaloon`, `ICE/EV`.
- **Factor #1 (`Regulatory Source`) & Build-vs-Buy**: `BLOCKED (Feed)` / `HANDLED (Schedule)` -> Tell owner bluntly: *"Live MyEG/JPJ plate-to-roadtax API requires commercial licensing; we build deterministic JPJ progressive/EV tables (`2501cc` monotonic, `150kW` ZEV) and mark live portal sync as Buy/Manual until API credentials exist."*
- **Factor #13–#15 (`DB Plan`)**: `HANDLED` -> Forward migration `075_road_tax_rules.sql` (`NUMERIC(12,2)`), idempotent seed backfill, rollback `DROP/RESTORE` contingency without breaking historical issued quotations.

