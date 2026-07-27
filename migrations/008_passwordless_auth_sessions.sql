-- Replace password/JWT authentication with hashed one-time codes and revocable server-side sessions.

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255) NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS auth_login_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_hash VARCHAR(64) NOT NULL,
    code_hash VARCHAR(64) NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 5 CHECK (max_attempts BETWEEN 1 AND 10),
    expires_at TIMESTAMPTZ NOT NULL,
    resend_available_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_login_codes_email_created ON auth_login_codes(email_hash, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_login_codes_user_id ON auth_login_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_login_codes_expires_at ON auth_login_codes(expires_at);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    last_activity_at TIMESTAMPTZ NOT NULL,
    idle_expires_at TIMESTAMPTZ NOT NULL,
    absolute_expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES users(id),
    user_agent VARCHAR(500),
    ip_address VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_auth_session_expiry CHECK (idle_expires_at <= absolute_expires_at)
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_idle_expires_at ON auth_sessions(idle_expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_absolute_expires_at ON auth_sessions(absolute_expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_revoked_at ON auth_sessions(revoked_at);

ALTER TABLE auth_login_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE auth_login_codes, auth_sessions FROM anon, authenticated;

COMMENT ON TABLE auth_login_codes IS 'Hashed, expiring one-time employee login challenges';
COMMENT ON TABLE auth_sessions IS 'Revocable server-side employee sessions; cookie tokens are stored only as hashes';

COMMIT;
