# Repository Structure & Ownership Guide

This document is the architectural map of the **Risk-Locker / quote_risklocker** repository. For detailed system design, see [ARCHITECTURE.md](ARCHITECTURE.md); for business rules and invariants, see [BUSINESS-RULES.md](../domain/BUSINESS-RULES.md).

For historical release notes from v6 through v26, see [CHANGELOG-V6-V26.md](../history/CHANGELOG-V6-V26.md).

---

## 1. Top-Level Directory Layout

| Directory / File | Responsibility |
| :--- | :--- |
| `backend/` | FastAPI backend (Python 3.11): API routers, extraction pipeline, domain services, rendering engine |
| `frontend/` | Next.js 15.5 frontend (React 19, TypeScript): App router, session workspace, template canvas, comparisons |
| `migrations/` | Ordered SQL migrations applied via Supabase / PostgreSQL migration runner |
| `tests/` | Hermetic backend test suite (100% in-memory SQLite / mock based; zero live DB dependencies) |
| `commands/` | Operational scripts: local server start (`start-*.ps1`), deploy gates (`verify-deploy-gate.ps1`), DB seeding |
| `docs/` | 3-tier Agent Brain knowledge base, routing tables, and active logbooks |
| `assets/` | Production branding, company logos, and benefit icon graphic assets |
| `.qc-tmp/` | Gitignored in-repo temporary workspace: test output, QA run scripts, screenshots, and logs |
| `.github/workflows/` | CI/CD pipeline (`deploy.yml`): pre-deploy verification gate and automated VPS deployment |
| `deploy/` | Production infrastructure configs: Nginx reverse proxy and VPS bootstrap scripts |
| `ecosystem.config.cjs` | PM2 process manager configuration (`rl-quote-api`, `rl-quote-worker`, `rl-quote-frontend`) |

---

## 2. Backend Architecture (`backend/app/`)

```
backend/app/
├── api/
│   ├── routes.py            # Master route aggregation & backward-compatibility facade
│   ├── schemas.py           # Pydantic request/response validation schemas
│   └── routers/             # Domain-scoped API endpoints
│       ├── auth.py          # Authentication, user profiles, session tokens
│       ├── catalogs.py      # Insurers, benefit profiles, packages, offerings, conditions
│       ├── comparison.py    # Multi-quote comparison matrix, manual quotes, WhatsApp export
│       ├── copilot.py       # Conversational AI assistant & duplicate session cleanup
│       ├── insights.py      # Hit/Miss ledger, vehicle ownership history, client CRM dossier
│       ├── sessions.py      # PDF upload intake, extraction jobs, quotation drafts
│       ├── system.py        # Health probes, JPJ road tax rules, trash management
│       ├── templates.py     # Quotation master templates, benefit card presets, visual assets
│       └── tenures.py       # Annual insurance tenure timelines & renewal tracking
├── core/
│   ├── config.py            # App settings (pydantic-settings) & environment variables
│   ├── errors.py            # Custom exceptions and HTTP error handlers
│   └── http_security.py     # Rate limiting, auth cookies, CORS, and request security
├── db/
│   ├── database.py          # SQLAlchemy engine, session maker, connection pool
│   └── migrations.py        # Schema migration runner tracking `schema_migrations`
├── extraction/              # PDF document extraction engine
│   ├── candidate_finder.py  # Regex & text extraction for plate, premium, insurer, dates
│   ├── entity_classifier.py # Vehicle make/model classification & EV power normalization
│   ├── gemini_extractor.py  # Resilient multi-model Gemini fallback rotation
│   └── draft_mapper.py      # Normalizes extracted fields into canonical quotation drafts
├── models/
│   ├── tables.py            # Canonical SQLAlchemy ORM model definitions
│   └── enums.py             # Domain status enums (QuotationStatus, OfferingKind, etc.)
├── rendering/               # Deterministic quotation document generation
│   ├── template_renderer.py # Master HTML/PDF renderer: geometry, row heights, card grids
│   ├── benefit_grid_renderer.py # Benefit grid dynamic rendering and balancing logic
│   ├── render_context.py    # 7-tier benefit description precedence & asset overlay engine
│   └── grid_layout.py       # Fixed-grid and dynamic-flow layout calculators
├── services/                # Business logic and domain workflows
│   ├── business_setup_service.py     # Insurer setup, catalog lifecycle, benefit profiles facade
│   ├── workspace_service.py          # Quotation draft review workspace facade
│   ├── session_service.py            # Quotation session CRUD & dossier grouping
│   ├── generation_service.py         # Deterministic PDF quotation generation & storage
│   ├── marketing_comparison_service.py # 3-pane NxM comparison compilation & rate math
│   ├── insurance_tenure_service.py   # Annual renewal lifecycle & timeline ledger
│   ├── gemini_account_service.py     # Thread-safe multi-account Gemini key pooling & rotation
│   ├── road_tax_engine.py            # Official JPJ formula execution & rate math calculations
│   ├── road_tax_service.py           # Official 2026 JPJ road tax schedule & EV calculations
│   └── vehicle_tracking_service.py   # Malaysian plate normalization & ownership progression
└── storage/
    └── supabase_storage.py  # Private Supabase Storage adapter for source and quotation PDFs
```

---

## 3. Frontend Architecture (`frontend/src/`)

```
frontend/src/
├── app/
│   ├── layout.tsx                   # Root HTML shell, fonts, notifications provider
│   ├── page.tsx                     # Landing / dashboard redirect
│   ├── sessions/                    # Sessions dossier, search, vehicle grouping, bulk actions
│   │   └── [id]/                    # Unified Quotation Workspace (Preview, Review, Edit)
│   ├── comparison/                  # 3-Pane Marketing Comparison & Excel matrix workspace
│   ├── insights/                    # Teams-style calendar, Hit/Miss ledger, CRM client dossiers
│   ├── upload/                      # Single & bulk intake with Test Upload sandbox toggle
│   └── builder/
│       ├── benefits/                # 4-Tab Benefits Cockpit (Company, Catalogs, Rules, Matrix)
│       ├── global-benefits/         # Global 63-concept visual asset assignment & review
│       ├── templates/               # Quotation master template designer & preset manager
│       └── uploads/                 # Bulk upload intake limit configuration
├── components/
│   ├── session-workspace/           # Review Phase, PDF viewer, field editors, card grids
│   ├── comparison/                  # Comparison matrix, manual quote modal, WhatsApp export
│   ├── template-canvas/             # Quotation A4 preview canvas (`shared.tsx`, preset blocks)
│   ├── template-builder/            # Section-based & freeform template editor
│   ├── insights/                    # Calendar views, CRM dossiers, sync sessions modal
│   ├── tenures/                     # Renewal timeline drawer & status ledger
│   └── global-ai-copilot.tsx        # Floating conversational drawer with duplicate cleanup
└── lib/
    ├── api.ts                       # Typed frontend fetch client with same-origin proxy
    ├── template-section-compiler.ts # Bidirectional slot-to-canvas compiler
    ├── benefit-presets.ts           # System benefit card visual presets (Masonry, 3D, Minimal)
    └── benefit-utils.ts             # Benefit currency/distance formatters (RM, KM, text)
```

---

## 4. Key Developer Invariants

1. **Zero External Temporary Files**: All temporary files must stay inside `/.qc-tmp/`. Never write outside the project root.
2. **Hermetic Test Suite**: Tests in `tests/` must run against in-memory SQLite (`sqlite:///:memory:`) and never require live Postgres connections.
3. **No Silent Guesses**: Never guess uncertain extracted values; staff manual edits always take priority over AI candidates.
4. **Deploy Gate Parity**: Before committing or pushing, run `.\commands\verify-deploy-gate.ps1` to mirror CI/CD checks 1:1.
5. **Agent Brain Discipline**: Record durable changes in topic docs and append a 1-line log entry to `docs/core/STATE.md` after every interaction.
