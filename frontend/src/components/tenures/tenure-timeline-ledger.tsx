"use client";

import React, { useState, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useLedgerState } from "./useLedgerState";
import { useLedgerModals } from "./useLedgerModals";
import { LedgerKpiCards } from "./LedgerKpiCards";
import { LedgerFiltersBar } from "./LedgerFiltersBar";
import { LedgerTable } from "./LedgerTable";
import { LedgerCalendarView } from "./LedgerCalendarView";
import { LedgerModalsContainer } from "./LedgerModals";
import { Dialog } from "@/components/ui/dialog";
import { useRealtimeSync } from "@/hooks/useRealtimeSync";
import { RealtimePresenceBanner } from "@/components/realtime/RealtimePresenceBanner";
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

  // Highlighted tenure row(s) from notifications or Copilot deep-links
  const [highlightedTenureId, setHighlightedTenureId] = useState<string | null>(null);
  const [highlightedTenureIds, setHighlightedTenureIds] = useState<Set<string>>(new Set());
  const pendingSelectIdsRef = useRef<string[]>([]);
  const pendingScrollIdRef = useRef<string | null>(null);
  const [, setTicker] = useState(0);

  // Tick relative timestamps every 5 seconds
  useEffect(() => {
    const timer = setInterval(() => setTicker((t) => t + 1), 5000);
    return () => clearInterval(timer);
  }, []);

  // Listen for highlight / tenure_ids / select / search deep-link parameters
  useEffect(() => {
    const rawTenureIds = searchParams?.get("tenure_ids");
    const singleHighlight = searchParams?.get("highlight_tenure") || searchParams?.get("highlight");
    const shouldSelect = searchParams?.get("select") === "true" || searchParams?.get("select") === "1";
    const paramYear = searchParams?.get("year");
    const paramCategory = searchParams?.get("category");
    const paramSearch = searchParams?.get("search");

    const parsedIds: string[] = [];
    if (rawTenureIds) {
      rawTenureIds
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .forEach((id) => {
          if (!parsedIds.includes(id)) parsedIds.push(id);
        });
    }
    if (singleHighlight) {
      singleHighlight
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .forEach((id) => {
          if (!parsedIds.includes(id)) parsedIds.push(id);
        });
    }

    if (parsedIds.length > 0 || paramSearch) {
      state.setViewMode("ledger");
      if (paramYear) {
        state.setSelectedYear(paramYear);
      } else if (parsedIds.length > 0 || paramSearch) {
        state.setSelectedYear("all");
      }
      if (paramCategory === "active" || paramCategory === "lost" || paramCategory === "all") {
        state.setCategory(paramCategory);
      } else if (parsedIds.length > 0 || paramSearch) {
        state.setCategory("all");
      }
      if (rawTenureIds && parsedIds.length > 0) {
        state.setFocusedTenureIds(parsedIds);
      } else {
        state.setFocusedTenureIds([]);
      }
      if (paramSearch && !rawTenureIds) {
        state.setSearch(paramSearch);
      } else if (rawTenureIds) {
        state.setSearch("");
      }
    }

    if (parsedIds.length > 0) {
      setHighlightedTenureId(parsedIds[0]);
      setHighlightedTenureIds(new Set(parsedIds));
      pendingScrollIdRef.current = parsedIds[0];
      if (shouldSelect) {
        pendingSelectIdsRef.current = parsedIds;
      }

      const clearTimer = setTimeout(() => {
        setHighlightedTenureId(null);
        setHighlightedTenureIds(new Set());
        try {
          const currentUrl = new URL(window.location.href);
          let changed = false;
          for (const k of ["highlight_tenure", "highlight", "t"]) {
            if (currentUrl.searchParams.has(k)) {
              currentUrl.searchParams.delete(k);
              changed = true;
            }
          }
          if (changed) {
            window.history.replaceState(
              {},
              "",
              currentUrl.pathname +
                (currentUrl.search ? `?${currentUrl.searchParams.toString()}` : "")
            );
          }
        } catch {}
      }, 4500);

      return () => clearTimeout(clearTimer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Apply pending auto-selection and smooth scroll once ledger rows finish loading
  useEffect(() => {
    if (state.loadingTenures || state.tenures.length === 0) return;
    const loadedSet = new Set(state.tenures.map((t) => t.id));

    if (pendingSelectIdsRef.current.length > 0) {
      const matched = pendingSelectIdsRef.current.filter((id) => loadedSet.has(id));
      if (matched.length > 0) {
        state.setSelectedTenureIds(matched);
        pendingSelectIdsRef.current = [];
      }
    }

    if (pendingScrollIdRef.current && loadedSet.has(pendingScrollIdRef.current)) {
      const scrollId = pendingScrollIdRef.current;
      pendingScrollIdRef.current = null;
      setTimeout(() => {
        const el = document.getElementById(`tenure-row-${scrollId}`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 120);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.loadingTenures, state.tenures]);

  const realtime = useRealtimeSync({
    scope: "ledger",
    resourceId: "all",
    hasUnsavedChanges: Boolean(modals.activeDrawerTenureId || modals.addVehicleModalOpen),
    onRemoteUpdate: () => {
      state.loadMonths();
      state.loadStageSummary();
      state.loadTenures();
      state.loadYoyStats();
    },
  });

  useEffect(() => {
    if (modals.activeDrawerTenureId) {
      void realtime.reportEditing(`tenure:${modals.activeDrawerTenureId}`);
    } else if (modals.addVehicleModalOpen) {
      void realtime.reportEditing("new-vehicle");
    } else {
      void realtime.clearEditing();
    }
  }, [modals.activeDrawerTenureId, modals.addVehicleModalOpen, realtime.reportEditing, realtime.clearEditing]);

  return (
    <div className="space-y-4">
      <RealtimePresenceBanner
        connected={realtime.connected}
        syncMode={realtime.syncMode}
        otherEditors={realtime.otherEditors}
        primaryEditor={realtime.primaryEditor}
        isPrimaryEditor={realtime.isPrimaryEditor}
        pendingUpdate={realtime.pendingUpdate}
        onRefreshNow={() => void realtime.refreshNow()}
        onDismissPending={realtime.dismissPendingUpdate}
      />

      {state.loadError && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--rl-radius-sm)] border border-red-300 bg-red-50 px-3.5 py-2.5 text-xs font-semibold text-red-900"
        >
          <span>Could not load ledger data: {state.loadError}</span>
          <button
            type="button"
            onClick={state.retryAll}
            className="rounded border border-red-300 bg-white px-2.5 py-1 text-[11px] font-bold text-red-900 hover:bg-red-100 cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}
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
        anchor={state.anchor}
        onSelectAnchor={state.setAnchor}
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
        tenuresCount={state.activeTenuresTotal}
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

      {/* Copilot Deep-Link Focus Banner */}
      {state.focusedTenureIds.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--rl-radius-sm)] border border-emerald-300 bg-emerald-50 px-3.5 py-2 text-xs text-emerald-950">
          <span className="font-semibold">
            Showing {state.focusedTenureIds.length} vehicle{state.focusedTenureIds.length === 1 ? "" : "s"} selected from AI Copilot
            {state.selectedTenureIds.length > 0 ? ` · ${state.selectedTenureIds.length} checked` : ""}
          </span>
          <button
            type="button"
            onClick={() => {
              pendingSelectIdsRef.current = [];
              pendingScrollIdRef.current = null;
              state.setFocusedTenureIds([]);
              state.setSelectedTenureIds([]);
              try {
                const url = new URL(window.location.href);
                url.searchParams.delete("tenure_ids");
                url.searchParams.delete("select");
                window.history.replaceState({}, "", url.pathname + (url.search ? `?${url.searchParams.toString()}` : ""));
              } catch {}
            }}
            className="rounded border border-emerald-400 bg-white px-2.5 py-1 text-[11px] font-bold text-emerald-900 hover:bg-emerald-100 cursor-pointer"
          >
            Show All Ledger
          </button>
        </div>
      )}

      {/* 3. VIEW 1: EXECUTIVE TABLE LEDGER */}
      {state.viewMode === "ledger" && (
        <LedgerTable
          loadingTenures={state.loadingTenures}
          tenures={state.tenures}
          totalTenures={state.totalTenures}
          page={state.page}
          pageSize={state.pageSize}
          onPageChange={state.setPage}
          vehicleGroups={state.vehicleGroups}
          selectedTenureIds={state.selectedTenureIds}
          sortBy={state.sortBy}
          sortDir={state.sortDir}
          category={state.category}
          selectedMonth={state.selectedMonth}
          selectedYear={state.selectedYear}
          highlightedTenureId={highlightedTenureId}
          highlightedTenureIds={highlightedTenureIds}
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
          hasActiveFilters={state.hasActiveFilters}
          onResetFilters={state.resetFilters}
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

      {/* 6. ACCESSIBLE BULK ACTION CONFIRMATION DIALOG */}
      <Dialog
        open={Boolean(state.pendingBulkAction)}
        onOpenChange={(open) => {
          if (!open && !state.deletingBulk && !state.confirmingBulk) {
            state.setPendingBulkAction(null);
          }
        }}
        title={
          state.pendingBulkAction === "delete"
            ? `Move ${state.selectedTenureIds.length} deal(s) to Trash?`
            : `Confirm HIT for ${state.selectedTenureIds.length} deal(s)?`
        }
        description={
          state.pendingBulkAction === "delete"
            ? "Associated quotation sessions, comparisons, and PDFs will be archived for 30 days."
            : "This marks all selected deals as Won / Issued Policy and creates upcoming renewal tenures for next year where applicable."
        }
        onConfirm={state.confirmPendingBulkAction}
        confirmLabel={
          state.pendingBulkAction === "delete"
            ? "Move to Trash"
            : `Confirm Hit (${state.selectedTenureIds.length})`
        }
        confirmVariant={state.pendingBulkAction === "delete" ? "danger" : "primary"}
        loading={state.deletingBulk || state.confirmingBulk}
      />
    </div>
  );
}
