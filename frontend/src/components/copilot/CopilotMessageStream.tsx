"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  ArrowSquareOut,
  ArrowsClockwise,
  CaretDown,
  CaretRight,
  Check,
  CheckCircle,
  Copy,
  DownloadSimple,
  FileXls,
  Robot,
  ShieldCheck,
  Sparkle,
  ThumbsDown,
  ThumbsUp,
  Trash,
  WarningCircle,
  WhatsappLogo,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, API_BASE } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { useAuth } from "@/lib/auth";
import { CopilotMarkdown } from "./CopilotMarkdown";
import type { CopilotArtifact, CopilotMessage, CopilotPageContext } from "./types";

type CopilotMessageStreamProps = {
  messages: CopilotMessage[];
  loading: boolean;
  streaming: boolean;
  pageContext: CopilotPageContext;
  onSelectStarterPrompt: (prompt: string) => void;
  onOpenArtifact: (artifact: CopilotArtifact) => void;
  onFeedback: (messageId: string, feedback: "up" | "down" | null) => Promise<void>;
  onRegenerate: (promptText: string) => void;
};

function stripMarkdownForWhatsApp(md: string): string {
  return (md || "")
    .replace(/^#{1,3}\s+/gm, "*")
    .replace(/\*\*([^*]+)\*\*/g, "*$1*")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
}

function getContextStarterPrompts(ctx: CopilotPageContext): Array<{ label: string; prompt: string }> {
  if (ctx.pathname.startsWith("/comparison") && ctx.anchor_id) {
    return [
      { label: "Explain Winner & Best Value", prompt: "Compare all quotes for this car and explain which insurer gives the best overall value." },
      { label: "Draft WhatsApp Pitch", prompt: "Write a short, polite WhatsApp comparison summary for the client using the exact quotes for this car." },
      { label: "Check Prior Years YoY", prompt: "Compare this car's current quotes against all previous policy years on record." },
    ];
  }
  if (ctx.pathname.startsWith("/ledger")) {
    return [
      { label: "Search Plate Substring", prompt: "How many cars got '88' in their number plates? Show links to their ledgers." },
      { label: "Pending Renewals Without Quotes", prompt: "Which upcoming renewals still have 0 comparison quotes uploaded?" },
      { label: "Export Whole Ledger to Excel", prompt: "Export the full motor renewal ledger across all years to an Excel workbook." },
    ];
  }
  return [
    { label: "Find Plates Containing '88'", prompt: "How many cars got '88' in their number plates? List them with direct ledger links." },
    { label: "Top Insurer Quote Share", prompt: "Which insurance companies had the most quotes and highest Hit rate across our database?" },
    { label: "Export Full Comparison Excel", prompt: "Generate an Excel workbook of all comparison quotes with premiums, towing, and totals." },
    { label: "Check Duplicate Uploads", prompt: "Check if there are duplicate quotation uploads we can safely clean up." },
  ];
}

export function CopilotMessageStream({
  messages,
  loading,
  streaming,
  pageContext,
  onSelectStarterPrompt,
  onOpenArtifact,
  onFeedback,
  onRegenerate,
}: CopilotMessageStreamProps) {
  const { user } = useAuth();
  const isAdmin = !!user && ["super_admin", "admin", "dev"].includes(user.role);
  const endRef = useRef<HTMLDivElement>(null);

  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({});
  const [expandedSql, setExpandedSql] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [waCopiedId, setWaCopiedId] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<Record<string, boolean>>({});
  const [actionResult, setActionResult] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState<Record<string, string>>({});

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streaming]);

  async function handleDownloadArtifact(art: CopilotArtifact) {
    const url = art.download_url.startsWith("/api/") ? art.download_url : `${API_BASE}${art.download_url}`;
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) return;
    const blob = await res.blob();
    const objUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objUrl;
    a.download = art.filename || "risklocker_export.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(objUrl);
  }

  async function handleCleanDuplicates(actionKey: string, sessionIds: string[]) {
    if (!sessionIds.length) return;
    setActionBusy((prev) => ({ ...prev, [actionKey]: true }));
    setActionError((prev) => ({ ...prev, [actionKey]: "" }));
    try {
      const res = await api<{ message: string; cleaned_count: number }>(
        "/copilot/sessions/cleanup-duplicates",
        {
          method: "POST",
          body: JSON.stringify({ session_ids: sessionIds }),
        }
      );
      setActionResult((prev) => ({
        ...prev,
        [actionKey]: res.message || `Moved ${res.cleaned_count} duplicate session(s) to Trash.`,
      }));
    } catch (err) {
      setActionError((prev) => ({ ...prev, [actionKey]: apiErrorMessage(err) }));
    } finally {
      setActionBusy((prev) => ({ ...prev, [actionKey]: false }));
    }
  }

  const starters = getContextStarterPrompts(pageContext);

  if (loading && messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 text-xs text-[var(--rl-text-muted)]">
        <ArrowsClockwise size={16} className="animate-spin mr-2" />
        Loading conversation...
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.length === 0 && (
        <div className="mx-auto max-w-lg py-6 text-center space-y-4">
          <div className="mx-auto size-12 rounded-[var(--rl-radius-md)] bg-[var(--rl-black)] text-white grid place-items-center shadow-sm">
            <Robot size={24} weight="fill" />
          </div>
          <div className="space-y-1">
            <h4 className="text-sm font-bold text-[var(--rl-text-strong)]">
              RiskLocker Intelligence Copilot
            </h4>
            <p className="text-xs text-[var(--rl-text-muted)] leading-relaxed">
              Ask anything across your motor ledger, comparison matrices, clients, plates, or insurer catalogs — or request a formatted Excel export.
            </p>
          </div>
          <div className="grid gap-2 text-left pt-1">
            {starters.map((s, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onSelectStarterPrompt(s.prompt)}
                className="w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white px-3 py-2 text-left hover:border-[var(--rl-black)] hover:bg-neutral-50 transition-colors cursor-pointer group"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-[var(--rl-text-strong)]">{s.label}</span>
                  <span className="text-[10px] text-[var(--rl-text-muted)] group-hover:text-[var(--rl-text-strong)]">
                    Use ↵
                  </span>
                </div>
                <div className="mt-0.5 text-[11px] text-[var(--rl-text-muted)] line-clamp-1">{s.prompt}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {messages.map((m, idx) => {
        const isUser = m.role === "user";
        const prevUserText =
          !isUser && idx > 0 && messages[idx - 1]?.role === "user"
            ? messages[idx - 1].content_markdown
            : "";
        const stepsOpen = expandedSteps[m.id] ?? !!m.isStreaming;

        return (
          <div key={m.id} className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
            <div
              className={`max-w-[92%] rounded-[var(--rl-radius-md)] px-3.5 py-2.5 ${
                isUser
                  ? "bg-[var(--rl-black)] text-white shadow-xs text-xs"
                  : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-strong)] shadow-xs w-full"
              }`}
            >
              {/* Thinking & Tool Steps (Assistant) */}
              {!isUser && m.tool_trace && m.tool_trace.length > 0 && (
                <div className="mb-2.5 rounded-[var(--rl-radius-sm)] border border-neutral-200 bg-neutral-50/80 px-2.5 py-1.5">
                  <button
                    type="button"
                    onClick={() => setExpandedSteps((p) => ({ ...p, [m.id]: !stepsOpen }))}
                    className="w-full flex items-center justify-between text-[11px] font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] cursor-pointer"
                  >
                    <span className="flex items-center gap-1.5">
                      {m.isStreaming ? (
                        <ArrowsClockwise size={12} className="animate-spin text-emerald-600" />
                      ) : (
                        <Sparkle size={12} weight="fill" className="text-emerald-600" />
                      )}
                      {m.isStreaming
                        ? "Investigating database..."
                        : `Checked ${m.tool_trace.length} live step${m.tool_trace.length === 1 ? "" : "s"}`}
                    </span>
                    {stepsOpen ? <CaretDown size={12} /> : <CaretRight size={12} />}
                  </button>

                  {stepsOpen && (
                    <div className="mt-1.5 space-y-1 border-t border-neutral-200 pt-1.5">
                      {m.tool_trace.map((step) => {
                        const sqlKey = `${m.id}_${step.step_id}`;
                        const showSql = !!expandedSql[sqlKey];
                        return (
                          <div key={step.step_id} className="text-[11px]">
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-1.5 min-w-0">
                                {step.status === "running" ? (
                                  <ArrowsClockwise size={11} className="animate-spin text-blue-600 shrink-0" />
                                ) : step.status === "error" ? (
                                  <WarningCircle size={11} weight="fill" className="text-rose-600 shrink-0" />
                                ) : (
                                  <CheckCircle size={11} weight="fill" className="text-emerald-600 shrink-0" />
                                )}
                                <span className="truncate text-[var(--rl-text)]">{step.label}</span>
                              </div>
                              <div className="flex items-center gap-2 shrink-0 font-mono text-[10px] text-[var(--rl-text-muted)]">
                                {step.row_count !== null && step.row_count !== undefined && (
                                  <span>{step.row_count} rows</span>
                                )}
                                {step.elapsed_ms !== null && step.elapsed_ms !== undefined && (
                                  <span>{step.elapsed_ms}ms</span>
                                )}
                                {isAdmin && step.sql && (
                                  <button
                                    type="button"
                                    onClick={() => setExpandedSql((p) => ({ ...p, [sqlKey]: !showSql }))}
                                    className="text-blue-700 hover:underline cursor-pointer"
                                  >
                                    {showSql ? "Hide SQL" : "SQL"}
                                  </button>
                                )}
                              </div>
                            </div>
                            {isAdmin && showSql && step.sql && (
                              <pre className="mt-1 overflow-x-auto rounded bg-neutral-900 p-2 font-mono text-[10px] text-neutral-100">
                                {step.sql}
                              </pre>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Message Body */}
              {isUser ? (
                <div className="whitespace-pre-wrap leading-relaxed">{m.content_markdown}</div>
              ) : m.content_markdown ? (
                <CopilotMarkdown content={m.content_markdown} />
              ) : m.isStreaming ? (
                <div className="flex items-center gap-2 py-1 text-xs text-[var(--rl-text-muted)]">
                  <span className="inline-block size-2 rounded-full bg-emerald-500 animate-ping" />
                  <span>Thinking...</span>
                </div>
              ) : null}

              {/* Verified Navigation Chips */}
              {!isUser && m.verified_links && m.verified_links.length > 0 && (
                <div className="mt-3 pt-2.5 border-t border-neutral-100 flex flex-wrap gap-1.5">
                  {m.verified_links.map((lnk, lIdx) => (
                    <Link
                      key={lIdx}
                      href={lnk.href as Route}
                      className="inline-flex items-center gap-1 rounded-full border border-neutral-200 bg-neutral-50 hover:bg-neutral-900 hover:text-white hover:border-neutral-900 px-2.5 py-1 text-[11px] font-semibold text-[var(--rl-text-strong)] transition-colors"
                    >
                      <span>{lnk.label}</span>
                      <ArrowSquareOut size={11} weight="bold" />
                    </Link>
                  ))}
                </div>
              )}

              {/* Excel / Table Artifacts */}
              {!isUser && m.artifacts && m.artifacts.length > 0 && (
                <div className="mt-3 space-y-2">
                  {m.artifacts.map((art) => (
                    <div
                      key={art.id}
                      className="rounded-[var(--rl-radius-sm)] border border-emerald-200 bg-emerald-50/50 p-2.5 flex flex-wrap items-center justify-between gap-2"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="size-8 rounded bg-emerald-700 text-white grid place-items-center shrink-0">
                          <FileXls size={18} weight="fill" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs font-bold text-[var(--rl-text-strong)] truncate">{art.filename}</div>
                          <div className="text-[10px] text-[var(--rl-text-muted)] font-mono">
                            {art.row_count.toLocaleString()} rows · {(art.size_bytes / 1024).toFixed(1)} KB
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          onClick={() => onOpenArtifact(art)}
                          className="h-7 text-[11px]"
                        >
                          Preview Table
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => handleDownloadArtifact(art)}
                          icon={<DownloadSimple size={12} weight="bold" />}
                          className="h-7 text-[11px]"
                        >
                          Download .xlsx
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Human-in-the-Loop Action Cards */}
              {!isUser && m.action_cards && m.action_cards.length > 0 && (
                <div className="mt-3 space-y-2">
                  {m.action_cards.map((act, aIdx) => {
                    const aKey = `${m.id}_${aIdx}`;
                    if (act.type === "session_cleanup") {
                      return (
                        <Card key={aIdx} className="p-3 border border-[var(--rl-border)] bg-neutral-50 space-y-2">
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <ShieldCheck size={16} weight="fill" className="text-[var(--rl-black)]" />
                              <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                                {act.title || `Clean ${act.redundant_count} Duplicate Uploads`}
                              </span>
                            </div>
                            <Badge variant="default" className="text-[10px]">
                              {act.redundant_count} Redundant
                            </Badge>
                          </div>
                          {actionResult[aKey] ? (
                            <div className="text-xs text-emerald-700 font-medium">{actionResult[aKey]}</div>
                          ) : (
                            <div className="space-y-1.5">
                              {actionError[aKey] && (
                                <div className="text-[11px] text-rose-700">{actionError[aKey]}</div>
                              )}
                              <Button
                                type="button"
                                size="sm"
                                loading={!!actionBusy[aKey]}
                                onClick={() => handleCleanDuplicates(aKey, act.session_ids_to_trash || [])}
                                icon={<Trash size={12} />}
                                className="h-7 text-[11px]"
                              >
                                Confirm &amp; Move {act.redundant_count} Duplicates to Trash
                              </Button>
                            </div>
                          )}
                        </Card>
                      );
                    }
                    return null;
                  })}
                </div>
              )}

              {/* Assistant Footer Toolbar */}
              {!isUser && !m.isStreaming && m.content_markdown && (
                <div className="mt-2.5 pt-2 border-t border-neutral-100 flex flex-wrap items-center justify-between gap-2 text-[11px] text-[var(--rl-text-muted)]">
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(m.content_markdown);
                        setCopiedId(m.id);
                        setTimeout(() => setCopiedId(null), 1500);
                      }}
                      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-neutral-100 hover:text-[var(--rl-text-strong)] cursor-pointer"
                    >
                      {copiedId === m.id ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                      <span>{copiedId === m.id ? "Copied" : "Copy"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(stripMarkdownForWhatsApp(m.content_markdown));
                        setWaCopiedId(m.id);
                        setTimeout(() => setWaCopiedId(null), 1500);
                      }}
                      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-emerald-50 hover:text-emerald-700 cursor-pointer"
                    >
                      <WhatsappLogo size={12} weight="fill" />
                      <span>{waCopiedId === m.id ? "WhatsApp Ready!" : "WhatsApp"}</span>
                    </button>
                    {prevUserText && (
                      <button
                        type="button"
                        disabled={streaming}
                        onClick={() => onRegenerate(prevUserText)}
                        className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-neutral-100 hover:text-[var(--rl-text-strong)] cursor-pointer disabled:opacity-40"
                      >
                        <ArrowsClockwise size={12} />
                        <span>Retry</span>
                      </button>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5">
                    {typeof m.total_tokens === "number" && m.total_tokens > 0 && (
                      <span className="font-mono text-[10px] text-neutral-400">
                        {m.total_tokens.toLocaleString()} tok
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => onFeedback(m.id, m.feedback === "up" ? null : "up")}
                      className={`p-1 rounded cursor-pointer ${
                        m.feedback === "up"
                          ? "bg-emerald-100 text-emerald-700"
                          : "hover:bg-neutral-100 text-neutral-400"
                      }`}
                      title="Helpful"
                    >
                      <ThumbsUp size={12} weight={m.feedback === "up" ? "fill" : "regular"} />
                    </button>
                    <button
                      type="button"
                      onClick={() => onFeedback(m.id, m.feedback === "down" ? null : "down")}
                      className={`p-1 rounded cursor-pointer ${
                        m.feedback === "down"
                          ? "bg-rose-100 text-rose-700"
                          : "hover:bg-neutral-100 text-neutral-400"
                      }`}
                      title="Needs improvement"
                    >
                      <ThumbsDown size={12} weight={m.feedback === "down" ? "fill" : "regular"} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}
      <div ref={endRef} />
    </div>
  );
}
