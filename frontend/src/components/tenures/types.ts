export type LedgerSortColumn =
  | "vehicle_no"
  | "coverage_period"
  | "stage"
  | "last_activity"
  | "created_at"
  | "pic";

export type LedgerDensity = "comfortable" | "compact";
export type LedgerOptionalColumn = "last_activity" | "created_at" | "pic";
export type LedgerAnchor = "all" | "expiring" | "starting";

export interface MonthSummaryByNum {
  month_num: number;
  month: string;
  total: number;
  start_count: number;
  end_count: number;
  cars: number;
  hit: number;
  miss: number;
  pending: number;
}

export interface YoYStatItem {
  year: string;
  total: number;
  cars: number;
  active: number;
  lost: number;
  growth_percentage: number | null;
}

export interface MonthItem {
  month: string;
  total: number;
  start_count: number;
  end_count: number;
  cars: number;
  hit: number;
  miss: number;
  pending: number;
}

export interface PicItem {
  id: string;
  name: string;
  type: "subagent" | "company_personnel" | "client_self" | "external_contact";
  agency_group: string | null;
  commission_rate: number;
  phone: string | null;
  email: string | null;
  whatsapp_number?: string | null;
  is_owner?: boolean;
}

export interface TenureRow {
  id: string;
  vehicle_no: string;
  customer_name: string;
  coverage_start_date: string;
  coverage_end_date: string;
  expiry_month: string;
  status: string;
  stage: string;
  business_type: string;
  pic_id: string | null;
  sub_agent_name: string;
  pic_agency: string;
  key_in_ucd: boolean;
  date_of_key_in: string | null;
  print_roadtax: string;
  roadtax_receipt: string;
  client_payment_received: boolean;
  agency_payment_done: boolean;
  comment: string;
  notes: string;
  client_preference_notes: string;
  days_in_stage: number;
  winning_company_id: string | null;
  winning_company_name: string;
  winning_quotation_ref: string | null;
  winning_file_id?: string | null;
  winning_file_name?: string | null;
  won_premium: number | null;
  miss_reason: string | null;
  loss_reason_category: string | null;
  road_tax: number;
  runner_fee: number;
  covernote_session_id?: string | null;
  policy_number?: string | null;
  covernote_policy?: {
    session_id: string;
    company: string;
    policy_number?: string | null;
    total_payable?: number | string | null;
    sum_insured?: number | string | null;
    coverage_start_date?: string | null;
    coverage_end_date?: string | null;
    coverage_period_formatted?: string | null;
    perils?: string | null;
    windscreen?: number | string | null;
    towing?: string | null;
    uploaded_file_id?: string | null;
    file_name?: string | null;
    is_previous_year_policy?: boolean;
    previous_policy_year?: number | null;
  } | null;
  is_covernote_issued?: boolean;
  has_selected_winner?: boolean;
  is_upcoming_renewal?: boolean;
  upcoming_renewal_start?: string | null;
  upcoming_renewal_end?: string | null;
  previous_tenure_id?: string | null;
  sourced_quotes: Array<{
    session_id: string;
    company: string;
    version: number;
    total_payable: string | null;
    sum_insured: string | null;
    uploaded_file_id?: string | null;
    file_name?: string | null;
    coverage_start_date?: string | null;
    coverage_end_date?: string | null;
    coverage_period_formatted?: string | null;
    is_winner?: boolean;
  }>;
  generated_quotations: Array<{
    session_id: string;
    quotation_ref: string;
    company: string;
    status: string;
  }>;
  customer_id?: string | null;
  customer_ic_no?: string | null;
  chassis_no?: string | null;
  engine_no?: string | null;
  car_brand?: string | null;
  car_model?: string | null;
  engine_cc?: string | null;
  manufacture_year?: number | null;
  is_projected?: boolean;
  is_hidden?: boolean;
  tenure_type?: string;
  superseded_by_tenure_id?: string | null;
  created_at?: string;
  is_main?: boolean;
  stage_history?: Record<string, string>;
  stage_updated_at?: string;
  last_activity_at?: string | null;
  is_discarded?: boolean;
  external_policy_start_date?: string | null;
  external_policy_end_date?: string | null;
  created_by_id?: string | null;
  created_by_email?: string | null;
  created_by_name?: string | null;
}

export interface VehicleGroup {
  vehicle_no: string;
  customer_name: string;
  customer_ic_no?: string | null;
  car_brand?: string | null;
  car_model?: string | null;
  engine_cc?: string | null;
  manufacture_year?: number | null;
  chassis_no?: string | null;
  engine_no?: string | null;
  mainTenure: TenureRow;
  tenures: TenureRow[];
}

export interface CalendarSession {
  session_id?: string;
  vehicle_no?: string;
  detected_company?: string;
  company?: string;
  customer_name?: string;
  quotation_date?: string;
  total_payable?: number | string;
  sum_insured?: number | string;
  created_at?: string;
  [key: string]: any;
}

export type CalendarEvent =
  | {
      type: "start" | "end";
      tenure: TenureRow;
    }
  | {
      type: "session";
      session: CalendarSession;
    };

export interface StageSummary {
  quotations: number;
  material_to_client: number;
  close_win: number;
  issue_policy: number;
  close_lose: number;
  others?: number;
  total: number;
}

export const STAGE_CONFIGS: Record<
  string,
  { label: string; bg: string; text: string; border: string; badge: string; isLost?: boolean }
> = {
  Quotations: {
    label: "Quotations",
    bg: "bg-blue-50/60",
    text: "text-blue-900",
    border: "border-blue-200",
    badge: "bg-blue-100 text-blue-800 border-blue-200",
  },
  "Material to Client": {
    label: "Material to Client",
    bg: "bg-purple-50/60",
    text: "text-purple-900",
    border: "border-purple-200",
    badge: "bg-purple-100 text-purple-800 border-purple-200",
  },
  "Close - Win": {
    label: "Close - Win",
    bg: "bg-emerald-50/60",
    text: "text-emerald-900",
    border: "border-emerald-200",
    badge: "bg-emerald-100 text-emerald-800 border-emerald-200",
  },
  "Issue Policy": {
    label: "Issue Policy",
    bg: "bg-amber-50/60",
    text: "text-amber-900",
    border: "border-amber-200",
    badge: "bg-amber-100 text-amber-800 border-amber-200",
  },
  "Close - Lose": {
    label: "Close - Lose",
    bg: "bg-rose-50/60",
    text: "text-rose-900",
    border: "border-rose-200",
    badge: "bg-rose-100 text-rose-800 border-rose-200",
    isLost: true,
  },
};

export const STAGE_ORDER = [
  "Quotations",
  "Material to Client",
  "Close - Win",
  "Issue Policy",
  "Close - Lose",
];

export const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const POPULAR_BRANDS = [
  "Perodua",
  "Proton",
  "Toyota",
  "Honda",
  "Nissan",
  "Mazda",
  "Mercedes-Benz",
  "BMW",
  "Hyundai",
  "Kia",
  "BYD",
  "Tesla",
  "Mitsubishi",
  "Subaru",
  "Volkswagen",
  "Audi",
  "Volvo",
  "Ford",
  "Isuzu",
  "Other",
];

export function formatDateSafe(dateStr?: string | null): string {
  if (!dateStr) return "—";
  const datePart = dateStr.split("T")[0];
  const parts = datePart.split("-");
  if (parts.length === 3) {
    const [y, m, d] = parts;
    const monthIdx = parseInt(m, 10) - 1;
    const monthName = MONTH_NAMES[monthIdx] || m;
    return `${parseInt(d, 10)} ${monthName} ${y}`;
  }
  return dateStr;
}

export function formatDateTimeSafe(dateStr?: string | null): string {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleString("en-MY", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return dateStr;
  }
}

export function formatRelativeTime(dateStr?: string | null): string {
  if (!dateStr) return "";
  const diffSec = Math.max(0, Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000));
  if (diffSec < 5) return "Just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  const diffDays = Math.floor(diffHour / 24);
  return `${diffDays}d ago`;
}
