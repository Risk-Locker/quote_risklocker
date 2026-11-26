"use client";

import React, { useState, useMemo } from "react";
import {
  ArrowArcLeft,
  ArrowArcRight,
  ArrowCounterClockwise,
  CaretDown,
  CaretUp,
  Check,
  Columns,
  Lightning,
  MagnifyingGlass,
  Package as PackageIcon,
  Plus,
  Rows,
  ShieldCheck,
  X,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import type { BenefitCardSummary, WorkspaceSnapshot } from "../types";
import { IncludedCard, MatrixAddonCard } from "./benefit-cards";
import { AddCustomBenefitModal } from "./add-custom-benefit-modal";

export interface BenefitsManagerPanelProps {
  companyName?: string | null;
  vehicleType?: string | null;
  onClosePanel?: () => void;
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
  onQueue: (
    operation: Record<string, unknown> & { op: string },
    path: string,
    revertOp?: Record<string, unknown> & { op: string }
  ) => void;
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
  addCustomBenefit: (payload?: any) => void;
  highlightedSelectionId?: string | null;
  onApproveBenefit?: (card: BenefitCardSummary) => void;
}

export function BenefitsManagerPanel({
  companyName,
  vehicleType,
  onClosePanel,
  benefitsCollapsed,
  setBenefitsCollapsed,
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
  addCustomBenefit,
  highlightedSelectionId = null,
  onApproveBenefit,
}: BenefitsManagerPanelProps) {
  const [showAddCustomModal, setShowAddCustomModal] = useState(false);
  const [customModalPlacement, setCustomModalPlacement] = useState<"foc" | "addon">("addon");
  const [layoutMode, setLayoutMode] = useState<"stacked" | "side_by_side">("stacked");
  const [searchQuery, setSearchQuery] = useState("");

  const q = searchQuery.trim().toLowerCase();
  const filterCard = (c: BenefitCardSummary) => {
    if (!q) return true;
    return (
      (c.label || "").toLowerCase().includes(q) ||
      (c.description || "").toLowerCase().includes(q) ||
      (c.value || "").toLowerCase().includes(q) ||
      (c.concept_key || "").toLowerCase().includes(q)
    );
  };

  const filteredFocCards = useMemo(() => focCards.filter(filterCard), [focCards, q]);
  const filteredPurchasedAddons = useMemo(() => purchasedAddonCards.filter(filterCard), [purchasedAddonCards, q]);
  const filteredAddonCards = useMemo(() => addonCards.filter(filterCard), [addonCards, q]);

  const resolveAssetUrl = (card: BenefitCardSummary) => {
    const concept = globalConcepts.find(
      (c) =>
        c.concept_key === card.concept_key ||
        c.id === card.concept_id ||
        c.label.toLowerCase() === card.label.toLowerCase()
    );
    return (
      concept?.default_asset?.url ||
      (concept?.default_asset_id
        ? `/business/assets/${concept.default_asset_id}/content?profile=ui`
        : null) ||
      (card.asset_id ? `/business/assets/${card.asset_id}/content?profile=ui` : null) ||
      (card.label
        ? conceptAssets[card.label.toLowerCase()] ||
          conceptAssets[card.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")]
        : null)
    );
  };

  const handleToggleSelect = (card: BenefitCardSummary, willSelect: boolean) => {
    const selection = workspace.benefits.find(
      (item) => item.catalog_offering_id === card.offering_id || item.selection_key === card.card_key
    );
    const selectionId =
      selection && typeof selection === "object" && "id" in selection
        ? String(selection.id)
        : card.selection_id || null;
    const pending = !selectionId || String(selectionId).startsWith("pending:");
    const defaultPrice = card.price || (card as any).optional_price || null;

    if (willSelect) {
      if (selectionId && !pending) {
        onQueue(
          { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: "paid", is_extra: true, ...(defaultPrice ? { price: defaultPrice } : {}) },
          `benefits.${selectionId}.state`
        );
      } else if (card.offering_id && !String(card.offering_id).startsWith("custom:") && !String(card.offering_id).startsWith("pending:")) {
        onQueue(
          { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: "paid", is_extra: true, ...(defaultPrice ? { price: defaultPrice } : {}) },
          `benefits.offer.${card.offering_id}`
        );
      } else if (selectionId || card.concept_key) {
        const targetId = selectionId || card.concept_key!;
        onQueue(
          { op: "benefit_update", selection_id: targetId, state: "current", cost_status: "paid", is_extra: true, ...(defaultPrice ? { price: defaultPrice } : {}) },
          `benefits.${targetId}.state`
        );
      }
    } else {
      if (selectionId && !pending) {
        onQueue(
          { op: "benefit_update", selection_id: selectionId, state: "available_addon", cost_status: "paid", is_extra: false },
          `benefits.${selectionId}.state`
        );
      } else if (card.offering_id && !String(card.offering_id).startsWith("custom:") && !String(card.offering_id).startsWith("pending:")) {
        onQueue(
          { op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "paid", is_extra: false },
          `benefits.offer.${card.offering_id}`
        );
      } else if (selectionId || card.concept_key) {
        const targetId = selectionId || card.concept_key!;
        onQueue(
          { op: "benefit_update", selection_id: targetId, state: "available_addon", cost_status: "paid", is_extra: false },
          `benefits.${targetId}.state`
        );
      }
    }
  };

  const handleAddCustomSubmit = (data: {
    label: string;
    value: string;
    price: number | null;
    description: string;
    icon_hint: string;
    isSelected: boolean;
    cost_status?: "included" | "paid";
    placement?: "foc" | "addon";
  }) => {
    addCustomBenefit(data);
  };

  return (
    <div className="rl-tour-benefits grid gap-2 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-2 shadow-card transition-all">
      {/* Top Header & Global Controls */}
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <div className="min-w-0">
          <h2 className="text-xs font-bold text-[var(--rl-text-strong)] whitespace-nowrap">
            {companyName ? `${companyName} Benefits & Add-ons` : "Benefits & Add-ons"}
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-1">
          {/* Layout Mode Selector (Stacked vs Side-by-Side) */}
          <div className="hidden 2xl:flex items-center rounded-md border border-[var(--rl-border)] bg-gray-100 p-0.5 text-[11px] font-semibold">
            <button
              type="button"
              onClick={() => setLayoutMode("stacked")}
              className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors cursor-pointer ${
                layoutMode === "stacked"
                  ? "bg-white text-[var(--rl-text-strong)] shadow-2xs font-bold"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
              title="Stacked View: Box 1 on top, Box 2 below"
            >
              <Rows size={12} weight="bold" />
              <span>Stacked</span>
            </button>
            <button
              type="button"
              onClick={() => setLayoutMode("side_by_side")}
              className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors cursor-pointer ${
                layoutMode === "side_by_side"
                  ? "bg-white text-[var(--rl-text-strong)] shadow-2xs font-bold"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
              title="Side-by-Side View: Box 1 and Box 2 in 2 columns"
            >
              <Columns size={12} weight="bold" />
              <span>Side-by-Side</span>
            </button>
          </div>

          {/* Unified Add Buttons (Single Symbol Each) */}
          <Button
            size="sm"
            variant="primary"
            icon={<Plus size={13} weight="bold" />}
            onClick={() => {
              setCustomModalPlacement("addon");
              setShowAddCustomModal(true);
            }}
            className="!h-7 !min-h-[26px] !px-2 !text-[11px] font-bold bg-[var(--rl-red)] hover:bg-red-700 border-[var(--rl-red)] text-white shadow-xs"
            title="Add a custom benefit or add-on"
          >
            Add Custom Benefit
          </Button>
          <Button
            size="sm"
            variant="secondary"
            icon={<Plus size={13} weight="bold" />}
            onClick={() => {
              setModalTarget("available_addon");
              setShowGlobalModal(true);
            }}
            className="!h-7 !min-h-[26px] !px-2 !text-[11px]"
            title="Browse global library of benefits and add-ons"
          >
            Global Library
          </Button>

          <Button
            size="sm"
            variant="secondary"
            icon={<ArrowCounterClockwise size={12} weight="bold" className="text-amber-600" />}
            onClick={handleReset}
            className="!h-7 !min-h-[26px] !px-2 !text-[11px]"
            title="Reset to initial insurance defaults and detections"
          >
            Reset
          </Button>
          <Button
            size="sm"
            variant="secondary"
            icon={<ArrowArcLeft size={12} weight="bold" />}
            onClick={handleUndo}
            disabled={undoStack.length === 0}
            className="!h-7 !min-h-[26px] !px-2 !text-[11px]"
            title="Undo recent benefit change"
          >
            Undo
          </Button>
          <Button
            size="sm"
            variant="secondary"
            icon={<ArrowArcRight size={12} weight="bold" />}
            onClick={handleRedo}
            disabled={redoStack.length === 0}
            className="!h-7 !min-h-[26px] !px-2 !text-[11px]"
            title="Redo benefit change"
          >
            Redo
          </Button>
          <button
            type="button"
            onClick={() => setBenefitsCollapsed((v) => !v)}
            className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
            title={benefitsCollapsed ? "Expand Benefits & Add-ons" : "Collapse Benefits & Add-ons"}
          >
            {benefitsCollapsed ? <CaretDown size={12} weight="bold" /> : <CaretUp size={12} weight="bold" />}
            <span>{benefitsCollapsed ? "Expand" : "Collapse"}</span>
          </button>
          {onClosePanel ? (
            <button
              type="button"
              onClick={onClosePanel}
              className="hidden lg:flex items-center justify-center p-1 text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded border border-transparent hover:border-gray-200 transition-all cursor-pointer"
              title="Close Benefit Edit Panel"
              aria-label="Close Benefit Edit Panel"
            >
              <X size={13} weight="bold" />
            </button>
          ) : null}
        </div>
      </div>

      {/* Search and Quick Filters */}
      <div className="relative flex items-center">
        <MagnifyingGlass size={14} className="absolute left-2.5 text-[var(--rl-text-muted)] pointer-events-none" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search benefits by name, description, or limit..."
          className="h-7 w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white pl-8 pr-20 text-[11px] text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)] focus:border-[var(--rl-red)] focus:ring-1 focus:ring-[var(--rl-red)] focus:outline-none transition-all shadow-2xs"
        />
        {searchQuery ? (
          <button
            type="button"
            onClick={() => setSearchQuery("")}
            className="absolute right-2 flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] cursor-pointer"
          >
            Clear
            <X size={12} weight="bold" />
          </button>
        ) : null}
      </div>

      {benefitsCollapsed ? (
        <div className="flex flex-wrap items-center justify-between text-xs text-[var(--rl-text-muted)] pt-2 border-t border-[var(--rl-border)]">
          <span>
            Box 1 (FOC Inclusions): <strong className="text-emerald-700 font-semibold">{focCards.length} active</strong>
          </span>
          <span>
            Box 2 (Matrix Add-ons):{" "}
            <strong className="text-amber-700 font-semibold">{purchasedAddonCards.length} ticked</strong> /{" "}
            <strong className="text-blue-700 font-semibold">{addonCards.length} optional</strong>
          </span>
        </div>
      ) : (
        <div className={layoutMode === "side_by_side" ? "grid grid-cols-1 2xl:grid-cols-2 gap-3.5 items-start" : "grid gap-3.5"}>
          {/* ========================================================================= */}
          {/* BOX 1: Default / FOC Benefits (Maps to Top-Right Card in Design 2)        */}
          {/* ========================================================================= */}
          <section className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-gray-50/70 p-3 flex flex-col gap-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-2">
              <div className="flex items-center gap-2 min-w-0">
                <div className="flex size-6 items-center justify-center rounded-md bg-emerald-100 text-emerald-800 shrink-0">
                  <ShieldCheck size={15} weight="fill" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                    Box 1: Free Added Coverage
                  </h3>
                  <p className="text-[11px] text-[var(--rl-text-muted)]">
                    Top-Right card on Design 2. Complimentary inclusions.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="rounded-md bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[11px] font-bold text-emerald-800 font-mono">
                  {filteredFocCards.length}{q ? ` / ${focCards.length}` : ""} active
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setCustomModalPlacement("foc");
                    setShowAddCustomModal(true);
                  }}
                  className="inline-flex items-center gap-1 rounded-md border border-emerald-300 bg-white hover:bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-800 transition-colors cursor-pointer shadow-2xs"
                  title="Add a custom complimentary benefit to Box 1"
                >
                  <Plus size={12} weight="bold" />
                  <span>Add</span>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-2.5">
              {filteredFocCards.length === 0 ? (
                <div className="col-span-full flex flex-col items-center justify-center p-5 text-center text-xs text-[var(--rl-text-muted)]">
                  {searchQuery ? (
                    <p>No free inclusions match &ldquo;{searchQuery}&rdquo;.</p>
                  ) : (
                    <>
                      <p>No included benefits active.</p>
                      <Button size="sm" variant="secondary" onClick={handleReset} className="mt-2 text-xs">
                        Reset to insurance defaults
                      </Button>
                    </>
                  )}
                </div>
              ) : (
                filteredFocCards.map((card, idx) => {
                  const selection = workspace.benefits.find(
                    (item) => item.catalog_offering_id === card.offering_id || item.selection_key === card.card_key
                  );
                  const assetUrl = resolveAssetUrl(card);
                  const cardSelId = (selection && "id" in selection ? String(selection.id) : card.selection_id) || card.card_key;
                  return (
                    <IncludedCard
                      key={card.offering_id || card.card_key || idx}
                      card={card}
                      index={idx}
                      assetUrl={assetUrl}
                      selection={selection}
                      canUndo={Boolean(card.branch_key)}
                      onQueue={onQueue}
                      hideColumnButtons={false}
                      companyName={companyName}
                      isHighlighted={Boolean(highlightedSelectionId && (highlightedSelectionId === cardSelId || highlightedSelectionId === card.card_key))}
                      onApproveBenefit={onApproveBenefit}
                    />
                  );
                })
              )}
            </div>
          </section>

          {/* ========================================================================= */}
          {/* BOX 2: Add-On Upgrades & Extra Benefits (Maps to Bottom Matrix in Design 2) */}
          {/* ========================================================================= */}
          <section className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-gray-50/70 p-3 flex flex-col gap-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-2">
              <div className="flex items-center gap-2 min-w-0">
                <div className="flex size-6 items-center justify-center rounded-md bg-amber-100 text-amber-800 shrink-0">
                  <Lightning size={15} weight="fill" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                    Box 2: Add-On Upgrades
                  </h3>
                  <p className="text-[11px] text-[var(--rl-text-muted)]">
                    Tick to select add-on. Selected items float to Slot #01.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="rounded-md bg-emerald-50 border border-emerald-300 px-2 py-0.5 text-[11px] font-bold text-emerald-800 font-mono">
                  ✔ {filteredPurchasedAddons.length}{q ? ` / ${purchasedAddonCards.length}` : ""} Ticked
                </span>
                <span className="rounded-md bg-blue-50 border border-blue-200 px-2 py-0.5 text-[11px] font-bold text-blue-800 font-mono">
                  {filteredAddonCards.length}{q ? ` / ${addonCards.length}` : ""} Optional
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setCustomModalPlacement("addon");
                    setShowAddCustomModal(true);
                  }}
                  className="inline-flex items-center gap-1 rounded-md border border-amber-300 bg-white hover:bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-900 transition-colors cursor-pointer shadow-2xs"
                  title="Add a custom add-on to Box 2"
                >
                  <Plus size={12} weight="bold" />
                  <span>Add</span>
                </button>
              </div>
            </div>

            {/* Package Bundle Stack (if available) */}
            {workspace.packs && workspace.packs.length > 0 && (
              <div className="grid gap-2 rounded-lg border border-red-200/90 bg-red-50/30 p-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <PackageIcon size={15} weight="fill" className="text-[var(--rl-red)]" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                      Add-on Bundle Packages ({workspace.packs.length})
                    </h4>
                  </div>
                  <span className="text-[10px] font-bold text-[var(--rl-red)] bg-red-100 border border-red-200 px-1.5 py-0.5 rounded">
                    Bundle Tier
                  </span>
                </div>
                {workspace.packs.map((pack) => {
                  const activeGroup = workspace.benefit_cards.groups?.find((g) =>
                    pack.plans.some((p) => p.plan_id === g.plan_id)
                  );
                  const selectedPlanId = packPlanSelections[pack.package_id] || pack.plans[0]?.plan_id || "";
                  const selectedPlan = pack.plans.find((p) => p.plan_id === selectedPlanId) || pack.plans[0];
                  return (
                    <div
                      key={pack.package_id}
                      className="rounded-md border border-neutral-200 bg-white p-2.5 shadow-xs flex flex-wrap items-center justify-between gap-2.5"
                    >
                      <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--rl-red-light)] text-[var(--rl-red)]">
                          <PackageIcon size={15} weight="bold" />
                        </div>
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-bold text-[var(--rl-text-strong)]">{pack.name}</span>
                            {activeGroup && (
                              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700">
                                <Check size={11} weight="bold" /> Active ({activeGroup.plan_label})
                              </span>
                            )}
                          </div>
                          {selectedPlan && (
                            <p className="text-[11px] text-[var(--rl-text-muted)]">
                              Includes {selectedPlan.members.length} benefits
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 flex-wrap">
                        <div className="flex flex-wrap items-center p-0.5 rounded-md border border-[var(--rl-border)] bg-gray-100 gap-1">
                          {pack.plans.map((plan) => {
                            const isSelected = plan.plan_id === selectedPlanId;
                            return (
                              <button
                                key={plan.plan_id}
                                type="button"
                                onClick={() =>
                                  setPackPlanSelections((prev) => ({ ...prev, [pack.package_id]: plan.plan_id }))
                                }
                                className={`px-2 py-0.5 text-xs font-semibold rounded cursor-pointer transition-all ${
                                  isSelected
                                    ? "bg-white text-[var(--rl-text-strong)] shadow-xs font-bold"
                                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                                }`}
                              >
                                {plan.name}
                              </button>
                            );
                          })}
                        </div>
                        <Button
                          size="sm"
                          onClick={() => addPack(pack, selectedPlanId)}
                          disabled={!selectedPlanId}
                          className="text-xs font-bold h-7 px-2.5 bg-[var(--rl-red)] hover:bg-red-700 text-white shadow-xs"
                        >
                          {activeGroup ? "Switch Tier" : "Apply Bundle"}
                        </Button>
                        {activeGroup && (
                          <button
                            type="button"
                            onClick={() => removePack(activeGroup.plan_id)}
                            className="rounded border border-red-200 bg-red-50 px-2 py-0.5 text-[11px] font-bold text-[var(--rl-red)] hover:bg-red-100 transition-colors cursor-pointer"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Matrix Addons Grid - Both Selected (Floated to Top) and Optional */}
            <div className="grid grid-cols-1 gap-2.5">
              {filteredPurchasedAddons.length === 0 && filteredAddonCards.length === 0 ? (
                <div className="col-span-full flex flex-col items-center justify-center p-6 text-center text-xs text-[var(--rl-text-muted)]">
                  {searchQuery ? (
                    <p>No add-on covers match &ldquo;{searchQuery}&rdquo;.</p>
                  ) : (
                    <>
                      <p>No add-on covers available for this quotation.</p>
                      <div className="mt-3 flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="primary"
                          icon={<Plus size={14} weight="bold" />}
                          onClick={() => {
                            setCustomModalPlacement("addon");
                            setShowAddCustomModal(true);
                          }}
                          className="text-xs bg-[var(--rl-red)] border-[var(--rl-red)] text-white font-bold"
                        >
                          Add Custom Add-on
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setModalTarget("available_addon");
                            setShowGlobalModal(true);
                          }}
                          className="text-xs"
                        >
                          Global Library
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <>
                  {/* 1. Ticked / Purchased Add-ons (Floated to top, index #01, #02...) */}
                  {filteredPurchasedAddons.map((card, idx) => {
                    const selection = workspace.benefits.find(
                      (item) => item.catalog_offering_id === card.offering_id || item.selection_key === card.card_key
                    );
                    const assetUrl = resolveAssetUrl(card);
                    const cardSelId = (selection && "id" in selection ? String(selection.id) : card.selection_id) || card.card_key;
                    return (
                      <MatrixAddonCard
                        key={card.offering_id || card.card_key || `purchased-${idx}`}
                        card={card}
                        index={idx}
                        assetUrl={assetUrl}
                        selection={selection}
                        isSelected={true}
                        onToggleSelect={(willSelect) => handleToggleSelect(card, willSelect)}
                        onQueue={onQueue}
                        companyName={companyName}
                        isHighlighted={Boolean(highlightedSelectionId && (highlightedSelectionId === cardSelId || highlightedSelectionId === card.card_key))}
                        onApproveBenefit={onApproveBenefit}
                      />
                    );
                  })}

                  {/* 2. Optional Available Add-ons (Unticked, index continues from purchased) */}
                  {filteredAddonCards.map((card, idx) => {
                    const selection = workspace.benefits.find(
                      (item) => item.catalog_offering_id === card.offering_id || item.selection_key === card.card_key
                    );
                    const assetUrl = resolveAssetUrl(card);
                    const effectiveIndex = filteredPurchasedAddons.length + idx;
                    const cardSelId = (selection && "id" in selection ? String(selection.id) : card.selection_id) || card.card_key;
                    return (
                      <MatrixAddonCard
                        key={card.offering_id || card.card_key || `addon-${idx}`}
                        card={card}
                        index={effectiveIndex}
                        assetUrl={assetUrl}
                        selection={selection}
                        isSelected={false}
                        onToggleSelect={(willSelect) => handleToggleSelect(card, willSelect)}
                        onQueue={onQueue}
                        companyName={companyName}
                        isHighlighted={Boolean(highlightedSelectionId && (highlightedSelectionId === cardSelId || highlightedSelectionId === card.card_key))}
                        onApproveBenefit={onApproveBenefit}
                      />
                    );
                  })}
                </>
              )}
            </div>
          </section>
        </div>
      )}

      {/* Add Custom Benefit Modal */}
      <AddCustomBenefitModal
        open={showAddCustomModal}
        initialPlacement={customModalPlacement}
        companyName={companyName}
        vehicleType={vehicleType}
        onClose={() => setShowAddCustomModal(false)}
        onAdd={handleAddCustomSubmit}
      />
    </div>
  );
}
