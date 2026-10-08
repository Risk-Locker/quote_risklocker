-- Migration 070: Configurable TPO Extra Premium Surcharge & AmAssurance Private Car Products Reactivation

-- 1. Add extra_premium_amount to coverage_types
ALTER TABLE coverage_types
ADD COLUMN IF NOT EXISTS extra_premium_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00;

-- 2. Configure default extra premium of RM 100 for Third Party Only
UPDATE coverage_types
SET extra_premium_amount = 100.00
WHERE coverage_key = 'third_party';

-- 3. Upsert app_settings for tpo_extra_premium
INSERT INTO app_settings (key, value, created_at, updated_at)
VALUES (
    'tpo_extra_premium',
    '{"amount": 100.00, "currency": "MYR", "enabled": true}'::jsonb,
    NOW(),
    NOW()
)
ON CONFLICT (key) DO UPDATE
SET value = EXCLUDED.value,
    updated_at = NOW();

-- 4. Reactivate AmAssurance Private Car Comprehensive product
UPDATE insurance_products
SET status = 'active', updated_at = NOW()
WHERE id = '6549519c-eda5-4c93-bf1e-bb2da87ce268';

-- 5. Publish AmAssurance Auto365 Lite and Plus catalogs
UPDATE benefit_catalogs
SET status = 'published', updated_at = NOW()
WHERE id IN (
    'd3241bc8-160e-4aba-83bb-c88aec3a6758', -- auto365 Comprehensive Lite
    '7ec7079a-ab2d-4984-97cc-bcd500c2679f'  -- auto365 Comprehensive Plus
);
