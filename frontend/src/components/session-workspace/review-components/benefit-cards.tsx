"use client";

import React, { useState, useEffect } from "react";
import { ArrowCounterClockwise, ArrowLeft, ArrowRight, Check, Eye, EyeSlash, Lock, PencilSimple, Plus, Sparkle, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Design2BenefitIconSvg } from "@/components/template-canvas/design2-icons";
import { fileUrl } from "@/lib/api";
import type { BenefitCardSummary } from "../types";

export function IncludedCard({
  card,
  index,
  assetUrl,
  selection,
  canUndo,
  onQueue,
  isPurchasedAddon = false,
  hideColumnButtons = false,
  companyName,
}: {
  card: BenefitCardSummary;
  index: number;
  assetUrl?: string | null;
  selection?: { id: string; cost_status: string } | Record<string, unknown> | null;
  canUndo: boolean;
  onQueue: (operation: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) => void;
  isPurchasedAddon?: boolean;
  hideColumnButtons?: boolean;
  companyName?: string | null;
}) {
  const selectionId = selection && typeof selection === "object" && "id" in selection ? String(selection.id) : (card.selection_id || null);
  const pending = !selectionId || String(selectionId).startsWith("pending:");
  const hasCatalogOffering = Boolean(card.offering_id && !String(card.offering_id).startsWith("custom:") && !String(card.offering_id).startsWith("pending:"));

  const isWindscreen = card.label.toLowerCase().includes("windscreen") || (card.concept_key || "").toLowerCase().includes("windscreen");
  const isBetterment = card.label.toLowerCase().includes("betterment") || (card.concept_key || "").toLowerCase().includes("betterment");
  const insLower = (companyName || "").toLowerCase();
  const isUnder10Insurer = insLower.includes("qbe") || insLower.includes("stmb") || insLower.includes("takaful malaysia") || insLower.includes("lonpac");
  const defaultBetterment = isUnder10Insurer ? "Up to 10 Years" : "Up to 15 Years";

  const embeddedMetricMatch = !card.value
    ? card.label.match(/\(((?:rm|myr)\s*[\d,]+(?:\.\d{1,2})?|\d+\s*km|unlimited[^)]*)\)\s*$/i)
    : null;
  const effectiveRawVal = card.value || (embeddedMetricMatch ? embeddedMetricMatch[1].trim() : "");
  const isExplicitlyCleared = Boolean(
    ((selection as any)?.typed_value_override &&
      "display_text" in ((selection as any)?.typed_value_override || {}) &&
      String((selection as any)?.typed_value_override?.display_text ?? "").trim() === "") ||
    ((card as any).typed_value &&
      "display_text" in ((card as any).typed_value || {}) &&
      String((card as any).typed_value?.display_text ?? "").trim() === "")
  );

  const displayLimitVal = isExplicitlyCleared
    ? ""
    : isBetterment && (/^\s*rm\b/i.test(effectiveRawVal) || !effectiveRawVal)
      ? defaultBetterment
      : effectiveRawVal;
  const isLimitHidden = Boolean(
    (selection as any)?.typed_value_override?.hide_limit ??
    (card as any).typed_value?.hide_limit ??
    (card as any).hide_coverage
  );

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState(card.label);
  const [isEditingLimit, setIsEditingLimit] = useState(false);
  const [limitInput, setLimitInput] = useState(displayLimitVal || "");
  const [isEditingDesc, setIsEditingDesc] = useState(false);
  const [descInput, setDescInput] = useState(card.description || "");
  const [savedField, setSavedField] = useState<string | null>(null);

  useEffect(() => { setTitleInput(card.label); }, [card.label]);
  useEffect(() => { setLimitInput(displayLimitVal || ""); }, [displayLimitVal]);
  useEffect(() => { setDescInput(card.description || ""); }, [card.description]);

  const flashSaved = (field: string) => {
    setSavedField(field);
    setTimeout(() => setSavedField(null), 1400);
  };

  const stripMetricFromLabelIfPresent = (): string | undefined => {
    const stripped = card.label.replace(/\s*\((?:(?:rm|myr)\s*[\d,]+(?:\.\d{1,2})?|\d+\s*km|unlimited[^)]*)\)\s*$/i, "").trim();
    return stripped && stripped !== card.label ? stripped : undefined;
  };

  const handleToggleCoverageVisibility = () => {
    const nextHidden = !isLimitHidden;
    flashSaved("coverage");
    const limitText = displayLimitVal || card.value || "";
    const newTyped = {
      type: limitText ? "custom" : "text",
      display_text: limitText,
      hide_limit: nextHidden,
    };
    const cleanedLabel = nextHidden ? stripMetricFromLabelIfPresent() : undefined;
    if (selectionId && !pending) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, typed_value: newTyped, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.${selectionId}.limit`
      );
    } else if (hasCatalogOffering) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", typed_value: newTyped, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.offer.${card.offering_id}.limit`
      );
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue(
        { op: "benefit_update", selection_id: targetId, typed_value: newTyped, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.${targetId}.limit`
      );
    }
  };

  const handleTitleCommit = (newVal: string) => {
    setIsEditingTitle(false);
    const clean = newVal.trim();
    if (!clean || clean === card.label) return;
    flashSaved("title");
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, label: clean }, `benefits.${selectionId}.label`);
    } else if (hasCatalogOffering) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "current", label: clean }, `benefits.offer.${card.offering_id}.label`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, label: clean }, `benefits.${targetId}.label`);
    }
  };

  const handleLimitCommit = (newVal: string) => {
    setIsEditingLimit(false);
    let clean = newVal.trim();
    if (isBetterment && /^\s*rm\b/i.test(clean)) {
      clean = defaultBetterment;
    }
    flashSaved("limit");
    const typed = clean
      ? { type: "custom", display_text: clean, hide_limit: false }
      : { type: "text", display_text: "", hide_limit: true };
    const cleanedLabel = stripMetricFromLabelIfPresent();
    if (selectionId && !pending) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, typed_value: typed, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.${selectionId}.limit`
      );
    } else if (hasCatalogOffering) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", typed_value: typed, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.offer.${card.offering_id}.limit`
      );
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue(
        { op: "benefit_update", selection_id: targetId, typed_value: typed, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.${targetId}.limit`
      );
    }
  };

  const handleRemoveCoverage = () => {
    setLimitInput("");
    handleLimitCommit("");
  };

  const handleDescCommit = (newVal: string) => {
    setIsEditingDesc(false);
    const clean = newVal.trim();
    flashSaved("desc");
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, description: clean }, `benefits.${selectionId}.description`);
    } else if (hasCatalogOffering) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "current", description: clean }, `benefits.offer.${card.offering_id}`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, description: clean }, `benefits.${targetId}.description`);
    }
  };

  const currentPriceObj = card.price || (card as any).optional_price;
  const currentAmount = currentPriceObj ? (typeof currentPriceObj === "object" ? (currentPriceObj.amount ?? (currentPriceObj as any).value) : currentPriceObj) : null;
  const currentPriceNum = currentAmount !== null && currentAmount !== "" && !isNaN(Number(currentAmount)) ? Number(currentAmount) : null;

  const initialPriceObj = card.initial_price || (card as any).optional_price;
  const initialAmount = initialPriceObj ? (typeof initialPriceObj === "object" ? (initialPriceObj.amount ?? (initialPriceObj as any).value) : initialPriceObj) : null;
  const initialPriceNum = initialAmount !== null && initialAmount !== "" && !isNaN(Number(initialAmount)) ? Number(initialAmount) : null;

  const [isEditingPrice, setIsEditingPrice] = useState(false);
  const [priceInput, setPriceInput] = useState(currentPriceNum !== null ? String(currentPriceNum) : "");

  useEffect(() => {
    setPriceInput(currentPriceNum !== null ? String(currentPriceNum) : "");
  }, [currentPriceNum]);

  const handlePriceCommit = (newValStr: string) => {
    setIsEditingPrice(false);
    const trimmed = newValStr.trim();
    flashSaved("price");
    if (!trimmed) {
      if (selectionId && !pending) {
        onQueue({ op: "benefit_update", selection_id: selectionId, price: null, cost_status: "included" }, `benefits.${selectionId}.price`);
      } else if (hasCatalogOffering) {
        onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: "included", price: null }, `benefits.offer.${card.offering_id}`);
      } else if (selectionId || card.concept_key) {
        const targetId = selectionId || card.concept_key!;
        onQueue({ op: "benefit_update", selection_id: targetId, price: null, cost_status: "included" }, `benefits.${targetId}.price`);
      }
      return;
    }
    const cleanNum = parseFloat(trimmed.replace(/[^0-9.]/g, ""));
    if (isNaN(cleanNum)) return;
    const newPrice = { amount: cleanNum, currency: "MYR" };
    const costStatus = cleanNum > 0 ? "paid" : "included";
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, price: newPrice, cost_status: costStatus }, `benefits.${selectionId}.price`);
    } else if (hasCatalogOffering) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: costStatus, price: newPrice }, `benefits.offer.${card.offering_id}`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, price: newPrice, cost_status: costStatus }, `benefits.${targetId}.price`);
    }
  };

  const handleRevertPrice = () => {
    setIsEditingPrice(false);
    if (initialPriceNum !== null) {
      setPriceInput(String(initialPriceNum));
      const resetPrice = { amount: initialPriceNum, currency: "MYR" };
      flashSaved("price");
      if (selectionId && !pending) {
        onQueue({ op: "benefit_update", selection_id: selectionId, price: resetPrice, cost_status: "paid" }, `benefits.${selectionId}.price`);
      } else if (hasCatalogOffering) {
        onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: "paid", price: resetPrice }, `benefits.offer.${card.offering_id}`);
      } else if (selectionId || card.concept_key) {
        const targetId = selectionId || card.concept_key!;
        onQueue({ op: "benefit_update", selection_id: targetId, price: resetPrice, cost_status: "paid" }, `benefits.${targetId}.price`);
      }
    }
  };

  const hasPriceDiff = initialPriceNum !== null && (currentPriceNum === null || Math.abs(initialPriceNum - currentPriceNum) > 0.01);

  const toggleLimitVisibility = () => {
    if (!selectionId) return;
    const currentOverride = (selection as any)?.typed_value_override || {};
    const newOverride = { ...currentOverride, hide_limit: !isLimitHidden };
    onQueue(
      { op: "benefit_update", selection_id: selectionId, typed_value_override: newOverride },
      `benefits.${selectionId}.typed_value_override`,
      { op: "benefit_update", selection_id: selectionId, typed_value_override: currentOverride }
    );
  };

  // Directional Movement Handlers:
  // 1. Move Left to Column 1 (Make Free / Included cover)
  const handleMakeFoc = () => {
    if (selectionId && !pending) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: "included", is_extra: false, price: null },
        `benefits.${selectionId}.cost_status`,
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: "paid", is_extra: true, ...(currentPriceNum ? { price: { amount: currentPriceNum, currency: "MYR" } } : {}) }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: "included", is_extra: false, price: null },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: "paid", is_extra: true }
      );
    } else if (card.concept_key || selectionId) {
      const targetId = selectionId || card.concept_key!;
      onQueue(
        { op: "benefit_update", selection_id: targetId, state: "current", cost_status: "included", is_extra: false, price: null },
        `benefits.${targetId}.cost_status`,
        { op: "benefit_update", selection_id: targetId, state: "current", cost_status: "paid", is_extra: true }
      );
    }
  };

  // 2. Move Right to Column 2 (Purchased Extras / Paid Add-on on Quote)
  const handleMakePaid = () => {
    const defaultPrice = currentPriceNum ? { amount: currentPriceNum, currency: "MYR" } : null;
    if (selectionId && !pending) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: "paid", is_extra: true, ...(defaultPrice ? { price: defaultPrice } : {}) },
        `benefits.${selectionId}.cost_status`,
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: "included", is_extra: false, price: null }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: "paid", is_extra: true, ...(defaultPrice ? { price: defaultPrice } : {}) },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: "included", is_extra: false, price: null }
      );
    } else if (card.concept_key || selectionId) {
      const targetId = selectionId || card.concept_key!;
      onQueue(
        { op: "benefit_update", selection_id: targetId, state: "current", cost_status: "paid", is_extra: true, ...(defaultPrice ? { price: defaultPrice } : {}) },
        `benefits.${targetId}.cost_status`,
        { op: "benefit_update", selection_id: targetId, state: "current", cost_status: "included", is_extra: false, price: null }
      );
    }
  };

  // 3. Move Right to Column 3 (Optional Add-on covers)
  const handleMoveToOptional = () => {
    if (selectionId && !pending) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "available_addon", cost_status: "paid" },
        `benefits.${selectionId}.state`,
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: isPurchasedAddon ? "paid" : "included" }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "paid" },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: isPurchasedAddon ? "paid" : "included" }
      );
    } else {
      const customKey = `addon:${card.concept_key || index}`;
      onQueue(
        { op: "create_custom_benefit", selection_key: customKey, state: "available_addon", cost_status: "paid", label: card.label },
        `benefits.add.${index}`,
        { op: "benefit_update", selection_id: customKey, state: "removed" }
      );
    }
  };

  const [confirmRemoveOpen, setConfirmRemoveOpen] = useState(false);

  const performRemove = () => {
    setConfirmRemoveOpen(false);
    if (selectionId) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "removed" },
        `benefits.${selectionId}.state`,
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: "included" }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "removed", cost_status: "included" },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: "included" }
      );
    } else if (card.concept_key) {
      onQueue(
        { op: "benefit_update", selection_id: card.concept_key, state: "removed" },
        `benefits.${card.concept_key}.state`,
        { op: "benefit_update", selection_id: card.concept_key, state: "current", cost_status: "included" }
      );
    }
  };

  const handleRemove = () => setConfirmRemoveOpen(true);

  return (
    <article className={`group flex items-start justify-between gap-3.5 rounded-[var(--rl-radius-sm)] border p-4 shadow-xs transition-all ${card.is_detected
      ? "border-amber-300 bg-amber-50/50 ring-1 ring-amber-300/60"
      : "border-[var(--rl-border)] bg-[var(--rl-surface)] hover:border-[var(--rl-border-strong)]"
      }`}>
      {/* Left: index + image */}
      <div className="flex items-start gap-2.5 shrink-0">
        <span className="flex h-8 min-w-8 px-1.5 items-center justify-center rounded bg-neutral-100 font-mono text-[16px] font-bold text-[var(--rl-text-muted)] mt-0.5">
          #{index + 1}
        </span>
        <div className="flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-md border border-[var(--rl-border)] bg-white p-1">
          {assetUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={fileUrl(assetUrl)} alt={card.label} className="h-full w-full object-contain" />
          ) : (
            <Sparkle size={22} className="text-[var(--rl-text-muted)]" />
          )}
        </div>
      </div>
      {/* Body: title, detected badge, value, description, price */}
      <div className="flex-1 min-w-0 flex flex-col gap-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          {isEditingTitle ? (
            <input
              type="text"
              value={titleInput}
              autoFocus
              onChange={(e) => setTitleInput(e.target.value)}
              onBlur={() => handleTitleCommit(titleInput)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleTitleCommit(titleInput);
                if (e.key === "Escape") { setIsEditingTitle(false); setTitleInput(card.label); }
              }}
              className="h-8 w-full rounded border border-[var(--rl-black)] px-2 font-bold text-[20px] text-[var(--rl-text-strong)] focus:outline-none"
            />
          ) : (
            <div className="group/title flex items-center gap-1.5 max-w-full">
              <h3 className="text-[20px] font-bold text-[var(--rl-text-strong)] leading-snug break-words">{card.label}</h3>
              <button
                type="button"
                onClick={() => setIsEditingTitle(true)}
                className="opacity-70 group-hover/title:opacity-100 p-1 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-opacity cursor-pointer shrink-0"
                title="Edit title"
              >
                <PencilSimple size={15} />
              </button>
            </div>
          )}
          {card.is_detected ? (
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[12px] font-bold text-amber-800 ring-1 ring-amber-400/50 shrink-0">★ Detected</span>
          ) : null}
          {card.cost_status === "unknown" ? (
            <span
              className="rounded bg-amber-50 border border-amber-300 px-1.5 py-0.5 text-[12px] font-bold text-amber-800 shrink-0 flex items-center gap-0.5"
              title="Unclassified cost status from source quotation: Review whether this is Free/Included or a Paid add-on"
            >
              ⚠️ Review Cost
            </span>
          ) : null}
          {savedField ? (
            <span className="text-[13px] font-bold text-emerald-600 flex items-center gap-0.5">
              <Check size={14} weight="bold" /> Saved
            </span>
          ) : null}
        </div>

        {/* Coverage Limit: Editable, Hideable, and Removable for all Box 1 & Box 2 cards */}
        <div className="flex items-center gap-2 flex-wrap mt-0.5 text-[18px]">
          <span className="text-[18px] font-semibold text-[var(--rl-text-muted)]">Coverage:</span>
          {isEditingLimit ? (
            <input
              type="text"
              placeholder={isBetterment ? `Coverage (e.g. ${defaultBetterment})` : "Coverage (e.g. RM 1,000, 50 km)"}
              value={limitInput}
              autoFocus
              onChange={(e) => setLimitInput(e.target.value)}
              onBlur={() => handleLimitCommit(limitInput)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleLimitCommit(limitInput);
                if (e.key === "Escape") { setIsEditingLimit(false); setLimitInput(displayLimitVal || ""); }
              }}
              className="h-8 w-56 rounded border border-[var(--rl-black)] px-2 font-mono text-[18px] font-bold text-[var(--rl-text-strong)] focus:outline-none"
            />
          ) : displayLimitVal && !["", "Included standard cover", "Included", "FOC", "As quoted", "Optional", "Standard"].includes(displayLimitVal) ? (
            <div className="group/limit flex items-center gap-1.5 flex-wrap">
              <button
                type="button"
                onClick={() => setIsEditingLimit(true)}
                className={`text-[18px] font-bold leading-snug break-words text-left transition-colors cursor-pointer hover:underline ${isLimitHidden ? "text-[var(--rl-text-muted)] line-through" : "text-[#5ABA00]"}`}
                title="Click to edit coverage amount"
              >
                {displayLimitVal}
              </button>
              <button
                type="button"
                onClick={() => setIsEditingLimit(true)}
                className="p-1 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-colors cursor-pointer"
                title="Edit coverage amount"
              >
                <PencilSimple size={15} />
              </button>
              <button
                type="button"
                onClick={handleToggleCoverageVisibility}
                className={`p-1 rounded transition-colors cursor-pointer ${isLimitHidden ? "text-amber-600 bg-amber-50 hover:bg-amber-100" : "text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60"}`}
                title={isLimitHidden ? "Coverage is hidden on quotation (click to show)" : "Hide coverage on quotation"}
              >
                {isLimitHidden ? <EyeSlash size={16} weight="bold" /> : <Eye size={16} />}
              </button>
              <button
                type="button"
                onClick={handleRemoveCoverage}
                className="p-1 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-red)] hover:bg-[var(--rl-red-light)] transition-colors cursor-pointer"
                title="Remove coverage amount"
                aria-label="Remove coverage amount"
              >
                <X size={15} weight="bold" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => { setLimitInput(""); setIsEditingLimit(true); }}
              className="text-[16px] font-medium text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] flex items-center gap-1 transition-colors cursor-pointer"
              title="Set coverage amount"
            >
              <Plus size={14} weight="bold" />
              <span>Add coverage</span>
            </button>
          )}
        </div>

        {/* Description */}
        {isEditingDesc ? (
          <textarea
            rows={2}
            value={descInput}
            autoFocus
            onChange={(e) => setDescInput(e.target.value)}
            onBlur={() => handleDescCommit(descInput)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleDescCommit(descInput); }
              if (e.key === "Escape") { setIsEditingDesc(false); setDescInput(card.description || ""); }
            }}
            className="w-full rounded border border-[var(--rl-black)] p-1.5 text-[17px] text-[var(--rl-text-strong)] leading-relaxed focus:outline-none mt-0.5"
          />
        ) : card.description ? (
          <div className="group/desc flex items-start gap-1.5 mt-0.5">
            <p className="text-[17px] text-[var(--rl-text-muted)] leading-relaxed break-words whitespace-normal flex-1">
              {card.description}
            </p>
            <button
              type="button"
              onClick={() => setIsEditingDesc(true)}
              className="opacity-70 group-hover/desc:opacity-100 p-1 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-opacity shrink-0 mt-0.5 cursor-pointer"
              title="Edit description"
            >
              <PencilSimple size={15} />
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setIsEditingDesc(true)}
            className="text-[15px] text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] flex items-center gap-1 transition-colors mt-0.5 cursor-pointer"
            title="Add description"
          >
            <Plus size={14} weight="bold" />
            <span>Add description</span>
          </button>
        )}

        {/* Price Tag & Revert Controls for Included/Purchased Add-ons */}
        {(currentPriceNum !== null || Boolean((card as any).is_extra) || card.cost_status === "paid") && (
          <div className="flex items-center gap-2 mt-1">
            {isEditingPrice ? (
              <div className="flex items-center gap-1.5">
                <span className="text-[16px] font-bold text-[var(--rl-text-muted)]">RM</span>
                <input
                  type="number"
                  step="any"
                  value={priceInput}
                  autoFocus
                  placeholder="0 (FOC)"
                  onChange={(e) => setPriceInput(e.target.value)}
                  onBlur={() => handlePriceCommit(priceInput)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handlePriceCommit(priceInput);
                    if (e.key === "Escape") { setIsEditingPrice(false); setPriceInput(currentPriceNum !== null ? String(currentPriceNum) : ""); }
                  }}
                  className="h-8 w-24 rounded border border-[var(--rl-black)] px-2 font-mono text-[16px] font-bold text-[var(--rl-text-strong)] focus:outline-none"
                />
              </div>
            ) : (
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setIsEditingPrice(true)}
                  className={`group/price flex items-center gap-1.5 rounded px-2 py-0.5 text-[16px] font-bold transition-colors ${currentPriceNum !== null ? "bg-amber-100/80 hover:bg-amber-200 text-amber-900" : "bg-neutral-100 hover:bg-neutral-200 text-neutral-600"}`}
                  title="Click to edit price (clear or 0 for FOC)"
                >
                  <span>{currentPriceNum !== null ? `RM ${currentPriceNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "FOC / Free"}</span>
                  <PencilSimple size={14} className="text-[var(--rl-text-muted)] group-hover/price:text-[var(--rl-black)]" />
                </button>
              </div>
            )}
            {hasPriceDiff ? (
              <button
                type="button"
                onClick={handleRevertPrice}
                className="flex items-center gap-1 rounded bg-gray-100 hover:bg-gray-200 px-2 py-0.5 text-[14px] font-semibold text-gray-600 transition-colors"
                title={`Revert to initial catalog price (RM ${initialPriceNum})`}
              >
                <ArrowCounterClockwise size={14} weight="bold" />
                <span>Revert (RM {initialPriceNum})</span>
              </button>
            ) : null}
          </div>
        )}
      </div>
      {/* Actions */}
      <div className="flex items-center gap-1 shrink-0 mt-0.5">
        <button
          type="button"
          aria-label={`Remove ${card.label} from this quotation`}
          onClick={handleRemove}
          className="rounded p-1.5 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)] transition-colors cursor-pointer"
          title="Remove benefit completely"
        >
          <X size={18} weight="bold" />
        </button>
      </div>
      <ConfirmDialog
        open={confirmRemoveOpen}
        onOpenChange={setConfirmRemoveOpen}
        title="Remove Benefit"
        message={`Are you sure you want to remove "${card.label}" completely?`}
        confirmLabel="Remove"
        onConfirm={performRemove}
      />
    </article>
  );
}

export function AddonCard({
  card,
  index,
  assetUrl,
  onQueue,
  companyName,
}: {
  card: BenefitCardSummary;
  index: number;
  assetUrl?: string | null;
  onQueue: (operation: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) => void;
  companyName?: string | null;
}) {
  const selectionId = card.selection_id;
  const pending = !selectionId || String(selectionId).startsWith("pending:");

  const isWindscreen = card.label.toLowerCase().includes("windscreen") || (card.concept_key || "").toLowerCase().includes("windscreen");
  const isBetterment = card.label.toLowerCase().includes("betterment") || (card.concept_key || "").toLowerCase().includes("betterment");
  const insLower = (companyName || "").toLowerCase();
  const isUnder10Insurer = insLower.includes("qbe") || insLower.includes("stmb") || insLower.includes("takaful malaysia") || insLower.includes("lonpac");
  const defaultBetterment = isUnder10Insurer ? "Up to 10 Years" : "Up to 15 Years";

  const displayLimitVal = isBetterment && (/^\s*rm\b/i.test(card.value || "") || !card.value)
    ? defaultBetterment
    : card.value;
  const isLimitHidden = !isWindscreen && Boolean(
    (card as any).typed_value?.hide_limit ??
    (card as any).hide_coverage
  );
  const isPriceHidden = !!(card as any).typed_value?.hide_price;

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState(card.label);
  const [isEditingLimit, setIsEditingLimit] = useState(false);
  const [limitInput, setLimitInput] = useState(card.value || "");
  const [isEditingDesc, setIsEditingDesc] = useState(false);
  const [descInput, setDescInput] = useState(card.description || "");
  const [savedField, setSavedField] = useState<string | null>(null);

  useEffect(() => { setTitleInput(card.label); }, [card.label]);
  useEffect(() => { setLimitInput(card.value || ""); }, [card.value]);
  useEffect(() => { setDescInput(card.description || ""); }, [card.description]);

  const flashSaved = (field: string) => {
    setSavedField(field);
    setTimeout(() => setSavedField(null), 1400);
  };

  const hasAddonCatalogOffering = Boolean(card.offering_id && !String(card.offering_id).startsWith("custom:") && !String(card.offering_id).startsWith("pending:"));

  const handleToggleCoverageVisibility = () => {
    if (isWindscreen) return;
    const nextHidden = !isLimitHidden;
    flashSaved("coverage");
    const limitText = displayLimitVal || card.value || "";
    const newTyped = {
      type: limitText ? "custom" : "text",
      display_text: limitText,
      hide_limit: nextHidden,
    };
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, typed_value: newTyped }, `benefits.${selectionId}.hide_limit`);
    } else if (hasAddonCatalogOffering) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", typed_value: newTyped }, `benefits.offer.${card.offering_id}`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, typed_value: newTyped }, `benefits.${targetId}.hide_limit`);
    }
  };

  const handleTitleCommit = (newVal: string) => {
    setIsEditingTitle(false);
    const clean = newVal.trim();
    if (!clean || clean === card.label) return;
    flashSaved("title");
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, label: clean }, `benefits.${selectionId}.label`);
    } else if (hasAddonCatalogOffering) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", label: clean }, `benefits.offer.${card.offering_id}`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, label: clean }, `benefits.${targetId}.label`);
    }
  };

  const handleLimitCommit = (newVal: string) => {
    setIsEditingLimit(false);
    let clean = newVal.trim();
    if (isBetterment && /^\s*rm\b/i.test(clean)) {
      clean = defaultBetterment;
    }
    flashSaved("limit");
    const typed = clean
      ? { type: "custom", display_text: clean, hide_limit: false }
      : { type: "text", display_text: "", hide_limit: true };
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, typed_value: typed }, `benefits.${selectionId}.limit`);
    } else if (hasAddonCatalogOffering) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", typed_value: typed }, `benefits.offer.${card.offering_id}`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, typed_value: typed }, `benefits.${targetId}.limit`);
    }
  };

  const handleDescCommit = (newVal: string) => {
    setIsEditingDesc(false);
    const clean = newVal.trim();
    flashSaved("desc");
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, description: clean }, `benefits.${selectionId}.description`);
    } else if (hasAddonCatalogOffering) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", description: clean }, `benefits.offer.${card.offering_id}`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, description: clean }, `benefits.${targetId}.description`);
    }
  };

  const currentPriceObj = card.price || card.optional_price;
  const currentAmount = currentPriceObj ? (typeof currentPriceObj === "object" ? (currentPriceObj.amount ?? (currentPriceObj as any).value) : currentPriceObj) : null;
  const currentPriceNum = currentAmount !== null && currentAmount !== "" && !isNaN(Number(currentAmount)) ? Number(currentAmount) : null;

  const initialPriceObj = card.initial_price || card.optional_price;
  const initialAmount = initialPriceObj ? (typeof initialPriceObj === "object" ? (initialPriceObj.amount ?? (initialPriceObj as any).value) : initialPriceObj) : null;
  const initialPriceNum = initialAmount !== null && initialAmount !== "" && !isNaN(Number(initialAmount)) ? Number(initialAmount) : null;

  const [isEditingPrice, setIsEditingPrice] = useState(false);
  const [priceInput, setPriceInput] = useState(currentPriceNum !== null ? String(currentPriceNum) : "");

  useEffect(() => {
    setPriceInput(currentPriceNum !== null ? String(currentPriceNum) : "");
  }, [currentPriceNum]);

  const handlePriceCommit = (newValStr: string) => {
    setIsEditingPrice(false);
    const trimmed = newValStr.trim();
    flashSaved("price");
    if (!trimmed) {
      // Cleared to FOC / null
      if (selectionId && !pending) {
        onQueue({ op: "benefit_update", selection_id: selectionId, price: null, cost_status: "foc" }, `benefits.${selectionId}.price`);
      } else if (card.offering_id) {
        onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "foc", price: null }, `benefits.offer.${card.offering_id}`);
      } else if (selectionId || card.concept_key) {
        const targetId = selectionId || card.concept_key!;
        onQueue({ op: "benefit_update", selection_id: targetId, price: null, cost_status: "foc" }, `benefits.${targetId}.price`);
      }
      return;
    }
    const cleanNum = parseFloat(trimmed.replace(/[^0-9.]/g, ""));
    if (isNaN(cleanNum)) return;
    const newPrice = { amount: cleanNum, currency: "MYR" };
    const costStatus = cleanNum > 0 ? "paid" : "foc";
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, price: newPrice, cost_status: costStatus }, `benefits.${selectionId}.price`);
    } else if (card.offering_id) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: costStatus, price: newPrice }, `benefits.offer.${card.offering_id}`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, price: newPrice, cost_status: costStatus }, `benefits.${targetId}.price`);
    }
  };

  const handleRevertPrice = () => {
    setIsEditingPrice(false);
    if (initialPriceNum !== null) {
      setPriceInput(String(initialPriceNum));
      const resetPrice = { amount: initialPriceNum, currency: "MYR" };
      flashSaved("price");
      if (selectionId && !pending) {
        onQueue({ op: "benefit_update", selection_id: selectionId, price: resetPrice, cost_status: "paid" }, `benefits.${selectionId}.price`);
      } else if (card.offering_id) {
        onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "paid", price: resetPrice }, `benefits.offer.${card.offering_id}`);
      } else if (selectionId || card.concept_key) {
        const targetId = selectionId || card.concept_key!;
        onQueue({ op: "benefit_update", selection_id: targetId, price: resetPrice, cost_status: "paid" }, `benefits.${targetId}.price`);
      }
    }
  };

  const hasPriceDiff = initialPriceNum !== null && (currentPriceNum === null || Math.abs(initialPriceNum - currentPriceNum) > 0.01);

  const handleAddToPurchasedAddons = () => {
    const priceVal = card.price || card.optional_price || null;
    let finalPrice = null;
    if (priceVal) {
      if (typeof priceVal === "object") {
        const amt = priceVal.amount ?? (priceVal as any).value;
        if (amt !== null && amt !== undefined && !isNaN(Number(amt)) && Number(amt) > 0) {
          finalPrice = { amount: Number(amt), value: Number(amt), currency: "MYR" };
        }
      } else if (!isNaN(Number(priceVal)) && Number(priceVal) > 0) {
        finalPrice = { amount: Number(priceVal), value: Number(priceVal), currency: "MYR" };
      }
    } else if (card.detected_cost && !isNaN(Number(card.detected_cost)) && Number(card.detected_cost) > 0) {
      finalPrice = { amount: Number(card.detected_cost), value: Number(card.detected_cost), currency: "MYR" };
    }

    if (selectionId) {
      onQueue(
        {
          op: "benefit_update",
          selection_id: selectionId,
          state: "current",
          cost_status: "paid",
          ...(finalPrice ? { price: finalPrice } : {}),
        },
        `benefits.${selectionId}.state`,
        { op: "benefit_update", selection_id: selectionId, state: "available_addon", cost_status: "paid" }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        {
          op: "select_catalog_offering",
          offering_id: card.offering_id,
          state: "current",
          cost_status: "paid",
          ...(finalPrice ? { price: finalPrice } : {}),
        },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "paid" }
      );
    } else {
      const customKey = `extra:${card.concept_key || card.concept_id || index}`;
      onQueue(
        {
          op: "create_custom_benefit",
          selection_key: customKey,
          concept_id: card.concept_id,
          concept_key: card.concept_key,
          state: "current",
          cost_status: "paid",
          label: card.label,
          ...(finalPrice ? { price: finalPrice } : {}),
        },
        `benefits.add.${index}`,
        { op: "benefit_update", selection_id: customKey, state: "removed" }
      );
    }
  };

  // Move Left all the way to Column 1 (Free / Included Cover)
  const handleMakeFoc = () => {
    if (selectionId && !pending) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: "included", is_extra: false, price: null },
        `benefits.${selectionId}.state`,
        { op: "benefit_update", selection_id: selectionId, state: "available_addon", cost_status: "paid" }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: "included", is_extra: false, price: null },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "paid" }
      );
    } else {
      const customKey = `foc:${card.concept_key || card.concept_id || index}`;
      onQueue(
        {
          op: "create_custom_benefit",
          selection_key: customKey,
          concept_id: card.concept_id,
          concept_key: card.concept_key,
          state: "current",
          cost_status: "included",
          label: card.label,
          price: null,
        },
        `benefits.add.${index}`,
        { op: "benefit_update", selection_id: customKey, state: "removed" }
      );
    }
  };

  const handleRemove = () => {
    if (selectionId) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "removed" },
        `benefits.${selectionId}.state`,
        { op: "benefit_update", selection_id: selectionId, state: "available_addon", cost_status: "paid" }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "removed", cost_status: "paid" },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "paid" }
      );
    } else if (card.concept_key) {
      onQueue(
        { op: "benefit_update", selection_id: card.concept_key, state: "removed" },
        `benefits.${card.concept_key}.state`,
        { op: "benefit_update", selection_id: card.concept_key, state: "available_addon", cost_status: "paid" }
      );
    }
  };

  return (
    <article className={`group flex items-start justify-between gap-2.5 rounded-[var(--rl-radius-sm)] border border-dashed p-2.5 transition-all ${card.is_detected
      ? "border-amber-400 bg-amber-50/50 ring-1 ring-amber-300/60"
      : "border-[var(--rl-border)] bg-[var(--rl-surface)] hover:border-[var(--rl-black)] hover:bg-white"
      }`}>
      {/* Left: index + image */}
      <div className="flex items-start gap-2 shrink-0">
        <span className="flex h-6 w-6 items-center justify-center rounded bg-neutral-100 font-mono text-[10px] font-bold text-[var(--rl-text-muted)] mt-0.5">
          #{index + 1}
        </span>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-md border border-[var(--rl-border)] bg-white p-1">
          {assetUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={fileUrl(assetUrl)} alt={card.label} className="h-full w-full object-contain" />
          ) : (
            <Sparkle size={18} className="text-[var(--rl-text-muted)]" />
          )}
        </div>
      </div>
      {/* Body: title, detected badge, coverage, description, price */}
      <div className="flex-1 min-w-0 flex flex-col gap-0.5">
        <div className="flex items-center gap-1.5 flex-wrap">
          {isEditingTitle ? (
            <input
              type="text"
              value={titleInput}
              autoFocus
              onChange={(e) => setTitleInput(e.target.value)}
              onBlur={() => handleTitleCommit(titleInput)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleTitleCommit(titleInput);
                if (e.key === "Escape") { setIsEditingTitle(false); setTitleInput(card.label); }
              }}
              className="h-5 w-full rounded border border-[var(--rl-black)] px-1.5 font-bold text-xs text-[var(--rl-text-strong)] focus:outline-none"
            />
          ) : (
            <div className="group/title flex items-center gap-1 max-w-full">
              <h3 className="text-xs font-bold text-[var(--rl-text-strong)] leading-tight break-words">{card.label}</h3>
              <button
                type="button"
                onClick={() => setIsEditingTitle(true)}
                className="opacity-70 group-hover/title:opacity-100 p-0.5 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-opacity cursor-pointer shrink-0"
                title="Edit title"
              >
                <PencilSimple size={10} />
              </button>
            </div>
          )}
          {card.is_detected ? (
            <span className="rounded bg-amber-100 px-1 py-0.5 text-[9px] font-bold text-amber-800 ring-1 ring-amber-400/50 shrink-0">★ Detected</span>
          ) : null}
          {card.cost_status === "unknown" ? (
            <span
              className="rounded bg-amber-50 border border-amber-300 px-1 py-0.5 text-[9px] font-bold text-amber-800 shrink-0 flex items-center gap-0.5"
              title="Unclassified cost status from source quotation: Review whether this is Free/Included or a Paid add-on"
            >
              ⚠️ Review Cost
            </span>
          ) : null}
          {savedField ? (
            <span className="text-[9px] font-bold text-emerald-600 flex items-center gap-0.5">
              <Check size={10} weight="bold" /> Saved
            </span>
          ) : null}
        </div>

        {/* Coverage Limit */}
        {isEditingLimit ? (
          <input
            type="text"
            placeholder={isBetterment ? `Coverage (e.g. ${defaultBetterment})` : "Coverage (e.g. RM 1,000, 50 km)"}
            value={limitInput}
            autoFocus
            onChange={(e) => setLimitInput(e.target.value)}
            onBlur={() => handleLimitCommit(limitInput)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleLimitCommit(limitInput);
              if (e.key === "Escape") { setIsEditingLimit(false); setLimitInput(displayLimitVal || ""); }
            }}
            className="h-5 w-44 rounded border border-[var(--rl-black)] px-1 font-mono text-[11px] font-bold text-[var(--rl-text-strong)] focus:outline-none mt-0.5"
          />
        ) : displayLimitVal && !["", "Optional payable add-on", "Included", "FOC", "As quoted", "Optional"].includes(displayLimitVal) ? (
          <div className="group/limit flex items-center gap-1 mt-0.5 flex-wrap">
            <p className={`text-[11px] font-bold leading-tight break-words transition-colors ${isLimitHidden ? "text-[var(--rl-text-muted)] line-through" : "text-[#5ABA00]"}`}>
              {displayLimitVal}
            </p>
            <button
              type="button"
              onClick={() => setIsEditingLimit(true)}
              className="opacity-70 group-hover/limit:opacity-100 p-0.5 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-opacity cursor-pointer"
              title="Edit coverage limit"
            >
              <PencilSimple size={10} />
            </button>
            <button
              type="button"
              onClick={handleToggleCoverageVisibility}
              className={`p-0.5 rounded transition-colors cursor-pointer ${isLimitHidden ? "text-amber-600 bg-amber-50 hover:bg-amber-100" : "opacity-70 group-hover/limit:opacity-100 text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60"}`}
              title={isLimitHidden ? "Coverage is hidden on quotation (click to show)" : "Hide coverage on quotation"}
            >
              {isLimitHidden ? <EyeSlash size={11} weight="bold" /> : <Eye size={11} />}
            </button>
            <button
              type="button"
              onClick={() => { setLimitInput(""); handleLimitCommit(""); }}
              className="opacity-70 group-hover/limit:opacity-100 p-0.5 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-red)] hover:bg-[var(--rl-red-light)] transition-opacity cursor-pointer"
              title="Remove coverage amount"
            >
              <X size={10} weight="bold" />
            </button>
          </div>
        ) : (
          <div className="group/limit flex items-center gap-1 mt-0.5">
            <button
              type="button"
              onClick={() => setIsEditingLimit(true)}
              className="text-[10px] text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] flex items-center gap-0.5 transition-colors cursor-pointer"
              title="Set coverage limit"
            >
              <PencilSimple size={9} />
              <span>+ Coverage</span>
            </button>
          </div>
        )}

        {/* Description */}
        {isEditingDesc ? (
          <textarea
            rows={2}
            value={descInput}
            autoFocus
            onChange={(e) => setDescInput(e.target.value)}
            onBlur={() => handleDescCommit(descInput)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleDescCommit(descInput); }
              if (e.key === "Escape") { setIsEditingDesc(false); setDescInput(card.description || ""); }
            }}
            className="w-full rounded border border-[var(--rl-black)] p-1 text-[10px] text-[var(--rl-text-strong)] leading-snug focus:outline-none mt-0.5"
          />
        ) : card.description ? (
          <div className="group/desc flex items-start gap-1 mt-0.5">
            <p className="text-[10px] text-[var(--rl-text-muted)] leading-snug break-words whitespace-normal flex-1">
              {card.description}
            </p>
            <button
              type="button"
              onClick={() => setIsEditingDesc(true)}
              className="opacity-70 group-hover/desc:opacity-100 p-0.5 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-opacity shrink-0 mt-0.5 cursor-pointer"
              title="Edit description"
            >
              <PencilSimple size={10} />
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setIsEditingDesc(true)}
            className="text-[9px] text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] flex items-center gap-0.5 transition-colors mt-0.5 cursor-pointer"
            title="Add description"
          >
            <PencilSimple size={9} />
            <span>+ Description</span>
          </button>
        )}

        {/* Price Tag & Revert Controls */}
        <div className="flex items-center gap-1.5 mt-1">
          {isEditingPrice ? (
            <div className="flex items-center gap-1">
              <span className="text-[10px] font-bold text-[var(--rl-text-muted)]">RM</span>
              <input
                type="number"
                step="any"
                value={priceInput}
                autoFocus
                placeholder="0 (FOC)"
                onChange={(e) => setPriceInput(e.target.value)}
                onBlur={() => handlePriceCommit(priceInput)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handlePriceCommit(priceInput);
                  if (e.key === "Escape") { setIsEditingPrice(false); setPriceInput(currentPriceNum !== null ? String(currentPriceNum) : ""); }
                }}
                className="h-5 w-16 rounded border border-[var(--rl-black)] px-1 font-mono text-[11px] font-bold text-[var(--rl-text-strong)] focus:outline-none"
              />
            </div>
          ) : (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setIsEditingPrice(true)}
                className={`group/price flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold transition-colors ${isPriceHidden ? "bg-gray-100 text-gray-500 line-through" : currentPriceNum !== null ? "bg-red-50 hover:bg-red-100/80 text-[var(--rl-red)]" : "bg-neutral-100 hover:bg-neutral-200 text-neutral-600"}`}
                title="Click to edit price (clear or 0 for FOC)"
              >
                <span>{currentPriceNum !== null ? `RM ${currentPriceNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "FOC / Free"}</span>
                <PencilSimple size={10} className="text-[var(--rl-text-muted)] group-hover/price:text-[var(--rl-red)]" />
              </button>
            </div>
          )}
          {hasPriceDiff ? (
            <button
              type="button"
              onClick={handleRevertPrice}
              className="flex items-center gap-0.5 rounded bg-gray-100 hover:bg-gray-200 px-1.5 py-0.5 text-[9px] font-semibold text-gray-600 transition-colors"
              title={`Revert to initial catalog price (RM ${initialPriceNum})`}
            >
              <ArrowCounterClockwise size={10} weight="bold" />
              <span>Revert (RM {initialPriceNum})</span>
            </button>
          ) : null}
        </div>
      </div>
      {/* Actions */}
      <div className="flex items-center gap-1 shrink-0 mt-0.5">
        <Button
          size="sm"
          variant="secondary"
          title="Move left to Purchased Extras on this quotation"
          onClick={handleAddToPurchasedAddons}
          className="text-[11px] h-7 px-2 font-bold bg-amber-50 border border-amber-300 text-amber-900 hover:bg-amber-100 transition-colors shadow-2xs"
        >
          ← Add to Quote
        </Button>
        <Button
          size="sm"
          variant="secondary"
          title="Move left directly to Free / Included covers"
          onClick={handleMakeFoc}
          className="text-[11px] h-7 px-2 text-emerald-800 hover:bg-emerald-100 transition-colors"
        >
          ← FOC
        </Button>
        <button
          type="button"
          aria-label={`Remove ${card.label}`}
          onClick={handleRemove}
          className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)] transition-colors cursor-pointer"
          title="Remove add-on completely"
        >
          <X size={14} weight="bold" />
        </button>
      </div>
    </article>
  );
}

export function MatrixAddonCard({
  card,
  index,
  assetUrl,
  selection,
  isSelected,
  onToggleSelect,
  onQueue,
  companyName,
}: {
  card: BenefitCardSummary;
  index: number;
  assetUrl?: string | null;
  selection?: { id: string; cost_status: string } | Record<string, unknown> | null;
  isSelected: boolean;
  onToggleSelect: (willSelect: boolean) => void;
  onQueue: (operation: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) => void;
  companyName?: string | null;
}) {
  const selectionId = selection && typeof selection === "object" && "id" in selection ? String(selection.id) : (card.selection_id || null);
  const pending = !selectionId || String(selectionId).startsWith("pending:");
  const hasMatrixCatalogOffering = Boolean(card.offering_id && !String(card.offering_id).startsWith("custom:") && !String(card.offering_id).startsWith("pending:"));

  const isWindscreen = card.label.toLowerCase().includes("windscreen") || (card.concept_key || "").toLowerCase().includes("windscreen");
  const isBetterment = card.label.toLowerCase().includes("betterment") || (card.concept_key || "").toLowerCase().includes("betterment");
  const insLower = (companyName || "").toLowerCase();
  const isUnder10Insurer = insLower.includes("qbe") || insLower.includes("stmb") || insLower.includes("takaful malaysia") || insLower.includes("lonpac");
  const defaultBetterment = isUnder10Insurer ? "Up to 10 Years" : "Up to 15 Years";

  const embeddedMetricMatch = !card.value
    ? card.label.match(/\(((?:rm|myr)\s*[\d,]+(?:\.\d{1,2})?|\d+\s*km|unlimited[^)]*)\)\s*$/i)
    : null;
  const effectiveRawVal = card.value || (embeddedMetricMatch ? embeddedMetricMatch[1].trim() : "");
  const isExplicitlyCleared = Boolean(
    ((selection as any)?.typed_value_override &&
      "display_text" in ((selection as any)?.typed_value_override || {}) &&
      String((selection as any)?.typed_value_override?.display_text ?? "").trim() === "") ||
    ((card as any).typed_value &&
      "display_text" in ((card as any).typed_value || {}) &&
      String((card as any).typed_value?.display_text ?? "").trim() === "")
  );

  const displayLimitVal = isExplicitlyCleared
    ? ""
    : isBetterment && (/^\s*rm\b/i.test(effectiveRawVal) || !effectiveRawVal)
      ? defaultBetterment
      : effectiveRawVal;
  const isLimitHidden = Boolean(
    (selection as any)?.typed_value_override?.hide_limit ??
    (card as any).typed_value?.hide_limit ??
    (card as any).hide_coverage
  );

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState(card.label);
  const [isEditingLimit, setIsEditingLimit] = useState(false);
  const [limitInput, setLimitInput] = useState(displayLimitVal || "");
  const [isEditingDesc, setIsEditingDesc] = useState(false);
  const [descInput, setDescInput] = useState(card.description || "");
  const [savedField, setSavedField] = useState<string | null>(null);

  useEffect(() => { setTitleInput(card.label); }, [card.label]);
  useEffect(() => { setLimitInput(displayLimitVal || ""); }, [displayLimitVal]);
  useEffect(() => { setDescInput(card.description || ""); }, [card.description]);

  const flashSaved = (field: string) => {
    setSavedField(field);
    setTimeout(() => setSavedField(null), 1400);
  };

  const stripMetricFromLabelIfPresent = (): string | undefined => {
    const stripped = card.label.replace(/\s*\((?:(?:rm|myr)\s*[\d,]+(?:\.\d{1,2})?|\d+\s*km|unlimited[^)]*)\)\s*$/i, "").trim();
    return stripped && stripped !== card.label ? stripped : undefined;
  };

  const handleToggleCoverageVisibility = () => {
    const nextHidden = !isLimitHidden;
    flashSaved("coverage");
    const limitText = displayLimitVal || card.value || "";
    const newTyped = {
      type: limitText ? "custom" : "text",
      display_text: limitText,
      hide_limit: nextHidden,
    };
    const cleanedLabel = nextHidden ? stripMetricFromLabelIfPresent() : undefined;
    if (selectionId && !pending) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, typed_value: newTyped, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.${selectionId}.limit`
      );
    } else if (hasMatrixCatalogOffering) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: isSelected ? "current" : "available_addon", typed_value: newTyped, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.offer.${card.offering_id}.limit`
      );
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue(
        { op: "benefit_update", selection_id: targetId, typed_value: newTyped, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.${targetId}.limit`
      );
    }
  };

  const handleTitleCommit = (newVal: string) => {
    setIsEditingTitle(false);
    const clean = newVal.trim();
    if (!clean || clean === card.label) return;
    flashSaved("title");
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, label: clean }, `benefits.${selectionId}.label`);
    } else if (hasMatrixCatalogOffering) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: isSelected ? "current" : "available_addon", label: clean }, `benefits.offer.${card.offering_id}.label`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, label: clean }, `benefits.${targetId}.label`);
    }
  };

  const handleLimitCommit = (newVal: string) => {
    setIsEditingLimit(false);
    let clean = newVal.trim();
    if (isBetterment && /^\s*rm\b/i.test(clean)) {
      clean = defaultBetterment;
    }
    flashSaved("limit");
    const typed = clean
      ? { type: "custom", display_text: clean, hide_limit: false }
      : { type: "text", display_text: "", hide_limit: true };
    const cleanedLabel = stripMetricFromLabelIfPresent();
    if (selectionId && !pending) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, typed_value: typed, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.${selectionId}.limit`
      );
    } else if (hasMatrixCatalogOffering) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: isSelected ? "current" : "available_addon", typed_value: typed, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.offer.${card.offering_id}.limit`
      );
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue(
        { op: "benefit_update", selection_id: targetId, typed_value: typed, ...(cleanedLabel ? { label: cleanedLabel } : {}) },
        `benefits.${targetId}.limit`
      );
    }
  };

  const handleRemoveCoverage = () => {
    setLimitInput("");
    handleLimitCommit("");
  };

  const handleDescCommit = (newVal: string) => {
    setIsEditingDesc(false);
    const clean = newVal.trim();
    flashSaved("desc");
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, description: clean }, `benefits.${selectionId}.description`);
    } else if (hasMatrixCatalogOffering) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: isSelected ? "current" : "available_addon", description: clean }, `benefits.offer.${card.offering_id}`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, description: clean }, `benefits.${targetId}.description`);
    }
  };

  const currentPriceObj = card.price || (card as any).optional_price;
  const currentAmount = currentPriceObj ? (typeof currentPriceObj === "object" ? (currentPriceObj.amount ?? (currentPriceObj as any).value) : currentPriceObj) : null;
  const currentPriceNum = currentAmount !== null && currentAmount !== "" && !isNaN(Number(currentAmount)) ? Number(currentAmount) : null;

  const initialPriceObj = card.initial_price || (card as any).optional_price;
  const initialAmount = initialPriceObj ? (typeof initialPriceObj === "object" ? (initialPriceObj.amount ?? (initialPriceObj as any).value) : initialPriceObj) : null;
  const initialPriceNum = initialAmount !== null && initialAmount !== "" && !isNaN(Number(initialAmount)) ? Number(initialAmount) : null;

  const [isEditingPrice, setIsEditingPrice] = useState(false);
  const [priceInput, setPriceInput] = useState(currentPriceNum !== null ? String(currentPriceNum) : "");

  useEffect(() => {
    setPriceInput(currentPriceNum !== null ? String(currentPriceNum) : "");
  }, [currentPriceNum]);

  const handlePriceCommit = (newValStr: string) => {
    setIsEditingPrice(false);
    const trimmed = newValStr.trim();
    flashSaved("price");
    if (!trimmed) {
      if (selectionId && !pending) {
        onQueue({ op: "benefit_update", selection_id: selectionId, price: null, cost_status: "paid" }, `benefits.${selectionId}.price`);
      } else if (hasMatrixCatalogOffering) {
        onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: isSelected ? "current" : "available_addon", cost_status: "paid", price: null }, `benefits.offer.${card.offering_id}`);
      } else if (selectionId || card.concept_key) {
        const targetId = selectionId || card.concept_key!;
        onQueue({ op: "benefit_update", selection_id: targetId, price: null, cost_status: "paid" }, `benefits.${targetId}.price`);
      }
      return;
    }
    const cleanNum = parseFloat(trimmed.replace(/[^0-9.]/g, ""));
    if (isNaN(cleanNum)) return;
    const newPrice = { amount: cleanNum, currency: "MYR" };
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, price: newPrice, cost_status: "paid" }, `benefits.${selectionId}.price`);
    } else if (hasMatrixCatalogOffering) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: isSelected ? "current" : "available_addon", cost_status: "paid", price: newPrice }, `benefits.offer.${card.offering_id}`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, price: newPrice, cost_status: "paid" }, `benefits.${targetId}.price`);
    }
  };

  const handleRevertPrice = () => {
    setIsEditingPrice(false);
    if (initialPriceNum !== null) {
      setPriceInput(String(initialPriceNum));
      const resetPrice = { amount: initialPriceNum, currency: "MYR" };
      flashSaved("price");
      if (selectionId && !pending) {
        onQueue({ op: "benefit_update", selection_id: selectionId, price: resetPrice, cost_status: "paid" }, `benefits.${selectionId}.price`);
      } else if (hasMatrixCatalogOffering) {
        onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: isSelected ? "current" : "available_addon", cost_status: "paid", price: resetPrice }, `benefits.offer.${card.offering_id}`);
      } else if (selectionId || card.concept_key) {
        const targetId = selectionId || card.concept_key!;
        onQueue({ op: "benefit_update", selection_id: targetId, price: resetPrice, cost_status: "paid" }, `benefits.${targetId}.price`);
      }
    }
  };

  const hasPriceDiff = initialPriceNum !== null && (currentPriceNum === null || Math.abs(initialPriceNum - currentPriceNum) > 0.01);

  const handleMakeFoc = () => {
    if (selectionId && !pending) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: "included", is_extra: false, price: null },
        `benefits.${selectionId}.cost_status`,
        { op: "benefit_update", selection_id: selectionId, state: isSelected ? "current" : "available_addon", cost_status: "paid", is_extra: true, ...(currentPriceNum ? { price: { amount: currentPriceNum, currency: "MYR" } } : {}) }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: "included", is_extra: false, price: null },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: isSelected ? "current" : "available_addon", cost_status: "paid", is_extra: true }
      );
    } else if (card.concept_key || selectionId) {
      const targetId = selectionId || card.concept_key!;
      onQueue(
        { op: "benefit_update", selection_id: targetId, state: "current", cost_status: "included", is_extra: false, price: null },
        `benefits.${targetId}.cost_status`,
        { op: "benefit_update", selection_id: targetId, state: isSelected ? "current" : "available_addon", cost_status: "paid", is_extra: true }
      );
    }
  };

  const [confirmRemoveAddonOpen, setConfirmRemoveAddonOpen] = useState(false);

  const performRemove = () => {
    setConfirmRemoveAddonOpen(false);
    if (selectionId) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "removed" },
        `benefits.${selectionId}.state`
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "removed" },
        `benefits.offer.${card.offering_id}`
      );
    } else if (card.concept_key) {
      onQueue(
        { op: "benefit_update", selection_id: card.concept_key, state: "removed" },
        `benefits.${card.concept_key}.state`
      );
    }
  };

  const handleRemove = () => setConfirmRemoveAddonOpen(true);

  const isBundleEffect = Boolean(card.is_bundle_effect || card.cost_status === "bundle_included");
  const serialStr = String(index + 1).padStart(2, "0");

  return (
    <article
      className={`group flex items-start gap-3.5 rounded-[var(--rl-radius-sm)] border p-4 shadow-xs transition-all ${isSelected
        ? "border-emerald-300 bg-emerald-50/40 ring-1 ring-emerald-400/40"
        : "border-[var(--rl-border)] bg-[var(--rl-surface)] hover:border-[var(--rl-border-strong)]"
        }`}
    >
      {/* 1. Design 2 Checkbox (Click to toggle Selected / Ticked; locked when managed by parent bundle) */}
      <button
        type="button"
        disabled={isBundleEffect}
        onClick={() => {
          if (!isBundleEffect) onToggleSelect(!isSelected);
        }}
        className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md transition-transform ${isBundleEffect ? "cursor-default opacity-90" : "hover:scale-105 cursor-pointer"
          }`}
        title={
          isBundleEffect
            ? "Included automatically with active bundled benefit — remove or untick the parent bundle to restore Box 1 towing"
            : isSelected
              ? "Ticked on Quote (Click to untick)"
              : "Unticked (Click to tick and push to top #01)"
        }
      >
        {isSelected ? (
          <div className="flex size-7 items-center justify-center rounded-full bg-[#5ABA00] text-white shadow-xs">
            <Check size={16} weight="bold" />
          </div>
        ) : (
          <div className="size-6 rounded-md border-2 border-neutral-400 bg-white hover:border-[#5ABA00] transition-colors" />
        )}
      </button>

      {/* 2. Number + Asset Media */}
      <div className="flex items-center gap-2.5 shrink-0">
        <span
          className={`flex h-8 min-w-8 px-1.5 items-center justify-center rounded font-mono text-[16px] font-bold ${isSelected ? "bg-emerald-100 text-emerald-800" : "bg-neutral-100 text-neutral-600"
            }`}
        >
          #{serialStr}
        </span>
        <div className="flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-md border border-[var(--rl-border)] bg-white p-1">
          {card.icon_hint === "unlimited_towing" ? (
            <Design2BenefitIconSvg hint={card.icon_hint} size={36} />
          ) : assetUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={fileUrl(assetUrl)} alt={card.label} className="size-full object-contain" />
          ) : card.icon_hint ? (
            <Design2BenefitIconSvg hint={card.icon_hint} size={36} />
          ) : (
            <Sparkle size={22} className={isSelected ? "text-emerald-600" : "text-[var(--rl-text-muted)]"} />
          )}
        </div>
      </div>

      {/* 3. Middle Body: Title, Limit, Price, Description */}
      <div id={`workspace-benefit-${selectionId || card.card_key}`} className="flex-1 min-w-0 flex flex-col gap-1.5">
        {/* Title Row */}
        <div className="flex items-center gap-2 flex-wrap">
          {isEditingTitle ? (
            <input
              type="text"
              value={titleInput}
              autoFocus
              onChange={(e) => setTitleInput(e.target.value)}
              onBlur={() => handleTitleCommit(titleInput)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleTitleCommit(titleInput);
                if (e.key === "Escape") { setIsEditingTitle(false); setTitleInput(card.label); }
              }}
              className="h-8 w-full max-w-md rounded border border-[var(--rl-black)] px-2 font-bold text-[20px] text-[var(--rl-text-strong)] focus:outline-none"
            />
          ) : (
            <div className="group/title flex items-center gap-1.5 max-w-full">
              <h4 className="text-[20px] font-bold text-[var(--rl-text-strong)] leading-snug break-words">
                {card.label}
              </h4>
              <button
                type="button"
                onClick={() => setIsEditingTitle(true)}
                className="opacity-70 group-hover/title:opacity-100 p-1 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] transition-opacity cursor-pointer shrink-0"
                title="Edit title"
              >
                <PencilSimple size={15} />
              </button>
            </div>
          )}

          {isSelected && (
            <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[12px] font-bold text-emerald-800 shrink-0">
              ✔ Ticked on Quote
            </span>
          )}

          {card.is_detected && (
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[12px] font-bold text-amber-800 shrink-0">
              ★ Detected
            </span>
          )}

          {card.is_bundle_effect || card.cost_status === "bundle_included" ? (
            <span className="rounded bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 text-[11px] font-bold text-emerald-700 shrink-0">
              Upgraded Benefit
            </span>
          ) : null}

          {card.plan_tier_uncertain && (
            <span
              className="inline-flex items-center gap-1 rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-[11px] font-bold text-amber-800 shrink-0"
              title={card.needs_review_reason || "Plan tier was uncertain and defaulted to Plan 1. Please verify."}
            >
              <span>⚠ Verify Plan</span>
              {selectionId && !pending ? (
                <button
                  type="button"
                  onClick={() =>
                    onQueue(
                      { op: "benefit_update", selection_id: selectionId, confirm_plan_tier: true },
                      `benefits.${selectionId}.plan_tier`
                    )
                  }
                  className="inline-flex items-center gap-0.5 rounded bg-emerald-600 px-1 py-0.5 text-[10px] font-bold text-white hover:bg-emerald-700 cursor-pointer"
                  title="Confirm detected plan tier"
                >
                  <Check size={9} weight="bold" />
                  <span>Confirm</span>
                </button>
              ) : null}
            </span>
          )}

          {savedField && (
            <span className="text-[13px] font-bold text-emerald-600 flex items-center gap-0.5">
              <Check size={14} weight="bold" /> Saved
            </span>
          )}
        </div>

        {/* Bundled Benefit Plan Tier Selector */}
        {card.available_bundle_tiers && card.available_bundle_tiers.length > 0 && selectionId && !pending && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] font-semibold text-[var(--rl-text-muted)]">Plan Level:</span>
            {card.available_bundle_tiers.map((tierOpt) => {
              const isActiveTier = card.selected_bundle_tier_id
                ? card.selected_bundle_tier_id === tierOpt.id
                : (card.selected_bundle_tier_label || "").toLowerCase() === tierOpt.label.toLowerCase();
              return (
                <button
                  key={tierOpt.id}
                  type="button"
                  onClick={() =>
                    onQueue(
                      {
                        op: "benefit_update",
                        selection_id: selectionId,
                        bundle_tier_id: tierOpt.id,
                      },
                      `benefits.${selectionId}.plan_tier`
                    )
                  }
                  className={`rounded px-2 py-0.5 text-[11px] font-bold transition-colors cursor-pointer border ${isActiveTier
                    ? "bg-[var(--rl-black)] text-white border-[var(--rl-black)]"
                    : "bg-white text-[var(--rl-text-strong)] border-[var(--rl-border)] hover:bg-neutral-100"
                    }`}
                >
                  {tierOpt.label}
                </button>
              );
            })}
          </div>
        )}

        {/* Coverage Limit & Price Row (Spacious & Clean) */}
        <div className="flex items-center gap-4 flex-wrap text-[18px]">
          {/* Coverage Limit */}
          <div className="flex items-center gap-1.5 text-[18px] flex-wrap">
            <span className="font-semibold text-[var(--rl-text-muted)]">Coverage:</span>
            {isEditingLimit ? (
              <input
                type="text"
                placeholder={isBetterment ? `Coverage (e.g. ${defaultBetterment})` : "Coverage Limit (e.g. RM 1,000)"}
                value={limitInput}
                autoFocus
                onChange={(e) => setLimitInput(e.target.value)}
                onBlur={() => handleLimitCommit(limitInput)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleLimitCommit(limitInput);
                  if (e.key === "Escape") { setIsEditingLimit(false); setLimitInput(displayLimitVal || ""); }
                }}
                className="h-8 w-52 rounded border border-[var(--rl-black)] px-2 font-mono text-[18px] font-bold text-[var(--rl-text-strong)] focus:outline-none"
              />
            ) : displayLimitVal && !["", "Included standard cover", "Included", "FOC", "As quoted", "Optional", "Standard"].includes(displayLimitVal) ? (
              <div className="group/limit flex items-center gap-1.5 flex-wrap">
                <button
                  type="button"
                  onClick={() => setIsEditingLimit(true)}
                  className={`font-bold break-words text-left transition-colors cursor-pointer hover:underline ${isLimitHidden ? "text-[var(--rl-text-muted)] line-through" : "text-[#5ABA00]"}`}
                  title="Click to edit coverage limit"
                >
                  {displayLimitVal}
                </button>
                <button
                  type="button"
                  onClick={() => setIsEditingLimit(true)}
                  className="p-1 text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] transition-colors cursor-pointer"
                  title="Edit coverage limit"
                >
                  <PencilSimple size={15} />
                </button>
                <button
                  type="button"
                  onClick={handleToggleCoverageVisibility}
                  className={`p-1 rounded transition-colors cursor-pointer ${isLimitHidden ? "text-amber-600 bg-amber-50 hover:bg-amber-100" : "text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60"}`}
                  title={isLimitHidden ? "Coverage is hidden on quotation (click to show)" : "Hide coverage on quotation"}
                >
                  {isLimitHidden ? <EyeSlash size={16} weight="bold" /> : <Eye size={16} />}
                </button>
                <button
                  type="button"
                  onClick={handleRemoveCoverage}
                  className="p-1 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-red)] hover:bg-[var(--rl-red-light)] transition-colors cursor-pointer"
                  title="Remove coverage amount"
                  aria-label="Remove coverage amount"
                >
                  <X size={15} weight="bold" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => { setLimitInput(""); setIsEditingLimit(true); }}
                className="text-[16px] font-medium text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] flex items-center gap-1 transition-colors cursor-pointer"
                title="Set coverage amount"
              >
                <Plus size={14} weight="bold" />
                <span>Add coverage</span>
              </button>
            )}
          </div>

          {/* Premium Price (hidden for unlocked side-by-side bundle benefit cards — price lives only on parent bundle) */}
          {!(card.is_bundle_effect || card.cost_status === "bundle_included") && (
            <div className="flex items-center gap-1.5 text-[16px]">
              <span className="font-semibold text-[var(--rl-text-muted)]">Price:</span>
              {isEditingPrice ? (
                <div className="flex items-center gap-1.5">
                  <span className="text-[16px] font-bold text-[var(--rl-text-muted)]">RM</span>
                  <input
                    type="number"
                    step="any"
                    value={priceInput}
                    autoFocus
                    placeholder="0.00"
                    onChange={(e) => setPriceInput(e.target.value)}
                    onBlur={() => handlePriceCommit(priceInput)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handlePriceCommit(priceInput);
                      if (e.key === "Escape") { setIsEditingPrice(false); setPriceInput(currentPriceNum !== null ? String(currentPriceNum) : ""); }
                    }}
                    className="h-8 w-24 rounded border border-[var(--rl-black)] px-2 font-mono text-[16px] font-bold text-[var(--rl-text-strong)] focus:outline-none"
                  />
                </div>
              ) : (
                <div className="group/price flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setIsEditingPrice(true)}
                    className={`flex items-center gap-1.5 rounded px-2 py-0.5 text-[16px] font-mono font-bold transition-colors ${isSelected
                      ? currentPriceNum !== null && currentPriceNum > 0
                        ? "bg-amber-100 text-amber-900 hover:bg-amber-200"
                        : "bg-emerald-100 text-emerald-800 hover:bg-emerald-200"
                      : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                      }`}
                    title="Click to edit price (0 for FOC)"
                  >
                    <span>
                      {currentPriceNum !== null && currentPriceNum > 0
                        ? `RM ${currentPriceNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                        : isSelected
                          ? "FOC / Free"
                          : "+ Set Price"}
                    </span>
                    <PencilSimple size={14} className="text-[var(--rl-text-muted)] group-hover/price:text-[var(--rl-black)]" />
                  </button>
                  {hasPriceDiff && (
                    <button
                      type="button"
                      onClick={handleRevertPrice}
                      className="flex items-center gap-1 rounded bg-gray-100 hover:bg-gray-200 px-1.5 py-0.5 text-[14px] font-semibold text-gray-600 transition-colors"
                      title={`Revert to initial catalog price (RM ${initialPriceNum})`}
                    >
                      <ArrowCounterClockwise size={14} weight="bold" />
                      <span>Revert</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Description Row */}
        {isEditingDesc ? (
          <textarea
            rows={2}
            value={descInput}
            autoFocus
            onChange={(e) => setDescInput(e.target.value)}
            onBlur={() => handleDescCommit(descInput)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleDescCommit(descInput); }
              if (e.key === "Escape") { setIsEditingDesc(false); setDescInput(card.description || ""); }
            }}
            className="w-full rounded border border-[var(--rl-black)] p-1.5 text-[17px] text-[var(--rl-text-strong)] leading-relaxed focus:outline-none"
          />
        ) : card.description ? (
          <div className="group/desc flex items-start gap-1.5">
            <p className="text-[17px] text-[var(--rl-text-muted)] leading-relaxed break-words whitespace-normal flex-1">
              {card.description}
            </p>
            <button
              type="button"
              onClick={() => setIsEditingDesc(true)}
              className="opacity-70 group-hover/desc:opacity-100 p-1 text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] transition-opacity shrink-0 cursor-pointer"
              title="Edit description"
            >
              <PencilSimple size={15} />
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setIsEditingDesc(true)}
            className="text-[15px] text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] flex items-center gap-1 transition-colors cursor-pointer"
            title="Add description"
          >
            <Plus size={14} weight="bold" />
            <span>Add description</span>
          </button>
        )}
      </div>

      {/* 4. Action Button: Delete (hidden on bundle-included effects so parent bundle controls Box 1 restoration) */}
      {!isBundleEffect && (
        <div className="flex items-center gap-1 shrink-0 self-start">
          <button
            type="button"
            aria-label={`Remove ${card.label}`}
            onClick={handleRemove}
            className="rounded p-1.5 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)] transition-colors cursor-pointer"
            title="Remove add-on completely"
          >
            <X size={18} weight="bold" />
          </button>
        </div>
      )}
      <ConfirmDialog
        open={confirmRemoveAddonOpen}
        onOpenChange={setConfirmRemoveAddonOpen}
        title="Remove Add-on"
        message={`Are you sure you want to remove "${card.label}" from this quotation?`}
        confirmLabel="Remove"
        onConfirm={performRemove}
      />
    </article>
  );
}


