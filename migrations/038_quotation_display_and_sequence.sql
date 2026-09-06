-- Add display_options JSONB to quotation_drafts
ALTER TABLE quotation_drafts ADD COLUMN IF NOT EXISTS display_options JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Add display_overrides JSONB to benefit_concepts
ALTER TABLE benefit_concepts ADD COLUMN IF NOT EXISTS display_overrides JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Create sequence for quotation ref
CREATE SEQUENCE IF NOT EXISTS quotation_ref_seq START WITH 1;

-- Add quotation_ref to sessions
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS quotation_ref TEXT;

-- Truncate correction_memory to wipe noisy AI data
TRUNCATE TABLE correction_memory;
