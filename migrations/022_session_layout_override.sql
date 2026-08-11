-- Session-scoped layout override: an edited canvas layout saved for one session
-- only (never touches the master template). generate uses it when present.

BEGIN;

ALTER TABLE quotation_drafts
    ADD COLUMN IF NOT EXISTS layout_override JSON;

COMMIT;
