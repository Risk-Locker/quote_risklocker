-- Migration 061: Drop template revision immutability triggers to allow deletion and cascade cleanup of templates
DROP TRIGGER IF EXISTS template_revision_immutable ON public.template_revisions;
DROP FUNCTION IF EXISTS public.prevent_published_template_mutation();

-- Ensure render_snapshots foreign key cascades when a template revision is deleted
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_name = 'render_snapshots_template_revision_id_fkey'
          AND table_name = 'render_snapshots'
    ) THEN
        ALTER TABLE public.render_snapshots
            DROP CONSTRAINT render_snapshots_template_revision_id_fkey;

        ALTER TABLE public.render_snapshots
            ADD CONSTRAINT render_snapshots_template_revision_id_fkey
            FOREIGN KEY (template_revision_id)
            REFERENCES public.template_revisions(id)
            ON DELETE CASCADE;
    END IF;
END $$;
