"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";

export type LedgerSortColumn =
  | "vehicle_no"
  | "coverage_period"
  | "stage"
  | "last_activity"
  | "created_at"
  | "pic";

function formatRelativeTime(dateStr?: string | null): string {
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
import {
  CalendarBlank,
  Car,
  MagnifyingGlass,
  ArrowsClockwise,
  CheckCircle,
  XCircle,
  Clock,
  ArrowRight,
  FilePdf,
  CaretLeft,
  CaretRight,
  CaretDown,
  CaretUp,
  Table,
  Columns,
  ListDashes,
  CalendarCheck,
  ArrowSquareOut,
  UserCheck,
  Users,
  Check,
  Warning,
  Archive,
  PencilSimple,
  NotePencil,
  Tag,
  CurrencyDollar,
  Sparkle,
  Plus,
  Trash,
  TrendUp,
  UploadSimple,
} from "@phosphor-icons/react";
import { api, fileUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TenureTimelineDrawer } from "@/components/tenures/tenure-timeline-drawer";
import { EditVehicleDealModal } from "@/components/tenures/edit-vehicle-deal-modal";
import { getVehicleDisplayName } from "@/lib/vehicle-utils";

export interface YoYStatItem {
  year: string;
  total: number;
  cars: number;
  active: number;
  lost: number;
  growth_percentage: number | null;
}

export function formatDateSafe(dateStr?: string | null): string {
  if (!dateStr) return "—";
  const datePart = dateStr.split("T")[0];
  const parts = datePart.split("-");
  if (parts.length === 3) {
    const [y, m, d] = parts;
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const monthIdx = parseInt(m, 10) - 1;
    const monthName = months[monthIdx] || m;
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
  } | null;
  is_covernote_issued?: boolean;
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

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function TenureTimelineLedger() {
  const router = useRouter();

  // Current year & month defaults
  const currentYear = useMemo(() => new Date().getFullYear().toString(), []);
  const currentMonthNum = useMemo(() => new Date().getMonth() + 1, []);
  const currentMonthKey = useMemo(() => {
    return `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}`;
  }, []);

  const [selectedYear, setSelectedYear] = useState<string>(currentYear);
  const [selectedMonth, setSelectedMonth] = useState<string>(currentMonthKey);
  const [months, setMonths] = useState<MonthItem[]>([]);
  const [loadingMonths, setLoadingMonths] = useState(true);

  // Category toggle: 'active' (default) vs 'lost' (lost clients & follow-up) vs 'all'
  const [category, setCategory] = useState<"active" | "lost" | "all">("active");

  // Selected Stage Filter from KPI Cards
  const [stageFilter, setStageFilter] = useState<string>("all");

  // Stage Summary Counts
  const [summary, setSummary] = useState<StageSummary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  // Dual View Mode: Ledger Table vs Visual Calendar
  const [viewMode, setViewMode] = useState<"ledger" | "calendar">("ledger");
  const [calendarDisplay, setCalendarDisplay] = useState<"grid" | "agenda">("grid");

  // Tenures Data & Filters
  const [tenures, setTenures] = useState<TenureRow[]>([]);
  const [loadingTenures, setLoadingTenures] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [policyFilter, setPolicyFilter] = useState<"all" | "issued" | "pending">("all");

  const issuedCount = useMemo(() => {
    return tenures.filter((t) => Boolean(t.covernote_policy || t.stage === "Close - Win" || t.status === "hit")).length;
  }, [tenures]);
  const pendingCount = useMemo(() => {
    return tenures.filter((t) => !Boolean(t.covernote_policy || t.stage === "Close - Win" || t.status === "hit")).length;
  }, [tenures]);

  // Sorting state (default: last_activity desc)
  const [sortBy, setSortBy] = useState<LedgerSortColumn>("last_activity");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Highlighted tenure row (e.g. from Policy Issue notification) & live relative ticker
  const searchParams = useSearchParams();
  const [highlightedTenureId, setHighlightedTenureId] = useState<string | null>(null);
  const [, setTicker] = useState(0);

  // Tick relative timestamps every 5 seconds
  useEffect(() => {
    const timer = setInterval(() => setTicker((t) => t + 1), 5000);
    return () => clearInterval(timer);
  }, []);

  // Upload Cover Note Modal State
  const [covernoteUploadTenure, setCovernoteUploadTenure] = useState<TenureRow | null>(null);
  const [uploadingCovernote, setUploadingCovernote] = useState(false);

  // Listen for highlight parameter from notifications or URL
  useEffect(() => {
    const target = searchParams?.get("highlight_tenure");
    if (target) {
      setHighlightedTenureId(target);
      setViewMode("ledger");
      setTimeout(() => {
        const el = document.getElementById(`tenure-row-${target}`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 500);

      const clearTimer = setTimeout(() => {
        setHighlightedTenureId(null);
        // Clear param from URL so page refresh doesn't re-trigger blinking
        try {
          const currentUrl = new URL(window.location.href);
          if (currentUrl.searchParams.has("highlight_tenure")) {
            currentUrl.searchParams.delete("highlight_tenure");
            currentUrl.searchParams.delete("t");
            window.history.replaceState({}, "", currentUrl.pathname + (currentUrl.search ? `?${currentUrl.searchParams.toString()}` : ""));
          }
        } catch {}
      }, 6000); // 6 seconds soft illumination
      return () => clearTimeout(clearTimer);
    }
  }, [searchParams]);

  // Calendar Sessions state
  const [calendarSessions, setCalendarSessions] = useState<any[]>([]);
  const [calendarVehicleFilter, setCalendarVehicleFilter] = useState<string>("all");
  const [loadingCalendar, setLoadingCalendar] = useState(false);

  const handleSort = (column: LedgerSortColumn) => {
    if (sortBy === column) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(column);
      setSortDir(column === "vehicle_no" || column === "coverage_period" ? "asc" : "desc");
    }
  };

  // YoY Statistics Ribbon State
  const [yoyStats, setYoyStats] = useState<YoYStatItem[]>([]);
  const [allYearsSummary, setAllYearsSummary] = useState<{ total: number; cars: number; active: number; lost: number } | null>(null);
  const [loadingYoy, setLoadingYoy] = useState(false);

  // Bulk Selection & Operations
  const [selectedTenureIds, setSelectedTenureIds] = useState<string[]>([]);
  const [deletingBulk, setDeletingBulk] = useState(false);

  const [showHidden, setShowHidden] = useState<boolean>(false);

  // PICs directory for dropdown selection
  const [pics, setPics] = useState<PicItem[]>([]);
  const [activeDrawerTenureId, setActiveDrawerTenureId] = useState<string | null>(null);
  const [editingTenure, setEditingTenure] = useState<TenureRow | null>(null);

  // Inline save feedback state
  const [savingFieldId, setSavingFieldId] = useState<string | null>(null);
  const [savedFieldId, setSavedFieldId] = useState<string | null>(null);

  // Miss outcome modal state
  const [missModalTenure, setMissModalTenure] = useState<TenureRow | null>(null);
  const [keepClientChoice, setKeepClientChoice] = useState<"keep" | "discard">("keep");
  const [createNextYearDeal, setCreateNextYearDeal] = useState<boolean>(true);
  const [externalInsurer, setExternalInsurer] = useState<string>("");
  const [missReason, setMissReason] = useState<string>("");
  const [savingMissOutcome, setSavingMissOutcome] = useState<boolean>(false);

  // Issue Policy confirmation modal state
  const [issuePolicyModalTenure, setIssuePolicyModalTenure] = useState<TenureRow | null>(null);
  const [selectedWinnerQuote, setSelectedWinnerQuote] = useState<string>("");
  const [policyStartDate, setPolicyStartDate] = useState<string>("");
  const [savingIssuePolicy, setSavingIssuePolicy] = useState<boolean>(false);

  // Delete vehicle confirmation modal state
  const [deleteConfirmTarget, setDeleteConfirmTarget] = useState<{ id: string; vehicleNo: string; allIds: string[] } | null>(null);
  const [deletingVehicle, setDeletingVehicle] = useState<boolean>(false);

  // Hit confirmation modal state (confirming policy details before marking Hit)
  const [hitConfirmTenure, setHitConfirmTenure] = useState<TenureRow | null>(null);
  const [hitConfirmedStartDate, setHitConfirmedStartDate] = useState<string>("");
  const [hitConfirmedEndDate, setHitConfirmedEndDate] = useState<string>("");
  const [hitConfirmedInsurer, setHitConfirmedInsurer] = useState<string>("");
  const [savingHitConfirm, setSavingHitConfirm] = useState<boolean>(false);

  const handleConfirmMiss = async () => {
    if (!missModalTenure) return;
    setSavingMissOutcome(true);
    try {
      const isDiscard = keepClientChoice === "discard";
      const startDt = missModalTenure.coverage_start_date ? new Date(missModalTenure.coverage_start_date) : new Date();
      const currentYear = startDt.getFullYear();
      const targetYear = currentYear + 1;

      // 1. Mark current tenure as Close - Lose / miss
      const updatePayload: any = {
        stage: "Close - Lose",
        status: "miss",
        is_discarded: isDiscard,
      };
      if (externalInsurer.trim()) {
        updatePayload.loss_reason_category = externalInsurer.trim();
        updatePayload.notes = `Customer chose ${externalInsurer.trim()} for ${currentYear}. ${missReason.trim()}`.trim();
      } else if (missReason.trim()) {
        updatePayload.notes = missReason.trim();
      }

      await api(`/tenures/${missModalTenure.id}/ledger-fields`, {
        method: "PATCH",
        body: JSON.stringify(updatePayload),
      });

      // 2. If keeping client and create next year deal is checked:
      if (!isDiscard && createNextYearDeal) {
        let nextStartStr = `${targetYear}-01-01`;
        let nextEndStr = `${targetYear}-12-31`;

        if (missModalTenure.coverage_end_date) {
          const endDate = new Date(missModalTenure.coverage_end_date);
          const nextStart = new Date(endDate);
          nextStart.setDate(nextStart.getDate() + 1);
          const nextEnd = new Date(nextStart);
          nextEnd.setDate(nextEnd.getDate() + 364);
          nextStartStr = nextStart.toISOString().split("T")[0];
          nextEndStr = nextEnd.toISOString().split("T")[0];
        }

        await api("/tenures", {
          method: "POST",
          body: JSON.stringify({
            vehicle_no: missModalTenure.vehicle_no,
            customer_name: missModalTenure.customer_name,
            coverage_start_date: nextStartStr,
            coverage_end_date: nextEndStr,
            chassis_no: missModalTenure.chassis_no || null,
            car_model: missModalTenure.car_model || null,
            engine_cc: missModalTenure.engine_cc || null,
            notes: `Win-Back Renewal deal created for ${targetYear} after ${currentYear} miss.`,
          }),
        });
      }

      setMissModalTenure(null);
      loadTenures();
      loadStageSummary();
      loadYoyStats();
    } catch (err: any) {
      alert("Failed to update deal: " + (err?.message || err));
    } finally {
      setSavingMissOutcome(false);
    }
  };

  const handleConfirmHit = async () => {
    if (!hitConfirmTenure) return;
    setSavingHitConfirm(true);
    try {
      const updatePayload: any = {
        stage: "Close - Win",
        status: "hit",
      };
      if (hitConfirmedStartDate) {
        updatePayload.coverage_start_date = hitConfirmedStartDate;
      }
      if (hitConfirmedEndDate) {
        updatePayload.coverage_end_date = hitConfirmedEndDate;
      }
      if (hitConfirmedInsurer) {
        updatePayload.winning_company_name = hitConfirmedInsurer;
      }
      await api(`/tenures/${hitConfirmTenure.id}/ledger-fields`, {
        method: "PATCH",
        body: JSON.stringify(updatePayload),
      });

      try {
        const ev = {
          tenure_id: hitConfirmTenure.id,
          vehicle_no: hitConfirmTenure.vehicle_no,
          company: hitConfirmedInsurer || hitConfirmTenure.covernote_policy?.company || hitConfirmTenure.winning_company_name || "",
          timestamp: Date.now(),
        };
        localStorage.setItem("rl_latest_policy_issue", JSON.stringify(ev));
        window.dispatchEvent(new CustomEvent("rl_policy_issued", { detail: ev }));
      } catch {}

      setHitConfirmTenure(null);
      loadTenures();
      loadStageSummary();
      loadYoyStats();
    } catch (err: any) {
      alert("Failed to confirm hit: " + (err?.message || err));
    } finally {
      setSavingHitConfirm(false);
    }
  };

  const handleUploadCovernoteForTenure = async (file: File) => {
    if (!covernoteUploadTenure) return;
    setUploadingCovernote(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("tenure_id", covernoteUploadTenure.id);

      const res = await api<any>("/uploads", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: form,
      });

      const jobId = res?.job_id;
      if (jobId) {
        let attempts = 0;
        while (attempts < 15) {
          await new Promise((r) => setTimeout(r, 1000));
          attempts++;
          try {
            const jobStatus = await api<any>(`/uploads/jobs/${jobId}`);
            if (jobStatus?.status === "completed" || jobStatus?.status === "failed") {
              break;
            }
          } catch {
            break;
          }
        }
      }

      const vehicleName = covernoteUploadTenure.vehicle_no;
      setCovernoteUploadTenure(null);
      await loadTenures();
      await loadStageSummary();
      alert(`Cover Note for ${vehicleName} uploaded successfully! Policy is now in Issue Policy stage.`);
    } catch (err: any) {
      alert("Cover Note upload failed: " + (err.message || String(err)));
    } finally {
      setUploadingCovernote(false);
    }
  };

  const renderPipelineProgress = (t: TenureRow) => {
    const isHit = t.stage === "Close - Win";
    const isMiss = t.stage === "Close - Lose";
    const canHit = t.stage === "Issue Policy";

    const linearStages = [
      { id: "Quotations", label: "Quotations" },
      { id: "Material to Client", label: "Material to Client" },
      { id: "Issue Policy", label: "Issue Policy" },
    ];

    const currentIdx = linearStages.findIndex((s) => s.id === t.stage);

    const getStageTimestamp = (stId: string) => {
      return t.stage_history?.[stId] || (t.stage === stId ? t.stage_updated_at : null);
    };

    const getStageTooltip = (stId: string, label: string) => {
      const ts = getStageTimestamp(stId);
      if (ts) {
        return `${label}\nUpdated: ${formatDateTimeSafe(ts)}`;
      }
      return `${label}\nStatus: Not reached yet`;
    };

    if (isHit) {
      const hitTs = t.stage_history?.["Close - Win"] || t.stage_updated_at;
      return (
        <div className="flex items-center gap-1.5">
          <span
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-100 text-emerald-900 border border-emerald-300 text-[11px] font-bold shadow-2xs cursor-help"
            title={`✓ HIT (Won)\nUpdated: ${formatDateTimeSafe(hitTs)}`}
          >
            <CheckCircle size={13} weight="fill" className="text-emerald-700" />
            <span>✓ HIT (Won)</span>
          </span>
          <button
            type="button"
            onClick={() => patchTenureField(t.id, { stage: "Issue Policy", status: "draft" })}
            className="text-[10px] text-neutral-400 hover:text-neutral-700 underline cursor-pointer"
            title="Revert back to Issue Policy (will delete empty auto-created next-year renewal)"
          >
            Revert
          </button>
        </div>
      );
    }

    if (isMiss) {
      const missTs = t.stage_history?.["Close - Lose"] || t.stage_updated_at;
      return (
        <div className="flex items-center gap-1.5">
          <span
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-rose-100 text-rose-900 border border-rose-300 text-[11px] font-bold shadow-2xs cursor-help"
            title={`✕ MISS (Lost)\nUpdated: ${formatDateTimeSafe(missTs)}`}
          >
            <XCircle size={13} weight="fill" className="text-rose-700" />
            <span>✕ MISS (Lost)</span>
          </span>
          <button
            type="button"
            onClick={() => patchTenureField(t.id, { stage: "Quotations", status: "draft" })}
            className="text-[10px] text-neutral-400 hover:text-neutral-700 underline cursor-pointer"
            title="Reopen quote"
          >
            Reopen
          </button>
        </div>
      );
    }

    return (
      <div className="flex items-center gap-1.5 flex-wrap">
        {/* Straight Arrow Progress Bar */}
        <div className="inline-flex items-center bg-neutral-100/90 p-0.5 rounded border border-neutral-200 text-[10px] font-semibold">
          {linearStages.map((st, idx) => {
            const isActive = t.stage === st.id;
            const isCompleted = currentIdx > idx;
            const tooltipText = getStageTooltip(st.id, st.label);

            return (
              <React.Fragment key={st.id}>
                <button
                  type="button"
                  onClick={() => {
                    if (st.id === "Issue Policy") {
                      const hasCn = Boolean(t.covernote_policy || t.is_covernote_issued);
                      if (!hasCn) {
                        setCovernoteUploadTenure(t);
                        return;
                      }
                      patchTenureField(t.id, { stage: "Issue Policy" });
                    } else {
                      const isPolicyIssued = Boolean(
                        t.covernote_policy ||
                        t.is_covernote_issued ||
                        t.stage === "Issue Policy" ||
                        t.stage === "Close - Win" ||
                        t.status === "hit"
                      );
                      if (isPolicyIssued && (st.id === "Quotations" || st.id === "Material to Client")) {
                        alert(
                          `This policy has already been issued with an official Cover Note for ${t.vehicle_no || "this vehicle"}.\n\n` +
                          `The pipeline is locked to protect the issued policy. To move the pipeline back to ${st.label}, you must first unlink/remove the Cover Note in the Marketing Comparison table.`
                        );
                        return;
                      }
                      patchTenureField(t.id, { stage: st.id });
                    }
                  }}
                  className={`px-2 py-0.5 rounded transition-all cursor-pointer flex items-center gap-1 ${
                    isActive
                      ? "bg-white text-neutral-900 shadow-2xs font-bold border border-neutral-300/80"
                      : isCompleted
                      ? "text-emerald-700 hover:text-emerald-900 font-medium"
                      : "text-neutral-400 hover:text-neutral-700"
                  }`}
                  title={
                    st.id === "Issue Policy" && !Boolean(t.covernote_policy || t.is_covernote_issued)
                      ? "Official Cover Note PDF required to reach Issue Policy stage. Click to upload."
                      : Boolean(t.covernote_policy || t.is_covernote_issued) && (st.id === "Quotations" || st.id === "Material to Client")
                      ? "Cover Note is active. Unlink Cover Note in Marketing Comparison first to revert stage."
                      : tooltipText
                  }
                >
                  {isCompleted && <Check size={10} weight="bold" className="text-emerald-600 shrink-0" />}
                  <span>{st.label}</span>
                  {st.id === "Issue Policy" && !Boolean(t.covernote_policy || t.is_covernote_issued) && (
                    <UploadSimple size={10} className="text-amber-600 shrink-0" />
                  )}
                </button>
                {idx < linearStages.length - 1 && (
                  <span className="text-neutral-300 px-0.5 select-none font-bold">→</span>
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* HIT Button: Only clickable if Policy is Issued */}
        {canHit ? (
          <button
            type="button"
            onClick={() => {
              setHitConfirmTenure(t);
              const winningQ = t.sourced_quotes?.find(q => q.is_winner || q.company === t.winning_company_name || q.company === t.winning_company_id);
              const startCandidate = t.covernote_policy?.coverage_start_date || winningQ?.coverage_start_date || t.coverage_start_date || new Date().toISOString().split("T")[0];
              setHitConfirmedStartDate(startCandidate);
              if (t.covernote_policy?.coverage_end_date || winningQ?.coverage_end_date || t.coverage_end_date) {
                setHitConfirmedEndDate(t.covernote_policy?.coverage_end_date || winningQ?.coverage_end_date || t.coverage_end_date);
              } else {
                const endD = new Date(startCandidate);
                endD.setDate(endD.getDate() + 364);
                setHitConfirmedEndDate(endD.toISOString().split("T")[0]);
              }
              setHitConfirmedInsurer(t.covernote_policy?.company || t.winning_company_name || t.winning_company_id || winningQ?.company || t.sourced_quotes?.[0]?.company || "");
            }}
            className="px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[10px] shadow-2xs cursor-pointer transition-colors flex items-center gap-1"
            title="Policy is issued! Click to review policy details and mark as HIT (won)"
          >
            <CheckCircle size={11} weight="bold" />
            <span>Hit</span>
          </button>
        ) : (
          <button
            type="button"
            disabled
            className="px-2 py-1 rounded bg-neutral-100 text-neutral-400 border border-neutral-200 text-[10px] font-medium cursor-not-allowed opacity-60 flex items-center gap-1"
            title="Policy must be in 'Issue Policy' stage before marking as Hit"
          >
            <svg className="w-2.5 h-2.5 text-neutral-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
            <span>Hit</span>
          </button>
        )}

        {/* MISS Button: Always accessible anytime */}
        <button
          type="button"
          onClick={() => {
            setMissModalTenure(t);
            setKeepClientChoice("keep");
            setCreateNextYearDeal(true);
            setExternalInsurer("");
            setMissReason("");
          }}
          className="px-2 py-1 rounded bg-rose-50 hover:bg-rose-100 text-rose-700 hover:text-rose-900 border border-rose-200 hover:border-rose-300 font-bold text-[10px] cursor-pointer transition-colors flex items-center gap-0.5"
          title="Deal lost / Miss (choose to keep client or drop)"
        >
          <XCircle size={11} weight="bold" />
          <span>Miss</span>
        </button>
      </div>
    );
  };

  const monthScrollRef = useRef<HTMLDivElement>(null);

  // Load YoY stats
  const loadYoyStats = useCallback(async () => {
    setLoadingYoy(true);
    try {
      const res = await api<{
        years: YoYStatItem[];
        all_years?: { total: number; cars: number; active: number; lost: number };
      }>("/tenures/stats/yoy" + (showHidden ? "?show_hidden=true" : ""));
      setYoyStats(res.years || []);
      if (res.all_years) {
        setAllYearsSummary(res.all_years);
      }
    } catch (err) {
      console.error("Failed to load YoY stats:", err);
    } finally {
      setLoadingYoy(false);
    }
  }, [showHidden]);

  useEffect(() => {
    loadYoyStats();
  }, [loadYoyStats]);

  // Load PICs directory
  useEffect(() => {
    api<PicItem[]>("/pics")
      .then((data) => setPics(Array.isArray(data) ? data : []))
      .catch((err) => console.error("Failed to load PICs:", err));
  }, []);

  // Load Months timeline
  const loadMonths = useCallback(async () => {
    setLoadingMonths(true);
    try {
      const res = await api<{ months: MonthItem[] }>("/tenures/months" + (showHidden ? "?show_hidden=true" : ""));
      const list = res.months || [];
      setMonths(list);
    } catch (err) {
      console.error("Failed to load tenure months:", err);
    } finally {
      setLoadingMonths(false);
    }
  }, [showHidden]);

  useEffect(() => {
    loadMonths();
  }, [loadMonths]);

  // Load 10-Stage KPI Summary
  const loadStageSummary = useCallback(async () => {
    setLoadingSummary(true);
    try {
      const params = new URLSearchParams();
      if (selectedYear && selectedYear !== "all") {
        params.set("year", selectedYear);
      }
      if (selectedMonth && selectedMonth !== "all" && selectedMonth.includes("-")) {
        const m = parseInt(selectedMonth.split("-")[1], 10);
        params.set("month", String(m));
      }
      const data = await api<StageSummary>(`/tenures/stage-summary?${params.toString()}`);
      setSummary(data);
    } catch (err) {
      console.error("Failed to load stage summary:", err);
    } finally {
      setLoadingSummary(false);
    }
  }, [selectedYear, selectedMonth]);

  useEffect(() => {
    loadStageSummary();
  }, [loadStageSummary]);

  // Load Tenures
  const loadTenures = useCallback(async () => {
    setLoadingTenures(true);
    try {
      const params = new URLSearchParams();
      // Tabular view is strictly by Year; Calendar view can filter by Month
      if (viewMode === "calendar" && selectedMonth && selectedMonth !== "all") {
        params.set("month", selectedMonth);
      } else if (selectedYear && selectedYear !== "all") {
        params.set("year", selectedYear);
      }

      if (category !== "all") {
        params.set("category", category);
      }

      if (stageFilter !== "all") {
        params.set("stage", stageFilter);
      }

      if (search.trim()) {
        params.set("search", search.trim());
      }

      if (showHidden) {
        params.set("show_hidden", "true");
      }

      params.set("sort_by", sortBy);
      params.set("sort_dir", sortDir);
      params.set("page_size", "150");

      const res = await api<{ items: TenureRow[]; total: number }>(`/tenures?${params.toString()}`);
      setTenures(res.items || []);
    } catch (err) {
      console.error("Failed to load tenures:", err);
    } finally {
      setLoadingTenures(false);
    }
  }, [viewMode, selectedYear, selectedMonth, category, stageFilter, search, showHidden, sortBy, sortDir]);

  useEffect(() => {
    loadTenures();
  }, [loadTenures]);

  // Auto-refresh ledger on window focus or when policy is issued via upload
  useEffect(() => {
    const handleRefresh = () => {
      loadTenures();
      loadStageSummary();
    };
    window.addEventListener("focus", handleRefresh);
    window.addEventListener("rl_policy_issued", handleRefresh);
    return () => {
      window.removeEventListener("focus", handleRefresh);
      window.removeEventListener("rl_policy_issued", handleRefresh);
    };
  }, [loadTenures, loadStageSummary]);

  // Load Calendar Quotation Sessions
  const loadCalendarSessions = useCallback(async () => {
    setLoadingCalendar(true);
    try {
      const params = new URLSearchParams();
      if (selectedYear && selectedYear !== "all") {
        params.set("year", selectedYear);
      }
      if (selectedMonth && selectedMonth !== "all" && selectedMonth.includes("-")) {
        const m = parseInt(selectedMonth.split("-")[1], 10);
        params.set("month", String(m));
      }
      if (calendarVehicleFilter && calendarVehicleFilter !== "all") {
        params.set("vehicle_no", calendarVehicleFilter);
      }
      const res = await api<{ sessions: any[]; total: number }>(`/tenures/calendar-sessions?${params.toString()}`);
      setCalendarSessions(res.sessions || []);
    } catch (err) {
      console.error("Failed to load calendar sessions:", err);
    } finally {
      setLoadingCalendar(false);
    }
  }, [selectedYear, selectedMonth, calendarVehicleFilter]);

  useEffect(() => {
    if (viewMode === "calendar") {
      loadCalendarSessions();
    }
  }, [viewMode, loadCalendarSessions]);

  // Handle live inline edit patch
  const patchTenureField = async (tenureId: string, updates: Partial<TenureRow>) => {
    setSavingFieldId(tenureId);
    try {
      await api(`/tenures/${tenureId}/ledger-fields`, {
        method: "PATCH",
        body: JSON.stringify(updates),
      });

      // Update local state snappily with multi-tenure customer propagation
      setTenures((prev) => {
        const targetTenure = prev.find((t) => t.id === tenureId);
        const custId = targetTenure?.customer_id;
        const oldName = targetTenure?.customer_name;
        const isCustomerUpdate = Boolean(updates.customer_name || updates.customer_ic_no);

        return prev.map((t) => {
          if (t.id === tenureId) {
            return { ...t, ...updates };
          }
          if (
            isCustomerUpdate &&
            ((custId && t.customer_id === custId) || (oldName && t.customer_name === oldName))
          ) {
            return {
              ...t,
              ...(updates.customer_name ? { customer_name: updates.customer_name } : {}),
              ...(updates.customer_ic_no ? { customer_ic_no: updates.customer_ic_no } : {}),
            };
          }
          return t;
        });
      });

      // Trigger summary count refresh
      loadStageSummary();

      // If stage, status, or discard changed, reload full tenures list so auto-created next-year renewal is shown/removed immediately
      if (updates.stage || updates.status || updates.is_discarded !== undefined) {
        loadTenures();
      }

      // Show brief success check
      setSavedFieldId(tenureId);
      setTimeout(() => setSavedFieldId(null), 2000);
    } catch (err) {
      console.error("Failed to patch tenure field:", err);
      alert("Failed to save change. Please check your connection.");
    } finally {
      setSavingFieldId(null);
    }
  };

  // Selection & Bulk Delete Operations
  const handleToggleSelectAll = () => {
    if (selectedTenureIds.length === tenures.length && tenures.length > 0) {
      setSelectedTenureIds([]);
    } else {
      setSelectedTenureIds(tenures.map((t) => t.id));
    }
  };

  const handleToggleSelectRow = (tenureId: string) => {
    setSelectedTenureIds((prev) =>
      prev.includes(tenureId) ? prev.filter((id) => id !== tenureId) : [...prev, tenureId]
    );
  };

  const handleBulkDelete = async () => {
    if (selectedTenureIds.length === 0) return;
    const count = selectedTenureIds.length;
    if (
      !confirm(
        `Are you sure you want to delete ${count} selected policy deals? This will remove them from the ledger and unlink any associated draft sessions.`
      )
    ) {
      return;
    }
    setDeletingBulk(true);
    try {
      await api("/tenures/bulk", {
        method: "DELETE",
        body: JSON.stringify({ tenure_ids: selectedTenureIds }),
      });
      setSelectedTenureIds([]);
      loadTenures();
      loadStageSummary();
      loadMonths();
      loadYoyStats();
    } catch (err: any) {
      alert("Failed to delete selected deals: " + (err.message || "Unknown error"));
    } finally {
      setDeletingBulk(false);
    }
  };

  const [confirmingBulk, setConfirmingBulk] = useState(false);
  const handleBulkConfirmHit = async () => {
    if (selectedTenureIds.length === 0) return;
    const count = selectedTenureIds.length;
    if (
      !confirm(
        `Confirm Hit (Policy Won / Issued) for ${count} selected policy deal(s)? This will mark them as won and automatically roll forward their next-year renewal tracking.`
      )
    ) {
      return;
    }
    setConfirmingBulk(true);
    try {
      await api("/tenures/bulk-confirm-hit", {
        method: "POST",
        body: JSON.stringify({ tenure_ids: selectedTenureIds }),
      });
      setSelectedTenureIds([]);
      loadTenures();
      loadStageSummary();
      loadYoyStats();
    } catch (err: any) {
      alert("Failed to bulk confirm hit: " + (err?.message || err));
    } finally {
      setConfirmingBulk(false);
    }
  };

  // Handle deleting a single deal from the ledger
  const handleDeleteTenure = async (tenureId: string, vehicleNo: string) => {
    if (
      !confirm(
        `Are you sure you want to delete the deal for ${vehicleNo}? This will delete this tenure record from the ledger.`
      )
    ) {
      return;
    }
    try {
      await api(`/tenures/${tenureId}`, { method: "DELETE" });
      setTenures((prev) => prev.filter((t) => t.id !== tenureId));
      setSelectedTenureIds((prev) => prev.filter((id) => id !== tenureId));
      loadStageSummary();
      loadMonths();
      loadYoyStats();
    } catch (err: any) {
      alert("Failed to delete deal: " + (err.message || "Unknown error"));
    }
  };

  // Helper to extract stage count from summary
  function getStageCount(stage: string): number {
    if (!summary) return 0;
    switch (stage) {
      case "Quotations":
        return summary.quotations || 0;
      case "Material to Client":
        return summary.material_to_client || 0;
      case "Close - Win":
        return summary.close_win || 0;
      case "Issue Policy":
        return summary.issue_policy || 0;
      case "Close - Lose":
        return summary.close_lose || 0;
      default:
        return 0;
    }
  }

  // Handle setting a tenure as the approved/main policy for this vehicle
  const handleSetMainTenure = async (targetTenureId: string, vehicleNo: string) => {
    try {
      await api(`/tenures/${targetTenureId}/set-main`, { method: "POST" });
      setTenures((prev) =>
        prev.map((t) => {
          if (t.vehicle_no === vehicleNo) {
            return { ...t, is_main: t.id === targetTenureId };
          }
          return t;
        })
      );
    } catch (err: any) {
      alert("Failed to set main policy: " + (err?.message || err));
    }
  };

  // Handle stage card click: toggle filter
  function handleStageCardClick(stage: string) {
    if (stageFilter === stage) {
      setStageFilter("all");
    } else {
      setStageFilter(stage);
      if (stage === "Close - Lose") {
        setCategory("lost");
      } else if (category === "lost") {
        setCategory("active");
      }
    }
  }

  // Scroll active month into view
  useEffect(() => {
    if (!selectedMonth || selectedMonth === "all") return;
    const el = monthScrollRef.current?.querySelector(`[data-month="${selectedMonth}"]`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
    }
  }, [selectedMonth]);

  function scrollMonths(direction: "left" | "right") {
    if (monthScrollRef.current) {
      const delta = direction === "left" ? -320 : 320;
      monthScrollRef.current.scrollBy({ left: delta, behavior: "smooth" });
    }
  }

  function handleJumpToCurrentMonth() {
    setSelectedYear(currentYear);
    setSelectedMonth(currentMonthKey);
  }

  // 12 Clean Month list for selected year (shows start, end, total, and cars)
  const monthsOfYear = useMemo(() => {
    const yr = selectedYear === "all" ? currentYear : selectedYear;
    return MONTH_NAMES.map((name, idx) => {
      const mStr = `${yr}-${String(idx + 1).padStart(2, "0")}`;
      const existing = months.find((m) => m.month === mStr);
      return {
        month: mStr,
        label: name,
        monthNum: idx + 1,
        total: existing ? existing.total : 0,
        start_count: existing ? existing.start_count : 0,
        end_count: existing ? existing.end_count : 0,
        cars: existing ? existing.cars : 0,
      };
    });
  }, [selectedYear, months, currentYear]);

  // Year items to show in year switcher (strictly dynamic from actual uploaded policies + current year + next renewal year)
  const availableYears = useMemo(() => {
    const nextYear = (parseInt(currentYear, 10) + 1).toString();
    const yearsSet = new Set<string>([currentYear, nextYear]);
    yoyStats.forEach((s) => {
      if (s.year) yearsSet.add(s.year);
    });
    return Array.from(yearsSet).sort();
  }, [currentYear, yoyStats]);

  // Find PIC details helper
  function getPicDisplay(t: TenureRow) {
    if (t.pic_id) {
      const matched = pics.find((p) => p.id === t.pic_id);
      if (matched) {
        return {
          id: matched.id,
          name: matched.name,
          type: matched.type,
          commission: matched.commission_rate,
          agency: matched.agency_group,
          phone: matched.phone,
          whatsapp: matched.whatsapp_number || matched.phone,
          isOwner: matched.is_owner,
        };
      }
    }
    if (t.sub_agent_name) {
      return {
        id: null,
        name: t.sub_agent_name,
        type: "subagent" as const,
        commission: 0,
        agency: t.pic_agency || null,
        phone: null,
        whatsapp: null,
        isOwner: false,
      };
    }
    return null;
  }

  // Calendar Geometry for Visual View (maps both Start and Expiry events)
  const calendarData = useMemo(() => {
    let yr = parseInt(currentYear, 10);
    let mo = currentMonthNum - 1;

    if (selectedMonth && selectedMonth !== "all" && selectedMonth.includes("-")) {
      const parts = selectedMonth.split("-");
      yr = parseInt(parts[0], 10);
      mo = parseInt(parts[1], 10) - 1;
    } else if (selectedYear && selectedYear !== "all") {
      yr = parseInt(selectedYear, 10);
      mo = 0;
    }

    const firstDay = new Date(yr, mo, 1).getDay();
    const daysInMonth = new Date(yr, mo + 1, 0).getDate();
    const monthLabel = new Date(yr, mo, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });

    type CalendarEvent =
      | {
          type: "start" | "end";
          tenure: TenureRow;
        }
      | {
          type: "session";
          session: any;
        };

    const dayMap: Record<number, CalendarEvent[]> = {};
    for (let d = 1; d <= daysInMonth; d++) {
      dayMap[d] = [];
    }

    // 1. Add uploaded quotation sessions plotted by quotation_date
    calendarSessions.forEach((s) => {
      if (s.quotation_date) {
        const parts = s.quotation_date.split("-");
        if (parts.length === 3) {
          const itemYr = parseInt(parts[0], 10);
          const itemMo = parseInt(parts[1], 10) - 1;
          const itemDay = parseInt(parts[2], 10);
          if (itemYr === yr && itemMo === mo && dayMap[itemDay]) {
            dayMap[itemDay].push({ type: "session", session: s });
          }
        }
      }
    });

    // 2. Filter to ONLY approved / main policies for coverage start/end events
    const calendarTenures = tenures.filter((t) => t.is_main);

    calendarTenures.forEach((t) => {
      // 1. Check start date
      if (t.coverage_start_date) {
        const datePart = t.coverage_start_date.split("T")[0];
        const parts = datePart.split("-");
        if (parts.length === 3) {
          const itemYr = parseInt(parts[0], 10);
          const itemMo = parseInt(parts[1], 10) - 1;
          const itemDay = parseInt(parts[2], 10);
          if (itemYr === yr && itemMo === mo && dayMap[itemDay]) {
            dayMap[itemDay].push({ type: "start", tenure: t });
          }
        }
      }
      // 2. Check end date
      if (t.coverage_end_date) {
        const datePart = t.coverage_end_date.split("T")[0];
        const parts = datePart.split("-");
        if (parts.length === 3) {
          const itemYr = parseInt(parts[0], 10);
          const itemMo = parseInt(parts[1], 10) - 1;
          const itemDay = parseInt(parts[2], 10);
          if (itemYr === yr && itemMo === mo && dayMap[itemDay]) {
            dayMap[itemDay].push({ type: "end", tenure: t });
          }
        }
      }
    });

    const agendaDays: Array<{ day: number; dateStr: string; items: CalendarEvent[] }> = [];
    for (let d = 1; d <= daysInMonth; d++) {
      if (dayMap[d]?.length > 0) {
        const dt = new Date(yr, mo, d);
        agendaDays.push({
          day: d,
          dateStr: dt.toLocaleDateString("en-US", { weekday: "short", day: "numeric", month: "short", year: "numeric" }),
          items: dayMap[d],
        });
      }
    }

    return {
      year: yr,
      month: mo,
      monthLabel,
      firstDay,
      daysInMonth,
      dayMap,
      agendaDays,
    };
  }, [selectedMonth, selectedYear, tenures, calendarSessions, currentYear, currentMonthNum]);

  // Unique vehicle list for calendar filter dropdown
  const calendarVehicleOptions = useMemo(() => {
    const set = new Set<string>();
    tenures.forEach((t) => {
      if (t.vehicle_no) set.add(t.vehicle_no.trim().toUpperCase());
    });
    calendarSessions.forEach((s) => {
      if (s.vehicle_no && s.vehicle_no !== "Unknown") set.add(s.vehicle_no.trim().toUpperCase());
    });
    return Array.from(set).sort();
  }, [tenures, calendarSessions]);

  // Group tenures by vehicle for the vehicle-centric ledger (1 row per vehicle per year)
  const vehicleGroups = useMemo(() => {
    const map = new Map<string, TenureRow[]>();
    for (const t of tenures) {
      const key = (t.vehicle_no || t.chassis_no || t.id).trim().toUpperCase();
      if (!map.has(key)) {
        map.set(key, []);
      }
      map.get(key)!.push(t);
    }

    const groups: Array<{
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
    }> = [];

    map.forEach((tList, key) => {
      const sorted = [...tList].sort((a, b) => {
        const da = a.coverage_start_date || "";
        const db = b.coverage_start_date || "";
        return db.localeCompare(da);
      });
      const main = sorted.find((t) => t.is_main) || sorted[0];
      groups.push({
        vehicle_no: key,
        customer_name: main.customer_name,
        customer_ic_no: main.customer_ic_no,
        car_brand: main.car_brand,
        car_model: main.car_model,
        engine_cc: main.engine_cc,
        manufacture_year: main.manufacture_year,
        chassis_no: main.chassis_no,
        engine_no: main.engine_no,
        mainTenure: main,
        tenures: sorted,
      });
    });

    let filteredGroups = groups;
    if (policyFilter === "issued") {
      filteredGroups = filteredGroups.filter((g) => {
        const t = g.mainTenure;
        return Boolean(t.covernote_policy || t.stage === "Close - Win" || t.status === "hit");
      });
    } else if (policyFilter === "pending") {
      filteredGroups = filteredGroups.filter((g) => {
        const t = g.mainTenure;
        return !Boolean(t.covernote_policy || t.stage === "Close - Win" || t.status === "hit");
      });
    }

    return [...filteredGroups].sort((a, b) => {
      let cmp = 0;
      if (sortBy === "vehicle_no") {
        cmp = a.vehicle_no.localeCompare(b.vehicle_no);
        return sortDir === "asc" ? cmp : -cmp;
      } else if (sortBy === "coverage_period") {
        const isIssuedA = Boolean(
          a.mainTenure.covernote_policy ||
          a.mainTenure.is_covernote_issued ||
          a.mainTenure.stage === "Close - Win" ||
          a.mainTenure.status === "hit"
        );
        const isIssuedB = Boolean(
          b.mainTenure.covernote_policy ||
          b.mainTenure.is_covernote_issued ||
          b.mainTenure.stage === "Close - Win" ||
          b.mainTenure.status === "hit"
        );

        // Tier 1: Perfectly issued policies ALWAYS appear first at the top!
        if (isIssuedA && !isIssuedB) return -1;
        if (!isIssuedA && isIssuedB) return 1;

        // Tier 2: Within same bucket (both issued OR both unissued), sort by date
        const da = (isIssuedA ? (a.mainTenure.covernote_policy?.coverage_start_date || a.mainTenure.coverage_start_date) : (a.mainTenure.coverage_start_date || a.mainTenure.coverage_end_date)) || "";
        const db = (isIssuedB ? (b.mainTenure.covernote_policy?.coverage_start_date || b.mainTenure.coverage_start_date) : (b.mainTenure.coverage_start_date || b.mainTenure.coverage_end_date)) || "";

        // Deals with no dates always go to the end of their respective bucket
        if (!da && db) return 1;
        if (da && !db) return -1;
        if (!da && !db) return a.vehicle_no.localeCompare(b.vehicle_no);

        const dateCmp = da.localeCompare(db);
        if (dateCmp !== 0) {
          return sortDir === "asc" ? dateCmp : -dateCmp;
        }
        return a.vehicle_no.localeCompare(b.vehicle_no);
      } else if (sortBy === "stage") {
        const stageWeight: Record<string, number> = {
          "Close - Win": 5,
          "Issue Policy": 4,
          "Material to Client": 3,
          "Quotations": 2,
          "Close - Lose": 1,
        };
        const wa = stageWeight[a.mainTenure.stage] ?? 0;
        const wb = stageWeight[b.mainTenure.stage] ?? 0;
        if (wa !== wb) {
          cmp = wa - wb;
          return sortDir === "asc" ? cmp : -cmp;
        }
        // Tie-breaker within same stage: most recently active deal first
        const dateA = a.mainTenure.last_activity_at || a.mainTenure.stage_updated_at || a.mainTenure.created_at || "";
        const dateB = b.mainTenure.last_activity_at || b.mainTenure.stage_updated_at || b.mainTenure.created_at || "";
        return dateB.localeCompare(dateA);
      } else if (sortBy === "created_at") {
        const ca = a.mainTenure.created_at || "";
        const cb = b.mainTenure.created_at || "";
        if (!ca && cb) return 1;
        if (ca && !cb) return -1;
        cmp = ca.localeCompare(cb);
        return sortDir === "asc" ? cmp : -cmp;
      } else if (sortBy === "pic") {
        const picA = (getPicDisplay(a.mainTenure)?.name || a.mainTenure.sub_agent_name || "").toLowerCase();
        const picB = (getPicDisplay(b.mainTenure)?.name || b.mainTenure.sub_agent_name || "").toLowerCase();
        cmp = picA.localeCompare(picB);
        return sortDir === "asc" ? cmp : -cmp;
      } else {
        // "last_activity"
        const dateA = a.mainTenure.last_activity_at || a.mainTenure.stage_updated_at || a.mainTenure.created_at || "";
        const dateB = b.mainTenure.last_activity_at || b.mainTenure.stage_updated_at || b.mainTenure.created_at || "";
        if (!dateA && dateB) return 1;
        if (dateA && !dateB) return -1;
        cmp = dateA.localeCompare(dateB);
        return sortDir === "asc" ? cmp : -cmp;
      }
    });
  }, [tenures, sortBy, sortDir, pics, policyFilter]);

  return (
    <div className="space-y-5">
      {/* ========================================================================= */}
      {/* 1. TOP STAGE KPI BANNER: 5 SUMMARY CARDS                                   */}
      {/* ========================================================================= */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-neutral-900 uppercase tracking-wider">
              5-Stage Pipeline Overview
            </span>
            {loadingSummary && (
              <ArrowsClockwise className="w-3.5 h-3.5 animate-spin text-neutral-400" />
            )}
          </div>
          {stageFilter !== "all" && (
            <button
              type="button"
              onClick={() => setStageFilter("all")}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
            >
              <span>Clear Filter ({stageFilter})</span>
              <XCircle className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* 5 KPI Cards Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
          {STAGE_ORDER.map((stageKey) => {
            const conf = STAGE_CONFIGS[stageKey] || STAGE_CONFIGS.Quotations;
            const count = getStageCount(stageKey);
            const isSelected = stageFilter === stageKey;

            return (
              <button
                key={stageKey}
                type="button"
                onClick={() => handleStageCardClick(stageKey)}
                className={`p-2.5 rounded-[var(--rl-radius-sm)] border text-left transition-all cursor-pointer flex flex-col justify-between min-h-[74px] ${
                  conf.bg
                } ${conf.border} ${
                  isSelected
                    ? "ring-2 ring-neutral-900 shadow-sm font-bold scale-[1.02]"
                    : "hover:shadow-xs hover:border-neutral-400"
                }`}
                title={`Click to filter by ${conf.label}`}
              >
                <div className="text-[11px] font-semibold text-neutral-700 leading-tight truncate">
                  {conf.label}
                </div>
                <div className="flex items-baseline justify-between mt-1">
                  <span className="text-lg font-extrabold text-neutral-900 font-mono">
                    {count}
                  </span>
                  {conf.isLost && (
                    <span className="text-[9px] font-bold text-rose-600 uppercase tracking-wider">
                      Lost
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 2. POLICIES & RENEWALS BY DATE (YEARS & MONTHS)                           */}
      {/* ========================================================================= */}
      <div className="bg-white border border-[#e5e5ea] rounded-[var(--rl-radius)] p-4 shadow-2xs space-y-3.5">
        {/* Top Header: Title & Actions */}
        <div className="flex items-center justify-between flex-wrap gap-2 pb-2.5 border-b border-[#f2f2f7]">
          <div>
            <div className="flex items-center gap-2">
              <CalendarBlank className="w-4 h-4 text-neutral-700" />
              <span className="text-xs font-bold text-neutral-900 uppercase tracking-wider">
                Policies &amp; Renewals
              </span>
            </div>
            <p className="text-[11px] text-neutral-500 mt-0.5">
              Select a year and month to view policy periods and cars. Hover on a month to see starting vs expiring policies.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleJumpToCurrentMonth}
              className="text-[11px] font-semibold text-[#6e6e73] hover:text-[#1b1717] transition-colors px-2.5 py-1 rounded-[var(--rl-radius-sm)] hover:bg-[#f5f5f7] border border-[#e5e5ea] cursor-pointer"
              title="Jump to current active month"
            >
              Current Month
            </button>
            <div className="flex items-center rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] bg-[#f5f5f7] p-0.5">
              <button
                type="button"
                onClick={() => scrollMonths("left")}
                className="p-1 hover:bg-white rounded-[var(--rl-radius-sm)] text-[#6e6e73] hover:text-[#1b1717] transition-colors cursor-pointer"
                title="Scroll months left"
                aria-label="Scroll months left"
              >
                <CaretLeft size={13} weight="bold" />
              </button>
              <button
                type="button"
                onClick={() => scrollMonths("right")}
                className="p-1 hover:bg-white rounded-[var(--rl-radius-sm)] text-[#6e6e73] hover:text-[#1b1717] transition-colors cursor-pointer"
                title="Scroll months right"
                aria-label="Scroll months right"
              >
                <CaretRight size={13} weight="bold" />
              </button>
            </div>
            <button
              type="button"
              onClick={() => {
                loadMonths();
                loadStageSummary();
                loadTenures();
                loadYoyStats();
              }}
              className="text-[11px] font-medium text-[#8e8e93] hover:text-[#1b1717] flex items-center gap-1 ml-1 cursor-pointer"
            >
              <ArrowsClockwise className="w-3 h-3" /> Refresh
            </button>
          </div>
        </div>

        {/* Row 1: Years Switcher with Cars and Policy Counts */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-neutral-700 uppercase tracking-wide">
              Step 1: Select Year
            </span>
            {selectedYear !== "all" && (
              <span className="text-[11px] text-neutral-500">
                Viewing {selectedYear} ({yoyStats.find((s) => s.year === selectedYear)?.total ?? 0} policies · {yoyStats.find((s) => s.year === selectedYear)?.cars ?? 0} cars)
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 flex-wrap">
            {/* All Years button */}
            <button
              type="button"
              onClick={() => {
                setSelectedYear("all");
                setSelectedMonth("all");
              }}
              className={`px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
                selectedYear === "all"
                  ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                  : "bg-[#f5f5f7] text-[#454545] hover:text-[#1b1717] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
              }`}
            >
              <span>All Years</span>
              {allYearsSummary && (
                <span
                  className={`px-1.5 py-0.2 rounded text-[10px] font-mono font-bold ${
                    selectedYear === "all" ? "bg-white/20 text-white" : "bg-[#e5e5ea] text-neutral-700"
                  }`}
                >
                  {allYearsSummary.total} policies · {allYearsSummary.cars} cars
                </span>
              )}
            </button>

            {/* Dynamic Year Buttons */}
            {availableYears.map((yr) => {
              const isSelected = selectedYear === yr;
              const stat = yoyStats.find((s) => s.year === yr);
              const totalPolicies = stat ? stat.total : 0;
              const totalCars = stat ? stat.cars : 0;

              return (
                <button
                  key={yr}
                  type="button"
                  onClick={() => {
                    setSelectedYear(yr);
                    setSelectedMonth("all");
                  }}
                  className={`px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
                    isSelected
                      ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                      : "bg-[#f5f5f7] text-[#454545] hover:text-[#1b1717] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
                  }`}
                  title={`${yr}: ${totalPolicies} policies, ${totalCars} cars`}
                >
                  <span className="font-mono font-bold">{yr}</span>
                  {yr === currentYear && (
                    <span className="text-[10px] text-amber-500 font-bold" title="Current Year">●</span>
                  )}
                  {totalPolicies > 0 && (
                    <span
                      className={`px-1.5 py-0.2 rounded text-[10px] font-mono font-bold ${
                        isSelected ? "bg-white/20 text-white" : "bg-[#e5e5ea] text-neutral-700"
                      }`}
                    >
                      {totalPolicies} {totalPolicies === 1 ? "pol" : "pols"} · {totalCars} {totalCars === 1 ? "car" : "cars"}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Row 2: 12 Months Tabs with Start/End Hover Tooltip - ONLY SHOWN IN CALENDAR VIEW */}
        {viewMode === "calendar" && (
          <div className="space-y-1.5 pt-2 border-t border-[#f2f2f7]">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-neutral-700 uppercase tracking-wide">
                Step 2: Filter by Month
              </span>
              <span className="text-[10px] text-neutral-400">
                Hover over a month to see starting vs expiring breakdown
              </span>
            </div>

            {loadingMonths ? (
              <div className="h-9 flex items-center text-xs text-[#8e8e93]">Loading tenure timeline...</div>
            ) : (
              <div
                ref={monthScrollRef}
                className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-0.5 scroll-smooth scrollbar-thin"
              >
                {/* "All Months" tab */}
                <button
                  type="button"
                  onClick={() => setSelectedMonth("all")}
                  className={`shrink-0 min-w-max px-3.5 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 cursor-pointer ${
                    selectedMonth === "all"
                      ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                      : "bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
                  }`}
                >
                  <span>{selectedYear === "all" ? "All Months" : `All ${selectedYear}`}</span>
                </button>

                {/* 12 Months: Jan to Dec */}
                {monthsOfYear.map((m) => {
                  const isActive = selectedMonth === m.month;
                  const isCurrent = m.month === currentMonthKey;
                  const tooltipText = `${m.label} ${selectedYear === "all" ? currentYear : selectedYear}\n• ${m.start_count} Starting\n• ${m.end_count} Expiring\n${m.total} Total Policies · ${m.cars} Cars`;

                  return (
                    <button
                      key={m.month}
                      type="button"
                      data-month={m.month}
                      onClick={() => setSelectedMonth(m.month)}
                      className={`shrink-0 min-w-max px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-medium whitespace-nowrap transition-all flex items-center gap-1.5 cursor-pointer ${
                        isActive
                          ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                          : "bg-[#f5f5f7] text-[#454545] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
                      } ${isCurrent && !isActive ? "ring-1 ring-[#007aff]/60 font-semibold" : ""}`}
                      title={tooltipText}
                    >
                      <span>{m.label}</span>
                      {m.total > 0 && (
                        <span
                          className={`px-1.5 py-0.2 rounded text-[10px] font-bold font-mono ${
                            isActive ? "bg-white/20 text-white" : "bg-[#e5e5ea] text-[#1b1717]"
                          }`}
                        >
                          ({m.total})
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* 3. ACTIVE RENEWALS VS LOST CLIENTS PANEL & SEARCH CONTROLS                 */}
      {/* ========================================================================= */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Category Switcher: Active Renewals vs Issued vs Pending vs Lost Clients */}
        <div className="flex items-center gap-1 bg-[#f5f5f7] p-1 rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] w-fit flex-wrap">
          <button
            type="button"
            onClick={() => {
              setCategory("active");
              setPolicyFilter("all");
              if (stageFilter === "Close - Lose" || stageFilter === "Others") {
                setStageFilter("all");
              }
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-bold transition-all cursor-pointer ${
              category === "active" && policyFilter === "all"
                ? "bg-white text-neutral-900 shadow-2xs"
                : "text-neutral-500 hover:text-neutral-800"
            }`}
          >
            <span>All Renewals ({tenures.length})</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setCategory("active");
              setPolicyFilter("issued");
              if (stageFilter === "Close - Lose" || stageFilter === "Others") {
                setStageFilter("all");
              }
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-bold transition-all cursor-pointer ${
              category === "active" && policyFilter === "issued"
                ? "bg-emerald-600 text-white shadow-2xs"
                : "text-emerald-700 hover:text-emerald-900 hover:bg-emerald-50"
            }`}
            title="Filter to vehicles with an issued policy / cover note bound"
          >
            <CheckCircle size={13} weight="bold" />
            <span>Issued Policies ({issuedCount})</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setCategory("active");
              setPolicyFilter("pending");
              if (stageFilter === "Close - Lose" || stageFilter === "Others") {
                setStageFilter("all");
              }
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-bold transition-all cursor-pointer ${
              category === "active" && policyFilter === "pending"
                ? "bg-amber-600 text-white shadow-2xs"
                : "text-amber-700 hover:text-amber-900 hover:bg-amber-50"
            }`}
            title="Filter to vehicles awaiting cover note upload / policy issue"
          >
            <span>Awaiting Cover Note ({pendingCount})</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setCategory("lost");
              setPolicyFilter("all");
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-bold transition-all cursor-pointer ${
              category === "lost"
                ? "bg-rose-50 text-rose-900 border border-rose-200 shadow-2xs"
                : "text-neutral-500 hover:text-neutral-800"
            }`}
          >
            <Archive size={14} weight={category === "lost" ? "bold" : "regular"} />
            <span>Lost Clients &amp; Win-Backs</span>
          </button>
        </div>

        {/* Bulk Actions Pill */}
        {selectedTenureIds.length > 0 && (
          <div className="flex items-center gap-2 bg-neutral-900 text-white px-3 py-1.5 rounded-[var(--rl-radius-sm)] shadow-md animate-fadeIn flex-wrap">
            <span className="text-xs font-bold text-neutral-200">
              {selectedTenureIds.length} selected
            </span>
            <button
              type="button"
              onClick={handleBulkConfirmHit}
              disabled={confirmingBulk}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all shadow-xs cursor-pointer disabled:opacity-50"
              title="Confirm policy as Hit (Won / Issued Policy) for all selected deals in one go"
            >
              <CheckCircle size={13} weight="bold" />
              <span>{confirmingBulk ? "Confirming..." : `Bulk Confirm Hit (${selectedTenureIds.length})`}</span>
            </button>
            <button
              type="button"
              onClick={handleBulkDelete}
              disabled={deletingBulk}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-all shadow-xs cursor-pointer disabled:opacity-50"
              title="Delete all selected deals"
            >
              <Trash size={13} weight="bold" />
              <span>{deletingBulk ? "Deleting..." : "Delete Selected"}</span>
            </button>
            <button
              type="button"
              onClick={() => setSelectedTenureIds([])}
              className="text-[11px] text-neutral-400 hover:text-white underline cursor-pointer"
            >
              Clear
            </button>
          </div>
        )}

        {/* Search & View Mode Switcher */}
        <div className="flex items-center gap-2 flex-1 max-w-lg justify-end">
          <div className="relative flex-1">
            <MagnifyingGlass className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search plate (e.g. JRC 3838), client, subagent, comment..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-9 pl-9 pr-3 rounded-[var(--rl-radius-sm)] border border-neutral-200 bg-white text-xs font-medium focus:ring-1 focus:ring-neutral-900 outline-none"
            />
          </div>

          <div className="flex items-center gap-1 bg-[#f5f5f7] p-1 rounded-[var(--rl-radius-sm)] border border-[#e5e5ea]">
            <button
              type="button"
              onClick={() => setViewMode("ledger")}
              className={`p-1.5 rounded-[var(--rl-radius-sm)] text-xs transition-all cursor-pointer ${
                viewMode === "ledger"
                  ? "bg-white text-neutral-900 shadow-2xs"
                  : "text-neutral-500 hover:text-neutral-800"
              }`}
              title="Table Ledger View"
            >
              <Table size={16} weight={viewMode === "ledger" ? "bold" : "regular"} />
            </button>
            <button
              type="button"
              onClick={() => setViewMode("calendar")}
              className={`p-1.5 rounded-[var(--rl-radius-sm)] text-xs transition-all cursor-pointer ${
                viewMode === "calendar"
                  ? "bg-white text-neutral-900 shadow-2xs"
                  : "text-neutral-500 hover:text-neutral-800"
              }`}
              title="Calendar Expiry View"
            >
              <CalendarBlank size={16} weight={viewMode === "calendar" ? "bold" : "regular"} />
            </button>
          </div>

          <button
            type="button"
            onClick={() => setShowHidden(!showHidden)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-bold transition-all border cursor-pointer ${
              showHidden
                ? "bg-amber-100 text-amber-900 border-amber-300 shadow-2xs"
                : "bg-white text-neutral-600 border-neutral-200 hover:text-neutral-900"
            }`}
            title="Toggle display of older superseded or archived tenures"
          >
            <Archive size={14} weight={showHidden ? "fill" : "regular"} />
            <span>{showHidden ? "Hide Superseded" : "Show Superseded"}</span>
          </button>

          <Link
            href={"/upload/marketing-comparison" as Route}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--rl-radius-sm)] bg-neutral-900 hover:bg-neutral-800 text-white text-xs font-bold transition-all shadow-xs cursor-pointer"
            title="Intake quotations & build Marketing Comparison matrix"
          >
            <Plus size={14} weight="bold" />
            <span>Add Vehicle</span>
          </Link>
        </div>
      </div>

      {/* Advisory Banner for Lost Clients Panel */}
      {category === "lost" && (
        <div className="flex items-center justify-between p-3 rounded-[var(--rl-radius)] border border-rose-200 bg-rose-50/70 text-xs text-rose-900">
          <div className="flex items-center gap-2">
            <Archive size={16} className="text-rose-700 shrink-0" />
            <span>
              <strong>Lost Clients Panel:</strong> Policies closed as <em>Close - Lose</em> or <em>Others</em> are segregated here to keep upcoming renewal pipelines clean, while preserving follow-up reminders and win-back opportunities.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setCategory("active")}
            className="text-xs font-bold underline hover:no-underline text-rose-800 shrink-0 ml-2 cursor-pointer"
          >
            Back to Active Ledger
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 4. VIEW 1: EXECUTIVE TABLE LEDGER & INLINE EXPANDABLE SUB-PANEL            */}
      {/* ========================================================================= */}
      {viewMode === "ledger" && (
        <div className="bg-white border border-neutral-200/90 rounded-[var(--rl-radius)] overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs whitespace-nowrap">
              <thead className="bg-[#f9f9fb] border-b border-neutral-200/80 text-[11px] font-bold uppercase tracking-wider text-neutral-600">
                <tr>
                  <th className="py-3 px-3 w-16 text-center">
                    <div className="flex items-center justify-center">
                      <input
                        type="checkbox"
                        checked={tenures.length > 0 && selectedTenureIds.length === tenures.length}
                        onChange={handleToggleSelectAll}
                        className="w-3.5 h-3.5 rounded border-neutral-300 text-neutral-900 focus:ring-neutral-900 cursor-pointer"
                        title="Select all policies on this page"
                        aria-label="Select all policies on this page"
                      />
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort("vehicle_no")}
                    className="py-3 px-3 min-w-[200px] cursor-pointer hover:text-black transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Vehicle &amp; Customer</span>
                      <span className={`text-[10px] transition-colors ${sortBy === "vehicle_no" ? "text-neutral-900 font-bold" : "text-neutral-300"}`}>
                        {sortBy === "vehicle_no" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                      </span>
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort("coverage_period")}
                    className="py-3 px-3 min-w-[170px] cursor-pointer hover:text-black transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Coverage Period</span>
                      <span className={`text-[10px] transition-colors ${sortBy === "coverage_period" ? "text-neutral-900 font-bold" : "text-neutral-300"}`}>
                        {sortBy === "coverage_period" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                      </span>
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort("stage")}
                    className="py-3 px-3 min-w-[340px] cursor-pointer hover:text-black transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Pipeline Stage</span>
                      <span className={`text-[10px] transition-colors ${sortBy === "stage" ? "text-neutral-900 font-bold" : "text-neutral-300"}`}>
                        {sortBy === "stage" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                      </span>
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort("last_activity")}
                    className="py-3 px-3 min-w-[190px] cursor-pointer hover:text-black transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Latest Activity &amp; Quotes</span>
                      <span className={`text-[10px] transition-colors ${sortBy === "last_activity" ? "text-neutral-900 font-bold" : "text-neutral-300"}`}>
                        {sortBy === "last_activity" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                      </span>
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort("created_at")}
                    className="py-3 px-3 min-w-[160px] cursor-pointer hover:text-black transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Date of Ledger Creation</span>
                      <span className={`text-[10px] transition-colors ${sortBy === "created_at" ? "text-neutral-900 font-bold" : "text-neutral-300"}`}>
                        {sortBy === "created_at" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                      </span>
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort("pic")}
                    className="py-3 px-3 min-w-[160px] cursor-pointer hover:text-black transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <span>PIC &amp; Milestones</span>
                      <span className={`text-[10px] transition-colors ${sortBy === "pic" ? "text-neutral-900 font-bold" : "text-neutral-300"}`}>
                        {sortBy === "pic" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                      </span>
                    </div>
                  </th>
                  <th className="py-3 px-3 text-right min-w-[190px]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {loadingTenures ? (
                  <tr>
                    <td colSpan={8} className="py-14 text-center text-neutral-400">
                      <ArrowsClockwise className="w-5 h-5 animate-spin mx-auto mb-2 text-neutral-500" />
                      Loading Motor Renewal Ledger...
                    </td>
                  </tr>
                ) : tenures.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-14 text-center text-neutral-400">
                      {category === "lost"
                        ? "No lost client records found matching the active filters."
                        : `No active renewal policies found for ${selectedMonth === "all" ? selectedYear : selectedMonth}.`}
                    </td>
                  </tr>
                ) : (
                  vehicleGroups.map((group) => {
                    const mainTenure = group.mainTenure;
                    const picInfo = getPicDisplay(mainTenure);
                    const stageConf = STAGE_CONFIGS[mainTenure.stage] || STAGE_CONFIGS.Quotations;
                    const isOverdue = mainTenure.days_in_stage > 7 && !stageConf.isLost && mainTenure.stage !== "Close - Win";
                    const isPolicyIssued = Boolean(
                      mainTenure.covernote_policy ||
                      mainTenure.is_covernote_issued ||
                      mainTenure.stage === "Close - Win" ||
                      mainTenure.status === "hit"
                    );
                    const isGroupSelected = group.tenures.some((t) => selectedTenureIds.includes(t.id));
                    const displayName = getVehicleDisplayName(group.vehicle_no, group.chassis_no);
                    const isChassis = displayName.startsWith("Chassis:");
                    const isBlank = displayName === "No Plate (Blank)";

                    return (
                      <React.Fragment key={group.vehicle_no}>
                        {/* Primary Vehicle Row */}
                        <tr
                          id={`tenure-row-${mainTenure.id}`}
                          className={`hover:bg-neutral-50/80 transition-colors ${
                            highlightedTenureId === mainTenure.id
                              ? "bg-emerald-50/90 ring-2 ring-emerald-500/80 ring-inset shadow-md transition-all duration-1000"
                              : stageConf.isLost
                              ? "bg-rose-50/20"
                              : ""
                          }`}
                        >
                          {/* 0. Select Checkbox & Direct Delete */}
                          <td className="py-3 px-3 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              <input
                                type="checkbox"
                                checked={isGroupSelected}
                                onChange={() => {
                                  const ids = group.tenures.map((t) => t.id);
                                  if (isGroupSelected) {
                                    setSelectedTenureIds((prev) => prev.filter((id) => !ids.includes(id)));
                                  } else {
                                    setSelectedTenureIds((prev) => [...prev, ...ids]);
                                  }
                                }}
                                className="w-3.5 h-3.5 rounded border-neutral-300 text-neutral-900 focus:ring-neutral-900 cursor-pointer"
                                title={`Select ${displayName}`}
                                aria-label={`Select ${displayName}`}
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  const allIds = group.tenures.map((t) => t.id);
                                  setDeleteConfirmTarget({ id: mainTenure.id, vehicleNo: displayName, allIds });
                                }}
                                className="flex size-6 items-center justify-center rounded text-neutral-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                                title={`Delete ${displayName}`}
                                aria-label={`Delete ${displayName}`}
                              >
                                <Trash size={13} weight="bold" />
                              </button>
                            </div>
                          </td>

                          {/* 1. Vehicle & Client */}
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <div className="font-bold text-neutral-900 font-mono text-sm flex items-center gap-1.5">
                                <Car className="w-3.5 h-3.5 text-neutral-600 shrink-0" />
                                <span className="truncate max-w-[150px]" title={displayName}>
                                  {displayName}
                                </span>
                              </div>

                              {isChassis && (
                                <span className="px-1.5 py-0.2 rounded bg-amber-100 text-amber-900 font-sans text-[9px] font-bold shrink-0">
                                  CHASSIS
                                </span>
                              )}
                              {isBlank && (
                                <span className="px-1.5 py-0.2 rounded bg-neutral-100 text-neutral-600 font-sans text-[9px] font-bold shrink-0">
                                  NO PLATE
                                </span>
                              )}
                              <button
                                type="button"
                                onClick={() => setEditingTenure(mainTenure)}
                                className="p-1 rounded text-neutral-400 hover:text-neutral-900 hover:bg-neutral-100 transition-colors cursor-pointer"
                                title="Edit Customer, Plate & Deal Details"
                              >
                                <PencilSimple size={13} weight="bold" />
                              </button>
                            </div>
                            <div className="flex items-center gap-1.5 mt-0.5">
                              <Link
                                href={`/client-records?search=${encodeURIComponent(group.customer_name)}` as Route}
                                className="text-neutral-800 hover:text-blue-600 font-medium text-[11px] truncate max-w-[140px] inline-block"
                                title={`View client record for ${group.customer_name}`}
                              >
                                {group.customer_name}
                              </Link>
                              {group.customer_ic_no && (
                                <span className="text-[10px] text-neutral-400 font-mono truncate max-w-[90px]">
                                  {group.customer_ic_no}
                                </span>
                              )}
                            </div>
                            {(group.car_model || group.car_brand || group.engine_cc || group.manufacture_year) && (
                              <div className="text-[10px] text-neutral-500 font-medium mt-0.5 truncate max-w-[210px]">
                                {group.car_brand ? `${group.car_brand} ` : ""}
                                {group.car_model || ""}
                                {group.engine_cc ? ` · ${group.engine_cc}cc` : ""}
                                {group.manufacture_year ? ` · YOM ${group.manufacture_year}` : ""}
                              </div>
                            )}
                            {mainTenure.created_by_email && (
                              <div className="text-[10px] text-neutral-400 font-medium mt-0.5 truncate max-w-[210px] flex items-center gap-1">
                                <span>By:</span>
                                <span className="text-neutral-600 font-semibold">{mainTenure.created_by_email}</span>
                              </div>
                            )}
                          </td>

                          {/* 2. Coverage Period (Main Policy) */}
                          <td className="py-3 px-3">
                            {isPolicyIssued && (mainTenure.covernote_policy?.coverage_start_date || mainTenure.coverage_start_date) ? (
                              <div className="space-y-0.5">
                                <div className="flex items-center gap-1 text-[11px]">
                                  <span className="text-[9px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-1 py-0.2 rounded border border-emerald-200 shrink-0">
                                    Start
                                  </span>
                                  <span className="font-mono font-medium text-neutral-800">
                                    {formatDateSafe(mainTenure.covernote_policy?.coverage_start_date || mainTenure.coverage_start_date)}
                                  </span>
                                </div>
                                <div className="flex items-center gap-1 text-[11px]">
                                  <span className="text-[9px] font-bold uppercase tracking-wider text-rose-700 bg-rose-50 px-1 py-0.2 rounded border border-rose-200 shrink-0">
                                    End
                                  </span>
                                  <span className="font-mono font-medium text-neutral-800">
                                    {formatDateSafe(mainTenure.covernote_policy?.coverage_end_date || mainTenure.coverage_end_date)}
                                  </span>
                                </div>
                                <div className="text-[9.5px] text-emerald-700 font-bold flex items-center gap-0.5 pt-0.5">
                                  <CheckCircle size={10} weight="fill" /> Issued Policy
                                </div>
                              </div>
                            ) : mainTenure.external_policy_start_date ? (
                              <div className="space-y-0.5">
                                <span className="text-[9px] font-bold uppercase tracking-wider text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded border border-purple-200">
                                  External Policy
                                </span>
                                <div className="text-[11px] font-mono text-neutral-700">
                                  {formatDateSafe(mainTenure.external_policy_start_date)} → {formatDateSafe(mainTenure.external_policy_end_date)}
                                </div>
                              </div>
                            ) : (mainTenure.coverage_start_date && mainTenure.coverage_end_date && mainTenure.sourced_quotes && mainTenure.sourced_quotes.length > 0) ? (
                              <div className="space-y-0.5">
                                <div className="flex items-center gap-1 text-[11px]">
                                  <span className="text-[9px] font-bold uppercase tracking-wider text-amber-700 bg-amber-50 px-1 py-0.2 rounded border border-amber-200 shrink-0">
                                    Start
                                  </span>
                                  <span className="font-mono font-medium text-neutral-800">
                                    {formatDateSafe(mainTenure.coverage_start_date)}
                                  </span>
                                </div>
                                <div className="flex items-center gap-1 text-[11px]">
                                  <span className="text-[9px] font-bold uppercase tracking-wider text-amber-700 bg-amber-50 px-1 py-0.2 rounded border border-amber-200 shrink-0">
                                    End
                                  </span>
                                  <span className="font-mono font-medium text-neutral-800">
                                    {formatDateSafe(mainTenure.coverage_end_date)}
                                  </span>
                                </div>
                                <div className="text-[9.5px] text-amber-700 font-semibold pt-0.5">
                                  Pending Cover Note
                                </div>
                              </div>
                            ) : (
                              <div className="space-y-0.5">
                                <span className="text-neutral-400 font-mono text-xs">—</span>
                                <div className="text-[10px] text-neutral-400 font-medium">Pending Renewal</div>
                              </div>
                            )}
                            <div className="flex items-center gap-1.5 mt-1">
                              {mainTenure.expiry_month ? (
                                <span className="text-[10px] text-neutral-500 font-medium font-mono">
                                  Exp: {mainTenure.expiry_month}
                                </span>
                              ) : (
                                <span className="text-[10px] text-neutral-400 font-medium italic">
                                  Extracted on Upload
                                </span>
                              )}
                              {mainTenure.is_main && (
                                <span className="px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-800 text-[9px] font-bold border border-emerald-200 flex items-center gap-0.5">
                                  ★ Main
                                </span>
                              )}
                            </div>
                          </td>

                          {/* 3. Pipeline Stage (Main Policy) */}
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-1.5">
                              {renderPipelineProgress(mainTenure)}
                              <span
                                className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold font-mono shrink-0 ${
                                  isOverdue
                                    ? "bg-rose-100 text-rose-800 border border-rose-200"
                                    : "bg-neutral-100 text-neutral-700"
                                }`}
                                title={`${mainTenure.days_in_stage} day(s) in this pipeline stage`}
                              >
                                {mainTenure.days_in_stage}d
                              </span>
                            </div>
                          </td>

                          {/* 4. Policy Details & Sourced Quotes */}
                          <td className="py-3 px-3">
                            {mainTenure.covernote_policy ? (
                              <div className="space-y-1.5 min-w-[210px] max-w-[260px]">
                                {/* Official Issued Cover Note Top Strip */}
                                <div className="flex items-center justify-between gap-1.5 flex-wrap">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-900 border border-emerald-300 text-[10px] font-bold">
                                      <CheckCircle size={12} weight="fill" className="text-emerald-700" />
                                      {mainTenure.covernote_policy.company}
                                    </span>
                                    <span className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-800 text-[9px] font-bold border border-emerald-200">
                                      ⚡ Policy Issued · {formatRelativeTime(mainTenure.last_activity_at || mainTenure.created_at) || "Recent"}
                                    </span>
                                  </div>
                                  {mainTenure.covernote_policy.total_payable && (
                                    <span className="text-emerald-950 font-mono font-bold text-xs bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                                      RM {Number(mainTenure.covernote_policy.total_payable).toFixed(2)}
                                    </span>
                                  )}
                                </div>

                                {/* Authentic Insurance Period & Policy # */}
                                <div className="text-[10.5px] font-mono text-neutral-700 flex items-center justify-between gap-1">
                                  <span className="font-semibold text-neutral-900">
                                    {formatDateSafe(mainTenure.covernote_policy.coverage_start_date)} – {formatDateSafe(mainTenure.covernote_policy.coverage_end_date)}
                                  </span>
                                  {mainTenure.covernote_policy.policy_number && (
                                    <span className="text-[9.5px] text-neutral-500 truncate" title={mainTenure.covernote_policy.policy_number}>
                                      #{mainTenure.covernote_policy.policy_number}
                                    </span>
                                  )}
                                </div>

                                {/* Key Perils */}
                                {mainTenure.covernote_policy.perils && (
                                  <div className="text-[9.5px] text-neutral-600 truncate bg-neutral-50 px-1.5 py-0.5 rounded border border-neutral-200/60" title={mainTenure.covernote_policy.perils}>
                                    🛡️ {mainTenure.covernote_policy.perils}
                                  </div>
                                )}

                                {/* Direct PDF Link & Quick Hit Action */}
                                <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                                  {mainTenure.covernote_policy.uploaded_file_id && (
                                    <a
                                      href={fileUrl(`/uploaded-files/${mainTenure.covernote_policy.uploaded_file_id}/content`)}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-[10px] font-bold border border-emerald-300 transition-colors"
                                      title="Download official Cover Note PDF"
                                    >
                                      <FilePdf size={11} weight="fill" className="text-emerald-600" />
                                      <span>Policy PDF</span>
                                    </a>
                                  )}

                                  {mainTenure.stage === "Issue Policy" && (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setHitConfirmTenure(mainTenure);
                                        const startCandidate = mainTenure.covernote_policy?.coverage_start_date || mainTenure.coverage_start_date || new Date().toISOString().split("T")[0];
                                        setHitConfirmedStartDate(startCandidate);
                                        if (mainTenure.covernote_policy?.coverage_end_date || mainTenure.coverage_end_date) {
                                          setHitConfirmedEndDate(mainTenure.covernote_policy?.coverage_end_date || mainTenure.coverage_end_date);
                                        } else {
                                          const endD = new Date(startCandidate);
                                          endD.setDate(endD.getDate() + 364);
                                          setHitConfirmedEndDate(endD.toISOString().split("T")[0]);
                                        }
                                        setHitConfirmedInsurer(mainTenure.covernote_policy?.company || mainTenure.winning_company_name || "");
                                      }}
                                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-700 hover:bg-emerald-800 text-white text-[10px] font-bold shadow-2xs transition-colors cursor-pointer"
                                      title="Policy is issued! Click to seal HIT"
                                    >
                                      <CheckCircle size={11} weight="bold" />
                                      <span>Confirm Hit ✓</span>
                                    </button>
                                  )}
                                </div>

                                {/* Multi-Insurer Quotation Quick Links (target="_blank" for middle/right click) */}
                                {mainTenure.sourced_quotes && mainTenure.sourced_quotes.length > 0 && (
                                  <div className="flex items-center gap-1 flex-wrap pt-1 border-t border-neutral-100">
                                    <span className="text-[9px] font-bold text-neutral-400 uppercase">Quotes:</span>
                                    {mainTenure.sourced_quotes.map((q) => (
                                      <Link
                                        key={q.session_id}
                                        href={`/workspace?session_id=${q.session_id}` as Route}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className={`inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] transition-colors border shadow-2xs hover:border-neutral-900 ${
                                          q.is_winner
                                            ? "bg-amber-50 text-amber-900 border-amber-300 font-bold"
                                            : "bg-white text-neutral-700 border-neutral-200 hover:bg-neutral-50 font-medium"
                                        }`}
                                        title={`Open ${q.company} quote workspace in new tab (middle-click/right-click enabled)`}
                                      >
                                        <span>{q.company}</span>
                                        {q.total_payable && (
                                          <span className="font-mono text-[9px] text-neutral-500 font-bold">
                                            {Number(q.total_payable).toFixed(0)}
                                          </span>
                                        )}
                                      </Link>
                                    ))}
                                    <Link
                                      href={`/comparison?tenure_id=${mainTenure.id}` as Route}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-0.5 text-[10px] font-bold text-amber-800 hover:text-amber-950 hover:underline ml-0.5"
                                      title="Open Marketing Comparison in new tab"
                                    >
                                      <span>({mainTenure.sourced_quotes.length}) →</span>
                                    </Link>
                                  </div>
                                )}
                              </div>
                            ) : mainTenure.sourced_quotes.length === 0 ? (
                              <div className="space-y-1">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span className="text-neutral-400 italic text-[11px]">0 quotes compiled</span>
                                  <span className="inline-flex items-center px-1.5 py-0.2 rounded bg-neutral-100 text-neutral-600 text-[9px] font-medium border border-neutral-200">
                                    Awaiting Cover Note
                                  </span>
                                </div>
                                <div className="text-[10px] text-neutral-500 font-mono">
                                  {formatDateSafe(mainTenure.coverage_start_date)} – {formatDateSafe(mainTenure.coverage_end_date)}
                                </div>
                                <Link
                                  href={`/comparison?tenure_id=${mainTenure.id}` as Route}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-[10px] font-bold text-neutral-700 hover:text-black underline"
                                >
                                  <span>Open Comparison Matrix →</span>
                                </Link>
                              </div>
                            ) : (
                              <div className="space-y-1.5 min-w-[210px] max-w-[260px]">
                                {/* Leading / Sourced Quote Strip */}
                                <div className="flex items-center justify-between gap-1.5 flex-wrap">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span className="font-bold text-xs text-neutral-900 truncate">
                                      {mainTenure.winning_company_name || mainTenure.sourced_quotes[0].company}
                                    </span>
                                    <span className="inline-flex items-center px-1.5 py-0.2 rounded bg-amber-50 text-amber-800 text-[9px] font-bold border border-amber-200">
                                      Awaiting Cover Note
                                    </span>
                                  </div>
                                  {(mainTenure.won_premium ? String(mainTenure.won_premium) : mainTenure.sourced_quotes[0].total_payable) && (
                                    <span className="text-neutral-900 font-mono font-bold text-xs bg-neutral-100 px-1.5 py-0.5 rounded border border-neutral-200 shrink-0">
                                      RM {mainTenure.won_premium || mainTenure.sourced_quotes[0].total_payable}
                                    </span>
                                  )}
                                </div>

                                {/* Target Coverage Period */}
                                <div className="text-[10.5px] font-mono text-neutral-600">
                                  {formatDateSafe(mainTenure.coverage_start_date)} – {formatDateSafe(mainTenure.coverage_end_date)}
                                </div>

                                {/* Multi-Insurer Quotation Quick-Links (target="_blank" for middle/right click) */}
                                <div className="flex items-center gap-1 flex-wrap pt-0.5">
                                  {mainTenure.sourced_quotes.map((q) => (
                                    <Link
                                      key={q.session_id}
                                      href={`/workspace?session_id=${q.session_id}` as Route}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] transition-colors border shadow-2xs hover:border-neutral-900 ${
                                        q.is_winner
                                          ? "bg-amber-50 text-amber-900 border-amber-300 font-bold"
                                          : "bg-white text-neutral-700 border-neutral-200 hover:bg-neutral-50 font-medium"
                                      }`}
                                      title={`Open ${q.company} quote in new tab (middle/right-click enabled)`}
                                    >
                                      <span>{q.company}</span>
                                      {q.total_payable && (
                                        <span className="font-mono text-[9px] text-neutral-500 font-bold">
                                          {Number(q.total_payable).toFixed(0)}
                                        </span>
                                      )}
                                    </Link>
                                  ))}
                                  <Link
                                    href={`/comparison?tenure_id=${mainTenure.id}` as Route}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-0.5 text-[10px] font-bold text-amber-800 hover:text-amber-950 hover:underline ml-0.5"
                                    title="Open Marketing Comparison in new tab"
                                  >
                                    <span>({mainTenure.sourced_quotes.length}) →</span>
                                  </Link>
                                </div>

                                {/* PDF links */}
                                <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                                  {mainTenure.winning_file_id ? (
                                    <a
                                      href={fileUrl(`/uploaded-files/${mainTenure.winning_file_id}/content`)}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-[10px] font-bold border border-emerald-300 transition-colors cursor-pointer"
                                      title={`Accepted Quotation PDF: ${mainTenure.winning_file_name || "Quotation PDF"}`}
                                    >
                                      <FilePdf size={11} weight="fill" className="text-emerald-600" />
                                      <span className="truncate max-w-[120px]">
                                        {mainTenure.stage === "Close - Win" || mainTenure.status === "hit" ? "Accepted PDF" : "Quote PDF"}
                                      </span>
                                    </a>
                                  ) : mainTenure.sourced_quotes?.find(q => q.uploaded_file_id) ? (
                                    (() => {
                                      const winQuote = mainTenure.sourced_quotes.find(q => q.is_winner && q.uploaded_file_id) || mainTenure.sourced_quotes.find(q => q.uploaded_file_id);
                                      const isActualWinner = Boolean(winQuote?.is_winner || mainTenure.stage === "Close - Win" || mainTenure.status === "hit");
                                      return winQuote?.uploaded_file_id ? (
                                        <a
                                          href={fileUrl(`/uploaded-files/${winQuote.uploaded_file_id}/content`)}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold border transition-colors cursor-pointer ${
                                            isActualWinner
                                              ? "bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border-emerald-300"
                                              : "bg-blue-50 hover:bg-blue-100 text-blue-800 border-blue-200"
                                          }`}
                                          title={`Quotation PDF: ${winQuote.file_name || winQuote.company}`}
                                        >
                                          <FilePdf size={11} weight="fill" className={isActualWinner ? "text-emerald-600" : "text-blue-600"} />
                                          <span className="truncate max-w-[120px]">{isActualWinner ? "Accepted PDF" : "Quote PDF"}</span>
                                        </a>
                                      ) : null;
                                    })()
                                  ) : null}
                                  {mainTenure.generated_quotations && mainTenure.generated_quotations.length > 0 && (
                                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-700 text-[10px] font-bold border border-neutral-200">
                                      <FilePdf size={11} weight="fill" className="text-neutral-500" />
                                      <span>{mainTenure.generated_quotations.length} Quote Gen</span>
                                    </span>
                                  )}
                                </div>
                              </div>
                            )}
                          </td>

                          {/* 5. Date of Ledger Creation */}
                          <td className="py-3 px-3 min-w-[150px]">
                            <div className="space-y-0.5">
                              <div className="text-[11px] font-mono font-semibold text-neutral-900">
                                {formatDateSafe(mainTenure.created_at)}
                              </div>
                              <div className="text-[10px] font-mono text-neutral-500">
                                {mainTenure.created_at ? (() => {
                                  try {
                                    const d = new Date(mainTenure.created_at);
                                    return isNaN(d.getTime())
                                      ? ""
                                      : d.toLocaleTimeString("en-MY", {
                                          hour: "2-digit",
                                          minute: "2-digit",
                                          hour12: true,
                                        });
                                  } catch {
                                    return "";
                                  }
                                })() : "—"}
                              </div>
                            </div>
                          </td>

                          {/* 6. PIC & Milestones */}
                          <td className="py-3 px-3">
                            <div className="space-y-1.5">
                              {/* Row 1: PIC info */}
                              <div className="flex items-center gap-1.5 flex-wrap text-xs">
                                {picInfo ? (
                                  <div className="flex items-center gap-1">
                                    <span className="font-semibold text-neutral-800 truncate max-w-[110px]" title={`PIC: ${picInfo.name}`}>
                                      {picInfo.name}
                                    </span>
                                    {picInfo.whatsapp && (
                                      <a
                                        href={`https://wa.me/${picInfo.whatsapp.replace(/[^0-9]/g, "")}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-emerald-600 hover:text-emerald-800 text-[10px] font-bold bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200"
                                        title={`WhatsApp ${picInfo.whatsapp}`}
                                      >
                                        WA
                                      </a>
                                    )}
                                  </div>
                                ) : (
                                  <span className="text-neutral-400 italic text-[11px]">Unassigned</span>
                                )}
                              </div>

                              {/* Row 2: Payment Status */}
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                                    mainTenure.client_payment_received
                                      ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                      : "bg-neutral-50 text-neutral-500 border-neutral-200"
                                  }`}
                                  title="Client Payment Status"
                                >
                                  {mainTenure.client_payment_received ? "✓ Cli Paid" : "Cli Unpaid"}
                                </span>
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                                    mainTenure.agency_payment_done
                                      ? "bg-blue-50 text-blue-800 border-blue-200"
                                      : "bg-neutral-50 text-neutral-500 border-neutral-200"
                                  }`}
                                  title="Agency Payment Status"
                                >
                                  {mainTenure.agency_payment_done ? "✓ Agc Paid" : "Agc Due"}
                                </span>
                              </div>
                            </div>
                          </td>

                          {/* 6. Actions */}
                          <td className="py-3 px-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <Link
                                href={`/comparison?tenure_id=${mainTenure.id}` as Route}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-[#1b1717] hover:bg-black text-white text-xs font-bold transition-colors shadow-2xs cursor-pointer"
                                title="Go to Marketing Comparison matrix for this vehicle (New Tab)"
                              >
                                <Columns className="w-3.5 h-3.5" />
                                <span>Compare</span>
                              </Link>

                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => setActiveDrawerTenureId(mainTenure.id)}
                                className="h-7 text-xs font-semibold cursor-pointer border-[#e5e5ea] hover:border-black"
                              >
                                Logs
                              </Button>

                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => setEditingTenure(mainTenure)}
                                className="h-7 text-xs font-semibold cursor-pointer border-[#e5e5ea] hover:border-black"
                              >
                                Details
                              </Button>
                            </div>
                          </td>
                        </tr>

                      </React.Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 5. VIEW 2: VISUAL CALENDAR VIEW (MONTH GRID & AGENDA)                      */}
      {/* ========================================================================= */}
      {viewMode === "calendar" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-1">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm font-bold text-neutral-900">
                {calendarData.monthLabel}
              </span>
              <span className="text-xs font-medium text-neutral-500">
                · {calendarData.agendaDays.reduce((acc, g) => acc + g.items.length, 0)} timeline events ({calendarData.agendaDays.reduce((acc, g) => acc + g.items.filter(i => i.type === "start").length, 0)} starting · {calendarData.agendaDays.reduce((acc, g) => acc + g.items.filter(i => i.type === "end").length, 0)} expiring · {calendarData.agendaDays.reduce((acc, g) => acc + g.items.filter(i => i.type === "session").length, 0)} quotes)
              </span>

              {/* Vehicle Filter Selector */}
              <div className="flex items-center gap-1.5 ml-1">
                <label className="text-xs font-bold text-neutral-600">Vehicle:</label>
                <select
                  value={calendarVehicleFilter}
                  onChange={(e) => setCalendarVehicleFilter(e.target.value)}
                  className="h-7 px-2 text-xs font-mono font-bold rounded-[var(--rl-radius-sm)] border border-neutral-300 bg-white text-neutral-800"
                >
                  <option value="all">All Vehicles ({calendarVehicleOptions.length})</option>
                  {calendarVehicleOptions.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
                {loadingCalendar && (
                  <span className="text-xs text-blue-600 font-semibold animate-pulse">Loading quotes...</span>
                )}
              </div>
            </div>

            <div className="flex items-center rounded-[var(--rl-radius-sm)] border border-neutral-200 bg-neutral-100 p-0.5 shrink-0">
              <button
                type="button"
                onClick={() => setCalendarDisplay("grid")}
                className={`px-2.5 py-1 text-xs font-semibold rounded-[var(--rl-radius-sm)] transition-all flex items-center gap-1 ${
                  calendarDisplay === "grid"
                    ? "bg-white text-neutral-900 shadow-2xs"
                    : "text-neutral-500 hover:text-neutral-800"
                }`}
              >
                <CalendarBlank size={13} weight="bold" />
                <span>Month Grid</span>
              </button>
              <button
                type="button"
                onClick={() => setCalendarDisplay("agenda")}
                className={`px-2.5 py-1 text-xs font-semibold rounded-[var(--rl-radius-sm)] transition-all flex items-center gap-1 ${
                  calendarDisplay === "agenda"
                    ? "bg-white text-neutral-900 shadow-2xs"
                    : "text-neutral-500 hover:text-neutral-800"
                }`}
              >
                <ListDashes size={13} weight="bold" />
                <span>Agenda List</span>
              </button>
            </div>
          </div>

          {/* Month Grid */}
          {calendarDisplay === "grid" && (
            <div className="bg-white border border-neutral-200/90 rounded-[var(--rl-radius)] p-3 shadow-2xs">
              <div className="grid grid-cols-7 gap-2 pb-2 border-b border-neutral-100 text-center text-[11px] font-bold uppercase tracking-wider text-neutral-400">
                <span>Sun</span>
                <span>Mon</span>
                <span>Tue</span>
                <span>Wed</span>
                <span>Thu</span>
                <span>Fri</span>
                <span>Sat</span>
              </div>

              <div className="grid grid-cols-7 gap-2 pt-2">
                {Array.from({ length: calendarData.firstDay }).map((_, idx) => (
                  <div
                    key={`blank-${idx}`}
                    className="min-h-[105px] rounded-[var(--rl-radius-sm)] bg-neutral-50/40 border border-dashed border-neutral-150/60"
                  />
                ))}

                {Array.from({ length: calendarData.daysInMonth }).map((_, idx) => {
                  const dayNum = idx + 1;
                  const dayTenures = calendarData.dayMap[dayNum] || [];
                  const isToday =
                    new Date().getFullYear() === calendarData.year &&
                    new Date().getMonth() === calendarData.month &&
                    new Date().getDate() === dayNum;

                  return (
                    <div
                      key={`day-${dayNum}`}
                      className={`min-h-[105px] p-1.5 rounded-[var(--rl-radius-sm)] border flex flex-col transition-all ${
                        isToday
                          ? "bg-blue-50/20 border-blue-400/80 ring-1 ring-blue-300"
                          : dayTenures.length > 0
                          ? "bg-white border-neutral-200 shadow-2xs"
                          : "bg-neutral-50/30 border-neutral-150"
                      }`}
                    >
                      <div className="flex items-center justify-between pb-1 border-b border-neutral-100/60 mb-1">
                        <span
                          className={`text-xs font-bold px-1.5 py-0.2 rounded ${
                            isToday ? "bg-blue-600 text-white" : "text-neutral-700"
                          }`}
                        >
                          {dayNum}
                        </span>

                        {dayTenures.length > 0 && (
                          <span className="text-[10px] font-bold text-neutral-600 bg-neutral-100 px-1.5 py-0.2 rounded-full">
                            {dayTenures.length}
                          </span>
                        )}
                      </div>

                      <div className="flex-1 space-y-1 overflow-y-auto max-h-[110px] scrollbar-thin">
                        {dayTenures.map((item, itemIdx) => {
                          if (item.type === "session") {
                            const s = item.session;
                            return (
                              <div
                                key={`sess-${s.session_id}-${itemIdx}`}
                                className="p-1.5 bg-blue-50/70 hover:bg-blue-100/90 border border-blue-200/90 rounded transition-all text-[11px]"
                              >
                                <div className="flex items-center justify-between gap-1">
                                  <span className="text-[9px] font-bold px-1 py-0.2 rounded uppercase shrink-0 bg-blue-100 text-blue-800 border border-blue-200">
                                    Quote
                                  </span>
                                  <span className="font-bold text-neutral-900 font-mono truncate text-[11px]" title={s.vehicle_no}>
                                    {s.vehicle_no}
                                  </span>
                                </div>
                                <p className="text-[10px] text-blue-900 truncate mt-0.5 font-medium">
                                  {s.detected_company || "Underwriter"}
                                </p>
                                <div className="flex items-center justify-between gap-1 pt-1 mt-1 border-t border-blue-200/50">
                                  <span className="text-[9px] font-bold text-neutral-700 font-mono">
                                    {s.total_payable ? `RM ${s.total_payable}` : (s.sum_insured ? `SI: RM ${s.sum_insured}` : "—")}
                                  </span>
                                  {s.tenure_id ? (
                                    <Link
                                      href={`/comparison?tenure_id=${s.tenure_id}` as Route}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-amber-500 hover:bg-amber-600 text-slate-950 text-[9px] font-bold transition-colors"
                                    >
                                      <Columns className="w-2.5 h-2.5" />
                                      <span>Compare</span>
                                    </Link>
                                  ) : (
                                    <Link
                                      href={`/sessions/${s.session_id}/review` as Route}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-neutral-200 hover:bg-neutral-300 text-neutral-800 text-[9px] font-bold transition-colors"
                                    >
                                      <ArrowSquareOut className="w-2.5 h-2.5" />
                                      <span>Review</span>
                                    </Link>
                                  )}
                                </div>
                              </div>
                            );
                          }

                          const t = item.tenure;
                          const isStart = item.type === "start";
                          const displayName = getVehicleDisplayName(t.vehicle_no, t.chassis_no);

                          return (
                            <div
                              key={`${t.id}-${item.type}-${itemIdx}`}
                              onClick={() => setActiveDrawerTenureId(t.id)}
                              className="p-1.5 bg-neutral-50 hover:bg-neutral-100/90 border border-neutral-200/80 rounded cursor-pointer transition-all hover:shadow-xs group text-[11px]"
                            >
                              <div className="flex items-center justify-between gap-1">
                                <span
                                  className={`text-[9px] font-bold px-1 py-0.2 rounded uppercase shrink-0 ${
                                    isStart
                                      ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                                      : "bg-rose-100 text-rose-800 border border-rose-200"
                                  }`}
                                >
                                  {isStart ? "Start" : "Exp"}
                                </span>
                                <span className="font-bold text-neutral-900 font-mono truncate text-[11px]" title={displayName}>
                                  {displayName}
                                </span>
                              </div>

                              <p className="text-[10px] text-neutral-500 truncate mt-0.5">
                                {t.customer_name}
                              </p>

                              <div className="flex items-center justify-between gap-1 pt-1 mt-1 border-t border-neutral-200/50">
                                <span className="text-[9px] text-neutral-400">
                                  {t.sourced_quotes.length} quotes
                                </span>
                                <Link
                                  href={`/comparison?tenure_id=${t.id}` as Route}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-amber-500 hover:bg-amber-600 text-slate-950 text-[9px] font-bold transition-colors"
                                >
                                  <Columns className="w-2.5 h-2.5" />
                                  <span>Compare</span>
                                </Link>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Agenda List */}
          {calendarDisplay === "agenda" && (
            <div className="space-y-3">
              {calendarData.agendaDays.length === 0 ? (
                <div className="bg-white border border-neutral-200 rounded-[var(--rl-radius)] p-12 text-center text-xs text-neutral-400">
                  No policy start or expiry dates recorded for {calendarData.monthLabel}.
                </div>
              ) : (
                calendarData.agendaDays.map((group) => (
                  <div
                    key={group.day}
                    className="bg-white border border-neutral-200/90 rounded-[var(--rl-radius)] overflow-hidden shadow-2xs"
                  >
                    <div className="px-4 py-2 bg-neutral-50/80 border-b border-neutral-200/70 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CalendarCheck className="w-4 h-4 text-neutral-600" />
                        <span className="text-xs font-bold text-neutral-900">{group.dateStr}</span>
                      </div>
                      <span className="text-[11px] font-semibold text-neutral-500">
                        {group.items.length} {group.items.length === 1 ? "Event" : "Events"} ({group.items.filter(i => i.type === "start").length} Starts · {group.items.filter(i => i.type === "end").length} Expiries)
                      </span>
                    </div>

                    <div className="divide-y divide-neutral-100 p-2">
                      {group.items.map((item, itemIdx) => {
                        if (item.type === "session") {
                          const s = item.session;
                          return (
                            <div
                              key={`agenda-sess-${s.session_id}-${itemIdx}`}
                              className="p-3 hover:bg-blue-50/40 rounded-lg transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 border border-blue-100/60"
                            >
                              <div className="space-y-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-100 text-blue-800 border border-blue-200">
                                    Quotation Uploaded
                                  </span>
                                  <span className="font-bold text-sm text-neutral-900 font-mono">{s.vehicle_no}</span>
                                  <span className="text-xs text-neutral-400">·</span>
                                  <span className="text-xs font-semibold text-neutral-700">
                                    {s.detected_company || "Underwriter"}
                                  </span>
                                  <span className="text-xs text-neutral-400">·</span>
                                  <span className="text-xs font-medium text-neutral-600">{s.customer_name}</span>
                                </div>

                                <div className="flex items-center gap-2 text-xs text-neutral-500 flex-wrap">
                                  <span>Quotation Date:</span>
                                  <strong className="font-mono text-neutral-800">{s.quotation_date}</strong>
                                  <span className="text-neutral-400">·</span>
                                  <span>Total Payable:</span>
                                  <strong className="font-mono text-emerald-700">
                                    {s.total_payable ? `RM ${s.total_payable}` : (s.sum_insured ? `SI: RM ${s.sum_insured}` : "—")}
                                  </strong>
                                </div>
                              </div>

                              <div className="flex items-center gap-2 shrink-0">
                                {s.tenure_id ? (
                                  <Link
                                    href={`/comparison?tenure_id=${s.tenure_id}` as Route}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-colors shadow-2xs"
                                  >
                                    <Columns className="w-3.5 h-3.5" />
                                    <span>Marketing Comparison</span>
                                  </Link>
                                ) : (
                                  <Link
                                    href={`/sessions/${s.session_id}/review` as Route}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-neutral-100 hover:bg-neutral-200 text-neutral-800 text-xs font-bold transition-colors"
                                  >
                                    <ArrowSquareOut className="w-3.5 h-3.5" />
                                    <span>Review Session</span>
                                  </Link>
                                )}
                              </div>
                            </div>
                          );
                        }

                        const t = item.tenure;
                        const isStart = item.type === "start";
                        const displayName = getVehicleDisplayName(t.vehicle_no, t.chassis_no);

                        return (
                          <div
                            key={`${t.id}-${item.type}-${itemIdx}`}
                            onClick={() => setActiveDrawerTenureId(t.id)}
                            className="p-3 hover:bg-neutral-50/70 rounded-lg cursor-pointer transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                          >
                            <div className="space-y-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span
                                  className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${
                                    isStart
                                      ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                                      : "bg-rose-100 text-rose-800 border border-rose-200"
                                  }`}
                                >
                                  {isStart ? "Policy Start" : "Policy Expiry"}
                                </span>
                                <span className="font-bold text-sm text-neutral-900 font-mono">{displayName}</span>
                                <span className="text-xs text-neutral-400">·</span>
                                <span className="text-xs font-medium text-neutral-700">{t.customer_name}</span>
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">
                                  {t.stage || "Quotations"}
                                </span>
                              </div>

                              <div className="flex items-center gap-2 text-xs text-neutral-500 flex-wrap">
                                <span>Coverage:</span>
                                {t.stage === "Issue Policy" && t.coverage_start_date ? (
                                  <strong className="font-mono text-neutral-800">
                                    {formatDateSafe(t.coverage_start_date)} – {formatDateSafe(t.coverage_end_date)}
                                  </strong>
                                ) : (
                                  <span className="italic text-neutral-400">
                                    Pending Issue (Confirmed on Policy Issue)
                                  </span>
                                )}
                                <span className="text-neutral-400">·</span>
                                <span>{t.sourced_quotes.length} Quotes</span>
                                {t.sub_agent_name && (
                                  <>
                                    <span className="text-neutral-400">·</span>
                                    <span className="text-emerald-700 font-medium">
                                      PIC: {t.sub_agent_name}
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              <Link
                                href={`/comparison?tenure_id=${t.id}` as Route}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-colors shadow-2xs"
                              >
                                <Columns className="w-3.5 h-3.5" />
                                <span>Marketing Comparison</span>
                              </Link>

                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setActiveDrawerTenureId(t.id);
                                }}
                                className="h-8 text-xs font-medium cursor-pointer"
                              >
                                Logs &amp; Activity <ArrowRight className="w-3.5 h-3.5 ml-1" />
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}

      {/* Slide-out Interactive Tenure Timeline Drawer */}
      {activeDrawerTenureId && (
        <TenureTimelineDrawer
          tenureId={activeDrawerTenureId}
          isOpen={Boolean(activeDrawerTenureId)}
          onClose={() => setActiveDrawerTenureId(null)}
          onRefresh={() => {
            loadTenures();
            loadStageSummary();
          }}
        />
      )}

      {/* Modal for Quick Edit Customer & Vehicle Deal */}
      <EditVehicleDealModal
        isOpen={Boolean(editingTenure)}
        onClose={() => setEditingTenure(null)}
        tenure={editingTenure}
        pics={pics}
        onSave={patchTenureField}
      />

      {/* Modal for Miss / Client Outcome & Keep Client Workflow */}
      {missModalTenure && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="bg-white rounded-[var(--rl-radius)] border border-neutral-200 shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-4 border-b border-neutral-100 bg-[#fbfbfd] flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-neutral-900">Mark Deal as Miss (Client Lost)</h3>
                <p className="text-xs text-neutral-500 font-mono mt-0.5">
                  {missModalTenure.vehicle_no} · {missModalTenure.customer_name}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMissModalTenure(null)}
                className="text-neutral-400 hover:text-neutral-700 text-sm font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* Step 1: Keep or Drop */}
              <div>
                <label className="text-xs font-bold text-neutral-800 block mb-2">
                  Do you want to keep this client for next year&apos;s renewal?
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setKeepClientChoice("keep")}
                    className={`p-3 rounded-lg border text-left text-xs transition-all cursor-pointer ${
                      keepClientChoice === "keep"
                        ? "border-emerald-500 bg-emerald-50/50 text-emerald-950 ring-1 ring-emerald-500"
                        : "border-neutral-200 hover:bg-neutral-50 text-neutral-700"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5">
                      <CheckCircle size={14} weight="bold" className={keepClientChoice === "keep" ? "text-emerald-600" : "text-neutral-400"} />
                      <span>Keep Client</span>
                    </div>
                    <p className="text-[11px] text-neutral-500 mt-1">
                      Keep client profile and track next year&apos;s renewal win-back.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setKeepClientChoice("discard")}
                    className={`p-3 rounded-lg border text-left text-xs transition-all cursor-pointer ${
                      keepClientChoice === "discard"
                        ? "border-rose-500 bg-rose-50/50 text-rose-950 ring-1 ring-rose-500"
                        : "border-neutral-200 hover:bg-neutral-50 text-neutral-700"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5">
                      <XCircle size={14} weight="bold" className={keepClientChoice === "discard" ? "text-rose-600" : "text-neutral-400"} />
                      <span>Drop / Discard</span>
                    </div>
                    <p className="text-[11px] text-neutral-500 mt-1">
                      Client is dropped. Will NOT create next year&apos;s renewal deal.
                    </p>
                  </button>
                </div>
              </div>

              {/* Step 2: Next Year Deal Notification & Checkbox (Only if Keeping Client) */}
              {keepClientChoice === "keep" && (
                <div className="p-3 bg-blue-50/60 border border-blue-200 rounded-lg space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer text-xs font-bold text-blue-950">
                    <input
                      type="checkbox"
                      checked={createNextYearDeal}
                      onChange={(e) => setCreateNextYearDeal(e.target.checked)}
                      className="w-4 h-4 rounded text-blue-600 accent-blue-600 cursor-pointer"
                    />
                    <span>
                      Create {missModalTenure.coverage_start_date ? new Date(missModalTenure.coverage_start_date).getFullYear() + 1 : "Next Year"} Renewal Ledger deal immediately
                    </span>
                  </label>
                  <p className="text-[11px] text-blue-800 pl-6 leading-relaxed">
                    When checked, {missModalTenure.vehicle_no} will be placed into next year&apos;s Renewal Ledger for future follow-up.
                  </p>
                </div>
              )}

              {/* Step 3: Current Year External Insurance Note */}
              <div>
                <label className="text-xs font-semibold text-neutral-700 block mb-1">
                  Current year insurance used by customer <span className="text-neutral-400 font-normal">(optional)</span>:
                </label>
                <input
                  type="text"
                  placeholder="e.g. Etiqa, Allianz, Zurich, Tokio Marine..."
                  value={externalInsurer}
                  onChange={(e) => setExternalInsurer(e.target.value)}
                  className="w-full h-8 px-3 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900"
                />
                <p className="text-[10px] text-neutral-400 mt-0.5">
                  If not known, you can leave this blank.
                </p>
              </div>

              <div>
                <label className="text-xs font-semibold text-neutral-700 block mb-1">
                  Notes / Reason for loss <span className="text-neutral-400 font-normal">(optional)</span>:
                </label>
                <input
                  type="text"
                  placeholder="e.g. Competitor price lower, renewed with bank..."
                  value={missReason}
                  onChange={(e) => setMissReason(e.target.value)}
                  className="w-full h-8 px-3 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900"
                />
              </div>
            </div>

            <div className="p-3 bg-neutral-50 border-t border-neutral-200 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setMissModalTenure(null)}
                className="px-3 py-1.5 text-xs font-medium text-neutral-600 hover:text-neutral-900 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmMiss}
                disabled={savingMissOutcome}
                className="px-4 py-1.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded shadow-xs cursor-pointer disabled:opacity-50"
              >
                {savingMissOutcome ? "Saving..." : "Confirm Miss & Update"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal for Issue Policy Confirmation & Insurance Period Input */}
      {issuePolicyModalTenure && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="bg-white rounded-[var(--rl-radius)] border border-neutral-200 shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-4 border-b border-neutral-100 bg-[#fbfbfd] flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-neutral-900">Confirm Policy Issuance</h3>
                <p className="text-xs text-neutral-500 font-mono mt-0.5">
                  {issuePolicyModalTenure.vehicle_no} · {issuePolicyModalTenure.customer_name}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIssuePolicyModalTenure(null)}
                className="text-neutral-400 hover:text-neutral-700 text-sm font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* Step 1: Confirm Winner */}
              <div>
                <label className="text-xs font-bold text-neutral-800 block mb-1">
                  1. Confirmed Winning Quotation
                </label>
                <p className="text-[11px] text-neutral-500 mb-2">
                  Select the quote that the customer confirmed:
                </p>
                {issuePolicyModalTenure.sourced_quotes.length === 0 ? (
                  <div className="p-2.5 bg-neutral-50 rounded border border-neutral-200 text-xs text-neutral-500 italic">
                    No quotes compiled yet.
                  </div>
                ) : (
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {issuePolicyModalTenure.sourced_quotes.map((q) => {
                      const isSelected = selectedWinnerQuote === q.company;
                      return (
                        <button
                          key={q.session_id}
                          type="button"
                          onClick={() => setSelectedWinnerQuote(q.company)}
                          className={`w-full p-2.5 rounded border text-left text-xs transition-all cursor-pointer flex items-center justify-between ${
                            isSelected
                              ? "border-emerald-500 bg-emerald-50 text-emerald-950 font-bold ring-1 ring-emerald-500"
                              : "border-neutral-200 hover:bg-neutral-50 text-neutral-700"
                          }`}
                        >
                          <span>{q.company}</span>
                          {q.total_payable && (
                            <span className="font-mono text-neutral-900 font-bold">
                              RM {q.total_payable}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Step 2: Input Insurance Period Start Date */}
              <div>
                <label className="text-xs font-bold text-neutral-800 block mb-1">
                  2. Confirmed Insurance Period
                </label>
                <p className="text-[11px] text-neutral-500 mb-2">
                  Enter the official policy start date (coverage automatically runs for 1 full year):
                </p>
                <input
                  type="date"
                  value={policyStartDate}
                  onChange={(e) => setPolicyStartDate(e.target.value)}
                  className="w-full h-9 px-3 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900 font-mono"
                />
                {policyStartDate && (
                  <div className="mt-2 p-2 bg-emerald-50 border border-emerald-200 rounded text-[11px] text-emerald-900 font-mono">
                    Coverage: {policyStartDate} → {(() => {
                      const d = new Date(policyStartDate);
                      d.setDate(d.getDate() + 364);
                      return d.toISOString().split("T")[0];
                    })()}
                  </div>
                )}
              </div>
            </div>

            <div className="p-3 bg-neutral-50 border-t border-neutral-200 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setIssuePolicyModalTenure(null)}
                className="px-3 py-1.5 text-xs font-medium text-neutral-600 hover:text-neutral-900 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!policyStartDate) {
                    alert("Please select an insurance start date.");
                    return;
                  }
                  setSavingIssuePolicy(true);
                  try {
                    const startDt = new Date(policyStartDate);
                    const endDt = new Date(startDt);
                    endDt.setDate(endDt.getDate() + 364);
                    const startStr = startDt.toISOString().split("T")[0];
                    const endStr = endDt.toISOString().split("T")[0];

                    await patchTenureField(issuePolicyModalTenure.id, {
                      stage: "Issue Policy",
                      coverage_start_date: startStr as any,
                      coverage_end_date: endStr as any,
                    });

                    setIssuePolicyModalTenure(null);
                    loadTenures();
                    loadStageSummary();
                  } catch (err: any) {
                    alert("Failed to confirm issue policy: " + (err?.message || err));
                  } finally {
                    setSavingIssuePolicy(false);
                  }
                }}
                disabled={savingIssuePolicy}
                className="px-4 py-1.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded shadow-xs cursor-pointer disabled:opacity-50"
              >
                {savingIssuePolicy ? "Confirming..." : "Confirm & Issue Policy"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal for Hit Confirmation: Confirm Policy Dates, Insurer, and Accepted PDF before marking Hit */}
      {hitConfirmTenure && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="bg-white rounded-[var(--rl-radius)] border border-neutral-200 shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-4 border-b border-neutral-100 bg-[#fbfbfd] flex items-center justify-between">
              <div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle size={16} weight="fill" className="text-emerald-600" />
                  <h3 className="font-bold text-sm text-neutral-900">Confirm Policy &amp; Mark as HIT (Won)</h3>
                </div>
                <p className="text-xs text-neutral-500 font-mono mt-0.5">
                  {hitConfirmTenure.vehicle_no} · {hitConfirmTenure.customer_name}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setHitConfirmTenure(null)}
                className="text-neutral-400 hover:text-neutral-700 text-sm font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* Confirmed Winning Insurer */}
              <div>
                <label className="text-xs font-bold text-neutral-800 block mb-1">
                  1. Confirmed Insurer
                </label>
                <input
                  type="text"
                  value={hitConfirmedInsurer}
                  onChange={(e) => setHitConfirmedInsurer(e.target.value)}
                  placeholder="e.g. Allianz General Insurance, Zurich Takaful..."
                  className="w-full h-9 px-3 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900 font-semibold"
                />
              </div>

              {/* Confirmed Insurance Period */}
              <div>
                <label className="text-xs font-bold text-neutral-800 block mb-1">
                  2. Confirmed Insurance Period (Tempoh Insurans)
                </label>
                <p className="text-[11px] text-neutral-500 mb-2">
                  Verify or adjust the policy dates extracted from the quotation PDF:
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-[10px] font-bold text-neutral-600 block mb-1">Start Date</span>
                    <input
                      type="date"
                      value={hitConfirmedStartDate}
                      onChange={(e) => {
                        const newStart = e.target.value;
                        setHitConfirmedStartDate(newStart);
                        if (newStart) {
                          const d = new Date(newStart);
                          d.setDate(d.getDate() + 364);
                          setHitConfirmedEndDate(d.toISOString().split("T")[0]);
                        }
                      }}
                      className="w-full h-8 px-2.5 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900 font-mono"
                    />
                  </div>
                  <div>
                    <span className="text-[10px] font-bold text-neutral-600 block mb-1">End Date</span>
                    <input
                      type="date"
                      value={hitConfirmedEndDate}
                      onChange={(e) => setHitConfirmedEndDate(e.target.value)}
                      className="w-full h-8 px-2.5 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900 font-mono"
                    />
                  </div>
                </div>

                {hitConfirmedStartDate && hitConfirmedEndDate && (
                  <div className="mt-2.5 p-2 bg-emerald-50 border border-emerald-200 rounded text-[11px] text-emerald-950 font-mono flex items-center justify-between">
                    <span>Period: {hitConfirmedStartDate} → {hitConfirmedEndDate}</span>
                    <span className="text-[10px] font-bold text-emerald-700 bg-white px-1.5 py-0.5 rounded border border-emerald-300">
                      1 Year
                    </span>
                  </div>
                )}
              </div>

              {/* Accepted Quotation PDF */}
              <div>
                <label className="text-xs font-bold text-neutral-800 block mb-1">
                  3. {hitConfirmTenure.covernote_policy ? "Official Cover Note / Policy PDF" : "Accepted Quotation PDF"}
                </label>
                {hitConfirmTenure.covernote_policy?.uploaded_file_id ? (
                  <div className="p-2.5 bg-emerald-50/60 border border-emerald-300 rounded flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5 truncate">
                      <FilePdf size={16} weight="fill" className="text-emerald-700 shrink-0" />
                      <span className="font-bold text-emerald-950 truncate">
                        {hitConfirmTenure.covernote_policy.file_name || `${hitConfirmTenure.covernote_policy.company} Cover Note`}
                      </span>
                    </div>
                    <a
                      href={fileUrl(`/uploaded-files/${hitConfirmTenure.covernote_policy.uploaded_file_id}/content`)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-800 hover:text-emerald-950 font-bold text-[11px] underline shrink-0 ml-2"
                    >
                      View Policy PDF ↗
                    </a>
                  </div>
                ) : hitConfirmTenure.winning_file_id ? (
                  <div className="p-2.5 bg-neutral-50 border border-neutral-200 rounded flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5 truncate">
                      <FilePdf size={16} weight="fill" className="text-emerald-600 shrink-0" />
                      <span className="font-medium text-neutral-900 truncate">
                        {hitConfirmTenure.winning_file_name || "Accepted Quotation PDF"}
                      </span>
                    </div>
                    <a
                      href={fileUrl(`/uploaded-files/${hitConfirmTenure.winning_file_id}/content`)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-700 hover:text-emerald-900 font-bold text-[11px] underline shrink-0 ml-2"
                    >
                      View PDF ↗
                    </a>
                  </div>
                ) : hitConfirmTenure.sourced_quotes?.find((q) => q.uploaded_file_id) ? (
                  (() => {
                    const winQuote =
                      hitConfirmTenure.sourced_quotes.find((q) => q.is_winner && q.uploaded_file_id) ||
                      hitConfirmTenure.sourced_quotes.find((q) => q.uploaded_file_id);
                    return winQuote?.uploaded_file_id ? (
                      <div className="p-2.5 bg-neutral-50 border border-neutral-200 rounded flex items-center justify-between text-xs">
                        <div className="flex items-center gap-1.5 truncate">
                          <FilePdf size={16} weight="fill" className="text-blue-600 shrink-0" />
                          <span className="font-medium text-neutral-900 truncate">
                            {winQuote.file_name || `${winQuote.company} Quote`}
                          </span>
                        </div>
                        <a
                          href={fileUrl(`/uploaded-files/${winQuote.uploaded_file_id}/content`)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-700 hover:text-blue-900 font-bold text-[11px] underline shrink-0 ml-2"
                        >
                          View PDF ↗
                        </a>
                      </div>
                    ) : (
                      <div className="p-2.5 bg-neutral-50 rounded border border-neutral-200 text-xs text-neutral-500 italic">
                        No PDF uploaded for this quote.
                      </div>
                    );
                  })()
                ) : (
                  <div className="p-2.5 bg-neutral-50 rounded border border-neutral-200 text-xs text-neutral-500 italic">
                    No PDF uploaded for this quote.
                  </div>
                )}
              </div>

              <div className="p-2.5 bg-amber-50 rounded border border-amber-200 text-[11px] text-amber-900 leading-relaxed">
                Confirming this policy issuance will mark the deal as <strong>HIT (Won)</strong> and automatically create the next-year renewal in the Motor Timeline.
              </div>
            </div>

            <div className="p-3 bg-neutral-50 border-t border-neutral-200 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setHitConfirmTenure(null)}
                className="px-3 py-1.5 text-xs font-medium text-neutral-600 hover:text-neutral-900 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmHit}
                disabled={savingHitConfirm}
                className="px-4 py-1.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded shadow-xs cursor-pointer disabled:opacity-50 flex items-center gap-1"
              >
                <CheckCircle size={13} weight="bold" />
                <span>{savingHitConfirm ? "Confirming..." : "Confirm & Mark as HIT (Won)"}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal for Delete Confirmation & 30-Day Trash Warning */}
      {deleteConfirmTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="bg-white rounded-[var(--rl-radius)] border border-neutral-200 shadow-xl max-w-sm w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-4 border-b border-neutral-100 bg-[#fbfbfd] flex items-center justify-between">
              <h3 className="font-bold text-sm text-neutral-900">Confirm Move to Trash</h3>
              <button
                type="button"
                onClick={() => setDeleteConfirmTarget(null)}
                className="text-neutral-400 hover:text-neutral-700 text-sm font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>
            <div className="p-4 space-y-2 text-xs text-neutral-600">
              <p>
                Are you sure you want to delete <strong className="text-neutral-900">{deleteConfirmTarget.vehicleNo}</strong>?
              </p>
              <p className="text-[11px] text-neutral-600 bg-amber-50 p-2.5 rounded border border-amber-200 leading-relaxed">
                This will delete the vehicle deal and move all associated quotation sessions, comparison matrices, and generated PDF records to Trash.
                Items in Trash are retained for <strong>30 days</strong> before permanent deletion.
              </p>
            </div>
            <div className="p-3 bg-neutral-50 border-t border-neutral-200 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteConfirmTarget(null)}
                className="px-3 py-1.5 text-xs font-medium text-neutral-600 hover:text-neutral-900 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  setDeletingVehicle(true);
                  try {
                    await api("/tenures/bulk", {
                      method: "DELETE",
                      body: JSON.stringify({ tenure_ids: deleteConfirmTarget.allIds }),
                    });
                    setDeleteConfirmTarget(null);
                    loadTenures();
                    loadStageSummary();
                    loadMonths();
                    loadYoyStats();
                  } catch (err: any) {
                    alert("Failed to delete deal: " + (err?.message || err));
                  } finally {
                    setDeletingVehicle(false);
                  }
                }}
                disabled={deletingVehicle}
                className="px-3.5 py-1.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded shadow-xs cursor-pointer disabled:opacity-50"
              >
                {deletingVehicle ? "Deleting..." : "Yes, Move to Trash"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal for Cover Note Upload to reach Issue Policy stage */}
      {covernoteUploadTenure && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="bg-white rounded-[var(--rl-radius)] border border-neutral-200 shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-4 border-b border-neutral-100 bg-[#fbfbfd] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center text-amber-800">
                  <UploadSimple size={18} weight="bold" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-neutral-900">Upload Policy / Cover Note</h3>
                  <p className="text-[11px] text-neutral-500">
                    Required before advancing to Issue Policy stage
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setCovernoteUploadTenure(null)}
                className="text-neutral-400 hover:text-neutral-700 text-sm font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* Vehicle & Customer Context Card */}
              <div className="bg-neutral-50 p-3.5 rounded-lg border border-neutral-200 space-y-2 text-xs">
                <div className="flex items-center justify-between pb-1.5 border-b border-neutral-200/60">
                  <span className="font-mono font-bold text-sm text-neutral-900">
                    {getVehicleDisplayName(covernoteUploadTenure.vehicle_no, covernoteUploadTenure.chassis_no)}
                  </span>
                  {covernoteUploadTenure.expiry_month && (
                    <span className="text-[10px] font-mono font-semibold bg-white px-2 py-0.5 rounded border border-neutral-200 text-neutral-600">
                      Exp: {covernoteUploadTenure.expiry_month}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <span className="text-neutral-500 block text-[10px]">Customer:</span>
                    <span className="font-semibold text-neutral-800 truncate block">
                      {covernoteUploadTenure.customer_name || "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-neutral-500 block text-[10px]">Customer IC / Reg No:</span>
                    <span className="font-mono text-neutral-800 truncate block">
                      {covernoteUploadTenure.customer_ic_no || "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-neutral-500 block text-[10px]">Chassis No:</span>
                    <span className="font-mono text-neutral-800 truncate block">
                      {covernoteUploadTenure.chassis_no || "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-neutral-500 block text-[10px]">Vehicle Model:</span>
                    <span className="text-neutral-800 truncate block">
                      {[covernoteUploadTenure.car_brand, covernoteUploadTenure.car_model].filter(Boolean).join(" ") || "—"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Upload Drop Area */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-neutral-800 block">
                  Select Official Cover Note PDF
                </label>
                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const file = e.dataTransfer.files?.[0];
                    if (file && file.type === "application/pdf") {
                      handleUploadCovernoteForTenure(file);
                    } else if (file) {
                      alert("Please select a PDF file.");
                    }
                  }}
                  className="border-2 border-dashed border-neutral-300 hover:border-neutral-900 rounded-xl p-6 text-center transition-colors bg-white hover:bg-neutral-50/50 cursor-pointer relative"
                >
                  <input
                    type="file"
                    accept=".pdf,application/pdf"
                    disabled={uploadingCovernote}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        handleUploadCovernoteForTenure(file);
                      }
                    }}
                    className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                  />
                  {uploadingCovernote ? (
                    <div className="flex flex-col items-center gap-2 py-2">
                      <ArrowsClockwise className="w-6 h-6 animate-spin text-amber-600" />
                      <span className="text-xs font-bold text-neutral-800">
                        Extracting &amp; Attaching Cover Note...
                      </span>
                      <span className="text-[10px] text-neutral-500">
                        OCR scanning schedule excess, perils, and policy number
                      </span>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-2">
                      <div className="w-10 h-10 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-600">
                        <FilePdf size={22} weight="duotone" />
                      </div>
                      <div>
                        <span className="text-xs font-bold text-neutral-800 block">
                          Drop Cover Note PDF here, or click to browse
                        </span>
                        <span className="text-[10px] text-neutral-400">
                          Supports official PDF schedules from all Malaysian insurers
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Secondary link to workspace upload */}
              <div className="pt-2 text-center">
                <Link
                  href={`/upload?mode=comparison&tenure_id=${covernoteUploadTenure.id}` as Route}
                  onClick={() => setCovernoteUploadTenure(null)}
                  className="text-[11px] text-neutral-600 hover:text-neutral-900 font-semibold underline"
                >
                  Or open dedicated Upload Intake Workspace →
                </Link>
              </div>
            </div>

            <div className="p-3 bg-neutral-50 border-t border-neutral-200 flex items-center justify-end">
              <button
                type="button"
                onClick={() => setCovernoteUploadTenure(null)}
                disabled={uploadingCovernote}
                className="px-3.5 py-1.5 text-xs font-medium text-neutral-600 hover:text-neutral-900 cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
