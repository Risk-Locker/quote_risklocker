# Risklocker AI Startup Guide

This is the mandatory entry point for every repository-capable AI agent and maintainer. Read this file before inspecting or changing the repository.

External chat tools cannot be forced to follow repository instructions. Give them this file and the needed project documents before asking them to work on the project.

## Working Sequence

1. Read the current request and `AGENTS.md`.
2. Assess whether the active conversation already has accurate, sufficient project context.
3. Read `MEMORY.md` only when the context is missing, stale, broad, cross-cutting, or inconsistent.
4. Use the routing table below to read only the necessary topic documents and the relevant implementation files. The generated code map is a navigation aid, not a substitute for code inspection.
5. Implement or investigate the requested work, then run the narrowest meaningful verification.
6. Before responding, reconcile the documents affected by durable project knowledge. Do not create documentation changes for a scan, question, or response that changed no durable fact.

## Prompt Routing

| Request area | Read first | Then inspect |
| --- | --- | --- |
| General orientation or unclear scope | `MEMORY.md`, `PROJECT-CONTEXT.md`, `STRUCTURE.md` | `generated/CODEBASE-MAP.md` |
| Visual whole-project overview | `PROJECT-DIAGRAM.md` | linked topic documents and implementation files |
| Product behavior, roles, workflow, accuracy | `BUSINESS-RULES.md` | relevant routes, services, tests |
| Frontend, UX, accessibility, template editor | `DESIGN-SYSTEM.md`, `STRUCTURE.md` | relevant Next.js routes and components |
| Backend, API, authentication, authorization | `ARCHITECTURE.md`, `API-CONTRACT.md` | routes, services, RBAC, tests |
| Extraction or review values | `BUSINESS-RULES.md`, `ARCHITECTURE.md` | extraction modules, fixtures, regression tests |
| Templates or PDF generation | `BUSINESS-RULES.md`, `ARCHITECTURE.md`, `REFERENCES.md` | renderer, template config, builder, assets |
| Database, Supabase, storage, migrations | `ARCHITECTURE.md`, `OPERATIONS.md` | models, migrations, storage services |
| Insurer benefit/add-on catalogs, packages, coverage | `BENEFITS-CONFIGURATION.md`, `BUSINESS-RULES.md` | seed scripts, benefit_setup_service, builder |
| Testing, failures, regression coverage | `TESTING.md` | relevant tests and implementation |
| Environment, local run, deployment, retention | `OPERATIONS.md`, `SETUP.md` | config and command scripts |
| Deployment, VPS, subdomains, infrastructure | `SETUP.md` | `OPERATIONS.md` env tables |
| How the owner talks / how to interpret him | `INSTRUCTIONS.md` | AGENTS.md interaction rules |
| Recent work, logbook, current snapshot | `MEMORY.md` | files cited in the latest entries |
| Documentation maintenance | this file, `MEMORY.md` if needed | the affected canonical document |
| Skill selection | `SKILLS.md` | the selected skill instructions |

## Documentation Registry

| Document | Canonical purpose | Update when |
| --- | --- | --- |
| `MEMORY.md` | Short current project snapshot + ultra-short logbook of every interaction | after every interaction, without waiting for git commit |
| `INSTRUCTIONS.md` | How the owner talks and how agents must interpret him | owner expresses a new preference or interaction rule |
| `PROJECT-CONTEXT.md` | Product purpose, users, scope | product scope or supported workflows change |
| `PROJECT-DIAGRAM.md` | Single visual map of user flow, features, and system boundaries | workflow, routes, roles, major services, or integrations change |
| `BUSINESS-RULES.md` | Mandatory workflow, security, and business rules | rules, roles, data-retention, or review behavior changes |
| `ARCHITECTURE.md` | System boundaries and data flow | services, storage, integrations, or data flow change |
| `STRUCTURE.md` | Curated repository guide | top-level ownership or navigation changes (file add/delete) |
| `DESIGN-SYSTEM.md` | UI and accessibility rules | visual, interaction, or workflow-screen rules change |
| `API-CONTRACT.md` | HTTP contract summary | API behavior, auth, or file-access contract changes |
| `TESTING.md` | Test strategy and commands | coverage expectations, fixtures, or checks change |
| `OPERATIONS.md` | Configuration and runbook | environment, scripts, migrations, or deployment changes |
| `SETUP.md` | Deployment runbook (VPS, subdomain, DB, storage, monitoring) | any infrastructure change; always placeholders only |
| `SKILLS.md` | Agent skill routing | skills installed, removed, or routing policy changes |
| `REFERENCES.md` | Runtime asset and private-reference policy | reference locations or asset policy changes |
| `BENEFITS-CONFIGURATION.md` | Canonical per-insurer benefit/add-on configuration matrix (company × coverage × vehicle × add-on system) | any insurer catalog, coverage type, or vehicle config changes |
| `generated/CODEBASE-MAP.md` | Detailed generated source map | structure, routes, schema, environment, or major behavior changes |

Do not add a Markdown document unless it has a distinct long-term purpose that cannot be incorporated into a registered document. Add it to this registry in the same change. Generated documentation belongs in `docs/generated/` and must identify its generator.

## Documentation Rules

- Keep `MEMORY.md` concise and current. Replace stale statements; do not turn it into an activity log or changelog.
- Record a durable decision in both `MEMORY.md` and its canonical topic document when it changes how future work must be done.
- Never document secrets, customer PDFs, generated PDFs, private source-document contents, or service-role credentials.
- Preserve the project constraints in `AGENTS.md` and `BUSINESS-RULES.md`.
- After structural changes, run `python commands/update-code-map.py --write`, then run its `--check` mode before finishing.
