-- 091_liberty_company_and_amgen_family_catalog_parity.sql
-- 1. Seed Liberty (`slug = 'liberty'`) as a distinct Motor insurer alongside Kurnia & AmAssurance.
-- 2. Enforce clean, non-colliding `detection_phrases` & `company_aliases` across Liberty, Kurnia, AmAssurance, and MMIP
--    (never letting shared parent "Liberty General Insurance Berhad" or shared "auto365" bias a single brand).
-- 3. Carbon-copy AmAssurance's authoritative products, tiers, catalogs, offerings, packages, configs,
--    active conditions, policy_rules, and bundled Mystery Box rules verbatim onto BOTH Liberty and Kurnia
--    (also repairing legacy 086 Kurnia "Kurnia Auto365" renames & overwritten source_aliases).

BEGIN;

-- ============================================================================
-- 1. Seed Liberty Company & Enforce Clean Non-Colliding Aliases
-- ============================================================================

INSERT INTO public.insurance_companies (
    id,
    slug,
    revision,
    name,
    category,
    source_template_category,
    detection_phrases,
    status,
    created_at,
    updated_at
)
SELECT
    'c0000000-0000-4000-8000-000000000091'::uuid,
    'liberty',
    1,
    'Liberty',
    'Motor',
    'Amgen / AmAssurance / Kurnia-style',
    '["Liberty", "Liberty Insurance", "Liberty Insurance Berhad", "www.libertyinsurance.com.my", "libertyinsurance.com.my"]'::jsonb,
    'active',
    NOW(),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM public.insurance_companies
    WHERE slug = 'liberty'
       OR LOWER(name) IN ('liberty', 'liberty insurance', 'liberty insurance berhad', 'liberty general insurance berhad')
);

UPDATE public.insurance_companies
SET
    slug = COALESCE(NULLIF(slug, ''), 'liberty'),
    name = 'Liberty',
    source_template_category = 'Amgen / AmAssurance / Kurnia-style',
    detection_phrases = '["Liberty", "Liberty Insurance", "Liberty Insurance Berhad", "www.libertyinsurance.com.my", "libertyinsurance.com.my"]'::jsonb,
    status = 'active',
    updated_at = NOW()
WHERE slug = 'liberty'
   OR LOWER(name) IN ('liberty', 'liberty insurance', 'liberty insurance berhad', 'liberty general insurance berhad');

UPDATE public.insurance_companies
SET
    source_template_category = 'Amgen / AmAssurance / Kurnia-style',
    detection_phrases = '["Kurnia", "Kurnia Insurans", "Kurnia Insurance", "Kurnia Insurans (Malaysia) Berhad", "www.kurnia.com", "kurnia.com", "Kurnia Auto Assist"]'::jsonb,
    status = 'active',
    updated_at = NOW()
WHERE slug = 'kurnia';

UPDATE public.insurance_companies
SET
    source_template_category = 'Amgen / AmAssurance / Kurnia-style',
    detection_phrases = '["AmAssurance", "amassurance", "AmGen", "AmGeneral", "AmGeneral Insurance", "www.amassurance.com.my", "amassurance.com.my"]'::jsonb,
    status = 'active',
    updated_at = NOW()
WHERE slug = 'amassurance';

UPDATE public.insurance_companies
SET
    detection_phrases = '["MMIP", "Malaysian Motor Insurance Pool", "Malaysia Motor Insurance Pool", "Motor Insurance Pool"]'::jsonb,
    policy_rules = '{
      "allowed_coverage_types": ["third_party"],
      "betterment": {"auto_waive_without_peril": false, "max_waiver_years": 0, "default_display": "N/A (Third Party)"},
      "towing": {"metric": "none", "base_limit": "No towing"}
    }'::jsonb,
    status = 'active',
    updated_at = NOW()
WHERE slug = 'mmip';

-- Remove colliding cross-brand or shared boilerplate aliases from company_aliases
DELETE FROM public.company_aliases
WHERE company_id IN (SELECT id FROM public.insurance_companies WHERE slug = 'amassurance')
  AND LOWER(alias) IN ('kurnia', 'kurnia one touch', 'liberty', 'liberty insurance', 'liberty general insurance', 'liberty general insurance berhad', 'auto365', 'auto 365');

DELETE FROM public.company_aliases
WHERE company_id IN (SELECT id FROM public.insurance_companies WHERE slug = 'kurnia')
  AND LOWER(alias) IN ('liberty', 'liberty insurance', 'liberty general insurance', 'liberty general insurance berhad', 'amassurance', 'amgen', 'amgeneral', 'amgeneral insurance', 'auto365', 'auto 365', 'kurnia one touch');

DELETE FROM public.company_aliases
WHERE company_id IN (SELECT id FROM public.insurance_companies WHERE slug = 'liberty')
  AND LOWER(alias) IN ('kurnia', 'kurnia one touch', 'amassurance', 'amgen', 'amgeneral', 'amgeneral insurance', 'auto365', 'auto 365', 'liberty general insurance', 'liberty general insurance berhad');

-- ============================================================================
-- 2. Carbon-Copy AmAssurance -> Liberty & Kurnia (Products, Catalogs, Bundles)
-- ============================================================================

DO $$
DECLARE
    v_am_id UUID;
    v_target_slug TEXT;
    v_target_id UUID;
    v_am_rules JSONB;
    v_prod RECORD;
    v_new_prod_id UUID;
    v_tier RECORD;
    v_new_tier_id UUID;
    v_cat RECORD;
    v_new_cat_id UUID;
    v_src_rev RECORD;
    v_tgt_rev_id UUID;
    v_off RECORD;
    v_new_off_id UUID;
    v_pkg RECORD;
    v_new_pkg_id UUID;
    v_plan RECORD;
    v_new_plan_id UUID;
    v_bundle RECORD;
    v_new_bundle_id UUID;
    v_btier RECORD;
    v_new_btier_id UUID;
    v_prod_map JSONB;
    v_tier_map JSONB;
    v_off_map JSONB;
    v_pkg_map JSONB;
    v_towing_cid UUID;
BEGIN
    SELECT id, policy_rules INTO v_am_id, v_am_rules
    FROM public.insurance_companies
    WHERE slug = 'amassurance'
    LIMIT 1;

    IF v_am_id IS NULL THEN
        SELECT id, policy_rules INTO v_am_id, v_am_rules
        FROM public.insurance_companies
        WHERE LOWER(name) LIKE '%amassurance%' OR LOWER(name) LIKE '%amgen%'
        LIMIT 1;
    END IF;

    IF v_am_id IS NULL THEN
        RETURN;
    END IF;

    SELECT id INTO v_towing_cid
    FROM public.benefit_concepts
    WHERE concept_key = 'towing'
    ORDER BY (status = 'active') DESC
    LIMIT 1;

    FOREACH v_target_slug IN ARRAY ARRAY['liberty', 'kurnia'] LOOP
        SELECT id INTO v_target_id
        FROM public.insurance_companies
        WHERE slug = v_target_slug
        LIMIT 1;

        IF v_target_id IS NULL THEN
            CONTINUE;
        END IF;

        -- 2a. Copy AmAssurance policy_rules verbatim onto target company
        IF v_am_rules IS NOT NULL THEN
            UPDATE public.insurance_companies
            SET policy_rules = v_am_rules,
                source_template_category = 'Amgen / AmAssurance / Kurnia-style',
                updated_at = NOW()
            WHERE id = v_target_id;
        END IF;

        -- Repair legacy 086 Kurnia renames before syncing
        IF v_target_slug = 'kurnia' THEN
            UPDATE public.insurance_products
            SET name = REPLACE(name, 'Kurnia Auto365', 'auto365'),
                updated_at = NOW()
            WHERE company_id = v_target_id
              AND name LIKE '%Kurnia Auto365%';

            UPDATE public.benefit_catalogs
            SET name = REPLACE(name, 'Kurnia Auto365', 'auto365'),
                updated_at = NOW()
            WHERE company_id = v_target_id
              AND name LIKE '%Kurnia Auto365%';
        END IF;

        v_prod_map := '{}'::jsonb;
        v_tier_map := '{}'::jsonb;
        v_pkg_map := '{}'::jsonb;

        -- 2b. Sync Products & Product Tiers verbatim
        FOR v_prod IN
            SELECT * FROM public.insurance_products WHERE company_id = v_am_id AND status = 'active'
        LOOP
            SELECT id INTO v_new_prod_id
            FROM public.insurance_products
            WHERE company_id = v_target_id AND product_key = v_prod.product_key
            LIMIT 1;

            IF v_new_prod_id IS NULL THEN
                v_new_prod_id := gen_random_uuid();
                INSERT INTO public.insurance_products (
                    id, company_id, product_key, name, channel, revision, status, created_at, updated_at
                )
                VALUES (
                    v_new_prod_id, v_target_id, v_prod.product_key, v_prod.name, v_prod.channel, 1, v_prod.status, NOW(), NOW()
                );
            ELSE
                UPDATE public.insurance_products
                SET name = v_prod.name,
                    channel = v_prod.channel,
                    status = v_prod.status,
                    updated_at = NOW()
                WHERE id = v_new_prod_id;
            END IF;
            v_prod_map := v_prod_map || jsonb_build_object(v_prod.id::text, v_new_prod_id::text);

            FOR v_tier IN
                SELECT * FROM public.insurance_product_tiers WHERE product_id = v_prod.id AND status = 'active'
            LOOP
                SELECT id INTO v_new_tier_id
                FROM public.insurance_product_tiers
                WHERE product_id = v_new_prod_id AND tier_key = v_tier.tier_key
                LIMIT 1;

                IF v_new_tier_id IS NULL THEN
                    v_new_tier_id := gen_random_uuid();
                    INSERT INTO public.insurance_product_tiers (
                        id, product_id, tier_key, name, sort_order, revision, status, created_at, updated_at
                    )
                    VALUES (
                        v_new_tier_id, v_new_prod_id, v_tier.tier_key, v_tier.name, v_tier.sort_order, 1, v_tier.status, NOW(), NOW()
                    );
                ELSE
                    UPDATE public.insurance_product_tiers
                    SET name = v_tier.name,
                        sort_order = v_tier.sort_order,
                        status = v_tier.status,
                        updated_at = NOW()
                    WHERE id = v_new_tier_id;
                END IF;
                v_tier_map := v_tier_map || jsonb_build_object(v_tier.id::text, v_new_tier_id::text);
            END LOOP;
        END LOOP;

        -- 2c. Sync BenefitCatalogs (non-package-scoped), latest published revision, offerings & packages
        FOR v_cat IN
            SELECT * FROM public.benefit_catalogs
            WHERE company_id = v_am_id AND status IN ('active', 'published') AND package_id IS NULL
        LOOP
            v_new_prod_id := CASE WHEN v_cat.product_id IS NOT NULL THEN (v_prod_map ->> v_cat.product_id::text)::uuid ELSE NULL END;
            v_new_tier_id := CASE WHEN v_cat.tier_id IS NOT NULL THEN (v_tier_map ->> v_cat.tier_id::text)::uuid ELSE NULL END;

            SELECT id INTO v_new_cat_id
            FROM public.benefit_catalogs
            WHERE company_id = v_target_id
              AND COALESCE(product_id, '00000000-0000-0000-0000-000000000000'::uuid) = COALESCE(v_new_prod_id, '00000000-0000-0000-0000-000000000000'::uuid)
              AND COALESCE(tier_id, '00000000-0000-0000-0000-000000000000'::uuid) = COALESCE(v_new_tier_id, '00000000-0000-0000-0000-000000000000'::uuid)
              AND package_id IS NULL
            LIMIT 1;

            IF v_new_cat_id IS NULL THEN
                v_new_cat_id := gen_random_uuid();
                INSERT INTO public.benefit_catalogs (
                    id, company_id, product_id, tier_id, package_id, segment_id,
                    vehicle_category_id, vehicle_subcategory_id, coverage_type_id, engine_type,
                    name, revision, status, created_at, updated_at
                )
                VALUES (
                    v_new_cat_id,
                    v_target_id,
                    v_new_prod_id,
                    v_new_tier_id,
                    NULL,
                    v_cat.segment_id,
                    v_cat.vehicle_category_id,
                    v_cat.vehicle_subcategory_id,
                    v_cat.coverage_type_id,
                    v_cat.engine_type,
                    v_cat.name,
                    1,
                    v_cat.status,
                    NOW(),
                    NOW()
                );
            ELSE
                UPDATE public.benefit_catalogs
                SET segment_id = v_cat.segment_id,
                    vehicle_category_id = v_cat.vehicle_category_id,
                    vehicle_subcategory_id = v_cat.vehicle_subcategory_id,
                    coverage_type_id = v_cat.coverage_type_id,
                    engine_type = v_cat.engine_type,
                    name = v_cat.name,
                    status = v_cat.status,
                    updated_at = NOW()
                WHERE id = v_new_cat_id;
            END IF;

            SELECT * INTO v_src_rev
            FROM public.benefit_catalog_revisions
            WHERE catalog_id = v_cat.id
              AND state = 'published'
              AND COALESCE(is_archived, FALSE) = FALSE
            ORDER BY revision_number DESC
            LIMIT 1;

            IF v_src_rev.id IS NOT NULL THEN
                SELECT id INTO v_tgt_rev_id
                FROM public.benefit_catalog_revisions
                WHERE catalog_id = v_new_cat_id
                  AND state = 'published'
                  AND COALESCE(is_archived, FALSE) = FALSE
                ORDER BY revision_number DESC
                LIMIT 1;

                IF v_tgt_rev_id IS NULL THEN
                    v_tgt_rev_id := gen_random_uuid();
                    INSERT INTO public.benefit_catalog_revisions (
                        id, catalog_id, revision_number, state, source_document_ids,
                        content_hash, published_at, created_at, updated_at, is_archived
                    )
                    VALUES (
                        v_tgt_rev_id, v_new_cat_id, 1, 'published', v_src_rev.source_document_ids,
                        v_src_rev.content_hash, NOW(), NOW(), NOW(), FALSE
                    );
                END IF;

                v_off_map := '{}'::jsonb;
                FOR v_off IN
                    SELECT * FROM public.catalog_offerings WHERE catalog_revision_id = v_src_rev.id
                LOOP
                    INSERT INTO public.catalog_offerings (
                        id, catalog_revision_id, offering_key, concept_id, offering_kind,
                        applies_to_type, applies_to_id, role, label_override, description_override,
                        typed_value, display_value, optional_price, source_citation,
                        source_aliases, presentation_facet_ids, sort_order, status, created_at, updated_at
                    )
                    VALUES (
                        gen_random_uuid(),
                        v_tgt_rev_id,
                        v_off.offering_key,
                        v_off.concept_id,
                        v_off.offering_kind,
                        v_off.applies_to_type,
                        v_off.applies_to_id,
                        v_off.role,
                        v_off.label_override,
                        v_off.description_override,
                        v_off.typed_value,
                        v_off.display_value,
                        v_off.optional_price,
                        v_off.source_citation,
                        v_off.source_aliases,
                        v_off.presentation_facet_ids,
                        v_off.sort_order,
                        v_off.status,
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (catalog_revision_id, offering_key) DO UPDATE SET
                        concept_id = EXCLUDED.concept_id,
                        offering_kind = EXCLUDED.offering_kind,
                        applies_to_type = EXCLUDED.applies_to_type,
                        applies_to_id = EXCLUDED.applies_to_id,
                        role = EXCLUDED.role,
                        label_override = EXCLUDED.label_override,
                        description_override = EXCLUDED.description_override,
                        typed_value = EXCLUDED.typed_value,
                        display_value = EXCLUDED.display_value,
                        optional_price = EXCLUDED.optional_price,
                        source_citation = EXCLUDED.source_citation,
                        source_aliases = EXCLUDED.source_aliases,
                        presentation_facet_ids = EXCLUDED.presentation_facet_ids,
                        sort_order = EXCLUDED.sort_order,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    RETURNING id INTO v_new_off_id;

                    v_off_map := v_off_map || jsonb_build_object(v_off.id::text, v_new_off_id::text);
                END LOOP;

                FOR v_pkg IN
                    SELECT * FROM public.benefit_packages WHERE catalog_revision_id = v_src_rev.id
                LOOP
                    INSERT INTO public.benefit_packages (
                        id, catalog_revision_id, package_key, name, package_kind, sort_order, revision, status, created_at, updated_at
                    )
                    VALUES (
                        gen_random_uuid(),
                        v_tgt_rev_id,
                        v_pkg.package_key,
                        v_pkg.name,
                        v_pkg.package_kind,
                        v_pkg.sort_order,
                        1,
                        v_pkg.status,
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (catalog_revision_id, package_key) DO UPDATE SET
                        name = EXCLUDED.name,
                        package_kind = EXCLUDED.package_kind,
                        sort_order = EXCLUDED.sort_order,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    RETURNING id INTO v_new_pkg_id;

                    v_pkg_map := v_pkg_map || jsonb_build_object(v_pkg.id::text, v_new_pkg_id::text);

                    FOR v_plan IN
                        SELECT * FROM public.benefit_package_plans WHERE package_id = v_pkg.id
                    LOOP
                        INSERT INTO public.benefit_package_plans (
                            id, package_id, plan_key, name, sort_order, status, created_at, updated_at
                        )
                        VALUES (
                            gen_random_uuid(), v_new_pkg_id, v_plan.plan_key, v_plan.name, v_plan.sort_order, v_plan.status, NOW(), NOW()
                        )
                        ON CONFLICT (package_id, plan_key) DO UPDATE SET
                            name = EXCLUDED.name,
                            sort_order = EXCLUDED.sort_order,
                            status = EXCLUDED.status,
                            updated_at = NOW()
                        RETURNING id INTO v_new_plan_id;

                        INSERT INTO public.benefit_package_plan_items (
                            id, plan_id, offering_id, typed_value_override, sort_order, created_at, updated_at
                        )
                        SELECT
                            gen_random_uuid(),
                            v_new_plan_id,
                            (v_off_map ->> bpi.offering_id::text)::uuid,
                            bpi.typed_value_override,
                            bpi.sort_order,
                            NOW(),
                            NOW()
                        FROM public.benefit_package_plan_items bpi
                        WHERE bpi.plan_id = v_plan.id
                          AND (v_off_map ->> bpi.offering_id::text) IS NOT NULL
                        ON CONFLICT (plan_id, offering_id) DO UPDATE SET
                            typed_value_override = EXCLUDED.typed_value_override,
                            sort_order = EXCLUDED.sort_order,
                            updated_at = NOW();
                    END LOOP;
                END LOOP;
            END IF;
        END LOOP;

        -- 2d. Sync CompanyBenefitConfig verbatim
        INSERT INTO public.company_benefit_configs (
            id, company_id, profile_id, concept_id, is_enabled, baseline_description, baseline_cost, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            v_target_id,
            cbc.profile_id,
            cbc.concept_id,
            cbc.is_enabled,
            cbc.baseline_description,
            cbc.baseline_cost,
            NOW(),
            NOW()
        FROM public.company_benefit_configs cbc
        WHERE cbc.company_id = v_am_id
        ON CONFLICT (company_id, profile_id, concept_id) DO UPDATE SET
            is_enabled = EXCLUDED.is_enabled,
            baseline_description = EXCLUDED.baseline_description,
            baseline_cost = EXCLUDED.baseline_cost,
            updated_at = NOW();

        -- 2e. Retire legacy 1-to-1 towing conditions on target (parity with 090) and sync active conditions verbatim
        IF v_towing_cid IS NOT NULL THEN
            UPDATE public.company_benefit_conditions
            SET is_active = FALSE,
                updated_at = NOW()
            WHERE company_id = v_target_id
              AND target_concept_id = v_towing_cid
              AND is_active = TRUE;
        END IF;

        INSERT INTO public.company_benefit_conditions (
            id, company_id, profile_id, name, trigger_concept_id, trigger_plan_filter,
            target_concept_id, action_type, replacement_description, replacement_title,
            replacement_value, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            v_target_id,
            cond.profile_id,
            cond.name,
            cond.trigger_concept_id,
            cond.trigger_plan_filter,
            cond.target_concept_id,
            cond.action_type,
            cond.replacement_description,
            cond.replacement_title,
            cond.replacement_value,
            cond.is_active,
            NOW(),
            NOW()
        FROM public.company_benefit_conditions cond
        WHERE cond.company_id = v_am_id
          AND cond.is_active = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM public.company_benefit_conditions tc
              WHERE tc.company_id = v_target_id
                AND tc.trigger_concept_id = cond.trigger_concept_id
                AND tc.target_concept_id = cond.target_concept_id
                AND COALESCE(tc.trigger_plan_filter, '') = COALESCE(cond.trigger_plan_filter, '')
                AND COALESCE(tc.profile_id, '00000000-0000-0000-0000-000000000000'::uuid) = COALESCE(cond.profile_id, '00000000-0000-0000-0000-000000000000'::uuid)
          );

        -- 2f. Clone Bundled Benefits ("Mystery Box"), Tiers & Effects verbatim
        FOR v_bundle IN
            SELECT * FROM public.company_benefit_bundles
            WHERE company_id = v_am_id AND is_active = TRUE
        LOOP
            IF v_bundle.profile_id IS NOT NULL THEN
                INSERT INTO public.company_benefit_bundles (
                    id, company_id, profile_id, bundle_key, name, primary_concept_id,
                    trigger_concept_ids, match_aliases, catalog_scope, force_box2,
                    has_plan_tiers, is_active, sort_order, created_at, updated_at
                )
                VALUES (
                    md5('bundle:091:' || v_target_id::text || ':' || v_bundle.profile_id::text || ':' || v_bundle.bundle_key)::uuid,
                    v_target_id,
                    v_bundle.profile_id,
                    v_bundle.bundle_key,
                    v_bundle.name,
                    v_bundle.primary_concept_id,
                    v_bundle.trigger_concept_ids,
                    v_bundle.match_aliases,
                    v_bundle.catalog_scope,
                    v_bundle.force_box2,
                    v_bundle.has_plan_tiers,
                    v_bundle.is_active,
                    v_bundle.sort_order,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (company_id, profile_id, bundle_key) WHERE profile_id IS NOT NULL DO UPDATE SET
                    name = EXCLUDED.name,
                    primary_concept_id = EXCLUDED.primary_concept_id,
                    trigger_concept_ids = EXCLUDED.trigger_concept_ids,
                    match_aliases = EXCLUDED.match_aliases,
                    catalog_scope = EXCLUDED.catalog_scope,
                    force_box2 = EXCLUDED.force_box2,
                    has_plan_tiers = EXCLUDED.has_plan_tiers,
                    is_active = EXCLUDED.is_active,
                    sort_order = EXCLUDED.sort_order,
                    updated_at = NOW()
                RETURNING id INTO v_new_bundle_id;
            ELSE
                INSERT INTO public.company_benefit_bundles (
                    id, company_id, profile_id, bundle_key, name, primary_concept_id,
                    trigger_concept_ids, match_aliases, catalog_scope, force_box2,
                    has_plan_tiers, is_active, sort_order, created_at, updated_at
                )
                VALUES (
                    md5('bundle:091:' || v_target_id::text || ':global:' || v_bundle.bundle_key)::uuid,
                    v_target_id,
                    NULL,
                    v_bundle.bundle_key,
                    v_bundle.name,
                    v_bundle.primary_concept_id,
                    v_bundle.trigger_concept_ids,
                    v_bundle.match_aliases,
                    v_bundle.catalog_scope,
                    v_bundle.force_box2,
                    v_bundle.has_plan_tiers,
                    v_bundle.is_active,
                    v_bundle.sort_order,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (company_id, bundle_key) WHERE profile_id IS NULL DO UPDATE SET
                    name = EXCLUDED.name,
                    primary_concept_id = EXCLUDED.primary_concept_id,
                    trigger_concept_ids = EXCLUDED.trigger_concept_ids,
                    match_aliases = EXCLUDED.match_aliases,
                    catalog_scope = EXCLUDED.catalog_scope,
                    force_box2 = EXCLUDED.force_box2,
                    has_plan_tiers = EXCLUDED.has_plan_tiers,
                    is_active = EXCLUDED.is_active,
                    sort_order = EXCLUDED.sort_order,
                    updated_at = NOW()
                RETURNING id INTO v_new_bundle_id;
            END IF;

            FOR v_btier IN
                SELECT * FROM public.company_benefit_bundle_tiers WHERE bundle_id = v_bundle.id
            LOOP
                INSERT INTO public.company_benefit_bundle_tiers (
                    id, bundle_id, tier_key, label, match_tokens, is_default_fallback, sort_order, created_at, updated_at
                )
                VALUES (
                    md5('btier:091:' || v_new_bundle_id::text || ':' || v_btier.tier_key)::uuid,
                    v_new_bundle_id,
                    v_btier.tier_key,
                    v_btier.label,
                    v_btier.match_tokens,
                    v_btier.is_default_fallback,
                    v_btier.sort_order,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (bundle_id, tier_key) DO UPDATE SET
                    label = EXCLUDED.label,
                    match_tokens = EXCLUDED.match_tokens,
                    is_default_fallback = EXCLUDED.is_default_fallback,
                    sort_order = EXCLUDED.sort_order,
                    updated_at = NOW()
                RETURNING id INTO v_new_btier_id;

                DELETE FROM public.company_benefit_bundle_effects WHERE tier_id = v_new_btier_id;

                INSERT INTO public.company_benefit_bundle_effects (
                    id, tier_id, target_concept_id, effect_type, display_title, display_value,
                    display_description, icon_hint, comparison_value, sort_order, created_at, updated_at
                )
                SELECT
                    md5('beff:091:' || v_new_btier_id::text || ':' || eff.target_concept_id::text || ':' || eff.effect_type || ':' || eff.sort_order::text)::uuid,
                    v_new_btier_id,
                    eff.target_concept_id,
                    eff.effect_type,
                    eff.display_title,
                    eff.display_value,
                    eff.display_description,
                    eff.icon_hint,
                    eff.comparison_value,
                    eff.sort_order,
                    NOW(),
                    NOW()
                FROM public.company_benefit_bundle_effects eff
                WHERE eff.tier_id = v_btier.id;
            END LOOP;
        END LOOP;
    END LOOP;
END $$;

COMMIT;
