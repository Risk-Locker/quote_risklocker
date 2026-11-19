-- Migration 083: Align Kurnia betterment waiver window to 15 years in DB policy_rules.
-- Preserves 082 checksum immutability on already-applied databases.

UPDATE insurance_companies
SET policy_rules = jsonb_set(
    COALESCE(policy_rules, '{}'::jsonb),
    '{betterment}',
    '{"max_waiver_years": 15, "default_display": "Up to 15 Years", "auto_waive_regardless_of_yom": false}'::jsonb,
    true
)
WHERE slug = 'kurnia';
