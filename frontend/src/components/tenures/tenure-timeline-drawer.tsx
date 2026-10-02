"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  X,
  FilePdf,
  CheckCircle,
  XCircle,
  PaperPlaneTilt,
  Clock,
  Car,
  User,
  ArrowsClockwise,
  ArrowSquareOut,
  CaretDown,
  CaretUp,
  Tag,
  Columns,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

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
  onRefresh,
}: TenureTimelineDrawerProps) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [expandedCompany, setExpandedCompany] = useState<string | null>(null);

  // Status update modal state
  const [statusVal, setStatusVal] = useState("draft");
  const [wonPremium, setWonPremium] = useState("");
  const [winningRef, setWinningRef] = useState("");
  const [missReason, setMissReason] = useState("");
  const [notes, setNotes] = useState("");
  const [savingStatus, setSavingStatus] = useState(false);
  const [generatingQuote, setGeneratingQuote] = useState<string | null>(null);

  const [shiftingDates, setShiftingDates] = useState(false);
  const [newStartDateInput, setNewStartDateInput] = useState("");
  const [projectingRenewal, setProjectingRenewal] = useState(false);
  const [lapsingTenure, setLapsingTenure] = useState(false);

  async function loadDetail() {
    if (!tenureId) return;
    setLoading(true);
    try {
      const res = await api<any>(`/tenures/${tenureId}`);
      setData(res);
      setStatusVal(res.status || "draft");
      setWonPremium(res.won_premium ? String(res.won_premium) : "");
      setWinningRef(res.winning_quotation_ref || "");
      setMissReason(res.miss_reason || "");
      setNotes(res.notes || "");
      if (res.coverage_start_date) {
        setNewStartDateInput(res.coverage_start_date.substring(0, 10));
      }
    } catch (err) {
      console.error("Failed to load tenure detail:", err);
    } finally {
      setLoading(false);
    }
  }

  async function doShiftDates(dateStr: string) {
    if (!dateStr) return;
    setShiftingDates(true);
    try {
      await api(`/tenures/${tenureId}/shift-dates`, {
        method: "POST",
        body: JSON.stringify({ start_date: dateStr }),
      });
      await loadDetail();
      if (onRefresh) onRefresh();
    } catch (err: any) {
      alert("Failed to shift dates: " + (err?.message || err));
    } finally {
      setShiftingDates(false);
    }
  }

  async function handleQuickShift(daysToAdd: number) {
    if (!data?.coverage_start_date) return;
    const current = new Date(data.coverage_start_date);
    current.setDate(current.getDate() + daysToAdd);
    const dateStr = current.toISOString().substring(0, 10);
    setNewStartDateInput(dateStr);
    await doShiftDates(dateStr);
  }

  async function handleProjectRenewal() {
    setProjectingRenewal(true);
    try {
      await api(`/tenures/${tenureId}/project-renewal`, { method: "POST" });
      await loadDetail();
      if (onRefresh) onRefresh();
    } catch (err: any) {
      alert("Failed to project renewal: " + (err?.message || err));
    } finally {
      setProjectingRenewal(false);
    }
  }

  async function handleMarkLapsed() {
    const reason = prompt("Enter reason for lapse (e.g. Sold vehicle, Competitor, Unreachable):", "Customer discontinued");
    if (!reason) return;
    setLapsingTenure(true);
    try {
      await api(`/tenures/${tenureId}/lapse`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      await loadDetail();
      if (onRefresh) onRefresh();
    } catch (err: any) {
      alert("Failed to mark tenure lapsed: " + (err?.message || err));
    } finally {
      setLapsingTenure(false);
    }
  }

  useEffect(() => {
    if (isOpen && tenureId) {
      loadDetail();
    }
  }, [isOpen, tenureId]);

  if (!isOpen) return null;

  async function handleSaveStatus() {
    setSavingStatus(true);
    try {
      await api(`/tenures/${tenureId}/status`, {
        method: "POST",
        body: JSON.stringify({
          status: statusVal,
          winning_quotation_ref: winningRef || null,
          won_premium: wonPremium ? parseFloat(wonPremium) : null,
          miss_reason: missReason || null,
          notes: notes || null,
        }),
      });
      await loadDetail();
      if (onRefresh) onRefresh();
    } catch (err: any) {
      alert("Failed to save status: " + (err?.message || err));
    } finally {
      setSavingStatus(false);
    }
  }

  async function handleGenerateQuote(sessionId: string) {
    setGeneratingQuote(sessionId);
    try {
      await api(`/tenures/${tenureId}/generate-quote`, {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId }),
      });
      await loadDetail();
      if (onRefresh) onRefresh();
    } catch (err: any) {
      alert("Failed to generate quote: " + (err?.message || err));
    } finally {
      setGeneratingQuote(null);
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-xs flex justify-end animate-fade-in">
      <div className="w-full max-w-2xl bg-white h-full shadow-2xl flex flex-col border-l border-neutral-200">
        {/* Drawer Header */}
        <div className="px-6 py-5 border-b border-neutral-200 bg-neutral-50/60 flex items-center justify-between">
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
              Coverage: {data?.coverage_start_date ? new Date(data.coverage_start_date).toLocaleDateString("en-GB") : "—"} to{" "}
              {data?.coverage_end_date ? new Date(data.coverage_end_date).toLocaleDateString("en-GB") : "—"}{" "}
              <span className="font-semibold text-neutral-700">(Expiring {data?.expiry_month})</span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href={`/comparison?tenure_id=${tenureId}` as Route}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-colors shadow-xs"
            >
              <Columns className="w-4 h-4" />
              <span>Marketing Comparison</span>
            </Link>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-700 hover:bg-neutral-200/60 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {loading ? (
            <div className="py-20 text-center text-xs text-neutral-400 flex flex-col items-center gap-2">
              <ArrowsClockwise className="w-6 h-6 animate-spin text-neutral-500" />
              <span>Loading tenure timeline...</span>
            </div>
          ) : !data ? (
            <div className="py-20 text-center text-sm text-neutral-500">Tenure not found.</div>
          ) : (
            <>
              {/* Previous Policy Banner */}
              {data.previous_tenure && (
                <div className="p-3 bg-amber-50/80 border border-amber-200/80 rounded-xl text-xs text-amber-900 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold uppercase tracking-wider text-[10px] bg-amber-200/80 px-2 py-0.5 rounded text-amber-950">
                      Previous Year Policy
                    </span>
                    <span>
                      Exp: {data.previous_tenure.expiry_month} · Outcome: <strong>{data.previous_tenure.status.toUpperCase()}</strong>
                      {data.previous_tenure.won_premium && ` (RM ${data.previous_tenure.won_premium.toFixed(2)})`}
                    </span>
                  </div>
                </div>
              )}

              {/* 1. SOURCED INSURER QUOTATIONS & VERSIONS */}
              <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-2xs space-y-3">
                <div className="flex items-center justify-between border-b border-neutral-100 pb-2">
                  <h3 className="text-xs font-bold text-neutral-900 uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                    1. Sourced Insurer Quotations &amp; Versions
                  </h3>
                  <span className="text-[11px] text-neutral-400 font-medium">
                    {Object.keys(data.sourced_quotes_by_company || {}).length} Insurers
                  </span>
                </div>

                <div className="space-y-3 pt-1">
                  {Object.entries(data.sourced_quotes_by_company || {}).map(([company, quotes]: [string, any]) => {
                    const activeQuote = quotes.find((q: any) => q.is_active) || quotes[quotes.length - 1];
                    const hasHistory = quotes.length > 1;
                    const isExpanded = expandedCompany === company;

                    return (
                      <div key={company} className="border border-neutral-200/70 rounded-lg p-3 bg-neutral-50/40 space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm text-neutral-900">{company}</span>
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800">
                              v{activeQuote?.version || 1}
                            </span>
                            {hasHistory && (
                              <button
                                onClick={() => setExpandedCompany(isExpanded ? null : company)}
                                className="text-[11px] text-neutral-500 hover:text-neutral-800 underline flex items-center gap-0.5 ml-1"
                              >
                                {quotes.length} versions {isExpanded ? <CaretUp /> : <CaretDown />}
                              </button>
                            )}
                          </div>
                          <div className="text-right">
                            <span className="text-xs font-semibold text-neutral-900">
                              Total: RM {activeQuote?.total_payable || "—"}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center justify-between text-xs text-neutral-500 pt-1">
                          <span>Sum Insured: RM {activeQuote?.sum_insured || "—"}</span>
                          <div className="flex items-center gap-2">
                            <a
                              href={`/sessions/${activeQuote?.session_id}`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[11px] font-medium text-blue-600 hover:underline flex items-center gap-1"
                            >
                              Review &amp; Edit <ArrowSquareOut className="w-3 h-3" />
                            </a>
                            {!activeQuote?.quotation_ref && (
                              <Button
                                size="sm"
                                variant="secondary"
                                disabled={generatingQuote === activeQuote?.session_id}
                                onClick={() => handleGenerateQuote(activeQuote.session_id)}
                                className="h-6 text-[10px] px-2"
                              >
                                {generatingQuote === activeQuote?.session_id ? "Generating..." : "+ Create RL Quote"}
                              </Button>
                            )}
                          </div>
                        </div>

                        {/* Version History Accordion */}
                        {isExpanded && hasHistory && (
                          <div className="mt-2 pt-2 border-t border-neutral-200/60 space-y-1.5 text-xs bg-white p-2 rounded">
                            <span className="text-[10px] font-bold uppercase text-neutral-400">Version History</span>
                            {quotes.map((q: any) => (
                              <div key={q.session_id} className="flex items-center justify-between text-neutral-600 py-0.5">
                                <div className="flex items-center gap-2">
                                  <span className="font-semibold text-neutral-700">v{q.version}</span>
                                  <span className="text-neutral-400">·</span>
                                  <span>Total: RM {q.total_payable || "—"}</span>
                                  {q.is_active && <span className="text-[10px] text-green-700 font-bold bg-green-50 px-1 rounded">(Active)</span>}
                                </div>
                                <span className="text-[10px] text-neutral-400">
                                  {q.created_at ? new Date(q.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 2. GENERATED RISKLOCKER QUOTATIONS */}
              <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-2xs space-y-3">
                <div className="flex items-center justify-between border-b border-neutral-100 pb-2">
                  <h3 className="text-xs font-bold text-neutral-900 uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                    2. Generated Risklocker Quotations
                  </h3>
                  <span className="text-[11px] text-neutral-400 font-medium">
                    {data.generated_risklocker_quotations?.length || 0} Ready
                  </span>
                </div>

                {(!data.generated_risklocker_quotations || data.generated_risklocker_quotations.length === 0) ? (
                  <div className="py-4 text-center text-xs text-neutral-400">
                    No Risklocker quotation PDFs generated yet. Click &quot;+ Create RL Quote&quot; above to generate one.
                  </div>
                ) : (
                  <div className="space-y-2 pt-1">
                    {data.generated_risklocker_quotations.map((g: any) => (
                      <div
                        key={g.session_id}
                        className="flex items-center justify-between p-2.5 bg-neutral-50/70 border border-neutral-200/80 rounded-lg text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <FilePdf className="w-4 h-4 text-red-600" />
                          <span className="font-bold text-neutral-900 font-mono">{g.quotation_ref}</span>
                          <span className="text-neutral-400">({g.company})</span>
                          <span className="text-neutral-600 font-medium">RM {g.total_payable || "—"}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <a
                            href={`/api/sessions/${g.session_id}/pdf?download=true`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[11px] text-neutral-700 bg-white border border-neutral-200 px-2 py-1 rounded hover:bg-neutral-100 font-medium flex items-center gap-1"
                          >
                            <FilePdf className="w-3.5 h-3.5 text-neutral-600" /> Download PDF
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* DATE MODULARITY & TENURE LIFECYCLE */}
              <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-2xs space-y-3">
                <div className="flex items-center justify-between border-b border-neutral-100 pb-2">
                  <h3 className="text-xs font-bold text-neutral-900 uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                    Coverage Period &amp; Date Shifter
                  </h3>
                  <div className="flex items-center gap-1.5">
                    {data.is_projected && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-200">
                        Projected Reminder
                      </span>
                    )}
                    {(data.delay_days || 0) > 0 && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-orange-100 text-orange-900">
                        +{data.delay_days}d Late
                      </span>
                    )}
                  </div>
                </div>

                <div className="p-3 bg-neutral-50/80 border border-neutral-200/80 rounded-lg text-xs space-y-2">
                  <div className="flex items-center justify-between text-neutral-700">
                    <span>
                      Current Coverage: <strong className="font-mono text-neutral-900">{data.coverage_start_date ? new Date(data.coverage_start_date).toLocaleDateString("en-GB") : "—"}</strong> → <strong className="font-mono text-neutral-900">{data.coverage_end_date ? new Date(data.coverage_end_date).toLocaleDateString("en-GB") : "—"}</strong>
                    </span>
                    <span className="text-[11px] text-neutral-500">
                      Cohort: <strong>{data.expiry_month}</strong>
                    </span>
                  </div>

                  {/* Quick Shift Buttons */}
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <span className="text-[11px] font-semibold text-neutral-500 mr-1">Quick Shift:</span>
                    <button
                      type="button"
                      disabled={shiftingDates}
                      onClick={() => handleQuickShift(1)}
                      className="px-2 py-1 rounded bg-white border border-neutral-200 hover:bg-neutral-100 text-[11px] font-semibold text-neutral-800 transition-colors"
                    >
                      +1 Day
                    </button>
                    <button
                      type="button"
                      disabled={shiftingDates}
                      onClick={() => handleQuickShift(7)}
                      className="px-2 py-1 rounded bg-white border border-neutral-200 hover:bg-neutral-100 text-[11px] font-semibold text-neutral-800 transition-colors"
                    >
                      +1 Week
                    </button>
                    <button
                      type="button"
                      disabled={shiftingDates}
                      onClick={() => handleQuickShift(30)}
                      className="px-2 py-1 rounded bg-white border border-neutral-200 hover:bg-neutral-100 text-[11px] font-semibold text-neutral-800 transition-colors"
                    >
                      +1 Month
                    </button>

                    {/* Custom Date Input */}
                    <div className="flex items-center gap-1 ml-auto">
                      <input
                        type="date"
                        value={newStartDateInput}
                        onChange={(e) => setNewStartDateInput(e.target.value)}
                        className="text-xs h-7 px-2 border border-neutral-200 rounded bg-white focus:outline-hidden focus:ring-1 focus:ring-neutral-900"
                      />
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={shiftingDates || !newStartDateInput}
                        onClick={() => doShiftDates(newStartDateInput)}
                        className="h-7 text-[11px] px-2"
                      >
                        {shiftingDates ? "Syncing..." : "Apply Shift"}
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Lifecycle Actions */}
                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    disabled={lapsingTenure || data.status === "lapsed"}
                    onClick={handleMarkLapsed}
                    className="text-xs font-semibold text-red-600 hover:text-red-700 hover:underline disabled:opacity-50 cursor-pointer"
                  >
                    {data.status === "lapsed" ? "Policy Marked Lapsed" : "Customer Not Renewing / Mark Lapsed"}
                  </button>
                </div>
              </div>

              {/* 3. STATUS & OUTCOME RECORD */}
              <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-2xs space-y-4">
                <div className="flex items-center justify-between border-b border-neutral-100 pb-2">
                  <h3 className="text-xs font-bold text-neutral-900 uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                    3. Delivery Status &amp; Outcome
                  </h3>
                  <span className="text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-neutral-100 text-neutral-700">
                    Current: {data.status}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div>
                    <label className="block font-semibold text-neutral-700 mb-1">Tenure Status</label>
                    <select
                      value={statusVal}
                      onChange={(e) => setStatusVal(e.target.value)}
                      className="w-full h-8 px-2 rounded-lg border border-neutral-200 bg-white text-xs font-medium focus:ring-1 focus:ring-neutral-900 outline-none"
                    >
                      <option value="draft">Draft / Ingestion</option>
                      <option value="comparing">Comparing (Sourcing Quotes)</option>
                      <option value="sent">Sent to Client (Proposal Pending)</option>
                      <option value="hit">HIT — Policy Won / Bound</option>
                      <option value="miss">MISS — Lost to Competitor / Declined</option>
                      <option value="closed">Closed</option>
                    </select>
                  </div>

                  {statusVal === "hit" && (
                    <>
                      <div>
                        <label className="block font-semibold text-neutral-700 mb-1">Won Premium (RM)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={wonPremium}
                          onChange={(e) => setWonPremium(e.target.value)}
                          placeholder="e.g. 995.00"
                          className="w-full h-8 px-2 rounded-lg border border-neutral-200 bg-white text-xs font-medium focus:ring-1 focus:ring-neutral-900 outline-none"
                        />
                      </div>
                      <div>
                        <label className="block font-semibold text-neutral-700 mb-1">Winning Quotation Ref</label>
                        <input
                          type="text"
                          value={winningRef}
                          onChange={(e) => setWinningRef(e.target.value)}
                          placeholder="e.g. RL260000101"
                          className="w-full h-8 px-2 rounded-lg border border-neutral-200 bg-white text-xs font-medium focus:ring-1 focus:ring-neutral-900 outline-none"
                        />
                      </div>
                    </>
                  )}

                  {statusVal === "miss" && (
                    <div className="sm:col-span-2">
                      <label className="block font-semibold text-neutral-700 mb-1">Miss Reason</label>
                      <input
                        type="text"
                        value={missReason}
                        onChange={(e) => setMissReason(e.target.value)}
                        placeholder="e.g. Customer renewed direct / Competitor price cheaper by RM50"
                        className="w-full h-8 px-2 rounded-lg border border-neutral-200 bg-white text-xs font-medium focus:ring-1 focus:ring-neutral-900 outline-none"
                      />
                    </div>
                  )}

                  <div className="sm:col-span-2">
                    <label className="block font-semibold text-neutral-700 mb-1">Notes / Delivery Details</label>
                    <textarea
                      rows={2}
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="e.g. Sent quote via WhatsApp on 15/06/2026. Customer requested STMB with windscreen."
                      className="w-full p-2 rounded-lg border border-neutral-200 bg-white text-xs font-medium focus:ring-1 focus:ring-neutral-900 outline-none"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <Button
                    size="sm"
                    disabled={savingStatus}
                    onClick={handleSaveStatus}
                    className="h-8 px-4 text-xs font-semibold"
                  >
                    {savingStatus ? "Saving..." : "Update Tenure Outcome"}
                  </Button>
                </div>
              </div>

              {/* 4. AUDIT & ACTIVITY TIMELINE */}
              <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-2xs space-y-3">
                <div className="flex items-center justify-between border-b border-neutral-100 pb-2">
                  <h3 className="text-xs font-bold text-neutral-900 uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-neutral-400"></span>
                    4. Chronological Activity Log
                  </h3>
                  <span className="text-[11px] text-neutral-400 font-medium">
                    {data.activities?.length || 0} events
                  </span>
                </div>

                <div className="space-y-2 pt-1">
                  {(!data.activities || data.activities.length === 0) ? (
                    <div className="text-xs text-neutral-400 py-3 text-center bg-neutral-50/60 rounded-lg">
                      No activity entries recorded yet for this tenure.
                    </div>
                  ) : (
                    data.activities.map((act: any) => {
                      let timeStr = "";
                      if (act.created_at) {
                        try {
                          timeStr = new Date(act.created_at).toLocaleString("en-US", {
                            year: "numeric",
                            month: "numeric",
                            day: "numeric",
                            hour: "numeric",
                            minute: "2-digit",
                            second: "2-digit",
                            hour12: true,
                          });
                        } catch {
                          timeStr = act.created_at;
                        }
                      }
                      return (
                        <div key={act.id} className="flex items-start gap-2.5 text-xs py-2 border-b border-neutral-100 last:border-none">
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
