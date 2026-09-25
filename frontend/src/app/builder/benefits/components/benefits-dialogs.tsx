"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Check, Copy, EyeSlash, Info, Lightning, PencilSimple } from "@phosphor-icons/react";
import type { CompanyMatrixData } from "../types";
import type {
  CompanySummary as Company,
  ConceptSummary as Concept,
  BenefitProfile,
} from "@/types/benefits";

export interface BenefitsDialogsProps {
  dialog: "config" | "clone" | "bundle" | null;
  setDialog: (d: "config" | "clone" | "bundle" | null) => void;
  formName: string;
  setFormName: (val: string) => void;
  formAsPackage: boolean;
  setFormAsPackage: (val: boolean) => void;
  formPackageName: string;
  setFormPackageName: (val: string) => void;
  createConfig: () => void;
  clonePackage: () => void;
  createBundle: () => void;
  saving: boolean;
  showAiModal: boolean;
  setShowAiModal: (open: boolean) => void;
  matrixData: CompanyMatrixData | null;
  aiModalTab: "spec" | "diff";
  setAiModalTab: (tab: "spec" | "diff") => void;
  copyAiPrompt: () => void;
  copiedPrompt: boolean;
  aiSyncPrompt: string;
  aiDiffInput: string;
  setAiDiffInput: (val: string) => void;
  runAiDiffCheck: () => void;
  aiDiffLoading: boolean;
  aiDiffResult: any;
  conditionDialog: boolean;
  setConditionDialog: (open: boolean) => void;
  selectedCompany: Company | null;
  condFormName: string;
  setCondFormName: (val: string) => void;
  condTriggerId: string;
  setCondTriggerId: (val: string) => void;
  concepts: Concept[];
  condPlanFilter: string;
  setCondPlanFilter: (val: string) => void;
  condTargetId: string;
  setCondTargetId: (val: string) => void;
  condActionType: "replace_description" | "hide_target";
  setCondActionType: (action: "replace_description" | "hide_target") => void;
  condReplacement: string;
  setCondReplacement: (val: string) => void;
  saveCompanyCondition: () => void;
  conditionSaving: boolean;
  cloneModalOpen: boolean;
  setCloneModalOpen: (open: boolean) => void;
  selectedProfile: BenefitProfile | null;
  cloneName: string;
  setCloneName: (val: string) => void;
  cloneNotes: string;
  setCloneNotes: (val: string) => void;
  handleCloneProfile: () => void;
  profileActionLoading: boolean;
}

export function BenefitsDialogs({
  dialog,
  setDialog,
  formName,
  setFormName,
  formAsPackage,
  setFormAsPackage,
  formPackageName,
  setFormPackageName,
  createConfig,
  clonePackage,
  createBundle,
  saving,
  showAiModal,
  setShowAiModal,
  matrixData,
  aiModalTab,
  setAiModalTab,
  copyAiPrompt,
  copiedPrompt,
  aiSyncPrompt,
  aiDiffInput,
  setAiDiffInput,
  runAiDiffCheck,
  aiDiffLoading,
  aiDiffResult,
  conditionDialog,
  setConditionDialog,
  selectedCompany,
  condFormName,
  setCondFormName,
  condTriggerId,
  setCondTriggerId,
  concepts,
  condPlanFilter,
  setCondPlanFilter,
  condTargetId,
  setCondTargetId,
  condActionType,
  setCondActionType,
  condReplacement,
  setCondReplacement,
  saveCompanyCondition,
  conditionSaving,
  cloneModalOpen,
  setCloneModalOpen,
  selectedProfile,
  cloneName,
  setCloneName,
  cloneNotes,
  setCloneNotes,
  handleCloneProfile,
  profileActionLoading,
}: BenefitsDialogsProps) {
  return (
    <>
      {/* ── Dialog: Add Configuration ────────────────────────────────── */}
      {dialog === "config" && (
        <Dialog open={dialog === "config"} onOpenChange={() => setDialog(null)} title="Add Configuration">
          <div className="max-w-md p-6">
            <p className="text-xs text-[var(--rl-text-muted)]">
              Create a new product configuration or package tier.
            </p>
            <div className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)]">Configuration Name</label>
                <Input
                  value={formName}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormName(e.target.value)}
                  placeholder="e.g. Private Car Protector"
                  className="mt-1 w-full"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="formAsPackage"
                  checked={formAsPackage}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormAsPackage(e.target.checked)}
                />
                <label htmlFor="formAsPackage" className="font-medium text-[var(--rl-text-strong)]">
                  Create as named package (Package mode)
                </label>
              </div>
              {formAsPackage && (
                <div>
                  <label className="block font-semibold text-[var(--rl-text-strong)]">Package Name</label>
                  <Input
                    value={formPackageName}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormPackageName(e.target.value)}
                    placeholder="e.g. auto365 Comprehensive Lite"
                    className="mt-1 w-full"
                  />
                </div>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" size="sm" onClick={() => setDialog(null)}>
                  Cancel
                </Button>
                <Button size="sm" onClick={createConfig} disabled={saving}>
                  {saving ? "Creating..." : "Create"}
                </Button>
              </div>
            </div>
          </div>
        </Dialog>
      )}

      {/* ── Dialog: Clone Package ────────────────────────────────────── */}
      {dialog === "clone" && (
        <Dialog open={dialog === "clone"} onOpenChange={() => setDialog(null)} title="Clone Package">
          <div className="max-w-md p-6">
            <p className="text-xs text-[var(--rl-text-muted)]">
              Create a duplicate package tier based on this active configuration.
            </p>
            <div className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)]">New Package Name</label>
                <Input
                  value={formName}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormName(e.target.value)}
                  className="mt-1 w-full"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" size="sm" onClick={() => setDialog(null)}>
                  Cancel
                </Button>
                <Button size="sm" onClick={clonePackage} disabled={saving}>
                  {saving ? "Cloning..." : "Clone"}
                </Button>
              </div>
            </div>
          </div>
        </Dialog>
      )}

      {/* ── Dialog: New Bundle ───────────────────────────────────────── */}
      {dialog === "bundle" && (
        <Dialog open={dialog === "bundle"} onOpenChange={() => setDialog(null)} title="New Addon Bundle">
          <div className="max-w-md p-6">
            <p className="text-xs text-[var(--rl-text-muted)]">
              Create a grouped bundle of add-on offerings.
            </p>
            <div className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)]">Bundle Name</label>
                <Input
                  value={formName}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormName(e.target.value)}
                  placeholder="e.g. Safety Protection Bundle"
                  className="mt-1 w-full"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" size="sm" onClick={() => setDialog(null)}>
                  Cancel
                </Button>
                <Button size="sm" onClick={createBundle} disabled={saving}>
                  {saving ? "Creating..." : "Create Bundle"}
                </Button>
              </div>
            </div>
          </div>
        </Dialog>
      )}

      {/* ── Dialog: AI Seed & Sync Spec Modal ───────────────────────── */}
      {showAiModal && (
        <Dialog
          open={showAiModal}
          onOpenChange={setShowAiModal}
          title={`AI Seed & Sync Specification — ${matrixData?.company.name || "Insurer"}`}
        >
          <div className="max-w-4xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setAiModalTab("spec")}
                  className={`rounded-[var(--rl-radius-sm)] px-3 py-1.5 text-xs font-semibold transition-all ${
                    aiModalTab === "spec"
                      ? "bg-[var(--rl-black)] text-white"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  1. AI Seed Spec & Markdown Table
                </button>
                <button
                  type="button"
                  onClick={() => setAiModalTab("diff")}
                  className={`rounded-[var(--rl-radius-sm)] px-3 py-1.5 text-xs font-semibold transition-all ${
                    aiModalTab === "diff"
                      ? "bg-[var(--rl-black)] text-white"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  2. Non-Destructive Diff Tester
                </button>
              </div>

              {aiModalTab === "spec" && (
                <Button
                  size="sm"
                  onClick={copyAiPrompt}
                  icon={copiedPrompt ? <Check size={14} weight="bold" /> : <Copy size={14} weight="bold" />}
                  className="bg-emerald-700 text-white hover:bg-emerald-800"
                >
                  {copiedPrompt ? "Copied Prompt & Table!" : "Copy AI Prompt & Table"}
                </Button>
              )}
            </div>

            {aiModalTab === "spec" ? (
              <div className="space-y-3">
                <div className="rounded-[var(--rl-radius-sm)] border border-blue-200 bg-blue-50/70 p-3 text-xs text-blue-950">
                  <p className="font-semibold">How to use this with an AI agent (Claude, ChatGPT, Gemini):</p>
                  <p className="mt-1 text-[11px] text-blue-900">
                    Click <strong>&quot;Copy AI Prompt & Table&quot;</strong> above, then paste it along with any new insurer brochure or policy schedule into your chat.
                    The AI will understand the exact structure and return only the changes or new benefits needed without re-seeding existing catalog rows!
                  </p>
                </div>

                <div className="relative">
                  <pre className="max-h-[420px] overflow-y-auto rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3.5 font-mono text-[11px] text-[var(--rl-text-strong)] leading-relaxed whitespace-pre-wrap">
                    {aiSyncPrompt}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="rounded-[var(--rl-radius-sm)] border border-emerald-200 bg-emerald-50/70 p-3 text-xs text-emerald-950">
                  <p className="font-semibold">Non-Destructive Delta Sync Inspector:</p>
                  <p className="mt-1 text-[11px] text-emerald-900">
                    Paste the JSON payload returned by an AI or drafted manually to test which benefits will be added or modified in the database.
                  </p>
                </div>

                <div className="grid gap-1.5">
                  <label className="text-xs font-semibold text-[var(--rl-text-strong)]">
                    Incoming Delta JSON:
                  </label>
                  <textarea
                    value={aiDiffInput}
                    onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setAiDiffInput(e.target.value)}
                    placeholder={`{\n  "scenarios": [\n    {\n      "scenario_name": "Private Car Protector",\n      "defaults": [\n        {"concept_key": "new_breakdown_assist", "display_value": "Free Towing 100km"}\n      ],\n      "addons": [\n        {"concept_key": "windscreen", "display_value": "RM 1,200", "price": 180.0}\n      ]\n    }\n  ]\n}`}
                    className="h-44 w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3 font-mono text-xs text-[var(--rl-text-strong)] focus:outline-none"
                  />
                </div>

                <div className="flex justify-end gap-2">
                  <Button
                    size="sm"
                    onClick={runAiDiffCheck}
                    disabled={aiDiffLoading || !aiDiffInput.trim()}
                    icon={<Lightning size={14} weight="fill" />}
                    className="bg-[var(--rl-black)] text-white"
                  >
                    {aiDiffLoading ? "Analyzing Changes..." : "Run Diff Check"}
                  </Button>
                </div>

                {aiDiffResult && (
                  <div className="mt-3 space-y-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3.5 text-xs">
                    {aiDiffResult.error ? (
                      <div className="text-[var(--rl-red)] font-semibold">{aiDiffResult.error}</div>
                    ) : (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2">
                          <span className="font-bold text-[var(--rl-text-strong)]">
                            Diff Analysis Result: {aiDiffResult.total_changes || 0} change(s) detected
                          </span>
                          <Badge variant={aiDiffResult.total_changes > 0 ? "success" : "default"}>
                            {aiDiffResult.total_changes > 0 ? "Incremental Updates Ready" : "Up-to-date"}
                          </Badge>
                        </div>

                        {aiDiffResult.scenarios_diff?.map((sd: any, idx: number) => (
                          <div key={idx} className="rounded border border-[var(--rl-border)] p-2.5 space-y-1.5 bg-[var(--rl-bg)]">
                            <div className="font-bold text-[12px] text-[var(--rl-text-strong)]">
                              Scenario: {sd.scenario_name} ({sd.status})
                            </div>
                            {sd.added_defaults?.length > 0 && (
                              <div className="text-emerald-800 text-[11px]">
                                + Added Defaults: {sd.added_defaults.map((d: any) => d.concept_key).join(", ")}
                              </div>
                            )}
                            {sd.added_addons?.length > 0 && (
                              <div className="text-blue-800 text-[11px]">
                                + Added Add-ons: {sd.added_addons.map((a: any) => `${a.concept_key} (${a.price ? `RM ${a.price}` : a.display_value})`).join(", ")}
                              </div>
                            )}
                            {sd.modified_addons?.length > 0 && (
                              <div className="text-amber-800 text-[11px]">
                                • Modified Add-on Pricing: {sd.modified_addons.map((m: any) => `${m.to.concept_key}: RM ${m.from.price} → RM ${m.to.price}`).join(", ")}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </Dialog>
      )}

      {/* ── Dialog: Add / Edit Benefit Condition Rule ───────────────── */}
      {conditionDialog && (
        <Dialog
          open={conditionDialog}
          onOpenChange={setConditionDialog}
          title="New Dynamic Benefit Condition Rule"
        >
          <div className="max-w-lg p-6 space-y-4 text-xs">
            <p className="text-[var(--rl-text-muted)]">
              Define a dynamic condition for <strong>{selectedCompany?.name}</strong>. When the trigger benefit is active in a quote, the target benefit description automatically upgrades.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
                  Rule Name *
                </label>
                <Input
                  value={condFormName}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCondFormName(e.target.value)}
                  placeholder="e.g. DPP -> Unlimited Towing Upgrade"
                  className="w-full"
                />
              </div>

              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
                  When this Trigger Benefit is Active / Purchased *
                </label>
                <select
                  value={condTriggerId}
                  onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setCondTriggerId(e.target.value)}
                  className="w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-2 text-xs text-[var(--rl-text-strong)] focus:outline-none"
                >
                  <option value="">-- Select Trigger Benefit --</option>
                  {concepts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label} ({c.concept_key})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
                  Trigger Plan Filter (Optional)
                </label>
                <Input
                  value={condPlanFilter}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCondPlanFilter(e.target.value)}
                  placeholder="e.g. Plan B, or leave blank for any plan / purchase"
                  className="w-full"
                />
              </div>

              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
                  Target Benefit to Modify *
                </label>
                <select
                  value={condTargetId}
                  onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setCondTargetId(e.target.value)}
                  className="w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-2 text-xs text-[var(--rl-text-strong)] focus:outline-none"
                >
                  <option value="">-- Select Target Benefit --</option>
                  {concepts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label} ({c.concept_key})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
                  Rule Action Type *
                </label>
                <div className="inline-flex items-center gap-1 p-1 bg-[var(--rl-bg)] border border-[var(--rl-border)] rounded-[4px]">
                  <button
                    type="button"
                    onClick={() => setCondActionType("replace_description")}
                    className={`flex items-center gap-1.5 rounded-[3px] px-3 py-1.5 transition-all text-xs ${
                      condActionType === "replace_description"
                        ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] font-semibold shadow-xs"
                        : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    }`}
                  >
                    <PencilSimple size={13} weight="bold" />
                    Replace Description
                  </button>
                  <button
                    type="button"
                    onClick={() => setCondActionType("hide_target")}
                    className={`flex items-center gap-1.5 rounded-[3px] px-3 py-1.5 transition-all text-xs ${
                      condActionType === "hide_target"
                        ? "bg-amber-100 text-amber-950 font-semibold shadow-xs border border-amber-300 dark:bg-amber-950 dark:text-amber-300"
                        : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    }`}
                  >
                    <EyeSlash size={13} weight="bold" />
                    Hide / Disappear Benefit
                  </button>
                </div>
              </div>

              {condActionType === "replace_description" ? (
                <div>
                  <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
                    Upgraded / Replacement Description *
                  </label>
                  <textarea
                    value={condReplacement}
                    onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setCondReplacement(e.target.value)}
                    placeholder="e.g. Unlimited towing distance within Malaysia"
                    rows={3}
                    className="w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-2.5 text-xs text-[var(--rl-text-strong)] focus:outline-none resize-none font-medium"
                  />
                </div>
              ) : (
                <div className="rounded-[var(--rl-radius-sm)] border border-amber-200 bg-amber-50/80 p-3 text-amber-950 text-xs flex items-start gap-2.5">
                  <Info size={18} className="text-amber-600 shrink-0 mt-0.5" weight="fill" />
                  <div>
                    <strong className="block font-bold mb-0.5">Automatic Target Benefit Suppression</strong>
                    <span>When the trigger benefit is added or active in a quotation, the target benefit will automatically be hidden and disappeared from quotation cards and review tables.</span>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-[var(--rl-border)]">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setConditionDialog(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={saveCompanyCondition}
                disabled={
                  conditionSaving ||
                  !condFormName.trim() ||
                  !condTriggerId ||
                  !condTargetId ||
                  (condActionType === "replace_description" && !condReplacement.trim())
                }
                className="bg-[var(--rl-black)] text-white shadow-sm font-semibold"
              >
                {conditionSaving ? "Saving Rule..." : "Create Condition Rule"}
              </Button>
            </div>
          </div>
        </Dialog>
      )}

      {/* ── Dialog: Clone Benefit Profile ───────────────────────────── */}
      {cloneModalOpen && (
        <Dialog
          open={cloneModalOpen}
          onOpenChange={setCloneModalOpen}
          title="Clone Benefit Profile as New Version"
        >
          <div className="max-w-md p-6 space-y-4 text-xs">
            <p className="text-[var(--rl-text-muted)]">
              Clone <strong>{selectedProfile?.name}</strong> to create a new draft version with all current benefit toggles, descriptions, and conditional rules copied across all insurance companies.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
                  New Profile Name *
                </label>
                <Input
                  value={cloneName}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCloneName(e.target.value)}
                  placeholder="e.g. Main Baseline (v2)"
                  className="w-full"
                />
              </div>

              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
                  Notes (Optional)
                </label>
                <textarea
                  value={cloneNotes}
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setCloneNotes(e.target.value)}
                  placeholder="e.g. Endorsements updated for Q4 2026 revisions"
                  rows={3}
                  className="w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-2.5 text-xs text-[var(--rl-text-strong)] focus:outline-none resize-none font-medium"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-[var(--rl-border)]">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCloneModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleCloneProfile}
                disabled={profileActionLoading || !cloneName.trim()}
                className="bg-[var(--rl-black)] text-white shadow-sm font-semibold"
              >
                {profileActionLoading ? "Cloning..." : "Create Cloned Draft"}
              </Button>
            </div>
          </div>
        </Dialog>
      )}
    </>
  );
}
