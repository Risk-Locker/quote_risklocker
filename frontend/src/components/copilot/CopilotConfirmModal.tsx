"use client";

import React from "react";
import { Warning } from "@phosphor-icons/react";
import { Dialog } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import type { CopilotUserQuota } from "./types";

type CopilotConfirmModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  estimatedInputTokens: number;
  estimatedLowTotal: number;
  estimatedHighTotal: number;
  lineCount: number;
  quota: CopilotUserQuota | null;
  onConfirm: () => void;
};

export function CopilotConfirmModal({
  open,
  onOpenChange,
  estimatedInputTokens,
  estimatedLowTotal,
  estimatedHighTotal,
  lineCount,
  quota,
  onConfirm,
}: CopilotConfirmModalProps) {
  const dailyRem = quota?.tokens_remaining ?? 0;
  const dailyLim = quota?.tokens_limit ?? 250_000;
  const maxTurnCap = quota?.max_tokens_per_turn ?? 150_000;
  const exceedsDaily = quota ? estimatedHighTotal > dailyRem : false;
  const totalBarrelTpm = (quota?.barrels || []).reduce((acc, b) => acc + (b.tpm_remaining || 0), 0);

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Confirm Heavy AI Query"
      description="This prompt is large and may consume substantial token capacity across multi-step verification."
      confirmLabel="Confirm & Send"
      confirmVariant="primary"
      onConfirm={onConfirm}
      maxWidth="md"
    >
      <div className="flex flex-col gap-3 text-xs">
        <div className="grid grid-cols-2 gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-neutral-50 p-3">
          <div>
            <span className="text-[11px] text-[var(--rl-text-muted)] block">Estimated Input</span>
            <span className="font-mono text-sm font-bold text-[var(--rl-text-strong)]">
              ~{estimatedInputTokens.toLocaleString()} tok
            </span>
          </div>
          <div>
            <span className="text-[11px] text-[var(--rl-text-muted)] block">Projected Turn Cost</span>
            <span className="font-mono text-sm font-bold text-[var(--rl-text-strong)]">
              ~{estimatedLowTotal.toLocaleString()}–{estimatedHighTotal.toLocaleString()} tok
            </span>
          </div>
          <div>
            <span className="text-[11px] text-[var(--rl-text-muted)] block">Remaining Daily Budget</span>
            <span className="font-mono text-xs font-semibold text-[var(--rl-text-strong)]">
              {dailyRem.toLocaleString()} / {dailyLim.toLocaleString()} tok
            </span>
          </div>
          <div>
            <span className="text-[11px] text-[var(--rl-text-muted)] block">80s Barrel Headroom</span>
            <span className="font-mono text-xs font-semibold text-[var(--rl-text-strong)]">
              {totalBarrelTpm > 0 ? `${totalBarrelTpm.toLocaleString()} tok` : "Auto-scheduled"}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {lineCount >= 10 && (
            <Badge variant="default" className="text-[10px]">
              {lineCount.toLocaleString()} lines detected (uses 1-pass bulk lookup when checking plates)
            </Badge>
          )}
          <Badge variant="default" className="text-[10px]">
            Per-turn safety cap: {maxTurnCap.toLocaleString()} tok
          </Badge>
        </div>

        {exceedsDaily && (
          <div className="flex items-start gap-2 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50 px-3 py-2 text-amber-900">
            <Warning size={15} weight="fill" className="shrink-0 mt-0.5 text-amber-600" />
            <span>
              Worst-case estimate may reach your remaining daily quota ({dailyRem.toLocaleString()} tok). The backend will still stop cleanly at your per-turn cap.
            </span>
          </div>
        )}
      </div>
    </Dialog>
  );
}
