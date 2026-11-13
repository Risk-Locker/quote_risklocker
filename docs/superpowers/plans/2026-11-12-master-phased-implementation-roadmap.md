# Master Phased Implementation Roadmap: 4-Phase System Remediation

> **Spec Document:** `docs/superpowers/plans/2026-11-12-master-phased-implementation-roadmap.md`  
> **Status:** Approved Master Blueprint Across All 4 Phases  
> **Execution Strategy:** Serialized Execution (Phase 1 $\to$ Phase 2 $\to$ Phase 3 $\to$ Phase 4)  
> **Target Standard:** Senior Enterprise Architect Grade ("Reads Like Butter", Pure Core, Imperative Shell, Decimal Currency Math)

---

## 1. Executive Master Architecture Overview

This master roadmap establishes the complete 4-phase architectural transformation of Quote Risklocker. It guarantees that memory of all four phases is permanently preserved across agent sessions, subagents, and future developers:

```
+---------------------------------------------------------------------------------------------------------------+
|                                  THE 4-PHASE SERIALIZED EXECUTION ROADMAP                                     |
+---------------------------------------------------------------------------------------------------------------+
|                                                                                                               |
|  [ PHASE 1: Core Underwriter Domain, Towing Engine & Unlocked Road Tax ]                                      |
|  - Separate Kurnia Insurans & AmAssurance completely (no parent-company bundling)                             |
|  - Pure table-driven Malaysian Towing Matrix for all 8 underwriters (Strict RM / km / Unlimited)              |
|  - STMB vs Amgen RM 40 towing-advantage ranking rule                                                          |
|  - Unlock RM 0.00 road tax & runner fee; eliminate forced auto-recalculation overwrites                       |
|  - Bidirectional cross-connection across Workspace, Comparison Matrix & Renewal Ledger                        |
|                                         │                                                                     |
|                                         ▼                                                                     |
|  [ PHASE 2: Pricing Precision & Excel-Style Staff Freedom ]                                                   |
|  - Bank Negara Malaysia (BNM) 5-cent cash rounding mechanism (0, 5, 10 cent endings)                           |
|  - UI toggle button: [ Exact Cents (.15) | BNM 5¢ Rounded (.15) ]                                             |
|  - Explicit [x] Include Road Tax and [x] Include Runner Fee checkboxes (for Lorries / commercial / self)       |
|  - Unlock all form inputs so staff edits are permanently respected and never snapped back                      |
|  - "Fast-Quote" manual fallback button (30-second manual quote entry when PDF is unreadable)                  |
|                                         │                                                                     |
|                                         ▼                                                                     |
|  [ PHASE 3: AI Rate-Limit Sharding, Elevator Queue & Fail-Closed Gate ]                                       |
|  - Strict AI Fast-Fail Gate: Halt & show clear alert on token/quota exhaustion (No silent regex degradation!)  |
|  - 2 verified active models per API key; safe caps: 12 RPM / 450 RPD per model (24 RPM / 900 RPD per key)     |
|  - Round-Robin Sharded Allocator: PDF 1 -> (Key 1, M1), PDF 2 -> (Key 1, M2), PDF 3 -> (Key 2, M1)...        |
|  - Multi-User Fair-Share "Elevator" Queue (WFQ): Interleave requests across users; prevent starvation          |
|  - Real-time queue position and progress banner in UI                                                         |
|                                         │                                                                     |
|                                         ▼                                                                     |
|  [ PHASE 4: Deduplication, Single Active Quote per Insurer & Storage Janitor ]                                |
|  - Unique (tenure_id, insurance_company_id) upsert: New upload replaces previous quote revision               |
|  - Eliminate confusing duplicate v1, v2, v3 comparison columns for the same vehicle and insurer               |
|  - Structural Covernote vs Quotation classifier (Page count, policy wording vs validity period) + toggle     |
|  - S3 / Local Storage Janitor: Automatically prune superseded draft PDFs to prevent storage ballooning        |
|                                                                                                               |
+---------------------------------------------------------------------------------------------------------------+
```

---

## 2. Phase-by-Phase Specifications & Milestones

### Phase 1: Core Underwriter Domain, Towing Engine & Unlocked Road Tax
- **Plan File:** [`docs/superpowers/plans/2026-11-12-milestone-1-core-domain-and-towing.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/superpowers/plans/2026-11-12-milestone-1-core-domain-and-towing.md)
- **Deliverables:**
  1. `Kurnia Insurans` seeded and registered as an independent `InsuranceCompany` with its own logo, detection phrases, and comparison slot.
  2. `AmAssurance` (Amgen) aliases refined; zero parent-company entanglement with Liberty or Kurnia.
  3. `backend/app/domain/motor/towing_matrix.py`: Pure table-driven towing engine implementing the authoritative matrix for QBE, STMB (Plans 1–4), Etiqa, Lonpac, Berjaya Sompo, Tune Protect, AmAssurance (Lite/Plus/Premier), and Kurnia. Output strictly: `RM <amount>`, `<num>km`, or `Unlimited`.
  4. `backend/app/domain/motor/winner_ranking_rules.py`: Implements the RM 40 advantage rule: when STMB vs Amgen total price delta is $\le \text{RM } 40.00$, Amgen with 365 km towing wins over STMB.
  5. Removal of forced `currentRT === 0` overwrites in `review-phase.tsx` and `marketing_comparison_service.py`.
  6. Atomic synchronization across Quotation Workspace, Comparison Matrix, and Renewal Ledger.

### Phase 2: Pricing Precision & Excel-Style Staff Freedom
- **Plan File:** [`docs/superpowers/plans/2026-11-12-milestone-2-pricing-precision-and-staff-freedom.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/superpowers/plans/2026-11-12-milestone-2-pricing-precision-and-staff-freedom.md)
- **Deliverables:**
  1. Pure Bank Negara Malaysia (BNM) 5-cent cash rounding engine (`backend/app/domain/motor/currency_rounding.py`):
     - Ends in 1, 2 $\to$ 0
     - Ends in 3, 4 $\to$ 5
     - Ends in 6, 7 $\to$ 5
     - Ends in 8, 9 $\to$ 10 (next 10 cents)
  2. Frontend Comparison Matrix toggle: `[ Exact Cents (.15) | BNM 5¢ Rounded (.15) ]`.
  3. Checkboxes: `[x] Include Road Tax` and `[x] Include Runner Fee`. When unchecked, the value is strictly `RM 0.00`, excluded from totals, and hidden from client-facing PDFs and WhatsApp teasers.
  4. Permanent edit respect: Staff edits are never reverted or overwritten by automatic recalculation hooks.
  5. "Manual Fast-Quote" fallback button: A clean 5-field modal enabling staff to enter an unreadable quote in 30 seconds.

### Phase 3: AI Rate-Limit Sharding, Elevator Queue & Fail-Closed Gate
- **Plan File:** [`docs/superpowers/plans/2026-11-12-milestone-3-ai-rate-limiting-and-elevator-queue.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/superpowers/plans/2026-11-12-milestone-3-ai-rate-limiting-and-elevator-queue.md)
- **Deliverables:**
  1. Strict Fast-Fail Gate: In `orchestrator.py`, if Gemini extraction encounters token exhaustion, quota limit (429), or missing keys, **stop immediately** and surface an explicit HTTP 429/503 user alert. Ban silent fallback to corrupt regex candidates.
  2. Sharded Allocator: 2 verified active models per API key, capped at 12 RPM / 450 RPD safe margins. Round-robin assignment across all available slots:
     $$\text{PDF } n \to \text{Slot } (n \bmod \text{Total Slots})$$
  3. Multi-User "Elevator" Fair-Share Queue (Weighted Fair Queuing):
     $$\text{User A [1]} \to \text{User B [1]} \to \text{User C [1]} \to \text{User A [2]} \dots$$
     Prevents a user uploading 30 files from starving users uploading 2 files.
  4. Real-time UI progress indicator: *"Processing 2 of your 5 PDFs (Position 1 in queue)"*.

### Phase 4: Deduplication, Single Active Quote per Insurer & Storage Janitor
- **Plan File:** [`docs/superpowers/plans/2026-11-12-milestone-4-deduplication-and-storage-janitor.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/superpowers/plans/2026-11-12-milestone-4-deduplication-and-storage-janitor.md)
- **Deliverables:**
  1. Single active quote per insurer per vehicle tenure: Keyed on `(tenure_id, insurance_company_id)`. Re-uploading an amended quote updates/replaces the existing column rather than creating v1, v2, v3 duplicate columns.
  2. Multi-Signal Covernote vs Quotation Classifier:
     - Structural signals: Page count (1–3 for Quote vs 5–15+ for Covernote), statutory wording vs quote validity period.
     - 1-click manual override toggle: `Document Type: [ Quotation | Cover Note ]`.
  3. S3 & Local Storage Janitor: Automatically prune or archive superseded files from disk and S3 buckets, preventing unbounded storage growth.

---

## 3. Engineering Invariants & Senior Developer Scrutiny Checklist

When peer-reviewed by the 15 senior developers, the codebase will adhere strictly to:
- **Zero Float for Currency:** 100% Python `decimal.Decimal` and SQL `NUMERIC(12, 2)`.
- **Pure Core, Imperative Shell:** All mathematical, domain, and ranking logic sits in pure functions without HTTP, ORM, or database state dependencies.
- **Flat Guard Clauses:** Nesting depth strictly $\le 3$; fail fast with early returns.
- **Hermetic TDD:** Failing tests written and committed before implementation code.
- **Modular Slicing:** Zero monolith files over 400 lines in newly created modules.

