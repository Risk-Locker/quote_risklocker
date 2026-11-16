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
  const [pendingExportAction, setPendingExportAction] = useState<"copy_png" | "download_png" | "download_pdf" | null>(null);

  async function generateCanvasBlob(): Promise<Blob | null> {
    const live = document.getElementById("rl-live-canvas-inner");
    if (!live || !previewTemplate) return null;

    const width = previewTemplate.config.canvas?.width || 794;
    const height = canvasH;

    return await toBlob(live, {
      cacheBust: false,
      backgroundColor: "#ffffff",
      width,
      height,
      pixelRatio: 4,
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
    await flushActiveInput();
    if (mutation.dirty) {
      try {
        await save();
      } catch (err) {
        console.warn("Could not save workspace before copying PNG, proceeding with live canvas:", err);
      }
    }
    setCopyingPng(true);
    setActionError(null);
    try {
      const blob = await generateCanvasBlob();
      if (!blob) throw new Error("Could not capture quotation template canvas.");

      if (typeof ClipboardItem !== "undefined" && navigator.clipboard && typeof navigator.clipboard.write === "function") {
        await navigator.clipboard.write([
          new ClipboardItem({ "image/png": blob }),
        ]);
        setCopiedPng(true);
        setToastMessage("High-definition quotation PNG copied to clipboard!");
        setTimeout(() => setCopiedPng(false), 2500);
        return;
      }

      const url = URL.createObjectURL(blob);
      triggerDownload(url, `quotation_${formValues.vehicle_no || id}.png`);
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      setToastMessage("Quotation PNG downloaded (clipboard was restricted by browser).");
    } catch (err: unknown) {
      console.error("[handleCopyPng error]", err);
      setActionError("Could not export quotation PNG: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setCopyingPng(false);
    }
  }

  async function executeDownloadPng() {
    await flushActiveInput();
    if (mutation.dirty) {
      try {
        await save();
      } catch (err) {
        console.warn("Could not save workspace before downloading PNG, proceeding with live canvas:", err);
      }
    }
    setDownloadingPng(true);
    setActionError(null);
    try {
      const blob = await generateCanvasBlob();
      if (!blob) throw new Error("Could not generate quotation image blob");
      const url = URL.createObjectURL(blob);
      try {
        window.open(url, "_blank");
      } catch {
        // Best effort
      }
      triggerDownload(url, `quotation_${formValues.vehicle_no || id}.png`);
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      setToastMessage("High-definition quotation PNG opened in new tab and downloaded!");
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
    await flushActiveInput();
    if (!workspace) return;
    setPdfLoading(true);
    setActionError(null);

    if (mutation.dirty) {
      try {
        await save();
      } catch (err) {
        console.warn("Could not save workspace before exporting PDF:", err);
      }
    }

    try {
      const conflict = await api<{ has_conflict: boolean; resolved: boolean }>(`/sessions/${id}/ownership-conflict`).catch(() => null);
      if (conflict?.has_conflict && !conflict?.resolved) {
        throw new Error("Action Required: Vehicle ownership conflict detected. Please resolve it on the Review step before generating the PDF.");
      }

      const requested = await api<{ job?: { id: string }; version?: { id: string } }>(
        `/sessions/${id}/versions`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({ draft_revision: workspace.revision }),
        }
      );

      const jobId = requested.job?.id;
      if (jobId) {
        let completed = false;
        for (let attempt = 0; attempt < 90; attempt += 1) {
          const status = await api<{ job: { state: string; error?: { message?: string } } }>(`/jobs/${jobId}`);
          if (status.job.state === "completed") {
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

      const versionId = requested.version?.id || (workspace.versions && workspace.versions[0]?.id);
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
    pendingExportAction,
    setPendingExportAction,
    handleCopyPng,
    handleDownloadPng,
    handleDownloadPdf,
    handleCopyExtractedInfo,
    confirmAndExecuteExport,
    triggerDownload,
  };
}
