-- 079: Seed Kurnia as a separate Motor insurance company if not already present
INSERT INTO insurance_companies (
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
    gen_random_uuid(),
    'kurnia',
    1,
    'Kurnia',
    'Motor',
    'Other / Unknown',
    '["Kurnia", "Kurnia Insurans", "Kurnia Insurance", "Kurnia Insurans (Malaysia) Berhad"]'::jsonb,
    'active',
    NOW(),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM insurance_companies
    WHERE slug = 'kurnia'
       OR LOWER(name) IN ('kurnia', 'kurnia insurans', 'kurnia insurance', 'kurnia insurans (malaysia) berhad')
);
