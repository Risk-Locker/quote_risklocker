"use client";

import React from "react";
import { CheckCircle, XCircle } from "@phosphor-icons/react";
import type { TenureRow } from "../types";

export interface MissModalProps {
  tenure: TenureRow | null;
  keepClientChoice: "keep" | "discard";
  setKeepClientChoice: (val: "keep" | "discard") => void;
  createNextYearDeal: boolean;
  setCreateNextYearDeal: (val: boolean) => void;
  externalInsurer: string;
  setExternalInsurer: (val: string) => void;
  missReason: string;
  setMissReason: (val: string) => void;
  savingMissOutcome: boolean;
  onConfirmMiss: () => Promise<void>;
  onClose: () => void;
}

export function MissModal({
  tenure,
  keepClientChoice,
  setKeepClientChoice,
  createNextYearDeal,
  setCreateNextYearDeal,
  externalInsurer,
  setExternalInsurer,
  missReason,
  setMissReason,
  savingMissOutcome,
  onConfirmMiss,
  onClose,
}: MissModalProps) {
  if (!tenure) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
      <div className="bg-white rounded-[var(--rl-radius)] border border-neutral-200 shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="p-4 border-b border-neutral-100 bg-[#fbfbfd] flex items-center justify-between">
          <div>
            <h3 className="font-bold text-sm text-neutral-900">Mark Deal as Miss (Client Lost)</h3>
            <p className="text-xs text-neutral-500 font-mono mt-0.5">
              {tenure.vehicle_no} · {tenure.customer_name}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-700 text-sm font-bold p-1 cursor-pointer"
          >
            ✕
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-bold text-neutral-800 block mb-2">
              Do you want to keep this client for next year&apos;s renewal?
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setKeepClientChoice("keep")}
                className={`p-3 rounded-lg border text-left text-xs transition-all cursor-pointer ${
                  keepClientChoice === "keep"
                    ? "border-emerald-500 bg-emerald-50/50 text-emerald-950 ring-1 ring-emerald-500"
                    : "border-neutral-200 hover:bg-neutral-50 text-neutral-700"
                }`}
              >
                <div className="font-bold flex items-center gap-1.5">
                  <CheckCircle
                    size={14}
                    weight="bold"
                    className={keepClientChoice === "keep" ? "text-emerald-600" : "text-neutral-400"}
                  />
                  <span>Keep Client</span>
                </div>
                <p className="text-[11px] text-neutral-500 mt-1">
                  Keep client profile and track next year&apos;s renewal win-back.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setKeepClientChoice("discard")}
                className={`p-3 rounded-lg border text-left text-xs transition-all cursor-pointer ${
                  keepClientChoice === "discard"
                    ? "border-rose-500 bg-rose-50/50 text-rose-950 ring-1 ring-rose-500"
                    : "border-neutral-200 hover:bg-neutral-50 text-neutral-700"
                }`}
              >
                <div className="font-bold flex items-center gap-1.5">
                  <XCircle
                    size={14}
                    weight="bold"
                    className={keepClientChoice === "discard" ? "text-rose-600" : "text-neutral-400"}
                  />
                  <span>Drop / Discard</span>
                </div>
                <p className="text-[11px] text-neutral-500 mt-1">
                  Client is dropped. Will NOT create next year&apos;s renewal deal.
                </p>
              </button>
            </div>
          </div>

          {keepClientChoice === "keep" && (
            <div className="p-3 bg-blue-50/60 border border-blue-200 rounded-lg space-y-2">
              <label className="flex items-center gap-2 cursor-pointer text-xs font-bold text-blue-950">
                <input
                  type="checkbox"
                  checked={createNextYearDeal}
                  onChange={(e) => setCreateNextYearDeal(e.target.checked)}
                  className="w-4 h-4 rounded text-blue-600 accent-blue-600 cursor-pointer"
                />
                <span>
                  Create{" "}
                  {tenure.coverage_start_date
                    ? new Date(tenure.coverage_start_date).getFullYear() + 1
                    : "Next Year"}{" "}
                  Renewal Ledger deal immediately
                </span>
              </label>
              <p className="text-[11px] text-blue-800 pl-6 leading-relaxed">
                When checked, {tenure.vehicle_no} will be placed into next year&apos;s Renewal
                Ledger for future follow-up.
              </p>
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-neutral-700 block mb-1">
              Current year insurance used by customer{" "}
              <span className="text-neutral-400 font-normal">(optional)</span>:
            </label>
            <input
              type="text"
              placeholder="e.g. Etiqa, Allianz, Zurich, Tokio Marine..."
              value={externalInsurer}
              onChange={(e) => setExternalInsurer(e.target.value)}
              className="w-full h-8 px-3 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900"
            />
            <p className="text-[10px] text-neutral-400 mt-0.5">
              If not known, you can leave this blank.
            </p>
          </div>

          <div>
            <label className="text-xs font-semibold text-neutral-700 block mb-1">
              Notes / Reason for loss{" "}
              <span className="text-neutral-400 font-normal">(optional)</span>:
            </label>
            <input
              type="text"
              placeholder="e.g. Competitor price lower, renewed with bank..."
              value={missReason}
              onChange={(e) => setMissReason(e.target.value)}
              className="w-full h-8 px-3 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900"
            />
          </div>
        </div>

        <div className="p-3 bg-neutral-50 border-t border-neutral-200 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs font-medium text-neutral-600 hover:text-neutral-900 cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirmMiss}
            disabled={savingMissOutcome}
            className="px-4 py-1.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded shadow-xs cursor-pointer disabled:opacity-50"
          >
            {savingMissOutcome ? "Saving..." : "Confirm Miss & Update"}
          </button>
        </div>
      </div>
    </div>
  );
}
