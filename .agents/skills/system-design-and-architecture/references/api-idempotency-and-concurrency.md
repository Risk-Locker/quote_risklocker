# API Idempotency, Concurrency & Failure-Resilience Patterns

## 1. Mutating Endpoint Contracts
- **Strict HTTP Method Semantics:** `GET`, `HEAD`, `OPTIONS` are 100% side-effect free (zero `INSERT`, `UPDATE`, `DELETE`, counter bumps, or audit commits inside `GET`).
- **Idempotent Financial & Workflow Writes:** Policy issuance, quotation generation, tenure advancement, payment confirmation, and bulk imports MUST survive client double-clicks, proxy retries, and worker restarts cleanly:
  - Wrap critical transitions in a single ACID transaction with `SELECT ... FOR UPDATE` on parent quotation/tenure rows, OR optimistic `version = expected_version` check returning HTTP `409 Conflict` on stale UI submissions.
  - Use PostgreSQL partial unique constraints (`WHERE deleted_at IS NULL`) and `INSERT ... ON CONFLICT DO NOTHING / UPDATE` instead of racy `SELECT`-then-`INSERT` sequences.

## 2. External I/O & Worker Resilience
- **Storage Fail-Closed (`Supabase Storage`):** Wrap storage calls with explicit timeouts and structured exceptions; NEVER catch storage absence/failure and dump private PDFs into `.qc-tmp/`.
- **Pooled Browser / External Resource Reuse:** Reuse warm worker resources (`pdf_generator.py` Playwright context, pooled HTTP clients) with bounded memory cleanup and hard per-job timeouts.
- **Partial Failure Rollback:** Multi-step mutations (e.g., generating PDF + inserting `RenderSnapshot` + uploading blob + updating tenure stage) write DB uncommitted first, upload blob with deterministic object key, then commit — cleaning orphaned blobs or scheduling compensating reconciliation if commit fails.

## 3. Scale & Indexing Rules
- Ban Python `.all()` full-table loads cleanly (`workspace_service`, `generation_service`): filter in PostgreSQL using indexed `WHERE`, `JOIN`, keyset or bounded `LIMIT/OFFSET` pagination (`max_limit <= 200`), and eager `selectinload`/`joinedload` to eliminate `N+1` queries.

