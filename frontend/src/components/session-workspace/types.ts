export type ScalarDecision = "confirm" | "edit" | "clear" | "keep_check_needed";

export type WorkspaceField = {
  value?: string | null;
  status: string;
  message?: string;
  decision?: { decision: ScalarDecision } | null;
};

export type GenerationBlocker = { code: string; path: string; message: string };

export type BenefitCardSummary = {
  card_key: string;
  selection_id: string | null;
  offering_id: string;
  offering_key: string;
  concept_id: string;
  concept_key: string;
  label: string;
  value: string;
  cost_status: string | null;
  branch_key?: string | null;
  asset_id?: string | null;
  asset_url?: string | null;
  is_detected?: boolean;
  group_id?: string | null;
  sort_order?: number;
  typed_value?: Record<string, unknown> | null;
  price?: { amount?: number | string; currency?: string } | null;
  optional_price?: { amount?: number | string; currency?: string } | null;
  initial_price?: { amount?: number | string; currency?: string } | null;
  detected_cost?: string | number | null;
  detected_limit?: string | number | null;
};

export type WorkspaceCapabilities = {
  can_edit_fields: boolean;
  can_edit_selections: boolean;
  can_edit_layout: boolean;
  can_generate: boolean;
  can_manage_catalogs: boolean;
  can_manage_templates: boolean;
  can_manage_assets: boolean;
  can_view_all_records: boolean;
  can_manage_users: boolean;
  can_manage_security: boolean;
  can_view_audit: boolean;
  can_manage_ip_controls: boolean;
  can_transfer_primary_admin: boolean;
};

export type WorkspaceSnapshot = {
  session_id: string;
  draft_id: string;
  uploaded_file_id: string;
  revision: number;
  status: string;
  fields: Record<string, WorkspaceField>;
  benefits: Array<Record<string, unknown> & { id: string; selection_key: string; label?: string | null; state: string; cost_status: string }>;
  benefit_cards: {
    current_benefits: BenefitCardSummary[];
    available_addons: BenefitCardSummary[];
    groups?: Array<{ plan_id: string; plan_key: string; plan_label: string; cards: BenefitCardSummary[] }>;
  };
  extras: Array<{ selection_id: string; label: string; price?: { amount?: number | string; currency?: string }; sort_order?: number }>;
  total_premium_adjusted: string;
  packs: Array<{
    package_id: string;
    package_key: string;
    name: string;
    plans: Array<{
      plan_id: string;
      plan_key: string;
      name: string;
      sort_order: number;
      members: Array<{ offering_id: string; label: string; typed_value_override?: Record<string, unknown> | null }>;
    }>;
  }>;
  package_tiers: Array<{
    package_id: string;
    package_key: string;
    name: string;
    sort_order: number;
    catalog_id: string;
    catalog_revision_id: string;
    defaults_count: number;
    addons_count: number;
    is_current: boolean;
  }>;
  source_lines: Array<Record<string, unknown> & {
    source_line_id: string;
    raw_label: string;
    disposition: string;
    candidate_mappings: Array<{ concept_id: string; label: string; matched_alias: string }>;
    extracted_value: Record<string, unknown> | null;
  }>;
  pinned: Record<string, string | null>;
  pinned_names: { company_name: string | null; product_name: string | null; tier_name: string | null; package_name?: string | null };
  hierarchy?: {
    company_name?: string | null;
    product_name?: string | null;
    vehicle_category?: string | null;
    segment?: string | null;
    coverage_type?: string | null;
    car_model?: string | null;
  };
  catalog: {
    defaults: Array<{ offering_id: string; label: string; value: string }>;
    addons: Array<{ offering_id: string; label: string; value: string }>;
  };
  template: { id: string; revision_id: string; revision_number: number; config_hash: string } | null;
  layout_override: Record<string, unknown> | null;
  layout_binding: { template_id: string | null; template_revision_id: string | null; base_hash: string | null };
  generation_blockers: GenerationBlocker[];
  versions: Array<{ id: string; version_number: number; draft_revision: number; stale: boolean; generated_at: string }>;
  extracted_benefits_section?: {
    detected_package?: { name: string; matching_package_id: string | null; is_active_tier: boolean };
    total_optional_cover_amount?: string;
    extras?: Array<{
      id: string;
      label: string;
      raw_text: string;
      coverage_limit?: string;
      cost?: string;
      is_optional_cover?: boolean;
      concept_key?: string;
      concept_id?: string | null;
      is_applied?: boolean;
      selection_id?: string | null;
      source?: string;
    }>;
    detected_packs?: Array<{ package_name: string; plan_name?: string; raw_text?: string }>;
  };
  capabilities: WorkspaceCapabilities;
};

export type WorkspaceOperation = Record<string, unknown> & { op: string };

export type MutationState = {
  dirty: boolean;
  dirtyPaths: string[];
  saving: boolean;
  saveError: string | null;
  lastSavedAt: string | null;
};
