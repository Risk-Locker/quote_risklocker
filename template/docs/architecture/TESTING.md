# Testing Strategy & Quality Gates

## 1. Test Philosophy & Rules

- **Deterministic & Isolated**: Unit tests must not depend on live external networks. Use mocks or local test databases.
- **Regression Invariants**: Every bug fix must include a test proving the failure was resolved and preventing future regression.
- **Gate Requirement**: No PR or feature may be marked done without all test suites passing with 0 errors.

## 2. Test Commands

```bash
# Run backend / unit tests
npm test # or pytest -q

# Run with coverage report
npm run test:cov # or pytest --cov

# Run frontend typecheck / linter
npx tsc --noEmit
npm run lint

# Run full brain validation
python commands/verify-brain.py
```

## 3. Test Suites & Layout

| Suite | Path | Purpose |
| :--- | :--- | :--- |
| **Unit Tests** | `tests/unit/` | Fast, isolated function and service unit tests |
| **Integration Tests** | `tests/integration/` | Database and API route end-to-end integration tests |
| **E2E / Browser Tests** | `tests/e2e/` | Playwright browser automation & user workflow tests |
