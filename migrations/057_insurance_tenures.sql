-- Migration: 057_insurance_tenures.sql
-- Description: Insurance Tenure foundation, tenure-level session grouping, version tracking, and upload deduplication content hash.

CREATE TABLE IF NOT EXISTS insurance_tenures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tracked_vehicle_id UUID NOT NULL REFERENCES tracked_vehicles(id) ON DELETE CASCADE,
    ownership_id UUID NULL REFERENCES vehicle_ownerships(id) ON DELETE SET NULL,
    vehicle_no VARCHAR(50) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    coverage_start_date TIMESTAMPTZ NOT NULL,
    coverage_end_date TIMESTAMPTZ NOT NULL,
    expiry_month VARCHAR(7) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    winning_company_id UUID NULL REFERENCES insurance_companies(id) ON DELETE SET NULL,
    winning_quotation_ref VARCHAR(50) NULL,
    won_premium NUMERIC(12, 2) NULL,
    miss_reason VARCHAR(100) NULL,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_insurance_tenures_vehicle ON insurance_tenures(tracked_vehicle_id);
CREATE INDEX IF NOT EXISTS idx_insurance_tenures_expiry_month ON insurance_tenures(expiry_month);
CREATE INDEX IF NOT EXISTS idx_insurance_tenures_vehicle_dates ON insurance_tenures(tracked_vehicle_id, coverage_start_date, coverage_end_date);
CREATE INDEX IF NOT EXISTS idx_insurance_tenures_status ON insurance_tenures(status);

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS tenure_id UUID NULL REFERENCES insurance_tenures(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS tenure_version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS is_tenure_active BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64) NULL;

CREATE INDEX IF NOT EXISTS idx_sessions_tenure_id ON sessions(tenure_id);
CREATE INDEX IF NOT EXISTS idx_sessions_content_hash ON sessions(content_hash);
