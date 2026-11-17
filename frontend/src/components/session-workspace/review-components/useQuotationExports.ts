"use client";

import { useCallback, useState } from "react";
import { toBlob, toPng } from "html-to-image";
import { api, fileUrl } from "@/lib/api";
import type { WorkspaceSnapshot, MutationState } from "../types";
import { FORM_FIELDS } from "./policy-fields-card";

export interface UseQuotationExportsOptions {
  id: string;
  workspace: WorkspaceSnapshot | null;
  mutation: MutationState;
  save: () => Promise<any>;
  formValues: Record<string, string>;
  previewFields: Record<string, string>;
  previewTemplate: any;
  canvasH: number;
  ownershipConflict: any;
  setConflictModalOpen: (open: boolean) => void;
  setToastMessage: (msg: string | null) => void;
  setActionError: (err: string | null) => void;
}

export function useQuotationExports({
  id,
  workspace,
  mutation,
  save,
  formValues,
  previewFields,
  previewTemplate,
  canvasH,
  ownershipConflict,
  setConflictModalOpen,
  setToastMessage,
  setActionError,
}: UseQuotationExportsOptions) {
  const [copyingPng, setCopyingPng] = useState(false);
  const [copiedPng, setCopiedPng] = useState(false);
  const [copiedInfo, setCopiedInfo] = useState(false);
  const [downloadingPng, setDownloadingPng] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [openingPreviewTab, setOpeningPreviewTab] = useState(false);
  const [pendingExportAction, setPendingExportAction] = useState<"copy_png" | "download_png" | "download_pdf" | null>(null);

  function dataUrlToBlob(dataUrl: string): Blob {
    const parts = dataUrl.split(",");
    const mime = parts[0].match(/:(.*?);/)?.[1] || "image/png";
    const bstr = atob(parts[1]);
    let n = bstr.length;
    const u8arr = new Uint8Array(n);
    while (n--) {
      u8arr[n] = bstr.charCodeAt(n);
    }
    return new Blob([u8arr], { type: mime });
  }

  async function generateCanvasPngDataUrl(): Promise<string | null> {
    const live = document.getElementById("rl-live-canvas-inner");
    if (!live || !previewTemplate) return null;

    const width = previewTemplate.config.canvas?.width || 794;
    const height = canvasH;

    return await toPng(live, {
      cacheBust: true,
      backgroundColor: "#ffffff",
      width,
      height,
      pixelRatio: 6, // Ultra-HD 8K-class rendering (4764x6738px)
      skipFonts: false,
      style: {
        transform: "none",
        transformOrigin: "top left",
        width: `${width}px`,
        height: `${height}px`,
        margin: "0",
        position: "static",
      },
    });
  }

  async function ensureWorkspaceSavedBeforeExport(): Promise<WorkspaceSnapshot> {
    await flushActiveInput();
    if (!workspace) {
      throw new Error("The quotation workspace is not loaded.");
    }
    if (!mutation.dirty) return workspace;
    const saved = await save();
    await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
    return saved;
  }

  async function ensureGeneratedPdfVersionId(activeWorkspace: WorkspaceSnapshot): Promise<string | undefined> {
    const conflict = await api<{ has_conflict: boolean; resolved: boolean }>(`/sessions/${id}/ownership-conflict`).catch(() => null);
    if (conflict?.has_conflict && !conflict?.resolved) {
      throw new Error("Action Required: Vehicle ownership conflict detected. Please resolve it on the Review step before generating the PDF.");
    }

    const requested = await api<{ job?: { id: string }; version?: { id: string } }>(
      `/sessions/${id}/versions`,
      {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ draft_revision: activeWorkspace.revision }),
      }
    );

    const jobId = requested.job?.id;
    let renderedVersionId = requested.version?.id;
    if (jobId) {
      let completed = false;
      for (let attempt = 0; attempt < 90; attempt += 1) {
        const status = await api<{
          job: { state: string; result?: { version_id?: string }; error?: { message?: string } };
        }>(`/jobs/${jobId}`);
        if (status.job.state === "completed") {
          renderedVersionId = status.job.result?.version_id || renderedVersionId;
          completed = true;
          break;
        }
        if (status.job.state === "failed" || status.job.state === "cancelled") {
          throw new Error(status.job.error?.message || "PDF generation did not complete.");
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
      }
      if (!completed) throw new Error("PDF generation is taking longer than expected. Please check your quotations list.");
    }

    return renderedVersionId || (activeWorkspace.versions && activeWorkspace.versions[0]?.id);
  }

  async function handleOpenNewQuotationTab() {
    setOpeningPreviewTab(true);
    setActionError(null);
    // Open synchronously on user click so browsers never popup-block after async PDF rendering
    const previewTab = window.open("", "_blank");
    if (previewTab) {
      previewTab.opener = null;
      previewTab.document.write(
        "<!doctype html><html><head><title>Generating Quotation PDF...</title></head><body style='margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:system-ui,sans-serif;background:#f5f5f7;color:#1b1717;'><div style='text-align:center'><div style='font-weight:700;font-size:15px'>Rendering RiskLocker Quotation PDF...</div><div style='font-size:12px;color:#64748b;margin-top:6px'>Opening in built-in PDF viewer momentarily.</div></div></body></html>"
      );
    }
    try {
      const activeWorkspace = await ensureWorkspaceSavedBeforeExport();
      const versionId = await ensureGeneratedPdfVersionId(activeWorkspace);
      const inlinePdfUrl = fileUrl(versionId ? `/versions/${versionId}/pdf?download=false` : `/sessions/${id}/pdf?download=false`);
      if (previewTab && !previewTab.closed) {
        previewTab.location.replace(inlinePdfUrl);
      } else {
        window.open(inlinePdfUrl, "_blank", "noopener,noreferrer");
      }
    } catch (err: unknown) {
      if (previewTab && !previewTab.closed) previewTab.close();
      setActionError("Could not open quotation PDF: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setOpeningPreviewTab(false);
    }
  }

  function triggerDownload(url: string, filename: string) {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  async function flushActiveInput() {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
  }

  async function executeCopyPng() {
    setCopyingPng(true);
    setActionError(null);
    try {
      await ensureWorkspaceSavedBeforeExport();
      const dataUrl = await generateCanvasPngDataUrl();
      if (!dataUrl) throw new Error("Could not capture quotation template canvas.");
      const blob = dataUrlToBlob(dataUrl);

      if (typeof ClipboardItem !== "undefined" && navigator.clipboard && typeof navigator.clipboard.write === "function") {
        await navigator.clipboard.write([
          new ClipboardItem({ "image/png": blob }),
        ]);
        setCopiedPng(true);
        setToastMessage("Ultra-HD 4K quotation PNG copied to clipboard!");
        setTimeout(() => setCopiedPng(false), 2500);
        return;
      }

      triggerDownload(dataUrl, `quotation_${formValues.vehicle_no || id}.png`);
      setToastMessage("4K quotation PNG downloaded (clipboard was restricted by browser).");
    } catch (err: unknown) {
      console.error("[handleCopyPng error]", err);
      setActionError("Could not export quotation PNG: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setCopyingPng(false);
    }
  }

  async function executeDownloadPng() {
    setDownloadingPng(true);
    setActionError(null);
    try {
      await ensureWorkspaceSavedBeforeExport();
      const dataUrl = await generateCanvasPngDataUrl();
      if (!dataUrl) throw new Error("Could not generate quotation image");
      triggerDownload(dataUrl, `quotation_${formValues.vehicle_no || id}.png`);
      setToastMessage("Ultra-HD 4K quotation PNG downloaded successfully!");
    } catch (err: unknown) {
      console.error("[handleDownloadPng error]", err);
      setActionError("Could not generate PNG for download: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setDownloadingPng(false);
    }
  }

  const handleCopyExtractedInfo = useCallback(() => {
    const lines: string[] = [];

    for (const field of FORM_FIELDS) {
      const val = field.kind === "total"
        ? (previewFields[field.name] || formValues[field.name] || "")
        : (formValues[field.name] ?? "");
      lines.push(`${field.label}: ${val || "—"}`);
    }

    const customEntries = Object.entries(workspace?.fields || {}).filter(
      ([k]) => !FORM_FIELDS.some((f) => f.name === k) && !k.startsWith("_")
    );
    if (customEntries.length > 0) {
      lines.push("");
      lines.push("--- Custom Fields ---");
      for (const [k, v] of customEntries) {
        const valStr = typeof v === "object" && v !== null && "value" in v ? String((v as any).value || "") : String(v || "");
        lines.push(`${k}: ${valStr || "—"}`);
      }
    }

    const extras = workspace?.extracted_benefits_section?.extras || [];
    if (extras.length > 0) {
      lines.push("");
      lines.push("--- Extra Benefits Detected ---");
      for (const extra of extras) {
        const parts: string[] = [extra.label];
        if (extra.coverage_limit) parts.push(`Limit: RM ${extra.coverage_limit}`);
        if (extra.cost) parts.push(`Cost: RM ${extra.cost}`);
        else parts.push("Cost: Included");
        if (extra.is_applied) parts.push("(Included in Grid)");
        lines.push(`- ${parts.join(" | ")}`);
      }
    }

    const textToCopy = lines.join("\n");
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(textToCopy).then(() => {
        setCopiedInfo(true);
        setToastMessage("All extracted information copied to clipboard!");
        setTimeout(() => setCopiedInfo(false), 2000);
      }).catch(() => {
        const textarea = document.createElement("textarea");
        textarea.value = textToCopy;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
        setCopiedInfo(true);
        setToastMessage("All extracted information copied to clipboard!");
        setTimeout(() => setCopiedInfo(false), 2000);
      });
    }
  }, [formValues, previewFields, workspace, setToastMessage]);

  async function executeDownloadPdf() {
    if (!workspace) return;
    setPdfLoading(true);
    setActionError(null);

    try {
      const activeWorkspace = await ensureWorkspaceSavedBeforeExport();
      const versionId = await ensureGeneratedPdfVersionId(activeWorkspace);
      const downloadPath = versionId ? `/versions/${versionId}/pdf?download=true` : `/sessions/${id}/pdf?download=true`;
      const downloadUrl = fileUrl(downloadPath);

      try {
        window.open(downloadUrl, "_blank");
      } catch {
        // Best effort popup
      }
      triggerDownload(downloadUrl, `quotation_${formValues.vehicle_no || id}.pdf`);
      setToastMessage("Official quotation PDF generated and downloaded!");
    } catch (err: unknown) {
      console.error("[handleDownloadPdf error]", err);
      setActionError("Could not generate PDF for download: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setPdfLoading(false);
    }
  }

  async function confirmAndExecuteExport(sentToClient: boolean) {
    const action = pendingExportAction;
    setPendingExportAction(null);
    if (!action) return;

    try {
      await ensureWorkspaceSavedBeforeExport();
    } catch (err: unknown) {
      setActionError("Could not save pending edits before export: " + (err instanceof Error ? err.message : String(err)));
      return;
    }

    if (!workspace?.is_test) {
      api(`/insights/sessions/${id}/activity`, {
        method: "POST",
        body: JSON.stringify({
          action_type: action === "download_pdf" ? "pdf_export" : "png_export",
          sent_to_client: sentToClient,
          summary: sentToClient
            ? `Sent quotation to client (${action === "download_pdf" ? "PDF" : "PNG"})`
            : `Internal save / export (${action === "download_pdf" ? "PDF" : "PNG"})`,
          version_number: (workspace?.versions?.length || 0) + 1,
        }),
      }).catch((err) => console.warn("Could not log export activity:", err));
    }

    if (action === "copy_png") {
      await executeCopyPng();
    } else if (action === "download_png") {
      await executeDownloadPng();
    } else if (action === "download_pdf") {
      await executeDownloadPdf();
    }
  }

  function handleCopyPng() {
    if (ownershipConflict?.has_conflict && !ownershipConflict?.resolved) {
      setConflictModalOpen(true);
      setToastMessage("Action Required: Please resolve the vehicle ownership conflict before exporting.");
      return;
    }
    setPendingExportAction("copy_png");
  }

  function handleDownloadPng() {
    if (ownershipConflict?.has_conflict && !ownershipConflict?.resolved) {
      setConflictModalOpen(true);
      setToastMessage("Action Required: Please resolve the vehicle ownership conflict before exporting.");
      return;
    }
    setPendingExportAction("download_png");
  }

  function handleDownloadPdf() {
    if (ownershipConflict?.has_conflict && !ownershipConflict?.resolved) {
      setConflictModalOpen(true);
      setToastMessage("Action Required: Please resolve the vehicle ownership conflict before exporting PDF.");
      return;
    }
    setPendingExportAction("download_pdf");
  }

  return {
    copyingPng,
    copiedPng,
    copiedInfo,
    downloadingPng,
    pdfLoading,
    openingPreviewTab,
    pendingExportAction,
    setPendingExportAction,
    handleCopyPng,
    handleDownloadPng,
    handleDownloadPdf,
    handleOpenNewQuotationTab,
    handleCopyExtractedInfo,
    confirmAndExecuteExport,
    triggerDownload,
  };
}
