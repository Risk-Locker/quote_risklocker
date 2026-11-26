-- 096_vehicle_plate_history.sql
-- Dated vehicle registration plate history for chassis-first vehicle tracking.
-- Additive only: preserves historical tenures and closed ledgers across plate assignments/transfers.

CREATE TABLE IF NOT EXISTS public.vehicle_plate_history (
    id UUID PRIMARY KEY,
    tracked_vehicle_id UUID NOT NULL REFERENCES public.tracked_vehicles(id) ON DELETE CASCADE,
    chassis_no VARCHAR(64) NULL,
    plate_no VARCHAR(64) NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_to TIMESTAMPTZ NULL,
    source_tenure_id UUID NULL REFERENCES public.insurance_tenures(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vehicle_plate_history_vehicle_from
    ON public.vehicle_plate_history (tracked_vehicle_id, effective_from DESC);

CREATE INDEX IF NOT EXISTS idx_vehicle_plate_history_chassis
    ON public.vehicle_plate_history (chassis_no);

CREATE INDEX IF NOT EXISTS idx_vehicle_plate_history_plate
    ON public.vehicle_plate_history (plate_no);
