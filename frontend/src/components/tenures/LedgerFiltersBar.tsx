"use client";

import React, { useMemo } from "react";
import {
  CalendarBlank,
  CaretLeft,
  CaretRight,
  ArrowsClockwise,
  CheckCircle,
  Archive,
  Columns,
  MagnifyingGlass,
  Table,
  Plus,
} from "@phosphor-icons/react";
import type { YoYStatItem, TenureRow } from "./types";
import { TenureBulkActions } from "./TenureBulkActions";
import { LedgerSearchInput } from "./LedgerSearchInput";

export interface MonthDisplayItem {
  month: string;
  label: string;
  start_count: number;
  end_count: number;
  total: number;
  cars: number;
}

export interface LedgerFiltersBarProps {
  // Year & Month filters
  selectedYear: string;
  onSelectYear: (year: string) => void;
  selectedMonth: string;
  onSelectMonth: (month: string) => void;
  availableYears: string[];
  monthsOfYear: MonthDisplayItem[];
  allYearsSummary: { total: number; cars: number; active: number; lost: number } | null;
  yoyStats: YoYStatItem[];
  loadingMonths: boolean;
  onJumpToCurrentMonth: () => void;
  onScrollMonths: (direction: "left" | "right") => void;
  monthScrollRef: React.RefObject<HTMLDivElement | null>;
  onRefresh: () => void;

  // Category & Policy status
  category: "active" | "lost" | "all";
  onSelectCategory: (category: "active" | "lost" | "all") => void;
  policyFilter: "all" | "issued" | "pending";
  onSelectPolicyFilter: (filter: "all" | "issued" | "pending") => void;
  stageFilter: string;
  onClearStageFilter: () => void;

  // Search & Counts
  tenuresCount: number;
  issuedCount: number;
  pendingCount: number;
  search: string;
  onSearchChange: (search: string) => void;

  // View modes & toggles
  viewMode: "ledger" | "calendar";
  onSelectViewMode: (mode: "ledger" | "calendar") => void;
  showHidden: boolean;
  onToggleShowHidden: () => void;
  onOpenAddVehicleModal: () => void;

  // Density & Column compression
  density?: "comfortable" | "compact";
  onSelectDensity?: (density: "comfortable" | "compact") => void;
  hiddenColumns?: string[];
  onToggleColumnVisibility?: (col: string) => void;

  // Bulk actions
  selectedTenureIds: string[];
  tenures: TenureRow[];
  onBulkConfirmHit: () => Promise<void>;
  onBulkDelete: () => Promise<void>;
  onClearSelection: () => void;
  confirmingBulk?: boolean;
  deletingBulk?: boolean;
}

const OPTIONAL_COLUMNS = [
  { id: "last_activity", label: "Latest Quotes & Activity" },
  { id: "created_at", label: "Date of Ledger Creation" },
  { id: "pic", label: "PIC & Milestones" },
];

export function LedgerFiltersBar({
  selectedYear,
  onSelectYear,
  selectedMonth,
  onSelectMonth,
  availableYears,
  monthsOfYear,
  allYearsSummary,
  yoyStats,
  loadingMonths,
  onJumpToCurrentMonth,
  onScrollMonths,
  monthScrollRef,
  onRefresh,

  category,
  onSelectCategory,
  policyFilter,
  onSelectPolicyFilter,
  stageFilter,
  onClearStageFilter,

  tenuresCount,
  issuedCount,
  pendingCount,
  search,
  onSearchChange,

  viewMode,
  onSelectViewMode,
  showHidden,
  onToggleShowHidden,
  onOpenAddVehicleModal,

  density = "comfortable",
  onSelectDensity,
  hiddenColumns = [],
  onToggleColumnVisibility,

  selectedTenureIds,
  tenures,
  onBulkConfirmHit,
  onBulkDelete,
  onClearSelection,
  confirmingBulk = false,
  deletingBulk = false,
}: LedgerFiltersBarProps) {
  const [colMenuOpen, setColMenuOpen] = React.useState(false);
  const currentYear = useMemo(() => new Date().getFullYear().toString(), []);
  const currentMonthKey = useMemo(() => {
    return `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}`;
  }, []);

  return (
    <div className="space-y-3.5">
      {/* 2. POLICIES & RENEWALS BY DATE (YEARS & MONTHS) */}
      <div className="bg-white border border-[#e5e5ea] rounded-[var(--rl-radius)] p-4 shadow-2xs space-y-3.5">
        {/* Top Header: Title & Actions */}
        <div className="flex items-center justify-between flex-wrap gap-2 pb-2.5 border-b border-[#f2f2f7]">
          <div>
            <div className="flex items-center gap-2">
              <CalendarBlank className="w-4 h-4 text-neutral-700" />
              <span className="text-xs font-bold text-neutral-900 uppercase tracking-wider">
                Policies &amp; Renewals
              </span>
            </div>
            <p className="text-[11px] text-neutral-500 mt-0.5">
              Select a year and month to view policy periods and cars. Hover on a month to see starting vs expiring policies.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onJumpToCurrentMonth}
              className="text-[11px] font-semibold text-[#6e6e73] hover:text-[#1b1717] transition-colors px-2.5 py-1 rounded-[var(--rl-radius-sm)] hover:bg-[#f5f5f7] border border-[#e5e5ea] cursor-pointer"
              title="Jump to current active month"
            >
              Current Month
            </button>
            <div className="flex items-center rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] bg-[#f5f5f7] p-0.5">
              <button
                type="button"
                onClick={() => onScrollMonths("left")}
                className="p-1 hover:bg-white rounded-[var(--rl-radius-sm)] text-[#6e6e73] hover:text-[#1b1717] transition-colors cursor-pointer"
                title="Scroll months left"
                aria-label="Scroll months left"
              >
                <CaretLeft size={13} weight="bold" />
              </button>
              <button
                type="button"
                onClick={() => onScrollMonths("right")}
                className="p-1 hover:bg-white rounded-[var(--rl-radius-sm)] text-[#6e6e73] hover:text-[#1b1717] transition-colors cursor-pointer"
                title="Scroll months right"
                aria-label="Scroll months right"
              >
                <CaretRight size={13} weight="bold" />
              </button>
            </div>
            <button
              type="button"
              onClick={onRefresh}
              className="text-[11px] font-medium text-[#8e8e93] hover:text-[#1b1717] flex items-center gap-1 ml-1 cursor-pointer"
            >
              <ArrowsClockwise className="w-3 h-3" /> Refresh
            </button>
          </div>
        </div>

        {/* Row 1: Years Switcher with Cars and Policy Counts */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-neutral-700 uppercase tracking-wide">
              Step 1: Select Year
            </span>
            {selectedYear !== "all" && (
              <span className="text-[11px] text-neutral-500">
                Viewing {selectedYear} ({yoyStats.find((s) => s.year === selectedYear)?.total ?? 0} policies ·{" "}
                {yoyStats.find((s) => s.year === selectedYear)?.cars ?? 0} cars)
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 flex-wrap">
            {/* All Years button */}
            <button
              type="button"
              onClick={() => {
                onSelectYear("all");
                onSelectMonth("all");
                onSelectPolicyFilter("all");
              }}
              className={`px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
                selectedYear === "all"
                  ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                  : "bg-[#f5f5f7] text-[#454545] hover:text-[#1b1717] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
              }`}
            >
              <span>All Years</span>
              {allYearsSummary && (
                <span
                  className={`px-1.5 py-0.2 rounded text-[10px] font-mono font-bold ${
                    selectedYear === "all" ? "bg-white/20 text-white" : "bg-[#e5e5ea] text-neutral-700"
                  }`}
                >
                  {allYearsSummary.total} policies · {allYearsSummary.cars} cars
                </span>
              )}
            </button>

            {/* Dynamic Year Buttons */}
            {availableYears.map((yr) => {
              const isSelected = selectedYear === yr;
              const stat = yoyStats.find((s) => s.year === yr);
              const totalPolicies = stat ? stat.total : 0;
              const totalCars = stat ? stat.cars : 0;

              return (
                <button
                  key={yr}
                  type="button"
                  onClick={() => {
                    onSelectYear(yr);
                    onSelectMonth("all");
                    onSelectPolicyFilter("all");
                  }}
                  className={`px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
                    isSelected
                      ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                      : "bg-[#f5f5f7] text-[#454545] hover:text-[#1b1717] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
                  }`}
                  title={`${yr}: ${totalPolicies} policies, ${totalCars} cars`}
                >
                  <span className="font-mono font-bold">{yr}</span>
                  {yr === currentYear && (
                    <span className="text-[10px] text-amber-500 font-bold" title="Current Year">
                      ●
                    </span>
                  )}
                  {(totalPolicies > 0 || totalCars > 0) && (
                    <span
                      className={`px-1.5 py-0.2 rounded text-[10px] font-mono font-bold ${
                        isSelected ? "bg-white/20 text-white" : "bg-[#e5e5ea] text-neutral-700"
                      }`}
                    >
                      {totalPolicies} {totalPolicies === 1 ? "pol" : "pols"} · {totalCars}{" "}
                      {totalCars === 1 ? "car" : "cars"}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Row 2: 12 Months Tabs with Start/End Hover Tooltip */}
        <div className="space-y-1.5 pt-2 border-t border-[#f2f2f7]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-neutral-700 uppercase tracking-wide">
              Step 2: Filter by Month
            </span>
            <span className="text-[10px] text-neutral-400">
              Hover over a month to see starting vs expiring breakdown
            </span>
          </div>

          {loadingMonths ? (
            <div className="h-9 flex items-center text-xs text-[#8e8e93]">Loading tenure timeline...</div>
          ) : (
            <div
              ref={monthScrollRef}
              className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-0.5 scroll-smooth scrollbar-thin"
            >
              {/* "All Months" tab */}
              <button
                type="button"
                onClick={() => onSelectMonth("all")}
                className={`shrink-0 min-w-max px-3.5 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 cursor-pointer ${
                  selectedMonth === "all"
                    ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                    : "bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
                }`}
              >
                <span>{selectedYear === "all" ? "All Months" : `All ${selectedYear}`}</span>
              </button>

              {/* 12 Months: Jan to Dec */}
              {monthsOfYear.map((m) => {
                const isActive = selectedMonth === m.month;
                const isCurrent = m.month === currentMonthKey;
                const tooltipText = `${m.label} ${
                  selectedYear === "all" ? currentYear : selectedYear
                }\n• ${m.start_count} Starting\n• ${m.end_count} Expiring\n${m.total} Total Policies · ${
                  m.cars
                } Cars`;

                return (
                  <button
                    key={m.month}
                    type="button"
                    data-month={m.month}
                    onClick={() => onSelectMonth(m.month)}
                    className={`shrink-0 min-w-max px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-medium whitespace-nowrap transition-all flex items-center gap-1.5 cursor-pointer ${
                      isActive
                        ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                        : "bg-[#f5f5f7] text-[#454545] hover:bg-[#e5e5ea] border border-[#e5e5ea]"
                    } ${isCurrent && !isActive ? "ring-1 ring-[#007aff]/60 font-semibold" : ""}`}
                    title={tooltipText}
                  >
                    <span>{m.label}</span>
                    {(m.total > 0 || m.cars > 0) && (
                      <span
                        className={`px-1.5 py-0.2 rounded text-[10px] font-bold font-mono ${
                          isActive ? "bg-white/20 text-white" : "bg-[#e5e5ea] text-[#1b1717]"
                        }`}
                      >
                        ({m.total > 0 ? m.total : m.cars})
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* 3. ACTIVE RENEWALS VS LOST CLIENTS PANEL & SEARCH CONTROLS (STICKY HEADER) */}
      <div className="sticky top-[56px] z-30 bg-[#f5f5f7]/95 backdrop-blur-md py-2.5 px-3 rounded-[var(--rl-radius)] border border-[#e5e5ea] shadow-xs space-y-2 transition-all">
        <div className="flex flex-col 2xl:flex-row 2xl:items-center justify-between gap-2">
          {/* Category Switcher: Active Renewals vs Issued vs Pending vs Lost Clients */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1 bg-white p-1 rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] shadow-2xs w-fit max-w-full flex-wrap">
              <button
                type="button"
                onClick={() => {
                  onSelectCategory("active");
                  onSelectPolicyFilter("all");
                  if (stageFilter === "Close - Lose" || stageFilter === "Others") {
                    onClearStageFilter();
                  }
                }}
                className={`shrink-0 whitespace-nowrap flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-bold transition-all cursor-pointer ${
                  category === "active" && policyFilter === "all"
                    ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                    : "text-neutral-600 hover:text-neutral-900 hover:bg-neutral-50"
                }`}
              >
                <span>All Renewals ({tenuresCount})</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  onSelectCategory("active");
                  onSelectPolicyFilter("issued");
                  if (stageFilter === "Close - Lose" || stageFilter === "Others") {
                    onClearStageFilter();
                  }
                }}
                className={`shrink-0 whitespace-nowrap flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-bold transition-all cursor-pointer ${
                  category === "active" && policyFilter === "issued"
                    ? "bg-emerald-600 text-white shadow-2xs"
                    : "text-emerald-700 hover:text-emerald-900 hover:bg-emerald-50"
                }`}
                title="Filter to vehicles with an issued policy / cover note bound"
              >
                <CheckCircle size={13} weight="bold" />
                <span>Issued Policies ({issuedCount})</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  onSelectCategory("active");
                  onSelectPolicyFilter("pending");
                  if (stageFilter === "Close - Lose" || stageFilter === "Others") {
                    onClearStageFilter();
                  }
                }}
                className={`shrink-0 whitespace-nowrap flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-bold transition-all cursor-pointer ${
                  category === "active" && policyFilter === "pending"
                    ? "bg-amber-600 text-white shadow-2xs"
                    : "text-amber-700 hover:text-amber-900 hover:bg-amber-50"
                }`}
                title="Filter to vehicles awaiting cover note upload / policy issue"
              >
                <span>Awaiting Cover Note ({pendingCount})</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  onSelectCategory("lost");
                  onSelectPolicyFilter("all");
                }}
                className={`shrink-0 whitespace-nowrap flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-bold transition-all cursor-pointer ${
                  category === "lost"
                    ? "bg-rose-50 text-rose-900 border border-rose-200 shadow-2xs"
                    : "text-neutral-500 hover:text-neutral-800"
                }`}
              >
                <Archive size={14} weight={category === "lost" ? "bold" : "regular"} />
                <span>Lost Clients &amp; Win-Backs</span>
              </button>
            </div>

            {/* Bulk Actions Pill */}
            <TenureBulkActions
              selectedTenureIds={selectedTenureIds}
              tenures={tenures}
              onBulkConfirmHit={onBulkConfirmHit}
              onBulkDelete={onBulkDelete}
              onClearSelection={onClearSelection}
              confirmingBulk={confirmingBulk}
              deletingBulk={deletingBulk}
            />
          </div>

          {/* Search & View Mode Switcher */}
          <div className="flex items-center gap-2 justify-between lg:justify-end flex-wrap sm:flex-nowrap shrink-0">
            {/* Interactive Expanding Search Capsule */}
            <LedgerSearchInput
              value={search}
              onChange={onSearchChange}
              placeholder="Search plate (e.g. JRC 3838), client, IC..."
            />

            <div className="flex items-center gap-1 bg-white p-1 rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] shadow-2xs shrink-0">
              <button
                type="button"
                onClick={() => onSelectViewMode("ledger")}
                className={`p-1.5 rounded-[var(--rl-radius-sm)] text-xs transition-all cursor-pointer ${
                  viewMode === "ledger"
                    ? "bg-[#1b1717] text-white shadow-2xs"
                    : "text-neutral-500 hover:text-neutral-800"
                }`}
                title="Table Ledger View"
              >
                <Table size={16} weight={viewMode === "ledger" ? "bold" : "regular"} />
              </button>
              <button
                type="button"
                onClick={() => onSelectViewMode("calendar")}
                className={`p-1.5 rounded-[var(--rl-radius-sm)] text-xs transition-all cursor-pointer ${
                  viewMode === "calendar"
                    ? "bg-[#1b1717] text-white shadow-2xs"
                    : "text-neutral-500 hover:text-neutral-800"
                }`}
                title="Calendar Expiry View"
              >
                <CalendarBlank size={16} weight={viewMode === "calendar" ? "bold" : "regular"} />
              </button>
            </div>

            {/* Density Toggle (Comfortable vs Compact) */}
            {viewMode === "ledger" && onSelectDensity && (
              <div className="flex items-center gap-0.5 bg-white p-0.5 rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] shadow-2xs shrink-0" title="Row density & compression">
                <button
                  type="button"
                  onClick={() => onSelectDensity("comfortable")}
                  className={`px-2 py-1 rounded-[var(--rl-radius-sm)] text-[11px] font-semibold transition-all cursor-pointer ${
                    density === "comfortable"
                      ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                      : "text-neutral-500 hover:text-neutral-800"
                  }`}
                  title="Normal row spacing"
                >
                  Normal
                </button>
                <button
                  type="button"
                  onClick={() => onSelectDensity("compact")}
                  className={`px-2 py-1 rounded-[var(--rl-radius-sm)] text-[11px] font-semibold transition-all cursor-pointer ${
                    density === "compact"
                      ? "bg-[#1b1717] text-white shadow-2xs font-bold"
                      : "text-neutral-500 hover:text-neutral-800"
                  }`}
                  title="Compact / Compressed mode (ideal for high zoom and smaller screens)"
                >
                  Compact
                </button>
              </div>
            )}

          {/* Column Visibility Menu */}
          {viewMode === "ledger" && onToggleColumnVisibility && (
            <div className="relative">
              <button
                type="button"
                onClick={() => setColMenuOpen((v) => !v)}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-semibold transition-all border cursor-pointer ${
                  hiddenColumns.length > 0
                    ? "bg-amber-50 text-amber-900 border-amber-300 shadow-2xs font-bold"
                    : "bg-white text-neutral-700 border-neutral-200 hover:text-neutral-900"
                }`}
                title="Customize visible columns to compress table width"
              >
                <Columns size={13} weight="bold" />
                <span>
                  Cols{hiddenColumns.length > 0 ? ` (${OPTIONAL_COLUMNS.length - hiddenColumns.length}/${OPTIONAL_COLUMNS.length})` : ""}
                </span>
              </button>

              {colMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-30"
                    onClick={() => setColMenuOpen(false)}
                  />
                  <div className="absolute right-0 top-full mt-1 w-52 bg-white rounded-lg border border-neutral-200 shadow-lg p-2 z-40 space-y-1 text-xs">
                    <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-neutral-400 border-b border-neutral-100">
                      Visible Columns
                    </div>
                    {OPTIONAL_COLUMNS.map((col) => {
                      const isVisible = !hiddenColumns.includes(col.id);
                      return (
                        <label
                          key={col.id}
                          className="flex items-center gap-2 px-2 py-1.5 hover:bg-neutral-50 rounded cursor-pointer select-none text-neutral-700"
                        >
                          <input
                            type="checkbox"
                            checked={isVisible}
                            onChange={() => onToggleColumnVisibility(col.id)}
                            className="w-3.5 h-3.5 rounded border-neutral-300 text-neutral-900 focus:ring-neutral-900 cursor-pointer"
                          />
                          <span className={isVisible ? "font-semibold text-neutral-900" : "text-neutral-500"}>
                            {col.label}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          )}

          <button
            type="button"
            onClick={onToggleShowHidden}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-bold transition-all border cursor-pointer ${
              showHidden
                ? "bg-amber-100 text-amber-900 border-amber-300 shadow-2xs"
                : "bg-white text-neutral-600 border-neutral-200 hover:text-neutral-900"
            }`}
            title="Toggle display of older superseded or archived tenures"
          >
            <Archive size={14} weight={showHidden ? "fill" : "regular"} />
            <span>{showHidden ? "Hide Superseded" : "Show Superseded"}</span>
          </button>

          <button
            type="button"
            onClick={onOpenAddVehicleModal}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--rl-radius-sm)] bg-neutral-900 hover:bg-neutral-800 text-white text-xs font-bold transition-all shadow-xs cursor-pointer"
            title="Add a custom vehicle / policy and start quotation comparison"
          >
            <Plus size={14} weight="bold" />
            <span>Add Vehicle</span>
          </button>
        </div>
      </div>
    </div>

      {/* Advisory Banner for Lost Clients Panel */}
      {category === "lost" && (
        <div className="flex items-center justify-between p-3 rounded-[var(--rl-radius)] border border-rose-200 bg-rose-50/70 text-xs text-rose-900">
          <div className="flex items-center gap-2">
            <Archive size={16} className="text-rose-700 shrink-0" />
            <span>
              <strong>Lost Clients Panel:</strong> Policies closed as <em>Close - Lose</em> or{" "}
              <em>Others</em> are segregated here to keep upcoming renewal pipelines clean, while
              preserving follow-up reminders and win-back opportunities.
            </span>
          </div>
          <button
            type="button"
            onClick={() => onSelectCategory("active")}
            className="text-xs font-bold underline hover:no-underline text-rose-800 shrink-0 ml-2 cursor-pointer"
          >
            Back to Active Ledger
          </button>
        </div>
      )}
    </div>
  );
}
