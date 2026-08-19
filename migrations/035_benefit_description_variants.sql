-- 035_benefit_description_variants.sql
-- Benefits & Package refactor (replan step 1): Global Benefits carry up to two
-- customer-facing description variants, each with an implied value shape.
-- Example (Towing): "Coverage up to {value} km" (distance) and
-- "Coverage up to RM {value}" (money); workmanship may use "{value} years"
-- (duration). The value TYPE is implied by the template, never chosen first.
-- Additive only; existing columns stay for legacy reads.

BEGIN;

ALTER TABLE public.benefit_concepts
    ADD COLUMN IF NOT EXISTS description_variants JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMIT;
