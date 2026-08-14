-- v7 additive extraction-line and reviewed quotation state.

BEGIN;

ALTER TABLE public.extraction_records
    ADD COLUMN IF NOT EXISTS benefit_lines JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS company_resolution JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS public.extraction_benefit_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_record_id UUID NOT NULL REFERENCES public.extraction_records(id) ON DELETE CASCADE,
    line_id VARCHAR(160) NOT NULL,
    raw_label TEXT NOT NULL,
    normalized_label VARCHAR(500) NOT NULL,
    page_number INTEGER CHECK (page_number IS NULL OR page_number >= 1),
    section VARCHAR(255),
    source_scope VARCHAR(60) NOT NULL DEFAULT 'unknown',
    line_kind VARCHAR(60) NOT NULL DEFAULT 'unknown',
    inclusion_state VARCHAR(40) NOT NULL DEFAULT 'unknown',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    candidate_mappings JSONB NOT NULL DEFAULT '[]'::jsonb,
    extracted_value JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_extraction_benefit_line UNIQUE (extraction_record_id, line_id)
);

ALTER TABLE public.quotation_drafts
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS scalar_decisions JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES public.insurance_companies(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS product_id UUID REFERENCES public.insurance_products(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS tier_id UUID REFERENCES public.insurance_product_tiers(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS catalog_revision_id UUID REFERENCES public.benefit_catalog_revisions(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS layout_override_template_id UUID REFERENCES public.output_template_configs(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS layout_override_base_hash CHAR(64);
CREATE INDEX IF NOT EXISTS quotation_drafts_company_idx ON public.quotation_drafts(company_id);
CREATE INDEX IF NOT EXISTS quotation_drafts_catalog_revision_idx ON public.quotation_drafts(catalog_revision_id);

CREATE TABLE IF NOT EXISTS public.draft_benefit_selections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id UUID NOT NULL REFERENCES public.quotation_drafts(id) ON DELETE CASCADE,
    selection_key VARCHAR(160) NOT NULL,
    catalog_offering_id UUID REFERENCES public.catalog_offerings(id) ON DELETE SET NULL,
    concept_id UUID REFERENCES public.benefit_concepts(id) ON DELETE SET NULL,
    source_line_id UUID REFERENCES public.extraction_benefit_lines(id) ON DELETE SET NULL,
    item_kind VARCHAR(40) NOT NULL CHECK (item_kind IN ('catalog', 'custom')),
    state VARCHAR(40) NOT NULL DEFAULT 'unresolved' CHECK (state IN ('current', 'available_addon', 'removed', 'superseded', 'unresolved')),
    cost_status VARCHAR(40) NOT NULL DEFAULT 'unknown' CHECK (cost_status IN ('included', 'paid', 'foc', 'unknown')),
    label_override VARCHAR(255),
    typed_value_override JSONB,
    evidence_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    sort_order INTEGER NOT NULL DEFAULT 0,
    selected_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    superseded_by_id UUID REFERENCES public.draft_benefit_selections(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_draft_benefit_selection_key UNIQUE (draft_id, selection_key),
    CHECK ((item_kind = 'catalog' AND catalog_offering_id IS NOT NULL) OR item_kind = 'custom'),
    CHECK ((item_kind = 'custom' AND label_override IS NOT NULL) OR item_kind = 'catalog')
);

CREATE TABLE IF NOT EXISTS public.draft_source_line_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id UUID NOT NULL REFERENCES public.quotation_drafts(id) ON DELETE CASCADE,
    source_line_id UUID NOT NULL REFERENCES public.extraction_benefit_lines(id) ON DELETE CASCADE,
    disposition VARCHAR(40) NOT NULL DEFAULT 'unresolved' CHECK (disposition IN ('unresolved', 'mapped', 'custom', 'source_only', 'omitted')),
    selection_id UUID REFERENCES public.draft_benefit_selections(id) ON DELETE SET NULL,
    decided_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_draft_source_line_decision UNIQUE (draft_id, source_line_id),
    CHECK ((disposition IN ('mapped', 'custom') AND selection_id IS NOT NULL) OR disposition NOT IN ('mapped', 'custom'))
);

DO $$
DECLARE item TEXT;
BEGIN
    FOREACH item IN ARRAY ARRAY['extraction_benefit_lines','draft_benefit_selections','draft_source_line_decisions'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', item);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon, authenticated', item);
    END LOOP;
END $$;

COMMIT;
