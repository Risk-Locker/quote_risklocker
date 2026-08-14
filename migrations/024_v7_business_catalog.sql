-- v7 additive business identity, provenance, assets, catalogs, packages, and imports.

BEGIN;

CREATE TABLE IF NOT EXISTS public.legal_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name VARCHAR(255) NOT NULL,
    registration_no VARCHAR(120),
    jurisdiction VARCHAR(80) NOT NULL DEFAULT 'MY',
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.insurance_companies
    ADD COLUMN IF NOT EXISTS legal_entity_id UUID REFERENCES public.legal_entities(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS slug VARCHAR(160),
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1;
CREATE UNIQUE INDEX IF NOT EXISTS insurance_companies_slug_uq ON public.insurance_companies(slug) WHERE slug IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.business_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_key VARCHAR(200) NOT NULL UNIQUE,
    asset_kind VARCHAR(40) NOT NULL CHECK (asset_kind IN ('company_logo', 'benefit_art', 'template_art', 'other')),
    label VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(120) NOT NULL,
    content_hash CHAR(64) NOT NULL,
    storage_path VARCHAR(800) NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    width_px INTEGER CHECK (width_px IS NULL OR width_px > 0),
    height_px INTEGER CHECK (height_px IS NULL OR height_px > 0),
    has_transparency BOOLEAN,
    derivative_manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    status VARCHAR(40) NOT NULL DEFAULT 'unassigned',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS business_assets_content_hash_idx ON public.business_assets(content_hash);
CREATE INDEX IF NOT EXISTS business_assets_kind_status_idx ON public.business_assets(asset_kind, status);

ALTER TABLE public.insurance_companies
    ADD COLUMN IF NOT EXISTS logo_asset_id UUID REFERENCES public.business_assets(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS insurance_companies_logo_asset_idx ON public.insurance_companies(logo_asset_id);

CREATE TABLE IF NOT EXISTS public.company_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.insurance_companies(id) ON DELETE CASCADE,
    alias VARCHAR(255) NOT NULL,
    normalized_alias VARCHAR(255) NOT NULL UNIQUE,
    alias_kind VARCHAR(40) NOT NULL DEFAULT 'detection',
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS company_aliases_company_idx ON public.company_aliases(company_id);

CREATE TABLE IF NOT EXISTS public.insurance_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.insurance_companies(id) ON DELETE CASCADE,
    product_key VARCHAR(160) NOT NULL,
    name VARCHAR(255) NOT NULL,
    channel VARCHAR(120),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_product_company_key UNIQUE (company_id, product_key)
);

CREATE TABLE IF NOT EXISTS public.insurance_product_tiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES public.insurance_products(id) ON DELETE CASCADE,
    tier_key VARCHAR(160) NOT NULL,
    name VARCHAR(255) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_product_tier_key UNIQUE (product_id, tier_key)
);

CREATE TABLE IF NOT EXISTS public.source_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issuer VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    reference_url VARCHAR(1500),
    reference_text TEXT,
    effective_from DATE,
    effective_to DATE,
    checksum CHAR(64) NOT NULL,
    verification_status VARCHAR(40) NOT NULL DEFAULT 'unverified' CHECK (verification_status IN ('unverified', 'verified', 'superseded', 'rejected')),
    reviewed_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from)
);
CREATE INDEX IF NOT EXISTS source_documents_checksum_idx ON public.source_documents(checksum);

CREATE TABLE IF NOT EXISTS public.benefit_concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_key VARCHAR(160) NOT NULL UNIQUE,
    label VARCHAR(255) NOT NULL,
    value_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    display_template VARCHAR(500) NOT NULL DEFAULT '{label}',
    required_variables JSONB NOT NULL DEFAULT '[]'::jsonb,
    optional_variables JSONB NOT NULL DEFAULT '[]'::jsonb,
    validation_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    default_asset_id UUID REFERENCES public.business_assets(id) ON DELETE SET NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.benefit_facets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_concept_id UUID NOT NULL REFERENCES public.benefit_concepts(id) ON DELETE CASCADE,
    facet_key VARCHAR(160) NOT NULL,
    label VARCHAR(255) NOT NULL,
    asset_id UUID REFERENCES public.business_assets(id) ON DELETE SET NULL,
    display_template VARCHAR(500),
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_benefit_facet_key UNIQUE (parent_concept_id, facet_key)
);

CREATE TABLE IF NOT EXISTS public.benefit_catalogs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES public.insurance_companies(id) ON DELETE CASCADE,
    product_id UUID REFERENCES public.insurance_products(id) ON DELETE CASCADE,
    tier_id UUID REFERENCES public.insurance_product_tiers(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    status VARCHAR(40) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (company_id IS NOT NULL OR status = 'compatibility')
);
CREATE UNIQUE INDEX IF NOT EXISTS benefit_catalogs_context_uq
    ON public.benefit_catalogs(company_id, COALESCE(product_id, '00000000-0000-0000-0000-000000000000'::uuid), COALESCE(tier_id, '00000000-0000-0000-0000-000000000000'::uuid));

CREATE TABLE IF NOT EXISTS public.benefit_catalog_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_id UUID NOT NULL REFERENCES public.benefit_catalogs(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL CHECK (revision_number >= 1),
    state VARCHAR(40) NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'published', 'retired', 'compatibility')),
    source_document_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_hash CHAR(64) NOT NULL,
    published_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_catalog_revision UNIQUE (catalog_id, revision_number),
    CHECK ((state = 'published' AND published_at IS NOT NULL) OR state <> 'published')
);

CREATE TABLE IF NOT EXISTS public.catalog_offerings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_revision_id UUID NOT NULL REFERENCES public.benefit_catalog_revisions(id) ON DELETE CASCADE,
    offering_key VARCHAR(160) NOT NULL,
    concept_id UUID NOT NULL REFERENCES public.benefit_concepts(id) ON DELETE RESTRICT,
    offering_kind VARCHAR(40) NOT NULL CHECK (offering_kind IN ('base', 'optional', 'package_component')),
    label_override VARCHAR(255),
    typed_value JSONB,
    source_document_id UUID REFERENCES public.source_documents(id) ON DELETE SET NULL,
    source_citation JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    presentation_facet_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_catalog_offering_key UNIQUE (catalog_revision_id, offering_key)
);

CREATE TABLE IF NOT EXISTS public.benefit_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_revision_id UUID NOT NULL REFERENCES public.benefit_catalog_revisions(id) ON DELETE CASCADE,
    from_offering_id UUID NOT NULL REFERENCES public.catalog_offerings(id) ON DELETE CASCADE,
    to_offering_id UUID NOT NULL REFERENCES public.catalog_offerings(id) ON DELETE CASCADE,
    relation_kind VARCHAR(40) NOT NULL CHECK (relation_kind IN ('replaces', 'supplements', 'requires', 'alternative_to', 'package_contains', 'presentation_of')),
    branch_key VARCHAR(160),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_benefit_relation UNIQUE (catalog_revision_id, from_offering_id, relation_kind, to_offering_id),
    CHECK (from_offering_id <> to_offering_id)
);

CREATE TABLE IF NOT EXISTS public.benefit_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_revision_id UUID NOT NULL REFERENCES public.benefit_catalog_revisions(id) ON DELETE CASCADE,
    package_key VARCHAR(160) NOT NULL,
    name VARCHAR(255) NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_benefit_package_key UNIQUE (catalog_revision_id, package_key)
);

CREATE TABLE IF NOT EXISTS public.benefit_package_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id UUID NOT NULL REFERENCES public.benefit_packages(id) ON DELETE CASCADE,
    plan_key VARCHAR(160) NOT NULL,
    name VARCHAR(255) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_benefit_package_plan_key UNIQUE (package_id, plan_key)
);

CREATE TABLE IF NOT EXISTS public.benefit_package_plan_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES public.benefit_package_plans(id) ON DELETE CASCADE,
    offering_id UUID NOT NULL REFERENCES public.catalog_offerings(id) ON DELETE RESTRICT,
    typed_value_override JSONB,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_benefit_package_plan_item UNIQUE (plan_id, offering_id)
);

CREATE TABLE IF NOT EXISTS public.catalog_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requested_by UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    idempotency_key VARCHAR(160) NOT NULL UNIQUE,
    state VARCHAR(40) NOT NULL DEFAULT 'dry_run' CHECK (state IN ('dry_run', 'validated', 'applied', 'failed')),
    source_filename VARCHAR(255) NOT NULL,
    source_checksum CHAR(64) NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1 CHECK (schema_version >= 1),
    report JSONB NOT NULL DEFAULT '{}'::jsonb,
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.template_assets
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS original_filename VARCHAR(255),
    ADD COLUMN IF NOT EXISTS content_hash CHAR(64);
UPDATE public.template_assets SET original_filename = filename WHERE original_filename IS NULL;
CREATE INDEX IF NOT EXISTS template_assets_content_hash_idx ON public.template_assets(content_hash);

CREATE OR REPLACE FUNCTION public.prevent_published_catalog_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state = 'published' THEN
        RAISE EXCEPTION 'Published catalog revisions are immutable';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;
DROP TRIGGER IF EXISTS benefit_catalog_revision_immutable ON public.benefit_catalog_revisions;
CREATE TRIGGER benefit_catalog_revision_immutable
BEFORE UPDATE OR DELETE ON public.benefit_catalog_revisions
FOR EACH ROW EXECUTE FUNCTION public.prevent_published_catalog_mutation();

CREATE OR REPLACE FUNCTION public.prevent_published_catalog_child_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE revision_id UUID;
BEGIN
    revision_id := COALESCE(NEW.catalog_revision_id, OLD.catalog_revision_id);
    IF EXISTS (SELECT 1 FROM public.benefit_catalog_revisions WHERE id = revision_id AND state = 'published') THEN
        RAISE EXCEPTION 'Rows belonging to a published catalog revision are immutable';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;
DROP TRIGGER IF EXISTS catalog_offering_immutable ON public.catalog_offerings;
CREATE TRIGGER catalog_offering_immutable BEFORE UPDATE OR DELETE ON public.catalog_offerings
FOR EACH ROW EXECUTE FUNCTION public.prevent_published_catalog_child_mutation();
DROP TRIGGER IF EXISTS benefit_relation_immutable ON public.benefit_relations;
CREATE TRIGGER benefit_relation_immutable BEFORE UPDATE OR DELETE ON public.benefit_relations
FOR EACH ROW EXECUTE FUNCTION public.prevent_published_catalog_child_mutation();
DROP TRIGGER IF EXISTS benefit_package_immutable ON public.benefit_packages;
CREATE TRIGGER benefit_package_immutable BEFORE UPDATE OR DELETE ON public.benefit_packages
FOR EACH ROW EXECUTE FUNCTION public.prevent_published_catalog_child_mutation();

DO $$
DECLARE item TEXT;
BEGIN
    FOREACH item IN ARRAY ARRAY[
        'legal_entities','business_assets','company_aliases','insurance_products','insurance_product_tiers',
        'source_documents','benefit_concepts','benefit_facets','benefit_catalogs','benefit_catalog_revisions',
        'catalog_offerings','benefit_relations','benefit_packages','benefit_package_plans',
        'benefit_package_plan_items','catalog_imports'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', item);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon, authenticated', item);
    END LOOP;
END $$;

COMMIT;
