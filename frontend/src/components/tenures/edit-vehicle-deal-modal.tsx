"use client";

import React, { useState, useEffect } from "react";
import {
  Car,
  IdentificationCard,
  User,
  CurrencyDollar,
  X,
  CheckCircle,
  Sparkle,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import type { TenureRow, PicItem } from "./tenure-timeline-ledger";
import { STAGE_ORDER } from "./tenure-timeline-ledger";

interface EditVehicleDealModalProps {
  isOpen: boolean;
  onClose: () => void;
  tenure: TenureRow | null;
  pics?: PicItem[];
  onSave: (tenureId: string, updates: Partial<TenureRow>) => Promise<void>;
}

export function EditVehicleDealModal({
  isOpen,
  onClose,
  tenure,
  pics = [],
  onSave,
}: EditVehicleDealModalProps) {
  const [customerName, setCustomerName] = useState("");
  const [customerIcNo, setCustomerIcNo] = useState("");
  const [vehicleNo, setVehicleNo] = useState("");
  const [chassisNo, setChassisNo] = useState("");
  const [engineNo, setEngineNo] = useState("");
  const [carBrand, setCarBrand] = useState("");
  const [carModel, setCarModel] = useState("");
  const [engineCc, setEngineCc] = useState("");
  const [stage, setStage] = useState("Quotations");
  const [businessType, setBusinessType] = useState("Renewal");
  const [picId, setPicId] = useState<string>("");
  const [subAgentName, setSubAgentName] = useState("");
  const [roadTax, setRoadTax] = useState("0");
  const [runnerFee, setRunnerFee] = useState("0");
  const [comment, setComment] = useState("");
  const [clientPreferenceNotes, setClientPreferenceNotes] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (tenure) {
      setCustomerName(tenure.customer_name || "");
      setCustomerIcNo(tenure.customer_ic_no || "");
      setVehicleNo(tenure.vehicle_no || "");
      setChassisNo(tenure.chassis_no || "");
      setEngineNo(tenure.engine_no || "");
      setCarBrand(tenure.car_brand || "");
      setCarModel(tenure.car_model || "");
      setEngineCc(tenure.engine_cc || "");
      setStage(tenure.stage || "Quotations");
      setBusinessType(tenure.business_type || "Renewal");
      setPicId(tenure.pic_id || "");
      setSubAgentName(tenure.sub_agent_name || "");
      setRoadTax(String(tenure.road_tax || 0));
      setRunnerFee(String(tenure.runner_fee || 0));
      setComment(tenure.comment || "");
      setClientPreferenceNotes(tenure.client_preference_notes || tenure.notes || "");
    }
  }, [tenure]);

  if (!isOpen || !tenure) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customerName.trim() || !vehicleNo.trim()) {
      alert("Customer Name and Vehicle Plate are required.");
      return;
    }

    setSaving(true);
    try {
      const selectedPic = pics.find((p) => p.id === picId);
      await onSave(tenure.id, {
        customer_name: customerName.trim(),
        customer_ic_no: customerIcNo.trim() || undefined,
        vehicle_no: vehicleNo.trim().toUpperCase(),
        chassis_no: chassisNo.trim() || undefined,
        engine_no: engineNo.trim() || undefined,
        car_brand: carBrand.trim() || undefined,
        car_model: carModel.trim() || undefined,
        engine_cc: engineCc.trim() || undefined,
        stage,
        business_type: businessType,
        pic_id: picId || null,
        sub_agent_name: selectedPic ? selectedPic.name : subAgentName.trim(),
        road_tax: parseFloat(roadTax) || 0,
        runner_fee: parseFloat(runnerFee) || 0,
        comment: comment.trim(),
        client_preference_notes: clientPreferenceNotes.trim(),
      });
      onClose();
    } catch (err: any) {
      console.error("Failed to update deal:", err);
      alert("Failed to update deal: " + (err.message || "Unknown error"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-white rounded-xl shadow-2xl border border-neutral-200 overflow-hidden my-8 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200 bg-neutral-50/80">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-black text-white">
              <Car size={18} weight="bold" />
            </div>
            <div>
              <h2 className="text-base font-bold text-neutral-900">
                Edit Deal &amp; Customer Information
              </h2>
              <p className="text-xs text-neutral-500 font-mono">
                {tenure.vehicle_no} · Expiry: {tenure.expiry_month}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-700 hover:bg-neutral-200/60 transition-colors"
          >
            <X size={18} weight="bold" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Customer Identity Section */}
          <div className="p-4 rounded-lg bg-blue-50/50 border border-blue-100 space-y-3">
            <div className="flex items-center gap-2 text-xs font-bold text-blue-900 uppercase tracking-wide">
              <User size={14} weight="bold" />
              <span>Customer Master Profile (Propagates Everywhere)</span>
            </div>
            <p className="text-[11px] text-blue-700 leading-relaxed">
              Modifying the Customer Name or Government IC propagates instantly across all policy tenures, marketing comparisons, and quotation drafts linked to this customer account.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div>
                <label className="block text-xs font-semibold text-neutral-700 mb-1">
                  Customer / Policyholder Name *
                </label>
                <input
                  type="text"
                  required
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="e.g. TAN JIN AUN"
                  className="w-full h-8 px-2.5 text-xs font-medium rounded border border-neutral-300 bg-white focus:border-black focus:ring-1 focus:ring-black outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-700 mb-1">
                  IC / Passport / BRN
                </label>
                <input
                  type="text"
                  value={customerIcNo}
                  onChange={(e) => setCustomerIcNo(e.target.value)}
                  placeholder="e.g. 821021085432"
                  className="w-full h-8 px-2.5 text-xs font-mono font-medium rounded border border-neutral-300 bg-white focus:border-black focus:ring-1 focus:ring-black outline-none"
                />
              </div>
            </div>
          </div>

          {/* Vehicle & Deal Attributes */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-neutral-700 mb-1">
                Vehicle Plate No *
              </label>
              <input
                type="text"
                required
                value={vehicleNo}
                onChange={(e) => setVehicleNo(e.target.value.toUpperCase())}
                placeholder="e.g. JYH8773"
                className="w-full h-8 px-2.5 text-xs font-mono font-bold rounded border border-neutral-300 bg-white focus:border-black focus:ring-1 focus:ring-black outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-neutral-700 mb-1">
                Lifecycle Stage
              </label>
              <select
                value={stage}
                onChange={(e) => setStage(e.target.value)}
                className="w-full h-8 px-2 text-xs font-semibold rounded border border-neutral-300 bg-white focus:border-black outline-none cursor-pointer"
              >
                {STAGE_ORDER.map((st: string) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-neutral-700 mb-1">
                Business Type
              </label>
              <select
                value={businessType}
                onChange={(e) => setBusinessType(e.target.value)}
                className="w-full h-8 px-2 text-xs font-semibold rounded border border-neutral-300 bg-white focus:border-black outline-none cursor-pointer"
              >
                <option value="Renewal">Renewal</option>
                <option value="New Business">New Business</option>
              </select>
            </div>
          </div>

          {/* Vehicle Technical Specifications */}
          <div className="p-3.5 rounded-lg bg-neutral-50 border border-neutral-200 space-y-2.5">
            <span className="text-[11px] font-bold text-neutral-700 uppercase tracking-wide flex items-center gap-1.5">
              <Car size={13} weight="bold" />
              <span>Vehicle Specifications &amp; Identifiers</span>
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-neutral-600 mb-1">
                  Chassis / VIN Number
                </label>
                <input
                  type="text"
                  value={chassisNo}
                  onChange={(e) => setChassisNo(e.target.value.toUpperCase())}
                  placeholder="e.g. PRBDB21B5KD..."
                  className="w-full h-8 px-2.5 text-xs font-mono font-medium rounded border border-neutral-300 bg-white focus:border-black outline-none uppercase"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-neutral-600 mb-1">
                  Engine Number
                </label>
                <input
                  type="text"
                  value={engineNo}
                  onChange={(e) => setEngineNo(e.target.value.toUpperCase())}
                  placeholder="e.g. 2NR-FE..."
                  className="w-full h-8 px-2.5 text-xs font-mono font-medium rounded border border-neutral-300 bg-white focus:border-black outline-none uppercase"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-neutral-600 mb-1">
                  Make &amp; Model
                </label>
                <input
                  type="text"
                  value={carModel}
                  onChange={(e) => setCarModel(e.target.value)}
                  placeholder="e.g. TOYOTA VIOS 1.5G"
                  className="w-full h-8 px-2.5 text-xs font-medium rounded border border-neutral-300 bg-white focus:border-black outline-none"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-neutral-600 mb-1">
                  Engine Capacity (CC)
                </label>
                <input
                  type="text"
                  value={engineCc}
                  onChange={(e) => setEngineCc(e.target.value)}
                  placeholder="e.g. 1496"
                  className="w-full h-8 px-2.5 text-xs font-mono font-medium rounded border border-neutral-300 bg-white focus:border-black outline-none"
                />
              </div>
            </div>
          </div>

          {/* Person In Charge & Cost Details */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-neutral-700 mb-1">
                SubAgent / PIC
              </label>
              <select
                value={picId}
                onChange={(e) => {
                  setPicId(e.target.value);
                  const found = pics.find((p) => p.id === e.target.value);
                  if (found) setSubAgentName(found.name);
                }}
                className="w-full h-8 px-2 text-xs font-semibold rounded border border-neutral-300 bg-white focus:border-black outline-none cursor-pointer"
              >
                <option value="">Direct Agency / In-House</option>
                {pics.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} {p.agency_group ? `(${p.agency_group})` : ""}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-neutral-700 mb-1">
                Road Tax (RM)
              </label>
              <input
                type="number"
                step="0.01"
                value={roadTax}
                onChange={(e) => setRoadTax(e.target.value)}
                className="w-full h-8 px-2.5 text-xs font-mono font-medium rounded border border-neutral-300 bg-white focus:border-black outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-neutral-700 mb-1">
                Runner Fee (RM)
              </label>
              <input
                type="number"
                step="0.01"
                value={runnerFee}
                onChange={(e) => setRunnerFee(e.target.value)}
                className="w-full h-8 px-2.5 text-xs font-mono font-medium rounded border border-neutral-300 bg-white focus:border-black outline-none"
              />
            </div>
          </div>

          {/* Operational Comment & Habitual Pattern Notes */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-neutral-700 mb-1">
                Operational Comment
              </label>
              <input
                type="text"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="e.g. Sent via WhatsApp, awaiting client decision"
                className="w-full h-8 px-2.5 text-xs font-medium rounded border border-neutral-300 bg-white focus:border-black outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-neutral-700 mb-1">
                Habitual / Preference Notes
              </label>
              <input
                type="text"
                value={clientPreferenceNotes}
                onChange={(e) => setClientPreferenceNotes(e.target.value)}
                placeholder="e.g. Needs windscreen RM1,700 and flood cover"
                className="w-full h-8 px-2.5 text-xs font-medium rounded border border-neutral-300 bg-white focus:border-black outline-none"
              />
            </div>
          </div>

          {/* Modal Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-neutral-200">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onClose}
              disabled={saving}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={saving}
              icon={<CheckCircle size={15} weight="bold" />}
              className="bg-black hover:bg-neutral-800 text-white text-xs font-semibold shadow-xs"
            >
              {saving ? "Saving Changes..." : "Save & Propagate Everywhere"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
