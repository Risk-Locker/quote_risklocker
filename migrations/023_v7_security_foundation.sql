-- v7 baseline security: one Primary Admin, durable rate-limit buckets, and Data API denial.

BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS users_single_primary_admin
    ON public.users ((role))
    WHERE role = 'super_admin';

CREATE TABLE IF NOT EXISTS public.rate_limit_buckets (
    scope VARCHAR(80) NOT NULL,
    key_hash CHAR(64) NOT NULL,
    window_started_at TIMESTAMPTZ NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0 CHECK (request_count >= 0),
    blocked_until TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (scope, key_hash)
);

CREATE INDEX IF NOT EXISTS rate_limit_buckets_blocked_until_idx
    ON public.rate_limit_buckets (blocked_until)
    WHERE blocked_until IS NOT NULL;

DO $$
DECLARE
    item RECORD;
BEGIN
    FOR item IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', item.schemaname, item.tablename);
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON TABLE %I.%I FROM anon, authenticated',
            item.schemaname,
            item.tablename
        );
    END LOOP;
END $$;

REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon, authenticated;

COMMIT;
