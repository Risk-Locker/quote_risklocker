"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Package as PackageIcon, Sparkle } from "@phosphor-icons/react";
import type { WorkspaceSnapshot } from "../types";

export interface ExtractedBenefitsCardProps {
  workspace: WorkspaceSnapshot;
  extractedBenefitsCollapsed: boolean;
  setExtractedBenefitsCollapsed: (val: boolean) => void;
  pinLoading: boolean;
  pinPackageTier: (pkgId: string) => Promise<void>;
  globalConcepts: any[];
  addConceptAsBenefit: (concept: any, target: "current" | "available_addon", price?: any, limit?: any) => void;
}

export function ExtractedBenefitsCard({
  workspace,
  extractedBenefitsCollapsed,
  setExtractedBenefitsCollapsed,
  pinLoading,
  pinPackageTier,
  globalConcepts,
  addConceptAsBenefit,
}: ExtractedBenefitsCardProps) {
  return (
    <Card className="grid gap-3.5 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-100">
                    <Sparkle size={16} weight="fill" />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-[var(--rl-text-strong)] flex items-center gap-2">
                      Extra Benefits
                      {workspace.extracted_benefits_section?.extras?.length ? (
                        <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[10px] font-bold text-indigo-700 font-mono">
                          {workspace.extracted_benefits_section.extras.length} detected
                        </span>
                      ) : null}
                    </h2>
                    <p className="text-[11px] text-[var(--rl-text-muted)]">
                      Optional covers detected from the uploaded quotation.
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

                  {/* RL-DISABLED raw_evidence_toggle — disabled 2026-08-28; restore when debug evidence tab is needed */}

                  {/* Detected Add-ons List */}
                  <div className="grid gap-2">
                    {workspace.extracted_benefits_section?.extras && workspace.extracted_benefits_section.extras.length > 0 ? (
                      <div className="divide-y divide-gray-100 rounded-lg border border-gray-200 overflow-hidden bg-white shadow-xs">
                        {workspace.extracted_benefits_section.extras.map((extra, idx) => {
                          const hasCost = extra.cost && extra.cost !== "0.00" && extra.cost !== "0";
                          return (
                            <div
                              key={extra.id || idx}
                              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 hover:bg-gray-50/80 transition-colors"
                            >
                              <div className="grid gap-0.5 min-w-0 flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                                    {extra.label}
                                  </span>
                                  {extra.is_applied ? (
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
                              <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0 pt-1 sm:pt-0 border-t sm:border-t-0 border-gray-100">
                                {(() => {
                                  const dispOvr = (extra as any)?.display_overrides;
                                  const showCov = (extra as any)?.show_coverage !== false &&
                                    !(dispOvr?.enabled && dispOvr?.showCoverage === false) &&
                                    !(dispOvr?.showCoverage === false);
                                  if (!showCov) return null;
                                  const rawLimit = extra.coverage_limit && typeof extra.coverage_limit === "string" && !extra.coverage_limit.includes("[object") ? extra.coverage_limit.trim() : "";
                                  const costNum = extra.cost ? parseFloat(String(extra.cost).replace(/[^0-9.]/g, "")) : null;
                                  const limitNum = rawLimit ? parseFloat(rawLimit.replace(/[^0-9.]/g, "")) : null;
                                  const isPlan = Boolean(rawLimit && /\b(plan|tier|level|package|option)\s*\d+\b/i.test(String(extra.label || "") + " " + rawLimit));
                                  const isGenuine = Boolean(rawLimit && limitNum !== null && limitNum > 0 && (costNum === null || Math.abs(limitNum - costNum) > 0.01) && !isPlan && (limitNum >= 100 || /RM/i.test(rawLimit)));
                                  if (!isGenuine) return null;
                                  return (
                                    <div className="text-right">
                                      <span className="block text-[9px] uppercase font-bold text-[var(--rl-text-muted)]">Limit / Sum</span>
                                      <span className="text-xs font-semibold text-[var(--rl-text-strong)] font-mono">
                                        {rawLimit}
                                      </span>
                                    </div>
                                  );
                                })()}

                                {hasCost && extra.cost ? (
                                  <div className="text-right">
                                    <span className="block text-[9px] uppercase font-bold text-[var(--rl-text-muted)]">Cost</span>
                                    <span className="text-xs font-bold text-[var(--rl-red)] font-mono">
                                      {String(extra.cost).startsWith("RM") ? String(extra.cost) : `RM ${extra.cost}`}
                                    </span>
                                  </div>
                                ) : null}

                                {!extra.is_applied && extra.concept_key ? (
                                  <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={() => {
                                      const concept = globalConcepts.find((c) => c.concept_key === extra.concept_key);
                                      if (concept) {
                                        const cleanCost = extra.cost ? Number(String(extra.cost).replace(/[^0-9.]/g, "")) : null;
                                        const priceObj = cleanCost && Number.isFinite(cleanCost) ? { amount: cleanCost, currency: "MYR" } : null;
                                        const cleanLimit = extra.coverage_limit && typeof extra.coverage_limit === "string" ? extra.coverage_limit.trim() : null;
                                        addConceptAsBenefit(concept, "available_addon", priceObj, cleanLimit);
                                      }
                                    }}
                                    className="text-[11px] h-7 px-2.5 shrink-0 font-medium"
                                    title="Add this detected cover to optional add-ons list"
                                  >
                                    + Add to add-ons
                                  </Button>
                                ) : null}
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
