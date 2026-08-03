-- Migration: Create our_specials and our_special_variants tables
-- Description: Replaces the flat benefit_options model with a parent-child structure
-- Existing benefit_options rows are preserved as inactive

UPDATE benefit_options SET status = 'inactive';

CREATE TABLE IF NOT EXISTS our_specials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label VARCHAR(255) NOT NULL,
    category VARCHAR(10) NOT NULL CHECK (category IN ('FOC', 'Add-on')),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_our_specials_category ON our_specials(category);
CREATE INDEX IF NOT EXISTS idx_our_specials_status ON our_specials(status);

COMMENT ON TABLE our_specials IS 'Parent Our Specials grouped by category (FOC or Add-on)';
COMMENT ON COLUMN our_specials.category IS 'Visual grouping only: FOC or Add-on. No business logic depends on this value.';

CREATE TABLE IF NOT EXISTS our_special_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    special_id UUID NOT NULL REFERENCES our_specials(id) ON DELETE CASCADE,
    label VARCHAR(255) NOT NULL,
    secondary_label VARCHAR(255),
    value_text VARCHAR(255),
    icon_asset_id VARCHAR(255),
    shape VARCHAR(50),
    bg_color VARCHAR(50),
    text_color VARCHAR(50),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_our_special_variants_special_id ON our_special_variants(special_id);
CREATE INDEX IF NOT EXISTS idx_our_special_variants_status ON our_special_variants(status);

COMMENT ON TABLE our_special_variants IS 'Individual variant cards under a parent Our Special';
COMMENT ON COLUMN our_special_variants.special_id IS 'FK to our_specials.id with CASCADE delete';
