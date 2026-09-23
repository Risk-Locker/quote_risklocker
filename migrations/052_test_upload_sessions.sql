-- Migration: 052_test_upload_sessions.sql
-- Description: Add is_test flag to sessions, uploaded_files, and batches to isolate test uploads from customer records and hit & miss tracking.

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_sessions_is_test ON sessions (is_test);

ALTER TABLE uploaded_files
    ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE batches
    ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT false;
