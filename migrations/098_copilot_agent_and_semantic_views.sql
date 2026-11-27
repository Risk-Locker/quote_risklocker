-- Migration 098: Enterprise Agentic Copilot Tables, Fleet Workload Telemetry Columns, and 6 Read-Only Semantic Views.

BEGIN;

-- 1. Persistent Copilot Threads (Chat Inbox Sessions)
CREATE TABLE IF NOT EXISTS public.copilot_threads (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'New Chat',
    is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
    anchor_type VARCHAR(40),
    anchor_id VARCHAR(120),
    anchor_label VARCHAR(255),
    compacted_summary TEXT,
    compacted_up_to_message_id UUID,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    purge_after TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_copilot_threads_user_inbox
    ON public.copilot_threads (user_id, deleted_at, is_pinned DESC, last_message_at DESC);

-- 2. Append-only Copilot Messages
CREATE TABLE IF NOT EXISTS public.copilot_messages (
    id UUID PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES public.copilot_threads(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content_markdown TEXT NOT NULL DEFAULT '',
    tool_trace_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    verified_links_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    action_cards_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    candidate_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    model_used VARCHAR(100),
    feedback VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_copilot_messages_thread_created
    ON public.copilot_messages (thread_id, created_at ASC);

-- 3. Copilot Artifacts (Excel / Table Exports)
CREATE TABLE IF NOT EXISTS public.copilot_artifacts (
    id UUID PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES public.copilot_threads(id) ON DELETE CASCADE,
    message_id UUID REFERENCES public.copilot_messages(id) ON DELETE SET NULL,
    owner_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    kind VARCHAR(30) NOT NULL DEFAULT 'xlsx',
    filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(120) NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    storage_path VARCHAR(800),
    preview_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    sql_fingerprint VARCHAR(64),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_copilot_artifacts_thread_created
    ON public.copilot_artifacts (thread_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_copilot_artifacts_owner_created
    ON public.copilot_artifacts (owner_id, created_at DESC);

-- Lock down new tables from Supabase PostgREST anon/authenticated roles
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['copilot_threads', 'copilot_messages', 'copilot_artifacts'] LOOP
        BEGIN
            EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon, authenticated', tbl);
        EXCEPTION WHEN undefined_object THEN
            NULL;
        END;
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl);
    END LOOP;
END $$;

-- 4. Additive AI Fleet Governance & Purpose Separation Columns
ALTER TABLE public.gemini_api_call_logs
    ADD COLUMN IF NOT EXISTS purpose VARCHAR(40) NOT NULL DEFAULT 'extraction';

ALTER TABLE public.gemini_api_call_logs
    ADD COLUMN IF NOT EXISTS actor_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_gemini_call_logs_purpose_date
    ON public.gemini_api_call_logs (purpose, local_date);

CREATE INDEX IF NOT EXISTS ix_gemini_call_logs_actor_date
    ON public.gemini_api_call_logs (actor_user_id, local_date);

ALTER TABLE public.ai_fleet_lanes
    ADD COLUMN IF NOT EXISTS copilot_rpd_used INTEGER NOT NULL DEFAULT 0;

ALTER TABLE public.ai_fleet_lanes
    ADD COLUMN IF NOT EXISTS interactive_yield_until DOUBLE PRECISION;

-- 5. Six Curated Read-Only Semantic Views (pre-filtered active rows, zero secrets/raw NRIC)
CREATE OR REPLACE VIEW public.ai_v_motor_ledger AS
SELECT
    t.id AS tenure_id,
    t.tracked_vehicle_id,
    COALESCE(NULLIF(TRIM(t.vehicle_no), ''), v.vehicle_no) AS vehicle_no,
    t.customer_id,
    t.customer_name,
    v.car_brand,
    v.car_model,
    v.engine_cc,
    v.manufacture_year,
    v.chassis_no,
    t.coverage_start_date,
    t.coverage_end_date,
    t.expiry_month,
    EXTRACT(YEAR FROM t.coverage_start_date)::integer AS policy_year,
    t.stage,
    t.status,
    t.business_type,
    ic.name AS winning_company,
    t.winning_quotation_ref,
    t.won_premium,
    t.road_tax,
    t.runner_fee,
    t.include_road_tax,
    t.include_runner_fee,
    t.ncd_percentage,
    t.motor_discount_pct,
    t.quotation_discount,
    pic.name AS pic_name,
    pic.type AS pic_type,
    pic.agency_group,
    t.sub_agent_name,
    t.loss_reason_category,
    t.miss_reason,
    t.policy_number,
    t.covernote_session_id,
    t.is_projected,
    t.is_hidden,
    t.client_payment_received,
    t.agency_payment_done,
    t.key_in_ucd,
    t.print_roadtax,
    t.comment,
    t.created_at,
    t.updated_at
FROM public.insurance_tenures t
LEFT JOIN public.tracked_vehicles v ON v.id = t.tracked_vehicle_id
LEFT JOIN public.person_in_charge pic ON pic.id = t.pic_id
LEFT JOIN public.insurance_companies ic ON ic.id = t.winning_company_id
WHERE t.deleted_at IS NULL
  AND t.is_discarded = FALSE;

CREATE OR REPLACE VIEW public.ai_v_comparison_quotes AS
SELECT
    e.id AS entry_id,
    e.tenure_id,
    e.session_id,
    COALESCE(NULLIF(TRIM(t.vehicle_no), ''), v.vehicle_no) AS vehicle_no,
    t.customer_name,
    v.car_brand,
    v.car_model,
    t.coverage_start_date,
    t.coverage_end_date,
    t.expiry_month,
    EXTRACT(YEAR FROM t.coverage_start_date)::integer AS policy_year,
    t.stage AS tenure_stage,
    e.company_name,
    e.sum_insured,
    e.valuation_type,
    e.motor_premium,
    e.road_tax,
    e.runner_fee,
    e.total_payable,
    e.discount,
    e.towing_limit,
    e.towing_km,
    e.agreed_value,
    e.waiver_betterment,
    e.betterment_rate,
    e.betterment_display,
    e.excess,
    e.rate_percentage,
    e.windscreen_sum_insured,
    e.special_perils,
    e.llp,
    e.llop,
    e.llp_llop,
    e.personal_accident,
    e.rank,
    e.manual_rank,
    e.is_recommended,
    e.is_manual,
    e.notes,
    e.uploaded_at
FROM public.tenure_comparison_entries e
JOIN public.insurance_tenures t ON t.id = e.tenure_id
LEFT JOIN public.tracked_vehicles v ON v.id = t.tracked_vehicle_id
WHERE t.deleted_at IS NULL
  AND t.is_discarded = FALSE
  AND e.is_hidden = FALSE;

CREATE OR REPLACE VIEW public.ai_v_vehicles_plates AS
SELECT
    v.id AS tracked_vehicle_id,
    v.vehicle_no,
    ph.plate_no AS historical_plate_no,
    ph.effective_from AS plate_effective_from,
    ph.effective_to AS plate_effective_to,
    v.car_brand,
    v.car_model,
    v.engine_cc,
    v.manufacture_year,
    v.chassis_no,
    v.customer_id,
    ca.canonical_name AS customer_name,
    ca.entity_type,
    COALESCE(ca.is_fleet, FALSE) AS is_fleet
FROM public.tracked_vehicles v
LEFT JOIN public.customer_accounts ca ON ca.id = v.customer_id
LEFT JOIN public.vehicle_plate_history ph ON ph.tracked_vehicle_id = v.id;

CREATE OR REPLACE VIEW public.ai_v_clients_fleet AS
SELECT
    ca.id AS customer_id,
    ca.canonical_name,
    ca.entity_type,
    ca.id_type,
    CASE
        WHEN ca.id_number IS NULL OR LENGTH(ca.id_number) <= 4 THEN '****'
        ELSE REPEAT('*', GREATEST(0, LENGTH(ca.id_number) - 4)) || RIGHT(ca.id_number, 4)
    END AS masked_id_number,
    ca.phone,
    ca.email,
    ca.is_fleet,
    COUNT(DISTINCT tv.id)::integer AS vehicle_count,
    COUNT(DISTINCT t.id) FILTER (WHERE t.deleted_at IS NULL AND t.is_discarded = FALSE)::integer AS tenure_count,
    COUNT(DISTINCT t.id) FILTER (WHERE t.deleted_at IS NULL AND t.is_discarded = FALSE AND t.stage = 'Hit')::integer AS active_hit_count,
    ca.created_at
FROM public.customer_accounts ca
LEFT JOIN public.tracked_vehicles tv ON tv.customer_id = ca.id
LEFT JOIN public.insurance_tenures t ON t.customer_id = ca.id
GROUP BY ca.id, ca.canonical_name, ca.entity_type, ca.id_type, ca.id_number, ca.phone, ca.email, ca.is_fleet, ca.created_at;

CREATE OR REPLACE VIEW public.ai_v_sessions AS
SELECT
    s.id AS session_id,
    s.draft_id,
    s.tenure_id,
    s.tracked_vehicle_id,
    s.customer_id,
    s.document_type,
    s.detected_company,
    s.quotation_ref,
    s.quotation_status,
    s.status,
    s.policy_number,
    s.coverage_start_date,
    s.coverage_end_date,
    uf.original_filename AS filename,
    s.created_at
FROM public.sessions s
JOIN public.quotation_drafts d ON d.id = s.draft_id
JOIN public.uploaded_files uf ON uf.id = s.uploaded_file_id
WHERE d.deleted_at IS NULL
  AND uf.deleted_at IS NULL
  AND s.is_test = FALSE;

CREATE OR REPLACE VIEW public.ai_v_insurer_catalogs AS
SELECT
    ic.name AS company_name,
    bc.name AS catalog_name,
    bc.engine_type,
    con.concept_key,
    con.label AS concept_label,
    co.offering_kind,
    co.role,
    co.display_value,
    co.description_override,
    con.description AS concept_description
FROM public.benefit_catalogs bc
JOIN public.insurance_companies ic ON ic.id = bc.company_id
JOIN public.benefit_catalog_revisions bcr ON bcr.catalog_id = bc.id
JOIN public.catalog_offerings co ON co.catalog_revision_id = bcr.id
JOIN public.benefit_concepts con ON con.id = co.concept_id
WHERE bcr.state = 'published'
  AND bcr.is_archived = FALSE
  AND co.status = 'active';

COMMIT;
