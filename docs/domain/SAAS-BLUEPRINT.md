# Risklocker Enterprise SaaS Blueprint (North Star Architecture)

This document is the permanent architectural compass for Risklocker. Every AI agent—regardless of conversation context, session refresh, or prompt brevity—must uphold these foundational SaaS standards to ensure unbeatable stability, data integrity, and user experience.

---

## 1. Core System Entity Hierarchy

Risklocker operates on a strict, relational domain model designed for high-concurrency motor insurance workflows and corporate fleet management:

```
┌────────────────────────────────────────────────────────┐
│               CustomerAccount / Legal Entity           │
│         (BRN / NRIC, Company Name, Contact Person)     │
└───────────────────────────┬────────────────────────────┘
                            │ 1 : N
                            ▼
┌────────────────────────────────────────────────────────┐
│                     TrackedVehicle                     │
│         (Registration Number, Chassis, Engine, Type)   │
└───────────────────────────┬────────────────────────────┘
                            │ 1 : N
                            ▼
┌────────────────────────────────────────────────────────┐
│                    InsuranceTenure                     │
│      (Policy Period, Year, Sum Insured, NCD, Status)   │
└─────────────┬────────────────────────────┬─────────────┘
              │ 1 : N                      │ 1 : 1
              ▼                            ▼
┌───────────────────────────┐ ┌──────────────────────────┐
│      QuotationDraft       │ │    MarketingComparison   │
│ (Insurer, Premium, Extr.) │ │  (Quotes, Winner Handoff)│
└─────────────┬─────────────┘ └──────────────────────────┘
              │ 1 : N
              ▼
┌───────────────────────────┐
│       RenderSnapshot      │
│  (Immutable Render Context│
│   & Generated PDF Version)│
└───────────────────────────┘
```

---

## 2. Database Invulnerability Standards

### A. Strict Foreign Keys & Cascade Determinism
* **Never use unconstrained foreign identifiers**: Every relational child must declare an explicit SQLAlchemy `ForeignKey` with deterministic deletion behavior:
  * Dependent child collections (e.g. `DraftBenefitSelection`, `RenderSnapshot`, `DraftSourceLineDecision`) must use `ondelete="CASCADE"`.
  * Core business parents (e.g. `CustomerAccount`, `TrackedVehicle`, `InsuranceCompany`) must use `ondelete="RESTRICT"` or `ondelete="SET NULL"` with explicit business validation before deletion.
* **Indexes on Filter & Join Keys**: Every foreign key, lookup column, and dashboard filter field (e.g. `tenure_id`, `vehicle_id`, `customer_id`, `created_at`, `status`) must carry an explicit B-tree index in PostgreSQL (`index=True` or composite index in `__table_args__`).

### B. Financial Integrity & Zero Floating-Point Drift
* **Monetary Values**: All premiums, add-on costs, road taxes, runner fees, stamp duties, and total payables must be stored as exact `Numeric(12, 2)` / `Decimal` values or exact integer cents.
* **Never use raw IEEE 754 floating-point numbers (`Float`)** for money calculations. All arithmetic operations must use deterministic round-half-up math (`ROUND_HALF_UP`) to prevent cent discrepancies.

### C. Atomic Migrations & Ledger Checksums
* Schema modifications must NEVER occur spontaneously at runtime.
* Every database change must be authored as a numbered SQL file under `migrations/` (e.g. `063_feature_name.sql`).
* Migrations must be ledger-recorded, checksummed, and transactionally executed via `backend/app/db/migrations.py`.

---

## 3. Enterprise API & Response Architecture

### A. Standardized Contract Shapes
All FastAPI endpoints return consistent, typed Pydantic response payloads:
```json
{
  "success": true,
  "data": { ... },
  "message": "Resource updated successfully",
  "meta": { "total": 120, "page": 1, "limit": 50 }
}
```

### B. Graceful Error Handling & HTTP Semantic Codes
* **400 Bad Request**: Malformed inputs, business rule violations, or unprocessable logical transitions.
* **401 Unauthorized**: Missing, expired, or invalid session cookies.
* **403 Forbidden**: Insufficient role permissions or CSRF token mismatch.
* **404 Not Found**: Entity does not exist or has been soft-deleted.
* **409 Conflict**: Foreign key or unique constraint violation (handled with informative message).
* **422 Unprocessable Entity**: Schema validation failure with exact field annotations.
* **500 Internal Error**: Handled centrally via exception middleware; raw internal database stack traces are NEVER exposed to the frontend client.

### C. Idempotency on High-Impact Operations
* State-changing mutations (PDF rendering, batch uploads, manual quotation creation) must accept an `idempotency_key` or check session versioning to guarantee that rapid double-clicks never duplicate records.

---

## 4. Proactive UX & Frontend Polish

### A. The "Zero Layout Shift" Rule
* Every asynchronous data-fetching view must render semantic loading skeletons matching the exact dimensions of the target table, card, or modal.
* Layouts must never jump, shift, or flash unstyled content during transitions.

### B. Optimistic UI Updates with Server Rollback
* Interactive controls (status toggles, winner selection, inline stage edits, PIC assignments) must update the UI immediately (sub-50ms) and persist to the database in the background.
* In the rare event of a network failure, the UI must automatically revert the state and display a clear, non-intrusive notification (`sonner` toast).

### C. Empty States & First-Time Experience
* Every table, list, or drawer must feature an informative empty state with actionable guidance:
  * Icon + Clear headline (e.g. *"No Active Motor Tenures Found"*).
  * 1-sentence contextual description.
  * Direct Call-to-Action button (e.g. *"Upload Quotation"* or *"Add Deal Manually"*).

---

## 5. Security & Multi-Tenancy Invariants

* **Zero Frontend Secrets**: Storage service-role keys, backend database URIs, API keys (Gemini, Resend), and cryptographic hash secrets must NEVER be prefixed with `NEXT_PUBLIC_` or sent in client responses.
* **Session Hardening**: Cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` in production. Rolling expiration with 8-hour idle timeout and 30-day absolute ceiling.
* **Stateless Ephemeral PDFs**: Uploaded and generated PDF binaries are never persisted in the database or public directories. They are scanned, parsed, and immediately quarantined/cleaned up.
