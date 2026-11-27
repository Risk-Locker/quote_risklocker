"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { ArrowClockwise, CheckCircle, Info, MagnifyingGlass } from "@phosphor-icons/react";
import type {
  BettermentPolicyRule,
  CompanySummary as Company,
  ConceptSummary as Concept,
  BenefitProfile,
  CompanyBenefitConfig,
} from "@/types/benefits";

export interface CompanyBenefitsTabProps {
  selectedProfile: BenefitProfile | null;
  isProfileArchived: boolean;
  selectedCompany: Company | null;
  onSaveBettermentRule?: (companyId: string, rule: BettermentPolicyRule) => Promise<void>;
  concepts: Concept[];
  companyConfigs: CompanyBenefitConfig[];
  configsLoading: boolean;
  configsSaving: boolean;
  configsSearch: string;
  setConfigsSearch: (v: string) => void;
  // RL-DISABLED configsCategoryFilter/setConfigsCategoryFilter — disabled 2026-10-03; category tagging removed, all benefits are flat
  // configsCategoryFilter: "all" | "default" | "addon";
  // setConfigsCategoryFilter: (v: "all" | "default" | "addon") => void;
  setAllConfigsEnabled: (enabled: boolean) => void;
  saveCompanyConfigs: () => void;
  customizingCostIds: Set<string>;
  setCustomizingCostIds: React.Dispatch<React.SetStateAction<Set<string>>>;
  toggleConfigEnabled: (conceptId: string, enabled: boolean) => void;
  updateConfigBaseline: (conceptId: string, desc: string) => void;
  updateConfigBaselineCost: (conceptId: string, cost: string) => void;
}

export function CompanyBenefitsTab({
  selectedProfile,
  isProfileArchived,
  selectedCompany,
  onSaveBettermentRule,
  concepts,
  companyConfigs,
  configsLoading,
  configsSaving,
  configsSearch,
  setConfigsSearch,
  // RL-DISABLED configsCategoryFilter/setConfigsCategoryFilter — disabled 2026-10-03
  // configsCategoryFilter,
  // setConfigsCategoryFilter,
  setAllConfigsEnabled,
  saveCompanyConfigs,
  customizingCostIds,
  setCustomizingCostIds,
  toggleConfigEnabled,
  updateConfigBaseline,
  updateConfigBaselineCost,
}: CompanyBenefitsTabProps) {
  const [ruleDraft, setRuleDraft] = useState<BettermentPolicyRule>({
    auto_waive_without_peril: false,
    allow_addon_purchase: true,
    free_exemption_years: 5,
    max_waiver_years: 10,
    free_display: "Up to 5 Years",
    default_display: "Up to 10 Years",
  });
  const [ruleSaving, setRuleSaving] = useState(false);
  const [ruleStatus, setRuleStatus] = useState<"idle" | "saved" | "error">("idle");
  const [ruleError, setRuleError] = useState("");

  useEffect(() => {
    setRuleStatus("idle");
    setRuleError("");
  }, [selectedCompany?.id]);

  useEffect(() => {
    const r = selectedCompany?.betterment_rule || selectedCompany?.policy_rules?.betterment;
    const freeYrs = typeof r?.free_exemption_years === "number" ? r.free_exemption_years : 5;
    const maxYrs = typeof r?.max_waiver_years === "number" ? r.max_waiver_years : 10;
    setRuleDraft({
      auto_waive_without_peril: Boolean(r?.auto_waive_without_peril ?? false),
      allow_addon_purchase: Boolean(r?.allow_addon_purchase ?? true),
      free_exemption_years: freeYrs,
      max_waiver_years: maxYrs,
      free_display: r?.free_display || `Up to ${freeYrs} Years`,
      default_display: r?.default_display || "Up to 10 Years",
    });
  }, [selectedCompany?.id, selectedCompany?.betterment_rule, selectedCompany?.policy_rules]);

  async function handleSaveRule() {
    if (!selectedCompany || !onSaveBettermentRule) return;
    if (ruleDraft.free_exemption_years > ruleDraft.max_waiver_years) {
      setRuleError("Free exemption years cannot exceed max waiver years.");
      setRuleStatus("error");
      return;
    }
    setRuleSaving(true);
    setRuleError("");
    setRuleStatus("idle");
    try {
      await onSaveBettermentRule(selectedCompany.id, ruleDraft);
      setRuleStatus("saved");
    } catch (err) {
      setRuleError(err instanceof Error ? err.message : "Failed to save betterment policy rules.");
      setRuleStatus("error");
    } finally {
      setRuleSaving(false);
    }
  }
  const enabledConfigsCount = useMemo(() => {
    const configMap = new Map(companyConfigs.map((c) => [c.concept_id, c]));
    return concepts.filter((c) => {
      if (c.status === "retired") return false;
      const cfg = configMap.get(c.id);
      return cfg ? cfg.is_enabled : false;
    }).length;
  }, [concepts, companyConfigs]);

  const filteredCompanyBenefitRows = useMemo(() => {
    const configMap = new Map(companyConfigs.map((c) => [c.concept_id, c]));
    return concepts
      .filter((c) => {
        if (c.status === "retired") return false;
        const cfg = configMap.get(c.id);
        // RL-DISABLED default/addon category filtering — disabled 2026-10-03; all benefits are now a flat list
        if (configsSearch.trim()) {
          const q = configsSearch.toLowerCase();
          const labelMatch = c.label?.toLowerCase().includes(q);
          const keyMatch = c.concept_key?.toLowerCase().includes(q);
          const descMatch = (cfg?.baseline_description || c.description || "").toLowerCase().includes(q);
          if (!labelMatch && !keyMatch && !descMatch) return false;
        }
        return true;
      })
      .map((c) => {
        const cfg = configMap.get(c.id);
        return {
          concept: c,
          config: cfg,
          isEnabled: cfg ? cfg.is_enabled : true,
          baselineDescription: cfg?.baseline_description ?? null,
          baselineCost: cfg?.baseline_cost ?? null,
        };
      })
      .sort((a, b) => {
        if (a.isEnabled !== b.isEnabled) {
          return a.isEnabled ? -1 : 1;
        }
        return (a.concept.sort_order ?? 99) - (b.concept.sort_order ?? 99);
      });
  }, [concepts, companyConfigs, configsSearch]);

  return (
    <div className="space-y-6">
      {isProfileArchived && (
        <div className="flex items-center gap-2.5 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50 px-4 py-3 text-xs text-amber-950 shadow-sm">
          <Info size={18} className="text-amber-600 shrink-0" weight="fill" />
          <span>
            <strong>Archived Profile (Read-Only):</strong> Profile <em>{selectedProfile?.name} (v{selectedProfile?.version_number})</em> is an immutable historical record. Toggling benefits and editing descriptions is locked. Click <strong>&quot;Clone as New Version&quot;</strong> in the profile bar above to create an editable draft.
          </span>
        </div>
      )}

      {selectedCompany && onSaveBettermentRule && (
        <Card className="border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--rl-border)] pb-3">
            <div>
              <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">
                Waiver of Betterment Rules — {selectedCompany.name}
              </h3>
              <p className="mt-0.5 text-xs text-[var(--rl-text-muted)]">
                Database-driven age thresholds controlling Box 1 free coverage, Box 2 paid option, and comparison scale.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {ruleStatus === "saved" && (
                <span className="text-xs font-semibold text-emerald-700">Saved</span>
              )}
              <Button
                size="sm"
                onClick={() => void handleSaveRule()}
                disabled={ruleSaving || isProfileArchived}
                className="h-8 gap-1.5 text-xs"
              >
                {ruleSaving ? <ArrowClockwise size={13} className="animate-spin" /> : <CheckCircle size={13} weight="bold" />}
                <span>{ruleSaving ? "Saving..." : "Save Policy Rules"}</span>
              </Button>
            </div>
          </div>

          {ruleError && (
            <div className="mt-3 rounded-[var(--rl-radius-sm)] border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">
              {ruleError}
            </div>
          )}

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
            <label className="flex items-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] px-3 py-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={ruleDraft.auto_waive_without_peril}
                disabled={isProfileArchived || ruleSaving}
                onChange={(e) => setRuleDraft((p) => ({ ...p, auto_waive_without_peril: e.target.checked }))}
                className="h-3.5 w-3.5 accent-[var(--rl-black)]"
              />
              <span className="font-medium text-[var(--rl-text-strong)]">Auto-waive (Free)</span>
            </label>

            <label className="flex items-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] px-3 py-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={ruleDraft.allow_addon_purchase}
                disabled={isProfileArchived || ruleSaving}
                onChange={(e) => setRuleDraft((p) => ({ ...p, allow_addon_purchase: e.target.checked }))}
                className="h-3.5 w-3.5 accent-[var(--rl-black)]"
              />
              <span className="font-medium text-[var(--rl-text-strong)]">Allow Box 2 Add-on</span>
            </label>

            <div className="space-y-1">
              <label className="block text-[10px] font-semibold uppercase tracking-wide text-[var(--rl-text-muted)]">
                Free Exemption Yrs
              </label>
              <Input
                type="number"
                min={0}
                max={20}
                value={ruleDraft.free_exemption_years}
                disabled={isProfileArchived || ruleSaving}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setRuleDraft((p) => ({ ...p, free_exemption_years: Math.max(0, Number(e.target.value) || 0) }))
                }
                className="h-8 text-xs"
              />
            </div>

            <div className="space-y-1">
              <label className="block text-[10px] font-semibold uppercase tracking-wide text-[var(--rl-text-muted)]">
                Max Waiver Yrs
              </label>
              <Input
                type="number"
                min={0}
                max={20}
                value={ruleDraft.max_waiver_years}
                disabled={isProfileArchived || ruleSaving}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setRuleDraft((p) => ({ ...p, max_waiver_years: Math.max(0, Number(e.target.value) || 0) }))
                }
                className="h-8 text-xs"
              />
            </div>

            <div className="space-y-1">
              <label className="block text-[10px] font-semibold uppercase tracking-wide text-[var(--rl-text-muted)]">
                Free Display Label
              </label>
              <Input
                value={ruleDraft.free_display || ""}
                disabled={isProfileArchived || ruleSaving}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setRuleDraft((p) => ({ ...p, free_display: e.target.value }))
                }
                placeholder="Up to 5 Years"
                className="h-8 text-xs"
              />
            </div>

            <div className="space-y-1">
              <label className="block text-[10px] font-semibold uppercase tracking-wide text-[var(--rl-text-muted)]">
                Add-on Display Label
              </label>
              <Input
                value={ruleDraft.default_display || ""}
                disabled={isProfileArchived || ruleSaving}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setRuleDraft((p) => ({ ...p, default_display: e.target.value }))
                }
                placeholder="Up to 10 Years"
                className="h-8 text-xs"
              />
            </div>
          </div>
        </Card>
      )}

      {/* Header & Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">
              {selectedCompany?.name || "Insurance Company"} — Master Benefit Pool & Baseline Descriptions
            </h2>
            <Badge variant="default">
              {enabledConfigsCount} of {concepts.length} Enabled
            </Badge>
          </div>
          <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
            Toggle which benefits are offered by this insurer and set insurer-specific baseline short descriptions.
            Scenario catalogs strictly inherit only from enabled benefits here.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Search input */}
          <div className="relative min-w-[220px]">
            <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
            <Input
              value={configsSearch}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setConfigsSearch(e.target.value)}
              placeholder="Search benefit or description..."
              className="pl-8 text-xs h-8"
            />
          </div>

          {/* RL-DISABLED Category filters — disabled 2026-10-03; all benefits are now a flat unified list */}

          {/* Quick Toggle Buttons */}
          <div className="flex items-center gap-1.5">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setAllConfigsEnabled(true)}
              className="h-8 text-xs font-medium"
            >
              Enable All
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setAllConfigsEnabled(false)}
              className="h-8 text-xs font-medium text-[var(--rl-text-muted)]"
            >
              Disable All
            </Button>
            <Button
              size="sm"
              onClick={saveCompanyConfigs}
              disabled={configsSaving || isProfileArchived}
              className={`h-8 gap-1.5 text-white shadow-sm font-semibold ${
                isProfileArchived ? "bg-neutral-400 cursor-not-allowed" : "bg-emerald-600 hover:bg-emerald-700"
              }`}
              title={isProfileArchived ? "Archived profile is read-only. Clone it to modify." : "Save Benefit Pool"}
            >
              {configsSaving ? <ArrowClockwise size={14} className="animate-spin" /> : <CheckCircle size={14} weight="bold" />}
              <span>{configsSaving ? "Saving..." : isProfileArchived ? "Archived (Read-Only)" : "Save Benefit Pool"}</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Benefit Configs Table */}
      {configsLoading ? (
        <PageLoading />
      ) : filteredCompanyBenefitRows.length === 0 ? (
        <div className="rounded-[var(--rl-radius)] border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface)] p-12 text-center text-xs text-[var(--rl-text-muted)]">
          No benefits match your search or filter.
        </div>
      ) : (
        <Card className="overflow-hidden border border-[var(--rl-border)] shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-xs">
              <thead>
                <tr className="border-b border-[var(--rl-border)] bg-[#1F2937] text-white">
                  <th className="w-12 px-4 py-3 text-center text-[11px] font-bold uppercase tracking-wider">
                    Active
                  </th>
                  <th className="w-[24%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Global Benefit Concept
                  </th>
                  <th className="w-[34%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Insurer Baseline Short Description (Used in Quotation Cards)
                  </th>
                  <th className="w-[22%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Default Price / Cost (Catalog Baseline)
                  </th>
                  <th className="w-[12%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Global Fallback
                  </th>
                  <th className="w-16 px-4 py-3 text-center text-[11px] font-bold uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--rl-border)]/70 bg-[var(--rl-surface)]">
                {filteredCompanyBenefitRows.map(({ concept: c, isEnabled, baselineDescription, baselineCost }) => {
                  // RL-DISABLED isDefault categorization — disabled 2026-10-03; all benefits are treated equally
                  const hasCustom = Boolean(baselineDescription && baselineDescription.trim() && baselineDescription.trim() !== (c.description || "").trim());

                  return (
                    <tr
                      key={c.id}
                      className={`transition-colors ${
                        isEnabled ? "hover:bg-[var(--rl-bg)]/50" : "bg-neutral-50/50 opacity-60 hover:opacity-100"
                      }`}
                    >
                      {/* Checkbox */}
                      <td className="px-4 py-3 text-center align-middle">
                        <input
                          type="checkbox"
                          checked={isEnabled}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => toggleConfigEnabled(c.id, e.target.checked)}
                          className="h-4 w-4 rounded border-[var(--rl-border)] text-[var(--rl-black)] focus:ring-[var(--rl-black)] cursor-pointer"
                        />
                      </td>

                      {/* Benefit Concept */}
                      <td className="px-4 py-3 align-top">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className={`font-bold text-[13px] leading-snug ${isEnabled ? "text-[var(--rl-text-strong)]" : "text-[var(--rl-text-muted)] line-through"}`}>
                              {c.label}
                            </span>
                            <span className="rounded bg-[var(--rl-bg)] border border-[var(--rl-border)] px-1.5 py-0.5 text-[10px] font-mono text-[var(--rl-text-muted)]">
                              {c.concept_key}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 pt-0.5">
                            <Badge variant={isEnabled ? "success" : "default"}>
                              {isEnabled ? "Active in Pool" : "Disabled in Pool"}
                            </Badge>
                            {hasCustom && (
                              <span className="rounded bg-blue-100 text-blue-800 border border-blue-200 px-1.5 py-0.2 text-[9px] font-bold uppercase">
                                Customized for Insurer
                              </span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Baseline Short Description */}
                      <td className="px-4 py-3 align-top">
                        <div className="space-y-1">
                          <Input
                            maxLength={120}
                            value={baselineDescription ?? ""}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateConfigBaseline(c.id, e.target.value)}
                            placeholder={c.description || "Enter insurer baseline short description..."}
                            disabled={!isEnabled}
                            className="text-xs h-8 bg-[var(--rl-bg)] focus:bg-[var(--rl-surface)] border-[var(--rl-border)] font-medium"
                          />
                          <div className="flex items-center justify-between text-[10px] text-[var(--rl-text-muted)]">
                            <span>Displays under benefit card on Review Workspace & generated PDFs</span>
                            {hasCustom && (
                              <button
                                onClick={() => updateConfigBaseline(c.id, "")}
                                className="text-blue-600 hover:underline font-semibold"
                              >
                                Reset to Global Default
                              </button>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Default Price / Cost */}
                      <td className="px-4 py-3 align-top">
                        <div className="space-y-1">
                          {!baselineCost && !customizingCostIds.has(c.id) ? (
                            <div className="flex items-center gap-2 pt-1">
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                0 RM (Free)
                              </span>
                              <button
                                type="button"
                                onClick={() => setCustomizingCostIds((prev) => new Set(prev).add(c.id))}
                                className="text-[10px] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] underline"
                                title="Click to enter a custom cost override"
                              >
                                Set Price
                              </button>
                            </div>
                          ) : (
                            <>
                              <Input
                                value={baselineCost ?? ""}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateConfigBaselineCost(c.id, e.target.value)}
                                onBlur={() => {
                                  if (!baselineCost || !baselineCost.trim()) {
                                    setCustomizingCostIds((prev) => {
                                      const next = new Set(prev);
                                      next.delete(c.id);
                                      return next;
                                    });
                                  }
                                }}
                                placeholder={
                                  c.concept_key === "windscreen"
                                    ? "15% of Sum Covered"
                                    : "e.g. RM 20.00 or 15% of Sum Covered"
                                }
                                disabled={!isEnabled}
                                className="text-xs h-8 bg-[var(--rl-bg)] focus:bg-[var(--rl-surface)] border-[var(--rl-border)] font-medium font-mono"
                              />
                              <div className="flex items-center justify-between text-[10px] text-[var(--rl-text-muted)]">
                                <span>
                                  {c.concept_key === "windscreen"
                                    ? "Formula: 15% of Sum Covered"
                                    : baselineCost?.includes("%")
                                    ? "Tariff formula (% rate)"
                                    : "Leave blank for 0 RM (free)"}
                                </span>
                                {(baselineCost || customizingCostIds.has(c.id)) && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      updateConfigBaselineCost(c.id, "");
                                      setCustomizingCostIds((prev) => {
                                        const next = new Set(prev);
                                        next.delete(c.id);
                                        return next;
                                      });
                                    }}
                                    className="text-red-600 hover:underline font-semibold"
                                  >
                                    Clear
                                  </button>
                                )}
                              </div>
                            </>
                          )}
                        </div>
                      </td>

                      {/* Global Fallback */}
                      <td className="px-4 py-3 align-top text-[11px] text-[var(--rl-text-muted)] italic leading-relaxed">
                        {c.description || "No description set"}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3 text-center align-middle">
                        <Badge variant={isEnabled ? "success" : "default"}>
                          {isEnabled ? "Active" : "Excluded"}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
