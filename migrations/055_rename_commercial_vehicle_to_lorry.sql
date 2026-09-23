-- Migration 055: Rename "Commercial Vehicle" display label to "Lorry"
-- Retains category_key = 'commercial_vehicle' intact for foreign keys, constraints, and queries

UPDATE vehicle_categories
SET name = 'Lorry'
WHERE category_key = 'commercial_vehicle';
