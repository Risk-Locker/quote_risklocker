# Phase 2: Database Schema Hardening & Double-Entry Ledger (`migrations/077+`)

> **Document:** `docs/plans/2026-11-14-phase-2-db-schema-and-double-entry-ledger.md`  
> **Status:** Approved / In Execution  
> **Prerequisites:** Phase 1 (P0 Hotfixes) 100% Verified Live  
> **Owner:** Principal Architect & Backend Ledger Lead  

---

## 1. Executive Summary & Forensic Context

In Phase 1, we halted critical runtime exploits (`F-01` through `F-06`), locked down RBAC, AST-evaluated formulas, secured edge middleware, hardened towing extraction regex, and eliminated the JPJ road tax rate discontinuity at 2501cc across both code and the live PostgreSQL database.

**Phase 2** targets the structural database layer (`F-08`, `F-12`, and architecture specs in `docs/change/02-database-and-data-models/`):
1. **Restore Immutability Triggers (`056`/`061` Reversal with Soft-Archive):**
   - Published template revisions (`template_revisions`) and catalog revisions (`benefit_catalog_revisions`) must be immutable.
   - Deleting a template revision must NEVER cascade-delete finalized customer legal receipts (`render_snapshots`). Restores `ON DELETE RESTRICT` with `archived_at` lifecycle flags.
2. **Normalized Vehicle Identity (Eliminating "UNPLATED" Collisions):**
   - Replace unsafe global unique index on `tracked_vehicles(vehicle_no)` with partial unique index `uq_tracked_vehicles_real_plate` that ignores placeholder values (`UNPLATED`, `NEW`, `NONE`).
   - Add partial unique index `uq_tracked_vehicles_chassis` on non-empty chassis numbers.
3. **Enterprise Double-Entry Financial Ledger:**
   - Eliminate boolean-only financial tracking (`client_payment_received`, `agency_payment_done`) and unindexed string money fields.
   - Introduce balanced double-entry accounting schema:
     - `ledger_accounts` (Chart of Accounts: Bank, AR Client, AP Insurer, Commission Revenue, Runner Fee).
     - `ledger_invoices` (Customer billable obligations with exact `NUMERIC(12, 2)` breakdowns).
     - `journal_entries` (Append-only transaction headers with idempotency keys and reversing entry links).
     - `journal_lines` (Balanced debit/credit line items with deferrable constraint trigger enforcing $\sum \text{debits} = \sum \text{credits}$).

---

## 2. Serialized Milestones Breakdown

### Milestone 2.1: PostgreSQL Migration `077_restore_immutability_and_ledger_schema.sql`
- **Scope:**
  - Add `archived_at TIMESTAMPTZ NULL` and `is_archived BOOLEAN NOT NULL DEFAULT false` to `template_revisions` and `benefit_catalog_revisions`.
  - Re-establish `ON DELETE RESTRICT` from `render_snapshots` to `template_revisions`.
  - Implement PostgreSQL trigger `prevent_published_revision_mutation()` preventing `UPDATE` or `DELETE` on published revisions unless changing `archived_at`.
  - Add partial unique indexes for `tracked_vehicles`: `uq_tracked_vehicles_real_plate` and `uq_tracked_vehicles_chassis`.
  - Create tables: `ledger_accounts`, `ledger_invoices`, `journal_entries`, `journal_lines`.
  - Add PostgreSQL function and trigger `trg_verify_journal_entry_balanced` to enforce double-entry zero-sum invariants on commit.
  - Seed canonical Chart of Accounts:
    - `1010-BANK-HLB` (Asset, Debit)
    - `1200-AR-CLIENT` (Asset, Debit)
    - `2100-AP-INSURER` (Liability, Credit)
    - `4010-COMM-REV` (Revenue, Credit)
    - `4020-RUNNER-FEE` (Revenue, Credit)
    - `5010-ROAD-TAX-EXP` (Expense, Debit)

### Milestone 2.2: SQLAlchemy ORM Models & Type Parity
- **Scope:**
  - In `backend/app/models/tables.py`, declare `LedgerAccount`, `LedgerInvoice`, `JournalEntry`, `JournalLine` using exact `Numeric(12, 2)` and Python `Decimal`.
  - Update `TrackedVehicle` model with partial index metadata and `is_provisional` flag.
  - Update `TemplateRevision` and `BenefitCatalogRevision` models with `archived_at` and `is_archived`.
  - Update `RenderSnapshot` relationship back to `ondelete="RESTRICT"`.

### Milestone 2.3: Pure Domain Accounting Engine & Pytest Suite
- **Scope:**
  - Create pure domain module `ledger_engine` under `domain/ledger/`:
    - Pure functions to construct balanced journal entries for:
      - Policy quotation issued (`AR Client` debit, `AP Insurer` credit, `Commission` credit, `Runner Fee` credit).
      - Client payment received (`Bank` debit, `AR Client` credit).
      - Insurer remittance settlement (`AP Insurer` debit, `Bank` credit).
      - Policy cancellation / endorsement reversal (clean reversing journal entries).
  - Add unit test suite under `tests/unit/` for double entry ledger with 100% hermetic SQLite assertions.

### Milestone 2.4: Authentic Live Verification & Knowledge Base Gate
- **Scope:**
  - Apply migration 077 to the live database (`commands/apply-migrations.ps1`).
  - Verify schema parity: `verify_schema_version()`.
  - Run full test gauntlet: Pytest unit & security suites.
  - Update `docs/core/STATE.md` and verify Knowledge Base with `commands/verify-brain.py`.
