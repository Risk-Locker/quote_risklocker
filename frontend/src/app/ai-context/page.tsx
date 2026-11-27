"use client";

import { useEffect, useState } from "react";
import {
  ArrowsClockwise,
  Brain,
  Buildings,
  CheckCircle,
  ChatCircleDots,
  Copy,
  Sparkle,
  Star,
  TerminalWindow,
  Database,
  Lightning,
  ShieldCheck,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { GuidedTour } from "@/components/guided-tour";
import { GeminiQuotaInfoButton } from "@/components/gemini-quota-meter";
import { api } from "@/lib/api";

type AIContextData = {
  gemini: {
    active: boolean;
    model: string;
    key_count: number;
    rpm_limit?: number;
    rpm_used?: number;
    rpd_limit?: number;
    rpd_used?: number;
    rpd_remaining?: number;
    percent_rpd_remaining?: number;
  };
  summary_stats?: {
    active_companies_count: number;
    benefit_concepts_count: number;
    field_aliases_count: number;
    saved_records_count: number;
    total_sessions_count: number;
  };
  companies: Array<{
    id: string;
    name: string;
    code: string;
    aliases: string[];
    aliases_count: number;
    has_packages: boolean;
  }>;
  benefit_concepts: Array<{
    id: string;
    key: string;
    name: string;
    category: string;
    aliases_count: number;
  }>;
  field_aliases: Array<{
    field_name: string;
    aliases: string[];
    count: number;
  }>;
  live_system_prompt: string;
};

type AIMemoryItem = {
  id: string;
  field_name: string;
  original_value: string;
  corrected_value: string;
  insurance_company: string;
  created_at: string | null;
};

type AIMemoryData = {
  total_memories: number;
  summary_by_field: Array<{ field: string; count: number }>;
  items: AIMemoryItem[];
};

type ActiveTab = "chat" | "learned" | "summary" | "companies" | "concepts" | "prompt";

export default function AIContextPage() {
  const [data, setData] = useState<AIContextData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<ActiveTab>("chat");
  const [copied, setCopied] = useState(false);
  const [promptOverride, setPromptOverride] = useState("");
  const [promptSaving, setPromptSaving] = useState(false);
  const [promptSaved, setPromptSaved] = useState(false);
  const [canEditPrompt, setCanEditPrompt] = useState(false);

  // AI Learned Correction Memory State
  const [memoryData, setMemoryData] = useState<AIMemoryData | null>(null);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memorySearch, setMemorySearch] = useState("");
  const [memoryFieldFilter, setMemoryFieldFilter] = useState("all");

  const filteredMemories = (memoryData?.items || []).filter((item) => {
    if (memoryFieldFilter !== "all" && item.field_name !== memoryFieldFilter) return false;
    if (!memorySearch.trim()) return true;
    const q = memorySearch.toLowerCase();
    return (
      item.field_name.toLowerCase().includes(q) ||
      item.original_value.toLowerCase().includes(q) ||
      item.corrected_value.toLowerCase().includes(q) ||
      item.insurance_company.toLowerCase().includes(q)
    );
  });

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      const res = await api<AIContextData>("/settings/ai-context");
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load AI context.");
    } finally {
      setLoading(false);
    }
  }

  async function loadPrompt() {
    try {
      const res = await api<{ override: string; effective_prompt: string; is_override_active: boolean }>("/settings/ai-prompt");
      setPromptOverride(res.override || "");
      setData((prev) => (prev ? { ...prev, live_system_prompt: res.effective_prompt } : prev));
    } catch {
      // Best effort
    }
  }

  async function loadCapabilities() {
    try {
      const res = await api<{ role: string }>("/auth/me");
      setCanEditPrompt(res.role === "admin" || res.role === "super_admin");
    } catch {
      setCanEditPrompt(false);
    }
  }

  async function loadMemory() {
    setMemoryLoading(true);
    try {
      const res = await api<AIMemoryData>("/settings/ai-memory");
      setMemoryData(res);
    } catch (err) {
      console.error("Failed to load AI memory:", err);
    } finally {
      setMemoryLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    loadPrompt();
    loadCapabilities();
    loadMemory();
  }, []);

  async function savePrompt() {
    setPromptSaving(true);
    setPromptSaved(false);
    setError("");
    try {
      const res = await api<{ override: string; is_override_active: boolean }>("/settings/ai-prompt", {
        method: "PUT",
        body: JSON.stringify({ text: promptOverride }),
      });
      setPromptOverride(res.override || "");
      setPromptSaved(true);
      setTimeout(() => setPromptSaved(false), 2000);
      await loadPrompt();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save the AI system prompt.");
    } finally {
      setPromptSaving(false);
    }
  }

  async function resetPrompt() {
    setPromptOverride("");
    await savePrompt();
  }

  function copyPrompt() {
    if (!data?.live_system_prompt) return;
    navigator.clipboard.writeText(data.live_system_prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (loading && !data) {
    return (
      <AppShell>
        <PageLoading />
      </AppShell>
    );
  }

  const gemini = data?.gemini;
  const summary = data?.summary_stats;

  return (
    <AppShell>
      <div className="grid gap-6 w-full pb-12">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-[var(--font-manrope)] text-[28px] font-bold text-[var(--rl-text-strong)]">
              AI Grounding & Knowledge
            </h1>
            <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
              Lightweight AI grounding assistant and real database context inspection with zero hallucination.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <GuidedTour
              storageKey="tour:ai-context"
              title="AI Grounding & Knowledge"
              description="Ask lightweight questions to the grounding assistant, inspect real insurer aliases, benefit concepts, and view the live database prompt."
              steps={[
                { target: "header", title: "Page purpose", body: "Inspect the AI's grounding memory or ask quick questions with ultra-low token consumption." },
                { target: ".rl-tour-tabs", title: "Navigation tabs", body: "Grounding Chatbot, Database Overview, Insurers & Packages, Benefit Concepts, and Live System Prompt." },
              ]}
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                loadData();
                loadMemory();
              }}
              className="gap-1.5"
            >
              <ArrowsClockwise size={15} weight="bold" />
              Refresh Context
            </Button>
          </div>
        </header>

        {error ? (
          <div role="alert" className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] border border-[var(--rl-red)]/20 px-4 py-3 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        {/* Authentic AI Engine Status Banner */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white p-4 shadow-xs">
          <div className="flex items-center gap-3">
            <span className={`grid size-10 place-items-center rounded-[var(--rl-radius-sm)] ${gemini?.active ? "bg-[var(--rl-black)] text-white" : "bg-gray-100 text-gray-400"}`}>
              <Brain size={22} weight="fill" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-bold text-[var(--rl-text-strong)]">
                  Gemini Multimodal AI Engine
                </p>
                <Badge variant={gemini?.active ? "success" : "default"}>
                  {gemini?.active ? "Live & Grounded" : "Offline"}
                </Badge>
              </div>
              <p className="text-xs text-[var(--rl-text-muted)] mt-0.5">
                Model: <strong>{gemini?.model}</strong> · {gemini?.key_count || 1} Rotation Key{(gemini?.key_count || 1) > 1 ? "s" : ""} Loaded · Grounded Database Mode
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <GeminiQuotaInfoButton quota={gemini} />
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="rl-tour-tabs flex border-b border-[var(--rl-border)] gap-2 overflow-x-auto">
          <button
            type="button"
            onClick={() => setTab("chat")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
              tab === "chat"
                ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
                : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
          >
            <ChatCircleDots size={16} weight="bold" />
            AI Grounding Assistant (Chatbot)
          </button>
          <button
            type="button"
            onClick={() => setTab("learned")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
              tab === "learned"
                ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
                : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
          >
            <Lightning size={16} weight="bold" />
            Learned Memory & Rules ({memoryData?.total_memories || 0})
          </button>
          <button
            type="button"
            onClick={() => setTab("summary")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
              tab === "summary"
                ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
                : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
          >
            <Database size={16} weight="bold" />
            Grounding Overview & Stats
          </button>
          <button
            type="button"
            onClick={() => setTab("companies")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
              tab === "companies"
                ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
                : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
          >
            <Buildings size={16} weight="bold" />
            Insurers & Packages ({data?.companies.length || 0})
          </button>
          <button
            type="button"
            onClick={() => setTab("concepts")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
              tab === "concepts"
                ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
                : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
          >
            <Star size={16} weight="bold" />
            Benefit Concepts ({data?.benefit_concepts.length || 0})
          </button>
          <button
            type="button"
            onClick={() => setTab("prompt")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
              tab === "prompt"
                ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
                : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
          >
            <TerminalWindow size={16} weight="bold" />
            System Prompt Editor
          </button>
        </div>

        {/* Tab 1: Unified Agentic AI Copilot Link */}
        {tab === "chat" && (
          <div className="grid gap-4">
            <Card className="border border-[var(--rl-border)] bg-white shadow-xs p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <span className="grid size-10 place-items-center rounded-[var(--rl-radius-sm)] bg-[var(--rl-black)] text-white shrink-0">
                  <Brain size={20} weight="fill" />
                </span>
                <div className="space-y-1">
                  <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">
                    Unified RiskLocker AI Copilot
                  </h2>
                  <p className="text-xs text-[var(--rl-text-muted)] max-w-xl leading-relaxed">
                    The grounding assistant has been upgraded into the full Agentic AI Copilot — with persistent Chat Inbox sessions, read-only SQL over all 6 semantic views, multi-year comparisons, and zero-token Excel exports.
                  </p>
                </div>
              </div>
              <a
                href="/copilot"
                className="inline-flex items-center gap-1.5 rounded-[var(--rl-radius-sm)] bg-[var(--rl-black)] px-4 py-2 text-xs font-semibold text-white hover:bg-neutral-800 shrink-0"
              >
                <Sparkle size={14} weight="fill" />
                Open AI Copilot Workspace
              </a>
            </Card>
          </div>
        )}

        {/* Tab: Learned Memory & Rules */}
        {tab === "learned" && (
          <div className="grid gap-4">
            {/* Metric Summary Cards */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[var(--rl-text-muted)] uppercase tracking-wider">
                    Total Learned Corrections
                  </span>
                  <Lightning size={20} weight="fill" className="text-amber-500" />
                </div>
                <p className="mt-2 text-2xl font-bold text-[var(--rl-text-strong)] font-mono">
                  {memoryData?.total_memories ?? 0}
                </p>
                <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                  Persistent correction rules automatically guiding extraction.
                </p>
              </Card>

              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[var(--rl-text-muted)] uppercase tracking-wider">
                    Corrected Fields Count
                  </span>
                  <ShieldCheck size={20} className="text-emerald-600" />
                </div>
                <p className="mt-2 text-2xl font-bold text-[var(--rl-text-strong)] font-mono">
                  {memoryData?.summary_by_field.length ?? 0}
                </p>
                <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                  Distinct quotation fields refined by human review.
                </p>
              </Card>

              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[var(--rl-text-muted)] uppercase tracking-wider">
                    Top Corrected Field
                  </span>
                  <Sparkle size={20} weight="fill" className="text-indigo-600" />
                </div>
                <p className="mt-2 text-xl font-bold text-[var(--rl-text-strong)] truncate font-mono">
                  {memoryData?.summary_by_field[0]?.field ? `${memoryData.summary_by_field[0].field} (${memoryData.summary_by_field[0].count}x)` : "None"}
                </p>
                <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                  Highest frequency learned field pattern.
                </p>
              </Card>
            </div>

            {/* Controls Bar: Search & Filter */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white p-3 shadow-xs">
              <div className="flex items-center gap-2 flex-1 min-w-[240px]">
                <Input
                  value={memorySearch}
                  onChange={(e) => setMemorySearch(e.target.value)}
                  placeholder="Search learned memories (field, value, insurer)..."
                  className="text-xs max-w-md"
                />
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={memoryFieldFilter}
                  onChange={(e) => setMemoryFieldFilter(e.target.value)}
                  aria-label="Filter by field name"
                  className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white px-2.5 py-1.5 text-xs text-[var(--rl-text-strong)] focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
                >
                  <option value="all">All Fields ({memoryData?.total_memories || 0})</option>
                  {memoryData?.summary_by_field.map((sf) => (
                    <option key={sf.field} value={sf.field}>
                      {sf.field} ({sf.count})
                    </option>
                  ))}
                </select>
                <Button variant="secondary" size="sm" onClick={loadMemory} disabled={memoryLoading} className="text-xs gap-1">
                  <ArrowsClockwise size={13} className={memoryLoading ? "animate-spin" : ""} />
                  Refresh
                </Button>
              </div>
            </div>

            {/* Memory Table */}
            <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white overflow-hidden shadow-xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs min-w-[700px]">
                  <thead className="bg-gray-50 border-b border-[var(--rl-border)] text-[var(--rl-text-muted)] uppercase text-[11px]">
                    <tr>
                      <th className="p-3">Field Name</th>
                      <th className="p-3">Original Detected</th>
                      <th className="p-3">Learned / Corrected</th>
                      <th className="p-3">Insurer Scope</th>
                      <th className="p-3">Date Learned</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--rl-border)]">
                    {filteredMemories.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-6 text-center text-xs text-[var(--rl-text-muted)]">
                          {memoryLoading ? "Loading learned AI memories..." : "No learned memories match your filter."}
                        </td>
                      </tr>
                    ) : (
                      filteredMemories.map((item) => (
                        <tr key={item.id} className="hover:bg-gray-50/50">
                          <td className="p-3 font-semibold text-[var(--rl-text-strong)] font-mono">
                            <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-800">
                              {item.field_name}
                            </span>
                          </td>
                          <td className="p-3 text-red-600 line-through truncate max-w-[180px]">
                            {item.original_value}
                          </td>
                          <td className="p-3 font-bold text-emerald-700 truncate max-w-[200px]">
                            <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-emerald-800 border border-emerald-200/60">
                              <CheckCircle size={12} weight="bold" className="text-emerald-600" />
                              {item.corrected_value}
                            </span>
                          </td>
                          <td className="p-3 text-[var(--rl-text-muted)]">
                            <span className="inline-flex items-center gap-1.5">
                              <Buildings size={14} className="text-gray-400" />
                              {item.insurance_company}
                            </span>
                          </td>
                          <td className="p-3 text-[var(--rl-text-muted)] font-mono text-[11px]">
                            {item.created_at
                              ? new Date(item.created_at).toLocaleDateString("en-MY", {
                                  year: "numeric",
                                  month: "short",
                                  day: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })
                              : "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Grounding Overview & Stats */}
        {tab === "summary" && (
          <div className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[var(--rl-text-muted)] uppercase tracking-wider">
                    Active Insurance Companies
                  </span>
                  <Buildings size={20} className="text-[var(--rl-black)]" />
                </div>
                <p className="mt-2 text-2xl font-bold text-[var(--rl-text-strong)] font-mono">
                  {summary?.active_companies_count ?? data?.companies.length ?? 7}
                </p>
                <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                  7 insurers active with catalog mappings &amp; aliases.
                </p>
              </Card>

              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[var(--rl-text-muted)] uppercase tracking-wider">
                    Standard Benefit Concepts
                  </span>
                  <Star size={20} className="text-amber-500" />
                </div>
                <p className="mt-2 text-2xl font-bold text-[var(--rl-text-strong)] font-mono">
                  {summary?.benefit_concepts_count ?? data?.benefit_concepts.length ?? 45}
                </p>
                <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                  Standardized benefit codes with artwork illustrations.
                </p>
              </Card>

              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[var(--rl-text-muted)] uppercase tracking-wider">
                    Field Aliases Dictionary
                  </span>
                  <ShieldCheck size={20} className="text-emerald-600" />
                </div>
                <p className="mt-2 text-2xl font-bold text-[var(--rl-text-strong)] font-mono">
                  {summary?.field_aliases_count ?? data?.field_aliases.length ?? 0}
                </p>
                <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                  Multilingual Malay &amp; English field variants mapped.
                </p>
              </Card>

              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[var(--rl-text-muted)] uppercase tracking-wider">
                    Saved Client Records
                  </span>
                  <Database size={20} className="text-blue-600" />
                </div>
                <p className="mt-2 text-2xl font-bold text-[var(--rl-text-strong)] font-mono">
                  {summary?.saved_records_count ?? 0}
                </p>
                <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                  Client records generated from official quotation PDFs.
                </p>
              </Card>

              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[var(--rl-text-muted)] uppercase tracking-wider">
                    Total Quotation Sessions
                  </span>
                  <Brain size={20} className="text-purple-600" />
                </div>
                <p className="mt-2 text-2xl font-bold text-[var(--rl-text-strong)] font-mono">
                  {summary?.total_sessions_count ?? 0}
                </p>
                <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                  Processed upload and review sessions in ledger.
                </p>
              </Card>
            </div>
          </div>
        )}

        {/* Tab 3: Companies */}
        {tab === "companies" && (
          <div className="grid gap-3">
            <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white overflow-hidden shadow-xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs min-w-[500px]">
                  <thead className="bg-gray-50 border-b border-[var(--rl-border)] text-[var(--rl-text-muted)] uppercase text-[11px]">
                    <tr>
                      <th className="p-3">Insurance Company</th>
                      <th className="p-3">Extraction Mode</th>
                      <th className="p-3">RAG Aliases &amp; Detection Phrases</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--rl-border)]">
                    {data?.companies.map((c) => (
                      <tr key={c.id} className="hover:bg-gray-50/50">
                        <td className="p-3 font-semibold text-[var(--rl-text-strong)]">
                          <div className="flex items-center gap-2">
                            <Buildings size={16} className="text-gray-400" />
                            <span>{c.name}</span>
                          </div>
                        </td>
                        <td className="p-3">
                          <Badge variant={c.has_packages ? "success" : "default"}>
                            {c.has_packages ? "4-Tier Package Chain" : "Single Add-on Mode"}
                          </Badge>
                        </td>
                        <td className="p-3">
                          <div className="flex flex-wrap gap-1">
                            {c.aliases.length ? (
                              c.aliases.map((alias, idx) => (
                                <span key={idx} className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] font-mono text-gray-700">
                                  {alias}
                                </span>
                              ))
                            ) : (
                              <span className="text-[var(--rl-text-muted)] italic">Exact name matching ({c.name})</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Benefit Concepts */}
        {tab === "concepts" && (
          <div className="grid gap-3">
            <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white overflow-hidden shadow-xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs min-w-[500px]">
                  <thead className="bg-gray-50 border-b border-[var(--rl-border)] text-[var(--rl-text-muted)] uppercase text-[11px]">
                    <tr>
                      <th className="p-3">Standard Concept Label</th>
                      <th className="p-3">Concept Key (ID)</th>
                      <th className="p-3">Category</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--rl-border)]">
                    {data?.benefit_concepts.map((b) => (
                      <tr key={b.id} className="hover:bg-gray-50/50">
                        <td className="p-3 font-semibold text-[var(--rl-text-strong)]">
                          {b.name}
                        </td>
                        <td className="p-3">
                          <span className="rounded bg-gray-100 px-2 py-0.5 font-mono text-[11px] text-gray-800 border border-gray-200">
                            {b.key}
                          </span>
                        </td>
                        <td className="p-3 text-[var(--rl-text-muted)]">
                          {b.category}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 5: Live System Prompt Preview */}
        {tab === "prompt" && (
          <div className="grid gap-4">
            <Card className="rl-tour-prompt p-4 border border-[var(--rl-border)] bg-white shadow-xs grid gap-3">
              <div className="flex items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-2">
                <div className="flex items-center gap-2 text-sm font-bold text-[var(--rl-text-strong)]">
                  <TerminalWindow size={18} weight="bold" />
                  AI System Prompt Override
                </div>
                {canEditPrompt ? (
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="secondary" onClick={resetPrompt} disabled={promptSaving || !promptOverride.trim()} className="h-7 text-xs gap-1">
                      <ArrowsClockwise size={13} weight="bold" />
                      Reset to default
                    </Button>
                    <Button size="sm" onClick={savePrompt} disabled={promptSaving} className="h-7 text-xs gap-1">
                      {promptSaved ? <CheckCircle size={13} weight="bold" /> : <Sparkle size={13} weight="bold" />}
                      {promptSaving ? "Saving..." : promptSaved ? "Saved!" : "Save prompt"}
                    </Button>
                  </div>
                ) : (
                  <Badge variant="default">Read-only (admin)</Badge>
                )}
              </div>
              <p className="text-xs text-[var(--rl-text-muted)]">
                Leave empty to use the built-in default prompt. When set, this text replaces the fixed instruction block; the live database grounding
                (insurers, benefit concepts, packs) is always appended automatically.
              </p>
              <textarea
                value={promptOverride}
                onChange={(e) => setPromptOverride(e.target.value)}
                disabled={!canEditPrompt}
                rows={8}
                placeholder="You are the RiskLocker High-Precision Malaysian Motor Insurance Quotation Extractor. ..."
                className="w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3 font-mono text-[12px] text-[var(--rl-text-strong)] focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)] disabled:opacity-60"
              />
              <div className="flex items-center justify-between text-[11px] text-[var(--rl-text-muted)]">
                <span>{promptOverride.trim().length.toLocaleString()} characters</span>
                <span className={promptOverride.trim() ? "text-emerald-700 font-semibold" : ""}>
                  {promptOverride.trim() ? "Custom override active" : "Using built-in default prompt"}
                </span>
              </div>
            </Card>

            <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs grid gap-3">
              <div className="flex items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-2">
                <div className="flex items-center gap-2 text-sm font-bold text-[var(--rl-text-strong)]">
                  <TerminalWindow size={18} weight="bold" />
                  Effective Prompt (what the AI actually receives)
                </div>
                <Button size="sm" variant="secondary" onClick={copyPrompt} className="h-7 text-xs gap-1">
                  <Copy size={13} weight="bold" />
                  <span>{copied ? "Copied!" : "Copy Prompt"}</span>
                </Button>
              </div>
              <pre className="overflow-x-auto rounded-[var(--rl-radius-sm)] bg-gray-900 p-4 font-mono text-[12px] text-gray-100 whitespace-pre-wrap leading-relaxed max-h-[350px]">
                {data?.live_system_prompt}
              </pre>
            </Card>
          </div>
        )}
      </div>
    </AppShell>
  );
}
