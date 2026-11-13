# Milestone 4: Deduplication, Single Active Quote per Insurer & Storage Janitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce a single active quotation column per insurer for each vehicle renewal tenure (replacing and pruning older revisions in-place instead of accumulating confusing parallel v1, v2, v3 columns), build a robust multi-signal Cover Note vs. Quotation classifier with a 1-click manual override toggle, and implement an automated S3 & local storage janitor service to permanently eliminate duplicate PDF storage waste.

**Architecture:** 
1. **Single-Column Invariant:** Keyed on `(tenure_id, company_id)`, quotation ingestion performs an in-place upsert on `TenureComparisonEntry`. Older drafts for the same company and tenure are demoted (`is_tenure_active = False`, `duplicate_resolution = "superseded"`).
2. **Multi-Signal Document Classification:** Pure heuristic scoring engine combining page counts (1–3 pages for quotes vs 5–15+ pages for cover notes), statutory wording cues, and validity periods, augmented by an instantaneous 1-click manual override toggle in the Quotation Workspace review header.
3. **Storage Janitor:** Safe, idempotent janitor service that scans for superseded, inactive quotation files, verifies zero external foreign references (protecting active sessions, bound cover notes, and business assets), and safely purges orphan binaries from local storage or S3/Supabase.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL (NUMERIC 12,2 / Decimal), Next.js 15.5, React 19, TypeScript, Tailwind CSS (`--rl-*` tokens), Phosphor Icons, Pytest.

**Spec:** [`docs/superpowers/plans/2026-11-12-master-phased-implementation-roadmap.md`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/superpowers/plans/2026-11-12-master-phased-implementation-roadmap.md) (Phase 4).

---

## Global Constraints

- **Single Column per Insurer per Tenure:** For any vehicle tenure, uploading a revised quotation for Insurer $X$ updates or replaces the existing Insurer $X$ column. Parallel duplicate columns for the same insurer on the same tenure are strictly prohibited.
- **Zero Orphaned PII & Storage Waste:** When a quotation is superseded by a newer revision, the old file record and physical binary on disk/S3 are pruned by the janitor once no active entity references them.
- **Pure Decimal Currency:** All financial math and comparison figures continue to enforce strict Python `decimal.Decimal` and SQL `NUMERIC(12, 2)`. Python `float` is prohibited for currency calculations.
- **Accurate Document Classification:** Cover notes populate Current Policy details and advance workflow stages; quotations populate comparison entries. Neither shall masquerade as the other.
- **Enterprise Code Quality ("Reads Like Butter"):** Function nesting depth $\le 3$, intent-revealing names (`upsert_quotation_comparison_entry`, `prune_superseded_quotations`), zero `any` in new TypeScript, modular slices $\le 400$ lines.

---

## 10-Point Edge-Case & Scenario Matrix

| ID | Dimension | Specific Failure Mode Prevented in Milestone 4 |
| :--- | :--- | :--- |
| **E-01** | Null / Unknown Insurer | A quote PDF without an immediately identified insurer (fallback "New Insurer") must not crash the deduplication upsert or overwrite an existing identified quote. |
| **E-02** | Decimal Rounding & Overrides | When an older quotation is replaced, any active manual overrides (e.g. road tax toggle, custom runner fee) must be preserved without converting `NUMERIC(12, 2)` values to IEEE-754 floats. |
| **E-03** | Partial Insurer Scope | In a tenure with 3 quotes (Etiqa v1, Kurnia v1, STMB v1), uploading Etiqa v2 replaces ONLY Etiqa v1. Kurnia and STMB remain active and unaffected. |
| **E-04** | Document Type State Inversion | Toggling a document from Quotation to Cover Note in `ReviewHeader` updates `session.document_type`, anchors the cover note to `tenure.covernote_session_id`, and cleans up any comparison entry so it doesn't linger as a quote column. |
| **E-05** | Page Count Classifier Cues | 1–3 page PDFs score negatively towards Quotation (-25.0); 5–15+ page bundles score positively towards Cover Note (+35.0); 4-page ambiguous docs remain neutral, relying on wording & filename signals. |
| **E-06** | Janitor Asset Protection | The storage janitor MUST NEVER delete an `UploadedFile` if referenced by any active session (`is_tenure_active is True`), bound Cover Note (`tenure.covernote_session_id`), or `BusinessAsset`. |
| **E-07** | Concurrency / Double Submit | Simultaneous uploads for the same insurer use an atomic SQL update/merge pattern without producing duplicate `TenureComparisonEntry` records or primary key collisions. |
| **E-08** | S3 / Disk Failure Resilience | If local disk deletion or S3 API call fails during pruning (e.g. file already unlinked or temporary glitch), the janitor logs the warning, skips cleanly without failing the database transaction, and reports accurate pruned metrics. |
| **E-09** | Statutory Term Precision | Malaysian statutory terms like `"Cover Note No"`, `"Sijil Insurans"`, and `"Certificate of Insurance"` are matched with regex word boundaries to avoid false positives on casual mentions in quotation disclaimers. |
| **E-10** | Responsive UI & Accessible Toggle | The `Document Type: [ Quotation | Cover Note ]` toggle in `ReviewHeader` renders with `--rl-*` tokens, supports keyboard focus and mobile touch, and causes zero layout shifts at 80%–120% zoom. |

---

## File Structure & Decomposition Map

```
backend/app/
├── services/
│   ├── marketing_comparison_service.py # MODIFIED: Single-column upsert per company; deduplicate comparison entries
│   ├── session_service.py              # MODIFIED: Archive/demote superseded company sessions
│   └── storage_janitor_service.py      # NEW: Prune superseded uploaded PDFs and reclaim storage
├── extraction/
│   └── candidate_finder.py             # MODIFIED: Multi-signal Covernote vs Quote classifier with page count
├── workers/
│   └── extraction_worker.py            # MODIFIED: Wire page count and company session superseding on quote ingestion
├── api/routers/
│   ├── sessions.py                     # MODIFIED: Support document_type patch and tenure sync
│   └── tenures.py                      # MODIFIED: Add /tenures/{id}/prune-superseded maintenance endpoint
frontend/src/
└── components/session-workspace/
    └── review-components/
        └── review-header.tsx           # MODIFIED: Add 1-click Document Type: [ Quotation | Cover Note ] toggle
tests/
├── unit/
│   ├── test_covernote_classifier.py    # NEW: Test page count & multi-signal document type classification
│   └── test_storage_janitor_service.py # NEW: Test hermetic storage pruning, dry-run, and reference protection
└── integration/
    ├── test_single_active_quote_upsert.py # NEW: Test single-column upsert and superseded session demotion
    └── test_session_document_type_toggle.py # NEW: Test document type toggle API & tenure synchronization
```

---

## Tasks

### Task 1: Single Active Quotation Upsert Semantic

**Files:**
- Modify: `backend/app/services/marketing_comparison_service.py:370-420,1785-1850`
- Modify: `backend/app/services/session_service.py:100-150`
- Modify: `backend/app/workers/extraction_worker.py:710-745`
- Test: `tests/integration/test_single_active_quote_upsert.py`

**Interfaces:**
- Consumes:
  - `InsuranceTenure`, `Session`, `TenureComparisonEntry`, `InsuranceCompany` from `app.models.tables`
- Produces:
  - `upsert_quotation_comparison_entry(db: Session, tenure: InsuranceTenure, session: Session) -> TenureComparisonEntry`
  - `archive_superseded_company_sessions(db: Session, tenure_id: str, company_id: str | None, detected_company: str | None, current_session_id: str) -> list[str]`

- [x] **Step 1.1: Write failing integration test for single active quote upsert**  
  Create `tests/integration/test_single_active_quote_upsert.py`:
  - Create a vehicle tenure.
  - Ingest Quotation A for "Etiqa" with sum insured 50,000 and motor premium 1,200. Verify 1 comparison entry exists.
  - Ingest Quotation B (revised revision) for "Etiqa" with sum insured 55,000 and motor premium 1,300.
  - Assert that `get_marketing_comparison` returns exactly ONE column for Etiqa, updated with 55,000 and 1,300.
  - Assert that Quotation A's session has `is_tenure_active = False` and `duplicate_resolution = "superseded"`.

- [x] **Step 1.2: Run test to confirm failure**  
  Execute: `.\.venv\Scripts\pytest.exe tests/integration/test_single_active_quote_upsert.py -v`  
  Expected: FAIL (currently generates two separate Etiqa comparison entries).

- [x] **Step 1.3: Implement single active quote upsert in comparison and session services**  
  - In `backend/app/services/session_service.py`, add `archive_superseded_company_sessions`:
    ```python
    def archive_superseded_company_sessions(
        db: Session,
        tenure_id: str,
        company_id: str | None,
        detected_company: str | None,
        current_session_id: str,
    ) -> list[str]:
        """Demote older sessions for the same insurer under this tenure."""
        # Query older sessions for the same company_id / detected_company and mark is_tenure_active=False
    ```
  - In `backend/app/services/marketing_comparison_service.py`:
    - Refactor `get_marketing_comparison` so when syncing sessions to `TenureComparisonEntry`, it matches by `(tenure_id, company_id)` or `(tenure_id, company_name)`.
    - If an entry for that company already exists, update its `session_id`, `motor_premium`, `sum_insured`, and benefits in-place instead of creating a second column.
    - If historical duplicate entries exist for the same company, clean them up by keeping the latest active entry and removing or marking duplicates.
  - In `backend/app/workers/extraction_worker.py`:
    - When a revised quotation is processed, call `archive_superseded_company_sessions` to demote older sessions.

- [x] **Step 1.4: Run test to verify pass**  
  Execute: `.\.venv\Scripts\pytest.exe tests/integration/test_single_active_quote_upsert.py -v`  
  Expected: PASS.

- [x] **Step 1.5: Commit Task 1**  
  ```bash
  git add backend/app/services/marketing_comparison_service.py backend/app/services/session_service.py backend/app/workers/extraction_worker.py tests/integration/test_single_active_quote_upsert.py
  git commit -m "feat(comparison): enforce single active quotation upsert per insurer and demote superseded sessions"
  ```

---

### Task 2: Multi-Signal Covernote vs. Quotation Classifier & Review Toggle

**Files:**
- Modify: `backend/app/extraction/candidate_finder.py:145-240`
- Modify: `backend/app/workers/extraction_worker.py:615-635`
- Modify: `backend/app/api/routers/sessions.py:1050-1120`
- Modify: `frontend/src/components/session-workspace/review-components/review-header.tsx:90-130`
- Test: `tests/unit/test_covernote_classifier.py`
- Test: `tests/integration/test_session_document_type_toggle.py`

**Interfaces:**
- Consumes:
  - `score_document_type(text: str, filename: str | None = None, page_count: int | None = None) -> tuple[str, float, dict]`
  - `detect_is_covernote(text: str, filename: str | None = None, page_count: int | None = None) -> bool`
- Produces:
  - Enhanced multi-signal classifier with page count cues.
  - `PATCH /sessions/{session_id}` accepting `{"document_type": "covernote" | "quotation"}` with automatic tenure anchoring / comparison entry detachment.
  - 1-click Document Type toggle button in `ReviewHeader`.

- [x] **Step 2.1: Write failing unit test for multi-signal classifier**  
  Create `tests/unit/test_covernote_classifier.py`:
  - Test 1-3 page quote with "SEBUT HARGA" or "VALID FOR 14 DAYS" -> classifies as `"quotation"`.
  - Test 6+ page document with "CERTIFICATE OF INSURANCE" or "POLICY SCHEDULE" -> classifies as `"covernote"`.
  - Test ambiguous 4-page document defaults correctly based on text cues.
  - Test edge cases: filename "CN_1234.pdf" vs "Quotation_Etiqa.pdf".

- [x] **Step 2.2: Run classifier test to confirm failure**  
  Execute: `.\.venv\Scripts\pytest.exe tests/unit/test_covernote_classifier.py -v`  
  Expected: FAIL (`page_count` argument not supported yet).

- [x] **Step 2.3: Implement multi-signal classifier in candidate_finder.py**  
  - In `backend/app/extraction/candidate_finder.py`:
    - Update `score_document_type` and `detect_is_covernote` to accept optional `page_count: int | None = None`.
    - If `page_count` in (1, 2, 3): `breakdown["page_count_quotation"] = -25.0`, `total_score -= 25.0`.
    - If `page_count >= 5`: `breakdown["page_count_covernote"] = 35.0`, `total_score += 35.0`.
    - Add statutory regex patterns for "Cover Note No", "Certificate of Insurance", "Jadual Polisi".
    - Add quotation validity regex for "Valid for 14 days", "Valid for 30 days", "Proposal Form".
  - In `backend/app/workers/extraction_worker.py`:
    - Pass `page_count=len(pages)` to `detect_is_covernote`.

- [x] **Step 2.4: Run classifier test to verify pass**  
  Execute: `.\.venv\Scripts\pytest.exe tests/unit/test_covernote_classifier.py -v`  
  Expected: PASS.

- [x] **Step 2.5: Write integration test for document type toggle API**  
  Create `tests/integration/test_session_document_type_toggle.py`:
  - Test patching session `document_type` from `"quotation"` to `"covernote"`:
    - Verifies `session.document_type == "covernote"`.
    - Verifies tenure `covernote_session_id` is updated.
    - Verifies any existing `TenureComparisonEntry` for this session is removed/hidden.
  - Test flipping back from `"covernote"` to `"quotation"`:
    - Verifies `tenure.covernote_session_id` is cleared (if it matched this session).
    - Verifies comparison entry is restored or recreated.

- [x] **Step 2.6: Implement session document_type toggle in API and ReviewHeader UI**  
  - In `backend/app/api/routers/sessions.py`:
    - Update `PATCH /sessions/{session_id}` to handle `document_type` changes and trigger tenure re-synchronization.
  - In `frontend/src/components/session-workspace/review-components/review-header.tsx`:
    - Add 1-click toggle button:
      ```tsx
      <div className="flex items-center gap-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-0.5 bg-[var(--rl-surface-subtle)] text-xs font-semibold">
        <button
          type="button"
          onClick={() => handleToggleDocumentType("quotation")}
          className={`px-2 py-1 rounded transition-colors ${docType === "quotation" ? "bg-white text-[var(--rl-text-strong)] shadow-xs font-bold" : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"}`}
        >
          Quotation
        </button>
        <button
          type="button"
          onClick={() => handleToggleDocumentType("covernote")}
          className={`px-2 py-1 rounded transition-colors ${docType === "covernote" ? "bg-emerald-600 text-white shadow-xs font-bold" : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"}`}
        >
          Cover Note
        </button>
      </div>
      ```
    - Wire `handleToggleDocumentType` to `PATCH /sessions/${workspace.session_id}` with optimistic update and toast notification.

- [x] **Step 2.7: Run integration and unit tests to verify pass**  
  Execute: `.\.venv\Scripts\pytest.exe tests/unit/test_covernote_classifier.py tests/integration/test_session_document_type_toggle.py -v`  
  Expected: PASS.

- [x] **Step 2.8: Commit Task 2**  
  ```bash
  git add backend/app/extraction/candidate_finder.py backend/app/workers/extraction_worker.py backend/app/api/routers/sessions.py frontend/src/components/session-workspace/review-components/review-header.tsx tests/unit/test_covernote_classifier.py tests/integration/test_session_document_type_toggle.py
  git commit -m "feat(classification): implement multi-signal covernote classifier and 1-click review header toggle"
  ```

---

### Task 3: S3 & Local Storage Janitor Service

**Files:**
- Create: `backend/app/services/storage_janitor_service.py`
- Modify: `backend/app/api/routers/tenures.py:200-250`
- Test: `tests/unit/test_storage_janitor_service.py`

**Interfaces:**
- Consumes:
  - `Session`, `UploadedFile`, `InsuranceTenure`, `BusinessAsset` from `app.models.tables`
- Produces:
  - `prune_superseded_quotations(db: Session, tenure_id: str | None = None, dry_run: bool = False) -> dict[str, Any]`
  - `delete_file_safely(file_path: str | None, object_key: str | None = None) -> bool`
  - Endpoint `POST /tenures/{tenure_id}/prune-superseded`

- [x] **Step 3.1: Write failing unit test for storage janitor service**  
  Create `tests/unit/test_storage_janitor_service.py`:
  - Test dry run: identifies superseded files without deleting physical files.
  - Test active file protection: does NOT delete files referenced by active sessions or covernotes.
  - Test business asset protection: does NOT delete files referenced by `business_assets`.
  - Test actual pruning: deletes temporary disk file, marks `uploaded_file.is_deleted = True`, and returns reclaimed byte count.
  - Test error resilience: missing file on disk does not raise an exception; proceeds safely.

- [x] **Step 3.2: Run test to confirm failure**  
  Execute: `.\.venv\Scripts\pytest.exe tests/unit/test_storage_janitor_service.py -v`  
  Expected: FAIL (`storage_janitor_service` does not exist).

- [x] **Step 3.3: Implement storage janitor service**  
  Create `backend/app/services/storage_janitor_service.py`:
  - Define `prune_superseded_quotations(db: Session, tenure_id: str | None = None, dry_run: bool = False) -> dict[str, Any]`:
    - Find sessions where `is_tenure_active is False` or `duplicate_resolution == "superseded"` or `status in ("trash", "archived")`.
    - Collect `uploaded_file_id`s.
    - Check if any active session, tenure covernote, or business asset references each `uploaded_file_id`.
    - If orphaned:
      - If `dry_run is False`: safely delete physical file via `os.remove` (if path exists), handle exceptions cleanly, and mark `uploaded_file.is_deleted = True` with `uploaded_file.stored_path = None`.
      - Accumulate `reclaimed_bytes` and `pruned_files_count`.
    - Return structured metrics dictionary.
  - In `backend/app/api/routers/tenures.py`:
    - Add maintenance route `@router.post("/{tenure_id}/prune-superseded")` calling `prune_superseded_quotations`.

- [x] **Step 3.4: Run test to verify pass**  
  Execute: `.\.venv\Scripts\pytest.exe tests/unit/test_storage_janitor_service.py -v`  
  Expected: PASS.

- [x] **Step 3.5: Commit Task 3**  
  ```bash
  git add backend/app/services/storage_janitor_service.py backend/app/api/routers/tenures.py tests/unit/test_storage_janitor_service.py
  git commit -m "feat(janitor): author s3 and local storage janitor service for superseded quotation pruning"
  ```

---

### Task 4: End-to-End Verification, TypeScript Check & CI Parity Gate

**Files:**
- Modify: `docs/superpowers/plans/2026-11-12-milestone-4-deduplication-and-storage-janitor.md` (Update status to Completed)
- Modify: `docs/core/STATE.md` (Log Milestone 4 completion)

- [x] **Step 4.1: Run full pytest suite**  
  Execute: `.\.venv\Scripts\pytest.exe tests/`  
  Expected: 100% pass rate across all tests.

- [x] **Step 4.2: Run frontend TypeScript verification**  
  Execute: `cd frontend; .\node_modules\.bin\tsc.cmd --noEmit`  
  Expected: 0 errors.

- [x] **Step 4.3: Run repo cleanliness & knowledge base verification**  
  Execute: `.\.venv\Scripts\python.exe commands/verify-brain.py`  
  Expected: All checks pass.

- [x] **Step 4.4: Final commit for Milestone 4**  
  ```bash
  git add docs/superpowers/plans/2026-11-12-milestone-4-deduplication-and-storage-janitor.md docs/core/STATE.md
  git commit -m "docs(milestone-4): finalize deduplication, covernote classifier and storage janitor implementation"
  ```

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-11-12-milestone-4-deduplication-and-storage-janitor.md`. Two execution options:

1. **Subagent-Driven (recommended)** - Fresh subagent dispatched per task, review checkpoints between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using `superpowers:executing-plans`, batch execution with review checkpoints.

Which approach would you like to take?
