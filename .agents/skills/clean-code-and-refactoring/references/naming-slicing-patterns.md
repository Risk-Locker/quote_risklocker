# Naming, Guard Clauses & Safe Monolith Slicing Patterns

## 1. Guard Clauses Over Deep Nesting

```python
# BAD (4 levels deep, unclear exit condition)
def assign_covernote(session, payload):
    if session is not None:
        if payload.plate:
            if not session.is_deleted:
                if is_covernote(payload):
                    return _save(session, payload)
    return None

# GOOD (flat guard clauses, crystal clear contract)
def assign_covernote(session: QuotationSession | None, payload: CovernoteInput) -> CovernoteAssignment:
    if session is None or session.is_deleted:
        raise SessionNotFoundError("Active quotation session is required")
    if not payload.normalized_plate:
        raise InvalidVehiclePlateError("Valid registration plate is required")
    if not is_covernote_document(payload):
        return CovernoteAssignment.skipped(reason="Document classified as quotation, not covernote")
    return _persist_covernote(session, payload)
```

## 2. Cleanly Decomposing React Monoliths (`>600` Lines)

Keep top-level page/coordinator as a crisp assembly shell (`<= 300` lines) delegating cleanly into a colocated folder:
```text
components/session-workspace/review/
├── index.ts                      # Public re-export (keeps parent imports clean)
├── review-workspace.tsx          # Layout + phase coordination (<300L)
├── types.ts                      # Strict DTO interfaces (<150L)
├── hooks/
│   └── use-review-draft.ts       # AbortController fetch, validation, explicit state (<250L)
└── panels/
    ├── policyholder-form.tsx     # Dedicated typed form card (<250L)
    └── benefits-manager.tsx      # Uses shadcn primitives & --rl-* tokens (<300L)
```

## 3. Clean Decomposition Checklist Before Merging
- Every exported function has explicit parameter/return type annotations (Python types & strict TypeScript — no unnecessary `Any`/`any`).
- Parent re-exports preserved during phased refactors so callers don't break mid-migration.
- Zero unused imports, commented dead functions, or duplicated currency/date utilities.

