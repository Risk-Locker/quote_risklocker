-- Migration: 053_render_snapshots_cascade.sql
-- Description: Update foreign key render_snapshots_draft_id_fkey to ON DELETE CASCADE so draft deletion cascades cleanly.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_name = 'render_snapshots_draft_id_fkey'
          AND table_name = 'render_snapshots'
    ) THEN
        ALTER TABLE public.render_snapshots
            DROP CONSTRAINT render_snapshots_draft_id_fkey;

        ALTER TABLE public.render_snapshots
            ADD CONSTRAINT render_snapshots_draft_id_fkey
            FOREIGN KEY (draft_id)
            REFERENCES public.quotation_drafts(id)
            ON DELETE CASCADE;
    END IF;
END $$;
