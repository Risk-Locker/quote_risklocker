"use client";

import React, { useState } from "react";
import { DownloadSimple, FileXls, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { API_BASE } from "@/lib/api";
import type { CopilotArtifact } from "./types";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function CopilotArtifactPane({
  artifact,
  onClose,
}: {
  artifact: CopilotArtifact;
  onClose: () => void;
}) {
  const [downloading, setDownloading] = useState(false);
  const [dlError, setDlError] = useState<string | null>(null);

  const columns = artifact.preview?.columns || [];
  const rows = artifact.preview?.rows || [];
  const totals = artifact.preview?.totals || {};

  async function handleDownload() {
    setDownloading(true);
    setDlError(null);
    try {
      const url = artifact.download_url.startsWith("/api/")
        ? artifact.download_url
        : `${API_BASE}${artifact.download_url}`;
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) {
        throw new Error(`Download failed (${res.status})`);
      }
      const blob = await res.blob();
      const objUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objUrl;
      a.download = artifact.filename || "risklocker_export.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objUrl);
    } catch (err) {
      setDlError(err instanceof Error ? err.message : "Could not download file.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="flex h-full flex-col border-l border-[var(--rl-border)] bg-white">
      <div className="p-3 border-b border-[var(--rl-border)] flex items-center justify-between gap-2 bg-neutral-50/70">
        <div className="flex items-center gap-2 min-w-0">
          <div className="size-7 rounded-[var(--rl-radius-sm)] bg-emerald-700 text-white grid place-items-center shrink-0">
            <FileXls size={16} weight="fill" />
          </div>
          <div className="min-w-0">
            <div className="text-xs font-bold text-[var(--rl-text-strong)] truncate">{artifact.filename}</div>
            <div className="text-[10px] text-[var(--rl-text-muted)] font-mono">
              {artifact.row_count.toLocaleString()} rows · {formatBytes(artifact.size_bytes)}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <Button
            type="button"
            size="sm"
            onClick={handleDownload}
            loading={downloading}
            icon={<DownloadSimple size={13} weight="bold" />}
            className="h-7 text-[11px]"
          >
            Download .xlsx
          </Button>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded hover:bg-neutral-200 text-[var(--rl-text-muted)] cursor-pointer"
            aria-label="Close artifact preview"
          >
            <X size={14} weight="bold" />
          </button>
        </div>
      </div>

      {dlError && (
        <div className="m-2 rounded bg-rose-50 border border-rose-200 px-2.5 py-1.5 text-[11px] text-rose-700">
          {dlError}
        </div>
      )}

      {Object.keys(totals).length > 0 && (
        <div className="px-3 py-2 border-b border-[var(--rl-border)] bg-emerald-50/50 flex flex-wrap gap-2">
          {Object.entries(totals).map(([col, sumVal]) => (
            <Badge key={col} variant="success" className="text-[10px] font-mono">
              SUM {col}: RM {Number(sumVal).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </Badge>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-auto p-3">
        <div className="text-[10px] text-[var(--rl-text-muted)] mb-2">
          Showing first {rows.length} of {artifact.row_count.toLocaleString()} rows (full dataset in Excel download).
        </div>
        <div className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] overflow-x-auto">
          <table className="w-full text-left text-[11px] border-collapse">
            <thead className="bg-neutral-50 border-b border-[var(--rl-border)]">
              <tr>
                {columns.map((c) => (
                  <th key={c} className="px-2.5 py-1.5 font-semibold text-[var(--rl-text-strong)] whitespace-nowrap">
                    {c.replace(/_/g, " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {rows.map((r, rIdx) => (
                <tr key={rIdx} className="hover:bg-neutral-50/70">
                  {columns.map((c) => (
                    <td key={c} className="px-2.5 py-1.5 text-[var(--rl-text)] whitespace-nowrap">
                      {r[c] === null || r[c] === undefined ? "—" : String(r[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
