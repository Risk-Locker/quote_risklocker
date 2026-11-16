"use client";

import React from "react";
import Link from "next/link";
import type { Route } from "next";
import { UploadSimple, ArrowsClockwise, FilePdf } from "@phosphor-icons/react";
import { useToast } from "@/components/ui/toast";
import { getVehicleDisplayName } from "@/lib/vehicle-utils";
import type { TenureRow } from "../types";

export interface CoverNoteUploadModalProps {
  tenure: TenureRow | null;
  uploadingCovernote: boolean;
  onUploadCovernote: (file: File) => Promise<void>;
  onClose: () => void;
}

export function CoverNoteUploadModal({
  tenure,
  uploadingCovernote,
  onUploadCovernote,
  onClose,
}: CoverNoteUploadModalProps) {
  const { toast } = useToast();
  if (!tenure) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="bg-white rounded-[var(--rl-radius)] border border-neutral-200 shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="p-4 border-b border-neutral-100 bg-[#fbfbfd] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center text-amber-800">
              <UploadSimple size={18} weight="bold" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-neutral-900">Upload Policy / Cover Note</h3>
              <p className="text-[11px] text-neutral-500">
                Required before advancing to Issue Policy stage
              </p>
            </div>
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
          <div className="bg-neutral-50 p-3.5 rounded-lg border border-neutral-200 space-y-2 text-xs">
            <div className="flex items-center justify-between pb-1.5 border-b border-neutral-200/60">
              <span className="font-mono font-bold text-sm text-neutral-900">
                {getVehicleDisplayName(tenure.vehicle_no, tenure.chassis_no)}
              </span>
              {tenure.expiry_month && (
                <span className="text-[10px] font-mono font-semibold bg-white px-2 py-0.5 rounded border border-neutral-200 text-neutral-600">
                  Exp: {tenure.expiry_month}
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div>
                <span className="text-neutral-500 block text-[10px]">Customer:</span>
                <span className="font-semibold text-neutral-800 truncate block">
                  {tenure.customer_name || "—"}
                </span>
              </div>
              <div>
                <span className="text-neutral-500 block text-[10px]">Customer IC / Reg No:</span>
                <span className="font-mono text-neutral-800 truncate block">
                  {tenure.customer_ic_no || "—"}
                </span>
              </div>
              <div>
                <span className="text-neutral-500 block text-[10px]">Chassis No:</span>
                <span className="font-mono text-neutral-800 truncate block">
                  {tenure.chassis_no || "—"}
                </span>
              </div>
              <div>
                <span className="text-neutral-500 block text-[10px]">Vehicle Model:</span>
                <span className="text-neutral-800 truncate block">
                  {[tenure.car_brand, tenure.car_model].filter(Boolean).join(" ") || "—"}
                </span>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-neutral-800 block">
              Select Official Cover Note PDF
            </label>
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const file = e.dataTransfer.files?.[0];
                if (file && file.type === "application/pdf") {
                  onUploadCovernote(file);
                } else if (file) {
                  toast("Please select a PDF file.", "warning");
                }
              }}
              className="border-2 border-dashed border-neutral-300 hover:border-neutral-900 rounded-xl p-6 text-center transition-colors bg-white hover:bg-neutral-50/50 cursor-pointer relative"
            >
              <input
                type="file"
                accept=".pdf,application/pdf"
                disabled={uploadingCovernote}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    onUploadCovernote(file);
                  }
                }}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
              {uploadingCovernote ? (
                <div className="flex flex-col items-center gap-2 py-2">
                  <ArrowsClockwise className="w-6 h-6 animate-spin text-amber-600" />
                  <span className="text-xs font-bold text-neutral-800">
                    Extracting &amp; Attaching Cover Note...
                  </span>
                  <span className="text-[10px] text-neutral-500">
                    OCR scanning schedule excess, perils, and policy number
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <div className="w-10 h-10 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-600">
                    <FilePdf size={22} weight="duotone" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-neutral-800 block">
                      Drop Cover Note PDF here, or click to browse
                    </span>
                    <span className="text-[10px] text-neutral-400">
                      Supports official PDF schedules from all Malaysian insurers
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="pt-2 text-center">
            <Link
              href={`/upload?mode=comparison&tenure_id=${tenure.id}` as Route}
              onClick={onClose}
              className="text-[11px] text-neutral-600 hover:text-neutral-900 font-semibold underline"
            >
              Or open dedicated Upload Intake Workspace →
            </Link>
          </div>
        </div>

        <div className="p-3 bg-neutral-50 border-t border-neutral-200 flex items-center justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={uploadingCovernote}
            className="px-3.5 py-1.5 text-xs font-medium text-neutral-600 hover:text-neutral-900 cursor-pointer disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
