-- Migration 077: Restore Immutability Triggers, Partial Unique Vehicle Indexes & Enterprise Double-Entry Ledger Schema
-- Reverses destructive drop-triggers in 056/061, adds soft-archive support, and introduces immutable ACID ledger.

-- ============================================================================
-- 1. Soft-Archive & Immutability Restoration (Template & Catalog Revisions)
-- ============================================================================

ALTER TABLE public.template_revisions
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE public.benefit_catalog_revisions
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT false;

-- Re-establish ON DELETE RESTRICT on render_snapshots.template_revision_id (reversing 061 cascade)
ALTER TABLE public.render_snapshots
    DROP CONSTRAINT IF EXISTS render_snapshots_template_revision_id_fkey;

ALTER TABLE public.render_snapshots
    ADD CONSTRAINT render_snapshots_template_revision_id_fkey
    FOREIGN KEY (template_revision_id) REFERENCES public.template_revisions(id) ON DELETE RESTRICT;

-- Immutability guard for published template revisions
CREATE OR REPLACE FUNCTION prevent_published_template_revision_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.state = 'published' THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Cannot delete a published template revision. Soft-archive it instead.';
        ELSIF TG_OP = 'UPDATE' THEN
            IF NEW.config IS DISTINCT FROM OLD.config OR
               NEW.page_profile_id IS DISTINCT FROM OLD.page_profile_id OR
               NEW.revision_number IS DISTINCT FROM OLD.revision_number OR
               NEW.template_id IS DISTINCT FROM OLD.template_id THEN
                RAISE EXCEPTION 'Published template revisions are immutable; create a new revision instead.';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_template_revisions_immutability ON public.template_revisions;
CREATE TRIGGER trg_template_revisions_immutability
    BEFORE UPDATE OR DELETE ON public.template_revisions
    FOR EACH ROW
    EXECUTE FUNCTION prevent_published_template_revision_mutation();

-- ============================================================================
-- 2. Normalized Vehicle Identity (Partial Unique Indexes for Plates & Chassis)
-- ============================================================================

ALTER TABLE public.tracked_vehicles
    ADD COLUMN IF NOT EXISTS is_provisional BOOLEAN NOT NULL DEFAULT false,
    ALTER COLUMN vehicle_no DROP NOT NULL;

-- Drop unsafe global unique constraint that rejected unplated / temporary vehicles
ALTER TABLE public.tracked_vehicles
    DROP CONSTRAINT IF EXISTS tracked_vehicles_vehicle_no_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_tracked_vehicles_real_plate
    ON public.tracked_vehicles (UPPER(REPLACE(vehicle_no, ' ', '')))
    WHERE vehicle_no IS NOT NULL
      AND vehicle_no NOT IN ('UNPLATED', 'UNKNOWN', 'NEW', 'NONE', 'NA', 'N/A', '-');

CREATE INDEX IF NOT EXISTS idx_tracked_vehicles_chassis
    ON public.tracked_vehicles (UPPER(TRIM(chassis_no)))
    WHERE chassis_no IS NOT NULL AND TRIM(chassis_no) <> '';

-- ============================================================================
-- 3. Enterprise Double-Entry Ledger Schema
-- ============================================================================

-- Chart of Accounts
CREATE TABLE IF NOT EXISTS public.ledger_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(120) NOT NULL,
    account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('asset', 'liability', 'equity', 'revenue', 'expense')),
    normal_side VARCHAR(6) NOT NULL CHECK (normal_side IN ('debit', 'credit')),
    description TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Seed Canonical Chart of Accounts
INSERT INTO public.ledger_accounts (code, name, account_type, normal_side, description)
VALUES 
    ('1010-BANK-HLB', 'Hong Leong Bank Operating Account', 'asset', 'debit', 'Primary agency operating account for collections and disbursements'),
    ('1200-AR-CLIENT', 'Accounts Receivable - Client', 'asset', 'debit', 'Receivables owed by insured clients upon quote acceptance'),
    ('2100-AP-INSURER', 'Accounts Payable - Insurer', 'liability', 'credit', 'Net motor premium payable to underwriters'),
    ('4010-COMM-REV', 'Agency Commission Revenue', 'revenue', 'credit', 'Earned agency commission on closed motor policies'),
    ('4020-RUNNER-FEE', 'Runner & Handling Fee Revenue', 'revenue', 'credit', 'Agency runner fee revenue for JPJ road tax delivery'),
    ('5010-ROAD-TAX-EXP', 'JPJ Road Tax Settlement Expense', 'expense', 'debit', 'Direct JPJ road tax fee disbursed on behalf of client')
ON CONFLICT (code) DO NOTHING;

-- Invoices per Insurance Tenure
CREATE TABLE IF NOT EXISTS public.ledger_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenure_id UUID NOT NULL REFERENCES public.insurance_tenures(id) ON DELETE RESTRICT,
    invoice_no VARCHAR(40) UNIQUE NOT NULL,
    gross_premium NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    service_tax NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    stamp_duty NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    road_tax NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    runner_fee NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    discount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    total_receivable NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(24) NOT NULL DEFAULT 'issued' CHECK (status IN ('draft', 'issued', 'partially_paid', 'paid', 'void')),
    issued_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_ledger_invoices_tenure_id ON public.ledger_invoices (tenure_id);

-- Append-Only Journal Entry Headers
CREATE TABLE IF NOT EXISTS public.journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_no VARCHAR(40) UNIQUE NOT NULL,
    tenure_id UUID NULL REFERENCES public.insurance_tenures(id) ON DELETE RESTRICT,
    invoice_id UUID NULL REFERENCES public.ledger_invoices(id) ON DELETE RESTRICT,
    entry_date DATE NOT NULL,
    description TEXT NOT NULL,
    idempotency_key VARCHAR(120) UNIQUE NOT NULL,
    reverses_entry_id UUID NULL REFERENCES public.journal_entries(id) ON DELETE RESTRICT,
    is_posted BOOLEAN NOT NULL DEFAULT true,
    created_by UUID NULL REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_journal_entries_tenure_id ON public.journal_entries (tenure_id);
CREATE INDEX IF NOT EXISTS idx_journal_entries_invoice_id ON public.journal_entries (invoice_id);
CREATE INDEX IF NOT EXISTS idx_journal_entries_idempotency_key ON public.journal_entries (idempotency_key);

-- Balanced Journal Lines (Exact Decimal Money)
CREATE TABLE IF NOT EXISTS public.journal_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_entry_id UUID NOT NULL REFERENCES public.journal_entries(id) ON DELETE RESTRICT,
    account_id UUID NOT NULL REFERENCES public.ledger_accounts(id) ON DELETE RESTRICT,
    debit_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (debit_amount >= 0.00),
    credit_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (credit_amount >= 0.00),
    memo TEXT NULL,
    sequence_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CHECK ((debit_amount > 0.00 AND credit_amount = 0.00) OR (credit_amount > 0.00 AND debit_amount = 0.00))
);

CREATE INDEX IF NOT EXISTS idx_journal_lines_journal_entry_id ON public.journal_lines (journal_entry_id);
CREATE INDEX IF NOT EXISTS idx_journal_lines_account_id ON public.journal_lines (account_id);

-- Immutability Guard: Reject UPDATE and DELETE on posted financial journals
CREATE OR REPLACE FUNCTION prevent_posted_journal_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Posted financial ledger records are immutable; emit a reversing entry instead.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_posted_journal_mutation ON public.journal_entries;
CREATE TRIGGER trg_prevent_posted_journal_mutation
    BEFORE UPDATE OR DELETE ON public.journal_entries
    FOR EACH ROW
    EXECUTE FUNCTION prevent_posted_journal_mutation();

DROP TRIGGER IF EXISTS trg_prevent_journal_line_mutation ON public.journal_lines;
CREATE TRIGGER trg_prevent_journal_line_mutation
    BEFORE UPDATE OR DELETE ON public.journal_lines
    FOR EACH ROW
    EXECUTE FUNCTION prevent_posted_journal_mutation();

-- Deferrable Balanced Invariant Constraint: Enforce SUM(debit) == SUM(credit) > 0 at COMMIT
CREATE OR REPLACE FUNCTION verify_journal_entry_balanced()
RETURNS TRIGGER AS $$
DECLARE
    v_entry_id UUID;
    v_sum_debit NUMERIC(12,2);
    v_sum_credit NUMERIC(12,2);
BEGIN
    v_entry_id := COALESCE(NEW.journal_entry_id, OLD.journal_entry_id);
    SELECT COALESCE(SUM(debit_amount), 0.00), COALESCE(SUM(credit_amount), 0.00)
    INTO v_sum_debit, v_sum_credit
    FROM public.journal_lines
    WHERE journal_entry_id = v_entry_id;

    IF v_sum_debit <> v_sum_credit THEN
        RAISE EXCEPTION 'Journal entry % is unbalanced: total debits (RM %) does not equal total credits (RM %)',
            v_entry_id, v_sum_debit, v_sum_credit;
    END IF;
    IF v_sum_debit <= 0.00 THEN
        RAISE EXCEPTION 'Journal entry % has zero total debit amount.', v_entry_id;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_verify_journal_entry_balanced ON public.journal_lines;
CREATE CONSTRAINT TRIGGER trg_verify_journal_entry_balanced
    AFTER INSERT OR UPDATE OR DELETE ON public.journal_lines
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    EXECUTE FUNCTION verify_journal_entry_balanced();
