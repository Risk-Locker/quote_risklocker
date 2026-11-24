-- Migration 092: Clear catalog coverage info/values for all concepts except Towing and Windscreen.
-- Preserves the benefit concepts, manual editing capability, and source PDF extraction priority.

BEGIN;

-- 1. Clear demo/default coverage values on benefit_concepts except towing & windscreen
UPDATE public.benefit_concepts
SET
    demo_value = NULL,
    updated_at = NOW()
WHERE LOWER(concept_key) NOT IN (
    'towing',
    '24-hr-towing',
    'roadside-towing',
    'windscreen',
    'windscreen-damage'
)
AND demo_value IS NOT NULL;

-- 2. Clear replacement_value on company_benefit_conditions except towing & windscreen targets
UPDATE public.company_benefit_conditions cbc
SET
    replacement_value = NULL,
    updated_at = NOW()
FROM public.benefit_concepts bc
WHERE cbc.target_concept_id = bc.id
  AND LOWER(bc.concept_key) NOT IN (
      'towing',
      '24-hr-towing',
      'roadside-towing',
      'windscreen',
      'windscreen-damage'
  )
  AND cbc.replacement_value IS NOT NULL;

-- 3. Clear display_value and typed_value on catalog_offerings except towing & windscreen concepts
UPDATE public.catalog_offerings co
SET
    display_value = NULL,
    typed_value = NULL,
    updated_at = NOW()
FROM public.benefit_concepts bc
WHERE co.concept_id = bc.id
  AND LOWER(bc.concept_key) NOT IN (
      'towing',
      '24-hr-towing',
      'roadside-towing',
      'windscreen',
      'windscreen-damage'
  )
  AND (co.display_value IS NOT NULL OR co.typed_value IS NOT NULL);

COMMIT;
