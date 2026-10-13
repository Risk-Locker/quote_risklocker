"use client";

import { useState } from "react";
import { toBlob, toPng } from "html-to-image";

export function useSnapshotExport(
  gridRef: React.RefObject<HTMLDivElement | null>,
  vehicleNo?: string
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
        alert("Comparison snapshot copied to clipboard!");
      }
    } catch (err: any) {
      alert("Failed to copy snapshot: " + (err.message || String(err)));
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
      alert("Failed to download snapshot: " + (err.message || String(err)));
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
