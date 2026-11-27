"use client";

import { useEffect, useState } from "react";
import {
  ArrowsClockwise,
  ArrowSquareOut,
  CheckCircle,
  Eye,
  EyeSlash,
  Key,
  Moon,
  Pause,
  Play,
  Plus,
  Robot,
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
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { GeminiAccountItem, GeminiQuotaStats } from "@/components/gemini-header-meter";
import { GeminiAnalyticsChart } from "@/components/gemini-analytics-chart";
import { GeminiTimelineCalendar } from "@/components/gemini-timeline-calendar";
import { GeminiQuotaRadarCard } from "@/components/gemini-quota-radar-card";
import { GeminiModelSwitcher } from "@/components/gemini-model-switcher";

interface NotificationItem {
  id: string;
  event_type: string;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
}

interface CopilotGovernanceSummary {
  policy: {
    enabled: boolean;
    shared_copilot_rpd_pct: number;
    shared_interactive_reserve_pct: number;
    staff_daily_turns: number;
    staff_daily_tokens: number;
    admin_daily_turns: number;
    admin_daily_tokens: number;
    max_tool_hops: number;
    max_input_tokens_per_turn: number;
  };
  pt_cycle_date: string;
  active_keys_count: number;
  shared_keys_count: number;
  dedicated_copilot_keys_count: number;
  dedicated_extraction_keys_count: number;
  total_fleet_rpd: number;
  copilot_rpd_limit: number;
  copilot_rpd_used: number;
  copilot_rpd_remaining: number;
  copilot_tokens_today: number;
  extraction_rpd_limit: number;
  extraction_rpd_used: number;
  extraction_tokens_today: number;
  shared_reserve_rpd: number;
  per_user_today: Array<{
    user_id: string;
    name: string;
    email: string;
    role: string;
    turns_today: number;
    llm_calls_today: number;
    tokens_today: number;
    excel_exports_today: number;
    daily_turn_limit: number;
    daily_token_limit: number;
  }>;
}

export default function SettingsAiEnginePage() {
  const [stats, setStats] = useState<GeminiQuotaStats | null>(null);
  const [modelAlerts, setModelAlerts] = useState<NotificationItem[]>([]);
  const [copilotGov, setCopilotGov] = useState<CopilotGovernanceSummary | null>(null);
  const [savingPolicy, setSavingPolicy] = useState(false);
  const [scopingId, setScopingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { toast } = useToast();

  // Add Key Form State
  const [newKey, setNewKey] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [newScope, setNewScope] = useState<"all" | "extraction_only" | "copilot_only">("all");
  const [showKey, setShowKey] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState("");

  // Testing & Deleting state
  const [testingIdx, setTestingIdx] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [pausingId, setPausingId] = useState<string | null>(null);
  const [timelineRefreshNonce, setTimelineRefreshNonce] = useState(0);

  async function handleTogglePause(keyId: string, currentPaused: boolean) {
    setPausingId(keyId);
    try {
      const res = await api<{ ok: boolean; is_paused: boolean; gemini: GeminiQuotaStats }>(
        `/settings/gemini/keys/${keyId}/toggle-pause`,
        {
          method: "POST",
          body: JSON.stringify({ paused: !currentPaused }),
        }
      );
      if (res?.ok) {
        toast(
          res.is_paused ? "Account put to rest (sleeping). Quota preserved." : "Account resumed to active fleet.",
          "info"
        );
        if (res.gemini) {
          setStats(res.gemini);
        } else {
          loadData();
        }
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to toggle account rest state.", "error");
    } finally {
      setPausingId(null);
    }
  }

  async function handleDismissAlert(notifId: string) {
    try {
      await api(`/notifications/${notifId}/read`, { method: "PATCH" });
      setModelAlerts((prev) => prev.filter((n) => n.id !== notifId));
      toast("Alert acknowledged and dismissed.", "info");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to dismiss alert.", "error");
    }
  }

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

    try {
      const notifRes = await api<{ notifications: NotificationItem[] }>("/notifications");
      if (notifRes?.notifications) {
        const unreadAlerts = notifRes.notifications.filter(
          (n) => n.event_type === "ai_model_alert" && !n.read_at
        );
        setModelAlerts(unreadAlerts);
      }
    } catch {
      // Ignore notification fetch errors
    }

    try {
      const govRes = await api<CopilotGovernanceSummary>("/settings/copilot-policy");
      if (govRes?.policy) {
        setCopilotGov(govRes);
      }
    } catch {
      // Non-admin or unavailable
    }
  }

  async function handleSaveCopilotPolicy(patch: Partial<CopilotGovernanceSummary["policy"]>) {
    if (!copilotGov) return;
    setSavingPolicy(true);
    try {
      const updated = await api<CopilotGovernanceSummary>("/settings/copilot-policy", {
        method: "PUT",
        body: JSON.stringify(patch),
      });
      setCopilotGov(updated);
      toast("Copilot workload governance policy saved.", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to save Copilot policy.", "error");
    } finally {
      setSavingPolicy(false);
    }
  }

  async function handleChangeWorkloadScope(keyId: string, workload_scope: "all" | "extraction_only" | "copilot_only") {
    setScopingId(keyId);
    try {
      const res = await api<{ ok: boolean; gemini: GeminiQuotaStats }>(`/settings/gemini/keys/${keyId}/workload-scope`, {
        method: "POST",
        body: JSON.stringify({ workload_scope }),
      });
      if (res?.gemini) setStats(res.gemini);
      const govRes = await api<CopilotGovernanceSummary>("/settings/copilot-policy");
      setCopilotGov(govRes);
      toast("Key workload scope updated.", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to update key workload scope.", "error");
    } finally {
      setScopingId(null);
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
          workload_scope: newScope,
        }),
      });

      if (res?.ok) {
        toast(res.message || "Key validated live with Google and added to pool!", "success");
        setNewKey("");
        setNewLabel("");
        setNewScope("all");
        if (res.gemini) {
          setStats(res.gemini);
        }
        loadData();
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
        setTimelineRefreshNonce((n) => n + 1);
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Test probe failed.", "error");
    } finally {
      setTestingIdx(null);
    }
  }

  const accounts = stats?.accounts || [];
  const activeIdx = stats?.active_account_index ?? 0;
  const poolRpdUsed = stats?.pool_rpd_used ?? 0;
  const poolRpdLimit = stats?.pool_rpd_limit ?? accounts.length * 480;
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
              Multi-account rate-limiting guard. All API keys are validated live and managed securely in Postgres via Settings.
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
                <span className="text-2xl font-bold text-gray-900">{accounts.length} / 16</span>
                <span className="text-xs text-gray-500">accounts</span>
              </div>
              <span className="mt-2 text-[11px] text-gray-500 block">
                Managed in Settings → AI Engine (DB-backed)
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
                <span
                  className="text-sm font-bold font-mono text-gray-900 break-all"
                  title={stats?.model || "gemini-3.1-flash-lite"}
                >
                  {stats?.model || "gemini-3.1-flash-lite"}
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

        {/* Actionable Model Alert Banner if shifts detected */}
        {modelAlerts.length > 0 && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 shadow-xs grid gap-3">
            {modelAlerts.map((alert) => (
              <div key={alert.id} className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <WarningOctagon size={20} weight="fill" className="text-amber-600 mt-0.5 shrink-0" />
                  <div>
                    <h3 className="text-sm font-bold text-amber-900">{alert.title}</h3>
                    <p className="text-xs text-amber-800 mt-1 whitespace-pre-line leading-relaxed font-mono">
                      {alert.body}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    className="h-8 text-xs border-amber-400 text-amber-900 hover:bg-amber-100"
                    onClick={() => {
                      const switcher = document.getElementById("ai-model-switcher-section");
                      switcher?.scrollIntoView({ behavior: "smooth" });
                    }}
                  >
                    Review & Switch Models
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 text-xs text-amber-800 hover:text-amber-950"
                    onClick={() => handleDismissAlert(alert.id)}
                  >
                    Acknowledge & Dismiss
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Autonomous 20-Minute Quota Radar Sentinel Card */}
        <GeminiQuotaRadarCard onRefreshData={loadData} />

        {/* Model Activation & Parallel Fleet Controls */}
        <div id="ai-model-switcher-section">
          <GeminiModelSwitcher
            onConfigChanged={(updatedStats) => {
              if (updatedStats) setStats(updatedStats);
              else loadData();
            }}
            onModelTested={() => setTimelineRefreshNonce((n) => n + 1)}
          />
        </div>

        {/* Card: Add New Gemini API Key with Mandatory Live Google Probe Gate */}
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

              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Workload Isolation Scope
                </label>
                <Select
                  value={newScope}
                  onChange={(e) => setNewScope(e.target.value as "all" | "extraction_only" | "copilot_only")}
                  disabled={validating}
                  className="text-xs"
                >
                  <option value="all">Shared Fleet (PDF Extraction + Copilot Ring-Fenced)</option>
                  <option value="extraction_only">Extraction Only (Reserved 100% for PDF Uploads)</option>
                  <option value="copilot_only">Copilot Only (Dedicated 100% to AI Chat &amp; Excel)</option>
                </Select>
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
                  Adds +480 RPD / +13 RPM safe capacity upon confirmation.
                </span>
              </div>
            </form>
          </div>
        </Card>

        {/* Card: Configured Accounts & Quota Health Table */}
        <Card>
          <div className="p-5">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div>
                <h2 className="text-base font-bold text-gray-900">Configured Fleet Accounts & Quota Health</h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  Individual account state, daily call counters, sliding-minute metrics, and direct active/rest toggles.
                </p>
              </div>
              <Badge variant="default" className="font-mono text-xs">
                {accounts.length} Configured / {poolRpdLimit} RPD Fleet Cap
              </Badge>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50/50 text-gray-500 font-semibold">
                    <th className="py-2.5 px-3">Account</th>
                    <th className="py-2.5 px-3">Source</th>
                    <th className="py-2.5 px-3">Workload Scope</th>
                    <th className="py-2.5 px-3">Masked Key</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Daily Usage (RPD)</th>
                    <th className="py-2.5 px-3">Burst (RPM)</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {accounts.map((acc, idx) => {
                    const isPaused = !!acc.is_paused;
                    const rpdPct = acc.rpd_limit > 0 ? Math.min(100, Math.round((acc.rpd_used / acc.rpd_limit) * 100)) : 0;

                    return (
                      <tr
                        key={acc.id}
                        className={`transition-colors ${
                          isPaused ? "bg-gray-50/40 text-gray-500" : "hover:bg-gray-50/80"
                        }`}
                      >
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2">
                            <span
                              className={`size-2 rounded-full shrink-0 ${
                                isPaused
                                  ? "bg-amber-400"
                                  : acc.status_color === "green"
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
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-100 text-blue-800">
                            Settings (DB)
                          </span>
                        </td>

                        <td className="py-3 px-3">
                          <select
                            value={acc.workload_scope || "all"}
                            disabled={scopingId === acc.id}
                            onChange={(e) =>
                              handleChangeWorkloadScope(
                                acc.id,
                                e.target.value as "all" | "extraction_only" | "copilot_only"
                              )
                            }
                            className="rounded border border-gray-200 bg-white px-2 py-1 text-[11px] font-medium text-gray-800 focus:outline-none focus:border-gray-900"
                          >
                            <option value="all">Shared (All)</option>
                            <option value="extraction_only">Extraction Only</option>
                            <option value="copilot_only">Copilot Only</option>
                          </select>
                        </td>

                        <td className="py-3 px-3 font-mono text-[11px] text-gray-600">
                          {acc.masked_key || "—"}
                        </td>

                        <td className="py-3 px-3">
                          {isPaused ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800 flex items-center gap-1 w-fit">
                              <Moon size={11} weight="fill" /> Off · Paused
                            </span>
                          ) : (
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex items-center gap-1 w-fit ${
                                acc.status_color === "green"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : acc.status_color === "amber"
                                  ? "bg-amber-100 text-amber-800"
                                  : acc.status_color === "red"
                                  ? "bg-rose-100 text-rose-800"
                                  : "bg-gray-200 text-gray-700"
                              }`}
                            >
                              <CheckCircle size={11} weight="fill" /> Active
                            </span>
                          )}
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
                            <button
                              type="button"
                              disabled={testingIdx === idx || isPaused}
                              onClick={() => handleTestKey(idx)}
                              title={isPaused ? "Turn on this key to test" : "Test this API key live against Google"}
                              className="text-[11px] font-medium text-gray-700 hover:text-gray-900 border border-gray-200 hover:bg-white px-2 py-1 rounded transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
                            >
                              <ArrowsClockwise size={12} className={testingIdx === idx ? "animate-spin" : ""} />
                              {testingIdx === idx ? "Verifying..." : "Verify Key"}
                            </button>

                            {/* Independent On/Off (Turn Off / Turn On) button for ANY key */}
                            <button
                              type="button"
                              disabled={pausingId === acc.id}
                              onClick={() => handleTogglePause(acc.id, isPaused)}
                              title={isPaused ? "Turn on this key into the active fleet" : "Turn off (rest) this key"}
                              className={`text-[11px] font-semibold border px-2.5 py-1 rounded transition-colors cursor-pointer flex items-center gap-1 ${
                                isPaused
                                  ? "bg-emerald-600 border-emerald-600 text-white hover:bg-emerald-700"
                                  : "bg-white border-gray-200 text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                              }`}
                            >
                              {pausingId === acc.id ? (
                                "..."
                              ) : isPaused ? (
                                <>
                                  <Play size={11} weight="fill" /> Turn On
                                </>
                              ) : (
                                <>
                                  <Pause size={11} weight="fill" /> Turn Off
                                </>
                              )}
                            </button>

                            <button
                              type="button"
                              disabled={deletingId === acc.id}
                              onClick={() => handleDeleteKey(acc.id, acc.label)}
                              title="Remove key from database and pool"
                              className="text-gray-400 hover:text-rose-600 p-1 rounded hover:bg-rose-50 transition-colors cursor-pointer"
                            >
                              <Trash size={14} weight="bold" />
                            </button>
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

        {/* Card: Copilot Workload Ring-Fence & Per-User Usage Governance */}
        {copilotGov && (
          <Card>
            <div className="p-5 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-gray-100">
                <div>
                  <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                    <Robot size={18} weight="fill" className="text-gray-900" />
                    AI Copilot Workload Ring-Fence &amp; Per-User Quota Governance
                  </h2>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Dynamically scales across {copilotGov.active_keys_count} active key(s) ({copilotGov.total_fleet_rpd.toLocaleString()} total RPD). Dedicated Copilot keys bypass shared % caps; batch uploads yield politely to live chats.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant={copilotGov.policy.enabled ? "secondary" : "primary"}
                    loading={savingPolicy}
                    onClick={() => handleSaveCopilotPolicy({ enabled: !copilotGov.policy.enabled })}
                  >
                    {copilotGov.policy.enabled ? "Pause Copilot (Extraction-Only)" : "Resume AI Copilot"}
                  </Button>
                </div>
              </div>

              {/* Dynamic N-Key Workload Split Bar */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                <div className="rounded-lg border border-gray-200 bg-gray-50/70 p-3">
                  <div className="text-[11px] font-semibold text-gray-500 uppercase">PDF Extraction Budget</div>
                  <div className="mt-1 text-lg font-bold font-mono text-gray-900">
                    {copilotGov.extraction_rpd_used.toLocaleString()} / {copilotGov.extraction_rpd_limit.toLocaleString()} RPD
                  </div>
                  <div className="text-[11px] text-gray-500 mt-0.5">
                    {copilotGov.extraction_tokens_today.toLocaleString()} tokens today · {copilotGov.dedicated_extraction_keys_count} dedicated key(s)
                  </div>
                </div>

                <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-3">
                  <div className="text-[11px] font-semibold text-blue-700 uppercase">Copilot Chat Budget</div>
                  <div className="mt-1 text-lg font-bold font-mono text-gray-900">
                    {copilotGov.copilot_rpd_used.toLocaleString()} / {copilotGov.copilot_rpd_limit.toLocaleString()} RPD
                  </div>
                  <div className="text-[11px] text-blue-800 mt-0.5">
                    {copilotGov.copilot_tokens_today.toLocaleString()} tokens today · {copilotGov.dedicated_copilot_keys_count} dedicated key(s)
                  </div>
                </div>

                <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
                  <div className="text-[11px] font-semibold text-amber-800 uppercase">Interactive Reserve Floor</div>
                  <div className="mt-1 text-lg font-bold font-mono text-gray-900">
                    {copilotGov.shared_reserve_rpd.toLocaleString()} RPD
                  </div>
                  <div className="text-[11px] text-amber-900 mt-0.5">
                    Bulk batches pause at floor on {copilotGov.shared_keys_count} shared key(s)
                  </div>
                </div>
              </div>

              {/* Editable Policy Controls */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
                <div>
                  <label className="text-[11px] font-semibold text-gray-600 block mb-1">
                    Shared Copilot Cap (%)
                  </label>
                  <Input
                    type="number"
                    min={5}
                    max={80}
                    value={copilotGov.policy.shared_copilot_rpd_pct}
                    onChange={(e) =>
                      setCopilotGov((prev) =>
                        prev
                          ? { ...prev, policy: { ...prev.policy, shared_copilot_rpd_pct: Number(e.target.value) } }
                          : prev
                      )
                    }
                    className="h-8 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-gray-600 block mb-1">
                    Batch Reserve Floor (%)
                  </label>
                  <Input
                    type="number"
                    min={0}
                    max={40}
                    value={copilotGov.policy.shared_interactive_reserve_pct}
                    onChange={(e) =>
                      setCopilotGov((prev) =>
                        prev
                          ? {
                              ...prev,
                              policy: { ...prev.policy, shared_interactive_reserve_pct: Number(e.target.value) },
                            }
                          : prev
                      )
                    }
                    className="h-8 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-gray-600 block mb-1">
                    Staff Turns / Day
                  </label>
                  <Input
                    type="number"
                    min={5}
                    max={500}
                    value={copilotGov.policy.staff_daily_turns}
                    onChange={(e) =>
                      setCopilotGov((prev) =>
                        prev ? { ...prev, policy: { ...prev.policy, staff_daily_turns: Number(e.target.value) } } : prev
                      )
                    }
                    className="h-8 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-gray-600 block mb-1">
                    Admin Turns / Day
                  </label>
                  <Input
                    type="number"
                    min={10}
                    max={1000}
                    value={copilotGov.policy.admin_daily_turns}
                    onChange={(e) =>
                      setCopilotGov((prev) =>
                        prev ? { ...prev, policy: { ...prev.policy, admin_daily_turns: Number(e.target.value) } } : prev
                      )
                    }
                    className="h-8 text-xs font-mono"
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <Button
                  type="button"
                  size="sm"
                  loading={savingPolicy}
                  onClick={() => handleSaveCopilotPolicy(copilotGov.policy)}
                >
                  Save Copilot Governance Policy
                </Button>
              </div>

              {/* Per-User Today Table */}
              {copilotGov.per_user_today.length > 0 && (
                <div className="overflow-x-auto border border-gray-100 rounded-lg">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead className="bg-gray-50 text-gray-500 font-semibold border-b border-gray-200">
                      <tr>
                        <th className="py-2 px-3">User</th>
                        <th className="py-2 px-3">Role</th>
                        <th className="py-2 px-3">Chats Today</th>
                        <th className="py-2 px-3">LLM Hops</th>
                        <th className="py-2 px-3">Tokens Used</th>
                        <th className="py-2 px-3">Excel Exports</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {copilotGov.per_user_today.map((u) => (
                        <tr key={u.user_id}>
                          <td className="py-2 px-3 font-medium text-gray-900">{u.name}</td>
                          <td className="py-2 px-3 font-mono text-[11px] text-gray-500">{u.role}</td>
                          <td className="py-2 px-3 font-mono">
                            {u.turns_today} / {u.daily_turn_limit}
                          </td>
                          <td className="py-2 px-3 font-mono">{u.llm_calls_today}</td>
                          <td className="py-2 px-3 font-mono">
                            {u.tokens_today.toLocaleString()} / {u.daily_token_limit.toLocaleString()}
                          </td>
                          <td className="py-2 px-3 font-mono">{u.excel_exports_today}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Live Timeline, Pacific Time Cycle Countdown & Minute-Level Token Activity */}
        <GeminiTimelineCalendar refreshNonce={timelineRefreshNonce} />

        {/* Google AI Studio Rate Limit Parity & Sliding Metric History */}
        <GeminiAnalyticsChart />

        {/* Card: Multi-Account Safety Guard Policies */}
        <Card>
          <div className="p-5">
            <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <ShieldCheck size={18} weight="fill" className="text-emerald-600" />
              Multi-Account Safety Guard Policies & Non-Bannable Architecture
            </h2>
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
              <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-3">
                <span className="font-bold text-gray-900 block mb-1">1. 480 RPD Hard Cap</span>
                <p className="text-gray-600 leading-relaxed text-[11px]">
                  Each endpoint stops sending requests at 480 calls/day, strictly below Google's 500 daily quota line to eliminate ban risks.
                </p>
              </div>

              <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-3">
                <span className="font-bold text-gray-900 block mb-1">2. 13 RPM Burst Guard</span>
                <p className="text-gray-600 leading-relaxed text-[11px]">
                  Sliding 60-second window throttles at 13 requests/min with adaptive breathing delays. Auto-switches across parallel slots during upload bursts.
                </p>
              </div>

              <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-3">
                <span className="font-bold text-gray-900 block mb-1">3. 200k TPM Token Guard</span>
                <p className="text-gray-600 leading-relaxed text-[11px]">
                  Calculates input and output token consumption in real-time. Over-capacity documents automatically downgrade to preserve quota.
                </p>
              </div>

              <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-3">
                <span className="font-bold text-gray-900 block mb-1">4. Fail-Closed Invariant</span>
                <p className="text-gray-600 leading-relaxed text-[11px]">
                  If all Gemini accounts reach their cap or go offline, PDF quotation uploads fail-closed to protect against unverified OCR hallucinations.
                </p>
              </div>
            </div>
          </div>
        </Card>
      </section>
    </AppShell>
  );
}
