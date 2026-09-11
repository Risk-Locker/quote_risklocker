-- Migration: Add Tuition Purpose Concept & Multi-Variant Schemas
-- Description: Adds tuition-purpose concept to benefit_concepts and configures variant options for CART, First Loss Special Perils, and Motor PA Plus.

INSERT INTO benefit_concepts (
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
) VALUES (
    '7e59f42c-a241-482f-b44c-3e3bf9b10901',
    'tuition-purpose',
    'Tuition Purpose',
    '{"category": "addon", "variants": []}'::jsonb,
    '{label}',
    '[]'::jsonb,
    '[]'::jsonb,
    '{}'::jsonb,
    'Extension of motor policy coverage for driving tuition and instructional driving purposes.',
    53,
    1,
    'active',
    NOW(),
    NOW()
) ON CONFLICT (concept_key) DO UPDATE SET
    label = EXCLUDED.label,
    description = EXCLUDED.description,
    value_schema = EXCLUDED.value_schema,
    updated_at = NOW();

UPDATE benefit_concepts
SET value_schema = '{"category": "addon", "variants": ["RM 50/day (14 days)", "RM 100/day (14 days)"]}'::jsonb,
    updated_at = NOW()
WHERE concept_key = 'repair-allowance';

UPDATE benefit_concepts
SET value_schema = '{"category": "addon", "variants": ["RM 5,000", "RM 10,000"]}'::jsonb,
    updated_at = NOW()
WHERE concept_key = 'first-loss-flood';

UPDATE benefit_concepts
SET value_schema = '{"category": "addon", "variants": ["Plan 1", "Plan 2", "Plan 3", "Plan 4"]}'::jsonb,
    updated_at = NOW()
WHERE concept_key = 'motor-pa-plus';
