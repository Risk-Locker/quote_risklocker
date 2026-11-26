"use client";

import React from "react";
import { Check, WarningCircle } from "@phosphor-icons/react";
import type { BenefitCardSummary, WorkspaceField, WorkspaceSnapshot } from "../types";

export interface AttentionItem {
  id: string;
  kind: "field" | "bundle";
  fieldKey?: string;
  selectionId?: string;
  card?: BenefitCardSummary;
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

function formatBenefitAttentionValue(card: BenefitCardSummary): string {
  const rawPrice = card.price?.amount ?? card.optional_price?.amount ?? card.detected_cost;
  const numPrice = rawPrice !== null && rawPrice !== undefined ? Number(rawPrice) : NaN;
  if (Number.isFinite(numPrice) && numPrice > 0) {
    return `RM ${numPrice.toFixed(2)}`;
  }
  if (card.selected_bundle_tier_label) {
    return card.selected_bundle_tier_label;
  }
  if (card.value) {
    return card.value;
  }
  return card.cost_status === "unknown" ? "Review Cost" : "Plan 1";
}

export function collectWorkspaceAttentionItems(
  workspace: WorkspaceSnapshot | null,
  currentCards: BenefitCardSummary[],
  addonCards: BenefitCardSummary[],
  formValues: Record<string, string>
): AttentionItem[] {
  const items: AttentionItem[] = [];
  if (!workspace) return items;

  const HIDDEN_MIRROR_FIELDS = new Set([
    "coverage_amount",
    "market_value",
    "agreed_value",
    "insured_name",
    "make",
    "ic_no",
    "nric_no",
    "id_number",
    "customer_ic_no",
    "veh_reg_no",
    "registration_no",
    "client_name",
    "policyholder_name",
    "engine_number",
    "chassis_number",
    "vehicle_model",
    "coverage_start_date",
    "coverage_end_date",
  ]);
  const seenFields = new Set<string>();
  const fields = workspace.fields || {};
  for (const [key, rawField] of Object.entries(fields)) {
    const field = rawField as WorkspaceField | undefined;
    if (!field || field.status !== "check_needed") continue;
    if (HIDDEN_MIRROR_FIELDS.has(key)) continue;
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

  const seenCards = new Set<string>();
  for (const card of [...currentCards, ...addonCards]) {
    const isFlagged = Boolean(
      card.plan_tier_uncertain || card.needs_review_reason || card.cost_status === "unknown"
    );
    if (!isFlagged) continue;
    const selKey = card.selection_id || card.card_key;
    if (seenCards.has(selKey)) continue;
    seenCards.add(selKey);
    items.push({
      id: `bundle:${selKey}`,
      kind: "bundle",
      selectionId: selKey,
      card,
      label: card.label,
      valueText: formatBenefitAttentionValue(card),
      reason:
        card.needs_review_reason ||
        (card.cost_status === "unknown"
          ? "Cost status unclassified — confirm Free/Included or Paid add-on"
          : "Plan tier uncertain — verify extracted plan level"),
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
  onApproveBenefit,
  onJumpToItem,
}: {
  workspace: WorkspaceSnapshot | null;
  currentCards: BenefitCardSummary[];
  addonCards: BenefitCardSummary[];
  formValues: Record<string, string>;
  onConfirmField: (fieldKey: string, value: string) => void;
  onConfirmBundleTier: (selectionId: string) => void;
  onApproveBenefit?: (card: BenefitCardSummary) => void;
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
              className="group relative inline-flex items-center overflow-hidden rounded border border-amber-300 bg-white pl-2 pr-1 py-0.5 text-[11px] font-medium text-amber-950 shadow-2xs transition-colors hover:border-amber-400"
              title={item.reason}
            >
              <button
                type="button"
                onClick={() => onJumpToItem?.(item)}
                className="inline-flex items-center gap-1 pr-1 hover:underline text-left cursor-pointer"
              >
                <span className="font-semibold">{item.label}:</span>
                <span className="font-mono text-amber-800 max-w-[150px] truncate">{item.valueText}</span>
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  if (item.kind === "field" && item.fieldKey) {
                    onConfirmField(item.fieldKey, formValues[item.fieldKey] ?? "");
                  } else if (item.card && onApproveBenefit) {
                    onApproveBenefit(item.card);
                  } else if (item.kind === "bundle" && item.selectionId) {
                    onConfirmBundleTier(item.selectionId);
                  }
                }}
                className="inline-flex items-center justify-center overflow-hidden max-w-0 opacity-0 group-hover:max-w-[28px] group-hover:opacity-100 group-focus-within:max-w-[28px] group-focus-within:opacity-100 rounded bg-emerald-600 px-0 group-hover:px-1.5 group-focus-within:px-1.5 py-0.5 text-[10px] font-bold text-white hover:bg-emerald-700 transition-all duration-150 cursor-pointer shrink-0"
                title={`Approve ${item.label}`}
                aria-label={`Approve ${item.label}`}
              >
                <Check size={11} weight="bold" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
