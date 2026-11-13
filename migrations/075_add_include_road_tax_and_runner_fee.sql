-- Migration 075: Add include_road_tax and include_runner_fee toggles
-- Supports commercial vehicles (lorries), fleets, and clients who self-renew road tax.

ALTER TABLE insurance_tenures
ADD COLUMN IF NOT EXISTS include_road_tax BOOLEAN NOT NULL DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS include_runner_fee BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE tenure_comparison_entries
ADD COLUMN IF NOT EXISTS include_road_tax BOOLEAN NOT NULL DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS include_runner_fee BOOLEAN NOT NULL DEFAULT TRUE;

