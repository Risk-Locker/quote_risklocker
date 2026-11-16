"use client";

import { useEffect, useState, useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import {
  ArrowsClockwise,
  Calendar,
  ChartBar,
  ChartLineUp,
  CheckCircle,
  Clock,
  Hourglass,
  MagnifyingGlass,
  Sparkle,
  WarningCircle,
} from "@phosphor-icons/react";

export interface TimelineLogItem {
  id: string;
  timestamp: string;
  iso_timestamp?: string;
  account_id: string;
  api_key_masked: string;
  model: string;
  endpoint_slot?: string;
  purpose: string;
  status_code: number;
  is_success: boolean;
  prompt_tokens: number;
  candidate_tokens: number;
  total_tokens: number;
  latency_ms: number;
  error_message?: string;
  local_date: string;
}

export interface MinuteBucket {
  minute: string;
  calls: number;
  total_tokens: number;
  prompt_tokens: number;
  candidate_tokens: number;
}

export interface DailyCycleHistory {
  date: string;
  calls: number;
  tokens: number;
  errors: number;
}

export interface FleetTimelineResponse {
  current_cycle: {
    pt_date: string;
    local_now_myt: string;
    next_reset_pt: string;
    next_reset_myt: string;
    seconds_until_reset: number;
    cycle_reset_display: string;
  };
  timeline: TimelineLogItem[];
  minute_buckets: MinuteBucket[];
  daily_history: DailyCycleHistory[];
}

export function GeminiTimelineCalendar() {
  const [data, setData] = useState<FleetTimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [filterModel, setFilterModel] = useState<string>("all");
  const [secondsRemaining, setSecondsRemaining] = useState<number>(0);

  async function fetchTimeline() {
    setLoading(true);
    setError("");
    try {
      const res = await api<FleetTimelineResponse>("/settings/gemini/timeline");
      if (res) {
        setData(res);
        setSecondsRemaining(res.current_cycle.seconds_until_reset || 0);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load timeline data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchTimeline();
    const interval = setInterval(fetchTimeline, 30_000); // refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // Live countdown timer ticking every second
  useEffect(() => {
    if (secondsRemaining <= 0) return;
    const timer = setInterval(() => {
      setSecondsRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [secondsRemaining]);

  const countdownFormatted = useMemo(() => {
    const hours = Math.floor(secondsRemaining / 3600);
    const minutes = Math.floor((secondsRemaining % 3600) / 60);
    const seconds = secondsRemaining % 60;
    return `${hours}h ${minutes}m ${seconds}s`;
  }, [secondsRemaining]);

  const filteredLogs = useMemo(() => {
    if (!data?.timeline) return [];
    return data.timeline.filter((item) => {
      const matchesSearch =
        searchTerm === "" ||
        item.account_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.purpose.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.model.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (item.endpoint_slot && item.endpoint_slot.toLowerCase().includes(searchTerm.toLowerCase()));
      const matchesModel = filterModel === "all" || item.model === filterModel;
      return matchesSearch && matchesModel;
    });
  }, [data?.timeline, searchTerm, filterModel]);

  const maxTokensInMinutes = useMemo(() => {
    if (!data?.minute_buckets || data.minute_buckets.length === 0) return 1;
    return Math.max(...data.minute_buckets.map((b) => b.total_tokens), 10_000);
  }, [data?.minute_buckets]);

  return (
    <Card className="overflow-hidden border border-[var(--rl-border)] shadow-xs">
      {/* Header with Pacific Time Quota Reset Banner */}
      <div className="border-b border-[var(--rl-border)] bg-gray-50/60 p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <ChartLineUp size={20} weight="bold" className="text-blue-600" />
              <h2 className="text-base font-bold text-gray-900">
                AI Fleet Real-Time Monitor & Pacific Quota Cycle
              </h2>
              <Badge variant="info" className="bg-blue-50 text-blue-700 border-blue-200 text-xs">
                Google PT Sync
              </Badge>
            </div>
            <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
              Monitors RPD, RPM, and TPM limits aligned strictly to Google AI Studio's 12:00 AM Pacific Time daily rollover (4:00 PM MYT Standard Time / 3:00 PM MYT Daylight Time).
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="secondary"
              size="sm"
              onClick={fetchTimeline}
              disabled={loading}
              className="gap-1.5 text-xs h-8 cursor-pointer"
            >
              <ArrowsClockwise size={14} className={loading ? "animate-spin" : ""} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Pacific Time Cycle Countdown Card */}
        {data?.current_cycle && (
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-3 flex items-center justify-between">
              <div>
                <span className="text-[11px] font-medium text-blue-800 uppercase tracking-wider block">
                  Active Quota Cycle (PT)
                </span>
                <span className="text-sm font-bold text-gray-900">
                  {data.current_cycle.pt_date} (Pacific Time)
                </span>
              </div>
              <Calendar size={24} weight="duotone" className="text-blue-500 shrink-0" />
            </div>

            <div className="rounded-lg border border-amber-100 bg-amber-50/50 p-3 flex items-center justify-between">
              <div>
                <span className="text-[11px] font-medium text-amber-800 uppercase tracking-wider block">
                  Next Quota Reset
                </span>
                <span className="text-sm font-bold text-gray-900">
                  {new Date(data.current_cycle.next_reset_myt).toLocaleTimeString("en-MY", {
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: true,
                  })}{" "}
                  MYT
                </span>
              </div>
              <Clock size={24} weight="duotone" className="text-amber-500 shrink-0" />
            </div>

            <div className="rounded-lg border border-emerald-100 bg-emerald-50/50 p-3 flex items-center justify-between">
              <div>
                <span className="text-[11px] font-medium text-emerald-800 uppercase tracking-wider block">
                  Reset Countdown
                </span>
                <span className="text-sm font-mono font-bold text-emerald-700">
                  {countdownFormatted}
                </span>
              </div>
              <Hourglass size={24} weight="duotone" className="text-emerald-500 shrink-0" />
            </div>
          </div>
        )}
      </div>

      <div className="p-5 space-y-6">
        {/* Minute-Level Token Activity Graph (Last 60 Minutes) */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-900 flex items-center gap-1.5">
              <Sparkle size={14} className="text-blue-600" />
              Minute-by-Minute Token Intensity & Request Rate (Past 60 Minutes)
            </span>
            <span className="text-[11px] text-[var(--rl-text-muted)]">
              Max TPM ceiling: 200,000 tokens/min
            </span>
          </div>

          <div className="h-28 w-full bg-gray-50/70 border border-gray-100 rounded-lg p-2.5 flex items-end gap-1 overflow-x-auto">
            {data?.minute_buckets.map((b, idx) => {
              const heightPct = Math.min(100, Math.max(8, (b.total_tokens / maxTokensInMinutes) * 100));
              const hasCalls = b.calls > 0;
              return (
                <div
                  key={idx}
                  className="flex-1 min-w-[10px] flex flex-col items-center justify-end h-full group relative cursor-pointer"
                >
                  <div
                    style={{ height: hasCalls ? `${heightPct}%` : "4%" }}
                    className={`w-full rounded-t-sm transition-all duration-300 ${
                      hasCalls
                        ? b.total_tokens > 150_000
                          ? "bg-amber-500 hover:bg-amber-600"
                          : "bg-blue-500 hover:bg-blue-600"
                        : "bg-gray-200 hover:bg-gray-300"
                    }`}
                  />
                  {/* Tooltip on hover */}
                  <div className="absolute bottom-full mb-1 hidden group-hover:flex flex-col items-center z-30 pointer-events-none">
                    <div className="bg-gray-900 text-white text-[10px] rounded px-2 py-1 whitespace-nowrap shadow-lg">
                      <div className="font-bold">{b.minute} MYT</div>
                      <div>{b.calls} call(s)</div>
                      <div>{b.total_tokens.toLocaleString()} tokens</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-[10px] text-gray-400 mt-1 px-1">
            <span>60 mins ago</span>
            <span>30 mins ago</span>
            <span>Current Minute</span>
          </div>
        </div>

        {/* Recent Daily Cycle History (Calendar Strip) */}
        {data?.daily_history && data.daily_history.length > 0 && (
          <div>
            <span className="text-xs font-semibold text-gray-900 block mb-2">
              Recent Quota Cycle Daily History
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
              {data.daily_history.slice(0, 7).map((d) => (
                <div
                  key={d.date}
                  className="rounded border border-gray-200/80 bg-white p-2 text-center text-xs hover:border-blue-300 transition-colors"
                >
                  <span className="text-[10px] font-mono text-gray-500 block">{d.date}</span>
                  <span className="font-bold text-gray-900 text-sm block my-0.5">{d.calls} calls</span>
                  <span className="text-[10px] text-blue-600 font-medium block">
                    {(d.tokens / 1000).toFixed(1)}k tokens
                  </span>
                  {d.errors > 0 && (
                    <span className="text-[9px] text-rose-500 block mt-0.5">{d.errors} error(s)</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Live Call Inspection Table */}
        <div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
            <span className="text-xs font-semibold text-gray-900">
              Live Call Inspection Ledger ({filteredLogs.length} recent calls)
            </span>

            <div className="flex items-center gap-2">
              <div className="relative w-48">
                <MagnifyingGlass size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Search calls..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="text-xs pl-7 h-7.5"
                />
              </div>

              <select
                value={filterModel}
                onChange={(e) => setFilterModel(e.target.value)}
                className="text-xs border border-gray-200 rounded px-2 h-7.5 bg-white text-gray-700 cursor-pointer"
              >
                <option value="all">All Models</option>
                <option value="gemini-3.1-flash-lite">gemini-3.1-flash-lite</option>
                <option value="gemini-3.5-flash-lite">gemini-3.5-flash-lite</option>
              </select>
            </div>
          </div>

          <div className="border border-[var(--rl-border)] rounded-lg overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 text-[11px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider border-b border-[var(--rl-border)]">
                <tr>
                  <th className="py-2 px-3">Time (MYT)</th>
                  <th className="py-2 px-3">Purpose / Action</th>
                  <th className="py-2 px-3">Model</th>
                  <th className="py-2 px-3">Slot / Key</th>
                  <th className="py-2 px-3 text-right">Tokens</th>
                  <th className="py-2 px-3 text-right">Latency</th>
                  <th className="py-2 px-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 font-mono text-[11px]">
                {filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-gray-400 font-sans text-xs">
                      No calls recorded yet in this cycle. Upload a quotation to see live metrics.
                    </td>
                  </tr>
                ) : (
                  filteredLogs.slice(0, 25).map((log) => (
                    <tr key={log.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="py-2 px-3 text-gray-600 whitespace-nowrap">{log.timestamp}</td>
                      <td className="py-2 px-3 font-sans font-medium text-gray-900">{log.purpose}</td>
                      <td className="py-2 px-3 text-blue-600 whitespace-nowrap">{log.model}</td>
                      <td className="py-2 px-3 text-gray-500 whitespace-nowrap">
                        {log.endpoint_slot || log.account_id}
                      </td>
                      <td className="py-2 px-3 text-right font-bold text-gray-900">
                        {log.total_tokens.toLocaleString()}
                      </td>
                      <td className="py-2 px-3 text-right text-gray-500">{log.latency_ms}ms</td>
                      <td className="py-2 px-3 text-center">
                        {log.is_success ? (
                          <Badge variant="success" className="text-[10px] py-0">
                            {log.status_code} OK
                          </Badge>
                        ) : (
                          <Badge variant="danger" className="text-[10px] py-0">
                            {log.status_code || "ERR"}
                          </Badge>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Card>
  );
}
