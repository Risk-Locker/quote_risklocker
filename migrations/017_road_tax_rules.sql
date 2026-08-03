-- Migration: Create road_tax_rules table
-- Description: Configurable road-tax rates by vehicle type, owner type, and CC range

CREATE TABLE IF NOT EXISTS road_tax_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_type VARCHAR(50) NOT NULL DEFAULT 'Car',
    owner_type VARCHAR(50) NOT NULL DEFAULT 'Individual',
    jurisdiction VARCHAR(100) NOT NULL DEFAULT 'West Malaysia',
    min_cc INT NOT NULL DEFAULT 0,
    max_cc INT,
    base_rate NUMERIC(12, 2) NOT NULL DEFAULT 0,
    formula TEXT,
    source VARCHAR(255),
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_road_tax_rules_vehicle ON road_tax_rules(vehicle_type, owner_type, jurisdiction);
CREATE INDEX IF NOT EXISTS idx_road_tax_rules_status ON road_tax_rules(status);

COMMENT ON TABLE road_tax_rules IS 'Configurable road-tax rates by vehicle type, owner type, jurisdiction and CC range';
COMMENT ON COLUMN road_tax_rules.formula IS 'Optional formula string like "280 + 0.50 * (cc - 1800)". If set, overrides base_rate.';
