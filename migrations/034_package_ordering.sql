-- 034_package_ordering.sql
-- Benefits & Package refactor (Task 3): package chain ordering.
-- benefit_packages gains an explicit sort_order so the comprehensive package
-- chain (level 1 base -> level 2 -> ...) keeps a deterministic presentation
-- order without relying on name/key sorting. Additive only.

BEGIN;

ALTER TABLE public.benefit_packages
    ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0;

COMMIT;
