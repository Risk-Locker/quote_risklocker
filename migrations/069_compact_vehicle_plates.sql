-- Migration 069: Enforce compact vehicle plate numbers without spaces
-- 1. Strip spaces from tracked_vehicles
UPDATE tracked_vehicles
SET vehicle_no = UPPER(REPLACE(vehicle_no, ' ', ''))
WHERE vehicle_no LIKE '% %';

-- 2. Strip spaces from insurance_tenures
UPDATE insurance_tenures
SET vehicle_no = UPPER(REPLACE(vehicle_no, ' ', ''))
WHERE vehicle_no LIKE '% %';
