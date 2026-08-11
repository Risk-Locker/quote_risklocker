-- Template groups: named, company-linked folders for organizing templates.

BEGIN;

CREATE TABLE IF NOT EXISTS template_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    company_id UUID REFERENCES insurance_companies(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE output_template_configs
    ADD COLUMN IF NOT EXISTS group_id UUID REFERENCES template_groups(id) ON DELETE SET NULL;

COMMIT;
