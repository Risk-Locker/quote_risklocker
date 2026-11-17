"use client";

import React from "react";
import Link from "next/link";
import type { Route } from "next";
import { FilePdf } from "@phosphor-icons/react";
import { fileUrl } from "@/lib/api";
import type { TenureRow } from "../types";
import { HighlightText } from "../HighlightText";

type QuoteStatusTone = "covernote" | "previous" | "awaiting" | "none";

const STATUS_CHIP: Record<QuoteStatusTone, { label: string; className: string }> = {
  covernote: { label: "Cover Note", className: "bg-emerald-50 text-emerald-800 border-emerald-200" },
  previous: { label: "Previous Policy", className: "bg-blue-50 text-blue-800 border-blue-200" },
  awaiting: { label: "Awaiting Cover Note", className: "bg-amber-50 text-amber-800 border-amber-200" },
  none: { label: "No quotes yet", className: "bg-neutral-100 text-neutral-600 border-neutral-200" },
};

interface QuoteHeadline {
  company: string | null;
  amount: string | null;
  tone: QuoteStatusTone;
  pdf: { fileId: string; label: string; title: string } | null;
}

function toDisplayAmount(value: number | string | null | undefined): string | null {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}

/** Resolve the single headline (insurer, amount, status, PDF) shown for a tenure. Display-only. */
function resolveQuoteHeadline(t: TenureRow): QuoteHeadline {
  const cn = t.covernote_policy;
  if (cn) {
    return {
      company: cn.company,
      amount: toDisplayAmount(cn.total_payable),
      tone: cn.is_previous_year_policy ? "previous" : "covernote",
      pdf: cn.uploaded_file_id
        ? { fileId: cn.uploaded_file_id, label: cn.file_name || "Cover Note PDF", title: "Open Cover Note PDF in new tab" }
        : null,
    };
  }
  const quotes = t.sourced_quotes || [];
  if (quotes.length === 0) {
    return { company: null, amount: null, tone: "none", pdf: null };
  }
  const winner = quotes.find((q) => q.is_winner && q.uploaded_file_id);
  const isSealed = Boolean(winner?.is_winner || t.stage === "Close - Win" || t.status === "hit");
  let pdf: QuoteHeadline["pdf"] = null;
  if (t.winning_file_id) {
    pdf = { fileId: t.winning_file_id, label: "Won PDF", title: "Open Won Quotation PDF" };
  } else if (winner?.uploaded_file_id) {
    pdf = {
      fileId: winner.uploaded_file_id,
      label: isSealed ? "Accepted PDF" : "Leading PDF",
      title: `Open ${isSealed ? "Accepted" : "Leading"} Quotation PDF (${winner.company})`,
    };
  }
  return {
    company: t.winning_company_name || quotes[0].company,
    amount: toDisplayAmount(t.won_premium) ?? toDisplayAmount(quotes[0].total_payable),
    tone: "awaiting",
    pdf,
  };
}

function ComparisonLink({ tenureId, count }: { tenureId: string; count: number }) {
  return (
    <Link
      href={`/comparison?tenure_id=${tenureId}` as Route}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center text-[10px] font-bold text-amber-800 hover:text-amber-950 hover:underline shrink-0"
      title="Open Marketing Comparison in new tab"
    >
      {count > 0 ? `${count} quote${count === 1 ? "" : "s"} →` : "Open comparison →"}
    </Link>
  );
}

function PdfLink({ pdf, search, compact }: { pdf: NonNullable<QuoteHeadline["pdf"]>; search: string; compact: boolean }) {
  return (
    <a
      href={fileUrl(pdf.fileId)}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-[10px] font-bold text-rose-700 hover:text-rose-900 bg-rose-50 hover:bg-rose-100 px-1.5 rounded border border-rose-200 transition-colors min-w-0"
      title={pdf.title}
      aria-label={pdf.title}
    >
      <FilePdf size={11} weight="fill" className="shrink-0" />
      {!compact && (
        <span className="truncate max-w-[120px]">
          <HighlightText text={pdf.label} query={search} />
        </span>
      )}
    </a>
  );
}

function CoverNoteKeyTerms({ policy }: { policy: NonNullable<TenureRow["covernote_policy"]> }) {
  const terms = [
    policy.sum_insured ? `SI: RM ${policy.sum_insured}` : null,
    policy.windscreen ? `WS: RM ${policy.windscreen}` : null,
    policy.towing ? `Tow: ${policy.towing}` : null,
  ].filter(Boolean);
  if (terms.length === 0) return null;
  return (
    <div className="text-[9.5px] text-neutral-500 font-medium truncate" title={terms.join(" · ")}>
      {terms.join(" · ")}
    </div>
  );
}

export function QuotesActivityCell({ tenure, isCompact, search }: { tenure: TenureRow; isCompact: boolean; search: string }) {
  const headline = resolveQuoteHeadline(tenure);
  const chip = STATUS_CHIP[headline.tone];
  const quotes = tenure.sourced_quotes || [];
  const awaitingQuotes = headline.tone === "previous" && quotes.length === 0;

  return (
    <div className={`space-y-1 min-w-0 ${isCompact ? "max-w-[170px]" : "max-w-[260px]"}`}>
      <div className="flex items-center gap-1 min-w-0">
        {headline.company ? (
          <span className="font-bold text-xs text-neutral-900 truncate" title={headline.company}>
            <HighlightText text={headline.company} query={search} />
          </span>
        ) : null}
        {headline.amount ? (
          <span className="ml-auto text-neutral-900 font-mono font-bold text-[11px] bg-neutral-100 px-1 rounded border border-neutral-200 shrink-0">
            RM {headline.amount}
          </span>
        ) : null}
      </div>

      <div className="flex items-center gap-1 min-w-0 flex-wrap">
        <span className={`inline-flex items-center px-1 rounded text-[9px] font-bold border shrink-0 ${chip.className}`}>
          {chip.label}
        </span>
        {headline.pdf ? <PdfLink pdf={headline.pdf} search={search} compact={isCompact} /> : null}
        {awaitingQuotes ? (
          <Link
            href={`/upload?tenure_id=${tenure.id}` as Route}
            target="_blank"
            className="text-[10px] font-bold text-neutral-700 hover:text-black hover:underline"
          >
            + Add quotes
          </Link>
        ) : (
          <ComparisonLink tenureId={tenure.id} count={quotes.length} />
        )}
      </div>

      {!isCompact && tenure.covernote_policy && (
        <CoverNoteKeyTerms policy={tenure.covernote_policy} />
      )}

      {!isCompact && quotes.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap pt-0.5">
          {quotes.map((q) => (
            <Link
              key={q.session_id}
              href={`/sessions/${q.session_id}/review` as Route}
              target="_blank"
              rel="noopener noreferrer"
              className={`inline-flex items-center gap-1 px-1.5 rounded text-[10px] transition-colors border hover:border-neutral-900 ${
                q.is_winner
                  ? "bg-amber-50 text-amber-900 border-amber-300 font-bold"
                  : "bg-white text-neutral-700 border-neutral-200 hover:bg-neutral-50 font-medium"
              }`}
              title={`Open ${q.company} quote workspace in new tab${q.total_payable ? ` · RM ${q.total_payable}` : ""}`}
            >
              {q.company}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
