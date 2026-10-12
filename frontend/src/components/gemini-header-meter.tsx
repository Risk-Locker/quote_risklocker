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
  ShieldCheck,
  Sparkle,
  Warning,
  WarningCircle,
  WarningOctagon,
  X,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";

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
  status_label: string;
  status_color: "green" | "amber" | "red";
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
  fleet_endpoints_count?: number;
  tokens_budget_per_request?: number;
  fleet_summary?: {
    keys_count: number;
    models_per_key: number;
    total_parallel_endpoints: number;
    fleet_rpd_limit: number;
    fleet_rpm_limit: number;
    fleet_tpm_limit: number;
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
  const [stats, setStats] = useState<GeminiQuotaStats | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [probing, setProbing] = useState(false);
  const [probeResult, setProbeResult] = useState<string | null>(null);
  const [switching, setSwitching] = useState<number | null>(null);
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

  async function handleSwitchAccount(idx: number, e: React.MouseEvent) {
    e.stopPropagation();
    setSwitching(idx);
    try {
      const res = await api<{ ok: boolean; gemini: GeminiQuotaStats }>("/settings/gemini/switch-account", {
        method: "POST",
        body: JSON.stringify({ account_index: idx }),
      });
      if (res?.gemini) {
        setStats(res.gemini);
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to switch account");
    } finally {
      setSwitching(null);
    }
  }

  if (!stats) return null;

  const accounts = stats.accounts || [];
  const activeIdx = stats.active_account_index ?? 0;
  const activeAcc = accounts[activeIdx] || accounts[0];
  const endpoints = stats.endpoints || [];

  const color = stats.status_color || "gray";
  const fleetRpdLimit = stats.fleet_summary?.fleet_rpd_limit ?? stats.pool_rpd_limit ?? stats.rpd_limit ?? 1840;
  const fleetRpdUsed = stats.pool_rpd_used ?? stats.rpd_used ?? 0;
  const fleetRpmLimit = stats.fleet_summary?.fleet_rpm_limit ?? stats.pool_rpm_limit ?? stats.rpm_limit ?? 48;
  const fleetRpmUsed = stats.pool_rpm_used ?? stats.rpm_used ?? 0;
  const fleetTpmLimit = stats.fleet_summary?.fleet_tpm_limit ?? stats.tpm_limit ?? 880_000;
  const tokensBudget = stats.fleet_summary?.tokens_per_request_budget ?? stats.tokens_budget_per_request ?? 43_000;
  const totalEndpoints = stats.fleet_summary?.total_parallel_endpoints ?? (endpoints.length > 0 ? endpoints.length : 4);
  const totalKeys = stats.fleet_summary?.keys_count ?? stats.key_count ?? stats.keys_count ?? (accounts.length > 0 ? accounts.length : 2);

  const rpdPercent = Math.min(100, Math.round((fleetRpdUsed / fleetRpdLimit) * 100));
  const rpmPercent = Math.min(100, Math.round((fleetRpmUsed / fleetRpmLimit) * 100));

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
          <span>Fleet: {totalKeys} Keys · {totalEndpoints} Endpoints</span>
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
                <h3 className="text-xs font-bold text-gray-900">Gemini AI Parallel Fleet ({totalEndpoints} Endpoints)</h3>
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
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-mono">
                {stats.status_label || "Ready · Parallel"}
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
                    className="flex items-center justify-between rounded-lg border border-gray-150 bg-gray-50/50 px-2.5 py-1.5 text-xs"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className={`size-2 shrink-0 rounded-full ${
                          ep.status_color === "green"
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
                          {ep.rpm_used}/{ep.rpm_limit} RPM · {(ep.tpm_used || 0).toLocaleString()}/{(ep.tpm_limit || 110000).toLocaleString()} TPM
                        </div>
                      </div>
                    </div>

                    <span
                      className={`text-[9px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${
                        ep.is_ready ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {ep.status_label || (ep.is_ready ? "Ready" : "Cooling")}
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

          {/* Account Switcher Section (if more than 1 account) */}
          {accounts.length > 1 && (
            <div className="mt-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1.5">
                Switch Active Account
              </span>
              <div className="space-y-1">
                {accounts.map((acc, idx) => (
                  <div
                    key={acc.id}
                    className={`flex items-center justify-between rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
                      idx === activeIdx
                        ? "border-emerald-200 bg-emerald-50/50"
                        : "border-gray-100 hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`size-2 rounded-full ${
                          acc.status_color === "green"
                            ? "bg-emerald-500"
                            : acc.status_color === "amber"
                            ? "bg-amber-500"
                            : "bg-gray-400"
                        }`}
                      />
                      <div>
                        <div className="font-medium text-gray-800 text-[11px]">{acc.label}</div>
                        <div className="font-mono text-[9px] text-gray-400">
                          {acc.rpd_used}/{acc.rpd_limit} RPD · {acc.masked_key}
                        </div>
                      </div>
                    </div>

                    {idx === activeIdx ? (
                      <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded">
                        Active
                      </span>
                    ) : (
                      <button
                        type="button"
                        disabled={switching !== null}
                        onClick={(e) => handleSwitchAccount(idx, e)}
                        className="text-[10px] font-medium text-gray-700 hover:text-gray-900 border border-gray-200 hover:bg-white rounded px-2 py-0.5 transition-colors cursor-pointer"
                      >
                        {switching === idx ? "Switching..." : "Select"}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions & Footer */}
          <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between text-xs">
            <button
              type="button"
              disabled={probing}
              onClick={(e) => handleProbe(e)}
              className="inline-flex items-center gap-1.5 text-[11px] font-medium text-gray-700 hover:text-gray-900 border border-gray-200 hover:bg-gray-50 rounded-lg px-2.5 py-1 transition-colors cursor-pointer"
            >
              <ArrowsClockwise size={12} weight="bold" className={probing ? "animate-spin" : ""} />
              {probing ? "Testing..." : "Test Active Key"}
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
