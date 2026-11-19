"use client";

import { Calculator, ShieldCheck, WarningCircle } from "@phosphor-icons/react";
import { Info } from "@phosphor-icons/react";

const COPAY_RATES = [15, 20, 25, 30, 35, 40];

export type BettermentModeSelection = {
  mode: "auto" | "waived" | "copay";
  waiver_betterment?: boolean;
  betterment_rate?: number | null;
};

export interface BettermentEditorControlsProps {
  waiverBetterment: boolean;
  bettermentRate?: number | null;
  isAuto?: boolean;
  companyName?: string;
  manufactureYear?: number | null;
  onSelect: (selection: BettermentModeSelection) => void;
  disabled?: boolean;
  compact?: boolean;
}

/**
 * Direct Waiver of Betterment selector with formula visibility:
 * - Auto (calculated from YOM + Insurer policy_rules + Peril)
 * - Waived — No (0%)
 * - Apply Co-pay (Auto by Age or explicit 15%–40% schedule)
 */
export function BettermentEditorControls({
  waiverBetterment,
  bettermentRate,
  isAuto = false,
  companyName,
  manufactureYear,
  onSelect,
  disabled = false,
  compact = false,
}: BettermentEditorControlsProps) {
  const mode: "auto" | "waived" | "copay" = isAuto
    ? "auto"
    : waiverBetterment
      ? "waived"
      : "copay";

  const activeRate = bettermentRate != null ? Math.round(Number(bettermentRate)) : null;

  const btnCls = (active: boolean, tone: "dark" | "emerald" | "amber" = "dark") => {
    const activeStyles =
      tone === "emerald"
        ? "bg-emerald-700 text-white border-emerald-700"
        : tone === "amber"
          ? "bg-amber-700 text-white border-amber-700"
          : "bg-[#1b1717] text-white border-[#1b1717]";
    return `rounded-[var(--rl-radius-sm)] border px-2.5 ${
      compact ? "min-h-[28px] text-[11px]" : "min-h-[32px] text-[12px]"
    } font-semibold transition-colors cursor-pointer ${
      active ? activeStyles : "bg-[#ffffff] text-[#1b1717] border-[#e5e5ea] hover:bg-[#f5f5f7]"
    }`;
  };

  return (
    <div className="space-y-2">
      {/* Transparent Malaysian Motor Betterment formula guide */}
      <div className="rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] bg-[#f5f5f7] px-2.5 py-2 text-[10px] leading-relaxed text-[#454545]">
        <div className="flex items-start gap-1.5">
          <Info size={13} weight="bold" className="text-[#1b1717] shrink-0 mt-0.5" />
          <div>
            <span className="font-bold text-[#1b1717]">Betterment Formula: </span>
            <span>
              Age = Policy Year − YOM{manufactureYear ? ` (${manufactureYear})` : ""}. Under 5 yrs = 0%. Ages 5→10+ incur 15%→40% co-pay unless insurer waiver applies
              {companyName ? ` (${companyName})` : ""}.
            </span>
          </div>
        </div>
      </div>

      {/* Primary Mode Row */}
      <div className="grid grid-cols-3 gap-1.5">
        <button
          type="button"
          disabled={disabled}
          onClick={() => onSelect({ mode: "auto", betterment_rate: null })}
          className={`${btnCls(mode === "auto")} flex items-center justify-center gap-1`}
          title="Recalculate automatically from YOM, Insurer waiver window, and Perils"
        >
          <Calculator size={12} weight="bold" />
          Auto
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() =>
            onSelect({ mode: "waived", waiver_betterment: true, betterment_rate: 0 })
          }
          className={`${btnCls(mode === "waived", "emerald")} flex items-center justify-center gap-1`}
        >
          <ShieldCheck size={12} weight="bold" />
          No (0%)
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() =>
            onSelect({
              mode: "copay",
              waiver_betterment: false,
              betterment_rate: activeRate && activeRate > 0 ? activeRate : 20,
            })
          }
          className={`${btnCls(mode === "copay", "amber")} flex items-center justify-center gap-1`}
        >
          <WarningCircle size={12} weight="bold" />
          Co-pay
        </button>
      </div>

      {/* Explicit Co-pay rate chips when Co-pay mode or overriding rate */}
      <div className="space-y-1">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-[#6e6e73] block">
          Explicit Co-pay Schedule
        </span>
        <div className="grid grid-cols-3 gap-1.5">
          {COPAY_RATES.map((pct) => {
            const isSelected = mode === "copay" && activeRate === pct;
            return (
              <button
                key={pct}
                type="button"
                disabled={disabled}
                onClick={() =>
                  onSelect({
                    mode: "copay",
                    waiver_betterment: false,
                    betterment_rate: pct,
                  })
                }
                className={btnCls(isSelected, "amber")}
              >
                Yes ({pct}%)
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
