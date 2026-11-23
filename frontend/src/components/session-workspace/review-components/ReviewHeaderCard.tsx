"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import type { Route } from "next";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { StatusBadge } from "@/components/status-badge";
import { GuidedTour } from "@/components/guided-tour";
import {
  ArrowsClockwise,
  ArrowSquareOut,
  CaretLeft,
  Columns,
  Eye,
  FilePdf,
  FloppyDisk,
  ListChecks,
  PencilSimple,
  Sparkle,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useOpenInNewTabPreference } from "@/hooks/useOpenInNewTabPreference";
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
  benefitsColCollapsed: boolean;
  setBenefitsColCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
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
  redetecting?: boolean;
  onStartRedetect?: () => void;
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
  benefitsColCollapsed,
  setBenefitsColCollapsed,
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
  redetecting: externalRedetecting = false,
  onStartRedetect,
}: ReviewHeaderCardProps) {
  const { toast } = useToast();
  const { openInNewTab } = useOpenInNewTabPreference();
  const [internalRedetecting, setInternalRedetecting] = useState(false);
  const redetecting = externalRedetecting || internalRedetecting;
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
    if (onStartRedetect) {
      if (mutation.dirty) {
        setRedetectDialogOpen(true);
      } else {
        onStartRedetect();
      }
      return;
    }
    setRedetectDialogOpen(true);
  };

  const confirmRedetect = async () => {
    setRedetectDialogOpen(false);
    if (onStartRedetect) {
      onStartRedetect();
      return;
    }
    setInternalRedetecting(true);
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
      setInternalRedetecting(false);
    }
  };

  const metadataTitle = [
    workspace.created_by_email || workspace.created_by
      ? `Uploaded: ${workspace.created_by_email || workspace.created_by}`
      : null,
    workspace.last_edited_by_email || workspace.last_edited_by
      ? `Last edited: ${workspace.last_edited_by_email || workspace.last_edited_by}`
      : null,
    mutation.lastSavedAt && !mutation.dirty && !mutation.saving
      ? `Saved ${new Date(mutation.lastSavedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`
      : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <header className="sticky top-[44px] lg:static z-20 shrink-0 w-full border-b border-[var(--rl-border)] bg-[var(--rl-surface)] px-2.5 py-1 shadow-xs">
      <div className="flex w-full flex-wrap items-center justify-between gap-x-2 gap-y-1">
        {/* Left Section: Compact Single-Row Workspace Identity */}
        <div className="flex flex-wrap items-center gap-1 min-w-0">
          {onBack ? (
            <button
              type="button"
              onClick={onBack}
              className="flex items-center gap-1 rounded-md border border-[var(--rl-border)] bg-white px-1.5 py-0.5 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-gray-50 transition-colors cursor-pointer shadow-2xs"
              title="Return to previous screen"
            >
              <CaretLeft size={12} weight="bold" />
              <span>Back</span>
            </button>
          ) : null}

          <h1 className="text-xs font-bold tracking-tight text-[var(--rl-text-strong)] whitespace-nowrap">
            Quotation Workspace
          </h1>

          {/* 1-Click Document Type Toggle */}
          <div className="inline-flex items-center rounded-md border border-[var(--rl-border)] bg-[var(--rl-surface-subtle)] p-0.5 text-[10px] font-semibold shadow-2xs">
            <button
              type="button"
              onClick={() => handleToggleDocumentType("quotation")}
              disabled={togglingDocType}
              className={`px-1.5 py-0.5 rounded transition-colors cursor-pointer ${
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
              className={`px-1.5 py-0.5 rounded transition-colors cursor-pointer ${
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
              className="inline-flex items-center gap-1 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-900 border border-amber-500/30"
              title="Test upload: isolated from customer records and hit & miss tracking"
            >
              <Sparkle size={10} weight="fill" className="text-amber-600" />
              Test
            </span>
          ) : null}

          {companyName ? <Badge variant="default">{companyName}</Badge> : null}
          <StatusBadge status={workspace.status} />

          {mutation.dirty ? (
            <Badge variant="warning">
              {mutation.dirtyPaths.length} unsaved
            </Badge>
          ) : mutation.saveError ? (
            <Badge variant="danger">Save failed</Badge>
          ) : null}

          {/* Compact Vehicle & Customer Badge (with audit hover tooltip) */}
          <span
            title={metadataTitle || undefined}
            className="inline-flex items-center gap-1 rounded bg-neutral-100 border border-neutral-200 px-1.5 py-0.5 text-[10px] text-[var(--rl-text-strong)] font-mono font-medium shadow-2xs max-w-[170px] 2xl:max-w-[230px]"
          >
            <strong className="font-bold text-neutral-900 shrink-0">{formValues.vehicle_no || "Draft"}</strong>
            <span className="text-neutral-400">·</span>
            <span className="truncate">{formValues.customer_name || "Client"}</span>
          </span>
        </div>

        {/* Right Section: 4-Panel Layout Switcher, Save & Export Actions */}
        <div className="flex flex-wrap items-center gap-1">
          <GuidedTour
            storageKey="tour:session-workspace"
            title="Quotation Workspace"
            launcherLabel="Help"
            description="Review the AI-extracted values, pin the insurer catalog (and package tier), preview in real time, and customize benefits."
            steps={[
              { target: ".rl-tour-template", title: "Master template & catalog", body: "Pin the published insurer catalog and template profile here." },
              { target: ".rl-tour-fields", title: "Extracted values", body: "AI-extracted policy and vehicle details. Edit anything here directly." },
              { target: ".rl-tour-preview", title: "Live preview", body: "Real-time preview of the quotation PDF. Updates instantly as you edit." },
              { target: ".rl-tour-benefits", title: "Benefit Edit", body: "Edit Free Added Coverage (Box 1) and Add-on Matrix (Box 2) side-by-side with the live preview." },
            ]}
          />

          {/* Unified 4-Panel Switcher: Source PDF | Form | Preview | Benefit Edit */}
          <div className="flex items-center gap-0.5 rounded-md border border-[var(--rl-border)] bg-gray-100 p-0.5 shadow-2xs">
            <button
              type="button"
              onClick={() => setPdfOpen((v) => !v)}
              className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold transition-all cursor-pointer ${
                pdfOpen
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-white/50"
              }`}
              title={pdfOpen ? "Hide PDF" : "Show source PDF"}
              aria-label={pdfOpen ? "Hide PDF" : "Show source PDF"}
            >
              <FilePdf size={12} weight={pdfOpen ? "fill" : "bold"} className={pdfOpen ? "text-[var(--rl-red)]" : ""} />
              <span>Source PDF</span>
            </button>
            <button
              type="button"
              onClick={() => setFormCollapsed((v) => !v)}
              className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold transition-all cursor-pointer ${
                !formCollapsed
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-white/50"
              }`}
              title={!formCollapsed ? "Hide Form & Extracted Values panel" : "Show Form & Extracted Values panel"}
            >
              <PencilSimple size={12} weight={!formCollapsed ? "fill" : "bold"} className={!formCollapsed ? "text-[var(--rl-black)]" : ""} />
              <span>Form</span>
            </button>
            <button
              type="button"
              onClick={() => setPreviewColCollapsed((v) => !v)}
              className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold transition-all cursor-pointer ${
                !previewColCollapsed
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-white/50"
              }`}
              title={!previewColCollapsed ? "Hide Live Preview panel" : "Show Live Preview panel"}
            >
              <Eye size={12} weight={!previewColCollapsed ? "fill" : "bold"} className={!previewColCollapsed ? "text-[var(--rl-black)]" : ""} />
              <span>Preview</span>
            </button>
            <button
              type="button"
              onClick={() => setBenefitsColCollapsed((v) => !v)}
              className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold transition-all cursor-pointer ${
                !benefitsColCollapsed
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-white/50"
              }`}
              title={!benefitsColCollapsed ? "Hide Benefit Edit panel" : "Show Benefit Edit panel"}
            >
              <ListChecks size={12} weight={!benefitsColCollapsed ? "fill" : "bold"} className={!benefitsColCollapsed ? "text-[var(--rl-red)]" : ""} />
              <span>Benefit Edit</span>
            </button>
          </div>

          <Button
            variant="secondary"
            size="sm"
            icon={<ArrowsClockwise className={redetecting ? "animate-spin text-amber-600" : ""} weight="bold" />}
            onClick={handleRedetect}
            disabled={redetecting}
            className="cursor-pointer bg-white !h-7 !min-h-[26px] !px-2 !text-[11px]"
            title="Run multi-pass visual logo & deep AI verification from source PDF"
          >
            {redetecting ? "Re-detecting..." : "Re-detect"}
          </Button>

          {workspace.tenure_id && !workspace.is_test && (
            <Link
              href={`/comparison?tenure_id=${workspace.tenure_id}` as Route}
              target={openInNewTab ? "_blank" : undefined}
              rel={openInNewTab ? "noopener noreferrer" : undefined}
              className="inline-flex items-center gap-1 min-h-[26px] h-7 px-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white hover:border-[var(--rl-black)] text-[var(--rl-text-strong)] text-[11px] font-semibold transition-colors shadow-2xs"
              title="Open Marketing Comparison Matrix for this quotation"
            >
              <Columns size={12} weight="bold" />
              <span>Compare</span>
              {openInNewTab && <ArrowSquareOut size={11} weight="bold" className="text-[var(--rl-text-muted)]" />}
            </Link>
          )}

          <Button
            size="sm"
            variant={mutation.dirty ? "primary" : "secondary"}
            loading={mutation.saving}
            icon={<FloppyDisk weight="bold" />}
            onClick={() => saveAndCheckLearning()}
            className="!h-7 !min-h-[26px] !px-2 !text-[11px]"
            title={metadataTitle || "Save workspace changes"}
          >
            {mutation.saving ? "Saving..." : mutation.dirty ? "Save & Sync" : "Saved"}
          </Button>

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
