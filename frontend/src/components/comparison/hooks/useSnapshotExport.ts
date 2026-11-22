"use client";

import { useState } from "react";
import { toBlob, toPng } from "html-to-image";

/**
 * Ensures web fonts and all <img> assets inside the target element are loaded and decoded
 * prior to high-DPI capture so exported PNGs never contain missing logos, QR codes, or fallback fonts.
 */
export async function waitForSnapshotAssets(element: HTMLElement): Promise<void> {
  if (typeof document !== "undefined" && document.fonts?.ready) {
    try {
      await document.fonts.ready;
    } catch {
      // Ignore font readiness rejections and continue capture
    }
  }

  const images = Array.from(element.querySelectorAll("img"));
  await Promise.all(
    images.map(async (img) => {
      if (!img.complete) {
        await new Promise<void>((resolve) => {
          const timer = window.setTimeout(resolve, 2500);
          const done = () => {
            window.clearTimeout(timer);
            img.removeEventListener("load", done);
            img.removeEventListener("error", done);
            resolve();
          };
          img.addEventListener("load", done);
          img.addEventListener("error", done);
        });
      }
      if (typeof img.decode === "function") {
        await img.decode().catch(() => { });
      }
    })
  );

  await new Promise<void>((resolve) => {
    window.requestAnimationFrame(() => resolve());
  });
}

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
      await waitForSnapshotAssets(gridRef.current);
      const blob = await toBlob(gridRef.current, {
        pixelRatio: 3,
        backgroundColor: "#ffffff",
        cacheBust: true,
      });
      if (blob) {
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        onNotify?.("success", "Snapshot Copied", "Comparison snapshot copied to clipboard.");
      }
    } catch (err: unknown) {
      const msg = "Failed to copy snapshot: " + (err instanceof Error ? err.message : String(err));
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
      await waitForSnapshotAssets(gridRef.current);
      const dataUrl = await toPng(gridRef.current, {
        pixelRatio: 3,
        backgroundColor: "#ffffff",
        cacheBust: true,
      });
      const link = document.createElement("a");
      link.download = `quotation-comparison-${vehicleNo || "matrix"}.png`;
      link.href = dataUrl;
      link.click();
    } catch (err: unknown) {
      const msg = "Failed to download snapshot: " + (err instanceof Error ? err.message : String(err));
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
