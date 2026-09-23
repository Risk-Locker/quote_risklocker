-- Migration: 050_quotation_insights_and_vehicle_tracking.sql
-- Description: Create tracked_vehicles, vehicle_ownerships, and quotation_activities for Insights & Analytics Hit and Miss tracking.

CREATE TABLE IF NOT EXISTS tracked_vehicles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_no VARCHAR(50) NOT NULL UNIQUE,
    car_brand VARCHAR(120) NULL,
    car_model VARCHAR(160) NULL,
    engine_cc VARCHAR(50) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tracked_vehicles_vehicle_no ON tracked_vehicles (vehicle_no);

CREATE TABLE IF NOT EXISTS vehicle_ownerships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id UUID NOT NULL REFERENCES tracked_vehicles(id) ON DELETE CASCADE,
    customer_name VARCHAR(255) NOT NULL,
    valid_from VARCHAR(50) NULL,
    valid_until VARCHAR(50) NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    sequence_order INT NOT NULL DEFAULT 1,
    source_session_id UUID NULL REFERENCES sessions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vehicle_ownerships_vehicle_id ON vehicle_ownerships (vehicle_id);
CREATE INDEX IF NOT EXISTS idx_vehicle_ownerships_current ON vehicle_ownerships (vehicle_id, is_current);

CREATE TABLE IF NOT EXISTS quotation_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    vehicle_no VARCHAR(50) NOT NULL,
    customer_name VARCHAR(255) NULL,
    action_type VARCHAR(50) NOT NULL DEFAULT 'quote_generated',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version_number INT NOT NULL DEFAULT 1,
    sent_to_client BOOLEAN NOT NULL DEFAULT FALSE,
    summary TEXT NOT NULL DEFAULT '',
    addons_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    miss_reason VARCHAR(100) NULL,
    won_premium NUMERIC(12, 2) NULL,
    notes TEXT NULL,
    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quotation_activities_session_id ON quotation_activities (session_id);
CREATE INDEX IF NOT EXISTS idx_quotation_activities_vehicle_no ON quotation_activities (vehicle_no);
CREATE INDEX IF NOT EXISTS idx_quotation_activities_timestamp ON quotation_activities (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_quotation_activities_status ON quotation_activities (status);

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS quotation_status VARCHAR(50) NOT NULL DEFAULT 'pending';

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ NULL;

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS miss_reason VARCHAR(100) NULL;

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS tracked_vehicle_id UUID NULL REFERENCES tracked_vehicles(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_sessions_quotation_status ON sessions (quotation_status);
