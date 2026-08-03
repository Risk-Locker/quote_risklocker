-- Migration: Add styling columns to our_special_variants
-- Description: border_width, border_color, and shadow for variant card design

ALTER TABLE our_special_variants ADD COLUMN IF NOT EXISTS border_width VARCHAR(20);
ALTER TABLE our_special_variants ADD COLUMN IF NOT EXISTS border_color VARCHAR(50);
ALTER TABLE our_special_variants ADD COLUMN IF NOT EXISTS shadow VARCHAR(20);
