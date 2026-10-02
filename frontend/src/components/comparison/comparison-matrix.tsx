"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import type { Route } from "next";
import {
  Check,
  Printer,
  Plus,
  PencilSimple,
  Trash,
  Star,
  ChatCircleDots,
  ArrowRight,
  ShieldCheck,
  FilePdf,
  X,
  User,
  IdentificationCard,
  Car,
  CalendarBlank,
  MapPin,
  Phone,
  Envelope,
  FloppyDisk,
  SidebarSimple,
  UploadSimple,
  CircleNotch,
  Columns,
  ArrowsClockwise,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ManualQuoteModal } from "./manual-quote-modal";
import { decodeMalaysianIC } from "@/lib/mykad";

interface ComparisonMatrixProps {
  tenureId: string;
}

interface TenureSpec {
  id: string;
  vehicle_no: string;
  customer_name: string;
  ic_no?: string;
  formatted_ic?: string;
  birth_date?: string;
  customer_age?: number;
  customer_gender?: string;
  nric_state?: string;
  phone?: string;
  email?: string;
  address?: string;
  engine_no?: string;
  chassis_no?: string;
  manufacture_year?: number;
  seating_capacity?: string;
  coverage_start_date: string;
  coverage_end_date: string;
  coverage_period_formatted: string;
  expiry_month: string;
  status: string;
  road_tax: number;
  runner_fee: number;
  runner_fee_type?: string;
  fixed_costs_total: number;
  windscreen_target: number | null;
  ncd_percentage: number | null;
  engine_cc: string;
  vehicle_model: string;
  vehicle_type: string;
}

interface ComparisonEntry {
  id: string;
  tenure_id: string;
  session_id: string | null;
  company_name: string;
  company_id: string | null;
  sum_insured: number;
  valuation_type: string;
  motor_premium: number;
  road_tax: number;
  runner_fee: number;
  total_payable: number;
  rounded_total_payable?: number | null;
  exact_total_payable?: number | null;
  towing_limit: string;
  towing_km?: string;
  agreed_value: boolean;
  waiver_betterment: boolean;
  betterment_rate?: number;
  betterment_display?: string;
  excess: number;
  rate_factor?: number | null;
  rate_factor_formatted?: string | null;
  rate_percentage: number | null;
  windscreen_sum_insured: number | null;
  special_perils: string | null;
  llp_llop: string | null;
  is_recommended: boolean;
  is_manual: boolean;
  sort_order: number;
  rank?: number;
  version?: number;
  uploaded_at?: string;
  notes: string | null;
}

export function ComparisonMatrix({ tenureId }: ComparisonMatrixProps) {
  const router = useRouter();
  const [data, setData] = useState<{
    tenure: TenureSpec;
    entries: ComparisonEntry[];
    previous_policy: any;
    recommended_sum_insured: Record<string, number>;
    ncd: { current: number | null; next: number | null };
    pending_jobs_count?: number;
    vehicle_age?: number;
    date_conflict?: {
      has_conflict: boolean;
      majority_date?: string;
      unique_dates?: string[];
      message?: string;
    };
    generated_quotations?: Array<{
      session_id: string;
      reference_number: string;
      quotation_ref?: string;
      company_name: string;
      total_payable: number;
      sum_insured: number;
      status: string;
      version_number?: number;
      created_at: string;
      has_pdf: boolean;
    }>;
  } | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedWhatsapp, setCopiedWhatsapp] = useState(false);
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState<ComparisonEntry | null>(null);

  // Source PDF Viewer State & Resizer/Docking
  const [activePdfSession, setActivePdfSession] = useState<{
    sessionId: string;
    companyName: string;
  } | null>(null);

  const [pdfPanelWidth, setPdfPanelWidth] = useState<number>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("rl_comparison_pdf_width");
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= 340 && parsed <= 880) return parsed;
      }
    }
    return 600;
  });

  const [pdfDockMode, setPdfDockMode] = useState<"docked" | "floating">(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("rl_comparison_pdf_dock");
      if (saved === "docked" || saved === "floating") return saved;
    }
    return "floating";
  });

  const [isResizing, setIsResizing] = useState(false);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = Math.max(340, Math.min(880, window.innerWidth - e.clientX));
      setPdfPanelWidth(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      localStorage.setItem("rl_comparison_pdf_width", String(pdfPanelWidth));
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing, pdfPanelWidth]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("rl_comparison_pdf_dock", pdfDockMode);
    }
  }, [pdfDockMode]);

  // Company-Level Nested Quotations State
  const [activeQuoteByCompany, setActiveQuoteByCompany] = useState<Record<string, number>>({});
  const [expandedCompanies, setExpandedCompanies] = useState<Record<string, boolean>>({});

  // Edit state for Fixed Costs & Customer/Vehicle Specs
  const [editingFixedCosts, setEditingFixedCosts] = useState(false);
  const [customerNameInput, setCustomerNameInput] = useState("");
  const [icNoInput, setIcNoInput] = useState("");
  const [roadTaxInput, setRoadTaxInput] = useState("70");
  const [runnerFeeInput, setRunnerFeeInput] = useState("50");
  const [windscreenInput, setWindscreenInput] = useState("1700");
  const [engineCcInput, setEngineCcInput] = useState("");
  const [engineNoInput, setEngineNoInput] = useState("");
  const [chassisNoInput, setChassisNoInput] = useState("");
  const [vehicleModelInput, setVehicleModelInput] = useState("");
  const [manufactureYearInput, setManufactureYearInput] = useState("");
  const [startDateInput, setStartDateInput] = useState("");
  const [endDateInput, setEndDateInput] = useState("");
  const [savingFixedCosts, setSavingFixedCosts] = useState(false);
  const [selectingWinnerId, setSelectingWinnerId] = useState<string | null>(null);
  const [generatingQuoteEntryId, setGeneratingQuoteEntryId] = useState<string | null>(null);
  const [generatingAllQuotes, setGeneratingAllQuotes] = useState(false);

  // Bi-directional Date Helpers (+1yr -1d / -1yr +1d)
  const handleStartDateChange = (newStart: string) => {
    setStartDateInput(newStart);
    if (!newStart) return;
    try {
      const parts = newStart.split("-");
      if (parts.length === 3) {
        const y = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10);
        const d = parseInt(parts[2], 10);
        if (!isNaN(y) && !isNaN(m) && !isNaN(d)) {
          const dt = new Date(Date.UTC(y, m - 1, d));
          dt.setUTCFullYear(dt.getUTCFullYear() + 1);
          dt.setUTCDate(dt.getUTCDate() - 1);
          setEndDateInput(dt.toISOString().split("T")[0]);
        }
      }
    } catch {
      // ignore parsing error
    }
  };

  const handleEndDateChange = (newEnd: string) => {
    setEndDateInput(newEnd);
    if (!newEnd) return;
    try {
      const parts = newEnd.split("-");
      if (parts.length === 3) {
        const y = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10);
        const d = parseInt(parts[2], 10);
        if (!isNaN(y) && !isNaN(m) && !isNaN(d)) {
          const dt = new Date(Date.UTC(y, m - 1, d));
          dt.setUTCDate(dt.getUTCDate() + 1);
          dt.setUTCFullYear(dt.getUTCFullYear() - 1);
          setStartDateInput(dt.toISOString().split("T")[0]);
        }
      }
    } catch {
      // ignore parsing error
    }
  };

  const populateEditInputs = (tenure: TenureSpec) => {
    setCustomerNameInput(tenure.customer_name || "");
    setIcNoInput(tenure.ic_no || "");
    setRoadTaxInput(String(tenure.road_tax));
    setRunnerFeeInput(String(tenure.runner_fee));
    setWindscreenInput(String(tenure.windscreen_target || "1700"));
    setEngineCcInput(tenure.engine_cc || "");
    setEngineNoInput(tenure.engine_no || "");
    setChassisNoInput(tenure.chassis_no || "");
    setVehicleModelInput(tenure.vehicle_model || "");
    setManufactureYearInput(tenure.manufacture_year ? String(tenure.manufacture_year) : "");
    if (tenure.coverage_start_date) {
      setStartDateInput(tenure.coverage_start_date.split("T")[0]);
    }
    if (tenure.coverage_end_date) {
      setEndDateInput(tenure.coverage_end_date.split("T")[0]);
    }
  };

  const fetchComparison = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      setError(null);
      const json = await api<any>(`/comparison/${tenureId}`);
      setData(json);
      populateEditInputs(json.tenure);
    } catch (err: any) {
      setError(err.message || "Failed to load comparison");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const searchParams = useSearchParams();
  const isFromUpload = searchParams.get("from_upload") === "true";
  const [isCompilingBatch, setIsCompilingBatch] = useState(isFromUpload);

  useEffect(() => {
    if (tenureId) {
      fetchComparison();
    }
  }, [tenureId]);

  // Live polling for remaining background batch extractions
  useEffect(() => {
    if (!tenureId) return;
    const shouldPoll = isFromUpload || (data?.pending_jobs_count !== undefined && data.pending_jobs_count > 0);
    if (!shouldPoll) return;

    let count = 0;
    const interval = setInterval(() => {
      count++;
      fetchComparison(true);
      if (count >= 12) {
        clearInterval(interval);
        setIsCompilingBatch(false);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [tenureId, isFromUpload, data?.pending_jobs_count]);

  const handleSaveFixedCosts = async () => {
    try {
      setSavingFixedCosts(true);
      const updated = await api<any>(`/comparison/${tenureId}/fixed-costs`, {
        method: "POST",
        body: JSON.stringify({
          road_tax: parseFloat(roadTaxInput) || 0,
          runner_fee: parseFloat(runnerFeeInput) || 0,
          windscreen_target: parseFloat(windscreenInput) || 0,
          coverage_start_date: startDateInput || undefined,
          coverage_end_date: endDateInput || undefined,
          customer_name: customerNameInput || undefined,
          ic_no: icNoInput || undefined,
          engine_cc: engineCcInput || undefined,
          engine_no: engineNoInput || undefined,
          chassis_no: chassisNoInput || undefined,
          vehicle_model: vehicleModelInput || undefined,
          manufacture_year: parseInt(manufactureYearInput, 10) || undefined,
        }),
      });
      setData(updated);
      populateEditInputs(updated.tenure);
      setEditingFixedCosts(false);
    } catch (err: any) {
      alert("Error updating details: " + err.message);
    } finally {
      setSavingFixedCosts(false);
    }
  };

  const handleGenerateSingleQuote = async (entryId: string) => {
    try {
      setGeneratingQuoteEntryId(entryId);
      await api(`/comparison/${tenureId}/entry/${entryId}/generate-quote`, {
        method: "POST",
      });
      await fetchComparison(true);
    } catch (err: any) {
      alert("Failed to generate quotation: " + (err.message || String(err)));
    } finally {
      setGeneratingQuoteEntryId(null);
    }
  };

  const handleGenerateAllQuotes = async () => {
    try {
      setGeneratingAllQuotes(true);
      await api(`/comparison/${tenureId}/generate-all-quotes`, {
        method: "POST",
      });
      await fetchComparison(true);
    } catch (err: any) {
      alert("Failed to generate all quotations: " + (err.message || String(err)));
    } finally {
      setGeneratingAllQuotes(false);
    }
  };

  const handleSaveEntry = async (payload: any) => {
    const updated = await api<any>(`/comparison/${tenureId}/entry`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setData(updated);
  };

  const handleDeleteEntry = async (entryId: string) => {
    if (!confirm("Are you sure you want to remove this underwriter column from comparison?")) return;
    try {
      const updated = await api<any>(`/comparison/${tenureId}/entry/${entryId}`, {
        method: "DELETE",
      });
      setData(updated);
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleCopyWhatsapp = async () => {
    try {
      const json = await api<{ status: string; teaser_text: string }>(`/comparison/${tenureId}/whatsapp-teaser`);
      await navigator.clipboard.writeText(json.teaser_text);
      setCopiedWhatsapp(true);
      setTimeout(() => setCopiedWhatsapp(false), 3000);
    } catch (err: any) {
      alert("Failed to copy WhatsApp summary: " + err.message);
    }
  };

  const handleSelectWinner = async (entryId: string) => {
    try {
      setSelectingWinnerId(entryId);

      // Optimistic update so UI toggles instantly
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          entries: prev.entries.map((e) =>
            e.id === entryId ? { ...e, is_recommended: !e.is_recommended } : e
          ),
        };
      });

      await api<any>(`/comparison/${tenureId}/winner`, {
        method: "POST",
        body: JSON.stringify({ entry_id: entryId }),
      });

      await fetchComparison(true);
    } catch (err: any) {
      alert("Error updating winner selection: " + err.message);
      await fetchComparison(true);
    } finally {
      setSelectingWinnerId(null);
    }
  };

  // Decode Malaysian IC Date of Birth
  const decodedIc = useMemo(() => {
    return decodeMalaysianIC(data?.tenure?.ic_no);
  }, [data?.tenure?.ic_no]);

  // Group quotes by underwriter company name for nested quotations
  const companyGroups = useMemo(() => {
    const quoteEntries = data?.entries || [];
    const map = new Map<
      string,
      {
        companyName: string;
        companyId: string | null;
        entries: ComparisonEntry[];
        hasWinner: boolean;
      }
    >();
    for (const entry of quoteEntries) {
      const key = (entry.company_name || "Unknown Insurer").trim();
      if (!map.has(key)) {
        map.set(key, {
          companyName: key,
          companyId: entry.company_id,
          entries: [],
          hasWinner: false,
        });
      }
      const grp = map.get(key)!;
      grp.entries.push(entry);
      if (entry.is_recommended) {
        grp.hasWinner = true;
      }
    }
    return Array.from(map.values());
  }, [data?.entries]);

  if (loading && !data) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3">
        <div className="size-8 animate-spin rounded-full border-2 border-[#1b1717] border-t-transparent" />
        <p className="text-sm font-semibold text-[#6e6e73]">Compiling Marketing Comparison Matrix...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-center">
        <p className="text-sm font-semibold text-rose-700">{error || "Failed to load comparison"}</p>
        <Button variant="secondary" size="sm" onClick={() => fetchComparison()} className="mt-3">
          Retry
        </Button>
      </div>
    );
  }

  const { tenure, entries, previous_policy, recommended_sum_insured, ncd } = data;
  const winnerEntries = entries.filter((e) => e.is_recommended);
  const hasWinners = winnerEntries.length > 0;

  const renderUnderwriterCard = (
    entry: ComparisonEntry,
    group: {
      companyName: string;
      companyId: string | null;
      entries: ComparisonEntry[];
      hasWinner: boolean;
    },
    activeIdx: number,
    isSplit: boolean
  ) => {
    const isWinner = entry.is_recommended;
    const isViewingPdf = activePdfSession?.sessionId === entry.session_id;

    return (
      <div
        key={entry.id}
        className={`${
          isSplit ? "w-[260px]" : "w-[275px]"
        } shrink-0 rounded-2xl bg-white flex flex-col justify-between transition-all duration-200 relative break-inside-avoid print:w-auto print:flex-1 print:min-w-[200px] ${
          isViewingPdf
            ? "border-2 border-[#1b1717] ring-4 ring-[#1b1717]/15 shadow-xl scale-[1.01]"
            : isWinner
            ? "border-2 border-[#1b1717] shadow-lg ring-1 ring-black/5"
            : "border border-[#e5e5ea] shadow-xs hover:border-neutral-400"
        }`}
      >
        {/* Winner Top Ribbon */}
        {isWinner && (
          <div className="bg-[#1b1717] text-white text-xs font-bold px-3 py-1.5 flex items-center justify-between rounded-t-xl print:bg-black print:text-white">
            <span className="flex items-center gap-1.5">
              <Star weight="fill" size={14} className="text-amber-400" />
              RECOMMENDED WINNER
            </span>
            <ShieldCheck size={16} weight="bold" />
          </div>
        )}

        <div>
          {/* Header */}
          <div className={`p-4 border-b ${isWinner ? "border-[#e5e5ea] bg-[#f5f5f7]/60" : "border-[#e5e5ea]"}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <h3 className="font-bold text-sm text-[#1b1717] uppercase tracking-tight truncate">
                    {entry.company_name}
                  </h3>
                  {entry.rank === 1 && (
                    <span className="rounded bg-amber-400/25 text-amber-900 border border-amber-300 font-bold px-1.5 py-0.5 text-[10px]">
                      🏆 Rank #1 · Best Deal
                    </span>
                  )}
                  {entry.rank === 2 && (
                    <span className="rounded bg-neutral-100 text-neutral-700 border border-neutral-300 font-bold px-1.5 py-0.5 text-[10px]">
                      Rank #2
                    </span>
                  )}
                  {entry.rank === 3 && (
                    <span className="rounded bg-neutral-100 text-neutral-700 border border-neutral-300 font-bold px-1.5 py-0.5 text-[10px]">
                      Rank #3
                    </span>
                  )}
                  {entry.version && (
                    <span
                      className="rounded bg-blue-50 text-blue-700 border border-blue-200 font-bold px-1.5 py-0.5 text-[10px]"
                      title={entry.uploaded_at ? `Uploaded ${new Date(entry.uploaded_at).toLocaleTimeString()}` : undefined}
                    >
                      v{entry.version}
                    </span>
                  )}
                  {isViewingPdf && (
                    <span className="rounded bg-[#1b1717] text-white px-1.5 py-0.2 text-[9px] font-bold">
                      PDF ★
                    </span>
                  )}
                </div>
                <span className="text-xs text-[#6e6e73] font-medium block mt-0.5">
                  {entry.valuation_type === "agreed_value" ? "Agreed Value 约定价" : "Market Value 市价"}
                </span>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {entry.is_manual && (
                  <span className="rounded bg-[#f5f5f7] px-1.5 py-0.5 text-[10px] font-bold text-[#6e6e73] uppercase border border-[#e5e5ea]">
                    Manual
                  </span>
                )}
              </div>
            </div>

            {/* Multiple Quotes Revision Switcher (Quote 1/2, Quote 2/2) */}
            {!isSplit && group.entries.length > 1 && (
              <div className="mt-3 pt-2.5 border-t border-[#e5e5ea] flex items-center justify-between gap-1">
                <div className="flex items-center gap-1 overflow-x-auto py-0.5">
                  {group.entries.map((q, qIdx) => {
                    const isCurrent = qIdx === activeIdx;
                    const isEntryWinner = q.is_recommended;
                    return (
                      <button
                        key={q.id}
                        type="button"
                        onClick={() =>
                          setActiveQuoteByCompany((prev) => ({
                            ...prev,
                            [group.companyName]: qIdx,
                          }))
                        }
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all flex items-center gap-1 cursor-pointer shrink-0 ${
                          isCurrent
                            ? "bg-[#1b1717] text-white shadow-xs"
                            : "bg-[#f5f5f7] text-[#454545] hover:bg-neutral-200 border border-[#e5e5ea]"
                        }`}
                        title={`Quote ${qIdx + 1}/${group.entries.length}: RM ${q.total_payable.toFixed(2)} (${
                          q.valuation_type === "agreed_value" ? "Agreed" : "Market"
                        })`}
                      >
                        <span>{`Quote ${qIdx + 1}/${group.entries.length}`}</span>
                        {isEntryWinner && (
                          <Star
                            weight="fill"
                            size={10}
                            className={isCurrent ? "text-amber-300" : "text-amber-500"}
                          />
                        )}
                      </button>
                    );
                  })}
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setExpandedCompanies((prev) => ({
                      ...prev,
                      [group.companyName]: true,
                    }))
                  }
                  className="text-[10px] font-semibold text-[#6e6e73] hover:text-[#1b1717] px-1.5 py-0.5 rounded hover:bg-neutral-100 transition-colors no-print shrink-0"
                  title="View revisions side-by-side"
                >
                  Split
                </button>
              </div>
            )}

            {/* In Split View: show which quote this column represents */}
            {isSplit && (
              <div className="mt-2 pt-2 border-t border-[#e5e5ea] flex items-center justify-between">
                <span className="text-[11px] font-bold text-[#1b1717] bg-[#f5f5f7] px-2 py-0.5 rounded">
                  {`Quote ${activeIdx + 1} of ${group.entries.length}`}
                </span>
                {isWinner && (
                  <span className="text-[10px] font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                    Winner ★
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Numeric Figures Card */}
          <div className="p-4 space-y-3.5 border-b border-[#e5e5ea]">
            <div>
              <span className="text-[11px] uppercase font-bold text-[#6e6e73] block mb-0.5">
                Sum Insured (保额)
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

            <div>
              <span className="text-[11px] uppercase font-bold text-[#6e6e73] block mb-0.5">
                Motor Premium (车险)
              </span>
              <p className="font-mono text-sm font-bold text-[#1b1717]">
                RM {entry.motor_premium.toFixed(2)}
              </p>
            </div>

            {/* Total Payable Box */}
            <div
              className={`rounded-xl p-3.5 border transition-colors ${
                isWinner
                  ? "border-2 border-[#1b1717] bg-[#f5f5f7]"
                  : "border border-[#e5e5ea] bg-[#f5f5f7]/80"
              }`}
            >
              <span className="text-[11px] uppercase font-bold text-[#454545] block">
                Total Payable (总额)
              </span>
              <p
                className="font-mono text-lg font-black text-[#1b1717]"
                title={entry.exact_total_payable && entry.rounded_total_payable && entry.exact_total_payable !== entry.rounded_total_payable ? `Exact cents: RM ${entry.exact_total_payable.toFixed(2)}` : undefined}
              >
                RM {(entry.rounded_total_payable != null ? entry.rounded_total_payable : Math.ceil(entry.total_payable)).toFixed(2)}
              </p>
              <span className="text-[11px] text-[#6e6e73] font-medium block mt-0.5">
                (Incl. RM {tenure.fixed_costs_total.toFixed(2)} Road Tax &amp; Runner)
              </span>
            </div>
          </div>

          {/* Feature Comparison Rows */}
          <div className="p-4 space-y-2.5 text-xs divide-y divide-[#e5e5ea]">
            {/* Towing Limit */}
            <div className="flex items-center justify-between pt-1">
              <span className="text-[#6e6e73]">Towing (拖车):</span>
              <span className="font-bold text-[#1b1717]">{entry.towing_km || entry.towing_limit || "Unlimited"}</span>
            </div>

            {/* Agreed Value */}
            <div className="flex items-center justify-between pt-2">
              <span className="text-[#6e6e73]">Agreed Value:</span>
              <span className={`font-bold ${entry.agreed_value ? "text-emerald-700" : "text-[#6e6e73]"}`}>
                {entry.agreed_value ? "Yes" : "No"}
              </span>
            </div>

            {/* Betterment Co-pay / Waiver */}
            <div className="flex items-center justify-between pt-2">
              <span className="text-[#6e6e73]">Betterment (自付额):</span>
              <span className={`font-bold ${
                (entry.betterment_display && entry.betterment_display.startsWith("No")) || entry.waiver_betterment
                  ? "text-emerald-700"
                  : "text-amber-700"
              }`}>
                {entry.betterment_display || (entry.waiver_betterment ? "No (0%)" : "Yes")}
              </span>
            </div>

            {/* Excess */}
            <div className="flex items-center justify-between pt-2">
              <span className="text-[#6e6e73]">Excess:</span>
              <span className="font-mono font-bold text-[#1b1717]">
                RM {entry.excess.toFixed(2)}
              </span>
            </div>

            {/* Net Rate (Decimal Factor) */}
            <div className="flex items-center justify-between pt-2">
              <span className="text-[#6e6e73]">Net Rate:</span>
              <span
                className="font-mono font-bold text-[#1b1717] cursor-help"
                title={entry.rate_factor_formatted ? `Full 6-decimal factor: ${entry.rate_factor_formatted}` : (entry.rate_percentage ? `Rate percentage: ${entry.rate_percentage.toFixed(4)}%` : undefined)}
              >
                {entry.rate_factor != null
                  ? `Rate: ${entry.rate_factor.toFixed(4)}`
                  : entry.rate_percentage
                  ? `${entry.rate_percentage.toFixed(4)}%`
                  : "—"}
              </span>
            </div>

            {/* Windscreen (Target vs Sourced) */}
            <div className="flex items-center justify-between pt-2">
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
            <div className="flex items-center justify-between pt-2">
              <span className="text-[#6e6e73]">Special Perils:</span>
              <span className={`font-bold ${entry.special_perils ? "text-emerald-700" : "text-[#6e6e73]"}`}>
                {entry.special_perils || "Not Included"}
              </span>
            </div>

            {/* LLP / LLOP (Passenger Liability) */}
            <div className="flex items-center justify-between pt-2">
              <span className="text-[#6e6e73]">LLP / LLOP:</span>
              <span className={`font-bold ${entry.llp_llop ? "text-[#1b1717]" : "text-[#6e6e73]"}`}>
                {entry.llp_llop || "—"}
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
                setActivePdfSession({
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
            onClick={() => handleSelectWinner(entry.id)}
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

          {/* Generate Quotation Button for this specific card */}
          <Button
            variant="secondary"
            size="sm"
            className="w-full text-xs font-bold border-[#e5e5ea] bg-white hover:border-[#1b1717] text-[#1b1717]"
            loading={generatingQuoteEntryId === entry.id}
            onClick={() => handleGenerateSingleQuote(entry.id)}
            icon={<FilePdf size={14} weight="bold" className="text-[#ed1c24]" />}
            title="Generate official Risk-Locker quotation draft from this underwriter"
          >
            Generate Quotation
          </Button>

          {/* Direct Review & Issue Action if session exists */}
          {entry.session_id && (
            <Link
              href={`/sessions/${entry.session_id}/review` as Route}
              className={`flex items-center justify-center gap-1.5 w-full py-1.5 rounded-lg text-xs font-bold transition-colors shadow-2xs ${
                isWinner
                  ? "text-[#ed1c24] bg-rose-50 hover:bg-rose-100 border border-rose-200"
                  : "text-[#1b1717] bg-white hover:bg-neutral-100 border border-[#e5e5ea]"
              }`}
            >
              <FilePdf size={14} weight="bold" className={isWinner ? "text-[#ed1c24]" : "text-[#454545]"} />
              <span>{isWinner ? "Review & Issue Winner PDF →" : "Review & Edit Draft →"}</span>
            </Link>
          )}

          <div className="flex items-center justify-between px-1 pt-1">
            <button
              type="button"
              onClick={() => {
                setEditingEntry(entry);
                setIsManualModalOpen(true);
              }}
              className="text-xs font-medium text-[#454545] hover:text-[#1b1717] flex items-center gap-1 cursor-pointer"
            >
              <PencilSimple size={13} />
              Edit
            </button>

            <button
              type="button"
              onClick={() => handleDeleteEntry(entry.id)}
              className="text-xs font-medium text-[#ed1c24] hover:text-[#c4171e] flex items-center gap-1 cursor-pointer"
            >
              <Trash size={13} />
              Delete
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex gap-4 items-start relative w-full">
      <div className="flex-1 min-w-0 space-y-6 pb-12 overflow-x-hidden print:overflow-visible">
        {/* Print-Only Executive Comparison Header */}
        <div className="hidden print:block mb-6 border-b-2 border-[#1b1717] pb-4">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-black bg-[#1b1717] text-white px-2 py-0.5 rounded tracking-wider">
                  RISK-LOCKER
                </span>
                <h1 className="text-xl font-bold tracking-tight text-[#1b1717]">
                  MOTOR QUOTATION COMPARISON REPORT
                </h1>
              </div>
              <p className="text-xs text-[#6e6e73] mt-1">
                Underwriter Market Benchmarking · Policy Period: {tenure.coverage_period_formatted}
              </p>
            </div>
            <div className="text-right text-xs space-y-0.5">
              <p className="font-mono font-bold text-sm text-[#1b1717]">
                {tenure.vehicle_no || tenure.chassis_no || "Unregistered Vehicle"}
              </p>
              <p className="font-semibold text-[#454545]">{tenure.customer_name} {tenure.ic_no ? `(${tenure.ic_no})` : ""}</p>
              <p className="text-[#6e6e73]">{tenure.vehicle_model} · {tenure.engine_cc}</p>
            </div>
          </div>
        </div>

        {/* Live Batch Extraction Notification Banner */}
        {isCompilingBatch && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 flex items-center justify-between text-xs text-amber-900 font-medium no-print print:hidden">
            <span className="flex items-center gap-2">
              <CircleNotch size={16} className="animate-spin text-amber-700" />
              Scanning and compiling quotations for this vehicle... newly completed quotes will appear automatically.
            </span>
            <span className="text-[11px] text-amber-700 font-bold bg-amber-100/70 border border-amber-200 px-2 py-0.5 rounded">
              {entries.length} quote(s) compiled
            </span>
          </div>
        )}

        {/* 3-Stage Action Stepper Bar */}
        <div className="rounded-2xl border border-[#e5e5ea] bg-white p-3 shadow-xs no-print print:hidden">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 text-xs">
          {/* Stage 1: Compare Underwriters */}
          <div className="flex items-center gap-3 p-3 rounded-xl bg-[#f5f5f7]">
            <span className="size-6 rounded-full bg-[#1b1717] text-white font-bold flex items-center justify-center text-xs shrink-0">
              1
            </span>
            <div className="min-w-0">
              <span className="font-bold text-[#1b1717] block truncate text-xs">Compare Underwriters</span>
              <span className="text-[11px] text-[#6e6e73] block truncate">
                {entries.length} quote(s) compiled · Review terms &amp; benefits
              </span>
            </div>
          </div>

          {/* Stage 2: Select Recommendation(s) */}
          <div className={`flex items-center gap-3 p-3 rounded-xl transition-colors ${hasWinners ? "bg-emerald-50 border border-emerald-200" : "bg-[#f5f5f7]"}`}>
            <span className={`size-6 rounded-full font-bold flex items-center justify-center text-xs shrink-0 ${hasWinners ? "bg-emerald-600 text-white" : "bg-[#e5e5ea] text-[#454545]"}`}>
              2
            </span>
            <div className="min-w-0">
              <span className={`font-bold block truncate text-xs ${hasWinners ? "text-emerald-950" : "text-[#454545]"}`}>
                {winnerEntries.length === 0
                  ? "Select Recommendation(s)"
                  : winnerEntries.length === 1
                  ? `Recommended: ${winnerEntries[0].company_name}`
                  : `${winnerEntries.length} Recommendations Selected ★`}
              </span>
              <span className="text-[11px] text-[#6e6e73] block truncate">
                {winnerEntries.length === 0
                  ? "Click any quote to recommend"
                  : winnerEntries.map((w) => w.company_name.split(" ")[0]).join(", ")}
              </span>
            </div>
          </div>

          {/* Stage 3: Review & Issue Quotation */}
          <div className={`flex items-center justify-between p-3 rounded-xl transition-colors ${hasWinners ? "bg-rose-50 border border-rose-200" : "bg-[#f5f5f7]"}`}>
            <div className="flex items-center gap-3 min-w-0">
              <span className={`size-6 rounded-full font-bold flex items-center justify-center text-xs shrink-0 ${hasWinners ? "bg-[#ed1c24] text-white" : "bg-[#e5e5ea] text-[#454545]"}`}>
                3
              </span>
              <div className="min-w-0">
                <span className="font-bold text-[#1b1717] block truncate text-xs">
                  {winnerEntries.length > 1
                    ? `Issue ${winnerEntries.length} Quotations`
                    : winnerEntries.length === 1
                    ? `Issue ${winnerEntries[0].company_name.split(" ")[0]} Quotation`
                    : "Review & Issue Quotation"}
                </span>
                <span className="text-[11px] text-[#6e6e73] block truncate">
                  {winnerEntries.length === 0
                    ? "Select recommendation first"
                    : "Client-ready quotation ready to build"}
                </span>
              </div>
            </div>

            {/* Direct Links for Selected Winners */}
            {winnerEntries.length === 1 && winnerEntries[0].session_id && (
              <Link
                href={`/sessions/${winnerEntries[0].session_id}/review` as Route}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-[#ed1c24] hover:text-[#c4171e] px-3 py-1.5 rounded-lg bg-white shadow-xs border border-rose-200 shrink-0 transition-colors hover:bg-rose-50"
              >
                <span>Open Quote</span>
                <ArrowRight size={13} weight="bold" />
              </Link>
            )}

            {winnerEntries.length > 1 && (
              <div className="flex items-center gap-1.5 shrink-0">
                {winnerEntries.map((w) =>
                  w.session_id ? (
                    <Link
                      key={w.id}
                      href={`/sessions/${w.session_id}/review` as Route}
                      title={`Open ${w.company_name} quote review`}
                      className="inline-flex items-center gap-1 text-[11px] font-bold text-[#ed1c24] hover:text-[#c4171e] px-2 py-1 rounded-md bg-white shadow-2xs border border-rose-200 transition-colors hover:bg-rose-50"
                    >
                      <span>{w.company_name.split(" ")[0]}</span>
                      <ArrowRight size={10} weight="bold" />
                    </Link>
                  ) : null
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Vehicle Info & Action Header */}
      <div className="rounded-2xl border border-[#e5e5ea] bg-white p-5 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="rounded-lg bg-[#f5f5f7] px-3 py-1 font-mono text-sm font-bold text-[#1b1717] border border-[#e5e5ea]">
              {tenure.vehicle_no}
            </span>
            <h1 className="text-xl font-bold tracking-tight text-[#1b1717]">
              {tenure.customer_name}
            </h1>
            <span className="rounded-md bg-[#f5f5f7] px-2.5 py-0.5 text-xs font-semibold text-[#454545] border border-[#e5e5ea]">
              Expiring {tenure.expiry_month}
            </span>
          </div>
          <div className="text-xs text-[#6e6e73] mt-2 flex items-center gap-2 flex-wrap">
            <span>Period: <strong className="text-[#1b1717] font-mono">{tenure.coverage_period_formatted}</strong></span>
            <span>•</span>
            <span>Model: <strong className="text-[#1b1717]">{tenure.vehicle_model || "Motor Vehicle"}</strong> ({tenure.engine_cc || "N/A"})</span>
            {(tenure.formatted_ic || tenure.ic_no) && (
              <>
                <span>•</span>
                <span>IC: <strong className="text-[#1b1717] font-mono">{tenure.formatted_ic || tenure.ic_no}</strong></span>
              </>
            )}
            {tenure.birth_date && (
              <>
                <span>•</span>
                <span>DOB: <strong className="text-[#1b1717] font-mono">{new Date(tenure.birth_date).toLocaleDateString("en-MY", { day: "2-digit", month: "2-digit", year: "numeric" })}</strong></span>
              </>
            )}
            {tenure.customer_age != null && (
              <span>({tenure.customer_age} yo{tenure.customer_gender ? `, ${tenure.customer_gender}` : ""}{tenure.nric_state ? `, ${tenure.nric_state}` : ""})</span>
            )}
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-tight ${
              (tenure.runner_fee_type === "passport" || tenure.runner_fee >= 20.0)
                ? "bg-purple-100 text-purple-800 border border-purple-200"
                : "bg-blue-100 text-blue-800 border border-blue-200"
            }`}>
              {(tenure.runner_fee_type === "passport" || tenure.runner_fee >= 20.0)
                ? `Passport (RM ${tenure.runner_fee.toFixed(2)})`
                : `MyKad (RM ${tenure.runner_fee.toFixed(2)})`}
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5 flex-wrap no-print print:hidden">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleCopyWhatsapp}
            icon={copiedWhatsapp ? <Check weight="bold" size={16} className="text-emerald-500" /> : <ChatCircleDots weight="bold" size={16} />}
            className={copiedWhatsapp ? "border-emerald-500 bg-emerald-50 text-emerald-700" : ""}
          >
            {copiedWhatsapp ? "Copied WhatsApp Teaser!" : "Copy WhatsApp Teaser"}
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => window.print()}
            icon={<Printer weight="bold" size={16} />}
          >
            Print
          </Button>

          {entries.length > 0 && (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleGenerateAllQuotes}
              loading={generatingAllQuotes}
              icon={<FilePdf weight="bold" size={16} className="text-[#ed1c24]" />}
              className="border-[#e5e5ea] bg-white hover:border-[#1b1717] text-[#1b1717] font-semibold"
              title="Generate official Risk-Locker quotations for all underwriter options"
            >
              Generate All Quotations
            </Button>
          )}

          <Link
            href={`/upload?mode=comparison&tenure_id=${tenure.id}` as Route}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#e5e5ea] bg-white hover:bg-neutral-50 text-xs font-semibold text-[#1b1717] transition-colors shadow-2xs"
            title="Upload additional quotation PDFs for this vehicle"
          >
            <UploadSimple size={15} weight="bold" />
            <span>Upload Quotes</span>
          </Link>

          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              setEditingEntry(null);
              setIsManualModalOpen(true);
            }}
            icon={<Plus weight="bold" size={14} />}
            className="bg-[#1b1717] hover:bg-black text-white font-semibold"
          >
            Add Insurer Quote
          </Button>
        </div>
      </div>

      {/* Date Reconciliation Conflict Banner (Non-blocking) */}
      {data.date_conflict?.has_conflict && (
        <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-xs text-amber-950 shadow-xs flex items-start justify-between gap-3 no-print print:hidden">
          <div className="space-y-1">
            <p className="font-bold flex items-center gap-1.5 text-amber-900">
              <CalendarBlank size={16} weight="bold" className="text-amber-700" />
              Coverage Date Reconciliation Variance Detected
            </p>
            <p className="text-amber-800 leading-relaxed">
              {data.date_conflict.message}
            </p>
            <div className="flex items-center gap-2 pt-1 font-mono text-[11px]">
              <span className="font-bold text-amber-900">Detected dates:</span>
              {data.date_conflict.unique_dates?.map((d) => (
                <span key={d} className="px-1.5 py-0.5 bg-amber-100 rounded border border-amber-200">
                  {d}
                </span>
              ))}
            </div>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800 bg-amber-200/70 px-2 py-1 rounded">
            Non-Blocking
          </span>
        </div>
      )}

      {/* Main 3-Pane Excel Comparison Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-[280px_minmax(0,1fr)_280px] print:grid-cols-[240px_minmax(0,1fr)_220px] gap-4 items-start">
        {/* ============================================================== */}
        {/* LEFT PANE: Customer Dossier & Vehicle Fixed Costs              */}
        {/* ============================================================== */}
        <div className="rounded-2xl border border-[#e5e5ea] bg-white shadow-sm overflow-hidden sticky top-6 print:static print:shadow-none break-inside-avoid">
          <div className="bg-[#f5f5f7] px-4 py-3 border-b border-[#e5e5ea] flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-[#1b1717]">
              Customer &amp; Vehicle Ledger
            </span>
            <button
              type="button"
              onClick={() => {
                if (!editingFixedCosts && data?.tenure) {
                  populateEditInputs(data.tenure);
                }
                setEditingFixedCosts(!editingFixedCosts);
              }}
              className="rounded p-1 text-[#454545] hover:text-[#1b1717] hover:bg-neutral-200 transition-colors no-print print:hidden"
              title="Edit customer, vehicle & fixed charges"
            >
              <PencilSimple size={15} weight="bold" />
            </button>
          </div>

          <div className="p-4 space-y-4 text-xs divide-y divide-[#e5e5ea]">
            {/* Customer Information Block */}
            <div className="space-y-1.5">
              <span className="text-xs font-bold text-[#6e6e73] uppercase tracking-wider block mb-1">
                Customer Information
              </span>
              {editingFixedCosts ? (
                <div className="space-y-2 bg-[#f5f5f7] p-2.5 rounded-lg border border-[#e5e5ea]">
                  <div>
                    <label className="text-[11px] font-semibold text-[#454545] block mb-1">Customer Name</label>
                    <input
                      type="text"
                      value={customerNameInput}
                      onChange={(e) => setCustomerNameInput(e.target.value)}
                      className="w-full rounded px-2.5 py-1.5 text-xs border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-[#454545] block mb-1">IC / Passport Number</label>
                    <input
                      type="text"
                      value={icNoInput}
                      onChange={(e) => setIcNoInput(e.target.value)}
                      placeholder="e.g. 881205-14-5521"
                      className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                    />
                  </div>
                </div>
              ) : (
                <div>
                  <p className="font-bold text-sm text-[#1b1717]">{tenure.customer_name}</p>
                  {tenure.ic_no ? (
                    <div className="mt-1 space-y-1">
                      <div className="flex items-center gap-1.5">
                        <IdentificationCard size={14} className="text-[#6e6e73]" />
                        <span className="font-mono text-xs font-semibold text-[#1b1717] bg-[#f5f5f7] px-2 py-0.5 rounded border border-[#e5e5ea]">
                          {tenure.ic_no}
                        </span>
                      </div>
                      {decodedIc.isValid && decodedIc.formattedDob && (
                        <div className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                          <span>DOB: {decodedIc.formattedDob}</span>
                          <span>•</span>
                          <span>Age {decodedIc.age} yrs{decodedIc.gender ? ` (${decodedIc.gender})` : ""}</span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-[#6e6e73] italic">No IC recorded</p>
                  )}
                  {tenure.phone && (
                    <p className="text-xs text-[#454545] mt-1 flex items-center gap-1">
                      <Phone size={12} className="text-[#6e6e73]" />
                      <span>{tenure.phone}</span>
                    </p>
                  )}
                  {tenure.address && (
                    <p className="text-xs text-[#6e6e73] mt-1 flex items-start gap-1">
                      <MapPin size={12} className="text-[#6e6e73] shrink-0 mt-0.5" />
                      <span className="truncate" title={tenure.address}>{tenure.address}</span>
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Period */}
            <div className="pt-3 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#6e6e73] uppercase">Insurance Period (保险日期)</span>
                {editingFixedCosts && (
                  <span className="text-[10px] text-indigo-700 font-bold bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                    Auto 1-Year Sync
                  </span>
                )}
              </div>
              {editingFixedCosts ? (
                <div className="space-y-2 bg-[#f5f5f7] p-2.5 rounded-lg border border-[#e5e5ea]">
                  <div>
                    <label className="text-[11px] font-semibold text-[#454545] block mb-1">Start Date (生效日)</label>
                    <input
                      type="date"
                      value={startDateInput}
                      onChange={(e) => handleStartDateChange(e.target.value)}
                      className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-[#454545] block mb-1">End Date (截止日)</label>
                    <input
                      type="date"
                      value={endDateInput}
                      onChange={(e) => handleEndDateChange(e.target.value)}
                      className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                    />
                  </div>
                </div>
              ) : (
                <p className="font-mono font-bold text-xs text-[#1b1717]">{tenure.coverage_period_formatted}</p>
              )}
            </div>

            {/* Roadtax & Runner Fee */}
            <div className="pt-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#6e6e73] uppercase">Road Tax + Runner (路税)</span>
                <span className="font-mono font-bold text-sm text-emerald-700">
                  RM {tenure.fixed_costs_total.toFixed(2)}
                </span>
              </div>

              {editingFixedCosts ? (
                <div className="space-y-2 bg-[#f5f5f7] p-2.5 rounded-lg border border-[#e5e5ea]">
                  <div>
                    <label className="text-[11px] font-semibold text-[#454545] block mb-1">Road Tax (RM)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={roadTaxInput}
                      onChange={(e) => setRoadTaxInput(e.target.value)}
                      className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717]"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-[11px] font-semibold text-[#454545]">Runner Fee (RM)</label>
                      <span className="text-[10px] font-medium text-[#6e6e73]">
                        {tenure.runner_fee_type === "passport" ? "Passport (RM 20)" : "MyKad (RM 10)"}
                      </span>
                    </div>
                    <input
                      type="number"
                      step="0.01"
                      value={runnerFeeInput}
                      onChange={(e) => setRunnerFeeInput(e.target.value)}
                      className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717]"
                    />
                  </div>
                </div>
              ) : (
                <div className="text-xs text-[#454545] space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-[#6e6e73]">Road Tax:</span>
                    <span className="font-mono font-medium text-[#1b1717]">RM {tenure.road_tax.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[#6e6e73]">Runner Fee:</span>
                      {tenure.runner_fee_type === "passport" ? (
                        <span className="inline-flex items-center px-1.5 py-0.2 text-[10px] font-bold rounded-md bg-amber-50 text-amber-800 border border-amber-200">
                          Passport (RM 20)
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-1.5 py-0.2 text-[10px] font-bold rounded-md bg-neutral-100 text-neutral-700 border border-neutral-200">
                          MyKad (RM 10)
                        </span>
                      )}
                    </div>
                    <span className="font-mono font-medium text-[#1b1717]">RM {tenure.runner_fee.toFixed(2)}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Vehicle Mechanical Specs */}
            <div className="pt-3 space-y-2">
              <span className="text-xs font-bold text-[#6e6e73] uppercase tracking-wider block">
                Vehicle Mechanicals
              </span>
              {editingFixedCosts ? (
                <div className="space-y-2 bg-[#f5f5f7] p-2.5 rounded-lg border border-[#e5e5ea]">
                  <div>
                    <label className="text-[11px] font-semibold text-[#454545] block mb-1">Make / Model</label>
                    <input
                      type="text"
                      value={vehicleModelInput}
                      onChange={(e) => setVehicleModelInput(e.target.value)}
                      className="w-full rounded px-2.5 py-1.5 text-xs border border-[#e5e5ea] bg-white text-[#1b1717]"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-[#454545] block mb-1">Year of Make (YOM)</label>
                    <input
                      type="number"
                      value={manufactureYearInput}
                      onChange={(e) => setManufactureYearInput(e.target.value)}
                      placeholder="e.g. 2020"
                      className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717]"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-[#454545] block mb-1">Engine CC</label>
                    <input
                      type="text"
                      value={engineCcInput}
                      onChange={(e) => setEngineCcInput(e.target.value)}
                      placeholder="e.g. 1496 CC"
                      className="w-full rounded px-2.5 py-1.5 text-xs border border-[#e5e5ea] bg-white text-[#1b1717]"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-[#454545] block mb-1">Engine Number</label>
                    <input
                      type="text"
                      value={engineNoInput}
                      onChange={(e) => setEngineNoInput(e.target.value)}
                      className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717]"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-[#454545] block mb-1">Chassis / VIN</label>
                    <input
                      type="text"
                      value={chassisNoInput}
                      onChange={(e) => setChassisNoInput(e.target.value)}
                      className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717]"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-[#454545] block mb-1">Windscreen Target (RM)</label>
                    <input
                      type="number"
                      value={windscreenInput}
                      onChange={(e) => setWindscreenInput(e.target.value)}
                      className="w-full rounded px-2.5 py-1.5 text-xs font-mono border border-[#e5e5ea] bg-white text-[#1b1717]"
                    />
                  </div>

                  <div className="flex justify-end gap-1.5 pt-2 border-t border-[#e5e5ea]">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 text-xs px-2.5"
                      onClick={() => {
                        if (data?.tenure) populateEditInputs(data.tenure);
                        setEditingFixedCosts(false);
                      }}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      variant="primary"
                      className="h-7 text-xs px-3 bg-[#1b1717] text-white hover:bg-black font-semibold"
                      loading={savingFixedCosts}
                      onClick={handleSaveFixedCosts}
                    >
                      Save Changes
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-1.5 text-xs text-[#454545]">
                  <div className="flex justify-between">
                    <span className="text-[#6e6e73]">Model:</span>
                    <span className="font-semibold text-[#1b1717]">{tenure.vehicle_model}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#6e6e73]">Year of Make:</span>
                    <span className="font-semibold text-[#1b1717]">
                      {tenure.manufacture_year || "Not Recorded"}
                      {data?.vehicle_age ? ` (${data.vehicle_age} yrs)` : ""}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#6e6e73]">Engine CC:</span>
                    <span className="font-semibold text-[#1b1717]">{tenure.engine_cc}</span>
                  </div>
                  {tenure.engine_no && (
                    <div className="flex justify-between">
                      <span className="text-[#6e6e73]">Engine No:</span>
                      <span className="font-mono text-[#1b1717]">{tenure.engine_no}</span>
                    </div>
                  )}
                  {tenure.chassis_no && (
                    <div className="flex justify-between">
                      <span className="text-[#6e6e73]">Chassis / VIN:</span>
                      <span className="font-mono text-[#1b1717]">{tenure.chassis_no}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-[#6e6e73]">Target Windscreen:</span>
                    <span className="font-mono font-bold text-[#1b1717]">
                      RM {tenure.windscreen_target ? tenure.windscreen_target.toLocaleString() : "1,700.00"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#6e6e73]">NCD Status:</span>
                    <span className="font-bold text-[#1b1717]">
                      {tenure.ncd_percentage != null
                        ? `${tenure.ncd_percentage % 1 === 0 ? tenure.ncd_percentage.toFixed(0) : tenure.ncd_percentage.toFixed(2)}%`
                        : "Not Detected"}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Feature Row Legend */}
            <div className="pt-4 space-y-2">
              <span className="text-xs font-bold text-[#6e6e73] uppercase tracking-wider">
                Comparison Rows
              </span>
              <ul className="space-y-1.5 text-xs text-[#454545]">
                <li className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-neutral-400" />
                  <span>Sum Insured (保额)</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-neutral-400" />
                  <span>Motor Premium (车险)</span>
                </li>
                <li className="flex items-center gap-2 font-bold text-[#1b1717]">
                  <span className="size-2 rounded-full bg-[#ed1c24]" />
                  <span>Total Payable (总额)</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-neutral-400" />
                  <span>Towing Coverage (拖车)</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-neutral-400" />
                  <span>Agreed Value (约定价)</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-neutral-400" />
                  <span>Waiver Of Betterment</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-neutral-400" />
                  <span>Net Rate % / Excess</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-neutral-400" />
                  <span>Windscreen (挡风玻璃)</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-neutral-400" />
                  <span>Special Perils / Flood (天灾)</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-neutral-400" />
                  <span>Passenger Liability (LLP)</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* ============================================================== */}
        {/* CENTER PANE: Dynamic Side-by-Side Underwriter Columns           */}
        {/* ============================================================== */}
        <div className="min-w-0 overflow-x-auto pb-4 print:overflow-visible print:w-full">
          <div className="flex gap-4 min-w-max print:min-w-0 print:flex-wrap">
            {companyGroups.map((group) => {
              const isExpanded = expandedCompanies[group.companyName] && group.entries.length > 1;

              if (isExpanded) {
                // Split view for this company: render multiple revisions side-by-side with shared header
                return (
                  <div
                    key={group.companyName}
                    className="flex flex-col gap-2 p-2.5 rounded-2xl bg-[#f5f5f7] border-2 border-[#1b1717]/20 shadow-xs break-inside-avoid"
                  >
                    <div className="flex items-center justify-between px-2 py-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs text-[#1b1717] uppercase tracking-wider">
                          {group.companyName}
                        </span>
                        <span className="text-[10px] font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200">
                          {group.entries.length} Quotes Split
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedCompanies((prev) => ({
                            ...prev,
                            [group.companyName]: false,
                          }))
                        }
                        className="text-[10px] font-bold text-[#454545] hover:text-[#1b1717] px-2 py-0.5 rounded bg-white hover:bg-neutral-200 border border-[#e5e5ea] transition-colors cursor-pointer no-print"
                      >
                        Collapse to Tabbed
                      </button>
                    </div>

                    <div className="flex gap-3">
                      {group.entries.map((entry, idx) =>
                        renderUnderwriterCard(entry, group, idx, true)
                      )}
                    </div>
                  </div>
                );
              }

              // Default: Tabbed Single Card with Revision Pills
              const customIdx = activeQuoteByCompany[group.companyName];
              let activeIdx = 0;
              if (customIdx !== undefined && customIdx >= 0 && customIdx < group.entries.length) {
                activeIdx = customIdx;
              } else {
                const winnerIdx = group.entries.findIndex((e) => e.is_recommended);
                activeIdx = winnerIdx !== -1 ? winnerIdx : 0;
              }
              const entry = group.entries[activeIdx] || group.entries[0];

              return renderUnderwriterCard(entry, group, activeIdx, false);
            })}

            {/* Empty State Banner when no quotes are linked yet */}
            {companyGroups.length === 0 && (
              <div className="flex-1 min-w-[340px] max-w-[560px] p-8 rounded-2xl border-2 border-dashed border-[#e5e5ea] bg-white text-center flex flex-col items-center justify-center gap-4">
                <div className="size-14 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center">
                  <Columns size={28} weight="duotone" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-[#1b1717]">
                    {isCompilingBatch || (data?.pending_jobs_count && data.pending_jobs_count > 0)
                      ? "Extracting Quotation Documents..."
                      : "No Insurer Quotes Added Yet"}
                  </h3>
                  <p className="text-xs text-[#6e6e73] max-w-sm mt-1 leading-relaxed">
                    {isCompilingBatch || (data?.pending_jobs_count && data.pending_jobs_count > 0)
                      ? "Our extraction pipeline is reading underwriter PDFs, extracting sums insured, motor premiums, and benefit riders. This matrix will refresh automatically."
                      : `No quotation PDFs are linked to ${tenure.vehicle_no}. Upload underwriter quotation PDFs or enter manual portal figures to begin side-by-side comparison.`}
                  </p>
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <Button
                    type="button"
                    onClick={() => router.push(`/upload/marketing-comparison?tenure_id=${tenureId}` as Route)}
                    className="bg-[#1b1717] hover:bg-black text-white text-xs font-bold px-4 py-2 rounded-xl"
                  >
                    <Plus size={14} weight="bold" className="mr-1.5" />
                    Upload Quotation PDFs
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => fetchComparison()}
                    className="text-xs font-semibold px-3 py-2 rounded-xl"
                  >
                    <ArrowsClockwise size={14} weight="bold" className="mr-1" />
                    Refresh
                  </Button>
                </div>
              </div>
            )}

            {/* "+ Add Insurer Quote" Action Card */}
            <div
              onClick={() => {
                setEditingEntry(null);
                setIsManualModalOpen(true);
              }}
              className="w-[240px] shrink-0 rounded-2xl border-2 border-dashed border-[#e5e5ea] hover:border-[#1b1717] p-6 flex flex-col items-center justify-center text-center gap-3 cursor-pointer transition-colors bg-white group no-print print:hidden"
            >
              <div className="size-12 rounded-full bg-[#f5f5f7] flex items-center justify-center text-[#454545] group-hover:bg-[#1b1717] group-hover:text-white transition-colors">
                <Plus size={22} weight="bold" />
              </div>
              <div>
                <p className="text-sm font-bold text-[#1b1717]">
                  Add Insurer Quote
                </p>
                <p className="text-xs text-[#6e6e73] mt-0.5">
                  Enter portal figures manually or adjust rates
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* ============================================================== */}
        {/* RIGHT PANE: Previous Policy & Valuation Matrix                 */}
        {/* ============================================================== */}
        <div className="space-y-4 sticky top-6">
          {/* Previous Policy Card (Strict DB query, zero gibberish fallbacks) */}
          <div className="rounded-2xl border border-[#e5e5ea] bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between border-b border-[#e5e5ea] pb-2.5 mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#1b1717]">
                Previous Policy ({previous_policy?.year || "Past Year"})
              </span>
              {previous_policy?.insurer && (
                <span className="rounded bg-[#f5f5f7] px-2 py-0.5 text-xs font-bold text-[#1b1717] border border-[#e5e5ea]">
                  {previous_policy.insurer}
                </span>
              )}
            </div>

            {previous_policy ? (
              <div className="space-y-2 text-xs text-[#454545]">
                <div className="flex justify-between">
                  <span className="text-[#6e6e73]">Sum Insured:</span>
                  <span className="font-mono font-bold text-[#1b1717]">
                    {previous_policy.sum_insured
                      ? `RM ${previous_policy.sum_insured.toLocaleString("en-MY", { minimumFractionDigits: 2 })}`
                      : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#6e6e73]">Premium Paid:</span>
                  <span className="font-mono font-bold text-emerald-700">
                    {previous_policy.insurance_premium
                      ? `RM ${previous_policy.insurance_premium.toFixed(2)}`
                      : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#6e6e73]">Included Perils:</span>
                  <span className="font-medium text-[#1b1717]">
                    {previous_policy.perils || "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#6e6e73]">YOM / Model:</span>
                  <span className="font-medium text-[#1b1717]">
                    {previous_policy.yom || ""} {previous_policy.model || tenure.vehicle_model}
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-center py-4 text-xs text-[#6e6e73]">
                <p>No previous policy record found in database.</p>
                <p className="text-[11px] text-neutral-400 mt-1">Past year will remain empty until recorded.</p>
              </div>
            )}
          </div>

          {/* Recommended Sum Insured / Valuation Matrix */}
          <div className="rounded-2xl border border-[#e5e5ea] bg-white p-4 shadow-sm">
            <span className="block text-xs font-bold uppercase tracking-wider text-[#1b1717] border-b border-[#e5e5ea] pb-2 mb-3">
              Recommended Sum Insured
            </span>

            <div className="space-y-2 text-xs">
              {Object.keys(recommended_sum_insured).length > 0 ? (
                Object.entries(recommended_sum_insured).map(([insurerKey, sumVal]) => (
                  <div key={insurerKey} className="flex justify-between items-center">
                    <span className="text-[#454545] font-semibold">{insurerKey}:</span>
                    <span className="font-mono font-bold text-[#1b1717]">
                      RM {Number(sumVal).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                ))
              ) : (
                <p className="text-xs text-[#6e6e73] text-center py-2">No underwriter sums recorded</p>
              )}
            </div>
          </div>

          {/* NCD Block */}
          <div className="rounded-2xl border border-[#e5e5ea] bg-white p-4 shadow-sm">
            <span className="block text-xs font-bold uppercase tracking-wider text-[#1b1717] border-b border-[#e5e5ea] pb-2 mb-3">
              NCD Entitlement
            </span>
            <div className="grid grid-cols-2 gap-2 text-center text-xs">
              <div className="rounded-lg bg-[#f5f5f7] p-2 border border-[#e5e5ea]">
                <span className="text-xs text-[#6e6e73] block">Current NCD</span>
                <span className="font-mono font-bold text-sm text-[#1b1717]">
                  {ncd?.current != null
                    ? `${ncd.current % 1 === 0 ? ncd.current.toFixed(0) : ncd.current.toFixed(2)}%`
                    : "Not Detected"}
                </span>
              </div>
              <div className="rounded-lg bg-emerald-50 p-2 border border-emerald-200">
                <span className="text-xs text-emerald-800 block font-semibold">Next NCD</span>
                <span className="font-mono font-bold text-sm text-emerald-800">
                  {ncd?.next != null
                    ? `${ncd.next % 1 === 0 ? ncd.next.toFixed(0) : ncd.next.toFixed(2)}%`
                    : "Not Detected"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* BOTTOM SECTION: Generated Risk-Locker Quotations               */}
      {/* ============================================================== */}
      {data.generated_quotations && data.generated_quotations.length > 0 && (
        <div className="rounded-2xl border border-[#e5e5ea] bg-white p-6 shadow-sm no-print print:hidden">
          <div className="flex items-center justify-between pb-4 border-b border-[#e5e5ea] mb-4">
            <div>
              <h3 className="text-base font-bold text-[#1b1717] flex items-center gap-2">
                <FilePdf size={20} weight="fill" className="text-[#ed1c24]" />
                Generated Risk-Locker Quotations
              </h3>
              <p className="text-xs text-[#6e6e73] mt-0.5">
                Official branded client quotations generated from this marketing comparison
              </p>
            </div>
            <span className="rounded-full bg-[#f5f5f7] border border-[#e5e5ea] px-3 py-1 text-xs font-bold text-[#1b1717]">
              {data.generated_quotations.length} Issued
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.generated_quotations.map((gq) => (
              <div
                key={gq.session_id}
                className="p-4 rounded-xl border border-[#e5e5ea] bg-[#f5f5f7]/50 hover:bg-[#f5f5f7] transition-all space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-mono text-xs font-bold text-[#1b1717] bg-white px-2 py-0.5 rounded border border-[#e5e5ea]">
                        {gq.quotation_ref || gq.reference_number || "Draft Quote"}
                      </span>
                      <span className="rounded bg-blue-50 text-blue-700 border border-blue-200 font-bold px-1.5 py-0.5 text-[10px]">
                        v{gq.version_number || 1}
                      </span>
                    </div>
                    <p className="text-xs font-bold text-[#1b1717] mt-1.5 uppercase">
                      {gq.company_name}
                    </p>
                  </div>
                  <div className="text-right flex flex-col items-end gap-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {gq.status}
                    </span>
                    {gq.created_at && (
                      <span className="text-[10px] text-[#6e6e73]">
                        {new Date(gq.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-baseline justify-between text-xs pt-1 border-t border-[#e5e5ea]/80">
                  <span className="text-[#6e6e73]">Total Payable:</span>
                  <span className="font-mono font-bold text-sm text-[#1b1717]">
                    RM {gq.total_payable.toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                  </span>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <Link
                    href={`/sessions/${gq.session_id}/review` as Route}
                    className="flex-1 text-center py-1.5 px-2.5 rounded-lg text-xs font-bold text-white bg-[#1b1717] hover:bg-black transition-colors"
                  >
                    Review Quote
                  </Link>
                  <a
                    href={`/api/sessions/${gq.session_id}/pdf`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="py-1.5 px-3 rounded-lg text-xs font-bold text-[#1b1717] bg-white hover:bg-neutral-100 border border-[#e5e5ea] transition-colors flex items-center gap-1"
                  >
                    <FilePdf size={14} className="text-[#ed1c24]" />
                    PDF
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      </div>

      {/* Docked Source PDF Viewer Pane (Sticky side-by-side with matrix, 0 columns covered) */}
      {activePdfSession && pdfDockMode === "docked" && (
        <div
          style={{ width: pdfPanelWidth }}
          className="shrink-0 sticky top-4 h-[calc(100vh-2rem)] border border-[#e5e5ea] bg-white rounded-2xl shadow-xl flex flex-col overflow-hidden relative transition-all no-print print:hidden"
        >
          {/* Draggable Resize Divider on Left Edge */}
          <div
            onMouseDown={() => setIsResizing(true)}
            className="absolute top-0 bottom-0 -left-1.5 w-3 cursor-col-resize hover:bg-[#1b1717]/40 z-30 flex items-center justify-center group"
            title="Click & drag to resize PDF viewer"
          >
            <div className="w-1 h-12 rounded-full bg-neutral-300 group-hover:bg-[#1b1717] transition-colors" />
          </div>

          <div className="flex items-center justify-between p-3.5 border-b border-[#e5e5ea] bg-[#f5f5f7]">
            <div className="flex items-center gap-2.5 min-w-0">
              <FilePdf size={22} className="text-[#ed1c24] shrink-0" weight="bold" />
              <div className="min-w-0">
                <h4 className="text-xs font-bold text-[#1b1717] truncate">
                  {activePdfSession.companyName} Source PDF
                </h4>
                <p className="text-[11px] text-[#6e6e73] truncate">
                  Verify extracted values directly against source document
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                onClick={() => setPdfDockMode("floating")}
                className="px-2 py-1 text-[11px] font-semibold rounded-lg border border-[#e5e5ea] bg-white hover:bg-neutral-100 text-[#454545] flex items-center gap-1 transition-colors cursor-pointer"
                title="Switch to floating overlay drawer"
              >
                <SidebarSimple size={13} weight="bold" />
                <span>Float</span>
              </button>
              <button
                type="button"
                onClick={() => setActivePdfSession(null)}
                className="p-1.5 rounded-lg border border-[#e5e5ea] bg-white hover:bg-neutral-100 text-[#454545] transition-colors cursor-pointer"
                title="Close PDF Panel"
              >
                <X size={15} weight="bold" />
              </button>
            </div>
          </div>
          <div className="flex-1 bg-neutral-100 p-2 overflow-hidden">
            <iframe
              key={activePdfSession.sessionId}
              src={`/api/sessions/${activePdfSession.sessionId}/pdf`}
              className="w-full h-full rounded-lg border border-[#e5e5ea] bg-white"
              title="Underwriter Source PDF"
            />
          </div>
        </div>
      )}

      {/* Floating Source PDF Viewer Drawer (Draggable Resizer) */}
      {activePdfSession && pdfDockMode === "floating" && (
        <div
          style={{ width: pdfPanelWidth }}
          className="fixed inset-y-0 right-0 z-50 bg-white border-l border-[#e5e5ea] shadow-2xl flex flex-col animate-in slide-in-from-right duration-150 no-print print:hidden"
        >
          {/* Draggable Resize Divider on Left Edge */}
          <div
            onMouseDown={() => setIsResizing(true)}
            className="absolute top-0 bottom-0 -left-1.5 w-3 cursor-col-resize hover:bg-[#1b1717]/40 z-30 flex items-center justify-center group"
            title="Click & drag to resize PDF viewer"
          >
            <div className="w-1 h-16 rounded-full bg-neutral-300 group-hover:bg-[#1b1717] transition-colors" />
          </div>

          <div className="flex items-center justify-between p-4 border-b border-[#e5e5ea] bg-[#f5f5f7]">
            <div className="flex items-center gap-2.5 min-w-0">
              <FilePdf size={22} className="text-[#ed1c24] shrink-0" weight="bold" />
              <div className="min-w-0">
                <h4 className="text-sm font-bold text-[#1b1717] truncate">
                  {activePdfSession.companyName} Source PDF
                </h4>
                <p className="text-xs text-[#6e6e73] truncate">
                  Verify extracted values directly against source document
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                onClick={() => setPdfDockMode("docked")}
                className="px-2.5 py-1 text-xs font-semibold rounded-lg border border-[#e5e5ea] bg-white hover:bg-neutral-100 text-[#1b1717] flex items-center gap-1.5 transition-colors cursor-pointer"
                title="Dock side-by-side with matrix table"
              >
                <SidebarSimple size={14} weight="bold" />
                <span>Dock to Window</span>
              </button>
              <button
                type="button"
                onClick={() => setActivePdfSession(null)}
                className="p-1.5 rounded-lg border border-[#e5e5ea] bg-white hover:bg-neutral-100 text-[#454545] transition-colors cursor-pointer"
                title="Close PDF Panel"
              >
                <X size={16} weight="bold" />
              </button>
            </div>
          </div>
          <div className="flex-1 bg-neutral-100 p-2 overflow-hidden">
            <iframe
              key={activePdfSession.sessionId}
              src={`/api/sessions/${activePdfSession.sessionId}/pdf`}
              className="w-full h-full rounded-lg border border-[#e5e5ea] bg-white"
              title="Underwriter Source PDF"
            />
          </div>
        </div>
      )}

      {/* Add / Edit Insurer Quote Modal (Dual-Mode: Upload PDF + Manual Portal Entry) */}
      <ManualQuoteModal
        isOpen={isManualModalOpen}
        onClose={() => {
          setIsManualModalOpen(false);
          setEditingEntry(null);
        }}
        onSave={handleSaveEntry}
        initialData={editingEntry}
        tenureId={tenureId}
        onUploadSuccess={() => fetchComparison()}
      />
    </div>
  );
}
