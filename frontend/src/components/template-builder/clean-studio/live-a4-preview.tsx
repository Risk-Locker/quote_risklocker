"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowClockwise,
  CaretDown,
  FilePdf,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
  ShieldCheck,
} from "@phosphor-icons/react";
import type { BlockTree, CustomerSessionPreview } from "./types";
import { fileUrl } from "@/lib/api";

interface LiveA4PreviewProps {
  tree: BlockTree;
  sessions: CustomerSessionPreview[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  lastUpdated: number;
}

export function LiveA4Preview({
  tree,
  sessions,
  activeSessionId,
  onSelectSession,
  lastUpdated,
}: LiveA4PreviewProps) {
  const [zoomScale, setZoomScale] = useState(0.48); // Fit A4 nicely in 400-500px column
  const [debouncedTree, setDebouncedTree] = useState<BlockTree>(tree);
  const [syncing, setSyncing] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(0);

  // Debounce tree update by 5 seconds with visible countdown
  useEffect(() => {
    setSyncing(true);
    setSecondsRemaining(5);

    const interval = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          setDebouncedTree(tree);
          setSyncing(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [tree, lastUpdated]);

  function handleInstantSync() {
    setDebouncedTree(tree);
    setSyncing(false);
    setSecondsRemaining(0);
  }

  const activeSession = useMemo(() => {
    if (!sessions.length) return null;
    return sessions.find((s) => s.id === activeSessionId) || sessions[0];
  }, [sessions, activeSessionId]);

  // Fallback quotation data if no sessions exist
  const quoteData = useMemo(() => {
    return {
      customer_name: activeSession?.customer_name || "CHENG TECK KIONG",
      vehicle_no: activeSession?.vehicle_no || "ANY 368",
      insurance_company: activeSession?.insurance_company || "BERJAYA SOMPO INSURANCE BERHAD",
      coverage_type: activeSession?.coverage_type || "Comprehensive",
      cover_period: activeSession?.cover_period || "04-06-2026 to 03-06-2027",
      car_model: activeSession?.car_model || "Tesla Model 3 Performance",
      engine_cc: activeSession?.engine_cc || "9.4 kW",
      ncd_percent: activeSession?.ncd_percent || "25.00%",
      valuation_type: activeSession?.valuation_type || "Market Value",
      authorized_driver: activeSession?.authorized_driver || "All Driver",
      excess_amount: activeSession?.excess_amount || "RM 0.00",
      coverage_amount: activeSession?.coverage_amount || "RM 199,000.00",
      premium: activeSession?.premium || "3,758.21",
      roadtax_runner:
        (parseFloat(activeSession?.roadtax || "20") + parseFloat(activeSession?.runner_fee || "10")).toFixed(2),
      total_amount: activeSession?.total_amount || "4,073.21",
      valid_until: activeSession?.valid_until || "14 Days",
      quotation_reference: activeSession?.quotation_reference || "RL260000313",
      benefits: activeSession?.benefits || [
        { id: "b1", label: "Panel Workmanship Warranty", value: "12 Months", is_extra: false, description: "Repair guarantee at panel workshops." },
        { id: "b2", label: "Emergency Towing Assistance", value: "Unlimited", is_extra: false, description: "24/7 unlimited distance breakdown towing." },
        { id: "b3", label: "Legal Defense Costs", value: "RM 2,000", is_extra: false, description: "Legal fees protection up to RM 2,000." },
        { id: "b4", label: "All Drivers Excess Waiver", value: "Included", is_extra: false, description: "Waives RM400 compulsory excess for unnamed drivers." },
        { id: "b5", label: "Special Perils (Flood & Storm)", value: "RM 199,000", is_extra: false, description: "Full natural disaster flood and typhoon cover." },
        { id: "b6", label: "Legal Liability of Passengers", value: "Included", is_extra: false, description: "Third party negligence cover." },
        { id: "b7", label: "Roadside Assistance Helpline", value: "24/7", is_extra: false, description: "Jumpstart, tyre puncture, fuel delivery." },
        { id: "b8", label: "Windscreen Coverage", value: "RM 4,000", is_extra: true, cost_value: "RM 150.00", description: "Front & rear glass replacement without NCD loss." },
        { id: "b9", label: "Driver PA / Personal Accident", value: "RM 20,000", is_extra: true, cost_value: "RM 150.00", description: "Accidental medical reimbursement and disability cover." },
      ],
    };
  }, [activeSession]);

  function resolveValue(variableId?: string): string {
    if (!variableId) return "";
    return (quoteData as any)[variableId] || `{${variableId}}`;
  }

  return (
    <div className="w-[480px] shrink-0 border-r border-slate-200 bg-slate-900 flex flex-col h-full overflow-hidden select-none">
      {/* Top Controls Toolbar */}
      <div className="p-2.5 border-b border-slate-800 bg-slate-950 shrink-0 flex items-center justify-between text-white">
        <div className="flex items-center gap-2 min-w-0">
          <FilePdf size={16} weight="bold" className="text-emerald-400 shrink-0" />
          <div className="min-w-0">
            <div className="text-[11px] font-bold tracking-tight truncate">
              Live Quotation (A4 Preview)
            </div>
            <div className="text-[9.5px] text-slate-400 flex items-center gap-2">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  syncing ? "bg-amber-400 animate-ping" : "bg-emerald-400"
                }`}
              />
              <span>{syncing ? `Updating in ${secondsRemaining}s...` : "Live Synced"}</span>
              {syncing && (
                <button
                  type="button"
                  onClick={handleInstantSync}
                  className="px-1.5 py-0.5 rounded bg-blue-600 hover:bg-blue-500 text-[9px] text-white font-bold ml-1 transition-colors"
                >
                  Update Now
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1 bg-slate-800 rounded p-0.5">
          <button
            type="button"
            onClick={() => setZoomScale((z) => Math.max(0.3, z - 0.05))}
            className="p-1 rounded text-slate-400 hover:text-white"
            title="Zoom Out"
          >
            <MagnifyingGlassMinus size={13} weight="bold" />
          </button>
          <span className="text-[10px] font-mono px-1 text-slate-300">
            {Math.round(zoomScale * 100)}%
          </span>
          <button
            type="button"
            onClick={() => setZoomScale((z) => Math.min(0.8, z + 0.05))}
            className="p-1 rounded text-slate-400 hover:text-white"
            title="Zoom In"
          >
            <MagnifyingGlassPlus size={13} weight="bold" />
          </button>
        </div>
      </div>

      {/* Real Customer Session Picker Dropdown */}
      <div className="px-3 py-1.5 bg-slate-800/90 border-b border-slate-700/80 flex items-center justify-between">
        <span className="text-[10px] text-slate-300 font-semibold">Preview Session:</span>
        <select
          value={activeSession?.id || ""}
          onChange={(e) => onSelectSession(e.target.value)}
          className="bg-slate-900 text-white text-[11px] font-medium rounded border border-slate-700 px-2 py-0.5 max-w-[280px] truncate focus:outline-hidden"
        >
          {sessions.map((s) => (
            <option key={s.id} value={s.id}>
              {s.vehicle_no || "Blank"} · {s.insurance_company || "Insurer"} · {s.customer_name || "Customer"}
            </option>
          ))}
          {!sessions.length && <option value="">ANY 368 · Berjaya Sompo · Tesla Model 3</option>}
        </select>
      </div>

      {/* Scaled A4 Document View Container */}
      <div className="flex-1 overflow-auto p-4 flex justify-center items-start">
        <div
          style={{
            width: "794px",
            height: "1123px",
            transform: `scale(${zoomScale})`,
            transformOrigin: "top center",
          }}
          className="bg-white text-slate-900 shadow-2xl relative shrink-0 p-8 flex flex-col justify-between"
        >
          {/* 1. Header Section */}
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div className="flex items-center gap-2">
              <img
                src="/assets/risklocker_logo_cropped.png"
                alt="RiskLocker"
                className="w-7 h-7 object-contain"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = "none";
                }}
              />
              <span className="text-base font-extrabold tracking-tight text-slate-900">
                Motor Insurance <span className="text-red-600">Quotation</span>
              </span>
            </div>

            <div className="text-right text-[10px] leading-tight space-y-0.5">
              <div>
                <span className="text-slate-500 font-medium">Quotation Ref: </span>
                <span className="font-bold text-red-600 font-mono">
                  {quoteData.quotation_reference}
                </span>
              </div>
              <div>
                <span className="text-slate-500 font-medium">Vehicle No: </span>
                <span className="font-bold text-red-600 font-mono">{quoteData.vehicle_no}</span>
              </div>
              <div className="font-extrabold text-slate-800 uppercase tracking-tight">
                INSURER: <span className="text-red-600">{quoteData.insurance_company}</span>
              </div>
            </div>
          </div>

          {/* 2. Body Section: Vehicle Specs & Right QR Bank Box */}
          <div className="grid grid-cols-12 gap-3 my-2 items-start">
            {/* Left 8 Cols: Specs Table with Unified Outer Border */}
            <div className="col-span-8 rounded border border-slate-300 bg-white overflow-hidden shadow-2xs">
              <div className="bg-slate-900 text-white text-[10px] font-bold px-3 py-1 flex items-center justify-between">
                <span>Coverage & Vehicle Information / 车辆及保单资料</span>
              </div>

              <div className="p-2 space-y-1 text-[9.5px]">
                <div className="flex justify-between border-b border-slate-100 pb-0.5">
                  <span className="font-semibold text-slate-600">Customer / 客户姓名</span>
                  <span className="font-bold text-red-600 uppercase">{quoteData.customer_name}</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 pb-0.5">
                  <span className="font-semibold text-slate-600">Coverage Type / 保单种类</span>
                  <span className="font-bold text-slate-800">{quoteData.coverage_type}</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 pb-0.5">
                  <span className="font-semibold text-slate-600">Car Model / 车型</span>
                  <span className="font-bold text-red-600">{quoteData.car_model}</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 pb-0.5">
                  <span className="font-semibold text-slate-600">Engine Capacity / 发动机排量</span>
                  <span className="font-bold text-slate-800">{quoteData.engine_cc}</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 pb-0.5">
                  <span className="font-semibold text-slate-600">NCD</span>
                  <span className="font-bold text-red-600">{quoteData.ncd_percent}</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 pb-0.5">
                  <span className="font-semibold text-slate-600">Cover of Period / 保单期限</span>
                  <span className="font-bold text-red-600 font-mono">{quoteData.cover_period}</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 pb-0.5">
                  <span className="font-semibold text-slate-600">Valuation Type / 估价方式</span>
                  <span className="font-bold text-slate-800">{quoteData.valuation_type}</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 pb-0.5">
                  <span className="font-semibold text-slate-600">Authorised Driver / 授权驾驶人</span>
                  <span className="font-bold text-red-600">{quoteData.authorized_driver}</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 pb-0.5">
                  <span className="font-semibold text-slate-600">Policy Excess / 自负额</span>
                  <span className="font-bold text-red-600">{quoteData.excess_amount}</span>
                </div>
                <div className="flex justify-between border-b border-slate-200 pb-1">
                  <span className="font-bold text-slate-800">Vehicle Sum Insured / 车辆保额</span>
                  <span className="font-extrabold text-red-600">{quoteData.coverage_amount}</span>
                </div>

                {/* Premium & Total Row with Combined Roadtax & Runner Fee */}
                <div className="bg-slate-50 p-2 rounded border border-slate-200 space-y-1">
                  <div className="flex justify-between text-[9px] text-slate-600 font-medium">
                    <span>Insurance Premium / 保费 :</span>
                    <span className="font-bold text-slate-800">RM {quoteData.premium}</span>
                  </div>
                  <div className="flex justify-between text-[9px] text-slate-600 font-medium">
                    <span>Roadtax and Runner Fee / 路税及服务费 :</span>
                    <span className="font-bold text-slate-800">RM {quoteData.roadtax_runner}</span>
                  </div>
                  <div className="flex justify-between text-[11px] font-extrabold text-slate-900 border-t border-slate-300 pt-1">
                    <span>TOTAL PAYABLE / 应付总额 :</span>
                    <span className="text-red-600 text-sm">RM {quoteData.total_amount}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right 4 Cols: Bank QR Image Flush Right */}
            <div className="col-span-4 rounded border border-slate-300 overflow-hidden bg-slate-900 h-full flex items-center justify-center">
              <img
                src="/assets/bank_qr_layout_dark.jpg"
                alt="Bank Details & DuitNow QR"
                className="w-full h-auto object-contain"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = "none";
                }}
              />
            </div>
          </div>

          {/* 3. Benefits Section: Rendered using Authentic Masonry Flow */}
          <div className="my-1 space-y-2">
            <div className="bg-slate-900 text-white text-[10px] font-bold px-3 py-1 rounded-sm flex items-center justify-between">
              <span>{quoteData.insurance_company} Comprehensive Benefits</span>
            </div>

            {/* Authentic Masonry Flow Cards */}
            <div className="grid grid-cols-3 gap-2">
              {quoteData.benefits.slice(0, 9).map((b) => (
                <div
                  key={b.id}
                  className="rounded border border-slate-200 bg-white p-2 shadow-2xs flex flex-col justify-between min-h-[58px]"
                >
                  <div className="flex items-start justify-between gap-1">
                    <span className="text-[9px] font-bold text-slate-800 line-clamp-1 leading-tight">
                      {b.label}
                    </span>
                    <span
                      className={`text-[8.5px] font-extrabold px-1 py-0.2 rounded shrink-0 ${
                        b.is_extra
                          ? "bg-amber-100 text-amber-800"
                          : "bg-emerald-50 text-emerald-700"
                      }`}
                    >
                      {b.value || "Included"}
                    </span>
                  </div>
                  <p className="text-[8px] text-slate-400 line-clamp-2 mt-1 leading-snug">
                    {b.description || "Comprehensive policy protection."}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* 4. Footer Section */}
          <div className="border-t border-slate-200 pt-2 text-center text-[8px] text-slate-400">
            * Terms & Conditions Apply | Quotation Validity: {quoteData.valid_until} | RiskLocker Auto Protection
          </div>
        </div>
      </div>
    </div>
  );
}
