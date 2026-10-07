"use client";

import { useEffect, useState } from "react";
import {
  ArrowsClockwise,
  ArrowSquareOut,
  CheckCircle,
  Eye,
  EyeSlash,
  Key,
  Plus,
  ShieldCheck,
  Sparkle,
  Trash,
  Warning,
  WarningCircle,
  WarningOctagon,
} from "@phosphor-icons/react";
import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { GeminiAccountItem, GeminiQuotaStats } from "@/components/gemini-header-meter";

export default function SettingsAiEnginePage() {
  const [stats, setStats] = useState<GeminiQuotaStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { toast } = useToast();

  // Add Key Form State
  const [newKey, setNewKey] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState("");

  // Testing & Deleting state
  const [testingIdx, setTestingIdx] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [switchingIdx, setSwitchingIdx] = useState<number | null>(null);

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      const res = await api<{ gemini?: GeminiQuotaStats }>("/settings/limits");
      if (res?.gemini) {
        setStats(res.gemini);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Gemini fleet settings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleAddKey(e: React.FormEvent) {
    e.preventDefault();
    setValidationError("");
    const trimmedKey = newKey.trim();
    if (!trimmedKey) {
      setValidationError("Please paste an API key.");
      return;
    }
    if (trimmedKey.length < 20) {
      setValidationError("Invalid key format. Google API keys are at least 20 characters.");
      return;
    }

    setValidating(true);
    try {
      const res = await api<{ ok: boolean; message: string; gemini: GeminiQuotaStats }>("/settings/gemini/keys", {
        method: "POST",
        body: JSON.stringify({
          key: trimmedKey,
          label: newLabel.trim() || undefined,
        }),
      });

      if (res?.ok) {
        toast(res.message || "Key validated live with Google and added to pool!", "success");
        setNewKey("");
        setNewLabel("");
        if (res.gemini) {
          setStats(res.gemini);
        } else {
          loadData();
        }
      }
    } catch (err) {
      setValidationError(err instanceof Error ? err.message : "Validation failed. Google rejected this key.");
    } finally {
      setValidating(false);
    }
  }

  async function handleDeleteKey(keyId: string, label: string) {
    if (!confirm(`Are you sure you want to remove '${label}' from the active pool?`)) {
      return;
    }
    setDeletingId(keyId);
    try {
      const res = await api<{ ok: boolean; message: string; gemini: GeminiQuotaStats }>(
        `/settings/gemini/keys/${keyId}`,
        { method: "DELETE" }
      );
      if (res?.ok) {
        toast(res.message || "Key removed from pool.", "info");
        if (res.gemini) {
          setStats(res.gemini);
        } else {
          loadData();
        }
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not delete key.", "error");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleTestKey(idx: number) {
    setTestingIdx(idx);
    try {
      const res = await api<{ gemini: GeminiQuotaStats }>("/settings/gemini/probe", {
        method: "POST",
        body: JSON.stringify({ account_index: idx }),
      });
      if (res?.gemini) {
        setStats(res.gemini);
        const acc = res.gemini.accounts?.[idx];
        if (acc?.status === "ready") {
          toast(`Account ${idx + 1} verified: HTTP 200 OK`, "success");
        } else {
          toast(`Account ${idx + 1} status: ${acc?.status_label || acc?.status}`, "warning");
        }
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Test probe failed.", "error");
    } finally {
      setTestingIdx(null);
    }
  }

  async function handleSetActive(idx: number) {
    setSwitchingIdx(idx);
    try {
      const res = await api<{ ok: boolean; gemini: GeminiQuotaStats }>("/settings/gemini/switch-account", {
        method: "POST",
        body: JSON.stringify({ account_index: idx }),
      });
      if (res?.gemini) {
        setStats(res.gemini);
        toast(`Active account switched to Account ${idx + 1}`, "success");
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to switch active account.", "error");
    } finally {
      setSwitchingIdx(null);
    }
  }

  const accounts = stats?.accounts || [];
  const activeIdx = stats?.active_account_index ?? 0;
  const poolRpdUsed = stats?.pool_rpd_used ?? 0;
  const poolRpdLimit = stats?.pool_rpd_limit ?? accounts.length * 440;
  const poolPercent = poolRpdLimit > 0 ? Math.min(100, Math.round((poolRpdUsed / poolRpdLimit) * 100)) : 0;

  return (
    <AppShell>
      <section className="grid gap-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)] flex items-center gap-2.5">
              <Sparkle size={28} weight="fill" className="text-emerald-500" />
              Gemini AI Fleet Management
            </h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">
              Multi-account rate-limiting guard. Primary key loaded from <code className="font-mono text-gray-700 bg-gray-100 px-1 py-0.5 rounded">.env</code>; additional accounts validated live and saved in Settings.
            </p>
          </div>
          <Button
            variant="secondary"
            icon={<ArrowsClockwise size={16} weight="bold" className={loading ? "animate-spin" : ""} />}
            onClick={loadData}
          >
            Refresh
          </Button>
        </div>

        <SettingsNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        {/* Fleet Quota Overview Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <div className="p-4">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block">Configured Accounts</span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-gray-900">{accounts.length} / 6</span>
                <span className="text-xs text-gray-500">accounts</span>
              </div>
              <span className="mt-2 text-[11px] text-gray-500 block">
                1 from .env, {Math.max(0, accounts.length - 1)} added manually
              </span>
            </div>
          </Card>

          <Card>
            <div className="p-4">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block">Daily Safe Quota (RPD)</span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-gray-900">{poolRpdUsed} / {poolRpdLimit}</span>
                <span className="text-xs text-gray-500 font-mono">({poolPercent}%)</span>
              </div>
              <div className="mt-2 h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    poolPercent >= 90 ? "bg-rose-500" : poolPercent >= 70 ? "bg-amber-500" : "bg-emerald-500"
                  }`}
                  style={{ width: `${poolPercent}%` }}
                />
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-4">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block">Active Lite Model</span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-base font-bold font-mono text-gray-900 truncate">
                  {stats?.model || "gemini-3.1-flash-lite-preview"}
                </span>
              </div>
              <span className="mt-2 text-[11px] text-emerald-600 font-medium flex items-center gap-1">
                <CheckCircle size={13} weight="fill" />
                High-quota Lite model active
              </span>
            </div>
          </Card>

          <Card>
            <div className="p-4">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block">Prompt Token Guard</span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-gray-900">60,000</span>
                <span className="text-xs text-gray-500">tokens max</span>
              </div>
              <span className="mt-2 text-[11px] text-gray-500 block">
                Auto-truncates oversize prompt layers
              </span>
            </div>
          </Card>
        </div>

        {/* Card 1: Add New Gemini API Key with Mandatory Live Google Probe Gate */}
        <Card>
          <div className="p-5">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div>
                <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                  <Key size={18} weight="fill" className="text-emerald-600" />
                  Add Gemini API Key (Live Pre-Flight Verification)
                </h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  Paste a key from Google AI Studio. The system tests it with a live Google API probe before saving.
                </p>
              </div>
              <a
                href="https://aistudio.google.com/apikey"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 px-2.5 py-1.5 rounded-lg transition-colors"
              >
                Get Free Key at AI Studio
                <ArrowSquareOut size={13} weight="bold" />
              </a>
            </div>

            <form onSubmit={handleAddKey} className="mt-4 grid gap-3 max-w-2xl">
              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Google Gemini API Key <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <Input
                    type={showKey ? "text" : "password"}
                    value={newKey}
                    onChange={(e) => setNewKey(e.target.value)}
                    placeholder="Paste Gemini API key (e.g. AIzaSy... or AQ...)"
                    className="font-mono text-xs pr-10"
                    disabled={validating}
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    tabIndex={-1}
                  >
                    {showKey ? <EyeSlash size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <span className="text-[11px] text-gray-400 mt-1 block">
                  Keys are stored encrypted in Postgres and loaded into the active round-robin engine.
                </span>
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Account Label (Optional)
                </label>
                <Input
                  type="text"
                  value={newLabel}
                  onChange={(e) => setNewLabel(e.target.value)}
                  placeholder={`Account ${accounts.length + 1} (e.g. Personal Project / Mahmud)`}
                  className="text-xs"
                  disabled={validating}
                />
              </div>

              {validationError && (
                <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-700 flex items-start gap-2">
                  <WarningOctagon size={16} weight="fill" className="shrink-0 text-rose-600 mt-0.5" />
                  <div>
                    <strong>Verification Failed:</strong> {validationError}
                  </div>
                </div>
              )}

              <div className="flex items-center gap-3 pt-2">
                <Button
                  type="submit"
                  loading={validating}
                  icon={<Plus size={16} weight="bold" />}
                  disabled={!newKey.trim() || validating}
                >
                  {validating ? "Validating with Google API..." : "Validate & Confirm Key"}
                </Button>
                <span className="text-[11px] text-gray-500">
                  Adds +440 RPD / +10 RPM safe capacity upon confirmation.
                </span>
              </div>
            </form>
          </div>
        </Card>

        {/* Card 2: Configured Accounts & Quota Health Table */}
        <Card>
          <div className="p-5">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div>
                <h2 className="text-base font-bold text-gray-900">Configured Fleet Accounts & Quota Health</h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  Individual account state, daily call counters, sliding-minute metrics, and actions.
                </p>
              </div>
              <Badge variant="default" className="font-mono text-xs">
                {accounts.length} Active / {stats?.pool_rpd_limit ?? accounts.length * 440} RPD Fleet Cap
              </Badge>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50/50 text-gray-500 font-semibold">
                    <th className="py-2.5 px-3">Account</th>
                    <th className="py-2.5 px-3">Source</th>
                    <th className="py-2.5 px-3">Masked Key</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Daily Usage (RPD)</th>
                    <th className="py-2.5 px-3">Burst (RPM)</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {accounts.map((acc, idx) => {
                    const isActive = idx === activeIdx;
                    const rpdPct = Math.min(100, Math.round((acc.rpd_used / acc.rpd_limit) * 100));

                    return (
                      <tr
                        key={acc.id}
                        className={`hover:bg-gray-50/80 transition-colors ${
                          isActive ? "bg-emerald-50/30 font-medium" : ""
                        }`}
                      >
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2">
                            <span
                              className={`size-2 rounded-full shrink-0 ${
                                acc.status_color === "green"
                                  ? "bg-emerald-500"
                                  : acc.status_color === "amber"
                                  ? "bg-amber-500"
                                  : acc.status_color === "red"
                                  ? "bg-rose-500"
                                  : "bg-gray-400"
                              }`}
                            />
                            <div>
                              <div className="font-semibold text-gray-900">{acc.label}</div>
                              {acc.last_switch_reason && (
                                <div className="text-[10px] text-gray-400 truncate max-w-xs">
                                  {acc.last_switch_reason}
                                </div>
                              )}
                            </div>
                          </div>
                        </td>

                        <td className="py-3 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                              acc.source === "env"
                                ? "bg-purple-100 text-purple-800"
                                : "bg-blue-100 text-blue-800"
                            }`}
                          >
                            {acc.source === "env" ? ".env (Primary)" : "Manual"}
                          </span>
                        </td>

                        <td className="py-3 px-3 font-mono text-[11px] text-gray-600">
                          {acc.masked_key || "—"}
                        </td>

                        <td className="py-3 px-3">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                              acc.status_color === "green"
                                ? "bg-emerald-100 text-emerald-800"
                                : acc.status_color === "amber"
                                ? "bg-amber-100 text-amber-800"
                                : acc.status_color === "red"
                                ? "bg-rose-100 text-rose-800"
                                : "bg-gray-200 text-gray-700"
                            }`}
                          >
                            {acc.status_label || acc.status}
                          </span>
                        </td>

                        <td className="py-3 px-3">
                          <div className="w-28">
                            <div className="flex justify-between text-[10px] text-gray-600 font-mono mb-1">
                              <span>{acc.rpd_used} / {acc.rpd_limit}</span>
                              <span>{rpdPct}%</span>
                            </div>
                            <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  rpdPct >= 90 ? "bg-rose-500" : rpdPct >= 70 ? "bg-amber-500" : "bg-emerald-500"
                                }`}
                                style={{ width: `${rpdPct}%` }}
                              />
                            </div>
                          </div>
                        </td>

                        <td className="py-3 px-3 font-mono text-[11px] text-gray-600">
                          {acc.rpm_used} / {acc.rpm_limit}
                        </td>

                        <td className="py-3 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {isActive ? (
                              <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-2 py-1 rounded">
                                Active
                              </span>
                            ) : (
                              <button
                                type="button"
                                disabled={switchingIdx !== null}
                                onClick={() => handleSetActive(idx)}
                                className="text-[11px] font-medium text-gray-700 hover:text-gray-900 border border-gray-200 hover:bg-white px-2 py-1 rounded transition-colors cursor-pointer"
                              >
                                {switchingIdx === idx ? "..." : "Make Active"}
                              </button>
                            )}

                            <button
                              type="button"
                              disabled={testingIdx === idx}
                              onClick={() => handleTestKey(idx)}
                              title="Test this API key live against Google"
                              className="text-[11px] font-medium text-gray-700 hover:text-gray-900 border border-gray-200 hover:bg-white px-2 py-1 rounded transition-colors cursor-pointer flex items-center gap-1"
                            >
                              <ArrowsClockwise size={12} className={testingIdx === idx ? "animate-spin" : ""} />
                              {testingIdx === idx ? "Testing..." : "Test"}
                            </button>

                            {acc.source === "manual" ? (
                              <button
                                type="button"
                                disabled={deletingId === acc.id}
                                onClick={() => handleDeleteKey(acc.id, acc.label)}
                                title="Remove key from database and pool"
                                className="text-gray-400 hover:text-rose-600 p-1 rounded hover:bg-rose-50 transition-colors cursor-pointer"
                              >
                                <Trash size={14} weight="bold" />
                              </button>
                            ) : (
                              <span
                                title="Primary key defined in .env cannot be deleted from the UI"
                                className="text-gray-300 p-1 cursor-not-allowed"
                              >
                                <Trash size={14} weight="regular" />
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </Card>

        {/* Card 3: Multi-Account Safety Guard Policies */}
        <Card>
          <div className="p-5">
            <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <ShieldCheck size={18} weight="fill" className="text-emerald-600" />
              Multi-Account Safety Guard Policies & Non-Bannable Architecture
            </h2>
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
              <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-3">
                <span className="font-bold text-gray-900 block mb-1">1. 440 RPD Hard Cap</span>
                <p className="text-gray-600 leading-relaxed text-[11px]">
                  Each account stops sending requests at 440 calls/day, leaving a 60-call buffer under Google's 500 daily quota to avoid hard account bans.
                </p>
              </div>

              <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-3">
                <span className="font-bold text-gray-900 block mb-1">2. 10 RPM Burst Guard</span>
                <p className="text-gray-600 leading-relaxed text-[11px]">
                  Sliding 60-second window throttles at 10 requests/min, leaving 5 RPM buffer. Auto-switches to standby accounts during upload spikes.
                </p>
              </div>

              <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-3">
                <span className="font-bold text-gray-900 block mb-1">3. 100k TPM Token Guard</span>
                <p className="text-gray-600 leading-relaxed text-[11px]">
                  Accumulates input & output tokens per minute. Caps at 100,000 tokens/min (out of 250k Google limit) to prevent token exhaustion.
                </p>
              </div>

              <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-3">
                <span className="font-bold text-gray-900 block mb-1">4. Zero-Downtime Fallback</span>
                <p className="text-gray-600 leading-relaxed text-[11px]">
                  If all accounts reach 440 RPD (up to 2,640 calls/day), AI calls freeze completely and deterministic regex/OCR extracts values without errors.
                </p>
              </div>
            </div>
          </div>
        </Card>
      </section>
    </AppShell>
  );
}
