"use client";

import React from "react";
import Link from "next/link";
import type { Route } from "next";
import { Car, XCircle, FilePdf, ArrowRight, ArrowsClockwise, Sparkle } from "@phosphor-icons/react";
import { POPULAR_BRANDS } from "../types";

export interface AddCustomVehicleModalProps {
  isOpen: boolean;
  onClose: () => void;
  newVehPlate: string;
  setNewVehPlate: (val: string) => void;
  newVehCustomerName: string;
  setNewVehCustomerName: (val: string) => void;
  newVehIcNo: string;
  setNewVehIcNo: (val: string) => void;
  newVehBrand: string;
  setNewVehBrand: (val: string) => void;
  newVehCustomBrand: string;
  setNewVehCustomBrand: (val: string) => void;
  newVehModel: string;
  setNewVehModel: (val: string) => void;
  newVehYom: string;
  setNewVehYom: (val: string) => void;
  newVehEngineCc: string;
  setNewVehEngineCc: (val: string) => void;
  newVehStartDate: string;
  onStartDateChange: (val: string) => void;
  newVehEndDate: string;
  onEndDateChange: (val: string) => void;
  newVehWindscreen: string;
  setNewVehWindscreen: (val: string) => void;
  savingNewVehicle: boolean;
  onCreateVehicle: (openComparison: boolean) => Promise<void>;
}

export function AddCustomVehicleModal({
  isOpen,
  onClose,
  newVehPlate,
  setNewVehPlate,
  newVehCustomerName,
  setNewVehCustomerName,
  newVehIcNo,
  setNewVehIcNo,
  newVehBrand,
  setNewVehBrand,
  newVehCustomBrand,
  setNewVehCustomBrand,
  newVehModel,
  setNewVehModel,
  newVehYom,
  setNewVehYom,
  newVehEngineCc,
  setNewVehEngineCc,
  newVehStartDate,
  onStartDateChange,
  newVehEndDate,
  onEndDateChange,
  newVehWindscreen,
  setNewVehWindscreen,
  savingNewVehicle,
  onCreateVehicle,
}: AddCustomVehicleModalProps) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={() => !savingNewVehicle && onClose()}
    >
      <div
        className="bg-white rounded-[var(--rl-radius-md)] border border-neutral-200 shadow-xl w-full max-w-2xl overflow-hidden animate-in zoom-in-95 duration-150 flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 bg-neutral-900 text-white flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-white">
              <Car size={18} weight="bold" />
            </div>
            <div>
              <h3 className="text-sm font-bold tracking-tight">Add Custom Vehicle &amp; Policy</h3>
              <p className="text-[11px] text-neutral-300">
                Register a vehicle to track on the renewal ledger and start marketing comparison quotes.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={savingNewVehicle}
            aria-label="Close modal"
            data-testid="close-add-vehicle-btn"
            className="text-neutral-400 hover:text-white p-1 rounded-sm cursor-pointer transition-colors"
          >
            <XCircle size={18} weight="bold" />
          </button>
        </div>

        <div className="p-5 space-y-4 overflow-y-auto">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-neutral-800 mb-1">
                Vehicle Reg. No (Plate) <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={newVehPlate}
                onChange={(e) => setNewVehPlate(e.target.value.toUpperCase().replace(/\s+/g, ""))}
                placeholder="e.g. WVV1234 or JDR2263"
                className="w-full px-3 py-2 text-xs font-mono font-bold uppercase rounded-[var(--rl-radius-sm)] border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900"
                autoFocus
              />
              <span className="text-[10px] text-neutral-400 mt-0.5 block">
                Spaces are automatically trimmed and capitalized.
              </span>
            </div>

            <div>
              <label className="block text-xs font-bold text-neutral-800 mb-1">
                Customer / Policyholder Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={newVehCustomerName}
                onChange={(e) => setNewVehCustomerName(e.target.value)}
                placeholder="e.g. Tan Ah Kow or ABC Logistics Sdn Bhd"
                className="w-full px-3 py-2 text-xs rounded-[var(--rl-radius-sm)] border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900"
              />
              <span className="text-[10px] text-neutral-400 mt-0.5 block">
                Individual policyholder or commercial enterprise name.
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-neutral-800 mb-1">
                IC / Passport / Company Reg No.
              </label>
              <input
                type="text"
                value={newVehIcNo}
                onChange={(e) => setNewVehIcNo(e.target.value)}
                placeholder="e.g. 901010-14-1234 or 202301012345"
                className="w-full px-3 py-2 text-xs rounded-[var(--rl-radius-sm)] border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-neutral-800 mb-1">
                Brand / Manufacturer
              </label>
              <div className="flex gap-2">
                <select
                  value={newVehBrand}
                  onChange={(e) => setNewVehBrand(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-[var(--rl-radius-sm)] border border-neutral-300 bg-white focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900"
                >
                  {POPULAR_BRANDS.map((b) => (
                    <option key={b} value={b}>
                      {b}
                    </option>
                  ))}
                </select>
                {newVehBrand === "Other" && (
                  <input
                    type="text"
                    value={newVehCustomBrand}
                    onChange={(e) => setNewVehCustomBrand(e.target.value)}
                    placeholder="Specify Make"
                    className="w-full px-3 py-2 text-xs rounded-[var(--rl-radius-sm)] border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900"
                  />
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-bold text-neutral-800 mb-1">Model</label>
              <input
                type="text"
                value={newVehModel}
                onChange={(e) => setNewVehModel(e.target.value)}
                placeholder="e.g. Myvi 1.5 AV or City V"
                className="w-full px-3 py-2 text-xs rounded-[var(--rl-radius-sm)] border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-neutral-800 mb-1">
                Year of Make (YOM)
              </label>
              <input
                type="number"
                min="1980"
                max={new Date().getFullYear() + 1}
                value={newVehYom}
                onChange={(e) => setNewVehYom(e.target.value)}
                placeholder="e.g. 2022"
                className="w-full px-3 py-2 text-xs rounded-[var(--rl-radius-sm)] border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-neutral-800 mb-1">
                Engine Capacity (CC)
              </label>
              <input
                type="text"
                value={newVehEngineCc}
                onChange={(e) => setNewVehEngineCc(e.target.value)}
                placeholder="e.g. 1496 CC"
                className="w-full px-3 py-2 text-xs rounded-[var(--rl-radius-sm)] border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-bold text-neutral-800 mb-1">
                Coverage Start Date
              </label>
              <input
                type="date"
                value={newVehStartDate}
                onChange={(e) => onStartDateChange(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-[var(--rl-radius-sm)] border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900"
              />
              <span className="text-[10px] text-neutral-400 mt-0.5 block">
                Auto-calculates expiry (+1 yr -1 day).
              </span>
            </div>

            <div>
              <label className="block text-xs font-bold text-neutral-800 mb-1">
                Coverage End Date (Expiry)
              </label>
              <input
                type="date"
                value={newVehEndDate}
                onChange={(e) => onEndDateChange(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-[var(--rl-radius-sm)] border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-neutral-800 mb-1">
                Target Windscreen (RM)
              </label>
              <input
                type="number"
                step="100"
                value={newVehWindscreen}
                onChange={(e) => setNewVehWindscreen(e.target.value)}
                placeholder="e.g. 1000 or 1500"
                className="w-full px-3 py-2 text-xs rounded-[var(--rl-radius-sm)] border border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-neutral-900"
              />
            </div>
          </div>

          <div className="p-3 rounded-[var(--rl-radius-sm)] bg-neutral-50 border border-neutral-200 flex items-center justify-between text-xs text-neutral-600">
            <div className="flex items-center gap-2">
              <FilePdf size={16} className="text-neutral-500 shrink-0" />
              <span>Already have quotation PDFs from insurers?</span>
            </div>
            <Link
              href={"/upload/marketing-comparison" as Route}
              onClick={onClose}
              className="font-bold text-neutral-900 hover:underline flex items-center gap-1"
            >
              <span>Upload PDFs directly</span>
              <ArrowRight size={12} weight="bold" />
            </Link>
          </div>
        </div>

        <div className="p-4 bg-neutral-50 border-t border-neutral-200 flex flex-col sm:flex-row items-center justify-end gap-2.5 shrink-0">
          <button
            type="button"
            onClick={onClose}
            disabled={savingNewVehicle}
            data-testid="cancel-add-vehicle-btn"
            className="w-full sm:w-auto px-4 py-2 text-xs font-semibold text-neutral-600 hover:text-neutral-900 transition-colors cursor-pointer disabled:opacity-50"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={() => onCreateVehicle(false)}
            disabled={savingNewVehicle}
            className="w-full sm:w-auto px-4 py-2 text-xs font-bold rounded-[var(--rl-radius-sm)] bg-white hover:bg-neutral-100 text-neutral-800 border border-neutral-300 transition-all shadow-2xs cursor-pointer disabled:opacity-50"
          >
            {savingNewVehicle ? "Saving..." : "Save to Ledger Only"}
          </button>

          <button
            type="button"
            onClick={() => onCreateVehicle(true)}
            disabled={savingNewVehicle}
            className="w-full sm:w-auto px-4 py-2 text-xs font-bold rounded-[var(--rl-radius-sm)] bg-neutral-900 hover:bg-neutral-800 text-white transition-all shadow-xs cursor-pointer flex items-center justify-center gap-1.5 disabled:opacity-50"
          >
            {savingNewVehicle ? (
              <>
                <ArrowsClockwise size={14} className="animate-spin" />
                <span>Creating Vehicle...</span>
              </>
            ) : (
              <>
                <Sparkle size={14} weight="bold" className="text-amber-400" />
                <span>Save &amp; Build Comparison Matrix</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
