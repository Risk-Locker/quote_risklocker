-- 078: Add field-level manual_overrides JSONB to tenure_comparison_entries
ALTER TABLE tenure_comparison_entries
    ADD COLUMN IF NOT EXISTS manual_overrides JSONB NOT NULL DEFAULT '[]'::jsonb;
