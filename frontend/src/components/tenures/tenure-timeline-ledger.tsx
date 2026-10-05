"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Route } from "next";
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
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
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
  won_premium: number | null;
  miss_reason: string | null;
  loss_reason_category: string | null;
  road_tax: number;
  runner_fee: number;
  sourced_quotes: Array<{
    session_id: string;
    company: string;
    version: number;
    total_payable: string | null;
    sum_insured: string | null;
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
  stage_updated_at?: string;
  last_activity_at?: string | null;
  is_discarded?: boolean;
  external_policy_start_date?: string | null;
  external_policy_end_date?: string | null;
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

  // Sorting state (default: last_activity desc)
  const [sortBy, setSortBy] = useState<"last_activity" | "vehicle_no" | "customer_name" | "stage">("last_activity");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Calendar Sessions state
  const [calendarSessions, setCalendarSessions] = useState<any[]>([]);
  const [calendarVehicleFilter, setCalendarVehicleFilter] = useState<string>("all");
  const [loadingCalendar, setLoadingCalendar] = useState(false);

  const handleSort = (column: "last_activity" | "vehicle_no" | "customer_name" | "stage") => {
    if (sortBy === column) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(column);
      setSortDir("desc");
    }
  };

  // YoY Statistics Ribbon State
  const [yoyStats, setYoyStats] = useState<YoYStatItem[]>([]);
  const [allYearsSummary, setAllYearsSummary] = useState<{ total: number; cars: number; active: number; lost: number } | null>(null);
  const [loadingYoy, setLoadingYoy] = useState(false);

  // Bulk Selection & Operations
  const [selectedTenureIds, setSelectedTenureIds] = useState<string[]>([]);
  const [deletingBulk, setDeletingBulk] = useState(false);

  // Inline Expandable Sub-panel State
  const [expandedTenureIds, setExpandedTenureIds] = useState<string[]>([]);
  const [showHidden, setShowHidden] = useState<boolean>(false);

  const toggleExpandRow = (id: string) => {
    setExpandedTenureIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

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

    if (isHit) {
      return (
        <div className="flex items-center gap-1.5">
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-100 text-emerald-900 border border-emerald-300 text-[11px] font-bold shadow-2xs">
            <CheckCircle size={13} weight="fill" className="text-emerald-700" />
            <span>✓ HIT (Won)</span>
          </span>
          <button
            type="button"
            onClick={() => patchTenureField(t.id, { stage: "Issue Policy", status: "draft" })}
            className="text-[10px] text-neutral-400 hover:text-neutral-700 underline cursor-pointer"
            title="Revert back to Issue Policy"
          >
            Revert
          </button>
        </div>
      );
    }

    if (isMiss) {
      return (
        <div className="flex items-center gap-1.5">
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-rose-100 text-rose-900 border border-rose-300 text-[11px] font-bold shadow-2xs">
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

            return (
              <React.Fragment key={st.id}>
                <button
                  type="button"
                  onClick={() => patchTenureField(t.id, { stage: st.id })}
                  className={`px-2 py-0.5 rounded transition-all cursor-pointer flex items-center gap-1 ${
                    isActive
                      ? "bg-white text-neutral-900 shadow-2xs font-bold border border-neutral-300/80"
                      : isCompleted
                      ? "text-emerald-700 hover:text-emerald-900 font-medium"
                      : "text-neutral-400 hover:text-neutral-700"
                  }`}
                  title={`Step ${idx + 1}: Move to ${st.label}`}
                >
                  {isCompleted && <Check size={10} weight="bold" className="text-emerald-600 shrink-0" />}
                  <span>{st.label}</span>
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
            onClick={() => patchTenureField(t.id, { stage: "Close - Win", status: "hit" })}
            className="px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[10px] shadow-2xs cursor-pointer transition-colors flex items-center gap-1"
            title="Policy is issued! Click to mark this client as HIT"
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

  // Year items to show in year switcher (strictly dynamic from actual uploaded policies + current year)
  const availableYears = useMemo(() => {
    const yearsSet = new Set<string>([currentYear]);
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

    return [...groups].sort((a, b) => {
      let cmp = 0;
      if (sortBy === "vehicle_no") {
        cmp = a.vehicle_no.localeCompare(b.vehicle_no);
      } else if (sortBy === "customer_name") {
        cmp = (a.customer_name || "").localeCompare(b.customer_name || "");
      } else if (sortBy === "stage") {
        cmp = (a.mainTenure.stage || "").localeCompare(b.mainTenure.stage || "");
      } else {
        // "last_activity"
        const dateA = a.mainTenure.last_activity_at || a.mainTenure.stage_updated_at || a.mainTenure.created_at || "";
        const dateB = b.mainTenure.last_activity_at || b.mainTenure.stage_updated_at || b.mainTenure.created_at || "";
        cmp = dateA.localeCompare(dateB);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [tenures, sortBy, sortDir]);

  const [expandedVehicleKeys, setExpandedVehicleKeys] = useState<string[]>([]);
  const toggleExpandVehicle = (key: string) => {
    setExpandedVehicleKeys((prev) =>
      prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key]
    );
  };

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
        {/* Category Switcher: Active Renewals vs Lost Clients */}
        <div className="flex items-center gap-1 bg-[#f5f5f7] p-1 rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] w-fit">
          <button
            type="button"
            onClick={() => {
              setCategory("active");
              if (stageFilter === "Close - Lose" || stageFilter === "Others") {
                setStageFilter("all");
              }
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-bold transition-all cursor-pointer ${
              category === "active"
                ? "bg-white text-neutral-900 shadow-2xs"
                : "text-neutral-500 hover:text-neutral-800"
            }`}
          >
            <span>Active Renewal Ledger</span>
          </button>

          <button
            type="button"
            onClick={() => setCategory("lost")}
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
          <div className="flex items-center gap-2 bg-rose-50 border border-rose-200 px-3 py-1 rounded-[var(--rl-radius-sm)]">
            <span className="text-xs font-bold text-rose-800">
              {selectedTenureIds.length} selected
            </span>
            <button
              type="button"
              onClick={handleBulkDelete}
              disabled={deletingBulk}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-all shadow-xs cursor-pointer"
              title="Delete all selected deals"
            >
              <Trash size={13} weight="bold" />
              <span>{deletingBulk ? "Deleting..." : "Delete Selected"}</span>
            </button>
            <button
              type="button"
              onClick={() => setSelectedTenureIds([])}
              className="text-[11px] text-neutral-500 hover:text-neutral-800 underline cursor-pointer"
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
                    <div className="flex items-center gap-1">
                      <span>Vehicle &amp; Customer</span>
                      {sortBy === "vehicle_no" && (
                        <span>{sortDir === "asc" ? "▲" : "▼"}</span>
                      )}
                    </div>
                  </th>
                  <th className="py-3 px-3 min-w-[170px]">Coverage Period</th>
                  <th
                    onClick={() => handleSort("stage")}
                    className="py-3 px-3 min-w-[340px] cursor-pointer hover:text-black transition-colors"
                  >
                    <div className="flex items-center gap-1">
                      <span>Pipeline Stage</span>
                      {sortBy === "stage" && (
                        <span>{sortDir === "asc" ? "▲" : "▼"}</span>
                      )}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort("last_activity")}
                    className="py-3 px-3 min-w-[190px] cursor-pointer hover:text-black transition-colors"
                  >
                    <div className="flex items-center gap-1">
                      <span>Latest Activity &amp; Quotes</span>
                      {sortBy === "last_activity" && (
                        <span>{sortDir === "asc" ? "▲" : "▼"}</span>
                      )}
                    </div>
                  </th>
                  <th className="py-3 px-3 min-w-[160px]">PIC &amp; Milestones</th>
                  <th className="py-3 px-3 text-right min-w-[190px]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {loadingTenures ? (
                  <tr>
                    <td colSpan={7} className="py-14 text-center text-neutral-400">
                      <ArrowsClockwise className="w-5 h-5 animate-spin mx-auto mb-2 text-neutral-500" />
                      Loading Motor Renewal Ledger...
                    </td>
                  </tr>
                ) : tenures.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-14 text-center text-neutral-400">
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
                    const isVehicleExpanded = expandedVehicleKeys.includes(group.vehicle_no);
                    const isGroupSelected = group.tenures.some((t) => selectedTenureIds.includes(t.id));
                    const displayName = getVehicleDisplayName(group.vehicle_no, group.chassis_no);
                    const isChassis = displayName.startsWith("Chassis:");
                    const isBlank = displayName === "No Plate (Blank)";
                    const hasMultiplePeriods = group.tenures.length > 1;

                    return (
                      <React.Fragment key={group.vehicle_no}>
                        {/* Primary Vehicle Row */}
                        <tr
                          className={`hover:bg-neutral-50/80 transition-colors ${
                            stageConf.isLost ? "bg-rose-50/20" : isVehicleExpanded ? "bg-[#f5f5f7]/60" : ""
                          }`}
                        >
                          {/* 0. Select Checkbox & Direct Delete & Expand */}
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
                                onClick={() => toggleExpandVehicle(group.vehicle_no)}
                                className={`p-1 rounded transition-colors cursor-pointer ${
                                  isVehicleExpanded
                                    ? "bg-neutral-900 text-white"
                                    : "text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100"
                                }`}
                                title={isVehicleExpanded ? "Collapse policy periods" : "Expand all policy periods"}
                                aria-label={isVehicleExpanded ? "Collapse policy periods" : "Expand all policy periods"}
                              >
                                {isVehicleExpanded ? <CaretUp size={13} weight="bold" /> : <CaretDown size={13} weight="bold" />}
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteTenure(mainTenure.id, displayName)}
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

                              {/* Multi-Period Toggle Pill Badge */}
                              <button
                                type="button"
                                onClick={() => toggleExpandVehicle(group.vehicle_no)}
                                className={`px-2 py-0.5 rounded-full text-[10px] font-bold border transition-colors cursor-pointer flex items-center gap-1 ${
                                  hasMultiplePeriods
                                    ? "bg-amber-50 hover:bg-amber-100 text-amber-900 border-amber-300 shadow-2xs"
                                    : "bg-neutral-100 text-neutral-600 border-neutral-200"
                                }`}
                                title={`This vehicle has ${group.tenures.length} policy period(s). Click to expand.`}
                              >
                                <span>{group.tenures.length} {group.tenures.length === 1 ? "Period" : "Periods"}</span>
                                {isVehicleExpanded ? <CaretUp size={10} weight="bold" /> : <CaretDown size={10} weight="bold" />}
                              </button>

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
                          </td>

                          {/* 2. Coverage Period (Main Policy) */}
                          <td className="py-3 px-3">
                            {mainTenure.stage === "Issue Policy" && mainTenure.coverage_start_date ? (
                              <div className="space-y-0.5">
                                <div className="flex items-center gap-1 text-[11px]">
                                  <span className="text-[9px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-1 py-0.2 rounded border border-emerald-200 shrink-0">
                                    Start
                                  </span>
                                  <span className="font-mono font-medium text-neutral-800">
                                    {formatDateSafe(mainTenure.coverage_start_date)}
                                  </span>
                                </div>
                                <div className="flex items-center gap-1 text-[11px]">
                                  <span className="text-[9px] font-bold uppercase tracking-wider text-rose-700 bg-rose-50 px-1 py-0.2 rounded border border-rose-200 shrink-0">
                                    End
                                  </span>
                                  <span className="font-mono font-medium text-neutral-800">
                                    {formatDateSafe(mainTenure.coverage_end_date)}
                                  </span>
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
                            ) : (
                              <div className="space-y-0.5">
                                <span className="text-neutral-400 font-mono text-xs">—</span>
                                <div className="text-[10px] text-neutral-400 font-medium">Pending Issue</div>
                              </div>
                            )}
                            <div className="flex items-center gap-1.5 mt-1">
                              <span className="text-[10px] text-neutral-500 font-medium">
                                Exp: {mainTenure.expiry_month}
                              </span>
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

                          {/* 4. Latest Activity & Quotes */}
                          <td className="py-3 px-3">
                            {mainTenure.sourced_quotes.length === 0 ? (
                              <span className="text-neutral-400 italic text-[11px]">0 quotes compiled</span>
                            ) : (
                              <div className="space-y-1 max-w-[210px]">
                                <div className="flex items-center justify-between gap-1.5">
                                  <span className="font-bold text-xs text-neutral-900 truncate">
                                    {mainTenure.sourced_quotes[0].company}
                                  </span>
                                  {mainTenure.sourced_quotes[0].total_payable && (
                                    <span className="text-neutral-900 font-mono font-bold text-xs bg-neutral-100 px-1.5 py-0.5 rounded border border-neutral-200 shrink-0">
                                      RM {mainTenure.sourced_quotes[0].total_payable}
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-center justify-between text-[10px]">
                                  <Link
                                    href={`/comparison?tenure_id=${mainTenure.id}` as Route}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="font-bold text-amber-800 hover:text-amber-950 hover:underline flex items-center gap-1"
                                    title="Open Marketing Comparison in new tab"
                                  >
                                    <span>Comparison ({mainTenure.sourced_quotes.length}) →</span>
                                  </Link>
                                  {mainTenure.last_activity_at && (
                                    <span className="text-neutral-400 font-mono">
                                      {new Date(mainTenure.last_activity_at).toLocaleDateString("en-MY", { day: "2-digit", month: "short" })}
                                    </span>
                                  )}
                                </div>
                              </div>
                            )}
                            {mainTenure.generated_quotations && mainTenure.generated_quotations.length > 0 && (
                              <div className="mt-1">
                                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-800 text-[10px] font-bold border border-emerald-200">
                                  <FilePdf size={11} weight="fill" className="text-emerald-600" />
                                  <span>{mainTenure.generated_quotations.length} Issued</span>
                                </span>
                              </div>
                            )}
                          </td>

                          {/* 5. PIC & Milestones */}
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

                              <button
                                type="button"
                                onClick={() => toggleExpandVehicle(group.vehicle_no)}
                                className={`h-7 px-2 text-xs font-bold rounded flex items-center gap-1 transition-colors cursor-pointer ${
                                  isVehicleExpanded
                                    ? "bg-neutral-900 text-white"
                                    : "bg-neutral-100 hover:bg-neutral-200 text-neutral-700"
                                }`}
                                title={isVehicleExpanded ? "Collapse periods" : "Expand periods list"}
                              >
                                <span>{hasMultiplePeriods ? `Periods (${group.tenures.length})` : isVehicleExpanded ? "Close" : "Details"}</span>
                                {isVehicleExpanded ? <CaretUp size={11} weight="bold" /> : <CaretDown size={11} weight="bold" />}
                              </button>
                            </div>
                          </td>
                        </tr>

                        {/* Inline Expandable Sub-panel: Serialized Policy Periods & Deal Details */}
                        {isVehicleExpanded && (
                          <tr className="bg-[#f9f9fb] border-b-2 border-neutral-300">
                            <td colSpan={7} className="p-4 whitespace-normal space-y-4">
                              {/* Serialized Policy Periods Sub-table */}
                              <div className="bg-white rounded-xl border border-neutral-200 shadow-2xs overflow-hidden">
                                <div className="px-4 py-2.5 bg-neutral-100/70 border-b border-neutral-200 flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <CalendarBlank size={14} className="text-neutral-700" />
                                    <span className="font-bold text-xs text-neutral-900 uppercase tracking-wider">
                                      Serialized Policy Periods for {displayName} ({group.tenures.length} Periods)
                                    </span>
                                  </div>
                                  <span className="text-[11px] text-neutral-500 font-medium">
                                    ★ Marked &quot;Approved / Main&quot; policy appears in Calendar View
                                  </span>
                                </div>

                                <div className="overflow-x-auto">
                                  <table className="w-full text-left text-xs whitespace-nowrap">
                                    <thead className="bg-neutral-50/60 text-[10px] font-bold uppercase tracking-wider text-neutral-500 border-b border-neutral-200/60">
                                      <tr>
                                        <th className="py-2.5 px-3">Approved / Main Role</th>
                                        <th className="py-2.5 px-3">Coverage Period</th>
                                        <th className="py-2.5 px-3">Sourced Quotes</th>
                                        <th className="py-2.5 px-3">Stage</th>
                                        <th className="py-2.5 px-3">Fulfillment &amp; Checklist</th>
                                        <th className="py-2.5 px-3 text-right">Actions</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-neutral-100">
                                      {group.tenures.map((t) => {
                                        const tStageConf = STAGE_CONFIGS[t.stage] || STAGE_CONFIGS.Quotations;
                                        return (
                                          <tr key={t.id} className={`hover:bg-neutral-50/60 transition-colors ${t.is_main ? "bg-amber-50/30" : ""}`}>
                                            {/* Approved / Main Toggle */}
                                            <td className="py-2.5 px-3">
                                              {t.is_main ? (
                                                <button
                                                  type="button"
                                                  onClick={() => handleSetMainTenure(t.id, group.vehicle_no)}
                                                  className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-900 border border-emerald-300 font-bold text-[11px] flex items-center gap-1 shadow-2xs cursor-pointer hover:bg-emerald-200 transition-colors"
                                                  title="Currently marked as the Approved / Main policy for Calendar View"
                                                >
                                                  <CheckCircle size={13} weight="fill" className="text-emerald-700" />
                                                  <span>★ Approved / Main</span>
                                                </button>
                                              ) : (
                                                <button
                                                  type="button"
                                                  onClick={() => handleSetMainTenure(t.id, group.vehicle_no)}
                                                  className="px-2.5 py-1 rounded-full bg-neutral-100 hover:bg-amber-100 text-neutral-600 hover:text-amber-900 border border-neutral-200 hover:border-amber-300 font-medium text-[11px] flex items-center gap-1 cursor-pointer transition-colors"
                                                  title="Click to set this period as the Approved / Main policy for Calendar View"
                                                >
                                                  <Clock size={12} className="text-neutral-400" />
                                                  <span>Set as Main Policy</span>
                                                </button>
                                              )}
                                            </td>

                                            {/* Coverage Period */}
                                            <td className="py-2.5 px-3">
                                              <div className="font-mono font-bold text-neutral-900 text-xs">
                                                {formatDateSafe(t.coverage_start_date)} → {formatDateSafe(t.coverage_end_date)}
                                              </div>
                                              <div className="text-[10px] text-neutral-500 font-medium mt-0.5">
                                                Expiry Cohort: {t.expiry_month}
                                              </div>
                                            </td>

                                            {/* Sourced Quotes */}
                                            <td className="py-2.5 px-3">
                                              {t.sourced_quotes.length === 0 ? (
                                                <span className="text-neutral-400 italic text-[11px]">0 quotes</span>
                                              ) : (
                                                <div className="flex flex-wrap gap-1 max-w-[260px]">
                                                  {t.sourced_quotes.map((q) => (
                                                    <span
                                                      key={q.session_id}
                                                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-800 text-[10px] font-medium border border-neutral-200/60"
                                                    >
                                                      <span className="font-bold">{q.company}</span>
                                                      {q.total_payable && <span className="font-mono text-neutral-700 font-semibold">RM {q.total_payable}</span>}
                                                    </span>
                                                  ))}
                                                </div>
                                              )}
                                            </td>

                                            {/* Stage */}
                                            <td className="py-2.5 px-3">
                                              {renderPipelineProgress(t)}
                                            </td>

                                            {/* Fulfillment & Checklist */}
                                            <td className="py-2.5 px-3">
                                              <div className="flex items-center gap-3 text-xs">
                                                <label className="flex items-center gap-1 text-[11px] font-medium text-neutral-700 cursor-pointer">
                                                  <input
                                                    type="checkbox"
                                                    checked={Boolean(t.key_in_ucd)}
                                                    onChange={(e) => patchTenureField(t.id, { key_in_ucd: e.target.checked })}
                                                    className="w-3.5 h-3.5 accent-teal-600 rounded cursor-pointer"
                                                  />
                                                  <span>UCD</span>
                                                </label>
                                                <label className="flex items-center gap-1 text-[11px] font-medium text-neutral-700 cursor-pointer">
                                                  <input
                                                    type="checkbox"
                                                    checked={Boolean(t.client_payment_received)}
                                                    onChange={(e) => patchTenureField(t.id, { client_payment_received: e.target.checked })}
                                                    className="w-3.5 h-3.5 accent-emerald-600 rounded cursor-pointer"
                                                  />
                                                  <span>Client Paid</span>
                                                </label>
                                                <label className="flex items-center gap-1 text-[11px] font-medium text-neutral-700 cursor-pointer">
                                                  <input
                                                    type="checkbox"
                                                    checked={Boolean(t.agency_payment_done)}
                                                    onChange={(e) => patchTenureField(t.id, { agency_payment_done: e.target.checked })}
                                                    className="w-3.5 h-3.5 accent-blue-600 rounded cursor-pointer"
                                                  />
                                                  <span>Agency Paid</span>
                                                </label>
                                              </div>
                                            </td>

                                            {/* Period Actions */}
                                            <td className="py-2.5 px-3 text-right">
                                              <div className="flex items-center justify-end gap-1.5">
                                                <Link
                                                  href={`/comparison?tenure_id=${t.id}` as Route}
                                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500 hover:bg-amber-600 text-slate-950 text-[11px] font-bold transition-colors shadow-2xs"
                                                >
                                                  <Columns className="w-3 h-3" />
                                                  <span>Compare</span>
                                                </Link>
                                                <Button
                                                  size="sm"
                                                  variant="secondary"
                                                  onClick={() => setActiveDrawerTenureId(t.id)}
                                                  className="h-6 text-[11px] font-medium px-2"
                                                >
                                                  Timeline
                                                </Button>
                                                <button
                                                  type="button"
                                                  onClick={() => handleDeleteTenure(t.id, displayName)}
                                                  className="p-1 rounded text-neutral-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                                                  title="Delete this period"
                                                >
                                                  <Trash size={12} weight="bold" />
                                                </button>
                                              </div>
                                            </td>
                                          </tr>
                                        );
                                      })}
                                    </tbody>
                                  </table>
                                </div>
                              </div>

                              {/* Sub-panel Secondary Cards: Remarks, Operations & Lost Client Retention */}
                              <div className={`grid grid-cols-1 ${mainTenure.stage === "Close - Lose" ? "md:grid-cols-3" : "md:grid-cols-2"} gap-4 text-xs`}>
                                {/* Sub-panel Card 1: Deal Intelligence & Remarks */}
                                <div className="p-3.5 bg-white rounded-xl border border-neutral-200 shadow-2xs space-y-3">
                                  <div className="flex items-center justify-between pb-1.5 border-b border-neutral-100">
                                    <span className="font-bold text-neutral-900 uppercase tracking-wider text-[11px] flex items-center gap-1">
                                      <NotePencil size={14} className="text-amber-600" />
                                      Deal Intelligence &amp; Remarks
                                    </span>
                                    {savingFieldId === mainTenure.id && (
                                      <span className="text-[10px] text-neutral-500 font-semibold animate-pulse">
                                        Saving...
                                      </span>
                                    )}
                                    {savedFieldId === mainTenure.id && (
                                      <span className="text-[10px] text-emerald-600 font-bold">
                                        ✓ Saved
                                      </span>
                                    )}
                                  </div>

                                  <div>
                                    <label className="text-[11px] font-bold text-neutral-700 block mb-1">
                                      Deal Comment
                                    </label>
                                    <input
                                      type="text"
                                      defaultValue={mainTenure.comment || ""}
                                      placeholder="Add deal comment / reminder..."
                                      onBlur={(e) => {
                                        if (e.target.value !== (mainTenure.comment || "")) {
                                          patchTenureField(mainTenure.id, { comment: e.target.value });
                                        }
                                      }}
                                      onKeyDown={(e) => {
                                        if (e.key === "Enter") e.currentTarget.blur();
                                      }}
                                      className="w-full h-8 px-2.5 text-xs rounded border border-neutral-300 bg-white focus:ring-1 focus:ring-neutral-900 outline-none"
                                    />
                                  </div>

                                  <div>
                                    <label className="text-[11px] font-bold text-neutral-700 block mb-1">
                                      Client Habitual Preference Notes
                                    </label>
                                    <textarea
                                      rows={2}
                                      defaultValue={mainTenure.client_preference_notes || mainTenure.notes || ""}
                                      placeholder="Habitual pattern, underwriter preferences, agreed value rules..."
                                      onBlur={(e) => {
                                        if (e.target.value !== (mainTenure.client_preference_notes || "")) {
                                          patchTenureField(mainTenure.id, { client_preference_notes: e.target.value });
                                        }
                                      }}
                                      className="w-full p-2 text-xs rounded border border-neutral-300 bg-white focus:ring-1 focus:ring-neutral-900 outline-none resize-none"
                                    />
                                  </div>
                                </div>

                                {/* Sub-panel Card 2: Operations & Fulfillment */}
                                <div className="p-3.5 bg-white rounded-xl border border-neutral-200 shadow-2xs space-y-3">
                                  <div className="flex items-center justify-between pb-1.5 border-b border-neutral-100">
                                    <span className="font-bold text-neutral-900 uppercase tracking-wider text-[11px] flex items-center gap-1">
                                      <CurrencyDollar size={14} className="text-emerald-600" />
                                      Operations &amp; Roadtax Fulfillment
                                    </span>
                                  </div>

                                  <div className="grid grid-cols-2 gap-2">
                                    <div>
                                      <label className="text-[10px] font-bold text-neutral-600 block mb-0.5">
                                        Print Roadtax
                                      </label>
                                      <select
                                        value={mainTenure.print_roadtax || "No"}
                                        onChange={(e) => patchTenureField(mainTenure.id, { print_roadtax: e.target.value })}
                                        className="w-full h-7 px-1.5 text-xs font-semibold rounded border border-neutral-300 bg-white"
                                      >
                                        <option value="No">No</option>
                                        <option value="MyEG Pending">MyEG Pending</option>
                                        <option value="Done">Done</option>
                                        <option value="Counter">Counter</option>
                                        <option value="Digital Only">Digital Only</option>
                                      </select>
                                    </div>
                                    <div>
                                      <label className="text-[10px] font-bold text-neutral-600 block mb-0.5">
                                        Roadtax Receipt
                                      </label>
                                      <select
                                        value={mainTenure.roadtax_receipt || "None"}
                                        onChange={(e) => patchTenureField(mainTenure.id, { roadtax_receipt: e.target.value })}
                                        className="w-full h-7 px-1.5 text-xs font-semibold rounded border border-neutral-300 bg-white"
                                      >
                                        <option value="None">None</option>
                                        <option value="Pending">Pending</option>
                                        <option value="Received">Received</option>
                                        <option value="Sent to Client">Sent to Client</option>
                                      </select>
                                    </div>
                                  </div>

                                  <div className="pt-2 border-t border-neutral-100 flex items-center justify-between">
                                    <Link
                                      href={`/comparison?tenure_id=${mainTenure.id}` as Route}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-xs font-bold text-amber-700 hover:text-amber-900 flex items-center gap-1"
                                    >
                                      <span>Open Comparison Matrix →</span>
                                    </Link>
                                    <button
                                      type="button"
                                      onClick={() => setEditingTenure(mainTenure)}
                                      className="text-xs font-bold text-neutral-700 hover:text-neutral-900 underline cursor-pointer"
                                    >
                                      Edit Deal Modal
                                    </button>
                                  </div>
                                </div>

                                {/* Sub-panel Card 3: Lost Client Retention & External Policy Dates */}
                                {mainTenure.stage === "Close - Lose" && (
                                  <div className="p-3.5 bg-amber-50/50 rounded-xl border border-amber-200/80 shadow-2xs space-y-3">
                                    <div className="flex items-center justify-between pb-1.5 border-b border-amber-200/60">
                                      <span className="font-bold text-amber-950 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                                        <Clock size={14} className="text-amber-700" />
                                        Lost Client Retention
                                      </span>
                                      <span
                                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                          mainTenure.is_discarded
                                            ? "bg-rose-100 text-rose-800 border border-rose-300"
                                            : "bg-emerald-100 text-emerald-800 border border-emerald-300"
                                        }`}
                                      >
                                        {mainTenure.is_discarded ? "Discarded" : "Active Pipeline"}
                                      </span>
                                    </div>

                                    <p className="text-[11px] text-amber-900/80 leading-relaxed">
                                      Track competitor policy dates to automatically queue this vehicle for renewal outreach next year.
                                    </p>

                                    <div className="grid grid-cols-2 gap-2">
                                      <div>
                                        <label className="text-[10px] font-bold text-amber-900 block mb-0.5">
                                          External Policy Start
                                        </label>
                                        <input
                                          type="date"
                                          defaultValue={
                                            mainTenure.external_policy_start_date
                                              ? mainTenure.external_policy_start_date.split("T")[0]
                                              : ""
                                          }
                                          onBlur={(e) => {
                                            const val = e.target.value;
                                            if (val !== (mainTenure.external_policy_start_date?.split("T")[0] || "")) {
                                              patchTenureField(mainTenure.id, { external_policy_start_date: val || null });
                                            }
                                          }}
                                          className="w-full h-7 px-2 text-xs font-mono font-medium rounded border border-amber-300 bg-white"
                                        />
                                      </div>
                                      <div>
                                        <label className="text-[10px] font-bold text-amber-900 block mb-0.5">
                                          External Policy End
                                        </label>
                                        <input
                                          type="date"
                                          defaultValue={
                                            mainTenure.external_policy_end_date
                                              ? mainTenure.external_policy_end_date.split("T")[0]
                                              : ""
                                          }
                                          onBlur={(e) => {
                                            const val = e.target.value;
                                            if (val !== (mainTenure.external_policy_end_date?.split("T")[0] || "")) {
                                              patchTenureField(mainTenure.id, { external_policy_end_date: val || null });
                                            }
                                          }}
                                          className="w-full h-7 px-2 text-xs font-mono font-medium rounded border border-amber-300 bg-white"
                                        />
                                      </div>
                                    </div>

                                    <div className="pt-2 border-t border-amber-200/60 flex items-center justify-between">
                                      <span className="text-[10px] text-amber-800">
                                        {mainTenure.is_discarded
                                          ? "Excluded from active renewal queue."
                                          : "Queued for next year's renewal."}
                                      </span>
                                      <button
                                        type="button"
                                        onClick={() =>
                                          patchTenureField(mainTenure.id, { is_discarded: !mainTenure.is_discarded })
                                        }
                                        className={`px-2 py-1 text-xs font-bold rounded transition-colors cursor-pointer border ${
                                          mainTenure.is_discarded
                                            ? "bg-white text-emerald-700 border-emerald-300 hover:bg-emerald-50"
                                            : "bg-white text-rose-700 border-rose-300 hover:bg-rose-50"
                                        }`}
                                      >
                                        {mainTenure.is_discarded ? "Restore Client" : "Discard Client"}
                                      </button>
                                    </div>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
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
                                <strong className="font-mono text-neutral-800">
                                  {formatDateSafe(t.coverage_start_date)} – {formatDateSafe(t.coverage_end_date)}
                                </strong>
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
    </div>
  );
}
