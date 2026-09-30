-- Migration: 059_customer_identity_master.sql
-- Description: Customer account master table, government ID indexing, and vehicle/tenure entity relationships.

CREATE TABLE IF NOT EXISTS customer_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(20) NOT NULL DEFAULT 'individual',
    id_type VARCHAR(30) NOT NULL DEFAULT 'nric',
    id_number VARCHAR(50) NOT NULL,
    canonical_name VARCHAR(255) NOT NULL,
    name_aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    phone VARCHAR(50) NULL,
    email VARCHAR(120) NULL,
    address TEXT NULL,
    alternate_contacts JSONB NOT NULL DEFAULT '[]'::jsonb,
    passport_history JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_fleet BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_customer_id_number ON customer_accounts(id_number);
CREATE INDEX IF NOT EXISTS ix_customer_canonical_name ON customer_accounts(canonical_name);
CREATE INDEX IF NOT EXISTS ix_customer_is_fleet ON customer_accounts(is_fleet);

ALTER TABLE tracked_vehicles
    ADD COLUMN IF NOT EXISTS chassis_no VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS engine_no VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS customer_id UUID NULL REFERENCES customer_accounts(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_tracked_vehicles_chassis ON tracked_vehicles(chassis_no);
CREATE INDEX IF NOT EXISTS idx_tracked_vehicles_engine ON tracked_vehicles(engine_no);
CREATE INDEX IF NOT EXISTS idx_tracked_vehicles_customer ON tracked_vehicles(customer_id);

ALTER TABLE vehicle_ownerships
    ADD COLUMN IF NOT EXISTS customer_id UUID NULL REFERENCES customer_accounts(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_vehicle_ownerships_customer ON vehicle_ownerships(customer_id);

ALTER TABLE insurance_tenures
    ADD COLUMN IF NOT EXISTS customer_id UUID NULL REFERENCES customer_accounts(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_insurance_tenures_customer ON insurance_tenures(customer_id);

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS customer_id UUID NULL REFERENCES customer_accounts(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_sessions_customer ON sessions(customer_id);
