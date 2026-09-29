-- Migration: 058_marketing_comparison.sql
-- Description: Marketing Comparison tables, tenure fixed charges, and side-by-side underwriter metrics.

ALTER TABLE insurance_tenures
    ADD COLUMN IF NOT EXISTS road_tax NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    ADD COLUMN IF NOT EXISTS runner_fee NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    ADD COLUMN IF NOT EXISTS windscreen_target NUMERIC(10, 2) NULL,
    ADD COLUMN IF NOT EXISTS ncd_percentage NUMERIC(5, 2) NULL,
    ADD COLUMN IF NOT EXISTS recommended_sum_insured_json JSONB NULL;

CREATE TABLE IF NOT EXISTS tenure_comparison_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenure_id UUID NOT NULL REFERENCES insurance_tenures(id) ON DELETE CASCADE,
    session_id UUID NULL REFERENCES sessions(id) ON DELETE SET NULL,
    company_name VARCHAR(120) NOT NULL,
    company_id UUID NULL REFERENCES insurance_companies(id) ON DELETE SET NULL,
    sum_insured NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    valuation_type VARCHAR(20) NOT NULL DEFAULT 'market_value',
    motor_premium NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    road_tax NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    runner_fee NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    total_payable NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    towing_limit VARCHAR(100) NOT NULL DEFAULT 'Unlimited',
    agreed_value BOOLEAN NOT NULL DEFAULT FALSE,
    waiver_betterment BOOLEAN NOT NULL DEFAULT FALSE,
    excess NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    rate_percentage NUMERIC(8, 4) NULL,
    windscreen_sum_insured NUMERIC(10, 2) NULL,
    special_perils VARCHAR(50) NULL,
    llp_llop VARCHAR(50) NULL,
    personal_accident VARCHAR(50) NULL,
    is_recommended BOOLEAN NOT NULL DEFAULT FALSE,
    is_manual BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_tenure_comp_tenure ON tenure_comparison_entries(tenure_id);
CREATE INDEX IF NOT EXISTS idx_tenure_comp_session ON tenure_comparison_entries(session_id);
