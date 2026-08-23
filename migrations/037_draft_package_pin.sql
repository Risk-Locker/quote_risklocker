-- 037_draft_package_pin.sql
-- Active package tier pin on quotation drafts.
-- Persists the active comprehensive package tier per draft so multi-tier
-- catalogs (such as AmAssurance 4-tier auto365) remember and seed the
-- chosen tier deterministically without mutating company-wide catalog config.

BEGIN;

ALTER TABLE public.quotation_drafts
    ADD COLUMN IF NOT EXISTS package_id UUID
        REFERENCES public.benefit_packages(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS quotation_drafts_package_id_idx
    ON public.quotation_drafts(package_id);

COMMIT;
