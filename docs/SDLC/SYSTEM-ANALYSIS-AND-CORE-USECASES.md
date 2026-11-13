# Risklocker Core System Analysis & Architectural Forensic Report

> **Location:** `docs/SDLC/SYSTEM-ANALYSIS-AND-CORE-USECASES.md`  
> **Status:** Current State Forensic Audit & SDLC Architecture Review  
> **Audience:** Product Owner, Lead Developers & System Architects  

---

## 1. Executive Summary: What Happened to This Codebase?

To understand why a 40-year veteran software engineer was shocked and laughing when reviewing this codebase, we need to be completely honest about what the code reveals:

1. **The Code Was Built by "Prompt-Driven Feature Patching" (Vibecoding):**  
   Features were prompted one by one without an upfront architectural blueprint. Whenever a new feature was requested (e.g., "now build a comparison table", "now add a renewal ledger", "now add road tax"), the AI generated brand-new, isolated tables, services, and frontend pages instead of extending a unified domain model.
2. **Three Parallel Universes for the Same Business Object:**  
   In the real world, an insurance quote is just an insurance quote. In this codebase, an insurance quote is coded in **three separate, disconnected models**:
   - `QuotationDraft` (a giant JSON blob in the Quotation Workspace)
   - `TenureComparisonEntry` (a separate relational table with hardcoded flat columns in the Comparison Engine)
   - `InsuranceTenure` (a separate pipeline table with ad-hoc financial flags in the "Ledger")  
   Then, **over 2,200 lines of glue code** (`marketing_comparison_service.py`) were written to desperately keep these three separate universes in sync.
3. **The System Is "Running on Hope and Luck":**  
   - **Silent AI Failure:** When Gemini AI runs out of tokens, hits a 429 quota limit, or has an invalid key, the backend catches the error, logs a warning, and **silently continues** with crude regex. The user is never warned that the AI failed, and broken/empty quotation drafts are created.
   - **Floating-Point Money:** Premiums, taxes, and discounts are stored and computed using Python `float` instead of `Decimal`, causing rounding discrepancies.
   - **Zero Concurrency Protection:** Multiple users or fast double-clicks can overwrite comparison entries and tenures because there are no pessimistic row locks (`with_for_update`) on critical financial updates.
4. **Extreme Code Bloat:**  
   A few massive files hold the entire application (`tenure-timeline-ledger.tsx` has 3,974 lines, `review-phase.tsx` has 2,760 lines, `comparison-matrix.tsx` has 2,003 lines).

---

## 2. The Core Features: Real-World Use Cases vs. How It Was Coded

Below is the breakdown of the system's core features. Each section presents the **plain-English business use case** first, followed by a dropdown explaining **how the coding was actually done** and **why it broke**.

---

### Feature 1: AI Document Intake & PDF Extraction

**The Real Business Use Case:**  
An insurance agent receives a renewal notice or competitor quotation PDF from a client via WhatsApp or email. The agent uploads the PDF to Risklocker. The system must extract vehicle details (plate, make, model, engine CC, chassis number), customer IC, coverage dates, sum insured, NCD %, and selected benefits. If the AI service is unavailable or out of quota, **the system must immediately stop and alert the user** so an unverified or corrupted quotation is never presented to a client.

<details>
<summary><b>Technical Breakdown: How it was coded & why it is broken</b></summary>

- **The Code Location:** `backend/app/extraction/orchestrator.py` & `gemini_extractor.py`
- **What Was Implemented:**
  1. The code extracts raw text using `pdfplumber` / `pypdf`.
  2. If a Gemini API key is configured, it calls Gemini multimodal vision.
  3. **The Silent Failure Flaw (`orchestrator.py` line 317):**
     ```python
     except Exception as exc:
         logging.getLogger(__name__).warning("Gemini multimodal extraction note: %s", exc)
         warnings.append(f"Gemini multimodal extraction note: {exc}")
     ```
     When Gemini tokens expire or the API returns a `429 RESOURCE_EXHAUSTED` error, the exception is caught and swallowed. `gemini_res` remains `None`.
  4. The orchestrator continues straight into `build_draft(candidates)` using whatever primitive regex could find from the raw text.
  5. The draft status is often set to `Ready` or `Check Needed` without blocking the pipeline.
- **Why the Veteran Engineer Criticized It:**  
  A mission-critical financial document pipeline must have **Fast-Fail Gates**. If AI is a mandatory extraction dependency, failing to reach the AI must return an explicit HTTP 503 / 429 status code with a user-facing error banner: *"AI Extraction Unavailable: API Quota Exhausted. Please recharge tokens or switch keys."* Instead, the code "hopes" that regex will find enough fields, resulting in silent data corruption.
</details>

---

### Feature 2: Quotation Workspace & Review

**The Real Business Use Case:**  
The agent reviews the extracted quotation data on screen. The agent confirms or edits the vehicle details, sum insured, road tax, and add-on benefits (e.g. Windscreen RM 1,000, Special Perils, Towing). The system validates the numbers, recalculates SST (8%) and Stamp Duty (RM 10), and produces an official Risklocker Quotation PDF with a reference number (`RL-YYYYMM-XXXX`).

<details>
<summary><b>Technical Breakdown: How it was coded & why it is broken</b></summary>

- **The Code Location:** `backend/app/services/session_service.py`, `workspace_patch_service.py`, and frontend `frontend/src/components/session-workspace/review-phase.tsx` (2,760 lines)
- **What Was Implemented:**
  1. Data is saved in `QuotationDraft.fields` as a loose, untyped JSON object (`{"gross_premium": {"value": "1250.00", "status": "ready"}}`).
  2. The review page (`review-phase.tsx`) is a 2,760-line monolith containing PDF viewer state, form state, benefit pickers, inline calculations, and save debouncers all in one component.
  3. Calculations for taxes and totals are duplicated: the frontend JavaScript calculates preview totals using `parseFloat()`, and backend services calculate totals independently.
- **Why the Veteran Engineer Criticized It:**  
  - Putting core business fields into a generic JSON column defeats PostgreSQL's relational guarantees (no foreign keys on fields, no database-level constraints, no indexable Decimal columns).
  - Mixing UI presentation, PDF viewing, and financial recalculations in a single 2,760-line component makes maintenance impossible and causes state bugs when users navigate back and forth.
</details>

---

### Feature 3: Multi-Insurer Marketing Comparison

**The Real Business Use Case:**  
A customer does not buy the first quote. They ask: *"What is Allianz offering vs. Etiqa vs. Zurich?"*  
The agent needs a side-by-side comparison table showing 3 to 5 insurer options for the same vehicle renewal term. The agent wants to compare premiums, excess, towing limits, agreed value vs market value, and free benefits, pick a "recommended winner", and generate a WhatsApp teaser or formal comparison report.

<details>
<summary><b>Technical Breakdown: How it was coded & why it is broken</b></summary>

- **The Code Location:** `backend/app/api/routers/comparison.py`, `backend/app/services/marketing_comparison_service.py` (2,236 lines), and frontend `comparison-matrix.tsx` (2,003 lines)
- **What Was Implemented:**
  1. Instead of linking existing `QuotationDraft` objects to a comparison view, a completely separate table called `TenureComparisonEntry` was built.
  2. This table re-declares 20+ columns already present in quotations: `motor_premium`, `road_tax`, `runner_fee`, `total_payable`, `discount`, `towing_limit`, `agreed_value`, `waiver_betterment`, `excess`, `special_perils`, etc.
  3. When an agent clicks "Generate Quotation" on a comparison column, `generate_quotation_for_entry()` creates a *synthetic* dummy `UploadedFile`, a *synthetic* `QuotationDraft`, and a *synthetic* `Session` from the comparison row.
  4. And vice-versa: when an agent uploads a PDF in the quotation workspace, a sync routine tries to copy values into `TenureComparisonEntry`.
- **Why the Veteran Engineer Criticized It & Laughed:**  
  When the user asked *"you meant to be in the same file?"*, the veteran engineer was exasperated because:
  - This is a catastrophic violation of **Single Source of Truth (SSOT)**.
  - A comparison column and a quotation are the **exact same thing** from a business standpoint.
  - Creating two parallel sets of database tables, two parallel calculation engines, and 2,236 lines of duct-tape code to keep them synchronized is the textbook definition of "noob/vibecoded" architecture.
</details>

---

### Feature 4: Motor Renewal Pipeline (Misnamed "Ledger")

**The Real Business Use Case:**  
Motor insurance policies in Malaysia renew once every 12 months. An agency needs to track which customer vehicles are expiring in January, February, March, etc., and move them through a workflow pipeline:
`Lead / Expiry Anchor` -> `Quoting` -> `Comparison Sent` -> `Client Picked Winner` -> `Payment Received` -> `Covernote Issued` -> `Renewed`.

<details>
<summary><b>Technical Breakdown: How it was coded & why it is broken</b></summary>

- **The Code Location:** `backend/app/models/tables.py` (`InsuranceTenure`), `backend/app/services/insurance_tenure_service.py`, and frontend `frontend/src/components/tenures/tenure-timeline-ledger.tsx` (3,974 lines)
- **What Was Implemented:**
  1. The feature is named "Motor Renewal Ledger" in the UI and documentation.
  2. The table `insurance_tenures` contains deal-stage pipeline columns (`stage`, `business_type`, `pic_id`, `sub_agent_name`), operational checklists (`key_in_ucd`, `print_roadtax`, `client_payment_received`, `agency_payment_done`), and financial numbers (`won_premium`, `road_tax`, `runner_fee`).
  3. The frontend is a single monolithic file of **3,974 lines** containing 300+ variables, inline drawer modals, vehicle history lookups, sync modals, and custom drag/tab filters.
- **Why the Veteran Engineer Asked "How many systems did you analyze before making this?":**  
  - In accounting and enterprise software, a **Ledger** has a strict definition: double-entry bookkeeping (debits and credits), immutable audit logs, chart of accounts, and zero in-place overwriting.
  - This system is **not a ledger at all**; it is an **Insurance Renewal Pipeline / CRM Kanban board** (like HubSpot Deals or Applied Epic Expiration Reports) that was given the wrong name.
  - Because it was designed without analyzing real insurance agency management systems (AMS360, Applied Epic, Guidewire), payment reconciliation was modeled as naive boolean checkboxes (`client_payment_received: bool`, `agency_payment_done: bool`) with floating-point values instead of transaction records.
</details>

---

### Feature 5: Template Studio & PDF Generation

**The Real Business Use Case:**  
The agency produces branded A4 customer-facing quotations. The PDF must look crisp, clean, strictly match Malaysian insurance standards, and render identically across different devices and print outputs.

<details>
<summary><b>Technical Breakdown: How it was coded & why it is broken</b></summary>

- **The Code Location:** `backend/app/rendering/template_renderer_design2.py`, `benefit_schedule_renderer.py`, and frontend `design2-canvas.tsx` (857 lines)
- **What Was Implemented:**
  1. A live React preview canvas (`design2-canvas.tsx`) renders the HTML/CSS quotation in the browser.
  2. A Python service renders Jinja2 HTML templates and spins up a headless Chromium browser via Playwright to generate the PDF file.
  3. Four separate historical publication scripts accumulated in `commands/`:
     - `publish-v2-master-template.py`
     - `publish-v3-derivative-templates.py`
     - `publish-v4-master-templates.py`
     - `publish-design2-master-template.py`
- **Why the Veteran Engineer Criticized It:**  
  - Scripts were stamped with version numbers (`v2`, `v3`, `v4`) and left abandoned in the root `commands/` directory instead of using a parameterized CLI command or database migration.
  - Two parallel layout rendering engines (React canvas in TypeScript vs. Jinja2/Playwright in Python) require double maintenance whenever a CSS rule, font size, or benefit card layout is adjusted.
</details>

---

## 3. The 5 Root Architectural Disconnects

The veteran engineer's reaction was driven by five core structural problems:

```
+-----------------------------------------------------------------------------------+
|                        THE FRAGMENTED CODEBASE REALITY                            |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|    [ Upload / OCR Pipeline ]                                                      |
|           |                                                                       |
|           v (Swallows AI Token Errors Silently!)                                  |
|    [ QuotationDraft Table ] <==== (2,200L Glue Code) ====> [ TenureComparison ]   |
|    - Stored in JSON blob                                  - Flat relational cols  |
|    - Separate calculation                                 - Separate calculation  |
|           |                                                       |               |
|           +-----------------------+-------------------------------+               |
|                                   v                                               |
|                    [ InsuranceTenure ("Ledger") ]                                 |
|                    - Misnamed (It is a CRM pipeline, not a ledger)                |
|                    - Boolean payment flags instead of transaction records         |
|                    - 4,000-line single-file React component                       |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

### Disconnect 1: Domain Duplication vs. Single Source of Truth (SSOT)
When the user said *"you meant to be in the same file?"*, it revealed a confusion between **code organization** and **domain modeling**:
- **What the user thought:** The senior engineer wanted all the code pasted into one gigantic file.
- **What the engineer actually meant:** An insurance quotation from an insurer is a **single business entity**. It should have one authoritative database model, one calculation engine, and one validation schema. Whether you view it in a Single-Quote Editor, a Multi-Quote Comparison Grid, or a Policy Expiry Calendar, it is the same entity. Creating separate models (`QuotationDraft` vs `TenureComparisonEntry`) forced thousands of lines of synchronization code.

### Disconnect 2: Silent Failure vs. Fail-Closed Resilience ("Hope and Luck")
Financial software must **fail closed and fail loudly**:
- If Gemini API quota expires, **stop the upload immediately** and show an error dialog: *"Gemini API Quota Exceeded (429). Please verify API billing or key settings."*
- Never fall back silently to partial regex scraping and present a half-empty quotation as "Ready".
- Never compute financial premiums with IEEE 754 floating-point numbers (`float`). Always use arbitrary-precision `Decimal(12, 2)`.

### Disconnect 3: Architectural Sprawl and Component Bloat
- Single components should have a single responsibility and typically stay under 300–500 lines.
- Files like `tenure-timeline-ledger.tsx` (3,974 lines), `review-phase.tsx` (2,760 lines), and `comparison-matrix.tsx` (2,003 lines) are unmaintainable. They mix network fetching, modal management, business logic, formatting, and DOM layout into one giant block.

### Disconnect 4: Command Debris & Lack of Hygiene
In `commands/`, scripts were accumulated across sprints without cleanup:
- `run-backend.cmd` vs `start-backend.ps1`
- `clean-legacy-sessions-to-tenures.py` vs `clean-slate-sessions-and-tenures.py`
- `publish-v2...`, `publish-v3...`, `publish-v4...`, `publish-design2...`
Leaving obsolete, one-off, and contradictory scripts in the main command directory gives reviewers the immediate impression that the codebase has no maintenance standards or automated lifecycle.

### Disconnect 5: What SDLC Was Used vs. What Was Needed
- **What Was Used:** Prompt-Driven Ad-Hoc Hacking. The AI wrote whatever was needed to make the immediate prompt pass, without checking if the new code duplicated existing logic or violated database normalization.
- **What Was Needed:** An **Incremental Agile SDLC with Modular Domain Architecture**:
  1. Define the Core Domain Model (Customer -> Vehicle -> PolicyTerm -> InsurerQuote -> CoverageBenefit).
  2. Build a pure, tested calculation engine (Python `Decimal` only).
  3. Build clean, small UI views (under 400 lines each) that query the core domain via REST APIs.
  4. Write automated integration tests verifying real failure states (e.g. simulated AI token outage).

---

## 4. The Recommended Remediation Roadmap

To transform this system from a fragile prototype into a resilient, enterprise-grade product, follow this phased execution plan:

```
[Phase 1: Fail-Safe AI & Guardrails]
   - Halt on AI exhaustion; return HTTP 429/503 + user-facing alert
   - Enforce Decimal currency math across all calculation services
              |
              v
[Phase 2: Unified Quotation Domain Model]
   - Merge TenureComparisonEntry into QuotationOffer entity
   - Eliminate 2,200 lines of sync glue code in marketing_comparison_service.py
              |
              v
[Phase 3: Frontend Monolith Decomposition]
   - Slice tenure-timeline-ledger.tsx (3,974L) into 6 modular components
   - Slice review-phase.tsx (2,760L) and comparison-matrix.tsx (2,003L)
              |
              v
[Phase 4: Workspace & Command Hygiene]
   - Archive one-off migration/cleaner scripts into commands/archive/
   - Standardize CLI entry points to PowerShell and unified scripts
```

This structured plan ensures that each incremental addition strengthens the architecture rather than adding technical debt.

