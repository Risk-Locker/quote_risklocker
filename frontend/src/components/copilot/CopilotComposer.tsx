"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  FileXls,
  Globe,
  PaperPlaneRight,
  StopCircle,
  X,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { CopilotConfirmModal } from "./CopilotConfirmModal";
import type { CopilotPageContext, CopilotUserQuota } from "./types";

type CopilotComposerProps = {
  streaming: boolean;
  quota: CopilotUserQuota | null;
  pageContext: CopilotPageContext;
  contextPinned: boolean;
  onToggleContextPinned: (pinned: boolean) => void;
  onSend: (text: string, opts: { enableWebResearch: boolean; usePageContext: boolean }) => void;
  onStop: () => void;
  externalDraft?: string;
  onConsumeExternalDraft?: () => void;
};

function formatCompactTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10_000 ? 0 : 1)}k`;
  return String(n);
}

export function CopilotComposer({
  streaming,
  quota,
  pageContext,
  contextPinned,
  onToggleContextPinned,
  onSend,
  onStop,
  externalDraft,
  onConsumeExternalDraft,
}: CopilotComposerProps) {
  const [text, setText] = useState("");
  const [webResearch, setWebResearch] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (externalDraft) {
      setText(externalDraft);
      onConsumeExternalDraft?.();
      setTimeout(() => textareaRef.current?.focus(), 30);
    }
  }, [externalDraft, onConsumeExternalDraft]);

  // Smooth auto-growing height (2 to ~10 lines)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(208, Math.max(48, el.scrollHeight))}px`;
  }, [text]);

  const isDisabledByQuota = !!quota && (!quota.enabled || quota.is_exhausted);

  const draftStats = useMemo(() => {
    const trimmed = text.trim();
    if (!trimmed) {
      return { inputTokens: 0, lowTotal: 0, highTotal: 0, lines: 0 };
    }
    const lines = trimmed.split(/\r?\n/).filter((l) => l.trim().length > 0).length;
    // System prompt + tool declarations overhead (~1,900 tok) + ~0.28 tok/char
    const inputTokens = Math.max(300, Math.round(1_900 + trimmed.length * 0.28));
    // Bulk checks normally resolve in 1 tool hop + 1 answer hop (low ~2x, high ~3.2x)
    const lowTotal = Math.round(inputTokens * 1.4 + 400);
    const highTotal = Math.round(inputTokens * 3.0 + 1_500);
    return { inputTokens, lowTotal, highTotal, lines };
  }, [text]);

  const warnThreshold = quota?.warn_turn_tokens ?? 15_000;
  const needsConfirmation = useMemo(() => {
    if (!text.trim()) return false;
    if (draftStats.highTotal >= warnThreshold) return true;
    if (draftStats.lines >= 40) return true;
    if (quota && quota.tokens_remaining > 0 && draftStats.highTotal >= quota.tokens_remaining * 0.5) {
      return true;
    }
    return false;
  }, [text, draftStats, warnThreshold, quota]);

  function dispatchSend() {
    const trimmed = text.trim();
    if (!trimmed || streaming || isDisabledByQuota) return;
    onSend(trimmed, { enableWebResearch: webResearch, usePageContext: contextPinned });
    setText("");
    setConfirmOpen(false);
  }

  function handleSubmit() {
    const trimmed = text.trim();
    if (!trimmed || streaming || isDisabledByQuota) return;
    if (needsConfirmation) {
      setConfirmOpen(true);
      return;
    }
    dispatchSend();
  }

  const barrels = quota?.barrels || [];

  return (
    <div className="border-t border-[var(--rl-border)] bg-white px-4 py-3 flex flex-col gap-2 shrink-0">
      {/* Options & Live Token/Barrel Telemetry Row */}
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          {pageContext.anchor_label && contextPinned ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-neutral-900 text-white px-2.5 py-0.5 text-[11px] font-medium">
              <span>Context: {pageContext.anchor_label}</span>
              <button
                type="button"
                onClick={() => onToggleContextPinned(false)}
                className="hover:text-neutral-300 cursor-pointer"
                title="Switch to whole system"
              >
                <X size={10} weight="bold" />
              </button>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full border border-[var(--rl-border)] bg-neutral-50 text-[var(--rl-text-muted)] px-2.5 py-0.5 text-[11px] font-medium">
              Whole System
              {pageContext.anchor_label && (
                <button
                  type="button"
                  onClick={() => onToggleContextPinned(true)}
                  className="ml-1 text-blue-700 hover:underline cursor-pointer"
                >
                  + Pin {pageContext.anchor_label}
                </button>
              )}
            </span>
          )}

          <button
            type="button"
            onClick={() => setWebResearch((v) => !v)}
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold transition-colors cursor-pointer ${
              webResearch
                ? "border-blue-600 bg-blue-50 text-blue-800"
                : "border-[var(--rl-border)] bg-white text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
            title="Allow Gemini Google Search for external JPJ/vehicle lookups (OFF by default to save tokens)"
          >
            <Globe size={12} weight={webResearch ? "fill" : "regular"} />
            <span>Web: {webResearch ? "ON" : "OFF"}</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setText((prev) =>
                prev.trim()
                  ? `${prev.trim()} (export results to an Excel .xlsx file)`
                  : "Export a clean Excel (.xlsx) workbook of "
              );
              textareaRef.current?.focus();
            }}
            className="inline-flex items-center gap-1 rounded-full border border-[var(--rl-border)] bg-white px-2.5 py-0.5 text-[11px] font-medium text-[var(--rl-text-muted)] hover:text-emerald-700 hover:border-emerald-300 cursor-pointer"
          >
            <FileXls size={12} />
            <span>Excel</span>
          </button>
        </div>

        {/* Live Quota & Barrel Capacity Pills */}
        {quota && (
          <div className="flex flex-wrap items-center gap-1.5">
            {barrels.length > 0 && (
              <span
                className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-neutral-200 bg-neutral-50 text-[var(--rl-text-muted)]"
                title="Live 80s barrel TPM remaining across active Chatbot models"
              >
                {barrels
                  .slice(0, 2)
                  .map(
                    (b, idx) =>
                      `M${idx + 1}: ${formatCompactTokens(b.tpm_remaining)}${
                        b.reload_in_sec > 0 ? ` (${Math.ceil(b.reload_in_sec)}s)` : ""
                      }`
                  )
                  .join(" · ")}
              </span>
            )}
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                !quota.enabled
                  ? "border-rose-200 bg-rose-50 text-rose-700"
                  : quota.tokens_remaining <= 20_000 || quota.turns_remaining <= 5
                  ? "border-amber-200 bg-amber-50 text-amber-800"
                  : "border-neutral-200 bg-neutral-50 text-[var(--rl-text-muted)]"
              }`}
              title={`Daily chats left: ${quota.turns_remaining}/${quota.turns_limit}`}
            >
              {!quota.enabled
                ? "Paused by Admin"
                : `${formatCompactTokens(quota.tokens_remaining)}/${formatCompactTokens(quota.tokens_limit)} tok · ${quota.turns_remaining} chats`}
            </span>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="flex items-end gap-2">
        <div className="flex-1 flex flex-col gap-1">
          <textarea
            ref={textareaRef}
            rows={2}
            value={text}
            disabled={isDisabledByQuota}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder={
              isDisabledByQuota
                ? "Copilot quota reached or paused by admin..."
                : "Ask anything or paste up to 400+ plates — search ledgers, compare years, or export Excel..."
            }
            className="w-full resize-none overflow-y-auto rounded-[var(--rl-radius-md)] border border-[var(--rl-border)] bg-[var(--rl-bg)]/70 px-3.5 py-2.5 text-sm leading-relaxed text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)] focus:outline-none focus:border-[var(--rl-black)] focus:bg-white disabled:opacity-60"
          />
          {text.trim().length > 0 && (
            <div className="flex items-center justify-between px-1 text-[11px] font-mono text-[var(--rl-text-muted)]">
              <div className="flex items-center gap-2">
                <span
                  className={
                    needsConfirmation ? "text-amber-700 font-semibold" : "text-[var(--rl-text-muted)]"
                  }
                >
                  ~{draftStats.inputTokens.toLocaleString()} input tok (est. {formatCompactTokens(draftStats.lowTotal)}–{formatCompactTokens(draftStats.highTotal)} total)
                </span>
                {draftStats.lines >= 3 && (
                  <span className="rounded bg-neutral-100 px-1.5 py-0.2 text-[10px] text-neutral-700">
                    {draftStats.lines.toLocaleString()} lines
                  </span>
                )}
              </div>
              {needsConfirmation && (
                <span className="text-amber-700 font-sans text-[11px] font-medium">
                  Confirmation required before send
                </span>
              )}
            </div>
          )}
        </div>

        {streaming ? (
          <Button
            type="button"
            variant="danger"
            size="sm"
            onClick={onStop}
            icon={<StopCircle size={16} weight="fill" />}
            className="h-10 px-3.5 shrink-0 mb-0.5"
          >
            Stop
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            onClick={handleSubmit}
            disabled={!text.trim() || isDisabledByQuota}
            icon={<PaperPlaneRight size={16} weight="fill" />}
            className="h-10 px-3.5 shrink-0 mb-0.5"
          >
            Send
          </Button>
        )}
      </div>

      <CopilotConfirmModal
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        estimatedInputTokens={draftStats.inputTokens}
        estimatedLowTotal={draftStats.lowTotal}
        estimatedHighTotal={draftStats.highTotal}
        lineCount={draftStats.lines}
        quota={quota}
        onConfirm={dispatchSend}
      />
    </div>
  );
}
