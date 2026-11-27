"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  ArrowDown,
  ArrowSquareOut,
  ArrowsClockwise,
  CalendarBlank,
  CaretDown,
  CaretRight,
  Check,
  CheckCircle,
  Columns,
  Copy,
  DownloadSimple,
  FileText,
  FileXls,
  HourglassMedium,
  Robot,
  ShieldCheck,
  Sparkle,
  ThumbsDown,
  ThumbsUp,
  Trash,
  Users,
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
import type { CopilotArtifact, CopilotMessage, CopilotPageContext, CopilotQueueStatus } from "./types";

type CopilotMessageStreamProps = {
  messages: CopilotMessage[];
  loading: boolean;
  streaming: boolean;
  queueStatus?: CopilotQueueStatus | null;
  readOnly?: boolean;
  centered?: boolean;
  pageContext: CopilotPageContext;
  onSelectStarterPrompt: (prompt: string) => void;
  onOpenArtifact: (artifact: CopilotArtifact) => void;
  onFeedback: (messageId: string, feedback: "up" | "down" | null) => Promise<void>;
  onRegenerate: (promptText: string) => void;
  onNavigateDeepLink?: () => void;
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
      { label: "Search Plate Substring", prompt: "How many cars got '88' in their number plates? Show links to select them in the ledger." },
      { label: "Pending Renewals Without Quotes", prompt: "Which upcoming renewals still have 0 comparison quotes uploaded?" },
      { label: "Export Whole Ledger to Excel", prompt: "Export the full motor renewal ledger across all years to an Excel workbook." },
    ];
  }
  return [
    { label: "Bulk Check Pasted Plates", prompt: "Check which of these vehicle plates exist in our database and which are missing:\n" },
    { label: "Top Insurer Quote Share", prompt: "Which insurance companies had the most quotes and highest Hit rate across our database?" },
    { label: "Export Full Comparison Excel", prompt: "Generate an Excel workbook of all comparison quotes with premiums, towing, and totals." },
    { label: "Check Duplicate Uploads", prompt: "Check if there are duplicate quotation uploads we can safely clean up." },
  ];
}

function linkIcon(kind: string) {
  switch (kind) {
    case "ledger_batch":
    case "ledger":
      return <CalendarBlank size={13} weight="bold" />;
    case "comparison":
      return <Columns size={13} weight="bold" />;
    case "client":
      return <Users size={13} weight="bold" />;
    case "session":
      return <FileText size={13} weight="bold" />;
    default:
      return <ArrowSquareOut size={13} weight="bold" />;
  }
}

export function CopilotMessageStream({
  messages,
  loading,
  streaming,
  queueStatus,
  readOnly = false,
  centered = false,
  pageContext,
  onSelectStarterPrompt,
  onOpenArtifact,
  onFeedback,
  onRegenerate,
  onNavigateDeepLink,
}: CopilotMessageStreamProps) {
  const { user } = useAuth();
  const isAdmin = !!user && ["super_admin", "admin", "dev"].includes(user.role);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({});
  const [expandedSql, setExpandedSql] = useState<Record<string, boolean>>({});
  const [expandedUserMsgs, setExpandedUserMsgs] = useState<Record<string, boolean>>({});
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [waCopiedId, setWaCopiedId] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<Record<string, boolean>>({});
  const [actionResult, setActionResult] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState<Record<string, string>>({});

  function handleScroll() {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    setIsAtBottom(distance < 90);
  }

  useEffect(() => {
    if (isAtBottom) {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, streaming, isAtBottom]);

  function jumpToLatest() {
    setIsAtBottom(true);
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }

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
      <div className="flex-1 flex items-center justify-center p-6 text-sm text-[var(--rl-text-muted)]">
        <ArrowsClockwise size={18} className="animate-spin mr-2" />
        Loading conversation...
      </div>
    );
  }

  return (
    <div className="relative flex-1 min-h-0 flex flex-col">
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 sm:px-6 py-5"
      >
        <div className={`flex flex-col gap-5 ${centered ? "mx-auto max-w-3xl" : "w-full"}`}>
          {messages.length === 0 && (
            <div className="mx-auto max-w-xl py-8 text-center flex flex-col items-center gap-4">
              <div className="size-12 rounded-[var(--rl-radius-md)] bg-[var(--rl-black)] text-white grid place-items-center shadow-sm">
                <Robot size={24} weight="fill" />
              </div>
              <div className="flex flex-col gap-1.5">
                <h4 className="text-base font-bold text-[var(--rl-text-strong)]">
                  RiskLocker Intelligence Copilot
                </h4>
                <p className="text-sm text-[var(--rl-text-muted)] leading-relaxed">
                  {readOnly
                    ? "Select a conversation from the left sidebar to inspect messages, SQL steps, and exported workbooks."
                    : "Ask anything across your motor ledger, comparison matrices, clients, plates, or paste up to 400+ entries for instant cross-checking."}
                </p>
              </div>
              {!readOnly && (
                <div className="grid sm:grid-cols-2 gap-2.5 text-left w-full pt-1">
                  {starters.map((s, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => onSelectStarterPrompt(s.prompt)}
                      className="w-full rounded-[var(--rl-radius-md)] border border-[var(--rl-border)] bg-white px-3.5 py-2.5 text-left hover:border-[var(--rl-black)] hover:bg-neutral-50 transition-colors cursor-pointer group"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-[var(--rl-text-strong)]">{s.label}</span>
                        <span className="text-[10px] text-[var(--rl-text-muted)] group-hover:text-[var(--rl-text-strong)]">
                          Use ↵
                        </span>
                      </div>
                      <div className="mt-1 text-xs text-[var(--rl-text-muted)] line-clamp-1">{s.prompt}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {messages.map((m, idx) => {
            const isUser = m.role === "user";
            const prevUserText =
              !isUser && idx > 0 && messages[idx - 1]?.role === "user"
                ? messages[idx - 1].content_markdown
                : "";
            const stepsOpen = expandedSteps[m.id] ?? !!m.isStreaming;

            // Collapsible long user pasted prompt (>6 lines or >500 chars)
            const userLines = isUser ? m.content_markdown.split(/\r?\n/).length : 0;
            const isLongUserPrompt = isUser && (userLines > 6 || m.content_markdown.length > 500);
            const userExpanded = !!expandedUserMsgs[m.id];

            if (isUser) {
              return (
                <div key={m.id} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl bg-[var(--rl-black)] text-white px-4 py-2.5 shadow-xs text-sm leading-relaxed">
                    {isLongUserPrompt && !userExpanded ? (
                      <div className="flex flex-col gap-1.5">
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-semibold text-xs text-neutral-200">
                            Bulk Prompt · {userLines.toLocaleString()} lines ({m.content_markdown.length.toLocaleString()} chars)
                          </span>
                          <button
                            type="button"
                            onClick={() => setExpandedUserMsgs((p) => ({ ...p, [m.id]: true }))}
                            className="text-xs font-semibold underline text-emerald-300 hover:text-emerald-200 cursor-pointer shrink-0"
                          >
                            Show full
                          </button>
                        </div>
                        <div className="text-xs text-neutral-300 line-clamp-2 whitespace-pre-wrap">
                          {m.content_markdown}
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-1.5">
                        <div className="whitespace-pre-wrap">{m.content_markdown}</div>
                        {isLongUserPrompt && (
                          <button
                            type="button"
                            onClick={() => setExpandedUserMsgs((p) => ({ ...p, [m.id]: false }))}
                            className="self-end text-[11px] font-medium underline text-neutral-300 hover:text-white cursor-pointer"
                          >
                            Collapse
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            }

            return (
              <div key={m.id} className="flex flex-col items-start w-full">
                <div className="w-full flex flex-col gap-2.5 rounded-2xl bg-white border border-[var(--rl-border)] px-4 py-3.5 shadow-2xs text-[var(--rl-text-strong)]">
                  {/* Live Queue / Busy Wait Banner */}
                  {m.isStreaming && queueStatus && (
                    <div className="flex items-center gap-2 rounded-[var(--rl-radius-sm)] border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                      <HourglassMedium size={14} weight="fill" className="text-amber-600 animate-pulse shrink-0" />
                      <span>
                        {queueStatus.reason === "barrel_reload"
                          ? `AI is momentarily busy — resuming in ~${queueStatus.wait_seconds ?? 5}s...`
                          : `Waiting for your turn (#${queueStatus.position ?? 1} in queue)...`}
                      </span>
                    </div>
                  )}

                  {/* Thinking & Tool Steps */}
                  {m.tool_trace && m.tool_trace.length > 0 && (
                    <div className="rounded-[var(--rl-radius-sm)] border border-neutral-200 bg-neutral-50/80 px-3 py-2">
                      <button
                        type="button"
                        onClick={() => setExpandedSteps((p) => ({ ...p, [m.id]: !stepsOpen }))}
                        className="w-full flex items-center justify-between text-xs font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] cursor-pointer"
                      >
                        <span className="flex items-center gap-1.5">
                          {m.isStreaming ? (
                            <ArrowsClockwise size={13} className="animate-spin text-emerald-600" />
                          ) : (
                            <Sparkle size={13} weight="fill" className="text-emerald-600" />
                          )}
                          {m.isStreaming
                            ? "Investigating database..."
                            : `Checked ${m.tool_trace.length} live step${m.tool_trace.length === 1 ? "" : "s"}`}
                        </span>
                        {stepsOpen ? <CaretDown size={13} /> : <CaretRight size={13} />}
                      </button>

                      {stepsOpen && (
                        <div className="mt-2 flex flex-col gap-1.5 border-t border-neutral-200 pt-2">
                          {m.tool_trace.map((step) => {
                            const sqlKey = `${m.id}_${step.step_id}`;
                            const showSql = !!expandedSql[sqlKey];
                            return (
                              <div key={step.step_id} className="text-xs">
                                <div className="flex items-center justify-between gap-2">
                                  <div className="flex items-center gap-1.5 min-w-0">
                                    {step.status === "running" ? (
                                      <ArrowsClockwise size={12} className="animate-spin text-blue-600 shrink-0" />
                                    ) : step.status === "error" ? (
                                      <WarningCircle size={12} weight="fill" className="text-rose-600 shrink-0" />
                                    ) : (
                                      <CheckCircle size={12} weight="fill" className="text-emerald-600 shrink-0" />
                                    )}
                                    <span className="truncate text-[var(--rl-text)]">{step.label}</span>
                                  </div>
                                  <div className="flex items-center gap-2 shrink-0 font-mono text-[11px] text-[var(--rl-text-muted)]">
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
                                  <pre className="mt-1.5 overflow-x-auto rounded bg-neutral-900 p-2 font-mono text-[11px] text-neutral-100">
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
                  {m.content_markdown ? (
                    <CopilotMarkdown content={m.content_markdown} onNavigateDeepLink={onNavigateDeepLink} />
                  ) : m.isStreaming ? (
                    <div className="flex items-center gap-2 py-1 text-sm text-[var(--rl-text-muted)]">
                      <span className="inline-block size-2 rounded-full bg-emerald-500 animate-ping" />
                      <span>Thinking...</span>
                    </div>
                  ) : null}

                  {/* Verified Navigation & Auto-Select Deep-Links */}
                  {m.verified_links && m.verified_links.length > 0 && (
                    <div className="pt-2.5 border-t border-neutral-100 flex flex-wrap gap-1.5">
                      {m.verified_links.map((lnk, lIdx) => {
                        const isBatch = lnk.kind === "ledger_batch";
                        return (
                          <Link
                            key={lIdx}
                            href={lnk.href as Route}
                            onClick={() => onNavigateDeepLink?.()}
                            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
                              isBatch
                                ? "border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-700"
                                : "border-neutral-200 bg-neutral-50 hover:bg-neutral-900 hover:text-white hover:border-neutral-900 text-[var(--rl-text-strong)]"
                            }`}
                          >
                            {linkIcon(lnk.kind)}
                            <span>{lnk.label}</span>
                            <ArrowSquareOut size={11} weight="bold" />
                          </Link>
                        );
                      })}
                    </div>
                  )}

                  {/* Excel / Table Artifacts */}
                  {m.artifacts && m.artifacts.length > 0 && (
                    <div className="flex flex-col gap-2">
                      {m.artifacts.map((art) => (
                        <div
                          key={art.id}
                          className="rounded-[var(--rl-radius-sm)] border border-emerald-200 bg-emerald-50/50 p-3 flex flex-wrap items-center justify-between gap-2"
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className="size-8 rounded bg-emerald-700 text-white grid place-items-center shrink-0">
                              <FileXls size={18} weight="fill" />
                            </div>
                            <div className="min-w-0">
                              <div className="text-xs font-bold text-[var(--rl-text-strong)] truncate">{art.filename}</div>
                              <div className="text-[11px] text-[var(--rl-text-muted)] font-mono">
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
                              className="h-7 text-xs"
                            >
                              Preview Table
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => handleDownloadArtifact(art)}
                              icon={<DownloadSimple size={13} weight="bold" />}
                              className="h-7 text-xs"
                            >
                              Download .xlsx
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Human-in-the-Loop Action Cards */}
                  {m.action_cards && m.action_cards.length > 0 && (
                    <div className="flex flex-col gap-2">
                      {m.action_cards.map((act, aIdx) => {
                        const aKey = `${m.id}_${aIdx}`;
                        if (act.type === "session_cleanup") {
                          return (
                            <Card key={aIdx} className="p-3 border border-[var(--rl-border)] bg-neutral-50 flex flex-col gap-2">
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
                                <div className="flex flex-col gap-1.5">
                                  {actionError[aKey] && (
                                    <div className="text-xs text-rose-700">{actionError[aKey]}</div>
                                  )}
                                  {!readOnly && (
                                    <Button
                                      type="button"
                                      size="sm"
                                      loading={!!actionBusy[aKey]}
                                      onClick={() => handleCleanDuplicates(aKey, act.session_ids_to_trash || [])}
                                      icon={<Trash size={13} />}
                                      className="h-7 text-xs w-fit"
                                    >
                                      Confirm &amp; Move {act.redundant_count} Duplicates to Trash
                                    </Button>
                                  )}
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
                  {!m.isStreaming && m.content_markdown && (
                    <div className="pt-2 border-t border-neutral-100 flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--rl-text-muted)]">
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => {
                            navigator.clipboard.writeText(m.content_markdown);
                            setCopiedId(m.id);
                            setTimeout(() => setCopiedId(null), 1500);
                          }}
                          className="inline-flex items-center gap-1 rounded px-2 py-1 hover:bg-neutral-100 hover:text-[var(--rl-text-strong)] cursor-pointer"
                        >
                          {copiedId === m.id ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
                          <span>{copiedId === m.id ? "Copied" : "Copy"}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            navigator.clipboard.writeText(stripMarkdownForWhatsApp(m.content_markdown));
                            setWaCopiedId(m.id);
                            setTimeout(() => setWaCopiedId(null), 1500);
                          }}
                          className="inline-flex items-center gap-1 rounded px-2 py-1 hover:bg-emerald-50 hover:text-emerald-700 cursor-pointer"
                        >
                          <WhatsappLogo size={13} weight="fill" />
                          <span>{waCopiedId === m.id ? "WhatsApp Ready!" : "WhatsApp"}</span>
                        </button>
                        {!readOnly && prevUserText && (
                          <button
                            type="button"
                            disabled={streaming}
                            onClick={() => onRegenerate(prevUserText)}
                            className="inline-flex items-center gap-1 rounded px-2 py-1 hover:bg-neutral-100 hover:text-[var(--rl-text-strong)] cursor-pointer disabled:opacity-40"
                          >
                            <ArrowsClockwise size={13} />
                            <span>Retry</span>
                          </button>
                        )}
                      </div>

                      <div className="flex items-center gap-1.5">
                        {m.model_used === "direct-db-verified" ? (
                          <span className="font-mono text-[11px] text-emerald-700 font-medium">
                            0 tok · Direct DB Verified
                          </span>
                        ) : typeof m.total_tokens === "number" && m.total_tokens > 0 ? (
                          <span className="font-mono text-[11px] text-neutral-400">
                            {m.total_tokens.toLocaleString()} tok{m.model_used ? ` · ${m.model_used.replace("gemini-", "")}` : ""}
                          </span>
                        ) : null}
                        {!readOnly && (
                          <>
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
                              <ThumbsUp size={13} weight={m.feedback === "up" ? "fill" : "regular"} />
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
                              <ThumbsDown size={13} weight={m.feedback === "down" ? "fill" : "regular"} />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={endRef} />
        </div>
      </div>

      {/* Jump to Latest Button when user scrolled up */}
      {!isAtBottom && messages.length > 0 && (
        <button
          type="button"
          onClick={jumpToLatest}
          className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 inline-flex items-center gap-1.5 rounded-full border border-[var(--rl-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--rl-text-strong)] shadow-md hover:bg-neutral-50 cursor-pointer"
        >
          <ArrowDown size={13} weight="bold" />
          <span>Jump to latest</span>
        </button>
      )}
    </div>
  );
}
