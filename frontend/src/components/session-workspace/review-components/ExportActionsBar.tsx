"use client";

import React, { useState } from "react";
import {
  Check,
  Copy,
  DownloadSimple,
  FilePdf,
  Lock,
  PaperPlaneRight,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";

export interface ExportActionsBarProps {
  handleDownloadPdf: () => void;
  pdfLoading?: boolean;
  ownershipConflict?: { has_conflict?: boolean; resolved?: boolean } | null;
  formValues?: Record<string, string>;
  previewFields?: Record<string, string>;
  companyName?: string | null;
  handleCopySummary?: () => void;
  copiedSummary?: boolean;
  handleCopyPng?: () => void;
  copyingPng?: boolean;
  copiedPng?: boolean;
  handleDownloadPng?: () => void;
  downloadingPng?: boolean;
  className?: string;
  isDirty?: boolean;
}

export function ExportActionsBar({
  handleDownloadPdf,
  pdfLoading = false,
  ownershipConflict,
  formValues = {},
  previewFields = {},
  companyName,
  handleCopySummary,
  copiedSummary: externalCopiedSummary,
  handleCopyPng,
  copyingPng = false,
  copiedPng = false,
  handleDownloadPng,
  downloadingPng = false,
  className = "",
  isDirty = false,
}: ExportActionsBarProps) {
  const [internalCopied, setInternalCopied] = useState(false);
  const isCopied = externalCopiedSummary ?? internalCopied;

  const hasConflict = Boolean(ownershipConflict?.has_conflict && !ownershipConflict?.resolved);

  const onCopySummaryClick = () => {
    if (handleCopySummary) {
      handleCopySummary();
      return;
    }

    const eff = { ...formValues, ...previewFields };
    const summaryLines = [
      "📋 MOTOR INSURANCE QUOTATION SUMMARY",
      "────────────────────────────────",
      `Insurer: ${companyName || eff.insurance_company || "Standard"}`,
      `Vehicle Plate: ${eff.vehicle_no || "—"}`,
      `Vehicle Model: ${eff.car_model || "—"}`,
      `Engine CC: ${eff.engine_cc || "—"}`,
      `Coverage: ${eff.coverage_type || "Comprehensive"}`,
      `Sum Insured: RM ${eff.sum_insured || "—"}`,
      `NCD: ${eff.ncd_percent || "0"}%`,
      `Basic Premium: RM ${eff.premium || "—"}`,
      `Road Tax: RM ${eff.roadtax || "0.00"}`,
      `Runner / Service Fee: RM ${eff.service_fee || "0.00"}`,
      "────────────────────────────────",
      `TOTAL PAYABLE: RM ${eff.total_amount || "—"}`,
      "",
      "Generated via Risklocker",
    ];

    const text = summaryLines.join("\n");
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        setInternalCopied(true);
        setTimeout(() => setInternalCopied(false), 2000);
      });
    }
  };

  const onWhatsAppExportClick = () => {
    const eff = { ...formValues, ...previewFields };
    const waText = [
      "📋 *MOTOR INSURANCE QUOTATION*",
      "─────────────────────────",
      `*Insurer:* ${companyName || eff.insurance_company || "Standard"}`,
      `*Vehicle Plate:* ${eff.vehicle_no || "—"}`,
      `*Vehicle Model:* ${eff.car_model || "—"}`,
      `*Engine CC:* ${eff.engine_cc || "—"}`,
      `*Coverage:* ${eff.coverage_type || "Comprehensive"}`,
      `*Sum Insured:* RM ${eff.sum_insured || "—"}`,
      `*NCD:* ${eff.ncd_percent || "0"}%`,
      `*Basic Premium:* RM ${eff.premium || "—"}`,
      `*Road Tax:* RM ${eff.roadtax || "0.00"}`,
      "─────────────────────────",
      `*TOTAL PAYABLE: RM ${eff.total_amount || "—"}*`,
      "",
      "_Generated via Risklocker_",
    ].join("\n");

    const waUrl = `https://wa.me/?text=${encodeURIComponent(waText)}`;
    window.open(waUrl, "_blank");
  };

  return (
    <div className={`flex flex-wrap items-center gap-1.5 ${className}`}>
      {/* 1. Copy Summary Button */}
      <button
        type="button"
        onClick={onCopySummaryClick}
        className={`flex items-center gap-1 rounded-md border border-[var(--rl-border)] px-2.5 py-1 text-xs font-semibold transition-all cursor-pointer ${
          isCopied
            ? "bg-emerald-50 text-emerald-800 border-emerald-300"
            : "bg-white text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-gray-50 shadow-2xs"
        }`}
        title="Copy structured quotation summary text to clipboard"
      >
        {isCopied ? (
          <Check size={13} weight="bold" className="text-emerald-600" />
        ) : (
          <Copy size={13} weight="bold" />
        )}
        <span>{isCopied ? "Summary Copied!" : "Copy Summary"}</span>
      </button>

      {/* 2. WhatsApp Export Trigger */}
      <button
        type="button"
        onClick={onWhatsAppExportClick}
        className="flex items-center gap-1 rounded-md border border-emerald-300 bg-emerald-50/70 hover:bg-emerald-100/90 text-emerald-800 px-2.5 py-1 text-xs font-semibold transition-all cursor-pointer shadow-2xs"
        title="Format quotation summary and share directly to client via WhatsApp"
      >
        <PaperPlaneRight size={13} weight="bold" className="text-emerald-600" />
        <span>WhatsApp</span>
      </button>

      {/* 3. PNG Quick Actions (if handlers provided) */}
      {handleCopyPng && handleDownloadPng ? (
        <div className="flex items-center rounded-lg border border-[var(--rl-border)] bg-gray-100 p-0.5 shadow-2xs">
          <button
            type="button"
            onClick={handleCopyPng}
            disabled={copyingPng}
            className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold transition-all cursor-pointer ${
              copiedPng
                ? "bg-emerald-50 text-emerald-800"
                : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-white"
            }`}
            title={isDirty ? "Save changes first to copy PNG" : "Copy quotation canvas to clipboard as image"}
          >
            {copiedPng ? <Check size={12} weight="bold" className="text-emerald-600" /> : <Copy size={12} weight="bold" />}
            <span>{copiedPng ? "Copied!" : copyingPng ? "Copying..." : "PNG"}</span>
          </button>
          <div className="h-3.5 w-px bg-gray-200" />
          <button
            type="button"
            onClick={handleDownloadPng}
            disabled={downloadingPng}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-white transition-all cursor-pointer"
            title={isDirty ? "Save changes first to download PNG" : "Download high-resolution PNG image"}
          >
            <DownloadSimple size={12} weight="bold" />
            <span>{downloadingPng ? "Saving..." : "Save PNG"}</span>
          </button>
        </div>
      ) : null}

      {/* 4. Official PDF Download Button */}
      <Button
        variant={hasConflict ? "secondary" : "primary"}
        size="sm"
        icon={hasConflict ? <Lock weight="bold" className="text-amber-500" /> : <FilePdf weight="bold" />}
        onClick={handleDownloadPdf}
        disabled={pdfLoading}
        title={
          hasConflict
            ? "Action Required: Resolve Vehicle Ownership before exporting PDF"
            : isDirty
            ? "Save changes first to download PDF"
            : "Open in new tab and download official PDF"
        }
      >
        {pdfLoading ? "Generating..." : hasConflict ? "Resolve Conflict" : "Download PDF"}
      </Button>
    </div>
  );
}
