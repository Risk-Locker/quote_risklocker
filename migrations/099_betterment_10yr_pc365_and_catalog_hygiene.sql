-- 099_betterment_10yr_pc365_and_catalog_hygiene.sql
-- Idempotent enterprise migration:
-- 1. Standardize insurance_companies.policy_rules->'betterment' across all insurers (10-year max cap, DB-driven placement).
-- 2. Replace all "Up to 15 Years" / "up to 15 years" references with 10-year rules in configs and catalog offerings;
--    enforce QBE strictly base/included and non-QBE strictly optional/addon_option; disable retired betterment-scale configs.
-- 3. Make private-car-365 concept description brand-neutral (Option 1) and clean stale auto365 TPFT Premier override.
-- 4. Repair catalog_offerings with NULL applies_to_type/applies_to_id on packaged catalogs.
-- 5. Clean false customer_discrepancies caused by insurer SSM BRNs or punctuation/ampersand-only differences.
-- 6. Repair historical non-manual tenure_comparison_entries with veh_age > 10 wrongly marked waiver_betterment = TRUE.

BEGIN;

-- 1. Standardize insurance_companies.policy_rules->'betterment'
UPDATE public.insurance_companies
SET policy_rules = jsonb_set(
        COALESCE(policy_rules, '{}'::jsonb),
        '{betterment}',
        '{"auto_waive_without_peril": true, "allow_addon_purchase": false, "free_exemption_years": 10, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 10 Years"}'::jsonb,
        true
    ),
    updated_at = NOW()
WHERE LOWER(COALESCE(slug, '')) = 'qbe'
   OR LOWER(COALESCE(name, '')) LIKE '%qbe%';

UPDATE public.insurance_companies
SET policy_rules = jsonb_set(
        COALESCE(policy_rules, '{}'::jsonb),
        '{betterment}',
        '{"auto_waive_without_peril": false, "allow_addon_purchase": false, "free_exemption_years": 0, "max_waiver_years": 0, "default_display": "No", "free_display": "No"}'::jsonb,
        true
    ),
    updated_at = NOW()
WHERE LOWER(COALESCE(slug, '')) = 'mmip'
   OR LOWER(COALESCE(name, '')) LIKE '%mmip%'
   OR LOWER(COALESCE(name, '')) LIKE '%motor insurance pool%';

UPDATE public.insurance_companies
SET policy_rules = jsonb_set(
        COALESCE(policy_rules, '{}'::jsonb),
        '{betterment}',
        '{"auto_waive_without_peril": false, "allow_addon_purchase": true, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"}'::jsonb,
        true
    ),
    updated_at = NOW()
WHERE LOWER(COALESCE(slug, '')) NOT IN ('qbe', 'mmip')
  AND LOWER(COALESCE(name, '')) NOT LIKE '%qbe%'
  AND LOWER(COALESCE(name, '')) NOT LIKE '%mmip%'
  AND LOWER(COALESCE(name, '')) NOT LIKE '%motor insurance pool%';

-- 2a. Remove all "up to 15 years" copy in company_benefit_configs
UPDATE public.company_benefit_configs
SET baseline_description = REGEXP_REPLACE(baseline_description, 'up to 15 years', 'up to 10 years', 'gi'),
    updated_at = NOW()
WHERE baseline_description ~* 'up to 15 years';

-- 2b. Remove all "up to 15 years" copy in catalog_offerings (latest & active revisions)
UPDATE public.catalog_offerings
SET description_override = REGEXP_REPLACE(description_override, 'up to 15 years', 'up to 10 years', 'gi'),
    updated_at = NOW()
WHERE description_override ~* 'up to 15 years';

UPDATE public.catalog_offerings
SET display_value = REGEXP_REPLACE(display_value, 'up to 15 years', 'Up to 10 Years', 'gi'),
    updated_at = NOW()
WHERE display_value ~* 'up to 15 years';

UPDATE public.catalog_offerings
SET typed_value = jsonb_set(
        typed_value,
        '{display_text}',
        to_jsonb(REGEXP_REPLACE(typed_value->>'display_text', 'up to 15 years', 'Up to 10 Years', 'gi')),
        true
    ),
    updated_at = NOW()
WHERE typed_value IS NOT NULL
  AND jsonb_typeof(typed_value) = 'object'
  AND COALESCE(typed_value->>'display_text', '') ~* 'up to 15 years';

-- 2c. Enforce QBE betterment-protection strictly base/included (remove any duplicate optional/addon_option rows on latest revisions)
WITH latest_rev AS (
    SELECT DISTINCT ON (catalog_id) id AS rev_id, catalog_id
    FROM public.benefit_catalog_revisions
    ORDER BY catalog_id, revision_number DESC
),
qbe_duplicate_optional AS (
    SELECT co.id
    FROM public.catalog_offerings co
    JOIN latest_rev lr ON lr.rev_id = co.catalog_revision_id
    JOIN public.benefit_catalogs bc ON bc.id = lr.catalog_id
    JOIN public.insurance_companies ic ON ic.id = bc.company_id
    JOIN public.benefit_concepts bcon ON bcon.id = co.concept_id
    WHERE bcon.concept_key = 'betterment-protection'
      AND (LOWER(COALESCE(ic.slug, '')) = 'qbe' OR LOWER(COALESCE(ic.name, '')) LIKE '%qbe%')
      AND (co.offering_kind = 'optional' OR co.role = 'addon_option')
      AND EXISTS (
          SELECT 1
          FROM public.catalog_offerings base_co
          WHERE base_co.catalog_revision_id = co.catalog_revision_id
            AND base_co.concept_id = co.concept_id
            AND base_co.id <> co.id
            AND (base_co.offering_kind = 'base' OR base_co.role = 'included')
      )
)
DELETE FROM public.benefit_package_plan_items bppi
USING qbe_duplicate_optional qdo
WHERE bppi.offering_id = qdo.id;

WITH latest_rev AS (
    SELECT DISTINCT ON (catalog_id) id AS rev_id, catalog_id
    FROM public.benefit_catalog_revisions
    ORDER BY catalog_id, revision_number DESC
),
qbe_duplicate_optional AS (
    SELECT co.id
    FROM public.catalog_offerings co
    JOIN latest_rev lr ON lr.rev_id = co.catalog_revision_id
    JOIN public.benefit_catalogs bc ON bc.id = lr.catalog_id
    JOIN public.insurance_companies ic ON ic.id = bc.company_id
    JOIN public.benefit_concepts bcon ON bcon.id = co.concept_id
    WHERE bcon.concept_key = 'betterment-protection'
      AND (LOWER(COALESCE(ic.slug, '')) = 'qbe' OR LOWER(COALESCE(ic.name, '')) LIKE '%qbe%')
      AND (co.offering_kind = 'optional' OR co.role = 'addon_option')
      AND EXISTS (
          SELECT 1
          FROM public.catalog_offerings base_co
          WHERE base_co.catalog_revision_id = co.catalog_revision_id
            AND base_co.concept_id = co.concept_id
            AND base_co.id <> co.id
            AND (base_co.offering_kind = 'base' OR base_co.role = 'included')
      )
)
DELETE FROM public.catalog_offerings co
USING qbe_duplicate_optional qdo
WHERE co.id = qdo.id;

UPDATE public.catalog_offerings co
SET offering_kind = 'base',
    role = 'included',
    optional_price = NULL,
    updated_at = NOW()
FROM public.benefit_catalog_revisions bcr
JOIN public.benefit_catalogs bc ON bc.id = bcr.catalog_id
JOIN public.insurance_companies ic ON ic.id = bc.company_id,
     public.benefit_concepts bcon
WHERE co.catalog_revision_id = bcr.id
  AND co.concept_id = bcon.id
  AND bcon.concept_key = 'betterment-protection'
  AND (LOWER(COALESCE(ic.slug, '')) = 'qbe' OR LOWER(COALESCE(ic.name, '')) LIKE '%qbe%')
  AND (co.offering_kind <> 'base' OR co.role <> 'included');

-- 2d. Enforce non-QBE betterment-protection strictly optional/addon_option (never duplicated in base & optional)
WITH latest_rev AS (
    SELECT DISTINCT ON (catalog_id) id AS rev_id, catalog_id
    FROM public.benefit_catalog_revisions
    ORDER BY catalog_id, revision_number DESC
),
non_qbe_duplicate_base AS (
    SELECT co.id
    FROM public.catalog_offerings co
    JOIN latest_rev lr ON lr.rev_id = co.catalog_revision_id
    JOIN public.benefit_catalogs bc ON bc.id = lr.catalog_id
    JOIN public.insurance_companies ic ON ic.id = bc.company_id
    JOIN public.benefit_concepts bcon ON bcon.id = co.concept_id
    WHERE bcon.concept_key = 'betterment-protection'
      AND NOT (LOWER(COALESCE(ic.slug, '')) = 'qbe' OR LOWER(COALESCE(ic.name, '')) LIKE '%qbe%')
      AND (co.offering_kind = 'base' OR co.role = 'included')
      AND EXISTS (
          SELECT 1
          FROM public.catalog_offerings opt_co
          WHERE opt_co.catalog_revision_id = co.catalog_revision_id
            AND opt_co.concept_id = co.concept_id
            AND opt_co.id <> co.id
            AND (opt_co.offering_kind = 'optional' OR opt_co.role = 'addon_option')
      )
)
DELETE FROM public.benefit_package_plan_items bppi
USING non_qbe_duplicate_base nqdb
WHERE bppi.offering_id = nqdb.id;

WITH latest_rev AS (
    SELECT DISTINCT ON (catalog_id) id AS rev_id, catalog_id
    FROM public.benefit_catalog_revisions
    ORDER BY catalog_id, revision_number DESC
),
non_qbe_duplicate_base AS (
    SELECT co.id
    FROM public.catalog_offerings co
    JOIN latest_rev lr ON lr.rev_id = co.catalog_revision_id
    JOIN public.benefit_catalogs bc ON bc.id = lr.catalog_id
    JOIN public.insurance_companies ic ON ic.id = bc.company_id
    JOIN public.benefit_concepts bcon ON bcon.id = co.concept_id
    WHERE bcon.concept_key = 'betterment-protection'
      AND NOT (LOWER(COALESCE(ic.slug, '')) = 'qbe' OR LOWER(COALESCE(ic.name, '')) LIKE '%qbe%')
      AND (co.offering_kind = 'base' OR co.role = 'included')
      AND EXISTS (
          SELECT 1
          FROM public.catalog_offerings opt_co
          WHERE opt_co.catalog_revision_id = co.catalog_revision_id
            AND opt_co.concept_id = co.concept_id
            AND opt_co.id <> co.id
            AND (opt_co.offering_kind = 'optional' OR opt_co.role = 'addon_option')
      )
)
DELETE FROM public.catalog_offerings co
USING non_qbe_duplicate_base nqdb
WHERE co.id = nqdb.id;

-- 2e. Disable retired betterment-scale configs
UPDATE public.company_benefit_configs cbc
SET is_enabled = FALSE,
    updated_at = NOW()
FROM public.benefit_concepts bcon
WHERE cbc.concept_id = bcon.id
  AND bcon.concept_key = 'betterment-scale'
  AND cbc.is_enabled IS TRUE;

-- 3. Private Car 365 brand-neutral description (Option 1) & clear mismatched TPFT Premier override
UPDATE public.benefit_concepts
SET description = 'auto365 multi-rider package bundling personal accident protection and upgraded towing assistance.',
    updated_at = NOW()
WHERE concept_key = 'private-car-365';

UPDATE public.catalog_offerings co
SET description_override = NULL,
    updated_at = NOW()
FROM public.benefit_concepts bcon
WHERE co.concept_id = bcon.id
  AND bcon.concept_key = 'private-car-365'
  AND co.description_override = 'Bundles All Drivers waiver, RM1,500 flood grant, RM1,000 key care & towing.';

-- 4. Repair orphan applies_to_id IS NULL on packaged catalogs
WITH latest_rev AS (
    SELECT DISTINCT ON (catalog_id) id AS rev_id, catalog_id
    FROM public.benefit_catalog_revisions
    ORDER BY catalog_id, revision_number DESC
),
orphan_packaged AS (
    SELECT
        co.id AS offering_id,
        COALESCE(
            bc.package_id,
            (
                SELECT bp.id
                FROM public.benefit_packages bp
                WHERE bp.catalog_revision_id = lr.rev_id
                  AND bp.package_kind IN ('comprehensive', 'tpft', 'tpo')
                ORDER BY bp.sort_order, bp.id
                LIMIT 1
            )
        ) AS resolved_pkg_id
    FROM public.catalog_offerings co
    JOIN latest_rev lr ON lr.rev_id = co.catalog_revision_id
    JOIN public.benefit_catalogs bc ON bc.id = lr.catalog_id
    WHERE co.applies_to_id IS NULL
      AND (
          bc.package_id IS NOT NULL
          OR EXISTS (
              SELECT 1
              FROM public.benefit_packages bp
              WHERE bp.catalog_revision_id = lr.rev_id
                AND bp.package_kind IN ('comprehensive', 'tpft', 'tpo')
          )
      )
)
UPDATE public.catalog_offerings co
SET applies_to_type = 'package',
    applies_to_id = op.resolved_pkg_id,
    updated_at = NOW()
FROM orphan_packaged op
WHERE co.id = op.offering_id
  AND op.resolved_pkg_id IS NOT NULL;

-- 5. Clean false customer_discrepancies (punctuation/& only name diffs or insurer own BRNs)
UPDATE public.quotation_drafts qd
SET display_options = jsonb_set(
        qd.display_options,
        '{customer_discrepancies}',
        COALESCE(
            (
                SELECT jsonb_agg(elem)
                FROM jsonb_array_elements(qd.display_options->'customer_discrepancies') AS elem
                WHERE NOT (
                    (
                        elem->>'field' = 'name'
                        AND REGEXP_REPLACE(UPPER(COALESCE(elem->>'current', '')), '[^A-Z0-9]+', '', 'g')
                            = REGEXP_REPLACE(UPPER(COALESCE(elem->>'detected', '')), '[^A-Z0-9]+', '', 'g')
                    )
                    OR REGEXP_REPLACE(UPPER(COALESCE(qd.fields->'ic_or_brn'->>'value', '')), '[^A-Z0-9]+', '', 'g') IN (
                        '197801007153', '44191P', '200601015674', '735426V',
                        '197001000276', '9557T', '201701025031', '199401021735',
                        '307414T', '198701002415', '161086D', '198001008821',
                        '62605U', '201701032316', '1246486D', '197601004719',
                        '30686K', '201701035345', '1249516V'
                    )
                )
            ),
            '[]'::jsonb
        ),
        true
    ),
    updated_at = NOW()
WHERE qd.display_options ? 'customer_discrepancies'
  AND jsonb_typeof(qd.display_options->'customer_discrepancies') = 'array'
  AND jsonb_array_length(qd.display_options->'customer_discrepancies') > 0;

-- 6. Historical comparison entry repair (> 10 years old, non-manual, non-TPFT/TPO)
UPDATE public.tenure_comparison_entries tce
SET waiver_betterment = FALSE,
    betterment_rate = 40.00,
    betterment_display = 'No (40%)',
    updated_at = NOW()
FROM public.insurance_tenures t
JOIN public.tracked_vehicles tv ON tv.id = t.tracked_vehicle_id
WHERE tce.tenure_id = t.id
  AND NOT (COALESCE(tce.manual_overrides, '[]'::jsonb) ? 'waiver_betterment')
  AND tv.manufacture_year IS NOT NULL
  AND tv.manufacture_year > 1900
  AND (EXTRACT(YEAR FROM COALESCE(t.coverage_start_date, CURRENT_DATE)) - tv.manufacture_year) > 10
  AND (tce.waiver_betterment IS TRUE OR tce.betterment_rate = 0)
  AND (
      tce.session_id IS NULL
      OR NOT EXISTS (
          SELECT 1
          FROM public.sessions s
          JOIN public.quotation_drafts qd ON qd.id = s.draft_id
          WHERE s.id = tce.session_id
            AND COALESCE(qd.fields->'coverage_type'->>'value', '') ~* 'third\s*party|tpo|tpft'
      )
  );

COMMIT;
