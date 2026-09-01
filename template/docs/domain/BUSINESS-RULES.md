# Mandatory Business Rules & Invariants

**These non-negotiable business rules cannot be broken or altered without explicit owner approval.**

## 1. Security & Data Protection Invariants

1. **No Hardcoded Secrets**: Secrets and private keys must never be committed to git or exposed to the client browser.
2. **Access Control & RBAC**: Every mutating endpoint must enforce authentication and role permissions.
3. **Data Integrity**: Financial calculations, prices, or sensitive totals must be computed or validated server-side.

## 2. Core Domain Workflow Invariants

1. **Workflow Rule 1**: `{{DEFINE_CORE_WORKFLOW_RULE_1}}`
2. **Workflow Rule 2**: `{{DEFINE_CORE_WORKFLOW_RULE_2}}`
3. **Workflow Rule 3**: `{{DEFINE_CORE_WORKFLOW_RULE_3}}`

## 3. Error Handling & Validation Rules

- Never silently swallow exceptions or return generic error messages for valid user actions.
- Provide descriptive, field-level validation messages when user input fails constraints.
