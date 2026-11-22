-- 088_seed_7_insurer_towing_bundles.sql
-- Authoritative 7-Insurer Bundled Benefit ("Mystery Box") Seeding & Alignment:
--   1. QBE: Driver & Passenger Protector (N4) -> Unlimited Towing Assistance (Unlimited - Plan 1), Base RM 500
--   2. STMB / Takaful Malaysia: Motor PA Plus Plans 1-4 -> Towing Assistance (100/200/300 km) / Unlimited Towing Assistance, Base 50 km
--   3. Etiqa: OTO 360 -> Unlimited Towing Assistance (Unlimited - Driver Plan 1), Base 200 km
--   4. Lonpac: E-Assist Smart Driver Plan 1 (RM 600) / Plan 2 & EV Plan (Unlimited), Base RM 400
--   5. Berjaya Sompo: Standard Unlimited (no upgrade required)
--   6. Tune Protect: Motor Easy Bundle / AutoBuddy / MotorShield -> Unlimited Towing Assistance, Base RM 300
--   7. AmAssurance: auto365 Lite = RM 200 (+ Breakdown Towing Assistance -> Towing Assistance (150 km)),
--                   auto365 Plus = 100 km, auto365 Premier = 365 km;
--                   Private Car 365 Plan 1 -> Towing Assistance (600 km), Plan 2/3/4 -> Unlimited Towing Assistance
--
-- Box 2 unlocked towing cards use empty display_value ('') with the limit in display_title
-- and no separate price; Unlimited Towing cards carry icon_hint = 'unlimited_towing'.

BEGIN;

-- 1. Align AmAssurance Private Car 365 catalog offerings as optional add-on (never Box 1 base)
UPDATE catalog_offerings co
SET offering_kind = 'optional',
    role = 'addon_option',
    updated_at = NOW()
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND ic.slug = 'amassurance'
  AND co.concept_id = '52229366-efe0-4680-b7fe-e285bd2de303'::uuid
  AND (co.offering_kind <> 'optional' OR COALESCE(co.role, '') <> 'addon_option');

-- 2. Align base Box 1 Towing offerings (auto365 Lite = RM 200, Plus = 100 km, Premier = 365 km, Sompo = Unlimited)
UPDATE catalog_offerings co
SET display_value = 'RM 200',
    description_override = '24/7 emergency accident and breakdown towing assistance up to RM 200.',
    updated_at = NOW()
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND ic.slug = 'amassurance'
  AND bc.name ILIKE '%auto365%Lite%'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid
  AND co.offering_kind = 'base';

UPDATE catalog_offerings co
SET display_value = '100 km',
    description_override = '24/7 emergency accident and breakdown towing assistance up to 100 km.',
    updated_at = NOW()
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND ic.slug = 'amassurance'
  AND bc.name ILIKE '%auto365%Plus%'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid
  AND co.offering_kind = 'base';

UPDATE catalog_offerings co
SET display_value = '365 km',
    description_override = '24/7 emergency accident and breakdown towing assistance up to 365 km.',
    updated_at = NOW()
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND ic.slug = 'amassurance'
  AND bc.name ILIKE '%auto365%Premier%'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid
  AND co.offering_kind = 'base';

UPDATE catalog_offerings co
SET display_value = 'Unlimited',
    description_override = '24/7 unlimited distance towing assistance to panel workshops and minor roadside repairs.',
    updated_at = NOW()
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic, coverage_types ct
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND bc.coverage_type_id = ct.id
  AND ic.slug = 'berjaya-sompo'
  AND ct.coverage_key = 'comprehensive'
  AND co.concept_id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid
  AND co.offering_kind = 'base';

-- 3. Update AmAssurance DB policy_rules JSONB with authoritative auto365 Lite RM 200 & Private Car 365 fallback rules
UPDATE insurance_companies
SET policy_rules = jsonb_set(
        COALESCE(policy_rules, '{}'::jsonb),
        '{towing}',
        '{"metric": "km", "base_limit": "100 km", "lite_limit": "RM 200", "premier_limit": "365 km", "sdpa_triggers": ["private car 365", "pc 365", "pc365", "365 plan"], "sdpa_plan1_limit": "600 km", "unlimited_triggers": ["amdrive plus"]}'::jsonb,
        TRUE
    ),
    updated_at = NOW()
WHERE slug = 'amassurance';

-- 4. Seed authoritative Bundled Benefits ("Mystery Box") across QBE, STMB, Etiqa, Lonpac, Tune Protect, AmAssurance
DO $$
DECLARE
    towing_cid UUID;
    qbe_id UUID;
    qbe_dpp_cid UUID;
    stmb_id UUID;
    stmb_pa_cid UUID;
    etiqa_id UUID;
    etiqa_oto_cid UUID;
    lonpac_id UUID;
    lonpac_sd_cid UUID;
    tune_id UUID;
    tune_primary_cid UUID;
    tune_autobuddy_cid UUID;
    tune_motorshield_cid UUID;
    tune_trigs JSONB;
    amgen_id UUID;
    amgen_pc365_cid UUID;
    amgen_bta_cid UUID;
    prof_rec RECORD;
    b_id UUID;
    t1_id UUID;
    t2_id UUID;
    t3_id UUID;
    t4_id UUID;
BEGIN
    SELECT id INTO towing_cid
    FROM benefit_concepts
    WHERE id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid
       OR concept_key IN ('towing', 'towing-assistance', 'emergency-towing')
    ORDER BY (id = '47e25689-0ef1-4db5-ae8e-251e8cd94af1'::uuid) DESC
    LIMIT 1;

    IF towing_cid IS NULL THEN
        RAISE NOTICE 'Skipping 088 bundle seed: towing concept not found';
        RETURN;
    END IF;

    SELECT id INTO qbe_id FROM insurance_companies WHERE slug = 'qbe' LIMIT 1;
    SELECT id INTO stmb_id FROM insurance_companies WHERE slug = 'takaful-malaysia' LIMIT 1;
    SELECT id INTO etiqa_id FROM insurance_companies WHERE slug = 'etiqa' LIMIT 1;
    SELECT id INTO lonpac_id FROM insurance_companies WHERE slug = 'lonpac' LIMIT 1;
    SELECT id INTO tune_id FROM insurance_companies WHERE slug = 'tune-protect' LIMIT 1;
    SELECT id INTO amgen_id FROM insurance_companies WHERE slug = 'amassurance' LIMIT 1;

    -- Resolve trigger concepts dynamically (by concept_key / label, then legacy condition trigger_concept_id)
    IF qbe_id IS NOT NULL THEN
        SELECT COALESCE(
            (SELECT id FROM benefit_concepts WHERE concept_key ILIKE '%driver-passenger%' OR label ILIKE '%Driver & Passenger Protector%' OR label ILIKE '%Driver and Passenger Protector%' LIMIT 1),
            (SELECT trigger_concept_id FROM company_benefit_conditions WHERE company_id = qbe_id AND target_concept_id = towing_cid AND is_active = TRUE LIMIT 1)
        ) INTO qbe_dpp_cid;
    END IF;

    IF stmb_id IS NOT NULL THEN
        SELECT COALESCE(
            (SELECT id FROM benefit_concepts WHERE concept_key IN ('motor-pa-plus', 'motor-pa') OR label ILIKE '%Motor PA Plus%' OR label ILIKE '%Motor PA%' LIMIT 1),
            (SELECT trigger_concept_id FROM company_benefit_conditions WHERE company_id = stmb_id AND target_concept_id = towing_cid AND is_active = TRUE LIMIT 1)
        ) INTO stmb_pa_cid;
    END IF;

    IF etiqa_id IS NOT NULL THEN
        SELECT COALESCE(
            (SELECT id FROM benefit_concepts WHERE concept_key ILIKE '%oto-360%' OR concept_key ILIKE '%oto360%' OR label ILIKE '%OTO 360%' OR label ILIKE '%OTO360%' LIMIT 1),
            (SELECT trigger_concept_id FROM company_benefit_conditions WHERE company_id = etiqa_id AND target_concept_id = towing_cid AND is_active = TRUE LIMIT 1)
        ) INTO etiqa_oto_cid;
    END IF;

    IF lonpac_id IS NOT NULL THEN
        SELECT COALESCE(
            (SELECT id FROM benefit_concepts WHERE id = '17d2dbf1-dcc1-41ad-88a4-b08e719bacfb'::uuid OR concept_key ILIKE '%e-assist%smart-driver%' OR label ILIKE '%Smart Driver%' LIMIT 1),
            (SELECT trigger_concept_id FROM company_benefit_conditions WHERE company_id = lonpac_id AND target_concept_id = towing_cid AND is_active = TRUE LIMIT 1)
        ) INTO lonpac_sd_cid;
    END IF;

    IF tune_id IS NOT NULL THEN
        SELECT COALESCE(
            (SELECT id FROM benefit_concepts WHERE id = 'eaa5602a-6bb9-4405-b049-6cb245ee1d66'::uuid OR concept_key ILIKE '%motor-easy%' OR label ILIKE '%Motor Easy Bundle%' LIMIT 1),
            (SELECT trigger_concept_id FROM company_benefit_conditions WHERE company_id = tune_id AND target_concept_id = towing_cid AND is_active = TRUE LIMIT 1)
        ) INTO tune_primary_cid;
        SELECT id INTO tune_autobuddy_cid FROM benefit_concepts WHERE concept_key ILIKE '%autobuddy%' OR label ILIKE '%AutoBuddy%' LIMIT 1;
        SELECT id INTO tune_motorshield_cid FROM benefit_concepts WHERE id = 'a58634b4-30da-477c-b61d-bfde2ebcc3f1'::uuid OR concept_key ILIKE '%motorshield%' OR concept_key ILIKE '%motor-shield%' OR label ILIKE '%Motor Shield%' OR label ILIKE '%MotorShield%' LIMIT 1;
    END IF;

    IF amgen_id IS NOT NULL THEN
        SELECT COALESCE(
            (SELECT id FROM benefit_concepts WHERE id = '52229366-efe0-4680-b7fe-e285bd2de303'::uuid OR concept_key IN ('private-car-365', 'private_car_365') OR label ILIKE '%Private Car 365%' LIMIT 1),
            (SELECT trigger_concept_id FROM company_benefit_conditions WHERE company_id = amgen_id AND target_concept_id = towing_cid LIMIT 1)
        ) INTO amgen_pc365_cid;
        SELECT id INTO amgen_bta_cid FROM benefit_concepts WHERE concept_key ILIKE '%breakdown%towing%' OR label ILIKE '%Breakdown Towing Assistance%' LIMIT 1;
    END IF;

    FOR prof_rec IN SELECT id FROM benefit_profiles WHERE is_active = TRUE LOOP

        -- 4a. QBE: Driver & Passenger Protector (N4)
        IF qbe_id IS NOT NULL AND qbe_dpp_cid IS NOT NULL THEN
            b_id := md5('bundle:088:' || qbe_id::text || ':' || prof_rec.id::text || ':qbe-dpp-bundle')::uuid;
            t1_id := md5('tier:088:' || b_id::text || ':default')::uuid;
            INSERT INTO company_benefit_bundles (
                id, company_id, profile_id, bundle_key, name, primary_concept_id,
                trigger_concept_ids, match_aliases, catalog_scope, force_box2, has_plan_tiers, is_active, sort_order
            ) VALUES (
                b_id, qbe_id, prof_rec.id, 'qbe-dpp-bundle', 'Driver & Passenger Protector (N4)', qbe_dpp_cid,
                jsonb_build_array(qbe_dpp_cid::text),
                '["driver & passenger protector", "driver and passenger protector", "dpp", "dpa", "unlimited auto assistance", "n4"]'::jsonb,
                NULL, TRUE, FALSE, TRUE, 10
            )
            ON CONFLICT (company_id, profile_id, bundle_key) WHERE profile_id IS NOT NULL DO UPDATE
            SET name = EXCLUDED.name, primary_concept_id = EXCLUDED.primary_concept_id,
                trigger_concept_ids = EXCLUDED.trigger_concept_ids, match_aliases = EXCLUDED.match_aliases,
                force_box2 = TRUE, has_plan_tiers = FALSE, is_active = TRUE, updated_at = NOW()
            RETURNING id INTO b_id;

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (t1_id, b_id, 'plan_1', 'Plan 1', '["plan 1", "p1", "n4"]'::jsonb, TRUE, 10)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE
            SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = TRUE, updated_at = NOW()
            RETURNING id INTO t1_id;

            INSERT INTO company_benefit_bundle_effects (
                id, tier_id, target_concept_id, effect_type, display_title, display_value,
                display_description, icon_hint, comparison_value, sort_order
            ) VALUES (
                md5('eff:088:' || t1_id::text || ':' || towing_cid::text)::uuid,
                t1_id, towing_cid, 'upgrade_to_box2',
                'Unlimited Towing Assistance', '',
                '24-Hour Unlimited Towing & Auto Assistance (Plan 1 via Driver & Passenger Protector N4).',
                'unlimited_towing', 'Unlimited - Plan 1', 10
            )
            ON CONFLICT (id) DO UPDATE
            SET effect_type = EXCLUDED.effect_type, display_title = EXCLUDED.display_title,
                display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description,
                icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();
        END IF;

        -- 4b. STMB / Takaful Malaysia: Motor PA Plus Plans 1-4
        IF stmb_id IS NOT NULL AND stmb_pa_cid IS NOT NULL THEN
            b_id := md5('bundle:088:' || stmb_id::text || ':' || prof_rec.id::text || ':stmb-motor-pa-plus')::uuid;
            INSERT INTO company_benefit_bundles (
                id, company_id, profile_id, bundle_key, name, primary_concept_id,
                trigger_concept_ids, match_aliases, catalog_scope, force_box2, has_plan_tiers, is_active, sort_order
            ) VALUES (
                b_id, stmb_id, prof_rec.id, 'stmb-motor-pa-plus', 'Motor PA Plus', stmb_pa_cid,
                jsonb_build_array(stmb_pa_cid::text),
                '["motor pa plus", "motor pa+", "motor pa", "pa plus"]'::jsonb,
                NULL, TRUE, TRUE, TRUE, 10
            )
            ON CONFLICT (company_id, profile_id, bundle_key) WHERE profile_id IS NOT NULL DO UPDATE
            SET name = EXCLUDED.name, primary_concept_id = EXCLUDED.primary_concept_id,
                trigger_concept_ids = EXCLUDED.trigger_concept_ids, match_aliases = EXCLUDED.match_aliases,
                force_box2 = TRUE, has_plan_tiers = TRUE, is_active = TRUE, updated_at = NOW()
            RETURNING id INTO b_id;

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':plan_1')::uuid, b_id, 'plan_1', 'Plan 1', '["plan 1", "motor pa plan 1", "p1"]'::jsonb, TRUE, 10)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = TRUE, updated_at = NOW()
            RETURNING id INTO t1_id;
            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t1_id::text || ':' || towing_cid::text)::uuid, t1_id, towing_cid, 'upgrade_to_box2', 'Towing Assistance (100 km)', '', '24/7 emergency towing assistance up to 100 km (Motor PA Plan 1).', 'towing', '100 km', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':plan_2')::uuid, b_id, 'plan_2', 'Plan 2', '["plan 2", "motor pa plan 2", "p2"]'::jsonb, FALSE, 20)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = FALSE, updated_at = NOW()
            RETURNING id INTO t2_id;
            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t2_id::text || ':' || towing_cid::text)::uuid, t2_id, towing_cid, 'upgrade_to_box2', 'Towing Assistance (200 km)', '', '24/7 emergency towing assistance up to 200 km (Motor PA Plan 2).', 'towing', '200 km', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':plan_3')::uuid, b_id, 'plan_3', 'Plan 3', '["plan 3", "motor pa plan 3", "p3"]'::jsonb, FALSE, 30)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = FALSE, updated_at = NOW()
            RETURNING id INTO t3_id;
            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t3_id::text || ':' || towing_cid::text)::uuid, t3_id, towing_cid, 'upgrade_to_box2', 'Towing Assistance (300 km)', '', '24/7 emergency towing assistance up to 300 km (Motor PA Plan 3).', 'towing', '300 km', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':plan_4')::uuid, b_id, 'plan_4', 'Plan 4', '["plan 4", "motor pa plan 4", "p4"]'::jsonb, FALSE, 40)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = FALSE, updated_at = NOW()
            RETURNING id INTO t4_id;
            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t4_id::text || ':' || towing_cid::text)::uuid, t4_id, towing_cid, 'upgrade_to_box2', 'Unlimited Towing Assistance', '', '24/7 emergency unlimited towing assistance across Malaysia (Motor PA Plan 4).', 'unlimited_towing', 'Unlimited', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();
        END IF;

        -- 4c. Etiqa: OTO 360
        IF etiqa_id IS NOT NULL AND etiqa_oto_cid IS NOT NULL THEN
            b_id := md5('bundle:088:' || etiqa_id::text || ':' || prof_rec.id::text || ':etiqa-oto-360')::uuid;
            INSERT INTO company_benefit_bundles (
                id, company_id, profile_id, bundle_key, name, primary_concept_id,
                trigger_concept_ids, match_aliases, catalog_scope, force_box2, has_plan_tiers, is_active, sort_order
            ) VALUES (
                b_id, etiqa_id, prof_rec.id, 'etiqa-oto-360', 'OTO 360', etiqa_oto_cid,
                jsonb_build_array(etiqa_oto_cid::text),
                '["oto 360", "oto360", "oto-360", "oto premier"]'::jsonb,
                NULL, TRUE, FALSE, TRUE, 10
            )
            ON CONFLICT (company_id, profile_id, bundle_key) WHERE profile_id IS NOT NULL DO UPDATE
            SET name = EXCLUDED.name, primary_concept_id = EXCLUDED.primary_concept_id,
                trigger_concept_ids = EXCLUDED.trigger_concept_ids, match_aliases = EXCLUDED.match_aliases,
                force_box2 = TRUE, has_plan_tiers = FALSE, is_active = TRUE, updated_at = NOW()
            RETURNING id INTO b_id;

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':default')::uuid, b_id, 'default', 'Driver Plan 1', '["driver plan 1", "oto 360", "plan 1"]'::jsonb, TRUE, 10)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = TRUE, updated_at = NOW()
            RETURNING id INTO t1_id;

            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t1_id::text || ':' || towing_cid::text)::uuid, t1_id, towing_cid, 'upgrade_to_box2', 'Unlimited Towing Assistance', '', '24/7 emergency unlimited towing assistance nationwide (Driver Plan 1 via OTO 360).', 'unlimited_towing', 'Unlimited - Driver Plan 1', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();
        END IF;

        -- 4d. Lonpac: E-Assist Smart Driver (Plan 1 -> RM 600, Plan 2 & EV Plan -> Unlimited)
        IF lonpac_id IS NOT NULL AND lonpac_sd_cid IS NOT NULL THEN
            b_id := md5('bundle:088:' || lonpac_id::text || ':' || prof_rec.id::text || ':lonpac-e-assist-smart-driver')::uuid;
            INSERT INTO company_benefit_bundles (
                id, company_id, profile_id, bundle_key, name, primary_concept_id,
                trigger_concept_ids, match_aliases, catalog_scope, force_box2, has_plan_tiers, is_active, sort_order
            ) VALUES (
                b_id, lonpac_id, prof_rec.id, 'lonpac-e-assist-smart-driver', 'E-Assist Smart Driver', lonpac_sd_cid,
                jsonb_build_array(lonpac_sd_cid::text),
                '["e-assist smart driver", "e assist smart driver", "smart driver", "sdpa"]'::jsonb,
                NULL, TRUE, TRUE, TRUE, 10
            )
            ON CONFLICT (company_id, profile_id, bundle_key) WHERE profile_id IS NOT NULL DO UPDATE
            SET name = EXCLUDED.name, primary_concept_id = EXCLUDED.primary_concept_id,
                trigger_concept_ids = EXCLUDED.trigger_concept_ids, match_aliases = EXCLUDED.match_aliases,
                force_box2 = TRUE, has_plan_tiers = TRUE, is_active = TRUE, updated_at = NOW()
            RETURNING id INTO b_id;

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':plan_1')::uuid, b_id, 'plan_1', 'Plan 1', '["plan 1", "p1", "plan a", "smart driver 1"]'::jsonb, TRUE, 10)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = TRUE, updated_at = NOW()
            RETURNING id INTO t1_id;
            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t1_id::text || ':' || towing_cid::text)::uuid, t1_id, towing_cid, 'upgrade_to_box2', 'Towing Assistance (RM 600)', '', '24/7 enhanced emergency towing assistance up to RM 600 (E-Assist Smart Driver Plan 1).', 'towing', 'RM 600', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':plan_2')::uuid, b_id, 'plan_2', 'Plan 2', '["plan 2", "p2", "plan b", "smart driver 2"]'::jsonb, FALSE, 20)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = FALSE, updated_at = NOW()
            RETURNING id INTO t2_id;
            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t2_id::text || ':' || towing_cid::text)::uuid, t2_id, towing_cid, 'upgrade_to_box2', 'Unlimited Towing Assistance', '', '24/7 emergency enhanced unlimited towing assistance (E-Assist Smart Driver Plan 2).', 'unlimited_towing', 'Unlimited', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':ev_plan')::uuid, b_id, 'ev_plan', 'EV Plan', '["ev plan", "ev"]'::jsonb, FALSE, 30)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = FALSE, updated_at = NOW()
            RETURNING id INTO t3_id;
            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t3_id::text || ':' || towing_cid::text)::uuid, t3_id, towing_cid, 'upgrade_to_box2', 'Unlimited Towing Assistance', '', '24/7 emergency enhanced unlimited towing assistance (E-Assist Smart Driver EV Plan).', 'unlimited_towing', 'Unlimited', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();
        END IF;

        -- 4e. Tune Protect: Motor Easy Bundle / AutoBuddy / MotorShield
        IF tune_id IS NOT NULL AND tune_primary_cid IS NOT NULL THEN
            SELECT COALESCE(jsonb_agg(DISTINCT x), '[]'::jsonb) INTO tune_trigs
            FROM unnest(ARRAY[tune_primary_cid::text, tune_autobuddy_cid::text, tune_motorshield_cid::text]) AS x
            WHERE x IS NOT NULL;

            b_id := md5('bundle:088:' || tune_id::text || ':' || prof_rec.id::text || ':tune-unlimited-bundle')::uuid;
            INSERT INTO company_benefit_bundles (
                id, company_id, profile_id, bundle_key, name, primary_concept_id,
                trigger_concept_ids, match_aliases, catalog_scope, force_box2, has_plan_tiers, is_active, sort_order
            ) VALUES (
                b_id, tune_id, prof_rec.id, 'tune-unlimited-bundle', 'Motor Easy Bundle / AutoBuddy / MotorShield', tune_primary_cid,
                tune_trigs,
                '["motor easy bundle", "motor easy", "autobuddy", "auto buddy", "motor shield", "motorshield"]'::jsonb,
                NULL, TRUE, FALSE, TRUE, 10
            )
            ON CONFLICT (company_id, profile_id, bundle_key) WHERE profile_id IS NOT NULL DO UPDATE
            SET name = EXCLUDED.name, primary_concept_id = EXCLUDED.primary_concept_id,
                trigger_concept_ids = EXCLUDED.trigger_concept_ids, match_aliases = EXCLUDED.match_aliases,
                force_box2 = TRUE, has_plan_tiers = FALSE, is_active = TRUE, updated_at = NOW()
            RETURNING id INTO b_id;

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':default')::uuid, b_id, 'default', 'Included', '["included", "unlimited"]'::jsonb, TRUE, 10)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = TRUE, updated_at = NOW()
            RETURNING id INTO t1_id;

            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t1_id::text || ':' || towing_cid::text)::uuid, t1_id, towing_cid, 'upgrade_to_box2', 'Unlimited Towing Assistance', '', '24-Hour emergency unlimited towing assistance included with Tune Protect bundle.', 'unlimited_towing', 'Unlimited', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();
        END IF;

        -- 4f. AmAssurance: Private Car 365 (Plans 1-4)
        IF amgen_id IS NOT NULL AND amgen_pc365_cid IS NOT NULL THEN
            b_id := md5('bundle:088:' || amgen_id::text || ':' || prof_rec.id::text || ':amassurance-private-car-365')::uuid;
            INSERT INTO company_benefit_bundles (
                id, company_id, profile_id, bundle_key, name, primary_concept_id,
                trigger_concept_ids, match_aliases, catalog_scope, force_box2, has_plan_tiers, is_active, sort_order
            ) VALUES (
                b_id, amgen_id, prof_rec.id, 'amassurance-private-car-365', 'Private Car 365', amgen_pc365_cid,
                jsonb_build_array(amgen_pc365_cid::text),
                '["private car 365", "pc 365", "pc365", "365 plan"]'::jsonb,
                NULL, TRUE, TRUE, TRUE, 10
            )
            ON CONFLICT (company_id, profile_id, bundle_key) WHERE profile_id IS NOT NULL DO UPDATE
            SET name = EXCLUDED.name, primary_concept_id = EXCLUDED.primary_concept_id,
                trigger_concept_ids = EXCLUDED.trigger_concept_ids, match_aliases = EXCLUDED.match_aliases,
                catalog_scope = NULL, force_box2 = TRUE, has_plan_tiers = TRUE, is_active = TRUE, updated_at = NOW()
            RETURNING id INTO b_id;

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':plan_1')::uuid, b_id, 'plan_1', 'Plan 1', '["plan 1", "p1"]'::jsonb, TRUE, 10)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = TRUE, updated_at = NOW()
            RETURNING id INTO t1_id;
            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t1_id::text || ':' || towing_cid::text)::uuid, t1_id, towing_cid, 'upgrade_to_box2', 'Towing Assistance (600 km)', '', '24/7 emergency accident & breakdown towing assistance up to 600 km (Private Car 365 Plan 1).', 'towing', '600 km', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':plan_2')::uuid, b_id, 'plan_2', 'Plan 2', '["plan 2", "p2"]'::jsonb, FALSE, 20)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = FALSE, updated_at = NOW()
            RETURNING id INTO t2_id;
            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t2_id::text || ':' || towing_cid::text)::uuid, t2_id, towing_cid, 'upgrade_to_box2', 'Unlimited Towing Assistance', '', '24/7 emergency unlimited towing assistance nationwide (Private Car 365 Plan 2).', 'unlimited_towing', 'Unlimited', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':plan_3')::uuid, b_id, 'plan_3', 'Plan 3', '["plan 3", "p3"]'::jsonb, FALSE, 30)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = FALSE, updated_at = NOW()
            RETURNING id INTO t3_id;
            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t3_id::text || ':' || towing_cid::text)::uuid, t3_id, towing_cid, 'upgrade_to_box2', 'Unlimited Towing Assistance', '', '24/7 emergency unlimited towing assistance nationwide (Private Car 365 Plan 3).', 'unlimited_towing', 'Unlimited', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':plan_4')::uuid, b_id, 'plan_4', 'Plan 4', '["plan 4", "p4"]'::jsonb, FALSE, 40)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = FALSE, updated_at = NOW()
            RETURNING id INTO t4_id;
            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t4_id::text || ':' || towing_cid::text)::uuid, t4_id, towing_cid, 'upgrade_to_box2', 'Unlimited Towing Assistance', '', '24/7 emergency unlimited towing assistance nationwide (Private Car 365 Plan 4).', 'unlimited_towing', 'Unlimited', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();
        END IF;

        -- 4g. AmAssurance: Breakdown Towing Assistance (auto365 Lite -> Towing Assistance (150 km))
        IF amgen_id IS NOT NULL AND amgen_bta_cid IS NOT NULL THEN
            b_id := md5('bundle:088:' || amgen_id::text || ':' || prof_rec.id::text || ':amassurance-breakdown-towing')::uuid;
            INSERT INTO company_benefit_bundles (
                id, company_id, profile_id, bundle_key, name, primary_concept_id,
                trigger_concept_ids, match_aliases, catalog_scope, force_box2, has_plan_tiers, is_active, sort_order
            ) VALUES (
                b_id, amgen_id, prof_rec.id, 'amassurance-breakdown-towing', 'Breakdown Towing Assistance', amgen_bta_cid,
                jsonb_build_array(amgen_bta_cid::text),
                '["breakdown towing assistance", "breakdown towing"]'::jsonb,
                'auto365 Lite', TRUE, FALSE, TRUE, 20
            )
            ON CONFLICT (company_id, profile_id, bundle_key) WHERE profile_id IS NOT NULL DO UPDATE
            SET name = EXCLUDED.name, primary_concept_id = EXCLUDED.primary_concept_id,
                trigger_concept_ids = EXCLUDED.trigger_concept_ids, match_aliases = EXCLUDED.match_aliases,
                catalog_scope = 'auto365 Lite', force_box2 = TRUE, has_plan_tiers = FALSE, is_active = TRUE, updated_at = NOW()
            RETURNING id INTO b_id;

            INSERT INTO company_benefit_bundle_tiers (id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order)
            VALUES (md5('tier:088:' || b_id::text || ':default')::uuid, b_id, 'default', '150 km', '["150 km", "breakdown towing"]'::jsonb, TRUE, 10)
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET label = EXCLUDED.label, match_tokens = EXCLUDED.match_tokens, is_default_fallback = TRUE, updated_at = NOW()
            RETURNING id INTO t1_id;

            INSERT INTO company_benefit_bundle_effects (id, tier_id, target_concept_id, effect_type, display_title, display_value, display_description, icon_hint, comparison_value, sort_order)
            VALUES (md5('eff:088:' || t1_id::text || ':' || towing_cid::text)::uuid, t1_id, towing_cid, 'upgrade_to_box2', 'Towing Assistance (150 km)', '', '24/7 breakdown towing assistance up to 150 km (auto365 Lite upgrade).', 'towing', '150 km', 10)
            ON CONFLICT (id) DO UPDATE SET display_title = EXCLUDED.display_title, display_value = EXCLUDED.display_value, display_description = EXCLUDED.display_description, icon_hint = EXCLUDED.icon_hint, comparison_value = EXCLUDED.comparison_value, updated_at = NOW();
        END IF;

    END LOOP;
END $$;

COMMIT;
