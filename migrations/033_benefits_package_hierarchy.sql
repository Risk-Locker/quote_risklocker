-- 033_benefits_package_hierarchy.sql
-- Benefits & Package refactor (Task 1 draft, owner-approved design 2026-08-16).
-- Additive only: hierarchy dimensions, scoped benefit aliases, Global Benefit
-- datasets, package kind, and catalog_offerings -> Benefit Assignment columns.
-- No data backfill (Task 10). Existing rows keep working (all columns nullable/defaulted).

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Hierarchy dimensions (database-driven, seeded defaults; admin-extendable)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_key VARCHAR(160) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.vehicle_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_key VARCHAR(160) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.vehicle_subcategories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID NOT NULL REFERENCES public.vehicle_categories(id) ON DELETE CASCADE,
    subcategory_key VARCHAR(160) NOT NULL,
    name VARCHAR(255) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_vehicle_subcategory_key UNIQUE (category_id, subcategory_key)
);

CREATE TABLE IF NOT EXISTS public.coverage_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coverage_key VARCHAR(160) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 2. Scoped benefit aliases (global | company | product | package)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.benefit_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    benefit_id UUID NOT NULL REFERENCES public.benefit_concepts(id) ON DELETE CASCADE,
    phrase VARCHAR(255) NOT NULL,
    normalized_phrase VARCHAR(255) NOT NULL,
    scope VARCHAR(40) NOT NULL DEFAULT 'global' CHECK (scope IN ('global', 'company', 'product', 'package')),
    company_id UUID REFERENCES public.insurance_companies(id) ON DELETE CASCADE,
    product_id UUID REFERENCES public.insurance_products(id) ON DELETE CASCADE,
    package_id UUID REFERENCES public.benefit_packages(id) ON DELETE CASCADE,
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (scope = 'global' AND company_id IS NULL AND product_id IS NULL AND package_id IS NULL)
        OR (scope = 'company' AND company_id IS NOT NULL AND product_id IS NULL AND package_id IS NULL)
        OR (scope = 'product' AND product_id IS NOT NULL AND package_id IS NULL)
        OR (scope = 'package' AND package_id IS NOT NULL)
    )
);

-- Scope-aware uniqueness (NULLs are distinct in a plain UNIQUE constraint)
CREATE UNIQUE INDEX IF NOT EXISTS benefit_aliases_global_uq
    ON public.benefit_aliases(benefit_id, normalized_phrase)
    WHERE scope = 'global';
CREATE UNIQUE INDEX IF NOT EXISTS benefit_aliases_company_uq
    ON public.benefit_aliases(benefit_id, normalized_phrase, company_id)
    WHERE scope = 'company';
CREATE UNIQUE INDEX IF NOT EXISTS benefit_aliases_product_uq
    ON public.benefit_aliases(benefit_id, normalized_phrase, product_id)
    WHERE scope = 'product';
CREATE UNIQUE INDEX IF NOT EXISTS benefit_aliases_package_uq
    ON public.benefit_aliases(benefit_id, normalized_phrase, package_id)
    WHERE scope = 'package';
CREATE INDEX IF NOT EXISTS benefit_aliases_benefit_idx ON public.benefit_aliases(benefit_id);

-- ---------------------------------------------------------------------------
-- 3. Global Benefit library (evolve benefit_concepts)
-- ---------------------------------------------------------------------------

ALTER TABLE public.benefit_concepts
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS demo_value JSONB,
    ADD COLUMN IF NOT EXISTS match_dataset JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS value_pattern_dataset JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0;

-- ---------------------------------------------------------------------------
-- 4. Packages: comprehensive chain | add-on bundle
-- ---------------------------------------------------------------------------

ALTER TABLE public.benefit_packages
    ADD COLUMN IF NOT EXISTS package_kind VARCHAR(40) NOT NULL DEFAULT 'comprehensive'
        CHECK (package_kind IN ('comprehensive', 'addon_bundle'));

-- ---------------------------------------------------------------------------
-- 5. catalog_offerings -> Benefit Assignment (keep table; additive columns)
-- ---------------------------------------------------------------------------

ALTER TABLE public.catalog_offerings
    ADD COLUMN IF NOT EXISTS applies_to_type VARCHAR(40)
        CHECK (applies_to_type IS NULL OR applies_to_type IN ('product', 'package', 'bundle')),
    ADD COLUMN IF NOT EXISTS applies_to_id UUID,
    ADD COLUMN IF NOT EXISTS role VARCHAR(40)
        CHECK (role IS NULL OR role IN ('included', 'addon_option', 'bundle_component')),
    ADD COLUMN IF NOT EXISTS display_value VARCHAR(500),
    ADD COLUMN IF NOT EXISTS optional_price JSONB,
    ADD CONSTRAINT catalog_offerings_applies_check CHECK (
        (applies_to_type IS NULL AND applies_to_id IS NULL)
        OR (applies_to_type IS NOT NULL AND applies_to_id IS NOT NULL)
    );

-- ---------------------------------------------------------------------------
-- 6. Catalog path context (segment/vehicle/coverage/package)
-- ---------------------------------------------------------------------------

ALTER TABLE public.benefit_catalogs
    ADD COLUMN IF NOT EXISTS segment_id UUID REFERENCES public.segments(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS vehicle_category_id UUID REFERENCES public.vehicle_categories(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS vehicle_subcategory_id UUID REFERENCES public.vehicle_subcategories(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS coverage_type_id UUID REFERENCES public.coverage_types(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS package_id UUID REFERENCES public.benefit_packages(id) ON DELETE SET NULL;

-- Package-scoped catalogs are unique per (company, product, package).
-- The legacy context index (company, product, tier) stays untouched for tier rows.
CREATE UNIQUE INDEX IF NOT EXISTS benefit_catalogs_package_context_uq
    ON public.benefit_catalogs(company_id, product_id, package_id)
    WHERE package_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 7. Quotation draft hierarchy pins (authoritative pin stays catalog_revision_id)
-- ---------------------------------------------------------------------------

ALTER TABLE public.quotation_drafts
    ADD COLUMN IF NOT EXISTS segment_id UUID REFERENCES public.segments(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS vehicle_category_id UUID REFERENCES public.vehicle_categories(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS vehicle_subcategory_id UUID REFERENCES public.vehicle_subcategories(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS coverage_type_id UUID REFERENCES public.coverage_types(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS package_id UUID REFERENCES public.benefit_packages(id) ON DELETE SET NULL;

-- ---------------------------------------------------------------------------
-- 8. Seeded hierarchy defaults (deterministic UUIDs; idempotent)
-- ---------------------------------------------------------------------------

INSERT INTO public.segments (id, segment_key, name, sort_order, status) VALUES
    ('a1111111-0000-4000-8000-000000000001', 'private', 'Private', 10, 'active'),
    ('a1111111-0000-4000-8000-000000000002', 'company_commercial', 'Company / Commercial', 20, 'active')
ON CONFLICT (segment_key) DO NOTHING;

INSERT INTO public.vehicle_categories (id, category_key, name, sort_order, status) VALUES
    ('b1111111-0000-4000-8000-000000000001', 'car', 'Car', 10, 'active'),
    ('b1111111-0000-4000-8000-000000000002', 'motorcycle', 'Motorcycle', 20, 'active'),
    ('b1111111-0000-4000-8000-000000000003', 'commercial_vehicle', 'Commercial Vehicle', 30, 'active')
ON CONFLICT (category_key) DO NOTHING;

INSERT INTO public.vehicle_subcategories (id, category_id, subcategory_key, name, sort_order, status) VALUES
    ('c1111111-0000-4000-8000-000000000001', 'b1111111-0000-4000-8000-000000000003', 'lorry_truck', 'Lorry / Truck', 10, 'active'),
    ('c1111111-0000-4000-8000-000000000002', 'b1111111-0000-4000-8000-000000000003', 'van', 'Van', 20, 'active'),
    ('c1111111-0000-4000-8000-000000000003', 'b1111111-0000-4000-8000-000000000003', 'bus', 'Bus', 30, 'active')
ON CONFLICT (category_id, subcategory_key) DO NOTHING;

INSERT INTO public.coverage_types (id, coverage_key, name, sort_order, status) VALUES
    ('d1111111-0000-4000-8000-000000000001', 'comprehensive', 'Comprehensive', 10, 'active'),
    ('d1111111-0000-4000-8000-000000000002', 'third_party_fire_theft', 'Third Party Fire & Theft', 20, 'active'),
    ('d1111111-0000-4000-8000-000000000003', 'third_party', 'Third Party', 30, 'active')
ON CONFLICT (coverage_key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 9. Lock down new tables (mirrors migrations 024/025)
-- ---------------------------------------------------------------------------

DO $$
DECLARE item TEXT;
BEGIN
    FOREACH item IN ARRAY ARRAY[
        'segments', 'vehicle_categories', 'vehicle_subcategories',
        'coverage_types', 'benefit_aliases'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', item);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon, authenticated', item);
    END LOOP;
END $$;

COMMIT;
