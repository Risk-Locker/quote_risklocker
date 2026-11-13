-- 076_add_critical_foreign_key_and_performance_indexes.sql
-- Add high-performance B-Tree indexes on frequently joined foreign keys
-- to eliminate sequential table scans and accelerate comparison queries.

-- 1. Comparison Entries & Sessions
CREATE INDEX IF NOT EXISTS idx_tenure_comparison_entries_tenure_id 
    ON tenure_comparison_entries (tenure_id);

CREATE INDEX IF NOT EXISTS idx_tenure_comparison_entries_session_id 
    ON tenure_comparison_entries (session_id);

CREATE INDEX IF NOT EXISTS idx_tenure_comparison_entries_company_id 
    ON tenure_comparison_entries (company_id);

CREATE INDEX IF NOT EXISTS idx_sessions_tenure_id 
    ON sessions (tenure_id);

CREATE INDEX IF NOT EXISTS idx_sessions_customer_id 
    ON sessions (customer_id);

CREATE INDEX IF NOT EXISTS idx_sessions_tracked_vehicle_id 
    ON sessions (tracked_vehicle_id);

-- 2. Insurance Tenures & Tracked Vehicles
CREATE INDEX IF NOT EXISTS idx_insurance_tenures_customer_id 
    ON insurance_tenures (customer_id);

CREATE INDEX IF NOT EXISTS idx_insurance_tenures_tracked_vehicle_id 
    ON insurance_tenures (tracked_vehicle_id);

CREATE INDEX IF NOT EXISTS idx_insurance_tenures_covernote_session_id 
    ON insurance_tenures (covernote_session_id);

CREATE INDEX IF NOT EXISTS idx_insurance_tenures_winning_company_id 
    ON insurance_tenures (winning_company_id);

-- 3. Extraction Records & Benefit Selections
CREATE INDEX IF NOT EXISTS idx_draft_benefit_selections_draft_id 
    ON draft_benefit_selections (draft_id);

CREATE INDEX IF NOT EXISTS idx_draft_benefit_selections_concept_id 
    ON draft_benefit_selections (concept_id);

CREATE INDEX IF NOT EXISTS idx_extraction_records_uploaded_file_id 
    ON extraction_records (uploaded_file_id);

CREATE INDEX IF NOT EXISTS idx_extraction_benefit_lines_extraction_record_id 
    ON extraction_benefit_lines (extraction_record_id);

-- 4. Generated PDF Versions & Jobs
CREATE INDEX IF NOT EXISTS idx_generated_pdf_versions_draft_id 
    ON generated_pdf_versions (draft_id);

CREATE INDEX IF NOT EXISTS idx_jobs_session_id 
    ON jobs (session_id);

-- 5. Customer Accounts Lookup
CREATE INDEX IF NOT EXISTS idx_customer_accounts_id_number 
    ON customer_accounts (id_number);

