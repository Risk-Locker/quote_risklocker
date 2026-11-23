"use client";

import React, { useEffect, useId, useState } from "react";
import {
  ArrowCounterClockwise,
  CheckCircle,
  Lightning,
  ShieldCheck,
  Sparkle,
  SpinnerGap,
  X,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

export interface AddCustomBenefitModalProps {
  open: boolean;
  onClose: () => void;
  initialPlacement?: "foc" | "addon";
  companyName?: string | null;
  vehicleType?: string | null;
  onAdd: (data: {
    label: string;
    value: string;
    price: number | null;
    description: string;
    icon_hint: string;
    isSelected: boolean;
    cost_status?: "included" | "paid";
    placement?: "foc" | "addon";
  }) => void;
}

const ICON_OPTIONS = [
  { hint: "windscreen", label: "Windscreen" },
  { hint: "towing", label: "Towing" },
  { hint: "pa", label: "PA Plus" },
  { hint: "special_perils", label: "Perils" },
  { hint: "betterment", label: "Betterment" },
  { hint: "accessories", label: "Accessories" },
  { hint: "llp", label: "Passenger" },
  { hint: "respray", label: "Respray" },
  { hint: "generic", label: "Standard" },
];

export function AddCustomBenefitModal({
  open,
  onClose,
  onAdd,
  initialPlacement = "foc",
  companyName,
  vehicleType,
}: AddCustomBenefitModalProps) {
  const titleId = useId();
  const [placement, setPlacement] = useState<"foc" | "addon">(initialPlacement);
  const [label, setLabel] = useState("");
  const [value, setValue] = useState("");
  const [priceStr, setPriceStr] = useState("");
  const [description, setDescription] = useState("");
  const [iconHint, setIconHint] = useState("generic");
  const [isSelected, setIsSelected] = useState(true);

  const [aiPolishing, setAiPolishing] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiSource, setAiSource] = useState<"gemini" | "fallback" | null>(null);
  const [previousDescription, setPreviousDescription] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setPlacement(initialPlacement);
      setAiError(null);
    }
  }, [open, initialPlacement]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !aiPolishing) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, aiPolishing, onClose]);

  if (!open) return null;

  const resetFormState = () => {
    setLabel("");
    setValue("");
    setPriceStr("");
    setDescription("");
    setIconHint("generic");
    setIsSelected(true);
    setAiError(null);
    setAiSource(null);
    setPreviousDescription(null);
  };

  const handleClose = () => {
    if (aiPolishing) return;
    setAiError(null);
    onClose();
  };

  const handleAiEnhance = async () => {
    const cleanLabel = label.trim() || description.trim();
    if (!cleanLabel || aiPolishing) return;
    setAiPolishing(true);
    setAiError(null);
    const snapshotBeforeAi = description;
    try {
      const res = await api<{ description: string; source: "gemini" | "fallback" }>(
        "/copilot/polish-benefit-description",
        {
          method: "POST",
          body: JSON.stringify({
            label: label.trim() || cleanLabel.slice(0, 80),
            coverage_limit: value.trim(),
            draft_description: description.trim(),
            placement,
            insurer_name: companyName || undefined,
            vehicle_type: vehicleType || undefined,
          }),
        }
      );
      if (res?.description) {
        setPreviousDescription(snapshotBeforeAi);
        setDescription(res.description);
        setAiSource(res.source);
      }
    } catch (err) {
      setAiError(apiErrorMessage(err));
    } finally {
      setAiPolishing(false);
    }
  };

  const handleUndoAi = () => {
    if (previousDescription === null) return;
    setDescription(previousDescription);
    setPreviousDescription(null);
    setAiSource(null);
    setAiError(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanLabel = label.trim();
    if (!cleanLabel) return;

    let cleanPrice: number | null = null;
    if (placement === "addon" && priceStr.trim()) {
      const num = parseFloat(priceStr.replace(/[^0-9.]/g, ""));
      if (!isNaN(num) && num > 0) {
        cleanPrice = num;
      }
    }

    onAdd({
      label: cleanLabel,
      value: value.trim(),
      price: cleanPrice,
      description: description.trim(),
      icon_hint: iconHint,
      isSelected: placement === "foc" ? true : isSelected,
      cost_status: placement === "foc" ? "included" : "paid",
      placement,
    });

    resetFormState();
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-150"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div className="relative w-full max-w-lg rounded-xl border border-[var(--rl-border)] bg-white p-5 shadow-xl">
        <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
          <div className="flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded-lg bg-red-50 text-[var(--rl-red)]">
              <Sparkle size={18} weight="fill" />
            </div>
            <div>
              <h2 id={titleId} className="text-sm font-bold text-[var(--rl-text-strong)]">
                Add Custom Add-on / Benefit
              </h2>
              <p className="text-[11px] text-[var(--rl-text-muted)]">
                Create a custom add-on with exact pricing, coverage limit, and Design 2 parity.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close modal"
            className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-neutral-100 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
          >
            <X size={16} weight="bold" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3.5">
          <div>
            <label className="block text-xs font-bold text-[var(--rl-text-strong)] mb-1.5">
              Placement Section <span className="text-[var(--rl-red)]">*</span>
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => {
                  setPlacement("foc");
                  setPriceStr("");
                }}
                className={`p-2.5 rounded-lg border text-left flex items-start gap-2 cursor-pointer transition-all ${placement === "foc"
                  ? "border-emerald-500 bg-emerald-50/70 text-emerald-900 ring-1 ring-emerald-500"
                  : "border-gray-200 hover:border-gray-300 text-[var(--rl-text-muted)]"
                  }`}
              >
                <ShieldCheck size={18} className="text-emerald-600 mt-0.5 shrink-0" weight="fill" />
                <div>
                  <div className="text-xs font-bold text-emerald-950">Free Added Coverage (Box 1)</div>
                  <div className="text-[10px] text-gray-500 leading-tight">Top-Right Card · Complimentary Inclusions</div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setPlacement("addon")}
                className={`p-2.5 rounded-lg border text-left flex items-start gap-2 cursor-pointer transition-all ${placement === "addon"
                  ? "border-amber-500 bg-amber-50/70 text-amber-900 ring-1 ring-amber-500"
                  : "border-gray-200 hover:border-gray-300 text-[var(--rl-text-muted)]"
                  }`}
              >
                <Lightning size={18} className="text-amber-600 mt-0.5 shrink-0" weight="fill" />
                <div>
                  <div className="text-xs font-bold text-amber-950">Add-On Upgrades (Box 2)</div>
                  <div className="text-[10px] text-gray-500 leading-tight">Bottom 24-Card Matrix · Paid / Optional</div>
                </div>
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-[var(--rl-text-strong)] mb-1">
              Benefit Name <span className="text-[var(--rl-red)]">*</span>
            </label>
            <Input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Waiver of Betterment, Special Perils, Emergency Towing"
              autoFocus
              required
              className="text-xs"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-[var(--rl-text-strong)] mb-1">
                Coverage Limit / Sum
              </label>
              <Input
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="e.g. 5 years, RM 2,000, 50 km"
                className="text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-[var(--rl-text-strong)] mb-1">
                Price (RM)
              </label>
              <Input
                value={placement === "foc" ? "FOC (Included)" : priceStr}
                disabled={placement === "foc"}
                onChange={(e) => setPriceStr(e.target.value)}
                placeholder="e.g. 150.00 (or 0 for FOC)"
                className={`text-xs font-mono ${placement === "foc" ? "bg-emerald-50 text-emerald-800 font-bold cursor-not-allowed" : ""}`}
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between gap-2 mb-1">
              <div className="flex items-center gap-2">
                <label className="block text-xs font-bold text-[var(--rl-text-strong)]">
                  Description
                </label>
                {aiSource && (
                  <span className="inline-flex items-center gap-1 rounded bg-red-50 border border-red-200 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--rl-red)]">
                    <Sparkle size={10} weight="fill" />
                    {aiSource === "gemini" ? "Enhanced with AI" : "Suggested phrasing"}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5">
                {previousDescription !== null && (
                  <button
                    type="button"
                    onClick={handleUndoAi}
                    className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:bg-neutral-100 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
                    title="Restore your original description text"
                  >
                    <ArrowCounterClockwise size={12} weight="bold" />
                    <span>Undo AI</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleAiEnhance}
                  disabled={aiPolishing || (!label.trim() && !description.trim())}
                  className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-red-50/90 hover:bg-red-100 px-2.5 py-1 text-[11px] font-bold text-[var(--rl-red)] transition-colors cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed shadow-2xs"
                  title="Scan Benefit Name, Limit, and your short note to polish into a customer-ready description"
                >
                  {aiPolishing ? (
                    <SpinnerGap size={12} className="animate-spin" weight="bold" />
                  ) : (
                    <Sparkle size={12} weight="fill" />
                  )}
                  <span>{aiPolishing ? "Enhancing..." : "AI Enhance"}</span>
                </button>
              </div>
            </div>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => {
                setDescription(e.target.value);
                if (aiSource) setAiSource(null);
              }}
              placeholder="Write a short note (e.g. Upto 5 years of waiver) then click AI Enhance, or enter full description..."
              className="w-full rounded-md border border-[var(--rl-border)] p-2 text-xs leading-relaxed text-[var(--rl-text-strong)] focus:outline-none focus:ring-1 focus:ring-[var(--rl-red)]"
            />
            {aiError && (
              <p className="mt-1 text-[11px] font-medium text-[var(--rl-red)]" role="alert">
                {aiError}
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-bold text-[var(--rl-text-strong)] mb-1.5">
              Icon Concept Hint
            </label>
            <div className="flex flex-wrap gap-1.5">
              {ICON_OPTIONS.map((opt) => (
                <button
                  key={opt.hint}
                  type="button"
                  onClick={() => setIconHint(opt.hint)}
                  className={`px-2.5 py-1 text-[11px] font-semibold rounded-md border transition-all cursor-pointer ${iconHint === opt.hint
                    ? "border-[var(--rl-red)] bg-red-50 text-[var(--rl-red)] font-bold shadow-2xs"
                    : "border-[var(--rl-border)] bg-neutral-50 text-[var(--rl-text-muted)] hover:bg-neutral-100"
                    }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {placement === "addon" ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={(e) => setIsSelected(e.target.checked)}
                  className="size-4 rounded text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                />
                <div>
                  <span className="text-xs font-bold text-emerald-950 block">
                    Selected / Ticked on Quotation (Float to Top #01)
                  </span>
                  <span className="text-[10px] text-emerald-800">
                    Adds price to total payable and pushes as a ticked rider in Design 2 matrix.
                  </span>
                </div>
              </label>
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50/60 p-2.5 text-xs text-emerald-950">
              <CheckCircle size={16} weight="fill" className="text-emerald-600 shrink-0" />
              <span>Added directly to <strong>Box 1 (Free Added Coverage)</strong> at no customer charge.</span>
            </div>
          )}

          <div className="flex items-center justify-end gap-2 border-t border-[var(--rl-border)] pt-3">
            <Button type="button" variant="secondary" size="sm" onClick={handleClose} className="text-xs">
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!label.trim() || aiPolishing}
              className="bg-[var(--rl-red)] hover:bg-red-700 text-white font-bold text-xs"
            >
              {placement === "foc" ? "Add Free Coverage" : "Add Add-on"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
