-- Add truthful phase and elapsed-time support to durable jobs.

BEGIN;

ALTER TABLE public.jobs
    ADD COLUMN IF NOT EXISTS phase VARCHAR(80) NOT NULL DEFAULT 'queued',
    ADD COLUMN IF NOT EXISTS phase_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS phase_timestamps JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE public.jobs
SET phase = CASE state
        WHEN 'processing' THEN 'starting'
        WHEN 'completed' THEN 'completed'
        WHEN 'failed' THEN 'failed'
        WHEN 'cancelled' THEN 'cancelled'
        ELSE 'queued'
    END,
    phase_started_at = COALESCE(updated_at, created_at, NOW()),
    phase_timestamps = jsonb_build_object(
        CASE state
            WHEN 'processing' THEN 'starting'
            WHEN 'completed' THEN 'completed'
            WHEN 'failed' THEN 'failed'
            WHEN 'cancelled' THEN 'cancelled'
            ELSE 'queued'
        END,
        COALESCE(updated_at, created_at, NOW())
    )
WHERE phase_timestamps = '{}'::jsonb;

COMMIT;
