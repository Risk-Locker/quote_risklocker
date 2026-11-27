export type CopilotToolStep = {
  step_id: string;
  status: "running" | "done" | "error";
  tool: string;
  label: string;
  sql?: string | null;
  row_count?: number | null;
  elapsed_ms?: number | null;
};

export type CopilotVerifiedLink = {
  kind: "ledger_batch" | "comparison" | "ledger" | "session" | "client" | string;
  label: string;
  href: string;
};

export type CopilotArtifactPreview = {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  totals?: Record<string, number>;
  truncated?: boolean;
  elapsed_ms?: number;
};

export type CopilotArtifact = {
  id: string;
  thread_id: string;
  message_id?: string | null;
  kind: string;
  filename: string;
  mime_type: string;
  row_count: number;
  size_bytes: number;
  preview: CopilotArtifactPreview;
  download_url: string;
  expires_at?: string | null;
  created_at?: string | null;
};

export type CopilotThread = {
  id: string;
  user_id?: string;
  owner_name?: string | null;
  owner_email?: string | null;
  owner_role?: string | null;
  title: string;
  is_pinned: boolean;
  anchor_type?: "tenure" | "session" | "vehicle" | "client" | string | null;
  anchor_id?: string | null;
  anchor_label?: string | null;
  total_tokens: number;
  has_summary: boolean;
  last_message_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CopilotMessage = {
  id: string;
  thread_id: string;
  role: "user" | "assistant";
  content_markdown: string;
  tool_trace: CopilotToolStep[];
  verified_links: CopilotVerifiedLink[];
  action_cards: Array<Record<string, any>>;
  artifacts: CopilotArtifact[];
  prompt_tokens?: number;
  candidate_tokens?: number;
  total_tokens?: number;
  model_used?: string | null;
  feedback?: "up" | "down" | null;
  created_at?: string | null;
  isStreaming?: boolean;
};

export type CopilotBarrelStatus = {
  lane_id: string;
  model: string;
  account_id: string;
  account_label: string;
  scope: string;
  rpm_used: number;
  rpm_limit: number;
  rpm_remaining: number;
  tpm_used: number;
  tpm_limit: number;
  tpm_remaining: number;
  rpd_used: number;
  rpd_limit: number;
  in_flight_count: number;
  in_flight_tokens: number;
  reload_in_sec: number;
  status: string;
};

export type CopilotQueueStatus = {
  reason: "fair_queue" | "barrel_reload" | string;
  position?: number;
  active_users?: number;
  inflight_turns?: number;
  wait_seconds?: number;
  estimated_tokens?: number;
};

export type CopilotAdminUser = {
  id: string;
  name: string;
  email: string;
  role: string;
  status: string;
  thread_count: number;
  last_active_at?: string | null;
  tokens_used_today: number;
  is_self: boolean;
};

export type CopilotUserQuota = {
  enabled: boolean;
  turns_used: number;
  turns_limit: number;
  turns_remaining: number;
  tokens_used: number;
  tokens_limit: number;
  tokens_remaining: number;
  is_exhausted: boolean;
  pt_cycle_date: string;
  warn_turn_tokens?: number;
  max_tokens_per_turn?: number;
  max_input_tokens_per_turn?: number;
  barrels?: CopilotBarrelStatus[];
  dedicated_copilot_keys_count?: number;
};

export type CopilotPageContext = {
  pathname: string;
  anchor_type?: "tenure" | "session" | "vehicle" | "client" | null;
  anchor_id?: string | null;
  anchor_label?: string | null;
};

export type CopilotDrawerMode = "compact" | "wide" | "modal";
