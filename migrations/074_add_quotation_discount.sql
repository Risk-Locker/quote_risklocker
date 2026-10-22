-- Migration 074: Add quotation_discount to insurance_tenures and discount to tenure_comparison_entries
-- Allows applying custom agency/rebate discounts to quotations in the marketing comparison table.

ALTER TABLE insurance_tenures
ADD COLUMN IF NOT EXISTS quotation_discount NUMERIC(10, 2) NOT NULL DEFAULT 0.00;

ALTER TABLE tenure_comparison_entries
ADD COLUMN IF NOT EXISTS discount NUMERIC(10, 2) DEFAULT NULL;
