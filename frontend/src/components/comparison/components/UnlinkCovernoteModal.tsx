"use client";

import React from "react";
import { X, DownloadSimple } from "@phosphor-icons/react";

interface UnlinkCovernoteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUnlink: () => void;
  onDownloadAndUnlink: () => void;
  isUnlinking: boolean;
  vehicleNo?: string;
}

export function UnlinkCovernoteModal({
  isOpen,
  onClose,
  onUnlink,
  onDownloadAndUnlink,
  isUnlinking,
  vehicleNo,
}: UnlinkCovernoteModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full border border-neutral-200 overflow-hidden animate-scale-up">
        <div className="p-5 border-b border-neutral-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="size-8 rounded-full bg-rose-100 text-rose-700 flex items-center justify-center font-bold text-sm">
              !
            </div>
            <div>
              <h3 className="text-sm font-bold text-neutral-900">Remove / Unlink Cover Note</h3>
              <p className="text-xs text-neutral-500">Reverts policy stage back to Quotations</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-700 p-1 rounded-lg cursor-pointer"
          >
            <X size={16} weight="bold" />
          </button>
        </div>

        <div className="p-5 space-y-3">
          <p className="text-xs text-neutral-700 leading-relaxed">
            You are unlinking the official issued Cover Note for{" "}
            <strong>{vehicleNo || "this vehicle"}</strong>. Once removed, the policy will return to
            Quotations mode so you can re-upload or test freely.
          </p>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900">
            💡 <strong>Testing Tip:</strong> Would you like to download a local copy of this Cover
            Note PDF to your device before unlinking?
          </div>
        </div>

        <div className="p-4 bg-neutral-50 border-t border-neutral-100 flex flex-col sm:flex-row items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isUnlinking}
            className="w-full sm:w-auto px-3 py-2 text-xs font-semibold text-neutral-600 hover:text-neutral-900 hover:bg-neutral-200/60 rounded-lg transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onUnlink}
            disabled={isUnlinking}
            className="w-full sm:w-auto px-3 py-2 text-xs font-semibold text-rose-700 hover:text-rose-900 hover:bg-rose-100/70 rounded-lg border border-rose-200 transition-colors cursor-pointer disabled:opacity-50"
          >
            {isUnlinking ? "Removing..." : "Unlink Without Download"}
          </button>
          <button
            type="button"
            onClick={onDownloadAndUnlink}
            disabled={isUnlinking}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-bold text-white bg-emerald-700 hover:bg-emerald-800 rounded-lg shadow-sm transition-colors cursor-pointer disabled:opacity-50"
          >
            <DownloadSimple size={14} weight="bold" />
            <span>Download &amp; Unlink</span>
          </button>
        </div>
      </div>
    </div>
  );
}
