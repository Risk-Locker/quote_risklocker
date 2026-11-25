-- Migration 094: Allow paused_quota and paused_user in jobs.state check constraint.

BEGIN;

ALTER TABLE public.jobs
    DROP CONSTRAINT IF EXISTS jobs_state_check;

ALTER TABLE public.jobs
    ADD CONSTRAINT jobs_state_check
    CHECK (state IN ('queued', 'processing', 'paused_quota', 'paused_user', 'completed', 'failed', 'cancelled'));

COMMIT;
