"use client";

import React from "react";
import { ArrowsClockwise, XCircle } from "@phosphor-icons/react";
import type { StageSummary } from "./types";
import { STAGE_CONFIGS, STAGE_ORDER } from "./types";

export interface LedgerKpiCardsProps {
  summary: StageSummary | null;
  loadingSummary: boolean;
  stageFilter: string;
  onSelectStage: (stage: string) => void;
  onClearStageFilter: () => void;
}

export function LedgerKpiCards({
  summary,
  loadingSummary,
  stageFilter,
  onSelectStage,
  onClearStageFilter,
}: LedgerKpiCardsProps) {
  const getStageCount = (stage: string): number => {
    if (!summary) return 0;
    switch (stage) {
      case "Quotations":
        return summary.quotations || 0;
      case "Material to Client":
        return summary.material_to_client || 0;
      case "Issue Policy":
        return summary.issue_policy || 0;
      case "Close - Win":
        return summary.close_win || 0;
      case "Close - Lose":
        return summary.close_lose || 0;
      case "Others":
        return summary.others || 0;
      default:
        return 0;
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-neutral-900 uppercase tracking-wider">
            5-Stage Pipeline Overview
          </span>
          {loadingSummary && (
            <ArrowsClockwise className="w-3.5 h-3.5 animate-spin text-neutral-400" />
          )}
        </div>
        {stageFilter !== "all" && (
          <button
            type="button"
            onClick={onClearStageFilter}
            className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
          >
            <span>Clear Filter ({stageFilter})</span>
            <XCircle className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* 5 KPI Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
        {STAGE_ORDER.map((stageKey) => {
          const conf = STAGE_CONFIGS[stageKey] || STAGE_CONFIGS.Quotations;
          const count = getStageCount(stageKey);
          const isSelected = stageFilter === stageKey;

          return (
            <button
              key={stageKey}
              type="button"
              onClick={() => onSelectStage(stageKey)}
              className={`p-2.5 rounded-[var(--rl-radius-sm)] border text-left transition-all cursor-pointer flex flex-col justify-between min-h-[74px] ${
                conf.bg
              } ${conf.border} ${
                isSelected
                  ? "ring-2 ring-neutral-900 shadow-sm font-bold scale-[1.02]"
                  : "hover:shadow-xs hover:border-neutral-400"
              }`}
              title={`Click to filter by ${conf.label}`}
            >
              <div className="text-[11px] font-semibold text-neutral-700 leading-tight truncate">
                {conf.label}
              </div>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-lg font-extrabold text-neutral-900 font-mono">
                  {count}
                </span>
                {conf.isLost && (
                  <span className="text-[9px] font-bold text-rose-600 uppercase tracking-wider">
                    Lost
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
