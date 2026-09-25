"use client";

import {
  EyeSlash,
  Info,
  Lightning,
  PencilSimple,
  Plus,
  Trash,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageLoading } from "@/components/ui/page-loading";
import {
  BenefitProfile,
  CompanyBenefitCondition,
  CompanySummary as Company,
  ConceptSummary as Concept,
} from "@/types/benefits";

interface BenefitConditionsTabProps {
  isProfileArchived: boolean;
  selectedProfile: BenefitProfile | null;
  selectedCompany: Company | null;
  companyConditions: CompanyBenefitCondition[];
  conditionsLoading: boolean;
  concepts: Concept[];
  onOpenAddConditionDialog: () => void;
  onQuickCreateUnlimitedTowingRule: () => void;
  onDeleteCondition: (condId: string) => void;
}

export function BenefitConditionsTab({
  isProfileArchived,
  selectedProfile,
  selectedCompany,
  companyConditions,
  conditionsLoading,
  concepts,
  onOpenAddConditionDialog,
  onQuickCreateUnlimitedTowingRule,
  onDeleteCondition,
}: BenefitConditionsTabProps) {
  return (
    <div className="space-y-6">
      {isProfileArchived && (
        <div className="flex items-center gap-2.5 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50 px-4 py-3 text-xs text-amber-950 shadow-sm">
          <Info size={18} className="text-amber-600 shrink-0" weight="fill" />
          <span>
            <strong>Archived Profile (Read-Only):</strong> Profile{" "}
            <em>
              {selectedProfile?.name} (v{selectedProfile?.version_number})
            </em>{" "}
            is an immutable historical record. Adding, editing, or deleting
            condition rules is locked. Click{" "}
            <strong>&quot;Clone as New Version&quot;</strong> in the profile bar
            above to create an editable draft.
          </span>
        </div>
      )}
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">
              {selectedCompany?.name || "Insurance Company"} — Benefit
              Conditions & Logic Rules
            </h2>
            <Badge variant="default">
              {companyConditions.length} Rule
              {companyConditions.length === 1 ? "" : "s"} Active
            </Badge>
          </div>
          <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
            Dynamic rules evaluate during quotation review and PDF generation.
            Example: If the customer purchases Driver Passenger Protector, Towing
            & Assistance is upgraded to &quot;Unlimited towing distance&quot;.
          </p>
        </div>

        <Button
          size="sm"
          onClick={onOpenAddConditionDialog}
          className="gap-1.5 bg-[var(--rl-black)] text-white shadow-sm font-semibold"
        >
          <Plus size={14} weight="bold" />
          <span>Add Conditional Rule</span>
        </Button>
      </div>

      {/* Conditions Table or Empty State */}
      {conditionsLoading ? (
        <PageLoading />
      ) : companyConditions.length === 0 ? (
        <div className="rounded-[var(--rl-radius)] border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface)] p-12 text-center">
          <Lightning
            size={40}
            className="mx-auto text-amber-500 mb-3"
            weight="duotone"
          />
          <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">
            No Conditional Rules Configured
          </h3>
          <p className="mt-1.5 text-xs text-[var(--rl-text-muted)] max-w-md mx-auto leading-relaxed">
            Configure dynamic cross-benefit rules. When a user selects a specific
            endorsement or plan, other benefits automatically upgrade their
            limit or description.
          </p>
          <div className="mt-4 flex justify-center gap-2">
            <Button
              size="sm"
              onClick={onQuickCreateUnlimitedTowingRule}
              className="gap-1.5 bg-[var(--rl-black)] text-white shadow-sm font-semibold"
            >
              <Plus size={14} weight="bold" />
              <span>Create Driver Passenger → Unlimited Towing Rule</span>
            </Button>
          </div>
        </div>
      ) : (
        <Card className="overflow-hidden border border-[var(--rl-border)] shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-xs">
              <thead>
                <tr className="border-b border-[var(--rl-border)] bg-[#1F2937] text-white">
                  <th className="w-[24%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Rule Name
                  </th>
                  <th className="w-[22%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Trigger Condition (When Active)
                  </th>
                  <th className="w-[18%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Target Benefit
                  </th>
                  <th className="w-[14%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Action
                  </th>
                  <th className="w-[16%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Behavior / Description
                  </th>
                  <th className="w-[6%] px-4 py-3 text-center text-[11px] font-bold uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--rl-border)]/70 bg-[var(--rl-surface)]">
                {companyConditions.map((cond) => {
                  const triggerConcept = concepts.find(
                    (c) => c.id === cond.trigger_concept_id
                  );
                  const targetConcept = concepts.find(
                    (c) => c.id === cond.target_concept_id
                  );

                  return (
                    <tr
                      key={cond.id}
                      className="hover:bg-[var(--rl-bg)]/40 transition-colors"
                    >
                      <td className="px-4 py-3.5 align-top">
                        <div className="font-bold text-[13px] text-[var(--rl-text-strong)]">
                          {cond.name}
                        </div>
                        <span className="text-[10px] text-[var(--rl-text-muted)]">
                          Priority {cond.sort_order ?? 0}
                        </span>
                      </td>

                      <td className="px-4 py-3.5 align-top">
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5 font-semibold text-emerald-950">
                            <Lightning
                              size={14}
                              className="text-amber-500 shrink-0"
                              weight="fill"
                            />
                            <span>
                              {triggerConcept?.label || cond.trigger_concept_id}
                            </span>
                          </div>
                          {cond.trigger_plan_filter && (
                            <Badge variant="default" className="text-[10px]">
                              Plan filter: {cond.trigger_plan_filter}
                            </Badge>
                          )}
                        </div>
                      </td>

                      <td className="px-4 py-3.5 align-top">
                        <div className="font-semibold text-[var(--rl-text-strong)]">
                          {targetConcept?.label || cond.target_concept_id}
                        </div>
                        <div className="text-[10px] font-mono text-[var(--rl-text-muted)]">
                          {targetConcept?.concept_key}
                        </div>
                      </td>

                      <td className="px-4 py-3.5 align-top">
                        {cond.action_type === "hide_target" ? (
                          <span className="inline-flex items-center gap-1 rounded bg-amber-100 text-amber-900 border border-amber-300 px-2 py-0.5 text-[10px] font-bold">
                            <EyeSlash size={12} weight="bold" />
                            Hide Target
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded bg-blue-100 text-blue-900 border border-blue-300 px-2 py-0.5 text-[10px] font-bold">
                            <PencilSimple size={12} weight="bold" />
                            Replace Desc
                          </span>
                        )}
                      </td>

                      <td className="px-4 py-3.5 align-top">
                        {cond.action_type === "hide_target" ? (
                          <div className="rounded border border-amber-200 bg-amber-50/80 p-2 text-amber-950 font-medium text-[11px] leading-snug">
                            Automatically hides target benefit from quotation cards
                          </div>
                        ) : (
                          <div className="rounded border border-blue-200 bg-blue-50/70 p-2 text-blue-950 font-medium text-[11px] leading-snug">
                            &quot;{cond.replacement_description}&quot;
                          </div>
                        )}
                      </td>

                      <td className="px-4 py-3.5 align-middle text-center">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => onDeleteCondition(cond.id)}
                          className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                          title="Delete Rule"
                        >
                          <Trash size={13} />
                        </Button>
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
