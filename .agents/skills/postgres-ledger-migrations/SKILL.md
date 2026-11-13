---
name: postgres-ledger-migrations
description: >-
  Enforce ACID enterprise database migrations (`migrations/075+`), NUMERIC(12,2) monetary columns, immutability triggers, partial unique indexes, double-entry ledger balance constraints, and hermetic CI schema parity.
---

# PostgreSQL & Double-Entry Ledger Migration Playbook

Consult `migrations/AGENTS.md` and `docs/change/02-database-and-data-models/` before authoring any schema change.

## 1. Non-Negotiable Migration Rules

1. **Monotonic Forward-Only:** Never modify or renumber existing migrations `001`–`074`. Author the next numbered SQL script (`075_...sql`) and synchronize `backend/app/models/tables.py` + `verify_schema_version()`.
2. **Exact Monetary Types:** Every fee, premium, discount, stamp duty, commission, payment, or tax field uses `NUMERIC(12, 2)`—never `DOUBLE PRECISION`/`Float` or unvalidated `VARCHAR(100)`.
3. **Never Drop Safety Triggers Without Replacement:** Migrations `056` and `061` broke immutability guarantees. Published template revisions, finalized `RenderSnapshot` records, and posted ledger journals MUST remain append-only / `ON DELETE RESTRICT` with soft-archive (`archived_at`) flags.
4. **Partial Unique Indexes & Normalized Keys:** Vehicle registration plates (`normalized_plate`) enforce uniqueness only across active rows (`WHERE deleted_at IS NULL`), preventing silent duplicates and rejecting empty `"UNPLATED"` phantom creates. Customer deduplication requires deterministic IC/registration matching—never homonym names alone.

## 2. Double-Entry Ledger Invariant

- Financial workflows (client invoices, insurer payables, runner fees, refunds, commissions) record immutable **balanced journal entries** (`SUM(debit) == SUM(credit)`) tied to idempotency keys rather than mutable `client_payment_received` booleans or unindexed string fields. See `references/acid-ledger-and-triggers.md` for trigger & partial unique index SQL templates.

## 3. Pre-Migration Edge-Case Checklist

- **Zero String Money Columns:** Reject `VARCHAR` or float types for stamp duty, rebate, or runner fees — store exact `NUMERIC(12, 2)`.
- **Idempotency Constraint:** All settlement/payment posting tables enforce `UNIQUE (idempotency_key)` + `ON CONFLICT` protection against double clicks.
- **Backward Compatibility:** New `NOT NULL` columns MUST provide safe defaults or explicit data backfills before tightening constraints (`F-05`–`F-08` legacy rows).
- **Foreign Keys & Cascades:** Never cascade-delete financial journals or finalized customer quotes — enforce `ON DELETE RESTRICT`.

## 4. Mandatory Verification Before Completion

Run inside project `.venv`:
```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -c "from app.db.session import verify_schema_version; verify_schema_version(); print('schema OK')"
.\.venv\Scripts\python.exe -m pytest -q
```
Both must pass 100% hermetically against in-memory SQLite mocks without hitting remote Postgres.

