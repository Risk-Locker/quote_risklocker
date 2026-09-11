-- Migration: Add description_override to catalog_offerings
-- Description: Allows company, scenario, and vehicle specific benefit short description overrides while maintaining fallback to global benefit concepts.

ALTER TABLE catalog_offerings
    ADD COLUMN IF NOT EXISTS description_override TEXT;
