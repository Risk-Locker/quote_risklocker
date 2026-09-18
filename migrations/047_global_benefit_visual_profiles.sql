-- Migration: Global Benefit Visual Profiles & Asset Categories
-- Description: Adds category column to business_assets and creates global_benefit_profiles and global_benefit_profile_assets tables with initial active seed profile.

-- 1. Add category column to business_assets
ALTER TABLE business_assets
    ADD COLUMN IF NOT EXISTS category VARCHAR(120) NOT NULL DEFAULT 'General';

CREATE INDEX IF NOT EXISTS idx_business_assets_category ON business_assets(category);

-- Categorize existing benefit artwork as initial 3D pack
UPDATE business_assets
SET category = 'Global Benefits 3D v1'
WHERE asset_kind = 'benefit_art';

-- 2. Create global_benefit_profiles table
CREATE TABLE IF NOT EXISTS global_benefit_profiles (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(160) NOT NULL UNIQUE,
    description TEXT,
    asset_category VARCHAR(120) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT false,
    status VARCHAR(40) NOT NULL DEFAULT 'draft',
    cloned_from_id UUID REFERENCES global_benefit_profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Exactly one active visual profile globally
CREATE UNIQUE INDEX IF NOT EXISTS uq_single_active_global_benefit_profile
ON global_benefit_profiles (is_active)
WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_global_benefit_profiles_status ON global_benefit_profiles(status);
CREATE INDEX IF NOT EXISTS idx_global_benefit_profiles_asset_category ON global_benefit_profiles(asset_category);

-- 3. Create global_benefit_profile_assets table
CREATE TABLE IF NOT EXISTS global_benefit_profile_assets (
    id UUID PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES global_benefit_profiles(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES benefit_concepts(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES business_assets(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_global_benefit_profile_concept_asset UNIQUE (profile_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_gbpa_profile ON global_benefit_profile_assets(profile_id);
CREATE INDEX IF NOT EXISTS idx_gbpa_concept ON global_benefit_profile_assets(concept_id);
CREATE INDEX IF NOT EXISTS idx_gbpa_asset ON global_benefit_profile_assets(asset_id);

-- 4. Seed initial active profile
INSERT INTO global_benefit_profiles (id, name, slug, description, asset_category, is_active, status, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000010',
    'Global Benefits 3D v1',
    'global-benefits-3d-v1',
    'Default 3D isometric benefit icon pack',
    'Global Benefits 3D v1',
    true,
    'active',
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- Populate initial concept-to-asset bindings from benefit_concepts
INSERT INTO global_benefit_profile_assets (id, profile_id, concept_id, asset_id, created_at, updated_at)
SELECT
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000010',
    bc.id,
    bc.default_asset_id,
    NOW(),
    NOW()
FROM benefit_concepts bc
WHERE bc.default_asset_id IS NOT NULL
ON CONFLICT (profile_id, concept_id) DO NOTHING;
