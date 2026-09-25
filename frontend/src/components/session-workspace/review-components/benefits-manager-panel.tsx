"use client";

import React from "react";
import {
  ArrowArcLeft,
  ArrowArcRight,
  ArrowCounterClockwise,
  CaretDown,
  CaretUp,
  Check,
  CheckCircle,
  Lightning,
  Package as PackageIcon,
  Plus,
  Sparkle,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { BenefitCardSummary, WorkspaceSnapshot } from "../types";
import { AddonCard, IncludedCard } from "./benefit-cards";

export interface BenefitsManagerPanelProps {
  companyName?: string | null;
  benefitsCollapsed: boolean;
  setBenefitsCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  benefitsViewMode: "defaults" | "addons" | "both";
  setBenefitsViewMode: (mode: "defaults" | "addons" | "both") => void;
  currentCards: BenefitCardSummary[];
  addonCards: BenefitCardSummary[];
  focCards: BenefitCardSummary[];
  purchasedAddonCards: BenefitCardSummary[];
  handleReset: () => void;
  handleUndo: () => void;
  handleRedo: () => void;
  undoStack: unknown[];
  redoStack: unknown[];
  setModalTarget: (target: "current" | "available_addon") => void;
  setShowGlobalModal: (show: boolean) => void;
  workspace: WorkspaceSnapshot;
  globalConcepts: any[];
  conceptAssets: Record<string, string>;
  onQueue: (operation: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) => void;
  packPlanSelections: Record<string, string>;
  setPackPlanSelections: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  removePack: (planId: string) => void;
  addPack: (pack: any, planId: string) => void;
  customLabel: string;
  setCustomLabel: (v: string) => void;
  customValue: string;
  setCustomValue: (v: string) => void;
  customPrice: string;
  setCustomPrice: (v: string) => void;
  addCustomBenefit: (target: "current" | "available_addon") => void;
}

export function BenefitsManagerPanel({
  companyName,
  benefitsCollapsed,
  setBenefitsCollapsed,
  benefitsViewMode,
  setBenefitsViewMode,
  currentCards,
  addonCards,
  focCards,
  purchasedAddonCards,
  handleReset,
  handleUndo,
  handleRedo,
  undoStack,
  redoStack,
  setModalTarget,
  setShowGlobalModal,
  workspace,
  globalConcepts,
  conceptAssets,
  onQueue,
  packPlanSelections,
  setPackPlanSelections,
  removePack,
  addPack,
  customLabel,
  setCustomLabel,
  customValue,
  setCustomValue,
  customPrice,
  setCustomPrice,
  addCustomBenefit,
}: BenefitsManagerPanelProps) {
  return (
    <div className="rl-tour-benefits grid gap-4 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-card transition-all">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-[var(--rl-text-strong)]">
            {companyName ? `${companyName} Benefits & Add-ons` : "Benefits & Add-ons"}
          </h2>
          <p className="text-xs text-[var(--rl-text-muted)]">
            Manage policy defaults and payable add-ons with automatic canvas and PDF slot alignment.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {!benefitsCollapsed ? (
            <div className="flex items-center gap-1 rounded-md border border-[var(--rl-border)] bg-gray-100 p-1">
              <button
                type="button"
                onClick={() => setBenefitsViewMode("defaults")}
                className={`flex items-center gap-1.5 rounded px-3 py-1 text-xs font-semibold transition-all ${
                  benefitsViewMode === "defaults"
                    ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-100 text-[10px] font-bold text-emerald-800">
                  {currentCards.length}
                </span>
                Default / FOC Benefits
              </button>

              <button
                type="button"
                onClick={() => setBenefitsViewMode("addons")}
                className={`flex items-center gap-1.5 rounded px-3 py-1 text-xs font-semibold transition-all ${
                  benefitsViewMode === "addons"
                    ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-blue-100 text-[10px] font-bold text-blue-800">
                  {addonCards.length}
                </span>
                Optional Add-ons
              </button>

              <button
                type="button"
                onClick={() => setBenefitsViewMode("both")}
                className={`flex items-center gap-1.5 rounded px-3 py-1 text-xs font-semibold transition-all ${
                  benefitsViewMode === "both"
                    ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                Side by Side
              </button>
            </div>
          ) : null}

          <button
            type="button"
            onClick={() => setBenefitsCollapsed((v) => !v)}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors"
            title={benefitsCollapsed ? "Expand Benefits & Add-ons" : "Collapse Benefits & Add-ons"}
          >
            {benefitsCollapsed ? <CaretDown size={14} weight="bold" /> : <CaretUp size={14} weight="bold" />}
            <span>{benefitsCollapsed ? "Expand" : "Collapse"}</span>
          </button>
        </div>
      </div>

      {benefitsCollapsed ? (
        <div className="flex flex-wrap items-center justify-between text-xs text-[var(--rl-text-muted)] pt-2 border-t border-[var(--rl-border)]">
          <span>
            Included / FOC: <strong className="text-emerald-700 font-semibold">{focCards.length} active</strong>
          </span>
          {purchasedAddonCards.length > 0 ? (
            <span>
              Purchased Add-ons:{" "}
              <strong className="text-amber-700 font-semibold">{purchasedAddonCards.length} active</strong>
            </span>
          ) : null}
          <span>
            Optional Add-ons: <strong className="text-blue-700 font-semibold">{addonCards.length} configured</strong>
          </span>
        </div>
      ) : (
        <>
          {/* Global Actions Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                icon={<ArrowCounterClockwise size={14} weight="bold" className="text-amber-600" />}
                onClick={handleReset}
                title="Reset to initial insurance defaults and detections"
              >
                Reset
              </Button>
              <Button
                size="sm"
                variant="secondary"
                icon={<ArrowArcLeft size={14} weight="bold" />}
                onClick={handleUndo}
                disabled={undoStack.length === 0}
                title="Undo recent benefit change"
              >
                Undo
              </Button>
              <Button
                size="sm"
                variant="secondary"
                icon={<ArrowArcRight size={14} weight="bold" />}
                onClick={handleRedo}
                disabled={redoStack.length === 0}
                title="Redo benefit change"
              >
                Redo
              </Button>
              <span className="text-xs text-[var(--rl-text-muted)]">
                {focCards.length} standard covers{purchasedAddonCards.length > 0 ? ` + ${purchasedAddonCards.length} purchased add-ons` : ""}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                icon={<Sparkle size={14} weight="bold" className="text-[var(--rl-red)]" />}
                onClick={() => {
                  setModalTarget("available_addon");
                  setShowGlobalModal(true);
                }}
              >
                + Global Library
              </Button>
            </div>
          </div>

          {/* Multi-Box Interactive Grid Display */}
          <div
            className={`grid gap-4 ${
              benefitsViewMode === "both"
                ? purchasedAddonCards.length > 0
                  ? "lg:grid-cols-3"
                  : "lg:grid-cols-2"
                : "grid-cols-1"
            }`}
          >
            {/* BOX 1: Default / FOC Included Benefits */}
            {(benefitsViewMode === "defaults" || benefitsViewMode === "both") && (
              <div className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-gray-50/60 p-3 flex flex-col gap-2.5">
                <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2">
                  <div className="flex items-center gap-1.5">
                    <CheckCircle size={16} weight="fill" className="text-emerald-600" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                      Included / FOC Benefits
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[10px] font-bold text-emerald-800">
                      {focCards.length} standard covers (constant)
                    </span>
                  </div>
                </div>

                <div className="grid gap-2 max-h-[380px] overflow-y-auto pr-1">
                  {focCards.length === 0 ? (
                    <div className="flex flex-col items-center justify-center p-6 text-center text-xs text-[var(--rl-text-muted)]">
                      <p>No included benefits active.</p>
                      <Button size="sm" variant="secondary" onClick={handleReset} className="mt-2 text-xs">
                        Reset to insurance defaults
                      </Button>
                    </div>
                  ) : (
                    focCards.map((card, idx) => {
                      const selection = workspace.benefits.find(
                        (item) =>
                          item.catalog_offering_id === card.offering_id || item.selection_key === card.card_key
                      );
                      const concept = globalConcepts.find(
                        (c) =>
                          c.concept_key === card.concept_key ||
                          c.id === card.concept_id ||
                          c.label.toLowerCase() === card.label.toLowerCase()
                      );
                      const assetUrl =
                        concept?.default_asset?.url ||
                        (concept?.default_asset_id
                          ? `/business/assets/${concept.default_asset_id}/content?profile=ui`
                          : null) ||
                        (card.asset_id ? `/business/assets/${card.asset_id}/content?profile=ui` : null) ||
                        (card.label
                          ? conceptAssets[card.label.toLowerCase()] ||
                            conceptAssets[card.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")]
                          : null);
                      return (
                        <IncludedCard
                          key={card.offering_id || card.card_key || idx}
                          card={card}
                          index={idx}
                          assetUrl={assetUrl}
                          selection={selection}
                          canUndo={Boolean(card.branch_key)}
                          onQueue={onQueue}
                        />
                      );
                    })
                  )}
                </div>
              </div>
            )}

            {/* BOX 1.5: Purchased Add-ons (Active on Quote) */}
            {(benefitsViewMode === "defaults" || benefitsViewMode === "both" || benefitsViewMode === "addons") &&
              purchasedAddonCards.length > 0 && (
                <div className="rounded-[var(--rl-radius-sm)] border border-amber-200 bg-amber-50/40 p-3 flex flex-col gap-2.5">
                  <div className="flex items-center justify-between border-b border-amber-200/80 pb-2">
                    <div className="flex items-center gap-1.5">
                      <Sparkle size={16} weight="fill" className="text-amber-600" />
                      <h3 className="text-xs font-bold uppercase tracking-wider text-amber-900">
                        Purchased Add-ons
                      </h3>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-amber-100 border border-amber-300 px-2 py-0.5 text-[10px] font-bold text-amber-800">
                        {purchasedAddonCards.length} on quotation
                      </span>
                    </div>
                  </div>

                  <div className="grid gap-2 max-h-[380px] overflow-y-auto pr-1">
                    {purchasedAddonCards.map((card, idx) => {
                      const selection = workspace.benefits.find(
                        (item) =>
                          item.catalog_offering_id === card.offering_id || item.selection_key === card.card_key
                      );
                      const concept = globalConcepts.find(
                        (c) =>
                          c.concept_key === card.concept_key ||
                          c.id === card.concept_id ||
                          c.label.toLowerCase() === card.label.toLowerCase()
                      );
                      const assetUrl =
                        concept?.default_asset?.url ||
                        (concept?.default_asset_id
                          ? `/business/assets/${concept.default_asset_id}/content?profile=ui`
                          : null) ||
                        (card.asset_id ? `/business/assets/${card.asset_id}/content?profile=ui` : null) ||
                        (card.label
                          ? conceptAssets[card.label.toLowerCase()] ||
                            conceptAssets[card.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")]
                          : null);
                      return (
                        <IncludedCard
                          key={card.offering_id || card.card_key || idx}
                          card={card}
                          index={idx}
                          assetUrl={assetUrl}
                          selection={selection}
                          canUndo={Boolean(card.branch_key)}
                          onQueue={onQueue}
                        />
                      );
                    })}
                  </div>
                </div>
              )}

            {/* BOX 2: Optional Payable Add-ons */}
            {(benefitsViewMode === "addons" || benefitsViewMode === "both") && (
              <div className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-gray-50/60 p-3 flex flex-col gap-2.5">
                <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2">
                  <div className="flex items-center gap-1.5">
                    <Lightning size={16} weight="fill" className="text-blue-600" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                      Optional Add-on Covers
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-800">
                      {addonCards.length} available
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setModalTarget("available_addon");
                        setShowGlobalModal(true);
                      }}
                      className="rounded p-1 text-blue-700 hover:bg-blue-100"
                      title="Add from Global Library to Add-ons"
                    >
                      <Plus size={14} weight="bold" />
                    </button>
                  </div>
                </div>

                {workspace.packs.length > 0 ? (
                  <div className="grid gap-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <PackageIcon size={16} weight="fill" className="text-[var(--rl-red)]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                          Add-on Bundle Packages
                        </h4>
                      </div>
                      <span className="text-[10px] font-bold text-[var(--rl-red)] bg-red-50 border border-red-200 px-2 py-0.5 rounded-full">
                        Stack Cards ({workspace.packs.length} bundles)
                      </span>
                    </div>
                    <p className="text-[11px] text-[var(--rl-text-muted)] -mt-1.5">
                      Pre-bundled multi-benefit packs. Choose a plan tier to see included benefits and add to quotation.
                    </p>
                    {workspace.packs.map((pack) => {
                      const activeGroup = workspace.benefit_cards.groups?.find((g) =>
                        pack.plans.some((p) => p.plan_id === g.plan_id)
                      );
                      const selectedPlanId = packPlanSelections[pack.package_id] || pack.plans[0]?.plan_id || "";
                      const selectedPlan = pack.plans.find((p) => p.plan_id === selectedPlanId) || pack.plans[0];
                      return (
                        <div
                          key={pack.package_id}
                          className="relative rounded-[var(--rl-radius-sm)] border-2 border-red-200/80 bg-white p-3.5 shadow-sm transition-all hover:border-[var(--rl-red)]/60"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2">
                            <div className="flex items-center gap-2">
                              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--rl-red-light)] text-[var(--rl-red)]">
                                <PackageIcon size={16} weight="bold" />
                              </div>
                              <div>
                                <div className="flex items-center gap-1.5">
                                  <h5 className="text-xs font-bold text-[var(--rl-text-strong)]">{pack.name}</h5>
                                  <span className="rounded bg-gray-100 px-1.5 py-0.2 text-[9px] font-bold text-gray-600 uppercase">
                                    Bundle Stack
                                  </span>
                                </div>
                                {activeGroup ? (
                                  <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700">
                                    <Check size={11} weight="bold" /> Active on Quote ({activeGroup.plan_label})
                                  </span>
                                ) : null}
                              </div>
                            </div>

                            {activeGroup ? (
                              <button
                                type="button"
                                onClick={() => removePack(activeGroup.plan_id)}
                                className="rounded border border-red-200 bg-red-50 px-2.5 py-1 text-[11px] font-bold text-[var(--rl-red)] hover:bg-red-100 transition-colors"
                              >
                                Remove Bundle
                              </button>
                            ) : null}
                          </div>

                          {/* Plan Tier Selector Pills */}
                          <div className="mt-2.5">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                              Select Plan Tier:
                            </span>
                            <div className="mt-1 flex flex-wrap gap-1.5">
                              {pack.plans.map((plan) => {
                                const isSelected = plan.plan_id === selectedPlanId;
                                return (
                                  <button
                                    key={plan.plan_id}
                                    type="button"
                                    onClick={() =>
                                      setPackPlanSelections((prev) => ({ ...prev, [pack.package_id]: plan.plan_id }))
                                    }
                                    className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold transition-all ${
                                      isSelected
                                        ? "bg-[var(--rl-red)] text-white shadow-xs"
                                        : "bg-gray-100 text-[var(--rl-text-strong)] hover:bg-gray-200"
                                    }`}
                                  >
                                    <span>{plan.name}</span>
                                  </button>
                                );
                              })}
                            </div>
                          </div>

                          {/* Included Member Benefit Boxes Preview */}
                          {selectedPlan ? (
                            <div className="mt-3 rounded-lg border border-gray-100 bg-neutral-50/70 p-2.5">
                              <div className="flex items-center justify-between mb-1.5">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                                  Includes {selectedPlan.members.length} benefits in this tier:
                                </span>
                              </div>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                                {selectedPlan.members.map((m, mIdx) => (
                                  <div
                                    key={m.offering_id || mIdx}
                                    className="flex items-center justify-between gap-1.5 rounded bg-white p-1.5 border border-gray-200/70 text-xs shadow-2xs"
                                  >
                                    <div className="flex items-center gap-1.5 min-w-0">
                                      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-[9px] font-bold text-emerald-800">
                                        ✓
                                      </span>
                                      <span className="truncate font-semibold text-[11px] text-[var(--rl-text-strong)]">
                                        {m.label}
                                      </span>
                                    </div>
                                    {m.typed_value_override && typeof m.typed_value_override.display_text === "string" ? (
                                      <span className="shrink-0 text-[10px] font-mono font-bold text-gray-500">
                                        {String(m.typed_value_override.display_text)}
                                      </span>
                                    ) : null}
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}

                          <div className="mt-3 flex items-center justify-end">
                            <Button
                              size="sm"
                              onClick={() => addPack(pack, selectedPlanId)}
                              disabled={!selectedPlanId}
                              className="text-xs font-bold h-8 px-4 bg-[var(--rl-red)] hover:bg-red-700 text-white shadow-xs"
                            >
                              {activeGroup
                                ? `Switch to ${selectedPlan?.name || "Tier"}`
                                : `Apply ${selectedPlan?.name || "Bundle"} →`}
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : null}

                <div className="grid gap-2 max-h-[380px] overflow-y-auto pr-1">
                  {addonCards.length === 0 ? (
                    <div className="flex flex-col items-center justify-center p-6 text-center text-xs text-[var(--rl-text-muted)]">
                      <p>No optional add-ons configured for this quotation.</p>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          setModalTarget("available_addon");
                          setShowGlobalModal(true);
                        }}
                        className="mt-2 text-xs"
                      >
                        Browse Global Add-ons
                      </Button>
                    </div>
                  ) : (
                    addonCards.map((card, idx) => {
                      const concept = globalConcepts.find(
                        (c) =>
                          c.concept_key === card.concept_key ||
                          c.id === card.concept_id ||
                          c.label.toLowerCase() === card.label.toLowerCase()
                      );
                      const assetUrl =
                        concept?.default_asset?.url ||
                        (concept?.default_asset_id
                          ? `/business/assets/${concept.default_asset_id}/content?profile=ui`
                          : null) ||
                        (card.asset_id ? `/business/assets/${card.asset_id}/content?profile=ui` : null) ||
                        (card.label
                          ? conceptAssets[card.label.toLowerCase()] ||
                            conceptAssets[card.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")]
                          : null);
                      return (
                        <AddonCard
                          key={card.offering_id || card.card_key || idx}
                          card={card}
                          index={idx}
                          assetUrl={assetUrl}
                          onQueue={onQueue}
                        />
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Quick Custom Benefit Adder Row */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[var(--rl-border)]">
            <div className="flex-1 min-w-[200px]">
              <Input
                value={customLabel}
                placeholder="Type custom benefit name (e.g. Free 24h Car Wash, Special Battery Cover)..."
                onChange={(e) => setCustomLabel(e.target.value)}
                className="text-xs font-medium"
              />
            </div>
            <div className="w-36">
              <Input
                value={customValue}
                placeholder="Value (e.g. FOC, RM 500)"
                onChange={(e) => setCustomValue(e.target.value)}
                className="text-xs font-medium"
              />
            </div>
            <div className="w-28">
              <Input
                value={customPrice}
                placeholder="Price RM (add-ons)"
                onChange={(e) => setCustomPrice(e.target.value)}
                className="text-xs font-medium"
                title="Optional price shown in the Extras section and added to the total premium"
              />
            </div>
            <Button
              size="sm"
              onClick={() => addCustomBenefit("current")}
              disabled={!customLabel.trim()}
              className="text-xs"
            >
              + Add to Default / FOC
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => addCustomBenefit("available_addon")}
              disabled={!customLabel.trim()}
              className="text-xs"
            >
              + Add to Add-ons
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
