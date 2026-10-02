-- Migration: 063_tracked_vehicle_yom_and_tenure_lifecycle.sql
-- Description: Add manufacture_year to tracked_vehicles, add is_hidden, tenure_type, and superseded_by to insurance_tenures, and expand comparison entries with rank, betterment, towing_km, and version.

ALTER TABLE tracked_vehicles
    ADD COLUMN IF NOT EXISTS manufacture_year INT NULL;

CREATE INDEX IF NOT EXISTS idx_tracked_vehicles_manufacture_year ON tracked_vehicles(manufacture_year);

ALTER TABLE insurance_tenures
    ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS tenure_type VARCHAR(50) NOT NULL DEFAULT 'variable',
    ADD COLUMN IF NOT EXISTS superseded_by_tenure_id UUID NULL REFERENCES insurance_tenures(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_insurance_tenures_is_hidden ON insurance_tenures(is_hidden);
CREATE INDEX IF NOT EXISTS idx_insurance_tenures_superseded_by ON insurance_tenures(superseded_by_tenure_id);

ALTER TABLE tenure_comparison_entries
    ADD COLUMN IF NOT EXISTS rank INT NULL,
    ADD COLUMN IF NOT EXISTS betterment_rate NUMERIC(5, 2) NULL,
    ADD COLUMN IF NOT EXISTS betterment_display VARCHAR(50) NULL,
    ADD COLUMN IF NOT EXISTS towing_km VARCHAR(50) NULL,
    ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMPTZ NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_tenure_comparison_entries_rank ON tenure_comparison_entries(rank);
