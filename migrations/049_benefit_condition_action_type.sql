-- Migration: 049_benefit_condition_action_type.sql
-- Description: Add action_type to company_benefit_conditions to support 'hide_target' and 'replace_description'.

ALTER TABLE company_benefit_conditions
    ADD COLUMN IF NOT EXISTS action_type VARCHAR(50) NOT NULL DEFAULT 'replace_description';

ALTER TABLE company_benefit_conditions
    ALTER COLUMN replacement_description DROP NOT NULL;
