-- 084_conditional_box2_promotion_and_7_insurers.sql
-- Promote conditional towing/benefit upgrades from Box 1 (Free Added Coverage)
-- to ticked Box 2 (Add-On Upgrades ++) via action_type = 'promote_to_addon'
-- across all 7 insurers with 100% database-driven configuration.

BEGIN;

-- 1. Ensure company_benefit_conditions supports 'promote_to_addon', 'replace_description', 'hide_target'
ALTER TABLE company_benefit_conditions
    DROP CONSTRAINT IF EXISTS company_benefit_conditions_action_type_check;

ALTER TABLE company_benefit_conditions
    ADD COLUMN IF NOT EXISTS replacement_value VARCHAR(120);

-- 2. Convert active towing upgrade conditions across QBE, STMB, Etiqa, Lonpac, Tune Protect to 'promote_to_addon'
--    so the base Box 1 Towing card hides when the trigger add-on is purchased and appears ticked in Box 2.

-- 2a. QBE: Driver & Passenger Protector (N4) -> Unlimited Towing (Unlimited - Plan 1)
UPDATE company_benefit_conditions cond
SET action_type = 'promote_to_addon',
    replacement_title = 'Unlimited Towing',
    replacement_value = 'Unlimited - Plan 1',
    replacement_description = '24-Hour Unlimited Towing & Auto Assistance (Plan 1 via Driver & Passenger Protector N4).',
    updated_at = NOW()
FROM insurance_companies ic
WHERE cond.company_id = ic.id
  AND ic.slug = 'qbe'
  AND cond.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND cond.is_active = TRUE;

-- 2b. STMB / Takaful Malaysia: Motor PA Plus Plans 1-4 -> Towing (100 km / 200 km / 300 km / Unlimited Towing with empty coverage)
UPDATE company_benefit_conditions cond
SET action_type = 'promote_to_addon',
    replacement_title = CASE
        WHEN cond.trigger_plan_filter ILIKE '%4%' THEN 'Unlimited Towing'
        ELSE 'Towing'
    END,
    replacement_value = CASE
        WHEN cond.trigger_plan_filter ILIKE '%1%' THEN '100 km'
        WHEN cond.trigger_plan_filter ILIKE '%2%' THEN '200 km'
        WHEN cond.trigger_plan_filter ILIKE '%3%' THEN '300 km'
        WHEN cond.trigger_plan_filter ILIKE '%4%' THEN ''
        ELSE cond.replacement_value
    END,
    replacement_description = CASE
        WHEN cond.trigger_plan_filter ILIKE '%1%' THEN '24/7 emergency towing assistance up to 100 km (Motor PA Plan 1).'
        WHEN cond.trigger_plan_filter ILIKE '%2%' THEN '24/7 emergency towing assistance up to 200 km (Motor PA Plan 2).'
        WHEN cond.trigger_plan_filter ILIKE '%3%' THEN '24/7 emergency towing assistance up to 300 km (Motor PA Plan 3).'
        WHEN cond.trigger_plan_filter ILIKE '%4%' THEN '24/7 emergency unlimited towing assistance across Malaysia (Motor PA Plan 4).'
        ELSE cond.replacement_description
    END,
    updated_at = NOW()
FROM insurance_companies ic
WHERE cond.company_id = ic.id
  AND ic.slug = 'takaful-malaysia'
  AND cond.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND cond.trigger_plan_filter IS NOT NULL
  AND cond.is_active = TRUE;

-- Ensure STMB Motor PA Plus optional offering shows default '1-4' range when unpurchased
UPDATE catalog_offerings co
SET display_value = '1-4'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic, benefit_concepts con
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND co.concept_id = con.id
  AND ic.slug = 'takaful-malaysia'
  AND (con.concept_key ILIKE '%motor-pa%' OR con.concept_key ILIKE '%motor_pa%' OR con.label ILIKE '%motor pa plus%')
  AND co.offering_kind IN ('optional', 'upgrade')
  AND NULLIF(BTRIM(COALESCE(co.display_value, '')), '') IS NULL;

-- 2c. Etiqa: OTO 360 -> Unlimited Towing (Unlimited - Driver Plan 1)
UPDATE company_benefit_conditions cond
SET action_type = 'promote_to_addon',
    replacement_title = 'Unlimited Towing',
    replacement_value = 'Unlimited - Driver Plan 1',
    replacement_description = '24/7 emergency unlimited towing assistance nationwide (Driver Plan 1 via OTO 360).',
    updated_at = NOW()
FROM insurance_companies ic
WHERE cond.company_id = ic.id
  AND ic.slug = 'etiqa'
  AND cond.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND cond.is_active = TRUE;

-- 2d. Lonpac: E-Assist Smart Driver (Plan 1 -> RM 600, Plan 2 / EV Plan -> Unlimited)
UPDATE company_benefit_conditions cond
SET action_type = 'promote_to_addon',
    updated_at = NOW()
FROM insurance_companies ic
WHERE cond.company_id = ic.id
  AND ic.slug = 'lonpac'
  AND cond.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND cond.is_active = TRUE;

-- 2e. Tune Protect: Motor Easy Bundle / AutoBuddy / MotorShield -> Unlimited Towing
UPDATE company_benefit_conditions cond
SET action_type = 'promote_to_addon',
    replacement_title = 'Unlimited Towing',
    replacement_value = 'Unlimited',
    updated_at = NOW()
FROM insurance_companies ic
WHERE cond.company_id = ic.id
  AND ic.slug = 'tune-protect'
  AND cond.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND cond.is_active = TRUE;

-- 2f. AmAssurance: align auto365 Lite (RM 200), auto365 Plus (100 km), auto365 Premier (365 km)
UPDATE catalog_offerings co
SET display_value = 'RM 200',
    description_override = '24/7 emergency accident and breakdown towing assistance up to RM 200.'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND ic.slug = 'amassurance'
  AND bc.name ILIKE '%auto365%Lite%'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND co.offering_kind = 'base';

UPDATE catalog_offerings co
SET display_value = '100 km',
    description_override = '24/7 emergency accident and breakdown towing assistance up to 100 km.'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND ic.slug = 'amassurance'
  AND bc.name ILIKE '%auto365%Plus%'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND co.offering_kind = 'base';

UPDATE catalog_offerings co
SET display_value = '365 km',
    description_override = '24/7 emergency accident and breakdown towing assistance up to 365 km.'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND ic.slug = 'amassurance'
  AND bc.name ILIKE '%auto365%Premier%'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND co.offering_kind = 'base';

-- Seed Breakdown Towing Assistance -> Extended Towing Assistance (150 km) condition for AmAssurance if concept exists
INSERT INTO company_benefit_conditions (
    id, company_id, profile_id, name, trigger_concept_id, trigger_plan_filter,
    target_concept_id, action_type, replacement_title, replacement_value, replacement_description,
    is_active, created_at, updated_at
)
SELECT
    'aa365001-0001-4000-8000-000000000001'::uuid,
    ic.id,
    bp.id,
    'Breakdown Towing Assistance -> Extended Towing (150 km)',
    trig.id,
    NULL,
    '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid,
    'promote_to_addon',
    'Extended Towing Assistance',
    '150 km',
    '24/7 breakdown towing assistance up to 150 km.',
    TRUE,
    NOW(),
    NOW()
FROM insurance_companies ic
JOIN benefit_profiles bp ON bp.is_active = TRUE
JOIN benefit_concepts trig ON (trig.concept_key ILIKE '%breakdown%towing%' OR trig.label ILIKE '%Breakdown Towing Assistance%')
WHERE ic.slug = 'amassurance'
  AND NOT EXISTS (
      SELECT 1 FROM company_benefit_conditions existing
      WHERE existing.company_id = ic.id
        AND existing.profile_id = bp.id
        AND existing.trigger_concept_id = trig.id
        AND existing.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid
  )
LIMIT 1;

COMMIT;
