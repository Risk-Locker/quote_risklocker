"use client";

import React, { useEffect, useState } from "react";
import { ShieldCheck, FloppyDisk } from "@phosphor-icons/react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const TOWING_PRESETS = ["Unlimited", "200 KM", "150 KM", "RM 500", "RM 400", "RM 300", "No Towing"];

export interface EditCoverNoteModalProps {
  isOpen: boolean;
  onClose: () => void;
  covernotePolicy: Record<string, any> | null | undefined;
  roadTax: number;
  runnerFee: number;
  includeRoadTax?: boolean;
  includeRunnerFee?: boolean;
  onSave: (patch: Record<string, any>) => Promise<void>;
}

export function EditCoverNoteModal({
  isOpen,
  onClose,
  covernotePolicy,
  roadTax,
  runnerFee,
  includeRoadTax = true,
  includeRunnerFee = true,
  onSave,
}: EditCoverNoteModalProps) {
  const [policyNumber, setPolicyNumber] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sumInsured, setSumInsured] = useState("");
  const [motorPremium, setMotorPremium] = useState("");
  const [agreedValue, setAgreedValue] = useState(false);
  const [excess, setExcess] = useState("");
  const [windscreen, setWindscreen] = useState("");
  const [towingLimit, setTowingLimit] = useState("Unlimited");
  const [specialPerils, setSpecialPerils] = useState<"Included" | "Not Included">("Not Included");
  const [llpLlop, setLlpLlop] = useState<"Included" | "Not Included">("Not Included");
  const [waiverBetterment, setWaiverBetterment] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !covernotePolicy) return;
    setPolicyNumber(String(covernotePolicy.policy_number || ""));
    setCompanyName(String(covernotePolicy.company_name || ""));
    setStartDate(String(covernotePolicy.coverage_start_date || "").slice(0, 10));
    setEndDate(String(covernotePolicy.coverage_end_date || "").slice(0, 10));
    setSumInsured(covernotePolicy.sum_insured != null ? String(covernotePolicy.sum_insured) : "0");
    const mp = covernotePolicy.exact_motor_premium ?? covernotePolicy.motor_premium ?? 0;
    setMotorPremium(String(mp));
    setAgreedValue(Boolean(covernotePolicy.agreed_value || covernotePolicy.valuation_type === "agreed_value"));
    setExcess(covernotePolicy.excess != null ? String(covernotePolicy.excess) : "0");
    setWindscreen(covernotePolicy.windscreen_sum_insured != null ? String(covernotePolicy.windscreen_sum_insured) : "0");
    setTowingLimit(String(covernotePolicy.towing_limit || covernotePolicy.towing_km || "Unlimited"));
    setSpecialPerils(
      covernotePolicy.special_perils && !String(covernotePolicy.special_perils).toLowerCase().includes("not")
        ? "Included"
        : "Not Included"
    );
    setLlpLlop(
      covernotePolicy.llp_llop && !String(covernotePolicy.llp_llop).toLowerCase().includes("not")
        ? "Included"
        : "Not Included"
    );
    setWaiverBetterment(Boolean(covernotePolicy.waiver_betterment));
    setError(null);
  }, [isOpen, covernotePolicy]);

  if (!covernotePolicy) return null;

  const effRt = includeRoadTax ? Number(roadTax || 0) : 0;
  const effRf = includeRunnerFee ? Number(runnerFee || 0) : 0;
  const parsedMp = parseFloat(motorPremium || "0");
  const previewTotal = (Number.isFinite(parsedMp) && parsedMp >= 0 ? parsedMp : 0) + effRt + effRf;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const parsedSi = parseFloat(sumInsured || "0");
    const parsedPrem = parseFloat(motorPremium || "0");
    const parsedEx = parseFloat(excess || "0");
    const parsedWs = parseFloat(windscreen || "0");
    if (!Number.isFinite(parsedSi) || parsedSi < 0) {
      setError("Sum Insured must be a non-negative amount.");
      return;
    }
    if (!Number.isFinite(parsedPrem) || parsedPrem < 0) {
      setError("Motor Premium must be a non-negative amount.");
      return;
    }
    if (!Number.isFinite(parsedEx) || parsedEx < 0) {
      setError("Excess must be a non-negative amount.");
      return;
    }
    if (!Number.isFinite(parsedWs) || parsedWs < 0) {
      setError("Windscreen limit must be a non-negative amount.");
      return;
    }
    if (startDate && endDate && endDate < startDate) {
      setError("Cover End Date cannot be earlier than Cover Start Date.");
      return;
    }

    try {
      setSaving(true);
      await onSave({
        policy_number: policyNumber.trim(),
        company_name: companyName.trim() || covernotePolicy.company_name,
        ...(startDate ? { coverage_start_date: startDate } : {}),
        ...(endDate ? { coverage_end_date: endDate } : {}),
        sum_insured: parsedSi,
        motor_premium: parsedPrem,
        agreed_value: agreedValue,
        valuation_type: agreedValue ? "agreed_value" : "market_value",
        excess: parsedEx,
        windscreen_sum_insured: parsedWs,
        towing_limit: towingLimit.trim() || "Unlimited",
        special_perils: specialPerils,
        llp_llop: llpLlop,
        waiver_betterment: waiverBetterment,
      });
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to update Cover Note details.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(next) => {
        if (!next && !saving) onClose();
      }}
      title="Edit Issued Cover Note"
      description="Updates sync directly across Current Policy, Tenure renewal records, linked Draft Workspace, and Client PDFs."
      maxWidth="2xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="max-h-[65vh] overflow-y-auto pr-1 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                Cover Note / Policy #
              </label>
              <Input
                value={policyNumber}
                onChange={(e) => setPolicyNumber(e.target.value)}
                placeholder="e.g. CN-2026-0001"
                className="font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                Underwriter / Insurer
              </label>
              <Input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g. Lonpac Insurance"
                className="text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                Cover Start Date
              </label>
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                Cover End Date
              </label>
              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                Sum Insured (RM)
              </label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={sumInsured}
                onChange={(e) => setSumInsured(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                Motor Premium (RM)
              </label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={motorPremium}
                onChange={(e) => setMotorPremium(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                Excess (RM)
              </label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={excess}
                onChange={(e) => setExcess(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                Agreed Value
              </label>
              <div className="grid grid-cols-2 gap-1.5">
                <button
                  type="button"
                  onClick={() => setAgreedValue(true)}
                  className={`py-2 px-3 rounded-[6px] text-xs font-semibold border cursor-pointer ${
                    agreedValue ? "bg-[#1b1717] text-white border-[#1b1717]" : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea]"
                  }`}
                >
                  Yes (Agreed)
                </button>
                <button
                  type="button"
                  onClick={() => setAgreedValue(false)}
                  className={`py-2 px-3 rounded-[6px] text-xs font-semibold border cursor-pointer ${
                    !agreedValue ? "bg-[#1b1717] text-white border-[#1b1717]" : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea]"
                  }`}
                >
                  No (Market)
                </button>
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                Betterment Co-pay
              </label>
              <div className="grid grid-cols-2 gap-1.5">
                <button
                  type="button"
                  onClick={() => setWaiverBetterment(false)}
                  className={`py-2 px-3 rounded-[6px] text-xs font-semibold border cursor-pointer ${
                    !waiverBetterment ? "bg-[#1b1717] text-white border-[#1b1717]" : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea]"
                  }`}
                >
                  Yes (Standard %)
                </button>
                <button
                  type="button"
                  onClick={() => setWaiverBetterment(true)}
                  className={`py-2 px-3 rounded-[6px] text-xs font-semibold border cursor-pointer ${
                    waiverBetterment ? "bg-[#1b1717] text-white border-[#1b1717]" : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea]"
                  }`}
                >
                  No (Waived 0%)
                </button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                Windscreen (RM)
              </label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={windscreen}
                onChange={(e) => setWindscreen(e.target.value)}
                className="font-mono text-xs"
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                Special Perils
              </label>
              <div className="grid grid-cols-2 gap-1.5">
                {(["Included", "Not Included"] as const).map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setSpecialPerils(opt)}
                    className={`py-2 px-2 rounded-[6px] text-[11px] font-semibold border cursor-pointer ${
                      specialPerils === opt ? "bg-[#1b1717] text-white border-[#1b1717]" : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea]"
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
                LLP / LLOP
              </label>
              <div className="grid grid-cols-2 gap-1.5">
                {(["Included", "Not Included"] as const).map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setLlpLlop(opt)}
                    className={`py-2 px-2 rounded-[6px] text-[11px] font-semibold border cursor-pointer ${
                      llpLlop === opt ? "bg-[#1b1717] text-white border-[#1b1717]" : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea]"
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
              Towing Limit
            </label>
            <div className="flex flex-wrap gap-1 mb-1.5">
              {TOWING_PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setTowingLimit(preset)}
                  className={`px-2 py-0.5 rounded-[6px] text-[10px] font-semibold border cursor-pointer ${
                    towingLimit.toLowerCase() === preset.toLowerCase()
                      ? "bg-[#1b1717] text-white border-[#1b1717]"
                      : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea]"
                  }`}
                >
                  {preset}
                </button>
              ))}
            </div>
            <Input
              value={towingLimit}
              onChange={(e) => setTowingLimit(e.target.value)}
              placeholder="e.g. Unlimited, 200 KM, RM 500"
              className="text-xs"
            />
          </div>

          <div className="rounded-[8px] border border-[var(--rl-border)] bg-[var(--rl-bg)] px-3 py-2 flex items-center justify-between text-xs">
            <span className="font-semibold text-[var(--rl-text)] flex items-center gap-1.5">
              <ShieldCheck size={14} weight="bold" className="text-emerald-700" />
              Total Payable (incl. RM {(effRt + effRf).toFixed(2)} Roadtax + Runner Fee):
            </span>
            <span className="font-mono font-bold text-sm text-[var(--rl-text-strong)]">
              RM {previewTotal.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
        </div>

        {error && <p className="text-xs font-semibold text-[#ed1c24]">{error}</p>}

        <div className="flex justify-end gap-2 pt-2 border-t border-[var(--rl-border)]">
          <Button type="button" variant="secondary" size="sm" disabled={saving} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" size="sm" loading={saving}>
            <FloppyDisk size={14} weight="bold" />
            <span>Save Cover Note</span>
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
