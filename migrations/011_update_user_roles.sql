-- Update allowed user roles to super_admin, admin, staff, dev.

BEGIN;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;

UPDATE users SET role = 'staff' WHERE role = 'Staff';
UPDATE users SET role = 'admin' WHERE role = 'Admin';
UPDATE users SET role = 'staff' WHERE role = 'Manager';

ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('super_admin', 'admin', 'staff', 'dev'));

COMMIT;
