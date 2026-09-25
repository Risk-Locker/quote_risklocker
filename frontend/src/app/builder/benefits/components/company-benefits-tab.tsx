"use client";

import React, { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { ArrowClockwise, CheckCircle, Info, MagnifyingGlass } from "@phosphor-icons/react";
import type {
  CompanySummary as Company,
  ConceptSummary as Concept,
  BenefitProfile,
  CompanyBenefitConfig,
} from "@/types/benefits";

export interface CompanyBenefitsTabProps {
  selectedProfile: BenefitProfile | null;
  isProfileArchived: boolean;
  selectedCompany: Company | null;
  concepts: Concept[];
  companyConfigs: CompanyBenefitConfig[];
  configsLoading: boolean;
  configsSaving: boolean;
  configsSearch: string;
  setConfigsSearch: (v: string) => void;
  configsCategoryFilter: "all" | "default" | "addon";
  setConfigsCategoryFilter: (v: "all" | "default" | "addon") => void;
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
  concepts,
  companyConfigs,
  configsLoading,
  configsSaving,
  configsSearch,
  setConfigsSearch,
  configsCategoryFilter,
  setConfigsCategoryFilter,
  setAllConfigsEnabled,
  saveCompanyConfigs,
  customizingCostIds,
  setCustomizingCostIds,
  toggleConfigEnabled,
  updateConfigBaseline,
  updateConfigBaselineCost,
}: CompanyBenefitsTabProps) {
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
        const isDefault =
          c.value_schema?.category === "default" ||
          c.category === "default" ||
          (c.sort_order !== undefined && c.sort_order <= 11);
        if (configsCategoryFilter === "default" && !isDefault) return false;
        if (configsCategoryFilter === "addon" && isDefault) return false;
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
  }, [concepts, companyConfigs, configsCategoryFilter, configsSearch]);

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

          {/* Category filters */}
          <div className="flex items-center rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-0.5 text-xs">
            <button
              onClick={() => setConfigsCategoryFilter("all")}
              className={`rounded-[3px] px-2.5 py-1 font-medium transition-all ${
                configsCategoryFilter === "all"
                  ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] shadow-sm font-semibold"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              All ({concepts.length})
            </button>
            <button
              onClick={() => setConfigsCategoryFilter("default")}
              className={`rounded-[3px] px-2.5 py-1 font-medium transition-all ${
                configsCategoryFilter === "default"
                  ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] shadow-sm font-semibold"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              Core Defaults
            </button>
            <button
              onClick={() => setConfigsCategoryFilter("addon")}
              className={`rounded-[3px] px-2.5 py-1 font-medium transition-all ${
                configsCategoryFilter === "addon"
                  ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] shadow-sm font-semibold"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              Add-ons
            </button>
          </div>

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
                  const isDefault = c.category === "default" || (c.sort_order !== undefined && c.sort_order <= 11);
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
                          {isDefault && !baselineCost && !customizingCostIds.has(c.id) ? (
                            <div className="flex items-center gap-2 pt-1">
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                Included (FOC)
                              </span>
                              <button
                                type="button"
                                onClick={() => setCustomizingCostIds((prev) => new Set(prev).add(c.id))}
                                className="text-[10px] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] underline"
                                title="Click to enter a custom cost override"
                              >
                                Customize
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
                                  isDefault
                                    ? "e.g. RM 50.00"
                                    : c.concept_key === "windscreen"
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
                                    : isDefault
                                    ? "Free default (leave blank for FOC)"
                                    : "Base add-on cost"}
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
