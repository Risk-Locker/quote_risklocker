"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import type {
  LedgerSortColumn,
  LedgerDensity,
  YoYStatItem,
  MonthItem,
  PicItem,
  TenureRow,
  StageSummary,
  VehicleGroup,
  CalendarEvent,
  CalendarSession,
} from "./types";
import { MONTH_NAMES } from "./types";

export function useLedgerState() {
  const { toast } = useToast();
  const currentYear = useMemo(() => new Date().getFullYear().toString(), []);

  const [selectedYear, setSelectedYear] = useState<string>(currentYear);
  const [selectedMonth, setSelectedMonth] = useState<string>("all");
  const [months, setMonths] = useState<MonthItem[]>([]);
  const [loadingMonths, setLoadingMonths] = useState(true);

  // Category toggle: 'active' (default) vs 'lost' vs 'all'
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

  // Sorting state (default: last_activity desc)
  const [sortBy, setSortBy] = useState<LedgerSortColumn>("last_activity");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Bulk Selection & Operations
  const [selectedTenureIds, setSelectedTenureIds] = useState<string[]>([]);
  const [deletingBulk, setDeletingBulk] = useState(false);
  const [confirmingBulk, setConfirmingBulk] = useState(false);

  const [showHidden, setShowHidden] = useState<boolean>(false);

  // Density compression: 'comfortable' vs 'compact'
  const [density, setDensityState] = useState<LedgerDensity>("comfortable");

  useEffect(() => {
    try {
      const stored = localStorage.getItem("rl_ledger_density");
      if (stored === "compact" || stored === "comfortable") {
        setDensityState(stored as LedgerDensity);
      }
    } catch {}
  }, []);

  const setDensity = useCallback((mode: LedgerDensity) => {
    setDensityState(mode);
    try {
      localStorage.setItem("rl_ledger_density", mode);
    } catch {}
  }, []);

  // Hidden optional columns for extra horizontal compression
  const [hiddenColumns, setHiddenColumnsState] = useState<string[]>([]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("rl_ledger_hidden_cols");
      if (stored) {
        setHiddenColumnsState(JSON.parse(stored));
      }
    } catch {}
  }, []);

  const toggleColumnVisibility = useCallback((col: string) => {
    setHiddenColumnsState((prev) => {
      const next = prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col];
      try {
        localStorage.setItem("rl_ledger_hidden_cols", JSON.stringify(next));
      } catch {}
      return next;
    });
  }, []);

  // PICs directory for dropdown selection
  const [pics, setPics] = useState<PicItem[]>([]);

  // YoY Statistics Ribbon State
  const [yoyStats, setYoyStats] = useState<YoYStatItem[]>([]);
  const [allYearsSummary, setAllYearsSummary] = useState<{
    total: number;
    cars: number;
    active: number;
    lost: number;
  } | null>(null);
  const [loadingYoy, setLoadingYoy] = useState(false);

  // Calendar Quotation Sessions
  const [calendarSessions, setCalendarSessions] = useState<CalendarSession[]>([]);
  const [calendarVehicleFilter, setCalendarVehicleFilter] = useState<string>("all");
  const [loadingCalendar, setLoadingCalendar] = useState(false);

  const monthScrollRef = useRef<HTMLDivElement>(null);

  // Issued & Pending counts
  const issuedCount = useMemo(() => {
    return tenures.filter(
      (t) => Boolean(t.covernote_policy || t.stage === "Close - Win" || t.status === "hit")
    ).length;
  }, [tenures]);

  const pendingCount = useMemo(() => {
    return tenures.filter(
      (t) => !Boolean(t.covernote_policy || t.stage === "Close - Win" || t.status === "hit")
    ).length;
  }, [tenures]);

  const handleSort = (column: LedgerSortColumn) => {
    if (sortBy === column) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(column);
      setSortDir(column === "vehicle_no" || column === "coverage_period" ? "asc" : "desc");
    }
  };

  // Load YoY stats
  const loadYoyStats = useCallback(async () => {
    setLoadingYoy(true);
    try {
      const res = await api<{
        years: YoYStatItem[];
        all_years_summary: { total: number; cars: number; active: number; lost: number };
      }>("/tenures/yoy-stats");
      setYoyStats(res.years || []);
      setAllYearsSummary(res.all_years_summary || null);
    } catch (err) {
      console.error("Failed to load YoY stats:", err);
    } finally {
      setLoadingYoy(false);
    }
  }, []);

  // Load PICs directory
  const loadPics = useCallback(async () => {
    try {
      const res = await api<{ pics: PicItem[] }>("/tenures/pics");
      setPics(res.pics || []);
    } catch (err) {
      console.error("Failed to load PICs:", err);
    }
  }, []);

  // Load Months timeline
  const loadMonths = useCallback(async () => {
    setLoadingMonths(true);
    try {
      const res = await api<{ months: MonthItem[] }>(
        "/tenures/months" + (showHidden ? "?show_hidden=true" : "")
      );
      setMonths(res.months || []);
    } catch (err) {
      console.error("Failed to load months:", err);
    } finally {
      setLoadingMonths(false);
    }
  }, [showHidden]);

  // Load 5-Stage KPI Summary
  const loadStageSummary = useCallback(async () => {
    setLoadingSummary(true);
    try {
      const params = new URLSearchParams();
      if (selectedMonth && selectedMonth !== "all") {
        const parts = selectedMonth.split("-");
        if (parts.length === 2) {
          params.set("year", parts[0]);
          params.set("month", String(parseInt(parts[1], 10)));
        }
      } else if (selectedYear && selectedYear !== "all") {
        params.set("year", selectedYear);
      }
      const data = await api<StageSummary>(`/tenures/stage-summary?${params.toString()}`);
      setSummary(data);
    } catch (err) {
      console.error("Failed to load stage summary:", err);
    } finally {
      setLoadingSummary(false);
    }
  }, [selectedYear, selectedMonth]);

  // Load Tenures
  const loadTenures = useCallback(async () => {
    setLoadingTenures(true);
    try {
      const params = new URLSearchParams();
      if (selectedMonth && selectedMonth !== "all") {
        const parts = selectedMonth.split("-");
        if (parts.length === 2) {
          params.set("year", parts[0]);
          params.set("month", String(parseInt(parts[1], 10)));
        }
      } else if (selectedYear && selectedYear !== "all") {
        params.set("year", selectedYear);
      }

      if (category === "lost") {
        params.set("category", "lost");
      }
      if (stageFilter && stageFilter !== "all") {
        params.set("stage", stageFilter);
      }
      if (search.trim()) {
        params.set("q", search.trim());
      }
      if (statusFilter && statusFilter !== "all") {
        params.set("status", statusFilter);
      }
      if (showHidden) {
        params.set("show_hidden", "true");
      }
      params.set("limit", "1000");

      const res = await api<{ items: TenureRow[]; total: number }>(
        `/tenures?${params.toString()}`
      );
      setTenures(res.items || []);
    } catch (err) {
      console.error("Failed to load tenures:", err);
    } finally {
      setLoadingTenures(false);
    }
  }, [selectedYear, selectedMonth, category, stageFilter, search, statusFilter, showHidden]);

  // Load Calendar Quotation Sessions
  const loadCalendarSessions = useCallback(async () => {
    if (viewMode !== "calendar") return;
    setLoadingCalendar(true);
    try {
      const params = new URLSearchParams();
      if (selectedYear && selectedYear !== "all") {
        params.set("year", selectedYear);
      }
      if (selectedMonth && selectedMonth !== "all") {
        params.set("month", String(parseInt(selectedMonth.split("-")[1], 10)));
      }
      const res = await api<{ sessions: CalendarSession[]; total: number }>(
        `/tenures/calendar-sessions?${params.toString()}`
      );
      setCalendarSessions(res.sessions || []);
    } catch (err) {
      console.error("Failed to load calendar sessions:", err);
    } finally {
      setLoadingCalendar(false);
    }
  }, [viewMode, selectedYear, selectedMonth]);

  // Handle live inline edit patch
  const patchTenureField = async (tenureId: string, updates: Partial<TenureRow>) => {
    try {
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
            ((custId && t.customer_id === custId) ||
              (!custId && oldName && t.customer_name === oldName))
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

      await api(`/tenures/${tenureId}`, {
        method: "PATCH",
        body: JSON.stringify(updates),
      });

      loadStageSummary();
      if (updates.stage || updates.status || updates.is_discarded !== undefined) {
        loadTenures();
        loadMonths();
        loadYoyStats();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast("Failed to update tenure: " + msg, "error");
      loadTenures();
    }
  };

  // Selection & Bulk Delete Operations
  const handleToggleSelectAll = () => {
    if (selectedTenureIds.length > 0) {
      setSelectedTenureIds([]);
    } else {
      setSelectedTenureIds(tenures.map((t) => t.id));
    }
  };

  const handleToggleSelectGroup = (ids: string[], isSelected: boolean) => {
    if (isSelected) {
      setSelectedTenureIds((prev) => prev.filter((id) => !ids.includes(id)));
    } else {
      setSelectedTenureIds((prev) => [...prev, ...ids]);
    }
  };

  const handleBulkDelete = async () => {
    const count = selectedTenureIds.length;
    if (
      !confirm(
        `Move ${count} selected deal(s) to Trash? Associated quotation sessions, comparisons, and PDFs will be archived for 30 days.`
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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast("Bulk delete failed: " + msg, "error");
    } finally {
      setDeletingBulk(false);
    }
  };

  const handleBulkConfirmHit = async () => {
    const count = selectedTenureIds.length;
    if (
      !confirm(
        `Confirm policy as HIT (Won / Issued Policy) for all ${count} selected deals? This will create upcoming renewal deals for next year where applicable.`
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
      loadMonths();
      loadYoyStats();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast("Bulk confirm hit failed: " + msg, "error");
    } finally {
      setConfirmingBulk(false);
    }
  };

  // Scroll active month into view
  const scrollMonths = (direction: "left" | "right") => {
    if (monthScrollRef.current) {
      const delta = direction === "left" ? -320 : 320;
      monthScrollRef.current.scrollBy({ left: delta, behavior: "smooth" });
    }
  };

  const handleJumpToCurrentMonth = () => {
    const now = new Date();
    const currMonthStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    setSelectedYear(now.getFullYear().toString());
    setSelectedMonth(currMonthStr);
  };

  // Available years dynamically computed
  const availableYears = useMemo(() => {
    const nextYear = (parseInt(currentYear, 10) + 1).toString();
    const yearsSet = new Set<string>([currentYear, nextYear]);
    yoyStats.forEach((s) => yearsSet.add(s.year));
    return Array.from(yearsSet).sort();
  }, [currentYear, yoyStats]);

  // 12 Clean Month list for selected year
  const monthsOfYear = useMemo(() => {
    const yr = selectedYear === "all" ? currentYear : selectedYear;
    return MONTH_NAMES.map((name, idx) => {
      const mStr = `${yr}-${String(idx + 1).padStart(2, "0")}`;
      const existing = months.find((m) => m.month === mStr);
      return {
        month: mStr,
        label: name,
        total: existing?.total || 0,
        start_count: existing?.start_count || 0,
        end_count: existing?.end_count || 0,
        cars: existing?.cars || 0,
      };
    });
  }, [selectedYear, currentYear, months]);

  // Calendar Geometry for Visual View
  const calendarData = useMemo(() => {
    const now = new Date();
    let yr = now.getFullYear();
    let mo = now.getMonth();
    if (selectedMonth && selectedMonth !== "all") {
      const parts = selectedMonth.split("-");
      if (parts.length === 2) {
        yr = parseInt(parts[0], 10);
        mo = parseInt(parts[1], 10) - 1;
      }
    }

    const firstDay = new Date(yr, mo, 1).getDay();
    const daysInMonth = new Date(yr, mo + 1, 0).getDate();
    const monthLabel = new Date(yr, mo, 1).toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
    });

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
          if (itemYr === yr && itemMo === mo && itemDay >= 1 && itemDay <= daysInMonth) {
            if (
              calendarVehicleFilter === "all" ||
              s.vehicle_no?.toUpperCase().trim() === calendarVehicleFilter.toUpperCase().trim()
            ) {
              dayMap[itemDay].push({ type: "session", session: s });
            }
          }
        }
      }
    });

    // 2. Filter to ONLY approved / main policies for coverage start/end events
    const calendarTenures = tenures.filter((t) => t.is_main);
    calendarTenures.forEach((t) => {
      // Check start date
      if (t.coverage_start_date) {
        const datePart = t.coverage_start_date.split("T")[0];
        const parts = datePart.split("-");
        if (parts.length === 3) {
          const itemYr = parseInt(parts[0], 10);
          const itemMo = parseInt(parts[1], 10) - 1;
          const itemDay = parseInt(parts[2], 10);
          if (itemYr === yr && itemMo === mo && itemDay >= 1 && itemDay <= daysInMonth) {
            if (
              calendarVehicleFilter === "all" ||
              t.vehicle_no?.toUpperCase().trim() === calendarVehicleFilter.toUpperCase().trim()
            ) {
              dayMap[itemDay].push({ type: "start", tenure: t });
            }
          }
        }
      }

      // Check end date
      if (t.coverage_end_date) {
        const datePart = t.coverage_end_date.split("T")[0];
        const parts = datePart.split("-");
        if (parts.length === 3) {
          const itemYr = parseInt(parts[0], 10);
          const itemMo = parseInt(parts[1], 10) - 1;
          const itemDay = parseInt(parts[2], 10);
          if (itemYr === yr && itemMo === mo && itemDay >= 1 && itemDay <= daysInMonth) {
            if (
              calendarVehicleFilter === "all" ||
              t.vehicle_no?.toUpperCase().trim() === calendarVehicleFilter.toUpperCase().trim()
            ) {
              dayMap[itemDay].push({ type: "end", tenure: t });
            }
          }
        }
      }
    });

    const agendaDays: Array<{ day: number; dateStr: string; items: CalendarEvent[] }> = [];
    for (let d = 1; d <= daysInMonth; d++) {
      if (dayMap[d].length > 0) {
        const dt = new Date(yr, mo, d);
        const dateStr = dt.toLocaleDateString("en-MY", {
          weekday: "short",
          day: "numeric",
          month: "short",
          year: "numeric",
        });
        agendaDays.push({ day: d, dateStr, items: dayMap[d] });
      }
    }

    return {
      firstDay,
      daysInMonth,
      monthLabel,
      year: yr,
      month: mo,
      dayMap,
      agendaDays,
    };
  }, [selectedMonth, calendarSessions, tenures, calendarVehicleFilter]);

  // Unique vehicle list for calendar filter dropdown
  const calendarVehicleOptions = useMemo(() => {
    const set = new Set<string>();
    tenures.forEach((t) => {
      if (t.vehicle_no) set.add(t.vehicle_no.trim().toUpperCase());
    });
    calendarSessions.forEach((s) => {
      if (s.vehicle_no) set.add(s.vehicle_no.trim().toUpperCase());
    });
    return Array.from(set).sort();
  }, [tenures, calendarSessions]);

  // Group tenures by vehicle for the vehicle-centric ledger
  const vehicleGroups = useMemo(() => {
    const map = new Map<string, TenureRow[]>();
    for (const t of tenures) {
      const key = (t.vehicle_no || t.chassis_no || t.id).trim().toUpperCase();
      if (!map.has(key)) {
        map.set(key, []);
      }
      map.get(key)!.push(t);
    }

    const groups: VehicleGroup[] = [];
    map.forEach((tList, key) => {
      const sorted = [...tList].sort((a, b) => {
        const da = a.coverage_start_date || "";
        const db = b.coverage_start_date || "";
        return da.localeCompare(db);
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

    const filtered = groups.filter((g) => {
      if (policyFilter === "all") return true;
      const t = g.mainTenure;
      const hasPolicy = Boolean(
        t.covernote_policy || t.is_covernote_issued || t.stage === "Close - Win" || t.status === "hit"
      );
      if (policyFilter === "issued") return hasPolicy;
      if (policyFilter === "pending") return !hasPolicy;
      return true;
    });

    return filtered.sort((a, b) => {
      let cmp = 0;
      if (sortBy === "vehicle_no") {
        cmp = a.vehicle_no.localeCompare(b.vehicle_no);
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

        if (isIssuedA && !isIssuedB) return -1;
        if (!isIssuedA && isIssuedB) return 1;

        const da =
          (isIssuedA
            ? a.mainTenure.covernote_policy?.coverage_start_date ||
              a.mainTenure.coverage_start_date
            : a.mainTenure.coverage_start_date) || "";
        const db =
          (isIssuedB
            ? b.mainTenure.covernote_policy?.coverage_start_date ||
              b.mainTenure.coverage_start_date
            : b.mainTenure.coverage_start_date) || "";

        if (!da && db) return 1;
        if (da && !db) return -1;
        if (!da && !db) return 0;

        cmp = da.localeCompare(db);
      } else if (sortBy === "stage") {
        const stageWeight: Record<string, number> = {
          "Close - Win": 5,
          "Issue Policy": 4,
          "Material to Client": 3,
          Quotations: 2,
          "Close - Lose": 1,
        };
        const wa = stageWeight[a.mainTenure.stage] ?? 0;
        const wb = stageWeight[b.mainTenure.stage] ?? 0;
        cmp = wa - wb;
        if (cmp === 0) {
          const dateA =
            a.mainTenure.last_activity_at ||
            a.mainTenure.stage_updated_at ||
            a.mainTenure.created_at ||
            "";
          const dateB =
            b.mainTenure.last_activity_at ||
            b.mainTenure.stage_updated_at ||
            b.mainTenure.created_at ||
            "";
          cmp = dateA.localeCompare(dateB);
        }
      } else if (sortBy === "created_at") {
        const ca = a.mainTenure.created_at || "";
        const cb = b.mainTenure.created_at || "";
        cmp = ca.localeCompare(cb);
      } else if (sortBy === "pic") {
        const picA = (a.mainTenure.sub_agent_name || "").toLowerCase();
        const picB = (b.mainTenure.sub_agent_name || "").toLowerCase();
        cmp = picA.localeCompare(picB);
      } else {
        const dateA =
          a.mainTenure.last_activity_at ||
          a.mainTenure.stage_updated_at ||
          a.mainTenure.created_at ||
          "";
        const dateB =
          b.mainTenure.last_activity_at ||
          b.mainTenure.stage_updated_at ||
          b.mainTenure.created_at ||
          "";
        cmp = dateA.localeCompare(dateB);
      }

      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [tenures, policyFilter, sortBy, sortDir]);

  // Initial loads
  useEffect(() => {
    loadMonths();
    loadPics();
    loadYoyStats();
  }, [loadMonths, loadPics, loadYoyStats]);

  useEffect(() => {
    loadStageSummary();
  }, [loadStageSummary]);

  useEffect(() => {
    loadTenures();
  }, [loadTenures]);

  useEffect(() => {
    loadCalendarSessions();
  }, [loadCalendarSessions]);

  return {
    currentYear,
    selectedYear,
    setSelectedYear,
    selectedMonth,
    setSelectedMonth,
    months,
    loadingMonths,
    category,
    setCategory,
    stageFilter,
    setStageFilter,
    summary,
    loadingSummary,
    viewMode,
    setViewMode,
    calendarDisplay,
    setCalendarDisplay,
    tenures,
    loadingTenures,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    policyFilter,
    setPolicyFilter,
    sortBy,
    setSortBy,
    sortDir,
    setSortDir,
    handleSort,
    selectedTenureIds,
    setSelectedTenureIds,
    handleToggleSelectAll,
    handleToggleSelectGroup,
    handleBulkDelete,
    handleBulkConfirmHit,
    deletingBulk,
    confirmingBulk,
    showHidden,
    setShowHidden,
    pics,
    yoyStats,
    allYearsSummary,
    loadingYoy,
    calendarSessions,
    calendarVehicleFilter,
    setCalendarVehicleFilter,
    calendarVehicleOptions,
    loadingCalendar,
    monthScrollRef,
    scrollMonths,
    handleJumpToCurrentMonth,
    issuedCount,
    pendingCount,
    availableYears,
    monthsOfYear,
    calendarData,
    vehicleGroups,
    loadMonths,
    loadStageSummary,
    loadTenures,
    loadYoyStats,
    loadCalendarSessions,
    patchTenureField,
    density,
    setDensity,
    hiddenColumns,
    toggleColumnVisibility,
  };
}
