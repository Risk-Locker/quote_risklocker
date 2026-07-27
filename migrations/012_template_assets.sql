-- Store metadata for reusable template assets uploaded by admins.

BEGIN;

CREATE TABLE IF NOT EXISTS template_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploaded_by UUID REFERENCES users(id),
    label VARCHAR(255) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(120) NOT NULL,
    storage_provider VARCHAR(50) NOT NULL DEFAULT 'supabase',
    storage_bucket VARCHAR(160),
    storage_path VARCHAR(800) NOT NULL,
    storage_sha256 VARCHAR(64),
    size_bytes INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_template_assets_status ON template_assets(status);
CREATE INDEX IF NOT EXISTS idx_template_assets_uploaded_by ON template_assets(uploaded_by);

ALTER TABLE template_assets ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE template_assets FROM anon, authenticated;

COMMENT ON TABLE template_assets IS 'Reusable PNG/SVG assets for the template builder';

COMMIT;
