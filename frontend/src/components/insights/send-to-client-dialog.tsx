"use client";

import React from "react";
import { PaperPlaneRight, FloppyDisk, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";

interface SendToClientDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (sentToClient: boolean) => void;
  actionTitle?: string;
}

export function SendToClientDialog({
  open,
  onClose,
  onConfirm,
  actionTitle = "Export Quotation",
}: SendToClientDialogProps) {
  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="send-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-150"
    >
      <div
        className="relative w-full max-w-md bg-white rounded-lg shadow-xl border border-neutral-200 overflow-hidden"
        style={{ borderRadius: "8px" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-neutral-100 flex items-center justify-center text-neutral-800">
              <PaperPlaneRight size={18} weight="duotone" />
            </div>
            <div>
              <h3 id="send-dialog-title" className="text-sm font-semibold text-neutral-900">
                {actionTitle}
              </h3>
              <p className="text-xs text-neutral-500">Quotation Activity Ledger</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-600 p-1 rounded transition-colors"
            aria-label="Close dialog"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="px-5 py-4">
          <p className="text-sm text-neutral-700 leading-relaxed">
            Are you sending this quotation directly to the client, or saving it as an internal draft?
          </p>
          <p className="text-xs text-neutral-400 mt-2">
            Marking as &ldquo;Sent to Client&rdquo; registers this version in your Hit &amp; Miss pipeline with the current timestamp.
          </p>
        </div>

        {/* Actions */}
        <div className="px-5 py-3.5 bg-neutral-50 border-t border-neutral-100 flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="text-xs text-neutral-600 hover:text-neutral-900"
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => onConfirm(false)}
            className="text-xs border-neutral-300 text-neutral-800 hover:bg-neutral-100 gap-1.5"
          >
            <FloppyDisk size={14} />
            Internal Save Only
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => onConfirm(true)}
            className="text-xs bg-[#1b1717] hover:bg-[#2c2727] text-white gap-1.5 shadow-sm"
          >
            <PaperPlaneRight size={14} weight="bold" />
            Yes, Sent to Client
          </Button>
        </div>
      </div>
    </div>
  );
}
