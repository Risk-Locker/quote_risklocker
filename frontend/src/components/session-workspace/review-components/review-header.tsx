"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status-badge";
import { GuidedTour } from "@/components/guided-tour";
import {
  Check,
  Copy,
  DownloadSimple,
  Eye,
  FilePdf,
  FloppyDisk,
  Lock,
  PencilSimple,
  Sparkle,
} from "@phosphor-icons/react";
import type { WorkspaceSnapshot, MutationState } from "../types";

export interface ReviewHeaderProps {
  workspace: WorkspaceSnapshot;
  companyName: string | null | undefined;
  mutation: MutationState;
  formValues: Record<string, string>;
  pdfOpen: boolean;
  setPdfOpen: React.Dispatch<React.SetStateAction<boolean>>;
  formCollapsed: boolean;
  setFormCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  previewColCollapsed: boolean;
  setPreviewColCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  saveAndCheckLearning: () => void;
  copiedPng: boolean;
  copyingPng: boolean;
  handleCopyPng: () => void;
  downloadingPng: boolean;
  handleDownloadPng: () => void;
  ownershipConflict: any;
  handleDownloadPdf: () => void;
  pdfLoading: boolean;
}

export function ReviewHeader({
  workspace,
  companyName,
  mutation,
  formValues,
  pdfOpen,
  setPdfOpen,
  formCollapsed,
  setFormCollapsed,
  previewColCollapsed,
  setPreviewColCollapsed,
  saveAndCheckLearning,
  copiedPng,
  copyingPng,
  handleCopyPng,
  downloadingPng,
  handleDownloadPng,
  ownershipConflict,
  handleDownloadPdf,
  pdfLoading,
}: ReviewHeaderProps) {
  return (
    <header className="sticky top-[56px] z-20 w-full border-b border-[var(--rl-border)] bg-[var(--rl-surface)] px-4 py-3 shadow-xs">
      <div className="mx-auto flex w-full max-w-[1800px] flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-[var(--rl-text-strong)]">Quotation Workspace</h1>
            {workspace.is_test ? (
              <span
                className="inline-flex items-center gap-1 rounded bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-900 border border-amber-500/30"
                title="Test upload: isolated from customer records and hit & miss tracking"
              >
                <Sparkle size={12} weight="fill" className="text-amber-600" />
                Test Upload (Sandbox)
              </span>
            ) : null}
            {companyName ? <Badge variant="default">{companyName}</Badge> : null}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <StatusBadge status={workspace.status} />
            {mutation.dirty ? <Badge variant="warning">Unsaved changes</Badge> : <Badge variant="success">All changes saved</Badge>}
            <span className="text-xs text-[var(--rl-text-muted)] font-mono">
              {formValues.vehicle_no || "Draft"} · {formValues.customer_name || "Client"}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <GuidedTour
            storageKey="tour:session-workspace"
            title="Quotation Workspace"
            description="Review the AI-extracted values, pin the insurer catalog (and package tier), customize benefits, and generate the final PDF."
            steps={[
              { target: ".rl-tour-template", title: "Master template & catalog", body: "Pin the published insurer catalog and template profile here." },
              { target: ".rl-tour-fields", title: "Extracted values", body: "AI-extracted policy and vehicle details. Edit anything here directly." },
              { target: ".rl-tour-benefits", title: "Benefits & add-ons", body: "Defaults are the included benefits. Add-ons are payable extras." },
              { target: ".rl-tour-preview", title: "Live preview", body: "Real-time preview of the quotation PDF. Updates instantly as you edit." },
            ]}
          />

          {/* Unified 3-Panel Layout Switcher */}
          <div className="flex items-center gap-0.5 rounded-lg border border-[var(--rl-border)] bg-gray-100 p-0.5 shadow-2xs">
            <button
              type="button"
              onClick={() => setPdfOpen((v) => !v)}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all ${
                pdfOpen
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-white/50"
              }`}
              title={pdfOpen ? "Hide PDF" : "Show source PDF"}
              aria-label={pdfOpen ? "Hide PDF" : "Show source PDF"}
            >
              <FilePdf size={14} weight={pdfOpen ? "fill" : "bold"} className={pdfOpen ? "text-[var(--rl-red)]" : ""} />
              <span>PDF</span>
            </button>
            <button
              type="button"
              onClick={() => setFormCollapsed((v) => !v)}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all ${
                !formCollapsed
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-white/50"
              }`}
              title={!formCollapsed ? "Hide Form & Extracted Values panel" : "Show Form & Extracted Values panel"}
            >
              <PencilSimple size={14} weight={!formCollapsed ? "fill" : "bold"} className={!formCollapsed ? "text-[var(--rl-black)]" : ""} />
              <span>Form</span>
            </button>
            <button
              type="button"
              onClick={() => setPreviewColCollapsed((v) => !v)}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all ${
                !previewColCollapsed
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-white/50"
              }`}
              title={!previewColCollapsed ? "Hide Live Preview & Benefits panel" : "Show Live Preview & Benefits panel"}
            >
              <Eye size={14} weight={!previewColCollapsed ? "fill" : "bold"} className={!previewColCollapsed ? "text-[var(--rl-black)]" : ""} />
              <span>Preview</span>
            </button>
          </div>

          <Button
            variant={mutation.dirty ? "primary" : "secondary"}
            loading={mutation.saving}
            icon={<FloppyDisk weight="bold" />}
            onClick={() => saveAndCheckLearning()}
          >
            {mutation.dirty ? "Save Changes" : "Saved"}
          </Button>

          {/* PNG Actions Button (Copy as PNG | Download PNG) */}
          <Button
            variant="secondary"
            size="sm"
            icon={copiedPng ? <Check weight="bold" className="text-emerald-600" /> : <Copy weight="bold" />}
            onClick={handleCopyPng}
            disabled={copyingPng}
            title={mutation.dirty ? "Save changes first to copy PNG" : "Copy high-resolution quotation canvas to clipboard as image"}
          >
            {copiedPng ? "Copied PNG!" : copyingPng ? "Copying..." : "Copy as PNG"}
          </Button>

          <Button
            variant="secondary"
            size="sm"
            icon={<DownloadSimple weight="bold" />}
            onClick={handleDownloadPng}
            disabled={downloadingPng}
            title={mutation.dirty ? "Save changes first to download PNG" : "Open in new tab and download high-resolution PNG"}
          >
            {downloadingPng ? "Generating..." : "Download as PNG"}
          </Button>

          {/* Unified Action 3: Download PDF */}
          <Button
            variant={ownershipConflict?.has_conflict && !ownershipConflict?.resolved ? "secondary" : "primary"}
            size="sm"
            icon={ownershipConflict?.has_conflict && !ownershipConflict?.resolved ? <Lock weight="bold" className="text-amber-500" /> : <FilePdf weight="bold" />}
            onClick={handleDownloadPdf}
            disabled={pdfLoading}
            title={
              ownershipConflict?.has_conflict && !ownershipConflict?.resolved
                ? "Action Required: Resolve Vehicle Ownership before exporting PDF"
                : mutation.dirty
                ? "Save changes first to download PDF"
                : "Open in new tab and download official PDF"
            }
          >
            {pdfLoading ? "Generating..." : ownershipConflict?.has_conflict && !ownershipConflict?.resolved ? "Resolve Conflict to Export" : "Download PDF"}
          </Button>
        </div>
      </div>
    </header>
  );
}
