-- 082_v30_7_dynamic_addons_betterment_towing_catalog_clean.sql
-- v30.7:
-- 1. Add DB-driven insurer policy_rules JSONB (betterment & towing limits) on insurance_companies
-- 2. Add conditional dynamic extra_addons JSONB on tenure_comparison_entries
-- 3. Remove verbose prose strings from base catalog_offerings.typed_value & auto-seeded draft_benefit_selections
-- 4. Repair ICE drafts (e.g. TMCA7642479) erroneously pinned to EV catalogs & supersede phantom EV betterment selections

BEGIN;

-- 1. DB-driven underwriter betterment & towing rules
ALTER TABLE insurance_companies
    ADD COLUMN IF NOT EXISTS policy_rules JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE insurance_companies
SET policy_rules = '{
  "betterment": {"auto_waive_without_peril": true, "max_waiver_years": 10, "default_display": "Up to 10 Years"},
  "towing": {"metric": "RM", "base_limit": "RM 500", "tariff_limit": "RM 200", "unlimited_triggers": ["driver passenger protector", "driver & passenger protector", "dpa", "dpp", "n4", "unlimited auto assistance"]}
}'::jsonb
WHERE LOWER(COALESCE(slug, name)) LIKE '%qbe%' AND policy_rules = '{}'::jsonb;

UPDATE insurance_companies
SET policy_rules = '{
  "betterment": {"auto_waive_without_peril": false, "max_waiver_years": 15, "default_display": "Up to 15 Years"},
  "towing": {"metric": "km", "base_limit": "200 km", "unlimited_triggers": ["oto 360", "oto360", "oto-360", "driver plan 1"]}
}'::jsonb
WHERE LOWER(COALESCE(slug, name)) LIKE '%etiqa%' AND policy_rules = '{}'::jsonb;

UPDATE insurance_companies
SET policy_rules = '{
  "betterment": {"auto_waive_without_peril": false, "max_waiver_years": 10, "default_display": "Up to 10 Years"},
  "towing": {"metric": "km", "base_limit": "50 km", "plan_limits": {"plan 1": "100 km", "plan 2": "200 km", "plan 3": "300 km", "plan 4": "Unlimited"}}
}'::jsonb
WHERE (LOWER(COALESCE(slug, name)) LIKE '%takaful%' OR LOWER(COALESCE(slug, name)) LIKE '%stmb%') AND policy_rules = '{}'::jsonb;

UPDATE insurance_companies
SET policy_rules = '{
  "betterment": {"auto_waive_without_peril": false, "max_waiver_years": 10, "default_display": "Up to 10 Years"},
  "towing": {"metric": "RM", "base_limit": "RM 400", "tariff_limit": "RM 200", "sdpa_plan1_limit": "RM 600", "unlimited_triggers": ["e-assist smart driver", "sdpa", "plan 2", "ev plan"]}
}'::jsonb
WHERE LOWER(COALESCE(slug, name)) LIKE '%lonpac%' AND policy_rules = '{}'::jsonb;

UPDATE insurance_companies
SET policy_rules = '{
  "betterment": {"auto_waive_without_peril": false, "max_waiver_years": 15, "default_display": "Up to 15 Years"},
  "towing": {"metric": "Unlimited", "base_limit": "Unlimited", "tariff_limit": "RM 200"}
}'::jsonb
WHERE LOWER(COALESCE(slug, name)) LIKE '%sompo%' AND policy_rules = '{}'::jsonb;

UPDATE insurance_companies
SET policy_rules = '{
  "betterment": {"auto_waive_without_peril": false, "max_waiver_years": 15, "default_display": "Up to 15 Years"},
  "towing": {"metric": "RM", "base_limit": "RM 300", "unlimited_triggers": ["motor easy bundle", "autobuddy", "motor shield"]}
}'::jsonb
WHERE LOWER(COALESCE(slug, name)) LIKE '%tune%' AND policy_rules = '{}'::jsonb;

UPDATE insurance_companies
SET policy_rules = '{
  "betterment": {"auto_waive_without_peril": false, "max_waiver_years": 15, "default_display": "Up to 15 Years"},
  "towing": {"metric": "km", "base_limit": "100 km", "lite_limit": "50 km", "premier_limit": "365 km", "unlimited_triggers": ["amdrive plus"]}
}'::jsonb
WHERE (LOWER(COALESCE(slug, name)) LIKE '%amassurance%' OR LOWER(COALESCE(slug, name)) LIKE '%amgen%') AND policy_rules = '{}'::jsonb;

UPDATE insurance_companies
SET policy_rules = '{
  "betterment": {"auto_waive_without_peril": false, "max_waiver_years": 10, "default_display": "Up to 10 Years"},
  "towing": {"metric": "km", "base_limit": "150 km", "rm_fallback": "RM 200", "unlimited_triggers": ["auto assist plus", "auto assist premier", "amdrive plus"]}
}'::jsonb
WHERE LOWER(COALESCE(slug, name)) LIKE '%kurnia%' AND policy_rules = '{}'::jsonb;

-- 2. Conditional dynamic optional add-on states for Comparison Matrix rows below LLP / LLOP
ALTER TABLE tenure_comparison_entries
    ADD COLUMN IF NOT EXISTS extra_addons JSONB NOT NULL DEFAULT '{}'::jsonb;

-- 3. Clean prose sentences out of base catalog_offerings.typed_value so Box 1 renders strictly Title + Description
UPDATE catalog_offerings co
SET description_override = CASE
        WHEN NULLIF(BTRIM(COALESCE(co.description_override, '')), '') IS NULL
             AND co.typed_value IS NOT NULL
             AND co.typed_value->>'type' = 'text'
             AND LENGTH(COALESCE(co.typed_value->>'value', '')) > 18
        THEN BTRIM(co.typed_value->>'value')
        ELSE co.description_override
    END,
    typed_value = NULL
WHERE co.offering_kind = 'base'
  AND co.typed_value IS NOT NULL
  AND co.typed_value->>'type' = 'text'
  AND LENGTH(COALESCE(co.typed_value->>'value', '')) > 18;

-- Clean matching non-manual prose overrides on existing active Box 1 selections
UPDATE draft_benefit_selections dbs
SET typed_value_override = NULL
FROM catalog_offerings co
WHERE dbs.catalog_offering_id = co.id
  AND co.offering_kind = 'base'
  AND COALESCE(dbs.evidence_snapshot->>'source', '') <> 'manual'
  AND dbs.typed_value_override IS NOT NULL
  AND dbs.typed_value_override->>'type' = 'text'
  AND LENGTH(COALESCE(dbs.typed_value_override->>'value', '')) > 18;

-- 4. Repair ICE/weight drafts erroneously pinned to EV catalogs (and remove phantom EV Betterment Waiver selections)
WITH ice_ev_pinned AS (
    SELECT qd.id AS draft_id
    FROM quotation_drafts qd
    JOIN benefit_catalog_revisions bcr ON qd.catalog_revision_id = bcr.id
    JOIN benefit_catalogs bc ON bcr.catalog_id = bc.id
    WHERE bc.engine_type = 'ev'
      AND (
          UPPER(COALESCE(qd.fields->'engine_cc'->>'value', qd.fields->>'engine_cc', '')) ~ '(CC|KG|TON)'
      )
      AND NOT (
          UPPER(COALESCE(qd.fields->'car_model'->>'value', qd.fields->>'car_model', '')) ~ '(TESLA|BYD|ORA|ZEEKR|IONIQ|EV6|ATTO|DOLPHIN|SEAL|LEAF|TAYCAN|EQA|EQB|EQC|EQE|EQS|E\.MAS|EMAS|OMODA E5|MG4|ELECTRIC|KILOWATT)'
      )
      AND NOT (
          UPPER(COALESCE(qd.fields->'engine_cc'->>'value', qd.fields->>'engine_cc', '')) ~ '(KW|WATT)'
      )
)
UPDATE draft_benefit_selections dbs
SET state = 'superseded'
FROM ice_ev_pinned iep
WHERE dbs.draft_id = iep.draft_id
  AND dbs.state = 'current'
  AND COALESCE(dbs.evidence_snapshot->>'source', '') <> 'manual'
  AND (
      dbs.selection_key LIKE 'catalog:ev-%'
      OR dbs.selection_key ILIKE '%betterment%'
  );

WITH ice_ev_pinned AS (
    SELECT qd.id AS draft_id
    FROM quotation_drafts qd
    JOIN benefit_catalog_revisions bcr ON qd.catalog_revision_id = bcr.id
    JOIN benefit_catalogs bc ON bcr.catalog_id = bc.id
    WHERE bc.engine_type = 'ev'
      AND (
          UPPER(COALESCE(qd.fields->'engine_cc'->>'value', qd.fields->>'engine_cc', '')) ~ '(CC|KG|TON)'
      )
      AND NOT (
          UPPER(COALESCE(qd.fields->'car_model'->>'value', qd.fields->>'car_model', '')) ~ '(TESLA|BYD|ORA|ZEEKR|IONIQ|EV6|ATTO|DOLPHIN|SEAL|LEAF|TAYCAN|EQA|EQB|EQC|EQE|EQS|E\.MAS|EMAS|OMODA E5|MG4|ELECTRIC|KILOWATT)'
      )
      AND NOT (
          UPPER(COALESCE(qd.fields->'engine_cc'->>'value', qd.fields->>'engine_cc', '')) ~ '(KW|WATT)'
      )
)
UPDATE quotation_drafts qd
SET product_id = NULL,
    tier_id = NULL,
    catalog_revision_id = NULL
FROM ice_ev_pinned iep
WHERE qd.id = iep.draft_id;

COMMIT;
