-- Durable worker heartbeat used by production readiness and operations.

BEGIN;

CREATE TABLE IF NOT EXISTS public.worker_heartbeats (
    worker_id VARCHAR(160) PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    state VARCHAR(40) NOT NULL DEFAULT 'idle',
    process_id INTEGER NOT NULL,
    release_id VARCHAR(160)
);

CREATE INDEX IF NOT EXISTS worker_heartbeats_heartbeat_idx
    ON public.worker_heartbeats(heartbeat_at DESC);

ALTER TABLE public.worker_heartbeats ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE public.worker_heartbeats FROM anon, authenticated;

COMMIT;
