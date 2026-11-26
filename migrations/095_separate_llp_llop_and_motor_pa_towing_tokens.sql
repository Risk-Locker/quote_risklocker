-- 095_separate_llp_llop_and_motor_pa_towing_tokens.sql
-- 1. Separate LLP (Legal Liability to Passengers / Endorsement 100) and
--    LLOP (Legal Liability of Passengers / Endorsement 72) columns on tenure_comparison_entries.
-- 2. Add explicit towing limit match tokens (including 'unlimited' / 'unlimited towing' for Plan 4)
--    onto STMB Motor PA Plus bundle tiers so Unlimited Towing is matched deterministically.

BEGIN;

ALTER TABLE public.tenure_comparison_entries
    ADD COLUMN IF NOT EXISTS llp VARCHAR(50) NULL;

ALTER TABLE public.tenure_comparison_entries
    ADD COLUMN IF NOT EXISTS llop VARCHAR(50) NULL;

-- Safe backfill for manual entries without linked sessions
UPDATE public.tenure_comparison_entries
SET llp = llp_llop
WHERE session_id IS NULL
  AND llp IS NULL
  AND llop IS NULL
  AND llp_llop IS NOT NULL
  AND LOWER(TRIM(llp_llop)) NOT IN ('', '-', 'no', 'none', 'not included', 'excluded');

-- Add explicit towing match tokens to STMB Motor PA Plus tiers
UPDATE public.company_benefit_bundle_tiers t
SET match_tokens = CASE t.tier_key
        WHEN 'plan_4' THEN '["plan 4", "motor pa plan 4", "p4", "unlimited", "unlimited towing"]'::jsonb
        WHEN 'plan_3' THEN '["plan 3", "motor pa plan 3", "p3", "300 km", "300km"]'::jsonb
        WHEN 'plan_2' THEN '["plan 2", "motor pa plan 2", "p2", "200 km", "200km"]'::jsonb
        WHEN 'plan_1' THEN '["plan 1", "motor pa plan 1", "p1", "100 km", "100km"]'::jsonb
        ELSE t.match_tokens
    END,
    updated_at = NOW()
FROM public.company_benefit_bundles b
WHERE t.bundle_id = b.id
  AND b.bundle_key = 'stmb-motor-pa-plus'
  AND t.tier_key IN ('plan_1', 'plan_2', 'plan_3', 'plan_4');

COMMIT;
