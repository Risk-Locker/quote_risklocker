"use client";

import React from "react";
import { CheckCircle, Sparkle } from "@phosphor-icons/react";
import type { TenureRow } from "../types";
import { formatDateSafe } from "../types";

type CoverageTone = "issued" | "upcoming" | "external" | "pending" | "empty";

interface CoverageSummary {
  start: string | null | undefined;
  end: string | null | undefined;
  tone: CoverageTone;
  label: string;
}

const TONE_STYLES: Record<CoverageTone, { chip: string; label: string }> = {
  issued: { chip: "text-emerald-700 bg-emerald-50 border-emerald-200", label: "text-emerald-700" },
  upcoming: { chip: "text-blue-700 bg-blue-50 border-blue-200", label: "text-blue-700" },
  external: { chip: "text-purple-700 bg-purple-50 border-purple-200", label: "text-purple-700" },
  pending: { chip: "text-amber-700 bg-amber-50 border-amber-200", label: "text-amber-700" },
  empty: { chip: "text-neutral-500 bg-neutral-50 border-neutral-200", label: "text-neutral-400" },
};

export function isTenurePolicyIssued(t: TenureRow): boolean {
  return Boolean(t.covernote_policy || t.is_covernote_issued || t.stage === "Close - Win" || t.status === "hit");
}

/** Pick which coverage period represents this tenure (display-only, no date arithmetic). */
function summarizeCoverage(t: TenureRow): CoverageSummary {
  const cn = t.covernote_policy;
  if (cn?.is_previous_year_policy) {
    return { start: t.coverage_start_date, end: t.coverage_end_date, tone: "upcoming", label: "Upcoming Renewal" };
  }
  if (isTenurePolicyIssued(t) && (cn?.coverage_start_date || t.coverage_start_date)) {
    return {
      start: cn?.coverage_start_date || t.coverage_start_date,
      end: cn?.coverage_end_date || t.coverage_end_date,
      tone: "issued",
      label: "Issued Policy",
    };
  }
  if (t.external_policy_start_date) {
    return { start: t.external_policy_start_date, end: t.external_policy_end_date, tone: "external", label: "External Policy" };
  }
  if (t.coverage_start_date && t.coverage_end_date && t.sourced_quotes?.length > 0) {
    return { start: t.coverage_start_date, end: t.coverage_end_date, tone: "pending", label: "Pending Cover Note" };
  }
  return { start: null, end: null, tone: "empty", label: "Pending Renewal" };
}

export function CoveragePeriodCell({ tenure, isCompact }: { tenure: TenureRow; isCompact: boolean }) {
  const summary = summarizeCoverage(tenure);
  const styles = TONE_STYLES[summary.tone];
  const hasDates = Boolean(summary.start || summary.end);
  const LabelIcon = summary.tone === "issued" ? CheckCircle : summary.tone === "upcoming" ? Sparkle : null;

  return (
    <div className="space-y-0.5">
      {hasDates ? (
        <div className={`font-mono text-neutral-800 ${isCompact ? "text-[11px]" : "text-[11px] font-medium"}`}>
          {formatDateSafe(summary.start)}
          <span className="text-neutral-400 mx-1">→</span>
          {formatDateSafe(summary.end)}
        </div>
      ) : (
        <div className="text-neutral-400 font-mono text-xs">—</div>
      )}

      <div className="flex items-center gap-1 flex-wrap">
        <span className={`inline-flex items-center gap-0.5 px-1 rounded border text-[9px] font-bold ${styles.chip}`}>
          {LabelIcon ? <LabelIcon size={9} weight="fill" /> : null}
          {summary.label}
        </span>
        {tenure.expiry_month ? (
          <span className="text-[9.5px] text-neutral-500 font-mono" title="Expiry month anchor">
            {isCompact ? tenure.expiry_month : `Exp: ${tenure.expiry_month}`}
          </span>
        ) : (
          <span className="text-[9.5px] text-neutral-400 italic">Extracted on upload</span>
        )}
        {tenure.is_main && <span className="text-[9px] text-emerald-800 font-bold">★ Main</span>}
      </div>
    </div>
  );
}
