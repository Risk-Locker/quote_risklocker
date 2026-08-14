-- Paginated Records workspace, archive state, and URL-compatible saved views.

BEGIN;

ALTER TABLE public.client_records
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS client_records_archived_at_idx ON public.client_records(archived_at);

CREATE TABLE IF NOT EXISTS public.record_saved_views (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_shared BOOLEAN NOT NULL DEFAULT TRUE,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_record_saved_view_owner_name UNIQUE(owner_id, name)
);
CREATE INDEX IF NOT EXISTS record_saved_views_owner_idx ON public.record_saved_views(owner_id);

ALTER TABLE public.record_saved_views ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE public.record_saved_views FROM anon, authenticated;

COMMIT;
