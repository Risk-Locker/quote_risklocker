"use client";

import React, { useState, useEffect } from "react";
import { X, Receipt, CheckCircle, XCircle, ArrowsClockwise, Sparkle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface AdjustFeesModalProps {
  isOpen: boolean;
  onClose: () => void;
  tenureId: string;
  initialRoadTax: number;
  initialRunnerFee: number;
  initialIncludeRoadTax: boolean;
  initialIncludeRunnerFee: boolean;
  engineCapacity?: string;
  vehicleType?: string;
  onSaved: (updatedData: any) => void;
}

export function AdjustFeesModal({
  isOpen,
  onClose,
  tenureId,
  initialRoadTax,
  initialRunnerFee,
  initialIncludeRoadTax,
  initialIncludeRunnerFee,
  engineCapacity,
  vehicleType,
  onSaved,
}: AdjustFeesModalProps) {
  const [roadTax, setRoadTax] = useState<string>(String(initialRoadTax ?? 0));
  const [runnerFee, setRunnerFee] = useState<string>(String(initialRunnerFee ?? 0));
  const [includeRoadTax, setIncludeRoadTax] = useState<boolean>(initialIncludeRoadTax ?? true);
  const [includeRunnerFee, setIncludeRunnerFee] = useState<boolean>(initialIncludeRunnerFee ?? true);
  const [isSaving, setIsSaving] = useState(false);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [recalcFeedback, setRecalcFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setRoadTax(String(initialRoadTax ?? 0));
      setRunnerFee(String(initialRunnerFee ?? 0));
      setIncludeRoadTax(initialIncludeRoadTax ?? true);
      setIncludeRunnerFee(initialIncludeRunnerFee ?? true);
      setRecalcFeedback(null);
    }
  }, [isOpen, initialRoadTax, initialRunnerFee, initialIncludeRoadTax, initialIncludeRunnerFee]);

  if (!isOpen) return null;

  const parsedRt = parseFloat(roadTax) || 0;
  const parsedRf = parseFloat(runnerFee) || 0;
  const effectiveRt = includeRoadTax ? parsedRt : 0;
  const effectiveRf = includeRunnerFee ? parsedRf : 0;
  const totalFixed = effectiveRt + effectiveRf;

  const handleRecalculateJPJ = async () => {
    try {
      setIsRecalculating(true);
      setRecalcFeedback(null);
      const res = await api<{ road_tax: number; formatted_capacity?: string }>(
        "/comparison/calculate-road-tax",
        {
          method: "POST",
          body: JSON.stringify({
            capacity: engineCapacity,
            vehicle_type: vehicleType || "Car",
          }),
        }
      );
      if (res && typeof res.road_tax === "number") {
        setRoadTax(res.road_tax.toFixed(2));
        setRecalcFeedback(`Recalculated: RM ${res.road_tax.toFixed(2)} (${res.formatted_capacity || engineCapacity || "Standard"})`);
      }
    } catch (e: any) {
      setRecalcFeedback("JPJ calc failed: " + (e.message || String(e)));
    } finally {
      setIsRecalculating(false);
    }
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      const res = await api<any>(`/comparison/${tenureId}/toggle-fees`, {
        method: "POST",
        body: JSON.stringify({
          road_tax: parsedRt,
          runner_fee: parsedRf,
          include_road_tax: includeRoadTax,
          include_runner_fee: includeRunnerFee,
        }),
      });
      onSaved(res);
      onClose();
    } catch (e: any) {
      alert("Failed to save fee settings: " + (e.message || String(e)));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 no-print animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl border border-neutral-200 max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#e5e5ea] bg-[#f5f5f7]">
          <div>
            <h3 className="text-base font-bold text-[#1b1717] flex items-center gap-2">
              <Receipt size={20} weight="fill" className="text-[#1b1717]" />
              Adjust Fixed Fees &amp; Road Tax
            </h3>
            <p className="text-xs text-[#6e6e73]">
              Configure government road tax and runner service fees for this deal
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-xl border border-neutral-300 hover:bg-neutral-200 text-neutral-600 transition-colors cursor-pointer"
          >
            <X size={18} weight="bold" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Section 1: Road Tax */}
          <div className={`p-4 rounded-2xl border transition-all ${includeRoadTax ? "bg-white border-[#e5e5ea] shadow-2xs" : "bg-neutral-50 border-neutral-200 opacity-80"}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-[#1b1717]">Road Tax (JPJ)</span>
                {engineCapacity && (
                  <span className="text-[11px] font-mono text-[#6e6e73] bg-[#f5f5f7] px-2 py-0.5 rounded border border-[#e5e5ea]">
                    {engineCapacity}
                  </span>
                )}
              </div>
              <label className="flex items-center gap-1.5 text-xs font-semibold cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={includeRoadTax}
                  onChange={(e) => setIncludeRoadTax(e.target.checked)}
                  className="rounded border-[#e5e5ea] text-[#1b1717] focus:ring-0 size-4 cursor-pointer"
                />
                <span className={includeRoadTax ? "text-emerald-700" : "text-neutral-500"}>
                  {includeRoadTax ? "Included" : "Excluded"}
                </span>
              </label>
            </div>

            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-bold text-[#6e6e73]">RM</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  disabled={!includeRoadTax}
                  value={roadTax}
                  onChange={(e) => setRoadTax(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 rounded-xl border border-neutral-300 font-mono text-sm font-bold text-[#1b1717] focus:border-[#1b1717] focus:ring-1 focus:ring-[#1b1717] outline-none disabled:bg-neutral-100 disabled:text-neutral-400"
                />
              </div>

              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={handleRecalculateJPJ}
                loading={isRecalculating}
                icon={<ArrowsClockwise size={14} weight="bold" className={isRecalculating ? "animate-spin" : ""} />}
                className="text-xs font-semibold shrink-0 border-[#e5e5ea] bg-[#f5f5f7] hover:bg-neutral-200"
                title="Recalculate road tax based on engine capacity"
              >
                Recalculate JPJ
              </Button>
            </div>

            {recalcFeedback && (
              <p className="mt-2 text-xs font-medium text-blue-700 bg-blue-50 px-2.5 py-1 rounded-lg border border-blue-200">
                {recalcFeedback}
              </p>
            )}

            {/* Quick Presets */}
            <div className="mt-3 flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] text-[#6e6e73]">Presets:</span>
              {[20, 70, 90, 200, 280, 380].map((val) => (
                <button
                  key={val}
                  type="button"
                  disabled={!includeRoadTax}
                  onClick={() => setRoadTax(String(val))}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold transition-all cursor-pointer ${
                    parsedRt === val && includeRoadTax
                      ? "bg-[#1b1717] text-white"
                      : "bg-[#f5f5f7] hover:bg-neutral-200 text-[#454545] border border-[#e5e5ea]"
                  }`}
                >
                  RM {val}
                </button>
              ))}
            </div>
          </div>

          {/* Section 2: Runner Fee */}
          <div className={`p-4 rounded-2xl border transition-all ${includeRunnerFee ? "bg-white border-[#e5e5ea] shadow-2xs" : "bg-neutral-50 border-neutral-200 opacity-80"}`}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-bold text-[#1b1717]">Runner / Service Fee</span>
              <label className="flex items-center gap-1.5 text-xs font-semibold cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={includeRunnerFee}
                  onChange={(e) => setIncludeRunnerFee(e.target.checked)}
                  className="rounded border-[#e5e5ea] text-[#1b1717] focus:ring-0 size-4 cursor-pointer"
                />
                <span className={includeRunnerFee ? "text-emerald-700" : "text-neutral-500"}>
                  {includeRunnerFee ? "Included" : "Excluded"}
                </span>
              </label>
            </div>

            <div className="relative mb-3">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-bold text-[#6e6e73]">RM</span>
              <input
                type="number"
                step="0.01"
                min="0"
                disabled={!includeRunnerFee}
                value={runnerFee}
                onChange={(e) => setRunnerFee(e.target.value)}
                className="w-full pl-10 pr-3 py-2 rounded-xl border border-neutral-300 font-mono text-sm font-bold text-[#1b1717] focus:border-[#1b1717] focus:ring-1 focus:ring-[#1b1717] outline-none disabled:bg-neutral-100 disabled:text-neutral-400"
              />
            </div>

            {/* Presets */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] text-[#6e6e73]">Presets:</span>
              {[
                { label: "MyKad (RM 10)", val: 10 },
                { label: "Passport (RM 20)", val: 20 },
                { label: "Corporate (RM 50)", val: 50 },
                { label: "Free (RM 0)", val: 0 },
              ].map((p) => (
                <button
                  key={p.val}
                  type="button"
                  disabled={!includeRunnerFee}
                  onClick={() => setRunnerFee(String(p.val))}
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-all cursor-pointer ${
                    parsedRf === p.val && includeRunnerFee
                      ? "bg-[#1b1717] text-white"
                      : "bg-[#f5f5f7] hover:bg-neutral-200 text-[#454545] border border-[#e5e5ea]"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Summary Box */}
          <div className="p-3.5 rounded-2xl bg-[#f5f5f7] border border-[#e5e5ea] flex items-center justify-between">
            <span className="text-xs font-semibold text-[#454545]">Effective Fixed Fees Added to Total:</span>
            <span className="text-base font-mono font-bold text-[#1b1717]">
              RM {totalFixed.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-2.5 px-6 py-4 border-t border-[#e5e5ea] bg-[#f5f5f7]">
          <Button variant="secondary" size="sm" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleSave}
            loading={isSaving}
            className="bg-[#1b1717] hover:bg-black text-white font-semibold"
          >
            Save &amp; Update Matrix
          </Button>
        </div>
      </div>
    </div>
  );
}

