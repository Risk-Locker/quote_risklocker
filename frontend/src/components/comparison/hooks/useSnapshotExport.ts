"use client";

import { useState } from "react";
import { toBlob, toPng } from "html-to-image";

export function useSnapshotExport(
  gridRef: React.RefObject<HTMLDivElement | null>,
  vehicleNo?: string,
  onNotify?: (type: "success" | "error", title: string, message: string) => void
) {
  const [copyingSnapshot, setCopyingSnapshot] = useState(false);
  const [downloadingSnapshot, setDownloadingSnapshot] = useState(false);

  const handleCopySnapshot = async () => {
    if (!gridRef.current) return;
    try {
      setCopyingSnapshot(true);
      const blob = await toBlob(gridRef.current, {
        pixelRatio: 2,
        backgroundColor: "#ffffff",
        cacheBust: true,
      });
      if (blob) {
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        onNotify?.("success", "Snapshot Copied", "Comparison snapshot copied to clipboard.");
      }
    } catch (err: any) {
      const msg = "Failed to copy snapshot: " + (err.message || String(err));
      if (onNotify) onNotify("error", "Copy Snapshot Failed", msg);
      else console.error(msg);
    } finally {
      setCopyingSnapshot(false);
    }
  };

  const handleDownloadSnapshot = async () => {
    if (!gridRef.current) return;
    try {
      setDownloadingSnapshot(true);
      const dataUrl = await toPng(gridRef.current, {
        pixelRatio: 2,
        backgroundColor: "#ffffff",
        cacheBust: true,
      });
      const link = document.createElement("a");
      link.download = `quotation-comparison-${vehicleNo || "matrix"}.png`;
      link.href = dataUrl;
      link.click();
    } catch (err: any) {
      const msg = "Failed to download snapshot: " + (err.message || String(err));
      if (onNotify) onNotify("error", "Download Snapshot Failed", msg);
      else console.error(msg);
    } finally {
      setDownloadingSnapshot(false);
    }
  };

  return {
    copyingSnapshot,
    downloadingSnapshot,
    handleCopySnapshot,
    handleDownloadSnapshot,
  };
}
