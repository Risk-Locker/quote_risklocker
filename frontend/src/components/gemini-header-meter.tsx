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
  const totalAcc = accounts.length || 1;

  const color = stats.status_color || "gray";
  const rpdUsed = activeAcc?.rpd_used ?? stats.rpd_used ?? 0;
  const rpdLimit = activeAcc?.rpd_limit ?? stats.rpd_limit ?? 440;
  const rpmUsed = activeAcc?.rpm_used ?? stats.rpm_used ?? 0;
  const rpmLimit = activeAcc?.rpm_limit ?? stats.rpm_limit ?? 10;
  const tpmUsed = activeAcc?.tpm_used ?? 0;
  const tpmLimit = stats.tpm_limit ?? 100_000;

  const rpdPercent = Math.min(100, Math.round((rpdUsed / rpdLimit) * 100));
  const rpmPercent = Math.min(100, Math.round((rpmUsed / rpmLimit) * 100));
  const tpmPercent = Math.min(100, Math.round((tpmUsed / tpmLimit) * 100));

  return (
    <div className="relative" ref={containerRef}>
      {/* Interactive Top Header Pill Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Gemini AI Fleet Rate Limit Monitor"
        className="flex items-center gap-2 rounded-full border border-gray-200 bg-white/90 px-2.5 py-1 text-[11px] font-medium text-gray-700 shadow-xs hover:border-gray-300 hover:bg-gray-50 transition-all cursor-pointer select-none"
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
          <Sparkle size={12} weight="fill" className="text-gray-500" />
          <span>Acc {activeIdx + 1}/{totalAcc}</span>
        </span>
        <span className="text-gray-300">|</span>
        <span className="font-mono text-[10px] text-gray-600">
          {rpdUsed}/{rpdLimit} RPD
        </span>
        <span className="text-gray-300">·</span>
        <span className="font-mono text-[10px] text-gray-600">
          {rpmUsed}/{rpmLimit} RPM
        </span>
      </button>

      {/* Dropdown Popover */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-[340px] rounded-xl border border-gray-200 bg-white p-4 shadow-xl z-50 animate-in fade-in zoom-in-95 duration-150">
          {/* Header Row */}
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <span className="grid size-6 place-items-center rounded-md bg-emerald-50 text-emerald-600">
                <Sparkle size={14} weight="fill" />
              </span>
              <div>
                <h3 className="text-xs font-bold text-gray-900">Gemini AI Fleet Guard</h3>
                <span className="text-[10px] font-mono text-gray-500">
                  {stats.model || "gemini-3.1-flash-lite-preview"}
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

          {/* Active Account Card */}
          <div className="mt-3 rounded-lg border border-gray-100 bg-gray-50/70 p-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-gray-900 flex items-center gap-1.5">
                {activeAcc?.label || `Account ${activeIdx + 1}`}
                <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-gray-200 text-gray-700">
                  {activeAcc?.source === "env" ? ".env" : "Manual"}
                </span>
              </span>
              <span
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                  color === "green"
                    ? "bg-emerald-100 text-emerald-800"
                    : color === "amber"
                    ? "bg-amber-100 text-amber-800"
                    : color === "red"
                    ? "bg-rose-100 text-rose-800"
                    : "bg-gray-200 text-gray-700"
                }`}
              >
                {activeAcc?.status_label || stats.status_label || "Untested"}
              </span>
            </div>

            {activeAcc?.masked_key && (
              <div className="mt-1 font-mono text-[10px] text-gray-500">
                Key: {activeAcc.masked_key}
              </div>
            )}

            {/* Meters Progress Bars */}
            <div className="mt-3 space-y-2">
              {/* Daily Requests (RPD) */}
              <div>
                <div className="flex justify-between text-[10px] text-gray-600 font-medium">
                  <span>Daily Requests (RPD)</span>
                  <span className="font-mono">
                    {rpdUsed} / {rpdLimit} ({rpdPercent}%)
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

              {/* Requests Per Minute (RPM) */}
              <div>
                <div className="flex justify-between text-[10px] text-gray-600 font-medium">
                  <span>Requests Per Minute (RPM)</span>
                  <span className="font-mono">
                    {rpmUsed} / {rpmLimit} ({rpmPercent}%)
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

              {/* Tokens Per Minute (TPM) */}
              <div>
                <div className="flex justify-between text-[10px] text-gray-600 font-medium">
                  <span>Tokens Per Minute (TPM)</span>
                  <span className="font-mono">
                    {tpmUsed.toLocaleString()} / {tpmLimit.toLocaleString()}
                  </span>
                </div>
                <div className="mt-1 h-1.5 w-full rounded-full bg-gray-200 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-indigo-500 transition-all"
                    style={{ width: `${tpmPercent}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Prompt Guard Badge */}
            <div className="mt-3 flex items-center justify-between text-[10px] bg-white rounded border border-gray-100 px-2 py-1">
              <span className="text-gray-600 flex items-center gap-1">
                <ShieldCheck size={12} weight="fill" className="text-emerald-600" />
                Prompt Guard
              </span>
              <span className="font-mono text-gray-500">&lt; 60k tokens safe cap</span>
            </div>
          </div>

          {/* Hard Cutoff Banner if all accounts reached cap */}
          {stats.pool_cutoff_active && (
            <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-[11px] text-amber-800 flex items-start gap-1.5">
              <Warning size={14} weight="fill" className="shrink-0 mt-0.5 text-amber-600" />
              <div>
                <strong className="font-semibold">Pool Quota Exhausted:</strong> All {totalAcc} accounts reached safety limit today. AI calls paused; deterministic regex OCR is active.
              </div>
            </div>
          )}

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
