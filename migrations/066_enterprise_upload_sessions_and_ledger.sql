-- Migration 066: Enterprise Upload Sessions, Card Visibility, PIC WhatsApp & Annual Ledger
BEGIN;

-- 1. Card visibility and manual ranking on comparison entries
ALTER TABLE tenure_comparison_entries 
  ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS manual_rank INTEGER NULL;

-- 2. Lineage, duplicate resolution, and upload session tracking
ALTER TABLE sessions 
  ADD COLUMN IF NOT EXISTS duplicate_of_session_id UUID NULL REFERENCES sessions(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS duplicate_resolution VARCHAR(50) NULL DEFAULT 'pending', -- 'pending', 'kept', 'replaced', 'removed'
  ADD COLUMN IF NOT EXISTS batch_session_index INTEGER NOT NULL DEFAULT 1;

-- 3. External competitor retention and discard state on tenures
ALTER TABLE insurance_tenures 
  ADD COLUMN IF NOT EXISTS is_discarded BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS external_policy_start_date TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS external_policy_end_date TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Backfill last_activity_at from stage_updated_at or created_at
UPDATE insurance_tenures 
SET last_activity_at = COALESCE(stage_updated_at, updated_at, created_at)
WHERE last_activity_at IS NOT NULL;

-- 4. Person In Charge WhatsApp & Default Owner Flag
ALTER TABLE person_in_charge 
  ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR(50) NULL,
  ADD COLUMN IF NOT EXISTS is_owner BOOLEAN NOT NULL DEFAULT FALSE;

-- 5. Performance Indexes
CREATE INDEX IF NOT EXISTS idx_tenure_comparison_entries_hidden ON tenure_comparison_entries(tenure_id, is_hidden);
CREATE INDEX IF NOT EXISTS idx_sessions_duplicate_of ON sessions(duplicate_of_session_id);
CREATE INDEX IF NOT EXISTS idx_tenures_annual_ledger ON insurance_tenures(tracked_vehicle_id, is_discarded, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS idx_pic_whatsapp ON person_in_charge(whatsapp_number);

COMMIT;
