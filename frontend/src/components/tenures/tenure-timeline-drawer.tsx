"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  X,
  FilePdf,
  Clock,
  Car,
  ArrowsClockwise,
  ArrowSquareOut,
  CaretDown,
  CaretUp,
  Columns,
  ShieldCheck,
  CheckCircle,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";

export interface TenureTimelineDrawerProps {
  tenureId: string;
  isOpen: boolean;
  onClose: () => void;
  onRefresh?: () => void;
}

export function TenureTimelineDrawer({
  tenureId,
  isOpen,
  onClose,
}: TenureTimelineDrawerProps) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [expandedCompany, setExpandedCompany] = useState<string | null>(null);

  async function loadDetail() {
    if (!tenureId) return;
    setLoading(true);
    try {
      const res = await api<any>(`/tenures/${tenureId}`);
      setData(res);
    } catch (err) {
      console.error("Failed to load tenure detail:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isOpen && tenureId) {
      loadDetail();
    }
  }, [isOpen, tenureId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-xs flex justify-end animate-fade-in no-print">
      <div className="w-full max-w-2xl bg-white h-full shadow-2xl flex flex-col border-l border-neutral-200">
        {/* Drawer Header */}
        <div className="px-6 py-5 border-b border-neutral-200 bg-neutral-50/70 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold text-neutral-900 tracking-tight flex items-center gap-1.5">
                <Car className="w-5 h-5 text-neutral-700" />
                {data?.vehicle_no || "Vehicle Tenure"}
              </span>
              <span className="text-xs text-neutral-400">·</span>
              <span className="text-sm font-medium text-neutral-700">{data?.customer_name}</span>
            </div>
            <p className="text-xs text-neutral-500 mt-1">
              Confirmed Period:{" "}
              {data?.stage === "Issue Policy" && data?.coverage_start_date ? (
                <strong className="font-mono text-neutral-800">
                  {new Date(data.coverage_start_date).toLocaleDateString("en-GB")} to{" "}
                  {data.coverage_end_date ? new Date(data.coverage_end_date).toLocaleDateString("en-GB") : "—"}
                </strong>
              ) : (
                <span className="text-neutral-400 font-mono">— (Pending Policy Issue)</span>
              )}{" "}
              <span className="font-semibold text-neutral-600">(Cohort {data?.expiry_month})</span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href={`/comparison?tenure_id=${tenureId}` as Route}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1b1717] hover:bg-black text-white text-xs font-bold transition-colors shadow-xs"
            >
              <Columns className="w-4 h-4" />
              <span>Open Comparison</span>
            </Link>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-700 hover:bg-neutral-200/60 transition-colors cursor-pointer"
              title="Close Logs Drawer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Area: Pure Read-Only Audit & Quotation PDF Viewer */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {loading ? (
            <div className="py-20 text-center text-xs text-neutral-400 flex flex-col items-center gap-2">
              <ArrowsClockwise className="w-6 h-6 animate-spin text-neutral-500" />
              <span>Loading tenure logs...</span>
            </div>
          ) : !data ? (
            <div className="py-20 text-center text-sm text-neutral-500">Tenure not found.</div>
          ) : (
            <>
              {/* Summary Status Strip */}
              <div className="p-3 bg-neutral-50 border border-neutral-200 rounded-xl text-xs flex items-center justify-between">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-bold text-neutral-500 uppercase tracking-wider text-[10px]">
                    Current Stage:
                  </span>
                  <span className="px-2 py-0.5 rounded-md font-bold text-xs bg-neutral-900 text-white">
                    {data.stage || "Quotations"}
                  </span>
                  {data.won_premium && (
                    <span className="text-emerald-700 font-bold font-mono">
                      Bound: RM {Number(data.won_premium).toFixed(2)}
                    </span>
                  )}
                  {data.winning_quotation_ref && (
                    <span className="font-mono text-neutral-500 text-[11px]">
                      Ref: {data.winning_quotation_ref}
                    </span>
                  )}
                </div>
                {data.last_activity_at && (
                  <span className="text-[11px] text-neutral-400 font-mono">
                    Last active: {new Date(data.last_activity_at).toLocaleDateString("en-MY")}
                  </span>
                )}
              </div>

              {/* 1. SOURCED INSURER QUOTATIONS & VERSIONS */}
              <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-2xs space-y-3">
                <div className="flex items-center justify-between border-b border-neutral-100 pb-2">
                  <h3 className="text-xs font-bold text-neutral-900 uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                    1. Uploaded Insurer Quotations &amp; Versions
                  </h3>
                  <span className="text-[11px] text-neutral-400 font-medium">
                    {Object.keys(data.sourced_quotes_by_company || {}).length} Underwriter(s)
                  </span>
                </div>

                <div className="space-y-3 pt-1">
                  {Object.entries(data.sourced_quotes_by_company || {}).map(([company, quotes]: [string, any]) => {
                    const activeQuote = quotes.find((q: any) => q.is_active) || quotes[quotes.length - 1];
                    const hasHistory = quotes.length > 1;
                    const isExpanded = expandedCompany === company;

                    return (
                      <div key={company} className="border border-neutral-200/70 rounded-xl p-3 bg-neutral-50/50 space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm text-neutral-900">{company}</span>
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800">
                              v{activeQuote?.version || 1}
                            </span>
                            {hasHistory && (
                              <button
                                onClick={() => setExpandedCompany(isExpanded ? null : company)}
                                className="text-[11px] text-neutral-500 hover:text-neutral-800 underline flex items-center gap-0.5 ml-1 cursor-pointer"
                              >
                                {quotes.length} versions {isExpanded ? <CaretUp /> : <CaretDown />}
                              </button>
                            )}
                          </div>
                          <div className="text-right">
                            <span className="text-xs font-mono font-bold text-neutral-900">
                              RM {activeQuote?.total_payable || "—"}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center justify-between text-xs text-neutral-500 pt-1">
                          <span>Sum Insured: RM {activeQuote?.sum_insured || "—"}</span>
                          <div className="flex items-center gap-2">
                            <a
                              href={`/sessions/${activeQuote?.session_id}/review`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[11px] font-semibold text-neutral-700 hover:text-black flex items-center gap-1 bg-white px-2 py-1 rounded border border-neutral-200"
                            >
                              Review Draft <ArrowSquareOut className="w-3 h-3" />
                            </a>
                            <a
                              href={`/api/sessions/${activeQuote?.session_id}/pdf`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[11px] font-semibold text-rose-700 hover:text-rose-900 flex items-center gap-1 bg-rose-50 px-2 py-1 rounded border border-rose-200"
                            >
                              <FilePdf size={13} className="text-rose-600" />
                              Source PDF
                            </a>
                          </div>
                        </div>

                        {/* Version History Accordion */}
                        {isExpanded && hasHistory && (
                          <div className="mt-2 pt-2 border-t border-neutral-200/60 space-y-1.5 text-xs bg-white p-2.5 rounded-lg">
                            <span className="text-[10px] font-bold uppercase text-neutral-400">Version History</span>
                            {quotes.map((q: any) => (
                              <div key={q.session_id} className="flex items-center justify-between text-neutral-600 py-1 border-b border-neutral-100 last:border-none">
                                <div className="flex items-center gap-2">
                                  <span className="font-bold text-neutral-800">v{q.version}</span>
                                  <span className="text-neutral-400">·</span>
                                  <span className="font-mono font-semibold">RM {q.total_payable || "—"}</span>
                                  {q.is_active && (
                                    <span className="text-[10px] text-emerald-700 font-bold bg-emerald-50 px-1 rounded">
                                      (Active)
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className="text-[10px] text-neutral-400 font-mono">
                                    {q.created_at ? new Date(q.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                                  </span>
                                  <a
                                    href={`/api/sessions/${q.session_id}/pdf`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[10px] text-rose-700 hover:underline flex items-center gap-0.5"
                                  >
                                    <FilePdf size={12} /> PDF
                                  </a>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 2. GENERATED OFFICIAL RISKLOCKER QUOTATIONS */}
              <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-2xs space-y-3">
                <div className="flex items-center justify-between border-b border-neutral-100 pb-2">
                  <h3 className="text-xs font-bold text-neutral-900 uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                    2. Official Generated Risk-Locker Quotation PDFs
                  </h3>
                  <span className="text-[11px] text-neutral-400 font-medium">
                    {data.generated_risklocker_quotations?.length || 0} Issued
                  </span>
                </div>

                {!data.generated_risklocker_quotations || data.generated_risklocker_quotations.length === 0 ? (
                  <div className="py-4 text-center text-xs text-neutral-400 bg-neutral-50 rounded-lg">
                    No official Risk-Locker quotation PDFs generated yet. Select a recommendation in the Comparison Matrix to issue one.
                  </div>
                ) : (
                  <div className="space-y-2 pt-1">
                    {data.generated_risklocker_quotations.map((g: any) => (
                      <div
                        key={g.session_id}
                        className="flex items-center justify-between p-3 bg-neutral-50/70 border border-neutral-200/80 rounded-xl text-xs"
                      >
                        <div className="flex items-center gap-2 flex-wrap">
                          <FilePdf className="w-4 h-4 text-red-600" />
                          <span className="font-bold text-neutral-900 font-mono">{g.quotation_ref}</span>
                          <span className="text-neutral-500">({g.company})</span>
                          <span className="font-mono font-bold text-neutral-900">RM {g.total_payable || "—"}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <a
                            href={`/api/sessions/${g.session_id}/pdf?download=true`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[11px] text-neutral-700 bg-white border border-neutral-200 px-2.5 py-1 rounded-md hover:bg-neutral-100 font-semibold flex items-center gap-1 transition-colors"
                          >
                            <FilePdf className="w-3.5 h-3.5 text-red-600" /> Download PDF
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 3. AUDIT & CHRONOLOGICAL ACTIVITY LOG */}
              <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-2xs space-y-3">
                <div className="flex items-center justify-between border-b border-neutral-100 pb-2">
                  <h3 className="text-xs font-bold text-neutral-900 uppercase tracking-wider flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-neutral-500" />
                    3. Chronological Audit &amp; Activity Log
                  </h3>
                  <span className="text-[11px] text-neutral-400 font-medium">
                    {data.activities?.length || 0} events
                  </span>
                </div>

                <div className="space-y-2 pt-1">
                  {!data.activities || data.activities.length === 0 ? (
                    <div className="text-xs text-neutral-400 py-3 text-center bg-neutral-50/60 rounded-lg">
                      No activity entries recorded yet for this tenure.
                    </div>
                  ) : (
                    data.activities.map((act: any) => {
                      let timeStr = "";
                      if (act.created_at) {
                        try {
                          timeStr = new Date(act.created_at).toLocaleString("en-MY", {
                            year: "numeric",
                            month: "numeric",
                            day: "numeric",
                            hour: "numeric",
                            minute: "2-digit",
                            second: "2-digit",
                          });
                        } catch {
                          timeStr = act.created_at;
                        }
                      }
                      return (
                        <div
                          key={act.id}
                          className="flex items-start gap-2.5 text-xs py-2 border-b border-neutral-100 last:border-none"
                        >
                          <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                          <div className="flex-1">
                            <p className="text-neutral-900 font-semibold text-xs leading-snug">{act.summary}</p>
                            {timeStr && (
                              <p className="text-[11px] text-neutral-500 font-mono mt-0.5">{timeStr}</p>
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
