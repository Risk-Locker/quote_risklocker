"use client";

import React, { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { StatusBadge } from "@/components/status-badge";
import { GuidedTour } from "@/components/guided-tour";
import {
  ArrowsClockwise,
  CaretLeft,
  Eye,
  FilePdf,
  FloppyDisk,
  PencilSimple,
  Sparkle,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import type { WorkspaceSnapshot, MutationState } from "../types";
import { ExportActionsBar } from "./ExportActionsBar";

export interface ReviewHeaderCardProps {
  workspace: WorkspaceSnapshot;
  companyName: string | null | undefined;
  mutation: MutationState;
  formValues: Record<string, string>;
  previewFields?: Record<string, string>;
  onBack?: () => void;
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
  handleCopySummary?: () => void;
  copiedSummary?: boolean;
}

export function ReviewHeaderCard({
  workspace,
  companyName,
  mutation,
  formValues,
  previewFields = {},
  onBack,
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
  handleCopySummary,
  copiedSummary,
}: ReviewHeaderCardProps) {
  const { toast } = useToast();
  const [redetecting, setRedetecting] = useState(false);
  const [redetectDialogOpen, setRedetectDialogOpen] = useState(false);
  const [docType, setDocType] = useState<"quotation" | "covernote">(
    workspace.document_type === "covernote" ? "covernote" : "quotation"
  );
  const [pendingDocType, setPendingDocType] = useState<"quotation" | "covernote" | null>(null);
  const [togglingDocType, setTogglingDocType] = useState(false);

  useEffect(() => {
    if (workspace.document_type) {
      setDocType(workspace.document_type === "covernote" ? "covernote" : "quotation");
    }
  }, [workspace.document_type]);

  const handleToggleDocumentType = (newType: "quotation" | "covernote") => {
    if (newType === docType || togglingDocType) return;
    setPendingDocType(newType);
  };

  const confirmToggleDocumentType = async () => {
    if (!pendingDocType || togglingDocType) return;
    const newType = pendingDocType;
    setPendingDocType(null);
    setTogglingDocType(true);
    try {
      const res = await api<{ status: string; document_type: string }>(`/sessions/${workspace.session_id}`, {
        method: "PATCH",
        body: JSON.stringify({ document_type: newType }),
      });
      if (res?.status === "success") {
        setDocType(newType);
        workspace.document_type = newType;
        toast(
          newType === "covernote"
            ? "Designated as official Cover Note (Issued Policy)."
            : "Reverted document to Quotation.",
          "success"
        );
      }
    } catch (err: any) {
      toast("Failed to update document type: " + (err?.message || "Server error"), "error");
    } finally {
      setTogglingDocType(false);
    }
  };

  const handleRedetect = () => {
    setRedetectDialogOpen(true);
  };

  const confirmRedetect = async () => {
    setRedetectDialogOpen(false);
    setRedetecting(true);
    try {
      const res = await api<{ success: boolean; message?: string; changed_fields?: string[] }>(
        `/sessions/${workspace.session_id}/rescan`,
        {
          method: "POST",
          body: JSON.stringify({ mode: "in_place", engine: "deep" }),
        }
      );
      const changedSuffix = res?.changed_fields?.length ? ` (${res.changed_fields.length} field(s) updated)` : "";
      toast((res?.message || "Deep Re-detection completed.") + changedSuffix, "success");
      window.location.reload();
    } catch (err: any) {
      toast("Failed to re-detect: " + (err?.message || "Server error"), "error");
      setRedetecting(false);
    }
  };

  return (
    <header className="sticky top-[56px] z-20 w-full border-b border-[var(--rl-border)] bg-[var(--rl-surface)] px-4 py-3 shadow-xs">
      <div className="mx-auto flex w-full max-w-[1800px] flex-wrap items-center justify-between gap-3">
        {/* Left Section: Back Button, Session Header Status & Vehicle Quick Badge */}
        <div className="flex items-start gap-3">
          {onBack ? (
            <button
              type="button"
              onClick={onBack}
              className="mt-0.5 flex items-center gap-1 rounded-md border border-[var(--rl-border)] bg-white px-2 py-1 text-xs font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-gray-50 transition-colors cursor-pointer shadow-2xs"
              title="Return to previous screen"
            >
              <CaretLeft size={14} weight="bold" />
              <span>Back</span>
            </button>
          ) : null}

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-bold text-[var(--rl-text-strong)]">Quotation Workspace</h1>
              
              {/* 1-Click Document Type Toggle */}
              <div className="inline-flex items-center rounded-md border border-[var(--rl-border)] bg-[var(--rl-surface-subtle)] p-0.5 text-xs font-semibold shadow-2xs">
                <button
                  type="button"
                  onClick={() => handleToggleDocumentType("quotation")}
                  disabled={togglingDocType}
                  className={`px-2 py-0.5 rounded transition-colors cursor-pointer ${
                    docType === "quotation"
                      ? "bg-white text-[var(--rl-text-strong)] shadow-xs font-bold"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                  title="Categorize as Quotation (Comparison option)"
                >
                  Quotation
                </button>
                <button
                  type="button"
                  onClick={() => handleToggleDocumentType("covernote")}
                  disabled={togglingDocType}
                  className={`px-2 py-0.5 rounded transition-colors cursor-pointer ${
                    docType === "covernote"
                      ? "bg-emerald-600 text-white shadow-xs font-bold"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                  title="Categorize as Official Cover Note (Issued Policy)"
                >
                  Cover Note
                </button>
              </div>

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

            {/* Vehicle Quick Badge & Status Line */}
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <StatusBadge status={workspace.status} />
              {mutation.dirty ? (
                <Badge variant="warning">
                  {mutation.dirtyPaths.length} unsaved change{mutation.dirtyPaths.length === 1 ? "" : "s"}
                </Badge>
              ) : mutation.saveError ? (
                <Badge variant="danger">Save failed</Badge>
              ) : (
                <Badge variant="success">All changes saved</Badge>
              )}
              
              {/* Vehicle Quick Badge */}
              <span className="inline-flex items-center gap-1 rounded bg-neutral-100 border border-neutral-200 px-2 py-0.5 text-xs text-[var(--rl-text-strong)] font-mono font-medium shadow-2xs">
                <strong className="font-bold text-neutral-900">{formValues.vehicle_no || "Draft"}</strong>
                <span className="text-neutral-400">·</span>
                <span>{formValues.customer_name || "Client"}</span>
              </span>

              {workspace.created_by_email || workspace.created_by ? (
                <span className="inline-flex items-center gap-1 rounded bg-neutral-100 px-2 py-0.5 text-[11px] font-medium text-neutral-700 border border-neutral-200">
                  <span className="text-neutral-400">Uploaded:</span>
                  <span className="font-semibold text-neutral-900">{workspace.created_by_email || workspace.created_by}</span>
                </span>
              ) : null}
              {workspace.last_edited_by_email || workspace.last_edited_by ? (
                <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-900 border border-amber-200">
                  <span className="text-amber-600">Last edited:</span>
                  <span className="font-bold text-amber-950">{workspace.last_edited_by_email || workspace.last_edited_by}</span>
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {/* Right Section: Layout Toggles, Save Button & Export Actions */}
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
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all cursor-pointer ${
                pdfOpen
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-white/50"
              }`}
              title={pdfOpen ? "Hide PDF" : "Show source PDF"}
              aria-label={pdfOpen ? "Hide PDF" : "Show source PDF"}
            >
              <FilePdf size={14} weight={pdfOpen ? "fill" : "bold"} className={pdfOpen ? "text-[var(--rl-red)]" : ""} />
              <span>Source PDF</span>
            </button>
            <button
              type="button"
              onClick={() => setFormCollapsed((v) => !v)}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all cursor-pointer ${
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
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all cursor-pointer ${
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
            variant="secondary"
            size="sm"
            icon={<ArrowsClockwise className={redetecting ? "animate-spin text-amber-600" : ""} weight="bold" />}
            onClick={handleRedetect}
            disabled={redetecting}
            className="cursor-pointer bg-white"
            title="Re-run AI & PDF detection to extract missing fields or benefits"
          >
            {redetecting ? "Re-detecting..." : "Re-detect"}
          </Button>

          <div className="flex items-center gap-2">
            {mutation.lastSavedAt && !mutation.dirty && !mutation.saving && (
              <span className="hidden sm:inline-block text-[11px] text-[var(--rl-text-muted)] font-medium">
                Saved {new Date(mutation.lastSavedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
            )}
            <Button
              variant={mutation.dirty ? "primary" : "secondary"}
              loading={mutation.saving}
              icon={<FloppyDisk weight="bold" />}
              onClick={() => saveAndCheckLearning()}
            >
              {mutation.saving ? "Saving..." : mutation.dirty ? "Save & Sync" : "Saved"}
            </Button>
          </div>

          {/* Modular Export Actions Bar */}
          <ExportActionsBar
            handleDownloadPdf={handleDownloadPdf}
            pdfLoading={pdfLoading}
            ownershipConflict={ownershipConflict}
            formValues={formValues}
            previewFields={previewFields}
            companyName={companyName}
            handleCopySummary={handleCopySummary}
            copiedSummary={copiedSummary}
            handleCopyPng={handleCopyPng}
            copyingPng={copyingPng}
            copiedPng={copiedPng}
            handleDownloadPng={handleDownloadPng}
            downloadingPng={downloadingPng}
            isDirty={mutation.dirty}
          />
        </div>
      </div>

      <Dialog
        open={Boolean(pendingDocType)}
        onOpenChange={(open) => {
          if (!open) setPendingDocType(null);
        }}
        title={
          pendingDocType === "covernote"
            ? "Designate as Official Cover Note?"
            : "Revert Document to Quotation?"
        }
        description={
          pendingDocType === "covernote"
            ? "This will anchor this document as the active Issued Policy for this renewal and advance the tenure stage to Issue Policy."
            : "This will unbind this document as the active Cover Note and return the tenure stage to Quotations."
        }
        onConfirm={confirmToggleDocumentType}
        confirmLabel="Confirm"
        confirmVariant="primary"
        loading={togglingDocType}
      />

      <Dialog
        open={redetectDialogOpen}
        onOpenChange={setRedetectDialogOpen}
        title="Deep Re-detect Quotation from Source PDF?"
        description="Runs multi-pass native PDF + Gemini Vision extraction and Malaysian domain verification (preserving KG/kW/CC units and commercial fee rules)."
        onConfirm={confirmRedetect}
        confirmLabel="Re-detect Now"
        confirmVariant="primary"
        loading={redetecting}
      />
    </header>
  );
}
