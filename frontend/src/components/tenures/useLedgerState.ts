"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import type {
  LedgerAnchor,
  LedgerSortColumn,
  LedgerDensity,
  YoYStatItem,
  MonthItem,
  MonthSummaryByNum,
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
  const [anchor, setAnchor] = useState<LedgerAnchor>("all");
  const [months, setMonths] = useState<MonthItem[]>([]);
  const [summaryByMonth, setSummaryByMonth] = useState<MonthSummaryByNum[]>([]);
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

  // Tenures Data, Pagination & Filters
  const [tenures, setTenures] = useState<TenureRow[]>([]);
  const [totalTenures, setTotalTenures] = useState(0);
  const [tabCounts, setTabCounts] = useState<{ all: number; issued: number; pending: number }>({
    all: 0,
    issued: 0,
    pending: 0,
  });
  const [page, setPage] = useState(1);
  const pageSize = 100;
  const [loadingTenures, setLoadingTenures] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [policyFilter, setPolicyFilter] = useState<"all" | "issued" | "pending">("all");

  // Debounce search input by 300ms to eliminate server pressure and race conditions
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Sorting state (default: last_activity desc)
  const [sortBy, setSortBy] = useState<LedgerSortColumn>("last_activity");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Bulk Selection & Operations
  const [selectedTenureIds, setSelectedTenureIds] = useState<string[]>([]);
  const [deletingBulk, setDeletingBulk] = useState(false);
  const [confirmingBulk, setConfirmingBulk] = useState(false);
  const [pendingBulkAction, setPendingBulkAction] = useState<"delete" | "hit" | null>(null);

  const [showHidden, setShowHidden] = useState<boolean>(false);

  // Density compression: 'comfortable' vs 'compact'
  const [density, setDensityState] = useState<LedgerDensity>("comfortable");

  useEffect(() => {
    try {
      const stored = localStorage.getItem("rl_ledger_density");
      if (stored === "compact" || stored === "comfortable") {
        setDensityState(stored as LedgerDensity);
      } else if (typeof window !== "undefined" && window.innerWidth < 1536) {
        setDensityState("compact");
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

  // Issued & Pending counts (server-computed across all pages, matching active period/search/anchor)
  const issuedCount = tabCounts.issued;
  const pendingCount = tabCounts.pending;
  const activeTenuresTotal = tabCounts.all;

  // Reset to page 1 when filters or sort change
  useEffect(() => {
    setPage(1);
  }, [
    selectedYear,
    selectedMonth,
    anchor,
    category,
    stageFilter,
    debouncedSearch,
    statusFilter,
    policyFilter,
    showHidden,
    sortBy,
    sortDir,
  ]);

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
      const params = new URLSearchParams();
      params.set("anchor", anchor);
      params.set("category", category);
      if (showHidden) params.set("show_hidden", "true");
      const res = await api<{
        years: YoYStatItem[];
        all_years?: { total: number; cars: number; active: number; lost: number };
        all_years_summary?: { total: number; cars: number; active: number; lost: number };
      }>(`/tenures/yoy-stats?${params.toString()}`);
      setYoyStats(res.years || []);
      setAllYearsSummary(res.all_years ?? res.all_years_summary ?? null);
    } catch (err) {
      console.error("Failed to load YoY stats:", err);
    } finally {
      setLoadingYoy(false);
    }
  }, [anchor, category, showHidden]);

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
      const params = new URLSearchParams();
      params.set("anchor", anchor);
      params.set("category", category);
      if (debouncedSearch.trim()) params.set("search", debouncedSearch.trim());
      if (showHidden) params.set("show_hidden", "true");
      const res = await api<{
        months: MonthItem[];
        summary_by_month?: MonthSummaryByNum[];
      }>(`/tenures/months?${params.toString()}`);
      setMonths(res.months || []);
      setSummaryByMonth(res.summary_by_month || []);
    } catch (err) {
      console.error("Failed to load months:", err);
    } finally {
      setLoadingMonths(false);
    }
  }, [anchor, category, debouncedSearch, showHidden]);

  // Load 5-Stage KPI Summary
  const loadStageSummary = useCallback(async () => {
    setLoadingSummary(true);
    try {
      const params = new URLSearchParams();
      params.set("anchor", anchor);
      params.set("category", category);
      if (selectedMonth && selectedMonth !== "all") {
        if (selectedMonth.includes("-")) {
          const parts = selectedMonth.split("-");
          params.set("year", parts[0]);
          params.set("month", String(parseInt(parts[1], 10)));
        } else {
          params.set("month", String(parseInt(selectedMonth, 10)));
        }
      } else if (selectedYear && selectedYear !== "all") {
        params.set("year", selectedYear);
      }
      if (debouncedSearch.trim()) params.set("search", debouncedSearch.trim());
      if (policyFilter !== "all") params.set("policy_status", policyFilter);
      if (showHidden) params.set("show_hidden", "true");
      const data = await api<StageSummary>(`/tenures/stage-summary?${params.toString()}`);
      setSummary(data);
    } catch (err) {
      console.error("Failed to load stage summary:", err);
    } finally {
      setLoadingSummary(false);
    }
  }, [selectedYear, selectedMonth, anchor, category, debouncedSearch, policyFilter, showHidden]);

  // Load Tenures
  const loadTenures = useCallback(async () => {
    setLoadingTenures(true);
    try {
      const params = new URLSearchParams();
      params.set("anchor", anchor);
      params.set("category", category);
      if (selectedMonth && selectedMonth !== "all") {
        if (selectedMonth.includes("-")) {
          const parts = selectedMonth.split("-");
          params.set("year", parts[0]);
          params.set("month", String(parseInt(parts[1], 10)));
        } else {
          params.set("month", String(parseInt(selectedMonth, 10)));
        }
      } else if (selectedYear && selectedYear !== "all") {
        params.set("year", selectedYear);
      }

      if (stageFilter && stageFilter !== "all") {
        params.set("stage", stageFilter);
      }
      if (policyFilter !== "all") {
        params.set("policy_status", policyFilter);
      }
      if (debouncedSearch.trim()) {
        params.set("search", debouncedSearch.trim());
      }
      if (statusFilter && statusFilter !== "all") {
        params.set("status", statusFilter);
      }
      if (showHidden) {
        params.set("show_hidden", "true");
      }
      params.set("sort_by", sortBy);
      params.set("sort_dir", sortDir);
      params.set("page", String(page));
      params.set("page_size", String(pageSize));

      const res = await api<{
        items: TenureRow[];
        total: number;
        active_total?: number;
        issued_count?: number;
        pending_count?: number;
      }>(`/tenures?${params.toString()}`);
      setTenures(res.items || []);
      setTotalTenures(res.total ?? (res.items || []).length);
      setTabCounts({
        all: res.active_total ?? res.total ?? (res.items || []).length,
        issued: res.issued_count ?? 0,
        pending: res.pending_count ?? 0,
      });
    } catch (err) {
      console.error("Failed to load tenures:", err);
    } finally {
      setLoadingTenures(false);
    }
  }, [
    selectedYear,
    selectedMonth,
    anchor,
    category,
    stageFilter,
    policyFilter,
    debouncedSearch,
    statusFilter,
    showHidden,
    sortBy,
    sortDir,
    page,
    pageSize,
  ]);

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
        const mPart = selectedMonth.includes("-") ? selectedMonth.split("-")[1] : selectedMonth;
        params.set("month", String(parseInt(mPart, 10)));
      }
      if (calendarVehicleFilter && calendarVehicleFilter !== "all") {
        params.set("vehicle_no", calendarVehicleFilter);
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
  }, [viewMode, selectedYear, selectedMonth, calendarVehicleFilter]);

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

      await api(`/tenures/${tenureId}/ledger-fields`, {
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
    if (selectedTenureIds.length === 0) return;
    setPendingBulkAction("delete");
  };

  const handleBulkConfirmHit = async () => {
    if (selectedTenureIds.length === 0) return;
    setPendingBulkAction("hit");
  };

  const confirmPendingBulkAction = async () => {
    const action = pendingBulkAction;
    if (!action || selectedTenureIds.length === 0) {
      setPendingBulkAction(null);
      return;
    }
    const count = selectedTenureIds.length;
    if (action === "delete") {
      setDeletingBulk(true);
      try {
        await api("/tenures/bulk", {
          method: "DELETE",
          body: JSON.stringify({ tenure_ids: selectedTenureIds }),
        });
        setSelectedTenureIds([]);
        setPendingBulkAction(null);
        toast(`Moved ${count} deal(s) to Trash.`, "success");
        loadTenures();
        loadStageSummary();
        loadMonths();
        loadYoyStats();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        toast("Bulk delete failed: " + msg, "error");
        setPendingBulkAction(null);
      } finally {
        setDeletingBulk(false);
      }
      return;
    }

    setConfirmingBulk(true);
    try {
      await api("/tenures/bulk-confirm-hit", {
        method: "POST",
        body: JSON.stringify({ tenure_ids: selectedTenureIds }),
      });
      setSelectedTenureIds([]);
      setPendingBulkAction(null);
      toast(`Confirmed ${count} deal(s) as HIT.`, "success");
      loadTenures();
      loadStageSummary();
      loadMonths();
      loadYoyStats();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast("Bulk confirm hit failed: " + msg, "error");
      setPendingBulkAction(null);
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

  // 12 Clean Month list for selected year (or aggregated across all years when selectedYear === "all")
  const monthsOfYear = useMemo(() => {
    if (selectedYear === "all") {
      return MONTH_NAMES.map((name, idx) => {
        const mNum = idx + 1;
        const mKey = String(mNum).padStart(2, "0");
        const existing = summaryByMonth.find((m) => m.month_num === mNum);
        return {
          month: mKey,
          label: name,
          total: existing?.total || 0,
          start_count: existing?.start_count || 0,
          end_count: existing?.end_count || 0,
          cars: existing?.cars || 0,
        };
      });
    }
    return MONTH_NAMES.map((name, idx) => {
      const mStr = `${selectedYear}-${String(idx + 1).padStart(2, "0")}`;
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
  }, [selectedYear, months, summaryByMonth]);

  // Calendar Geometry for Visual View
  const calendarData = useMemo(() => {
    const now = new Date();
    let yr = selectedYear !== "all" ? parseInt(selectedYear, 10) : now.getFullYear();
    let mo = now.getMonth();

    if (selectedMonth && selectedMonth !== "all") {
      if (selectedMonth.includes("-")) {
        const parts = selectedMonth.split("-");
        yr = parseInt(parts[0], 10);
        mo = parseInt(parts[1], 10) - 1;
      } else {
        mo = Math.max(0, Math.min(11, parseInt(selectedMonth, 10) - 1));
      }
    } else if (selectedYear !== "all" && yr !== now.getFullYear()) {
      const firstActiveIdx = monthsOfYear.findIndex((m) => m.total > 0);
      mo = firstActiveIdx >= 0 ? firstActiveIdx : 0;
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

    // 2. Include all active non-discarded non-lost tenures in calendar view (never gate on is_main)
    const calendarTenures = tenures.filter(
      (t) => !t.is_discarded && t.stage !== "Close - Lose" && t.stage !== "Others"
    );
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
  }, [selectedYear, selectedMonth, monthsOfYear, calendarSessions, tenures, calendarVehicleFilter]);

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

  // 1 row per policy term (never collapse 2026 & 2027 terms into one hidden row under All Years)
  const vehicleGroups = useMemo(() => {
    const groups: VehicleGroup[] = tenures.map((t) => ({
      vehicle_no: (t.vehicle_no || t.chassis_no || t.id).trim().toUpperCase(),
      customer_name: t.customer_name,
      customer_ic_no: t.customer_ic_no,
      car_brand: t.car_brand,
      car_model: t.car_model,
      engine_cc: t.engine_cc,
      manufacture_year: t.manufacture_year,
      chassis_no: t.chassis_no,
      engine_no: t.engine_no,
      mainTenure: t,
      tenures: [t],
    }));

    // 1. Instant client-side search filtering (0ms latency while typing, before debounced network query)
    const query = searchInput.trim().toLowerCase();
    const searched = query
      ? groups.filter((g) => {
          const matchVehicle = (g.vehicle_no || "").toLowerCase().includes(query);
          const matchCustomer = (g.customer_name || "").toLowerCase().includes(query);
          const matchIc = (g.customer_ic_no || "").toLowerCase().includes(query);
          const matchChassis = (g.chassis_no || "").toLowerCase().includes(query);
          const matchEngine = (g.engine_no || "").toLowerCase().includes(query);
          const matchBrand = (g.car_brand || "").toLowerCase().includes(query);
          const matchModel = (g.car_model || "").toLowerCase().includes(query);
          const matchPolicy =
            (g.mainTenure?.policy_number || "").toLowerCase().includes(query) ||
            (g.mainTenure?.covernote_policy?.policy_number || "").toLowerCase().includes(query);
          const matchSubagent = (g.mainTenure?.sub_agent_name || "").toLowerCase().includes(query);
          const matchNotes =
            (g.mainTenure?.notes || "").toLowerCase().includes(query) ||
            (g.mainTenure?.comment || "").toLowerCase().includes(query) ||
            (g.mainTenure?.client_preference_notes || "").toLowerCase().includes(query);
          const matchQuotes = g.tenures.some((t) =>
            (t.policy_number || "").toLowerCase().includes(query) ||
            (t.covernote_policy?.policy_number || "").toLowerCase().includes(query) ||
            t.sourced_quotes?.some((q) => (q.company || "").toLowerCase().includes(query))
          );
          return (
            matchVehicle ||
            matchCustomer ||
            matchIc ||
            matchChassis ||
            matchEngine ||
            matchBrand ||
            matchModel ||
            matchPolicy ||
            matchSubagent ||
            matchNotes ||
            matchQuotes
          );
        })
      : groups;

    const filtered = searched.filter((g) => {
      if (policyFilter === "all") return true;
      const t = g.mainTenure;
      const hasPolicy = Boolean(
        t.is_covernote_issued ||
          (t.covernote_policy && !t.covernote_policy.is_previous_year_policy) ||
          t.stage === "Close - Win" ||
          t.status === "hit"
      );
      if (policyFilter === "issued") return hasPolicy;
      if (policyFilter === "pending") return !hasPolicy;
      return true;
    });

    return filtered;
  }, [tenures, policyFilter, searchInput]);

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
    anchor,
    setAnchor,
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
    totalTenures,
    page,
    setPage,
    pageSize,
    activeTenuresTotal,
    loadingTenures,
    search: searchInput,
    setSearch: setSearchInput,
    debouncedSearch,
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
    pendingBulkAction,
    setPendingBulkAction,
    confirmPendingBulkAction,
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
