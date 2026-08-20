"use client";

import { useEffect, useState } from "react";
import {
  ArrowsClockwise,
  Brain,
  Buildings,
  CheckCircle,
  Copy,
  Info,
  Prohibit,
  Sparkle,
  Star,
  TerminalWindow,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageLoading } from "@/components/ui/page-loading";
import { GuidedTour } from "@/components/guided-tour";
import { GeminiQuotaInfoButton } from "@/components/gemini-quota-meter";
import { api } from "@/lib/api";

type AIContextData = {
  gemini: {
    active: boolean;
    model: string;
    key_count: number;
    rpm_limit: number;
    rpm_used: number;
    rpd_limit: number;
    rpd_used: number;
    rpd_remaining: number;
    percent_rpd_remaining: number;
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
  negative_rules: Array<{
    target: string;
    rule: string;
    patterns: string[];
    explanation: string;
  }>;
  live_system_prompt: string;
};

type ActiveTab = "rules" | "companies" | "concepts" | "negative" | "prompt";

export default function AIContextPage() {
  const [data, setData] = useState<AIContextData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<ActiveTab>("rules");
  const [copied, setCopied] = useState(false);
  const [promptOverride, setPromptOverride] = useState("");
  const [promptSaving, setPromptSaving] = useState(false);
  const [promptSaved, setPromptSaved] = useState(false);
  const [canEditPrompt, setCanEditPrompt] = useState(false);

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

  useEffect(() => {
    loadData();
    loadPrompt();
    loadCapabilities();
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

  return (
    <AppShell>
      <div className="grid gap-6 max-w-6xl mx-auto">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-[var(--font-manrope)] text-[28px] font-bold text-[var(--rl-text-strong)]">
              AI Grounding & RAG Context
            </h1>
            <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
              Inspect the live memory, grounding rules, active insurer aliases, and prompt context fed into the Gemini Multimodal AI.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <GuidedTour
              storageKey="tour:ai-context"
              title="AI Grounding & RAG Context"
              description="See exactly what the AI knows and how it's instructed: grounding rules, insurer aliases, benefit concepts, disqualification filters, and the live system prompt (which admins can override)."
              steps={[
                { target: "header", title: "Page purpose", body: "Inspect the AI's memory and instructions. This is a read-only dashboard (except the prompt editor, which admins can change)." },
                { target: ".rl-tour-tabs", title: "Inspection tabs", body: "Grounding rules, insurers & packages, benefit concepts, disqualification filters, and the live system prompt." },
                { target: ".rl-tour-prompt", title: "System prompt editor", body: "Admins can override the AI's system prompt here. Leave empty to use the built-in default; the live database grounding is always appended automatically." },
              ]}
            />
            <Button variant="secondary" size="sm" onClick={loadData} className="gap-1.5">
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

        {/* AI Engine Status Banner */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white p-4 shadow-xs">
          <div className="flex items-center gap-3">
            <span className={`grid size-10 place-items-center rounded-[var(--rl-radius-sm)] ${gemini?.active ? "bg-[var(--rl-black)] text-white" : "bg-gray-100 text-gray-400"
              }`}>
              <Brain size={22} weight="fill" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-bold text-[var(--rl-text-strong)]">
                  Gemini Multimodal AI Engine
                </p>
                <Badge variant={gemini?.active ? "success" : "default"}>
                  {gemini?.active ? "Active & Grounded" : "Offline"}
                </Badge>
              </div>
              <p className="text-xs text-[var(--rl-text-muted)] mt-0.5">
                Model: <strong>{gemini?.model}</strong> · {gemini?.key_count} Key{gemini?.key_count && gemini.key_count > 1 ? "s" : ""} in Pool · Quota: {gemini?.rpd_remaining.toLocaleString()} / {gemini?.rpd_limit.toLocaleString()} RPD remaining
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
            onClick={() => setTab("rules")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors ${tab === "rules"
              ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
              : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
          >
            Grounding Rules ({data?.negative_rules.length || 0})
          </button>
          <button
            type="button"
            onClick={() => setTab("companies")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors ${tab === "companies"
              ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
              : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
          >
            Insurer Companies & Packages ({data?.companies.length || 0})
          </button>
          <button
            type="button"
            onClick={() => setTab("concepts")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors ${tab === "concepts"
              ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
              : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
          >
            Benefit Concepts Library ({data?.benefit_concepts.length || 0})
          </button>
          <button
            type="button"
            onClick={() => setTab("negative")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors ${tab === "negative"
              ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
              : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
          >
            Disqualification Filters
          </button>
          <button
            type="button"
            onClick={() => setTab("prompt")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors ${tab === "prompt"
              ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
              : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
          >
            Live Gemini System Prompt Preview
          </button>
        </div>

        {/* Tab 1: Grounding Rules */}
        {tab === "rules" && (
          <div className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center gap-2 text-sm font-bold text-[var(--rl-text-strong)]">
                  <Star size={16} weight="fill" className="text-amber-500" />
                  Insured Customer Name Grounding
                </div>
                <p className="text-xs text-[var(--rl-text-muted)] mt-1">
                  Extracts the policyholder / insured party. Excludes agent names, broker names, account codes, and toll-free breakdown numbers.
                </p>
                <div className="mt-3 flex flex-wrap gap-1">
                  <span className="bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-mono px-2 py-0.5 rounded">The Insured</span>
                  <span className="bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-mono px-2 py-0.5 rounded">Pihak Diinsuranskan</span>
                  <span className="bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-mono px-2 py-0.5 rounded">Participant</span>
                </div>
              </Card>

              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center gap-2 text-sm font-bold text-[var(--rl-text-strong)]">
                  <Star size={16} weight="fill" className="text-amber-500" />
                  Vehicle Make, Model & Variant Full Preservation
                </div>
                <p className="text-xs text-[var(--rl-text-muted)] mt-1">
                  Enforces full model string capture including transmission (CVT / Automatic / Manual), doors, and body type without truncating.
                </p>
                <div className="mt-3 text-xs font-mono bg-gray-50 p-2 rounded border border-[var(--rl-border)] text-gray-700">
                  PERODUA ATIVA AV MY21 D55L 4D WAGON 1 SP AUTOMATIC (CVT)
                </div>
              </Card>

              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center gap-2 text-sm font-bold text-[var(--rl-text-strong)]">
                  <Star size={16} weight="fill" className="text-amber-500" />
                  Coverage Type Normalization
                </div>
                <p className="text-xs text-[var(--rl-text-muted)] mt-1">
                  Translates and standardizes Malay/English headers into canonical coverage categories.
                </p>
                <div className="mt-3 flex flex-wrap gap-1">
                  <span className="bg-gray-100 text-gray-800 text-[11px] font-semibold px-2 py-0.5 rounded">Comprehensive</span>
                  <span className="bg-gray-100 text-gray-800 text-[11px] font-semibold px-2 py-0.5 rounded">Third Party Fire & Theft</span>
                  <span className="bg-gray-100 text-gray-800 text-[11px] font-semibold px-2 py-0.5 rounded">Third Party</span>
                </div>
              </Card>

              <Card className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center gap-2 text-sm font-bold text-[var(--rl-text-strong)]">
                  <Star size={16} weight="fill" className="text-amber-500" />
                  Package vs Single Mode Detection
                </div>
                <p className="text-xs text-[var(--rl-text-muted)] mt-1">
                  Determines whether the underwriting insurer uses packaged tier chains (e.g. AmAssurance Lite/Plus/Standard/Premier) or single add-on mode.
                </p>
                <div className="mt-3 flex items-center gap-2 text-xs">
                  <Badge variant="default">AmAssurance: Package Mode</Badge>
                  <Badge variant="default">Other Insurers: Single Mode</Badge>
                </div>
              </Card>
            </div>
          </div>
        )}

        {/* Tab 2: Companies */}
        {tab === "companies" && (
          <div className="grid gap-3">
            <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 border-b border-[var(--rl-border)] text-[var(--rl-text-muted)] uppercase text-[11px]">
                  <tr>
                    <th className="p-3">Insurance Company</th>
                    <th className="p-3">Extraction Mode</th>
                    <th className="p-3">RAG Aliases & Detection Phrases</th>
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
                          {c.has_packages ? "Package Chain Mode" : "Single Add-on Mode"}
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
        )}

        {/* Tab 3: Benefit Concepts */}
        {tab === "concepts" && (
          <div className="grid gap-3">
            <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
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
        )}

        {/* Tab 4: Negative Disqualification Filters */}
        {tab === "negative" && (
          <div className="grid gap-3">
            {data?.negative_rules.map((rule, idx) => (
              <Card key={idx} className="p-4 border border-[var(--rl-border)] bg-white shadow-xs">
                <div className="flex items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-2">
                  <div className="flex items-center gap-2">
                    <Prohibit size={18} weight="bold" className="text-red-500" />
                    <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">{rule.rule}</h3>
                  </div>
                  <Badge variant="danger">Target: {rule.target}</Badge>
                </div>
                <p className="text-xs text-[var(--rl-text-muted)] mt-2">
                  {rule.explanation}
                </p>
                <div className="mt-3">
                  <span className="text-[11px] font-semibold text-[var(--rl-text-strong)] block mb-1">
                    Disqualified Patterns & Phrases:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {rule.patterns.map((pat, pIdx) => (
                      <span key={pIdx} className="rounded bg-red-50 text-red-800 border border-red-200 px-2 py-0.5 text-[11px] font-mono">
                        ✕ {pat}
                      </span>
                    ))}
                  </div>
                </div>
              </Card>
            ))}
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
                (insurers, benefit concepts, packs) is always appended automatically. The default prompt is auto-generated from the current database.
              </p>
              <textarea
                value={promptOverride}
                onChange={(e) => setPromptOverride(e.target.value)}
                disabled={!canEditPrompt}
                rows={10}
                placeholder="You are the RiskLocker High-Precision Malaysian Motor Insurance Quotation Extractor. ..."
                className="w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3 font-mono text-[12px] text-[var(--rl-text-strong)] focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)] disabled:opacity-60"
              />
              <div className="flex items-center justify-between text-[11px] text-[var(--rl-text-muted)]">
                <span>{promptOverride.trim().length.toLocaleString()} characters (max 12,000)</span>
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
              <pre className="overflow-x-auto rounded-[var(--rl-radius-sm)] bg-gray-900 p-4 font-mono text-[12px] text-gray-100 whitespace-pre-wrap leading-relaxed">
                {data?.live_system_prompt}
              </pre>
            </Card>
          </div>
        )}
      </div>
    </AppShell>
  );
}
