-- Replace passwordless login codes with password authentication.

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255) NOT NULL DEFAULT '';

-- Remove the named @risklocker.com constraint; accounts are now created by the super admin or admin users.
ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_risklocker_email;

-- Drop the one-time login code table; sessions remain for cookie-based authentication.
DROP TABLE IF EXISTS auth_login_codes CASCADE;

COMMIT;
