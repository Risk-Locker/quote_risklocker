-- Migration 093: Persistent 2D AI Fleet Lanes, Live Fleet Event Log, and Server-Backed Upload Runs (Staging Batches).

BEGIN;

CREATE TABLE IF NOT EXISTS public.ai_fleet_lanes (
    lane_id VARCHAR(160) PRIMARY KEY,
    account_id VARCHAR(100) NOT NULL,
    api_key_masked VARCHAR(50),
    model VARCHAR(100) NOT NULL,
    rpm_limit INTEGER NOT NULL DEFAULT 13,
    tpm_limit INTEGER NOT NULL DEFAULT 200000,
    rpd_limit INTEGER NOT NULL DEFAULT 480,
    in_flight_count INTEGER NOT NULL DEFAULT 0,
    in_flight_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    recent_calls_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    recent_tokens_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    rpd_used INTEGER NOT NULL DEFAULT 0,
    pt_cycle_date VARCHAR(10) NOT NULL,
    last_dispatched_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    cooling_until DOUBLE PRECISION,
    global_pause_until DOUBLE PRECISION,
    status VARCHAR(40) NOT NULL DEFAULT 'ready',
    last_error TEXT,
    last_latency_ms INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ai_fleet_lanes_account_model
    ON public.ai_fleet_lanes (account_id, model);

CREATE TABLE IF NOT EXISTS public.upload_runs (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    title VARCHAR(255) NOT NULL,
    mode VARCHAR(30) NOT NULL DEFAULT 'bulk',
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    tenure_id UUID REFERENCES public.insurance_tenures(id) ON DELETE SET NULL,
    is_test BOOLEAN NOT NULL DEFAULT FALSE,
    total_files INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_upload_runs_owner_created
    ON public.upload_runs (owner_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_upload_runs_status
    ON public.upload_runs (status);

CREATE TABLE IF NOT EXISTS public.ai_fleet_events (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level VARCHAR(20) NOT NULL DEFAULT 'info',
    event_type VARCHAR(50) NOT NULL,
    lane_id VARCHAR(160),
    account_id VARCHAR(100),
    model VARCHAR(100),
    job_id UUID,
    upload_run_id UUID,
    filename VARCHAR(255),
    message TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_ai_fleet_events_created_at
    ON public.ai_fleet_events (created_at DESC);

CREATE INDEX IF NOT EXISTS ix_ai_fleet_events_upload_run_id
    ON public.ai_fleet_events (upload_run_id);

CREATE INDEX IF NOT EXISTS ix_ai_fleet_events_job_id
    ON public.ai_fleet_events (job_id);

ALTER TABLE public.jobs
    ADD COLUMN IF NOT EXISTS upload_run_id UUID REFERENCES public.upload_runs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_jobs_upload_run_id
    ON public.jobs (upload_run_id);

ALTER TABLE public.jobs
    ADD COLUMN IF NOT EXISTS paused_reason VARCHAR(120);

ALTER TABLE public.sessions
    ADD COLUMN IF NOT EXISTS upload_run_id UUID REFERENCES public.upload_runs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_sessions_upload_run_id
    ON public.sessions (upload_run_id);

COMMIT;
