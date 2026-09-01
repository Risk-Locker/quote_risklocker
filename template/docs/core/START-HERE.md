# AI Startup Guide (Universal)

This is the mandatory entry point for every repository-capable AI agent and maintainer. Read this file before inspecting or changing the repository.

## 1. Working Sequence

1. Read the current request and `AGENTS.md`.
2. Assess whether the active conversation already has accurate, sufficient project context.
3. Read `docs/core/STATE.md` only when current sprint state, active invariants, or recent changes are relevant.
4. Use the routing table below to read only the necessary topic documents and the relevant implementation files. The generated code map (`docs/generated/CODEBASE-MAP.md`) is a navigation aid, not a substitute for code inspection.
5. Implement or investigate the requested work, then run the narrowest meaningful verification.
6. Before responding, reconcile the documents affected by durable project knowledge. Append a 1-2 line log entry to `docs/core/STATE.md`.

## 2. Prompt Routing Table

| Request area | Read first | Then inspect |
| :--- | :--- | :--- |
| General orientation or unclear scope | `docs/core/STATE.md`, `docs/domain/PROJECT-CONTEXT.md`, `docs/architecture/STRUCTURE.md` | `docs/generated/CODEBASE-MAP.md` |
| Visual whole-project overview | `docs/domain/PROJECT-DIAGRAM.md` | linked topic documents and implementation files |
| Product behavior, roles, workflow, accuracy | `docs/domain/BUSINESS-RULES.md` | relevant routes, services, tests |
| Frontend, UX, accessibility, styling | `docs/architecture/DESIGN-SYSTEM.md`, `docs/architecture/STRUCTURE.md` | relevant UI routes and components |
| Backend, API, authentication, authorization | `docs/architecture/ARCHITECTURE.md`, `docs/architecture/API-CONTRACT.md` | backend routes, services, schemas, tests |
| Database, schema, models, migrations | `docs/architecture/ARCHITECTURE.md`, `docs/architecture/OPERATIONS.md` | models, migrations, DB adapters |
| Testing, test failures, regression coverage | `docs/architecture/TESTING.md` | test suites and test fixtures |
| Environment, local run, scripts, retention | `docs/architecture/OPERATIONS.md`, `docs/architecture/SETUP.md` | config files and command scripts |
| Deployment, production server, infrastructure | `docs/architecture/SETUP.md` | `docs/architecture/OPERATIONS.md` env tables |
| How the owner talks / how to interpret him | `docs/core/INSTRUCTIONS.md` | `AGENTS.md` interaction rules |
| Recent work, active snapshot | `docs/core/STATE.md` | files cited in the latest entries |
| Historical work & past decisions archive | `docs/history/` | historical monthly logs (MEMORY-YYYY-MM.md) |
| Skill selection | `docs/core/SKILLS.md` | the selected skill instructions |

## 3. Documentation Registry (3-Tier Structure)

### Tier 1: Core Agent Engine (`docs/core/`)
| Document | Purpose | Update when |
| :--- | :--- | :--- |
| `docs/core/START-HERE.md` | Master entry point, routing table & doc registry | Any document is added, moved, or removed |
| `docs/core/INSTRUCTIONS.md` | How the owner talks and how agents must interpret him | Owner expresses a new interaction preference |
| `docs/core/SKILLS.md` | Agent skill routing table and installation guide | Skills are installed, removed, or changed |
| `docs/core/STATE.md` | Active working memory (<80 lines) & recent logs | After every interaction; rotate old logs to `docs/history/` |

### Tier 2: Architecture & Operations (`docs/architecture/`)
| Document | Purpose | Update when |
| :--- | :--- | :--- |
| `docs/architecture/ARCHITECTURE.md` | System boundaries, service architecture & data flows | Services, storage, or integrations change |
| `docs/architecture/API-CONTRACT.md` | HTTP route contracts, auth & payload specifications | API endpoints, payloads, or auth contracts change |
| `docs/architecture/DESIGN-SYSTEM.md` | UI design tokens, typography & layout rules | Visual styling, tokens, or component rules change |
| `docs/architecture/OPERATIONS.md` | Runtime configuration, env vars & runbook | Environment variables, scripts, or DB migrations change |
| `docs/architecture/SETUP.md` | Dev setup & deployment runbook (server, DB, SSL) | Setup, dev steps, or infrastructure changes |
| `docs/architecture/STRUCTURE.md` | Curated repository guide & ownership map | File or directory additions / deletions occur |
| `docs/architecture/TESTING.md` | Test strategy, test suites & CI/CD gates | Coverage expectations or test commands change |
| `docs/architecture/REFERENCES.md` | Asset policy & runtime reference boundaries | Asset paths or storage rules change |

### Tier 3: Domain & Business Specs (`docs/domain/`)
| Document | Purpose | Update when |
| :--- | :--- | :--- |
| `docs/domain/BUSINESS-RULES.md` | Mandatory business rules & security invariants | Business logic, compliance, or workflow rules change |
| `docs/domain/PROJECT-CONTEXT.md` | Product vision, user roles, supported workflows | Product scope or target user requirements change |
| `docs/domain/PROJECT-DIAGRAM.md` | Visual user workflow & system boundary diagram | Major user flows or system integrations change |

### History & Generated Tooling
| Document | Purpose | Update when |
| :--- | :--- | :--- |
| `docs/history/MEMORY-YYYY-MM.md` | Monthly archive of past interaction log entries | Monthly or when `docs/core/STATE.md` is rotated |
| `docs/generated/CODEBASE-MAP.md` | AST-generated symbol, route, and line map | Run `python commands/update-code-map.py --write` |

## 4. Documentation Maintenance Rules

1. **Keep `STATE.md` Lean**: When `docs/core/STATE.md` grows beyond ~80 lines, archive older entries into `docs/history/MEMORY-YYYY-MM.md`.
2. **Never Let Docs Drift**: Run `python commands/verify-brain.py` to confirm that all doc links and registry entries are valid.
3. **No Stray Markdown Files**: Every markdown document must reside in its designated subfolder and be registered in this table.
4. **Preserve Invariants**: Non-negotiable business rules in `docs/domain/BUSINESS-RULES.md` and `AGENTS.md` must never be overridden without explicit owner approval.
