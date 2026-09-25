"use client";

import React, { useState, useEffect } from "react";
import { ArrowCounterClockwise, Check, PencilSimple, Sparkle, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { fileUrl } from "@/lib/api";
import type { BenefitCardSummary } from "../types";

export function IncludedCard({
  card,
  index,
  assetUrl,
  selection,
  canUndo,
  onQueue,
}: {
  card: BenefitCardSummary;
  index: number;
  assetUrl?: string | null;
  selection?: { id: string; cost_status: string } | Record<string, unknown> | null;
  canUndo: boolean;
  onQueue: (operation: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) => void;
}) {
  const selectionId = selection && typeof selection === "object" && "id" in selection ? String(selection.id) : (card.selection_id || null);
  const pending = !selectionId || String(selectionId).startsWith("pending:");

  const isLimitHidden = !!(selection as any)?.typed_value_override?.hide_limit || !!(card as any).typed_value?.hide_limit;

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

  const handleTitleCommit = (newVal: string) => {
    setIsEditingTitle(false);
    const clean = newVal.trim();
    if (!clean || clean === card.label) return;
    flashSaved("title");
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, label: clean }, `benefits.${selectionId}.label`);
    } else if (card.offering_id) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, label: clean }, `benefits.offer.${card.offering_id}`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, label: clean }, `benefits.${targetId}.label`);
    }
  };

  const handleLimitCommit = (newVal: string) => {
    setIsEditingLimit(false);
    const clean = newVal.trim();
    flashSaved("limit");
    const typed = clean ? { type: "custom", display_text: clean } : null;
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, typed_value: typed }, `benefits.${selectionId}.limit`);
    } else if (card.offering_id) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, typed_value: typed }, `benefits.offer.${card.offering_id}`);
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
    } else if (card.offering_id) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, description: clean }, `benefits.offer.${card.offering_id}`);
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
      } else if (card.offering_id) {
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
    } else if (card.offering_id) {
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
      } else if (card.offering_id) {
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

  const handleMoveToAddon = () => {
    if (!window.confirm(`Are you sure you want to move "${card.label}" to add-ons?`)) return;
    if (selectionId) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "available_addon", cost_status: "paid" },
        `benefits.${selectionId}.state`,
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: "included" }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "paid" },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "removed", cost_status: "included" }
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

  const handleRemove = () => {
    if (!window.confirm(`Are you sure you want to remove "${card.label}" completely?`)) return;
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

  return (
    <article className={`group flex items-start justify-between gap-2.5 rounded-[var(--rl-radius-sm)] border p-2.5 shadow-xs transition-all ${card.is_detected
      ? "border-amber-300 bg-amber-50/50 ring-1 ring-amber-300/60"
      : "border-[var(--rl-border)] bg-[var(--rl-surface)] hover:border-[var(--rl-border-strong)]"
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
      {/* Body: title, detected badge, value, description, price */}
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
              <h3 className="text-xs font-bold text-[var(--rl-text-strong)] leading-tight truncate">{card.label}</h3>
              <button
                type="button"
                onClick={() => setIsEditingTitle(true)}
                className="opacity-0 group-hover/title:opacity-100 p-0.5 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-opacity cursor-pointer"
                title="Edit title"
              >
                <PencilSimple size={10} />
              </button>
            </div>
          )}
          {card.is_detected ? (
            <span className="rounded bg-amber-100 px-1 py-0.5 text-[9px] font-bold text-amber-800 ring-1 ring-amber-400/50 shrink-0">★ Detected</span>
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
            placeholder="Coverage (e.g. RM 1,000, 50 km)"
            value={limitInput}
            autoFocus
            onChange={(e) => setLimitInput(e.target.value)}
            onBlur={() => handleLimitCommit(limitInput)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleLimitCommit(limitInput);
              if (e.key === "Escape") { setIsEditingLimit(false); setLimitInput(card.value || ""); }
            }}
            className="h-5 w-44 rounded border border-[var(--rl-black)] px-1 font-mono text-[11px] font-bold text-[var(--rl-text-strong)] focus:outline-none mt-0.5"
          />
        ) : card.value && !["", "Included standard cover", "Included", "FOC", "As quoted", "Optional"].includes(card.value) && (/\d/.test(card.value) || /unlimited/i.test(card.value)) ? (
          <div className="group/limit flex items-center gap-1 mt-0.5">
            <p className={`text-[11px] font-bold leading-tight truncate transition-colors ${isLimitHidden ? "text-[var(--rl-text-muted)] line-through" : "text-[var(--rl-text-strong)]"}`}>
              {card.value}
            </p>
            <button
              type="button"
              onClick={() => setIsEditingLimit(true)}
              className="opacity-0 group-hover/limit:opacity-100 p-0.5 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-opacity cursor-pointer"
              title="Edit coverage limit"
            >
              <PencilSimple size={10} />
            </button>
          </div>
        ) : (
          <div className="group/limit flex items-center gap-1 mt-0.5">
            <button
              type="button"
              onClick={() => setIsEditingLimit(true)}
              className="opacity-0 group-hover:opacity-60 hover:!opacity-100 text-[10px] text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] flex items-center gap-0.5 transition-opacity cursor-pointer"
              title="Set coverage limit"
            >
              <PencilSimple size={9} />
              <span>+ Limit</span>
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
            <p className="text-[10px] text-[var(--rl-text-muted)] leading-snug line-clamp-2 flex-1">
              {card.description}
            </p>
            <button
              type="button"
              onClick={() => setIsEditingDesc(true)}
              className="opacity-0 group-hover/desc:opacity-100 p-0.5 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-opacity shrink-0 mt-0.5 cursor-pointer"
              title="Edit description"
            >
              <PencilSimple size={10} />
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setIsEditingDesc(true)}
            className="opacity-0 group-hover:opacity-60 hover:!opacity-100 text-[9px] text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] flex items-center gap-0.5 transition-opacity mt-0.5 cursor-pointer"
            title="Add description"
          >
            <PencilSimple size={9} />
            <span>+ Description</span>
          </button>
        )}

        {/* Price Tag & Revert Controls for Included/Purchased Add-ons */}
        {(currentPriceNum !== null || Boolean((card as any).is_extra) || card.cost_status === "paid") && (
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
                  className={`group/price flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold transition-colors ${currentPriceNum !== null ? "bg-amber-100/80 hover:bg-amber-200 text-amber-900" : "bg-neutral-100 hover:bg-neutral-200 text-neutral-600"}`}
                  title="Click to edit price (clear or 0 for FOC)"
                >
                  <span>{currentPriceNum !== null ? `RM ${currentPriceNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "FOC / Free"}</span>
                  <PencilSimple size={10} className="text-[var(--rl-text-muted)] group-hover/price:text-[var(--rl-black)]" />
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
        )}
      </div>
      {/* Actions */}
      <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
        <Button
          variant="secondary"
          size="sm"
          title="Move this benefit to Optional Add-ons"
          onClick={handleMoveToAddon}
          className="text-[11px] h-7 px-2"
        >
          → Add-on
        </Button>
        <button
          type="button"
          aria-label={`Remove ${card.label} from this quotation`}
          onClick={handleRemove}
          className="rounded-full p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)] transition-colors cursor-pointer"
          title="Remove benefit completely"
        >
          <X size={14} weight="bold" />
        </button>
      </div>
    </article>
  );
}

export function AddonCard({
  card,
  index,
  assetUrl,
  onQueue,
}: {
  card: BenefitCardSummary;
  index: number;
  assetUrl?: string | null;
  onQueue: (operation: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) => void;
}) {
  const selectionId = card.selection_id;
  const pending = !selectionId || String(selectionId).startsWith("pending:");

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

  const handleTitleCommit = (newVal: string) => {
    setIsEditingTitle(false);
    const clean = newVal.trim();
    if (!clean || clean === card.label) return;
    flashSaved("title");
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, label: clean }, `benefits.${selectionId}.label`);
    } else if (card.offering_id) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, label: clean }, `benefits.offer.${card.offering_id}`);
    } else if (selectionId || card.concept_key) {
      const targetId = selectionId || card.concept_key!;
      onQueue({ op: "benefit_update", selection_id: targetId, label: clean }, `benefits.${targetId}.label`);
    }
  };

  const handleLimitCommit = (newVal: string) => {
    setIsEditingLimit(false);
    const clean = newVal.trim();
    flashSaved("limit");
    const typed = clean ? { type: "custom", display_text: clean } : null;
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, typed_value: typed }, `benefits.${selectionId}.limit`);
    } else if (card.offering_id) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, typed_value: typed }, `benefits.offer.${card.offering_id}`);
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
    } else if (card.offering_id) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, description: clean }, `benefits.offer.${card.offering_id}`);
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

  const handleMoveToDefault = () => {
    const priceVal = card.price || card.optional_price || null;
    const costStatus = priceVal ? "paid" : "included";
    if (selectionId) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: costStatus, ...(priceVal ? { price: priceVal } : {}) },
        `benefits.${selectionId}.state`,
        { op: "benefit_update", selection_id: selectionId, state: "available_addon", cost_status: "paid" }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: costStatus, ...(priceVal ? { price: priceVal } : {}) },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "removed", cost_status: "included" }
      );
    } else {
      const customKey = `default:${card.concept_key || index}`;
      onQueue(
        { op: "create_custom_benefit", selection_key: customKey, state: "current", cost_status: costStatus, label: card.label, ...(priceVal ? { price: priceVal } : {}) },
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
              <h3 className="text-xs font-bold text-[var(--rl-text-strong)] leading-tight truncate">{card.label}</h3>
              <button
                type="button"
                onClick={() => setIsEditingTitle(true)}
                className="opacity-0 group-hover/title:opacity-100 p-0.5 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-opacity cursor-pointer"
                title="Edit title"
              >
                <PencilSimple size={10} />
              </button>
            </div>
          )}
          {card.is_detected ? (
            <span className="rounded bg-amber-100 px-1 py-0.5 text-[9px] font-bold text-amber-800 ring-1 ring-amber-400/50 shrink-0">★ Detected</span>
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
            placeholder="Coverage (e.g. RM 1,000, 50 km)"
            value={limitInput}
            autoFocus
            onChange={(e) => setLimitInput(e.target.value)}
            onBlur={() => handleLimitCommit(limitInput)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleLimitCommit(limitInput);
              if (e.key === "Escape") { setIsEditingLimit(false); setLimitInput(card.value || ""); }
            }}
            className="h-5 w-44 rounded border border-[var(--rl-black)] px-1 font-mono text-[11px] font-bold text-[var(--rl-text-strong)] focus:outline-none mt-0.5"
          />
        ) : card.value && !["", "Optional payable add-on", "Included", "FOC", "As quoted", "Optional"].includes(card.value) && (/\d/.test(card.value) || /unlimited/i.test(card.value)) ? (
          <div className="group/limit flex items-center gap-1 mt-0.5">
            <p className="text-[11px] font-bold text-[var(--rl-text-strong)] leading-tight truncate">
              {card.value}
            </p>
            <button
              type="button"
              onClick={() => setIsEditingLimit(true)}
              className="opacity-0 group-hover/limit:opacity-100 p-0.5 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-opacity cursor-pointer"
              title="Edit coverage limit"
            >
              <PencilSimple size={10} />
            </button>
          </div>
        ) : (
          <div className="group/limit flex items-center gap-1 mt-0.5">
            <button
              type="button"
              onClick={() => setIsEditingLimit(true)}
              className="opacity-0 group-hover:opacity-60 hover:!opacity-100 text-[10px] text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] flex items-center gap-0.5 transition-opacity cursor-pointer"
              title="Set coverage limit"
            >
              <PencilSimple size={9} />
              <span>+ Limit</span>
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
            <p className="text-[10px] text-[var(--rl-text-muted)] leading-snug line-clamp-2 flex-1">
              {card.description}
            </p>
            <button
              type="button"
              onClick={() => setIsEditingDesc(true)}
              className="opacity-0 group-hover/desc:opacity-100 p-0.5 rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] hover:bg-neutral-200/60 transition-opacity shrink-0 mt-0.5 cursor-pointer"
              title="Edit description"
            >
              <PencilSimple size={10} />
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setIsEditingDesc(true)}
            className="opacity-0 group-hover:opacity-60 hover:!opacity-100 text-[9px] text-[var(--rl-text-muted)] hover:text-[var(--rl-black)] flex items-center gap-0.5 transition-opacity mt-0.5 cursor-pointer"
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
      <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
        <Button
          size="sm"
          variant="secondary"
          title="Move to Default / FOC Benefits"
          onClick={handleMoveToDefault}
          className="text-[11px] h-7 px-2 group-hover:bg-[var(--rl-black)] group-hover:text-white"
        >
          ← Default/FOC
        </Button>
        <button
          type="button"
          aria-label={`Remove ${card.label}`}
          onClick={handleRemove}
          className="rounded-full p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)] transition-colors"
          title="Remove add-on completely"
        >
          <X size={14} weight="bold" />
        </button>
      </div>
    </article>
  );
}


