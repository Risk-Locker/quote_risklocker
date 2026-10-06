-- Migration 067: Insurance Tenure Stage History & Hover Timestamps
BEGIN;

ALTER TABLE insurance_tenures 
  ADD COLUMN IF NOT EXISTS stage_history JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Backfill initial stage timestamp for existing tenures
UPDATE insurance_tenures
SET stage_history = jsonb_build_object(COALESCE(stage, 'Quotations'), to_char(COALESCE(stage_updated_at, updated_at, created_at, NOW()), 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))
WHERE stage_history = '{}'::jsonb;

COMMIT;
