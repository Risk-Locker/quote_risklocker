-- Migration: Unified Global Benefit Profiles Architecture
-- Description: Establishes a global benefit_profiles table representing unified system-wide version profiles across all insurance companies, linking company_benefit_configs and company_benefit_conditions.

CREATE TABLE IF NOT EXISTS benefit_profiles (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version_number INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT false,
    status VARCHAR(40) NOT NULL DEFAULT 'draft',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Exactly one active profile globally
CREATE UNIQUE INDEX IF NOT EXISTS uq_single_active_benefit_profile
ON benefit_profiles (is_active)
WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_benefit_profiles_status ON benefit_profiles(status);
CREATE INDEX IF NOT EXISTS idx_benefit_profiles_version ON benefit_profiles(version_number);

-- Insert baseline active unified profile
INSERT INTO benefit_profiles (id, name, version_number, is_active, status, notes, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Main Unified Baseline (14/09/2026)',
    1,
    true,
    'active',
    'Default unified active profile across all insurance companies',
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- Migrate company_benefit_configs
ALTER TABLE company_benefit_configs DROP CONSTRAINT IF EXISTS company_benefit_configs_profile_id_fkey;
ALTER TABLE company_benefit_configs DROP CONSTRAINT IF EXISTS uq_profile_concept_config;

UPDATE company_benefit_configs
SET profile_id = '00000000-0000-0000-0000-000000000001'
WHERE profile_id IS NOT NULL OR profile_id IS NULL;

ALTER TABLE company_benefit_configs
    ADD CONSTRAINT company_benefit_configs_profile_id_fkey
    FOREIGN KEY (profile_id) REFERENCES benefit_profiles(id) ON DELETE CASCADE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_company_profile_concept_config'
    ) THEN
        ALTER TABLE company_benefit_configs
            ADD CONSTRAINT uq_company_profile_concept_config
            UNIQUE (company_id, profile_id, concept_id);
    END IF;
END $$;

-- Migrate company_benefit_conditions
ALTER TABLE company_benefit_conditions DROP CONSTRAINT IF EXISTS company_benefit_conditions_profile_id_fkey;

UPDATE company_benefit_conditions
SET profile_id = '00000000-0000-0000-0000-000000000001'
WHERE profile_id IS NOT NULL OR profile_id IS NULL;

ALTER TABLE company_benefit_conditions
    ADD CONSTRAINT company_benefit_conditions_profile_id_fkey
    FOREIGN KEY (profile_id) REFERENCES benefit_profiles(id) ON DELETE CASCADE;

-- Drop legacy per-company profiles table
DROP TABLE IF EXISTS company_benefit_profiles CASCADE;
