-- v7 additive fixed page profiles, immutable template revisions, jobs, and render snapshots.

BEGIN;

ALTER TABLE public.output_template_configs ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS public.template_page_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_key VARCHAR(160) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    width NUMERIC(12,4) NOT NULL CHECK (width > 0),
    height NUMERIC(12,4) NOT NULL CHECK (height > 0),
    unit VARCHAR(20) NOT NULL DEFAULT 'px' CHECK (unit IN ('px', 'mm', 'in')),
    safe_margins JSONB NOT NULL DEFAULT '{}'::jsonb,
    bleed JSONB NOT NULL DEFAULT '{}'::jsonb,
    background_behavior VARCHAR(40) NOT NULL DEFAULT 'clip',
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.template_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES public.output_template_configs(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    state VARCHAR(40) NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'published', 'retired', 'compatibility')),
    page_profile_id UUID NOT NULL REFERENCES public.template_page_profiles(id) ON DELETE RESTRICT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    config_hash CHAR(64) NOT NULL,
    published_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_template_revision UNIQUE (template_id, revision_number),
    CHECK ((revision_number >= 1) OR (state = 'compatibility' AND revision_number = 0)),
    CHECK ((state = 'published' AND published_at IS NOT NULL) OR state <> 'published')
);

ALTER TABLE public.quotation_drafts
    ADD COLUMN IF NOT EXISTS template_revision_id UUID REFERENCES public.template_revisions(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS layout_override_template_revision_id UUID REFERENCES public.template_revisions(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS public.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    session_id UUID REFERENCES public.sessions(id) ON DELETE CASCADE,
    uploaded_file_id UUID REFERENCES public.uploaded_files(id) ON DELETE CASCADE,
    job_type VARCHAR(60) NOT NULL,
    idempotency_key VARCHAR(160) NOT NULL,
    state VARCHAR(40) NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'processing', 'completed', 'failed', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 100,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    safe_error JSONB NOT NULL DEFAULT '{}'::jsonb,
    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_owner VARCHAR(160),
    lease_expires_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_job_type_idempotency UNIQUE (job_type, idempotency_key)
);
CREATE INDEX IF NOT EXISTS jobs_claim_idx ON public.jobs(state, available_at, priority, created_at);
CREATE INDEX IF NOT EXISTS jobs_owner_idx ON public.jobs(owner_id);
CREATE INDEX IF NOT EXISTS jobs_session_idx ON public.jobs(session_id);
CREATE INDEX IF NOT EXISTS jobs_lease_idx ON public.jobs(lease_expires_at) WHERE lease_expires_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.render_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id UUID NOT NULL REFERENCES public.quotation_drafts(id) ON DELETE RESTRICT,
    draft_revision INTEGER NOT NULL CHECK (draft_revision >= 1),
    catalog_revision_id UUID REFERENCES public.benefit_catalog_revisions(id) ON DELETE RESTRICT,
    template_revision_id UUID NOT NULL REFERENCES public.template_revisions(id) ON DELETE RESTRICT,
    context_hash CHAR(64) NOT NULL UNIQUE,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    asset_hashes JSONB NOT NULL DEFAULT '{}'::jsonb,
    renderer_version VARCHAR(80) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.generated_pdf_versions
    ADD COLUMN IF NOT EXISTS draft_revision INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS catalog_revision_id UUID REFERENCES public.benefit_catalog_revisions(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS template_revision_id UUID REFERENCES public.template_revisions(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(160),
    ADD COLUMN IF NOT EXISTS render_context_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS render_context_hash CHAR(64),
    ADD COLUMN IF NOT EXISTS renderer_version VARCHAR(80) NOT NULL DEFAULT 'legacy';
CREATE UNIQUE INDEX IF NOT EXISTS generated_pdf_draft_idempotency_uq
    ON public.generated_pdf_versions(draft_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS generated_pdf_render_hash_idx ON public.generated_pdf_versions(render_context_hash);

CREATE OR REPLACE FUNCTION public.prevent_published_template_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state = 'published' THEN
        RAISE EXCEPTION 'Published template revisions are immutable';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;
DROP TRIGGER IF EXISTS template_revision_immutable ON public.template_revisions;
CREATE TRIGGER template_revision_immutable
BEFORE UPDATE OR DELETE ON public.template_revisions
FOR EACH ROW EXECUTE FUNCTION public.prevent_published_template_mutation();

DO $$
DECLARE item TEXT;
BEGIN
    FOREACH item IN ARRAY ARRAY['template_page_profiles','template_revisions','jobs','render_snapshots'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', item);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon, authenticated', item);
    END LOOP;
END $$;

COMMIT;
