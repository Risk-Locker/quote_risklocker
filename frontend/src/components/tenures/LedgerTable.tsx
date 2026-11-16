"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";
import { ArrowsClockwise, CaretLeft, CaretRight } from "@phosphor-icons/react";
import type { LedgerSortColumn, VehicleGroup, TenureRow, PicItem } from "./types";
import { TenureRowComponent } from "./TenureRow";

export interface LedgerTableProps {
  loadingTenures: boolean;
  tenures: TenureRow[];
  vehicleGroups: VehicleGroup[];
  selectedTenureIds: string[];
  sortBy: LedgerSortColumn;
  sortDir: "asc" | "desc";
  category: "active" | "lost" | "all";
  selectedMonth: string;
  selectedYear: string;
  highlightedTenureId: string | null;
  pics: PicItem[];
  density?: "comfortable" | "compact";
  hiddenColumns?: string[];
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
}

export function LedgerTable({
  loadingTenures,
  tenures,
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
}: LedgerTableProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const checkScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    checkScroll();
    window.addEventListener("resize", checkScroll);
    return () => window.removeEventListener("resize", checkScroll);
  }, [checkScroll, tenures, density, hiddenColumns]);

  const handleScrollBy = (amount: number) => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollBy({ left: amount, behavior: "smooth" });
    }
  };

  const totalCols =
    4 +
    (!hiddenColumns.includes("last_activity") ? 1 : 0) +
    (!hiddenColumns.includes("created_at") ? 1 : 0) +
    (!hiddenColumns.includes("pic") ? 1 : 0);

  const isCompact = density === "compact";

  return (
    <div className="bg-white border border-neutral-200/90 rounded-[var(--rl-radius)] overflow-hidden shadow-2xs flex flex-col">
      {/* Table Sub-Header & Horizontal Scroll Navigation Bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-[#f9f9fb] border-b border-neutral-200/80 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-bold text-neutral-800 text-[11px] uppercase tracking-wider">
            {category === "lost" ? "Lost Client Records" : "Active Renewal Policies"} ({tenures.length})
          </span>
          {isCompact && (
            <span className="px-1.5 py-0.2 rounded bg-neutral-200 text-neutral-800 text-[10px] font-bold">
              Compressed View
            </span>
          )}
          {hiddenColumns.length > 0 && (
            <span className="px-1.5 py-0.2 rounded bg-amber-100 text-amber-900 text-[10px] font-bold">
              {hiddenColumns.length} col{hiddenColumns.length === 1 ? "" : "s"} hidden
            </span>
          )}
        </div>

        {/* Quick Horizontal Scroll Buttons */}
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-neutral-400 hidden sm:inline">Columns:</span>
          <button
            type="button"
            onClick={() => handleScrollBy(-320)}
            disabled={!canScrollLeft}
            className="flex items-center gap-1 px-2 py-1 rounded bg-white hover:bg-neutral-100 text-neutral-700 text-xs font-semibold border border-neutral-200 shadow-2xs transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
            title="Scroll columns left"
            aria-label="Scroll columns left"
          >
            <CaretLeft size={13} weight="bold" />
            <span className="hidden md:inline">Left</span>
          </button>
          <button
            type="button"
            onClick={() => handleScrollBy(320)}
            disabled={!canScrollRight}
            className="flex items-center gap-1 px-2 py-1 rounded bg-white hover:bg-neutral-100 text-neutral-700 text-xs font-semibold border border-neutral-200 shadow-2xs transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
            title="Scroll columns right"
            aria-label="Scroll columns right"
          >
            <span className="hidden md:inline">Right</span>
            <CaretRight size={13} weight="bold" />
          </button>
        </div>
      </div>

      <div
        ref={scrollContainerRef}
        onScroll={checkScroll}
        className="overflow-x-auto scrollbar-thin relative"
      >
        <table className="w-full text-left text-xs whitespace-nowrap">
          <thead className="bg-[#f9f9fb] border-b border-neutral-200/80 text-[11px] font-bold uppercase tracking-wider text-neutral-600">
            <tr>
              {/* Sticky Column 0: Checkbox & Bulk Actions */}
              <th className={`w-14 min-w-[56px] max-w-[56px] text-center sticky left-0 z-30 bg-[#f9f9fb] ${isCompact ? "py-2 px-2" : "py-3 px-3"}`}>
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

              {/* Sticky Column 1: Vehicle & Customer */}
              <th
                onClick={() => onSort("vehicle_no")}
                className={`sticky left-[56px] z-30 bg-[#f9f9fb] border-r border-neutral-200/90 shadow-[4px_0_6px_-2px_rgba(0,0,0,0.06)] cursor-pointer hover:text-black transition-colors ${
                  isCompact ? "py-2 px-2.5 min-w-[180px]" : "py-3 px-3 min-w-[210px]"
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span>Vehicle &amp; Customer</span>
                  <span
                    className={`text-[10px] transition-colors ${
                      sortBy === "vehicle_no" ? "text-neutral-900 font-bold" : "text-neutral-300"
                    }`}
                  >
                    {sortBy === "vehicle_no" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                  </span>
                </div>
              </th>

              {/* Column 2: Coverage Period */}
              <th
                onClick={() => onSort("coverage_period")}
                className={`cursor-pointer hover:text-black transition-colors ${
                  isCompact ? "py-2 px-2.5 min-w-[140px]" : "py-3 px-3 min-w-[170px]"
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span>Coverage Period</span>
                  <span
                    className={`text-[10px] transition-colors ${
                      sortBy === "coverage_period"
                        ? "text-neutral-900 font-bold"
                        : "text-neutral-300"
                    }`}
                  >
                    {sortBy === "coverage_period" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                  </span>
                </div>
              </th>

              {/* Column 3: Pipeline Stage */}
              <th
                onClick={() => onSort("stage")}
                className={`cursor-pointer hover:text-black transition-colors ${
                  isCompact ? "py-2 px-2.5 min-w-[270px]" : "py-3 px-3 min-w-[340px]"
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span>Pipeline Stage</span>
                  <span
                    className={`text-[10px] transition-colors ${
                      sortBy === "stage" ? "text-neutral-900 font-bold" : "text-neutral-300"
                    }`}
                  >
                    {sortBy === "stage" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                  </span>
                </div>
              </th>

              {/* Column 4: Latest Activity & Quotes (Optional) */}
              {!hiddenColumns.includes("last_activity") && (
                <th
                  onClick={() => onSort("last_activity")}
                  className={`cursor-pointer hover:text-black transition-colors ${
                    isCompact ? "py-2 px-2.5 min-w-[160px]" : "py-3 px-3 min-w-[190px]"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span>Latest Activity &amp; Quotes</span>
                    <span
                      className={`text-[10px] transition-colors ${
                        sortBy === "last_activity" ? "text-neutral-900 font-bold" : "text-neutral-300"
                      }`}
                    >
                      {sortBy === "last_activity" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                    </span>
                  </div>
                </th>
              )}

              {/* Column 5: Date of Ledger Creation (Optional) */}
              {!hiddenColumns.includes("created_at") && (
                <th
                  onClick={() => onSort("created_at")}
                  className={`cursor-pointer hover:text-black transition-colors ${
                    isCompact ? "py-2 px-2.5 min-w-[130px]" : "py-3 px-3 min-w-[160px]"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span>Ledger Created</span>
                    <span
                      className={`text-[10px] transition-colors ${
                        sortBy === "created_at" ? "text-neutral-900 font-bold" : "text-neutral-300"
                      }`}
                    >
                      {sortBy === "created_at" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                    </span>
                  </div>
                </th>
              )}

              {/* Column 6: PIC & Milestones (Optional) */}
              {!hiddenColumns.includes("pic") && (
                <th
                  onClick={() => onSort("pic")}
                  className={`cursor-pointer hover:text-black transition-colors ${
                    isCompact ? "py-2 px-2.5 min-w-[130px]" : "py-3 px-3 min-w-[160px]"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span>PIC &amp; Milestones</span>
                    <span
                      className={`text-[10px] transition-colors ${
                        sortBy === "pic" ? "text-neutral-900 font-bold" : "text-neutral-300"
                      }`}
                    >
                      {sortBy === "pic" ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                    </span>
                  </div>
                </th>
              )}

              {/* Column 7: Actions */}
              <th className={`text-right ${isCompact ? "py-2 px-2.5 min-w-[160px]" : "py-3 px-3 min-w-[190px]"}`}>
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {loadingTenures ? (
              <tr>
                <td colSpan={totalCols} className="py-14 text-center text-neutral-400">
                  <ArrowsClockwise className="w-5 h-5 animate-spin mx-auto mb-2 text-neutral-500" />
                  Loading Motor Renewal Ledger...
                </td>
              </tr>
            ) : tenures.length === 0 ? (
              <tr>
                <td colSpan={totalCols} className="py-14 text-center text-neutral-400">
                  {category === "lost"
                    ? "No lost client records found matching the active filters."
                    : `No active renewal policies found for ${
                        selectedMonth === "all" ? selectedYear : selectedMonth
                      }.`}
                </td>
              </tr>
            ) : (
              vehicleGroups.map((group) => (
                <TenureRowComponent
                  key={group.vehicle_no}
                  group={group}
                  selectedTenureIds={selectedTenureIds}
                  onToggleSelectGroup={onToggleSelectGroup}
                  onDeleteTarget={onDeleteTarget}
                  highlightedTenureId={highlightedTenureId}
                  pics={pics}
                  density={density}
                  hiddenColumns={hiddenColumns}
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
    </div>
  );
}
