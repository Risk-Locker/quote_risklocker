"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Package as PackageIcon, Sparkle, PencilSimple, Trash, X, Check } from "@phosphor-icons/react";
import type { WorkspaceSnapshot } from "../types";

export interface ExtractedBenefitsCardProps {
  workspace: WorkspaceSnapshot;
  extractedBenefitsCollapsed: boolean;
  setExtractedBenefitsCollapsed: (val: boolean) => void;
  pinLoading: boolean;
  pinPackageTier: (pkgId: string) => Promise<void>;
  globalConcepts: any[];
  addConceptAsBenefit: (concept: any, target: "current" | "available_addon", price?: any, limit?: any) => void;
  onQueue?: (op: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) => void;
  queueOperation?: (op: Record<string, unknown> & { op: string }, path: string) => void;
  scheduleSave?: () => void;
  setToastMessage?: (msg: string | null) => void;
}

export function ExtractedBenefitsCard({
  workspace,
  extractedBenefitsCollapsed,
  setExtractedBenefitsCollapsed,
  pinLoading,
  pinPackageTier,
  globalConcepts,
  addConceptAsBenefit,
  onQueue,
  queueOperation,
  scheduleSave,
  setToastMessage,
}: ExtractedBenefitsCardProps) {
  const [editingPriceId, setEditingPriceId] = useState<string | null>(null);
  const [editingLimitId, setEditingLimitId] = useState<string | null>(null);
  const [tempPrice, setTempPrice] = useState("");
  const [tempLimit, setTempLimit] = useState("");
  const [locallyRemovedIds, setLocallyRemovedIds] = useState<Set<string>>(new Set());
  const [locallyEditedCosts, setLocallyEditedCosts] = useState<Record<string, string>>({});
  const [locallyEditedLimits, setLocallyEditedLimits] = useState<Record<string, string>>({});
  const [locallyAppliedIds, setLocallyAppliedIds] = useState<Record<string, boolean>>({});

  const dismissedFromDisplayOptions = React.useMemo(() => {
    const list = (workspace?.display_options as any)?.dismissed_extracted_lines;
    return new Set<string>(Array.isArray(list) ? list.map((item: any) => String(item).toLowerCase().trim()) : []);
  }, [workspace?.display_options]);

  const extras = React.useMemo(() => {
    const rawExtras = workspace.extracted_benefits_section?.extras || [];
    return rawExtras.filter((ex, idx) => {
      const key = String(ex.id || idx);
      const label = String(ex.label || "").toLowerCase().trim();
      if (locallyRemovedIds.has(key) || locallyRemovedIds.has(label)) return false;
      if (dismissedFromDisplayOptions.has(key.toLowerCase()) || dismissedFromDisplayOptions.has(label)) return false;
      return true;
    });
  }, [workspace.extracted_benefits_section?.extras, locallyRemovedIds, dismissedFromDisplayOptions]);

  const handleCommitPrice = (extra: any, key: string) => {
    const cleanNum = parseFloat(tempPrice.replace(/[^0-9.]/g, ""));
    const priceVal = !isNaN(cleanNum) && cleanNum > 0 ? cleanNum : null;
    const priceStr = priceVal !== null ? priceVal.toFixed(2) : "0.00";

    setLocallyEditedCosts((prev) => ({ ...prev, [key]: priceStr }));
    setEditingPriceId(null);

    const isApplied = locallyAppliedIds[key] !== undefined ? locallyAppliedIds[key] : extra.is_applied;
    if (isApplied && extra.selection_id && onQueue) {
      const priceObj = priceVal !== null ? { amount: priceVal, currency: "MYR" } : null;
      const costStatus = priceVal !== null ? "paid" : "included";
      onQueue(
        { op: "benefit_update", selection_id: extra.selection_id, price: priceObj, cost_status: costStatus },
        `benefits.${extra.selection_id}.price`
      );
      setToastMessage?.(`Updated cost for ${extra.label} to ${priceVal !== null ? `RM ${priceStr}` : "FOC / Free"}`);
    } else {
      setToastMessage?.(`Updated detected cost for ${extra.label} to RM ${priceStr}`);
    }
  };

  const handleCommitLimit = (extra: any, key: string) => {
    const clean = tempLimit.trim();
    setLocallyEditedLimits((prev) => ({ ...prev, [key]: clean }));
    setEditingLimitId(null);

    const isApplied = locallyAppliedIds[key] !== undefined ? locallyAppliedIds[key] : extra.is_applied;
    if (isApplied && extra.selection_id && onQueue) {
      const numericVal = clean.replace(/[^0-9.]/g, "");
      onQueue(
        {
          op: "benefit_update",
          selection_id: extra.selection_id,
          typed_value: {
            type: "money",
            value: numericVal,
            currency: "MYR",
            display_text: clean.toUpperCase().includes("RM") ? clean : `RM ${clean}`,
            semantic_role: "limit",
          },
        },
        `benefits.${extra.selection_id}.limit`
      );
      setToastMessage?.(`Updated limit for ${extra.label}`);
    }
  };

  const handleRemoveApplied = (extra: any, key: string) => {
    if (extra.selection_id && onQueue) {
      // Remove from quotation: move catalog offering to available_addon (or removed if custom)
      const isCustom = String(extra.selection_id).startsWith("custom:");
      onQueue(
        {
          op: "benefit_update",
          selection_id: extra.selection_id,
          state: isCustom ? "removed" : "available_addon",
          cost_status: "paid",
        },
        `benefits.${extra.selection_id}.state`
      );
    }
    setLocallyAppliedIds((prev) => ({ ...prev, [key]: false }));
    setToastMessage?.(`Removed "${extra.label}" from quotation.`);
  };

  const handleDismissDetected = (extra: any, key: string) => {
    const itemKey = extra.id || extra.label;
    const existing = (workspace?.display_options as any)?.dismissed_extracted_lines || [];
    const updated = Array.from(new Set([...existing, itemKey, extra.label, extra.id].filter(Boolean)));

    if (queueOperation) {
      queueOperation(
        { op: "update_display_options", options: { dismissed_extracted_lines: updated } },
        "options.dismissed_extracted_lines"
      );
      scheduleSave?.();
    }
    setLocallyRemovedIds((prev) => new Set([...prev, key, String(extra.id || ""), String(extra.label || "").toLowerCase().trim()]));
    setToastMessage?.(`Dismissed "${extra.label}".`);
  };

  const handleAddToQuotation = (extra: any, key: string) => {
    const rawCost = locallyEditedCosts[key] !== undefined ? locallyEditedCosts[key] : extra.cost;
    const cleanCost = rawCost ? Number(String(rawCost).replace(/[^0-9.]/g, "")) : null;
    const priceObj = cleanCost && Number.isFinite(cleanCost) && cleanCost > 0 ? { amount: cleanCost, currency: "MYR" } : null;
    const rawLimit = locallyEditedLimits[key] !== undefined ? locallyEditedLimits[key] : extra.coverage_limit;
    const cleanLimit = rawLimit && typeof rawLimit === "string" ? rawLimit.trim() : null;

    if (extra.concept_key) {
      const concept = globalConcepts.find((c) => c.concept_key === extra.concept_key);
      if (concept) {
        addConceptAsBenefit(concept, "current", priceObj, cleanLimit);
        setLocallyAppliedIds((prev) => ({ ...prev, [key]: true }));
        setToastMessage?.(`Added "${extra.label}" to purchased add-ons.`);
        return;
      }
    }

    // Fallback: create as custom benefit if concept is unmapped
    if (queueOperation) {
      const customKey = `addon:${extra.concept_key || key}`;
      queueOperation(
        {
          op: "create_custom_benefit",
          selection_key: customKey,
          label: extra.label,
          state: "current",
          cost_status: priceObj ? "paid" : "included",
          price: priceObj,
          typed_value: cleanLimit ? { type: "money", value: cleanLimit.replace(/[^0-9.]/g, ""), display_text: `RM ${cleanLimit}`, semantic_role: "limit" } : undefined,
        },
        `benefits.custom.${key}`
      );
      scheduleSave?.();
      setLocallyAppliedIds((prev) => ({ ...prev, [key]: true }));
      setToastMessage?.(`Added "${extra.label}" to quotation.`);
    }
  };

  return (
    <Card className="grid gap-3.5 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-100">
            <Sparkle size={16} weight="fill" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-[var(--rl-text-strong)] flex items-center gap-2">
              Detected Benefits
              {extras.length ? (
                <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[10px] font-bold text-indigo-700 font-mono">
                  {extras.length} detected
                </span>
              ) : null}
            </h2>
            <p className="text-[11px] text-[var(--rl-text-muted)]">
              Policy covers and add-ons detected from the uploaded quotation. Click prices or limits to edit.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {workspace.extracted_benefits_section?.total_optional_cover_amount ? (
            <span className="rounded-md bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-xs font-bold text-emerald-800 font-mono">
              Optional Covers: RM {workspace.extracted_benefits_section.total_optional_cover_amount}
            </span>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExtractedBenefitsCollapsed(!extractedBenefitsCollapsed)}
            className="text-xs h-7 px-2 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
          >
            {extractedBenefitsCollapsed ? "Expand" : "Collapse"}
          </Button>
        </div>
      </div>

      {!extractedBenefitsCollapsed && (
        <div className="grid gap-3.5">
          {/* Detected Package / Plan Banner */}
          {workspace.extracted_benefits_section?.detected_package?.name ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-blue-200 bg-gradient-to-r from-blue-50/80 to-indigo-50/80 p-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-blue-200 bg-white text-blue-600 shadow-xs">
                  <PackageIcon size={18} weight="duotone" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-blue-800">Detected Insurance Package</span>
                    {workspace.extracted_benefits_section.detected_package.is_active_tier ? (
                      <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[9px] font-bold text-emerald-800">
                        Active Tier
                      </span>
                    ) : null}
                  </div>
                  <p className="text-xs font-bold text-[var(--rl-text-strong)]">
                    {workspace.extracted_benefits_section.detected_package.name}
                  </p>
                </div>
              </div>

              {workspace.extracted_benefits_section.detected_package.matching_package_id &&
              !workspace.extracted_benefits_section.detected_package.is_active_tier ? (
                <Button
                  size="sm"
                  variant="primary"
                  disabled={pinLoading}
                  onClick={() => pinPackageTier(workspace.extracted_benefits_section!.detected_package!.matching_package_id!)}
                  className="text-xs font-semibold h-8 bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
                >
                  Switch to this Tier →
                </Button>
              ) : null}
            </div>
          ) : null}

          {/* Detected Add-ons List */}
          <div className="grid gap-2">
            {extras.length > 0 ? (
              <div className="divide-y divide-gray-100 rounded-lg border border-gray-200 overflow-hidden bg-white shadow-xs">
                {extras.map((extra, idx) => {
                  const key = String(extra.id || idx);
                  const isApplied = locallyAppliedIds[key] !== undefined ? locallyAppliedIds[key] : Boolean(extra.is_applied);
                  const effectiveCost = locallyEditedCosts[key] !== undefined ? locallyEditedCosts[key] : extra.cost;
                  const hasCost = Boolean(effectiveCost && effectiveCost !== "0.00" && effectiveCost !== "0");
                  const effectiveLimit = locallyEditedLimits[key] !== undefined ? locallyEditedLimits[key] : (extra.coverage_limit || "");
                  const isEditingCost = editingPriceId === key;
                  const isEditingLim = editingLimitId === key;

                  return (
                    <div
                      key={key}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 p-3 hover:bg-gray-50/80 transition-colors"
                    >
                      <div className="grid gap-0.5 min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                            {extra.label}
                          </span>
                          {isApplied ? (
                            hasCost ? (
                              <span className="rounded bg-amber-50 border border-amber-200 px-1.5 py-0.5 text-[9px] font-bold text-amber-800">
                                ✓ In Purchased Add-ons
                              </span>
                            ) : (
                              <span className="rounded bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 text-[9px] font-bold text-emerald-700">
                                ✓ Included in Grid
                              </span>
                            )
                          ) : (
                            <span className="rounded bg-amber-50 border border-amber-200 px-1.5 py-0.5 text-[9px] font-bold text-amber-700">
                              Detected in PDF
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0 pt-1.5 sm:pt-0 border-t sm:border-t-0 border-gray-100 flex-wrap">
                        {/* Limit / Sum insured with inline edit */}
                        {(() => {
                          const dispOvr = (extra as any)?.display_overrides;
                          const showCov = (extra as any)?.show_coverage !== false &&
                            !(dispOvr?.enabled && dispOvr?.showCoverage === false) &&
                            !(dispOvr?.showCoverage === false);
                          if (!showCov && !effectiveLimit) return null;

                          return (
                            <div className="text-right flex flex-col items-end">
                              <span className="block text-[9px] uppercase font-bold text-[var(--rl-text-muted)]">Limit / Sum</span>
                              {isEditingLim ? (
                                <div className="flex items-center gap-1 mt-0.5">
                                  <input
                                    type="text"
                                    value={tempLimit}
                                    autoFocus
                                    placeholder="5,000.00"
                                    onChange={(e) => setTempLimit(e.target.value)}
                                    onBlur={() => handleCommitLimit(extra, key)}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter") handleCommitLimit(extra, key);
                                      if (e.key === "Escape") setEditingLimitId(null);
                                    }}
                                    className="h-6 w-24 rounded border border-[var(--rl-black)] px-1 font-mono text-xs font-semibold text-[var(--rl-text-strong)] focus:outline-none bg-white shadow-2xs text-right"
                                  />
                                </div>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setEditingLimitId(key);
                                    setTempLimit(effectiveLimit ? String(effectiveLimit) : "");
                                  }}
                                  className="group/limit flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-semibold text-[var(--rl-text-strong)] font-mono hover:bg-gray-100 transition-colors border border-transparent hover:border-gray-200"
                                  title="Click to edit coverage limit"
                                >
                                  <span>{effectiveLimit ? (String(effectiveLimit).toUpperCase().includes("RM") ? effectiveLimit : `RM ${effectiveLimit}`) : "Set Limit"}</span>
                                  <PencilSimple size={10} className="text-[var(--rl-text-muted)] group-hover/limit:text-[var(--rl-text-strong)]" />
                                </button>
                              )}
                            </div>
                          );
                        })()}

                        {/* Cost with inline edit */}
                        <div className="text-right flex flex-col items-end">
                          <span className="block text-[9px] uppercase font-bold text-[var(--rl-text-muted)]">Cost</span>
                          {isEditingCost ? (
                            <div className="flex items-center gap-1 mt-0.5">
                              <span className="text-[10px] font-bold text-[var(--rl-text-muted)] font-mono">RM</span>
                              <input
                                type="number"
                                step="any"
                                value={tempPrice}
                                autoFocus
                                placeholder="0.00"
                                onChange={(e) => setTempPrice(e.target.value)}
                                onBlur={() => handleCommitPrice(extra, key)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") handleCommitPrice(extra, key);
                                  if (e.key === "Escape") setEditingPriceId(null);
                                }}
                                className="h-6 w-20 rounded border border-[var(--rl-black)] px-1 font-mono text-xs font-bold text-[var(--rl-text-strong)] focus:outline-none bg-white shadow-2xs"
                              />
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => {
                                setEditingPriceId(key);
                                setTempPrice(effectiveCost ? String(effectiveCost).replace(/[^0-9.]/g, "") : "");
                              }}
                              className="group/price flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-bold text-[var(--rl-red)] font-mono hover:bg-red-50 transition-colors border border-transparent hover:border-red-200"
                              title="Click to edit cost (0 for FOC)"
                            >
                              <span>
                                {hasCost
                                  ? (String(effectiveCost).startsWith("RM") ? String(effectiveCost) : `RM ${effectiveCost}`)
                                  : "FOC / Free"}
                              </span>
                              <PencilSimple size={10} className="text-[var(--rl-text-muted)] group-hover/price:text-[var(--rl-red)]" />
                            </button>
                          )}
                        </div>

                        {/* Action buttons: Remove applied, or Add / Dismiss unapplied */}
                        <div className="flex items-center gap-1.5">
                          {isApplied ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleRemoveApplied(extra, key)}
                              className="text-[11px] h-7 px-2 text-rose-600 hover:text-rose-700 hover:bg-rose-50 font-semibold border border-transparent hover:border-rose-200 transition-colors"
                              title="Remove this cover from purchased quotation extras"
                            >
                              <Trash size={12} className="mr-1" />
                              Remove
                            </Button>
                          ) : (
                            <>
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => handleAddToQuotation(extra, key)}
                                className="text-[11px] h-7 px-2.5 shrink-0 font-bold bg-amber-50 border border-amber-300 text-amber-900 hover:bg-amber-100 transition-colors shadow-2xs"
                                title="Add this detected cover to purchased extras on quotation"
                              >
                                + Add to Quote
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleDismissDetected(extra, key)}
                                className="text-[11px] h-7 px-2 text-gray-500 hover:text-rose-600 hover:bg-gray-100 font-medium transition-colors"
                                title="Dismiss this detected item so it does not appear"
                              >
                                <X size={12} className="mr-1" />
                                Dismiss
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-gray-200 p-6 text-center text-xs text-[var(--rl-text-muted)]">
                No add-ons or optional covers detected yet. Upload an insurance quotation PDF or run Gemini extraction.
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
