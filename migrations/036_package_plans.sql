-- 036_package_plans.sql
-- Benefit pack plans wiring: group selections to a published package plan
-- and carry an optional staff-entered price on custom add-on selections.
-- Additive only. Plan tables (benefit_package_plans, benefit_package_plan_items)
-- already exist from migration 024; no data backfill.

BEGIN;

ALTER TABLE public.draft_benefit_selections
    ADD COLUMN IF NOT EXISTS package_plan_id UUID
        REFERENCES public.benefit_package_plans(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS price JSONB;

CREATE INDEX IF NOT EXISTS draft_benefit_selections_plan_idx
    ON public.draft_benefit_selections(package_plan_id);

COMMIT;
