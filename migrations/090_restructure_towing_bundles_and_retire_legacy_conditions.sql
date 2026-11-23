-- 090_restructure_towing_bundles_and_retire_legacy_conditions.sql
-- 1. Repair Takaful Malaysia Motor PA Plus bundle pointing to retired 'motorcycle-pa-bundle' -> active 'motor-pa-plus'.
-- 2. Retire all legacy 1-to-1 towing rules in company_benefit_conditions so company_benefit_bundles is the single source of truth.
-- 3. Align AmAssurance auto365 packages (Comprehensive Lite=50 km, Plus=100 km, Premier=365 km, TPFT Premier=200 km),
--    ensure Private Car 365 optional add-on exists on their latest published revisions, and update AmAssurance policy_rules.

BEGIN;

DO $$
DECLARE
    towing_cid UUID;
    pc365_cid UUID;
    stmb_id UUID;
    stmb_pa_plus_cid UUID;
    amgen_id UUID;
    seg_private_id UUID;
    veh_car_id UUID;
    cov_tpft_id UUID;
    v_tpft_premier_prod_id UUID;
    v_tpft_premier_cat_id UUID;
    v_tpft_premier_rev_id UUID;
    rec RECORD;
    v_hash CHAR(64);
BEGIN
    SELECT id INTO towing_cid
    FROM public.benefit_concepts
    WHERE concept_key = 'towing'
    ORDER BY (status = 'active') DESC
    LIMIT 1;

    SELECT id INTO pc365_cid
    FROM public.benefit_concepts
    WHERE concept_key = 'private-car-365'
    ORDER BY (status = 'active') DESC
    LIMIT 1;

    SELECT id INTO stmb_id FROM public.insurance_companies WHERE slug = 'takaful-malaysia' LIMIT 1;
    SELECT id INTO amgen_id FROM public.insurance_companies WHERE slug = 'amassurance' LIMIT 1;

    -- 1. Fix Takaful Malaysia Motor PA Plus bundle (replace retired 'motorcycle-pa-bundle' with active 'motor-pa-plus')
    SELECT id INTO stmb_pa_plus_cid
    FROM public.benefit_concepts
    WHERE concept_key = 'motor-pa-plus' AND status = 'active'
    LIMIT 1;

    IF stmb_id IS NOT NULL AND stmb_pa_plus_cid IS NOT NULL THEN
        UPDATE public.company_benefit_bundles
        SET primary_concept_id = stmb_pa_plus_cid,
            trigger_concept_ids = jsonb_build_array(stmb_pa_plus_cid::text),
            match_aliases = '["motor pa plus", "motor pa+", "motor pa", "pa plus"]'::jsonb,
            updated_at = NOW()
        WHERE company_id = stmb_id
          AND bundle_key = 'stmb-motor-pa-plus';
    END IF;

    -- 2. Retire ALL legacy 1-to-1 towing rules in company_benefit_conditions
    IF towing_cid IS NOT NULL THEN
        UPDATE public.company_benefit_conditions
        SET is_active = FALSE,
            updated_at = NOW()
        WHERE target_concept_id IN (
            SELECT id FROM public.benefit_concepts WHERE concept_key = 'towing'
        )
          AND is_active = TRUE;
    END IF;

    -- 3. Align AmAssurance auto365 Comprehensive Lite (50 km), Plus (100 km), Premier (365 km) & TPFT Premier (200 km)
    IF amgen_id IS NOT NULL AND towing_cid IS NOT NULL THEN
        -- 3a. auto365 Comprehensive Lite (ICE & EV, excluding TPFT / Third Party) -> 50 km
        UPDATE public.catalog_offerings co
        SET display_value = '50 km',
            typed_value = CASE
                WHEN co.typed_value IS NOT NULL AND co.typed_value::text ILIKE '%200%' THEN NULL
                ELSE co.typed_value
            END,
            description_override = '24/7 emergency accident and breakdown towing assistance up to 50 km.',
            updated_at = NOW()
        FROM public.benefit_catalog_revisions bcr, public.benefit_catalogs bc
        WHERE co.catalog_revision_id = bcr.id
          AND bcr.catalog_id = bc.id
          AND bc.company_id = amgen_id
          AND bc.name ILIKE '%auto365%Comprehensive%Lite%'
          AND bc.name NOT ILIKE '%TPFT%'
          AND bc.name NOT ILIKE '%Third Party%'
          AND co.concept_id = towing_cid
          AND co.offering_kind = 'base';

        -- 3b. Ensure auto365 Comprehensive Plus -> 100 km & Premier -> 365 km
        UPDATE public.catalog_offerings co
        SET display_value = '100 km',
            description_override = '24/7 emergency accident and breakdown towing assistance up to 100 km.',
            updated_at = NOW()
        FROM public.benefit_catalog_revisions bcr, public.benefit_catalogs bc
        WHERE co.catalog_revision_id = bcr.id
          AND bcr.catalog_id = bc.id
          AND bc.company_id = amgen_id
          AND bc.name ILIKE '%auto365%Comprehensive%Plus%'
          AND co.concept_id = towing_cid
          AND co.offering_kind = 'base'
          AND COALESCE(co.display_value, '') <> '100 km';

        UPDATE public.catalog_offerings co
        SET display_value = '365 km',
            description_override = '24/7 emergency accident and breakdown towing assistance up to 365 km.',
            updated_at = NOW()
        FROM public.benefit_catalog_revisions bcr, public.benefit_catalogs bc
        WHERE co.catalog_revision_id = bcr.id
          AND bcr.catalog_id = bc.id
          AND bc.company_id = amgen_id
          AND bc.name ILIKE '%auto365%Comprehensive%Premier%'
          AND bc.name NOT ILIKE '%TPFT%'
          AND co.concept_id = towing_cid
          AND co.offering_kind = 'base'
          AND COALESCE(co.display_value, '') <> '365 km';

        -- 3c. Ensure Private Car 365 exists as optional addon_option on latest published revision of each auto365 Comprehensive catalog
        IF pc365_cid IS NOT NULL THEN
            FOR rec IN
                SELECT DISTINCT ON (bc.id)
                    bc.id AS catalog_id,
                    bcr.id AS rev_id
                FROM public.benefit_catalogs bc
                JOIN public.benefit_catalog_revisions bcr
                  ON bcr.catalog_id = bc.id
                 AND bcr.state = 'published'
                 AND bcr.is_archived = FALSE
                WHERE bc.company_id = amgen_id
                  AND bc.status IN ('published', 'active')
                  AND bc.name ILIKE 'auto365 Comprehensive%'
                  AND bc.name NOT ILIKE '%TPFT%'
                  AND bc.name NOT ILIKE '%Third Party%'
                ORDER BY bc.id, bcr.revision_number DESC
            LOOP
                IF EXISTS (
                    SELECT 1 FROM public.catalog_offerings co
                    WHERE co.catalog_revision_id = rec.rev_id
                      AND co.concept_id = pc365_cid
                ) THEN
                    UPDATE public.catalog_offerings
                    SET offering_kind = 'optional',
                        role = 'addon_option',
                        status = 'active',
                        updated_at = NOW()
                    WHERE catalog_revision_id = rec.rev_id
                      AND concept_id = pc365_cid;
                ELSE
                    INSERT INTO public.catalog_offerings (
                        id, catalog_revision_id, offering_key, concept_id,
                        offering_kind, role, label_override, description_override,
                        sort_order, status, created_at, updated_at
                    ) VALUES (
                        md5('co:090:pc365:' || rec.rev_id::text)::uuid,
                        rec.rev_id,
                        'private-car-365-090-' || substr(md5(rec.rev_id::text), 1, 8),
                        pc365_cid,
                        'optional',
                        'addon_option',
                        NULL,
                        'Bundles All Drivers waiver, RM1,500 flood grant, RM1,000 key care & towing.',
                        30,
                        'active',
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (catalog_revision_id, offering_key) DO NOTHING;
                END IF;
            END LOOP;
        END IF;

        -- 3d. Ensure auto365 TPFT Premier catalog exists under AmAssurance with base 200 km towing + Private Car 365 optional add-on
        SELECT id INTO seg_private_id FROM public.segments WHERE segment_key = 'private' LIMIT 1;
        SELECT id INTO veh_car_id FROM public.vehicle_categories WHERE category_key = 'car' LIMIT 1;
        SELECT id INTO cov_tpft_id FROM public.coverage_types WHERE coverage_key = 'third_party_fire_theft' LIMIT 1;

        SELECT id INTO v_tpft_premier_prod_id
        FROM public.insurance_products
        WHERE company_id = amgen_id
          AND (product_key = 'amassurance-auto365-tpft-premier' OR LOWER(name) = 'auto365 tpft premier')
        LIMIT 1;

        IF v_tpft_premier_prod_id IS NULL THEN
            v_tpft_premier_prod_id := md5('prod:090:amassurance:auto365-tpft-premier')::uuid;
            INSERT INTO public.insurance_products (
                id, company_id, product_key, name, channel, revision, status, created_at, updated_at
            ) VALUES (
                v_tpft_premier_prod_id,
                amgen_id,
                'amassurance-auto365-tpft-premier',
                'auto365 TPFT Premier',
                NULL,
                1,
                'active',
                NOW(),
                NOW()
            )
            ON CONFLICT (company_id, product_key) DO NOTHING;

            SELECT id INTO v_tpft_premier_prod_id
            FROM public.insurance_products
            WHERE company_id = amgen_id AND product_key = 'amassurance-auto365-tpft-premier'
            LIMIT 1;
        END IF;

        SELECT id INTO v_tpft_premier_cat_id
        FROM public.benefit_catalogs
        WHERE company_id = amgen_id
          AND LOWER(name) = 'auto365 tpft premier'
        LIMIT 1;

        IF v_tpft_premier_cat_id IS NULL AND v_tpft_premier_prod_id IS NOT NULL THEN
            v_tpft_premier_cat_id := md5('cat:090:amassurance:auto365-tpft-premier')::uuid;
            INSERT INTO public.benefit_catalogs (
                id, company_id, product_id, tier_id, name, revision, status,
                segment_id, vehicle_category_id, coverage_type_id, engine_type,
                created_at, updated_at
            ) VALUES (
                v_tpft_premier_cat_id,
                amgen_id,
                v_tpft_premier_prod_id,
                NULL,
                'auto365 TPFT Premier',
                1,
                'published',
                seg_private_id,
                veh_car_id,
                cov_tpft_id,
                'ice',
                NOW(),
                NOW()
            )
            ON CONFLICT DO NOTHING;

            SELECT id INTO v_tpft_premier_cat_id
            FROM public.benefit_catalogs
            WHERE company_id = amgen_id AND LOWER(name) = 'auto365 tpft premier'
            LIMIT 1;
        END IF;

        IF v_tpft_premier_cat_id IS NOT NULL THEN
            SELECT id INTO v_tpft_premier_rev_id
            FROM public.benefit_catalog_revisions
            WHERE catalog_id = v_tpft_premier_cat_id
              AND state = 'published'
              AND is_archived = FALSE
            ORDER BY revision_number DESC
            LIMIT 1;

            IF v_tpft_premier_rev_id IS NULL THEN
                v_tpft_premier_rev_id := md5('rev:090:amassurance:auto365-tpft-premier:1')::uuid;
                v_hash := md5('rev:090:amassurance:auto365-tpft-premier:hash1') || md5('rev:090:amassurance:auto365-tpft-premier:hash2');
                INSERT INTO public.benefit_catalog_revisions (
                    id, catalog_id, revision_number, state, source_document_ids,
                    content_hash, published_at, created_at, updated_at, is_archived
                ) VALUES (
                    v_tpft_premier_rev_id,
                    v_tpft_premier_cat_id,
                    1,
                    'published',
                    '[]'::jsonb,
                    v_hash,
                    NOW(),
                    NOW(),
                    NOW(),
                    FALSE
                )
                ON CONFLICT (catalog_id, revision_number) DO NOTHING;

                SELECT id INTO v_tpft_premier_rev_id
                FROM public.benefit_catalog_revisions
                WHERE catalog_id = v_tpft_premier_cat_id
                ORDER BY revision_number DESC
                LIMIT 1;
            END IF;

            IF v_tpft_premier_rev_id IS NOT NULL THEN
                IF EXISTS (
                    SELECT 1 FROM public.catalog_offerings
                    WHERE catalog_revision_id = v_tpft_premier_rev_id
                      AND concept_id = towing_cid
                      AND offering_kind = 'base'
                ) THEN
                    UPDATE public.catalog_offerings
                    SET display_value = '200 km',
                        description_override = '24/7 emergency accident and breakdown towing assistance up to 200 km.',
                        status = 'active',
                        updated_at = NOW()
                    WHERE catalog_revision_id = v_tpft_premier_rev_id
                      AND concept_id = towing_cid
                      AND offering_kind = 'base';
                ELSE
                    INSERT INTO public.catalog_offerings (
                        id, catalog_revision_id, offering_key, concept_id,
                        offering_kind, role, label_override, display_value, description_override,
                        sort_order, status, created_at, updated_at
                    ) VALUES (
                        md5('co:090:tpft-premier:towing')::uuid,
                        v_tpft_premier_rev_id,
                        'towing-tpft-premier-included',
                        towing_cid,
                        'base',
                        'included',
                        NULL,
                        '200 km',
                        '24/7 emergency accident and breakdown towing assistance up to 200 km.',
                        0,
                        'active',
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (catalog_revision_id, offering_key) DO NOTHING;
                END IF;

                IF pc365_cid IS NOT NULL THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM public.catalog_offerings
                        WHERE catalog_revision_id = v_tpft_premier_rev_id
                          AND concept_id = pc365_cid
                    ) THEN
                        INSERT INTO public.catalog_offerings (
                            id, catalog_revision_id, offering_key, concept_id,
                            offering_kind, role, label_override, description_override,
                            sort_order, status, created_at, updated_at
                        ) VALUES (
                            md5('co:090:tpft-premier:pc365')::uuid,
                            v_tpft_premier_rev_id,
                            'private-car-365-tpft-premier-addon',
                            pc365_cid,
                            'optional',
                            'addon_option',
                            NULL,
                            'Bundles All Drivers waiver, RM1,500 flood grant, RM1,000 key care & towing.',
                            30,
                            'active',
                            NOW(),
                            NOW()
                        )
                        ON CONFLICT (catalog_revision_id, offering_key) DO NOTHING;
                    END IF;
                END IF;
            END IF;
        END IF;

        -- 3e. Update AmAssurance policy_rules JSONB towing object
        UPDATE public.insurance_companies
        SET policy_rules = jsonb_set(
                COALESCE(policy_rules, '{}'::jsonb),
                '{towing}',
                '{"metric": "km", "base_limit": "100 km", "lite_limit": "50 km", "premier_limit": "365 km", "tpft_premier_limit": "200 km", "sdpa_triggers": ["private car 365", "pc 365", "pc365", "365 plan"], "sdpa_plan1_limit": "600 km", "unlimited_triggers": ["amdrive plus"]}'::jsonb,
                TRUE
            ),
            updated_at = NOW()
        WHERE id = amgen_id;
    END IF;
END $$;

COMMIT;
