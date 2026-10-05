-- Migration: 065_insurance_tenure_created_by.sql
-- Description: Add created_by_id attribution to insurance_tenures

ALTER TABLE insurance_tenures
    ADD COLUMN IF NOT EXISTS created_by_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_insurance_tenures_created_by_id ON insurance_tenures(created_by_id);
