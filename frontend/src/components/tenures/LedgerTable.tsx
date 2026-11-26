"use client";

import React, { useRef } from "react";
import { ArrowsClockwise } from "@phosphor-icons/react";
import type { LedgerDensity, LedgerSortColumn, VehicleGroup, TenureRow, PicItem } from "./types";
import { TenureRowComponent } from "./TenureRow";
import { resolveLedgerColumns, stickyVehicleOffset } from "./ledger-columns";
import { LedgerScrollRail } from "./LedgerScrollRail";

export interface LedgerTableProps {
  loadingTenures: boolean;
  tenures: TenureRow[];
  totalTenures?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (nextPage: number) => void;
  vehicleGroups: VehicleGroup[];
  selectedTenureIds: string[];
  sortBy: LedgerSortColumn;
  sortDir: "asc" | "desc";
  category: "active" | "lost" | "all";
  selectedMonth: string;
  selectedYear: string;
  highlightedTenureId: string | null;
  pics: PicItem[];
  density?: LedgerDensity;
  hiddenColumns?: string[];
  search?: string;
  onSort: (column: LedgerSortColumn) => void;
  onToggleSelectAll: () => void;
  onToggleSelectGroup: (ids: string[], isSelected: boolean) => void;
  onDeleteTarget: (target: { id: string; vehicleNo: string; allIds: string[] }) => void;
  onPatchField: (tenureId: string, updates: Partial<TenureRow>) => Promise<void>;
  onOpenCovernoteUpload: (tenure: TenureRow) => void;
  onOpenHitModal: (tenure: TenureRow) => void;
  onOpenMissModal: (tenure: TenureRow) => void;
  onOpenDrawer: (id: string) => void;
  onOpenEditModal: (tenure: TenureRow) => void;
  hasActiveFilters?: boolean;
  onResetFilters?: () => void;
}

function SortIndicator({ active, dir }: { active: boolean; dir: "asc" | "desc" }) {
  return (
    <span className={`text-[10px] transition-colors ${active ? "text-neutral-900 font-bold" : "text-neutral-300"}`}>
      {active ? (dir === "asc" ? "▲" : "▼") : "⇅"}
    </span>
  );
}

export function LedgerTable({
  loadingTenures,
  tenures,
  totalTenures,
  page = 1,
  pageSize = 100,
  onPageChange,
  vehicleGroups,
  selectedTenureIds,
  sortBy,
  sortDir,
  category,
  selectedMonth,
  selectedYear,
  highlightedTenureId,
  pics,
  density = "comfortable",
  hiddenColumns = [],
  search = "",
  onSort,
  onToggleSelectAll,
  onToggleSelectGroup,
  onDeleteTarget,
  onPatchField,
  onOpenCovernoteUpload,
  onOpenHitModal,
  onOpenMissModal,
  onOpenDrawer,
  onOpenEditModal,
  hasActiveFilters = false,
  onResetFilters,
}: LedgerTableProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const layout = resolveLedgerColumns(density, hiddenColumns);
  const vehicleStickyLeft = stickyVehicleOffset(layout.isCompact);

  return (
    <div className="bg-white border border-neutral-200/90 rounded-[var(--rl-radius)] overflow-clip shadow-2xs flex flex-col">
      {/* Compact Table Sub-Header */}
      <div className="flex items-center justify-between gap-2 px-3 py-2 bg-[#f9f9fb] border-b border-neutral-200/80 text-xs">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-bold text-neutral-800 text-[11px] uppercase tracking-wider">
            {category === "lost" ? "Lost Client Records" : "Active Renewal Policies"} ({totalTenures ?? tenures.length})
          </span>
          {layout.isCompact && (
            <span
              className="px-1.5 py-0.5 rounded-[var(--rl-radius-sm)] bg-neutral-200/80 text-neutral-800 text-[10px] font-bold"
              title="Compact 5-column layout fits 1280px+ screens cleanly. Switch to Normal for Ledger Created & PIC columns."
            >
              Compact View · 5 Core Cols
            </span>
          )}
          {hiddenColumns.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-[var(--rl-radius-sm)] bg-amber-100 text-amber-900 text-[10px] font-bold">
              {hiddenColumns.length} col{hiddenColumns.length === 1 ? "" : "s"} hidden
            </span>
          )}
        </div>
        {layout.isCompact && (
          <span className="text-[10.5px] text-neutral-400 hidden sm:inline">
            Secondary metadata (Created &amp; PIC) available in Logs / Normal mode
          </span>
        )}
      </div>

      <div ref={scrollContainerRef} className="overflow-x-auto scrollbar-thin relative">
        <table className="w-full text-left text-xs whitespace-nowrap">
          <thead className="bg-[#f9f9fb] border-b border-neutral-200/80 text-[11px] font-bold uppercase tracking-wider text-neutral-600">
            <tr>
              <th className={`${layout.widths.select} text-center sticky left-0 z-30 bg-[#f9f9fb] ${layout.isCompact ? "py-2 px-1.5" : "py-3 px-3"}`}>
                <div className="flex items-center justify-center">
                  <input
                    type="checkbox"
                    checked={tenures.length > 0 && selectedTenureIds.length === tenures.length}
                    onChange={onToggleSelectAll}
                    className="w-3.5 h-3.5 rounded border-neutral-300 text-neutral-900 focus:ring-neutral-900 cursor-pointer"
                    title="Select all policies on this page"
                    aria-label="Select all policies on this page"
                  />
                </div>
              </th>

              <th
                onClick={() => onSort("vehicle_no")}
                className={`sticky ${vehicleStickyLeft} z-30 bg-[#f9f9fb] border-r border-neutral-200/90 shadow-[4px_0_6px_-2px_rgba(0,0,0,0.06)] cursor-pointer hover:text-black transition-colors ${layout.cellPadding} ${layout.widths.vehicle}`}
              >
                <div className="flex items-center gap-1.5">
                  <span>Vehicle &amp; Customer</span>
                  <SortIndicator active={sortBy === "vehicle_no"} dir={sortDir} />
                </div>
              </th>

              <th
                onClick={() => onSort("coverage_period")}
                className={`cursor-pointer hover:text-black transition-colors ${layout.cellPadding} ${layout.widths.coverage}`}
              >
                <div className="flex items-center gap-1.5">
                  <span>Period / Expiry</span>
                  <SortIndicator active={sortBy === "coverage_period"} dir={sortDir} />
                </div>
              </th>

              <th
                onClick={() => onSort("stage")}
                className={`cursor-pointer hover:text-black transition-colors ${layout.cellPadding} ${layout.widths.stage}`}
              >
                <div className="flex items-center gap-1.5">
                  <span>Timeline &amp; Stage</span>
                  <SortIndicator active={sortBy === "stage"} dir={sortDir} />
                </div>
              </th>

              {layout.showQuotes && (
                <th
                  onClick={() => onSort("last_activity")}
                  className={`cursor-pointer hover:text-black transition-colors ${layout.cellPadding} ${layout.widths.quotes}`}
                >
                  <div className="flex items-center gap-1.5">
                    <span>Latest Quote &amp; Link</span>
                    <SortIndicator active={sortBy === "last_activity"} dir={sortDir} />
                  </div>
                </th>
              )}

              {layout.showCreatedAt && (
                <th
                  onClick={() => onSort("created_at")}
                  className={`cursor-pointer hover:text-black transition-colors ${layout.cellPadding} ${layout.widths.createdAt}`}
                >
                  <div className="flex items-center gap-1.5">
                    <span>Ledger Created</span>
                    <SortIndicator active={sortBy === "created_at"} dir={sortDir} />
                  </div>
                </th>
              )}

              {layout.showPic && (
                <th
                  onClick={() => onSort("pic")}
                  className={`cursor-pointer hover:text-black transition-colors ${layout.cellPadding} ${layout.widths.pic}`}
                >
                  <div className="flex items-center gap-1.5">
                    <span>PIC &amp; Milestones</span>
                    <SortIndicator active={sortBy === "pic"} dir={sortDir} />
                  </div>
                </th>
              )}

              <th className={`text-right sticky right-0 z-30 bg-[#f9f9fb] border-l border-neutral-200/80 shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.05)] ${layout.cellPadding} ${layout.widths.actions}`}>
                Actions
              </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-neutral-100">
            {loadingTenures ? (
              <tr>
                <td colSpan={layout.columnCount} className="py-14 text-center text-neutral-400">
                  <ArrowsClockwise className="w-5 h-5 animate-spin mx-auto mb-2 text-neutral-500" />
                  Loading Motor Renewal Ledger...
                </td>
              </tr>
            ) : tenures.length === 0 || vehicleGroups.length === 0 ? (
              <tr>
                <td colSpan={layout.columnCount} className="py-14 text-center text-neutral-500">
                  <div className="flex flex-col items-center gap-2.5">
                    <span>
                      {category === "lost"
                        ? "No lost client records found matching the active filters."
                        : `No active renewal policies found for ${selectedMonth === "all" ? selectedYear : selectedMonth}.`}
                    </span>
                    {hasActiveFilters && onResetFilters && (
                      <button
                        type="button"
                        onClick={onResetFilters}
                        className="rounded-md border border-neutral-300 bg-white px-3 py-1 text-xs font-semibold text-neutral-800 hover:bg-neutral-50 cursor-pointer shadow-2xs"
                      >
                        Reset Filters
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              vehicleGroups.map((group) => (
                <TenureRowComponent
                  key={group.mainTenure.id}
                  group={group}
                  selectedTenureIds={selectedTenureIds}
                  onToggleSelectGroup={onToggleSelectGroup}
                  onDeleteTarget={onDeleteTarget}
                  highlightedTenureId={highlightedTenureId}
                  pics={pics}
                  density={density}
                  hiddenColumns={hiddenColumns}
                  search={search}
                  onPatchField={onPatchField}
                  onOpenCovernoteUpload={onOpenCovernoteUpload}
                  onOpenHitModal={onOpenHitModal}
                  onOpenMissModal={onOpenMissModal}
                  onOpenDrawer={onOpenDrawer}
                  onOpenEditModal={onOpenEditModal}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Viewport-sticky Horizontal Pan Rail (visible whenever table overflows viewport width) */}
      <LedgerScrollRail
        scrollTargetRef={scrollContainerRef}
        recomputeDeps={[tenures.length, density, hiddenColumns.join(","), loadingTenures]}
      />

      {/* Server Pagination Footer */}
      {(totalTenures ?? tenures.length) > pageSize && onPageChange && (
        <div className="flex items-center justify-between px-3 py-2 bg-[#f9f9fb] border-t border-neutral-200/80 text-xs text-neutral-600">
          <span>
            Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, totalTenures ?? tenures.length)} of{" "}
            {totalTenures ?? tenures.length} policies
          </span>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={page <= 1 || loadingTenures}
              onClick={() => onPageChange(page - 1)}
              className="px-2.5 py-1 rounded border border-neutral-200 bg-white hover:bg-neutral-50 disabled:opacity-40 cursor-pointer font-semibold"
            >
              Prev
            </button>
            <span className="px-2 font-mono font-bold text-neutral-800">
              Page {page} / {Math.max(1, Math.ceil((totalTenures ?? tenures.length) / pageSize))}
            </span>
            <button
              type="button"
              disabled={page * pageSize >= (totalTenures ?? tenures.length) || loadingTenures}
              onClick={() => onPageChange(page + 1)}
              className="px-2.5 py-1 rounded border border-neutral-200 bg-white hover:bg-neutral-50 disabled:opacity-40 cursor-pointer font-semibold"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
