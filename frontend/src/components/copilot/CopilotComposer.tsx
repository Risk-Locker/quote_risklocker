"use client";

import React, { useEffect, useRef, useState } from "react";
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

  function handleSubmit() {
    const trimmed = text.trim();
    if (!trimmed || streaming || isDisabledByQuota) return;
    onSend(trimmed, { enableWebResearch: webResearch, usePageContext: contextPinned });
    setText("");
  }

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

        {/* Subtle Status Pill (only when paused or running low) */}
        {quota && (!quota.enabled || quota.turns_remaining <= 5) && (
          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
              !quota.enabled
                ? "border-rose-200 bg-rose-50 text-rose-700"
                : "border-amber-200 bg-amber-50 text-amber-800"
            }`}
            title={`Daily chats left: ${quota.turns_remaining}/${quota.turns_limit}`}
          >
            {!quota.enabled ? "Paused by Admin" : `${quota.turns_remaining} chats left`}
          </span>
        )}
      </div>

      {/* Input Area */}
      <div className="flex items-end gap-2">
        <div className="flex-1">
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
                : "Ask anything or paste vehicle plates to check..."
            }
            className="w-full resize-none overflow-y-auto rounded-[var(--rl-radius-md)] border border-[var(--rl-border)] bg-[var(--rl-bg)]/70 px-3.5 py-2.5 text-sm leading-relaxed text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)] focus:outline-none focus:border-[var(--rl-black)] focus:bg-white disabled:opacity-60"
          />
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
    </div>
  );
}
