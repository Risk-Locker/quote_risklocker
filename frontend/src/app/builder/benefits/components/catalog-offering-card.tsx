"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowCounterClockwise,
  ArrowsLeftRight,
  Plus,
  ShieldCheck,
  Sparkle,
  SpinnerGap,
  Trash,
} from "@phosphor-icons/react";
import type { ConceptSummary, OfferingSummary } from "@/types/benefits";

const ROLE_FALLBACK: Record<string, string> = {
  base: "included",
  optional: "addon_option",
  package_component: "bundle_component",
  upgrade: "upgrade",
};

function cleanCoverageValue(val?: string | null): string {
  if (!val) return "";
  const s = String(val).trim();
  if (!s || /^(?:included|optional|foc|as quoted|selected|standard|none|null|-|—)$/i.test(s)) {
    return "";
  }
  return s;
}

function formatPriceInput(price?: OfferingSummary["optional_price"]): string {
  if (!price) return "";
  if (price.type === "formula") {
    return String(price.display_text || (price as Record<string, unknown>).expression || price.formula || "");
  }
  if (price.value !== undefined && price.value !== null && Number(price.value) > 0) {
    return `RM ${Number(price.value).toFixed(2)}`;
  }
  if (price.amount !== undefined && price.amount !== null && String(price.amount).trim() !== "" && Number(price.amount) > 0) {
    return `RM ${price.amount}`;
  }
  return "";
}

export interface CatalogOfferingCardProps {
  concept: ConceptSummary;
  offering?: OfferingSummary;
  mode: "included" | "addon_option";
  baselineDesc?: string | null;
  baselineCost?: string | null;
  isExcludedByProfile?: boolean;
  isSavingCard?: boolean;
  disabled?: boolean;
  fileUrl: (url: string) => string;
  onAdd: (concept: ConceptSummary, targetRole: "included" | "addon_option") => void;
  onMoveRole: (offering: OfferingSummary, targetRole: "included" | "addon_option") => void;
  onRequestRemove: (offering: OfferingSummary, concept: ConceptSummary) => void;
  onUpdateLabel: (offering: OfferingSummary, newLabel: string) => void;
  onUpdateValue: (offering: OfferingSummary, newValue: string) => void;
  onUpdatePrice: (offering: OfferingSummary, newPrice: string) => void;
  onUpdateDescription: (offering: OfferingSummary, newDesc: string) => void;
  onSelectVariant: (offering: OfferingSummary, variant: string) => void;
}

export function CatalogOfferingCard({
  concept,
  offering,
  mode,
  baselineDesc = null,
  baselineCost = null,
  isExcludedByProfile = false,
  isSavingCard = false,
  disabled = false,
  fileUrl,
  onAdd,
  onMoveRole,
  onRequestRemove,
  onUpdateLabel,
  onUpdateValue,
  onUpdatePrice,
  onUpdateDescription,
  onSelectVariant,
}: CatalogOfferingCardProps) {
  const effectiveRole = offering ? (offering.role || ROLE_FALLBACK[offering.offering_kind] || "included") : null;
  const isActive = Boolean(offering && effectiveRole === mode);
  const activeInOtherRole = Boolean(offering && effectiveRole && effectiveRole !== mode);
  const hasVariants = Boolean(concept.variants && concept.variants.length > 0);
  const isTempId = Boolean(offering?.id?.startsWith("temp-"));

  // Local controlled inputs so background refreshes/revisions never steal focus
  const serverLabel = offering?.label_override?.trim() || "";
  const serverValue = cleanCoverageValue(offering?.display_value);
  const serverPrice = formatPriceInput(offering?.optional_price);
  const hasCustomDesc = Boolean(offering?.description_override && offering.description_override.trim().length > 0);
  const fallbackDesc = baselineDesc || concept.description || "";
  const serverDesc = hasCustomDesc ? (offering?.description_override || "") : fallbackDesc;

  const [labelText, setLabelText] = useState(serverLabel);
  const [valueText, setValueText] = useState(serverValue);
  const [priceText, setPriceText] = useState(serverPrice);
  const [descText, setDescText] = useState(serverDesc);

  const labelFocusedRef = useRef(false);
  const valueFocusedRef = useRef(false);
  const priceFocusedRef = useRef(false);
  const descDirtyRef = useRef(false);
  const descTextRef = useRef(descText);
  descTextRef.current = descText;
  const descTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!labelFocusedRef.current) setLabelText(serverLabel);
  }, [serverLabel, offering?.id]);

  useEffect(() => {
    if (!valueFocusedRef.current) setValueText(serverValue);
  }, [serverValue, offering?.id]);

  useEffect(() => {
    if (!priceFocusedRef.current) setPriceText(serverPrice);
  }, [serverPrice, offering?.id]);

  useEffect(() => {
    if (!descDirtyRef.current) {
      setDescText(serverDesc);
      descTextRef.current = serverDesc;
    }
  }, [serverDesc, offering?.id]);

  const flushDescSave = useCallback(() => {
    if (descTimerRef.current) {
      clearTimeout(descTimerRef.current);
      descTimerRef.current = null;
    }
    if (!descDirtyRef.current || !offering) return;
    descDirtyRef.current = false;

    const clean = descTextRef.current.trim();
    const currentOverride = (offering.description_override || "").trim();
    if (clean === currentOverride) return;
    if (clean === "" || clean === fallbackDesc.trim()) {
      onUpdateDescription(offering, "");
    } else {
      onUpdateDescription(offering, clean);
    }
  }, [offering, fallbackDesc, onUpdateDescription]);

  useEffect(() => {
    return () => {
      if (descTimerRef.current) clearTimeout(descTimerRef.current);
    };
  }, []);

  if (!isActive || !offering) {
    return (
      <div
        className={`group relative flex flex-col justify-between rounded-[var(--rl-radius-sm)] border p-3 transition-all ${
          activeInOtherRole
            ? "border-amber-300/80 bg-amber-50/40 dark:bg-amber-950/20"
            : "border-[var(--rl-border)] bg-[var(--rl-surface)] opacity-80 hover:opacity-100 hover:border-[var(--rl-text-muted)]"
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2.5 min-w-0">
            <div
              className={`grid h-7 w-7 shrink-0 place-items-center rounded-[4px] border ${
                concept.default_asset?.url
                  ? "bg-white border-[var(--rl-border)]"
                  : "bg-[var(--rl-bg)] text-[var(--rl-text-muted)] border-[var(--rl-border)]"
              }`}
            >
              {concept.default_asset?.url ? (
                <img src={fileUrl(concept.default_asset.url)} alt={concept.label} loading="lazy" className="h-4 w-4 object-contain" />
              ) : mode === "included" ? (
                <ShieldCheck size={16} />
              ) : (
                <Sparkle size={16} />
              )}
            </div>
            <div className="min-w-0">
              <span className="font-semibold text-xs text-[var(--rl-text-strong)] line-clamp-2 leading-snug break-words">
                {concept.label}
              </span>
              {isExcludedByProfile && (
                <span className="mt-0.5 inline-block rounded bg-amber-100 text-amber-900 border border-amber-300 dark:bg-amber-950 dark:text-amber-300 px-1 py-0.2 text-[8.5px] font-bold uppercase tracking-wider">
                  Excluded
                </span>
              )}
            </div>
          </div>

          {activeInOtherRole && offering ? (
            <button
              type="button"
              disabled={disabled || isSavingCard}
              onClick={() => onMoveRole(offering, mode)}
              className="shrink-0 inline-flex items-center gap-1 rounded-[4px] border border-amber-400 bg-white dark:bg-[var(--rl-surface)] px-2 py-1 text-[10px] font-semibold text-amber-900 dark:text-amber-200 hover:bg-amber-100 disabled:opacity-50"
              title={`Currently in ${mode === "included" ? "Add-ons" : "Defaults"}. Click to move here.`}
            >
              <ArrowsLeftRight size={11} />
              <span>Move here</span>
            </button>
          ) : (
            <button
              type="button"
              disabled={disabled || isSavingCard}
              onClick={() => onAdd(concept, mode)}
              className="shrink-0 inline-flex items-center gap-1 rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-bg)] px-2 py-1 text-[10px] font-semibold text-[var(--rl-text-strong)] hover:bg-[var(--rl-black)] hover:text-white hover:border-[var(--rl-black)] transition-colors disabled:opacity-50"
            >
              {isSavingCard ? <SpinnerGap size={11} className="animate-spin" /> : <Plus size={11} weight="bold" />}
              <span>Add</span>
            </button>
          )}
        </div>

        {fallbackDesc && (
          <div className="mt-2 text-[10px] text-[var(--rl-text-muted)] line-clamp-2 leading-snug break-words" title={fallbackDesc}>
            {fallbackDesc}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="group relative flex flex-col justify-between rounded-[var(--rl-radius-sm)] border border-[var(--rl-black)] bg-[var(--rl-bg)] p-3 shadow-sm ring-1 ring-[var(--rl-black)] transition-all">
      <div>
        {/* Card Header: Concept Name + Move + Explicit Remove */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div
              className={`grid h-7 w-7 shrink-0 place-items-center rounded-[4px] border ${
                concept.default_asset?.url
                  ? "bg-white border-[var(--rl-border)]"
                  : "bg-[var(--rl-black)] text-white border-[var(--rl-black)]"
              }`}
            >
              {concept.default_asset?.url ? (
                <img src={fileUrl(concept.default_asset.url)} alt={concept.label} loading="lazy" className="h-4 w-4 object-contain" />
              ) : mode === "included" ? (
                <ShieldCheck size={16} />
              ) : (
                <Sparkle size={16} />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-semibold text-xs text-[var(--rl-text-strong)] line-clamp-2 leading-snug break-words">
                  {offering.label_override?.trim() || concept.label}
                </span>
                {isSavingCard && (
                  <SpinnerGap size={12} className="animate-spin text-[var(--rl-text-muted)] shrink-0" />
                )}
              </div>
              {isExcludedByProfile && (
                <span className="mt-0.5 inline-block rounded bg-amber-100 text-amber-900 border border-amber-300 dark:bg-amber-950 dark:text-amber-300 px-1 py-0.2 text-[8.5px] font-bold uppercase tracking-wider">
                  Excluded
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              disabled={disabled || isSavingCard || isTempId}
              onClick={() => onMoveRole(offering, mode === "included" ? "addon_option" : "included")}
              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-1 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:border-[var(--rl-black)] transition-colors disabled:opacity-40"
              title={mode === "included" ? "Move to Add-ons" : "Move to Default / Included"}
            >
              <ArrowsLeftRight size={12} />
            </button>
            <button
              type="button"
              disabled={disabled || isSavingCard || isTempId}
              onClick={() => onRequestRemove(offering, concept)}
              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-1 text-[var(--rl-text-muted)] hover:text-[var(--rl-red)] hover:border-red-300 hover:bg-red-50/70 transition-colors disabled:opacity-40"
              title="Remove benefit from this configuration"
            >
              <Trash size={12} />
            </button>
          </div>
        </div>

        {/* Plan Variations 1-Click Switcher */}
        {hasVariants && (
          <div className="mt-2 flex flex-wrap gap-1">
            {concept.variants!.map((variant) => {
              const isVariantActive = offering.label_override?.includes(variant);
              return (
                <button
                  key={variant}
                  type="button"
                  disabled={disabled || isTempId}
                  onClick={() => onSelectVariant(offering, variant)}
                  className={`rounded-[4px] px-1.5 py-0.5 text-[10px] font-semibold transition-all ${
                    isVariantActive
                      ? "bg-[var(--rl-black)] text-white"
                      : "bg-[var(--rl-surface)] border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  {variant}
                </button>
              );
            })}
          </div>
        )}

        {/* Display Title Override */}
        <div className="mt-2 space-y-0.5">
          <div className="flex items-center justify-between text-[9.5px] text-[var(--rl-text-muted)]">
            <span>Display Title Override</span>
            {serverLabel && (
              <button
                type="button"
                disabled={disabled || isTempId}
                onClick={() => {
                  setLabelText("");
                  onUpdateLabel(offering, "");
                }}
                className="hover:text-[var(--rl-red)] underline"
                title="Reset title to concept label"
              >
                Reset
              </button>
            )}
          </div>
          <input
            type="text"
            value={labelText}
            disabled={disabled || isTempId}
            onFocus={() => {
              labelFocusedRef.current = true;
            }}
            onChange={(e) => setLabelText(e.target.value)}
            onBlur={() => {
              labelFocusedRef.current = false;
              const clean = labelText.trim();
              const nextVal = clean === concept.label.trim() ? "" : clean;
              if (nextVal !== serverLabel) {
                onUpdateLabel(offering, nextVal);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
            }}
            className="w-full rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[10.5px] font-medium text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
            placeholder={concept.label}
          />
        </div>
      </div>

      {/* Coverage Value / Limit & Price Row with 1-Click None / Free */}
      <div className="mt-2 space-y-1.5 pt-1.5 border-t border-[var(--rl-border)]/60">
        <div className="flex items-center gap-1">
          <div className="flex-1 min-w-0 flex items-center gap-1">
            <input
              type="text"
              value={valueText}
              disabled={disabled || isTempId}
              onFocus={() => {
                valueFocusedRef.current = true;
              }}
              onChange={(e) => setValueText(e.target.value)}
              onBlur={() => {
                valueFocusedRef.current = false;
                const clean = cleanCoverageValue(valueText);
                if (clean !== serverValue) {
                  setValueText(clean);
                  onUpdateValue(offering, clean);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              }}
              className="w-full rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-bold text-[var(--rl-text-strong)] min-w-0 focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
              placeholder="No limit / coverage"
              title="Coverage value or limit (e.g. Up to 10 Years, 200 km, RM 1,500)"
            />
            {(valueText || serverValue) && (
              <button
                type="button"
                disabled={disabled || isTempId}
                onClick={() => {
                  setValueText("");
                  onUpdateValue(offering, "");
                }}
                className="shrink-0 rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[9.5px] font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-red)] hover:border-red-300"
                title="Clear coverage value to None"
              >
                None
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1">
          <input
            type="text"
            value={priceText}
            disabled={disabled || isTempId}
            onFocus={() => {
              priceFocusedRef.current = true;
            }}
            onChange={(e) => setPriceText(e.target.value)}
            onBlur={() => {
              priceFocusedRef.current = false;
              const clean = priceText.trim();
              if (clean !== serverPrice.trim()) {
                onUpdatePrice(offering, clean);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
            }}
            className="flex-1 min-w-0 rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-bold text-[var(--rl-red)] text-right focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
            placeholder={(baselineCost || (mode === "included" ? "0 RM (Free)" : "Optional"))}
            title="Price / Cost (leave blank or click Free for RM 0)"
          />
          {(priceText || serverPrice) && (
            <button
              type="button"
              disabled={disabled || isTempId}
              onClick={() => {
                setPriceText("");
                onUpdatePrice(offering, "");
              }}
              className="shrink-0 rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[9.5px] font-semibold text-emerald-700 hover:bg-emerald-50"
              title="Set price to Free / RM 0"
            >
              Free
            </button>
          )}
          <span className="text-[9.5px] font-semibold text-[var(--rl-text-muted)] shrink-0 ml-auto">
            {mode === "included" ? "Default" : "Add-on"}
          </span>
        </div>
      </div>

      {/* Inline Description Editor */}
      <div className="mt-2 pt-1.5 border-t border-[var(--rl-border)]/50 space-y-1">
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-[var(--rl-text-muted)] font-medium">Description</span>
          {hasCustomDesc ? (
            <div className="flex items-center gap-1">
              <span className="rounded bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 px-1 py-0.2 text-[9.5px] font-semibold">
                Tier Custom
              </span>
              <button
                type="button"
                disabled={disabled || isTempId}
                title="Reset to baseline/global description"
                onClick={() => {
                  if (descTimerRef.current) {
                    clearTimeout(descTimerRef.current);
                    descTimerRef.current = null;
                  }
                  descDirtyRef.current = false;
                  setDescText(fallbackDesc);
                  descTextRef.current = fallbackDesc;
                  onUpdateDescription(offering, "");
                }}
                className="text-[var(--rl-text-muted)] hover:text-[var(--rl-red)] transition-colors p-0.5"
              >
                <ArrowCounterClockwise size={11} />
              </button>
            </div>
          ) : baselineDesc ? (
            <span className="rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 px-1 py-0.2 text-[9.5px] font-semibold">
              Company Baseline
            </span>
          ) : concept.description ? (
            <span className="rounded bg-[var(--rl-surface)] border border-[var(--rl-border)] text-[var(--rl-text-muted)] px-1 py-0.2 text-[9.5px]">
              Global Default
            </span>
          ) : (
            <span className="text-[9.5px] text-[var(--rl-text-muted)] italic">None</span>
          )}
        </div>
        <input
          type="text"
          value={descText}
          disabled={disabled || isTempId}
          onChange={(e) => {
            const val = e.target.value;
            setDescText(val);
            descTextRef.current = val;
            descDirtyRef.current = true;
            if (descTimerRef.current) clearTimeout(descTimerRef.current);
            descTimerRef.current = setTimeout(() => {
              flushDescSave();
            }, 600);
          }}
          onBlur={flushDescSave}
          className="w-full rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[10.5px] text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)] placeholder:italic focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
          placeholder={fallbackDesc || "Enter short description..."}
        />
      </div>
    </div>
  );
}
