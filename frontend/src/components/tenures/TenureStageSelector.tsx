"use client";

import React from "react";
import { CheckCircle, XCircle, Check, UploadSimple } from "@phosphor-icons/react";
import { useToast } from "@/components/ui/toast";
import type { TenureRow } from "./types";
import { formatDateTimeSafe } from "./types";

export interface TenureStageSelectorProps {
  tenure: TenureRow;
  compact?: boolean;
  onPatchField: (tenureId: string, updates: Partial<TenureRow>) => Promise<void>;
  onOpenCovernoteUpload: (tenure: TenureRow) => void;
  onOpenHitModal: (tenure: TenureRow) => void;
  onOpenMissModal: (tenure: TenureRow) => void;
}

export function TenureStageSelector({
  tenure: t,
  compact = false,
  onPatchField,
  onOpenCovernoteUpload,
  onOpenHitModal,
  onOpenMissModal,
}: TenureStageSelectorProps) {
  const { toast } = useToast();
  const isHit = t.stage === "Close - Win";
  const isMiss = t.stage === "Close - Lose";
  const canHit = t.stage === "Issue Policy";

  const linearStages = [
    { id: "Quotations", label: "Quotations", shortLabel: "Quotes" },
    { id: "Material to Client", label: "Material to Client", shortLabel: "Sent" },
    { id: "Issue Policy", label: "Issue Policy", shortLabel: "Policy" },
  ];

  const currentIdx = linearStages.findIndex((s) => s.id === t.stage);

  const getStageTimestamp = (stId: string) => {
    return t.stage_history?.[stId] || (t.stage === stId ? t.stage_updated_at : null);
  };

  const getStageTooltip = (stId: string, label: string) => {
    const ts = getStageTimestamp(stId);
    if (ts) {
      return `${label}\nUpdated: ${formatDateTimeSafe(ts)}`;
    }
    return `${label}\nStatus: Not reached yet`;
  };

  if (isHit) {
    const hitTs = t.stage_history?.["Close - Win"] || t.stage_updated_at;
    return (
      <div className="flex items-center gap-1.5">
        <span
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-100 text-emerald-900 border border-emerald-300 text-[11px] font-bold shadow-2xs cursor-help"
          title={`✓ HIT (Won)\nUpdated: ${formatDateTimeSafe(hitTs)}`}
        >
          <CheckCircle size={13} weight="fill" className="text-emerald-700" />
          <span>✓ HIT (Won)</span>
        </span>
        <button
          type="button"
          onClick={() => onPatchField(t.id, { stage: "Issue Policy", status: "draft" })}
          className="text-[10px] text-neutral-400 hover:text-neutral-700 underline cursor-pointer"
          title="Revert back to Issue Policy (will delete empty auto-created next-year renewal)"
        >
          Revert
        </button>
      </div>
    );
  }

  if (isMiss) {
    const missTs = t.stage_history?.["Close - Lose"] || t.stage_updated_at;
    return (
      <div className="flex items-center gap-1.5">
        <span
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-rose-100 text-rose-900 border border-rose-300 text-[11px] font-bold shadow-2xs cursor-help"
          title={`✕ MISS (Lost)\nUpdated: ${formatDateTimeSafe(missTs)}`}
        >
          <XCircle size={13} weight="fill" className="text-rose-700" />
          <span>✕ MISS (Lost)</span>
        </span>
        <button
          type="button"
          onClick={() => onPatchField(t.id, { stage: "Quotations", status: "draft" })}
          className="text-[10px] text-neutral-400 hover:text-neutral-700 underline cursor-pointer"
          title="Reopen quote"
        >
          Reopen
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {/* Straight Arrow Progress Bar */}
      <div className="inline-flex items-center bg-neutral-100/90 p-0.5 rounded border border-neutral-200 text-[10px] font-semibold">
        {linearStages.map((st, idx) => {
          const isActive = t.stage === st.id;
          const isCompleted = currentIdx > idx;
          const tooltipText = getStageTooltip(st.id, st.label);

          return (
            <React.Fragment key={st.id}>
              <button
                type="button"
                onClick={() => {
                  if (st.id === "Issue Policy") {
                    const hasCn = Boolean(t.covernote_policy || t.is_covernote_issued);
                    if (!hasCn) {
                      onOpenCovernoteUpload(t);
                      return;
                    }
                    onPatchField(t.id, { stage: "Issue Policy" });
                  } else {
                    const isPolicyIssued = Boolean(
                      t.covernote_policy ||
                        t.is_covernote_issued ||
                        t.stage === "Issue Policy" ||
                        t.stage === "Close - Win" ||
                        t.status === "hit"
                    );
                    if (isPolicyIssued && (st.id === "Quotations" || st.id === "Material to Client")) {
                      toast(
                        `Policy pipeline is locked for ${t.vehicle_no || "this vehicle"} because an official Cover Note was issued. Unlink the Cover Note in Comparison first.`,
                        "warning"
                      );
                      return;
                    }
                    onPatchField(t.id, { stage: st.id });
                  }
                }}
                className={`${compact ? "px-1.5 py-0.5" : "px-2 py-0.5"} rounded transition-all cursor-pointer flex items-center gap-1 ${
                  isActive
                    ? "bg-white text-neutral-900 shadow-2xs font-bold border border-neutral-300/80"
                    : isCompleted
                    ? "text-emerald-700 hover:text-emerald-900 font-medium"
                    : "text-neutral-400 hover:text-neutral-700"
                }`}
                title={
                  st.id === "Issue Policy" && !Boolean(t.covernote_policy || t.is_covernote_issued)
                    ? "Official Cover Note PDF required to reach Issue Policy stage. Click to upload."
                    : Boolean(t.covernote_policy || t.is_covernote_issued) &&
                      (st.id === "Quotations" || st.id === "Material to Client")
                    ? "Cover Note is active. Unlink Cover Note in Marketing Comparison first to revert stage."
                    : tooltipText
                }
              >
                {isCompleted && <Check size={10} weight="bold" className="text-emerald-600 shrink-0" />}
                <span>{compact ? st.shortLabel : st.label}</span>
                {st.id === "Issue Policy" && !Boolean(t.covernote_policy || t.is_covernote_issued) && (
                  <UploadSimple size={10} className="text-amber-600 shrink-0" />
                )}
              </button>
              {idx < linearStages.length - 1 && (
                <span className="text-neutral-300 px-0.5 select-none font-bold">→</span>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* HIT Button: Only clickable if Policy is Issued */}
      {canHit ? (
        <button
          type="button"
          onClick={() => onOpenHitModal(t)}
          className="px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[10px] shadow-2xs cursor-pointer transition-colors flex items-center gap-1"
          title="Policy is issued! Click to review policy details and mark as HIT (won)"
        >
          <CheckCircle size={11} weight="bold" />
          <span>Hit</span>
        </button>
      ) : (
        <button
          type="button"
          disabled
          className="px-2 py-1 rounded bg-neutral-100 text-neutral-400 border border-neutral-200 text-[10px] font-medium cursor-not-allowed opacity-60 flex items-center gap-1"
          title="Policy must be in 'Issue Policy' stage before marking as Hit"
        >
          <svg className="w-2.5 h-2.5 text-neutral-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
          </svg>
          <span>Hit</span>
        </button>
      )}

      {/* MISS Button: Always accessible anytime */}
      <button
        type="button"
        onClick={() => onOpenMissModal(t)}
        className="px-2 py-1 rounded bg-rose-50 hover:bg-rose-100 text-rose-700 hover:text-rose-900 border border-rose-200 hover:border-rose-300 font-bold text-[10px] cursor-pointer transition-colors flex items-center gap-0.5"
        title="Deal lost / Miss (choose to keep client or drop)"
      >
        <XCircle size={11} weight="bold" />
        <span>Miss</span>
      </button>
    </div>
  );
}
