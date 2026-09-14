-- Migration: Company Benefit Profiles & Global Cascade Architecture
-- Description: Introduces company_benefit_profiles for versioned benefit configurations, re-scopes company_benefit_configs and company_benefit_conditions with profile_id, and backfills baseline profiles for existing insurance companies.

CREATE TABLE IF NOT EXISTS company_benefit_profiles (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES insurance_companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    version_number INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT false,
    status VARCHAR(40) NOT NULL DEFAULT 'draft',
    parent_profile_id UUID REFERENCES company_benefit_profiles(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_company_profile_slug UNIQUE (company_id, slug)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_company_active_profile
ON company_benefit_profiles (company_id)
WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_benefit_profiles_company ON company_benefit_profiles(company_id);
CREATE INDEX IF NOT EXISTS idx_benefit_profiles_status ON company_benefit_profiles(company_id, status);

-- Insert baseline active profile for all existing insurance companies
INSERT INTO company_benefit_profiles (id, company_id, name, slug, version_number, is_active, status, notes, created_at, updated_at)
SELECT
    gen_random_uuid(),
    id,
    'Main Baseline (14/09/2026)',
    'main-baseline-14092026',
    1,
    true,
    'active',
    'Initial active baseline profile',
    NOW(),
    NOW()
FROM insurance_companies
ON CONFLICT (company_id, slug) DO NOTHING;

-- Add profile_id to company_benefit_configs
ALTER TABLE company_benefit_configs
    ADD COLUMN IF NOT EXISTS profile_id UUID REFERENCES company_benefit_profiles(id) ON DELETE CASCADE;

-- Backfill profile_id in company_benefit_configs
UPDATE company_benefit_configs
SET profile_id = (
    SELECT p.id FROM company_benefit_profiles p
    WHERE p.company_id = company_benefit_configs.company_id AND p.is_active = true
    LIMIT 1
)
WHERE profile_id IS NULL;

-- Drop old unique constraint on (company_id, concept_id) and add new one on (profile_id, concept_id)
ALTER TABLE company_benefit_configs DROP CONSTRAINT IF EXISTS uq_company_concept_config;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_profile_concept_config'
    ) THEN
        ALTER TABLE company_benefit_configs ADD CONSTRAINT uq_profile_concept_config UNIQUE (profile_id, concept_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_company_benefit_configs_profile ON company_benefit_configs(profile_id);

-- Add profile_id to company_benefit_conditions
ALTER TABLE company_benefit_conditions
    ADD COLUMN IF NOT EXISTS profile_id UUID REFERENCES company_benefit_profiles(id) ON DELETE CASCADE;

-- Backfill profile_id in company_benefit_conditions
UPDATE company_benefit_conditions
SET profile_id = (
    SELECT p.id FROM company_benefit_profiles p
    WHERE p.company_id = company_benefit_conditions.company_id AND p.is_active = true
    LIMIT 1
)
WHERE profile_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_company_benefit_conditions_profile ON company_benefit_conditions(profile_id);
