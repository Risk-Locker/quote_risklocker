-- Retain trash until an explicit reference-aware purge.

BEGIN;

ALTER TABLE public.trash_records
    ALTER COLUMN purge_after DROP NOT NULL;

UPDATE public.trash_records SET purge_after = NULL;
UPDATE public.output_template_configs SET purge_after = NULL WHERE deleted_at IS NOT NULL;
UPDATE public.our_specials SET purge_after = NULL WHERE deleted_at IS NOT NULL;
UPDATE public.our_special_variants SET purge_after = NULL WHERE deleted_at IS NOT NULL;
UPDATE public.client_records SET purge_after = NULL WHERE deleted_at IS NOT NULL;
UPDATE public.template_assets SET purge_after = NULL WHERE deleted_at IS NOT NULL;
UPDATE public.uploaded_files SET purge_after = NULL WHERE deleted_at IS NOT NULL;
UPDATE public.quotation_drafts SET purge_after = NULL WHERE deleted_at IS NOT NULL;

COMMIT;
