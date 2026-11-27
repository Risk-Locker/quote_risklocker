-- 100_etiqa_dpp_bundles_and_amgen_box2_exclusions.sql
-- Idempotent enterprise migration:
-- 1. Add universal per-tier parent card display_title & display_description columns to company_benefit_bundle_tiers.
-- 2. Etiqa: retire OTO 360 bundle/offerings and replace with Driver Passenger Protection (Plans 1-3)
--    with bilingual EN/ZH titles & descriptions and Unlimited Towing promotion (Box 1 -> Box 2) across all 3 plans.
-- 3. AmAssurance, Kurnia & Liberty: disable and remove the 6 non-offered Box 2 add-ons
--    (car-detailing-cleanup, increased-tppd, smart-driver-pa, key-replacement, vehicle-accessories, repaint-spray-paint).

BEGIN;

-- ============================================================================
-- 1. Universal Per-Tier Parent Card Title & Description Columns
-- ============================================================================
ALTER TABLE public.company_benefit_bundle_tiers
    ADD COLUMN IF NOT EXISTS display_title VARCHAR(255),
    ADD COLUMN IF NOT EXISTS display_description TEXT;

-- ============================================================================
-- 2. Etiqa: Replace OTO 360 with Driver Passenger Protection (Plans 1-3)
-- ============================================================================
DO $$
DECLARE
    v_etiqa_id UUID;
    v_oto_cid UUID;
    v_dpp_cid UUID;
    v_towing_cid UUID;
    v_active_prof_id UUID;
    v_bundle_id UUID;
    v_tier1_id UUID;
    v_tier2_id UUID;
    v_tier3_id UUID;
BEGIN
    SELECT id INTO v_etiqa_id
    FROM public.insurance_companies
    WHERE LOWER(COALESCE(slug, '')) = 'etiqa'
    LIMIT 1;

    SELECT id INTO v_oto_cid
    FROM public.benefit_concepts
    WHERE concept_key = 'oto-360'
    LIMIT 1;

    SELECT id INTO v_dpp_cid
    FROM public.benefit_concepts
    WHERE concept_key = 'driver-passenger-protector'
    LIMIT 1;

    SELECT id INTO v_towing_cid
    FROM public.benefit_concepts
    WHERE concept_key = 'towing'
    LIMIT 1;

    SELECT id INTO v_active_prof_id
    FROM public.benefit_profiles
    WHERE is_active IS TRUE
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_etiqa_id IS NOT NULL THEN
        -- 2a. Update Etiqa policy_rules->'towing'
        UPDATE public.insurance_companies
        SET policy_rules = jsonb_set(
                COALESCE(policy_rules, '{}'::jsonb),
                '{towing}',
                '{
                    "metric": "km",
                    "base_limit": "200 km",
                    "unlimited_label": "Unlimited",
                    "unlimited_triggers": [
                        "driver passenger protection",
                        "driver & passenger protection",
                        "driver and passenger protection",
                        "driver passenger protector",
                        "driver & passenger pa",
                        "dpp",
                        "driver plan 1",
                        "driver plan 2",
                        "driver plan 3",
                        "oto 360",
                        "oto360",
                        "oto-360"
                    ],
                    "raw_ext_unlimited_triggers": [
                        "driver passenger",
                        "dpp",
                        "driver plan",
                        "oto 360",
                        "oto360"
                    ],
                    "respect_universal_unlimited": false
                }'::jsonb,
                true
            ),
            updated_at = NOW()
        WHERE id = v_etiqa_id;

        -- 2b. Disable oto-360 & enable driver-passenger-protector in Etiqa company_benefit_configs
        IF v_oto_cid IS NOT NULL THEN
            UPDATE public.company_benefit_configs
            SET is_enabled = FALSE,
                updated_at = NOW()
            WHERE company_id = v_etiqa_id
              AND concept_id = v_oto_cid;
        END IF;

        IF v_dpp_cid IS NOT NULL THEN
            UPDATE public.company_benefit_configs
            SET is_enabled = TRUE,
                baseline_description = 'Personal accident protection for driver and passengers (Plans 1-3) with 24/7 Unlimited Towing.',
                updated_at = NOW()
            WHERE company_id = v_etiqa_id
              AND concept_id = v_dpp_cid;

            IF v_active_prof_id IS NOT NULL THEN
                INSERT INTO public.company_benefit_configs (
                    id, company_id, profile_id, concept_id, is_enabled, baseline_description, created_at, updated_at
                )
                SELECT
                    gen_random_uuid(),
                    v_etiqa_id,
                    v_active_prof_id,
                    v_dpp_cid,
                    TRUE,
                    'Personal accident protection for driver and passengers (Plans 1-3) with 24/7 Unlimited Towing.',
                    NOW(),
                    NOW()
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM public.company_benefit_configs cbc
                    WHERE cbc.company_id = v_etiqa_id
                      AND cbc.profile_id = v_active_prof_id
                      AND cbc.concept_id = v_dpp_cid
                );
            END IF;
        END IF;

        -- 2c. Swap oto-360 -> driver-passenger-protector across Etiqa catalog_offerings and selections
        IF v_oto_cid IS NOT NULL AND v_dpp_cid IS NOT NULL THEN
            -- Clear stale bundle_tier_id references to Etiqa's old oto-360 bundle
            UPDATE public.draft_benefit_selections dbs
            SET bundle_tier_id = NULL
            FROM public.company_benefit_bundle_tiers t
            JOIN public.company_benefit_bundles b ON b.id = t.bundle_id
            WHERE dbs.bundle_tier_id = t.id
              AND b.company_id = v_etiqa_id
              AND b.bundle_key = 'etiqa-oto-360';

            -- If an Etiqa draft somehow has BOTH oto-360 and driver-passenger-protector in state='current', supersede oto-360 first
            UPDATE public.draft_benefit_selections dbs
            SET state = 'superseded'
            FROM public.quotation_drafts qd
            WHERE dbs.draft_id = qd.id
              AND qd.company_id = v_etiqa_id
              AND dbs.concept_id = v_oto_cid
              AND dbs.state = 'current'
              AND EXISTS (
                  SELECT 1
                  FROM public.draft_benefit_selections dpp_sel
                  WHERE dpp_sel.draft_id = dbs.draft_id
                    AND dpp_sel.concept_id = v_dpp_cid
                    AND dpp_sel.state = 'current'
              );

            -- Remap remaining Etiqa oto-360 selections to driver-passenger-protector
            UPDATE public.draft_benefit_selections dbs
            SET concept_id = v_dpp_cid,
                selection_key = CASE
                    WHEN dbs.selection_key LIKE '%oto-360%' THEN REPLACE(dbs.selection_key, 'oto-360', 'driver-passenger-protector')
                    ELSE dbs.selection_key
                END,
                label_override = NULL
            FROM public.quotation_drafts qd
            WHERE dbs.draft_id = qd.id
              AND qd.company_id = v_etiqa_id
              AND dbs.concept_id = v_oto_cid;

            -- Delete duplicate oto-360 offerings where driver-passenger-protector already exists on the same revision
            DELETE FROM public.benefit_package_plan_items bppi
            USING public.catalog_offerings co,
                  public.benefit_catalog_revisions bcr,
                  public.benefit_catalogs bc
            WHERE bppi.offering_id = co.id
              AND co.catalog_revision_id = bcr.id
              AND bcr.catalog_id = bc.id
              AND bc.company_id = v_etiqa_id
              AND co.concept_id = v_oto_cid
              AND EXISTS (
                  SELECT 1
                  FROM public.catalog_offerings existing_dpp
                  WHERE existing_dpp.catalog_revision_id = co.catalog_revision_id
                    AND existing_dpp.concept_id = v_dpp_cid
              );

            DELETE FROM public.catalog_offerings co
            USING public.benefit_catalog_revisions bcr,
                  public.benefit_catalogs bc
            WHERE co.catalog_revision_id = bcr.id
              AND bcr.catalog_id = bc.id
              AND bc.company_id = v_etiqa_id
              AND co.concept_id = v_oto_cid
              AND EXISTS (
                  SELECT 1
                  FROM public.catalog_offerings existing_dpp
                  WHERE existing_dpp.catalog_revision_id = co.catalog_revision_id
                    AND existing_dpp.concept_id = v_dpp_cid
              );

            -- Convert remaining Etiqa oto-360 catalog offerings to driver-passenger-protector in Box 2
            UPDATE public.catalog_offerings co
            SET concept_id = v_dpp_cid,
                offering_kind = 'optional',
                role = 'addon_option',
                offering_key = CASE
                    WHEN NOT EXISTS (
                        SELECT 1
                        FROM public.catalog_offerings x
                        WHERE x.catalog_revision_id = co.catalog_revision_id
                          AND x.offering_key = REPLACE(co.offering_key, 'oto-360', 'driver-passenger-protector')
                          AND x.id <> co.id
                    ) AND co.offering_key LIKE '%oto-360%' THEN REPLACE(co.offering_key, 'oto-360', 'driver-passenger-protector')
                    ELSE LEFT('driver-passenger-protector-' || co.id::text, 160)
                END,
                label_override = E'Driver Passenger Protection\n意外保险 (计划1-3)',
                description_override = 'Death & Disability RM 15,000-50,000, Medical RM 500-1,500, Funeral RM 1,000 / Passenger + Unlimited Towing.',
                display_value = NULL,
                optional_price = NULL,
                updated_at = NOW()
            FROM public.benefit_catalog_revisions bcr,
                 public.benefit_catalogs bc
            WHERE co.catalog_revision_id = bcr.id
              AND bcr.catalog_id = bc.id
              AND bc.company_id = v_etiqa_id
              AND co.concept_id = v_oto_cid;
        END IF;

        -- 2d. Remove Etiqa OTO 360 bundle & upsert Etiqa Driver Passenger Protection bundle (Plans 1-3)
        DELETE FROM public.company_benefit_bundles
        WHERE company_id = v_etiqa_id
          AND bundle_key = 'etiqa-oto-360';

        IF v_dpp_cid IS NOT NULL AND v_towing_cid IS NOT NULL THEN
            SELECT id INTO v_bundle_id
            FROM public.company_benefit_bundles
            WHERE company_id = v_etiqa_id
              AND bundle_key = 'etiqa-driver-passenger-protection'
              AND (profile_id IS NOT DISTINCT FROM v_active_prof_id)
            LIMIT 1;

            IF v_bundle_id IS NULL THEN
                v_bundle_id := gen_random_uuid();
                INSERT INTO public.company_benefit_bundles (
                    id, company_id, profile_id, bundle_key, name, primary_concept_id,
                    trigger_concept_ids, match_aliases, catalog_scope,
                    force_box2, has_plan_tiers, is_active, sort_order, created_at, updated_at
                )
                VALUES (
                    v_bundle_id,
                    v_etiqa_id,
                    v_active_prof_id,
                    'etiqa-driver-passenger-protection',
                    'Driver Passenger Protection',
                    v_dpp_cid,
                    jsonb_build_array(v_dpp_cid::text),
                    '["driver passenger protection", "driver & passenger protection", "driver and passenger protection", "driver passenger protector", "driver & passenger pa", "dpp", "driver plan 1", "driver plan 2", "driver plan 3"]'::jsonb,
                    NULL,
                    TRUE,
                    TRUE,
                    TRUE,
                    10,
                    NOW(),
                    NOW()
                );
            ELSE
                UPDATE public.company_benefit_bundles
                SET name = 'Driver Passenger Protection',
                    primary_concept_id = v_dpp_cid,
                    trigger_concept_ids = jsonb_build_array(v_dpp_cid::text),
                    match_aliases = '["driver passenger protection", "driver & passenger protection", "driver and passenger protection", "driver passenger protector", "driver & passenger pa", "dpp", "driver plan 1", "driver plan 2", "driver plan 3"]'::jsonb,
                    catalog_scope = NULL,
                    force_box2 = TRUE,
                    has_plan_tiers = TRUE,
                    is_active = TRUE,
                    sort_order = 10,
                    updated_at = NOW()
                WHERE id = v_bundle_id;
            END IF;

            -- Rebuild tiers cleanly for Etiqa DPP bundle (preserve existing IDs if already present)
            SELECT id INTO v_tier1_id FROM public.company_benefit_bundle_tiers WHERE bundle_id = v_bundle_id AND tier_key = 'plan_1';
            IF v_tier1_id IS NULL THEN v_tier1_id := gen_random_uuid(); END IF;

            SELECT id INTO v_tier2_id FROM public.company_benefit_bundle_tiers WHERE bundle_id = v_bundle_id AND tier_key = 'plan_2';
            IF v_tier2_id IS NULL THEN v_tier2_id := gen_random_uuid(); END IF;

            SELECT id INTO v_tier3_id FROM public.company_benefit_bundle_tiers WHERE bundle_id = v_bundle_id AND tier_key = 'plan_3';
            IF v_tier3_id IS NULL THEN v_tier3_id := gen_random_uuid(); END IF;

            INSERT INTO public.company_benefit_bundle_tiers (
                id, bundle_id, tier_key, label, display_title, display_description,
                match_tokens, is_default_fallback, sort_order, created_at, updated_at
            )
            VALUES (
                v_tier1_id,
                v_bundle_id,
                'plan_1',
                'Plan 1',
                E'Driver Passenger Protection Plan 1\n意外保险-计划1',
                E'Death and Disability - RM 15,000 / Passenger\n死亡/永久性残疾-RM 15,000/每位乘客\nMedical Expenses - RM 500 / Passenger\n意外医药费用-RM 500/每位乘客\nFuneral Expenses - RM 1,000 / Passenger\n丧事津贴 - RM 1,000/每位乘客',
                '["plan 1", "pelan 1", "p1", "dpp plan 1", "driver plan 1", "计划1"]'::jsonb,
                TRUE,
                10,
                NOW(),
                NOW()
            )
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET
                label = EXCLUDED.label,
                display_title = EXCLUDED.display_title,
                display_description = EXCLUDED.display_description,
                match_tokens = EXCLUDED.match_tokens,
                is_default_fallback = EXCLUDED.is_default_fallback,
                sort_order = EXCLUDED.sort_order,
                updated_at = NOW();

            INSERT INTO public.company_benefit_bundle_tiers (
                id, bundle_id, tier_key, label, display_title, display_description,
                match_tokens, is_default_fallback, sort_order, created_at, updated_at
            )
            VALUES (
                v_tier2_id,
                v_bundle_id,
                'plan_2',
                'Plan 2',
                E'Driver Passenger Protection Plan 2\n意外保险-计划2',
                E'Death and Disability - RM 30,000 / Passenger\n死亡/永久性残疾-RM 30,000/每位乘客\nMedical Expenses - RM 1,000 / Passenger\n意外医药费用-RM 1,000/每位乘客\nFuneral Expenses - RM 1,000 / Passenger\n丧事津贴 - RM 1,000/每位乘客',
                '["plan 2", "pelan 2", "p2", "dpp plan 2", "driver plan 2", "计划2"]'::jsonb,
                FALSE,
                20,
                NOW(),
                NOW()
            )
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET
                label = EXCLUDED.label,
                display_title = EXCLUDED.display_title,
                display_description = EXCLUDED.display_description,
                match_tokens = EXCLUDED.match_tokens,
                is_default_fallback = EXCLUDED.is_default_fallback,
                sort_order = EXCLUDED.sort_order,
                updated_at = NOW();

            INSERT INTO public.company_benefit_bundle_tiers (
                id, bundle_id, tier_key, label, display_title, display_description,
                match_tokens, is_default_fallback, sort_order, created_at, updated_at
            )
            VALUES (
                v_tier3_id,
                v_bundle_id,
                'plan_3',
                'Plan 3',
                E'Driver Passenger Protection Plan 3\n意外保险-计划3',
                E'Death and Disability - RM 50,000 / Passenger\n死亡/永久性残疾-RM 50,000/每位乘客\nMedical Expenses - RM 1,500 / Passenger\n意外医药费用-RM 1,500/每位乘客\nFuneral Expenses - RM 1,000 / Passenger\n丧事津贴 - RM 1,000/每位乘客',
                '["plan 3", "pelan 3", "p3", "dpp plan 3", "driver plan 3", "计划3"]'::jsonb,
                FALSE,
                30,
                NOW(),
                NOW()
            )
            ON CONFLICT (bundle_id, tier_key) DO UPDATE SET
                label = EXCLUDED.label,
                display_title = EXCLUDED.display_title,
                display_description = EXCLUDED.display_description,
                match_tokens = EXCLUDED.match_tokens,
                is_default_fallback = EXCLUDED.is_default_fallback,
                sort_order = EXCLUDED.sort_order,
                updated_at = NOW();

            -- Replace effects for Plans 1, 2, 3 -> all promote Unlimited Towing to Box 2 & remove Box 1 free towing
            DELETE FROM public.company_benefit_bundle_effects
            WHERE tier_id IN (v_tier1_id, v_tier2_id, v_tier3_id);

            INSERT INTO public.company_benefit_bundle_effects (
                id, tier_id, target_concept_id, effect_type, display_title, display_value,
                display_description, icon_hint, comparison_value, sort_order, created_at, updated_at
            )
            VALUES
            (
                gen_random_uuid(),
                v_tier1_id,
                v_towing_cid,
                'upgrade_to_box2',
                'Unlimited Towing Assistance',
                '',
                '24/7 emergency unlimited towing assistance nationwide (Driver Passenger Protection Plan 1).',
                'unlimited_towing',
                'Unlimited',
                10,
                NOW(),
                NOW()
            ),
            (
                gen_random_uuid(),
                v_tier2_id,
                v_towing_cid,
                'upgrade_to_box2',
                'Unlimited Towing Assistance',
                '',
                '24/7 emergency unlimited towing assistance nationwide (Driver Passenger Protection Plan 2).',
                'unlimited_towing',
                'Unlimited',
                10,
                NOW(),
                NOW()
            ),
            (
                gen_random_uuid(),
                v_tier3_id,
                v_towing_cid,
                'upgrade_to_box2',
                'Unlimited Towing Assistance',
                '',
                '24/7 emergency unlimited towing assistance nationwide (Driver Passenger Protection Plan 3).',
                'unlimited_towing',
                'Unlimited',
                10,
                NOW(),
                NOW()
            );

            -- Bind existing Etiqa DPP current selections without a tier to Plan 1 by default
            UPDATE public.draft_benefit_selections dbs
            SET bundle_tier_id = v_tier1_id
            FROM public.quotation_drafts qd
            WHERE dbs.draft_id = qd.id
              AND qd.company_id = v_etiqa_id
              AND dbs.concept_id = v_dpp_cid
              AND dbs.state = 'current'
              AND dbs.bundle_tier_id IS NULL;
        END IF;
    END IF;
END $$;

-- ============================================================================
-- 3. AmAssurance, Kurnia & Liberty: Exclude 6 Non-Offered Box 2 Add-Ons
-- ============================================================================
DO $$
DECLARE
    v_active_prof_id UUID;
BEGIN
    SELECT id INTO v_active_prof_id
    FROM public.benefit_profiles
    WHERE is_active IS TRUE
    ORDER BY created_at DESC
    LIMIT 1;

    -- 3a. Disable in company_benefit_configs across all existing profiles
    UPDATE public.company_benefit_configs cbc
    SET is_enabled = FALSE,
        updated_at = NOW()
    FROM public.insurance_companies ic,
         public.benefit_concepts bcon
    WHERE cbc.company_id = ic.id
      AND cbc.concept_id = bcon.id
      AND LOWER(COALESCE(ic.slug, '')) IN ('amassurance', 'kurnia', 'liberty')
      AND bcon.concept_key IN (
          'car-detailing-cleanup',
          'increased-tppd',
          'smart-driver-pa',
          'key-replacement',
          'vehicle-accessories',
          'repaint-spray-paint'
      );

    -- 3b. Ensure explicit disabled row exists on active profile for all 3 companies x 6 concepts
    IF v_active_prof_id IS NOT NULL THEN
        INSERT INTO public.company_benefit_configs (
            id, company_id, profile_id, concept_id, is_enabled, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            ic.id,
            v_active_prof_id,
            bcon.id,
            FALSE,
            NOW(),
            NOW()
        FROM public.insurance_companies ic
        CROSS JOIN public.benefit_concepts bcon
        WHERE LOWER(COALESCE(ic.slug, '')) IN ('amassurance', 'kurnia', 'liberty')
          AND bcon.concept_key IN (
              'car-detailing-cleanup',
              'increased-tppd',
              'smart-driver-pa',
              'key-replacement',
              'vehicle-accessories',
              'repaint-spray-paint'
          )
          AND NOT EXISTS (
              SELECT 1
              FROM public.company_benefit_configs cbc
              WHERE cbc.company_id = ic.id
                AND cbc.profile_id = v_active_prof_id
                AND cbc.concept_id = bcon.id
          );
    END IF;

    -- 3c. Remove non-current draft selections (available_addon/removed/superseded/unresolved) for those 6 concepts on AmGen
    DELETE FROM public.draft_benefit_selections dbs
    USING public.quotation_drafts qd,
          public.insurance_companies ic,
          public.benefit_concepts bcon
    WHERE dbs.draft_id = qd.id
      AND qd.company_id = ic.id
      AND dbs.concept_id = bcon.id
      AND LOWER(COALESCE(ic.slug, '')) IN ('amassurance', 'kurnia', 'liberty')
      AND bcon.concept_key IN (
          'car-detailing-cleanup',
          'increased-tppd',
          'smart-driver-pa',
          'key-replacement',
          'vehicle-accessories',
          'repaint-spray-paint'
      )
      AND dbs.state <> 'current';

    -- 3d. Preserve historical state='current' selections as custom items with non-null label_override before deleting offerings
    UPDATE public.draft_benefit_selections dbs
    SET catalog_offering_id = NULL,
        item_kind = 'custom',
        label_override = COALESCE(NULLIF(TRIM(dbs.label_override), ''), bcon.label)
    FROM public.catalog_offerings co,
         public.benefit_catalog_revisions bcr,
         public.benefit_catalogs bc,
         public.insurance_companies ic,
         public.benefit_concepts bcon
    WHERE dbs.catalog_offering_id = co.id
      AND co.catalog_revision_id = bcr.id
      AND bcr.catalog_id = bc.id
      AND bc.company_id = ic.id
      AND co.concept_id = bcon.id
      AND LOWER(COALESCE(ic.slug, '')) IN ('amassurance', 'kurnia', 'liberty')
      AND bcon.concept_key IN (
          'car-detailing-cleanup',
          'increased-tppd',
          'smart-driver-pa',
          'key-replacement',
          'vehicle-accessories',
          'repaint-spray-paint'
      )
      AND (co.offering_kind IN ('optional', 'upgrade') OR co.role IN ('addon_option', 'bundle_component'));

    -- 3e. Delete package plan items referencing those Box 2 offerings
    DELETE FROM public.benefit_package_plan_items bppi
    USING public.catalog_offerings co,
          public.benefit_catalog_revisions bcr,
          public.benefit_catalogs bc,
          public.insurance_companies ic,
          public.benefit_concepts bcon
    WHERE bppi.offering_id = co.id
      AND co.catalog_revision_id = bcr.id
      AND bcr.catalog_id = bc.id
      AND bc.company_id = ic.id
      AND co.concept_id = bcon.id
      AND LOWER(COALESCE(ic.slug, '')) IN ('amassurance', 'kurnia', 'liberty')
      AND bcon.concept_key IN (
          'car-detailing-cleanup',
          'increased-tppd',
          'smart-driver-pa',
          'key-replacement',
          'vehicle-accessories',
          'repaint-spray-paint'
      )
      AND (co.offering_kind IN ('optional', 'upgrade') OR co.role IN ('addon_option', 'bundle_component'));

    -- 3f. Delete Box 2 offerings across all AmAssurance, Kurnia & Liberty catalogs for those 6 concepts
    DELETE FROM public.catalog_offerings co
    USING public.benefit_catalog_revisions bcr,
          public.benefit_catalogs bc,
          public.insurance_companies ic,
          public.benefit_concepts bcon
    WHERE co.catalog_revision_id = bcr.id
      AND bcr.catalog_id = bc.id
      AND bc.company_id = ic.id
      AND co.concept_id = bcon.id
      AND LOWER(COALESCE(ic.slug, '')) IN ('amassurance', 'kurnia', 'liberty')
      AND bcon.concept_key IN (
          'car-detailing-cleanup',
          'increased-tppd',
          'smart-driver-pa',
          'key-replacement',
          'vehicle-accessories',
          'repaint-spray-paint'
      )
      AND (co.offering_kind IN ('optional', 'upgrade') OR co.role IN ('addon_option', 'bundle_component'));
END $$;

COMMIT;
