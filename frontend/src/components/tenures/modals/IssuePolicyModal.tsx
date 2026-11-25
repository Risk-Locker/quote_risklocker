"use client";

import React from "react";
import type { TenureRow } from "../types";

export interface IssuePolicyModalProps {
  tenure: TenureRow | null;
  selectedWinnerQuote: string;
  setSelectedWinnerQuote: (val: string) => void;
  policyStartDate: string;
  setPolicyStartDate: (val: string) => void;
  savingIssuePolicy: boolean;
  onConfirmIssuePolicy: () => Promise<void>;
  onClose: () => void;
}

export function IssuePolicyModal({
  tenure,
  selectedWinnerQuote,
  setSelectedWinnerQuote,
  policyStartDate,
  setPolicyStartDate,
  savingIssuePolicy,
  onConfirmIssuePolicy,
  onClose,
}: IssuePolicyModalProps) {
  if (!tenure) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
      <div className="bg-white rounded-[var(--rl-radius)] border border-neutral-200 shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="p-4 border-b border-neutral-100 bg-[#fbfbfd] flex items-center justify-between">
          <div>
            <h3 className="font-bold text-sm text-neutral-900">Confirm Policy Issuance</h3>
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
            <label className="text-xs font-bold text-neutral-800 block mb-1">
              1. Confirmed Winning Quotation
            </label>
            <p className="text-[11px] text-neutral-500 mb-2">
              Select the quote that the customer confirmed:
            </p>
            {tenure.sourced_quotes.length === 0 ? (
              <div className="p-2.5 bg-neutral-50 rounded border border-neutral-200 text-xs text-neutral-500 italic">
                No quotes compiled yet.
              </div>
            ) : (
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {tenure.sourced_quotes.map((q) => {
                  const isSelected = selectedWinnerQuote === q.company;
                  return (
                    <button
                      key={q.session_id}
                      type="button"
                      onClick={() => setSelectedWinnerQuote(q.company)}
                      className={`w-full p-2.5 rounded border text-left text-xs transition-all cursor-pointer flex items-center justify-between ${
                        isSelected
                          ? "border-emerald-500 bg-emerald-50 text-emerald-950 font-bold ring-1 ring-emerald-500"
                          : "border-neutral-200 hover:bg-neutral-50 text-neutral-700"
                      }`}
                    >
                      <span>{q.company}</span>
                      {q.total_payable && (
                        <span className="font-mono text-neutral-900 font-bold">
                          RM {q.total_payable}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div>
            <label className="text-xs font-bold text-neutral-800 block mb-1">
              2. Confirmed Insurance Period
            </label>
            <p className="text-[11px] text-neutral-500 mb-2">
              Enter the official policy start date (coverage automatically runs for 1 full year):
            </p>
            <input
              type="date"
              value={policyStartDate}
              onChange={(e) => setPolicyStartDate(e.target.value)}
              className="w-full h-9 px-3 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900 font-mono"
            />
            {policyStartDate && (
              <div className="mt-2 p-2 bg-emerald-50 border border-emerald-200 rounded text-[11px] text-emerald-900 font-mono">
                Coverage: {policyStartDate} →{" "}
                {(() => {
                  const [yy, mm, dd] = policyStartDate.split("T")[0].split("-").map(Number);
                  if (!yy || !mm || !dd) return "—";
                  if (mm === 2 && dd === 29) return `${yy + 1}-02-28`;
                  const d = new Date(Date.UTC(yy + 1, mm - 1, dd));
                  d.setUTCDate(d.getUTCDate() - 1);
                  return d.toISOString().split("T")[0];
                })()}
              </div>
            )}
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
            onClick={onConfirmIssuePolicy}
            disabled={savingIssuePolicy}
            className="px-4 py-1.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded shadow-xs cursor-pointer disabled:opacity-50"
          >
            {savingIssuePolicy ? "Confirming..." : "Confirm & Issue Policy"}
          </button>
        </div>
      </div>
    </div>
  );
}
