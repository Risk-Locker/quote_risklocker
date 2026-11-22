-- 087_bundled_benefits_architecture.sql
-- First-class DB-driven Bundled Benefits ("Mystery Box") system:
--   - company_benefit_bundles: Company + BenefitProfile scoped bundle triggers & aliases
--   - company_benefit_bundle_tiers: Plan versions (Plan 1 / Plan 2 / Plan 3 / Plan 4 / EV Plan / Default)
--   - company_benefit_bundle_effects: 1-to-many Box 1 suppression & Box 2 unlocked effects
--   - draft_benefit_selections.bundle_tier_id: Exact persisted plan version per selection
--   - tenure_comparison_entries.review_flags: Uncertain/needs-review markers across Comparison Matrix

BEGIN;

CREATE TABLE IF NOT EXISTS public.company_benefit_bundles (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES public.insurance_companies(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES public.benefit_profiles(id) ON DELETE CASCADE,
    bundle_key VARCHAR(120) NOT NULL,
    name VARCHAR(255) NOT NULL,
    primary_concept_id UUID NOT NULL REFERENCES public.benefit_concepts(id) ON DELETE CASCADE,
    trigger_concept_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    match_aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    catalog_scope VARCHAR(160),
    force_box2 BOOLEAN NOT NULL DEFAULT TRUE,
    has_plan_tiers BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_benefit_bundles_company_profile
    ON public.company_benefit_bundles(company_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_company_benefit_bundles_primary_concept
    ON public.company_benefit_bundles(primary_concept_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_company_benefit_bundle_profile_key
    ON public.company_benefit_bundles(company_id, profile_id, bundle_key)
    WHERE profile_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_company_benefit_bundle_global_key
    ON public.company_benefit_bundles(company_id, bundle_key)
    WHERE profile_id IS NULL;

CREATE TABLE IF NOT EXISTS public.company_benefit_bundle_tiers (
    id UUID PRIMARY KEY,
    bundle_id UUID NOT NULL REFERENCES public.company_benefit_bundles(id) ON DELETE CASCADE,
    tier_key VARCHAR(80) NOT NULL,
    label VARCHAR(120) NOT NULL,
    match_tokens JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_default_fallback BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_company_benefit_bundle_tier_key UNIQUE (bundle_id, tier_key)
);

CREATE INDEX IF NOT EXISTS idx_company_benefit_bundle_tiers_bundle
    ON public.company_benefit_bundle_tiers(bundle_id);

CREATE TABLE IF NOT EXISTS public.company_benefit_bundle_effects (
    id UUID PRIMARY KEY,
    tier_id UUID NOT NULL REFERENCES public.company_benefit_bundle_tiers(id) ON DELETE CASCADE,
    target_concept_id UUID NOT NULL REFERENCES public.benefit_concepts(id) ON DELETE CASCADE,
    effect_type VARCHAR(40) NOT NULL DEFAULT 'upgrade_to_box2'
        CHECK (effect_type IN ('upgrade_to_box2', 'add_to_box2', 'hide_from_box1')),
    display_title VARCHAR(255),
    display_value VARCHAR(120),
    display_description TEXT,
    icon_hint VARCHAR(80),
    comparison_value VARCHAR(120),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_benefit_bundle_effects_tier
    ON public.company_benefit_bundle_effects(tier_id);
CREATE INDEX IF NOT EXISTS idx_company_benefit_bundle_effects_target
    ON public.company_benefit_bundle_effects(target_concept_id);

ALTER TABLE public.draft_benefit_selections
    ADD COLUMN IF NOT EXISTS bundle_tier_id UUID
        REFERENCES public.company_benefit_bundle_tiers(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_draft_benefit_selections_bundle_tier
    ON public.draft_benefit_selections(bundle_tier_id);

ALTER TABLE public.tenure_comparison_entries
    ADD COLUMN IF NOT EXISTS review_flags JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
DECLARE item TEXT;
BEGIN
    FOREACH item IN ARRAY ARRAY[
        'company_benefit_bundles',
        'company_benefit_bundle_tiers',
        'company_benefit_bundle_effects'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', item);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon, authenticated', item);
    END LOOP;
END $$;

COMMIT;
