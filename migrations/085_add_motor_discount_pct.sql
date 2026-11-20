-- Migration 085: Add motor_discount_pct to insurance_tenures
-- Percentage discount (0.00-100.00%) applied strictly to motor insurance premium (excluding road tax and runner fee).

ALTER TABLE insurance_tenures
ADD COLUMN IF NOT EXISTS motor_discount_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00;
