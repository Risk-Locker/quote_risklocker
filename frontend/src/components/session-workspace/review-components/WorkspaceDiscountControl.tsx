"use client";

import React, { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";

const PRESET_PCTS = [0, 5, 10, 15];

export interface WorkspaceDiscountControlProps {
  currentPct: number;
  effectiveDiscount?: string | null;
  netMotorPremium?: string | null;
  isLinkedToComparison?: boolean;
  saving?: boolean;
  onApplyDiscountPct: (pct: number) => Promise<void> | void;
}

export function WorkspaceDiscountControl({
  currentPct,
  effectiveDiscount,
  netMotorPremium,
  isLinkedToComparison,
  saving = false,
  onApplyDiscountPct,
}: WorkspaceDiscountControlProps) {
  const [inputVal, setInputVal] = useState<string>(() => (currentPct > 0 ? String(currentPct) : "0"));

  useEffect(() => {
    setInputVal(Number.isFinite(currentPct) ? String(currentPct) : "0");
  }, [currentPct]);

  const applyValue = (raw: number) => {
    const clamped = Math.min(100, Math.max(0, Number.isFinite(raw) ? raw : 0));
    setInputVal(String(clamped));
    void onApplyDiscountPct(clamped);
  };

  const effDiscNum = parseFloat(String(effectiveDiscount || "0").replace(/[^0-9.-]/g, "")) || 0;

  return (
    <div className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white p-2.5 flex flex-wrap items-center justify-between gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-bold text-[var(--rl-text-strong)]">
          Motor Discount %:
        </span>
        <div className="flex items-center p-0.5 rounded-lg border border-[var(--rl-border)] bg-[var(--rl-bg)] gap-0.5">
          {PRESET_PCTS.map((opt) => {
            const active = Math.abs((currentPct || 0) - opt) < 0.001;
            return (
              <button
                key={opt}
                type="button"
                disabled={saving}
                onClick={() => applyValue(opt)}
                className={`px-2 py-0.5 rounded-md text-[11px] font-bold transition-colors cursor-pointer disabled:opacity-50 ${
                  active
                    ? opt > 0
                      ? "bg-emerald-600 text-white shadow-2xs"
                      : "bg-white text-[var(--rl-text-strong)] shadow-2xs border border-black/10"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                {opt}%
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-1">
          <input
            type="number"
            min="0"
            max="100"
            step="0.5"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                applyValue(parseFloat(inputVal) || 0);
              }
            }}
            aria-label="Workspace motor discount percentage"
            className="w-16 h-7 rounded-[var(--rl-radius-sm)] px-2 text-xs font-mono font-bold border border-[var(--rl-border)] bg-white text-[var(--rl-text-strong)] focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
          />
          <span className="text-[11px] font-bold text-[var(--rl-text-muted)]">%</span>
          <button
            type="button"
            disabled={saving}
            onClick={() => applyValue(parseFloat(inputVal) || 0)}
            className="h-7 px-2.5 rounded-[var(--rl-radius-sm)] text-[11px] font-bold bg-[var(--rl-black)] hover:bg-black text-white transition-colors disabled:opacity-50 cursor-pointer"
          >
            {saving ? "Saving..." : "Apply"}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        {effDiscNum > 0 && (
          <span className="font-mono font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-2 py-0.5">
            - RM {effDiscNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            {netMotorPremium ? ` · Net: RM ${Number(String(netMotorPremium).replace(/[^0-9.-]/g, "") || 0).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : ""}
          </span>
        )}
        {isLinkedToComparison && (
          <Badge variant="default">Synced with Comparison</Badge>
        )}
      </div>
    </div>
  );
}
