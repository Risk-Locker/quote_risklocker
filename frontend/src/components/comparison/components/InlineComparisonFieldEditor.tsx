"use client";

import React, { useEffect, useRef, useState } from "react";
import { ArrowCounterClockwise, Check, PencilSimple, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import {
  BettermentEditorControls,
  type BettermentModeSelection,
} from "./BettermentEditorControls";
import {
  InlineDatePeriodPanel,
  InlineFixedCostsPanel,
  InlinePerilsPanel,
} from "./InlineComparisonPopoverPanels";
import { TowingLimitSelector } from "./TowingLimitSelector";

export type InlineEditableFieldKey =
  | "policy_number"
  | "company_name"
  | "sum_insured"
  | "motor_premium"
  | "total_payable"
  | "fixed_costs"
  | "coverage_period"
  | "included_perils"
  | "vehicle_model"
  | "manufacture_year"
  | "agreed_value"
  | "waiver_betterment"
  | "towing_limit"
  | "special_perils"
  | "llp"
  | "llop"
  | "llp_llop"
  | "excess"
  | "windscreen_sum_insured"
  | "notes"
  | `extra_addon:${string}`;

interface InlineComparisonFieldEditorProps {
  field: InlineEditableFieldKey;
  label: string;
  currentValue: string | number | null | undefined;
  isOverridden?: boolean;
  disabled?: boolean;
  companyName?: string;
  manufactureYear?: number | null;
  waiverBetterment?: boolean;
  bettermentRate?: number | null;
  isBettermentAuto?: boolean;
  coverageStartDate?: string | null;
  coverageEndDate?: string | null;
  canonicalPerils?: string[];
  roadTax?: number;
  runnerFee?: number;
  includeRoadTax?: boolean;
  includeRunnerFee?: boolean;
  onSave: (patch: Record<string, any>) => Promise<void>;
  children: React.ReactNode;
}

const TOGGLE_PRESETS = ["Included", "Not Included"];
const ADDON_PRESETS = ["Yes", "No"];

const AGREED_VALUE_OPTIONS = [
  {
    label: "Yes (Agreed)",
    isActive: (cur: string) => cur.toLowerCase() === "yes" || cur.toLowerCase() === "true",
    patch: { agreed_value: true, valuation_type: "agreed_value" },
  },
  {
    label: "No (Market)",
    isActive: (cur: string) => cur.toLowerCase() === "no" || cur.toLowerCase() === "false" || cur === "",
    patch: { agreed_value: false, valuation_type: "market_value" },
  },
];

/**
 * Popover-based inline editor supporting scalar fields, 3-option Towing Limit,
 * formula-aware Betterment modes, Perils checklist, Date range, Fixed Costs, and Extra Add-ons.
 */
export function InlineComparisonFieldEditor({
  field,
  label,
  currentValue,
  isOverridden = false,
  disabled = false,
  companyName,
  manufactureYear,
  waiverBetterment,
  bettermentRate,
  isBettermentAuto = false,
  coverageStartDate,
  coverageEndDate,
  canonicalPerils,
  roadTax = 0,
  runnerFee = 0,
  includeRoadTax = true,
  includeRunnerFee = true,
  onSave,
  children,
}: InlineComparisonFieldEditorProps) {
  const [open, setOpen] = useState(false);
  const [draftValue, setDraftValue] = useState<string>("");
  const [startDateDraft, setStartDateDraft] = useState<string>("");
  const [endDateDraft, setEndDateDraft] = useState<string>("");
  const [perilsDraft, setPerilsDraft] = useState<string[]>([]);
  const [rtDraft, setRtDraft] = useState<string>("0");
  const [rfDraft, setRfDraft] = useState<string>("0");
  const [incRtDraft, setIncRtDraft] = useState<boolean>(true);
  const [incRfDraft, setIncRfDraft] = useState<boolean>(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);

  const isExtraAddonField = field.startsWith("extra_addon:");

  useEffect(() => {
    if (!open) return;
    const initStr =
      currentValue === null || currentValue === undefined
        ? field === "special_perils" || field === "llp" || field === "llop" || field === "llp_llop"
          ? "Not Included"
          : isExtraAddonField
            ? "No"
            : ""
        : String(currentValue);
    setDraftValue(initStr);
    setStartDateDraft(String(coverageStartDate || "").slice(0, 10));
    setEndDateDraft(String(coverageEndDate || "").slice(0, 10));
    setPerilsDraft(Array.isArray(canonicalPerils) ? [...canonicalPerils] : []);
    setRtDraft(String(roadTax ?? 0));
    setRfDraft(String(runnerFee ?? 0));
    setIncRtDraft(includeRoadTax !== false);
    setIncRfDraft(includeRunnerFee !== false);
    setError(null);
    const timer = setTimeout(() => inputRef.current?.focus(), 20);
    return () => clearTimeout(timer);
  }, [
    open,
    currentValue,
    field,
    isExtraAddonField,
    coverageStartDate,
    coverageEndDate,
    canonicalPerils,
    roadTax,
    runnerFee,
    includeRoadTax,
    includeRunnerFee,
  ]);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const isNumericField =
    field === "excess" ||
    field === "windscreen_sum_insured" ||
    field === "sum_insured" ||
    field === "motor_premium" ||
    field === "total_payable";

  const isToggleField =
    field === "special_perils" || field === "llp" || field === "llop" || field === "llp_llop";
  const isTowingField = field === "towing_limit";
  const isBettermentField = field === "waiver_betterment";
  const isAgreedField = field === "agreed_value";
  const isDatePeriodField = field === "coverage_period";
  const isPerilsField = field === "included_perils";
  const isFixedCostsField = field === "fixed_costs";

  const handleCommit = async (overrideVal?: string) => {
    setError(null);

    if (isDatePeriodField) {
      if (!startDateDraft || !endDateDraft) {
        setError("Both start and end dates are required.");
        return;
      }
      if (endDateDraft < startDateDraft) {
        setError("End date cannot be earlier than start date.");
        return;
      }
      try {
        setSaving(true);
        await onSave({
          coverage_start_date: startDateDraft,
          coverage_end_date: endDateDraft,
        });
        setOpen(false);
      } catch (err: any) {
        setError(err?.message || "Failed to update dates");
      } finally {
        setSaving(false);
      }
      return;
    }

    if (isPerilsField) {
      try {
        setSaving(true);
        await onSave({ included_perils: perilsDraft });
        setOpen(false);
      } catch (err: any) {
        setError(err?.message || "Failed to update perils");
      } finally {
        setSaving(false);
      }
      return;
    }

    if (isFixedCostsField) {
      const parsedRt = parseFloat(rtDraft || "0");
      const parsedRf = parseFloat(rfDraft || "0");
      if (isNaN(parsedRt) || parsedRt < 0 || isNaN(parsedRf) || parsedRf < 0) {
        setError("Road tax and runner fee must be non-negative.");
        return;
      }
      try {
        setSaving(true);
        await onSave({
          road_tax: parsedRt,
          runner_fee: parsedRf,
          include_road_tax: incRtDraft,
          include_runner_fee: incRfDraft,
        });
        setOpen(false);
      } catch (err: any) {
        setError(err?.message || "Failed to save fixed costs");
      } finally {
        setSaving(false);
      }
      return;
    }

    const raw = (overrideVal !== undefined ? overrideVal : draftValue).trim();

    if (field === "notes" && raw.length > 160) {
      setError("Notes must be 160 characters or fewer.");
      return;
    }
    if ((field === "special_perils" || field === "llp" || field === "llop" || field === "llp_llop") && raw.length > 50) {
      setError("Value must be 50 characters or fewer.");
      return;
    }
    if (field === "towing_limit" && raw.length > 100) {
      setError("Towing limit must be 100 characters or fewer.");
      return;
    }
    if (field === "manufacture_year") {
      const yom = parseInt(raw, 10);
      if (isNaN(yom) || yom < 1950 || yom > 2050) {
        setError("Enter a valid 4-digit year (e.g. 2021).");
        return;
      }
      try {
        setSaving(true);
        await onSave({ manufacture_year: yom });
        setOpen(false);
      } catch (err: any) {
        setError(err?.message || "Failed to save YOM");
      } finally {
        setSaving(false);
      }
      return;
    }

    if (isExtraAddonField) {
      const addonKey = field.slice("extra_addon:".length);
      try {
        setSaving(true);
        await onSave({ extra_addons: { [addonKey]: raw } });
        setOpen(false);
      } catch (err: any) {
        setError(err?.message || "Failed to save add-on");
      } finally {
        setSaving(false);
      }
      return;
    }

    let payloadVal: string | number | null = raw;
    if (isNumericField) {
      if (!raw || raw.toLowerCase() === "not included") {
        payloadVal = 0;
      } else {
        const parsed = parseFloat(raw.replace(/[^0-9.-]/g, ""));
        if (isNaN(parsed) || parsed < 0) {
          setError("Enter a valid non-negative amount.");
          return;
        }
        payloadVal = parsed;
      }
    }

    try {
      setSaving(true);
      await onSave({ [field]: payloadVal });
      setOpen(false);
    } catch (err: any) {
      setError(err?.message || "Failed to save override");
    } finally {
      setSaving(false);
    }
  };

  const handlePatchSave = async (patch: Record<string, any>) => {
    try {
      setSaving(true);
      setError(null);
      await onSave(patch);
      setOpen(false);
    } catch (err: any) {
      setError(err?.message || "Failed to save override");
    } finally {
      setSaving(false);
    }
  };

  const handleBettermentSelect = async (sel: BettermentModeSelection) => {
    if (sel.mode === "auto") {
      await handlePatchSave({ betterment_mode: "auto" });
      return;
    }
    await handlePatchSave({
      betterment_mode: sel.mode,
      waiver_betterment: sel.waiver_betterment,
      betterment_rate: sel.betterment_rate,
    });
  };

  const handleRevert = async () => {
    try {
      setSaving(true);
      setError(null);
      await onSave({ clear_override_field: field });
      setOpen(false);
    } catch (err: any) {
      setError(err?.message || "Failed to revert override");
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    } else if (e.key === "Enter" && !e.shiftKey && !isPerilsField && !isDatePeriodField) {
      e.preventDefault();
      handleCommit();
    }
  };

  const popoverWidthClass = isPerilsField
    ? "w-80"
    : isTowingField || isBettermentField || isFixedCostsField || isDatePeriodField
      ? "w-72"
      : "w-64";

  return (
    <div className="relative inline-flex items-center gap-1 group max-w-full" ref={popoverRef}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        title={`Edit ${label}${isOverridden ? " (Manual override active)" : ""}`}
        className="inline-flex items-center gap-1 rounded-[var(--rl-radius-sm)] px-1.5 -mx-1.5 py-0.5 hover:bg-[#f5f5f7] focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#1b1717] transition-colors cursor-pointer text-right"
      >
        {children}
        {isOverridden ? (
          <span className="ml-0.5 rounded-[4px] bg-amber-100 text-amber-900 border border-amber-300 px-1 py-0 text-[9px] font-bold uppercase tracking-tight shrink-0">
            Manual
          </span>
        ) : (
          <PencilSimple
            size={11}
            weight="bold"
            className="text-[#6e6e73] opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity shrink-0 no-print"
          />
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={`Edit ${label}`}
          onKeyDown={handleKeyDown}
          className={`absolute right-0 top-full mt-1 z-50 ${popoverWidthClass} rounded-[var(--rl-radius)] border border-[#e5e5ea] bg-white p-3 shadow-xl text-left space-y-2.5 no-print`}
        >
          <div className="flex items-center justify-between gap-2 pb-1 border-b border-[#e5e5ea]">
            <span className="text-[11px] font-bold text-[#1b1717]">{label}</span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-[#6e6e73] hover:text-[#1b1717] p-0.5 rounded-[var(--rl-radius-sm)] cursor-pointer"
              aria-label="Close inline editor"
            >
              <X size={12} weight="bold" />
            </button>
          </div>

          {isAgreedField && (
            <div className="grid grid-cols-2 gap-1.5">
              {AGREED_VALUE_OPTIONS.map((opt) => {
                const active = opt.isActive(draftValue);
                return (
                  <button
                    key={opt.label}
                    type="button"
                    disabled={saving}
                    onClick={() => handlePatchSave(opt.patch)}
                    className={`px-2 py-1.5 rounded-[var(--rl-radius-sm)] text-[11px] font-semibold border transition-colors cursor-pointer ${
                      active
                        ? "bg-[#1b1717] text-white border-[#1b1717]"
                        : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea] hover:bg-[#e5e5ea]"
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          )}

          {isBettermentField && (
            <BettermentEditorControls
              waiverBetterment={waiverBetterment ?? draftValue.trim().toLowerCase().startsWith("yes")}
              bettermentRate={bettermentRate}
              isAuto={isBettermentAuto}
              companyName={companyName}
              manufactureYear={manufactureYear}
              onSelect={handleBettermentSelect}
              disabled={saving}
              compact
            />
          )}

          {isToggleField && (
            <div className="grid grid-cols-2 gap-1.5">
              {TOGGLE_PRESETS.map((opt) => {
                const active = draftValue.toLowerCase() === opt.toLowerCase();
                return (
                  <button
                    key={opt}
                    type="button"
                    disabled={saving}
                    onClick={() => handleCommit(opt)}
                    className={`px-2 py-1.5 rounded-[var(--rl-radius-sm)] text-[11px] font-semibold border transition-colors cursor-pointer ${
                      active
                        ? "bg-[#1b1717] text-white border-[#1b1717]"
                        : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea] hover:bg-[#e5e5ea]"
                    }`}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>
          )}

          {isExtraAddonField && (
            <div className="grid grid-cols-2 gap-1.5">
              {ADDON_PRESETS.map((opt) => {
                const active = draftValue.toLowerCase() === opt.toLowerCase();
                return (
                  <button
                    key={opt}
                    type="button"
                    disabled={saving}
                    onClick={() => handleCommit(opt)}
                    className={`px-2 py-1.5 rounded-[var(--rl-radius-sm)] text-[11px] font-semibold border transition-colors cursor-pointer ${
                      active
                        ? "bg-[#1b1717] text-white border-[#1b1717]"
                        : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea] hover:bg-[#e5e5ea]"
                    }`}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>
          )}

          {isTowingField && (
            <div className="space-y-2">
              <TowingLimitSelector
                value={draftValue}
                onChange={setDraftValue}
                disabled={saving}
                compact
              />
              <Button
                type="button"
                variant="primary"
                size="sm"
                loading={saving}
                onClick={() => handleCommit(draftValue)}
                className="w-full"
              >
                <Check size={12} weight="bold" />
                Save Towing Limit
              </Button>
            </div>
          )}

          {isDatePeriodField && (
            <InlineDatePeriodPanel
              startDate={startDateDraft}
              endDate={endDateDraft}
              onStartDateChange={setStartDateDraft}
              onEndDateChange={setEndDateDraft}
              onSave={() => handleCommit()}
              saving={saving}
            />
          )}

          {isPerilsField && (
            <InlinePerilsPanel
              perils={perilsDraft}
              onChange={setPerilsDraft}
              onSave={() => handleCommit()}
              saving={saving}
            />
          )}

          {isFixedCostsField && (
            <InlineFixedCostsPanel
              incRt={incRtDraft}
              incRf={incRfDraft}
              rtDraft={rtDraft}
              rfDraft={rfDraft}
              onIncRtChange={setIncRtDraft}
              onIncRfChange={setIncRfDraft}
              onRtChange={setRtDraft}
              onRfChange={setRfDraft}
              onSave={() => handleCommit()}
              saving={saving}
            />
          )}

          {!isAgreedField &&
            !isBettermentField &&
            !isTowingField &&
            !isExtraAddonField &&
            !isDatePeriodField &&
            !isPerilsField &&
            !isFixedCostsField && (
              <div className="flex items-center gap-1.5">
                {field === "notes" ? (
                  <textarea
                    ref={(el) => {
                      inputRef.current = el;
                    }}
                    rows={2}
                    maxLength={160}
                    value={draftValue}
                    onChange={(e) => setDraftValue(e.target.value)}
                    placeholder="Enter note (max 160 chars)..."
                    className="w-full rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] bg-white px-2 py-1 text-xs text-[#1b1717] focus:border-[#1b1717] focus:outline-none"
                  />
                ) : (
                  <input
                    ref={(el) => {
                      inputRef.current = el;
                    }}
                    type={isNumericField || field === "manufacture_year" ? "number" : "text"}
                    step={field === "manufacture_year" ? "1" : isNumericField ? "0.01" : undefined}
                    min={isNumericField ? "0" : field === "manufacture_year" ? "1950" : undefined}
                    value={draftValue}
                    onChange={(e) => setDraftValue(e.target.value)}
                    placeholder={isNumericField ? "0.00" : `Enter ${label.toLowerCase()}...`}
                    className="w-full rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] bg-white px-2 py-1 text-xs text-[#1b1717] focus:border-[#1b1717] focus:outline-none"
                  />
                )}
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => handleCommit()}
                  title="Save (Enter)"
                  className="shrink-0 rounded-[var(--rl-radius-sm)] bg-[#1b1717] text-white p-1.5 hover:bg-black disabled:opacity-50 cursor-pointer"
                >
                  <Check size={12} weight="bold" />
                </button>
              </div>
            )}

          {error && <p className="text-[10px] font-semibold text-[#ed1c24]">{error}</p>}

          {isOverridden && (
            <button
              type="button"
              disabled={saving}
              onClick={handleRevert}
              className="w-full inline-flex items-center justify-center gap-1 rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] bg-[#f5f5f7] px-2 py-1 text-[10px] font-semibold text-[#6e6e73] hover:text-[#1b1717] hover:bg-[#e5e5ea] cursor-pointer"
            >
              <ArrowCounterClockwise size={11} weight="bold" />
              <span>Revert to extracted</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
