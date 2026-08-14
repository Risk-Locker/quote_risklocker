-- 032_catalog_upgrade_offering_kind.sql
-- The v7 catalog model treats "upgrade" as a first-class offering kind, but
-- the 024 check constraint omitted it. Widening the constraint keeps the
-- existing values valid.

ALTER TABLE catalog_offerings DROP CONSTRAINT catalog_offerings_offering_kind_check;

ALTER TABLE catalog_offerings ADD CONSTRAINT catalog_offerings_offering_kind_check
    CHECK (offering_kind IN ('base', 'upgrade', 'optional', 'package_component'));
