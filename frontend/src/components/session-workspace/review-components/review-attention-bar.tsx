"use client";

import React from "react";
import { Check, WarningCircle } from "@phosphor-icons/react";
import type { BenefitCardSummary, WorkspaceField, WorkspaceSnapshot } from "../types";

export interface AttentionItem {
  id: string;
  kind: "field" | "bundle";
  fieldKey?: string;
  selectionId?: string;
  label: string;
  valueText: string;
  reason: string;
}

const FIELD_DISPLAY_LABELS: Record<string, string> = {
  quotation_reference: "Quotation Ref",
  vehicle_no: "Vehicle Plate",
  insurance_company: "Insurer Name",
  customer_name: "Customer Name",
  insured_name: "Insured Name",
  cover_period: "Cover Period",
  coverage_type: "Coverage Type",
  car_model: "Car Model",
  car_brand: "Car Brand",
  ncd_percent: "NCD %",
  valuation_type: "Valuation Type",
  excess_amount: "Policy Excess",
  sum_insured: "Sum Insured",
  vehicle_type: "Vehicle Type",
  engine_cc: "Engine CC / Capacity",
  ic_or_brn: "NRIC / BRN",
  vehicle_year: "Year of Make",
  premium: "Insurance Premium",
  roadtax: "Road Tax",
  service_fee: "Runner Fee",
  total_amount: "Total Payable",
};

export function collectWorkspaceAttentionItems(
  workspace: WorkspaceSnapshot | null,
  currentCards: BenefitCardSummary[],
  addonCards: BenefitCardSummary[],
  formValues: Record<string, string>
): AttentionItem[] {
  const items: AttentionItem[] = [];
  if (!workspace) return items;

  const seenFields = new Set<string>();
  const fields = workspace.fields || {};
  for (const [key, rawField] of Object.entries(fields)) {
    const field = rawField as WorkspaceField | undefined;
    if (!field || field.status !== "check_needed") continue;
    // Skip hidden internal mirror keys when primary key represents the field
    if (["coverage_amount", "market_value", "agreed_value", "insured_name"].includes(key)) continue;
    if (seenFields.has(key)) continue;
    seenFields.add(key);
    const val = (formValues[key] ?? field.value ?? "").toString().trim();
    if (!val && !field.message) continue;
    items.push({
      id: `field:${key}`,
      kind: "field",
      fieldKey: key,
      label: FIELD_DISPLAY_LABELS[key] || key.replace(/_/g, " "),
      valueText: val || "Missing",
      reason: field.message || "Needs verification",
    });
  }

  for (const card of [...currentCards, ...addonCards]) {
    if (!card.plan_tier_uncertain) continue;
    items.push({
      id: `bundle:${card.selection_id || card.card_key}`,
      kind: "bundle",
      selectionId: card.selection_id || card.card_key,
      label: card.label,
      valueText: card.selected_bundle_tier_label || "Plan 1",
      reason: card.needs_review_reason || "Plan tier uncertain — verify extracted plan level",
    });
  }

  return items;
}

export function ReviewAttentionBar({
  workspace,
  currentCards,
  addonCards,
  formValues,
  onConfirmField,
  onConfirmBundleTier,
  onJumpToItem,
}: {
  workspace: WorkspaceSnapshot | null;
  currentCards: BenefitCardSummary[];
  addonCards: BenefitCardSummary[];
  formValues: Record<string, string>;
  onConfirmField: (fieldKey: string, value: string) => void;
  onConfirmBundleTier: (selectionId: string) => void;
  onJumpToItem?: (item: AttentionItem) => void;
}) {
  const items = React.useMemo(
    () => collectWorkspaceAttentionItems(workspace, currentCards, addonCards, formValues),
    [workspace, currentCards, addonCards, formValues]
  );

  if (items.length === 0) return null;

  return (
    <div
      role="region"
      aria-label="Needs review items"
      className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50/90 px-3 py-2 text-xs text-amber-950 shadow-2xs"
    >
      <div className="flex flex-wrap items-center gap-2 min-w-0">
        <span className="inline-flex items-center gap-1 rounded bg-amber-200/80 px-2 py-0.5 text-[11px] font-bold text-amber-950 shrink-0">
          <WarningCircle size={13} weight="fill" className="text-amber-700" />
          Needs Review ({items.length})
        </span>
        <div className="flex flex-wrap items-center gap-1.5">
          {items.map((item) => (
            <div
              key={item.id}
              className="inline-flex items-center gap-1 rounded border border-amber-300 bg-white px-2 py-0.5 text-[11px] font-medium text-amber-950 shadow-2xs"
              title={item.reason}
            >
              <button
                type="button"
                onClick={() => onJumpToItem?.(item)}
                className="inline-flex items-center gap-1 hover:underline text-left cursor-pointer"
              >
                <span className="font-semibold">{item.label}:</span>
                <span className="font-mono text-amber-800 max-w-[140px] truncate">{item.valueText}</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  if (item.kind === "field" && item.fieldKey) {
                    onConfirmField(item.fieldKey, formValues[item.fieldKey] ?? "");
                  } else if (item.kind === "bundle" && item.selectionId) {
                    onConfirmBundleTier(item.selectionId);
                  }
                }}
                className="ml-0.5 inline-flex items-center gap-0.5 rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-bold text-white hover:bg-emerald-700 cursor-pointer"
                title={`Confirm ${item.label}`}
              >
                <Check size={10} weight="bold" />
                <span>Confirm</span>
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
