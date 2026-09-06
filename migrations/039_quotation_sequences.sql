-- Create table for yearly quotation reference sequences
CREATE TABLE IF NOT EXISTS quotation_sequences (
    year INT PRIMARY KEY,
    current_val BIGINT NOT NULL DEFAULT 0
);

-- Initialize year 2026 sequence starting after existing sessions
INSERT INTO quotation_sequences (year, current_val)
VALUES (2026, 147)
ON CONFLICT (year) DO NOTHING;

-- Backfill all existing sessions with chronological RL260000XXX references
WITH numbered_sessions AS (
    SELECT id, draft_id, ROW_NUMBER() OVER (ORDER BY created_at ASC) AS seq
    FROM sessions
)
UPDATE sessions s
SET quotation_ref = 'RL26' || LPAD(ns.seq::text, 7, '0')
FROM numbered_sessions ns
WHERE s.id = ns.id;

-- Sync quotation_drafts fields quotation_reference with session reference
WITH numbered_sessions AS (
    SELECT id, draft_id, ROW_NUMBER() OVER (ORDER BY created_at ASC) AS seq
    FROM sessions
)
UPDATE quotation_drafts d
SET fields = jsonb_set(
    COALESCE(d.fields, '{}'::jsonb),
    '{quotation_reference}',
    jsonb_build_object('value', 'RL26' || LPAD(ns.seq::text, 7, '0'), 'status', 'ready', 'message', '')
)
FROM numbered_sessions ns
WHERE d.id = ns.draft_id;
