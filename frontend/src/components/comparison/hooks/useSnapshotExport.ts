"use client";

import { useState } from "react";
import { toPng } from "html-to-image";

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
        await img.decode().catch(() => {});
      }
    })
  );

  await new Promise<void>((resolve) => {
    window.requestAnimationFrame(() => resolve());
  });
}

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

async function captureUltraHdPngDataUrl(element: HTMLElement): Promise<string> {
  await waitForSnapshotAssets(element);
  const rect = element.getBoundingClientRect();
  const width = Math.round(rect.width) || element.offsetWidth;
  const height = Math.round(rect.height) || element.offsetHeight;

  return await toPng(element, {
    pixelRatio: 4,
    skipFonts: false,
    width,
    height,
    backgroundColor: "#ffffff",
    cacheBust: true,
    style: {
      transform: "none",
      transformOrigin: "top left",
      width: `${width}px`,
      height: `${height}px`,
      margin: "0",
    },
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
      const dataUrl = await captureUltraHdPngDataUrl(gridRef.current);
      const blob = dataUrlToBlob(dataUrl);
      if (
        typeof ClipboardItem !== "undefined" &&
        navigator.clipboard &&
        typeof navigator.clipboard.write === "function"
      ) {
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        onNotify?.("success", "Snapshot Copied", "Ultra-HD comparison snapshot copied to clipboard.");
        return;
      }
      const link = document.createElement("a");
      link.download = `quotation-comparison-${vehicleNo || "matrix"}.png`;
      link.href = dataUrl;
      link.click();
      onNotify?.("success", "Snapshot Downloaded", "Clipboard unavailable — Ultra-HD PNG downloaded instead.");
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
      const dataUrl = await captureUltraHdPngDataUrl(gridRef.current);
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
