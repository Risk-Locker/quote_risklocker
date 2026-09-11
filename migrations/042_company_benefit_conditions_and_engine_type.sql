-- Migration: Company Benefit Conditions and Engine Type Architecture
-- Description: Adds engine_type to benefit_catalogs, introduces company_benefit_configs for insurer master benefit pool & baseline descriptions, and company_benefit_conditions for dynamic conditional benefit descriptions.

ALTER TABLE benefit_catalogs
    ADD COLUMN IF NOT EXISTS engine_type VARCHAR(20) NOT NULL DEFAULT 'ice';

CREATE TABLE IF NOT EXISTS company_benefit_configs (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES insurance_companies(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES benefit_concepts(id) ON DELETE CASCADE,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    baseline_description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_company_concept_config UNIQUE (company_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_company_benefit_configs_company ON company_benefit_configs(company_id);
CREATE INDEX IF NOT EXISTS idx_company_benefit_configs_concept ON company_benefit_configs(concept_id);

CREATE TABLE IF NOT EXISTS company_benefit_conditions (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES insurance_companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    trigger_concept_id UUID NOT NULL REFERENCES benefit_concepts(id) ON DELETE CASCADE,
    trigger_plan_filter VARCHAR(255),
    target_concept_id UUID NOT NULL REFERENCES benefit_concepts(id) ON DELETE CASCADE,
    replacement_description TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_benefit_conditions_company ON company_benefit_conditions(company_id);
CREATE INDEX IF NOT EXISTS idx_company_benefit_conditions_trigger ON company_benefit_conditions(trigger_concept_id);
CREATE INDEX IF NOT EXISTS idx_company_benefit_conditions_target ON company_benefit_conditions(target_concept_id);
