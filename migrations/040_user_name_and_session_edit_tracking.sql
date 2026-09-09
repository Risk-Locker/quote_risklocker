-- Migration: Add user name and session edit tracking
-- Description: Adds name column to users for staff identification, and last_edited_by_id and last_edited_at to sessions.

-- 1. Add name to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(120);

-- 2. Add last edited attribution to sessions
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS last_edited_by_id UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS last_edited_at TIMESTAMPTZ;

-- 3. Add index on sessions for sorting and performance
CREATE INDEX IF NOT EXISTS idx_sessions_last_edited_at ON sessions(last_edited_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_quotation_ref ON sessions(quotation_ref);
