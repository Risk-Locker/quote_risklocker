"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fileUrl } from "@/lib/api";
import {
  Check,
  Copy,
  DownloadSimple,
  PencilSimple,
  Trash,
  ArrowSquareOut,
  Calendar,
  FileImage,
  Info,
} from "@phosphor-icons/react";

export type AssetDetailItem = {
  id: string;
  asset_key: string;
  asset_kind: string;
  label: string;
  original_filename?: string;
  size_bytes?: number;
  category?: string;
  width_px?: number | null;
  height_px?: number | null;
  status: string;
  url: string;
  has_transparency?: boolean | null;
  created_at?: string | null;
  mapped_concepts?: string[];
};

interface AssetDetailsModalProps {
  asset: AssetDetailItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit?: (asset: AssetDetailItem) => void;
  onDelete?: (asset: AssetDetailItem) => void;
}

function formatBytes(bytes?: number): string {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function AssetDetailsModal({
  asset,
  open,
  onOpenChange,
  onEdit,
  onDelete,
}: AssetDetailsModalProps) {
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [copiedId, setCopiedId] = useState(false);

  if (!asset) return null;

  const fullUrl = fileUrl(asset.url);

  const handleCopyUrl = async () => {
    try {
      const absoluteUrl = fullUrl.startsWith("http")
        ? fullUrl
        : `${window.location.origin}${fullUrl}`;
      await navigator.clipboard.writeText(absoluteUrl);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2000);
    } catch {
      // Fallback
    }
  };

  const handleCopyId = async () => {
    try {
      await navigator.clipboard.writeText(asset.id);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    } catch {
      // Fallback
    }
  };

  const handleDownload = () => {
    const link = document.createElement("a");
    link.href = fullUrl;
    link.download = asset.original_filename || `${asset.asset_key}.png`;
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={asset.label}
      description={`Asset Key: ${asset.asset_key} · Folder: ${asset.category || "General"}`}
      maxWidth="2xl"
    >
      <div className="space-y-5">
        {/* Visual Preview Box on Transparent Checkerboard */}
        <div className="relative aspect-[16/9] w-full rounded-lg border border-[var(--rl-border)] overflow-hidden grid place-items-center bg-[linear-gradient(45deg,#f3f3f4_25%,transparent_25%),linear-gradient(-45deg,#f3f3f4_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#f3f3f4_75%),linear-gradient(-45deg,transparent_75%,#f3f3f4_75%)] bg-[length:20px_20px] bg-[position:0_0,0_10px,10px_-10px,-10px_0px] p-6 shadow-inner">
          <img
            src={fullUrl}
            alt={asset.label}
            className="max-h-full max-w-full object-contain filter drop-shadow-xs"
          />
          {asset.has_transparency ? (
            <Badge
              variant="success"
              className="absolute top-2.5 right-2.5 shadow-xs text-[11px]"
            >
              Transparent Alpha (PNG)
            </Badge>
          ) : (
            <Badge
              variant="info"
              className="absolute top-2.5 right-2.5 shadow-xs text-[11px]"
            >
              Solid Background
            </Badge>
          )}
        </div>

        {/* S3-Style Metadata Inspection Table */}
        <div className="rounded-lg border border-[var(--rl-border)] overflow-hidden text-xs">
          <div className="bg-gray-50 px-3.5 py-2 border-b border-[var(--rl-border)] font-semibold text-gray-700 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Info size={15} className="text-blue-600" />
              File & Storage Specifications
            </span>
            <span className="font-mono text-[11px] text-gray-500">
              {asset.status === "active" ? "Status: Active" : "Status: Available"}
            </span>
          </div>

          <div className="divide-y divide-gray-100 bg-white">
            <div className="flex items-center justify-between px-3.5 py-2">
              <span className="text-[var(--rl-text-muted)] font-medium">Asset ID</span>
              <div className="flex items-center gap-1.5">
                <span className="font-mono text-[11px] text-gray-900 select-all">{asset.id}</span>
                <button
                  type="button"
                  onClick={handleCopyId}
                  className="text-gray-400 hover:text-gray-700 cursor-pointer p-0.5 rounded"
                  title="Copy ID"
                >
                  {copiedId ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between px-3.5 py-2">
              <span className="text-[var(--rl-text-muted)] font-medium">Original Filename</span>
              <span className="font-mono text-[11px] text-gray-800">
                {asset.original_filename || "N/A"}
              </span>
            </div>

            <div className="flex items-center justify-between px-3.5 py-2">
              <span className="text-[var(--rl-text-muted)] font-medium">Category / Folder</span>
              <span className="font-medium text-gray-900">{asset.category || "General"}</span>
            </div>

            <div className="flex items-center justify-between px-3.5 py-2">
              <span className="text-[var(--rl-text-muted)] font-medium">Dimensions</span>
              <span className="font-mono font-medium text-gray-900">
                {asset.width_px && asset.height_px
                  ? `${asset.width_px} × ${asset.height_px} pixels`
                  : "Vector / Unknown"}
              </span>
            </div>

            <div className="flex items-center justify-between px-3.5 py-2">
              <span className="text-[var(--rl-text-muted)] font-medium">File Size</span>
              <span className="font-mono font-medium text-gray-900">
                {formatBytes(asset.size_bytes)} ({asset.size_bytes?.toLocaleString() || 0} bytes)
              </span>
            </div>

            <div className="flex items-center justify-between px-3.5 py-2">
              <span className="text-[var(--rl-text-muted)] font-medium">Uploaded Date & Time</span>
              <span className="text-gray-800">
                {asset.created_at
                  ? new Date(asset.created_at).toLocaleString("en-MY", {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })
                  : "N/A"}
              </span>
            </div>

            {asset.mapped_concepts && asset.mapped_concepts.length > 0 && (
              <div className="flex items-start justify-between px-3.5 py-2 gap-4">
                <span className="text-[var(--rl-text-muted)] font-medium shrink-0">
                  Mapped Benefit Concepts
                </span>
                <div className="flex flex-wrap justify-end gap-1">
                  {asset.mapped_concepts.map((concept, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center rounded bg-blue-50 border border-blue-200 px-1.5 py-0.5 text-[10.5px] font-semibold text-blue-700"
                    >
                      📌 {concept}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 pt-2 border-t border-[var(--rl-border)]">
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleCopyUrl}
              className="gap-1.5 text-xs h-8 cursor-pointer"
            >
              {copiedUrl ? (
                <>
                  <Check size={14} className="text-emerald-600" />
                  <span className="text-emerald-700 font-bold">Copied URL!</span>
                </>
              ) : (
                <>
                  <Copy size={14} />
                  <span>Copy Image URL</span>
                </>
              )}
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={handleDownload}
              className="gap-1.5 text-xs h-8 cursor-pointer"
            >
              <DownloadSimple size={14} />
              <span>Download</span>
            </Button>
          </div>

          <div className="flex items-center gap-2">
            {onEdit && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  onOpenChange(false);
                  onEdit(asset);
                }}
                className="gap-1.5 text-xs h-8 cursor-pointer"
              >
                <PencilSimple size={14} />
                <span>Edit / Rename</span>
              </Button>
            )}

            {onDelete && (
              <Button
                variant="danger"
                size="sm"
                onClick={() => {
                  onOpenChange(false);
                  onDelete(asset);
                }}
                className="gap-1.5 text-xs h-8 cursor-pointer"
              >
                <Trash size={14} />
                <span>Delete</span>
              </Button>
            )}
          </div>
        </div>
      </div>
    </Dialog>
  );
}
