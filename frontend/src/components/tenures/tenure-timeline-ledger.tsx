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

export interface YoYStatItem {
  year: string;
  total: number;
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
    return `${d}/${m}/${y}`;
  }
  return dateStr;
}

export interface MonthItem {
  month: string;
  total: number;
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
  is_projected?: boolean;
  created_at?: string;
}

export interface StageSummary {
  quotations: number;
  material_to_client: number;
  issue_policy: number;
  ucd_invoice_to_client: number;
  ucd_receipt_to_client: number;
  pending_payment: number;
  pending_delivery: number;
  close_win: number;
  close_lose: number;
  others: number;
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
  "Issue Policy": {
    label: "Issue Policy",
    bg: "bg-amber-50/60",
    text: "text-amber-900",
    border: "border-amber-200",
    badge: "bg-amber-100 text-amber-800 border-amber-200",
  },
  "UCD Invoice to Client": {
    label: "UCD Invoice to Client",
    bg: "bg-teal-50/60",
    text: "text-teal-900",
    border: "border-teal-200",
    badge: "bg-teal-100 text-teal-800 border-teal-200",
  },
  "UCD Receipt to Client": {
    label: "UCD Receipt to Client",
    bg: "bg-sky-50/60",
    text: "text-sky-900",
    border: "border-sky-200",
    badge: "bg-sky-100 text-sky-800 border-sky-200",
  },
  "Pending Payment": {
    label: "Pending Payment",
    bg: "bg-orange-50/60",
    text: "text-orange-900",
    border: "border-orange-200",
    badge: "bg-orange-100 text-orange-800 border-orange-200",
  },
  "Pending Delivery": {
    label: "Pending Delivery",
    bg: "bg-pink-50/60",
    text: "text-pink-900",
    border: "border-pink-200",
    badge: "bg-pink-100 text-pink-800 border-pink-200",
  },
  "Close - Win": {
    label: "Close - Win",
    bg: "bg-emerald-50/60",
    text: "text-emerald-900",
    border: "border-emerald-200",
    badge: "bg-emerald-100 text-emerald-800 border-emerald-200",
  },
  "Close - Lose": {
    label: "Close - Lose",
    bg: "bg-rose-50/60",
    text: "text-rose-900",
    border: "border-rose-200",
    badge: "bg-rose-100 text-rose-800 border-rose-200",
    isLost: true,
  },
  Others: {
    label: "Others",
    bg: "bg-neutral-100/60",
    text: "text-neutral-800",
    border: "border-neutral-200",
    badge: "bg-neutral-200 text-neutral-800 border-neutral-300",
    isLost: true,
  },
};

export const STAGE_ORDER = [
  "Quotations",
  "Material to Client",
  "Issue Policy",
  "UCD Invoice to Client",
  "UCD Receipt to Client",
  "Pending Payment",
  "Pending Delivery",
  "Close - Win",
  "Close - Lose",
  "Others",
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

  // YoY Statistics Ribbon State
  const [yoyStats, setYoyStats] = useState<YoYStatItem[]>([]);
  const [loadingYoy, setLoadingYoy] = useState(false);

  // Bulk Selection & Operations
  const [selectedTenureIds, setSelectedTenureIds] = useState<string[]>([]);
  const [deletingBulk, setDeletingBulk] = useState(false);

  // PICs directory for dropdown selection
  const [pics, setPics] = useState<PicItem[]>([]);
  const [activeDrawerTenureId, setActiveDrawerTenureId] = useState<string | null>(null);
  const [editingTenure, setEditingTenure] = useState<TenureRow | null>(null);

  // Inline save feedback state
  const [savingFieldId, setSavingFieldId] = useState<string | null>(null);
  const [savedFieldId, setSavedFieldId] = useState<string | null>(null);

  const monthScrollRef = useRef<HTMLDivElement>(null);

  // Load YoY stats
  const loadYoyStats = useCallback(async () => {
    setLoadingYoy(true);
    try {
      const res = await api<{ years: YoYStatItem[] }>("/tenures/stats/yoy");
      setYoyStats(res.years || []);
    } catch (err) {
      console.error("Failed to load YoY stats:", err);
    } finally {
      setLoadingYoy(false);
    }
  }, []);

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
      const res = await api<{ months: MonthItem[] }>("/tenures/months");
      const list = res.months || [];
      setMonths(list);
    } catch (err) {
      console.error("Failed to load tenure months:", err);
    } finally {
      setLoadingMonths(false);
    }
  }, []);

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
      if (selectedMonth && selectedMonth !== "all") {
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

      params.set("page_size", "100");

      const res = await api<{ items: TenureRow[]; total: number }>(`/tenures?${params.toString()}`);
      setTenures(res.items || []);
    } catch (err) {
      console.error("Failed to load tenures:", err);
    } finally {
      setLoadingTenures(false);
    }
  }, [selectedYear, selectedMonth, category, stageFilter, search]);

  useEffect(() => {
    loadTenures();
  }, [loadTenures]);

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
      case "Issue Policy":
        return summary.issue_policy || 0;
      case "UCD Invoice to Client":
        return summary.ucd_invoice_to_client || 0;
      case "UCD Receipt to Client":
        return summary.ucd_receipt_to_client || 0;
      case "Pending Payment":
        return summary.pending_payment || 0;
      case "Pending Delivery":
        return summary.pending_delivery || 0;
      case "Close - Win":
        return summary.close_win || 0;
      case "Close - Lose":
        return summary.close_lose || 0;
      case "Others":
        return summary.others || 0;
      default:
        return 0;
    }
  }

  // Handle stage card click: toggle filter
  function handleStageCardClick(stage: string) {
    if (stageFilter === stage) {
      setStageFilter("all");
    } else {
      setStageFilter(stage);
      // If clicking Close - Lose or Others, switch category to lost so the rows are visible!
      if (stage === "Close - Lose" || stage === "Others") {
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

  // 12 Clean Month list for selected year (NO "Future" tab)
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
      };
    });
  }, [selectedYear, months, currentYear]);

  // Year items to show in year switcher
  const availableYears = useMemo(() => {
    const defaultList = ["2025", "2026", "2027", "2028"];
    if (!defaultList.includes(currentYear)) {
      defaultList.push(currentYear);
    }
    return defaultList.sort();
  }, [currentYear]);

  // Find PIC details helper
  function getPicDisplay(t: TenureRow) {
    if (t.pic_id) {
      const matched = pics.find((p) => p.id === t.pic_id);
      if (matched) {
        return {
          name: matched.name,
          type: matched.type,
          commission: matched.commission_rate,
          agency: matched.agency_group,
        };
      }
    }
    if (t.sub_agent_name) {
      return {
        name: t.sub_agent_name,
        type: "subagent" as const,
        commission: 0,
        agency: t.pic_agency || null,
      };
    }
    return null;
  }

  // Calendar Geometry for Visual View
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

    const dayMap: Record<number, TenureRow[]> = {};
    for (let d = 1; d <= daysInMonth; d++) {
      dayMap[d] = [];
    }

    tenures.forEach((t) => {
      if (t.coverage_end_date) {
        // Deterministic split to avoid local timezone offset shifting the day
        const datePart = t.coverage_end_date.split("T")[0];
        const parts = datePart.split("-");
        if (parts.length === 3) {
          const itemYr = parseInt(parts[0], 10);
          const itemMo = parseInt(parts[1], 10) - 1;
          const itemDay = parseInt(parts[2], 10);
          if (itemYr === yr && itemMo === mo) {
            if (dayMap[itemDay]) {
              dayMap[itemDay].push(t);
            }
          }
        }
      }
    });

    const agendaDays: Array<{ day: number; dateStr: string; items: TenureRow[] }> = [];
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
  }, [selectedMonth, selectedYear, tenures, currentYear, currentMonthNum]);

  return (
    <div className="space-y-5">
      {/* ========================================================================= */}
      {/* 1. TOP STAGE KPI BANNER: 10 SUMMARY CARDS (Excel 1:1)                      */}
      {/* ========================================================================= */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-neutral-900 uppercase tracking-wider">
              10-Stage Pipeline Overview
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

        {/* 10 KPI Cards Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2">
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
      {/* 1.5 YEAR-OVER-YEAR MOTOR PORTFOLIO STATS RIBBON                            */}
      {/* ========================================================================= */}
      {yoyStats.length > 0 && (
        <div className="bg-white border border-[#e5e5ea] rounded-[var(--rl-radius)] p-3.5 shadow-2xs space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-neutral-900 uppercase tracking-wider flex items-center gap-1.5">
              <TrendUp className="w-4 h-4 text-emerald-600" />
              Annual Portfolio Trajectory &amp; YoY Growth
            </span>
            <span className="text-[11px] text-neutral-400">
              Click a year to view that renewal cohort
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
            {yoyStats.map((item) => {
              const isSelected = selectedYear === item.year;
              return (
                <button
                  key={item.year}
                  type="button"
                  onClick={() => {
                    setSelectedYear(item.year);
                    setSelectedMonth("all");
                  }}
                  className={`p-2.5 rounded-[var(--rl-radius-sm)] border text-left transition-all cursor-pointer flex flex-col justify-between ${
                    isSelected
                      ? "bg-neutral-900 border-neutral-900 text-white shadow-xs"
                      : "bg-[#fafafb] border-neutral-200/80 hover:border-neutral-400 hover:bg-white"
                  }`}
                  title={`Filter renewals to ${item.year}`}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-xs font-bold font-mono ${
                        isSelected ? "text-amber-400" : "text-neutral-900"
                      }`}
                    >
                      {item.year}
                    </span>
                    {item.growth_percentage !== null && (
                      <span
                        className={`text-[9px] font-extrabold px-1.5 py-0.2 rounded ${
                          item.growth_percentage >= 0
                            ? isSelected
                              ? "bg-emerald-500/20 text-emerald-300"
                              : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : isSelected
                            ? "bg-rose-500/20 text-rose-300"
                            : "bg-rose-50 text-rose-700 border border-rose-200"
                        }`}
                      >
                        {item.growth_percentage >= 0 ? "+" : ""}
                        {item.growth_percentage}%
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex items-baseline justify-between">
                    <span
                      className={`text-base font-extrabold font-mono ${
                        isSelected ? "text-white" : "text-neutral-900"
                      }`}
                    >
                      {item.total}{" "}
                      <span
                        className={`text-[10px] font-normal ${
                          isSelected ? "text-neutral-400" : "text-neutral-400"
                        }`}
                      >
                        deals
                      </span>
                    </span>
                    <span
                      className={`text-[10px] font-medium ${
                        isSelected ? "text-neutral-300" : "text-neutral-500"
                      }`}
                    >
                      {item.active} act · {item.lost} lost
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 2. YEAR & 12 CLEAN MONTH TABS BAR (NO "FUTURE" TAB)                        */}
      {/* ========================================================================= */}
      <div className="bg-white border border-[#e5e5ea] rounded-[var(--rl-radius)] p-3.5 shadow-2xs space-y-3">
        {/* Tier 1: Year Hierarchy Bar */}
        <div className="flex items-center justify-between flex-wrap gap-2 pb-2.5 border-b border-[#f2f2f7]">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-[#1b1717]">
              <CalendarBlank className="w-4 h-4 text-[#454545]" />
              Renewal Year:
            </span>
            <div className="flex items-center gap-1 flex-wrap">
              <button
                type="button"
                onClick={() => {
                  setSelectedYear("all");
                  setSelectedMonth("all");
                }}
                className={`px-3 py-1 rounded-[var(--rl-radius-sm)] text-xs font-medium transition-all cursor-pointer ${
                  selectedYear === "all"
                    ? "bg-[#1b1717] text-white shadow-2xs font-semibold"
                    : "bg-[#f5f5f7] text-[#6e6e73] hover:text-[#1b1717] hover:bg-[#e5e5ea]"
                }`}
              >
                All Years
              </button>

              {availableYears.map((yr) => {
                const isSelected = selectedYear === yr;
                return (
                  <button
                    key={yr}
                    type="button"
                    onClick={() => {
                      setSelectedYear(yr);
                      setSelectedMonth(`${yr}-${String(currentMonthNum).padStart(2, "0")}`);
                    }}
                    className={`px-3 py-1 rounded-[var(--rl-radius-sm)] text-xs font-medium transition-all cursor-pointer ${
                      isSelected
                        ? "bg-[#1b1717] text-white shadow-2xs font-semibold"
                        : "bg-[#f5f5f7] text-[#6e6e73] hover:text-[#1b1717] hover:bg-[#e5e5ea]"
                    }`}
                  >
                    <span>{yr}</span>
                    {yr === currentYear && (
                      <span className="ml-1 text-[10px] text-amber-500 font-bold">●</span>
                    )}
                  </button>
                );
              })}
            </div>
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
              }}
              className="text-[11px] text-[#8e8e93] hover:text-[#1b1717] flex items-center gap-1 ml-1 cursor-pointer"
            >
              <ArrowsClockwise className="w-3 h-3" /> Refresh
            </button>
          </div>
        </div>

        {/* Tier 2: 12 Clean Month Tabs (No Future tab) */}
        {loadingMonths ? (
          <div className="h-9 flex items-center text-xs text-[#8e8e93]">Loading tenure timeline...</div>
        ) : (
          <div
            ref={monthScrollRef}
            className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-0.5 scroll-smooth scrollbar-thin"
          >
            {/* "All Months in {Year}" button */}
            <button
              type="button"
              onClick={() => setSelectedMonth("all")}
              className={`shrink-0 min-w-max px-3.5 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 cursor-pointer ${
                selectedMonth === "all"
                  ? "bg-[#1b1717] text-white shadow-2xs"
                  : "bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
              }`}
            >
              <span>{selectedYear === "all" ? "All Months" : `All ${selectedYear}`}</span>
            </button>

            {/* 12 Months: Jan to Dec */}
            {monthsOfYear.map((m) => {
              const isActive = selectedMonth === m.month;
              const isCurrent = m.month === currentMonthKey;
              return (
                <button
                  key={m.month}
                  type="button"
                  data-month={m.month}
                  onClick={() => setSelectedMonth(m.month)}
                  className={`shrink-0 min-w-max px-3.5 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-medium whitespace-nowrap transition-all flex items-center gap-1.5 cursor-pointer ${
                    isActive
                      ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                      : "bg-[#f5f5f7] text-[#454545] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
                  } ${isCurrent && !isActive ? "ring-1 ring-[#007aff]/60 font-semibold" : ""}`}
                  title={isCurrent ? "Current active calendar month" : undefined}
                >
                  <span>{m.label}</span>
                  {m.total > 0 && (
                    <span
                      className={`px-1.5 py-0.2 rounded-[var(--rl-radius-sm)] text-[10px] font-bold ${
                        isActive ? "bg-white/20 text-white" : "bg-[#e5e5ea] text-[#1b1717]"
                      }`}
                    >
                      {m.total}
                    </span>
                  )}
                </button>
              );
            })}
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
      {/* 4. VIEW 1: EXCEL DIGITAL TWIN TABLE LEDGER                                 */}
      {/* ========================================================================= */}
      {viewMode === "ledger" && (
        <div className="bg-white border border-neutral-200/90 rounded-[var(--rl-radius)] overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs whitespace-nowrap">
              <thead className="bg-[#f9f9fb] border-b border-neutral-200/80 text-[11px] font-bold uppercase tracking-wider text-neutral-600">
                <tr>
                  <th className="py-3 px-2 w-14 text-center">
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
                  <th className="py-3 px-3">Vehicle &amp; Client</th>
                  <th className="py-3 px-3">Stages</th>
                  <th className="py-3 px-3">Expiry Date</th>
                  <th className="py-3 px-3 min-w-[160px]">Comment</th>
                  <th className="py-3 px-3 min-w-[160px]">Notes / Pattern</th>
                  <th className="py-3 px-3">Sub Agent / PIC</th>
                  <th className="py-3 px-3">Business</th>
                  <th className="py-3 px-3">Insurer &amp; Quotes</th>
                  <th className="py-3 px-3 text-center">Payment</th>
                  <th className="py-3 px-3 text-center">Key-in UCD</th>
                  <th className="py-3 px-3">Roadtax Status</th>
                  <th className="py-3 px-3 text-center">Days</th>
                  <th className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {loadingTenures ? (
                  <tr>
                    <td colSpan={14} className="py-14 text-center text-neutral-400">
                      <ArrowsClockwise className="w-5 h-5 animate-spin mx-auto mb-2 text-neutral-500" />
                      Loading Motor Renewal Ledger...
                    </td>
                  </tr>
                ) : tenures.length === 0 ? (
                  <tr>
                    <td colSpan={14} className="py-14 text-center text-neutral-400">
                      {category === "lost"
                        ? "No lost client records found matching the active filters."
                        : `No active renewal policies found for ${selectedMonth === "all" ? selectedYear : selectedMonth}.`}
                    </td>
                  </tr>
                ) : (
                  tenures.map((t) => {
                    const picInfo = getPicDisplay(t);
                    const stageConf = STAGE_CONFIGS[t.stage] || STAGE_CONFIGS.Quotations;
                    const isOverdue = t.days_in_stage > 7 && !stageConf.isLost && t.stage !== "Close - Win";

                    return (
                      <tr
                        key={t.id}
                        className={`hover:bg-neutral-50/80 transition-colors ${
                          stageConf.isLost ? "bg-rose-50/20" : ""
                        }`}
                      >
                        {/* 0. Select Checkbox & Direct Delete */}
                        <td className="py-3 px-2 text-center">
                          <div className="flex items-center justify-center gap-1">
                            <input
                              type="checkbox"
                              checked={selectedTenureIds.includes(t.id)}
                              onChange={() => handleToggleSelectRow(t.id)}
                              className="w-3.5 h-3.5 rounded border-neutral-300 text-neutral-900 focus:ring-neutral-900 cursor-pointer"
                              title={`Select ${t.vehicle_no}`}
                              aria-label={`Select ${t.vehicle_no}`}
                            />
                            <button
                              type="button"
                              onClick={() => handleDeleteTenure(t.id, t.vehicle_no)}
                              className="flex size-6 items-center justify-center rounded text-neutral-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                              title={`Delete deal for ${t.vehicle_no}`}
                              aria-label={`Delete deal for ${t.vehicle_no}`}
                            >
                              <Trash size={13} weight="bold" />
                            </button>
                          </div>
                        </td>

                        {/* 1. Name: Plate & Customer */}
                        <td className="py-3 px-3">
                          <div className="flex items-center justify-between gap-1">
                            <div className="font-bold text-neutral-900 font-mono text-sm flex items-center gap-1.5">
                              <Car className="w-3.5 h-3.5 text-neutral-600 shrink-0" />
                              <span className="truncate max-w-[130px]">{t.vehicle_no}</span>
                              {t.vehicle_no?.startsWith("CHASSIS:") && (
                                <span className="px-1.5 py-0.2 rounded bg-amber-100 text-amber-900 font-sans text-[9px] font-bold shrink-0">
                                  CHASSIS
                                </span>
                              )}
                            </div>
                            <button
                              type="button"
                              onClick={() => setEditingTenure(t)}
                              className="p-1 rounded text-neutral-400 hover:text-neutral-900 hover:bg-neutral-100 transition-colors cursor-pointer"
                              title="Edit Customer, Plate & Deal Details (propagates everywhere)"
                            >
                              <PencilSimple size={13} weight="bold" />
                            </button>
                          </div>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <Link
                              href={`/client-records?search=${encodeURIComponent(t.customer_name)}` as Route}
                              className="text-neutral-700 hover:text-blue-600 font-medium text-[11px] truncate max-w-[130px] inline-block"
                              title={`View client record for ${t.customer_name}`}
                            >
                              {t.customer_name}
                            </Link>
                            {t.customer_ic_no && (
                              <span className="text-[10px] text-neutral-400 font-mono truncate max-w-[85px]">
                                {t.customer_ic_no}
                              </span>
                            )}
                          </div>
                          {(t.car_model || t.car_brand || t.engine_cc) && (
                            <div className="text-[10px] text-neutral-500 font-medium mt-0.5 truncate max-w-[190px]">
                              {t.car_brand ? `${t.car_brand} ` : ""}{t.car_model || ""}{t.engine_cc ? ` · ${t.engine_cc}cc` : ""}
                            </div>
                          )}
                        </td>

                        {/* 2. Stages Dropdown */}
                        <td className="py-3 px-3">
                          <select
                            value={t.stage || "Quotations"}
                            onChange={(e) => patchTenureField(t.id, { stage: e.target.value })}
                            className={`h-7 px-2 text-[11px] font-bold rounded border cursor-pointer transition-colors outline-none ${stageConf.badge}`}
                          >
                            {STAGE_ORDER.map((st) => (
                              <option key={st} value={st}>
                                {st}
                              </option>
                            ))}
                          </select>
                        </td>

                        {/* 3. Expiry Date */}
                        <td className="py-3 px-3">
                          <div className="font-mono text-xs font-semibold text-neutral-800">
                            {formatDateSafe(t.coverage_end_date)}
                          </div>
                          <div className="text-[10px] text-neutral-400 font-medium">
                            {t.expiry_month}
                          </div>
                        </td>

                        {/* 4. Comment (Inline Live Edit) */}
                        <td className="py-3 px-3">
                          <input
                            type="text"
                            defaultValue={t.comment || ""}
                            placeholder="Add comment..."
                            onBlur={(e) => {
                              if (e.target.value !== (t.comment || "")) {
                                patchTenureField(t.id, { comment: e.target.value });
                              }
                            }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.currentTarget.blur();
                              }
                            }}
                            className="w-full h-7 px-2 text-xs rounded border border-transparent hover:border-neutral-300 focus:border-neutral-900 bg-transparent hover:bg-white focus:bg-white transition-all outline-none"
                          />
                        </td>

                        {/* 5. Notes / Pattern (Inline Live Edit) */}
                        <td className="py-3 px-3">
                          <input
                            type="text"
                            defaultValue={t.client_preference_notes || t.notes || ""}
                            placeholder="Habitual pattern..."
                            onBlur={(e) => {
                              if (e.target.value !== (t.client_preference_notes || "")) {
                                patchTenureField(t.id, { client_preference_notes: e.target.value });
                              }
                            }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.currentTarget.blur();
                              }
                            }}
                            className="w-full h-7 px-2 text-xs rounded border border-transparent hover:border-neutral-300 focus:border-neutral-900 bg-transparent hover:bg-white focus:bg-white transition-all outline-none"
                          />
                        </td>

                        {/* 6. Sub Agent / Person In Charge (PIC) */}
                        <td className="py-3 px-3">
                          <div className="flex flex-col gap-0.5">
                            <select
                              value={t.pic_id || ""}
                              onChange={(e) => {
                                const selectedPicId = e.target.value;
                                const matched = pics.find((p) => p.id === selectedPicId);
                                patchTenureField(t.id, {
                                  pic_id: selectedPicId || null,
                                  sub_agent_name: matched ? matched.name : "",
                                });
                              }}
                              className="h-7 px-2 text-xs font-semibold rounded border border-neutral-200 bg-white text-neutral-800 outline-none cursor-pointer max-w-[150px]"
                            >
                              <option value="">— Unassigned PIC —</option>
                              {pics.map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.name} {p.type === "subagent" ? `(SubAgent · ${p.commission_rate}%)` : `(${p.type})`}
                                </option>
                              ))}
                            </select>

                            {picInfo && (
                              <div className="flex items-center gap-1">
                                {picInfo.type === "subagent" ? (
                                  <span className="text-[10px] font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-1 rounded">
                                    SubAgent · {picInfo.commission}% Comm
                                  </span>
                                ) : picInfo.type === "client_self" ? (
                                  <span className="text-[10px] font-medium text-neutral-600 bg-neutral-100 px-1 rounded">
                                    Client (Self)
                                  </span>
                                ) : (
                                  <span className="text-[10px] font-medium text-blue-800 bg-blue-50 px-1 rounded">
                                    Company Personnel
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        </td>

                        {/* 7. Business Type (Renewal / New Business) */}
                        <td className="py-3 px-3">
                          <button
                            type="button"
                            onClick={() => {
                              const nextType = t.business_type === "New Business" ? "Renewal" : "New Business";
                              patchTenureField(t.id, { business_type: nextType });
                            }}
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-colors cursor-pointer ${
                              t.business_type === "New Business"
                                ? "bg-purple-100 text-purple-900 border-purple-200"
                                : "bg-neutral-100 text-neutral-800 border-neutral-200"
                            }`}
                            title="Click to toggle Renewal / New Business"
                          >
                            {t.business_type || "Renewal"}
                          </button>
                        </td>

                        {/* 8. Insurer & Sourced Quotes */}
                        <td className="py-3 px-3">
                          {t.sourced_quotes.length === 0 ? (
                            <span className="text-neutral-400 italic text-[11px]">0 quotes</span>
                          ) : (
                            <div className="flex flex-wrap gap-1 max-w-[180px]">
                              {t.sourced_quotes.map((q) => (
                                <span
                                  key={q.session_id}
                                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-800 text-[10px] font-medium border border-neutral-200/60"
                                >
                                  <span className="font-bold">{q.company}</span>
                                  {q.total_payable && (
                                    <span className="text-neutral-500 font-mono">RM {q.total_payable}</span>
                                  )}
                                </span>
                              ))}
                            </div>
                          )}
                        </td>

                        {/* 9. Payment Status (Client Paid / Agency Paid) */}
                        <td className="py-3 px-3 text-center">
                          <div className="flex items-center justify-center gap-1.5">
                            <label
                              className="flex items-center gap-0.5 text-[10px] font-semibold text-neutral-700 cursor-pointer"
                              title="Client Payment Received"
                            >
                              <input
                                type="checkbox"
                                checked={Boolean(t.client_payment_received)}
                                onChange={(e) =>
                                  patchTenureField(t.id, { client_payment_received: e.target.checked })
                                }
                                className="w-3.5 h-3.5 accent-emerald-600 rounded cursor-pointer"
                              />
                              <span>Cli</span>
                            </label>

                            <label
                              className="flex items-center gap-0.5 text-[10px] font-semibold text-neutral-700 cursor-pointer"
                              title="Agency Payment Settled"
                            >
                              <input
                                type="checkbox"
                                checked={Boolean(t.agency_payment_done)}
                                onChange={(e) =>
                                  patchTenureField(t.id, { agency_payment_done: e.target.checked })
                                }
                                className="w-3.5 h-3.5 accent-blue-600 rounded cursor-pointer"
                              />
                              <span>Agc</span>
                            </label>
                          </div>
                        </td>

                        {/* 10. Key-in UCD */}
                        <td className="py-3 px-3 text-center">
                          <input
                            type="checkbox"
                            checked={Boolean(t.key_in_ucd)}
                            onChange={(e) => patchTenureField(t.id, { key_in_ucd: e.target.checked })}
                            className="w-4 h-4 accent-teal-600 rounded cursor-pointer"
                            title="Keyed-in to UCD Portal"
                          />
                        </td>

                        {/* 11. Roadtax Status (Print Roadtax & Receipt) */}
                        <td className="py-3 px-3">
                          <div className="flex flex-col gap-1">
                            <select
                              value={t.print_roadtax || "No"}
                              onChange={(e) => patchTenureField(t.id, { print_roadtax: e.target.value })}
                              className="h-6 px-1.5 text-[10px] font-semibold rounded border border-neutral-200 bg-white text-neutral-800 outline-none cursor-pointer"
                              title="Print Roadtax"
                            >
                              <option value="No">Print: No</option>
                              <option value="MyEG Pending">MyEG Pending</option>
                              <option value="Done">Print: Done</option>
                              <option value="Counter">Counter</option>
                              <option value="Digital Only">Digital Only</option>
                            </select>

                            <select
                              value={t.roadtax_receipt || "None"}
                              onChange={(e) => patchTenureField(t.id, { roadtax_receipt: e.target.value })}
                              className="h-6 px-1.5 text-[10px] font-semibold rounded border border-neutral-200 bg-white text-neutral-800 outline-none cursor-pointer"
                              title="Roadtax Receipt Status"
                            >
                              <option value="None">Rcpt: None</option>
                              <option value="Pending">Rcpt: Pending</option>
                              <option value="Received">Rcpt: Received</option>
                              <option value="Sent to Client">Rcpt: Sent to Client</option>
                            </select>
                          </div>
                        </td>

                        {/* 12. Days in Stage */}
                        <td className="py-3 px-3 text-center">
                          <span
                            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold font-mono ${
                              isOverdue
                                ? "bg-rose-100 text-rose-800 border border-rose-200"
                                : "bg-neutral-100 text-neutral-700"
                            }`}
                          >
                            {t.days_in_stage}d
                          </span>
                        </td>

                        {/* 13. Actions */}
                        <td className="py-3 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Link
                              href={`/comparison?tenure_id=${t.id}` as Route}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-colors shadow-2xs cursor-pointer"
                              title="Go to Marketing Comparison matrix for this vehicle"
                            >
                              <Columns className="w-3.5 h-3.5" />
                              <span>Compare</span>
                            </Link>

                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => setActiveDrawerTenureId(t.id)}
                              className="h-7 text-xs font-medium cursor-pointer"
                            >
                              Timeline <ArrowRight className="w-3 h-3 ml-0.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
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
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-neutral-900">
                {calendarData.monthLabel}
              </span>
              <span className="text-xs font-medium text-neutral-500">
                · {tenures.length} policies expiring this month
              </span>
            </div>

            <div className="flex items-center rounded-[var(--rl-radius-sm)] border border-neutral-200 bg-neutral-100 p-0.5">
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
                        {dayTenures.map((t) => (
                          <div
                            key={t.id}
                            onClick={() => setActiveDrawerTenureId(t.id)}
                            className="p-1.5 bg-neutral-50 hover:bg-neutral-100/90 border border-neutral-200/80 rounded cursor-pointer transition-all hover:shadow-xs group text-[11px]"
                          >
                            <div className="flex items-center justify-between gap-1">
                              <span className="font-bold text-neutral-900 font-mono">
                                {t.vehicle_no}
                              </span>
                              <span className="text-[9px] font-bold px-1 py-0.2 rounded bg-neutral-200 text-neutral-800">
                                {t.stage || "Quotations"}
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
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-amber-500 hover:bg-amber-600 text-slate-950 text-[9px] font-bold transition-colors"
                              >
                                <Columns className="w-2.5 h-2.5" />
                                <span>Compare</span>
                              </Link>
                            </div>
                          </div>
                        ))}
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
                  No policy expiries recorded for {calendarData.monthLabel}.
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
                        {group.items.length} {group.items.length === 1 ? "Policy" : "Policies"} Expiring
                      </span>
                    </div>

                    <div className="divide-y divide-neutral-100 p-2">
                      {group.items.map((t) => (
                        <div
                          key={t.id}
                          onClick={() => setActiveDrawerTenureId(t.id)}
                          className="p-3 hover:bg-neutral-50/70 rounded-lg cursor-pointer transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-sm text-neutral-900 font-mono">{t.vehicle_no}</span>
                              <span className="text-xs text-neutral-400">·</span>
                              <span className="text-xs font-medium text-neutral-700">{t.customer_name}</span>
                              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">
                                {t.stage || "Quotations"}
                              </span>
                            </div>

                            <div className="flex items-center gap-2 text-xs text-neutral-500">
                              <span>Expiry:</span>
                              <strong className="font-mono text-neutral-800">
                                {t.coverage_end_date ? new Date(t.coverage_end_date).toLocaleDateString("en-GB") : "—"}
                              </strong>
                              <span className="text-neutral-400">·</span>
                              <span>{t.sourced_quotes.length} Sourced Quotes</span>
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
                              className="h-8 text-xs font-medium"
                            >
                              Timeline &amp; Activity <ArrowRight className="w-3.5 h-3.5 ml-1" />
                            </Button>
                          </div>
                        </div>
                      ))}
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
    </div>
  );
}
