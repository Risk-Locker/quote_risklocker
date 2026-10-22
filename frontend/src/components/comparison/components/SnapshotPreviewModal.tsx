"use client";

import React from "react";
import { Camera, Copy, DownloadSimple, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { formatBenefitCoverage, formatShortInsurerName } from "@/lib/benefit-utils";
import { formatLlpLlop, isLlpLlopIncluded } from "../types";
import type { TenureSpec, ComparisonEntry } from "../types";

interface SnapshotPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCopy: () => void;
  isCopying: boolean;
  onDownload: () => void;
  isDownloading: boolean;
  gridRef: React.RefObject<HTMLDivElement | null>;
  tenure: TenureSpec;
  snapshotVisibleCards: ComparisonEntry[];
  activeWinnerPeriod: string;
  visibleRanksMap: Record<string, number>;
  ncdData?: {
    current?: number | null;
    next?: number | null;
  };
}

export function SnapshotPreviewModal({
  isOpen,
  onClose,
  onCopy,
  isCopying,
  onDownload,
  isDownloading,
  gridRef,
  tenure,
  snapshotVisibleCards,
  activeWinnerPeriod,
  visibleRanksMap,
  ncdData,
}: SnapshotPreviewModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto no-print">
      <div className="bg-white rounded-3xl shadow-2xl border border-neutral-200 max-w-7xl w-full flex flex-col max-h-[92vh] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Modal Control Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#e5e5ea] bg-[#f5f5f7]">
          <div>
            <h3 className="text-base font-bold text-[#1b1717] flex items-center gap-2">
              <Camera size={20} weight="fill" className="text-[#1b1717]" />
              Executive Comparison Snapshot Grid
            </h3>
            <p className="text-xs text-[#6e6e73]">
              High-resolution snapshot of {snapshotVisibleCards.length} ranked underwriter option{snapshotVisibleCards.length !== 1 ? "s" : ""}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={onCopy}
              loading={isCopying}
              icon={<Copy size={15} weight="bold" />}
              className="font-bold border-neutral-300 hover:border-black"
            >
              Copy to Clipboard
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={onDownload}
              loading={isDownloading}
              icon={<DownloadSimple size={15} weight="bold" />}
              className="bg-[#1b1717] hover:bg-black text-white font-bold"
            >
              Download PNG
            </Button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-xl border border-neutral-300 hover:bg-neutral-200 text-neutral-600 transition-colors ml-2 cursor-pointer"
              title="Close Snapshot"
            >
              <X size={18} weight="bold" />
            </button>
          </div>
        </div>

        {/* Modal Body: Scrollable Canvas container */}
        <div className="flex-1 overflow-auto p-6 bg-neutral-100 flex items-center justify-center">
          {/* Snapshot Canvas targeted by html-to-image */}
          <div
            ref={gridRef}
            className="bg-white p-8 rounded-3xl border border-neutral-200 shadow-xl w-full max-w-6xl space-y-6"
            style={{ minWidth: snapshotVisibleCards.length <= 3 ? "760px" : "1040px" }}
          >
            {/* Snapshot Brand & Vehicle Header */}
            <div className="border-b-2 border-[#1b1717] pb-4 space-y-4">
              {/* Top Tier: Logo (Left), Title (Center), Plate (Right) */}
              <div className="relative flex items-center justify-between">
                <div className="flex items-center">
                  <img
                    src="/assets/brand/logo-black.png"
                    alt="Risklocker"
                    className="h-9 w-auto object-contain"
                  />
                </div>

                <div className="absolute left-1/2 -translate-x-1/2 text-center pointer-events-none">
                  <h2 className="text-lg md:text-xl font-black tracking-tight text-[#1b1717] uppercase">
                    MOTOR QUOTATION COMPARISON
                  </h2>
                </div>

                <div className="text-right">
                  <div className="inline-block bg-[#f5f5f7] border border-[#e5e5ea] px-3.5 py-1 rounded-lg shadow-2xs">
                    <span className="font-mono font-bold text-base text-[#1b1717]">
                      {tenure.is_plate_undetected || tenure.vehicle_no === "N/A"
                        ? `N/A · Chassis: ${tenure.chassis_no || "N/A"}`
                        : (tenure.vehicle_no || tenure.chassis_no || "Unregistered Vehicle")}
                    </span>
                  </div>
                </div>
              </div>

              {/* Bottom Tier: Policy Period (Left) baseline-aligned with Customer & Roadtax/Runner fee (Right) */}
              <div className="flex items-end justify-between text-xs pt-1">
                <div className="space-y-0.5">
                  <p className="text-xs font-semibold text-[#454545]">
                    Commercial General Insurance
                  </p>
                  <p className="text-[11px] text-[#6e6e73]">
                    Your Shield Against The Unexpected
                  </p>
                  <p className="text-xs text-[#454545]">
                    Coverage Period :{" "}
                    <span className="font-mono font-bold text-[#1b1717]">{activeWinnerPeriod}</span>
                  </p>
                </div>

                <div className="text-right space-y-0.5">
                  <p className="font-bold text-xs text-[#1b1717]">{tenure.customer_name}</p>
                  <p className="text-[11px] text-[#6e6e73]">{tenure.vehicle_model} · {tenure.engine_cc}</p>
                  <p className="text-[11px] font-semibold text-[#454545]">
                    Roadtax and Runner fee :{" "}
                    <span className="font-mono font-bold text-[#1b1717]">
                      RM {(tenure.road_tax + tenure.runner_fee).toFixed(2)}
                    </span>
                  </p>
                  {(tenure.quotation_discount ?? 0) > 0 && (
                    <p className="text-[11px] font-semibold text-emerald-700">
                      Quotation Discount :{" "}
                      <span className="font-mono font-bold">
                        - RM {(tenure.quotation_discount ?? 0).toFixed(2)}
                      </span>
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Visible Cards Grid (strictly ordered by rank) */}
            <div
              className={`grid gap-4 ${
                snapshotVisibleCards.length === 1
                  ? "grid-cols-1 max-w-sm mx-auto"
                  : snapshotVisibleCards.length === 2
                  ? "grid-cols-2"
                  : snapshotVisibleCards.length === 3
                  ? "grid-cols-3"
                  : snapshotVisibleCards.length === 4
                  ? "grid-cols-4"
                  : snapshotVisibleCards.length === 5
                  ? "grid-cols-5"
                  : "grid-cols-2 md:grid-cols-3 lg:grid-cols-4"
              }`}
            >
              {snapshotVisibleCards.map((card, idx) => {
                const isWinner = card.is_recommended;
                const rankNum = visibleRanksMap[card.id] || card.rank || idx + 1;
                return (
                  <div
                    key={card.id}
                    className={`rounded-2xl p-4 flex flex-col justify-between border-2 transition-all ${
                      isWinner
                        ? "border-[#1b1717] bg-white ring-2 ring-[#1b1717]/10 shadow-md"
                        : "border-neutral-200 bg-[#fbfbfb]"
                    }`}
                  >
                    <div className="space-y-3">
                      {/* Rank Badge & Winner Pill */}
                      <div className="flex items-center justify-between gap-1.5 h-6">
                        <span
                          className={`text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full whitespace-nowrap shrink-0 ${
                            rankNum === 1
                              ? "bg-amber-100 text-amber-900 border border-amber-300"
                              : "bg-neutral-100 text-neutral-700 border border-neutral-200"
                          }`}
                        >
                          {`Rank #${rankNum}`}
                        </span>
                        {isWinner && (
                          <span className="text-[10px] font-bold uppercase bg-emerald-100 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded-full whitespace-nowrap shrink-0">
                            Recommended
                          </span>
                        )}
                      </div>

                      {/* Company Name */}
                      <div className="h-6 flex items-center">
                        <h4 className="font-black text-sm text-[#1b1717] tracking-tight uppercase truncate whitespace-nowrap" title={card.company_name}>
                          {formatShortInsurerName(card.company_name)}
                        </h4>
                      </div>

                      {/* Premium Pricing Block */}
                      <div className="rounded-xl bg-white p-3 border border-neutral-200 space-y-1">
                        <div className="flex justify-between items-baseline text-xs text-[#6e6e73]">
                          <span>Sum Insured:</span>
                          <span className="font-mono font-bold text-[#1b1717]">
                            RM {card.sum_insured.toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                        {(card.effective_discount ?? tenure.quotation_discount ?? 0) > 0 ? (
                          <>
                            <div className="pt-1 border-t border-neutral-100 flex justify-between items-baseline text-xs text-[#6e6e73]">
                              <span>Total Payable:</span>
                              <span className="font-mono font-medium line-through">
                                RM {(card.rounded_total_payable != null ? card.rounded_total_payable : Math.round(card.total_payable)).toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                            <div className="flex justify-between items-baseline text-xs text-emerald-700">
                              <span className="font-medium">Discount:</span>
                              <span className="font-mono font-bold">
                                - RM {(card.effective_discount ?? tenure.quotation_discount ?? 0).toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                            <div className="pt-1 border-t border-emerald-100 flex justify-between items-baseline">
                              <span className="text-xs font-bold text-emerald-950">Net Payable:</span>
                              <span className="font-mono font-black text-base text-emerald-700">
                                RM {(card.rounded_net_total_payable != null ? card.rounded_net_total_payable : Math.max(0, (card.rounded_total_payable ?? Math.round(card.total_payable)) - Math.round(card.effective_discount ?? tenure.quotation_discount ?? 0))).toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                          </>
                        ) : (
                          <div className="pt-1 border-t border-neutral-100 flex justify-between items-baseline">
                            <span className="text-xs font-bold text-[#1b1717]">Total Payable:</span>
                            <span className="font-mono font-black text-base text-[#1b1717]">
                              RM {(card.rounded_total_payable != null ? card.rounded_total_payable : Math.round(card.total_payable)).toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Benefit Highlights */}
                      <div className="space-y-1 text-[11px] pt-1 border-t border-neutral-200/60">
                        <div className="h-5 flex items-center justify-between">
                          <span className="text-[#6e6e73]">Valuation:</span>
                          <span className="font-semibold text-[#1b1717]">
                            {card.valuation_type === "agreed_value" ? "Agreed Value" : "Market Value"}
                          </span>
                        </div>
                        <div className="h-5 flex items-center justify-between">
                          <span className="text-[#6e6e73]">NCD:</span>
                          <span className="font-mono font-bold text-[#1b1717]">
                            {card.ncd_percentage != null
                              ? `${card.ncd_percentage}%`
                              : ncdData?.next != null
                              ? `${ncdData.next}%`
                              : tenure.ncd_percentage != null
                              ? `${tenure.ncd_percentage}%`
                              : ncdData?.current != null
                              ? `${ncdData.current}%`
                              : "0%"}
                          </span>
                        </div>
                        <div className="h-5 flex items-center justify-between">
                          <span className="text-[#6e6e73]">Windscreen:</span>
                          <span className="font-mono font-semibold text-[#1b1717]">
                            {card.windscreen_sum_insured && card.windscreen_sum_insured > 0
                              ? `RM ${card.windscreen_sum_insured.toLocaleString()}`
                              : "None"}
                          </span>
                        </div>
                        <div className="h-5 flex items-center justify-between">
                          <span className="text-[#6e6e73]">Flood / Perils:</span>
                          <span
                            className={`font-semibold ${
                              card.special_perils && card.special_perils !== "0" && card.special_perils !== "None"
                                ? "text-emerald-700"
                                : "text-neutral-400"
                            }`}
                          >
                            {card.special_perils && card.special_perils !== "0" && card.special_perils !== "None"
                              ? "Covered"
                              : "Not Included"}
                          </span>
                        </div>
                        <div className="h-5 flex items-center justify-between">
                          <span className="text-[#6e6e73]">Betterment:</span>
                          <span className="font-semibold text-[#1b1717]">
                            {card.betterment_display || (card.waiver_betterment ? "No (0%)" : "Yes")}
                          </span>
                        </div>
                        <div className="h-5 flex items-center justify-between">
                          <span className="text-[#6e6e73]">LLP / LLOP:</span>
                          <span
                            className={`font-semibold ${
                              isLlpLlopIncluded(card.llp_llop)
                                ? "text-[#1b1717]"
                                : "text-neutral-400"
                            }`}
                          >
                            {formatLlpLlop(card.llp_llop)}
                          </span>
                        </div>
                        <div className="h-5 flex items-center justify-between">
                          <span className="text-[#6e6e73]">Towing Limit:</span>
                          <span className="font-mono font-semibold text-[#1b1717]">
                            {formatBenefitCoverage(card.towing_limit || card.towing_km || "Standard", undefined, card.company_name)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="pt-3 mt-3 border-t border-neutral-200 text-center">
                      <span className="text-[10px] font-mono text-neutral-400">
                        Ref:{" "}
                        {card.source_quotation_no ||
                          (card.quotation_ref && !card.quotation_ref.startsWith("RL")
                            ? card.quotation_ref
                            : card.notes || (card.session_id ? `ID: ${card.session_id.slice(0, 8)}` : "N/A"))}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Footer disclaimer */}
            <div className="flex items-center justify-between text-[10px] text-neutral-400 pt-2 border-t border-neutral-200">
              <span>Confidential quotation benchmarking prepared by Risklocker</span>
              <span className="font-mono">
                Generated {new Date().toLocaleDateString("en-MY")}, {new Date().toLocaleTimeString("en-MY", { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
