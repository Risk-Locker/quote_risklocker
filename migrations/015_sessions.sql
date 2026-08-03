-- Migration: Create sessions table
-- Description: Tracks a user session per uploaded file+draft for the session-based review workflow

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES users(id),
    uploaded_file_id UUID NOT NULL REFERENCES uploaded_files(id) UNIQUE,
    draft_id UUID NOT NULL REFERENCES quotation_drafts(id) UNIQUE,
    insurance_type VARCHAR(100) NOT NULL DEFAULT 'Motor',
    detected_company VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_owner_id ON sessions(owner_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at DESC);

COMMENT ON TABLE sessions IS 'User sessions linking an uploaded file to its review draft';
COMMENT ON COLUMN sessions.detected_company IS 'Insurance company name auto-detected from the uploaded filename';
