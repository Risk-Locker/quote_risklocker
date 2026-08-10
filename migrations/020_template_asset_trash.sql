-- Soft-delete (trash) support for template assets.

BEGIN;

ALTER TABLE template_assets ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE template_assets ADD COLUMN IF NOT EXISTS purge_after TIMESTAMPTZ;

COMMIT;
