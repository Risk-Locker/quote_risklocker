"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  ArrowsInSimple,
  ArrowsOutSimple,
  Check,
  ClockCountdown,
  Copy,
  Pulse,
  TerminalWindow,
  WarningCircle,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

interface FleetAssignment {
  filename?: string | null;
  purpose?: string | null;
  job_id?: string | null;
  upload_run_id?: string | null;
  elapsed_sec?: number;
}

interface FleetLane {
  lane_id: string;
  account_id: string;
  account_label: string;
  api_key_masked?: string | null;
  model: string;
  status: string;
  rpm_used: number;
  rpm_limit: number;
  tpm_used: number;
  tpm_limit: number;
  rpd_used: number;
  rpd_limit: number;
  in_flight_count: number;
  active_assignments?: FleetAssignment[];
  cooling_remaining_seconds?: number;
  last_latency_ms?: number;
  last_error?: string | null;
}

interface FleetEvent {
  id: string;
  created_at?: string | null;
  level: string;
  event_type: string;
  lane_id?: string | null;
  model?: string | null;
  filename?: string | null;
  message: string;
}

interface FleetTelemetryResponse {
  lanes: FleetLane[];
  active_lanes_count: number;
  total_lanes_count: number;
  queue_summary: {
    queued: number;
    processing: number;
    paused_quota: number;
    paused_user: number;
    completed: number;
    failed: number;
  };
  estimated_remaining_seconds: number;
  cadence_mode: string;
  avg_latency_ms: number;
  next_pt_reset_utc?: string;
  seconds_until_pt_reset?: number;
  events: FleetEvent[];
}

function formatDuration(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rem = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${rem.toString().padStart(2, "0")}s`;
  return `${rem}s`;
}

function laneStatusBadge(lane: FleetLane): { label: string; variant: "default" | "success" | "warning" | "danger" | "info" } {
  if (lane.status === "in_flight" || lane.in_flight_count > 0) return { label: "In-Flight", variant: "default" };
  if (lane.status === "ready") return { label: "Ready", variant: "success" };
  if (lane.status === "cooling_429") {
    return { label: `Cooling ${Math.ceil(lane.cooling_remaining_seconds || 0)}s`, variant: "warning" };
  }
  if (lane.status === "cooling_err") {
    return { label: `Cooldown ${Math.ceil(lane.cooling_remaining_seconds || 0)}s`, variant: "warning" };
  }
  if (lane.status === "exhausted_rpd") return { label: "Daily Limit", variant: "danger" };
  if (lane.status === "quarantined_auth") return { label: "Auth Blocked", variant: "danger" };
  if (lane.status === "paused") return { label: "Paused", variant: "info" };
  return { label: lane.status, variant: "info" };
}

interface LiveFleetInspectorProps {
  uploadRunId?: string | null;
  className?: string;
}

export function LiveFleetInspector({ uploadRunId, className = "" }: LiveFleetInspectorProps) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [enlarged, setEnlarged] = useState(false);
  const [data, setData] = useState<FleetTelemetryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logFilter, setLogFilter] = useState<"all" | "assigned" | "warn" | "error">("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);
  const logBoxRef = useRef<HTMLDivElement | null>(null);

  const fetchTelemetry = useCallback(async () => {
    try {
      const qs = new URLSearchParams({ limit: "200" });
      if (uploadRunId) qs.set("upload_run_id", uploadRunId);
      const res = await api<FleetTelemetryResponse>(`/settings/gemini/fleet-telemetry?${qs.toString()}`);
      setData(res);
      setError(null);
    } catch (err: any) {
      setError(err?.message || "Failed to load fleet telemetry.");
    } finally {
      setLoading(false);
    }
  }, [uploadRunId]);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    void fetchTelemetry();
    const timer = window.setInterval(() => {
      void fetchTelemetry();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [open, fetchTelemetry]);

  const filteredEvents = useMemo(() => {
    const list = data?.events || [];
    if (logFilter === "all") return list;
    if (logFilter === "assigned") return list.filter((e) => e.event_type === "assigned" || e.event_type === "success" || e.event_type === "proof_pass");
    if (logFilter === "warn") return list.filter((e) => e.level === "warn" || e.event_type.includes("429") || e.event_type === "paused_quota");
    return list.filter((e) => e.level === "error" || e.event_type === "quarantine_auth");
  }, [data?.events, logFilter]);

  useEffect(() => {
    if (open && autoScroll && logBoxRef.current) {
      logBoxRef.current.scrollTop = 0;
    }
  }, [filteredEvents, open, autoScroll]);

  async function handleCopyLogs() {
    const lines = filteredEvents.map((ev) => {
      const ts = ev.created_at ? new Date(ev.created_at).toLocaleTimeString("en-GB", { hour12: false }) : "--:--:--";
      return `[${ts}] [${ev.level.toUpperCase()}] [${ev.event_type}] ${ev.lane_id ? `(${ev.lane_id}) ` : ""}${ev.message}`;
    });
    const text = lines.length > 0 ? lines.join("\n") : "No fleet events recorded yet.";
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast(`Copied ${lines.length} fleet log line(s).`, "success");
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      toast("Could not access clipboard. Select log text manually.", "error");
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="Inspect live AI fleet routing, ETA, and logs"
        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-[var(--rl-radius-sm)] text-[11px] font-medium text-[var(--rl-text-muted)]/70 hover:text-[var(--rl-text-strong)] hover:bg-neutral-100/80 transition-colors cursor-pointer ${className}`}
      >
        <span className="size-1.5 rounded-full bg-neutral-400/80" />
        <TerminalWindow size={12} weight="regular" />
        <span>Fleet</span>
      </button>

      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="AI Fleet Telemetry & Lane Flow"
        description="Live 2D (Key × Model) slot assignments, queue ETA, and copyable execution log."
        maxWidth={enlarged ? "full" : "4xl"}
        className={enlarged ? "h-[88vh] flex flex-col" : "max-h-[85vh] flex flex-col"}
      >
        <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <Badge variant="default">
              Lanes: {data ? `${data.active_lanes_count}/${data.total_lanes_count}` : "—"}
            </Badge>
            <Badge variant="info">
              ETA: {data ? (data.estimated_remaining_seconds > 0 ? `~${formatDuration(data.estimated_remaining_seconds)}` : "Idle") : "—"}
            </Badge>
            <Badge variant="info">{data?.cadence_mode || "—"}</Badge>
            {data?.queue_summary?.paused_quota ? (
              <Badge variant="warning">
                Paused (Quota): {data.queue_summary.paused_quota} · Reset in {formatDuration(data.seconds_until_pt_reset || 0)}
              </Badge>
            ) : null}
          </div>

          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => setEnlarged((v) => !v)}
              icon={enlarged ? <ArrowsInSimple size={13} weight="bold" /> : <ArrowsOutSimple size={13} weight="bold" />}
            >
              {enlarged ? "Compact" : "Enlarge"}
            </Button>
          </div>
        </div>

        {error ? (
          <div className="mb-3 rounded-[var(--rl-radius-sm)] border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800 flex items-center gap-2">
            <WarningCircle size={15} weight="bold" />
            <span>{error}</span>
          </div>
        ) : null}

        {data?.queue_summary?.paused_quota ? (
          <div className="mb-3 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-950 flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-2">
              <ClockCountdown size={15} weight="bold" className="text-amber-700" />
              <span>
                Daily Google quota reached. {data.queue_summary.paused_quota} job(s) paused safely and will auto-resume at Pacific Time midnight (4:00 PM MYT).
              </span>
            </div>
            <Link
              href={"/settings?tab=ai-fleet" as Route}
              className="font-semibold underline text-amber-900 hover:text-black"
            >
              Add Key to Resume Now →
            </Link>
          </div>
        ) : null}

        <div className="flex-1 min-h-0 overflow-y-auto space-y-4 pr-1">
          {/* Queue Summary Strip */}
          {data ? (
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-center">
              {[
                { label: "Queued", val: data.queue_summary.queued },
                { label: "Processing", val: data.queue_summary.processing },
                { label: "Paused Quota", val: data.queue_summary.paused_quota },
                { label: "Paused User", val: data.queue_summary.paused_user },
                { label: "Completed", val: data.queue_summary.completed },
                { label: "Failed", val: data.queue_summary.failed },
              ].map((s) => (
                <div key={s.label} className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-2">
                  <div className="text-[10px] uppercase tracking-wider text-[var(--rl-text-muted)] font-semibold">{s.label}</div>
                  <div className="text-sm font-mono font-bold text-[var(--rl-text-strong)] mt-0.5">{s.val}</div>
                </div>
              ))}
            </div>
          ) : null}

          {/* 2D Lane Matrix */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)] flex items-center gap-1.5">
                <Pulse size={14} weight="bold" />
                <span>2D Lane Flow (Key × Model)</span>
              </h3>
              {loading && !data ? <span className="text-[11px] text-[var(--rl-text-muted)]">Loading...</span> : null}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
              {(data?.lanes || []).map((lane) => {
                const st = laneStatusBadge(lane);
                const active = lane.active_assignments?.[0];
                return (
                  <div
                    key={lane.lane_id}
                    className={`rounded-[var(--rl-radius-sm)] border p-2.5 text-xs ${
                      lane.in_flight_count > 0
                        ? "border-neutral-900 bg-neutral-50"
                        : "border-[var(--rl-border)] bg-white"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1.5">
                      <span className="font-semibold text-[var(--rl-text-strong)] truncate" title={lane.account_label}>
                        {lane.account_label}
                      </span>
                      <Badge variant={st.variant} className="text-[10px] px-1.5 py-0 min-h-[20px]">
                        {st.label}
                      </Badge>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-[var(--rl-text-muted)] font-mono">
                      <span>{lane.model.replace("gemini-", "")}</span>
                      <span>{lane.api_key_masked || ""}</span>
                    </div>
                    <div className="mt-2 grid grid-cols-3 gap-1 text-[10px] font-mono text-[var(--rl-text-muted)]">
                      <div>RPM {lane.rpm_used}/{lane.rpm_limit}</div>
                      <div>RPD {lane.rpd_used}/{lane.rpd_limit}</div>
                      <div>{lane.last_latency_ms ? `${lane.last_latency_ms}ms` : "—"}</div>
                    </div>
                    {active ? (
                      <div className="mt-1.5 rounded bg-neutral-900 text-white px-2 py-1 text-[10px] font-mono truncate flex items-center gap-1" title={active.filename || active.purpose || ""}>
                        <span
                          className={`px-1 rounded text-[9px] font-bold shrink-0 ${
                            String(active.purpose || "").startsWith("copilot")
                              ? "bg-blue-500 text-white"
                              : "bg-emerald-500 text-white"
                          }`}
                        >
                          {String(active.purpose || "").startsWith("copilot") ? "CHAT" : "PDF"}
                        </span>
                        <span className="truncate">
                          {active.filename || active.purpose} ({active.elapsed_sec ?? 0}s)
                        </span>
                      </div>
                    ) : lane.last_error ? (
                      <div className="mt-1.5 text-[10px] text-red-700 truncate" title={lane.last_error}>
                        {lane.last_error}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Scrollable Copyable Event Log */}
          <div className="flex flex-col">
            <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
              <div className="flex items-center gap-1.5">
                {(
                  [
                    { key: "all", label: "All Logs" },
                    { key: "assigned", label: "Flow / Success" },
                    { key: "warn", label: "429 / Quota" },
                    { key: "error", label: "Errors" },
                  ] as const
                ).map((f) => (
                  <button
                    key={f.key}
                    type="button"
                    onClick={() => setLogFilter(f.key)}
                    className={`px-2 py-1 rounded-[var(--rl-radius-sm)] text-[11px] font-semibold cursor-pointer ${
                      logFilter === f.key
                        ? "bg-[var(--rl-black)] text-white"
                        : "bg-neutral-100 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-1 text-[11px] text-[var(--rl-text-muted)] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={autoScroll}
                    onChange={(e) => setAutoScroll(e.target.checked)}
                    className="accent-black"
                  />
                  <span>Auto-follow</span>
                </label>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => void handleCopyLogs()}
                  icon={copied ? <Check size={13} weight="bold" /> : <Copy size={13} weight="bold" />}
                >
                  {copied ? "Copied" : "Copy Logs"}
                </Button>
              </div>
            </div>

            <div
              ref={logBoxRef}
              className={`rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-neutral-950 text-neutral-100 font-mono text-[11px] p-3 overflow-y-auto select-text space-y-1 ${
                enlarged ? "h-80" : "h-52"
              }`}
            >
              {filteredEvents.length === 0 ? (
                <div className="text-neutral-400">No fleet log entries matching this filter yet.</div>
              ) : (
                filteredEvents.map((ev) => {
                  const ts = ev.created_at
                    ? new Date(ev.created_at).toLocaleTimeString("en-GB", { hour12: false })
                    : "--:--:--";
                  const levelCls =
                    ev.level === "error"
                      ? "text-red-400"
                      : ev.level === "warn"
                        ? "text-amber-300"
                        : "text-emerald-300";
                  return (
                    <div key={ev.id} className="leading-relaxed break-words">
                      <span className="text-neutral-500">[{ts}]</span>{" "}
                      <span className={levelCls}>[{ev.event_type}]</span>{" "}
                      {ev.lane_id ? <span className="text-sky-300">({ev.lane_id}) </span> : null}
                      <span>{ev.message}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </Dialog>
    </>
  );
}
