/* eslint-disable @next/next/no-img-element */
"use client";

import React, { useEffect, useState } from "react";
import { Camera, Copy, DownloadSimple, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { formatBenefitCoverage } from "@/lib/benefit-utils";
import {
  formatTitleCaseInsurerName,
  getCompanyInitials,
  getCompanyLogoPath,
} from "@/lib/company-logos";
import { formatLlpLlop, formatMoneyWithRounding, isLlpLlopIncluded } from "../types";
import type { ComparisonEntry, RoundingMode, TenureSpec } from "../types";

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
  roundingMode?: RoundingMode;
}

const MONTHS_SHORT = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

function formatDateDDMMMYYYY(d: Date): string {
  const day = String(d.getDate()).padStart(2, "0");
  const month = MONTHS_SHORT[d.getMonth()] ?? "Jan";
  return `${day} ${month} ${d.getFullYear()}`;
}

function formatTime12h(d: Date): string {
  const hours24 = d.getHours();
  const minutes = String(d.getMinutes()).padStart(2, "0");
  const suffix = hours24 >= 12 ? "pm" : "am";
  const hours12 = hours24 % 12 || 12;
  return `${hours12}:${minutes} ${suffix}`;
}

function formatSingleDateToken(token: string): string | null {
  const trimmed = token.trim();
  const dmy = trimmed.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/);
  if (dmy) {
    const day = Number(dmy[1]);
    const monthIdx = Number(dmy[2]) - 1;
    const year = Number(dmy[3]);
    if (monthIdx >= 0 && monthIdx < 12 && day >= 1 && day <= 31) {
      return `${String(day).padStart(2, "0")} ${MONTHS_SHORT[monthIdx]} ${year}`;
    }
  }
  const iso = trimmed.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:T.*)?$/);
  if (iso) {
    const year = Number(iso[1]);
    const monthIdx = Number(iso[2]) - 1;
    const day = Number(iso[3]);
    if (monthIdx >= 0 && monthIdx < 12 && day >= 1 && day <= 31) {
      return `${String(day).padStart(2, "0")} ${MONTHS_SHORT[monthIdx]} ${year}`;
    }
  }
  return null;
}

function formatCoveragePeriodLong(raw: string): string {
  if (!raw || raw === "—") return "—";
  const parts = raw.split(/\s+(?:-|to)\s+/i);
  if (parts.length === 2) {
    const start = formatSingleDateToken(parts[0]);
    const end = formatSingleDateToken(parts[1]);
    if (start && end) {
      return `${start} - ${end}`;
    }
  }
  return raw;
}

function formatVehicleSummary(tenure: TenureSpec): string {
  const brand = (tenure.car_brand || "").trim();
  const model = (tenure.vehicle_model || "").trim();
  const cc = (tenure.engine_cc || "").trim();

  let modelPart = model;
  if (brand && modelPart) {
    if (!modelPart.toLowerCase().startsWith(brand.toLowerCase())) {
      modelPart = `${brand} ${modelPart}`;
    }
  } else if (brand && !modelPart) {
    modelPart = brand;
  }

  return [modelPart, cc].filter(Boolean).join(" · ") || "Motor Vehicle";
}

function formatSnapshotTowing(raw: string): string {
  const trimmed = (raw || "").trim();
  if (!trimmed) return "Standard";
  if (/^unlimited/i.test(trimmed)) return "Unlimited";
  return trimmed
    .replace(/^RM\s+/i, "MYR ")
    .replace(/\s+km$/i, " KM");
}

function isFloodPerilsCovered(val?: string | null): boolean {
  if (!val) return false;
  const normalized = val.trim().toLowerCase();
  return !["0", "none", "not included", "not covered", "nil", "no", "-", "—", "tiada", "tidak termasuk"].includes(
    normalized
  );
}

function resolveCardRef(card: ComparisonEntry): string {
  if (card.source_quotation_no) return card.source_quotation_no;
  if (card.quotation_ref && !card.quotation_ref.startsWith("RL")) return card.quotation_ref;
  if (card.notes) return card.notes;
  if (card.session_id) return card.session_id.slice(0, 8).toUpperCase();
  return "N/A";
}

function resolveHeaderVehicleField(tenure: TenureSpec): { label: string; value: string } {
  const isUndetected = Boolean(tenure.is_plate_undetected || !tenure.vehicle_no || tenure.vehicle_no === "N/A");
  if (isUndetected) {
    if (tenure.chassis_no) {
      return { label: "Chassis No :", value: tenure.chassis_no.toUpperCase() };
    }
    return { label: "Vehicle No :", value: "Unregistered Vehicle" };
  }
  return { label: "Vehicle No :", value: tenure.vehicle_no.toUpperCase() };
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
  roundingMode = "exact",
}: SnapshotPreviewModalProps) {
  const [failedLogos, setFailedLogos] = useState<Record<string, boolean>>({});
  const [generatedAt, setGeneratedAt] = useState<Date>(() => new Date());

  useEffect(() => {
    if (isOpen) {
      setGeneratedAt(new Date());
      setFailedLogos({});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const cardCount = snapshotVisibleCards.length;
  const isCompact = cardCount >= 3;
  const isFourCol = cardCount === 4;

  const canvasWidth =
    cardCount <= 1
      ? "880px"
      : cardCount === 2
        ? "1024px"
        : cardCount === 4
          ? "1280px"
          : "1160px";

  const gridColsClass =
    cardCount <= 1
      ? "grid-cols-1 max-w-[460px] mx-auto"
      : cardCount === 2
        ? "grid-cols-2 gap-5"
        : cardCount === 4
          ? "grid-cols-4 gap-3.5"
          : "grid-cols-3 gap-4";

  const headerVehicle = resolveHeaderVehicleField(tenure);
  const fixedCostsDisplay = (tenure.fixed_costs_total ?? 0).toLocaleString("en-MY", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto no-print">
      <div className="bg-white rounded-3xl shadow-2xl border border-neutral-200 max-w-[96vw] w-full flex flex-col max-h-[94vh] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Modal Control Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#e5e5ea] bg-[#f5f5f7] shrink-0">
          <div>
            <h3 className="text-base font-bold text-[#1b1717] flex items-center gap-2">
              <Camera size={20} weight="fill" className="text-[#1b1717]" />
              Executive Comparison Snapshot Grid
            </h3>
            <p className="text-xs text-[#6e6e73]">
              High-resolution snapshot of {cardCount} ranked underwriter option{cardCount !== 1 ? "s" : ""}
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

        {/* Modal Body: Scrollable Canvas Container */}
        <div className="flex-1 overflow-auto p-6 bg-neutral-100 flex items-start">
          <div className="mx-auto rounded-xl overflow-hidden shadow-2xl border border-neutral-200 shrink-0 bg-white">
            {/* Full-Bleed Export Target for html-to-image */}
            <div
              ref={gridRef}
              className="bg-white text-[#111827] overflow-hidden"
              style={{
                width: canvasWidth,
                fontFamily: "var(--font-inter), Inter, system-ui, -apple-system, sans-serif",
              }}
            >
              {/* Top Brand & Title Header */}
              <div className="px-10 pt-8 pb-4 flex items-start justify-between gap-6">
                <div className="pt-0.5 shrink-0">
                  <img
                    src="/assets/brand/logo-horizontal-black.png"
                    alt="Risk Locker"
                    loading="eager"
                    style={{ height: "44px", width: "auto", objectFit: "contain", display: "block" }}
                  />
                </div>

                <div className="text-right">
                  <h2
                    className="font-bold tracking-tight"
                    style={{ fontSize: "27px", lineHeight: 1.15, letterSpacing: "-0.02em" }}
                  >
                    <span style={{ color: "#43464B" }}>Motor Quotation </span>
                    <span style={{ color: "#D61B22" }}>Comparison</span>
                  </h2>

                  <div className="flex items-baseline justify-end gap-3 mt-1.5">
                    <span className="font-medium" style={{ fontSize: "16px", color: "#7A7D85" }}>
                      {headerVehicle.label}
                    </span>
                    <span
                      className="font-extrabold tracking-wide"
                      style={{ fontSize: "18px", color: "#111827" }}
                    >
                      {headerVehicle.value}
                    </span>
                  </div>
                </div>
              </div>

              {/* Metadata, Contact QR & Timestamp Row */}
              <div className="px-10 pb-5 flex items-end justify-between gap-6">
                <div className="min-w-0">
                  <p
                    className="font-extrabold uppercase tracking-tight mb-2"
                    style={{ fontSize: "18px", color: "#111827", lineHeight: 1.2 }}
                  >
                    {(tenure.customer_name || "VALUED CUSTOMER").toUpperCase()}
                  </p>

                  <div className="text-[13px] leading-[1.45] space-y-0.5">
                    <div className="flex items-baseline gap-1.5">
                      <span style={{ color: "#6B7280" }}>Vehicle :</span>
                      <span className="font-bold" style={{ color: "#111827" }}>
                        {formatVehicleSummary(tenure)}
                      </span>
                    </div>

                    <div className="flex items-baseline gap-1.5">
                      <span style={{ color: "#6B7280" }}>Roadtax &amp; Runner Fee :</span>
                      <span className="font-bold tabular-nums" style={{ color: "#111827" }}>
                        MYR {fixedCostsDisplay}
                      </span>
                    </div>

                    {(tenure.motor_discount_pct ?? 0) > 0 && (
                      <div className="flex items-baseline gap-1.5 font-semibold" style={{ color: "#15803D" }}>
                        <span>Motor Insurance Discount :</span>
                        <span className="font-bold tabular-nums">
                          -{(tenure.motor_discount_pct ?? 0) % 1 === 0
                            ? (tenure.motor_discount_pct ?? 0).toFixed(0)
                            : tenure.motor_discount_pct}%
                        </span>
                      </div>
                    )}

                    {(tenure.quotation_discount ?? 0) > 0 && (
                      <div className="flex items-baseline gap-1.5 font-semibold" style={{ color: "#15803D" }}>
                        <span>Quotation Discount :</span>
                        <span className="font-bold tabular-nums">
                          - MYR{" "}
                          {(tenure.quotation_discount ?? 0).toLocaleString("en-MY", {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </span>
                      </div>
                    )}

                    <div className="flex items-baseline gap-1.5">
                      <span style={{ color: "#6B7280" }}>Coverage Period :</span>
                      <span className="font-bold" style={{ color: "#111827" }}>
                        {formatCoveragePeriodLong(activeWinnerPeriod)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-10 shrink-0">
                  {/* Dark Contact QR */}
                  <div className="flex items-center gap-3">
                    <img
                      src="/assets/whatsapp_qr_dark.png"
                      alt="Contact Us QR"
                      loading="eager"
                      style={{
                        width: "62px",
                        height: "62px",
                        objectFit: "contain",
                        display: "block",
                        flexShrink: 0,
                      }}
                    />
                    <div className="text-[11px] font-semibold leading-[1.3]" style={{ color: "#374151" }}>
                      <div>Contact Us For</div>
                      <div>More Information</div>
                    </div>
                  </div>

                  {/* Generated Timestamp */}
                  <div className="min-w-[155px] text-[12px] leading-[1.45]">
                    <div className="italic text-right mb-1" style={{ color: "#8A8E96" }}>
                      Generated on
                    </div>
                    <div className="flex items-baseline justify-between gap-4">
                      <span style={{ color: "#6B7280" }}>Date :</span>
                      <span className="font-bold tabular-nums" style={{ color: "#111827" }}>
                        {formatDateDDMMMYYYY(generatedAt)}
                      </span>
                    </div>
                    <div className="flex items-baseline justify-between gap-4">
                      <span style={{ color: "#6B7280" }}>Time :</span>
                      <span className="font-bold tabular-nums" style={{ color: "#111827" }}>
                        {formatTime12h(generatedAt)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Divider */}
              <div className="mx-10 border-t border-[#E5E7EB]" />

              {/* Insurer Comparison Cards Grid */}
              <div className="px-10 pt-6 pb-2">
                <div className={`grid ${gridColsClass}`}>
                  {snapshotVisibleCards.map((card, idx) => {
                    const rankNum = visibleRanksMap[card.id] || card.rank || idx + 1;
                    const isTopRank = rankNum === 1;
                    const logoPath = getCompanyLogoPath(card.company_name);
                    const logoKey = `${card.id}:${logoPath ?? ""}`;
                    const showLogo = Boolean(logoPath && !failedLogos[logoKey]);
                    const displayInsurer = formatTitleCaseInsurerName(card.company_name);

                    const grossTotal =
                      roundingMode === "whole"
                        ? (card.whole_total_payable ?? card.exact_total_payable ?? card.total_payable)
                        : roundingMode === "5cent" || roundingMode === "bnm5"
                          ? (card.bnm_5cent_total_payable ?? card.exact_total_payable ?? card.total_payable)
                          : (card.exact_total_payable ?? card.total_payable);

                    const effectiveDiscount = card.effective_discount ?? tenure.quotation_discount ?? 0;

                    const netTotal =
                      roundingMode === "whole"
                        ? (card.whole_net_total_payable ?? card.net_total_payable ?? grossTotal)
                        : roundingMode === "5cent" || roundingMode === "bnm5"
                          ? (card.bnm_5cent_net_total_payable ?? card.net_total_payable ?? grossTotal)
                          : (card.net_total_payable ?? grossTotal);

                    const ncdValue =
                      card.ncd_percentage ??
                      ncdData?.next ??
                      tenure.ncd_percentage ??
                      ncdData?.current ??
                      0;

                    const floodCovered = isFloodPerilsCovered(card.special_perils);
                    const llpIncluded = isLlpLlopIncluded(card.llp_llop);
                    const llpLabel = formatLlpLlop(card.llp_llop);
                    const rawTowing = formatBenefitCoverage(
                      card.towing_limit || card.towing_km || "Standard",
                      undefined,
                      card.company_name
                    );
                    const towingLabel = formatSnapshotTowing(rawTowing || "Standard");
                    const isUnlimitedTowing = /^unlimited/i.test(towingLabel);
                    const isNoTowing = towingLabel === "No Towing";

                    return (
                      <div
                        key={card.id}
                        className="bg-[#F6F7F9] flex flex-col justify-between overflow-hidden rounded-[4px]"
                      >
                        <div
                          className={
                            isFourCol
                              ? "px-4 pt-4 pb-5"
                              : isCompact
                                ? "px-5 pt-5 pb-6"
                                : "px-7 pt-6 pb-7"
                          }
                        >
                          {/* Card Header: Logo Left, Rank + Ref + Name Right */}
                          <div className="flex items-start justify-between gap-3 mb-4">
                            <div className="shrink-0 flex items-center">
                              {showLogo ? (
                                <img
                                  src={logoPath!}
                                  alt={displayInsurer}
                                  loading="eager"
                                  onError={() =>
                                    setFailedLogos((prev) => ({ ...prev, [logoKey]: true }))
                                  }
                                  style={{
                                    height: isFourCol ? "38px" : isCompact ? "44px" : "56px",
                                    maxWidth: isFourCol ? "86px" : isCompact ? "104px" : "136px",
                                    objectFit: "contain",
                                    objectPosition: "left center",
                                    mixBlendMode: "multiply",
                                    display: "block",
                                  }}
                                />
                              ) : (
                                <div
                                  className="rounded-xl bg-white border border-[#E5E7EB] flex items-center justify-center font-extrabold tracking-tight text-[#374151]"
                                  style={{
                                    width: isFourCol ? "42px" : isCompact ? "48px" : "56px",
                                    height: isFourCol ? "42px" : isCompact ? "48px" : "56px",
                                    fontSize: isFourCol ? "14px" : "17px",
                                  }}
                                >
                                  {getCompanyInitials(card.company_name)}
                                </div>
                              )}
                            </div>

                            <div className="text-right flex flex-col items-end min-w-0">
                              <span
                                className={`rounded-[7px] font-bold leading-none whitespace-nowrap ${isTopRank
                                  ? "bg-[#73B83F] text-white"
                                  : "bg-[#E4E6EA] text-[#1F2937]"
                                  } ${isCompact ? "px-2.5 py-1 text-[13px]" : "px-3.5 py-1.5 text-[15px]"}`}
                              >
                                {`Rank#${rankNum}`}
                              </span>

                              <span
                                className={`mt-2 leading-tight truncate max-w-full ${isCompact ? "text-[10px]" : "text-[11.5px]"
                                  }`}
                                style={{ color: "#6B7280" }}
                              >
                                {`Ref : ${resolveCardRef(card)}`}
                              </span>

                              <h4
                                className={`mt-1 font-bold leading-tight truncate max-w-full ${isFourCol
                                  ? "text-[14.5px]"
                                  : isCompact
                                    ? "text-[16px]"
                                    : "text-[19px]"
                                  }`}
                                style={{ color: "#111827" }}
                                title={card.company_name}
                              >
                                {displayInsurer}
                              </h4>
                            </div>
                          </div>

                          {/* White Price Highlight Box */}
                          <div
                            className={`bg-white rounded-[16px] ${isCompact ? "px-3 py-2.5 mb-5" : "px-4 py-3 mb-6"
                              }`}
                            style={{
                              border: isTopRank ? "1.5px solid #B81D2B" : "1px solid #C6CAD1",
                            }}
                          >
                            <div className="flex items-baseline justify-between gap-2 pb-2.5 border-b border-[#E5E7EB]">
                              <span
                                className={`font-bold ${isCompact ? "text-[12px]" : "text-[13px]"}`}
                                style={{ color: "#111827" }}
                              >
                                Sum Insured:
                              </span>
                              <span
                                className={`font-extrabold tabular-nums whitespace-nowrap ${isCompact ? "text-[13px]" : "text-[14.5px]"
                                  }`}
                                style={{ color: "#111827" }}
                              >
                                MYR{" "}
                                {card.sum_insured.toLocaleString("en-MY", {
                                  minimumFractionDigits: 2,
                                  maximumFractionDigits: 2,
                                })}
                              </span>
                            </div>

                            {effectiveDiscount > 0 ? (
                              <div className="pt-2.5 space-y-1">
                                <div
                                  className={`flex items-baseline justify-between gap-2 ${isCompact ? "text-[11px]" : "text-[12px]"
                                    }`}
                                  style={{ color: "#6B7280" }}
                                >
                                  <span>Total Payable:</span>
                                  <span className="font-medium line-through tabular-nums whitespace-nowrap">
                                    MYR {formatMoneyWithRounding(grossTotal, roundingMode)}
                                  </span>
                                </div>

                                <div
                                  className={`flex items-baseline justify-between gap-2 ${isCompact ? "text-[11px]" : "text-[12px]"
                                    }`}
                                  style={{ color: "#15803D" }}
                                >
                                  <span className="font-medium">
                                    {(card.motor_discount_pct ?? tenure.motor_discount_pct ?? 0) > 0
                                      ? `Motor Disc (${Number(
                                        card.motor_discount_pct ?? tenure.motor_discount_pct
                                      )}%):`
                                      : "Discount:"}
                                  </span>
                                  <span className="font-bold tabular-nums whitespace-nowrap">
                                    - MYR{" "}
                                    {effectiveDiscount.toLocaleString("en-MY", {
                                      minimumFractionDigits: 2,
                                      maximumFractionDigits: 2,
                                    })}
                                  </span>
                                </div>

                                <div className="pt-1 border-t border-[#E5E7EB] flex items-baseline justify-between gap-2">
                                  <span
                                    className={`font-bold ${isCompact ? "text-[13.5px]" : "text-[16px]"}`}
                                    style={{ color: "#111827" }}
                                  >
                                    Net Payable:
                                  </span>
                                  <span
                                    className={`font-extrabold tabular-nums whitespace-nowrap ${isFourCol
                                      ? "text-[16px]"
                                      : isCompact
                                        ? "text-[18px]"
                                        : "text-[22px]"
                                      }`}
                                    style={{ color: isTopRank ? "#6EB337" : "#111827" }}
                                  >
                                    MYR {formatMoneyWithRounding(netTotal, roundingMode)}
                                  </span>
                                </div>
                              </div>
                            ) : (
                              <div className="pt-2.5 flex items-baseline justify-between gap-2">
                                <span
                                  className={`font-bold ${isFourCol
                                    ? "text-[13.5px]"
                                    : isCompact
                                      ? "text-[15px]"
                                      : "text-[18px]"
                                    }`}
                                  style={{ color: "#111827" }}
                                >
                                  Total Payable:
                                </span>
                                <span
                                  className={`font-extrabold tabular-nums whitespace-nowrap ${isFourCol
                                    ? "text-[16px]"
                                    : isCompact
                                      ? "text-[18px]"
                                      : "text-[22px]"
                                    }`}
                                  style={{ color: isTopRank ? "#6EB337" : "#111827" }}
                                >
                                  MYR {formatMoneyWithRounding(grossTotal, roundingMode)}
                                </span>
                              </div>
                            )}
                          </div>

                          {/* 7 Specification Rows */}
                          <div
                            className={`px-1.5 space-y-2.5 ${isFourCol
                              ? "text-[11.5px]"
                              : isCompact
                                ? "text-[12.5px]"
                                : "text-[14px]"
                              }`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span style={{ color: "#6B7280" }}>Valuation:</span>
                              <span className="font-bold text-right" style={{ color: "#4B4F56" }}>
                                {card.valuation_type === "agreed_value" ? "Agreed Value" : "Market Value"}
                              </span>
                            </div>

                            <div className="flex items-center justify-between gap-2">
                              <span style={{ color: "#6B7280" }}>NCD:</span>
                              <span
                                className="font-bold tabular-nums text-right"
                                style={{ color: "#4B4F56" }}
                              >
                                {ncdValue}%
                              </span>
                            </div>

                            <div className="flex items-center justify-between gap-2">
                              <span style={{ color: "#6B7280" }}>Windscreen:</span>
                              <span
                                className="font-bold tabular-nums text-right"
                                style={{
                                  color:
                                    card.windscreen_sum_insured && card.windscreen_sum_insured > 0
                                      ? "#4B4F56"
                                      : "#9CA3AF",
                                }}
                              >
                                {card.windscreen_sum_insured && card.windscreen_sum_insured > 0
                                  ? `MYR ${card.windscreen_sum_insured.toLocaleString("en-MY")}`
                                  : "None"}
                              </span>
                            </div>

                            <div className="flex items-center justify-between gap-2">
                              <span style={{ color: "#6B7280" }}>Flood/Perils:</span>
                              <span
                                className={`text-right ${floodCovered ? "font-bold" : "font-semibold"}`}
                                style={{ color: floodCovered ? "#6BB235" : "#9CA3AF" }}
                              >
                                {floodCovered ? "Covered" : "Not Included"}
                              </span>
                            </div>

                            <div className="flex items-center justify-between gap-2">
                              <span style={{ color: "#6B7280" }}>Betterment:</span>
                              <span className="font-bold text-right" style={{ color: "#4B4F56" }}>
                                {card.betterment_display || (card.waiver_betterment ? "No (0%)" : "Yes")}
                              </span>
                            </div>

                            <div className="flex items-center justify-between gap-2">
                              <span style={{ color: "#6B7280" }}>LLP/LLOP:</span>
                              <span
                                className={`text-right ${llpIncluded ? "font-bold" : "font-semibold"}`}
                                style={{ color: llpIncluded ? "#4B4F56" : "#9CA3AF" }}
                              >
                                {llpLabel}
                              </span>
                            </div>

                            <div className="flex items-center justify-between gap-2">
                              <span style={{ color: "#6B7280" }}>Towing Limit:</span>
                              <span
                                className={`text-right ${isNoTowing ? "font-semibold" : "font-bold"}`}
                                style={{
                                  color: isUnlimitedTowing
                                    ? "#6BB235"
                                    : isNoTowing
                                      ? "#9CA3AF"
                                      : "#4B4F56",
                                }}
                              >
                                {towingLabel}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Bottom Accent Bar (Top Rank Only) */}
                        <div
                          style={{
                            height: "7px",
                            width: "100%",
                            backgroundColor: isTopRank ? "#55585D" : "transparent",
                          }}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Tagline */}
              <div className="py-5 text-center">
                <p
                  style={{
                    fontFamily: 'Georgia, "Times New Roman", Times, serif',
                    fontVariant: "small-caps",
                    fontSize: "19px",
                    letterSpacing: "0.06em",
                    color: "#3A3D42",
                    margin: 0,
                  }}
                >
                  Your Shield Against The Unexpected
                </p>
              </div>

              {/* Full-Bleed Red Footer Banner */}
              <div
                className="h-[46px] px-10 flex items-center justify-between"
                style={{ backgroundColor: "#DC1422", color: "#FFFFFF" }}
              >
                <div className="flex items-center gap-2.5 text-[14.5px] font-bold tracking-[0.03em]">
                  <span>CONFIDENTIAL</span>
                  <span className="opacity-85">|</span>
                  <span>RISKLOCKER SDN.BHD.</span>
                </div>

                <div className="flex items-center gap-9 text-[12.5px] font-medium">
                  <div className="flex items-center gap-2.5">
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                      aria-hidden="true"
                      style={{ flexShrink: 0 }}
                    >
                      <path d="M4 21h16v-2h-1V9h-5V4H5v15H4v2zm3-15h5v13H7V6zm7 5h3v8h-3v-8zM9 8h1.5v2H9V8zm0 3.5h1.5v2H9v-2zm0 3.5h1.5v2H9v-2z" />
                    </svg>
                    <span>011 1011 6880 ( Office )</span>
                  </div>

                  <div className="flex items-center gap-2.5">
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                      aria-hidden="true"
                      style={{ flexShrink: 0 }}
                    >
                      <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
                    </svg>
                    <span>admin@risklocker.com</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
