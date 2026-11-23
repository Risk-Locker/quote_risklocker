"use client";

import { useState } from "react";
import {
  ArrowsClockwise,
  CaretDown,
  CaretRight,
  EyeSlash,
  Info,
  Lightning,
  Package as PackageIcon,
  PencilSimple,
  Plus,
  Trash,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PageLoading } from "@/components/ui/page-loading";
import { BundleEditorDialog } from "./bundle-editor-dialog";
import {
  BenefitProfile,
  CompanyBenefitBundle,
  CompanyBenefitCondition,
  CompanySummary as Company,
  ConceptSummary as Concept,
} from "@/types/benefits";

interface BenefitConditionsTabProps {
  isProfileArchived: boolean;
  selectedProfile: BenefitProfile | null;
  selectedCompany: Company | null;
  companyBundles: CompanyBenefitBundle[];
  bundlesLoading: boolean;
  bundleSaving: boolean;
  onSaveBundle: (payload: Omit<CompanyBenefitBundle, "id" | "company_id" | "bundle_key"> & { id?: string; bundle_key?: string }) => Promise<void>;
  onDeleteBundle: (bundleId: string) => void;
  companyConditions: CompanyBenefitCondition[];
  conditionsLoading: boolean;
  concepts: Concept[];
  onOpenAddConditionDialog: () => void;
  onEditCondition: (cond: CompanyBenefitCondition) => void;
  onDeleteCondition: (condId: string) => void;
  onRefreshConcepts?: () => void;
}

export function BenefitConditionsTab({
  isProfileArchived,
  selectedProfile,
  selectedCompany,
  companyBundles,
  bundlesLoading,
  bundleSaving,
  onSaveBundle,
  onDeleteBundle,
  companyConditions,
  conditionsLoading,
  concepts,
  onOpenAddConditionDialog,
  onEditCondition,
  onDeleteCondition,
  onRefreshConcepts,
}: BenefitConditionsTabProps) {
  const [deletingCondId, setDeletingCondId] = useState<string | null>(null);
  const [deletingBundleId, setDeletingBundleId] = useState<string | null>(null);
  const [bundleDialogOpen, setBundleDialogOpen] = useState(false);
  const [editingBundle, setEditingBundle] = useState<CompanyBenefitBundle | null>(null);
  const [showLegacyConditions, setShowLegacyConditions] = useState(false);

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
            is an immutable historical record. Adding, editing, or deleting bundles or rules is locked. Click{" "}
            <strong>&quot;Clone as New Version&quot;</strong> in the profile bar above to create an editable draft.
          </span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">
              {selectedCompany?.name || "Insurance Company"} — Bundled Benefits &amp; Conditions
            </h2>
            <Badge variant="default">
              {companyBundles.length} Bundle{companyBundles.length === 1 ? "" : "s"}
            </Badge>
            <Badge variant="default">
              {companyConditions.length} Simple Rule{companyConditions.length === 1 ? "" : "s"}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
            Configure Bundled Benefits (&quot;Mystery Box&quot; packages with plan versions like Plan 1–4 that stay in Box 2, remove Box 1 base defaults, and unlock upgraded Box 2 benefits) alongside simple conditional overrides.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {onRefreshConcepts && (
            <Button
              size="sm"
              variant="secondary"
              onClick={onRefreshConcepts}
              className="gap-1.5 bg-white border border-[var(--rl-border)] text-[var(--rl-text-strong)] shadow-xs font-semibold"
              title="Refresh benefit concepts library"
            >
              <ArrowsClockwise size={14} weight="bold" />
              <span>Refresh Benefits</span>
            </Button>
          )}
          <Button
            size="sm"
            disabled={isProfileArchived}
            onClick={() => {
              setEditingBundle(null);
              setBundleDialogOpen(true);
            }}
            className="gap-1.5 bg-[var(--rl-red)] hover:bg-red-700 text-white shadow-sm font-semibold"
          >
            <PackageIcon size={14} weight="fill" />
            <span>Add Bundled Benefit</span>
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={isProfileArchived}
            onClick={onOpenAddConditionDialog}
            className="gap-1.5 bg-[var(--rl-black)] text-white shadow-sm font-semibold"
          >
            <Plus size={14} weight="bold" />
            <span>Add Simple Rule</span>
          </Button>
        </div>
      </div>

      {/* Primary Section: Bundled Benefits */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <PackageIcon size={16} weight="fill" className="text-[var(--rl-red)]" />
            <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">
              Bundled Benefits (Plan Versions &amp; Unlocked Box 2 Effects)
            </h3>
          </div>
        </div>

        {bundlesLoading ? (
          <PageLoading />
        ) : companyBundles.length === 0 ? (
          <div className="rounded-[var(--rl-radius)] border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface)] p-8 text-center">
            <PackageIcon size={36} className="mx-auto text-[var(--rl-red)] mb-2" weight="duotone" />
            <h4 className="text-sm font-bold text-[var(--rl-text-strong)]">No Bundled Benefits Configured Yet</h4>
            <p className="mt-1 text-xs text-[var(--rl-text-muted)] max-w-lg mx-auto">
              Create a Bundled Benefit when purchasing an add-on package (e.g. Private Car 365, Motor PA Plus, E-Assist Smart Driver, DPP, OTO 360, Motor Easy Bundle) upgrades or unlocks other Box 2 benefits across plan levels.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {companyBundles.map((bundle) => {
              const primaryConcept = concepts.find((c) => c.id === bundle.primary_concept_id);
              return (
                <Card key={bundle.id} className="border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3 pb-3 border-b border-[var(--rl-border)]/70">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-bold text-[var(--rl-text-strong)]">{bundle.name}</span>
                        {bundle.force_box2 && (
                          <Badge variant="default" className="bg-emerald-50 text-emerald-800 border border-emerald-200 text-[10px]">
                            Forced Box 2
                          </Badge>
                        )}
                        {bundle.has_plan_tiers ? (
                          <Badge variant="default" className="bg-blue-50 text-blue-800 border border-blue-200 text-[10px]">
                            {bundle.tiers.length} Plan Tiers
                          </Badge>
                        ) : (
                          <Badge variant="default" className="text-[10px]">Single Tier</Badge>
                        )}
                        {bundle.catalog_scope && (
                          <Badge variant="default" className="bg-amber-50 text-amber-800 border border-amber-200 text-[10px]">
                            Scope: {bundle.catalog_scope}
                          </Badge>
                        )}
                      </div>
                      <div className="text-[11px] text-[var(--rl-text-muted)] flex flex-wrap gap-x-3 gap-y-0.5">
                        <span>
                          Primary Concept: <strong className="text-[var(--rl-text-strong)]">{primaryConcept?.label || bundle.primary_concept_id}</strong>
                        </span>
                        {bundle.match_aliases.length > 0 && (
                          <span>
                            Keywords: <code className="text-[10px] bg-[var(--rl-bg)] px-1 rounded">{bundle.match_aliases.join(", ")}</code>
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={isProfileArchived}
                        onClick={() => {
                          setEditingBundle(bundle);
                          setBundleDialogOpen(true);
                        }}
                        className="h-7 px-2.5 text-xs gap-1"
                      >
                        <PencilSimple size={13} weight="bold" />
                        <span>Edit</span>
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={isProfileArchived}
                        onClick={() => setDeletingBundleId(bundle.id)}
                        className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                        title="Delete Bundle"
                      >
                        <Trash size={13} />
                      </Button>
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2.5">
                    {bundle.tiers.map((tier) => (
                      <div key={tier.id || tier.label} className="rounded border border-[var(--rl-border)] bg-[var(--rl-bg)]/50 p-2.5 space-y-1.5 text-xs">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-bold text-[var(--rl-text-strong)]">{tier.label}</span>
                          {tier.is_default_fallback && (
                            <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5">
                              Default Fallback
                            </span>
                          )}
                        </div>
                        {tier.effects.map((eff, idx) => {
                          const tConcept = concepts.find((c) => c.id === eff.target_concept_id);
                          return (
                            <div key={eff.id || idx} className="rounded bg-white border border-[var(--rl-border)]/80 px-2.5 py-2 space-y-0.5">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-semibold text-emerald-900">
                                  {eff.display_title || tConcept?.label || eff.target_concept_id}
                                </span>
                                <span className="text-[10px] font-mono text-[var(--rl-text-muted)]">
                                  {eff.effect_type} {eff.comparison_value ? `· ${eff.comparison_value}` : ""}
                                </span>
                              </div>
                              {eff.display_description && (
                                <p className="text-[11px] text-[var(--rl-text-muted)] leading-snug">{eff.display_description}</p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Secondary Section: Legacy / Simple Conditional Rules (Collapsible) */}
      <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-sm overflow-hidden">
        <button
          type="button"
          onClick={() => setShowLegacyConditions((v) => !v)}
          className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[var(--rl-bg)]/50 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2 text-xs font-bold text-[var(--rl-text-strong)]">
            {showLegacyConditions ? <CaretDown size={14} weight="bold" /> : <CaretRight size={14} weight="bold" />}
            <Lightning size={14} weight="fill" className="text-amber-500" />
            <span>Simple / Legacy Conditional Rules ({companyConditions.length})</span>
          </div>
          <span className="text-[11px] text-[var(--rl-text-muted)]">
            {showLegacyConditions ? "Click to collapse" : "Click to expand simple 1-to-1 rules"}
          </span>
        </button>

        {showLegacyConditions && (
          <div className="border-t border-[var(--rl-border)] p-4">
            {conditionsLoading ? (
              <PageLoading />
            ) : companyConditions.length === 0 ? (
              <div className="p-6 text-center">
                <p className="text-xs text-[var(--rl-text-muted)]">
                  No simple conditional rules configured. Manage Box 1 → Box 2 towing promotions via Bundled Benefits above.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-xs">
                  <thead>
                    <tr className="border-b border-[var(--rl-border)] bg-[#1F2937] text-white">
                      <th className="w-[24%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">Rule Name</th>
                      <th className="w-[22%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">Trigger Condition</th>
                      <th className="w-[18%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">Target Benefit</th>
                      <th className="w-[14%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">Action</th>
                      <th className="w-[16%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">Behavior</th>
                      <th className="w-[6%] px-4 py-3 text-center text-[11px] font-bold uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--rl-border)]/70 bg-[var(--rl-surface)]">
                    {companyConditions.map((cond) => {
                      const triggerConcept = concepts.find((c) => c.id === cond.trigger_concept_id);
                      const targetConcept = concepts.find((c) => c.id === cond.target_concept_id);
                      return (
                        <tr key={cond.id} className="hover:bg-[var(--rl-bg)]/40 transition-colors">
                          <td className="px-4 py-3.5 align-top">
                            <div className="font-bold text-[13px] text-[var(--rl-text-strong)]">{cond.name}</div>
                            <span className="text-[10px] text-[var(--rl-text-muted)]">Priority {cond.sort_order ?? 0}</span>
                          </td>
                          <td className="px-4 py-3.5 align-top">
                            <div className="space-y-1">
                              <div className="flex items-center gap-1.5 font-semibold text-emerald-950">
                                <Lightning size={14} className="text-amber-500 shrink-0" weight="fill" />
                                <span>{triggerConcept?.label || cond.trigger_concept_id}</span>
                              </div>
                              {cond.trigger_plan_filter && (
                                <Badge variant="default" className="text-[10px]">
                                  Plan filter: {cond.trigger_plan_filter}
                                </Badge>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3.5 align-top">
                            <div className="font-semibold text-[var(--rl-text-strong)]">{targetConcept?.label || cond.target_concept_id}</div>
                            <div className="text-[10px] font-mono text-[var(--rl-text-muted)]">{targetConcept?.concept_key}</div>
                          </td>
                          <td className="px-4 py-3.5 align-top">
                            {cond.action_type === "hide_target" ? (
                              <span className="inline-flex items-center gap-1 rounded bg-amber-100 text-amber-900 border border-amber-300 px-2 py-0.5 text-[10px] font-bold">
                                <EyeSlash size={12} weight="bold" /> Hide Target
                              </span>
                            ) : cond.action_type === "promote_to_addon" ? (
                              <span className="inline-flex items-center gap-1 rounded bg-emerald-100 text-emerald-900 border border-emerald-300 px-2 py-0.5 text-[10px] font-bold">
                                <Lightning size={12} weight="fill" /> Promote to Box 2
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 rounded bg-blue-100 text-blue-900 border border-blue-300 px-2 py-0.5 text-[10px] font-bold">
                                <PencilSimple size={12} weight="bold" /> Replace in Box 1
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3.5 align-top">
                            <div className="text-[11px] leading-snug text-[var(--rl-text-strong)]">
                              {cond.replacement_title && <div className="font-bold">{cond.replacement_title}</div>}
                              {cond.replacement_value && <div className="text-emerald-700 font-semibold">{cond.replacement_value}</div>}
                              <div>{cond.replacement_description}</div>
                            </div>
                          </td>
                          <td className="px-4 py-3.5 align-middle text-center">
                            <div className="flex items-center justify-center gap-1">
                              <Button
                                variant="secondary"
                                size="sm"
                                disabled={isProfileArchived}
                                onClick={() => onEditCondition(cond)}
                                className="h-7 w-7 p-0 text-blue-600 hover:text-blue-700 hover:bg-blue-50 border-blue-200"
                                title="Edit Rule"
                              >
                                <PencilSimple size={13} weight="bold" />
                              </Button>
                              <Button
                                variant="secondary"
                                size="sm"
                                disabled={isProfileArchived}
                                onClick={() => setDeletingCondId(cond.id)}
                                className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                                title="Delete Rule"
                              >
                                <Trash size={13} />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      <BundleEditorDialog
        open={bundleDialogOpen}
        onOpenChange={setBundleDialogOpen}
        selectedCompany={selectedCompany}
        concepts={concepts}
        editingBundle={editingBundle}
        saving={bundleSaving}
        onSave={onSaveBundle}
      />

      <ConfirmDialog
        open={Boolean(deletingBundleId)}
        onOpenChange={(open) => !open && setDeletingBundleId(null)}
        title="Delete Bundled Benefit"
        message="Are you sure you want to delete this bundled benefit? Quotes will no longer apply its automatic Box 2 unlocked upgrades."
        confirmLabel="Delete Bundle"
        onConfirm={() => {
          if (deletingBundleId) {
            onDeleteBundle(deletingBundleId);
            setDeletingBundleId(null);
          }
        }}
      />

      <ConfirmDialog
        open={Boolean(deletingCondId)}
        onOpenChange={(open) => !open && setDeletingCondId(null)}
        title="Delete Conditional Rule"
        message="Are you sure you want to delete this conditional rule? Quotes will no longer apply this automatic benefit upgrade or suppression."
        confirmLabel="Delete Rule"
        onConfirm={() => {
          if (deletingCondId) {
            onDeleteCondition(deletingCondId);
            setDeletingCondId(null);
          }
        }}
      />
    </div>
  );
}
