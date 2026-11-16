"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useLedgerState } from "./useLedgerState";
import { useLedgerModals } from "./useLedgerModals";
import { LedgerKpiCards } from "./LedgerKpiCards";
import { LedgerFiltersBar } from "./LedgerFiltersBar";
import { LedgerTable } from "./LedgerTable";
import { LedgerCalendarView } from "./LedgerCalendarView";
import { LedgerModalsContainer } from "./LedgerModals";
import type {
  LedgerSortColumn,
  YoYStatItem,
  MonthItem,
  PicItem,
  TenureRow,
  StageSummary,
  VehicleGroup,
  CalendarEvent,
} from "./types";
import {
  STAGE_CONFIGS,
  STAGE_ORDER,
  MONTH_NAMES,
  POPULAR_BRANDS,
  formatDateSafe,
  formatDateTimeSafe,
  formatRelativeTime,
} from "./types";

// Re-export types and domain utilities for full backward compatibility
export type {
  LedgerSortColumn,
  YoYStatItem,
  MonthItem,
  PicItem,
  TenureRow,
  StageSummary,
  VehicleGroup,
  CalendarEvent,
};
export {
  STAGE_CONFIGS,
  STAGE_ORDER,
  MONTH_NAMES,
  POPULAR_BRANDS,
  formatDateSafe,
  formatDateTimeSafe,
  formatRelativeTime,
};

export function TenureTimelineLedger() {
  const state = useLedgerState();
  const modals = useLedgerModals(state);
  const searchParams = useSearchParams();

  // Highlighted tenure row from notifications or URL
  const [highlightedTenureId, setHighlightedTenureId] = useState<string | null>(null);
  const [, setTicker] = useState(0);

  // Tick relative timestamps every 5 seconds
  useEffect(() => {
    const timer = setInterval(() => setTicker((t) => t + 1), 5000);
    return () => clearInterval(timer);
  }, []);

  // Listen for highlight parameter from notifications or URL
  useEffect(() => {
    const target = searchParams?.get("highlight_tenure");
    if (target) {
      setHighlightedTenureId(target);
      state.setViewMode("ledger");
      setTimeout(() => {
        const el = document.getElementById(`tenure-row-${target}`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 500);

      const clearTimer = setTimeout(() => {
        setHighlightedTenureId(null);
        try {
          const currentUrl = new URL(window.location.href);
          if (currentUrl.searchParams.has("highlight_tenure")) {
            currentUrl.searchParams.delete("highlight_tenure");
            currentUrl.searchParams.delete("t");
            window.history.replaceState(
              {},
              "",
              currentUrl.pathname +
                (currentUrl.search ? `?${currentUrl.searchParams.toString()}` : "")
            );
          }
        } catch {}
      }, 3500);

      return () => clearTimeout(clearTimer);
    }
  }, [searchParams, state]);

  return (
    <div className="space-y-4">
      {/* 1. TOP STAGE KPI BANNER: 5 SUMMARY CARDS */}
      <LedgerKpiCards
        summary={state.summary}
        loadingSummary={state.loadingSummary}
        stageFilter={state.stageFilter}
        onSelectStage={(stageKey) => {
          if (state.stageFilter === stageKey) {
            state.setStageFilter("all");
          } else {
            state.setStageFilter(stageKey);
            if (stageKey === "Close - Lose" || stageKey === "Others") {
              state.setCategory("lost");
            } else if (state.category === "lost") {
              state.setCategory("active");
            }
          }
        }}
        onClearStageFilter={() => state.setStageFilter("all")}
      />

      {/* 2. DATE RANGES, TABS, SEARCH & BULK ACTIONS CONTROLS */}
      <LedgerFiltersBar
        selectedYear={state.selectedYear}
        onSelectYear={state.setSelectedYear}
        selectedMonth={state.selectedMonth}
        onSelectMonth={state.setSelectedMonth}
        availableYears={state.availableYears}
        monthsOfYear={state.monthsOfYear}
        allYearsSummary={state.allYearsSummary}
        yoyStats={state.yoyStats}
        loadingMonths={state.loadingMonths}
        onJumpToCurrentMonth={state.handleJumpToCurrentMonth}
        onScrollMonths={state.scrollMonths}
        monthScrollRef={state.monthScrollRef}
        onRefresh={() => {
          state.loadMonths();
          state.loadStageSummary();
          state.loadTenures();
          state.loadYoyStats();
        }}
        category={state.category}
        onSelectCategory={state.setCategory}
        policyFilter={state.policyFilter}
        onSelectPolicyFilter={state.setPolicyFilter}
        stageFilter={state.stageFilter}
        onClearStageFilter={() => state.setStageFilter("all")}
        tenuresCount={state.tenures.length}
        issuedCount={state.issuedCount}
        pendingCount={state.pendingCount}
        search={state.search}
        onSearchChange={state.setSearch}
        viewMode={state.viewMode}
        onSelectViewMode={state.setViewMode}
        showHidden={state.showHidden}
        onToggleShowHidden={() => state.setShowHidden(!state.showHidden)}
        onOpenAddVehicleModal={() => modals.setAddVehicleModalOpen(true)}
        selectedTenureIds={state.selectedTenureIds}
        tenures={state.tenures}
        onBulkConfirmHit={state.handleBulkConfirmHit}
        onBulkDelete={state.handleBulkDelete}
        onClearSelection={() => state.setSelectedTenureIds([])}
        confirmingBulk={state.confirmingBulk}
        deletingBulk={state.deletingBulk}
        density={state.density}
        onSelectDensity={state.setDensity}
        hiddenColumns={state.hiddenColumns}
        onToggleColumnVisibility={state.toggleColumnVisibility}
      />

      {/* 3. VIEW 1: EXECUTIVE TABLE LEDGER */}
      {state.viewMode === "ledger" && (
        <LedgerTable
          loadingTenures={state.loadingTenures}
          tenures={state.tenures}
          vehicleGroups={state.vehicleGroups}
          selectedTenureIds={state.selectedTenureIds}
          sortBy={state.sortBy}
          sortDir={state.sortDir}
          category={state.category}
          selectedMonth={state.selectedMonth}
          selectedYear={state.selectedYear}
          highlightedTenureId={highlightedTenureId}
          pics={state.pics}
          density={state.density}
          hiddenColumns={state.hiddenColumns}
          search={state.search}
          onSort={state.handleSort}
          onToggleSelectAll={state.handleToggleSelectAll}
          onToggleSelectGroup={state.handleToggleSelectGroup}
          onDeleteTarget={(target) => modals.setDeleteConfirmTarget(target)}
          onPatchField={state.patchTenureField}
          onOpenCovernoteUpload={(tenure) => modals.setCovernoteUploadTenure(tenure)}
          onOpenHitModal={modals.handleOpenHitModal}
          onOpenMissModal={modals.handleOpenMissModal}
          onOpenDrawer={(id) => modals.setActiveDrawerTenureId(id)}
          onOpenEditModal={(tenure) => modals.setEditingTenure(tenure)}
        />
      )}

      {/* 4. VIEW 2: VISUAL CALENDAR VIEW */}
      {state.viewMode === "calendar" && (
        <LedgerCalendarView
          calendarData={state.calendarData}
          calendarVehicleFilter={state.calendarVehicleFilter}
          setCalendarVehicleFilter={state.setCalendarVehicleFilter}
          calendarVehicleOptions={state.calendarVehicleOptions}
          loadingCalendar={state.loadingCalendar}
          calendarDisplay={state.calendarDisplay}
          setCalendarDisplay={state.setCalendarDisplay}
          onOpenDrawer={(id) => modals.setActiveDrawerTenureId(id)}
        />
      )}

      {/* 5. DRAWERS & MODALS CONTAINER */}
      <LedgerModalsContainer modals={modals} state={state} />
    </div>
  );
}
