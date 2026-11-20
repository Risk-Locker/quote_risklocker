-- 086_mmip_kurnia_catalogs_and_design2_templates.sql
-- 1. Seed MMIP (Malaysian Motor Insurance Pool) as a strict Third Party Only (TPO) insurer with only 2 statutory TP benefits
-- 2. Update Kurnia (by Liberty General Insurance Berhad) detection aliases, template category, policy_rules, and deep-clone AmAssurance catalogs/configs/conditions
-- 3. Seed Half-A4 page profile (794x560) and 3 new Design 2 master templates (English-Only A4, Half-Page TPO Bilingual, Half-Page TPO English-Only)

BEGIN;

-- ============================================================================
-- 1. Seed MMIP (Malaysian Motor Insurance Pool) & Strict TPO Catalog
-- ============================================================================

INSERT INTO public.insurance_companies (
    id,
    slug,
    revision,
    name,
    category,
    source_template_category,
    detection_phrases,
    policy_rules,
    status,
    created_at,
    updated_at
)
SELECT
    'c0000000-0000-4000-8000-000000000086'::uuid,
    'mmip',
    1,
    'MMIP',
    'Motor',
    'Other / Unknown',
    '["MMIP", "Malaysian Motor Insurance Pool", "Malaysia Motor Insurance Pool", "Motor Insurance Pool"]'::jsonb,
    '{
      "allowed_coverage_types": ["third_party"],
      "betterment": {"auto_waive_without_peril": false, "max_waiver_years": 0, "default_display": "N/A (Third Party)"},
      "towing": {"metric": "none", "base_limit": "No towing"}
    }'::jsonb,
    'active',
    NOW(),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM public.insurance_companies
    WHERE slug = 'mmip'
       OR LOWER(name) IN ('mmip', 'malaysian motor insurance pool', 'malaysia motor insurance pool')
);

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

-- Ensure the two statutory Third Party BenefitConcepts exist
INSERT INTO public.benefit_concepts (
    id,
    concept_key,
    label,
    value_schema,
    display_template,
    required_variables,
    optional_variables,
    validation_rules,
    description,
    sort_order,
    revision,
    status,
    created_at,
    updated_at
)
VALUES
(
    'c1111111-0000-4000-8000-000000000091'::uuid,
    'third-party-bodily-injury',
    'Third Party Bodily Injury',
    '{"category": "base", "variants": []}'::jsonb,
    '{label}',
    '[]'::jsonb,
    '[]'::jsonb,
    '{}'::jsonb,
    'Covers legal liability for death or bodily injury to any third party caused by your vehicle.',
    1,
    1,
    'active',
    NOW(),
    NOW()
),
(
    'c1111111-0000-4000-8000-000000000092'::uuid,
    'third-party-property-damage',
    'Third Party Property Damage',
    '{"category": "base", "variants": []}'::jsonb,
    '{label}',
    '[]'::jsonb,
    '[]'::jsonb,
    '{}'::jsonb,
    'Covers legal liability for accidental loss or damage to third-party property up to RM 3,000,000.',
    2,
    1,
    'active',
    NOW(),
    NOW()
)
ON CONFLICT (concept_key) DO NOTHING;

-- Seed MMIP Third Party Only Product, Tier, Catalog, Revision, and STRICTLY 2 Base Offerings
DO $$
DECLARE
    v_mmip_id UUID;
    v_prod_id UUID;
    v_tier_id UUID;
    v_cat_id UUID;
    v_rev_id UUID;
    v_tpbi_id UUID;
    v_tppd_id UUID;
    v_tpo_cov_id UUID := 'd1111111-0000-4000-8000-000000000003'::uuid;
BEGIN
    SELECT id INTO v_mmip_id FROM public.insurance_companies WHERE slug = 'mmip' LIMIT 1;
    IF v_mmip_id IS NULL THEN
        RETURN;
    END IF;

    SELECT id INTO v_tpbi_id FROM public.benefit_concepts WHERE concept_key = 'third-party-bodily-injury' LIMIT 1;
    SELECT id INTO v_tppd_id FROM public.benefit_concepts WHERE concept_key = 'third-party-property-damage' LIMIT 1;

    -- Product
    SELECT id INTO v_prod_id
    FROM public.insurance_products
    WHERE company_id = v_mmip_id AND product_key = 'mmip-third-party-only'
    LIMIT 1;

    IF v_prod_id IS NULL THEN
        v_prod_id := gen_random_uuid();
        INSERT INTO public.insurance_products (id, company_id, product_key, name, revision, status, created_at, updated_at)
        VALUES (v_prod_id, v_mmip_id, 'mmip-third-party-only', 'Third Party Only (MMIP)', 1, 'active', NOW(), NOW());
    END IF;

    -- Tier
    SELECT id INTO v_tier_id
    FROM public.insurance_product_tiers
    WHERE product_id = v_prod_id AND tier_key = 'standard'
    LIMIT 1;

    IF v_tier_id IS NULL THEN
        v_tier_id := gen_random_uuid();
        INSERT INTO public.insurance_product_tiers (id, product_id, tier_key, name, sort_order, revision, status, created_at, updated_at)
        VALUES (v_tier_id, v_prod_id, 'standard', 'Standard', 1, 1, 'active', NOW(), NOW());
    END IF;

    -- Catalog
    SELECT id INTO v_cat_id
    FROM public.benefit_catalogs
    WHERE company_id = v_mmip_id
      AND COALESCE(product_id, '00000000-0000-0000-0000-000000000000'::uuid) = v_prod_id
      AND COALESCE(tier_id, '00000000-0000-0000-0000-000000000000'::uuid) = v_tier_id
    LIMIT 1;

    IF v_cat_id IS NULL THEN
        v_cat_id := gen_random_uuid();
        INSERT INTO public.benefit_catalogs (
            id, company_id, product_id, tier_id, coverage_type_id, engine_type,
            name, revision, status, created_at, updated_at
        )
        VALUES (
            v_cat_id, v_mmip_id, v_prod_id, v_tier_id, v_tpo_cov_id, 'ice',
            'MMIP Third Party Only', 1, 'published', NOW(), NOW()
        );
    ELSE
        UPDATE public.benefit_catalogs
        SET coverage_type_id = v_tpo_cov_id, status = 'published', updated_at = NOW()
        WHERE id = v_cat_id;
    END IF;

    -- Published Revision
    SELECT id INTO v_rev_id
    FROM public.benefit_catalog_revisions
    WHERE catalog_id = v_cat_id AND state = 'published'
    ORDER BY revision_number DESC
    LIMIT 1;

    IF v_rev_id IS NULL THEN
        v_rev_id := gen_random_uuid();
        INSERT INTO public.benefit_catalog_revisions (
            id, catalog_id, revision_number, state, source_document_ids,
            content_hash, published_at, created_at, updated_at
        )
        VALUES (
            v_rev_id, v_cat_id, 1, 'published', '[]'::jsonb,
            repeat('0', 64), NOW(), NOW(), NOW()
        );
    END IF;

    -- Ensure ONLY the 2 statutory TPO base offerings exist (no addons, no own damage, no towing)
    UPDATE public.catalog_offerings
    SET status = 'inactive', updated_at = NOW()
    WHERE catalog_revision_id = v_rev_id
      AND offering_key NOT IN ('base:third-party-bodily-injury', 'base:third-party-property-damage');

    IF v_tpbi_id IS NOT NULL THEN
        INSERT INTO public.catalog_offerings (
            id, catalog_revision_id, offering_key, concept_id, offering_kind, role,
            label_override, description_override, typed_value, display_value,
            sort_order, status, created_at, updated_at
        )
        VALUES (
            gen_random_uuid(), v_rev_id, 'base:third-party-bodily-injury', v_tpbi_id, 'base', 'included',
            'Third Party Bodily Injury',
            'Covers legal liability for death or bodily injury to any third party caused by your vehicle.',
            NULL, NULL, 1, 'active', NOW(), NOW()
        )
        ON CONFLICT (catalog_revision_id, offering_key) DO UPDATE SET
            status = 'active',
            offering_kind = 'base',
            role = 'included',
            updated_at = NOW();
    END IF;

    IF v_tppd_id IS NOT NULL THEN
        INSERT INTO public.catalog_offerings (
            id, catalog_revision_id, offering_key, concept_id, offering_kind, role,
            label_override, description_override, typed_value, display_value,
            sort_order, status, created_at, updated_at
        )
        VALUES (
            gen_random_uuid(), v_rev_id, 'base:third-party-property-damage', v_tppd_id, 'base', 'included',
            'Third Party Property Damage',
            'Covers legal liability for accidental loss or damage to third-party property up to RM 3,000,000.',
            NULL, NULL, 2, 'active', NOW(), NOW()
        )
        ON CONFLICT (catalog_revision_id, offering_key) DO UPDATE SET
            status = 'active',
            offering_kind = 'base',
            role = 'included',
            updated_at = NOW();
    END IF;
END $$;


-- ============================================================================
-- 2. Kurnia Full Alignment & Deep Clone of AmAssurance Catalogs/Configs/Conditions
-- ============================================================================

UPDATE public.insurance_companies
SET
    source_template_category = 'Amgen / AmAssurance / Kurnia-style',
    detection_phrases = '["Kurnia", "Kurnia Insurans", "Kurnia Insurance", "Kurnia Insurans (Malaysia) Berhad", "www.kurnia.com", "kurnia.com", "Kurnia One Touch", "Kurnia Auto Assist"]'::jsonb,
    policy_rules = '{
      "betterment": {"auto_waive_without_peril": false, "max_waiver_years": 15, "default_display": "Up to 15 Years"},
      "towing": {"metric": "km", "base_limit": "100 km", "lite_limit": "50 km", "premier_limit": "365 km", "rm_fallback": "RM 200", "unlimited_triggers": ["auto assist plus", "auto assist premier", "kurnia auto assist", "amdrive plus"]}
    }'::jsonb,
    status = 'active',
    updated_at = NOW()
WHERE slug = 'kurnia';

DO $$
DECLARE
    v_am_id UUID;
    v_kurnia_id UUID;
    v_prod RECORD;
    v_new_prod_id UUID;
    v_tier RECORD;
    v_new_tier_id UUID;
    v_cat RECORD;
    v_new_cat_id UUID;
    v_src_rev RECORD;
    v_new_rev_id UUID;
    v_pkg RECORD;
    v_new_pkg_id UUID;
    v_plan RECORD;
    v_new_plan_id UUID;
    v_off RECORD;
    v_new_off_id UUID;
    v_prod_map JSONB := '{}'::jsonb;
    v_tier_map JSONB := '{}'::jsonb;
    v_pkg_map JSONB := '{}'::jsonb;
    v_off_map JSONB := '{}'::jsonb;
BEGIN
    SELECT id INTO v_am_id FROM public.insurance_companies WHERE slug = 'amassurance' LIMIT 1;
    IF v_am_id IS NULL THEN
        SELECT id INTO v_am_id FROM public.insurance_companies WHERE LOWER(name) LIKE '%amassurance%' OR LOWER(name) LIKE '%amgen%' LIMIT 1;
    END IF;
    SELECT id INTO v_kurnia_id FROM public.insurance_companies WHERE slug = 'kurnia' LIMIT 1;

    IF v_am_id IS NULL OR v_kurnia_id IS NULL THEN
        RETURN;
    END IF;

    -- Clone products
    FOR v_prod IN
        SELECT * FROM public.insurance_products WHERE company_id = v_am_id AND status = 'active'
    LOOP
        SELECT id INTO v_new_prod_id
        FROM public.insurance_products
        WHERE company_id = v_kurnia_id AND product_key = v_prod.product_key
        LIMIT 1;

        IF v_new_prod_id IS NULL THEN
            v_new_prod_id := gen_random_uuid();
            INSERT INTO public.insurance_products (
                id, company_id, product_key, name, channel, revision, status, created_at, updated_at
            )
            VALUES (
                v_new_prod_id,
                v_kurnia_id,
                v_prod.product_key,
                REPLACE(REPLACE(REPLACE(v_prod.name, 'AmAssurance', 'Kurnia'), 'amDrive', 'Kurnia Auto Assist'), 'auto365', 'Kurnia Auto365'),
                v_prod.channel,
                1,
                v_prod.status,
                NOW(),
                NOW()
            );
        END IF;
        v_prod_map := v_prod_map || jsonb_build_object(v_prod.id::text, v_new_prod_id::text);

        -- Clone product tiers
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
            END IF;
            v_tier_map := v_tier_map || jsonb_build_object(v_tier.id::text, v_new_tier_id::text);
        END LOOP;
    END LOOP;

    -- Clone non-package-scoped BenefitCatalogs first, then package-scoped BenefitCatalogs
    FOR v_cat IN
        SELECT * FROM public.benefit_catalogs
        WHERE company_id = v_am_id AND status IN ('active', 'published') AND package_id IS NULL
    LOOP
        v_new_prod_id := CASE WHEN v_cat.product_id IS NOT NULL THEN (v_prod_map ->> v_cat.product_id::text)::uuid ELSE NULL END;
        v_new_tier_id := CASE WHEN v_cat.tier_id IS NOT NULL THEN (v_tier_map ->> v_cat.tier_id::text)::uuid ELSE NULL END;

        SELECT id INTO v_new_cat_id
        FROM public.benefit_catalogs
        WHERE company_id = v_kurnia_id
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
                v_kurnia_id,
                v_new_prod_id,
                v_new_tier_id,
                NULL,
                v_cat.segment_id,
                v_cat.vehicle_category_id,
                v_cat.vehicle_subcategory_id,
                v_cat.coverage_type_id,
                v_cat.engine_type,
                REPLACE(REPLACE(REPLACE(v_cat.name, 'AmAssurance', 'Kurnia'), 'amDrive', 'Kurnia Auto Assist'), 'auto365', 'Kurnia Auto365'),
                1,
                v_cat.status,
                NOW(),
                NOW()
            );

            SELECT * INTO v_src_rev
            FROM public.benefit_catalog_revisions
            WHERE catalog_id = v_cat.id AND state = 'published'
            ORDER BY revision_number DESC
            LIMIT 1;

            IF v_src_rev.id IS NOT NULL THEN
                v_new_rev_id := gen_random_uuid();
                INSERT INTO public.benefit_catalog_revisions (
                    id, catalog_id, revision_number, state, source_document_ids,
                    content_hash, published_at, created_at, updated_at
                )
                VALUES (
                    v_new_rev_id, v_new_cat_id, 1, 'published', v_src_rev.source_document_ids,
                    v_src_rev.content_hash, NOW(), NOW(), NOW()
                );

                v_off_map := '{}'::jsonb;
                FOR v_off IN
                    SELECT * FROM public.catalog_offerings WHERE catalog_revision_id = v_src_rev.id
                LOOP
                    v_new_off_id := gen_random_uuid();
                    INSERT INTO public.catalog_offerings (
                        id, catalog_revision_id, offering_key, concept_id, offering_kind,
                        applies_to_type, applies_to_id, role, label_override, description_override,
                        typed_value, display_value, optional_price, source_citation,
                        source_aliases, presentation_facet_ids, sort_order, status, created_at, updated_at
                    )
                    VALUES (
                        v_new_off_id,
                        v_new_rev_id,
                        v_off.offering_key,
                        v_off.concept_id,
                        v_off.offering_kind,
                        v_off.applies_to_type,
                        v_off.applies_to_id,
                        v_off.role,
                        REPLACE(REPLACE(v_off.label_override, 'AmAssurance', 'Kurnia'), 'amDrive', 'Kurnia Auto Assist'),
                        REPLACE(REPLACE(v_off.description_override, 'AmAssurance', 'Kurnia'), 'amDrive', 'Kurnia Auto Assist'),
                        v_off.typed_value,
                        v_off.display_value,
                        v_off.optional_price,
                        v_off.source_citation,
                        '["Kurnia", "Kurnia Insurans", "Kurnia Auto Assist"]'::jsonb,
                        v_off.presentation_facet_ids,
                        v_off.sort_order,
                        v_off.status,
                        NOW(),
                        NOW()
                    );
                    v_off_map := v_off_map || jsonb_build_object(v_off.id::text, v_new_off_id::text);
                END LOOP;

                -- Clone packages & plans inside this catalog revision
                FOR v_pkg IN
                    SELECT * FROM public.benefit_packages WHERE catalog_revision_id = v_src_rev.id
                LOOP
                    v_new_pkg_id := gen_random_uuid();
                    INSERT INTO public.benefit_packages (
                        id, catalog_revision_id, package_key, name, package_kind, sort_order, revision, status, created_at, updated_at
                    )
                    VALUES (
                        v_new_pkg_id,
                        v_new_rev_id,
                        v_pkg.package_key,
                        REPLACE(REPLACE(REPLACE(v_pkg.name, 'AmAssurance', 'Kurnia'), 'amDrive', 'Kurnia Auto Assist'), 'auto365', 'Kurnia Auto365'),
                        v_pkg.package_kind,
                        v_pkg.sort_order,
                        1,
                        v_pkg.status,
                        NOW(),
                        NOW()
                    );
                    v_pkg_map := v_pkg_map || jsonb_build_object(v_pkg.id::text, v_new_pkg_id::text);

                    FOR v_plan IN
                        SELECT * FROM public.benefit_package_plans WHERE package_id = v_pkg.id
                    LOOP
                        v_new_plan_id := gen_random_uuid();
                        INSERT INTO public.benefit_package_plans (
                            id, package_id, plan_key, name, sort_order, status, created_at, updated_at
                        )
                        VALUES (
                            v_new_plan_id, v_new_pkg_id, v_plan.plan_key, v_plan.name, v_plan.sort_order, v_plan.status, NOW(), NOW()
                        );

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
                          AND (v_off_map ->> bpi.offering_id::text) IS NOT NULL;
                    END LOOP;
                END LOOP;
            END IF;
        END IF;
    END LOOP;

    -- Clone CompanyBenefitConfig rows (idempotent)
    INSERT INTO public.company_benefit_configs (
        id, company_id, profile_id, concept_id, is_enabled, baseline_description, baseline_cost, created_at, updated_at
    )
    SELECT
        gen_random_uuid(),
        v_kurnia_id,
        cbc.profile_id,
        cbc.concept_id,
        cbc.is_enabled,
        REPLACE(REPLACE(cbc.baseline_description, 'AmAssurance', 'Kurnia'), 'amDrive', 'Kurnia Auto Assist'),
        cbc.baseline_cost,
        NOW(),
        NOW()
    FROM public.company_benefit_configs cbc
    WHERE cbc.company_id = v_am_id
      AND NOT EXISTS (
          SELECT 1 FROM public.company_benefit_configs k
          WHERE k.company_id = v_kurnia_id
            AND k.concept_id = cbc.concept_id
            AND COALESCE(k.profile_id, '00000000-0000-0000-0000-000000000000'::uuid) = COALESCE(cbc.profile_id, '00000000-0000-0000-0000-000000000000'::uuid)
      );

    -- Clone CompanyBenefitCondition rows (idempotent)
    INSERT INTO public.company_benefit_conditions (
        id, company_id, profile_id, name, trigger_concept_id, trigger_plan_filter,
        target_concept_id, action_type, replacement_description, replacement_title,
        replacement_value, is_active, created_at, updated_at
    )
    SELECT
        gen_random_uuid(),
        v_kurnia_id,
        cond.profile_id,
        REPLACE(REPLACE(cond.name, 'AmAssurance', 'Kurnia'), 'amDrive', 'Kurnia Auto Assist'),
        cond.trigger_concept_id,
        cond.trigger_plan_filter,
        cond.target_concept_id,
        cond.action_type,
        REPLACE(REPLACE(cond.replacement_description, 'AmAssurance', 'Kurnia'), 'amDrive', 'Kurnia Auto Assist'),
        REPLACE(REPLACE(cond.replacement_title, 'AmAssurance', 'Kurnia'), 'amDrive', 'Kurnia Auto Assist'),
        cond.replacement_value,
        cond.is_active,
        NOW(),
        NOW()
    FROM public.company_benefit_conditions cond
    WHERE cond.company_id = v_am_id
      AND NOT EXISTS (
          SELECT 1 FROM public.company_benefit_conditions kc
          WHERE kc.company_id = v_kurnia_id
            AND kc.trigger_concept_id = cond.trigger_concept_id
            AND kc.target_concept_id = cond.target_concept_id
            AND COALESCE(kc.profile_id, '00000000-0000-0000-0000-000000000000'::uuid) = COALESCE(cond.profile_id, '00000000-0000-0000-0000-000000000000'::uuid)
      );
END $$;


-- ============================================================================
-- 3. Half-A4 Compact Page Profile (794 x 560) for TPO Templates
-- ============================================================================

INSERT INTO public.template_page_profiles (
    profile_key,
    name,
    width,
    height,
    unit,
    safe_margins,
    bleed,
    background_behavior,
    revision,
    status
)
VALUES (
    'half_a4',
    'Half A4 (Compact TPO)',
    794,
    580,
    'px',
    '{"top":16,"right":24,"bottom":16,"left":24}'::jsonb,
    '{}'::jsonb,
    'clip',
    1,
    'active'
)
ON CONFLICT (profile_key) DO UPDATE SET
    height = 580,
    updated_at = NOW();

-- ============================================================================
-- 4. Seed 3 New Design 2 Master Templates (English-Only A4 & Half-Page TPO Variants)
-- ============================================================================

DO $$
DECLARE
    v_a4_id UUID;
    v_half_id UUID;
    v_base_cfg JSONB;
    v_spec RECORD;
    v_cfg JSONB;
    v_hash CHAR(64);
    v_rev_exists BOOLEAN;
BEGIN
    SELECT id INTO v_a4_id FROM public.template_page_profiles WHERE profile_key = 'a4' LIMIT 1;
    SELECT id INTO v_half_id FROM public.template_page_profiles WHERE profile_key = 'half_a4' LIMIT 1;
    IF v_a4_id IS NULL OR v_half_id IS NULL THEN
        RETURN;
    END IF;

    SELECT fixed_fields INTO v_base_cfg
    FROM public.output_template_configs
    WHERE id = 'b78e2024-0002-4000-8000-000000000002'::uuid
    LIMIT 1;

    IF v_base_cfg IS NULL THEN
        v_base_cfg := '{
            "version": 7,
            "layout_engine": "design2",
            "is_default": false,
            "agency_account_name": "RISKLOCKER SDN. BHD.",
            "bank_name": "Hong Leong Bank",
            "bank_account_no": "12300318500",
            "locked": false,
            "assets": {
                "risklocker_logo": "e9685e1f-ac95-410c-a2e9-eccb7ca35d5f",
                "bank_logo": "2168eaee-3e56-4903-8c4f-841f01ff2407",
                "bank_qr": "c4003185-0000-4000-8000-000000000001"
            },
            "canvas": {"width": 794, "height": 1123, "elements": []}
        }'::jsonb;
    END IF;

    FOR v_spec IN
        SELECT * FROM (VALUES
            (
                'b78e2024-0002-4000-8000-000000000003'::uuid,
                'motor_modern_design_2_en',
                'Design 2 (English Only)',
                'en',
                false,
                v_a4_id,
                'a4',
                'A4',
                1123,
                'e71503d244ae19456da9184ee9c8ce373d66444a2217a604209af91206fc016a'
            ),
            (
                'b78e2024-0002-4000-8000-000000000004'::uuid,
                'motor_modern_design_2_tpo_compact',
                'Design 2 (TPO Half-Page - Bilingual)',
                'bilingual',
                true,
                v_half_id,
                'half_a4',
                'Half A4 (Compact TPO)',
                580,
                'a4a2aa3ff801eb9d87cb057f5e0bee86740c1d52326df9cce7b308dc96b67a41'
            ),
            (
                'b78e2024-0002-4000-8000-000000000005'::uuid,
                'motor_modern_design_2_tpo_compact_en',
                'Design 2 (TPO Half-Page - English Only)',
                'en',
                true,
                v_half_id,
                'half_a4',
                'Half A4 (Compact TPO)',
                580,
                '4eb85741d43d283ecfcd84435e7c3ef0415f2d93d71bee4d44d19529c8b8d508'
            )
        ) AS t(tid, tkey, tname, lang_mode, hide_addons, pid, pkey, pname, ph, thash)
    LOOP
        v_cfg := v_base_cfg || jsonb_build_object(
            'version', 7,
            'template_name', v_spec.tname,
            'v7_master_key', v_spec.tkey,
            'template_key', v_spec.tkey,
            'layout_engine', 'design2',
            'language_mode', v_spec.lang_mode,
            'hide_addon_upgrades', v_spec.hide_addons,
            'is_default', false,
            'page_profile', jsonb_build_object(
                'profile_key', v_spec.pkey,
                'name', v_spec.pname,
                'width', 794,
                'height', v_spec.ph,
                'unit', 'px',
                'safe_margins', jsonb_build_object('top', CASE WHEN v_spec.hide_addons THEN 16 ELSE 24 END, 'right', 24, 'bottom', CASE WHEN v_spec.hide_addons THEN 16 ELSE 24 END, 'left', 24),
                'bleed', '{}'::jsonb,
                'background_behavior', 'clip'
            )
        );
        v_cfg := jsonb_set(v_cfg, '{canvas,height}', to_jsonb(v_spec.ph), true);
        v_cfg := jsonb_set(v_cfg, '{canvas,width}', to_jsonb(794), true);
        v_hash := v_spec.thash;

        INSERT INTO public.output_template_configs (
            id, revision, name, insurance_type, fixed_fields, status, created_at, updated_at
        )
        VALUES (
            v_spec.tid, 1, v_spec.tname, 'Motor', v_cfg, 'active', NOW(), NOW()
        )
        ON CONFLICT (id) DO NOTHING;

        SELECT EXISTS (
            SELECT 1 FROM public.template_revisions
            WHERE template_id = v_spec.tid AND state = 'published'
        ) INTO v_rev_exists;

        IF NOT v_rev_exists THEN
            INSERT INTO public.template_revisions (
                id, template_id, revision_number, state, page_profile_id,
                config, config_hash, published_at, created_at, updated_at
            )
            VALUES (
                gen_random_uuid(), v_spec.tid, 1, 'published', v_spec.pid,
                v_cfg, v_hash, NOW(), NOW(), NOW()
            )
            ON CONFLICT (template_id, revision_number) DO NOTHING;
        END IF;
    END LOOP;
END $$;

COMMIT;
