"use client";

import React from "react";
import Link from "next/link";
import type { Route } from "next";
import { X, ShieldCheck, CloudArrowUp } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";

interface NcdEntitlementModalProps {
  isOpen: boolean;
  onClose: () => void;
  tenureId: string;
  ncdData?: {
    current_period?: string;
    next_period?: string;
  };
  editCurrentNcd: string;
  setEditCurrentNcd: (val: string) => void;
  editNextNcd: string;
  setEditNextNcd: (val: string) => void;
  pastingPolicyText: string;
  setPastingPolicyText: (val: string) => void;
  onSave: () => void;
  isSaving: boolean;
}

export function NcdEntitlementModal({
  isOpen,
  onClose,
  tenureId,
  ncdData,
  editCurrentNcd,
  setEditCurrentNcd,
  editNextNcd,
  setEditNextNcd,
  pastingPolicyText,
  setPastingPolicyText,
  onSave,
  isSaving,
}: NcdEntitlementModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 no-print animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl border border-neutral-200 max-w-lg w-full overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#e5e5ea] bg-[#f5f5f7]">
          <div>
            <h3 className="text-base font-bold text-[#1b1717] flex items-center gap-2">
              <ShieldCheck size={20} weight="fill" className="text-emerald-600" />
              NCD Entitlement &amp; Previous Policy
            </h3>
            <p className="text-xs text-[#6e6e73]">
              Update Current NCD (last year policy) and Next NCD (renewal quotation)
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
          {/* Current NCD Selection */}
          <div>
            <div className="flex justify-between items-baseline mb-1.5">
              <label className="text-xs font-bold text-[#1b1717]">
                Current NCD (Last Year Policy)
              </label>
              <span className="text-[11px] font-mono text-[#6e6e73]">
                {ncdData?.current_period ? `Period: ${ncdData.current_period}` : ""}
              </span>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <input
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={editCurrentNcd}
                onChange={(e) => setEditCurrentNcd(e.target.value)}
                placeholder="e.g. 55"
                className="w-24 h-9 px-3 rounded-lg border border-neutral-300 font-mono text-sm font-bold text-center focus:border-[#1b1717] outline-none"
              />
              <span className="text-sm font-bold text-neutral-500">%</span>
              <div className="flex-1 flex gap-1 flex-wrap">
                {[0, 25, 30, 38.33, 45, 55].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setEditCurrentNcd(String(val))}
                    className={`px-2 py-1 rounded text-xs font-mono font-bold transition-all cursor-pointer ${
                      parseFloat(editCurrentNcd) === val
                        ? "bg-[#1b1717] text-white"
                        : "bg-neutral-100 hover:bg-neutral-200 text-neutral-800"
                    }`}
                  >
                    {val}%
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Next NCD Selection */}
          <div>
            <div className="flex justify-between items-baseline mb-1.5">
              <label className="text-xs font-bold text-[#1b1717]">
                Next NCD (Renewal Quotation)
              </label>
              <span className="text-[11px] font-mono text-[#6e6e73]">
                {ncdData?.next_period ? `Period: ${ncdData.next_period}` : ""}
              </span>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <input
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={editNextNcd}
                onChange={(e) => setEditNextNcd(e.target.value)}
                placeholder="e.g. 55"
                className="w-24 h-9 px-3 rounded-lg border border-neutral-300 font-mono text-sm font-bold text-center focus:border-[#1b1717] outline-none"
              />
              <span className="text-sm font-bold text-neutral-500">%</span>
              <div className="flex-1 flex gap-1 flex-wrap">
                {[0, 25, 30, 38.33, 45, 55].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setEditNextNcd(String(val))}
                    className={`px-2 py-1 rounded text-xs font-mono font-bold transition-all cursor-pointer ${
                      parseFloat(editNextNcd) === val
                        ? "bg-emerald-700 text-white"
                        : "bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200"
                    }`}
                  >
                    {val}%
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Paste or Drop Zone for Policy Text / PDF snippet */}
          <div className="rounded-xl border border-dashed border-neutral-300 p-3 bg-neutral-50 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-neutral-700 block">
                Upload Previous Policy (PNG / PDF) or Paste Text Snippet
              </span>
              <label className="inline-flex items-center gap-1 text-[10px] font-semibold text-neutral-700 bg-white border border-neutral-300 hover:bg-neutral-100 px-2 py-0.5 rounded cursor-pointer transition-colors shadow-2xs">
                <CloudArrowUp size={12} weight="bold" />
                <span>Choose File</span>
                <input
                  type="file"
                  accept="image/*,application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      const name = file.name;
                      setPastingPolicyText(`Uploaded file: ${name}`);
                      const match = name.match(/(\d+(?:\.\d+)?)\s*%/);
                      if (match) {
                        setEditCurrentNcd(match[1]);
                      }
                    }
                  }}
                />
              </label>
            </div>
            <textarea
              rows={2}
              value={pastingPolicyText}
              onChange={(e) => {
                const txt = e.target.value;
                setPastingPolicyText(txt);
                const match = txt.match(/(\d+(?:\.\d+)?)\s*%/);
                if (match) {
                  setEditCurrentNcd(match[1]);
                }
              }}
              placeholder="Drop last year policy PNG / PDF or paste 2-4 lines of text (e.g. 'Current NCD: 55% 22/01/2024 to 21/01/2025')..."
              className="w-full text-xs p-2 rounded-lg border border-neutral-200 bg-white font-mono outline-none focus:border-[#1b1717]"
            />
            <div className="flex items-center justify-between text-[10px] text-neutral-500">
              <span>Tip: Any detected % in the pasted text or file will auto-fill Current NCD.</span>
              <Link
                href={`/upload?mode=comparison&tenure_id=${tenureId}` as Route}
                className="text-blue-600 hover:underline font-semibold flex items-center gap-1"
                target="_blank"
              >
                <span>Full Intake OCR Upload ↗</span>
              </Link>
            </div>
          </div>
        </div>

        <div className="px-6 py-3 border-t border-[#e5e5ea] bg-[#f5f5f7] flex items-center justify-end gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={onClose}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={onSave}
            loading={isSaving}
            className="bg-[#1b1717] hover:bg-black text-white font-bold"
          >
            Save NCD Entitlement
          </Button>
        </div>
      </div>
    </div>
  );
}
