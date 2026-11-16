"use client";

import React from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  Car,
  CheckCircle,
  Columns,
  FilePdf,
  Sparkle,
  Trash,
  PencilSimple,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { fileUrl } from "@/lib/api";
import { getVehicleDisplayName, shouldDisplayBrand } from "@/lib/vehicle-utils";
import type { VehicleGroup, TenureRow, PicItem } from "./types";
import {
  STAGE_CONFIGS,
  formatDateSafe,
  formatDateTimeSafe,
  formatRelativeTime,
} from "./types";
import { TenureStageSelector } from "./TenureStageSelector";
import { HighlightText } from "./HighlightText";

export interface TenureRowProps {
  group: VehicleGroup;
  selectedTenureIds: string[];
  onToggleSelectGroup: (ids: string[], isSelected: boolean) => void;
  onDeleteTarget: (target: { id: string; vehicleNo: string; allIds: string[] }) => void;
  highlightedTenureId: string | null;
  pics: PicItem[];
  density?: "comfortable" | "compact";
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

  const isPolicyIssued = Boolean(
    mainTenure.covernote_policy ||
    mainTenure.is_covernote_issued ||
    mainTenure.stage === "Close - Win" ||
    mainTenure.status === "hit"
  );

  const isGroupSelected = group.tenures.some((t) => selectedTenureIds.includes(t.id));
  const displayName = getVehicleDisplayName(group.vehicle_no, group.chassis_no, group.engine_no);
  const isChassis = displayName.startsWith("Chassis:");
  const isEngine = displayName.startsWith("Engine:");
  const isBlank = displayName === "No Plate (Blank)";

  const getPicDisplay = (t: TenureRow) => {
    const matched = pics.find((p) => p.id === t.pic_id);
    if (matched) {
      return {
        name: matched.name,
        type: matched.type,
        agency: matched.agency_group,
        phone: matched.phone,
        whatsapp: matched.whatsapp_number,
      };
    }
    if (t.sub_agent_name) {
      return {
        name: t.sub_agent_name,
        type: "subagent" as const,
        agency: t.pic_agency || null,
        phone: null,
        whatsapp: null,
      };
    }
    return null;
  };

  const picInfo = getPicDisplay(mainTenure);
  const isHighlighted = highlightedTenureId === mainTenure.id;
  const isLost = stageConf.isLost;
  const stickyBg = isHighlighted
    ? "bg-emerald-50/95"
    : isLost
      ? "bg-[#fff7f7]"
      : "bg-white group-hover:bg-neutral-50/90";
  const isCompact = density === "compact";

  return (
    <tr
      id={`tenure-row-${mainTenure.id}`}
      className={`hover:bg-neutral-50/80 transition-colors group ${isHighlighted
          ? "bg-emerald-50/90 ring-2 ring-emerald-500/80 ring-inset shadow-md transition-all duration-1000"
          : isLost
            ? "bg-rose-50/20"
            : ""
        }`}
    >
      {/* 0. Select Checkbox & Direct Delete (Sticky) */}
      <td className={`w-14 min-w-[56px] max-w-[56px] text-center sticky left-0 z-20 ${stickyBg} ${isCompact ? "py-2 px-2" : "py-3 px-3"}`}>
        <div className="flex items-center justify-center gap-1.5">
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
            className="flex size-5 sm:size-6 items-center justify-center rounded text-neutral-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
            title={`Delete ${displayName}`}
            aria-label={`Delete ${displayName}`}
          >
            <Trash size={12} weight="bold" />
          </button>
        </div>
      </td>

      {/* 1. Vehicle & Client (Sticky) */}
      <td className={`sticky left-[56px] z-20 border-r border-neutral-200/90 shadow-[4px_0_6px_-2px_rgba(0,0,0,0.06)] ${stickyBg} ${isCompact ? "py-2 px-2.5 min-w-[180px]" : "py-3 px-3 min-w-[210px]"}`}>
        {isCompact ? (
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5 flex-wrap">
              <div className="font-bold text-neutral-900 font-mono text-xs flex items-center gap-1">
                <Car className="w-3.5 h-3.5 text-neutral-600 shrink-0" />
                <span className="truncate max-w-[110px]" title={displayName}>
                  <HighlightText text={displayName} query={search} />
                </span>
              </div>
              <span className="text-neutral-300">·</span>
              <span className="font-semibold text-neutral-800 text-xs truncate max-w-[130px]" title={group.customer_name}>
                {group.customer_name ? (
                  <HighlightText text={group.customer_name} query={search} />
                ) : (
                  <span className="text-neutral-400 italic">No name</span>
                )}
              </span>
              <button
                type="button"
                onClick={() => onOpenEditModal(mainTenure)}
                className="text-neutral-400 hover:text-black transition-colors"
                title="Edit Customer, Plate & Vehicle Details"
              >
                <PencilSimple size={11} weight="bold" />
              </button>
            </div>
            <div className="text-[10px] text-neutral-500 font-medium truncate max-w-[240px]">
              {shouldDisplayBrand(group.car_brand, group.car_model) ? <><HighlightText text={group.car_brand!} query={search} /> </> : ""}
              {group.car_model ? <HighlightText text={group.car_model} query={search} /> : ""}
              {group.engine_cc ? ` · ${group.engine_cc}cc` : ""}
              {group.manufacture_year ? ` · ${group.manufacture_year}` : ""}
              {group.customer_ic_no ? <> · IC: <HighlightText text={group.customer_ic_no} query={search} /></> : ""}
            </div>
          </div>
        ) : (
          <div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <div className="font-bold text-neutral-900 font-mono text-sm flex items-center gap-1.5">
                <Car className="w-3.5 h-3.5 text-neutral-600 shrink-0" />
                <span className="truncate max-w-[150px]" title={displayName}>
                  <HighlightText text={displayName} query={search} />
                </span>
              </div>

              {isChassis && (
                <span className="px-1.5 py-0.2 rounded bg-amber-100 text-amber-900 font-sans text-[9px] font-bold shrink-0">
                  CHASSIS
                </span>
              )}
              {isEngine && (
                <span className="px-1.5 py-0.2 rounded bg-indigo-100 text-indigo-900 font-sans text-[9px] font-bold shrink-0">
                  ENGINE
                </span>
              )}
              {isBlank && (
                <span className="px-1.5 py-0.2 rounded bg-neutral-100 text-neutral-600 font-sans text-[9px] font-bold shrink-0">
                  NO PLATE
                </span>
              )}
              <button
                type="button"
                onClick={() => onOpenEditModal(mainTenure)}
                className="text-neutral-400 hover:text-black transition-colors"
                title="Edit Customer, Plate & Vehicle Details"
              >
                <PencilSimple size={12} weight="bold" />
              </button>
            </div>

            <div className="text-xs font-semibold text-neutral-800 mt-1 truncate max-w-[210px]">
              {group.customer_name ? (
                <HighlightText text={group.customer_name} query={search} />
              ) : (
                <span className="text-neutral-400 italic">No customer name</span>
              )}
            </div>
            {group.customer_ic_no && (
              <div className="text-[10px] text-neutral-400 font-mono mt-0.5 truncate max-w-[210px]">
                IC: <HighlightText text={group.customer_ic_no} query={search} />
              </div>
            )}
            {(group.car_brand || group.car_model || group.engine_cc || group.manufacture_year) && (
              <div className="text-[10px] text-neutral-500 font-medium mt-0.5 truncate max-w-[210px]">
                {shouldDisplayBrand(group.car_brand, group.car_model) ? <><HighlightText text={group.car_brand!} query={search} /> </> : ""}
                {group.car_model ? <HighlightText text={group.car_model} query={search} /> : ""}
                {group.engine_cc ? ` · ${group.engine_cc}cc` : ""}
                {group.manufacture_year ? ` · YOM ${group.manufacture_year}` : ""}
              </div>
            )}
            {mainTenure.created_by_email && (
              <div className="text-[10px] text-neutral-400 font-medium mt-0.5 truncate max-w-[210px] flex items-center gap-1">
                <span>By:</span>
                <span className="text-neutral-600 font-semibold">{mainTenure.created_by_email}</span>
              </div>
            )}
          </div>
        )}
      </td>

      {/* 2. Coverage Period (Main Policy) */}
      <td className={isCompact ? "py-2 px-2.5" : "py-3 px-3"}>
        {isCompact ? (
          <div className="space-y-0.5">
            <div className="flex items-center gap-1 font-mono text-[11px] text-neutral-800">
              <span>{formatDateSafe(mainTenure.coverage_start_date)}</span>
              <span className="text-neutral-400">→</span>
              <span>{formatDateSafe(mainTenure.coverage_end_date)}</span>
            </div>
            <div className="flex items-center gap-1 flex-wrap">
              {isPolicyIssued ? (
                <span className="text-[9px] text-emerald-700 font-bold bg-emerald-50 px-1 py-0.2 rounded border border-emerald-200 flex items-center gap-0.5">
                  <CheckCircle size={9} weight="fill" /> Issued
                </span>
              ) : (
                <span className="text-[9px] text-amber-700 font-bold bg-amber-50 px-1 py-0.2 rounded border border-amber-200">
                  Pending
                </span>
              )}
              {mainTenure.expiry_month && (
                <span className="text-[9px] text-neutral-500 font-mono">
                  {mainTenure.expiry_month}
                </span>
              )}
              {mainTenure.is_main && (
                <span className="text-[9px] text-emerald-800 font-bold">★ Main</span>
              )}
            </div>
          </div>
        ) : mainTenure.covernote_policy?.is_previous_year_policy ? (
          <div className="space-y-0.5">
            <div className="flex items-center gap-1 text-[11px]">
              <span className="text-[9px] font-bold uppercase tracking-wider text-blue-700 bg-blue-50 px-1 py-0.2 rounded border border-blue-200 shrink-0">
                Start
              </span>
              <span className="font-mono font-medium text-neutral-800">
                {formatDateSafe(mainTenure.coverage_start_date)}
              </span>
            </div>
            <div className="flex items-center gap-1 text-[11px]">
              <span className="text-[9px] font-bold uppercase tracking-wider text-blue-700 bg-blue-50 px-1 py-0.2 rounded border border-blue-200 shrink-0">
                End
              </span>
              <span className="font-mono font-medium text-neutral-800">
                {formatDateSafe(mainTenure.coverage_end_date)}
              </span>
            </div>
            <div className="text-[9.5px] text-blue-700 font-bold flex items-center gap-0.5 pt-0.5">
              <Sparkle size={10} weight="fill" /> Upcoming Renewal
            </div>
          </div>
        ) : isPolicyIssued && (mainTenure.covernote_policy?.coverage_start_date || mainTenure.coverage_start_date) ? (
          <div className="space-y-0.5">
            <div className="flex items-center gap-1 text-[11px]">
              <span className="text-[9px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-1 py-0.2 rounded border border-emerald-200 shrink-0">
                Start
              </span>
              <span className="font-mono font-medium text-neutral-800">
                {formatDateSafe(
                  mainTenure.covernote_policy?.coverage_start_date || mainTenure.coverage_start_date
                )}
              </span>
            </div>
            <div className="flex items-center gap-1 text-[11px]">
              <span className="text-[9px] font-bold uppercase tracking-wider text-rose-700 bg-rose-50 px-1 py-0.2 rounded border border-rose-200 shrink-0">
                End
              </span>
              <span className="font-mono font-medium text-neutral-800">
                {formatDateSafe(
                  mainTenure.covernote_policy?.coverage_end_date || mainTenure.coverage_end_date
                )}
              </span>
            </div>
            <div className="text-[9.5px] text-emerald-700 font-bold flex items-center gap-0.5 pt-0.5">
              <CheckCircle size={10} weight="fill" /> Issued Policy
            </div>
          </div>
        ) : mainTenure.external_policy_start_date ? (
          <div className="space-y-0.5">
            <span className="text-[9px] font-bold uppercase tracking-wider text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded border border-purple-200">
              External Policy
            </span>
            <div className="text-[11px] font-mono text-neutral-700">
              {formatDateSafe(mainTenure.external_policy_start_date)} →{" "}
              {formatDateSafe(mainTenure.external_policy_end_date)}
            </div>
          </div>
        ) : mainTenure.coverage_start_date &&
          mainTenure.coverage_end_date &&
          mainTenure.sourced_quotes &&
          mainTenure.sourced_quotes.length > 0 ? (
          <div className="space-y-0.5">
            <div className="flex items-center gap-1 text-[11px]">
              <span className="text-[9px] font-bold uppercase tracking-wider text-amber-700 bg-amber-50 px-1 py-0.2 rounded border border-amber-200 shrink-0">
                Start
              </span>
              <span className="font-mono font-medium text-neutral-800">
                {formatDateSafe(mainTenure.coverage_start_date)}
              </span>
            </div>
            <div className="flex items-center gap-1 text-[11px]">
              <span className="text-[9px] font-bold uppercase tracking-wider text-amber-700 bg-amber-50 px-1 py-0.2 rounded border border-amber-200 shrink-0">
                End
              </span>
              <span className="font-mono font-medium text-neutral-800">
                {formatDateSafe(mainTenure.coverage_end_date)}
              </span>
            </div>
            <div className="text-[9.5px] text-amber-700 font-semibold pt-0.5">
              Pending Cover Note
            </div>
          </div>
        ) : (
          <div className="space-y-0.5">
            <span className="text-neutral-400 font-mono text-xs">—</span>
            <div className="text-[10px] text-neutral-400 font-medium">Pending Renewal</div>
          </div>
        )}
        <div className="flex items-center gap-1.5 mt-1">
          {mainTenure.expiry_month ? (
            <span className="text-[10px] text-neutral-500 font-medium font-mono">
              Exp: {mainTenure.expiry_month}
            </span>
          ) : (
            <span className="text-[10px] text-neutral-400 font-medium italic">
              Extracted on Upload
            </span>
          )}
          {mainTenure.is_main && (
            <span className="px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-800 text-[9px] font-bold border border-emerald-200 flex items-center gap-0.5">
              ★ Main
            </span>
          )}
        </div>
      </td>

      {/* 3. Pipeline Stage (Main Policy) */}
      <td className={isCompact ? "py-2 px-2.5" : "py-3 px-3"}>
        <div className="flex items-center gap-1.5">
          <TenureStageSelector
            tenure={mainTenure}
            onPatchField={onPatchField}
            onOpenCovernoteUpload={onOpenCovernoteUpload}
            onOpenHitModal={onOpenHitModal}
            onOpenMissModal={onOpenMissModal}
          />
          <span
            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold font-mono shrink-0 ${isOverdue
                ? "bg-rose-100 text-rose-800 border border-rose-200"
                : "bg-neutral-100 text-neutral-700"
              }`}
            title={`Days in stage: ${mainTenure.days_in_stage || 0}`}
          >
            {mainTenure.days_in_stage || 0}d
          </span>
        </div>
      </td>

      {/* 4. Policy Details & Sourced Quotes */}
      {!hiddenColumns.includes("last_activity") && (
        <td className={isCompact ? "py-2 px-2.5" : "py-3 px-3"}>
          {mainTenure.covernote_policy ? (
            <div className="space-y-1.5 min-w-[210px] max-w-[260px]">
              {/* Official Issued Cover Note Top Strip */}
              <div className="flex items-center justify-between gap-1 flex-wrap">
                <div className="flex items-center gap-1 flex-wrap">
                  <span className="font-bold text-xs text-neutral-900 truncate">
                    <HighlightText text={mainTenure.covernote_policy.company} query={search} />
                  </span>
                  <span
                    className={`inline-flex items-center px-1.5 py-0.2 rounded text-[9px] font-bold border ${mainTenure.covernote_policy.is_previous_year_policy
                        ? "bg-blue-50 text-blue-800 border-blue-200"
                        : "bg-emerald-50 text-emerald-800 border-emerald-200"
                      }`}
                  >
                    {mainTenure.covernote_policy.is_previous_year_policy
                      ? "Previous Policy"
                      : "Cover Note"}
                  </span>
                </div>
                {mainTenure.covernote_policy.total_payable && (
                  <span className="text-emerald-950 font-mono font-bold text-xs bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200 shrink-0">
                    RM {mainTenure.covernote_policy.total_payable}
                  </span>
                )}
              </div>

              {/* Authentic Insurance Period & Policy # */}
              <div className="text-[10.5px] font-mono text-neutral-700">
                {mainTenure.covernote_policy.coverage_period_formatted ||
                  (mainTenure.covernote_policy.coverage_start_date &&
                    mainTenure.covernote_policy.coverage_end_date ? (
                    <span>
                      {formatDateSafe(mainTenure.covernote_policy.coverage_start_date)} –{" "}
                      {formatDateSafe(mainTenure.covernote_policy.coverage_end_date)}
                    </span>
                  ) : (
                    "—"
                  ))}
              </div>

              {/* Key Perils */}
              {(mainTenure.covernote_policy.sum_insured ||
                mainTenure.covernote_policy.perils ||
                mainTenure.covernote_policy.windscreen) && (
                  <div className="text-[9.5px] text-neutral-500 font-medium truncate flex items-center gap-1 flex-wrap">
                    {mainTenure.covernote_policy.sum_insured && (
                      <span>SI: RM {mainTenure.covernote_policy.sum_insured}</span>
                    )}
                    {mainTenure.covernote_policy.windscreen && (
                      <span>· WS: RM {mainTenure.covernote_policy.windscreen}</span>
                    )}
                    {mainTenure.covernote_policy.towing && (
                      <span>· Tow: {mainTenure.covernote_policy.towing}</span>
                    )}
                  </div>
                )}

              {/* Direct PDF Link & Quick Hit Action */}
              <div className="flex items-center justify-between gap-1 pt-0.5">
                {mainTenure.covernote_policy.uploaded_file_id ? (
                  <a
                    href={fileUrl(mainTenure.covernote_policy.uploaded_file_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[10px] font-bold text-rose-700 hover:text-rose-900 bg-rose-50 hover:bg-rose-100 px-1.5 py-0.5 rounded border border-rose-200 transition-colors"
                    title="Open Cover Note PDF in new tab"
                  >
                    <FilePdf size={11} weight="fill" />
                    <span className="truncate max-w-[120px]">
                      <HighlightText
                        text={mainTenure.covernote_policy.file_name || "Cover Note PDF"}
                        query={search}
                      />
                    </span>
                  </a>
                ) : (
                  <span className="text-[10px] text-neutral-400 italic">No PDF bound</span>
                )}

                {mainTenure.stage !== "Close - Win" && (
                  <button
                    type="button"
                    onClick={() => onOpenHitModal(mainTenure)}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-700 hover:bg-emerald-800 text-white text-[10px] font-bold shadow-2xs transition-colors cursor-pointer"
                    title="Policy is issued! Click to seal HIT"
                  >
                    <CheckCircle size={11} weight="bold" />
                    <span>Confirm Hit ✓</span>
                  </button>
                )}
              </div>

              {/* Multi-Insurer Quotation Quick Links */}
              {mainTenure.sourced_quotes && mainTenure.sourced_quotes.length > 0 ? (
                <div className="flex items-center gap-1 flex-wrap pt-1 border-t border-neutral-100">
                  <span className="text-[9px] font-bold text-neutral-400 uppercase">Quotes:</span>
                  {mainTenure.sourced_quotes.map((q) => (
                    <Link
                      key={q.session_id}
                      href={`/sessions/${q.session_id}/review` as Route}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] transition-colors border shadow-2xs hover:border-neutral-900 ${q.is_winner
                          ? "bg-amber-50 text-amber-900 border-amber-300 font-bold"
                          : "bg-white text-neutral-700 border-neutral-200 hover:bg-neutral-50 font-medium"
                        }`}
                      title={`Open ${q.company} quote workspace in new tab`}
                    >
                      <span>{q.company}</span>
                      {q.total_payable && (
                        <span className="font-mono text-[9px] text-neutral-500 font-bold">
                          {Number(q.total_payable).toFixed(0)}
                        </span>
                      )}
                    </Link>
                  ))}
                  <Link
                    href={`/comparison?tenure_id=${mainTenure.id}` as Route}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-0.5 text-[10px] font-bold text-amber-800 hover:text-amber-950 hover:underline ml-0.5"
                    title="Open Marketing Comparison in new tab"
                  >
                    <span>({mainTenure.sourced_quotes.length}) →</span>
                  </Link>
                </div>
              ) : mainTenure.covernote_policy.is_previous_year_policy ? (
                <div className="flex items-center justify-between gap-1 pt-1 border-t border-neutral-100 text-[10.5px]">
                  <span className="text-[10px] text-neutral-500 font-medium italic">
                    0 quotes compiled · Awaiting Quotes
                  </span>
                  <Link
                    href={`/upload?tenure_id=${mainTenure.id}` as Route}
                    target="_blank"
                    className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:text-blue-800 hover:underline"
                  >
                    + Add Quotes →
                  </Link>
                </div>
              ) : null}
            </div>
          ) : mainTenure.sourced_quotes.length === 0 ? (
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-neutral-400 italic text-[11px]">0 quotes compiled</span>
                <span className="inline-flex items-center px-1.5 py-0.2 rounded bg-neutral-100 text-neutral-600 text-[9px] font-medium border border-neutral-200">
                  Awaiting Cover Note
                </span>
              </div>
              <div className="text-[10px] text-neutral-500 font-mono">
                {formatDateSafe(mainTenure.coverage_start_date)} –{" "}
                {formatDateSafe(mainTenure.coverage_end_date)}
              </div>
              <Link
                href={`/comparison?tenure_id=${mainTenure.id}` as Route}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[10px] font-bold text-neutral-700 hover:text-black underline"
              >
                <span>Open Comparison Matrix →</span>
              </Link>
            </div>
          ) : (
            <div className="space-y-1.5 min-w-[210px] max-w-[260px]">
              {/* Leading / Sourced Quote Strip */}
              <div className="flex items-center justify-between gap-1.5 flex-wrap">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="font-bold text-xs text-neutral-900 truncate">
                    {mainTenure.winning_company_name || mainTenure.sourced_quotes[0].company}
                  </span>
                  <span className="inline-flex items-center px-1.5 py-0.2 rounded bg-amber-50 text-amber-800 text-[9px] font-bold border border-amber-200">
                    Awaiting Cover Note
                  </span>
                </div>
                {(mainTenure.won_premium
                  ? String(mainTenure.won_premium)
                  : mainTenure.sourced_quotes[0].total_payable) && (
                    <span className="text-neutral-900 font-mono font-bold text-xs bg-neutral-100 px-1.5 py-0.5 rounded border border-neutral-200 shrink-0">
                      RM {mainTenure.won_premium || mainTenure.sourced_quotes[0].total_payable}
                    </span>
                  )}
              </div>

              {/* Target Coverage Period */}
              <div className="text-[10.5px] font-mono text-neutral-600">
                {formatDateSafe(mainTenure.coverage_start_date)} –{" "}
                {formatDateSafe(mainTenure.coverage_end_date)}
              </div>

              {/* Multi-Insurer Quotation Quick-Links */}
              <div className="flex items-center gap-1 flex-wrap pt-0.5">
                {mainTenure.sourced_quotes.map((q) => (
                  <Link
                    key={q.session_id}
                    href={`/sessions/${q.session_id}/review` as Route}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] transition-colors border shadow-2xs hover:border-neutral-900 ${q.is_winner
                        ? "bg-amber-50 text-amber-900 border-amber-300 font-bold"
                        : "bg-white text-neutral-700 border-neutral-200 hover:bg-neutral-50 font-medium"
                      }`}
                    title={`Open ${q.company} quote workspace in new tab`}
                  >
                    <span>{q.company}</span>
                    {q.total_payable && (
                      <span className="font-mono text-[9px] text-neutral-500 font-bold">
                        {Number(q.total_payable).toFixed(0)}
                      </span>
                    )}
                  </Link>
                ))}
                <Link
                  href={`/comparison?tenure_id=${mainTenure.id}` as Route}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-0.5 text-[10px] font-bold text-amber-800 hover:text-amber-950 hover:underline ml-0.5"
                  title="Open Marketing Comparison in new tab"
                >
                  <span>({mainTenure.sourced_quotes.length}) →</span>
                </Link>
              </div>

              {/* PDF links */}
              <div className="flex items-center gap-1 flex-wrap pt-0.5">
                {mainTenure.winning_file_id && (
                  <a
                    href={fileUrl(mainTenure.winning_file_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[10px] font-bold text-rose-700 hover:text-rose-900 bg-rose-50 px-1.5 py-0.2 rounded border border-rose-200"
                    title="Open Won Quotation PDF"
                  >
                    <FilePdf size={10} weight="fill" />
                    <span>Won PDF</span>
                  </a>
                )}
                {(() => {
                  const winQuote = mainTenure.sourced_quotes.find(
                    (q) => q.is_winner && q.uploaded_file_id
                  );
                  const isActualWinner = Boolean(
                    winQuote?.is_winner || mainTenure.stage === "Close - Win" || mainTenure.status === "hit"
                  );
                  if (winQuote && winQuote.uploaded_file_id) {
                    return (
                      <a
                        href={fileUrl(winQuote.uploaded_file_id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`inline-flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.2 rounded border ${isActualWinner
                            ? "text-rose-700 bg-rose-50 border-rose-200"
                            : "text-neutral-600 bg-neutral-50 border-neutral-200"
                          }`}
                        title={
                          isActualWinner
                            ? `Open Accepted Quotation PDF (${winQuote.company})`
                            : `Open Leading Quotation PDF (${winQuote.company})`
                        }
                      >
                        <FilePdf size={10} weight="fill" />
                        <span>{isActualWinner ? "Accepted PDF" : "Leading PDF"}</span>
                      </a>
                    );
                  }
                  return null;
                })()}
              </div>
            </div>
          )}
        </td>
      )}

      {/* 5. Date of Ledger Creation */}
      {!hiddenColumns.includes("created_at") && (
        <td className={`${isCompact ? "py-2 px-2.5 min-w-[130px]" : "py-3 px-3 min-w-[150px]"}`}>
          {mainTenure.created_at ? (
            <div>
              <div
                className="text-xs font-mono font-medium text-neutral-800"
                title={`Full Timestamp: ${formatDateTimeSafe(mainTenure.created_at)}`}
              >
                {(() => {
                  const d = new Date(mainTenure.created_at);
                  if (isNaN(d.getTime())) return formatDateSafe(mainTenure.created_at);
                  return d.toLocaleDateString("en-MY", {
                    day: "2-digit",
                    month: "short",
                    year: "numeric",
                  });
                })()}
              </div>
              <div className="text-[10px] text-neutral-400 font-mono mt-0.5">
                {formatRelativeTime(mainTenure.created_at)}
              </div>
            </div>
          ) : (
            <span className="text-neutral-400 italic text-[11px]">—</span>
          )}
        </td>
      )}

      {/* 6. PIC & Milestones */}
      {!hiddenColumns.includes("pic") && (
        <td className={isCompact ? "py-2 px-2.5" : "py-3 px-3"}>
          <div className="space-y-1 min-w-[140px]">
            {/* Row 1: PIC info */}
            <div className="flex items-center gap-1.5">
              {picInfo ? (
                <div className="flex items-center gap-1 flex-wrap">
                  <span className="font-bold text-xs text-neutral-900">{picInfo.name}</span>
                  {picInfo.agency && (
                    <span className="text-[9px] text-neutral-500 font-medium bg-neutral-100 px-1 py-0.2 rounded">
                      {picInfo.agency}
                    </span>
                  )}
                  {picInfo.whatsapp && (
                    <a
                      href={`https://wa.me/${picInfo.whatsapp.replace(/[^0-9]/g, "")}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-600 hover:text-emerald-800 text-[10px] font-bold bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200"
                      title={`WhatsApp ${picInfo.whatsapp}`}
                    >
                      WA
                    </a>
                  )}
                </div>
              ) : (
                <span className="text-neutral-400 italic text-[11px]">Unassigned</span>
              )}
            </div>

            {/* Row 2: Payment Status */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${mainTenure.client_payment_received
                    ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                    : "bg-neutral-50 text-neutral-500 border-neutral-200"
                  }`}
                title="Client Payment Status"
              >
                {mainTenure.client_payment_received ? "✓ Cli Paid" : "Cli Unpaid"}
              </span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${mainTenure.agency_payment_done
                    ? "bg-blue-50 text-blue-800 border-blue-200"
                    : "bg-neutral-50 text-neutral-500 border-neutral-200"
                  }`}
                title="Agency Payment Status"
              >
                {mainTenure.agency_payment_done ? "✓ Agc Paid" : "Agc Due"}
              </span>
            </div>
          </div>
        </td>
      )}

      {/* 7. Actions */}
      <td className={`text-right ${isCompact ? "py-2 px-2.5" : "py-3 px-3"}`}>
        <div className="flex items-center justify-end gap-1.5">
          <Link
            href={`/comparison?tenure_id=${mainTenure.id}` as Route}
            target="_blank"
            rel="noopener noreferrer"
            className={`inline-flex items-center gap-1 rounded bg-[#1b1717] hover:bg-black text-white font-bold transition-colors shadow-2xs cursor-pointer ${isCompact ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs"
              }`}
            title="Go to Marketing Comparison matrix for this vehicle (New Tab)"
          >
            <Columns className="w-3.5 h-3.5" />
            <span>Compare</span>
          </Link>

          <Button
            size="sm"
            variant="secondary"
            onClick={() => onOpenDrawer(mainTenure.id)}
            className={`cursor-pointer border-[#e5e5ea] hover:border-black ${isCompact ? "h-6 px-1.5 text-[11px]" : "h-7 text-xs font-semibold"
              }`}
          >
            Logs
          </Button>

          <Button
            size="sm"
            variant="secondary"
            onClick={() => onOpenEditModal(mainTenure)}
            className={`cursor-pointer border-[#e5e5ea] hover:border-black ${isCompact ? "h-6 px-1.5 text-[11px]" : "h-7 text-xs font-semibold"
              }`}
          >
            Details
          </Button>
        </div>
      </td>
    </tr>
  );
}
