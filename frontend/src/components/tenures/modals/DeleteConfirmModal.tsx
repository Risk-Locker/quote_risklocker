"use client";

import React from "react";

export interface DeleteConfirmModalProps {
  target: { id: string; vehicleNo: string; allIds: string[] } | null;
  deletingVehicle: boolean;
  onConfirmDelete: () => Promise<void>;
  onClose: () => void;
}

export function DeleteConfirmModal({
  target,
  deletingVehicle,
  onConfirmDelete,
  onClose,
}: DeleteConfirmModalProps) {
  if (!target) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
      <div className="bg-white rounded-[var(--rl-radius)] border border-neutral-200 shadow-xl max-w-sm w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="p-4 border-b border-neutral-100 bg-[#fbfbfd] flex items-center justify-between">
          <h3 className="font-bold text-sm text-neutral-900">Confirm Move to Trash</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-700 text-sm font-bold p-1 cursor-pointer"
          >
            ✕
          </button>
        </div>
        <div className="p-4 space-y-2 text-xs text-neutral-600">
          <p>
            Are you sure you want to delete{" "}
            <strong className="text-neutral-900">{target.vehicleNo}</strong>?
          </p>
          <p className="text-[11px] text-neutral-600 bg-amber-50 p-2.5 rounded border border-amber-200 leading-relaxed">
            This will delete the vehicle deal and move all associated quotation sessions,
            comparison matrices, and generated PDF records to Trash. Items in Trash are retained for{" "}
            <strong>30 days</strong> before permanent deletion.
          </p>
        </div>
        <div className="p-3 bg-neutral-50 border-t border-neutral-200 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs font-medium text-neutral-600 hover:text-neutral-900 cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirmDelete}
            disabled={deletingVehicle}
            className="px-3.5 py-1.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded shadow-xs cursor-pointer disabled:opacity-50"
          >
            {deletingVehicle ? "Deleting..." : "Yes, Move to Trash"}
          </button>
        </div>
      </div>
    </div>
  );
}
