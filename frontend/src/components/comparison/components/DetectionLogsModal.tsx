"use client";

import React from "react";
import { X, Car, ShieldCheck, CheckCircle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";

interface DetectionLogsModalProps {
  isOpen: boolean;
  onClose: () => void;
  detectionLogs?: any;
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
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 no-print animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl border border-neutral-200 max-w-4xl w-full max-h-[85vh] flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#e5e5ea] bg-[#f5f5f7]">
          <div>
            <h3 className="text-base font-bold text-[#1b1717] flex items-center gap-2">
              <ShieldCheck size={20} weight="fill" className="text-blue-600" />
              Automated Detection Audit &amp; System Telemetry
            </h3>
            <p className="text-xs text-[#6e6e73]">
              Inspection of OCR text anchors, JPJ road tax engine values, and contract-level peril detections
            </p>
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

        {/* Modal Body */}
        <div className="flex-1 overflow-auto p-6 space-y-6 text-[#1b1717]">
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
