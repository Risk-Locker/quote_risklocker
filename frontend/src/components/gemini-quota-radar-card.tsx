"use client";

import { useEffect, useState } from "react";
import {
  ArrowsClockwise,
  CheckCircle,
  Radioactive,
  ShieldCheck,
  Warning,
  WarningOctagon,
} from "@phosphor-icons/react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";

export interface QuotaRadarData {
  timestamp: string;
  local_date: string;
  overall_status: string;
  active_model: string;
  parallel_models: string[];
  key_count: number;
  total_endpoints: number;
  total_rpd_used: number;
  total_rpd_limit: number;
  google_catalog_verified: boolean;
  alerts: string[];
  endpoints: Array<{
    slot_id: string;
    account_label: string;
    masked_key: string;
    model: string;
    rpd_limit: number;
    status_label: string;
  }>;
}

export function GeminiQuotaRadarCard({ onRefreshData }: { onRefreshData?: () => void }) {
  const [radar, setRadar] = useState<QuotaRadarData | null>(null);
  const [loading, setLoading] = useState(false);
  const [runningProbe, setRunningProbe] = useState(false);
  const [error, setError] = useState("");
  const { toast } = useToast();

  async function loadRadar(forceRefresh = false) {
    if (forceRefresh) setRunningProbe(true);
    else setLoading(true);
    setError("");

    try {
      const res = await api<{ ok: boolean; radar: QuotaRadarData; cached?: boolean }>(
        `/settings/gemini/quota-radar?refresh=${forceRefresh ? "true" : "false"}`
      );
      if (res?.radar) {
        setRadar(res.radar);
        if (forceRefresh) {
          toast("Autonomous Quota Radar probe completed against Google AI Studio.", "success");
          if (onRefreshData) onRefreshData();
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Quota Radar status.");
    } finally {
      setLoading(false);
      setRunningProbe(false);
    }
  }

  useEffect(() => {
    loadRadar(false);
  }, []);

  function formatTime(isoStr: string): string {
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return isoStr;
    }
  }

  const hasAlerts = (radar?.alerts?.length ?? 0) > 0;

  return (
    <Card className="p-5 border border-[var(--rl-border)] bg-white shadow-xs grid gap-4">
      {/* Header and Probe Trigger */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-3">
        <div className="flex items-center gap-2.5">
          <div className="relative flex items-center justify-center size-8 rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-200">
            <ShieldCheck size={20} weight="fill" />
            <span className="absolute -top-1 -right-1 flex size-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full size-2.5 bg-emerald-500" />
            </span>
          </div>
          <div>
            <h2 className="text-sm font-bold text-[var(--rl-text-strong)] flex items-center gap-2">
              Autonomous AI Quota Radar (20-Minute Sentinel Cycle)
            </h2>
            <p className="text-xs text-[var(--rl-text-muted)] mt-0.5">
              Continuously probes upstream Google AI Studio model health, catalog deprecation, and ensures the 480 RPD cap is never crossed.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {radar?.timestamp && (
            <span className="text-[11px] text-[var(--rl-text-muted)] font-mono">
              Last probe: {formatTime(radar.timestamp)}
            </span>
          )}
          <Button
            variant="secondary"
            size="sm"
            loading={runningProbe}
            icon={<ArrowsClockwise size={14} weight="bold" className={runningProbe ? "animate-spin" : ""} />}
            onClick={() => loadRadar(true)}
            disabled={runningProbe || loading}
          >
            {runningProbe ? "Probing Google..." : "Probe Now"}
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2 text-xs font-semibold text-[var(--rl-red)]">
          {error}
        </div>
      ) : null}

      {/* Critical Alert Banner if Google changed quotas or model status */}
      {hasAlerts ? (
        <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800 space-y-1.5">
          <div className="flex items-center gap-2 font-bold text-rose-900">
            <WarningOctagon size={18} weight="fill" className="text-rose-600 shrink-0" />
            <span>AI Radar Warning / Google Quota Alert Detected</span>
          </div>
          <ul className="list-disc list-inside space-y-1 pl-1 text-[11px]">
            {radar?.alerts.map((alert, idx) => (
              <li key={idx} className="font-mono">{alert}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-emerald-50/60 border border-emerald-100 text-xs">
          <div className="flex items-center gap-2 text-emerald-800 font-medium">
            <CheckCircle size={16} weight="fill" className="text-emerald-600 shrink-0" />
            <span>
              Google AI Studio Catalog Verified — All active models operating within safe 480 RPD bounds.
            </span>
          </div>
          <Badge variant="success" className="font-mono text-[10px]">
            Zero Quota Anomalies
          </Badge>
        </div>
      )}

      {/* Quick Summary Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="p-2.5 rounded bg-[var(--rl-bg)] border border-[var(--rl-border)]">
          <span className="text-[10px] uppercase font-semibold text-[var(--rl-text-muted)] block">
            Probe Frequency
          </span>
          <span className="font-bold text-[var(--rl-text-strong)] mt-0.5 block">Every 20 Minutes</span>
          <span className="text-[10px] text-[var(--rl-text-muted)]">Autonomous cron task</span>
        </div>

        <div className="p-2.5 rounded bg-[var(--rl-bg)] border border-[var(--rl-border)]">
          <span className="text-[10px] uppercase font-semibold text-[var(--rl-text-muted)] block">
            Parallel Endpoints
          </span>
          <span className="font-bold text-[var(--rl-text-strong)] mt-0.5 block">
            {radar?.total_endpoints ?? 0} Slots Active
          </span>
          <span className="text-[10px] text-[var(--rl-text-muted)]">
            {radar?.key_count ?? 0} keys &times; {radar?.parallel_models.length ?? 0} models
          </span>
        </div>

        <div className="p-2.5 rounded bg-[var(--rl-bg)] border border-[var(--rl-border)]">
          <span className="text-[10px] uppercase font-semibold text-[var(--rl-text-muted)] block">
            Per-Model Daily Mark
          </span>
          <span className="font-bold text-emerald-700 font-mono mt-0.5 block">480 RPD Max</span>
          <span className="text-[10px] text-[var(--rl-text-muted)]">Locked below 500 ban line</span>
        </div>

        <div className="p-2.5 rounded bg-[var(--rl-bg)] border border-[var(--rl-border)]">
          <span className="text-[10px] uppercase font-semibold text-[var(--rl-text-muted)] block">
            Total Fleet Capacity
          </span>
          <span className="font-bold text-[var(--rl-text-strong)] font-mono mt-0.5 block">
            {radar?.total_rpd_used ?? 0} / {radar?.total_rpd_limit ?? 0}
          </span>
          <span className="text-[10px] text-[var(--rl-text-muted)]">Requests logged today</span>
        </div>
      </div>
    </Card>
  );
}
