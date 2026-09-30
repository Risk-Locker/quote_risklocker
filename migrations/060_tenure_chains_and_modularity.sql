-- Migration: 060_tenure_chains_and_modularity.sql
-- Description: Add tenure chaining, projected renewal lifecycle, 3-month reminder window, and modular date shifting fields.

ALTER TABLE insurance_tenures
    ADD COLUMN IF NOT EXISTS previous_tenure_id UUID NULL REFERENCES insurance_tenures(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS tenure_chain_id UUID NOT NULL DEFAULT gen_random_uuid(),
    ADD COLUMN IF NOT EXISTS is_projected BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS reminder_window_start TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS lapsed_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS delay_days INT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_insurance_tenures_chain ON insurance_tenures(tenure_chain_id);
CREATE INDEX IF NOT EXISTS idx_insurance_tenures_prev ON insurance_tenures(previous_tenure_id);
CREATE INDEX IF NOT EXISTS idx_insurance_tenures_projected ON insurance_tenures(is_projected);
CREATE INDEX IF NOT EXISTS idx_insurance_tenures_reminder ON insurance_tenures(reminder_window_start);
