export interface ComparisonMatrixProps {
  tenureId: string;
}

export interface TenureSpec {
  id: string;
  vehicle_no: string;
  is_plate_undetected?: boolean;
  tracking_by_chassis?: boolean;
  customer_name: string;
  ic_no?: string;
  formatted_ic?: string;
  birth_date?: string;
  customer_age?: number;
  customer_gender?: string;
  nric_state?: string;
  phone?: string;
  email?: string;
  address?: string;
  engine_no?: string;
  chassis_no?: string;
  manufacture_year?: number;
  seating_capacity?: string;
  coverage_start_date: string;
  coverage_end_date: string;
  coverage_period_formatted: string;
  expiry_month: string;
  status: string;
  road_tax: number;
  runner_fee: number;
  runner_fee_type?: string;
  fixed_costs_total: number;
  quotation_discount?: number;
  windscreen_target: number | null;
  ncd_percentage: number | null;
  engine_cc: string;
  car_brand?: string | null;
  vehicle_model: string;
  vehicle_type: string;
  winning_file_id?: string | null;
  winning_file_name?: string | null;
  policy_number?: string | null;
  covernote_session_id?: string | null;
}

export interface ComparisonEntry {
  id: string;
  tenure_id: string;
  session_id: string | null;
  company_name: string;
  company_id: string | null;
  sum_insured: number;
  valuation_type: string;
  motor_premium: number;
  rounded_motor_premium?: number | null;
  exact_motor_premium?: number | null;
  road_tax: number;
  runner_fee: number;
  discount?: number | null;
  effective_discount?: number | null;
  total_payable: number;
  rounded_total_payable?: number | null;
  exact_total_payable?: number | null;
  net_total_payable?: number;
  rounded_net_total_payable?: number;
  towing_limit: string;
  towing_km?: string;
  agreed_value: boolean;
  waiver_betterment: boolean;
  betterment_rate?: number;
  betterment_display?: string;
  excess: number;
  basic_figure_name?: string | null;
  basic_figure_amount?: number | null;
  rate_factor?: number | null;
  rate_factor_formatted?: string | null;
  rate_percentage: number | null;
  windscreen_sum_insured: number | null;
  special_perils: string | null;
  llp_llop: string | null;
  canonical_perils?: string[];
  canonical_perils_formatted?: string;
  is_recommended: boolean;
  is_manual: boolean;
  is_hidden?: boolean;
  manual_rank?: number | null;
  sort_order: number;
  rank?: number;
  version?: number;
  uploaded_at?: string;
  notes: string | null;
  quotation_ref?: string | null;
  source_quotation_no?: string | null;
  is_takaful?: boolean;
  ncd_percentage?: number | null;
  customer_name?: string | null;
  customer_address?: string | null;
  ic_or_brn?: string | null;
  vehicle_no?: string | null;
  engine_no?: string | null;
  chassis_no?: string | null;
  vehicle_year?: string | null;
  engine_cc?: string | null;
  vehicle_age?: number | null;
  detailed_perils?: Array<{
    name: string;
    coverage_limit?: string | number | null;
    premium_cost?: number;
    has_cost?: boolean;
    is_included?: boolean;
  }>;
  coverage_start_date?: string | null;
  coverage_end_date?: string | null;
  coverage_period_formatted?: string | null;
  uploaded_file_id?: string | null;
  original_filename?: string | null;
}

export interface ComparisonMatrixData {
  tenure: TenureSpec;
  entries: ComparisonEntry[];
  previous_policy: any;
  recommended_sum_insured: Record<string, number>;
  ncd: {
    current: number | null;
    next: number | null;
    current_period?: string;
    next_period?: string;
    has_previous_policy?: boolean;
  };
  pending_jobs_count?: number;
  vehicle_age?: number;
  upload_sessions?: Array<{
    session_id: string;
    batch_index: number;
    uploaded_at: string | null;
    quotes: Array<{
      session_id: string;
      company_name: string;
      version: number;
    }>;
  }>;
  duplicate_alerts?: Array<{
    id: string;
    session_id: string;
    company_name: string;
    original_session_id: string;
    original_version: number;
    original_date?: string | null;
    new_version: number;
    new_date?: string | null;
    file_name?: string;
    total_payable?: number;
    quotation_date?: string | null;
  }>;
  disqualified_documents?: Array<{
    id: string;
    session_id: string;
    file_name: string;
    reason: string;
    detected_reg_no?: string;
    expected_reg_no?: string;
  }>;
}

export function formatExpiryDateDisplay(tenure?: any, prevPolicy?: any): string {
  if (prevPolicy?.coverage_end_date) {
    const d = new Date(prevPolicy.coverage_end_date);
    if (!isNaN(d.getTime())) {
      const day = String(d.getDate()).padStart(2, "0");
      const month = String(d.getMonth() + 1).padStart(2, "0");
      return `${day}/${month}/${d.getFullYear()}`;
    }
  }
  if (tenure?.coverage_end_date) {
    const d = new Date(tenure.coverage_end_date);
    if (!isNaN(d.getTime())) {
      const day = String(d.getDate()).padStart(2, "0");
      const month = String(d.getMonth() + 1).padStart(2, "0");
      return `${day}/${month}/${d.getFullYear()}`;
    }
  }
  if (tenure?.expiry_month && tenure.expiry_month.includes("-")) {
    const [y, m] = tenure.expiry_month.split("-");
    if (y && m) return `${m.padStart(2, "0")}/${y}`;
  }
  return tenure?.expiry_month || "—";
}

export function formatLlpLlop(val: string | null | undefined): string {
  if (!val) return "Not Included";
  const trimmed = val.trim();
  if (
    !trimmed ||
    trimmed === "-" ||
    trimmed === "—" ||
    trimmed.toLowerCase() === "none" ||
    trimmed.toLowerCase() === "not included"
  ) {
    return "Not Included";
  }
  return trimmed;
}

export function isLlpLlopIncluded(val: string | null | undefined): boolean {
  if (!val) return false;
  const trimmed = val.trim().toLowerCase();
  return (
    trimmed !== "" &&
    trimmed !== "-" &&
    trimmed !== "—" &&
    trimmed !== "none" &&
    trimmed !== "not included"
  );
}
