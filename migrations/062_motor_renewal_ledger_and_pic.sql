-- Migration: 062_motor_renewal_ledger_and_pic.sql
-- Description: Add Person In Charge (PIC) & SubAgent entity, and expand InsuranceTenure with 12 lifecycle stages, UCD/roadtax checklist, comments, and preference notes.

CREATE TABLE IF NOT EXISTS person_in_charge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL DEFAULT 'subagent',
    agency_group VARCHAR(100) NULL,
    commission_rate NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    phone VARCHAR(50) NULL,
    email VARCHAR(120) NULL,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pic_name ON person_in_charge(name);
CREATE INDEX IF NOT EXISTS idx_pic_type ON person_in_charge(type);
CREATE INDEX IF NOT EXISTS idx_pic_agency ON person_in_charge(agency_group);

ALTER TABLE insurance_tenures
    ADD COLUMN IF NOT EXISTS stage VARCHAR(50) NOT NULL DEFAULT 'Quotations',
    ADD COLUMN IF NOT EXISTS business_type VARCHAR(50) NOT NULL DEFAULT 'Renewal',
    ADD COLUMN IF NOT EXISTS pic_id UUID NULL REFERENCES person_in_charge(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS sub_agent_name VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS key_in_ucd BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS date_of_key_in DATE NULL,
    ADD COLUMN IF NOT EXISTS print_roadtax VARCHAR(20) NOT NULL DEFAULT 'No',
    ADD COLUMN IF NOT EXISTS roadtax_receipt VARCHAR(20) NOT NULL DEFAULT 'None',
    ADD COLUMN IF NOT EXISTS client_payment_received BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS agency_payment_done BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS comment TEXT NULL,
    ADD COLUMN IF NOT EXISTS client_preference_notes TEXT NULL,
    ADD COLUMN IF NOT EXISTS loss_reason_category VARCHAR(50) NULL,
    ADD COLUMN IF NOT EXISTS stage_updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_insurance_tenures_stage ON insurance_tenures(stage);
CREATE INDEX IF NOT EXISTS idx_insurance_tenures_business_type ON insurance_tenures(business_type);
CREATE INDEX IF NOT EXISTS idx_insurance_tenures_pic_id ON insurance_tenures(pic_id);
CREATE INDEX IF NOT EXISTS idx_insurance_tenures_stage_updated ON insurance_tenures(stage_updated_at);
