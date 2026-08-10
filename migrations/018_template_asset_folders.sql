-- Organize template assets into folders (categories) for the template builder.

BEGIN;

ALTER TABLE template_assets
    ADD COLUMN IF NOT EXISTS folder VARCHAR(120) NOT NULL DEFAULT 'Uncategorized';

COMMIT;
