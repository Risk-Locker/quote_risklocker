"use client";

import { useEffect, useState, useMemo } from "react";
import {
  CalendarBlank,
  CaretLeft,
  CaretRight,
  CheckCircle,
  Clock,
  Eye,
  FilePdf,
  Funnel,
  GitDiff,
  PaperPlaneTilt,
  Sparkle,
  User,
  X,
  XCircle,
  MagnifyingGlass,
  ArrowSquareOut,
  Car,
  ArrowsClockwise,
  CheckSquare,
  Square,
  Rows,
  ListDashes,
  SlidersHorizontal,
  CaretDown,
  CaretUp,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";

type CalendarViewMode = "year" | "month" | "week" | "day";

interface CalendarActivity {
  id: string;
  session_id: string;
  vehicle_no: string;
  customer_name: string;
  action_type: string;
  timestamp: string | null;
  time_display: string;
  version_number: number;
  sent_to_client: boolean;
  summary: string;
  addons_snapshot?: any[];
  status: string;
  miss_reason?: string | null;
  won_premium?: number | null;
  total_premium?: string | null;
  company?: string;
  notes?: string | null;
  user_email?: string | null;
}

interface CalendarData {
  dates: Record<string, CalendarActivity[]>;
  total_activities: number;
}

const MISS_REASONS = [
  "Price too high / Competitor cheaper",
  "Client renewed elsewhere",
  "Delay in decision / Thinking over",
  "Vehicle sold / Transfer of ownership",
  "Client unreachable / No response",
  "Purchased directly with insurer",
  "Other",
];

export function TeamsCalendarView({
  onOpenVehicleHistory,
}: {
  onOpenVehicleHistory: (vehicleNo: string) => void;
}) {
  const { toast } = useToast();
  const [data, setData] = useState<CalendarData | null>(null);
  const [loading, setLoading] = useState(true);

  // View Mode: Year, Month, Week, Day
  const [viewMode, setViewMode] = useState<CalendarViewMode>("month");
  // Current focal date
  const [currentDate, setCurrentDate] = useState<Date>(new Date());

  // Filters
  const [statusFilter, setStatusFilter] = useState("all");
  const [companyFilter, setCompanyFilter] = useState("all");
  const [sentOnly, setSentOnly] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  // Day View Granularity & Clutter Controls
  const [dayTimeScale, setDayTimeScale] = useState<"60" | "30" | "15">("60");
  const [dayDensity, setDayDensity] = useState<"detailed" | "compact">("detailed");
  const [customerFilter, setCustomerFilter] = useState("all");
  const [selectedActivityIds, setSelectedActivityIds] = useState<Set<string>>(new Set());
  const [focusModeOnly, setFocusModeOnly] = useState(false);
  const [coalesceSessions, setCoalesceSessions] = useState(true);
  const [expandedSessionIds, setExpandedSessionIds] = useState<Set<string>>(new Set());

  // Status Change Modal
  const [selectedActivity, setSelectedActivity] = useState<CalendarActivity | null>(null);
  const [targetStatus, setTargetStatus] = useState<"hit" | "miss" | "pending">("hit");
  const [missReason, setMissReason] = useState(MISS_REASONS[0]);
  const [customMissReason, setCustomMissReason] = useState("");
  const [wonPremiumInput, setWonPremiumInput] = useState("");
  const [submittingStatus, setSubmittingStatus] = useState(false);
  const [coverageStartDate, setCoverageStartDate] = useState<string>("");
  const [coverageEndDate, setCoverageEndDate] = useState<string>("");

  // Diff drawer
  const [diffActivity, setDiffActivity] = useState<CalendarActivity | null>(null);

  function toDateKey(d: Date): string {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  // Fetch activities with date scoping based on viewMode
  async function fetchCalendarActivities() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (sentOnly) params.set("sent_only", "true");
      if (searchTerm.trim()) params.set("search", searchTerm.trim());

      const year = currentDate.getFullYear();
      if (viewMode === "year") {
        params.set("date_from", `${year}-01-01`);
        params.set("date_to", `${year}-12-31`);
        params.set("limit", "1000");
      } else if (viewMode === "month") {
        const month = currentDate.getMonth();
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        firstDay.setDate(firstDay.getDate() - 7);
        lastDay.setDate(lastDay.getDate() + 7);
        params.set("date_from", toDateKey(firstDay));
        params.set("date_to", toDateKey(lastDay));
        params.set("limit", "500");
      } else if (viewMode === "week") {
        const startOfWeek = new Date(currentDate);
        const day = startOfWeek.getDay();
        const diff = startOfWeek.getDate() - day + (day === 0 ? -6 : 1);
        startOfWeek.setDate(diff);
        const endOfWeek = new Date(startOfWeek);
        endOfWeek.setDate(startOfWeek.getDate() + 6);
        params.set("date_from", toDateKey(startOfWeek));
        params.set("date_to", toDateKey(endOfWeek));
        params.set("limit", "300");
      } else {
        const dKey = toDateKey(currentDate);
        params.set("date_from", dKey);
        params.set("date_to", dKey);
        params.set("limit", "250");
      }

      const res = await api<CalendarData>(`/insights/calendar?${params.toString()}`);
      setData(res);
    } catch (e: any) {
      toast(e?.message || "Could not retrieve quotation activity schedule", "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchCalendarActivities();
  }, [
    statusFilter,
    sentOnly,
    viewMode,
    currentDate.getFullYear(),
    viewMode === "month" ? currentDate.getMonth() : viewMode === "week" ? Math.floor(currentDate.getDate() / 7) : currentDate.getDate(),
  ]);

  // Flattened activities map: "YYYY-MM-DD" -> CalendarActivity[]
  const dateActivitiesMap = useMemo(() => {
    if (!data?.dates) return new Map<string, CalendarActivity[]>();
    const map = new Map<string, CalendarActivity[]>();
    for (const [dStr, items] of Object.entries(data.dates)) {
      let filtered = items;
      if (companyFilter !== "all") {
        filtered = filtered.filter((i) => (i.company || "").toLowerCase() === companyFilter.toLowerCase());
      }
      if (searchTerm.trim()) {
        const st = searchTerm.trim().toLowerCase();
        filtered = filtered.filter(
          (i) =>
            i.vehicle_no.toLowerCase().includes(st) ||
            i.customer_name.toLowerCase().includes(st) ||
            i.summary.toLowerCase().includes(st)
        );
      }
      map.set(dStr, filtered);
    }
    return map;
  }, [data, companyFilter, searchTerm]);

  // Companies available in activities
  const availableCompanies = useMemo(() => {
    if (!data?.dates) return [];
    const set = new Set<string>();
    for (const items of Object.values(data.dates)) {
      for (const i of items) {
        if (i.company) set.add(i.company);
      }
    }
    return Array.from(set).sort();
  }, [data]);

  function handlePrev() {
    const d = new Date(currentDate);
    if (viewMode === "year") {
      d.setFullYear(d.getFullYear() - 1);
    } else if (viewMode === "month") {
      d.setMonth(d.getMonth() - 1);
    } else if (viewMode === "week") {
      d.setDate(d.getDate() - 7);
    } else {
      d.setDate(d.getDate() - 1);
    }
    setCurrentDate(d);
  }

  function handleNext() {
    const d = new Date(currentDate);
    if (viewMode === "year") {
      d.setFullYear(d.getFullYear() + 1);
    } else if (viewMode === "month") {
      d.setMonth(d.getMonth() + 1);
    } else if (viewMode === "week") {
      d.setDate(d.getDate() + 7);
    } else {
      d.setDate(d.getDate() + 1);
    }
    setCurrentDate(d);
  }

  function handleToday() {
    setCurrentDate(new Date());
  }

  function zoomIntoDay(date: Date) {
    setCurrentDate(new Date(date));
    setViewMode("day");
    setCustomerFilter("all");
    setSelectedActivityIds(new Set());
    setFocusModeOnly(false);
  }

  const headerTitle = useMemo(() => {
    if (viewMode === "year") {
      return currentDate.getFullYear().toString();
    }
    if (viewMode === "month") {
      return currentDate.toLocaleDateString("en-US", { month: "long", year: "numeric" });
    }
    if (viewMode === "week") {
      const startOfWeek = new Date(currentDate);
      const day = startOfWeek.getDay();
      const diff = startOfWeek.getDate() - day + (day === 0 ? -6 : 1);
      startOfWeek.setDate(diff);

      const endOfWeek = new Date(startOfWeek);
      endOfWeek.setDate(startOfWeek.getDate() + 6);

      const sStr = startOfWeek.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      const eStr = endOfWeek.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
      return `${sStr} – ${eStr}`;
    }
    return currentDate.toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  }, [currentDate, viewMode]);

  // 12 Months for Apple-Style Year View
  const yearMonths = useMemo(() => {
    if (viewMode !== "year") return [];
    const year = currentDate.getFullYear();
    const months = [];
    const monthNames = [
      "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December"
    ];

    for (let m = 0; m < 12; m++) {
      const firstDay = new Date(year, m, 1);
      const lastDayDate = new Date(year, m + 1, 0);
      const daysCount = lastDayDate.getDate();

      let startDayOfWeek = firstDay.getDay() - 1;
      if (startDayOfWeek === -1) startDayOfWeek = 6;

      let monthTotalQuotes = 0;
      let monthHits = 0;
      let monthMisses = 0;

      const days = [];
      for (let p = 0; p < startDayOfWeek; p++) {
        days.push({ dayNum: null, key: `pad-${m}-${p}`, activities: [] });
      }

      for (let d = 1; d <= daysCount; d++) {
        const dStr = `${year}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
        const acts = dateActivitiesMap.get(dStr) || [];
        monthTotalQuotes += acts.length;
        if (acts.some((a) => a.status === "hit")) monthHits++;
        if (acts.some((a) => a.status === "miss")) monthMisses++;

        days.push({
          dayNum: d,
          key: dStr,
          date: new Date(year, m, d),
          activities: acts,
          hasHit: acts.some((a) => a.status === "hit"),
          hasMiss: acts.some((a) => a.status === "miss"),
          hasPending: acts.some((a) => a.status === "pending" || a.status === "superseded"),
        });
      }

      months.push({
        monthIndex: m,
        name: monthNames[m],
        days,
        totalQuotes: monthTotalQuotes,
        hits: monthHits,
        misses: monthMisses,
      });
    }
    return months;
  }, [currentDate, viewMode, dateActivitiesMap]);

  // Days for Month View Grid
  const monthDays = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    const firstDayOfMonth = new Date(year, month, 1);
    const lastDayOfMonth = new Date(year, month + 1, 0);

    let startDay = firstDayOfMonth.getDay() - 1;
    if (startDay === -1) startDay = 6;

    const days: Array<{ date: Date; isCurrentMonth: boolean; key: string }> = [];

    for (let i = startDay; i > 0; i--) {
      const prevDate = new Date(year, month, 1 - i);
      days.push({ date: prevDate, isCurrentMonth: false, key: toDateKey(prevDate) });
    }

    for (let i = 1; i <= lastDayOfMonth.getDate(); i++) {
      const curDate = new Date(year, month, i);
      days.push({ date: curDate, isCurrentMonth: true, key: toDateKey(curDate) });
    }

    const remaining = 42 - days.length;
    for (let i = 1; i <= remaining; i++) {
      const nextDate = new Date(year, month + 1, i);
      days.push({ date: nextDate, isCurrentMonth: false, key: toDateKey(nextDate) });
    }

    return days;
  }, [currentDate]);

  // Days for Week View
  const weekDays = useMemo(() => {
    const d = new Date(currentDate);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(d.setDate(diff));

    const result: Array<{ date: Date; key: string; label: string; isToday: boolean }> = [];
    const todayKey = toDateKey(new Date());

    for (let i = 0; i < 7; i++) {
      const dayDate = new Date(monday);
      dayDate.setDate(monday.getDate() + i);
      const key = toDateKey(dayDate);
      result.push({
        date: dayDate,
        key,
        label: dayDate.toLocaleDateString("en-US", { weekday: "short", day: "numeric" }),
        isToday: key === todayKey,
      });
    }
    return result;
  }, [currentDate]);

  // Day View Raw Activities
  const rawDayActivities = useMemo(() => {
    const key = toDateKey(currentDate);
    return dateActivitiesMap.get(key) || [];
  }, [currentDate, dateActivitiesMap]);

  // Unique customers for the day's quick-filter pills
  const dayUniqueCustomers = useMemo(() => {
    const counts = new Map<string, number>();
    for (const a of rawDayActivities) {
      const name = (a.customer_name || "").trim();
      if (name) counts.set(name, (counts.get(name) || 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [rawDayActivities]);

  // Filtered day activities (after customer pill filter and focus mode)
  const dayActivities = useMemo(() => {
    let acts = rawDayActivities;

    if (customerFilter !== "all") {
      acts = acts.filter((a) => (a.customer_name || "").toLowerCase() === customerFilter.toLowerCase());
    }

    if (focusModeOnly && selectedActivityIds.size > 0) {
      acts = acts.filter((a) => selectedActivityIds.has(a.id) || selectedActivityIds.has(a.session_id));
    }

    return acts;
  }, [rawDayActivities, customerFilter, focusModeOnly, selectedActivityIds]);

  // Helper to parse minute of day from time_display
  function parseActMin(a: CalendarActivity): number {
    if (!a.time_display) return 12 * 60;
    const m = a.time_display.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
    if (!m) return 12 * 60;
    let h = parseInt(m[1], 10);
    const min = parseInt(m[2], 10);
    const ampm = m[3].toUpperCase();
    if (ampm === "PM" && h < 12) h += 12;
    if (ampm === "AM" && h === 12) h = 0;
    return h * 60 + min;
  }

  // Day Timeline Slots (Supports 60m, 30m, and 15m intervals with dynamic bounds)
  const dayTimelineSlots = useMemo(() => {
    if (viewMode !== "day") return [];

    let minHour = 8;
    let maxHour = 20;

    for (const act of dayActivities) {
      const totalM = parseActMin(act);
      const actH = Math.floor(totalM / 60);
      if (actH < minHour) minHour = Math.max(0, actH);
      if (actH >= maxHour) maxHour = Math.min(23, actH + 1);
    }

    const intervalMin = parseInt(dayTimeScale, 10) || 60;
    const slots = [];

    for (let currentM = minHour * 60; currentM < maxHour * 60; currentM += intervalMin) {
      const h24 = Math.floor(currentM / 60);
      const min = currentM % 60;
      const ampm = h24 >= 12 ? "PM" : "AM";
      const h12 = h24 % 12 === 0 ? 12 : h24 % 12;
      const label = `${String(h12).padStart(2, "0")}:${String(min).padStart(2, "0")} ${ampm}`;

      slots.push({
        startMin: currentM,
        endMin: currentM + intervalMin,
        label,
      });
    }

    return slots;
  }, [viewMode, dayActivities, dayTimeScale]);

  // Coalesced session groups
  const coalescedSessionGroups = useMemo(() => {
    if (!coalesceSessions) return null;
    const map = new Map<string, { main: CalendarActivity; all: CalendarActivity[] }>();

    for (const a of dayActivities) {
      if (!map.has(a.session_id)) {
        map.set(a.session_id, { main: a, all: [a] });
      } else {
        const group = map.get(a.session_id)!;
        group.all.push(a);
        if (a.status === "hit" || (a.status === "miss" && group.main.status !== "hit")) {
          group.main = a;
        }
      }
    }
    return map;
  }, [dayActivities, coalesceSessions]);

  function getActivitiesForSlot(startMin: number, endMin: number): Array<{ activity: CalendarActivity; childEvents?: CalendarActivity[] }> {
    if (coalesceSessions && coalescedSessionGroups) {
      const result: Array<{ activity: CalendarActivity; childEvents?: CalendarActivity[] }> = [];
      for (const group of coalescedSessionGroups.values()) {
        const m = parseActMin(group.main);
        if (m >= startMin && m < endMin) {
          result.push({ activity: group.main, childEvents: group.all.length > 1 ? group.all : undefined });
        }
      }
      return result;
    }

    return dayActivities
      .filter((a) => {
        const m = parseActMin(a);
        return m >= startMin && m < endMin;
      })
      .map((a) => ({ activity: a }));
  }

  // Handle status modal submission
  async function handleSubmitStatus() {
    if (!selectedActivity) return;
    setSubmittingStatus(true);
    try {
      const reason = missReason === "Other" ? customMissReason.trim() || "Other" : missReason;
      const wonPremiumNum = targetStatus === "hit" && wonPremiumInput ? parseFloat(wonPremiumInput) : undefined;

      await api(`/insights/sessions/${selectedActivity.session_id}/status`, {
        method: "POST",
        body: JSON.stringify({
          status: targetStatus,
          miss_reason: targetStatus === "miss" ? reason : undefined,
          won_premium: wonPremiumNum,
          coverage_start_date: targetStatus === "hit" ? coverageStartDate : undefined,
          coverage_end_date: targetStatus === "hit" ? coverageEndDate : undefined,
        }),
      });

      toast(`Quotation status updated to ${targetStatus.toUpperCase()}`, "success");
      setSelectedActivity(null);
      fetchCalendarActivities();
    } catch (e: any) {
      toast(e?.message || "Failed to update quotation status", "error");
    } finally {
      setSubmittingStatus(false);
    }
  }

  async function handleReopenSession(sessionId: string) {
    try {
      await api(`/insights/sessions/${sessionId}/status`, {
        method: "POST",
        body: JSON.stringify({ status: "pending" }),
      });
      toast("Quotation reopened as Pending", "success");
      fetchCalendarActivities();
    } catch (err: any) {
      toast(err?.message || "Failed to reopen quotation", "error");
    }
  }

  function handleOpenStatusModal(activity: CalendarActivity, status: "hit" | "miss" | "pending") {
    setSelectedActivity(activity);
    setTargetStatus(status);
    setWonPremiumInput(activity.total_premium?.replace("RM", "").replace(",", "").trim() || "");
    setMissReason(MISS_REASONS[0]);
    setCustomMissReason("");
    const todayStr = new Date().toISOString().split("T")[0];
    setCoverageStartDate(todayStr);
    const nextYear = new Date();
    nextYear.setFullYear(nextYear.getFullYear() + 1);
    nextYear.setDate(nextYear.getDate() - 1);
    setCoverageEndDate(nextYear.toISOString().split("T")[0]);
  }

  function toggleSelectActivity(id: string) {
    setSelectedActivityIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleExpandSession(sessionId: string) {
    setExpandedSessionIds((prev) => {
      const next = new Set(prev);
      if (next.has(sessionId)) next.delete(sessionId);
      else next.add(sessionId);
      return next;
    });
  }

  return (
    <div className="space-y-4">
      {/* Top Teams-Style Control Header */}
      <div className="bg-white border border-neutral-200/90 rounded-lg p-3 shadow-sm flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        {/* Left: Navigation & Focal Title */}
        <div className="flex items-center gap-3">
          <div className="flex items-center rounded-md border border-neutral-200 bg-neutral-50 p-0.5">
            <button
              type="button"
              onClick={handlePrev}
              className="p-1.5 hover:bg-white rounded text-neutral-700 hover:text-neutral-950 transition-colors cursor-pointer"
              title="Previous"
            >
              <CaretLeft size={16} />
            </button>
            <button
              type="button"
              onClick={handleToday}
              className="px-2.5 py-1 text-xs font-medium hover:bg-white rounded text-neutral-700 hover:text-neutral-950 transition-colors cursor-pointer"
            >
              Today
            </button>
            <button
              type="button"
              onClick={handleNext}
              className="p-1.5 hover:bg-white rounded text-neutral-700 hover:text-neutral-950 transition-colors cursor-pointer"
              title="Next"
            >
              <CaretRight size={16} />
            </button>
          </div>

          <h2 className="text-base font-bold text-neutral-900 tracking-tight flex items-center gap-2">
            <CalendarBlank size={18} className="text-[#1b1717]" />
            <span>{headerTitle}</span>
          </h2>
        </div>

        {/* Right: Search, View Mode Toggle & Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Text Search Bar */}
          <div className="relative">
            <MagnifyingGlass size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              placeholder="Search plate, customer..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="text-xs h-8 pl-8 pr-2.5 border border-neutral-200 rounded-md bg-white text-neutral-800 focus:outline-none focus:ring-1 focus:ring-neutral-400 w-40 sm:w-48"
            />
          </div>

          {/* View Mode Switcher (Year, Month, Week, Day) */}
          <div className="flex items-center rounded-md border border-neutral-200 bg-neutral-100 p-0.5 text-xs font-medium">
            <button
              type="button"
              onClick={() => setViewMode("year")}
              className={`px-2.5 py-1 rounded transition-all cursor-pointer ${
                viewMode === "year"
                  ? "bg-white text-neutral-900 shadow-sm font-semibold"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              Year
            </button>
            <button
              type="button"
              onClick={() => setViewMode("month")}
              className={`px-2.5 py-1 rounded transition-all cursor-pointer ${
                viewMode === "month"
                  ? "bg-white text-neutral-900 shadow-sm font-semibold"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              Month
            </button>
            <button
              type="button"
              onClick={() => setViewMode("week")}
              className={`px-2.5 py-1 rounded transition-all cursor-pointer ${
                viewMode === "week"
                  ? "bg-white text-neutral-900 shadow-sm font-semibold"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              Week
            </button>
            <button
              type="button"
              onClick={() => setViewMode("day")}
              className={`px-2.5 py-1 rounded transition-all cursor-pointer ${
                viewMode === "day"
                  ? "bg-white text-neutral-900 shadow-sm font-semibold"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              Day
            </button>
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs h-8 border border-neutral-200 rounded-md px-2 bg-white text-neutral-800"
          >
            <option value="all">All Statuses</option>
            <option value="hit">Hit (Won)</option>
            <option value="miss">Miss (Lost)</option>
            <option value="pending">Pending</option>
          </select>

          {/* Insurer Filter */}
          {availableCompanies.length > 0 && (
            <select
              value={companyFilter}
              onChange={(e) => setCompanyFilter(e.target.value)}
              className="text-xs h-8 border border-neutral-200 rounded-md px-2 bg-white text-neutral-800"
            >
              <option value="all">All Insurers</option>
              {availableCompanies.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          )}

          {/* Refresh */}
          <Button
            size="sm"
            variant="secondary"
            onClick={fetchCalendarActivities}
            className="text-xs h-8 px-2.5 border-neutral-200 text-neutral-700 hover:bg-neutral-50"
            title="Refresh schedule"
          >
            <ArrowsClockwise size={13} />
          </Button>
        </div>
      </div>

      {/* Main Calendar Display */}
      {loading ? (
        <div className="bg-white border border-neutral-200 rounded-lg p-16 text-center shadow-sm">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-neutral-300 border-t-[#1b1717] mb-3" />
          <p className="text-xs text-neutral-500 font-medium">Loading quotation schedule &amp; time slots...</p>
        </div>
      ) : viewMode === "year" ? (
        /* ==================== APPLE-STYLE YEAR VIEW ==================== */
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {yearMonths.map((m) => (
              <div
                key={m.monthIndex}
                className="bg-white border border-neutral-200 rounded-lg p-3.5 shadow-2xs hover:shadow-sm transition-all flex flex-col justify-between"
              >
                {/* Month Card Header */}
                <div
                  onClick={() => {
                    setCurrentDate(new Date(currentDate.getFullYear(), m.monthIndex, 1));
                    setViewMode("month");
                  }}
                  className="flex items-center justify-between pb-2 border-b border-neutral-100 cursor-pointer group"
                >
                  <h3 className="font-bold text-sm text-neutral-900 group-hover:text-emerald-700 transition-colors">
                    {m.name}
                  </h3>
                  <span className="text-[11px] font-semibold text-neutral-500 bg-neutral-100 px-2 py-0.5 rounded">
                    {m.totalQuotes} quote{m.totalQuotes === 1 ? "" : "s"}
                    {m.hits > 0 ? ` · ${m.hits} won` : ""}
                  </span>
                </div>

                {/* Day of week labels */}
                <div className="grid grid-cols-7 text-center text-[10px] font-semibold text-neutral-400 py-1.5 border-b border-neutral-50">
                  <span>M</span>
                  <span>T</span>
                  <span>W</span>
                  <span>T</span>
                  <span>F</span>
                  <span>S</span>
                  <span>S</span>
                </div>

                {/* Mini Day Matrix */}
                <div className="grid grid-cols-7 gap-y-1 text-center text-xs pt-1.5 min-h-[140px]">
                  {m.days.map((d) => {
                    if (d.dayNum === null) {
                      return <div key={d.key} className="h-6" />;
                    }

                    const hasActs = d.activities.length > 0;
                    return (
                      <button
                        key={d.key}
                        type="button"
                        onClick={() => zoomIntoDay(d.date!)}
                        className={`h-6 w-full rounded flex flex-col items-center justify-center relative transition-all cursor-pointer ${
                          hasActs
                            ? "font-bold text-neutral-900 hover:bg-neutral-100"
                            : "text-neutral-500 hover:bg-neutral-50"
                        }`}
                        title={
                          hasActs
                            ? `${d.activities.length} quotations on ${d.key}`
                            : d.key
                        }
                      >
                        <span className="text-[11px] leading-none">{d.dayNum}</span>
                        {hasActs && (
                          <span className="flex items-center gap-0.5 mt-0.5">
                            {d.hasHit && <span className="h-1 w-1 rounded-full bg-emerald-500" />}
                            {d.hasMiss && <span className="h-1 w-1 rounded-full bg-rose-500" />}
                            {!d.hasHit && !d.hasMiss && <span className="h-1 w-1 rounded-full bg-neutral-400" />}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : viewMode === "month" ? (
        /* ==================== MONTH VIEW ==================== */
        <div className="bg-white border border-neutral-200 rounded-lg shadow-sm overflow-hidden">
          {/* Day of Week Headers */}
          <div className="grid grid-cols-7 border-b border-neutral-200 bg-neutral-50 text-xs font-semibold text-neutral-600 text-center py-2.5">
            <div>Mon</div>
            <div>Tue</div>
            <div>Wed</div>
            <div>Thu</div>
            <div>Fri</div>
            <div>Sat</div>
            <div>Sun</div>
          </div>

          {/* Month Day Grid */}
          <div className="grid grid-cols-7 divide-x divide-y divide-neutral-100 min-h-[640px]">
            {monthDays.map((item) => {
              const activities = dateActivitiesMap.get(item.key) || [];
              const isToday = item.key === toDateKey(new Date());

              return (
                <div
                  key={item.key}
                  onClick={() => zoomIntoDay(item.date)}
                  className={`min-h-[110px] p-2 flex flex-col transition-all cursor-pointer group hover:bg-neutral-50/80 ${
                    !item.isCurrentMonth ? "bg-neutral-50/40 text-neutral-400" : "bg-white text-neutral-900"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span
                      className={`text-xs font-bold h-5 w-5 flex items-center justify-center rounded-full transition-colors ${
                        isToday
                          ? "bg-neutral-900 text-white"
                          : "text-neutral-700 group-hover:bg-neutral-200"
                      }`}
                    >
                      {item.date.getDate()}
                    </span>

                    {activities.length > 0 && (
                      <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-neutral-100 text-neutral-600">
                        {activities.length}
                      </span>
                    )}
                  </div>

                  {/* Activity Mini Cards */}
                  <div className="space-y-1 overflow-hidden flex-1">
                    {activities.slice(0, 3).map((act) => (
                      <div
                        key={act.id}
                        className={`text-[10px] px-1.5 py-0.5 rounded truncate border leading-tight ${
                          act.status === "hit"
                            ? "bg-emerald-50 text-emerald-800 border-emerald-200 font-semibold"
                            : act.status === "miss"
                            ? "bg-rose-50 text-rose-800 border-rose-200"
                            : act.status === "superseded"
                            ? "bg-purple-50 text-purple-800 border-purple-200 opacity-80"
                            : "bg-neutral-100 text-neutral-800 border-neutral-200"
                        }`}
                        title={`${act.vehicle_no} - ${act.customer_name} (${act.time_display})`}
                      >
                        <span className="font-bold mr-1">{act.vehicle_no}</span>
                        <span className="opacity-75">{act.customer_name}</span>
                      </div>
                    ))}

                    {activities.length > 3 && (
                      <div className="text-[10px] font-semibold text-neutral-500 pl-1">
                        +{activities.length - 3} more
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : viewMode === "week" ? (
        /* ==================== WEEK VIEW ==================== */
        <div className="bg-white border border-neutral-200 rounded-lg shadow-sm overflow-hidden">
          {/* Week Day Headers */}
          <div className="grid grid-cols-7 border-b border-neutral-200 bg-neutral-50 text-center py-2">
            {weekDays.map((w) => (
              <div
                key={w.key}
                onClick={() => zoomIntoDay(w.date)}
                className={`cursor-pointer hover:text-emerald-700 transition-colors ${
                  w.isToday ? "font-bold text-neutral-950" : "text-neutral-600 font-semibold"
                }`}
              >
                <div className="text-xs">{w.label}</div>
              </div>
            ))}
          </div>

          {/* Week Hours Grid */}
          <div className="divide-y divide-neutral-100 overflow-y-auto max-h-[680px]">
            {["08:00 AM", "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM", "07:00 PM", "08:00 PM"].map((hourLabel) => (
              <div key={hourLabel} className="grid grid-cols-7 min-h-[55px] divide-x divide-neutral-100">
                {weekDays.map((w) => {
                  const acts = (dateActivitiesMap.get(w.key) || []).filter((a) => {
                    if (!a.time_display) return false;
                    const actHourPrefix = a.time_display.split(":")[0];
                    const gridHourPrefix = hourLabel.split(":")[0];
                    const actAmPm = a.time_display.includes("PM") ? "PM" : "AM";
                    const gridAmPm = hourLabel.includes("PM") ? "PM" : "AM";
                    return actHourPrefix === gridHourPrefix && actAmPm === gridAmPm;
                  });

                  return (
                    <div
                      key={w.key + hourLabel}
                      onClick={() => zoomIntoDay(w.date)}
                      className="p-1 border-r border-neutral-100 hover:bg-neutral-50/60 transition-colors cursor-pointer space-y-1"
                    >
                      {acts.map((act) => (
                        <div
                          key={act.id}
                          className={`p-1.5 rounded border text-[11px] shadow-2xs ${
                            act.status === "hit"
                              ? "bg-emerald-50 border-emerald-200 text-emerald-900 font-semibold"
                              : act.status === "miss"
                              ? "bg-rose-50 border-rose-200 text-rose-900"
                              : act.status === "superseded"
                              ? "bg-purple-50 border-purple-200 text-purple-900"
                              : "bg-neutral-100 border-neutral-200 text-neutral-800"
                          }`}
                        >
                          <div className="font-bold flex items-center justify-between">
                            <span>{act.vehicle_no}</span>
                            <span className="text-[10px] opacity-75">{act.time_display}</span>
                          </div>
                          <div className="text-[10px] truncate text-neutral-600">{act.customer_name}</div>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* ==================== DAY VIEW (IPHONE-STYLE DEEP ZOOM & DENSE DAY CONTROLS) ==================== */
        <div className="bg-white border border-neutral-200 rounded-lg shadow-sm overflow-hidden space-y-0">
          {/* Day View Top Bar */}
          <div className="p-3.5 border-b border-neutral-200 bg-neutral-50/80 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div>
              <div className="text-xs text-neutral-500 font-medium">Timeline Schedule for</div>
              <h3 className="text-base font-bold text-neutral-900 flex items-center gap-2">
                <span>{currentDate.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-neutral-200/80 text-neutral-800">
                  {dayActivities.length} plotted
                </span>
              </h3>
            </div>

            {/* Granularity & Density Switchers */}
            <div className="flex items-center gap-2 flex-wrap">
              {/* Time Zoom Segmented Button */}
              <div className="flex items-center rounded-md border border-neutral-200 bg-white p-0.5 text-xs font-medium shadow-2xs">
                <span className="px-2 text-[10px] font-bold text-neutral-400 uppercase">Zoom:</span>
                <button
                  type="button"
                  onClick={() => setDayTimeScale("60")}
                  className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
                    dayTimeScale === "60"
                      ? "bg-neutral-900 text-white font-semibold"
                      : "text-neutral-600 hover:text-neutral-950"
                  }`}
                  title="1-hour slot increments"
                >
                  1 Hour
                </button>
                <button
                  type="button"
                  onClick={() => setDayTimeScale("30")}
                  className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
                    dayTimeScale === "30"
                      ? "bg-neutral-900 text-white font-semibold"
                      : "text-neutral-600 hover:text-neutral-950"
                  }`}
                  title="30-minute slot increments"
                >
                  30 Min
                </button>
                <button
                  type="button"
                  onClick={() => setDayTimeScale("15")}
                  className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
                    dayTimeScale === "15"
                      ? "bg-neutral-900 text-white font-semibold"
                      : "text-neutral-600 hover:text-neutral-950"
                  }`}
                  title="15-minute minute-level precision"
                >
                  15 Min
                </button>
              </div>

              {/* Density Switcher */}
              <div className="flex items-center rounded-md border border-neutral-200 bg-white p-0.5 text-xs font-medium shadow-2xs">
                <button
                  type="button"
                  onClick={() => setDayDensity("detailed")}
                  className={`px-2 py-0.5 rounded transition-all cursor-pointer flex items-center gap-1 ${
                    dayDensity === "detailed"
                      ? "bg-neutral-900 text-white font-semibold"
                      : "text-neutral-600 hover:text-neutral-950"
                  }`}
                  title="Spacious detailed cards"
                >
                  <Rows size={13} />
                  <span>Detailed</span>
                </button>
                <button
                  type="button"
                  onClick={() => setDayDensity("compact")}
                  className={`px-2 py-0.5 rounded transition-all cursor-pointer flex items-center gap-1 ${
                    dayDensity === "compact"
                      ? "bg-neutral-900 text-white font-semibold"
                      : "text-neutral-600 hover:text-neutral-950"
                  }`}
                  title="Compact dense rows for 20+ quotes"
                >
                  <ListDashes size={13} />
                  <span>Compact</span>
                </button>
              </div>

              {/* Coalesce Sessions Toggle */}
              <button
                type="button"
                onClick={() => setCoalesceSessions(!coalesceSessions)}
                className={`text-xs px-2.5 py-1 rounded border transition-all cursor-pointer font-medium ${
                  coalesceSessions
                    ? "bg-emerald-50 border-emerald-300 text-emerald-900 font-semibold"
                    : "bg-white border-neutral-200 text-neutral-600 hover:bg-neutral-50"
                }`}
                title="When active, coalesces multiple events for the same vehicle into 1 clean quotation card"
              >
                {coalesceSessions ? "✓ Unique Quotes" : "All Raw Events"}
              </button>

              <Button
                size="sm"
                variant="secondary"
                onClick={() => setViewMode("month")}
                className="text-xs h-7 border-neutral-200"
              >
                Zoom to Month
              </Button>
            </div>
          </div>

          {/* Quick Filter Customer Pills & Selection Bar */}
          <div className="px-3.5 py-2.5 bg-neutral-50/50 border-b border-neutral-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2.5">
            {/* Customer Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto max-w-full pb-0.5">
              <span className="text-[11px] font-bold text-neutral-400 uppercase shrink-0">Filter Client:</span>
              <button
                type="button"
                onClick={() => setCustomerFilter("all")}
                className={`px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap transition-all cursor-pointer ${
                  customerFilter === "all"
                    ? "bg-neutral-900 text-white shadow-2xs"
                    : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                }`}
              >
                All ({rawDayActivities.length})
              </button>
              {dayUniqueCustomers.map(([cust, count]) => (
                <button
                  key={cust}
                  type="button"
                  onClick={() => setCustomerFilter(cust)}
                  className={`px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap transition-all cursor-pointer ${
                    customerFilter.toLowerCase() === cust.toLowerCase()
                      ? "bg-neutral-900 text-white shadow-2xs font-semibold"
                      : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                  }`}
                >
                  {cust} ({count})
                </button>
              ))}
            </div>

            {/* Selection & Focus Mode Controls */}
            <div className="flex items-center gap-2 shrink-0">
              {selectedActivityIds.size > 0 ? (
                <>
                  <button
                    type="button"
                    onClick={() => setFocusModeOnly(!focusModeOnly)}
                    className={`text-xs px-2.5 py-1 rounded font-semibold transition-all cursor-pointer ${
                      focusModeOnly
                        ? "bg-amber-600 text-white"
                        : "bg-amber-100 border border-amber-300 text-amber-900 hover:bg-amber-200"
                    }`}
                  >
                    {focusModeOnly ? "Show All Items" : `Focus Selected (${selectedActivityIds.size})`}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedActivityIds(new Set());
                      setFocusModeOnly(false);
                    }}
                    className="text-xs px-2 py-1 text-neutral-500 hover:text-neutral-800 underline cursor-pointer"
                  >
                    Clear Selection
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => setSelectedActivityIds(new Set(dayActivities.map((a) => a.id)))}
                  className="text-xs px-2 py-1 text-neutral-600 hover:text-neutral-900 border border-neutral-200 rounded hover:bg-white transition-colors cursor-pointer"
                >
                  Select All
                </button>
              )}
            </div>
          </div>

          {/* Granular Timeline Grid */}
          <div className="divide-y divide-neutral-100 overflow-y-auto max-h-[750px]">
            {dayTimelineSlots.map((slot) => {
              const matchedItems = getActivitiesForSlot(slot.startMin, slot.endMin);

              return (
                <div key={slot.label} className="flex min-h-[55px] group hover:bg-neutral-50/50 transition-colors">
                  {/* Time Gutter */}
                  <div className="w-24 shrink-0 p-2.5 text-xs font-semibold text-neutral-400 border-r border-neutral-200 text-right pr-4 select-none">
                    {slot.label}
                  </div>

                  {/* Slot Content */}
                  <div className="flex-1 p-2 space-y-2">
                    {matchedItems.length === 0 ? (
                      <div className="h-full flex items-center pl-2 text-xs text-neutral-300 font-light select-none">
                        —
                      </div>
                    ) : (
                      matchedItems.map(({ activity: act, childEvents }) => {
                        const isHit = act.status === "hit";
                        const isMiss = act.status === "miss";
                        const isSelected = selectedActivityIds.has(act.id) || selectedActivityIds.has(act.session_id);
                        const isExpanded = expandedSessionIds.has(act.session_id);

                        if (dayDensity === "compact") {
                          /* COMPACT DENSE ROW */
                          return (
                            <div
                              key={act.id}
                              className={`px-3 py-1.5 rounded border text-xs flex flex-col gap-1 transition-all ${
                                isSelected ? "ring-2 ring-neutral-900 bg-neutral-50" : ""
                              } ${
                                isHit
                                  ? "bg-emerald-50/70 border-emerald-200 text-emerald-950"
                                  : isMiss
                                  ? "bg-rose-50/70 border-rose-200 text-rose-950"
                                  : "bg-white border-neutral-200 text-neutral-900"
                              }`}
                            >
                              <div className="flex items-center justify-between gap-2 flex-wrap">
                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => toggleSelectActivity(act.id)}
                                    className="text-neutral-500 hover:text-neutral-950 cursor-pointer"
                                  >
                                    {isSelected ? <CheckSquare size={15} weight="fill" /> : <Square size={15} />}
                                  </button>

                                  <span className="font-bold text-neutral-900 font-mono text-[11px] bg-neutral-100 px-1.5 py-0.5 rounded">
                                    {act.time_display}
                                  </span>

                                  <button
                                    type="button"
                                    onClick={() => onOpenVehicleHistory(act.vehicle_no)}
                                    className="font-bold hover:underline flex items-center gap-1 text-neutral-900"
                                    title="View Vehicle Ownership History"
                                  >
                                    <Car size={14} className="text-neutral-500" />
                                    <span>{act.vehicle_no}</span>
                                  </button>

                                  <span className="text-neutral-600 font-medium truncate max-w-[160px]">
                                    {act.customer_name}
                                  </span>

                                  {act.company && (
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-600 border border-neutral-200">
                                      {act.company}
                                    </span>
                                  )}

                                  {childEvents && (
                                    <button
                                      type="button"
                                      onClick={() => toggleExpandSession(act.session_id)}
                                      className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-200/80 hover:bg-neutral-300 text-neutral-800 font-semibold flex items-center gap-0.5 cursor-pointer"
                                    >
                                      <span>{childEvents.length} events</span>
                                      {isExpanded ? <CaretUp size={10} /> : <CaretDown size={10} />}
                                    </button>
                                  )}
                                </div>

                                <div className="flex items-center gap-1.5">
                                  {isHit ? (
                                    <span className="font-bold text-emerald-800 text-[11px]">
                                      HIT {act.won_premium ? `· RM ${act.won_premium.toLocaleString()}` : ""}
                                    </span>
                                  ) : isMiss ? (
                                    <span className="font-bold text-rose-800 text-[11px]">
                                      MISS {act.miss_reason ? `(${act.miss_reason})` : ""}
                                    </span>
                                  ) : (
                                    <span className="text-neutral-600 text-[11px] font-medium">Pending</span>
                                  )}

                                  {/* Quick Action Buttons */}
                                  {(isHit || isMiss || act.status === "superseded") && (
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => handleReopenSession(act.session_id)}
                                      className="text-[11px] h-6 px-1.5 text-neutral-600 hover:text-neutral-900"
                                      title="Reset status back to Pending"
                                    >
                                      Reopen
                                    </Button>
                                  )}

                                  {act.status !== "hit" && act.status !== "superseded" && (
                                    <Button
                                      size="sm"
                                      variant="secondary"
                                      onClick={() => handleOpenStatusModal(act, "hit")}
                                      className="text-[11px] h-6 px-1.5 border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                                    >
                                      Hit
                                    </Button>
                                  )}

                                  {act.status !== "miss" && act.status !== "superseded" && (
                                    <Button
                                      size="sm"
                                      variant="secondary"
                                      onClick={() => handleOpenStatusModal(act, "miss")}
                                      className="text-[11px] h-6 px-1.5 border-rose-200 text-rose-700 hover:bg-rose-50"
                                    >
                                      Miss
                                    </Button>
                                  )}

                                  <a
                                    href={`/sessions/${act.session_id}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[11px] text-neutral-500 hover:text-neutral-900 p-1 rounded hover:bg-neutral-100"
                                    title="Open review workspace"
                                  >
                                    <ArrowSquareOut size={13} />
                                  </a>
                                </div>
                              </div>

                              {/* Expanded Inline History for Coalesced Quotation */}
                              {isExpanded && childEvents && (
                                <div className="mt-1 pt-1.5 border-t border-neutral-200/60 pl-6 space-y-1 text-[11px] text-neutral-600">
                                  {childEvents.map((evt, idx) => (
                                    <div key={evt.id || idx} className="flex items-center gap-2">
                                      <span className="font-mono text-neutral-400 font-bold">{evt.time_display}</span>
                                      <span>·</span>
                                      <span className="font-medium text-neutral-800">{evt.summary}</span>
                                      {evt.sent_to_client && (
                                        <span className="text-[10px] bg-neutral-900 text-white px-1.5 py-0.2 rounded">
                                          Sent
                                        </span>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        }

                        /* DETAILED SPURIOUS CARD */
                        return (
                          <div
                            key={act.id}
                            className={`p-3 rounded-lg border shadow-xs transition-all ${
                              isSelected ? "ring-2 ring-neutral-900 bg-neutral-50" : ""
                            } ${
                              isHit
                                ? "bg-emerald-50/70 border-emerald-200 text-emerald-950"
                                : isMiss
                                ? "bg-rose-50/70 border-rose-200 text-rose-950"
                                : "bg-white border-neutral-200 text-neutral-900"
                            }`}
                          >
                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                              {/* Left Details */}
                              <div className="flex items-center gap-2.5 flex-wrap">
                                <button
                                  type="button"
                                  onClick={() => toggleSelectActivity(act.id)}
                                  className="text-neutral-400 hover:text-neutral-950 cursor-pointer"
                                >
                                  {isSelected ? <CheckSquare size={16} weight="fill" /> : <Square size={16} />}
                                </button>

                                <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded bg-neutral-900 text-white">
                                  <Clock size={12} />
                                  {act.time_display}
                                </span>

                                <button
                                  type="button"
                                  onClick={() => onOpenVehicleHistory(act.vehicle_no)}
                                  className="font-bold text-sm hover:underline flex items-center gap-1 text-neutral-900"
                                  title="View Vehicle Ownership History"
                                >
                                  <Car size={15} className="text-neutral-500" />
                                  <span>{act.vehicle_no}</span>
                                </button>

                                <span className="text-xs text-neutral-600 flex items-center gap-1">
                                  <User size={13} className="text-neutral-400" />
                                  <span>{act.customer_name}</span>
                                </span>

                                {act.company && (
                                  <span className="text-[11px] px-2 py-0.5 rounded bg-neutral-100 text-neutral-700 border border-neutral-200">
                                    {act.company}
                                  </span>
                                )}

                                {childEvents && (
                                  <button
                                    type="button"
                                    onClick={() => toggleExpandSession(act.session_id)}
                                    className="text-[11px] px-2 py-0.5 rounded bg-neutral-200/80 hover:bg-neutral-300 text-neutral-800 font-semibold flex items-center gap-1 cursor-pointer"
                                  >
                                    <span>{childEvents.length} events recorded</span>
                                    {isExpanded ? <CaretUp size={11} /> : <CaretDown size={11} />}
                                  </button>
                                )}
                              </div>

                              {/* Right Status Badges & Actions */}
                              <div className="flex items-center gap-2 flex-wrap">
                                {isHit && (
                                  <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300">
                                    <CheckCircle size={13} weight="bold" />
                                    HIT {act.won_premium ? `· RM ${act.won_premium.toLocaleString()}` : ""}
                                  </span>
                                )}

                                {isMiss && (
                                  <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-300">
                                    <XCircle size={13} weight="bold" />
                                    MISS {act.miss_reason ? `(${act.miss_reason})` : ""}
                                  </span>
                                )}

                                {!isHit && !isMiss && (
                                  <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-neutral-100 text-neutral-700 border border-neutral-200 font-medium">
                                    Pending
                                  </span>
                                )}

                                {act.sent_to_client && (
                                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-neutral-900 text-white font-medium">
                                    <PaperPlaneTilt size={11} weight="fill" />
                                    Sent
                                  </span>
                                )}

                                {(isHit || isMiss || act.status === "superseded") && (
                                  <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={() => handleReopenSession(act.session_id)}
                                    className="text-xs h-7 px-2 border-neutral-200 text-neutral-700 hover:bg-neutral-100 gap-1"
                                    title="Reset status back to Pending"
                                  >
                                    <ArrowsClockwise size={12} />
                                    Reopen
                                  </Button>
                                )}

                                {act.status !== "hit" && act.status !== "superseded" && (
                                  <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={() => handleOpenStatusModal(act, "hit")}
                                    className="text-xs h-7 px-2 border-emerald-200 text-emerald-700 hover:bg-emerald-50 gap-1"
                                  >
                                    <CheckCircle size={12} weight="bold" />
                                    Hit
                                  </Button>
                                )}

                                {act.status !== "miss" && act.status !== "superseded" && (
                                  <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={() => handleOpenStatusModal(act, "miss")}
                                    className="text-xs h-7 px-2 border-rose-200 text-rose-700 hover:bg-rose-50 gap-1"
                                  >
                                    <XCircle size={12} weight="bold" />
                                    Miss
                                  </Button>
                                )}

                                <a
                                  href={`/sessions/${act.session_id}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-xs text-neutral-600 hover:text-neutral-900 border border-neutral-200 rounded px-2 py-1 hover:bg-neutral-50 transition-colors"
                                  title="Open quotation review session"
                                >
                                  <ArrowSquareOut size={13} />
                                  Session
                                </a>
                              </div>
                            </div>

                            {/* Summary description */}
                            <div className="mt-1.5 text-xs text-neutral-600 flex items-center justify-between">
                              <span>{act.summary}</span>
                              {act.total_premium && (
                                <span className="text-neutral-500 font-medium">
                                  Gross: {act.total_premium}
                                </span>
                              )}
                            </div>

                            {/* Expanded History for Coalesced Quotation */}
                            {isExpanded && childEvents && (
                              <div className="mt-2.5 pt-2 border-t border-neutral-200/80 pl-2 space-y-1 text-xs text-neutral-600 bg-neutral-50/80 p-2 rounded">
                                <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider mb-1">
                                  Quotation Event Trail:
                                </div>
                                {childEvents.map((evt, idx) => (
                                  <div key={evt.id || idx} className="flex items-center gap-2">
                                    <span className="font-mono text-neutral-500 font-bold text-[11px]">{evt.time_display}</span>
                                    <span>·</span>
                                    <span className="text-neutral-800">{evt.summary}</span>
                                    {evt.sent_to_client && (
                                      <span className="text-[9px] bg-neutral-900 text-white px-1.5 py-0.2 rounded">
                                        Sent to Client
                                      </span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Status Modal */}
      {selectedActivity && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-neutral-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-100 pb-3">
              <h3 className="font-bold text-sm text-neutral-900 flex items-center gap-2">
                {targetStatus === "hit" ? (
                  <>
                    <CheckCircle size={18} className="text-emerald-600" weight="bold" />
                    <span>Mark Quotation as Won (HIT)</span>
                  </>
                ) : targetStatus === "miss" ? (
                  <>
                    <XCircle size={18} className="text-rose-600" weight="bold" />
                    <span>Mark Quotation as Lost (MISS)</span>
                  </>
                ) : (
                  <span>Reopen as Pending</span>
                )}
              </h3>
              <button
                type="button"
                onClick={() => setSelectedActivity(null)}
                className="text-neutral-400 hover:text-neutral-700 cursor-pointer"
              >
                <X size={16} />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 bg-neutral-50 rounded border border-neutral-200/80 space-y-1">
                <div className="font-semibold text-neutral-900">
                  Vehicle: {selectedActivity.vehicle_no}
                </div>
                <div className="text-neutral-600">Customer: {selectedActivity.customer_name}</div>
                {selectedActivity.total_premium && (
                  <div className="text-neutral-600">Total Premium: {selectedActivity.total_premium}</div>
                )}
              </div>

              {targetStatus === "hit" && (
                <div className="space-y-3">
                  <div className="space-y-1">
                    <label className="font-medium text-neutral-700">Confirmed Won Premium (RM)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={wonPremiumInput}
                      onChange={(e) => setWonPremiumInput(e.target.value)}
                      placeholder="e.g. 1450.00"
                      className="w-full h-8 px-2.5 rounded border border-neutral-300 text-xs focus:ring-1 focus:ring-neutral-900"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <div>
                      <label className="block text-[11px] font-semibold text-neutral-700 mb-1">
                        Coverage Start Date
                      </label>
                      <input
                        type="date"
                        value={coverageStartDate}
                        onChange={(e) => setCoverageStartDate(e.target.value)}
                        className="w-full text-xs h-8 px-2 rounded border border-neutral-300 bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-neutral-700 mb-1">
                        Coverage End Date
                      </label>
                      <input
                        type="date"
                        value={coverageEndDate}
                        onChange={(e) => setCoverageEndDate(e.target.value)}
                        className="w-full text-xs h-8 px-2 rounded border border-neutral-300 bg-white"
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 text-[11px] text-neutral-500">
                    <span>Quick Period:</span>
                    <button
                      type="button"
                      onClick={() => {
                        const s = new Date(coverageStartDate || new Date());
                        const e = new Date(s);
                        e.setFullYear(e.getFullYear() + 1);
                        e.setDate(e.getDate() - 1);
                        setCoverageEndDate(e.toISOString().split("T")[0]);
                      }}
                      className="px-2 py-0.5 rounded border border-neutral-200 bg-neutral-100 hover:bg-neutral-200 text-neutral-800 font-medium cursor-pointer"
                    >
                      1 Year
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const s = new Date(coverageStartDate || new Date());
                        const e = new Date(s);
                        e.setMonth(e.getMonth() + 6);
                        e.setDate(e.getDate() - 1);
                        setCoverageEndDate(e.toISOString().split("T")[0]);
                      }}
                      className="px-2 py-0.5 rounded border border-neutral-200 bg-neutral-100 hover:bg-neutral-200 text-neutral-800 font-medium cursor-pointer"
                    >
                      6 Months
                    </button>
                  </div>
                  <p className="text-[11px] text-neutral-500">
                    Finalizes policy for this vehicle and schedules a 9-month renewal reminder.
                  </p>
                </div>
              )}

              {targetStatus === "miss" && (
                <div className="space-y-2">
                  <label className="font-medium text-neutral-700">Primary Reason for Miss / Loss</label>
                  <select
                    value={missReason}
                    onChange={(e) => setMissReason(e.target.value)}
                    className="w-full h-8 px-2 rounded border border-neutral-300 text-xs bg-white focus:ring-1 focus:ring-neutral-900"
                  >
                    {MISS_REASONS.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>

                  {missReason === "Other" && (
                    <input
                      type="text"
                      placeholder="Specify custom loss reason..."
                      value={customMissReason}
                      onChange={(e) => setCustomMissReason(e.target.value)}
                      className="w-full h-8 px-2.5 rounded border border-neutral-300 text-xs mt-1.5 focus:ring-1 focus:ring-neutral-900"
                    />
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-neutral-100">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedActivity(null)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                loading={submittingStatus}
                onClick={handleSubmitStatus}
                className={`text-xs ${
                  targetStatus === "hit"
                    ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                    : targetStatus === "miss"
                    ? "bg-rose-600 hover:bg-rose-700 text-white"
                    : "bg-[#1b1717] hover:bg-[#2c2727] text-white"
                }`}
              >
                Confirm Status
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
