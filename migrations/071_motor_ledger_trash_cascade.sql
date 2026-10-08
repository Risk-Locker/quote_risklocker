-- Migration 071: Motor Renewal Ledger Soft-Delete and 30-Day Trash Cascading

-- 1. Add deleted_at and purge_after to insurance_tenures
ALTER TABLE insurance_tenures
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

ALTER TABLE insurance_tenures
ADD COLUMN IF NOT EXISTS purge_after TIMESTAMP WITH TIME ZONE DEFAULT NULL;

-- 2. Add indexes for performance and retention queries
CREATE INDEX IF NOT EXISTS ix_insurance_tenures_deleted_at ON insurance_tenures(deleted_at);
CREATE INDEX IF NOT EXISTS ix_insurance_tenures_purge_after ON insurance_tenures(purge_after);

-- 3. Cleanup existing orphan sessions previously marked status='trash' but file not trashed
-- Move their uploaded_files to deleted_at so they don't leak into active session lists
UPDATE uploaded_files u
SET deleted_at = NOW(),
    purge_after = NOW() + INTERVAL '30 days',
    status = 'deleted'
FROM sessions s
WHERE s.uploaded_file_id = u.id
  AND s.status = 'trash'
  AND u.deleted_at IS NULL;
