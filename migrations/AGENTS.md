# Database & Migration Rules (`migrations/AGENTS.md`)

> Scoped automatically when creating or reviewing SQL schema migrations under `migrations/`.

## Hard Database Invariants

1. **Append-Only Forward Migrations**:
   - Never rewrite already-applied migration numbers (`001`–`074`). Add monotonic numbered files (`075_...sql`) and mirror cleanly in `backend/app/models/tables.py` + `verify_schema_version()`.
2. **Financial & Identity Precision**:
   - Every currency/rate/fee column MUST be `NUMERIC(12, 2)` (never `DOUBLE PRECISION`/`Float` or unvalidated `VARCHAR(100)`).
   - Protect vehicle plate numbers and active tenures with normalized uppercase/whitespace-stripped keys and **partial unique indexes** (excluding soft-deleted/voided rows), never merging customers on homonym names alone.
3. **Immutability & Audit Protection**:
   - Never drop append-only or published-revision immutability triggers (`056`/`061` anti-pattern) without explicit soft-archive mechanisms and `ON DELETE RESTRICT` preservation of historical `render_snapshots`.
   - Double-entry ledger changes must preserve balanced `SUM(debit) == SUM(credit)` invariants via DB constraints/triggers and idempotent transaction keys.
4. **Migration Verification**:
   - Every schema edit must keep `from app.db.session import verify_schema_version; verify_schema_version()` green in CI/SQLite parity tests.

