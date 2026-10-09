-- Migration 072: Cover Note / Policy Separation from Quotations
-- Separates official issued cover notes / policies from marketing comparison quotation options.

-- 1. Add document_type and policy_number to sessions table
ALTER TABLE sessions
ADD COLUMN IF NOT EXISTS document_type VARCHAR(50) NOT NULL DEFAULT 'quotation';

ALTER TABLE sessions
ADD COLUMN IF NOT EXISTS policy_number VARCHAR(100);

-- 2. Add covernote_session_id and policy_number to insurance_tenures table
ALTER TABLE insurance_tenures
ADD COLUMN IF NOT EXISTS covernote_session_id UUID REFERENCES sessions(id) ON DELETE SET NULL;

ALTER TABLE insurance_tenures
ADD COLUMN IF NOT EXISTS policy_number VARCHAR(100);

-- 3. Create performance indexes
CREATE INDEX IF NOT EXISTS ix_sessions_document_type ON sessions(document_type);
CREATE INDEX IF NOT EXISTS ix_insurance_tenures_covernote_session_id ON insurance_tenures(covernote_session_id);
