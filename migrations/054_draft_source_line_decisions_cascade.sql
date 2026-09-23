-- Migration: 054_draft_source_line_decisions_cascade.sql
-- Description: Update foreign key draft_source_line_decisions_selection_id_fkey to ON DELETE CASCADE to prevent check constraint violations on delete.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_name = 'draft_source_line_decisions_selection_id_fkey'
          AND table_name = 'draft_source_line_decisions'
    ) THEN
        ALTER TABLE public.draft_source_line_decisions
            DROP CONSTRAINT draft_source_line_decisions_selection_id_fkey;

        ALTER TABLE public.draft_source_line_decisions
            ADD CONSTRAINT draft_source_line_decisions_selection_id_fkey
            FOREIGN KEY (selection_id)
            REFERENCES public.draft_benefit_selections(id)
            ON DELETE CASCADE;
    END IF;
END $$;
