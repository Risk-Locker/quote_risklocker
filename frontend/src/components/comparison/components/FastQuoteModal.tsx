"use client";

import { useState, useId } from "react";
import {
  X,
  Lightning,
  FloppyDisk,
  CircleNotch,
  CaretDown,
  CaretUp,
  ShieldCheck,
  Check,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type { TenureSpec } from "../types";

interface FastQuoteModalProps {
  isOpen: boolean;
  onClose: () => void;
  tenure: TenureSpec;
  onSuccess: () => Promise<void> | void;
}

const COMMON_INSURERS: Array<{ name: string; defaultTowing: string }> = [
  { name: "AmAssurance", defaultTowing: "365km" },
  { name: "STMB", defaultTowing: "50km" },
  { name: "Kurnia", defaultTowing: "200km" },
  { name: "Etiqa", defaultTowing: "200km" },
  { name: "Lonpac", defaultTowing: "RM400" },
  { name: "Berjaya Sompo", defaultTowing: "RM300" },
  { name: "Tune Protect", defaultTowing: "200km" },
  { name: "QBE", defaultTowing: "RM500" },
  { name: "Allianz", defaultTowing: "Unlimited" },
];

const TOWING_PRESETS = [
  "50km",
  "100km",
  "150km",
  "200km",
  "365km",
  "RM300",
  "RM400",
  "RM500",
  "RM1,000",
  "Unlimited",
];

export function FastQuoteModal({
  isOpen,
  onClose,
  tenure,
  onSuccess,
}: FastQuoteModalProps) {
  const [selectedInsurer, setSelectedInsurer] = useState("AmAssurance");
  const [customInsurer, setCustomInsurer] = useState("");
  const [sumInsured, setSumInsured] = useState("");
  const [motorPremium, setMotorPremium] = useState("");
  const [towingLimit, setTowingLimit] = useState("365km");
  const [valuationType, setValuationType] = useState<"market_value" | "agreed_value">("agreed_value");
  const [excess, setExcess] = useState("0");
  const [quotationNo, setQuotationNo] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleInsurerChange = (name: string) => {
    setSelectedInsurer(name);
    const match = COMMON_INSURERS.find((i) => i.name === name);
    if (match) {
      setTowingLimit(match.defaultTowing);
    }
  };

  const finalInsurerName = selectedInsurer === "Other" ? customInsurer.trim() : selectedInsurer;

  // Live estimated total
  const numPrem = parseFloat(motorPremium) || 0;
  const numRt = tenure.include_road_tax !== false ? (tenure.road_tax || 0) : 0;
  const numRf = tenure.include_runner_fee !== false ? (tenure.runner_fee || 0) : 0;
  const estimatedTotal = Math.max(0, numPrem + numRt + numRf - (tenure.quotation_discount || 0));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!finalInsurerName) {
      setErrorMsg("Please select or enter an insurer name.");
      return;
    }
    const parsedSum = parseFloat(sumInsured);
    if (isNaN(parsedSum) || parsedSum <= 0) {
      setErrorMsg("Please enter a valid Sum Insured (> 0).");
      return;
    }
    const parsedPrem = parseFloat(motorPremium);
    if (isNaN(parsedPrem) || parsedPrem < 0) {
      setErrorMsg("Please enter a valid Motor Premium.");
      return;
    }

    try {
      setSaving(true);
      setErrorMsg(null);

      await api(`/comparison/${tenure.id}/entry`, {
        method: "POST",
        body: JSON.stringify({
          company_name: finalInsurerName,
          sum_insured: parsedSum,
          motor_premium: parsedPrem,
          towing_limit: towingLimit || "Unlimited",
          valuation_type: valuationType,
          agreed_value: valuationType === "agreed_value",
          waiver_betterment: false,
          excess: parseFloat(excess) || 0,
          source_quotation_no: quotationNo.trim() || null,
          is_manual: true,
        }),
      });

      await onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to save fast quote.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto no-print">
      <div className="bg-white rounded-2xl shadow-2xl border border-neutral-200 max-w-lg w-full flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#e5e5ea] bg-[#f5f5f7]">
          <div className="flex items-center gap-2">
            <span className="w-7 h-7 rounded-lg bg-[#1b1717] text-white flex items-center justify-center">
              <Lightning size={16} weight="fill" className="text-amber-400" />
            </span>
            <div>
              <h3 className="text-sm font-bold text-[#1b1717]">Fast Quote (30-Sec Manual Fallback)</h3>
              <p className="text-[11px] text-[#6e6e73]">
                {tenure.vehicle_no} • {tenure.customer_name}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-neutral-400 hover:text-[#1b1717] hover:bg-neutral-200/60 transition-colors"
          >
            <X size={16} weight="bold" />
          </button>
        </div>

        {/* Error Banner */}
        {errorMsg && (
          <div className="px-5 py-2.5 bg-red-50 border-b border-red-200 text-xs font-semibold text-red-700">
            {errorMsg}
          </div>
        )}

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Insurer Picker */}
          <div>
            <label className="text-[11px] font-bold text-[#454545] uppercase tracking-wider block mb-1.5">
              1. Underwriter / Insurer
            </label>
            <div className="grid grid-cols-3 gap-1.5">
              {COMMON_INSURERS.map((ins) => (
                <button
                  key={ins.name}
                  type="button"
                  onClick={() => handleInsurerChange(ins.name)}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-all text-center truncate ${
                    selectedInsurer === ins.name
                      ? "bg-[#1b1717] text-white border-[#1b1717] shadow-xs"
                      : "bg-[#f5f5f7] text-[#454545] border-[#e5e5ea] hover:bg-neutral-200/50"
                  }`}
                >
                  {ins.name}
                </button>
              ))}
              <button
                type="button"
                onClick={() => handleInsurerChange("Other")}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-all text-center ${
                  selectedInsurer === "Other"
                    ? "bg-[#1b1717] text-white border-[#1b1717] shadow-xs"
                    : "bg-[#f5f5f7] text-[#454545] border-[#e5e5ea] hover:bg-neutral-200/50"
                }`}
              >
                Other...
              </button>
            </div>
            {selectedInsurer === "Other" && (
              <input
                type="text"
                value={customInsurer}
                onChange={(e) => setCustomInsurer(e.target.value)}
                placeholder="Enter Underwriter Name (e.g. Tokio Marine)"
                className="mt-2 w-full px-3 py-2 text-xs rounded-lg border border-[#e5e5ea] focus:border-[#1b1717] focus:ring-1 focus:ring-[#1b1717] outline-hidden"
                autoFocus
              />
            )}
          </div>

          {/* Sum Insured & Motor Premium */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-bold text-[#454545] uppercase tracking-wider block mb-1">
                2. Sum Insured (RM)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                required
                value={sumInsured}
                onChange={(e) => setSumInsured(e.target.value)}
                placeholder="e.g. 50000.00"
                className="w-full px-3 py-2 text-xs font-mono font-bold rounded-lg border border-[#e5e5ea] focus:border-[#1b1717] focus:ring-1 focus:ring-[#1b1717] outline-hidden"
              />
            </div>
            <div>
              <label className="text-[11px] font-bold text-[#454545] uppercase tracking-wider block mb-1">
                3. Motor Premium (RM)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                required
                value={motorPremium}
                onChange={(e) => setMotorPremium(e.target.value)}
                placeholder="e.g. 1420.35"
                className="w-full px-3 py-2 text-xs font-mono font-bold rounded-lg border border-[#e5e5ea] focus:border-[#1b1717] focus:ring-1 focus:ring-[#1b1717] outline-hidden"
              />
            </div>
          </div>

          {/* Towing Entitlement */}
          <div>
            <label className="text-[11px] font-bold text-[#454545] uppercase tracking-wider block mb-1">
              4. Towing Entitlement
            </label>
            <div className="flex gap-1.5 flex-wrap">
              {TOWING_PRESETS.slice(0, 6).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTowingLimit(t)}
                  className={`px-2 py-1 rounded text-[11px] font-semibold border transition-all ${
                    towingLimit === t
                      ? "bg-[#1b1717] text-white border-[#1b1717]"
                      : "bg-[#f5f5f7] text-[#454545] border-[#e5e5ea] hover:bg-neutral-200/50"
                  }`}
                >
                  {t}
                </button>
              ))}
              <input
                type="text"
                value={towingLimit}
                onChange={(e) => setTowingLimit(e.target.value)}
                placeholder="Custom towing"
                className="w-24 px-2 py-1 text-[11px] font-mono rounded border border-[#e5e5ea] focus:border-[#1b1717] outline-hidden"
              />
            </div>
          </div>

          {/* Advanced Accordion Toggle */}
          <div className="pt-1">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-[#6e6e73] hover:text-[#1b1717] font-semibold flex items-center gap-1 transition-colors"
            >
              {showAdvanced ? <CaretUp size={12} weight="bold" /> : <CaretDown size={12} weight="bold" />}
              <span>{showAdvanced ? "Hide details" : "+ Details (Valuation, Excess, Ref)"}</span>
            </button>

            {showAdvanced && (
              <div className="mt-2.5 p-3 rounded-xl bg-[#f5f5f7] border border-[#e5e5ea] grid grid-cols-2 gap-3 text-xs animate-in fade-in duration-100">
                <div>
                  <label className="text-[10px] font-bold text-[#454545] uppercase block mb-1">
                    Valuation Type
                  </label>
                  <select
                    value={valuationType}
                    onChange={(e) => setValuationType(e.target.value as any)}
                    className="w-full px-2.5 py-1.5 rounded-lg border border-[#e5e5ea] bg-white font-medium outline-hidden"
                  >
                    <option value="agreed_value">Agreed Value [A]</option>
                    <option value="market_value">Market Value [M]</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-bold text-[#454545] uppercase block mb-1">
                    Excess (RM)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={excess}
                    onChange={(e) => setExcess(e.target.value)}
                    placeholder="0.00"
                    className="w-full px-2.5 py-1.5 rounded-lg border border-[#e5e5ea] bg-white font-mono outline-hidden"
                  />
                </div>
                <div className="col-span-2">
                  <label className="text-[10px] font-bold text-[#454545] uppercase block mb-1">
                    Quotation Ref / No (Optional)
                  </label>
                  <input
                    type="text"
                    value={quotationNo}
                    onChange={(e) => setQuotationNo(e.target.value)}
                    placeholder="e.g. Q-2026-AMGEN-889"
                    className="w-full px-2.5 py-1.5 rounded-lg border border-[#e5e5ea] bg-white font-mono outline-hidden"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Live Calculation Preview Banner */}
          <div className="rounded-xl p-3 bg-neutral-900 text-white flex items-center justify-between text-xs font-mono shadow-xs">
            <div>
              <span className="text-[10px] text-neutral-400 block uppercase font-sans">
                Estimated Total Payable
              </span>
              <span className="text-sm font-bold text-emerald-400">
                RM {estimatedTotal.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="text-right text-[10px] text-neutral-400 font-sans">
              <span>Incl. RT (RM {numRt.toFixed(2)}) + RF (RM {numRf.toFixed(2)})</span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#e5e5ea]">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              loading={saving}
              icon={<FloppyDisk size={14} weight="bold" />}
              className="bg-[#1b1717] hover:bg-black text-white font-semibold"
            >
              Add Quote
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
