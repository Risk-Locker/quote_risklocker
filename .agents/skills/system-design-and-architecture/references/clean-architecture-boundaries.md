# Clean Architecture Boundaries & Dependency Rules

## 1. Strictly Acyclic Layer Direction

```text
Frontend React Slices (<600L UI / hooks / types)
   │  typed HTTP JSON (never business math)
   ▼
FastAPI Routers (backend/app/api/routers/*.py)
   │  Pydantic DTO validation + require_role() + CSRF
   ▼
Domain Services (backend/app/services/*.py, <=300L per cohesive concern)
   │  DB transaction scope (commit/rollback), SELECT FOR UPDATE, storage adapter
   ├──► Pure Calculation Engines (Decimal, zero I/O, zero eval())
   └──► Storage / AI Adapters (explicit timeout, circuit/quota guard, fail-closed)
```

## 2. Anti-Pattern -> Clean Architecture Patterns

| Smell / Anti-Pattern | Clean Enterprise Cure |
| :--- | :--- |
| Router performs direct `.query().all()` loops + commits in `GET` | `GET` calls pure read-only query helper (`COUNT` / `LIMIT` / explicit joins); state changes use idempotent `POST`/`PATCH`. |
| 1,500–3,900 line component mixing fetch, road-tax fallback math & DOM rendering | Split cleanly into `<file>/types.ts`, `hooks/use-*.ts`, and `<300–600L` pure presentational subcomponents consuming backend totals verbatim. |
| Service constructs `company_key or "etiqa"` on parse error | Return explicit `ResolutionResult(status="unresolved", reason=...)` forcing `Check Needed` in UI. |
| Duplicated utility formatting across 5 views (`formatCoverPeriod` formatting NRIC!) | Extract explicit single-responsibility domain formatters (`formatPolicyPeriod`, `formatMalaysianNric`, `formatMyrAmount`) with unit tests. |
| Side-effect `POST` fired in React `useEffect` on empty mount | Show neutral empty state; trigger `POST` ONLY on explicit user intent with an `Idempotency-Key` or disabled double-click guard. |

