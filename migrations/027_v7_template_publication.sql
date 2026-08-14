-- v7 canonical fixed-page profile used by immutable template publication.

BEGIN;

INSERT INTO public.template_page_profiles (
    profile_key,
    name,
    width,
    height,
    unit,
    safe_margins,
    bleed,
    background_behavior,
    revision,
    status
)
VALUES (
    'a4',
    'A4',
    794,
    1123,
    'px',
    '{"top":24,"right":24,"bottom":24,"left":24}'::jsonb,
    '{}'::jsonb,
    'clip',
    1,
    'active'
)
ON CONFLICT (profile_key) DO NOTHING;

COMMIT;
