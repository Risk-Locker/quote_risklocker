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
import { fileUrl } from "@/lib/api";
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
  runnerFeeInput: string;
  setRunnerFeeInput: (v: string) => void;
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
  manufactureYearInput: string;
  setManufactureYearInput: (v: string) => void;
  startDateInput: string;
  endDateInput: string;
  onStartDateChange: (v: string) => void;
  onEndDateChange: (v: string) => void;
  savingFixedCosts: boolean;
  onSaveFixedCosts: () => void;
  onPopulateEditInputs: () => void;
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
  runnerFeeInput,
  setRunnerFeeInput,
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
  manufactureYearInput,
  setManufactureYearInput,
  startDateInput,
  endDateInput,
  onStartDateChange,
  onEndDateChange,
  savingFixedCosts,
  onSaveFixedCosts,
  onPopulateEditInputs,
}: CustomerVehicleLedgerPaneProps) {
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
                  <label className="text-[11px] font-semibold text-[#454545] block mb-1">Engine CC</label>
                  <input
                    type="text"
                    value={engineCcInput}
                    onChange={(e) => setEngineCcInput(e.target.value)}
                    placeholder="e.g. 1477 cc"
                    className="w-full rounded px-2.5 py-1.5 text-xs border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                  />
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
                  <label className="text-[11px] font-semibold text-[#454545] block mb-1">Road Tax (RM)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={roadTaxInput}
                    onChange={(e) => setRoadTaxInput(e.target.value)}
                    className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-[#454545] block mb-1">Runner Fee (RM)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={runnerFeeInput}
                    onChange={(e) => setRunnerFeeInput(e.target.value)}
                    className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                  />
                </div>
              </div>
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
                <span className="text-[#6e6e73]">Year of Make:</span>
                <span className="font-semibold text-[#1b1717]">
                  {tenure.manufacture_year || "Not Recorded"}
                  {vehicleAge ? ` (${vehicleAge} yrs)` : ""}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6e6e73]">Engine CC:</span>
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
