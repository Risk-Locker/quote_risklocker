-- 080_v30_5_towing_catalogs_conditions_and_vehicle_grounding.sql
-- v30.5 Authoritative 7-Insurer Towing Matrix, Benefit Conditions, Clean Catalogs & Level-2 Grounding Schema

BEGIN;

-- 1. Schema additions for Level-2 Online Grounding cache & Condition replacement_value
ALTER TABLE vehicle_models
    ADD COLUMN IF NOT EXISTS grounding_meta JSONB;

ALTER TABLE company_benefit_conditions
    ADD COLUMN IF NOT EXISTS replacement_value VARCHAR(120);

-- 2. Publish QBE Private Car Protector (ICE Comprehensive) so ICE quotes do not fall back to EV catalogs
UPDATE benefit_catalogs
SET status = 'published', updated_at = NOW()
WHERE id = 'cc95f8e7-94a7-428a-a283-14e9f8b51439'
  AND status = 'draft';

UPDATE benefit_catalog_revisions
SET state = 'published',
    published_at = COALESCE(published_at, NOW())
WHERE id = '819026f3-2640-47d4-b0ee-54dd6dc2355f'
  AND catalog_id = 'cc95f8e7-94a7-428a-a283-14e9f8b51439'
  AND (state <> 'published' OR published_at IS NULL);

-- 3. Deactivate complimentary base Emergency Towing from non-Comprehensive (Third Party / TPFT) catalogs
-- (Use soft status='inactive' rather than DELETE to preserve historical draft_benefit_selections referential integrity)
UPDATE catalog_offerings co
SET status = 'inactive'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, coverage_types ct
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.coverage_type_id = ct.id
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND co.offering_kind = 'base'
  AND co.role = 'included'
  AND ct.coverage_key IN ('third_party', 'third_party_fire_theft')
  AND co.status <> 'inactive';

-- 4. Seed authoritative Standard Box-1 base towing limits across all 7 insurers' Comprehensive catalogs
-- 4a. QBE: Standard RM 500
UPDATE catalog_offerings co
SET display_value = 'RM 500',
    description_override = '24/7 accidental towing assistance to nearest approved panel workshop up to RM 500.'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic, coverage_types ct
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND bc.coverage_type_id = ct.id
  AND ic.slug = 'qbe'
  AND ct.coverage_key = 'comprehensive'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND co.offering_kind = 'base';

-- 4b. STMB / Takaful Malaysia: Standard 50 km
UPDATE catalog_offerings co
SET display_value = '50 km',
    description_override = '24/7 breakdown and accident towing assistance up to 50 km round trip.'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic, coverage_types ct
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND bc.coverage_type_id = ct.id
  AND ic.slug = 'takaful-malaysia'
  AND ct.coverage_key = 'comprehensive'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND co.offering_kind = 'base';

-- 4c. Etiqa: Standard 200 km (also cleans any test override pollution)
UPDATE catalog_offerings co
SET display_value = '200 km',
    description_override = '24/7 emergency accident & breakdown towing assistance up to 200 km.'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic, coverage_types ct
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND bc.coverage_type_id = ct.id
  AND ic.slug = 'etiqa'
  AND ct.coverage_key = 'comprehensive'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND co.offering_kind = 'base';

-- 4d. Lonpac: Standard RM 400
UPDATE catalog_offerings co
SET display_value = 'RM 400',
    description_override = '24/7 emergency accident towing cost reimbursement up to RM 400 to nearest approved repairer.'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic, coverage_types ct
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND bc.coverage_type_id = ct.id
  AND ic.slug = 'lonpac'
  AND ct.coverage_key = 'comprehensive'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND co.offering_kind = 'base';

-- 4e. Berjaya Sompo: Default Unlimited (no upgrade required)
UPDATE catalog_offerings co
SET display_value = 'Unlimited',
    description_override = '24/7 unlimited distance towing assistance to panel workshops and minor roadside repairs.'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic, coverage_types ct
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND bc.coverage_type_id = ct.id
  AND ic.slug = 'berjaya-sompo'
  AND ct.coverage_key = 'comprehensive'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND co.offering_kind = 'base';

-- 4f. Tune Protect: Standard RM 300 (non-bundled comprehensive) & Unlimited on Motor Easy + Motor Bundle
UPDATE catalog_offerings co
SET display_value = 'RM 300',
    description_override = '24/7 emergency accident towing assistance to nearest workshop up to RM 300.'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic, coverage_types ct
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND bc.coverage_type_id = ct.id
  AND ic.slug = 'tune-protect'
  AND ct.coverage_key = 'comprehensive'
  AND bc.id <> '4d9e7c2c-6b5b-40a5-b4d4-211f3305d955'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND co.offering_kind = 'base';

INSERT INTO catalog_offerings (
    id, catalog_revision_id, concept_id, offering_key, offering_kind, role,
    display_value, description_override, status, sort_order,
    source_citation, source_aliases, presentation_facet_ids, created_at, updated_at
)
SELECT
    '9a7d6c5b-4e3f-4a2b-8c1d-4d9e7c2c0001'::uuid,
    '33b72a49-1ee6-4de4-b043-33cf9f3a52b7'::uuid,
    '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid,
    'tune-bundle-towing-unlimited',
    'base',
    'included',
    'Unlimited',
    '24/7 unlimited emergency towing assistance bundled under Motor Easy + Motor Bundle.',
    'active',
    10,
    '{}'::jsonb,
    '[]'::jsonb,
    '[]'::jsonb,
    NOW(),
    NOW()
WHERE EXISTS (
    SELECT 1 FROM benefit_catalog_revisions WHERE id = '33b72a49-1ee6-4de4-b043-33cf9f3a52b7'::uuid
)
AND NOT EXISTS (
    SELECT 1 FROM catalog_offerings
    WHERE catalog_revision_id = '33b72a49-1ee6-4de4-b043-33cf9f3a52b7'::uuid
      AND concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid
);

-- 4g. AmAssurance: auto365 Lite = 50 km, auto365 Plus = 100 km, auto365 Premier = 365 km
UPDATE catalog_offerings co
SET display_value = '50 km',
    description_override = '24/7 emergency accident and breakdown towing assistance up to 50 km.'
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

-- 5. Align CompanyBenefitConfig (Tier 3 baseline_description for towing) across active/standard profiles
UPDATE company_benefit_configs cbc
SET baseline_description = CASE ic.slug
    WHEN 'qbe' THEN '24/7 accidental towing assistance to nearest approved panel workshop up to RM 500.'
    WHEN 'takaful-malaysia' THEN '24/7 breakdown and accident towing assistance up to 50 km round trip.'
    WHEN 'etiqa' THEN '24/7 emergency accident & breakdown towing assistance up to 200 km.'
    WHEN 'lonpac' THEN '24/7 emergency accident towing cost reimbursement up to RM 400 to nearest approved repairer.'
    WHEN 'berjaya-sompo' THEN '24/7 unlimited distance towing assistance to panel workshops and roadside repairs.'
    WHEN 'tune-protect' THEN '24/7 emergency accident towing assistance to nearest workshop up to RM 300.'
    WHEN 'amassurance' THEN NULL
    ELSE cbc.baseline_description
END,
    updated_at = NOW()
FROM insurance_companies ic
WHERE cbc.company_id = ic.id
  AND cbc.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND ic.slug IN ('qbe','takaful-malaysia','etiqa','lonpac','berjaya-sompo','tune-protect','amassurance');

-- 6. Sync CompanyBenefitConditions (Tier 2 conditional upgrades + replacement_value) on active Master profile
-- 6a. QBE DPP -> Unlimited - Plan 1
UPDATE company_benefit_conditions cond
SET replacement_title = 'Unlimited Towing',
    replacement_value = 'Unlimited - Plan 1',
    replacement_description = '24-Hour Unlimited Towing & Auto Assistance (Plan 1 via Driver & Passenger Protector N4).',
    updated_at = NOW()
FROM insurance_companies ic
WHERE cond.company_id = ic.id
  AND ic.slug = 'qbe'
  AND cond.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1';

-- 6b. STMB / Takaful Malaysia: Motor PA Plans 1/2/3/4 (deactivate ambiguous NULL-filter wildcard so Plan 1 never jumps to Unlimited)
UPDATE company_benefit_conditions cond
SET is_active = FALSE,
    updated_at = NOW()
WHERE cond.id = 'e3aab2f9-f90d-4260-846f-d21222ed745e';

UPDATE company_benefit_conditions cond
SET replacement_title = CASE
        WHEN cond.trigger_plan_filter ILIKE '%4%' THEN 'Unlimited Towing'
        ELSE 'Extended Towing Assistance'
    END,
    replacement_value = CASE
        WHEN cond.trigger_plan_filter ILIKE '%1%' THEN '100 km'
        WHEN cond.trigger_plan_filter ILIKE '%2%' THEN '200 km'
        WHEN cond.trigger_plan_filter ILIKE '%3%' THEN '300 km'
        WHEN cond.trigger_plan_filter ILIKE '%4%' THEN 'Unlimited'
        ELSE '100 km'
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
  AND cond.trigger_plan_filter IS NOT NULL;

-- 6c. Etiqa: OTO 360 -> Unlimited - Driver Plan 1
UPDATE company_benefit_conditions cond
SET replacement_title = 'Unlimited Towing',
    replacement_value = 'Unlimited - Driver Plan 1',
    replacement_description = '24/7 emergency unlimited towing assistance nationwide (Driver Plan 1 via OTO 360).',
    updated_at = NOW()
FROM insurance_companies ic
WHERE cond.company_id = ic.id
  AND ic.slug = 'etiqa'
  AND cond.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1';

-- 6d. Lonpac: E-Assist Smart Driver Plan 1 / Plan A -> RM 600; Plan 2 / EV Plan / B / C / D -> Unlimited
UPDATE company_benefit_conditions cond
SET is_active = FALSE,
    updated_at = NOW()
WHERE cond.id = '5c70a6ec-fccc-4669-87ca-fe9045f65cc2';

UPDATE company_benefit_conditions cond
SET replacement_title = 'Extended Towing Assistance',
    replacement_value = 'RM 600',
    replacement_description = '24/7 enhanced emergency towing assistance up to RM 600 (E-Assist Smart Driver Plan 1).',
    updated_at = NOW()
WHERE cond.id = 'c8f85e3a-93b0-4cac-859d-1d7f0973cbbe';

UPDATE company_benefit_conditions cond
SET replacement_title = 'Unlimited Towing',
    replacement_value = 'Unlimited',
    replacement_description = '24/7 emergency enhanced unlimited towing assistance (E-Assist Smart Driver Plan 2 / EV Plan).',
    updated_at = NOW()
FROM insurance_companies ic
WHERE cond.company_id = ic.id
  AND ic.slug = 'lonpac'
  AND cond.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND cond.id <> 'c8f85e3a-93b0-4cac-859d-1d7f0973cbbe'
  AND cond.is_active = TRUE;

INSERT INTO company_benefit_conditions (
    id, company_id, profile_id, name, trigger_concept_id, trigger_plan_filter,
    target_concept_id, action_type, replacement_title, replacement_value, replacement_description,
    is_active, created_at, updated_at
)
SELECT
    v.cond_id::uuid,
    '4f2627c5-e412-44ef-9e17-e37f3472ac55'::uuid,
    '77b92af7-4897-48f5-8a42-99db0e2934d2'::uuid,
    v.cond_name,
    '17d2dbf1-dcc1-41ad-88a4-b08e719bacfb'::uuid,
    v.plan_filter,
    '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid,
    'replace_description',
    v.rep_title,
    v.rep_val,
    v.rep_desc,
    TRUE,
    NOW(),
    NOW()
FROM (
    VALUES
        ('5c70a6ec-0001-4669-87ca-fe9045f60001', 'E-Assist Smart Driver (Plan 1) -> RM 600 Towing', 'Plan 1', 'Extended Towing Assistance', 'RM 600', '24/7 enhanced emergency towing assistance up to RM 600 (E-Assist Smart Driver Plan 1).'),
        ('5c70a6ec-0002-4669-87ca-fe9045f60002', 'E-Assist Smart Driver (Plan 2) -> Unlimited Towing', 'Plan 2', 'Unlimited Towing', 'Unlimited', '24/7 emergency enhanced unlimited towing assistance (E-Assist Smart Driver Plan 2).'),
        ('5c70a6ec-0003-4669-87ca-fe9045f60003', 'E-Assist Smart Driver (EV Plan) -> Unlimited Towing', 'EV Plan', 'Unlimited Towing', 'Unlimited', '24/7 emergency enhanced unlimited towing assistance (E-Assist Smart Driver EV Plan).')
) AS v(cond_id, cond_name, plan_filter, rep_title, rep_val, rep_desc)
WHERE EXISTS (SELECT 1 FROM insurance_companies WHERE id = '4f2627c5-e412-44ef-9e17-e37f3472ac55'::uuid)
  AND EXISTS (SELECT 1 FROM benefit_profiles WHERE id = '77b92af7-4897-48f5-8a42-99db0e2934d2'::uuid)
  AND NOT EXISTS (
      SELECT 1 FROM company_benefit_conditions
      WHERE company_id = '4f2627c5-e412-44ef-9e17-e37f3472ac55'::uuid
        AND profile_id = '77b92af7-4897-48f5-8a42-99db0e2934d2'::uuid
        AND trigger_plan_filter = v.plan_filter
        AND target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid
  );

-- 6e. Berjaya Sompo: ensure replacement_value = Unlimited
UPDATE company_benefit_conditions cond
SET replacement_title = 'Unlimited Towing',
    replacement_value = 'Unlimited',
    updated_at = NOW()
FROM insurance_companies ic
WHERE cond.company_id = ic.id
  AND ic.slug = 'berjaya-sompo'
  AND cond.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1';

-- 6f. Tune Protect: AutoBuddy + Motor Easy + MotorShield -> Unlimited
UPDATE company_benefit_conditions cond
SET replacement_title = 'Unlimited Towing',
    replacement_value = 'Unlimited',
    replacement_description = '24-Hour emergency unlimited towing assistance.',
    updated_at = NOW()
FROM insurance_companies ic
WHERE cond.company_id = ic.id
  AND ic.slug = 'tune-protect'
  AND cond.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1';

INSERT INTO company_benefit_conditions (
    id, company_id, profile_id, name, trigger_concept_id, trigger_plan_filter,
    target_concept_id, action_type, replacement_title, replacement_value, replacement_description,
    is_active, created_at, updated_at
)
SELECT
    v.cond_id::uuid,
    '2bb76a34-baa3-4b6b-8c83-bc7bcc096bcf'::uuid,
    '77b92af7-4897-48f5-8a42-99db0e2934d2'::uuid,
    v.cond_name,
    v.trig_id::uuid,
    NULL,
    '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid,
    'replace_description',
    'Unlimited Towing',
    'Unlimited',
    v.rep_desc,
    TRUE,
    NOW(),
    NOW()
FROM (
    VALUES
        ('2b777a78-0001-476e-9ccf-e3a039eb0001', 'Motor Easy Bundle -> Unlimited Towing', 'eaa5602a-6bb9-4405-b049-6cb245ee1d66', '24-Hour emergency unlimited towing assistance via Motor Easy Bundle.'),
        ('2b777a78-0002-476e-9ccf-e3a039eb0002', 'MotorShield -> Unlimited Towing', 'a58634b4-30da-477c-b61d-bfde2ebcc3f1', '24-Hour emergency unlimited towing assistance via MotorShield.')
) AS v(cond_id, cond_name, trig_id, rep_desc)
WHERE EXISTS (SELECT 1 FROM insurance_companies WHERE id = '2bb76a34-baa3-4b6b-8c83-bc7bcc096bcf'::uuid)
  AND EXISTS (SELECT 1 FROM benefit_profiles WHERE id = '77b92af7-4897-48f5-8a42-99db0e2934d2'::uuid)
  AND NOT EXISTS (
      SELECT 1 FROM company_benefit_conditions
      WHERE company_id = '2bb76a34-baa3-4b6b-8c83-bc7bcc096bcf'::uuid
        AND profile_id = '77b92af7-4897-48f5-8a42-99db0e2934d2'::uuid
        AND trigger_concept_id = v.trig_id::uuid
        AND target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid
  );

-- 6g. AmAssurance: deactivate conflicting legacy private-car-365 towing overrides so auto365 Plus (100 km) & Premier (365 km) render accurately with no upgrade required
UPDATE company_benefit_conditions cond
SET is_active = FALSE,
    updated_at = NOW()
FROM insurance_companies ic
WHERE cond.company_id = ic.id
  AND ic.slug = 'amassurance'
  AND cond.target_concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'
  AND cond.trigger_concept_id = '52229366-efe0-4680-b7fe-e285bd2de303';

COMMIT;
