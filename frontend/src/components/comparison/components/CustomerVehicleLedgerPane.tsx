"use client";

import React from "react";
import {
  ArrowsClockwise,
  PencilSimple,
  IdentificationCard,
  Phone,
  MapPin,
  CheckCircle,
  FilePdf,
  FloppyDisk,
  X,
} from "@phosphor-icons/react";
import { fileUrl, api } from "@/lib/api";
import type { TenureSpec } from "../types";

interface CustomerVehicleLedgerPaneProps {
  tenure: TenureSpec;
  covernotePolicy?: any;
  vehicleAge?: number;
  decodedIc: {
    isValid: boolean;
    formattedDob?: string | null;
    age?: number | null;
    gender?: string | null;
  };
  activeWinnerPeriod: string;
  editingFixedCosts: boolean;
  setEditingFixedCosts: (val: boolean) => void;
  refreshingLedger: boolean;
  onRefreshLedger: () => void;
  customerNameInput: string;
  setCustomerNameInput: (v: string) => void;
  icNoInput: string;
  setIcNoInput: (v: string) => void;
  vehicleNoInput: string;
  setVehicleNoInput: (v: string) => void;
  carBrandInput: string;
  setCarBrandInput: (v: string) => void;
  roadTaxInput: string;
  setRoadTaxInput: (v: string) => void;
  includeRoadTaxInput: boolean;
  setIncludeRoadTaxInput: (v: boolean) => void;
  runnerFeeInput: string;
  setRunnerFeeInput: (v: string) => void;
  includeRunnerFeeInput: boolean;
  setIncludeRunnerFeeInput: (v: boolean) => void;
  windscreenInput: string;
  setWindscreenInput: (v: string) => void;
  engineCcInput: string;
  setEngineCcInput: (v: string) => void;
  engineNoInput: string;
  setEngineNoInput: (v: string) => void;
  chassisNoInput: string;
  setChassisNoInput: (v: string) => void;
  vehicleModelInput: string;
  setVehicleModelInput: (v: string) => void;
  vehicleTypeInput: string;
  setVehicleTypeInput: (v: string) => void;
  manufactureYearInput: string;
  setManufactureYearInput: (v: string) => void;
  startDateInput: string;
  endDateInput: string;
  onStartDateChange: (v: string) => void;
  onEndDateChange: (v: string) => void;
  savingFixedCosts: boolean;
  onSaveFixedCosts: () => void;
  onPopulateEditInputs: () => void;
  quotationDiscountInput: string;
  setQuotationDiscountInput: (v: string) => void;
}

export function CustomerVehicleLedgerPane({
  tenure,
  covernotePolicy,
  vehicleAge,
  decodedIc,
  activeWinnerPeriod,
  editingFixedCosts,
  setEditingFixedCosts,
  refreshingLedger,
  onRefreshLedger,
  customerNameInput,
  setCustomerNameInput,
  icNoInput,
  setIcNoInput,
  vehicleNoInput,
  setVehicleNoInput,
  carBrandInput,
  setCarBrandInput,
  roadTaxInput,
  setRoadTaxInput,
  includeRoadTaxInput,
  setIncludeRoadTaxInput,
  runnerFeeInput,
  setRunnerFeeInput,
  includeRunnerFeeInput,
  setIncludeRunnerFeeInput,
  windscreenInput,
  setWindscreenInput,
  engineCcInput,
  setEngineCcInput,
  engineNoInput,
  setEngineNoInput,
  chassisNoInput,
  setChassisNoInput,
  vehicleModelInput,
  setVehicleModelInput,
  vehicleTypeInput,
  setVehicleTypeInput,
  manufactureYearInput,
  setManufactureYearInput,
  startDateInput,
  endDateInput,
  onStartDateChange,
  onEndDateChange,
  savingFixedCosts,
  onSaveFixedCosts,
  onPopulateEditInputs,
  quotationDiscountInput,
  setQuotationDiscountInput,
}: CustomerVehicleLedgerPaneProps) {
  // Engine Capacity & Unit reactive parser
  const parseCapacity = (raw: string) => {
    const s = (raw || "").trim().toLowerCase();
    const numMatch = s.match(/[\d.]+/);
    const num = numMatch ? numMatch[0] : "";
    let unit: "cc" | "kw" | "kg" = "cc";
    if (s.includes("kg")) unit = "kg";
    else if (s.includes("kw") || s.includes("watt") || s.includes("w")) unit = "kw";
    else unit = "cc";
    return { num, unit };
  };

  const parsedCapacity = parseCapacity(engineCcInput);
  const [recalculatingTax, setRecalculatingTax] = React.useState(false);
  const [unitPrompt, setUnitPrompt] = React.useState<{
    targetUnit: "cc" | "kw" | "kg";
    targetVehicleType: string;
    targetVehicleLabel: string;
  } | null>(null);

  const handleRecalculateRoadTax = async (capNum: string, unit: string, vType: string) => {
    if (!capNum) return;
    try {
      setRecalculatingTax(true);
      const res = await api<{ road_tax: number }>(`/comparison/calculate-road-tax`, {
        method: "POST",
        body: JSON.stringify({
          capacity: capNum,
          unit: unit,
          vehicle_type: vType,
        }),
      });
      if (res && typeof res.road_tax === "number") {
        setRoadTaxInput(res.road_tax.toFixed(2));
      }
    } catch (e) {
      console.warn("Failed to recalculate road tax:", e);
    } finally {
      setRecalculatingTax(false);
    }
  };

  const handleUnitSelect = (newUnit: "cc" | "kw" | "kg") => {
    const num = parsedCapacity.num || "";
    const formattedVal = num ? (newUnit === "kg" ? `${num} KG` : newUnit === "kw" ? `${num} kW` : `${num} CC`) : "";
    setEngineCcInput(formattedVal);

    if (newUnit === "kg" && vehicleTypeInput !== "Lorry") {
      setUnitPrompt({
        targetUnit: "kg",
        targetVehicleType: "Lorry",
        targetVehicleLabel: "Lorry / Commercial Goods Vehicle",
      });
    } else if (newUnit === "kw" && !vehicleTypeInput.startsWith("EV")) {
      setUnitPrompt({
        targetUnit: "kw",
        targetVehicleType: "EVSaloonCar",
        targetVehicleLabel: "Electric Vehicle (EV Saloon)",
      });
    } else if (newUnit === "cc" && (vehicleTypeInput.startsWith("EV") || vehicleTypeInput === "Lorry")) {
      setUnitPrompt({
        targetUnit: "cc",
        targetVehicleType: "Car",
        targetVehicleLabel: "Private Car (ICE)",
      });
    } else {
      handleRecalculateRoadTax(num, newUnit, vehicleTypeInput);
    }
  };

  const handleVehicleTypeChange = (newVType: string) => {
    setVehicleTypeInput(newVType);
    const num = parsedCapacity.num || "";
    let targetUnit = parsedCapacity.unit;
    if (newVType === "Lorry") {
      targetUnit = "kg";
    } else if (newVType.startsWith("EV")) {
      targetUnit = "kw";
    } else if (["Car", "NonSaloonCar", "CompanyCar", "Motorcycle", "CompanyMotorcycle"].includes(newVType)) {
      targetUnit = "cc";
    }
    const formattedVal = num ? (targetUnit === "kg" ? `${num} KG` : targetUnit === "kw" ? `${num} kW` : `${num} CC`) : "";
    setEngineCcInput(formattedVal);
    handleRecalculateRoadTax(num, targetUnit, newVType);
  };

  const confirmUnitPrompt = () => {
    if (!unitPrompt) return;
    const num = parsedCapacity.num || "";
    setVehicleTypeInput(unitPrompt.targetVehicleType);
    handleRecalculateRoadTax(num, unitPrompt.targetUnit, unitPrompt.targetVehicleType);
    setUnitPrompt(null);
  };

  const keepClassUnitPrompt = () => {
    if (!unitPrompt) return;
    const num = parsedCapacity.num || "";
    handleRecalculateRoadTax(num, unitPrompt.targetUnit, vehicleTypeInput);
    setUnitPrompt(null);
  };
  return (
    <div
      id="tour-customer-ledger"
      className="rounded-2xl border border-[#e5e5ea] bg-white shadow-sm overflow-hidden sticky top-6 print:static print:shadow-none break-inside-avoid"
    >
      <div className="bg-[#f5f5f7] px-4 py-3 border-b border-[#e5e5ea] flex items-center justify-between">
        <span className="text-xs font-bold uppercase tracking-wider text-[#1b1717]">
          Customer &amp; Vehicle Ledger
        </span>
        <div className="flex items-center gap-1.5 no-print print:hidden">
          <button
            type="button"
            onClick={onRefreshLedger}
            disabled={refreshingLedger}
            className="rounded p-1 text-[#454545] hover:text-[#1b1717] hover:bg-neutral-200 transition-colors disabled:opacity-50 cursor-pointer"
            title="Re-extract customer & vehicle data from latest uploaded quotes and recalculate road tax"
          >
            <ArrowsClockwise
              size={15}
              weight="bold"
              className={refreshingLedger ? "animate-spin text-[#1b1717]" : ""}
            />
          </button>
          <button
            type="button"
            onClick={() => {
              if (!editingFixedCosts) {
                onPopulateEditInputs();
              }
              setEditingFixedCosts(!editingFixedCosts);
            }}
            className="rounded p-1 text-[#454545] hover:text-[#1b1717] hover:bg-neutral-200 transition-colors cursor-pointer"
            title="Edit customer, vehicle & fixed charges"
          >
            <PencilSimple size={15} weight="bold" />
          </button>
        </div>
      </div>

      <div className="p-4 space-y-4 text-xs divide-y divide-[#e5e5ea]">
        {/* Customer Information Block */}
        <div className="space-y-1.5">
          <span className="text-xs font-bold text-[#6e6e73] uppercase tracking-wider block mb-1">
            Customer Information
          </span>
          {editingFixedCosts ? (
            <div className="space-y-2 bg-[#f5f5f7] p-2.5 rounded-lg border border-[#e5e5ea]">
              <div>
                <label className="text-[11px] font-semibold text-[#454545] block mb-1">
                  Customer Name
                </label>
                <input
                  type="text"
                  value={customerNameInput}
                  onChange={(e) => setCustomerNameInput(e.target.value)}
                  className="w-full rounded px-2.5 py-1.5 text-xs border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-[#454545] block mb-1">
                  IC / Passport Number
                </label>
                <input
                  type="text"
                  value={icNoInput}
                  onChange={(e) => setIcNoInput(e.target.value)}
                  placeholder="e.g. 881205-14-5521"
                  className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                />
              </div>
            </div>
          ) : (
            <div>
              <p className="font-bold text-sm text-[#1b1717]">{tenure.customer_name}</p>
              {tenure.ic_no ? (
                <div className="mt-1 space-y-1">
                  <div className="flex items-center gap-1.5">
                    <IdentificationCard size={14} className="text-[#6e6e73]" />
                    <span className="font-mono text-xs font-semibold text-[#1b1717] bg-[#f5f5f7] px-2 py-0.5 rounded border border-[#e5e5ea]">
                      {tenure.ic_no}
                    </span>
                  </div>
                  {decodedIc.isValid && decodedIc.formattedDob && (
                    <div className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      <span>DOB: {decodedIc.formattedDob}</span>
                      <span>•</span>
                      <span>
                        Age {decodedIc.age} yrs{decodedIc.gender ? ` (${decodedIc.gender})` : ""}
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-xs text-[#6e6e73] italic">No IC recorded</p>
              )}
              {tenure.phone && (
                <p className="text-xs text-[#454545] mt-1 flex items-center gap-1">
                  <Phone size={12} className="text-[#6e6e73]" />
                  <span>{tenure.phone}</span>
                </p>
              )}
              {tenure.address && (
                <p className="text-xs text-[#6e6e73] mt-1 flex items-start gap-1">
                  <MapPin size={12} className="text-[#6e6e73] shrink-0 mt-0.5" />
                  <span className="truncate" title={tenure.address}>
                    {tenure.address}
                  </span>
                </p>
              )}
            </div>
          )}
        </div>

        {/* Period */}
        <div className="pt-3 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#6e6e73] uppercase">
              Insurance Period (保险日期)
            </span>
            {covernotePolicy ? (
              <span className="text-[10px] text-emerald-800 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-300 flex items-center gap-1">
                <CheckCircle size={11} weight="fill" /> Issued Cover Note
              </span>
            ) : (
              <span className="text-[10px] text-neutral-600 font-bold bg-neutral-100 px-2 py-0.5 rounded border border-neutral-200">
                Pending Issue
              </span>
            )}
            {editingFixedCosts && (
              <span className="text-[10px] text-indigo-700 font-bold bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                Auto 1-Year Sync
              </span>
            )}
          </div>
          {editingFixedCosts ? (
            <div className="space-y-2 bg-[#f5f5f7] p-2.5 rounded-lg border border-[#e5e5ea]">
              <div>
                <label className="text-[11px] font-semibold text-[#454545] block mb-1">
                  Start Date (生效日)
                </label>
                <input
                  type="date"
                  value={startDateInput}
                  onChange={(e) => onStartDateChange(e.target.value)}
                  className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-[#454545] block mb-1">
                  End Date (截止日)
                </label>
                <input
                  type="date"
                  value={endDateInput}
                  onChange={(e) => onEndDateChange(e.target.value)}
                  className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                />
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              <p className="font-mono font-bold text-xs text-[#1b1717]">{activeWinnerPeriod}</p>
              {covernotePolicy ? (
                <p className="text-[10px] text-[#6e6e73] flex items-center gap-1">
                  <span>Source:</span>
                  <strong className="text-emerald-900 font-bold">
                    {covernotePolicy.company_name}
                  </strong>
                  <span className="text-neutral-500 font-mono">
                    ({covernotePolicy.policy_number || "Official Issue"})
                  </span>
                  {covernotePolicy.uploaded_file_id && (
                    <a
                      href={fileUrl(
                        `/uploaded-files/${covernotePolicy.uploaded_file_id}/content`
                      )}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-700 hover:text-emerald-900 inline-flex items-center gap-0.5 underline font-semibold ml-1"
                      title="Open source Cover Note PDF"
                    >
                      <FilePdf size={12} weight="bold" />
                      <span>PDF</span>
                    </a>
                  )}
                </p>
              ) : null}
            </div>
          )}
        </div>

        {/* Vehicle Information Block */}
        <div className="pt-3 space-y-2">
          <span className="text-xs font-bold text-[#6e6e73] uppercase tracking-wider block">
            Vehicle Specifications
          </span>
          {editingFixedCosts ? (
            <div className="space-y-2 bg-[#f5f5f7] p-2.5 rounded-lg border border-[#e5e5ea]">
              <div>
                <label className="text-[11px] font-semibold text-[#454545] block mb-1">
                  Registration No
                </label>
                <input
                  type="text"
                  value={vehicleNoInput}
                  onChange={(e) => setVehicleNoInput(e.target.value)}
                  className="w-full rounded px-2.5 py-1.5 text-xs font-mono font-bold border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-semibold text-[#454545] block mb-1">Brand</label>
                  <input
                    type="text"
                    value={carBrandInput}
                    onChange={(e) => setCarBrandInput(e.target.value)}
                    placeholder="e.g. Proton"
                    className="w-full rounded px-2.5 py-1.5 text-xs border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-[#454545] block mb-1">Model</label>
                  <input
                    type="text"
                    value={vehicleModelInput}
                    onChange={(e) => setVehicleModelInput(e.target.value)}
                    placeholder="e.g. X50"
                    className="w-full rounded px-2.5 py-1.5 text-xs border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                  />
                </div>
              </div>
              <div>
                <label className="text-[11px] font-semibold text-[#454545] block mb-1">Vehicle Type</label>
                <select
                  value={vehicleTypeInput}
                  onChange={(e) => handleVehicleTypeChange(e.target.value)}
                  className="w-full rounded px-2.5 py-1.5 text-xs border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                >
                  <option value="Car">Private Car (Saloon / Sedan)</option>
                  <option value="NonSaloonCar">Non-Saloon (SUV / MPV / Van)</option>
                  <option value="CompanyCar">Company Registered Car</option>
                  <option value="Motorcycle">Private Motorcycle</option>
                  <option value="CompanyMotorcycle">Company Motorcycle</option>
                  <option value="Lorry">Lorry / Commercial Goods Vehicle</option>
                  <option value="EVSaloonCar">Electric Vehicle (EV Saloon)</option>
                  <option value="EVNonSaloonCar">Electric Vehicle (EV SUV / MPV)</option>
                </select>
              </div>

              {/* Reactive Unit Change Notification Banner */}
              {unitPrompt && (
                <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-950 animate-in fade-in duration-150">
                  <p className="font-semibold mb-0.5">
                    Switch vehicle class to {unitPrompt.targetVehicleLabel}?
                  </p>
                  <p className="text-[11px] text-amber-800 mb-2">
                    You selected <strong className="uppercase">{unitPrompt.targetUnit}</strong>. Would you like to update the vehicle type and recalculate standard JPJ road tax?
                  </p>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <button
                      type="button"
                      onClick={confirmUnitPrompt}
                      className="px-2 py-1 rounded bg-amber-950 text-white text-[11px] font-bold hover:bg-black transition-colors cursor-pointer"
                    >
                      Yes, Switch &amp; Recalculate
                    </button>
                    <button
                      type="button"
                      onClick={keepClassUnitPrompt}
                      className="px-2 py-1 rounded bg-white text-amber-950 text-[11px] font-semibold border border-amber-300 hover:bg-amber-100 transition-colors cursor-pointer"
                    >
                      Keep Current Class
                    </button>
                    <button
                      type="button"
                      onClick={() => setUnitPrompt(null)}
                      className="p-1 text-amber-700 hover:text-amber-950 ml-auto cursor-pointer"
                      title="Dismiss"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-semibold text-[#454545] block mb-1">Year</label>
                  <input
                    type="number"
                    value={manufactureYearInput}
                    onChange={(e) => setManufactureYearInput(e.target.value)}
                    placeholder="e.g. 2020"
                    className="w-full rounded px-2.5 py-1.5 text-xs border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                  />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-[11px] font-semibold text-[#454545]">Engine Capacity</label>
                    <span className="text-[9px] text-[#6e6e73] uppercase font-mono">{parsedCapacity.unit}</span>
                  </div>
                  <div className="flex rounded border border-[#e5e5ea] bg-white overflow-hidden focus-within:ring-1 focus-within:ring-[#1b1717]">
                    <input
                      type="text"
                      value={parsedCapacity.num}
                      onChange={(e) => {
                        const val = e.target.value.replace(/[^\d.]/g, "");
                        const u = parsedCapacity.unit;
                        const formatted = val ? (u === "kg" ? `${val} KG` : u === "kw" ? `${val} kW` : `${val} CC`) : "";
                        setEngineCcInput(formatted);
                      }}
                      placeholder={parsedCapacity.unit === "kg" ? "3500" : parsedCapacity.unit === "kw" ? "150" : "1496"}
                      className="w-full px-2 py-1.5 text-xs font-mono text-[#1b1717] focus:outline-none"
                    />
                    <div className="flex bg-[#f5f5f7] border-l border-[#e5e5ea] text-[10px] font-bold">
                      {(["cc", "kw", "kg"] as const).map((u) => (
                        <button
                          key={u}
                          type="button"
                          onClick={() => handleUnitSelect(u)}
                          className={`px-1.5 py-1 transition-colors uppercase cursor-pointer ${
                            parsedCapacity.unit === u
                              ? "bg-[#1b1717] text-white"
                              : "text-[#6e6e73] hover:text-[#1b1717] hover:bg-neutral-200"
                          }`}
                          title={u === "cc" ? "ICE (Petrol/Diesel CC)" : u === "kw" ? "Electric Vehicle (kW)" : "Commercial (BDM/BTM KG)"}
                        >
                          {u}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
              <div>
                <label className="text-[11px] font-semibold text-[#454545] block mb-1">Engine No</label>
                <input
                  type="text"
                  value={engineNoInput}
                  onChange={(e) => setEngineNoInput(e.target.value)}
                  className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-[#454545] block mb-1">Chassis / VIN</label>
                <input
                  type="text"
                  value={chassisNoInput}
                  onChange={(e) => setChassisNoInput(e.target.value)}
                  className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-[11px] font-semibold text-[#454545]">Road Tax (RM)</label>
                    <label className="flex items-center gap-1 text-[10px] text-[#6e6e73] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={includeRoadTaxInput}
                        onChange={(e) => setIncludeRoadTaxInput(e.target.checked)}
                        className="rounded border-[#e5e5ea] text-[#1b1717] focus:ring-0 size-3"
                      />
                      <span>Include</span>
                    </label>
                  </div>
                  <input
                    type="number"
                    step="0.01"
                    disabled={!includeRoadTaxInput}
                    value={roadTaxInput}
                    onChange={(e) => setRoadTaxInput(e.target.value)}
                    className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717] disabled:bg-neutral-100 disabled:text-neutral-400"
                  />
                  <div className="mt-1 flex items-center justify-between">
                    <button
                      type="button"
                      disabled={recalculatingTax || !parsedCapacity.num}
                      onClick={() => handleRecalculateRoadTax(parsedCapacity.num, parsedCapacity.unit, vehicleTypeInput)}
                      className="inline-flex items-center gap-1 text-[10px] font-semibold text-blue-700 hover:text-blue-900 transition-colors cursor-pointer disabled:opacity-50"
                      title="Recalculate JPJ Road Tax from current capacity and vehicle class"
                    >
                      <ArrowsClockwise size={11} className={recalculatingTax ? "animate-spin" : ""} />
                      <span>Recalculate JPJ</span>
                    </button>
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-[11px] font-semibold text-[#454545]">Runner Fee (RM)</label>
                    <label className="flex items-center gap-1 text-[10px] text-[#6e6e73] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={includeRunnerFeeInput}
                        onChange={(e) => setIncludeRunnerFeeInput(e.target.checked)}
                        className="rounded border-[#e5e5ea] text-[#1b1717] focus:ring-0 size-3"
                      />
                      <span>Include</span>
                    </label>
                  </div>
                  <input
                    type="number"
                    step="0.01"
                    disabled={!includeRunnerFeeInput}
                    value={runnerFeeInput}
                    onChange={(e) => setRunnerFeeInput(e.target.value)}
                    className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717] disabled:bg-neutral-100 disabled:text-neutral-400"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-semibold text-[#454545] block mb-1">
                    Target Windscreen (RM)
                  </label>
                  <input
                    type="number"
                    step="100"
                    value={windscreenInput}
                    onChange={(e) => setWindscreenInput(e.target.value)}
                    placeholder="e.g. 1000"
                    className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-emerald-900 block mb-1">
                    Quotation Discount (RM)
                  </label>
                  <input
                    type="number"
                    step="1"
                    min="0"
                    value={quotationDiscountInput}
                    onChange={(e) => setQuotationDiscountInput(e.target.value)}
                    placeholder="e.g. 50"
                    className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-emerald-300 bg-emerald-50/40 text-emerald-900 font-bold focus:outline-none focus:ring-1 focus:ring-emerald-600"
                  />
                </div>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setEditingFixedCosts(false)}
                  className="px-2.5 py-1 text-xs rounded border border-[#e5e5ea] bg-white hover:bg-neutral-100 text-[#454545] font-semibold transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={onSaveFixedCosts}
                  disabled={savingFixedCosts}
                  className="px-3 py-1 text-xs rounded bg-[#1b1717] hover:bg-black text-white font-bold inline-flex items-center gap-1 transition-colors disabled:opacity-50 cursor-pointer"
                >
                  <FloppyDisk size={12} weight="bold" />
                  <span>{savingFixedCosts ? "Saving..." : "Save Changes"}</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <span className="text-[#6e6e73]">Registration No:</span>
                {tenure.is_plate_undetected || tenure.vehicle_no === "N/A" ? (
                  <span className="font-mono font-bold text-[11px] text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                    N/A (Undetected)
                  </span>
                ) : (
                  <span className="font-mono font-bold text-[#1b1717]">{tenure.vehicle_no}</span>
                )}
              </div>
              <div className="flex justify-between">
                <span className="text-[#6e6e73]">Brand &amp; Model:</span>
                <span className="font-semibold text-[#1b1717]">
                  {tenure.car_brand ? `${tenure.car_brand} ` : ""}
                  {tenure.vehicle_model}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6e6e73]">Vehicle Type:</span>
                <span className="font-semibold text-[#1b1717]">
                  {tenure.vehicle_type === "NonSaloonCar"
                    ? "Non-Saloon (SUV / MPV)"
                    : tenure.vehicle_type === "CompanyCar"
                    ? "Company Car"
                    : tenure.vehicle_type === "Motorcycle"
                    ? "Motorcycle"
                    : tenure.vehicle_type === "CompanyMotorcycle"
                    ? "Company Motorcycle"
                    : tenure.vehicle_type === "Lorry"
                    ? "Lorry / Commercial"
                    : tenure.vehicle_type?.startsWith("EV")
                    ? `EV (${tenure.vehicle_type})`
                    : tenure.vehicle_type || "Private Car"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6e6e73]">Year of Make:</span>
                <span className="font-semibold text-[#1b1717]">
                  {tenure.manufacture_year || "Not Recorded"}
                  {vehicleAge ? ` (${vehicleAge} yrs)` : ""}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6e6e73]">Engine Capacity:</span>
                <span className="font-semibold text-[#1b1717]">{tenure.engine_cc}</span>
              </div>
              {tenure.engine_no && (
                <div className="flex justify-between">
                  <span className="text-[#6e6e73]">Engine No:</span>
                  <span className="font-mono text-[#1b1717]">{tenure.engine_no}</span>
                </div>
              )}
              {tenure.chassis_no && (
                <div className="flex justify-between">
                  <span className="text-[#6e6e73]">Chassis / VIN:</span>
                  <span className="font-mono text-[#1b1717]">{tenure.chassis_no}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-[#6e6e73]">Target Windscreen:</span>
                <span className="font-mono font-bold text-[#1b1717]">
                  {tenure.windscreen_target && tenure.windscreen_target > 0
                    ? `RM ${tenure.windscreen_target.toLocaleString("en-MY", { minimumFractionDigits: 2 })}`
                    : "None (RM 0.00)"}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[#6e6e73]">Quotation Discount:</span>
                {tenure.quotation_discount && tenure.quotation_discount > 0 ? (
                  <span className="font-mono font-bold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-300 text-[11px]">
                    - RM {tenure.quotation_discount.toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                  </span>
                ) : (
                  <span className="font-mono text-[#6e6e73]">None (RM 0.00)</span>
                )}
              </div>
              <div className="flex justify-between">
                <span className="text-[#6e6e73]">Road Tax:</span>
                <span className="font-mono font-bold text-[#1b1717]">
                  {tenure.include_road_tax !== false
                    ? `RM ${tenure.road_tax.toFixed(2)}`
                    : "Excluded (RM 0.00)"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6e6e73]">Runner Fee:</span>
                <span className="font-mono font-bold text-[#1b1717]">
                  {tenure.include_runner_fee !== false
                    ? `RM ${tenure.runner_fee.toFixed(2)}`
                    : "Excluded (RM 0.00)"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6e6e73]">NCD Status:</span>
                <span className="font-bold text-[#1b1717]">
                  {tenure.ncd_percentage != null
                    ? `${
                        tenure.ncd_percentage % 1 === 0
                          ? tenure.ncd_percentage.toFixed(0)
                          : tenure.ncd_percentage.toFixed(2)
                      }%`
                    : "Not Detected"}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
