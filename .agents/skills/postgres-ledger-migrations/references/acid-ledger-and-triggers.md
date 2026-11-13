# ACID Ledger, Triggers & Partial Unique Index Reference

## 1. Immutability & Double-Entry PostgreSQL Guards (`migrations/075+`)

```sql
-- Append-only ledger journal entries (reject UPDATE/DELETE on posted rows)
CREATE OR REPLACE FUNCTION prevent_posted_ledger_mutation()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Posted financial ledger records are immutable; emit a reversing entry instead.';
END;
$$ LANGUAGE plpgsql;

-- Balanced double-entry verification per transaction group
-- Enforce SUM(debit_myr) = SUM(credit_myr) inside deferrable constraint trigger at COMMIT!
```

## 2. Normalized Partial Unique Indexes (Prevent Duplicate Plates & Phantom UNPLATED Rows)
```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_vehicles_active_normalized_plate
ON vehicles (normalized_plate)
WHERE deleted_at IS NULL
  AND normalized_plate IS NOT NULL
  AND btrim(normalized_plate) <> '';
```

## 3. SQLite Hermetic CI Compatibility Notes
- Keep raw PostgreSQL triggers in forward `migrations/*.sql` idempotently guarded (`CREATE OR REPLACE FUNCTION`, `DROP TRIGGER IF EXISTS ...`).
- In `tests/` (SQLite `:memory:`), test SQLAlchemy constraints, `NUMERIC(12, 2)` `Decimal` round-trips, service-level immutability guards, and application-level reversing-entry balance checks so CI remains 100% offline-hermetic.

