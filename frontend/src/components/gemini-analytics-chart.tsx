"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { ChartBar, Sparkle } from "@phosphor-icons/react";

export type AnalyticsTimeRange = "today" | "last-1-day" | "last-7-days" | "last-28-days";

export interface AnalyticsTableRow {
  account_id: string;
  masked_key?: string;
  model: string;
  category: string;
  call_count: number;
  total_tokens: number;
  peak_rpm: number;
  rpm_limit: number;
  peak_tpm: number;
  tpm_limit: number;
  rpd_limit: number;
  status: string;
}

interface AnalyticsResponse {
  time_range: AnalyticsTimeRange;
  summary: {
    total_calls: number;
    total_tokens: number;
    models_active: number;
  };
  table: AnalyticsTableRow[];
}

function formatTokens(num: number): string {
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
  return String(num);
}

function formatModelName(model: string): string {
  if (model === "gemini-3.1-flash-lite") return "Gemini 3.1 Flash Lite";
  if (model === "gemini-3.5-flash-lite") return "Gemini 3.5 Flash Lite";
  return model;
}

export function GeminiAnalyticsChart() {
  const [timeRange, setTimeRange] = useState<AnalyticsTimeRange>("today");
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchAnalytics(range: AnalyticsTimeRange) {
    setLoading(true);
    setError("");
    try {
      const res = await api<AnalyticsResponse>(`/settings/gemini/analytics?time_range=${range}`);
      if (res) {
        setData(res);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Google AI Studio rate limit analytics.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchAnalytics(timeRange);
  }, [timeRange]);

  const ranges: { label: string; value: AnalyticsTimeRange }[] = [
    { label: "Today", value: "today" },
    { label: "Last 1 Day", value: "last-1-day" },
    { label: "Last 7 Days", value: "last-7-days" },
    { label: "Last 28 Days", value: "last-28-days" },
  ];

  return (
    <Card className="p-5 border border-[var(--rl-border)] bg-white shadow-xs grid gap-4">
      {/* Header and Time-Range Toggles */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-3">
        <div>
          <h2 className="text-sm font-bold text-[var(--rl-text-strong)] flex items-center gap-2">
            <ChartBar size={16} weight="fill" className="text-indigo-600" />
            Google AI Studio Rate Limit Parity & Peak Fleet Analytics
          </h2>
          <p className="text-xs text-[var(--rl-text-muted)] mt-0.5">
            Real-time sliding metrics queried directly from persisted Google Generative Language call logs.
          </p>
        </div>

        {/* Time-Range Toggle Pills */}
        <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)]">
          {ranges.map((r) => (
            <Button
              key={r.value}
              type="button"
              variant={timeRange === r.value ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setTimeRange(r.value)}
              className={`text-xs px-2.5 py-1 h-7 rounded-[var(--rl-radius-sm)] font-medium transition-colors ${
                timeRange === r.value
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs font-semibold"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              {r.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Summary KPI Counters */}
      {data?.summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div className="p-3 rounded-[var(--rl-radius-sm)] bg-[var(--rl-bg)] border border-[var(--rl-border)]">
            <span className="text-[11px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider block">
              Period API Calls
            </span>
            <div className="mt-1 text-xl font-bold font-mono text-[var(--rl-text-strong)]">
              {data.summary.total_calls.toLocaleString()}
            </div>
          </div>

          <div className="p-3 rounded-[var(--rl-radius-sm)] bg-[var(--rl-bg)] border border-[var(--rl-border)]">
            <span className="text-[11px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider block">
              Tokens Consumed
            </span>
            <div className="mt-1 text-xl font-bold font-mono text-indigo-700">
              {formatTokens(data.summary.total_tokens)}
            </div>
          </div>

          <div className="p-3 rounded-[var(--rl-radius-sm)] bg-[var(--rl-bg)] border border-[var(--rl-border)] col-span-2 sm:col-span-1">
            <span className="text-[11px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider block">
              Fleet Protection Status
            </span>
            <div className="mt-1 flex items-center gap-1.5 text-xs font-semibold text-emerald-700">
              <Sparkle size={14} weight="fill" className="text-emerald-600" />
              <span>13 RPM / 200k TPM / 480 RPD Enforced</span>
            </div>
          </div>
        </div>
      )}

      {error ? (
        <div className="text-xs text-[var(--rl-red)] bg-red-50 p-2.5 rounded-[var(--rl-radius-sm)] border border-red-200">
          {error}
        </div>
      ) : null}

      {/* Google AI Studio Parity Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-muted)] font-semibold">
              <th className="py-2.5 px-3">Model</th>
              <th className="py-2.5 px-3">Category</th>
              <th className="py-2.5 px-3">RPM (Peak / Limit)</th>
              <th className="py-2.5 px-3">TPM (Peak / Limit)</th>
              <th className="py-2.5 px-3">RPD (Used / Limit)</th>
              <th className="py-2.5 px-3 text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--rl-border)]">
            {loading ? (
              <tr>
                <td colSpan={6} className="py-6 text-center text-[var(--rl-text-muted)]">
                  Loading analytics...
                </td>
              </tr>
            ) : !data?.table || data.table.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-6 text-center text-[var(--rl-text-muted)]">
                  No API calls recorded in this time period.
                </td>
              </tr>
            ) : (
              data.table.map((row, idx) => {
                const isOverRpm = row.peak_rpm >= row.rpm_limit;
                const isOverTpm = row.peak_tpm >= row.tpm_limit;

                return (
                  <tr key={`${row.account_id}-${row.model}-${idx}`} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-3">
                      <div>
                        <div className="font-semibold text-[var(--rl-text-strong)]">
                          {formatModelName(row.model)}
                        </div>
                        <div className="text-[10px] text-[var(--rl-text-muted)] font-mono">
                          {row.masked_key ? `Key: ${row.masked_key}` : row.account_id}
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-3 text-[var(--rl-text-muted)]">
                      {row.category}
                    </td>

                    <td className="py-3 px-3 font-mono">
                      <div className="flex items-center gap-1.5">
                        <span className={isOverRpm ? "text-rose-600 font-bold" : "text-[var(--rl-text-strong)]"}>
                          {row.peak_rpm} / {row.rpm_limit}
                        </span>
                        {isOverRpm && (
                          <Badge variant="danger" className="text-[9px] px-1 py-0">
                            Peak Limit
                          </Badge>
                        )}
                      </div>
                    </td>

                    <td className="py-3 px-3 font-mono">
                      <span className={isOverTpm ? "text-rose-600 font-bold" : "text-[var(--rl-text-strong)]"}>
                        {formatTokens(row.peak_tpm)} / {formatTokens(row.tpm_limit)}
                      </span>
                    </td>

                    <td className="py-3 px-3">
                      <div className="w-32">
                        <div className="flex justify-between text-[10px] text-gray-600 font-mono mb-1">
                          <span>{row.call_count} / {row.rpd_limit}</span>
                          <span className="text-[10px] text-gray-500">
                            {row.rpd_limit > 0 ? Math.min(100, Math.round((row.call_count / row.rpd_limit) * 100)) : 0}%
                          </span>
                        </div>
                        <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-300 ${
                              (row.call_count / row.rpd_limit) >= 0.9
                                ? "bg-rose-500"
                                : (row.call_count / row.rpd_limit) >= 0.7
                                ? "bg-amber-500"
                                : "bg-emerald-500"
                            }`}
                            style={{
                              width: `${row.rpd_limit > 0 ? Math.min(100, Math.round((row.call_count / row.rpd_limit) * 100)) : 0}%`,
                            }}
                          />
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-3 text-right">
                      {row.call_count >= row.rpd_limit ? (
                        <Badge variant="danger">Exhausted</Badge>
                      ) : (row.call_count / row.rpd_limit) >= 0.8 ? (
                        <Badge variant="warning">High Usage</Badge>
                      ) : (
                        <Badge variant="success">Healthy</Badge>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

