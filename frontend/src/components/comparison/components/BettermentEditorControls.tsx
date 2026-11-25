"use client";

import { Calculator, ShieldCheck, WarningCircle } from "@phosphor-icons/react";
import { Info } from "@phosphor-icons/react";

const COPAY_RATES = [15, 20, 25, 30, 35, 40];

export type BettermentModeSelection = {
  mode: "auto" | "waived" | "no" | "copay";
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
 * Direct Betterment Waiver selector with formula visibility:
 * - Auto (calculated from YOM + Insurer policy_rules + Peril + Coverage Type)
 * - Yes (0%) — Waived / Exempt (< 5 yrs or valid waiver)
 * - No — Not applicable (TPO / TPFT / no percentage)
 * - No (15%–40%) — Comprehensive co-payment applies
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
  const activeRate = bettermentRate != null ? Math.round(Number(bettermentRate)) : null;

  const mode: "auto" | "waived" | "no" | "copay" = isAuto
    ? "auto"
    : waiverBetterment
      ? "waived"
      : activeRate != null && activeRate > 0
        ? "copay"
        : "no";

  const btnCls = (active: boolean, tone: "dark" | "emerald" | "amber" | "neutral" = "dark") => {
    const activeStyles =
      tone === "emerald"
        ? "bg-emerald-700 text-white border-emerald-700"
        : tone === "amber"
          ? "bg-amber-700 text-white border-amber-700"
          : tone === "neutral"
            ? "bg-[#4b4f56] text-white border-[#4b4f56]"
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
            <span className="font-bold text-[#1b1717]">Betterment Waiver Rules: </span>
            <span>
              Age = Policy Year − YOM{manufactureYear ? ` (${manufactureYear})` : ""}.{" "}
              <strong>Yes (0%)</strong> if &lt;5 yrs or waived
              {companyName ? ` (${companyName})` : ""}; <strong>No (15%→40%)</strong> for Comprehensive co-pay;{" "}
              <strong>No</strong> for TPO / TPFT / N/A.
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
          title="Recalculate automatically from YOM, Coverage Type, Insurer waiver window, and Perils"
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
          title="Betterment Waived / 0% Co-pay"
        >
          <ShieldCheck size={12} weight="bold" />
          Yes (0%)
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() =>
            onSelect({
              mode: "no",
              waiver_betterment: false,
              betterment_rate: null,
            })
          }
          className={`${btnCls(mode === "no", "neutral")} flex items-center justify-center gap-1`}
          title="No Betterment Waiver / Not Applicable (TPO, TPFT, or no percentage)"
        >
          <WarningCircle size={12} weight="bold" />
          No
        </button>
      </div>

      {/* Explicit Co-pay rate chips when Comprehensive co-payment applies */}
      <div className="space-y-1">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-[#6e6e73] block">
          Comprehensive Co-pay (No Waiver)
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
                No ({pct}%)
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
