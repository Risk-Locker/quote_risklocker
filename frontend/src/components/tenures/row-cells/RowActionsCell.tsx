"use client";

import React from "react";
import Link from "next/link";
import type { Route } from "next";
import { ClockCounterClockwise, Columns, PencilSimple } from "@phosphor-icons/react";
import type { TenureRow } from "../types";

interface RowActionsCellProps {
  tenure: TenureRow;
  isCompact: boolean;
  onOpenDrawer: (tenureId: string) => void;
  onOpenEditModal: (tenure: TenureRow) => void;
}

const SECONDARY_ACTION =
  "inline-flex items-center justify-center gap-1 rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] bg-white text-neutral-700 hover:border-[#1b1717] hover:text-[#1b1717] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b1717]/30";

/** Single consolidated action column: Compare (primary), Logs, Edit. Compact renders icon-only buttons. */
export function RowActionsCell({ tenure, isCompact, onOpenDrawer, onOpenEditModal }: RowActionsCellProps) {
  const size = isCompact ? "h-6 px-1.5 text-[11px]" : "h-7 px-2 text-xs font-semibold";
  return (
    <div className="flex items-center justify-end gap-1">
      <Link
        href={`/comparison?tenure_id=${tenure.id}` as Route}
        target="_blank"
        rel="noopener noreferrer"
        className={`inline-flex items-center gap-1 rounded-[var(--rl-radius-sm)] bg-[#1b1717] hover:bg-black text-white font-bold transition-colors ${size}`}
        title="Open Marketing Comparison for this vehicle (new tab)"
        aria-label="Open Marketing Comparison for this vehicle"
      >
        <Columns className="w-3.5 h-3.5" />
        {!isCompact && <span>Compare</span>}
      </Link>
      <button
        type="button"
        onClick={() => onOpenDrawer(tenure.id)}
        className={`${SECONDARY_ACTION} ${size}`}
        title="Open activity timeline & logs"
        aria-label="Open activity timeline and logs"
      >
        <ClockCounterClockwise className="w-3.5 h-3.5" />
        {!isCompact && <span>Logs</span>}
      </button>
      <button
        type="button"
        onClick={() => onOpenEditModal(tenure)}
        className={`${SECONDARY_ACTION} ${size}`}
        title="Edit customer, plate & vehicle details"
        aria-label="Edit customer, plate and vehicle details"
      >
        <PencilSimple className="w-3.5 h-3.5" />
        {!isCompact && <span>Edit</span>}
      </button>
    </div>
  );
}
