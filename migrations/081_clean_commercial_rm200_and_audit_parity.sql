-- 081_clean_commercial_rm200_and_audit_parity.sql
-- v30.6 Clean remaining legacy RM200/RM 200 towing catalog entries on AmAssurance
-- Commercial/Motorcycle/Private catalogs and optional EV towing descriptions so
-- Design 2 Box 1 <-> Top-Right never receives phantom RM 200 entries from DB seeds.

BEGIN;

-- 1. Commercial Lorry (A Permit / C Permit) do not include complimentary private-car towing
UPDATE catalog_offerings co
SET status = 'inactive'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, benefit_concepts c
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND co.concept_id = c.id
  AND c.concept_key = 'towing'
  AND co.offering_kind = 'base'
  AND co.role = 'included'
  AND (
    bc.name ILIKE '%Commercial Lorry%'
    OR LOWER(COALESCE(co.display_value, '')) IN ('rm 200', 'rm200')
  )
  AND bc.name ILIKE '%Commercial Lorry%'
  AND co.status <> 'inactive';

-- 2. AmAssurance Commercial Car Policy (Company Car) -> align to 100 km standard
UPDATE catalog_offerings co
SET display_value = '100 km',
    description_override = '24/7 emergency accident and breakdown towing assistance up to 100 km.'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic, benefit_concepts c
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND co.concept_id = c.id
  AND ic.slug = 'amassurance'
  AND bc.name ILIKE '%Commercial Car Policy%'
  AND c.concept_key = 'towing'
  AND co.offering_kind = 'base'
  AND (
    LOWER(COALESCE(co.display_value, '')) LIKE '%200%'
    OR LOWER(COALESCE(co.description_override, '')) LIKE '%rm%200%'
  );

-- 3. AmAssurance Motorcycle catalogs had display_value='RM 50' with stale 'up to RM200' copy
UPDATE catalog_offerings co
SET description_override = 'Emergency motorcycle towing assistance up to RM 50 to nearest approved repairer.'
FROM benefit_catalog_revisions bcr, benefit_catalogs bc, insurance_companies ic, benefit_concepts c
WHERE co.catalog_revision_id = bcr.id
  AND bcr.catalog_id = bc.id
  AND bc.company_id = ic.id
  AND co.concept_id = c.id
  AND ic.slug = 'amassurance'
  AND bc.name ILIKE '%Motorcycle%'
  AND c.concept_key = 'towing'
  AND LOWER(COALESCE(co.description_override, '')) LIKE '%rm%200%';

-- 4. Clean remaining stale 'up to RM200' copy in AmAssurance Private Car & EV optional towing add-ons
UPDATE catalog_offerings co
SET display_value = CASE
        WHEN LOWER(COALESCE(co.display_value, '')) IN ('rm 200', 'rm200') THEN NULL
        ELSE co.display_value
    END,
    description_override = '24/7 emergency accidental towing service to nearest approved panel repairer under policy terms.'
FROM benefit_concepts c
WHERE co.concept_id = c.id
  AND c.concept_key = 'towing'
  AND LOWER(COALESCE(co.description_override, '')) LIKE '%rm%200%'
  AND co.status = 'active';

COMMIT;
