"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  TrendUp,
  CurrencyDollar,
  CheckCircle,
  XCircle,
  Clock,
  PaperPlaneRight,
  Buildings,
  WarningCircle,
  ChartPie,
  ArrowsClockwise,
  CalendarCheck,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface MonthlyBreakdownItem {
  month_key: string;
  month_label: string;
  total_quotations: number;
  hits_count: number;
  misses_count: number;
  pending_count: number;
  hit_rate_percent: number;
  won_premium_total: number;
  lost_premium_total: number;
}

interface AnalyticsResponse {
  total_quotations: number;
  hits_count: number;
  misses_count: number;
  superseded_count?: number;
  pending_count: number;
  hit_rate_percent: number;
  sent_to_client_count: number;
  upcoming_renewals_count?: number;
  won_premium_total: number;
  lost_premium_total: number;
  miss_reasons: Record<string, number>;
  company_hits: Record<string, number>;
  monthly_breakdown?: MonthlyBreakdownItem[];
}

export function InsightsAnalyticsView() {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedMonth, setSelectedMonth] = useState<string>("all");

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<AnalyticsResponse>("/insights/analytics");
      setData(res);
    } catch (err) {
      console.error("Failed to load insights analytics:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const formatRM = (val: number) =>
    "RM " +
    val.toLocaleString("en-MY", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  // Calculate current active metrics based on selected month or all-time
  const activeMetrics = useMemo(() => {
    if (!data) return null;
    if (selectedMonth === "all" || !data.monthly_breakdown) {
      return {
        total: data.total_quotations,
        hits: data.hits_count,
        misses: data.misses_count,
        pending: data.pending_count,
        hitRate: data.hit_rate_percent,
        wonPremium: data.won_premium_total,
        lostPremium: data.lost_premium_total,
        label: "All-Time Performance",
      };
    }
    const item = data.monthly_breakdown.find((m) => m.month_key === selectedMonth);
    if (!item) {
      return {
        total: data.total_quotations,
        hits: data.hits_count,
        misses: data.misses_count,
        pending: data.pending_count,
        hitRate: data.hit_rate_percent,
        wonPremium: data.won_premium_total,
        lostPremium: data.lost_premium_total,
        label: "All-Time Performance",
      };
    }
    return {
      total: item.total_quotations,
      hits: item.hits_count,
      misses: item.misses_count,
      pending: item.pending_count,
      hitRate: item.hit_rate_percent,
      wonPremium: item.won_premium_total,
      lostPremium: item.lost_premium_total,
      label: `${item.month_label} Performance`,
    };
  }, [data, selectedMonth]);

  if (loading) {
    return <div className="p-12 text-center text-xs text-neutral-400">Loading conversion analytics...</div>;
  }

  if (!data || !activeMetrics) {
    return (
      <div className="p-12 text-center bg-white rounded-lg border border-neutral-200">
        <p className="text-sm text-neutral-600">Analytics data currently unavailable.</p>
      </div>
    );
  }

  const totalMisses = data.misses_count || 1;
  const sortedMissReasons = Object.entries(data.miss_reasons || {}).sort((a, b) => b[1] - a[1]);
  const sortedCompanies = Object.entries(data.company_hits || {}).sort((a, b) => b[1] - a[1]);
  const monthlyList = data.monthly_breakdown || [];

  return (
    <div className="space-y-6">
      {/* Top Controls with Monthly Selector */}
      <div className="bg-white border border-neutral-200/90 rounded-lg p-4 shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-neutral-900 tracking-tight flex items-center gap-2">
            <CalendarCheck size={18} className="text-[#1b1717]" />
            <span>Monthly Quotation Performance &amp; Hit Rates</span>
          </h2>
          <p className="text-xs text-neutral-500">
            Real-time pipeline metrics and conversion rate tracking broken down month-by-month.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Month Selector */}
          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="text-xs h-8 border border-neutral-200 rounded-md px-3 bg-white font-medium text-neutral-800 shadow-2xs focus:ring-1 focus:ring-neutral-900"
          >
            <option value="all">All Months (Cumulative)</option>
            {monthlyList.map((m) => (
              <option key={m.month_key} value={m.month_key}>
                {m.month_label} ({m.total_quotations} quotes · {m.hit_rate_percent}% Hit)
              </option>
            ))}
          </select>

          <Button
            size="sm"
            variant="secondary"
            onClick={() => fetchAnalytics()}
            className="text-xs gap-1.5 h-8 border-neutral-200 text-neutral-700 hover:bg-neutral-50"
            title="Refresh metrics"
          >
            <ArrowsClockwise size={13} />
            Refresh
          </Button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Hit Rate % */}
        <div className="bg-white p-4 rounded-lg border border-neutral-200/80 shadow-xs space-y-2">
          <div className="flex items-center justify-between text-neutral-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Hit Rate</span>
            <div className="w-7 h-7 rounded bg-emerald-50 text-emerald-700 flex items-center justify-center">
              <TrendUp size={16} weight="bold" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-neutral-900 tracking-tight">
              {activeMetrics.hitRate}%
            </div>
            <p className="text-[11px] text-neutral-500 mt-0.5 font-medium">
              {activeMetrics.hits} won out of {activeMetrics.hits + activeMetrics.misses} closed quotes ({activeMetrics.pending} pending)
            </p>
          </div>
        </div>

        {/* Won Premium */}
        <div className="bg-white p-4 rounded-lg border border-neutral-200/80 shadow-xs space-y-2">
          <div className="flex items-center justify-between text-neutral-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Won Premium</span>
            <div className="w-7 h-7 rounded bg-emerald-50 text-emerald-700 flex items-center justify-center">
              <CurrencyDollar size={16} weight="bold" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-neutral-900 tracking-tight">
              {formatRM(activeMetrics.wonPremium)}
            </div>
            <p className="text-[11px] text-emerald-700 font-medium mt-0.5">
              Converted revenue for {activeMetrics.label}
            </p>
          </div>
        </div>

        {/* Unconverted Deals (Miss) */}
        <div className="bg-white p-4 rounded-lg border border-neutral-200/80 shadow-xs space-y-2">
          <div className="flex items-center justify-between text-neutral-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Unconverted (Miss)</span>
            <div className="w-7 h-7 rounded bg-rose-50 text-rose-700 flex items-center justify-center">
              <XCircle size={16} weight="bold" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-neutral-900 tracking-tight">
              {activeMetrics.misses}
            </div>
            <p className="text-[11px] text-neutral-500 font-medium mt-0.5">
              Quotations not taken up by clients
            </p>
          </div>
        </div>

        {/* Upcoming Policy Renewals (9-Month / 90-Day Window) */}
        <div className="bg-white p-4 rounded-lg border border-neutral-200/80 shadow-xs space-y-2">
          <div className="flex items-center justify-between text-neutral-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Upcoming Renewals</span>
            <div className="w-7 h-7 rounded bg-amber-50 text-amber-700 flex items-center justify-center">
              <CalendarCheck size={16} weight="bold" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-neutral-900 tracking-tight">
              {data.upcoming_renewals_count ?? 0}
            </div>
            <p className="text-[11px] text-amber-700 font-medium mt-0.5">
              Policies expiring in next 90 days
            </p>
          </div>
        </div>
      </div>

      {/* Monthly Performance History Table */}
      {monthlyList.length > 0 && (
        <div className="bg-white rounded-lg border border-neutral-200/90 shadow-xs overflow-hidden">
          <div className="p-4 border-b border-neutral-100 bg-neutral-50/60 flex items-center justify-between">
            <h3 className="text-xs font-bold text-neutral-900 uppercase tracking-wider flex items-center gap-2">
              <CalendarCheck size={16} className="text-neutral-700" />
              <span>Month-by-Month Quotation Tracking &amp; Conversion Ledger</span>
            </h3>
            <span className="text-xs text-neutral-500">Click row to filter metrics</span>
          </div>

          <table className="w-full text-left text-xs">
            <thead className="bg-neutral-50 text-neutral-600 border-b border-neutral-200 font-semibold text-[11px]">
              <tr>
                <th className="p-3">Month</th>
                <th className="p-3">Total Done</th>
                <th className="p-3">Passed / Won (Hit)</th>
                <th className="p-3">Missed (Lost)</th>
                <th className="p-3">Pending</th>
                <th className="p-3">Hit Rate %</th>
                <th className="p-3 text-right">Won Premium (RM)</th>
                <th className="p-3 text-right">Lost Premium (RM)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {monthlyList.map((m) => {
                const isSelected = selectedMonth === m.month_key;

                return (
                  <tr
                    key={m.month_key}
                    onClick={() => setSelectedMonth(isSelected ? "all" : m.month_key)}
                    className={`cursor-pointer transition-colors ${
                      isSelected ? "bg-neutral-100/90 font-medium" : "hover:bg-neutral-50/80"
                    }`}
                  >
                    <td className="p-3 font-bold text-neutral-900">{m.month_label}</td>
                    <td className="p-3 font-semibold text-neutral-800">{m.total_quotations}</td>
                    <td className="p-3 text-emerald-700 font-semibold">
                      <span className="inline-flex items-center gap-1">
                        <CheckCircle size={13} weight="bold" />
                        {m.hits_count}
                      </span>
                    </td>
                    <td className="p-3 text-rose-700 font-semibold">
                      <span className="inline-flex items-center gap-1">
                        <XCircle size={13} weight="bold" />
                        {m.misses_count}
                      </span>
                    </td>
                    <td className="p-3 text-neutral-500">{m.pending_count}</td>
                    <td className="p-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[11px] font-bold border ${
                          m.hit_rate_percent >= 50
                            ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                            : m.hit_rate_percent > 0
                            ? "bg-amber-50 text-amber-800 border-amber-200"
                            : "bg-neutral-100 text-neutral-600 border-neutral-200"
                        }`}
                      >
                        {m.hit_rate_percent}%
                      </span>
                    </td>
                    <td className="p-3 text-right font-semibold text-emerald-800">{formatRM(m.won_premium_total)}</td>
                    <td className="p-3 text-right font-semibold text-rose-800">{formatRM(m.lost_premium_total)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Breakdown Section: Loss Reasons & Insurer Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Loss Reasons Breakdown */}
        <div className="bg-white p-5 rounded-lg border border-neutral-200/80 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-neutral-100 pb-3">
            <div className="flex items-center gap-2">
              <WarningCircle size={17} weight="bold" className="text-rose-600" />
              <h3 className="text-xs font-semibold text-neutral-900 uppercase tracking-wider">
                Loss Reasons Analysis
              </h3>
            </div>
            <span className="text-xs text-neutral-400">{data.misses_count} total misses</span>
          </div>

          {sortedMissReasons.length === 0 ? (
            <p className="text-xs text-neutral-400 py-6 text-center">No loss reasons recorded yet.</p>
          ) : (
            <div className="space-y-3">
              {sortedMissReasons.map(([reason, count]) => {
                const pct = Math.round((count / totalMisses) * 100);
                return (
                  <div key={reason} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-neutral-800">{reason}</span>
                      <span className="text-neutral-500 font-mono">
                        {count} ({pct}%)
                      </span>
                    </div>
                    <div className="w-full bg-neutral-100 h-2 rounded-full overflow-hidden">
                      <div
                        className="bg-rose-500 h-full rounded-full transition-all duration-300"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Insurer Hit Performance */}
        <div className="bg-white p-5 rounded-lg border border-neutral-200/80 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-neutral-100 pb-3">
            <div className="flex items-center gap-2">
              <Buildings size={17} weight="bold" className="text-neutral-800" />
              <h3 className="text-xs font-semibold text-neutral-900 uppercase tracking-wider">
                Top Converted Insurers
              </h3>
            </div>
            <span className="text-xs text-neutral-400">{data.hits_count} total wins</span>
          </div>

          {sortedCompanies.length === 0 ? (
            <p className="text-xs text-neutral-400 py-6 text-center">No converted quotations recorded yet.</p>
          ) : (
            <div className="space-y-3">
              {sortedCompanies.map(([company, count]) => {
                const pct = data.hits_count > 0 ? Math.round((count / data.hits_count) * 100) : 0;
                return (
                  <div key={company} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-neutral-800">{company || "Unassigned"}</span>
                      <span className="text-neutral-500 font-mono">
                        {count} won ({pct}%)
                      </span>
                    </div>
                    <div className="w-full bg-neutral-100 h-2 rounded-full overflow-hidden">
                      <div
                        className="bg-emerald-500 h-full rounded-full transition-all duration-300"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
