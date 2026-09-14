-- Migration: Add baseline_cost to company_benefit_configs
-- Description: Adds baseline_cost column to company_benefit_configs to store default pricing, rates, or formula strings for insurer benefits.

ALTER TABLE company_benefit_configs
    ADD COLUMN IF NOT EXISTS baseline_cost VARCHAR(255) NULL;
