"use client";

import React from "react";
import {
  ArrowsClockwise,
  CheckCircle,
  Prohibit,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import type { RedetectJobState } from "./useDeepRedetect";

function formatClock(sec: number): string {
  const m = String(Math.floor(sec / 60)).padStart(2, "0");
  const s = String(sec % 60).padStart(2, "0");
  return `${m}:${s}`;
}

export function DeepRedetectProgressBanner({
  job,
  elapsedSeconds,
  cancelling,
  onCancel,
  onDismiss,
}: {
  job: RedetectJobState | null;
  elapsedSeconds: number;
  cancelling: boolean;
  onCancel: () => void;
  onDismiss: () => void;
}) {
  if (!job) return null;

  const isRunning = job.status === "running";
  const isCompleted = job.status === "completed";
  const isCancelled = job.status === "cancelled";

  const tone = isRunning
    ? "border-amber-200 bg-amber-50/90 text-amber-950"
    : isCompleted
      ? "border-emerald-200 bg-emerald-50/90 text-emerald-950"
      : isCancelled
        ? "border-neutral-300 bg-neutral-100 text-neutral-900"
        : "border-rose-200 bg-rose-50 text-rose-950";

  const headerTitle = isRunning
    ? job.total_quotes > 1
      ? `Re-detecting Quote ${job.current_quote_index} of ${job.total_quotes}${job.current_quote_name ? ` · ${job.current_quote_name}` : ""}`
      : `Deep Re-detecting${job.current_quote_name ? ` · ${job.current_quote_name}` : ""}`
    : isCompleted
      ? "Deep Re-detect Complete"
      : isCancelled
        ? "Re-detect Cancelled"
        : "Re-detect Failed";

  return (
    <div
      role="status"
      aria-live="polite"
      className={`rounded-xl border px-4 py-3 shadow-xs transition-all no-print print:hidden ${tone}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-2.5 min-w-0 flex-1">
          <div className="mt-0.5 shrink-0">
            {isRunning ? (
              <ArrowsClockwise size={18} weight="bold" className="animate-spin text-amber-700" />
            ) : isCompleted ? (
              <CheckCircle size={18} weight="fill" className="text-emerald-600" />
            ) : isCancelled ? (
              <Prohibit size={18} weight="bold" className="text-neutral-600" />
            ) : (
              <WarningCircle size={18} weight="fill" className="text-rose-600" />
            )}
          </div>
          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-bold tracking-tight">{headerTitle}</span>
              <span className="rounded-full bg-white/80 border border-black/10 px-2 py-0.5 text-[10px] font-mono font-bold">
                {job.progress_pct}%
              </span>
              {isRunning && (
                <span className="text-[10px] font-mono font-semibold opacity-80">
                  {formatClock(elapsedSeconds)}
                </span>
              )}
              {isRunning && job.current_step_label && (
                <span className="text-[11px] font-semibold opacity-90">
                  — {job.current_step_label}
                </span>
              )}
            </div>

            <p className="text-xs opacity-90 leading-snug">
              {job.status === "failed" && job.error ? job.error : job.why_waiting}
            </p>

            {/* Step pipeline pills */}
            {job.steps?.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                {job.steps.map((step, i) => {
                  const chipClass =
                    step.status === "done"
                      ? "bg-emerald-600/15 text-emerald-900 border-emerald-500/30"
                      : step.status === "active"
                        ? "bg-[var(--rl-black)] text-white border-[var(--rl-black)]"
                        : step.status === "skipped"
                          ? "bg-white/40 text-neutral-500 border-black/10 line-through"
                          : "bg-white/60 text-neutral-600 border-black/10";
                  return (
                    <span
                      key={step.key}
                      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-semibold ${chipClass}`}
                    >
                      <span>{i + 1}.</span>
                      <span>{step.label}</span>
                    </span>
                  );
                })}
              </div>
            )}

            {/* Progress bar */}
            {isRunning && (
              <div className="h-1.5 w-full rounded-full bg-black/10 overflow-hidden mt-1">
                <div
                  className="h-full bg-amber-600 transition-all duration-300"
                  style={{ width: `${Math.max(4, Math.min(100, job.progress_pct))}%` }}
                />
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {isRunning ? (
            <Button
              type="button"
              variant="danger"
              size="sm"
              loading={cancelling}
              onClick={onCancel}
              className="h-7 px-2.5 text-xs"
            >
              {cancelling ? "Cancelling..." : "Cancel"}
            </Button>
          ) : (
            <button
              type="button"
              onClick={onDismiss}
              className="p-1 rounded hover:bg-black/10 transition-colors cursor-pointer"
              title="Dismiss"
              aria-label="Dismiss status"
            >
              <X size={14} weight="bold" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
