-- Soft-delete (trash) support for templates, our specials, variants, and client records.

BEGIN;

ALTER TABLE output_template_configs ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE output_template_configs ADD COLUMN IF NOT EXISTS purge_after TIMESTAMPTZ;

ALTER TABLE our_specials ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE our_specials ADD COLUMN IF NOT EXISTS purge_after TIMESTAMPTZ;

ALTER TABLE our_special_variants ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE our_special_variants ADD COLUMN IF NOT EXISTS purge_after TIMESTAMPTZ;

ALTER TABLE client_records ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE client_records ADD COLUMN IF NOT EXISTS purge_after TIMESTAMPTZ;

COMMIT;
