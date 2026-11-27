"use client";

import React, { useRef, useState } from "react";
import {
  FileXls,
  Globe,
  PaperPlaneRight,
  StopCircle,
  X,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    if (externalDraft) {
      setText(externalDraft);
      onConsumeExternalDraft?.();
      setTimeout(() => textareaRef.current?.focus(), 30);
    }
  }, [externalDraft, onConsumeExternalDraft]);

  const isDisabledByQuota = !!quota && (!quota.enabled || quota.is_exhausted);

  function submit() {
    const trimmed = text.trim();
    if (!trimmed || streaming || isDisabledByQuota) return;
    onSend(trimmed, { enableWebResearch: webResearch, usePageContext: contextPinned });
    setText("");
  }

  return (
    <div className="border-t border-[var(--rl-border)] bg-white p-3 space-y-2 shrink-0">
      {/* Options & Active Context Row */}
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          {pageContext.anchor_label && contextPinned ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-neutral-900 text-white px-2 py-0.5 text-[10px] font-medium">
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
            <span className="inline-flex items-center gap-1 rounded-full border border-[var(--rl-border)] bg-neutral-50 text-[var(--rl-text-muted)] px-2 py-0.5 text-[10px] font-medium">
              Whole System Context
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
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-colors cursor-pointer ${
              webResearch
                ? "border-blue-600 bg-blue-50 text-blue-800"
                : "border-[var(--rl-border)] bg-white text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
            title="Allow Gemini Google Search for external JPJ/vehicle lookups (OFF by default to save tokens)"
          >
            <Globe size={11} weight={webResearch ? "fill" : "regular"} />
            <span>Web Research: {webResearch ? "ON" : "OFF"}</span>
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
            className="inline-flex items-center gap-1 rounded-full border border-[var(--rl-border)] bg-white px-2 py-0.5 text-[10px] font-medium text-[var(--rl-text-muted)] hover:text-emerald-700 hover:border-emerald-300 cursor-pointer"
          >
            <FileXls size={11} />
            <span>Excel Export</span>
          </button>
        </div>

        {quota && (
          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
              !quota.enabled
                ? "border-rose-200 bg-rose-50 text-rose-700"
                : quota.turns_remaining <= 5
                ? "border-amber-200 bg-amber-50 text-amber-800"
                : "border-neutral-200 bg-neutral-50 text-[var(--rl-text-muted)]"
            }`}
          >
            {!quota.enabled
              ? "Paused by Admin"
              : `${quota.turns_remaining}/${quota.turns_limit} chats left today`}
          </span>
        )}
      </div>

      {/* Input Area */}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          rows={2}
          value={text}
          disabled={isDisabledByQuota}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={
            isDisabledByQuota
              ? "Copilot quota reached or paused by admin..."
              : "Ask anything — search plates, compare years, analyze renewals, or export Excel... (Enter to send)"
          }
          className="flex-1 resize-none rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] px-3 py-2 text-xs text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)] focus:outline-none focus:border-[var(--rl-black)] focus:bg-white disabled:opacity-60"
        />

        {streaming ? (
          <Button
            type="button"
            variant="danger"
            size="sm"
            onClick={onStop}
            icon={<StopCircle size={15} weight="fill" />}
            className="h-9 px-3 shrink-0"
          >
            Stop
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            onClick={submit}
            disabled={!text.trim() || isDisabledByQuota}
            icon={<PaperPlaneRight size={15} weight="fill" />}
            className="h-9 px-3 shrink-0"
          >
            Send
          </Button>
        )}
      </div>
    </div>
  );
}
