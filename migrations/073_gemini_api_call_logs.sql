-- Migration 073: Gemini API Call Logs and Persistent Quota Tracking
-- Creates persistent call logging and daily usage tracking for Gemini API accounts.

CREATE TABLE IF NOT EXISTS gemini_api_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(100) NOT NULL,
    api_key_masked VARCHAR(50),
    model VARCHAR(100) NOT NULL,
    endpoint_slot VARCHAR(100),
    status_code INTEGER NOT NULL,
    is_success BOOLEAN NOT NULL DEFAULT true,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    candidate_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    local_date VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS ix_gemini_call_logs_local_date ON gemini_api_call_logs(local_date);
CREATE INDEX IF NOT EXISTS ix_gemini_call_logs_acc_date ON gemini_api_call_logs(account_id, local_date);
CREATE INDEX IF NOT EXISTS ix_gemini_call_logs_created_at ON gemini_api_call_logs(created_at);
