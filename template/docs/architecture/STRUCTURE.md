# Repository Structure

## Top-Level Directory Ownership

| Directory / File | Responsibility |
| :--- | :--- |
| `src/` (or `frontend/`, `backend/`) | Core application source code |
| `migrations/` | Database schema migrations and rollback scripts |
| `tests/` | Unit, integration, and end-to-end regression tests |
| `commands/` | Maintenance scripts, doc linters, and operational automation |
| `docs/` | Governed 3-tier project knowledge base and generated code map |
| `AGENTS.md` | Master AI agent instructions and universal behavioral contract |

## 3-Tier Documentation Layout

- `docs/core/`: Universal portable agent engine (`START-HERE.md`, `INSTRUCTIONS.md`, `SKILLS.md`, `STATE.md`).
- `docs/architecture/`: Technical architecture, API contracts, design system, database operations, testing.
- `docs/domain/`: Pure domain specifications, business rules, product scope.
- `docs/history/`: Episodic monthly logbook archives (`MEMORY-YYYY-MM.md`).
- `docs/generated/`: AST symbol, route, and line mapping (`CODEBASE-MAP.md`).
