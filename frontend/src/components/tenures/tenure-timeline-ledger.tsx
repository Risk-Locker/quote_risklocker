"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
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
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { TenureTimelineDrawer } from "@/components/tenures/tenure-timeline-drawer";

export interface MonthItem {
  month: string;
  total: number;
  hit: number;
  miss: number;
  pending: number;
}

export interface TenureRow {
  id: string;
  vehicle_no: string;
  customer_name: string;
  coverage_start_date: string;
  coverage_end_date: string;
  expiry_month: string;
  status: string;
  winning_company_id: string | null;
  winning_quotation_ref: string | null;
  won_premium: number | null;
  miss_reason: string | null;
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
  created_at: string;
}

export function TenureTimelineLedger() {
  const [months, setMonths] = useState<MonthItem[]>([]);
  const [selectedMonth, setSelectedMonth] = useState<string>("");
  const [selectedYear, setSelectedYear] = useState<string>("all");
  const [loadingMonths, setLoadingMonths] = useState(true);

  const [tenures, setTenures] = useState<TenureRow[]>([]);
  const [loadingTenures, setLoadingTenures] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const [activeDrawerTenureId, setActiveDrawerTenureId] = useState<string | null>(null);
  const monthScrollRef = useRef<HTMLDivElement>(null);

  // Group months by Year
  const yearGroupMap = useMemo(() => {
    const map: Record<string, { year: string; total: number; months: MonthItem[] }> = {};
    months.forEach((m) => {
      if (m.month && m.month.includes("-")) {
        const y = m.month.split("-")[0];
        if (!map[y]) {
          map[y] = { year: y, total: 0, months: [] };
        }
        map[y].months.push(m);
        map[y].total += m.total;
      }
    });
    return map;
  }, [months]);

  const availableYears = useMemo(() => {
    return Object.keys(yearGroupMap).sort();
  }, [yearGroupMap]);

  // Grand total of all tenures across all months
  const grandTotal = useMemo(() => {
    return months.reduce((acc, m) => acc + (m.total || 0), 0);
  }, [months]);

  // Months list for the selected year (or all months if selectedYear === 'all')
  const monthsOfYear = useMemo(() => {
    if (selectedYear === "all") {
      return months.map((m) => ({
        month: m.month,
        shortLabel: formatMonthTab(m.month),
        total: m.total,
      }));
    }
    const y = selectedYear;
    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return monthNames.map((name, idx) => {
      const mStr = `${y}-${String(idx + 1).padStart(2, "0")}`;
      const existing = months.find((m) => m.month === mStr);
      return {
        month: mStr,
        shortLabel: name,
        total: existing ? existing.total : 0,
      };
    });
  }, [selectedYear, months]);

  // Load available expiry months
  const loadMonths = useCallback(async () => {
    setLoadingMonths(true);
    try {
      const res = await api<{ months: MonthItem[] }>("/tenures/months");
      const list = res.months || [];
      setMonths(list);

      // Default to the first month with items, or current month
      const currentMonthKey = new Date().toISOString().slice(0, 7);
      const withData = list.find((m) => m.total > 0);
      const initial = withData ? withData.month : (list.find((m) => m.month === currentMonthKey)?.month || list[0]?.month || "");
      setSelectedMonth(initial);
      if (initial && initial.includes("-")) {
        setSelectedYear(initial.split("-")[0]);
      }
    } catch (err) {
      console.error("Failed to load tenure months:", err);
    } finally {
      setLoadingMonths(false);
    }
  }, []);

  useEffect(() => {
    loadMonths();
  }, [loadMonths]);

  // Load tenures for selected month (or all months)
  const loadTenures = useCallback(async () => {
    setLoadingTenures(true);
    try {
      const params = new URLSearchParams();
      if (selectedMonth && selectedMonth !== "all") {
        params.set("month", selectedMonth);
      }
      if (search.trim()) params.set("search", search.trim());
      if (statusFilter !== "all") params.set("status", statusFilter);

      const res = await api<{ items: TenureRow[]; total: number }>(`/tenures?${params.toString()}`);
      setTenures(res.items || []);
    } catch (err) {
      console.error("Failed to load tenures:", err);
    } finally {
      setLoadingTenures(false);
    }
  }, [selectedMonth, search, statusFilter]);

  useEffect(() => {
    loadTenures();
  }, [loadTenures]);

  // Scroll active month into view when selected
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
    const currentMonthKey = new Date().toISOString().slice(0, 7);
    const yr = currentMonthKey.split("-")[0];
    setSelectedYear(yr);
    setSelectedMonth(currentMonthKey);
  }

  function formatMonthTab(monthStr: string) {
    if (!monthStr || monthStr === "all") return "All Months";
    try {
      const [y, m] = monthStr.split("-");
      const d = new Date(parseInt(y, 10), parseInt(m, 10) - 1, 1);
      return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
    } catch {
      return monthStr;
    }
  }

  function getStatusBadge(status: string, wonPremium: number | null) {
    switch (status) {
      case "hit":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[var(--rl-radius-sm)] text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200/60">
            <CheckCircle className="w-3 h-3" /> HIT {wonPremium ? `· RM ${wonPremium.toFixed(0)}` : ""}
          </span>
        );
      case "miss":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[var(--rl-radius-sm)] text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200/60">
            <XCircle className="w-3 h-3" /> MISS
          </span>
        );
      case "sent":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[var(--rl-radius-sm)] text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200/60">
            <Clock className="w-3 h-3" /> SENT
          </span>
        );
      case "comparing":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[var(--rl-radius-sm)] text-[10px] font-bold bg-amber-50 text-amber-900 border border-amber-200/80">
            COMPARING
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[var(--rl-radius-sm)] text-[10px] font-bold bg-neutral-100 text-neutral-700 border border-neutral-200/60">
            DRAFT
          </span>
        );
    }
  }

  const currentMonthKey = new Date().toISOString().slice(0, 7);

  return (
    <div className="space-y-5">
      {/* 2-Tier Year & Month Ledger Tabs Bar */}
      <div className="bg-white border border-[#e5e5ea] rounded-[var(--rl-radius)] p-3.5 shadow-2xs space-y-3">
        {/* Tier 1: Year Selector Bar */}
        <div className="flex items-center justify-between flex-wrap gap-2 pb-2.5 border-b border-[#f2f2f7]">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-[#1b1717]">
              <CalendarBlank className="w-4 h-4 text-[#454545]" />
              Year Hierarchy:
            </span>
            <div className="flex items-center gap-1 flex-wrap">
              <button
                type="button"
                onClick={() => {
                  setSelectedYear("all");
                  setSelectedMonth("all");
                }}
                className={`px-2.5 py-1 rounded-[var(--rl-radius-sm)] text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                  selectedYear === "all"
                    ? "bg-[#1b1717] text-white shadow-2xs font-semibold"
                    : "bg-[#f5f5f7] text-[#6e6e73] hover:text-[#1b1717] hover:bg-[#e5e5ea]"
                }`}
              >
                <span>All Years</span>
                {grandTotal > 0 && (
                  <span className={`px-1.5 py-0.2 rounded-[var(--rl-radius-sm)] text-[10px] font-bold ${
                    selectedYear === "all" ? "bg-white/20 text-white" : "bg-[#e5e5ea] text-[#454545]"
                  }`}>
                    {grandTotal}
                  </span>
                )}
              </button>

              {availableYears.map((yr) => {
                const yrTotal = yearGroupMap[yr]?.total || 0;
                const isSelected = selectedYear === yr;
                return (
                  <button
                    key={yr}
                    type="button"
                    onClick={() => {
                      setSelectedYear(yr);
                      const firstWithData = yearGroupMap[yr]?.months.find((m) => m.total > 0)?.month;
                      setSelectedMonth(firstWithData || yr);
                    }}
                    className={`px-2.5 py-1 rounded-[var(--rl-radius-sm)] text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                      isSelected
                        ? "bg-[#1b1717] text-white shadow-2xs font-semibold"
                        : "bg-[#f5f5f7] text-[#6e6e73] hover:text-[#1b1717] hover:bg-[#e5e5ea]"
                    }`}
                  >
                    <span>{yr}</span>
                    {yrTotal > 0 && (
                      <span className={`px-1.5 py-0.2 rounded-[var(--rl-radius-sm)] text-[10px] font-bold ${
                        isSelected ? "bg-white/20 text-white" : "bg-[#e5e5ea] text-[#454545]"
                      }`}>
                        {yrTotal}
                      </span>
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
              className="text-[11px] font-medium text-[#6e6e73] hover:text-[#1b1717] transition-colors px-2 py-0.5 rounded-[var(--rl-radius-sm)] hover:bg-[#f5f5f7] border border-transparent hover:border-[#e5e5ea] cursor-pointer"
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
                loadTenures();
              }}
              className="text-[11px] text-[#8e8e93] hover:text-[#1b1717] flex items-center gap-1 ml-1 cursor-pointer"
            >
              <ArrowsClockwise className="w-3 h-3" /> Refresh
            </button>
          </div>
        </div>

        {/* Tier 2: Sub-select Months of that Year */}
        {loadingMonths ? (
          <div className="h-9 flex items-center text-xs text-[#8e8e93]">Loading tenure timeline...</div>
        ) : (
          <div
            ref={monthScrollRef}
            className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-0.5 scroll-smooth scrollbar-thin"
          >
            {/* "All in {Year}" or "All Months" button */}
            <button
              type="button"
              onClick={() => setSelectedMonth(selectedYear === "all" ? "all" : selectedYear)}
              className={`shrink-0 min-w-max px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 cursor-pointer ${
                selectedMonth === "all" || selectedMonth === selectedYear
                  ? "bg-[#1b1717] text-white shadow-2xs"
                  : "bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
              }`}
            >
              <span>{selectedYear === "all" ? "All Months" : `All in ${selectedYear}`}</span>
              <span
                className={`px-1.5 py-0.2 rounded-[var(--rl-radius-sm)] text-[10px] font-bold ${
                  selectedMonth === "all" || selectedMonth === selectedYear
                    ? "bg-white/20 text-white"
                    : "bg-[#e5e5ea] text-[#454545]"
                }`}
              >
                {selectedYear === "all" ? grandTotal : (yearGroupMap[selectedYear]?.total || 0)}
              </span>
            </button>

            {/* Months */}
            {monthsOfYear.map((m) => {
              const isActive = selectedMonth === m.month;
              const isCurrent = m.month === currentMonthKey;
              return (
                <button
                  key={m.month}
                  type="button"
                  data-month={m.month}
                  onClick={() => setSelectedMonth(m.month)}
                  className={`shrink-0 min-w-max px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-medium whitespace-nowrap transition-all flex items-center gap-1.5 cursor-pointer ${
                    isActive
                      ? "bg-[#1b1717] text-white shadow-2xs font-semibold"
                      : "bg-[#f5f5f7] text-[#454545] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
                  } ${isCurrent && !isActive ? "ring-1 ring-[#007aff]/60 font-semibold" : ""}`}
                  title={isCurrent ? "Current active calendar month" : undefined}
                >
                  <span>{m.shortLabel}</span>
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

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <MagnifyingGlass className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search vehicle plate (e.g. JWK 9488) or client name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-9 pl-9 pr-3 rounded-[var(--rl-radius-sm)] border border-neutral-200 bg-white text-xs font-medium focus:ring-1 focus:ring-neutral-900 outline-none"
          />
        </div>

        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 px-3 rounded-[var(--rl-radius-sm)] border border-neutral-200 bg-white text-xs font-medium text-neutral-700 focus:ring-1 focus:ring-neutral-900 outline-none"
          >
            <option value="all">All Outcomes</option>
            <option value="draft">Draft</option>
            <option value="comparing">Comparing</option>
            <option value="sent">Sent to Client</option>
            <option value="hit">Hit (Won)</option>
            <option value="miss">Miss (Lost)</option>
          </select>
        </div>
      </div>

      {/* Tenures Ledger Table */}
      <div className="bg-white border border-neutral-200/90 rounded-[var(--rl-radius)] overflow-hidden shadow-2xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-neutral-50/70 border-b border-neutral-200/80 text-[11px] font-bold uppercase tracking-wider text-neutral-500">
              <tr>
                <th className="py-3 px-4">Customer &amp; Vehicle</th>
                <th className="py-3 px-4">Coverage Period</th>
                <th className="py-3 px-4">Sourced Quotes &amp; Versions</th>
                <th className="py-3 px-4">RL Generated Quotations</th>
                <th className="py-3 px-4">Status &amp; Outcome</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {loadingTenures ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-neutral-400">
                    <ArrowsClockwise className="w-5 h-5 animate-spin mx-auto mb-2 text-neutral-500" />
                    Loading month tenures...
                  </td>
                </tr>
              ) : tenures.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-neutral-400">
                    No policies found expiring in {formatMonthTab(selectedMonth)}.
                  </td>
                </tr>
              ) : (
                tenures.map((t) => (
                  <tr
                    key={t.id}
                    onClick={() => setActiveDrawerTenureId(t.id)}
                    className="hover:bg-neutral-50/60 cursor-pointer transition-colors"
                  >
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-neutral-900 text-sm flex items-center gap-1.5">
                        <Car className="w-4 h-4 text-neutral-700" />
                        {t.vehicle_no}
                      </div>
                      <div className="text-neutral-500 font-medium text-[11px] mt-0.5">{t.customer_name}</div>
                    </td>

                    <td className="py-3.5 px-4 text-neutral-600">
                      <div>
                        {new Date(t.coverage_start_date).toLocaleDateString("en-GB")} –{" "}
                        {new Date(t.coverage_end_date).toLocaleDateString("en-GB")}
                      </div>
                      <div className="text-[10px] text-neutral-400 font-semibold mt-0.5">Expiring {t.expiry_month}</div>
                    </td>

                    <td className="py-3.5 px-4">
                      {t.sourced_quotes.length === 0 ? (
                        <span className="text-neutral-400 italic">No quotes yet</span>
                      ) : (
                        <div className="flex flex-wrap gap-1.5">
                          {t.sourced_quotes.map((q) => (
                            <span
                              key={q.session_id}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[var(--rl-radius-sm)] bg-neutral-100 text-neutral-800 text-[11px] font-medium border border-neutral-200/50"
                            >
                              <span className="font-bold">{q.company}</span>
                              <span className="text-[10px] text-neutral-700 font-semibold bg-neutral-200/80 px-1 rounded-[var(--rl-radius-sm)]">
                                v{q.version}
                              </span>
                              {q.total_payable && <span className="text-neutral-500 text-[10px]">RM {q.total_payable}</span>}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>

                    <td className="py-3.5 px-4">
                      {t.generated_quotations.length === 0 ? (
                        <span className="text-neutral-400 italic">—</span>
                      ) : (
                        <div className="flex flex-wrap gap-1.5">
                          {t.generated_quotations.map((g) => (
                            <span
                              key={g.session_id}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[var(--rl-radius-sm)] bg-emerald-50 border border-emerald-200/60 text-emerald-900 text-[11px] font-mono font-bold"
                            >
                              <FilePdf className="w-3 h-3 text-red-600" />
                              {g.quotation_ref}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>

                    <td className="py-3.5 px-4">
                      {getStatusBadge(t.status, t.won_premium)}
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveDrawerTenureId(t.id);
                        }}
                        className="h-7 text-xs font-medium"
                      >
                        Timeline <ArrowRight className="w-3 h-3 ml-1" />
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Slide-out Interactive Tenure Timeline Drawer */}
      {activeDrawerTenureId && (
        <TenureTimelineDrawer
          tenureId={activeDrawerTenureId}
          isOpen={Boolean(activeDrawerTenureId)}
          onClose={() => setActiveDrawerTenureId(null)}
          onRefresh={loadTenures}
        />
      )}
    </div>
  );
}
