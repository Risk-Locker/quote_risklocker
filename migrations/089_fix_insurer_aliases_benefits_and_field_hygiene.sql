-- 089_fix_insurer_aliases_benefits_and_field_hygiene.sql
-- 1. Remove colliding Kurnia / Liberty aliases from AmAssurance and remove footer promo 'Kurnia One Touch' from Kurnia detection phrases.
-- 2. Remove base package aliases ('auto365', 'auto365 plus', 'auto365 premier', etc.) from the 'private-car-365' add-on concept.
-- 3. Strip plain-string non-canonical mirror keys from quotation_drafts.fields so they never trigger phantom Needs Review chips.

BEGIN;

-- 1. Clean colliding company_aliases & detection_phrases between AmAssurance and Kurnia
DELETE FROM public.company_aliases
WHERE company_id IN (
    SELECT id FROM public.insurance_companies WHERE slug = 'amassurance'
)
AND LOWER(alias) IN ('kurnia', 'liberty general insurance', 'liberty insurance');

UPDATE public.insurance_companies
SET
    detection_phrases = '["Kurnia", "Kurnia Insurans", "Kurnia Insurance", "Kurnia Insurans (Malaysia) Berhad", "www.kurnia.com", "kurnia.com", "Kurnia Auto Assist"]'::jsonb,
    updated_at = NOW()
WHERE slug = 'kurnia';

UPDATE public.insurance_companies
SET
    detection_phrases = '["AmAssurance", "amassurance", "AmGen", "AmGeneral", "AmGeneral Insurance", "auto365", "www.amassurance.com.my", "amassurance.com.my"]'::jsonb,
    updated_at = NOW()
WHERE slug = 'amassurance';

-- 2. Separate Auto365 Comprehensive (base package) from Private Car 365 Plan 1-4 (add-on benefit)
DELETE FROM public.benefit_aliases
WHERE benefit_id IN (
    SELECT id FROM public.benefit_concepts WHERE concept_key = 'private-car-365'
)
AND LOWER(phrase) IN (
    'auto365',
    'auto 365',
    'auto365 plus',
    'auto365 premier',
    'auto365 multi rider pack',
    'auto365 plus multi-rider upgrade pack',
    'tier upgrade'
);

-- 3. Strip plain-string non-canonical mirror keys from quotation_drafts.fields (preserve structured object fields)
UPDATE public.quotation_drafts d
SET fields = (
    SELECT COALESCE(jsonb_object_agg(e.key, e.value), '{}'::jsonb)
    FROM jsonb_each(d.fields) e
    WHERE NOT (
        e.key IN (
            'make', 'ic_no', 'nric_no', 'id_number', 'customer_ic_no',
            'veh_reg_no', 'registration_no', 'client_name', 'insured_name',
            'policyholder_name', 'engine_number', 'chassis_number',
            'vehicle_model', 'coverage_start_date', 'coverage_end_date'
        )
        AND jsonb_typeof(e.value) <> 'object'
    )
),
updated_at = NOW()
WHERE EXISTS (
    SELECT 1
    FROM jsonb_each(d.fields) e
    WHERE e.key IN (
        'make', 'ic_no', 'nric_no', 'id_number', 'customer_ic_no',
        'veh_reg_no', 'registration_no', 'client_name', 'insured_name',
        'policyholder_name', 'engine_number', 'chassis_number',
        'vehicle_model', 'coverage_start_date', 'coverage_end_date'
    )
    AND jsonb_typeof(e.value) <> 'object'
);

COMMIT;
