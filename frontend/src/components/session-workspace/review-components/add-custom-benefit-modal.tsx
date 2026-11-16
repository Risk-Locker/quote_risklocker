"use client";

import React, { useState } from "react";
import {
  Car,
  Check,
  CheckCircle,
  Lightning,
  ShieldCheck,
  Sparkle,
  Wrench,
  X,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface AddCustomBenefitModalProps {
  open: boolean;
  onClose: () => void;
  initialPlacement?: "foc" | "addon";
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

export function AddCustomBenefitModal({ open, onClose, onAdd, initialPlacement = "foc" }: AddCustomBenefitModalProps) {
  const [placement, setPlacement] = useState<"foc" | "addon">(initialPlacement);
  const [label, setLabel] = useState("");
  const [value, setValue] = useState("");
  const [priceStr, setPriceStr] = useState("");
  const [description, setDescription] = useState("");
  const [iconHint, setIconHint] = useState("generic");
  const [isSelected, setIsSelected] = useState(true);

  React.useEffect(() => {
    if (open) {
      setPlacement(initialPlacement);
    }
  }, [open, initialPlacement]);

  if (!open) return null;

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
      isSelected: true,
      cost_status: placement === "foc" ? "included" : (cleanPrice ? "paid" : "included"),
      placement,
    });

    setLabel("");
    setValue("");
    setPriceStr("");
    setDescription("");
    setIconHint("generic");
    setIsSelected(true);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="relative w-full max-w-lg rounded-xl border border-[var(--rl-border)] bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
          <div className="flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded-lg bg-red-50 text-[var(--rl-red)]">
              <Sparkle size={18} weight="fill" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Add Custom Add-on / Benefit</h2>
              <p className="text-[11px] text-[var(--rl-text-muted)]">
                Create a custom add-on with exact pricing, coverage limit, and Design 2 parity.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-neutral-100 hover:text-[var(--rl-text-strong)] transition-colors"
          >
            <X size={16} weight="bold" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
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
                className={`p-2.5 rounded-lg border text-left flex items-start gap-2 cursor-pointer transition-all ${
                  placement === "foc"
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
                className={`p-2.5 rounded-lg border text-left flex items-start gap-2 cursor-pointer transition-all ${
                  placement === "addon"
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
              placeholder="e.g. Special Perils (Flood & Storm), Emergency Towing, Tyre & Rim"
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
                placeholder="e.g. RM 2,000, 50 km, Full Coverage"
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
            <label className="block text-xs font-bold text-[var(--rl-text-strong)] mb-1">
              Description
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Full reimbursement for accidental tyre puncture and rim damage up to RM 2,000 per policy year."
              className="w-full rounded-md border border-[var(--rl-border)] p-2 text-xs leading-relaxed text-[var(--rl-text-strong)] focus:outline-none focus:ring-1 focus:ring-[var(--rl-red)]"
            />
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
                  className={`px-2.5 py-1 text-[11px] font-semibold rounded-md border transition-all ${
                    iconHint === opt.hint
                      ? "border-[var(--rl-red)] bg-red-50 text-[var(--rl-red)] font-bold shadow-2xs"
                      : "border-[var(--rl-border)] bg-neutral-50 text-[var(--rl-text-muted)] hover:bg-neutral-100"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

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

          <div className="flex items-center justify-end gap-2 border-t border-[var(--rl-border)] pt-3">
            <Button type="button" variant="secondary" size="sm" onClick={onClose} className="text-xs">
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!label.trim()}
              className="bg-[var(--rl-red)] hover:bg-red-700 text-white font-bold text-xs"
            >
              Add Add-on
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
