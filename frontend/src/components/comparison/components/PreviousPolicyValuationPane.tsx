"use client";

import React from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  PencilSimple,
  UploadSimple,
  CheckCircle,
  FilePdf,
  DownloadSimple,
  ShieldCheck,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { formatShortInsurerName, formatBenefitCoverage } from "@/lib/benefit-utils";
import { fileUrl } from "@/lib/api";
import { formatMoneyWithRounding } from "../types";
import type { DynamicAddonDefinition, TenureSpec, RoundingMode } from "../types";
import { InlineComparisonFieldEditor } from "./InlineComparisonFieldEditor";
import { DynamicAddonsControl } from "./DynamicAddonsControl";
import { PerilsChecklistEditor } from "./PerilsChecklistEditor";

export interface PreviousPolicyValuationPaneProps {
  tenure: TenureSpec;
  previous_policy?: any;
  covernote_policy?: any;
  recommended_sum_insured: Record<string, number>;
  ncd?: {
    current: number | null;
    next: number | null;
    current_period?: string;
    next_period?: string;
    has_previous_policy?: boolean;
  } | null;
  tenureId: string;
  isUnlinkingCovernote: boolean;
  roundingMode?: RoundingMode;
  activeDynamicAddons?: DynamicAddonDefinition[];
  dynamicAddonCatalog?: DynamicAddonDefinition[];
  onOpenNcdModal: () => void;
  onUnlinkCovernote: () => void;
  onOpenEditCovernote?: () => void;
  onPatchCovernoteField?: (patch: Record<string, any>) => Promise<void>;
}

export function PreviousPolicyValuationPane({
  tenure,
  previous_policy,
  covernote_policy,
  recommended_sum_insured,
  ncd,
  tenureId,
  isUnlinkingCovernote,
  roundingMode = "exact",
  activeDynamicAddons = [],
  dynamicAddonCatalog,
  onOpenNcdModal,
  onUnlinkCovernote,
  onOpenEditCovernote,
  onPatchCovernoteField,
}: PreviousPolicyValuationPaneProps) {
  const priorYear = tenure.coverage_start_date
    ? new Date(tenure.coverage_start_date).getFullYear() - 1
    : new Date().getFullYear() - 1;
  const prevPeriod = previous_policy?.period || ncd?.current_period || `${priorYear}`;
  const currentNcdVal = previous_policy?.ncd_percentage != null ? previous_policy.ncd_percentage : ncd?.current;

  const currentYear = tenure.coverage_start_date
    ? new Date(tenure.coverage_start_date).getFullYear()
    : new Date().getFullYear();
  const cn = covernote_policy;

  return (
    <div id="tour-current-policy" className="space-y-4 sticky top-6">
      {/* Card 1: Previous Policy Card (Baseline Reference & Current NCD) */}
      {previous_policy && (previous_policy.insurer || previous_policy.sum_insured > 0 || currentNcdVal != null) ? (
        <div className="rounded-[var(--rl-radius)] border border-neutral-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-neutral-200 pb-2.5 mb-3">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-xs font-bold uppercase tracking-wider text-neutral-900 truncate">
                Previous Policy ({prevPeriod})
              </span>
              <span className="rounded-[var(--rl-radius-sm)] bg-neutral-100 text-neutral-700 font-bold px-1.5 py-0.5 text-[9px] uppercase border border-neutral-200 shrink-0">
                Baseline
              </span>
            </div>
            {previous_policy.insurer && (
              <span
                className="rounded bg-neutral-100 px-2 py-0.5 text-xs font-bold text-neutral-800 border border-neutral-200 uppercase whitespace-nowrap shrink-0"
                title={previous_policy.insurer}
              >
                {formatShortInsurerName(previous_policy.insurer)}
              </span>
            )}
          </div>

          <div className="space-y-2 text-xs text-[#454545]">
            {/* Period of Insurance */}
            <div className="flex justify-between items-center py-1 border-b border-neutral-100 bg-neutral-50/70 -mx-4 px-4">
              <span className="text-[11px] font-bold text-neutral-700">Insurance Period:</span>
              <span className="font-mono font-bold text-xs text-neutral-900">{prevPeriod}</span>
            </div>

            {/* Current NCD */}
            <div className="flex justify-between items-center">
              <span className="text-neutral-500">Current NCD:</span>
              <span className="font-mono font-bold text-neutral-900">
                {currentNcdVal != null ? `${currentNcdVal}%` : "—"}
              </span>
            </div>

            {/* Sum Insured */}
            <div className="flex justify-between">
              <span className="text-neutral-500">Sum Insured:</span>
              <span className="font-mono font-bold text-neutral-900">
                {previous_policy.sum_insured
                  ? `RM ${previous_policy.sum_insured.toLocaleString("en-MY", { minimumFractionDigits: 2 })}`
                  : "—"}
              </span>
            </div>

            {/* Premium Paid */}
            <div className="flex justify-between">
              <span className="text-neutral-500">Premium Paid:</span>
              <span className="font-mono font-bold text-neutral-900">
                {previous_policy.insurance_premium
                  ? `RM ${Math.round(previous_policy.insurance_premium).toFixed(2)}`
                  : "—"}
              </span>
            </div>

            {/* Included Perils */}
            <div className="flex justify-between items-start gap-2">
              <span className="text-neutral-500 shrink-0">Included Perils:</span>
              <span
                className="font-medium text-neutral-800 text-right truncate max-w-[170px]"
                title={previous_policy.perils}
              >
                {previous_policy.perils || "Standard Policy Coverage"}
              </span>
            </div>

            {/* Riders */}
            <div className="mt-1 space-y-1">
              <div className="flex justify-between text-[11px]">
                <span className="text-neutral-500">Windscreen:</span>
                <span className="font-mono font-medium text-neutral-800">
                  {previous_policy.windscreen
                    ? `RM ${previous_policy.windscreen.toLocaleString("en-MY", { minimumFractionDigits: 2 })}`
                    : "—"}
                </span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-neutral-500">Towing:</span>
                <span className="font-mono font-medium text-neutral-800">
                  {formatBenefitCoverage(previous_policy.towing || "Unlimited", undefined, previous_policy.company_name)}
                </span>
              </div>
            </div>

            {/* Bottom action: 1-click edit NCD / upload previous policy */}
            <div className="pt-2.5 border-t border-neutral-100 flex items-center justify-between text-[10px]">
              <span className="text-neutral-400 font-mono">
                {previous_policy.policy_number ? `Ref: ${previous_policy.policy_number}` : "Prior Policy Term"}
              </span>
              <button
                type="button"
                onClick={onOpenNcdModal}
                className="text-neutral-700 hover:text-black font-bold flex items-center gap-1 cursor-pointer"
                title="Edit Current NCD or upload previous policy document"
              >
                <PencilSimple size={11} weight="bold" />
                <span>Edit / Upload</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-[var(--rl-radius)] border-2 border-dashed border-neutral-300 bg-neutral-50/60 p-4 shadow-2xs">
          <div className="flex items-center justify-between border-b border-neutral-200 pb-2 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-neutral-700">
              Previous Policy ({priorYear})
            </span>
            <span className="rounded-[var(--rl-radius-sm)] bg-neutral-200 text-neutral-600 font-bold px-1.5 py-0.5 text-[9px] uppercase">
              No Record
            </span>
          </div>
          <p className="text-[11px] text-neutral-500 leading-relaxed py-1.5 text-center">
            No prior policy term recorded for this vehicle.
          </p>
          <div className="pt-1 text-center">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onOpenNcdModal}
              icon={<UploadSimple size={12} weight="bold" />}
              className="text-xs"
            >
              <span>Upload Last Year Policy / Edit NCD</span>
            </Button>
          </div>
        </div>
      )}

      {/* Card 2: Current Policy Card (Official Cover Note OR Leading Option) */}
      {cn ? (
        <div className="rounded-[var(--rl-radius)] border-2 border-emerald-600 bg-gradient-to-b from-emerald-50/30 to-white p-4 shadow-md ring-2 ring-emerald-500/15">
          <div className="flex flex-col gap-1.5 border-b border-emerald-200 pb-2.5 mb-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-950 truncate">
                Current Policy ({currentYear})
              </span>
              {onOpenEditCovernote && (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={onOpenEditCovernote}
                  title="Edit all Cover Note details (Policy #, Insurer, Dates, Financials, Perils)"
                  icon={<PencilSimple size={11} weight="bold" />}
                  className="min-h-[26px] px-2.5 py-0.5 text-[11px] border-emerald-300 text-emerald-900 hover:bg-emerald-100 shrink-0"
                >
                  <span>Edit All</span>
                </Button>
              )}
            </div>
            <div className="flex items-center justify-between gap-1.5 flex-wrap">
              <span className="rounded-[var(--rl-radius-sm)] bg-emerald-700 text-white font-bold px-2 py-0.5 text-[9px] uppercase inline-flex items-center gap-1 shrink-0">
                <CheckCircle size={10} weight="fill" /> Issued Cover Note
              </span>
              {onPatchCovernoteField ? (
                <InlineComparisonFieldEditor
                  field="company_name"
                  label="Underwriter / Insurer"
                  currentValue={cn.company_name || ""}
                  onSave={onPatchCovernoteField}
                >
                  <span
                    className="rounded-[var(--rl-radius-sm)] bg-emerald-900 px-2 py-0.5 text-[10px] font-bold text-white uppercase whitespace-nowrap truncate max-w-[140px]"
                    title={cn.company_name}
                  >
                    {formatShortInsurerName(cn.company_name)}
                  </span>
                </InlineComparisonFieldEditor>
              ) : (
                <span
                  className="rounded-[var(--rl-radius-sm)] bg-emerald-900 px-2 py-0.5 text-[10px] font-bold text-white uppercase whitespace-nowrap truncate max-w-[140px]"
                  title={cn.company_name}
                >
                  {formatShortInsurerName(cn.company_name)}
                </span>
              )}
            </div>
          </div>

          <div className="space-y-2 text-xs text-[#454545]">
            {/* Policy / Cover Note Number */}
            <div className="flex justify-between items-center py-1 border-b border-emerald-100 bg-emerald-50/70 -mx-4 px-4">
              <span className="text-[11px] font-bold text-emerald-900">Cover Note / Policy #:</span>
              {onPatchCovernoteField ? (
                <InlineComparisonFieldEditor
                  field="policy_number"
                  label="Cover Note / Policy #"
                  currentValue={cn.policy_number || tenure.policy_number || ""}
                  onSave={onPatchCovernoteField}
                >
                  <span className="font-mono font-bold text-xs text-emerald-950">
                    {cn.policy_number || tenure.policy_number || "CN-ISSUED"}
                  </span>
                </InlineComparisonFieldEditor>
              ) : (
                <span className="font-mono font-bold text-xs text-emerald-950">
                  {cn.policy_number || tenure.policy_number || "CN-ISSUED"}
                </span>
              )}
            </div>

            {/* Period of Insurance */}
            <div className="flex justify-between items-center">
              <span className="text-neutral-500">Insurance Period:</span>
              {onPatchCovernoteField ? (
                <InlineComparisonFieldEditor
                  field="coverage_period"
                  label="Insurance Period"
                  currentValue={cn.coverage_period_formatted || ""}
                  coverageStartDate={cn.coverage_start_date}
                  coverageEndDate={cn.coverage_end_date}
                  onSave={onPatchCovernoteField}
                >
                  <span className="font-mono font-bold text-neutral-900">
                    {cn.coverage_period_formatted || "—"}
                  </span>
                </InlineComparisonFieldEditor>
              ) : (
                <span className="font-mono font-bold text-neutral-900">
                  {cn.coverage_period_formatted || "—"}
                </span>
              )}
            </div>

          {/* Sum Insured */}
            <div className="flex justify-between items-center">
              <span className="text-neutral-500">Sum Insured:</span>
              <div className="flex items-center gap-1">
                {onPatchCovernoteField ? (
                  <InlineComparisonFieldEditor
                    field="sum_insured"
                    label="Sum Insured (RM)"
                    currentValue={cn.sum_insured}
                    onSave={onPatchCovernoteField}
                  >
                    <span className="font-mono font-bold text-neutral-900">
                      RM {Number(cn.sum_insured || 0).toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                    </span>
                  </InlineComparisonFieldEditor>
                ) : (
                  <span className="font-mono font-bold text-neutral-900">
                    RM {Number(cn.sum_insured || 0).toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                  </span>
                )}
                {onPatchCovernoteField ? (
                  <InlineComparisonFieldEditor
                    field="agreed_value"
                    label="Agreed Value"
                    currentValue={cn.agreed_value || cn.valuation_type === "agreed_value" ? "Yes" : "No"}
                    onSave={onPatchCovernoteField}
                  >
                    <span className="text-[10px] text-neutral-600 font-semibold">
                      ({cn.valuation_type === "agreed_value" || cn.agreed_value ? "Agreed" : "Market"})
                    </span>
                  </InlineComparisonFieldEditor>
                ) : (
                  <span className="text-[10px] text-neutral-500 font-normal">
                    ({cn.valuation_type === "agreed_value" || cn.agreed_value ? "Agreed" : "Market"})
                  </span>
                )}
              </div>
            </div>

            {/* Motor Premium */}
            <div className="flex justify-between items-center">
              <span className="text-neutral-500">Motor Premium:</span>
              {onPatchCovernoteField ? (
                <InlineComparisonFieldEditor
                  field="motor_premium"
                  label="Motor Premium (RM)"
                  currentValue={cn.exact_motor_premium ?? cn.motor_premium}
                  onSave={onPatchCovernoteField}
                >
                  <span className="font-mono font-bold text-neutral-900">
                    RM {formatMoneyWithRounding(
                      roundingMode === "whole"
                        ? (cn.rounded_motor_premium ?? cn.exact_motor_premium ?? cn.motor_premium)
                        : (cn.exact_motor_premium ?? cn.motor_premium),
                      roundingMode
                    )}
                  </span>
                </InlineComparisonFieldEditor>
              ) : (
                <span className="font-mono font-bold text-neutral-900">
                  RM {formatMoneyWithRounding(
                    roundingMode === "whole"
                      ? (cn.rounded_motor_premium ?? cn.exact_motor_premium ?? cn.motor_premium)
                      : (cn.exact_motor_premium ?? cn.motor_premium),
                    roundingMode
                  )}
                </span>
            )}
          </div>

            {/* Total Payable */}
            <div className="flex justify-between items-center">
              <span className="text-neutral-500">Premium Payable:</span>
              {onPatchCovernoteField ? (
                <InlineComparisonFieldEditor
                  field="total_payable"
                  label="Premium Payable (RM)"
                  currentValue={cn.exact_total_payable ?? cn.total_payable}
                  onSave={onPatchCovernoteField}
                >
                  <span
                    className="font-mono font-bold text-emerald-700"
                    title={cn.exact_total_payable != null ? `Exact cents: RM ${Number(cn.exact_total_payable).toFixed(2)}` : undefined}
                  >
                    RM {formatMoneyWithRounding(
                      roundingMode === "whole"
                        ? (cn.rounded_total_payable ?? Math.round(cn.total_payable))
                        : (cn.exact_total_payable ?? cn.total_payable),
                      roundingMode
                    )}
                  </span>
                </InlineComparisonFieldEditor>
              ) : (
                <span
                  className="font-mono font-bold text-emerald-700"
                  title={cn.exact_total_payable != null ? `Exact cents: RM ${Number(cn.exact_total_payable).toFixed(2)}` : undefined}
                >
                  RM {formatMoneyWithRounding(
                    roundingMode === "whole"
                      ? (cn.rounded_total_payable ?? Math.round(cn.total_payable))
                      : (cn.exact_total_payable ?? cn.total_payable),
                    roundingMode
                  )}
                </span>
              )}
            </div>

            {/* Fixed Costs */}
            <div className="flex justify-between items-center">
              <span className="text-neutral-500">Fixed Costs:</span>
              {onPatchCovernoteField ? (
                <InlineComparisonFieldEditor
                  field="fixed_costs"
                  label="Fixed Costs (Road Tax + Runner)"
                  currentValue={(((cn.include_road_tax === false || tenure.include_road_tax === false ? 0 : (cn.road_tax ?? tenure.road_tax)) || 0) + ((cn.include_runner_fee === false || tenure.include_runner_fee === false ? 0 : (cn.runner_fee ?? tenure.runner_fee)) || 0)).toFixed(2)}
                  roadTax={cn.road_tax ?? tenure.road_tax ?? 0}
                  runnerFee={cn.runner_fee ?? tenure.runner_fee ?? 0}
                  includeRoadTax={cn.include_road_tax !== false && tenure.include_road_tax !== false}
                  includeRunnerFee={cn.include_runner_fee !== false && tenure.include_runner_fee !== false}
                  onSave={onPatchCovernoteField}
                >
                  <span className="font-mono font-medium text-neutral-700">
                    RM {(((cn.include_road_tax === false || tenure.include_road_tax === false ? 0 : (cn.road_tax ?? tenure.road_tax)) || 0) + ((cn.include_runner_fee === false || tenure.include_runner_fee === false ? 0 : (cn.runner_fee ?? tenure.runner_fee)) || 0)).toFixed(2)} (Tax + Runner)
                  </span>
                </InlineComparisonFieldEditor>
              ) : (
                <span className="font-mono font-medium text-neutral-700">
                  RM {(((cn.include_road_tax === false || tenure.include_road_tax === false ? 0 : (cn.road_tax ?? tenure.road_tax)) || 0) + ((cn.include_runner_fee === false || tenure.include_runner_fee === false ? 0 : (cn.runner_fee ?? tenure.runner_fee)) || 0)).toFixed(2)} (Tax + Runner)
                </span>
              )}
            </div>

            {/* Included Perils (Added vs Not Added visibility + interactive checklist) */}
            <div className="space-y-1.5 pt-1 border-t border-emerald-100">
              <div className="flex justify-between items-center gap-2">
                <span className="text-neutral-500 shrink-0 font-semibold">Included Perils:</span>
                {onPatchCovernoteField ? (
                  <InlineComparisonFieldEditor
                    field="included_perils"
                    label="Edit Included Perils"
                    currentValue={(cn.canonical_perils || []).join(", ")}
                    canonicalPerils={cn.canonical_perils || []}
                    onSave={onPatchCovernoteField}
                  >
                    <span className="text-[11px] font-semibold text-emerald-800 hover:underline">
                      Edit Perils ({(cn.canonical_perils || []).length} Added)
                    </span>
                  </InlineComparisonFieldEditor>
                ) : (
                  <span className="font-medium text-emerald-900 text-right">
                    {cn.canonical_perils_formatted || "Comprehensive Policy Coverage"}
                  </span>
                )}
              </div>
              <PerilsChecklistEditor
                readOnly
                compact
                selectedPerils={cn.canonical_perils || []}
              />
            </div>

            {/* Riders & Underwriting Terms */}
            <div className="mt-2 space-y-1">
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-neutral-500">Windscreen:</span>
                {onPatchCovernoteField ? (
                  <InlineComparisonFieldEditor
                    field="windscreen_sum_insured"
                    label="Windscreen (RM)"
                    currentValue={cn.windscreen_sum_insured}
                    onSave={onPatchCovernoteField}
                  >
                    <span className="font-mono font-medium text-neutral-800">
                      {cn.windscreen_sum_insured
                        ? `RM ${Number(cn.windscreen_sum_insured).toLocaleString("en-MY", { minimumFractionDigits: 2 })}`
                        : "Not Included"}
                    </span>
                  </InlineComparisonFieldEditor>
                ) : (
                  <span className="font-mono font-medium text-neutral-800">
                    {cn.windscreen_sum_insured
                      ? `RM ${Number(cn.windscreen_sum_insured).toLocaleString("en-MY", { minimumFractionDigits: 2 })}`
                      : "—"}
                  </span>
                )}
              </div>
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-neutral-500">Towing:</span>
                  {onPatchCovernoteField ? (
                    <InlineComparisonFieldEditor
                      field="towing_limit"
                      label="Towing Limit"
                      currentValue={cn.towing_limit || cn.towing_km || "Unlimited"}
                      onSave={onPatchCovernoteField}
                    >
                      <span className="font-mono font-medium text-neutral-800">
                        {formatBenefitCoverage(cn.towing_limit || cn.towing_km || "Unlimited", undefined, cn.company_name)}
                      </span>
                    </InlineComparisonFieldEditor>
                  ) : (
                    <span className="font-mono font-medium text-neutral-800">
                      {formatBenefitCoverage(cn.towing_limit || cn.towing_km || "Unlimited", undefined, cn.company_name)}
                    </span>
                  )}
                </div>
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-neutral-500">Special Perils:</span>
                  {onPatchCovernoteField ? (
                    <InlineComparisonFieldEditor
                      field="special_perils"
                      label="Special Perils"
                      currentValue={cn.special_perils || "Not Included"}
                      onSave={onPatchCovernoteField}
                    >
                      <span className="font-medium text-neutral-800">{cn.special_perils || "Not Included"}</span>
                    </InlineComparisonFieldEditor>
                  ) : (
                    <span className="font-medium text-neutral-800">{cn.special_perils || "Not Included"}</span>
                  )}
                </div>
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-neutral-500">LLP / LLOP:</span>
                  {onPatchCovernoteField ? (
                    <InlineComparisonFieldEditor
                      field="llp_llop"
                      label="LLP / LLOP"
                      currentValue={cn.llp_llop || "Not Included"}
                      onSave={onPatchCovernoteField}
                    >
                      <span className="font-medium text-neutral-800">{cn.llp_llop || "Not Included"}</span>
                    </InlineComparisonFieldEditor>
                  ) : (
                    <span className="font-medium text-neutral-800">{cn.llp_llop || "Not Included"}</span>
                  )}
                </div>

                {/* Conditional Dynamic Extra Add-ons (when >=1 policy in tenure includes one) */}
                {activeDynamicAddons.map((addon) => {
                  const val = (cn.extra_addons && cn.extra_addons[addon.key]) || "No";
                  const isYes = val === "Yes";
                  return (
                    <div key={addon.key} className="flex justify-between items-center text-[11px]">
                      <span className="text-neutral-500">{addon.label}:</span>
                      {onPatchCovernoteField ? (
                        <InlineComparisonFieldEditor
                          field={`extra_addon:${addon.key}`}
                          label={addon.label}
                          currentValue={val}
                          onSave={onPatchCovernoteField}
                        >
                          <span className={`font-bold ${isYes ? "text-emerald-700" : "text-neutral-600"}`}>
                            {val}
                          </span>
                        </InlineComparisonFieldEditor>
                      ) : (
                        <span className={`font-bold ${isYes ? "text-emerald-700" : "text-neutral-600"}`}>
                          {val}
                        </span>
                      )}
                    </div>
                  );
                })}

                {onPatchCovernoteField && (
                  <div className="flex justify-between items-center text-[11px] pt-0.5">
                    <span className="text-neutral-500">Extra Add-ons:</span>
                    <DynamicAddonsControl
                      currentExtraAddons={cn.extra_addons}
                      catalog={dynamicAddonCatalog}
                      onSetAddon={(key, val) => onPatchCovernoteField({ extra_addons: { [key]: val } })}
                    />
                  </div>
                )}

                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-neutral-500">Excess:</span>
                  {onPatchCovernoteField ? (
                    <InlineComparisonFieldEditor
                      field="excess"
                      label="Excess (RM)"
                      currentValue={cn.excess ?? 0}
                      onSave={onPatchCovernoteField}
                    >
                      <span className="font-mono font-medium text-neutral-800">
                        RM {Number(cn.excess || 0).toFixed(2)}
                      </span>
                    </InlineComparisonFieldEditor>
                  ) : (
                    <span className="font-mono font-medium text-neutral-800">
                      RM {Number(cn.excess || 0).toFixed(2)}
                    </span>
                  )}
                </div>
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-neutral-500">Betterment:</span>
                  {onPatchCovernoteField ? (
                    <InlineComparisonFieldEditor
                      field="waiver_betterment"
                      label="Betterment"
                      currentValue={cn.waiver_betterment ? "No (0%)" : cn.betterment_display || "Yes"}
                      companyName={cn.company_name}
                      manufactureYear={cn.manufacture_year || tenure.manufacture_year}
                      bettermentRate={cn.betterment_rate}
                      isBettermentAuto={cn.betterment_is_auto}
                      onSave={onPatchCovernoteField}
                    >
                      <span className={`font-bold ${cn.waiver_betterment ? "text-emerald-700" : "text-amber-700"}`}>
                        {cn.betterment_display || (cn.waiver_betterment ? "No (0%)" : "Yes")}
                      </span>
                    </InlineComparisonFieldEditor>
                  ) : (
                    <span className={`font-bold ${cn.waiver_betterment ? "text-emerald-700" : "text-amber-700"}`}>
                      {cn.betterment_display || (cn.waiver_betterment ? "No (0%)" : "Yes")}
                    </span>
                  )}
                </div>
              </div>

            <div className="flex justify-between items-center pt-1">
              <span className="text-neutral-500">Model:</span>
              {onPatchCovernoteField ? (
                <InlineComparisonFieldEditor
                  field="vehicle_model"
                  label="Vehicle Model"
                  currentValue={cn.vehicle_model || tenure.vehicle_model || ""}
                  onSave={onPatchCovernoteField}
                >
                  <span className="font-medium text-neutral-900 text-right truncate max-w-[150px]">
                    {cn.vehicle_model || tenure.vehicle_model}
                  </span>
                </InlineComparisonFieldEditor>
              ) : (
                <span className="font-medium text-neutral-900 text-right truncate max-w-[150px]">
                  {cn.vehicle_model || tenure.vehicle_model}
                </span>
              )}
            </div>
            <div className="flex justify-between items-center">
              <span className="text-neutral-500">YOM:</span>
              {onPatchCovernoteField ? (
                <InlineComparisonFieldEditor
                  field="manufacture_year"
                  label="Year of Manufacture (YOM)"
                  currentValue={cn.manufacture_year || tenure.manufacture_year || ""}
                  onSave={onPatchCovernoteField}
                >
                  <span className="font-mono font-medium text-neutral-900 text-right">
                    {cn.manufacture_year || tenure.manufacture_year || "—"}
                  </span>
                </InlineComparisonFieldEditor>
              ) : (
                <span className="font-mono font-medium text-neutral-900 text-right">
                  {cn.manufacture_year || tenure.manufacture_year || "—"}
                </span>
              )}
            </div>

            {/* Action Buttons (Unified --rl-radius-sm corners & consistent borders) */}
            <div className="pt-3 border-t border-emerald-200 flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5 flex-wrap">
                {cn.uploaded_file_id && (
                  <>
                    <a
                      href={fileUrl(`/uploaded-files/${cn.uploaded_file_id}/content`)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 min-w-[90px] min-h-[32px] flex items-center justify-center gap-1 py-1.5 px-2.5 rounded-[var(--rl-radius-sm)] text-xs font-semibold text-white bg-emerald-700 hover:bg-emerald-800 border border-emerald-700 transition-colors"
                      title="View official Cover Note PDF in new tab"
                    >
                      <FilePdf size={13} weight="bold" />
                      <span>View PDF</span>
                    </a>
                    <a
                      href={fileUrl(`/uploaded-files/${cn.uploaded_file_id}/content`)}
                      download={(cn as any).file_name || `${cn.company_name || "policy"}_covernote.pdf`}
                      className="min-h-[32px] flex items-center justify-center gap-1 py-1.5 px-2.5 rounded-[var(--rl-radius-sm)] text-xs font-semibold text-emerald-900 bg-emerald-100 hover:bg-emerald-200 border border-emerald-300 transition-colors cursor-pointer"
                      title="Download official Cover Note PDF to your device"
                    >
                      <DownloadSimple size={13} weight="bold" />
                      <span>Download</span>
                    </a>
                  </>
                )}
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  loading={isUnlinkingCovernote}
                  onClick={onUnlinkCovernote}
                  className="text-xs text-rose-700 hover:text-rose-900 hover:bg-rose-50 border-rose-200"
                  title="Unlink this cover note and revert policy stage"
                >
                  {isUnlinkingCovernote ? "Unlinking..." : "Unlink"}
                </Button>
              </div>
              {cn.session_id && (
                <Link
                  href={`/sessions/${cn.session_id}/review` as Route}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="min-h-[32px] flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-[var(--rl-radius-sm)] text-xs font-semibold text-emerald-950 bg-emerald-100/80 hover:bg-emerald-200/90 border border-emerald-300 transition-colors"
                  title="Open issued cover note in Quotation Workspace to review extracted fields or generate documentation"
                >
                  <FilePdf size={14} weight="bold" className="text-emerald-800" />
                  <span>Open in Quotation Workspace ↗</span>
                </Link>
              )}
            </div>

            <div className="mt-2 text-center text-[10px] font-bold text-emerald-800 bg-emerald-100/70 rounded py-1 border border-emerald-200/80">
              ✓ Policy Issued · Verified Binding Terms
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-[var(--rl-radius)] border-2 border-dashed border-neutral-300 bg-neutral-50/70 p-4 shadow-2xs">
          <div className="flex items-center justify-between border-b border-neutral-200/80 pb-2.5 mb-3">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-bold uppercase tracking-wider text-neutral-800">
                Current Policy ({currentYear})
              </span>
              <span className="rounded-[var(--rl-radius-sm)] bg-neutral-200 text-neutral-700 font-bold px-1.5 py-0.5 text-[9px] uppercase">
                Pending Issue
              </span>
            </div>
            <span className="rounded-[var(--rl-radius-sm)] bg-neutral-100 text-neutral-600 px-2 py-0.5 text-[10px] font-bold border border-neutral-200">
              Awaiting Cover Note
            </span>
          </div>

          <div className="space-y-2.5 py-3 text-center">
            <div className="size-10 rounded-full bg-neutral-100 border border-neutral-200 mx-auto flex items-center justify-center text-neutral-500">
              <ShieldCheck size={20} weight="duotone" />
            </div>
            <div>
              <p className="text-xs font-bold text-neutral-900">
                No Official Policy Issued Yet
              </p>
              <p className="text-[11px] text-neutral-500 max-w-xs mx-auto mt-1 leading-relaxed">
                This workspace is currently evaluating quotations. The Current Policy section accepts strictly official issued Cover Notes. Upload an issued Cover Note PDF to bind the policy.
              </p>
            </div>
            <div className="pt-1 flex items-center justify-center gap-2">
              <Link
                href={`/upload?mode=comparison&tenure_id=${tenureId}` as Route}
                className="min-h-[32px] px-3 py-1.5 rounded-[var(--rl-radius-sm)] bg-[#1b1717] hover:bg-black text-white text-[11px] font-semibold border border-[#1b1717] transition-colors inline-flex items-center gap-1.5 cursor-pointer"
              >
                <UploadSimple size={12} weight="bold" />
                <span>Upload Cover Note PDF</span>
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Recommended Sum Insured / Valuation Matrix */}
      <div className="rounded-[var(--rl-radius)] border border-[#e5e5ea] bg-white p-4 shadow-sm">
        <span className="block text-xs font-bold uppercase tracking-wider text-[#1b1717] border-b border-[#e5e5ea] pb-2 mb-3">
          Recommended Sum Insured
        </span>

        <div className="space-y-2 text-xs">
          {Object.keys(recommended_sum_insured).length > 0 ? (
            Object.entries(recommended_sum_insured).map(([insurerKey, sumVal]) => (
              <div key={insurerKey} className="flex justify-between items-center">
                <span className="text-[#454545] font-semibold">{insurerKey}:</span>
                <span className="font-mono font-bold text-[#1b1717]">
                  RM {Number(sumVal).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
            ))
          ) : (
            <p className="text-xs text-[#6e6e73] text-center py-2">No underwriter sums recorded</p>
          )}
        </div>
      </div>

      {/* NCD Block */}
      <div className="rounded-[var(--rl-radius)] border border-[#e5e5ea] bg-white p-4 shadow-sm space-y-3">
        <div className="flex items-center justify-between border-b border-[#e5e5ea] pb-2">
          <span className="block text-xs font-bold uppercase tracking-wider text-[#1b1717]">
            NCD Entitlement
          </span>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onOpenNcdModal}
            icon={<PencilSimple size={12} weight="bold" />}
            className="min-h-[26px] text-[11px] px-2.5 py-0.5"
            title="Edit Current or Next NCD / Upload last year policy"
          >
            <span>Edit / Upload</span>
          </Button>
        </div>

        <div className="grid grid-cols-2 gap-2 text-center text-xs">
          <div
            onClick={onOpenNcdModal}
            className="rounded-[var(--rl-radius)] bg-[#f5f5f7] p-3 border border-[#e5e5ea] flex flex-col justify-between cursor-pointer hover:border-neutral-400 transition-colors shadow-2xs group"
            title="Click to edit Current NCD or upload previous policy"
          >
            <div>
              <span className="text-xs text-[#6e6e73] block font-semibold uppercase tracking-wider">Current NCD</span>
              <span className="font-mono font-black text-base text-[#1b1717] mt-0.5 block">
                {ncd?.current != null
                  ? `${ncd.current % 1 === 0 ? ncd.current.toFixed(0) : ncd.current.toFixed(2)}%`
                  : "Not Recorded"}
              </span>
            </div>
            <div className="text-[10px] text-[#6e6e73] font-mono mt-2 pt-1.5 border-t border-neutral-200/80 leading-snug">
              {ncd?.current_period ? (
                <span>({ncd.current_period})</span>
              ) : (
                <span>(Prior Policy Term)</span>
              )}
            </div>
          </div>

          <div
            onClick={onOpenNcdModal}
            className="rounded-[var(--rl-radius)] bg-emerald-50/80 p-3 border border-emerald-200 flex flex-col justify-between cursor-pointer hover:border-emerald-400 transition-colors shadow-2xs group"
            title="Click to edit Next NCD"
          >
            <div>
              <span className="text-xs text-emerald-800 block font-semibold uppercase tracking-wider">Next NCD</span>
              <span className="font-mono font-black text-base text-emerald-800 mt-0.5 block">
                {ncd?.next != null
                  ? `${ncd.next % 1 === 0 ? ncd.next.toFixed(0) : ncd.next.toFixed(2)}%`
                  : "Not Detected"}
              </span>
            </div>
            <div className="text-[10px] text-emerald-700 font-mono mt-2 pt-1.5 border-t border-emerald-200/80 leading-snug">
              {ncd?.next_period ? (
                <span>({ncd.next_period})</span>
              ) : (
                <span>(Renewal Policy Term)</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
