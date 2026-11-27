"use client";

import React from "react";
import { Trash } from "@phosphor-icons/react";
import { getVehicleDisplayName } from "@/lib/vehicle-utils";
import type { LedgerDensity, VehicleGroup, TenureRow, PicItem } from "./types";
import { STAGE_CONFIGS } from "./types";
import { TenureStageSelector } from "./TenureStageSelector";
import { resolveLedgerColumns, stickyVehicleOffset } from "./ledger-columns";
import { VehicleCustomerCell } from "./row-cells/VehicleCustomerCell";
import { CoveragePeriodCell } from "./row-cells/CoveragePeriodCell";
import { QuotesActivityCell } from "./row-cells/QuotesActivityCell";
import { CreatedAtCell, PicCell } from "./row-cells/PicCell";
import { RowActionsCell } from "./row-cells/RowActionsCell";

export interface TenureRowProps {
  group: VehicleGroup;
  selectedTenureIds: string[];
  onToggleSelectGroup: (ids: string[], isSelected: boolean) => void;
  onDeleteTarget: (target: { id: string; vehicleNo: string; allIds: string[] }) => void;
  highlightedTenureId: string | null;
  highlightedTenureIds?: Set<string>;
  pics: PicItem[];
  density?: LedgerDensity;
  hiddenColumns?: string[];
  search?: string;
  onPatchField: (tenureId: string, updates: Partial<TenureRow>) => Promise<void>;
  onOpenCovernoteUpload: (tenure: TenureRow) => void;
  onOpenHitModal: (tenure: TenureRow) => void;
  onOpenMissModal: (tenure: TenureRow) => void;
  onOpenDrawer: (tenureId: string) => void;
  onOpenEditModal: (tenure: TenureRow) => void;
}

export function TenureRowComponent({
  group,
  selectedTenureIds,
  onToggleSelectGroup,
  onDeleteTarget,
  highlightedTenureId,
  highlightedTenureIds,
  pics,
  density = "comfortable",
  hiddenColumns = [],
  search = "",
  onPatchField,
  onOpenCovernoteUpload,
  onOpenHitModal,
  onOpenMissModal,
  onOpenDrawer,
  onOpenEditModal,
}: TenureRowProps) {
  const mainTenure = group.mainTenure;
  const layout = resolveLedgerColumns(density, hiddenColumns);
  const vehicleStickyLeft = stickyVehicleOffset(layout.isCompact);

  const stageConf = STAGE_CONFIGS[mainTenure.stage] || {
    label: mainTenure.stage,
    bg: "bg-neutral-50",
    text: "text-neutral-700",
    border: "border-neutral-200",
    badge: "bg-neutral-100 text-neutral-800 border-neutral-200",
  };

  const isOverdue =
    (mainTenure.stage === "Quotations" && mainTenure.days_in_stage > 7) ||
    (mainTenure.stage === "Material to Client" && mainTenure.days_in_stage > 5);

  const isGroupSelected = group.tenures.some((t) => selectedTenureIds.includes(t.id));
  const displayName = getVehicleDisplayName(group.vehicle_no, group.chassis_no, group.engine_no);
  const isHighlighted =
    highlightedTenureId === mainTenure.id || Boolean(highlightedTenureIds?.has(mainTenure.id));
  const isLost = stageConf.isLost;
  const stickyBg = isHighlighted
    ? "bg-emerald-50/95"
    : isLost
      ? "bg-[#fff7f7]"
      : "bg-white group-hover:bg-neutral-50/90";

  return (
    <tr
      id={`tenure-row-${mainTenure.id}`}
      className={`hover:bg-neutral-50/80 transition-colors group ${
        isHighlighted
          ? "bg-emerald-50/90 ring-2 ring-emerald-500/80 ring-inset shadow-md transition-all duration-1000"
          : isLost
            ? "bg-rose-50/20"
            : ""
      }`}
    >
      {/* 0. Select Checkbox & Delete (Sticky) */}
      <td
        className={`${layout.widths.select} text-center sticky left-0 z-20 ${stickyBg} ${
          layout.isCompact ? "py-2 px-1.5" : "py-3 px-3"
        }`}
      >
        <div className="flex items-center justify-center gap-1">
          <input
            type="checkbox"
            checked={isGroupSelected}
            onChange={() => {
              const ids = group.tenures.map((t) => t.id);
              onToggleSelectGroup(ids, isGroupSelected);
            }}
            className="w-3.5 h-3.5 rounded border-neutral-300 text-neutral-900 focus:ring-neutral-900 cursor-pointer"
            title={`Select ${displayName}`}
            aria-label={`Select ${displayName}`}
          />
          <button
            type="button"
            onClick={() => {
              const allIds = group.tenures.map((t) => t.id);
              onDeleteTarget({ id: mainTenure.id, vehicleNo: displayName, allIds });
            }}
            className="flex size-5 items-center justify-center rounded text-neutral-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
            title={`Delete ${displayName}`}
            aria-label={`Delete ${displayName}`}
          >
            <Trash size={12} weight="bold" />
          </button>
        </div>
      </td>

      {/* 1. Vehicle & Customer (Sticky) */}
      <td
        className={`sticky ${vehicleStickyLeft} z-20 border-r border-neutral-200/90 shadow-[4px_0_6px_-2px_rgba(0,0,0,0.06)] ${stickyBg} ${layout.cellPadding} ${layout.widths.vehicle}`}
      >
        <VehicleCustomerCell
          group={group}
          mainTenure={mainTenure}
          isCompact={layout.isCompact}
          search={search}
        />
      </td>

      {/* 2. Period / Expiry */}
      <td className={`${layout.cellPadding} ${layout.widths.coverage}`}>
        <CoveragePeriodCell tenure={mainTenure} isCompact={layout.isCompact} />
      </td>

      {/* 3. Timeline & Stage */}
      <td className={`${layout.cellPadding} ${layout.widths.stage}`}>
        <div className="flex items-center gap-1">
          <TenureStageSelector
            tenure={mainTenure}
            compact={layout.isCompact}
            onPatchField={onPatchField}
            onOpenCovernoteUpload={onOpenCovernoteUpload}
            onOpenHitModal={onOpenHitModal}
            onOpenMissModal={onOpenMissModal}
          />
          <span
            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold font-mono shrink-0 ${
              isOverdue
                ? "bg-rose-100 text-rose-800 border border-rose-200"
                : "bg-neutral-100 text-neutral-700"
            }`}
            title={`Days in stage: ${mainTenure.days_in_stage || 0}`}
          >
            {mainTenure.days_in_stage || 0}d
          </span>
        </div>
      </td>

      {/* 4. Latest Quote & Link */}
      {layout.showQuotes && (
        <td className={`${layout.cellPadding} ${layout.widths.quotes}`}>
          <QuotesActivityCell tenure={mainTenure} isCompact={layout.isCompact} search={search} />
        </td>
      )}

      {/* 5. Ledger Created */}
      {layout.showCreatedAt && (
        <td className={`${layout.cellPadding} ${layout.widths.createdAt}`}>
          <CreatedAtCell createdAt={mainTenure.created_at} />
        </td>
      )}

      {/* 6. PIC & Milestones */}
      {layout.showPic && (
        <td className={`${layout.cellPadding} ${layout.widths.pic}`}>
          <PicCell tenure={mainTenure} pics={pics} />
        </td>
      )}

      {/* 7. Actions (Sticky Right) */}
      <td className={`text-right sticky right-0 z-20 border-l border-neutral-200/80 shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.05)] ${stickyBg} ${layout.cellPadding} ${layout.widths.actions}`}>
        <RowActionsCell
          tenure={mainTenure}
          isCompact={layout.isCompact}
          onOpenDrawer={onOpenDrawer}
          onOpenEditModal={onOpenEditModal}
        />
      </td>
    </tr>
  );
}
