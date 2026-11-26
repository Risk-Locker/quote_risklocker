-- 097_backfill_chassis_vehicle_no_and_clean_labels.sql
-- Idempotent backfill:
-- 1. Clear field-label hallucinations in tracked_vehicles (engine_no, car_brand, car_model).
-- 2. Reconcile tracked_vehicles.vehicle_no to valid active tenure plate (seeding vehicle_plate_history)
--    or bare normalized chassis_no (>= 8 alnum chars).
-- 3. Sync active open insurance_tenures.vehicle_no from reconciled tracked_vehicles (preserving Close - Win / covernotes).
-- 4. Clean field-label hallucinations in active quotation_drafts.fields JSONB.

BEGIN;

-- 1. Clear field-label hallucinations on tracked_vehicles.engine_no
UPDATE public.tracked_vehicles
SET engine_no = NULL,
    updated_at = NOW()
WHERE engine_no IS NOT NULL
  AND UPPER(TRIM(engine_no)) IN (
      'CHASSIS NO', 'CHASSISNO', 'CHASSIS NUMBER', 'CHASSIS',
      'ENGINE NO', 'ENGINENO', 'ENGINE NUMBER', 'ENGINE',
      'NA', 'N/A', 'NONE', 'NIL', 'NOT STATED', 'NOTSTATED', 'UNKNOWN', '-'
  );

-- 2a. Clear field-label hallucinations on tracked_vehicles.car_brand
UPDATE public.tracked_vehicles
SET car_brand = NULL,
    updated_at = NOW()
WHERE car_brand IS NOT NULL
  AND UPPER(TRIM(car_brand)) IN (
      'VEHICLE MODEL', 'VEHICLEMODEL', 'VEHICLE MAKE', 'VEHICLEMAKE',
      'MAKE', 'MODEL', 'NA', 'N/A', 'NONE', 'NIL',
      'NOT STATED', 'NOTSTATED', 'UNKNOWN', '-'
  );

-- 2b. Strip accidental field-label prefixes from tracked_vehicles.car_model
UPDATE public.tracked_vehicles
SET car_model = NULLIF(
        TRIM(REGEXP_REPLACE(car_model, '^(?:vehicle\s+(?:model|make)\s*[:\-]?\s+|(?:model|make)\s*[:\-]\s+)', '', 'i')),
        ''
    ),
    updated_at = NOW()
WHERE car_model IS NOT NULL
  AND car_model ~* '^(?:vehicle\s+(?:model|make)\s+|(?:model|make)\s*[:\-]\s+)';

UPDATE public.tracked_vehicles
SET car_model = NULL,
    updated_at = NOW()
WHERE car_model IS NOT NULL
  AND UPPER(TRIM(car_model)) IN (
      'NOT STATED', 'NOTSTATED', 'NA', 'N/A', 'NONE', 'NIL',
      'UNKNOWN', 'VEHICLE MODEL', 'VEHICLE MAKE', 'OTHER COMMERCIAL'
  );

-- 3a. Recover tracked_vehicles.vehicle_no when an active linked tenure already holds a real plate
WITH recoverable_plates AS (
    SELECT DISTINCT ON (tv.id)
        tv.id AS tv_id,
        it.id AS tenure_id,
        tv.chassis_no AS raw_chassis,
        UPPER(REPLACE(TRIM(it.vehicle_no), ' ', '')) AS clean_plate
    FROM public.tracked_vehicles tv
    JOIN public.insurance_tenures it ON it.tracked_vehicle_id = tv.id
    WHERE it.deleted_at IS NULL
      AND it.vehicle_no IS NOT NULL
      AND UPPER(REPLACE(TRIM(it.vehicle_no), ' ', '')) ~ '^[A-Z]{1,3}[0-9]{1,4}[A-Z]?$'
      AND UPPER(TRIM(it.vehicle_no)) NOT IN (
          'VEHICLEMAKE', 'VEHICLEMODEL', 'NA', 'N/A', 'NONE', 'NIL',
          'UNKNOWN', 'UNREGISTERED', 'NEW', 'CUBICCAPACITY', 'NOTSTATED', 'UNPLATED'
      )
      AND (
          tv.vehicle_no IS NULL
          OR TRIM(tv.vehicle_no) = ''
          OR UPPER(TRIM(tv.vehicle_no)) IN (
              'VEHICLEMAKE', 'VEHICLEMODEL', 'NA', 'N/A', 'NONE', 'NIL',
              'UNKNOWN', 'UNREGISTERED', 'NEW', 'CUBICCAPACITY', 'NOTSTATED', 'NOT STATED', 'UNPLATED'
          )
          OR UPPER(TRIM(tv.vehicle_no)) LIKE 'CHASSIS%'
          OR UPPER(TRIM(tv.vehicle_no)) LIKE 'ENGINE%'
          OR UPPER(TRIM(tv.vehicle_no)) LIKE 'UNPLATED%'
      )
    ORDER BY tv.id, it.updated_at DESC NULLS LAST, it.created_at DESC
)
UPDATE public.tracked_vehicles tv
SET vehicle_no = rp.clean_plate,
    updated_at = NOW()
FROM recoverable_plates rp
WHERE tv.id = rp.tv_id
  AND NOT EXISTS (
      SELECT 1
      FROM public.tracked_vehicles other
      WHERE other.id <> tv.id
        AND UPPER(REPLACE(COALESCE(other.vehicle_no, ''), ' ', '')) = rp.clean_plate
  );

-- Seed initial VehiclePlateHistory row for recovered real plates when none exists yet
INSERT INTO public.vehicle_plate_history (
    id, tracked_vehicle_id, chassis_no, plate_no, effective_from, effective_to, source_tenure_id, created_at
)
SELECT
    gen_random_uuid(),
    tv.id,
    NULLIF(UPPER(REGEXP_REPLACE(COALESCE(tv.chassis_no, ''), '[^A-Za-z0-9]', '', 'g')), ''),
    UPPER(REPLACE(TRIM(tv.vehicle_no), ' ', '')),
    NOW(),
    NULL,
    (
        SELECT it.id
        FROM public.insurance_tenures it
        WHERE it.tracked_vehicle_id = tv.id
          AND it.deleted_at IS NULL
          AND UPPER(REPLACE(TRIM(it.vehicle_no), ' ', '')) = UPPER(REPLACE(TRIM(tv.vehicle_no), ' ', ''))
        ORDER BY it.updated_at DESC NULLS LAST, it.created_at DESC
        LIMIT 1
    ),
    NOW()
FROM public.tracked_vehicles tv
WHERE tv.vehicle_no IS NOT NULL
  AND UPPER(REPLACE(TRIM(tv.vehicle_no), ' ', '')) ~ '^[A-Z]{1,3}[0-9]{1,4}[A-Z]?$'
  AND NOT EXISTS (
      SELECT 1
      FROM public.vehicle_plate_history vph
      WHERE vph.tracked_vehicle_id = tv.id
  )
  AND EXISTS (
      SELECT 1
      FROM public.insurance_tenures it
      WHERE it.tracked_vehicle_id = tv.id
        AND it.deleted_at IS NULL
        AND UPPER(REPLACE(TRIM(it.vehicle_no), ' ', '')) = UPPER(REPLACE(TRIM(tv.vehicle_no), ' ', ''))
  );

-- 3b. For still-unplated vehicles with valid chassis_no (>= 8 alnum chars), set vehicle_no = bare uppercase chassis_no
UPDATE public.tracked_vehicles tv
SET vehicle_no = UPPER(REGEXP_REPLACE(tv.chassis_no, '[^A-Za-z0-9]', '', 'g')),
    updated_at = NOW()
WHERE tv.chassis_no IS NOT NULL
  AND LENGTH(REGEXP_REPLACE(tv.chassis_no, '[^A-Za-z0-9]', '', 'g')) >= 8
  AND (
      tv.vehicle_no IS NULL
      OR TRIM(tv.vehicle_no) = ''
      OR UPPER(TRIM(tv.vehicle_no)) IN (
          'VEHICLEMAKE', 'VEHICLEMODEL', 'NA', 'N/A', 'NONE', 'NIL',
          'UNKNOWN', 'UNREGISTERED', 'NEW', 'CUBICCAPACITY', 'NOTSTATED', 'NOT STATED', 'UNPLATED'
      )
      OR UPPER(TRIM(tv.vehicle_no)) LIKE 'CHASSIS%'
      OR UPPER(TRIM(tv.vehicle_no)) LIKE 'ENGINE%'
      OR UPPER(TRIM(tv.vehicle_no)) LIKE 'UNPLATED%'
  )
  AND NOT EXISTS (
      SELECT 1
      FROM public.tracked_vehicles other
      WHERE other.id <> tv.id
        AND UPPER(REPLACE(COALESCE(other.vehicle_no, ''), ' ', '')) =
            UPPER(REGEXP_REPLACE(tv.chassis_no, '[^A-Za-z0-9]', '', 'g'))
  );

-- 4. Sync active open insurance_tenures whose vehicle_no is a placeholder/label from their tracked_vehicle
UPDATE public.insurance_tenures it
SET vehicle_no = tv.vehicle_no,
    updated_at = NOW()
FROM public.tracked_vehicles tv
WHERE it.tracked_vehicle_id = tv.id
  AND it.deleted_at IS NULL
  AND COALESCE(it.stage, '') <> 'Close - Win'
  AND it.covernote_session_id IS NULL
  AND tv.vehicle_no IS NOT NULL
  AND TRIM(tv.vehicle_no) <> ''
  AND UPPER(TRIM(tv.vehicle_no)) NOT IN (
      'VEHICLEMAKE', 'VEHICLEMODEL', 'NA', 'N/A', 'NONE', 'NIL',
      'UNKNOWN', 'UNREGISTERED', 'NEW', 'CUBICCAPACITY', 'NOTSTATED', 'NOT STATED', 'UNPLATED'
  )
  AND UPPER(TRIM(tv.vehicle_no)) NOT LIKE 'CHASSIS%'
  AND UPPER(TRIM(tv.vehicle_no)) NOT LIKE 'ENGINE%'
  AND UPPER(TRIM(tv.vehicle_no)) NOT LIKE 'UNPLATED%'
  AND (
      it.vehicle_no IS NULL
      OR TRIM(it.vehicle_no) = ''
      OR UPPER(TRIM(it.vehicle_no)) IN (
          'VEHICLEMAKE', 'VEHICLEMODEL', 'NA', 'N/A', 'NONE', 'NIL',
          'UNKNOWN', 'UNREGISTERED', 'NEW', 'CUBICCAPACITY', 'NOTSTATED', 'NOT STATED', 'UNPLATED'
      )
      OR UPPER(TRIM(it.vehicle_no)) LIKE 'CHASSIS%'
      OR UPPER(TRIM(it.vehicle_no)) LIKE 'ENGINE%'
      OR UPPER(TRIM(it.vehicle_no)) LIKE 'UNPLATED%'
  );

-- 5a. Clean blocked vehicle_no in active quotation_drafts using normalized chassis_no when available
UPDATE public.quotation_drafts d
SET fields = CASE
        WHEN jsonb_typeof(d.fields->'vehicle_no') = 'object' THEN
            jsonb_set(
                d.fields,
                '{vehicle_no,value}',
                to_jsonb(UPPER(REGEXP_REPLACE(COALESCE(d.fields->'chassis_no'->>'value', ''), '[^A-Za-z0-9]', '', 'g'))),
                true
            )
        ELSE
            jsonb_set(
                d.fields,
                '{vehicle_no}',
                to_jsonb(UPPER(REGEXP_REPLACE(COALESCE(d.fields->'chassis_no'->>'value', ''), '[^A-Za-z0-9]', '', 'g'))),
                true
            )
    END,
    updated_at = NOW()
WHERE d.deleted_at IS NULL
  AND d.fields IS NOT NULL
  AND LENGTH(REGEXP_REPLACE(COALESCE(d.fields->'chassis_no'->>'value', ''), '[^A-Za-z0-9]', '', 'g')) >= 8
  AND (
      UPPER(TRIM(COALESCE(d.fields->'vehicle_no'->>'value', ''))) IN (
          '', 'VEHICLEMAKE', 'VEHICLEMODEL', 'NA', 'N/A', 'NONE', 'NIL',
          'UNKNOWN', 'UNREGISTERED', 'NEW', 'CUBICCAPACITY', 'NOTSTATED', 'NOT STATED', 'UNPLATED'
      )
      OR UPPER(TRIM(COALESCE(d.fields->'vehicle_no'->>'value', ''))) LIKE 'CHASSIS%'
      OR UPPER(TRIM(COALESCE(d.fields->'vehicle_no'->>'value', ''))) LIKE 'ENGINE%'
      OR UPPER(TRIM(COALESCE(d.fields->'vehicle_no'->>'value', ''))) LIKE 'UNPLATED%'
  );

-- 5b. Clear hallucinated engine_no in active quotation_drafts
UPDATE public.quotation_drafts d
SET fields = CASE
        WHEN jsonb_typeof(d.fields->'engine_no') = 'object' THEN
            jsonb_set(d.fields, '{engine_no,value}', '""'::jsonb, true)
        ELSE
            jsonb_set(d.fields, '{engine_no}', '""'::jsonb, true)
    END,
    updated_at = NOW()
WHERE d.deleted_at IS NULL
  AND d.fields IS NOT NULL
  AND UPPER(TRIM(COALESCE(d.fields->'engine_no'->>'value', ''))) IN (
      'CHASSIS NO', 'CHASSISNO', 'CHASSIS NUMBER', 'CHASSIS',
      'ENGINE NO', 'ENGINENO', 'ENGINE NUMBER', 'ENGINE',
      'NA', 'N/A', 'NONE', 'NIL', 'NOT STATED', 'NOTSTATED'
  );

-- 5c. Clear hallucinated car_brand in active quotation_drafts
UPDATE public.quotation_drafts d
SET fields = CASE
        WHEN jsonb_typeof(d.fields->'car_brand') = 'object' THEN
            jsonb_set(d.fields, '{car_brand,value}', '""'::jsonb, true)
        ELSE
            jsonb_set(d.fields, '{car_brand}', '""'::jsonb, true)
    END,
    updated_at = NOW()
WHERE d.deleted_at IS NULL
  AND d.fields IS NOT NULL
  AND UPPER(TRIM(COALESCE(d.fields->'car_brand'->>'value', ''))) IN (
      'VEHICLE MODEL', 'VEHICLEMODEL', 'VEHICLE MAKE', 'VEHICLEMAKE',
      'MAKE', 'MODEL', 'NA', 'N/A', 'NONE', 'NIL', 'NOT STATED', 'NOTSTATED'
  );

-- 5d. Strip 'Vehicle Model ' / 'Vehicle Make ' prefixes in active quotation_drafts.fields.car_model
UPDATE public.quotation_drafts d
SET fields = CASE
        WHEN jsonb_typeof(d.fields->'car_model') = 'object' THEN
            jsonb_set(
                d.fields,
                '{car_model,value}',
                to_jsonb(
                    TRIM(REGEXP_REPLACE(COALESCE(d.fields->'car_model'->>'value', ''), '^(?:vehicle\s+(?:model|make)\s*[:\-]?\s+|(?:model|make)\s*[:\-]\s+)', '', 'i'))
                ),
                true
            )
        ELSE
            d.fields
    END,
    updated_at = NOW()
WHERE d.deleted_at IS NULL
  AND d.fields IS NOT NULL
  AND jsonb_typeof(d.fields->'car_model') = 'object'
  AND COALESCE(d.fields->'car_model'->>'value', '') ~* '^(?:vehicle\s+(?:model|make)\s+|(?:model|make)\s*[:\-]\s+)';

COMMIT;
