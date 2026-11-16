"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  ArrowsClockwise,
  ArrowSquareOut,
  CheckCircle,
  Gear,
  Lightning,
  Pause,
  Play,
  ShieldCheck,
  Sparkle,
  Warning,
  WarningCircle,
  WarningOctagon,
  X,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";

export type GeminiAccountItem = {
  id: string;
  index: number;
  label: string;
  source: "env" | "manual";
  masked_key: string;
  status: string;
  status_label: string;
  status_color: "green" | "red" | "amber" | "gray";
  rpm_used: number;
  rpm_limit: number;
  rpm_remaining: number;
  rpd_used: number;
  rpd_limit: number;
  rpd_remaining: number;
  tpm_used: number;
  tpm_limit: number;
  tpm_remaining: number;
  cooling_until?: number | null;
  last_switch_reason?: string | null;
  last_probed_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  last_error_code?: number | null;
  successful_calls: number;
  failed_calls: number;
  is_active: boolean;
  is_paused?: boolean;
};

export type GeminiEndpointItem = {
  slot_id: string;
  slot_index: number;
  account_label: string;
  masked_key: string;
  model: string;
  rpm_used: number;
  rpm_limit: number;
  rpm_remaining: number;
  tpm_used: number;
  tpm_limit: number;
  tpm_remaining: number;
  cooling_until?: number | null;
  is_ready: boolean;
  is_paused?: boolean;
  status_label: string;
  status_color: "green" | "amber" | "red" | "gray";
};

export type GeminiQuotaStats = {
  active?: boolean;
  status?: string;
  status_label?: string;
  status_color?: "green" | "red" | "amber" | "gray";
  model?: string;
  models?: string[];
  active_account_index?: number;
  active_account_label?: string;
  keys_count?: number;
  key_count?: number;
  active_keys_count?: number;
  fleet_endpoints_count?: number;
  active_endpoints_count?: number;
  tokens_budget_per_request?: number;
  fleet_summary?: {
    keys_count: number;
    active_keys_count?: number;
    models_per_key: number;
    total_parallel_endpoints: number;
    active_parallel_endpoints?: number;
    fleet_rpd_limit: number;
    fleet_rpm_limit: number;
    fleet_tpm_limit: number;
    raw_rpd_capacity?: number;
    raw_rpm_capacity?: number;
    tokens_per_request_budget: number;
  };
  endpoints?: GeminiEndpointItem[];
  parallel_slots?: GeminiEndpointItem[];
  rpm_limit?: number;
  rpm_used?: number;
  rpm_remaining?: number;
  rpd_limit?: number;
  rpd_used?: number;
  rpd_remaining?: number;
  tpm_limit?: number;
  prompt_guard_limit?: number;
  pool_rpd_limit?: number;
  pool_rpd_used?: number;
  pool_rpd_remaining?: number;
  pool_rpm_limit?: number;
  pool_rpm_used?: number;
  pool_cutoff_active?: boolean;
  accounts?: GeminiAccountItem[];
  message?: string;
};

export function GeminiHeaderMeter() {
  const { toast } = useToast();
  const [stats, setStats] = useState<GeminiQuotaStats | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [probing, setProbing] = useState(false);
  const [probingIdx, setProbingIdx] = useState<number | null>(null);
  const [probeResult, setProbeResult] = useState<string | null>(null);
  const [pausingId, setPausingId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  async function loadLimits() {
    try {
      const res = await api<{ gemini?: GeminiQuotaStats }>("/settings/limits");
      if (res?.gemini) {
        setStats(res.gemini);
      }
    } catch {
      // Quiet fail on network hiccups
    }
  }

  useEffect(() => {
    loadLimits();
    const interval = setInterval(loadLimits, 30_000);
    return () => clearInterval(interval);
  }, []);

  // Close popover when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  async function handleProbe(e?: React.MouseEvent) {
    if (e) e.stopPropagation();
    setProbing(true);
    setProbeResult(null);
    try {
      const res = await api<{ gemini: GeminiQuotaStats }>("/settings/gemini/probe", {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (res?.gemini) {
        setStats(res.gemini);
        setProbeResult(res.gemini.status === "ready" ? "Live Verified: HTTP 200 OK" : `Status: ${res.gemini.status_label || res.gemini.status}`);
      }
    } catch (err) {
      setProbeResult(err instanceof Error ? err.message : "Probe connection failed");
    } finally {
      setProbing(false);
    }
  }

  async function handleProbeKey(idx: number, e: React.MouseEvent) {
    e.stopPropagation();
    setProbingIdx(idx);
    setProbeResult(null);
    try {
      const res = await api<{ gemini: GeminiQuotaStats }>("/settings/gemini/probe", {
        method: "POST",
        body: JSON.stringify({ account_index: idx }),
      });
      if (res?.gemini) {
        setStats(res.gemini);
        const targetAcc = res.gemini.accounts?.[idx];
        setProbeResult(
          targetAcc?.status === "ready" || res.gemini.status === "ready"
            ? `Key ${idx + 1} live verified: HTTP 200 OK`
            : `Key ${idx + 1} status: ${targetAcc?.status_label || res.gemini.status_label || "Error"}`
        );
      }
    } catch (err) {
      setProbeResult(err instanceof Error ? err.message : "Probe connection failed");
    } finally {
      setProbingIdx(null);
    }
  }

  async function handleTogglePause(keyId: string, currentPaused: boolean, e: React.MouseEvent) {
    e.stopPropagation();
    setPausingId(keyId);
    try {
      const res = await api<{ ok: boolean; is_paused: boolean; gemini: GeminiQuotaStats }>(
        `/settings/gemini/keys/${keyId}/toggle-pause`,
        {
          method: "POST",
          body: JSON.stringify({ paused: !currentPaused }),
        }
      );
      if (res?.gemini) {
        setStats(res.gemini);
        toast(
          res.is_paused ? "Key turned off (resting). Fleet capacity scaled down." : "Key resumed to active fleet.",
          "success"
        );
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to toggle key status", "error");
    } finally {
      setPausingId(null);
    }
  }

  if (!stats) return null;

  const accounts = stats.accounts || [];
  const endpoints = stats.endpoints || [];

  const activeKeysCount = stats.active_keys_count ?? stats.fleet_summary?.active_keys_count ?? accounts.filter((a) => !a.is_paused).length;
  const activeEndpointsCount = stats.active_endpoints_count ?? stats.fleet_summary?.active_parallel_endpoints ?? endpoints.filter((ep) => ep.is_ready && !ep.is_paused).length;
  const totalKeys = stats.fleet_summary?.keys_count ?? stats.key_count ?? stats.keys_count ?? (accounts.length > 0 ? accounts.length : 2);
  const totalEndpoints = stats.fleet_summary?.total_parallel_endpoints ?? (endpoints.length > 0 ? endpoints.length : 4);

  const color = stats.status_color || (activeKeysCount === 0 ? "gray" : "green");
  const fleetRpdLimit = stats.fleet_summary?.fleet_rpd_limit ?? stats.pool_rpd_limit ?? stats.rpd_limit ?? 1920;
  const fleetRpdUsed = stats.pool_rpd_used ?? stats.rpd_used ?? 0;
  const fleetRpmLimit = stats.fleet_summary?.fleet_rpm_limit ?? stats.pool_rpm_limit ?? stats.rpm_limit ?? 52;
  const fleetRpmUsed = stats.pool_rpm_used ?? stats.rpm_used ?? 0;
  const tokensBudget = stats.fleet_summary?.tokens_per_request_budget ?? stats.tokens_budget_per_request ?? 43_000;

  const rpdPercent = fleetRpdLimit > 0 ? Math.min(100, Math.round((fleetRpdUsed / fleetRpdLimit) * 100)) : 0;
  const rpmPercent = fleetRpmLimit > 0 ? Math.min(100, Math.round((fleetRpmUsed / fleetRpmLimit) * 100)) : 0;

  return (
    <div className="relative" ref={containerRef}>
      {/* Interactive Top Header Pill Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Gemini AI Fleet Rate Limit Monitor"
        className="flex items-center gap-2 rounded-full border border-gray-200 bg-white/95 px-2.5 py-1 text-[11px] font-medium text-gray-700 shadow-xs hover:border-gray-300 hover:bg-gray-50 transition-all cursor-pointer select-none"
      >
        {/* Pulsing Status Dot */}
        <span className="relative flex size-2">
          {color === "green" && (
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          )}
          {color === "amber" && (
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-amber-400 opacity-75" />
          )}
          {color === "red" && (
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-rose-400 opacity-75" />
          )}
          <span
            className={`relative inline-flex size-2 rounded-full ${
              color === "green"
                ? "bg-emerald-500"
                : color === "amber"
                ? "bg-amber-500"
                : color === "red"
                ? "bg-rose-500"
                : "bg-gray-400"
            }`}
          />
        </span>

        {/* Compact Meter Details */}
        <span className="font-semibold text-gray-900 flex items-center gap-1">
          <Sparkle size={12} weight="fill" className="text-amber-500" />
          <span>
            Fleet: {activeKeysCount}/{totalKeys} Keys · {activeEndpointsCount}/{totalEndpoints} Endpoints
          </span>
        </span>
        <span className="text-gray-300">|</span>
        <span className="font-mono text-[10px] text-gray-700 font-semibold" title={`Fleet Total: ${fleetRpdUsed} used of ${fleetRpdLimit} daily requests`}>
          {fleetRpdUsed}/{fleetRpdLimit} RPD
        </span>
        <span className="text-gray-300">·</span>
        <span className="font-mono text-[10px] text-gray-700 font-semibold" title={`Fleet Total: ${fleetRpmUsed} used of ${fleetRpmLimit} requests per minute`}>
          {fleetRpmUsed}/{fleetRpmLimit} RPM
        </span>
        <span className="text-gray-300">·</span>
        <span className="font-mono text-[10px] text-gray-700 font-semibold" title={`Per-request token budget: ~${tokensBudget.toLocaleString()} tokens`}>
          ~{Math.round(tokensBudget / 1000)}k tok/req
        </span>
      </button>

      {/* Dropdown Popover */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-[390px] rounded-xl border border-gray-200 bg-white p-4 shadow-xl z-50 animate-in fade-in zoom-in-95 duration-150">
          {/* Header Row */}
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <span className="grid size-6 place-items-center rounded-md bg-amber-50 text-amber-600">
                <Sparkle size={14} weight="fill" />
              </span>
              <div>
                <h3 className="text-xs font-bold text-gray-900">
                  Gemini AI Parallel Fleet ({activeEndpointsCount}/{totalEndpoints} Active)
                </h3>
                <span className="text-[10px] font-mono text-gray-500">
                  {totalKeys} Keys × 2 Models · Parallel Dispatching
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-gray-600 p-1 rounded-md"
            >
              <X size={14} weight="bold" />
            </button>
          </div>

          {/* Fleet Aggregate Capacity Card */}
          <div className="mt-3 rounded-lg border border-sky-100 bg-sky-50/60 p-3">
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="font-bold text-sky-950 flex items-center gap-1.5">
                <Lightning size={13} weight="fill" className="text-amber-500" />
                Fleet Aggregate Limits
              </span>
              <span
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full font-mono ${
                  activeKeysCount === 0
                    ? "bg-gray-200 text-gray-700"
                    : activeKeysCount === totalKeys
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-sky-100 text-sky-800"
                }`}
              >
                {stats.status_label || (activeKeysCount === 0 ? "Fleet Offline (All Keys Paused)" : `${activeEndpointsCount}/${totalEndpoints} Online`)}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center py-1 bg-white/80 rounded border border-sky-100">
              <div className="px-1">
                <span className="text-[9px] uppercase font-bold text-gray-400 block">Daily Total</span>
                <span className="font-mono text-xs font-bold text-gray-800">{fleetRpdLimit} RPD</span>
              </div>
              <div className="px-1 border-x border-sky-100">
                <span className="text-[9px] uppercase font-bold text-gray-400 block">Minute Total</span>
                <span className="font-mono text-xs font-bold text-gray-800">{fleetRpmLimit} RPM</span>
              </div>
              <div className="px-1">
                <span className="text-[9px] uppercase font-bold text-gray-400 block">Tok / Request</span>
                <span className="font-mono text-xs font-bold text-emerald-700">~{Math.round(tokensBudget / 1000)}k tok</span>
              </div>
            </div>

            {/* Progress Bars */}
            <div className="mt-2.5 space-y-2">
              <div>
                <div className="flex justify-between text-[10px] text-gray-600 font-medium">
                  <span>Daily Requests (RPD)</span>
                  <span className="font-mono font-semibold">
                    {fleetRpdUsed} / {fleetRpdLimit} ({rpdPercent}%)
                  </span>
                </div>
                <div className="mt-1 h-1.5 w-full rounded-full bg-gray-200 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      rpdPercent >= 90 ? "bg-rose-500" : rpdPercent >= 70 ? "bg-amber-500" : "bg-emerald-500"
                    }`}
                    style={{ width: `${rpdPercent}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[10px] text-gray-600 font-medium">
                  <span>Minute Rate (RPM)</span>
                  <span className="font-mono font-semibold">
                    {fleetRpmUsed} / {fleetRpmLimit} ({rpmPercent}%)
                  </span>
                </div>
                <div className="mt-1 h-1.5 w-full rounded-full bg-gray-200 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      rpmPercent >= 80 ? "bg-amber-500" : "bg-blue-500"
                    }`}
                    style={{ width: `${rpmPercent}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* 4 Parallel Model Endpoints Grid */}
          <div className="mt-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1.5">
              4 Model Endpoints (Parallel Quotas)
            </span>
            <div className="space-y-1.5 max-h-[170px] overflow-y-auto pr-1">
              {endpoints.length > 0 ? (
                endpoints.map((ep, idx) => (
                  <div
                    key={ep.slot_id || idx}
                    className={`flex items-center justify-between rounded-lg border px-2.5 py-1.5 text-xs transition-opacity ${
                      ep.is_paused ? "border-gray-200 bg-gray-50/40 opacity-60" : "border-gray-150 bg-gray-50/50"
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className={`size-2 shrink-0 rounded-full ${
                          ep.is_paused
                            ? "bg-gray-400"
                            : ep.status_color === "green"
                            ? "bg-emerald-500"
                            : ep.status_color === "amber"
                            ? "bg-amber-500"
                            : "bg-gray-400"
                        }`}
                      />
                      <div className="min-w-0">
                        <div className="font-medium text-gray-800 text-[11px] truncate flex items-center gap-1">
                          <span className="font-bold">{ep.account_label.replace("Account ", "Key ")}</span>
                          <span className="text-gray-400">·</span>
                          <span className="font-mono text-indigo-700 font-semibold">{ep.model.replace("gemini-2.5-", "")}</span>
                        </div>
                        <div className="font-mono text-[9px] text-gray-500">
                          {ep.is_paused
                            ? "Key Turned Off · Slot Inactive"
                            : `${ep.rpm_used}/${ep.rpm_limit} RPM · ${(ep.tpm_used || 0).toLocaleString()}/{(ep.tpm_limit || 200000).toLocaleString()} TPM`}
                        </div>
                      </div>
                    </div>

                    <span
                      className={`text-[9px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${
                        ep.is_paused
                          ? "bg-gray-200 text-gray-700"
                          : ep.is_ready
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {ep.status_label || (ep.is_paused ? "Off · Paused" : ep.is_ready ? "Ready" : "Cooling")}
                    </span>
                  </div>
                ))
              ) : (
                <div className="text-[11px] text-gray-500 p-2 text-center bg-gray-50 rounded">
                  4 parallel endpoints configured (2 keys × 2 models)
                </div>
              )}
            </div>
          </div>

          {/* Fleet Keys & Independent Controls Section */}
          <div className="mt-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                Fleet Keys (Independent Controls)
              </span>
              <span className="text-[9px] text-gray-400 font-mono">
                {activeKeysCount}/{totalKeys} Active
              </span>
            </div>
            <div className="space-y-1.5">
              {accounts.map((acc, idx) => {
                const isPaused = !!acc.is_paused;
                const isPausing = pausingId === acc.id;
                const isProbingThis = probingIdx === idx;

                return (
                  <div
                    key={acc.id}
                    className={`flex items-center justify-between rounded-lg border px-2.5 py-2 text-xs transition-colors ${
                      isPaused ? "border-gray-200 bg-gray-50/40" : "border-emerald-200 bg-emerald-50/20"
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className={`size-2 shrink-0 rounded-full ${
                          isPaused
                            ? "bg-amber-400"
                            : acc.status_color === "green"
                            ? "bg-emerald-500"
                            : acc.status_color === "amber"
                            ? "bg-amber-500"
                            : "bg-gray-400"
                        }`}
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-gray-900 text-[11px] truncate">{acc.label}</span>
                          {isPaused ? (
                            <span className="text-[9px] font-semibold text-amber-800 bg-amber-100 px-1.5 py-0.2 rounded shrink-0">
                              Off · Paused
                            </span>
                          ) : (
                            <span className="text-[9px] font-semibold text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded shrink-0">
                              Active
                            </span>
                          )}
                        </div>
                        <div className="font-mono text-[9px] text-gray-500 truncate">
                          {acc.rpd_used}/{acc.rpd_limit} RPD · {acc.masked_key}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0 ml-2">
                      {/* Individual Test Button */}
                      <button
                        type="button"
                        disabled={isProbingThis || isPaused}
                        onClick={(e) => handleProbeKey(idx, e)}
                        title={isPaused ? "Key is turned off — turn on to test" : `Test ${acc.label} live against Google`}
                        className="text-[10px] font-medium text-gray-700 hover:text-gray-900 border border-gray-200 hover:bg-white rounded px-1.5 py-0.5 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
                      >
                        <ArrowsClockwise size={10} className={isProbingThis ? "animate-spin" : ""} />
                        <span>{isProbingThis ? "..." : "Test"}</span>
                      </button>

                      {/* Independent On/Off Toggle Button */}
                      <button
                        type="button"
                        disabled={isPausing}
                        onClick={(e) => handleTogglePause(acc.id, isPaused, e)}
                        title={isPaused ? `Turn on ${acc.label} into active fleet` : `Turn off (pause) ${acc.label}`}
                        className={`text-[10px] font-semibold border rounded px-2 py-0.5 transition-colors cursor-pointer flex items-center gap-1 ${
                          isPaused
                            ? "bg-emerald-600 border-emerald-600 text-white hover:bg-emerald-700"
                            : "bg-white border-gray-200 text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                        }`}
                      >
                        {isPausing ? (
                          "..."
                        ) : isPaused ? (
                          <>
                            <Play size={10} weight="fill" /> Turn On
                          </>
                        ) : (
                          <>
                            <Pause size={10} weight="fill" /> Turn Off
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Actions & Footer */}
          <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between text-xs">
            <button
              type="button"
              disabled={probing}
              onClick={(e) => handleProbe(e)}
              className="inline-flex items-center gap-1.5 text-[11px] font-medium text-gray-700 hover:text-gray-900 border border-gray-200 hover:bg-gray-50 rounded-lg px-2.5 py-1 transition-colors cursor-pointer"
            >
              <ArrowsClockwise size={12} weight="bold" className={probing ? "animate-spin" : ""} />
              {probing ? "Testing..." : "Test Active Fleet"}
            </button>

            <Link
              href={"/settings/ai-engine" as Route}
              onClick={() => setIsOpen(false)}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-gray-900 hover:text-black underline underline-offset-2"
            >
              <Gear size={12} weight="bold" />
              Manage Fleet Keys
            </Link>
          </div>

          {probeResult && (
            <div className="mt-2 text-[10px] font-mono text-center text-gray-600 bg-gray-50 rounded py-1 px-2 border border-gray-150">
              {probeResult}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
