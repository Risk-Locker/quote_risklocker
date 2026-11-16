# Project Knowledge Base Index (`START-HERE.md`)

> Progressive-disclosure entry point for `docs/` (**Project Knowledge Base**), paired with the portable **Agent Harness** (`.agents/`). Read this before inspecting or modifying the application codebase.

External chat tools without workspace access should be given this file plus the needed topic docs before working on the project.

## 1. Working Sequence

1. Read the current request and `AGENTS.md`.
2. Assess whether the active conversation already has accurate, sufficient project context.
3. Read `docs/core/STATE.md` only when current sprint state, active invariants, or recent changes are relevant.
4. Use the routing table below to read only the necessary topic documents and the relevant implementation files. The generated code map (`docs/generated/CODEBASE-MAP.md`) and Graphify AST hub report (`docs/generated/GRAPH_REPORT.md`) are navigation aids, not substitutes for code inspection.
5. Implement or investigate the requested work, then run the narrowest meaningful verification.
6. Before responding, reconcile the documents affected by durable project knowledge. Append a 1-2 line log entry to `docs/core/STATE.md`.

## 2. Prompt Routing Table

| Request area | Read first | Then inspect |
| :--- | :--- | :--- |
| General orientation or unclear scope | `docs/core/STATE.md`, `docs/domain/PROJECT-CONTEXT.md`, `docs/architecture/STRUCTURE.md` | `docs/generated/CODEBASE-MAP.md` |
| SaaS Architecture, Data Integrity & Scalability | `docs/domain/SAAS-BLUEPRINT.md`, `docs/architecture/ARCHITECTURE.md` | models, migrations, services, API contracts |
| Visual whole-project overview | `docs/domain/PROJECT-DIAGRAM.md` | linked topic documents and implementation files |
| Product design intent, personas, UX philosophy | `docs/domain/DESIGN-INTENT.md` | `docs/domain/PROJECT-CONTEXT.md`, `docs/architecture/DESIGN-SYSTEM.md` |
| Product behavior, roles, workflow, accuracy | `docs/domain/BUSINESS-RULES.md` | relevant routes, services, tests |
| Frontend, UX, accessibility, template editor | `docs/architecture/DESIGN-SYSTEM.md`, `docs/architecture/STRUCTURE.md` | relevant Next.js routes and components |
| Backend, API, authentication, authorization | `docs/architecture/ARCHITECTURE.md`, `docs/architecture/API-CONTRACT.md` | routes, services, RBAC, tests |
| Extraction or review values | `docs/domain/BUSINESS-RULES.md`, `docs/architecture/ARCHITECTURE.md` | extraction modules, fixtures, regression tests |
| Templates or PDF generation | `docs/domain/BUSINESS-RULES.md`, `docs/architecture/ARCHITECTURE.md`, `docs/architecture/DESIGN-SYSTEM.md`, `docs/architecture/REFERENCES.md` | renderer, template config, builder, assets |
| Database, Supabase, storage, migrations | `docs/architecture/ARCHITECTURE.md`, `docs/architecture/OPERATIONS.md` | models, migrations, storage services |
| Insurer benefit catalogs, packages, matrix | `docs/domain/benefits/BENEFITS-CONFIGURATION.md`, `docs/domain/benefits/INSURER-CATALOG-DETAILS.md`, `docs/benefits/concise/all_benefits.md`, `docs/benefits/concise/company_all_benefits-v4.md` | seed scripts, benefit_setup_service, builder |
| Testing, failures, regression coverage | `docs/architecture/TESTING.md` | relevant tests and implementation |
| Environment, local run, deployment, retention | `docs/architecture/OPERATIONS.md`, `docs/architecture/SETUP.md` | config and command scripts |
| Deployment, VPS, subdomains, infrastructure | `docs/architecture/SETUP.md` | `docs/architecture/OPERATIONS.md` env tables |
| Commit, push, publish branch, or deploy pre-flight | `docs/architecture/TESTING.md`, `docs/core/INSTRUCTIONS.md` | `AGENTS.md`, `.github/workflows/deploy.yml` |
| How the owner talks / how to interpret him | `docs/core/INSTRUCTIONS.md` | `AGENTS.md` interaction rules |
| Recent work, active snapshot | `docs/core/STATE.md` | files cited in the latest entries |
| Enterprise audit & v30.1 freeze planning | `docs/change/00-master-index-and-roadmap/2026-11-10_18-09__master-index-and-roadmap__a-to-z-site-inventory-and-phased-execution-plan.md` | relevant domain/module dossier in `docs/change/` |
| Historical work & past decisions archive | `docs/history/MEMORY-2026-08.md`, `docs/history/CHANGELOG-V6-V26.md` | historical entries by date / version |
| Skill selection, vault tiers, plugins & freshness gates | `docs/core/SKILLS.md`, `docs/generated/SKILLS-INDEX.md` | target `.agents/skills/`, `.agents/plugins/`, or `skills-vault/` |
| SDLC, Core Use Cases & Architecture Analysis | `docs/SDLC/SYSTEM-ANALYSIS-AND-CORE-USECASES.md` | relevant domain routes & services |

## 3. Documentation Registry (3-Tier Structure)

### Tier 1: Core Context & Working Memory (`docs/core/`)
| Document | Purpose | Update when |
| :--- | :--- | :--- |
| `docs/core/START-HERE.md` | Progressive-disclosure index & doc registry | Any document is added, moved, or removed |
| `docs/core/INSTRUCTIONS.md` | How the owner talks and how agents must interpret requests | Owner expresses a new interaction preference |
| `docs/core/SKILLS.md` | Agent Skills routing & Cold Archive contract | Skill workflow or vault rules change |
| `docs/core/STATE.md` | Active working memory (<80 lines) & recent sprint log | After every interaction; rotate old logs to `docs/history/` |

### Tier 2: Architecture & Operations (`docs/architecture/`)
| Document | Purpose | Update when |
| :--- | :--- | :--- |
| `docs/architecture/ARCHITECTURE.md` | System boundaries, service architecture & data flows | Services, storage, or integrations change |
| `docs/architecture/API-CONTRACT.md` | HTTP route contracts, auth & file access | API endpoints, payloads, or auth contracts change |
| `docs/architecture/DESIGN-SYSTEM.md` | UI design tokens, typography & canvas layout rules | Visual styling, tokens, or canvas rules change |
| `docs/architecture/OPERATIONS.md` | Runtime configuration, env vars & runbook | Environment variables, scripts, or DB migrations change |
| `docs/architecture/SETUP.md` | Deployment runbook (VPS, Nginx, PM2, DB, SSL) | VPS or infrastructure setup changes |
| `docs/architecture/STRUCTURE.md` | Curated repository guide & ownership map | File or directory additions / deletions occur |
| `docs/architecture/TESTING.md` | Test strategy, test suites & CI/CD gates | Coverage expectations or test commands change |
| `docs/architecture/REFERENCES.md` | Asset policy & runtime reference boundaries | Asset paths or storage rules change |
| `docs/architecture/DYNAMIC-AUTO-FIT-PLAN.md` | Dynamic benefit auto-fit & multi-line title layout plan | Layout engine formulas or benefit grid scaling rules change |


### Tier 3: Domain & Business Specs (`docs/domain/`)
| Document | Purpose | Update when |
| :--- | :--- | :--- |
| `docs/domain/BUSINESS-RULES.md` | Mandatory business rules & security invariants | Business logic, compliance, or workflow rules change |
| `docs/domain/DESIGN-INTENT.md` | Product philosophy, staff/customer personas & UX invariants | UX philosophy, user expectations, or design contracts change |
| `docs/domain/SAAS-BLUEPRINT.md` | North Star SaaS blueprint, relational integrity & enterprise standards | Multi-tenancy, entity relations, or API contract standards change |
| `docs/domain/PROJECT-CONTEXT.md` | Product vision, user roles, supported workflows | Product scope or target user requirements change |
| `docs/domain/PROJECT-DIAGRAM.md` | Visual user workflow & system boundary diagram | Major user flows or system integrations change |
| `docs/domain/benefits/BENEFITS-CONFIGURATION.md` | Canonical 51-concept insurer & vehicle matrix | Insurer benefit configurations or seed lists change |
| `docs/domain/benefits/INSURER-CATALOG-DETAILS.md` | Detailed breakdown per insurer plan and rider | In-depth insurer plan details change |
| `docs/domain/benefits/COMMERCIAL-LORRY-CATALOG-COMPARISON.md` | Commercial lorry/truck vs private car benefit catalog comparison | Commercial vehicle benefit rules change |
| `docs/benefits/concise/all_benefits.md` | Master normalized 79-benefit catalog across all 7 insurers | Expanded benefit catalogs change |
| `docs/benefits/concise/company_all_benefits-v4.md` | Insurer-specific breakdown (Defaults vs Add-ons) across all 7 underwriters | Insurer benefit catalogs change |
| `docs/benefits/concise/current_all_benefits_12092026.md` | Active insurer benefit profile catalog (11/09/2026 snapshot) without OD/TPPD in Comprehensive | Active insurer profile versions change |
| `docs/benefits/concise/amgen.md` | AmAssurance / Liberty detailed tier & defaults breakdown reference | Insurer benefit profiles change |
| `docs/benefits/expanded/` | Full expanded markdown catalogs converted from underwriter DOCX files (AmAssurance.md, BerjayaSompo.md, Etiqa.md, Lonpac.md, QBE.md, STMB.md, TuneProtect.md) | Raw insurer coverage specifications change |

### Tier 4: Enterprise Forensic Audit & Planning (`docs/change/`)
| Document | Purpose | Update when |
| :--- | :--- | :--- |
| `docs/change/00-git-checkpoint-log.md` | Immutable `v30.1` checkpoint metadata & 6/6 CI gate verification log (`f8c410a`) | Reference baseline; do not mutate |
| `docs/change/00-master-index-and-roadmap/2026-11-10_18-09__master-index-and-roadmap__a-to-z-site-inventory-and-phased-execution-plan.md` | Master A-to-Z codebase inventory, P0–P3 findings ledger & phased remediation roadmap | Scope, priorities, or remediation phase statuses change |
| `docs/change/00-master-index-and-roadmap/2026-11-11_11-32__master-index-and-roadmap__step4-external-agent-repos-and-factory-evaluation.md` | Step 4 live evaluation matrix of 10 external agent frameworks vs local skills & Option 2 blueprint | Agent factory design, repos, or model-agnostic bridges change |
| `docs/change/00-master-index-and-roadmap/2026-11-11_12-59__master-index-and-roadmap__ai-factory-v2-single-vault-and-sacred-root.md` | AI Factory v2.0 upgrade architecture: Sacred Root (`AGENTS.md` only), 100+ Skill Vault, lockfile & local-install guard | Skill vault scaling, IDE bridges, or root contract rules change |
| `docs/change/01-usecases-and-system-design/2026-11-10_18-09__usecases-and-system-design__actors-lifecycles-state-machines-and-invariants.md` | Enterprise actors, end-to-end quotation/tenure/ledger state machines & failure invariants | Actor roles, workflows, or domain invariants change |
| `docs/change/02-database-and-data-models/2026-11-10_18-09__database-and-data-models__enterprise-normalized-schema-erd-and-migrations.md` | Normalized enterprise schema audit, ERD, FK/trigger gaps & migration remediation blueprints | Schema audit findings or target migrations change |
| `docs/change/03-pseudocode-blueprints/2026-11-10_18-09__pseudocode-blueprints__core-domain-engines-pseudocode.md` | Language-agnostic pseudocode specs for road tax, towing, benefits, PDF/storage & ledger engines | Core engine designs are refined prior to coding |
| `docs/change/04-architecture-variants-tournament/2026-11-10_18-10__architecture-variants-tournament__backend-rendering-state-and-api-tradeoffs.md` | Comparative trade-off matrix across rendering, state management, DB & queue architectures | Architectural variant decisions change |
| `docs/change/05-systematic-and-broken-logic/2026-11-10_18-10__systematic-and-broken-logic__backend-and-calculation-root-cause-forensics.md` | Textbook forensics of backend calculation bugs, storage bypasses, N+1 scans & silent failures | Backend root-cause findings or fixes are logged |
| `docs/change/06-ui-ux-and-design-consistency/2026-11-10_18-10__ui-ux-and-design-consistency__enterprise-ui-ux-simplification-and-cognitive-load.md` | Enterprise UI/UX simplification, cognitive-load audit, native modal & visual token alignment | UI/UX audit findings or design standards change |
| `docs/change/07-frontend-architecture/2026-11-10_18-10__frontend-architecture__component-modularity-state-and-route-consolidation.md` | Frontend monolith decomposition, client-side math removal & duplicate route consolidation | Frontend architecture specs change |
| `docs/change/08-security-and-compliance/2026-11-10_18-10__security-and-compliance__appsec-rbac-middleware-csrf-and-pii-audit.md` | AppSec audit: RBAC gaps, proxy middleware coverage, RAM rate limits & leaked PII fallbacks | Security audit findings or mitigations change |
| `docs/change/09-domain-modules/quotation-workspace/2026-11-10_18-12__quotation-workspace__audit-and-architecture-cure.md` | Deep module audit & cure for quotation builder, NRIC/preview bugs & template studio | Quotation workspace designs change |
| `docs/change/09-domain-modules/motor-quotation-comparison/2026-11-10_18-12__motor-quotation-comparison__audit-and-architecture-cure.md` | Deep module audit & cure for motor comparison, towing/NCD evaluators & tenure generation | Comparison engine designs change |
| `docs/change/09-domain-modules/ledger-and-accounting/2026-11-10_18-12__ledger-and-accounting__audit-and-architecture-cure.md` | Deep module audit & cure for ledger triggers, float money columns, runner fees & reconciliation | Ledger/accounting designs change |
| `docs/change/09-domain-modules/ai-and-automation-engine/2026-11-10_18-12__ai-and-automation-engine__audit-and-architecture-cure.md` | Deep module audit & cure for Gemini PDF extraction, AI context overrides, copilot & insights | AI/extraction pipeline designs change |

### Tier 5: SDLC & Architecture Audits (`docs/SDLC/`)
| Document | Purpose | Update when |
| :--- | :--- | :--- |
| `docs/SDLC/SYSTEM-ANALYSIS-AND-CORE-USECASES.md` | Core use cases, architectural forensic analysis & SDLC review | Core features or SDLC roadmap change |

### Active Implementation Plans (`docs/plans/`)
| Document | Purpose | Update when |
| :--- | :--- | :--- |
| `docs/plans/2026-11-13-ai-fleet-and-template-lifecycle.md` | AI Fleet quota equilibrium, living pacer, towing dynamic upgrade & template lifecycle plan | Active sprint tasks change or complete |
| `docs/plans/2026-11-14-phase-1-critical-p0-backend-and-security-hotfixes.md` | Critical P0 backend, storage, RBAC, AST formula evaluator & road tax monotonicity plan | Active sprint tasks change or complete |
| `docs/plans/2026-11-14-phase-2-db-schema-and-double-entry-ledger.md` | Database schema hardening, immutability restoration, partial indexes & double-entry ledger | Active sprint tasks change or complete |
| `docs/plans/2026-11-14-phase-3-backend-engines-and-api-purity.md` | Backend core engines, query performance, leap-safe calendar dates & API purity | Active sprint tasks change or complete |
| `docs/plans/2026-11-14-phase-4-frontend-demonolithization-and-ux.md` | Frontend de-monolithization, Playwright vector PDF export & PII cleansing | Active sprint tasks change or complete |
| `docs/plans/2026-11-15-phase-5-ai-pipeline-hardening-and-verification.md` | AI pipeline hardening, Gemini model lockdown & 10/10 verification gauntlet | Active sprint tasks change or complete |
| `docs/plans/2026-11-15-master-remediation-and-features-plan.md` | Master remediation of 7 domains, dynamic Gemini model selection, catalog studio assistant & token telemetry | Active sprint tasks change or complete |
| `docs/plans/2026-11-15-fleet-independent-key-controls.md` | Gemini AI Parallel Fleet independent key controls, Active multi-key status, kill-switches & dynamic capacity scaling | Active sprint tasks change or complete |
| `docs/plans/2026-11-15-design2-precision-and-builder-consolidation-plan.md` | Design 2 precision, "Template as Builder" view/unview toggles, ghost template cleanup & studio modernization | Active sprint tasks change or complete |
| `docs/plans/2026-11-16-pre-commit-hygiene-and-gate-readiness-plan.md` | Pre-commit repository hygiene, agency bank details harmonization & 10/10 gate readiness | Active sprint tasks change or complete |
| `docs/plans/2026-11-16-ci-cd-pipeline-hardening-and-deploy-monitoring-plan.md` | CI/CD deployment pipeline hardening, runner environment variables & mandatory deploy monitoring | Active sprint tasks change or complete |
| `docs/plans/2026-11-16-system-precision-fleet-and-assets-remediation.md` | Master plan for extraction referee gate, Google PT fleet quota window, assets library UX & Design 2 typography | Active sprint tasks change or complete |
| `docs/plans/milestone-1-extraction-referee-and-naming.md` | Extraction referee gate, commercial lorry classification & alphanumeric vehicle model formatting | Milestone 1 execution |
| `docs/plans/milestone-2-ai-fleet-pt-calendar-and-pacing.md` | Google AI Studio PT midnight quota cycle, account reset & batch assigner 70s pacing stagger | Milestone 2 execution |
| `docs/plans/milestone-3-ai-fleet-monitoring-dashboard.md` | AI fleet monitoring dashboard, Google PT cycle countdown, animated minute-bucket charts & timeline | Milestone 3 execution |
| `docs/plans/milestone-4-assets-library-ux-and-cleanup.md` | Assets library sticky toolbar, inspection details modal & dummy logo database cleanup | Milestone 4 execution |
| `docs/plans/milestone-5-marketing-comparison-state-hardening.md` | Marketing comparison stuck status timeout fallback & action footer cleanup | Milestone 5 execution |
| `docs/plans/milestone-6-design2-typography-and-fonts.md` | Design 2 typography & font pairing hierarchy (Helvetica, Calibri, Source Han Sans) | Milestone 6 execution |
| `docs/plans/2026-11-16-quotation-workspace-stabilization.md` | Quotation workspace stabilization, CostStatus normalization, vehicle model deduplication & fee toggle sync | Active sprint tasks change or complete |
| `docs/plans/ENTERPRISE-LEVEL-Extraction-2026-11-16-1830.md` | Master field rationalization, workspace schema unification & 3-Tier Multi-Level AI loop vision | Master enterprise architecture reference |
| `docs/plans/PLAN-1-DATABASE-CORE-AND-SYNC-ENGINE.md` | Immutable database core, key alignment, concurrency protection & real-time synchronization engine | Plan 1 execution |
| `docs/plans/PLAN-2-WORKSPACE-UI-AND-3-TIER-AI-LOOP.md` | Streamlined workspace UI, field pruning, Eye 2 auditor & Eye 3 pre-flight referee loop | Plan 2 execution |
| `docs/plans/milestone-1-db-core-and-decimal-math-cleanup.md` | Clean code remediation M1: PostgreSQL schema parity, pure Decimal math & sync service slicing | Milestone 1 execution |
| `docs/plans/milestone-2-frontend-deslop-and-component-deduplication.md` | Clean code remediation M2: Dead code purge, benefit card deduplication & zero client-side math | Milestone 2 execution |
| `docs/plans/milestone-3-patch-engine-slicing-and-3eye-wiring.md` | Clean code remediation M3: Workspace patch engine flattening & live 3-Eye referee wiring | Milestone 3 execution |
| `docs/plans/2026-11-17-principal-fintech-audit-and-master-roadmap.md` | Principal Fintech 7-pillar architectural audit & 6-milestone zero-touch master roadmap | Active sprint tasks change or complete |
| `docs/plans/milestone-1-sandbox-isolation-and-sessions-redesign.md` | Milestone 1: Test/Sandbox ledger isolation, N+1 session fix & `/sessions` activity command center | Milestone 1 execution |

### History & Generated Tooling
| Document | Purpose | Update when |
| :--- | :--- | :--- |
| `docs/history/MEMORY-YYYY-MM.md` | Monthly archive of past interaction log entries | Monthly or when `docs/core/STATE.md` is rotated |
| `docs/history/CHANGELOG-V6-V26.md` | Historical architectural additions and versioned changelogs (v6-v26) | Historical archive reference |
| `docs/history/USER-CHRONICLE-IDEA-SPEC.md` | Historical user discussions and serial chronicles | Reference archive |
| `docs/generated/CODEBASE-MAP.md` | AST-generated symbol, route, and line map | Run `python commands/update-code-map.py --write` |
| `docs/generated/GRAPH_REPORT.md` | Graphify AST community, god-node & dependency hub report (`--code-only`) | Re-run Graphify `extract` + `cluster-only` after major refactors |
| `docs/generated/SKILLS-INDEX.md` | Auto-generated Active vs Cold Skill Vault catalog, scope & boot token summary | Run `python commands/skills-manager.py index` (or `install`/`mount`/`unmount`) |

## 4. Documentation Maintenance Rules

1. **Keep `STATE.md` Lean**: When `docs/core/STATE.md` grows beyond ~80 lines, archive older entries into `docs/history/MEMORY-YYYY-MM.md`.
2. **Never Let Docs Drift**: Run `python commands/verify-brain.py` to confirm that all doc links and registry entries are valid.
3. **No Stray Markdown Files**: Every markdown document must reside in its designated subfolder and be registered in this table.
4. **Preserve Invariants**: Non-negotiable business rules in `docs/domain/BUSINESS-RULES.md` and `AGENTS.md` must never be overridden without explicit owner approval.
