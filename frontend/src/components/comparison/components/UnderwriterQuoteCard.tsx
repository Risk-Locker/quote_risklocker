"use client";

import React from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  Star,
  ShieldCheck,
  Eye,
  EyeSlash,
  FilePdf,
  ArrowsClockwise,
  PencilSimple,
  CheckCircle,
  Trash,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { formatShortInsurerName, formatBenefitCoverage } from "@/lib/benefit-utils";
import { formatLlpLlop, isLlpLlopIncluded } from "../types";
import type { ComparisonEntry, TenureSpec } from "../types";

export interface UnderwriterQuoteCardProps {
  entry: ComparisonEntry;
  group: {
    companyName: string;
    companyId: string | null;
    entries: ComparisonEntry[];
    hasWinner: boolean;
  };
  activeIds: string[];
  isViewingPdf: boolean;
  visibleRanksMap: Record<string, number>;
  visibleDisplayEntriesCount: number;
  editingRankEntryId: string | null;
  tenure: TenureSpec;
  selectingWinnerId: string | null;
  promotingEntryId: string | null;
  rescanningQuoteId: string | null;
  isRescanning: boolean;
  onToggleHideEntry: (entry: ComparisonEntry) => void;
  onSetManualRank: (entry: ComparisonEntry, rank: number) => void;
  onSetEditingRankEntryId: (id: string | null) => void;
  onSelectActiveVersion: (companyName: string, id: string) => void;
  onViewPdf: (session: { sessionId: string; companyName: string }) => void;
  onRescanQuote: (entry: ComparisonEntry) => void;
  onSelectWinner: (id: string) => void;
  onEditEntry: (entry: ComparisonEntry) => void;
  onPromoteToCovernote: (entry: ComparisonEntry) => void;
  onDeleteEntry: (id: string, deleteCompany: boolean) => void;
}

export function UnderwriterQuoteCard({
  entry,
  group,
  activeIds,
  isViewingPdf,
  visibleRanksMap,
  visibleDisplayEntriesCount,
  editingRankEntryId,
  tenure,
  selectingWinnerId,
  promotingEntryId,
  rescanningQuoteId,
  isRescanning,
  onToggleHideEntry,
  onSetManualRank,
  onSetEditingRankEntryId,
  onSelectActiveVersion,
  onViewPdf,
  onRescanQuote,
  onSelectWinner,
  onEditEntry,
  onPromoteToCovernote,
  onDeleteEntry,
}: UnderwriterQuoteCardProps) {
  const isWinner = entry.is_recommended;

  return (
    <div
      key={entry.id}
      className={`w-[275px] shrink-0 rounded-2xl bg-white flex flex-col justify-between transition-all duration-200 relative break-inside-avoid print:w-auto print:flex-1 print:min-w-[200px] ${
        isViewingPdf
          ? "border-2 border-[#1b1717] ring-4 ring-[#1b1717]/15 shadow-xl scale-[1.01]"
          : isWinner
          ? "border-2 border-[#1b1717] shadow-lg ring-1 ring-black/5"
          : "border border-[#e5e5ea] shadow-xs hover:border-neutral-400"
      }`}
    >
      {/* Equal Height Standardized Top Slot (h-8) for Perfect Grid Row Alignment */}
      {isWinner ? (
        <div className="h-8 bg-[#1b1717] text-white text-xs font-bold px-3 flex items-center justify-between rounded-t-xl shrink-0 print:bg-black print:text-white">
          <span className="flex items-center gap-1.5">
            <Star weight="fill" size={13} className="text-amber-400" />
            RECOMMENDED WINNER
          </span>
          <ShieldCheck size={15} weight="bold" />
        </div>
      ) : (
        <div className="h-8 bg-[#f5f5f7]/80 text-[#6e6e73] px-3 flex items-center justify-between rounded-t-xl shrink-0 border-b border-[#e5e5ea]/60">
          <span className="text-[11px] font-semibold text-neutral-600">Quotation Option</span>
          <span className="text-[10px] text-neutral-400 font-mono">Rank #{visibleRanksMap[entry.id] ?? entry.rank ?? 1}</span>
        </div>
      )}

      <div>
        {/* 4-Row Card Header */}
        <div className={`p-4 border-b ${isWinner ? "border-[#e5e5ea] bg-[#f5f5f7]/60" : "border-[#e5e5ea]"}`}>
          {/* Row 1: Company Name + Visibility Toggle */}
          <div className="flex items-center justify-between gap-2 h-7">
            <h3 className="font-bold text-sm text-[#1b1717] uppercase tracking-tight truncate whitespace-nowrap" title={entry.company_name}>
              {formatShortInsurerName(entry.company_name)}
            </h3>
            <div className="flex items-center gap-1 shrink-0">
              {isViewingPdf && (
                <span className="rounded bg-[#1b1717] text-white px-1.5 py-0.2 text-[9px] font-bold">
                  PDF ★
                </span>
              )}
              <button
                type="button"
                onClick={() => onToggleHideEntry(entry)}
                className={`p-1 rounded text-neutral-400 hover:text-[#1b1717] hover:bg-neutral-100 transition-colors cursor-pointer ${
                  entry.is_hidden ? "text-neutral-400 bg-neutral-100" : ""
                }`}
                title={entry.is_hidden ? "Unhide this quotation card" : "Hide this card from comparison & snapshot"}
              >
                {entry.is_hidden ? <EyeSlash size={15} weight="bold" /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {/* Row 2: Rank badge with clean highlight & instant click-to-rank picker */}
          <div className="mt-2 min-h-[26px] flex items-center justify-between gap-1">
            {editingRankEntryId === entry.id && visibleDisplayEntriesCount > 1 ? (
              <div className="flex items-center gap-1 flex-wrap py-0.5">
                <span className="text-[10px] text-[#6e6e73] font-bold mr-0.5">Rank:</span>
                {Array.from({ length: visibleDisplayEntriesCount }, (_, i) => i + 1).map((num) => {
                  const currentRank = visibleRanksMap[entry.id] ?? 1;
                  return (
                    <button
                      key={num}
                      type="button"
                      onClick={() => {
                        onSetManualRank(entry, num);
                        onSetEditingRankEntryId(null);
                      }}
                      className={`w-6 h-6 flex items-center justify-center text-[11px] font-bold rounded border cursor-pointer transition-colors ${
                        currentRank === num
                          ? "bg-[#1b1717] text-white border-[#1b1717] font-black"
                          : "bg-white text-[#454545] border-[#e5e5ea] hover:bg-neutral-100"
                      }`}
                    >
                      {num}
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => onSetEditingRankEntryId(null)}
                  className="text-[11px] text-[#6e6e73] hover:text-[#1b1717] ml-1 cursor-pointer font-bold px-1"
                  title="Close"
                >
                  ✕
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-1.5">
                {(() => {
                  const r = visibleRanksMap[entry.id] ?? 1;
                  const canEdit = visibleDisplayEntriesCount > 1;
                  return (
                    <button
                      type="button"
                      disabled={!canEdit}
                      onClick={() => canEdit && onSetEditingRankEntryId(entry.id)}
                      className={`rounded font-bold px-2 py-0.5 text-[11px] transition-colors ${
                        r === 1
                          ? "bg-amber-100 text-amber-950 border border-amber-300"
                          : "bg-neutral-100 text-neutral-800 border border-neutral-300"
                      } ${canEdit ? "hover:bg-amber-200 cursor-pointer" : "cursor-default"}`}
                      title={canEdit ? "Click to change rank" : "Only 1 quotation visible"}
                    >
                      Rank #{r}
                    </button>
                  );
                })()}
                {entry.manual_rank != null && (
                  <span className="text-[9px] text-[#8e8e93] font-semibold">(Manual)</span>
                )}
                {isWinner && (
                  <span className="text-[9px] font-bold text-amber-700 bg-amber-50 px-1.5 py-0.2 rounded border border-amber-200">
                    Winner ★
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Row 3: Dedicated Version Row with Clean Inline Switcher */}
          <div className="mt-2 min-h-[28px] flex items-center justify-between gap-1.5">
            {group.entries.length > 1 ? (
              <div className="flex items-center gap-1 p-0.5 bg-neutral-100 rounded-lg border border-neutral-200">
                {[...group.entries]
                  .sort((a, b) => (a.version || 0) - (b.version || 0))
                  .map((q) => {
                    const isThisSelected = q.id === entry.id;
                    const maxVer = Math.max(...group.entries.map((x) => x.version || 1));
                    const isLatest = (q.version || 1) === maxVer;
                    return (
                      <button
                        key={q.id}
                        type="button"
                        onClick={() => onSelectActiveVersion(group.companyName, q.id)}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all flex items-center gap-1 cursor-pointer shrink-0 ${
                          isThisSelected
                            ? "bg-[#1b1717] text-white shadow-xs"
                            : "text-neutral-600 hover:text-neutral-900 hover:bg-neutral-200/60"
                        }`}
                        title={`v${q.version || 1} • RM ${(q.rounded_total_payable != null ? q.rounded_total_payable : Math.round(q.total_payable)).toFixed(2)}${isLatest ? " (Latest)" : ""}`}
                      >
                        <span>v{q.version || 1}</span>
                        {isLatest && <span className="text-[9px] opacity-75 font-normal">Latest</span>}
                        {q.is_recommended && (
                          <Star
                            weight="fill"
                            size={10}
                            className={isThisSelected ? "text-amber-300" : "text-amber-500"}
                          />
                        )}
                      </button>
                    );
                  })}
              </div>
            ) : (
              <span className="text-[10px] font-semibold text-neutral-500 bg-neutral-100 px-2 py-0.5 rounded border border-neutral-200">
                v{entry.version || 1} (Latest)
              </span>
            )}
            <span className="text-[10px] text-neutral-400 font-mono">
              {entry.is_manual ? "Portal" : "PDF"}
            </span>
          </div>

          {/* Row 4: Valuation & Quotation Reference */}
          <div className="mt-2 pt-1 border-t border-[#e5e5ea]/80 flex items-center justify-between gap-1.5 min-h-[22px]">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-xs text-[#6e6e73] font-medium">
                {entry.valuation_type === "agreed_value" ? "Agreed Value" : "Market Value"}
              </span>
              <span className="font-mono text-[10px] text-[#8e8e93]">
                {entry.valuation_type === "agreed_value" ? "[A]" : "[M]"}
              </span>
            </div>
            <span
              className="font-mono text-[10px] text-[#6e6e73] truncate max-w-[130px] shrink-0"
              title={entry.source_quotation_no || entry.quotation_ref || undefined}
            >
              Ref: {entry.source_quotation_no || entry.quotation_ref || "—"}
            </span>
          </div>

          {/* Row 5: Policy Period */}
          <div className="mt-2 pt-1.5 border-t border-[#e5e5ea]/80 flex items-center justify-between text-[11px] min-h-[26px]">
            <span className="text-[#6e6e73] font-medium flex items-center gap-1">
              {isWinner && <Star size={11} weight="fill" className="text-amber-500" />}
              {isWinner ? "Winner Period:" : "Period:"}
            </span>
            <span className={`font-mono ${isWinner ? "font-bold text-neutral-900" : "text-neutral-800 font-medium"}`}>
              {entry.coverage_period_formatted || tenure.coverage_period_formatted}
            </span>
          </div>
        </div>

        {/* Numeric Figures Card with Exact Locked Heights */}
        <div className="p-4 space-y-3.5 border-b border-[#e5e5ea]">
          <div className="h-[48px] flex flex-col justify-center">
            <span className="text-[11px] uppercase font-bold text-[#6e6e73] block mb-0.5">
              Sum Insured
            </span>
            <div className="flex items-baseline gap-1.5">
              <p className="font-mono text-base font-bold text-[#1b1717]">
                RM {entry.sum_insured.toLocaleString("en-MY", { minimumFractionDigits: 2 })}
              </p>
              <span className="text-xs text-[#6e6e73]">
                {entry.valuation_type === "agreed_value" ? "[A]" : "[M]"}
              </span>
            </div>
          </div>

          <div className="h-[44px] flex flex-col justify-center">
            <span className="text-[11px] uppercase font-bold text-[#6e6e73] block mb-0.5">
              Motor Premium
            </span>
            <p
              className="font-mono text-sm font-bold text-[#1b1717]"
              title={
                entry.exact_motor_premium && (entry.rounded_motor_premium ?? Math.round(entry.motor_premium)) !== entry.exact_motor_premium
                  ? `Exact cents: RM ${entry.exact_motor_premium.toFixed(2)}`
                  : undefined
              }
            >
              RM {(entry.rounded_motor_premium != null ? entry.rounded_motor_premium : Math.round(entry.motor_premium)).toFixed(2)}
            </p>
          </div>

          {/* Total Payable Box */}
          <div
            className={`rounded-xl p-3.5 border transition-colors h-[92px] flex flex-col justify-between ${
              isWinner
                ? "border-2 border-[#1b1717] bg-[#f5f5f7]"
                : "border border-[#e5e5ea] bg-[#f5f5f7]/80"
            }`}
          >
            <span className="text-[11px] uppercase font-bold text-[#454545] block">
              Total Payable
            </span>
            {((entry.effective_discount ?? tenure.quotation_discount ?? 0) > 0) ? (
              <div>
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-xs text-neutral-400 line-through font-mono">
                    RM {(entry.rounded_total_payable != null ? entry.rounded_total_payable : (Math.round(entry.motor_premium) + tenure.fixed_costs_total)).toFixed(2)}
                  </span>
                  <span className="bg-emerald-50 text-emerald-800 text-[10px] font-bold px-1.5 py-0.5 rounded border border-emerald-300">
                    - RM {(entry.effective_discount ?? tenure.quotation_discount ?? 0).toFixed(2)}
                  </span>
                </div>
                <p
                  className="font-mono text-lg font-black text-emerald-700"
                  title={
                    entry.net_total_payable && entry.rounded_net_total_payable && entry.rounded_net_total_payable !== entry.net_total_payable
                      ? `Exact cents: RM ${entry.net_total_payable.toFixed(2)}`
                      : undefined
                  }
                >
                  RM {(entry.rounded_net_total_payable != null ? entry.rounded_net_total_payable : Math.max(0, (entry.rounded_total_payable ?? Math.round(entry.total_payable)) - Math.round(entry.effective_discount ?? tenure.quotation_discount ?? 0))).toFixed(2)}
                </p>
              </div>
            ) : (
              <p
                className="font-mono text-lg font-black text-[#1b1717]"
                title={
                  entry.exact_total_payable && (entry.rounded_total_payable ?? Math.round(entry.total_payable)) !== entry.exact_total_payable
                    ? `Exact cents: RM ${entry.exact_total_payable.toFixed(2)}`
                    : undefined
                }
              >
                RM {(entry.rounded_total_payable != null ? entry.rounded_total_payable : (Math.round(entry.motor_premium) + tenure.fixed_costs_total)).toFixed(2)}
              </p>
            )}
            <span className="text-[11px] text-[#6e6e73] font-medium block">
              (Incl. RM {tenure.fixed_costs_total.toFixed(2)} Roadtax &amp; Runner fee)
            </span>
          </div>
        </div>

        {/* Feature Comparison Rows */}
        <div className="p-4 space-y-2 text-xs divide-y divide-[#e5e5ea]">
          {/* Towing Limit */}
          <div className="h-8 flex items-center justify-between pt-1">
            <span className="text-[#6e6e73]">Towing:</span>
            <span className="font-bold text-[#1b1717]">{formatBenefitCoverage(entry.towing_km || entry.towing_limit || "Unlimited", undefined, entry.company_name)}</span>
          </div>

          {/* Agreed Value */}
          <div className="h-8 flex items-center justify-between pt-2">
            <span className="text-[#6e6e73]">Agreed Value:</span>
            <span className={`font-bold ${entry.agreed_value ? "text-emerald-700" : "text-[#6e6e73]"}`}>
              {entry.agreed_value ? "Yes" : "No"}
            </span>
          </div>

          {/* Betterment Co-pay / Waiver */}
          <div className="h-8 flex items-center justify-between pt-2">
            <div className="flex items-center gap-1 text-[#6e6e73]">
              <span>Betterment:</span>
            </div>
            <span
              className={`font-bold cursor-help ${
                (entry.betterment_display && entry.betterment_display.startsWith("No")) || entry.waiver_betterment
                  ? "text-emerald-700"
                  : "text-amber-700"
              }`}
              title="Malaysian Tariff Scale: <5 yrs: 0%, 5 yrs: 15%, 6 yrs: 20%, 7 yrs: 25%, 8 yrs: 30%, 9 yrs: 35%, 10+ yrs: 40%"
            >
              {entry.betterment_display || (entry.waiver_betterment ? "No (0%)" : "Yes")}
            </span>
          </div>

          {/* Excess */}
          <div className="h-8 flex items-center justify-between pt-2">
            <span className="text-[#6e6e73]">Excess:</span>
            <span className="font-mono font-bold text-[#1b1717]">
              RM {entry.excess.toFixed(2)}
            </span>
          </div>

          {/* Rate */}
          <div className="h-8 flex items-center justify-between pt-2">
            <span className="text-[#6e6e73]">Rate:</span>
            <span
              className="font-mono font-bold text-[#1b1717] cursor-help"
              title={`${entry.basic_figure_name || (entry.is_takaful ? "Basic Contribution" : "Basic Premium")} (RM ${(entry.basic_figure_amount || 0).toFixed(2)}) ÷ Sum Insured (RM ${entry.sum_insured.toFixed(2)}) = ${
                entry.sum_insured > 0 && entry.basic_figure_amount != null
                  ? (entry.basic_figure_amount / entry.sum_insured).toFixed(6)
                  : entry.rate_factor_formatted || "—"
              }`}
            >
              {entry.sum_insured > 0 && entry.basic_figure_amount != null
                ? (entry.basic_figure_amount / entry.sum_insured).toFixed(6)
                : entry.rate_factor_formatted || "—"}
            </span>
          </div>

          {/* Windscreen (Target vs Sourced) */}
          <div className="min-h-[38px] flex items-center justify-between pt-2">
            <span className="text-[#6e6e73]">Windscreen:</span>
            <div className="text-right">
              <span className="font-mono font-bold text-[#1b1717]">
                {entry.windscreen_sum_insured
                  ? `RM ${entry.windscreen_sum_insured.toLocaleString("en-MY", { minimumFractionDigits: 2 })}`
                  : "Not Included"}
              </span>
              {entry.windscreen_sum_insured && tenure.windscreen_target ? (
                <span
                  className={`block text-[10px] font-bold ${
                    entry.windscreen_sum_insured >= tenure.windscreen_target
                      ? "text-emerald-700"
                      : "text-amber-600"
                  }`}
                >
                  {entry.windscreen_sum_insured >= tenure.windscreen_target
                    ? "✓ Target Met"
                    : "Below Target"}
                </span>
              ) : null}
            </div>
          </div>

          {/* Special Perils / Flood */}
          <div className="h-8 flex items-center justify-between pt-2">
            <span className="text-[#6e6e73]">Special Perils:</span>
            <span className={`font-bold ${entry.special_perils ? "text-emerald-700" : "text-[#6e6e73]"}`}>
              {entry.special_perils ? formatBenefitCoverage(entry.special_perils, "RM") : "Not Included"}
            </span>
          </div>

          {/* LLP / LLOP (Passenger Liability) */}
          <div className="h-8 flex items-center justify-between pt-2">
            <span className="text-[#6e6e73]">LLP / LLOP:</span>
            <span className={`font-bold ${isLlpLlopIncluded(entry.llp_llop) ? "text-[#1b1717]" : "text-[#6e6e73]"}`}>
              {formatLlpLlop(entry.llp_llop)}
            </span>
          </div>

          {/* Notes / Endorsements */}
          {entry.notes && (
            <div className="pt-2">
              <span className="text-[10px] text-[#6e6e73] block mb-0.5 font-semibold">Notes:</span>
              <p
                className="text-[11px] text-[#454545] bg-[#f5f5f7] p-2 rounded border border-[#e5e5ea] leading-tight line-clamp-2"
                title={entry.notes}
              >
                {entry.notes}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Column Bottom Action Footer */}
      <div className="p-3.5 border-t border-[#e5e5ea] bg-[#f5f5f7]/70 space-y-2 no-print print:hidden">
        {/* Source PDF Viewing Option */}
        {entry.session_id ? (
          <button
            type="button"
            onClick={() =>
              onViewPdf({
                sessionId: entry.session_id!,
                companyName: entry.company_name,
              })
            }
            className={`w-full flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg text-xs font-bold transition-all shadow-2xs cursor-pointer ${
              isViewingPdf
                ? "bg-[#1b1717] text-white border border-[#1b1717]"
                : "bg-white hover:bg-neutral-100 text-[#1b1717] border border-[#e5e5ea]"
            }`}
            title="View uploaded underwriter quotation PDF to verify values"
          >
            <FilePdf size={15} weight="bold" className={isViewingPdf ? "text-amber-300" : "text-[#ed1c24]"} />
            <span>{isViewingPdf ? "Viewing PDF ★" : "View Source PDF"}</span>
          </button>
        ) : null}

        {/* Re-Analyze Single Quote Button */}
        <button
          type="button"
          disabled={rescanningQuoteId === entry.id || isRescanning}
          onClick={() => onRescanQuote(entry)}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg text-xs font-bold transition-all shadow-2xs bg-white hover:bg-neutral-100 text-[#1b1717] border border-[#e5e5ea] cursor-pointer disabled:opacity-50"
          title="Re-extract and re-calculate betterment, basic figures, and windscreen for this quote from the source PDF"
        >
          <ArrowsClockwise
            size={15}
            weight="bold"
            className={rescanningQuoteId === entry.id ? "animate-spin text-[#1b1717]" : "text-[#1b1717]"}
          />
          <span>{rescanningQuoteId === entry.id ? "Re-Analyzing..." : "Re-Analyze Quote"}</span>
        </button>

        {/* Winner Selection Button */}
        <Button
          variant={isWinner ? "primary" : "secondary"}
          size="sm"
          className={`w-full text-xs font-bold transition-all group ${
            isWinner
              ? "bg-[#1b1717] hover:bg-black text-white"
              : "border-[#e5e5ea] bg-white hover:border-[#1b1717] text-[#1b1717]"
          }`}
          loading={selectingWinnerId === entry.id}
          icon={<Star weight={isWinner ? "fill" : "bold"} size={14} className={isWinner ? "text-amber-400" : ""} />}
          onClick={() => onSelectWinner(entry.id)}
          title={isWinner ? "Click to deselect / unpick this underwriter" : "Pick as recommended winner"}
        >
          {isWinner ? (
            <>
              <span className="inline group-hover:hidden">Selected Winner ★</span>
              <span className="hidden group-hover:inline text-rose-300">Click to Deselect ✕</span>
            </>
          ) : (
            "Pick as Winner"
          )}
        </Button>

        {/* Direct Quotation Workspace Action */}
        {entry.session_id ? (
          <Link
            href={`/sessions/${entry.session_id}/review` as Route}
            target="_blank"
            rel="noopener noreferrer"
            className={`flex items-center justify-center gap-1.5 w-full py-2 px-3 rounded-lg text-xs font-bold transition-all shadow-2xs ${
              isWinner
                ? "text-[#ed1c24] bg-rose-50 hover:bg-rose-100 border border-rose-200"
                : "text-[#1b1717] bg-white hover:bg-neutral-100 border border-[#e5e5ea]"
            }`}
            title="Open quotation in the unified Quotation Workspace to review benefits, edit draft fields, and preview/generate customer PDF"
          >
            <FilePdf size={14} weight="bold" className={isWinner ? "text-[#ed1c24]" : "text-[#454545]"} />
            <span>{isWinner ? "Open Winner in Quotation Workspace →" : "Edit in Quotation Workspace →"}</span>
          </Link>
        ) : null}

        {/* Edit Quote Details Button (prominent and always editable) */}
        <button
          type="button"
          onClick={() => onEditEntry(entry)}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg text-xs font-semibold bg-white hover:bg-neutral-50 text-[#1b1717] border border-[#e5e5ea] shadow-2xs cursor-pointer transition-colors"
          title="Edit underwriter quotation details, sums insured, motor premium, excess, and perils"
        >
          <PencilSimple size={13} weight="bold" />
          <span>Edit Quote Details</span>
        </button>

        {/* Promote to Official Issued Cover Note */}
        {entry.session_id && (
          <button
            type="button"
            onClick={() => onPromoteToCovernote(entry)}
            disabled={promotingEntryId === entry.id}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-lg text-xs font-bold transition-all shadow-2xs bg-emerald-50 hover:bg-emerald-100 text-emerald-900 border border-emerald-300 cursor-pointer disabled:opacity-50"
            title="Promote this underwriter quote to official issued Cover Note"
          >
            <CheckCircle size={14} weight="bold" className="text-emerald-700" />
            <span>{promotingEntryId === entry.id ? "Promoting..." : "Mark as Issued Cover Note"}</span>
          </button>
        )}

        <div className="flex items-center justify-between px-1 pt-1 border-t border-neutral-100 mt-1">
          {group.entries.length > 1 ? (
            <>
              <button
                type="button"
                onClick={() => onDeleteEntry(entry.id, false)}
                className="text-[11px] font-medium text-neutral-500 hover:text-[#ed1c24] flex items-center gap-1 cursor-pointer"
                title={`Delete only version v${entry.version || 1}`}
              >
                <Trash size={12} />
                Delete v{entry.version || 1}
              </button>
              <button
                type="button"
                onClick={() => onDeleteEntry(entry.id, true)}
                className="text-[11px] font-bold text-[#ed1c24] hover:text-[#c4171e] flex items-center gap-1 cursor-pointer"
                title="Delete this entire underwriter column and all its versions"
              >
                <Trash size={12} weight="bold" />
                Delete Underwriter
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => onDeleteEntry(entry.id, true)}
              className="text-xs font-medium text-[#ed1c24] hover:text-[#c4171e] flex items-center gap-1 cursor-pointer ml-auto"
              title="Delete this underwriter comparison column"
            >
              <Trash size={13} />
              Delete Column
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
