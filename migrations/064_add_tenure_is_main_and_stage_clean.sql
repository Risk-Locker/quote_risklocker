-- Migration: 064_add_tenure_is_main_and_stage_clean.sql
-- Description: Add is_main to insurance_tenures for marking approved/primary policy periods

ALTER TABLE insurance_tenures
    ADD COLUMN IF NOT EXISTS is_main BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_insurance_tenures_is_main ON insurance_tenures(is_main);
