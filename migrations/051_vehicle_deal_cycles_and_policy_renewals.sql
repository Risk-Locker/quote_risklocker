-- Migration: 051_vehicle_deal_cycles_and_policy_renewals.sql
-- Description: Add coverage dates, renewal alerts, policy status, and deal cycle groupings to vehicle_ownerships and sessions.

ALTER TABLE vehicle_ownerships
    ADD COLUMN IF NOT EXISTS coverage_start_date TIMESTAMPTZ NULL;

ALTER TABLE vehicle_ownerships
    ADD COLUMN IF NOT EXISTS coverage_end_date TIMESTAMPTZ NULL;

ALTER TABLE vehicle_ownerships
    ADD COLUMN IF NOT EXISTS renewal_alert_date TIMESTAMPTZ NULL;

ALTER TABLE vehicle_ownerships
    ADD COLUMN IF NOT EXISTS policy_status VARCHAR(50) NOT NULL DEFAULT 'active';

CREATE INDEX IF NOT EXISTS idx_vehicle_ownerships_renewals ON vehicle_ownerships (coverage_end_date, renewal_alert_date);

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS deal_cycle_id VARCHAR(100) NULL;

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS coverage_start_date TIMESTAMPTZ NULL;

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS coverage_end_date TIMESTAMPTZ NULL;

CREATE INDEX IF NOT EXISTS idx_sessions_deal_cycle ON sessions (deal_cycle_id);
