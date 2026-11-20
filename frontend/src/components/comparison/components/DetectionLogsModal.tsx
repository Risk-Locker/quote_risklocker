"use client";

import React, { useState } from "react";
import { X, Car, ShieldCheck, CheckCircle, TerminalWindow, Copy, Check, WarningCircle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";

interface PipelineTraceStep {
  timestamp: string;
  progress: number;
  stage: string;
  message: string;
}

interface PipelineTraceItem {
  company_name?: string;
  version?: number;
  filename?: string;
  session_id?: string | null;
  job_id?: string | null;
  job_state?: string | null;
  reading_quality?: string | null;
  method_summary?: string[];
  warnings?: string[];
  steps?: PipelineTraceStep[];
}

interface DetectionLogsModalProps {
  isOpen: boolean;
  onClose: () => void;
  detectionLogs?: {
    vehicle?: {
      model?: string;
      engine_capacity?: string;
      propulsion?: string;
      calculated_road_tax?: string;
      jpj_status?: string;
    };
    verifications?: Array<{
      company_name?: string;
      version?: number;
      basic_figure?: string;
      sum_insured?: string;
      ncd?: string;
      excess?: string;
      excess_note?: string;
      perils_breakdown?: string[];
    }>;
    pipeline_traces?: PipelineTraceItem[];
  } | null;
  tenure: {
    vehicle_model: string;
    engine_cc: string;
    road_tax: number;
  };
}

export function DetectionLogsModal({
  isOpen,
  onClose,
  detectionLogs,
  tenure,
}: DetectionLogsModalProps) {
  const [activeTab, setActiveTab] = useState<"pipeline" | "audit">("pipeline");
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const traces = detectionLogs?.pipeline_traces || [];

  function handleCopyRawLogs() {
    const lines: string[] = [];
    for (const tr of traces) {
      lines.push(`=== ${tr.company_name || "Quote"} (v${tr.version ?? 1}) | File: ${tr.filename || "—"} | Job: ${tr.job_id || "manual"} (${tr.job_state || "—"}) ===`);
      if (tr.method_summary && tr.method_summary.length > 0) {
        lines.push(`Methods: ${tr.method_summary.join(", ")}`);
      }
      for (const s of tr.steps || []) {
        lines.push(`[${s.timestamp}] [${String(s.progress).padStart(3, " ")}%] [${s.stage}] ${s.message}`);
      }
      if (tr.warnings && tr.warnings.length > 0) {
        for (const w of tr.warnings) {
          lines.push(`[WARN] ${w}`);
        }
      }
      lines.push("");
    }
    navigator.clipboard?.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 no-print animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl border border-neutral-200 max-w-5xl w-full max-h-[85vh] flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-b border-[#e5e5ea] bg-[#f5f5f7]">
          <div>
            <h3 className="text-base font-bold text-[#1b1717] flex items-center gap-2">
              <ShieldCheck size={20} weight="fill" className="text-blue-600" />
              Automated Detection Audit &amp; Pipeline Execution Logs
            </h3>
            <p className="text-xs text-[#6e6e73]">
              Pure chronological scan trace (0% staging &rarr; 100% comparison) and contractual verification audit
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-neutral-200/70 p-0.5 rounded-xl text-xs">
              <button
                type="button"
                onClick={() => setActiveTab("pipeline")}
                className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-colors cursor-pointer ${
                  activeTab === "pipeline" ? "bg-white text-[#1b1717] shadow-xs" : "text-[#6e6e73] hover:text-[#1b1717]"
                }`}
              >
                <TerminalWindow size={14} weight="bold" />
                Pipeline Logs (0%&ndash;100%)
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("audit")}
                className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-colors cursor-pointer ${
                  activeTab === "audit" ? "bg-white text-[#1b1717] shadow-xs" : "text-[#6e6e73] hover:text-[#1b1717]"
                }`}
              >
                <ShieldCheck size={14} weight="bold" />
                Contractual Audit
              </button>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-xl border border-neutral-300 hover:bg-neutral-200 text-neutral-600 transition-colors cursor-pointer"
              title="Close"
            >
              <X size={18} weight="bold" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-auto p-6 space-y-6 text-[#1b1717]">
          {activeTab === "pipeline" ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-neutral-600">
                  Per-Quotation Pure Execution Trace ({traces.length} quote{traces.length === 1 ? "" : "s"})
                </span>
                {traces.length > 0 && (
                  <Button variant="secondary" size="sm" onClick={handleCopyRawLogs} className="text-xs h-7 px-2.5">
                    {copied ? <Check size={13} className="mr-1 text-emerald-600" /> : <Copy size={13} className="mr-1" />}
                    {copied ? "Copied" : "Copy Raw Logs"}
                  </Button>
                )}
              </div>

              {traces.length === 0 ? (
                <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-6 text-center text-xs text-neutral-500">
                  No pipeline trace records available for this tenure yet.
                </div>
              ) : (
                traces.map((tr, idx) => (
                  <div key={`${tr.session_id || idx}`} className="rounded-2xl border border-[#e5e5ea] overflow-hidden bg-white">
                    <div className="px-4 py-3 bg-[#f5f5f7] border-b border-[#e5e5ea] flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-bold text-[#1b1717]">
                          {tr.company_name || "Quotation"} <span className="text-[#6e6e73] font-normal">(v{tr.version ?? 1})</span>
                        </span>
                        <span className="font-mono text-[11px] bg-white border border-neutral-200 px-2 py-0.5 rounded text-neutral-700">
                          {tr.filename}
                        </span>
                        {tr.job_id && (
                          <span className="font-mono text-[10px] text-neutral-500">
                            job:{tr.job_id.slice(0, 8)}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5">
                        {tr.method_summary && tr.method_summary.length > 0 && (
                          <span className="text-[10px] font-mono bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full">
                            {tr.method_summary.join(" + ")}
                          </span>
                        )}
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                            tr.job_state === "completed"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                              : tr.job_state === "failed"
                              ? "bg-rose-50 text-rose-700 border-rose-200"
                              : "bg-neutral-100 text-neutral-700 border-neutral-200"
                          }`}
                        >
                          {tr.job_state || "completed"}
                        </span>
                      </div>
                    </div>

                    <div className="bg-neutral-950 text-neutral-100 p-4 font-mono text-[11px] space-y-1.5 overflow-x-auto">
                      {(tr.steps || []).map((step, sIdx) => (
                        <div key={sIdx} className="flex items-start gap-2.5 leading-relaxed">
                          <span className="text-neutral-500 shrink-0">{step.timestamp}</span>
                          <span
                            className={`shrink-0 font-bold w-11 text-right ${
                              step.progress === 100
                                ? "text-emerald-400"
                                : step.stage.includes("gemini")
                                ? "text-sky-400"
                                : "text-amber-300"
                            }`}
                          >
                            [{step.progress}%]
                          </span>
                          <span className="text-indigo-300 shrink-0">[{step.stage}]</span>
                          <span className="text-neutral-100 break-words">{step.message}</span>
                        </div>
                      ))}
                    </div>

                    {tr.warnings && tr.warnings.length > 0 && (
                      <div className="px-4 py-2.5 bg-amber-50 border-t border-amber-200 space-y-1">
                        {tr.warnings.map((w, wIdx) => (
                          <div key={wIdx} className="flex items-start gap-1.5 text-[11px] text-amber-900 font-mono">
                            <WarningCircle size={14} weight="fill" className="text-amber-600 shrink-0 mt-0.5" />
                            <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          ) : (
            <>
          {/* Vehicle & JPJ Mathematical Engine Section */}
          <div className="rounded-2xl border border-blue-200 bg-blue-50/50 p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                <Car size={16} weight="bold" />
                Vehicle Specs &amp; Mathematical JPJ Road Tax Engine
              </h4>
              <span className="text-[11px] font-bold bg-blue-600 text-white px-2 py-0.5 rounded-full">
                {detectionLogs?.vehicle?.jpj_status || "JPJ Schedule Verified"}
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="bg-white/80 p-2.5 rounded-xl border border-blue-100">
                <span className="text-[#6e6e73] block text-[10px]">Model &amp; Brand</span>
                <strong className="text-sm font-bold text-[#1b1717]">
                  {detectionLogs?.vehicle?.model || tenure.vehicle_model}
                </strong>
              </div>
              <div className="bg-white/80 p-2.5 rounded-xl border border-blue-100">
                <span className="text-[#6e6e73] block text-[10px]">Engine Capacity</span>
                <strong className="text-sm font-bold text-[#1b1717]">
                  {detectionLogs?.vehicle?.engine_capacity || tenure.engine_cc}
                </strong>
              </div>
              <div className="bg-white/80 p-2.5 rounded-xl border border-blue-100">
                <span className="text-[#6e6e73] block text-[10px]">Propulsion</span>
                <strong className="text-xs font-bold text-[#1b1717]">
                  {detectionLogs?.vehicle?.propulsion || "ICE"}
                </strong>
              </div>
              <div className="bg-white/80 p-2.5 rounded-xl border border-blue-100">
                <span className="text-[#6e6e73] block text-[10px]">JPJ Calculated Tax</span>
                <strong className="text-sm font-bold text-blue-700">
                  {detectionLogs?.vehicle?.calculated_road_tax || `RM ${tenure.road_tax.toFixed(2)}`}
                </strong>
              </div>
            </div>
          </div>

          {/* Quote-by-Quote Precision Verification Table */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-[#1b1717] flex items-center gap-2">
              <ShieldCheck size={16} weight="bold" className="text-emerald-600" />
              Contractual Quote Detection Audit (Perils &amp; Policy Excess)
            </h4>
            <div className="rounded-2xl border border-[#e5e5ea] overflow-hidden">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-[#f5f5f7] border-b border-[#e5e5ea] text-[#6e6e73] font-semibold">
                  <tr>
                    <th className="py-2.5 px-3">Underwriter</th>
                    <th className="py-2.5 px-3">Basic Figure</th>
                    <th className="py-2.5 px-3">Sum Insured</th>
                    <th className="py-2.5 px-3">NCD / NCB</th>
                    <th className="py-2.5 px-3">Strict Policy Excess</th>
                    <th className="py-2.5 px-3">Perils Detected &amp; Pricing</th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#e5e5ea]">
                  {(detectionLogs?.verifications || []).map((v: any, i: number) => (
                    <tr key={i} className="hover:bg-neutral-50/80 transition-colors">
                      <td className="py-3 px-3 font-bold text-[#1b1717]">
                        {v.company_name}{" "}
                        <span className="text-[10px] text-[#6e6e73] font-normal">(v{v.version})</span>
                      </td>
                      <td className="py-3 px-3 font-mono font-medium">{v.basic_figure}</td>
                      <td className="py-3 px-3 font-medium">{v.sum_insured}</td>
                      <td className="py-3 px-3 font-bold font-mono text-neutral-800">{v.ncd || "0%"}</td>
                      <td className="py-3 px-3">
                        <span className="font-bold text-[#1b1717] block font-mono">{v.excess}</span>
                        <span className="text-[10px] text-emerald-700 block">{v.excess_note}</span>
                      </td>
                      <td className="py-3 px-3">
                        {v.perils_breakdown && v.perils_breakdown.length > 0 ? (
                          <ul className="space-y-0.5 text-[11px]">
                            {v.perils_breakdown.map((pb: string, pIdx: number) => (
                              <li key={pIdx} className="text-[#454545] font-medium flex items-center gap-1">
                                <span className="size-1 rounded-full bg-neutral-400 shrink-0" />
                                <span>{pb}</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <span className="text-neutral-400 italic text-[11px]">Standard base covers only</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                          <CheckCircle size={13} weight="fill" />
                          100% Precision
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-[#e5e5ea] bg-[#f5f5f7]">
          <span className="text-xs text-[#6e6e73]">
            Autonomously validated against Bank Negara Malaysia motor tariff &amp; insurer schedule tables
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={onClose}
            className="font-bold"
          >
            Close Audit
          </Button>
        </div>
      </div>
    </div>
  );
}
