# Backend Engineering Rules (`backend/AGENTS.md`)

> Scoped automatically to Python / FastAPI / SQLAlchemy / Workers / Extraction / Rendering code under `backend/`.

## Hard Engineering Invariants

1. **Money & Tax Precision**:
   - NEVER use `float` or loose strings for premiums, fees, road tax, stamp duty, commissions, or discounts. Use `decimal.Decimal` (`ROUND_HALF_UP` to `0.01`) and SQLAlchemy `Numeric(12, 2)`.
   - NEVER use Python `eval()` (`road_tax_engine.py` style). Use deterministic bracket lookup tables or a strict `ast`-parsed expression evaluator with bounded operators (`+`, `-`, `*`, `/`).
2. **RBAC & HTTP Purity**:
   - Every `/admin/*`, `/settings/*`, `/users/*`, or mutation endpoint MUST enforce explicit `Depends(require_role(...))`—no implicit authenticated defaults.
   - **HTTP `GET` handlers MUST NEVER write, auto-create, repair, or commit DB transactions.** Side-effect initialization belongs strictly in explicit `POST`/`PATCH` endpoints.
3. **Storage & Worker Integrity**:
   - Production workers (`render_worker.py`, `extraction_worker.py`) must fail fast or enforce private Supabase Storage when `APP_ENV=production`—never silently fall back to `.qc-tmp/stateless_generated/`.
4. **Scalability & Queries**:
   - Ban full-table Python scans (`session.query(...).all()` / `_rows()`) on `Job`, `RenderSnapshot`, `ExtractionSession`, or `InsuranceTenure`. Always filter, join, paginate, and index in SQL.
   - Calendar renewals must use `dateutil.relativedelta(years=1)` / leap-safe calendar arithmetic—never `+364` or `+365` days.
5. **Rendering & PII Privacy**:
   - Zero hardcoded real customer names, NRICs, plate numbers, phone numbers, or bank accounts inside `backend/app/rendering/` fallbacks. Always read tenant config or explicit blank placeholders.
6. **AI Model Freshness & Calibration (`Rule 05`)**:
   - Never hardcode deprecated or retired Gemini IDs (`gemini-3.5-flash`, `gemini-3.1-flash-lite-preview`) across services; verify live `ai.google.dev` status before changing model defaults and never emit hardcoded confidence literals or truncate mid-PDF pages.
7. **Testing**:
   - All `tests/` must run 100% hermetically against in-memory SQLite/mocks under `.\.venv\Scripts\python.exe -m pytest -q`.

