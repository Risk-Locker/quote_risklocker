-- Migration: Create client_records table
-- Description: CRM dashboard for confirmed quotations with indexable insurer_no and vehicle_no

CREATE TABLE IF NOT EXISTS client_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    insurer_no VARCHAR(120) NOT NULL UNIQUE,
    session_id UUID REFERENCES sessions(id),
    draft_id UUID REFERENCES quotation_drafts(id),
    uploaded_file_id UUID REFERENCES uploaded_files(id),
    insurance_company VARCHAR(255),
    vehicle_no VARCHAR(50),
    customer_name VARCHAR(255),
    coverage_type VARCHAR(100),
    cover_period VARCHAR(100),
    car_model VARCHAR(255),
    ncd_percent VARCHAR(50),
    ncd VARCHAR(50),
    coverage_amount VARCHAR(100),
    premium VARCHAR(100),
    roadtax VARCHAR(100),
    service_fee VARCHAR(100),
    total_premium VARCHAR(100),
    issue_date VARCHAR(50),
    valid_until VARCHAR(50),
    vehicle_year VARCHAR(20),
    capacity VARCHAR(50),
    engine_no VARCHAR(100),
    chassis_no VARCHAR(100),
    market_value VARCHAR(100),
    agreed_value VARCHAR(100),
    excess_amount VARCHAR(100),
    basic_premium VARCHAR(100),
    ncd_amount VARCHAR(100),
    service_tax VARCHAR(100),
    stamp_duty VARCHAR(100),
    gross_premium VARCHAR(100),
    optional_covers TEXT,
    notes TEXT,
    raw_values JSONB NOT NULL DEFAULT '{}',
    extracted_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,
    generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_client_records_insurer_no ON client_records(insurer_no);
CREATE INDEX IF NOT EXISTS idx_client_records_insurance_company ON client_records(insurance_company);
CREATE INDEX IF NOT EXISTS idx_client_records_vehicle_no ON client_records(vehicle_no);
CREATE INDEX IF NOT EXISTS idx_client_records_created_at ON client_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_client_records_customer_name ON client_records(customer_name);

COMMENT ON TABLE client_records IS 'Confirmed quotation records for CRM dashboard and cross-system integration';
COMMENT ON COLUMN client_records.insurer_no IS 'Auto-generated key: INSURER-VEHICLE_NO format. Unique, editable.';
COMMENT ON COLUMN client_records.raw_values IS 'JSON backup of full draft fields at time of generation';
