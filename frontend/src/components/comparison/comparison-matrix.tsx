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
  Eye,
  EyeSlash,
  Camera,
  Copy,
  DownloadSimple,
  Info,
  WarningCircle,
  Warning,
  Clock,
  Sparkle,
  CloudArrowUp,
} from "@phosphor-icons/react";
import { toBlob, toPng } from "html-to-image";
import { api, fileUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ManualQuoteModal } from "./manual-quote-modal";
import { decodeMalaysianIC } from "@/lib/mykad";
import { formatBenefitCoverage } from "@/lib/benefit-utils";

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
  basic_figure_name?: string | null;
  basic_figure_amount?: number | null;
  rate_factor?: number | null;
  rate_factor_formatted?: string | null;
  rate_percentage: number | null;
  windscreen_sum_insured: number | null;
  special_perils: string | null;
  llp_llop: string | null;
  canonical_perils?: string[];
  canonical_perils_formatted?: string;
  is_recommended: boolean;
  is_manual: boolean;
  is_hidden?: boolean;
  manual_rank?: number | null;
  sort_order: number;
  rank?: number;
  version?: number;
  uploaded_at?: string;
  notes: string | null;
  quotation_ref?: string | null;
  is_takaful?: boolean;
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
    upload_sessions?: Array<{
      session_id: string;
      batch_index: number;
      uploaded_at: string | null;
      quotes: Array<{
        session_id: string;
        company_name: string;
        version: number;
      }>;
    }>;
    duplicate_alerts?: Array<{
      id: string;
      session_id: string;
      company_name: string;
      original_session_id: string;
      original_version: number;
      original_date?: string | null;
      new_version: number;
      new_date?: string | null;
      file_name?: string;
      total_payable?: number;
      quotation_date?: string | null;
    }>;
    disqualified_documents?: Array<{
      session_id: string;
      file_name: string;
      extracted_plate: string;
      plate_detected?: string;
      target_plate: string;
      company_name?: string;
      tenure_id?: string;
    }>;
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

  // Company-Level Active Versions (supports single view or side-by-side split)
  const [activeVersionsByCompany, setActiveVersionsByCompany] = useState<Record<string, string[]>>({});
  const [expandedBreakdownId, setExpandedBreakdownId] = useState<Record<string, boolean>>({});
  const [rescanningQuoteId, setRescanningQuoteId] = useState<string | null>(null);

  // Card Visibility & Ranking States
  const [showHiddenCards, setShowHiddenCards] = useState(false);
  const [highlightedSessionId, setHighlightedSessionId] = useState<string | null>(null);
  const [snapshotModalOpen, setSnapshotModalOpen] = useState(false);
  const [resolvingDuplicateId, setResolvingDuplicateId] = useState<string | null>(null);
  const [reranking, setReranking] = useState(false);
  const snapshotGridRef = useRef<HTMLDivElement>(null);
  const [copyingSnapshot, setCopyingSnapshot] = useState(false);
  const [downloadingSnapshot, setDownloadingSnapshot] = useState(false);

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
  const [isRescanning, setIsRescanning] = useState(false);
  const [isUploadingPrevPolicy, setIsUploadingPrevPolicy] = useState(false);
  const [editingRankEntryId, setEditingRankEntryId] = useState<string | null>(null);
  const [editingBasicFigureEntryId, setEditingBasicFigureEntryId] = useState<string | null>(null);
  const [basicFigureInput, setBasicFigureInput] = useState<string>("");
  const prevPolicyFileInputRef = useRef<HTMLInputElement>(null);

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
      const res = await api<any>(`/comparison/${tenureId}/entry/${entryId}/generate-quote`, {
        method: "POST",
      });
      if (res?.pdf_url) {
        const downloadUrl = fileUrl(res.pdf_url);
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = `${res.quotation_ref || "Quotation"}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else if (res?.session_id) {
        try {
          const versions = await api<any[]>(`/sessions/${res.session_id}/versions`);
          if (versions && versions.length > 0) {
            const latestVer = versions[0];
            const downloadUrl = fileUrl(`/versions/${latestVer.id}/pdf?download=true`);
            const link = document.createElement("a");
            link.href = downloadUrl;
            link.download = `${res.quotation_ref || "Quotation"}.pdf`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
          } else {
            window.open(`/sessions/${res.session_id}/review`, "_blank");
          }
        } catch {
          window.open(`/sessions/${res.session_id}/review`, "_blank");
        }
      }
      await fetchComparison(true);
    } catch (err: any) {
      alert("Failed to generate quotation: " + (err.message || String(err)));
    } finally {
      setGeneratingQuoteEntryId(null);
    }
  };

  const handleRescanQuotes = async () => {
    try {
      setIsRescanning(true);
      const updated = await api<any>(`/comparison/${tenureId}/rescan`, {
        method: "POST",
      });
      setData(updated);
    } catch (err: any) {
      alert("Failed to rescan quotes: " + (err.message || String(err)));
    } finally {
      setIsRescanning(false);
    }
  };

  const handleUploadPreviousPolicy = async (file: File) => {
    if (!file) return;
    try {
      setIsUploadingPrevPolicy(true);
      const formData = new FormData();
      formData.append("file", file);
      await api(`/comparison/${tenureId}/upload-previous-policy`, {
        method: "POST",
        body: formData,
      });
      await fetchComparison(true);
    } catch (err: any) {
      alert("Failed to upload previous policy PDF: " + (err.message || String(err)));
    } finally {
      setIsUploadingPrevPolicy(false);
      if (prevPolicyFileInputRef.current) {
        prevPolicyFileInputRef.current.value = "";
      }
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

  const handleToggleHideEntry = async (entry: ComparisonEntry) => {
    try {
      const nextHidden = !entry.is_hidden;
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          entries: prev.entries.map((e) => (e.id === entry.id ? { ...e, is_hidden: nextHidden } : e)),
        };
      });
      await api(`/comparison/${tenureId}/entries/${entry.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_hidden: nextHidden }),
      });
      await fetchComparison(true);
    } catch (err: any) {
      alert("Failed to update visibility: " + err.message);
      await fetchComparison(true);
    }
  };

  const handleSetManualRank = async (entry: ComparisonEntry, rankVal: number | null) => {
    try {
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          entries: prev.entries.map((e) => (e.id === entry.id ? { ...e, manual_rank: rankVal } : e)),
        };
      });
      await api(`/comparison/${tenureId}/entries/${entry.id}`, {
        method: "PATCH",
        body: JSON.stringify({ manual_rank: rankVal }),
      });
      await fetchComparison(true);
    } catch (err: any) {
      alert("Failed to update manual rank: " + err.message);
      await fetchComparison(true);
    }
  };

  const handleRerank = async () => {
    try {
      setReranking(true);
      await api(`/comparison/${tenureId}/rerank`, { method: "POST" });
      await fetchComparison(true);
    } catch (err: any) {
      alert("Failed to re-rank entries: " + err.message);
    } finally {
      setReranking(false);
    }
  };

  const handleResolveDuplicate = async (duplicateSessionId: string, action: "replace" | "keep" | "remove") => {
    try {
      setResolvingDuplicateId(duplicateSessionId);
      await api(`/comparison/${tenureId}/duplicates/${duplicateSessionId}/resolve`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      await fetchComparison(true);
    } catch (err: any) {
      alert("Failed to resolve duplicate quote: " + err.message);
    } finally {
      setResolvingDuplicateId(null);
    }
  };

  const handleCopySnapshot = async () => {
    if (!snapshotGridRef.current) return;
    try {
      setCopyingSnapshot(true);
      const blob = await toBlob(snapshotGridRef.current, {
        pixelRatio: 2,
        backgroundColor: "#ffffff",
        cacheBust: true,
      });
      if (blob) {
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        alert("Comparison snapshot copied to clipboard!");
      }
    } catch (err: any) {
      alert("Failed to copy snapshot: " + (err.message || String(err)));
    } finally {
      setCopyingSnapshot(false);
    }
  };

  const handleDownloadSnapshot = async () => {
    if (!snapshotGridRef.current) return;
    try {
      setDownloadingSnapshot(true);
      const dataUrl = await toPng(snapshotGridRef.current, {
        pixelRatio: 2,
        backgroundColor: "#ffffff",
        cacheBust: true,
      });
      const link = document.createElement("a");
      link.download = `quotation-comparison-${data?.tenure?.vehicle_no || "matrix"}.png`;
      link.href = dataUrl;
      link.click();
    } catch (err: any) {
      alert("Failed to download snapshot: " + (err.message || String(err)));
    } finally {
      setDownloadingSnapshot(false);
    }
  };

  // Decode Malaysian IC Date of Birth
  const decodedIc = useMemo(() => {
    return decodeMalaysianIC(data?.tenure?.ic_no);
  }, [data?.tenure?.ic_no]);

  const hiddenCount = useMemo(() => {
    return (data?.entries || []).filter((e) => e.is_hidden).length;
  }, [data?.entries]);

  // Group quotes by underwriter company name for nested quotations
  const companyGroups = useMemo(() => {
    const quoteEntries = (data?.entries || []).filter((e) => showHiddenCards || !e.is_hidden);
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
  }, [data?.entries, showHiddenCards]);

  // Helper to get active entry IDs for a company group (supports single view or side-by-side split)
  const getActiveEntryIdsForGroup = (group: { companyName: string; entries: ComparisonEntry[] }): string[] => {
    const customIds = activeVersionsByCompany[group.companyName];
    if (customIds && customIds.length > 0) {
      const valid = customIds.filter((id) => group.entries.some((e) => e.id === id));
      if (valid.length > 0) return valid;
    }
    const winner = group.entries.find((e) => e.is_recommended);
    return winner ? [winner.id] : (group.entries[0] ? [group.entries[0].id] : []);
  };

  // Quotation cards strictly visible in the UI viewport
  const visibleDisplayEntries = useMemo(() => {
    const list: ComparisonEntry[] = [];
    for (const group of companyGroups) {
      const activeIds = getActiveEntryIdsForGroup(group);
      for (const e of group.entries) {
        if (activeIds.includes(e.id) && (showHiddenCards || !e.is_hidden)) {
          list.push(e);
        }
      }
    }
    return list;
  }, [companyGroups, activeVersionsByCompany, showHiddenCards]);

  // Strict dynamic ranking computed ONLY among cards currently visible in the UI
  const visibleRanksMap = useMemo(() => {
    const sorted = [...visibleDisplayEntries].sort((a, b) => {
      if (a.manual_rank != null && b.manual_rank != null) return a.manual_rank - b.manual_rank;
      if (a.manual_rank != null) return -1;
      if (b.manual_rank != null) return 1;
      if (a.is_recommended && !b.is_recommended) return -1;
      if (!a.is_recommended && b.is_recommended) return 1;
      return (a.total_payable || 0) - (b.total_payable || 0);
    });

    const map: Record<string, number> = {};
    sorted.forEach((item, index) => {
      map[item.id] = index + 1;
    });
    return map;
  }, [visibleDisplayEntries]);

  // Snapshot cards strictly bound to visible cards and visible ranks
  const snapshotVisibleCards = useMemo(() => {
    return [...visibleDisplayEntries].sort((a, b) => {
      const rankA = visibleRanksMap[a.id] || 999;
      const rankB = visibleRanksMap[b.id] || 999;
      return rankA - rankB;
    });
  }, [visibleDisplayEntries, visibleRanksMap]);

  // Active winning quotation dynamically feeding Current Policy section
  const currentPolicyWinner = useMemo(() => {
    return (
      (data?.entries || []).find((e) => e.is_recommended) ||
      visibleDisplayEntries.find((e) => visibleRanksMap[e.id] === 1) ||
      visibleDisplayEntries[0] ||
      null
    );
  }, [data?.entries, visibleDisplayEntries, visibleRanksMap]);

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
    activeIds: string[]
  ) => {
    const isWinner = entry.is_recommended;
    const isViewingPdf = activePdfSession?.sessionId === entry.session_id;

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
          {/* 4-Row Card Header */}
          <div className={`p-4 border-b ${isWinner ? "border-[#e5e5ea] bg-[#f5f5f7]/60" : "border-[#e5e5ea]"}`}>
            {/* Row 1: Company Name + Visibility Toggle */}
            <div className="flex items-center justify-between gap-2 min-h-[26px]">
              <h3 className="font-bold text-sm text-[#1b1717] uppercase tracking-tight truncate" title={entry.company_name}>
                {entry.company_name}
              </h3>
              <div className="flex items-center gap-1 shrink-0">
                {isViewingPdf && (
                  <span className="rounded bg-[#1b1717] text-white px-1.5 py-0.2 text-[9px] font-bold">
                    PDF ★
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => handleToggleHideEntry(entry)}
                  className={`p-1 rounded text-neutral-400 hover:text-[#1b1717] hover:bg-neutral-100 transition-colors cursor-pointer ${
                    entry.is_hidden ? "text-neutral-400 bg-neutral-100" : ""
                  }`}
                  title={entry.is_hidden ? "Unhide this quotation card" : "Hide this card from comparison & snapshot"}
                >
                  {entry.is_hidden ? <EyeSlash size={15} weight="bold" /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* Row 2: Rank badge with clean highlight & instant click-to-rank picker (NO Auto, NO Best Deal, NO trophies) */}
            <div className="mt-2 min-h-[26px] flex items-center justify-between gap-1">
              {editingRankEntryId === entry.id && visibleDisplayEntries.length > 1 ? (
                <div className="flex items-center gap-1 flex-wrap py-0.5">
                  <span className="text-[10px] text-[#6e6e73] font-bold mr-0.5">Rank:</span>
                  {Array.from({ length: visibleDisplayEntries.length }, (_, i) => i + 1).map((num) => {
                    const currentRank = visibleRanksMap[entry.id] ?? 1;
                    return (
                      <button
                        key={num}
                        type="button"
                        onClick={() => {
                          handleSetManualRank(entry, num);
                          setEditingRankEntryId(null);
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
                    onClick={() => setEditingRankEntryId(null)}
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
                    const canEdit = visibleDisplayEntries.length > 1;
                    return (
                      <button
                        type="button"
                        disabled={!canEdit}
                        onClick={() => canEdit && setEditingRankEntryId(entry.id)}
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

            {/* Row 3: Dedicated Version Row (v1, v2, v3...) without Split text or Quote 1/2 */}
            <div className="mt-2 min-h-[26px] flex items-center gap-1.5 flex-wrap">
              {group.entries.map((q, qIdx) => {
                const isThisActive = activeIds.includes(q.id);
                const isThisCard = q.id === entry.id;
                const isEntryWinner = q.is_recommended;
                const formattedUpload = q.uploaded_at
                  ? new Date(q.uploaded_at).toLocaleString("en-GB", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                      hour12: true,
                    })
                  : "Uploaded Quote";

                return (
                  <button
                    key={q.id}
                    type="button"
                    onClick={() => {
                      setActiveVersionsByCompany((prev) => {
                        const current = getActiveEntryIdsForGroup(group);
                        if (current.includes(q.id)) {
                          if (current.length > 1) {
                            return {
                              ...prev,
                              [group.companyName]: current.filter((id) => id !== q.id),
                            };
                          }
                          return prev;
                        } else {
                          return {
                            ...prev,
                            [group.companyName]: [...current, q.id],
                          };
                        }
                      });
                    }}
                    className={`px-2.5 py-0.5 rounded text-[11px] font-bold transition-all flex items-center gap-1 cursor-pointer shrink-0 ${
                      isThisCard
                        ? "bg-[#1b1717] text-white shadow-xs"
                        : isThisActive
                        ? "bg-neutral-700 text-white hover:bg-neutral-800"
                        : "bg-[#f5f5f7] text-[#454545] hover:bg-neutral-200 border border-[#e5e5ea]"
                    }`}
                    title={`v${q.version || qIdx + 1} • Uploaded: ${formattedUpload} • RM ${q.total_payable.toFixed(2)} (${
                      q.valuation_type === "agreed_value" ? "Agreed" : "Market"
                    }) • Click to toggle side-by-side view`}
                  >
                    <span>v{q.version || qIdx + 1}</span>
                    {isEntryWinner && (
                      <Star
                        weight="fill"
                        size={10}
                        className={isThisCard ? "text-amber-300" : "text-amber-500"}
                      />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Row 4: Valuation */}
            <div className="mt-2 pt-1 border-t border-[#e5e5ea]/80 flex items-center justify-between">
              <span className="text-xs text-[#6e6e73] font-medium">
                {entry.valuation_type === "agreed_value" ? "Agreed Value 约定价" : "Market Value 市价"}
              </span>
              <span className="font-mono text-[10px] text-[#8e8e93]">
                {entry.valuation_type === "agreed_value" ? "[A]" : "[M]"}
              </span>
            </div>
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
              <span className="font-bold text-[#1b1717]">{formatBenefitCoverage(entry.towing_km || entry.towing_limit || "Unlimited", "KM")}</span>
            </div>

            {/* Agreed Value */}
            <div className="flex items-center justify-between pt-2">
              <span className="text-[#6e6e73]">Agreed Value:</span>
              <span className={`font-bold ${entry.agreed_value ? "text-emerald-700" : "text-[#6e6e73]"}`}>
                {entry.agreed_value ? "Yes" : "No"}
              </span>
            </div>

            {/* Betterment Co-pay / Waiver */}
            {/* Betterment Co-pay / Waiver with BNM Scale Tooltip */}
            <div className="flex items-center justify-between pt-2">
              <div className="flex items-center gap-1 text-[#6e6e73]">
                <span>Betterment (自付额):</span>
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
            <div className="flex items-center justify-between pt-2">
              <span className="text-[#6e6e73]">Excess:</span>
              <span className="font-mono font-bold text-[#1b1717]">
                RM {entry.excess.toFixed(2)}
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
                {entry.special_perils ? formatBenefitCoverage(entry.special_perils, "RM") : "Not Included"}
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

            {/* Collapsible Underwriter Breakdown & Basic Figure */}
            <div className="pt-2">
              <button
                type="button"
                onClick={() =>
                  setExpandedBreakdownId((prev) => ({
                    ...prev,
                    [entry.id]: !prev[entry.id],
                  }))
                }
                className="w-full flex items-center justify-between py-1.5 px-2 rounded-lg bg-[#f5f5f7] hover:bg-neutral-200 text-[11px] font-bold text-[#1b1717] transition-colors cursor-pointer"
              >
                <span>{entry.basic_figure_name || (entry.is_takaful ? "Basic Contribution" : "Basic Premium")} &amp; Breakdown</span>
                <span className="text-xs text-[#6e6e73] font-mono">
                  {expandedBreakdownId[entry.id] ? "▲ Hide" : "▼ Show"}
                </span>
              </button>

              {expandedBreakdownId[entry.id] && (
                <div className="mt-2 p-2.5 rounded-xl bg-neutral-50 border border-[#e5e5ea] space-y-2 text-xs">
                  {/* Basic Contribution / Basic Premium with Inline Edit */}
                  <div className="flex items-center justify-between">
                    <span className="text-[#6e6e73] font-medium">
                      {entry.basic_figure_name || (entry.is_takaful ? "Basic Contribution" : "Basic Premium")}:
                    </span>
                    {editingBasicFigureEntryId === entry.id ? (
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-[#6e6e73]">RM</span>
                        <input
                          type="number"
                          step="0.01"
                          value={basicFigureInput}
                          onChange={(e) => setBasicFigureInput(e.target.value)}
                          className="w-20 px-1.5 py-0.5 text-xs font-mono font-bold bg-white border border-[#1b1717] rounded focus:outline-none"
                          autoFocus
                        />
                        <button
                          type="button"
                          onClick={async () => {
                            const val = parseFloat(basicFigureInput);
                            if (!isNaN(val)) {
                              try {
                                await api(`/comparison/${tenureId}/entries/${entry.id}`, {
                                  method: "PATCH",
                                  body: JSON.stringify({ basic_figure_amount: val }),
                                });
                                await fetchComparison(true);
                              } catch (err: any) {
                                alert("Failed to update figure: " + err.message);
                              }
                            }
                            setEditingBasicFigureEntryId(null);
                          }}
                          className="px-1.5 py-0.5 text-[10px] font-bold bg-[#1b1717] text-white rounded hover:bg-neutral-800 cursor-pointer"
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingBasicFigureEntryId(null)}
                          className="px-1 py-0.5 text-[10px] text-[#6e6e73] hover:text-[#1b1717] cursor-pointer"
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-bold text-[#1b1717]">
                          RM {(entry.basic_figure_amount || 0).toFixed(2)}
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            setEditingBasicFigureEntryId(entry.id);
                            setBasicFigureInput(String(entry.basic_figure_amount || ""));
                          }}
                          className="text-[10px] text-[#6e6e73] hover:text-[#1b1717] underline cursor-pointer"
                          title="Edit basic figure to correct OCR typos"
                        >
                          Edit
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Sum Insured */}
                  <div className="flex items-center justify-between">
                    <span className="text-[#6e6e73] font-medium">Sum Insured:</span>
                    <span className="font-mono font-bold text-[#1b1717]">
                      RM {entry.sum_insured.toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                    </span>
                  </div>

                  {/* Net Rate Factor: 6 decimals (Basic Figure ÷ Sum Insured) */}
                  <div className="flex items-center justify-between">
                    <span className="text-[#6e6e73] font-medium">Net Rate Factor:</span>
                    <span
                      className="font-mono font-bold text-[#1b1717]"
                      title={`${entry.basic_figure_name || "Basic Figure"} RM ${(entry.basic_figure_amount || 0).toFixed(2)} ÷ RM ${entry.sum_insured.toFixed(2)}`}
                    >
                      {entry.sum_insured > 0 && entry.basic_figure_amount != null
                        ? (entry.basic_figure_amount / entry.sum_insured).toFixed(6)
                        : entry.rate_factor_formatted || "—"}
                    </span>
                  </div>

                  {/* Betterment Rule Analysis */}
                  <div className="pt-1.5 border-t border-[#e5e5ea]/80 text-[11px] text-[#6e6e73] space-y-1">
                    <div className="flex items-center justify-between">
                      <span>Vehicle Age:</span>
                      <span className="font-semibold text-[#1b1717]">
                        {data?.vehicle_age != null ? `${data.vehicle_age} Years` : "—"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Betterment Scale:</span>
                      <span className="font-semibold text-[#1b1717]">
                        {entry.betterment_rate != null ? `${entry.betterment_rate}%` : (entry.betterment_display || "—")}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Waiver Status:</span>
                      <span className={`font-semibold ${entry.waiver_betterment ? "text-emerald-700" : "text-amber-700"}`}>
                        {entry.waiver_betterment ? "Waived (0% Co-pay)" : "Standard Tariff Co-pay"}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
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

          {/* Re-Analyze Single Quote Button */}
          <button
            type="button"
            disabled={rescanningQuoteId === entry.id || isRescanning}
            onClick={async () => {
              try {
                setRescanningQuoteId(entry.id);
                const updated = await api<any>(`/comparison/${tenureId}/rescan`, {
                  method: "POST",
                });
                setData(updated);
              } catch (err: any) {
                alert("Failed to re-analyze quote: " + (err.message || String(err)));
              } finally {
                setRescanningQuoteId(null);
              }
            }}
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
              target="_blank"
              rel="noopener noreferrer"
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
                target="_blank"
                rel="noopener noreferrer"
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
                      target="_blank"
                      rel="noopener noreferrer"
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

      {/* Duplicate Quote Alert Banner */}
      {data.duplicate_alerts && data.duplicate_alerts.length > 0 && (
        <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 shadow-xs space-y-3 no-print print:hidden">
          <div className="flex items-center gap-2 text-amber-900 font-bold text-sm">
            <WarningCircle size={18} weight="fill" className="text-amber-600" />
            <span>Duplicate Quotation Version Detected</span>
          </div>
          <div className="space-y-2">
            {data.duplicate_alerts.map((dup) => (
              <div
                key={dup.session_id}
                className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-amber-200"
              >
                <div className="text-xs text-neutral-800">
                  <span className="font-bold">{dup.company_name}</span> · Quoted{" "}
                  <strong className="font-mono">RM {(dup.total_payable || 0).toFixed(2)}</strong> (Date: {dup.quotation_date || "N/A"})
                  <span className="ml-2 text-neutral-500 font-mono text-[11px]">[{dup.file_name || "Quotation.pdf"}]</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={resolvingDuplicateId === dup.session_id}
                    onClick={() => handleResolveDuplicate(dup.session_id, "replace")}
                    className="text-xs font-semibold hover:border-black"
                  >
                    Replace Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={resolvingDuplicateId === dup.session_id}
                    onClick={() => handleResolveDuplicate(dup.session_id, "keep")}
                    className="text-xs font-semibold hover:border-black"
                  >
                    Keep Both
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={resolvingDuplicateId === dup.session_id}
                    onClick={() => handleResolveDuplicate(dup.session_id, "remove")}
                    className="text-xs font-semibold text-rose-600 hover:border-rose-300"
                  >
                    Remove
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Disqualified Documents Due to Plate Mismatch Banner */}
      {data.disqualified_documents && data.disqualified_documents.length > 0 && (
        <div className="rounded-2xl border border-rose-300 bg-rose-50 p-4 text-xs text-rose-950 shadow-xs flex items-start justify-between gap-3 no-print print:hidden">
          <div className="space-y-1">
            <p className="font-bold flex items-center gap-1.5 text-rose-900">
              <WarningCircle size={16} weight="bold" className="text-rose-600" />
              {data.disqualified_documents.length} Uploaded File(s) Disqualified Due to Plate Mismatch
            </p>
            <p className="text-rose-800 leading-relaxed">
              The following file(s) did not match target vehicle plate{" "}
              <strong className="font-mono font-bold text-rose-950">{tenure.vehicle_no}</strong> and were routed out of this matrix to prevent cross-vehicle rate contamination:
            </p>
            <div className="flex flex-wrap gap-2 pt-1 font-mono text-[11px]">
              {data.disqualified_documents.map((doc, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-white rounded border border-rose-200 text-rose-900 font-semibold shadow-2xs"
                >
                  {doc.file_name} → Plate: <span className="font-bold">{doc.plate_detected || doc.extracted_plate || "UNKNOWN"}</span> ({doc.company_name || "Underwriter"})
                </span>
              ))}
            </div>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-rose-800 bg-rose-200/70 px-2 py-1 rounded shrink-0">
            Disqualified
          </span>
        </div>
      )}

      {/* Top-Level Session Timeline Ribbon */}
      {data.upload_sessions && data.upload_sessions.length > 0 && (
        <div className="rounded-2xl border border-[#e5e5ea] bg-white p-3 shadow-xs flex items-center gap-3 overflow-x-auto no-print print:hidden">
          <div className="flex items-center gap-1.5 text-xs font-bold text-[#1b1717] shrink-0 pl-1">
            <Clock size={16} weight="bold" className="text-[#6e6e73]" />
            <span>Session Timeline:</span>
          </div>
          <div className="flex items-center gap-2">
            {data.upload_sessions.map((batch, idx) => {
              const qNames = batch.quotes.map((q) => `${q.company_name} v${q.version}`).join(", ");
              const isHighlighted =
                batch.quotes.some((q) => q.session_id === highlightedSessionId) ||
                batch.session_id === highlightedSessionId;
              const firstSid = batch.quotes[0]?.session_id || batch.session_id;

              return (
                <div
                  key={batch.session_id}
                  onClick={() => setHighlightedSessionId(isHighlighted ? null : firstSid)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs cursor-pointer transition-all shrink-0 ${
                    isHighlighted
                      ? "bg-[#1b1717] text-white border-[#1b1717] shadow-sm"
                      : "bg-[#f5f5f7] hover:bg-[#e5e5ea] text-[#1b1717] border-[#e5e5ea]"
                  }`}
                  title={
                    batch.uploaded_at
                      ? `Uploaded at ${new Date(batch.uploaded_at).toLocaleTimeString()}`
                      : `Batch #${batch.batch_index || idx + 1}`
                  }
                >
                  <span
                    className={`size-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                      isHighlighted ? "bg-white text-[#1b1717]" : "bg-[#1b1717] text-white"
                    }`}
                  >
                    {batch.batch_index || idx + 1}
                  </span>
                  <span className="font-semibold">{qNames || "Quotation Batch"}</span>
                  <span className="text-[10px] opacity-70">
                    ({batch.quotes.length} {batch.quotes.length === 1 ? "quote" : "quotes"})
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

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
        <div className="flex items-center gap-2 flex-wrap no-print print:hidden">
          {hiddenCount > 0 && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowHiddenCards(!showHiddenCards)}
              icon={showHiddenCards ? <EyeSlash size={15} /> : <Eye size={15} />}
              className="border-neutral-300 text-xs font-semibold bg-neutral-50 hover:bg-neutral-100"
            >
              {showHiddenCards ? "Hide Inactive" : `${hiddenCount} hidden · Show All`}
            </Button>
          )}

          <Button
            variant="secondary"
            size="sm"
            onClick={handleRescanQuotes}
            loading={isRescanning}
            icon={<ArrowsClockwise size={15} weight="bold" className={isRescanning ? "animate-spin text-[#ed1c24]" : "text-[#ed1c24]"} />}
            className="border-2 border-[#1b1717] bg-[#f5f5f7] hover:bg-neutral-200 text-[#1b1717] font-bold"
            title="Re-extract and re-sync values from all uploaded quotation PDFs, re-evaluating Betterment rules and windscreen targets"
          >
            Re-Analyze All Quotes
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={handleRerank}
            loading={reranking}
            icon={<ArrowsClockwise size={15} weight="bold" />}
            title="Recalculate dynamic ranking order based on visible cards and manual overrides"
          >
            Re-Rank
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => setSnapshotModalOpen(true)}
            icon={<Camera size={15} weight="bold" />}
            className="border-[#e5e5ea] bg-white hover:border-[#1b1717] text-[#1b1717] font-semibold"
            title="Export high-resolution comparison snapshot grid"
          >
            Export Snapshot
          </Button>

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
              const activeIds = getActiveEntryIdsForGroup(group);
              const activeEntries = group.entries.filter(
                (e) => activeIds.includes(e.id) && (showHiddenCards || !e.is_hidden)
              );
              const entriesToRender =
                activeEntries.length > 0
                  ? activeEntries
                  : group.entries.filter((e) => showHiddenCards || !e.is_hidden).slice(0, 1);

              return entriesToRender.map((entry) =>
                renderUnderwriterCard(entry, group, activeIds)
              );
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
          {/* Current Policy Card (Dynamically reflecting selected winner quote terms) */}
          {(() => {
            const currentYear = tenure.coverage_start_date ? new Date(tenure.coverage_start_date).getFullYear() : new Date().getFullYear();
            return (
              <div className="rounded-2xl border-2 border-[#1b1717] bg-white p-4 shadow-sm">
                <div className="flex items-center justify-between border-b border-[#e5e5ea] pb-2.5 mb-3">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold uppercase tracking-wider text-[#1b1717]">
                      Current Policy ({currentYear})
                    </span>
                    <span className="rounded bg-amber-400 text-amber-950 font-bold px-1.5 py-0.2 text-[9px] uppercase">
                      {currentPolicyWinner?.is_recommended ? "Selected Winner" : "Leading Option"}
                    </span>
                  </div>
                  {currentPolicyWinner && (
                    <span className="rounded bg-[#1b1717] px-2 py-0.5 text-xs font-bold text-white">
                      {currentPolicyWinner.company_name}
                    </span>
                  )}
                </div>

                {currentPolicyWinner ? (
                  <div className="space-y-2 text-xs text-[#454545]">
                    <div className="flex justify-between">
                      <span className="text-[#6e6e73]">Sum Insured:</span>
                      <span className="font-mono font-bold text-[#1b1717]">
                        RM {currentPolicyWinner.sum_insured.toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                        <span className="text-[10px] text-[#6e6e73] font-normal ml-1">
                          ({currentPolicyWinner.valuation_type === "agreed_value" ? "Agreed" : "Market"})
                        </span>
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#6e6e73]">Premium Payable:</span>
                      <span className="font-mono font-bold text-emerald-700">
                        RM {(currentPolicyWinner.rounded_total_payable != null ? currentPolicyWinner.rounded_total_payable : currentPolicyWinner.total_payable).toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between items-start gap-2">
                      <span className="text-[#6e6e73] shrink-0">Included Perils:</span>
                      <span className="font-medium text-[#1b1717] text-right">
                        {currentPolicyWinner.canonical_perils_formatted || "Standard Policy Coverage"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#6e6e73]">YOM / Model:</span>
                      <span className="font-medium text-[#1b1717]">
                        {tenure.manufacture_year || ""} {tenure.vehicle_model}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-4 text-xs text-[#6e6e73]">
                    <p>No quotes active yet.</p>
                  </div>
                )}
              </div>
            );
          })()}

          {/* Previous Policy Card (Strict DB prior calendar year, zero gibberish fallbacks) */}
          {(() => {
            const currentYear = tenure.coverage_start_date ? new Date(tenure.coverage_start_date).getFullYear() : new Date().getFullYear();
            const prevYear = previous_policy?.year || currentYear - 1;
            return (
              <div className="rounded-2xl border border-[#e5e5ea] bg-white p-4 shadow-sm">
                <div className="flex items-center justify-between border-b border-[#e5e5ea] pb-2.5 mb-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#1b1717]">
                    Previous Policy ({prevYear})
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
                    <div className="flex justify-between items-start gap-2">
                      <span className="text-[#6e6e73] shrink-0">Included Perils:</span>
                      <span className="font-medium text-[#1b1717] text-right">
                        {previous_policy.perils || "Standard Policy Coverage"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#6e6e73]">YOM / Model:</span>
                      <span className="font-medium text-[#1b1717]">
                        {previous_policy.yom || ""} {previous_policy.model || tenure.vehicle_model}
                      </span>
                    </div>
                    <div className="pt-2 border-t border-[#e5e5ea] flex justify-end">
                      <button
                        type="button"
                        onClick={() => prevPolicyFileInputRef.current?.click()}
                        disabled={isUploadingPrevPolicy}
                        className="text-[11px] font-semibold text-[#6e6e73] hover:text-[#1b1717] flex items-center gap-1 cursor-pointer"
                      >
                        <CloudArrowUp size={13} weight="bold" />
                        <span>{isUploadingPrevPolicy ? "Uploading..." : `Replace ${prevYear} PDF`}</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-4 text-xs text-[#6e6e73] space-y-2">
                    <p>No {prevYear} policy record found in database.</p>
                    <button
                      type="button"
                      onClick={() => prevPolicyFileInputRef.current?.click()}
                      disabled={isUploadingPrevPolicy}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#e5e5ea] bg-[#f5f5f7] hover:bg-[#e5e5ea] text-xs font-bold text-[#1b1717] transition-colors cursor-pointer"
                    >
                      <CloudArrowUp size={15} weight="bold" />
                      <span>{isUploadingPrevPolicy ? "Uploading..." : `Upload ${prevYear} PDF`}</span>
                    </button>
                    <p className="text-[10px] text-neutral-400">Upload previous schedule/quote to compare past terms</p>
                  </div>
                )}

                <input
                  type="file"
                  ref={prevPolicyFileInputRef}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleUploadPreviousPolicy(file);
                  }}
                  accept=".pdf"
                  className="hidden"
                />
              </div>
            );
          })()}

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
                    target="_blank"
                    rel="noopener noreferrer"
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

      {/* High-Resolution NxM Comparison Snapshot Modal */}
      {snapshotModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto no-print">
          <div className="bg-white rounded-3xl shadow-2xl border border-neutral-200 max-w-7xl w-full flex flex-col max-h-[92vh] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Control Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#e5e5ea] bg-[#f5f5f7]">
              <div>
                <h3 className="text-base font-bold text-[#1b1717] flex items-center gap-2">
                  <Camera size={20} weight="fill" className="text-[#1b1717]" />
                  Executive Comparison Snapshot Grid
                </h3>
                <p className="text-xs text-[#6e6e73]">
                  High-resolution snapshot of {snapshotVisibleCards.length} ranked underwriter option{snapshotVisibleCards.length !== 1 ? "s" : ""}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleCopySnapshot}
                  loading={copyingSnapshot}
                  icon={<Copy size={15} weight="bold" />}
                  className="font-bold border-neutral-300 hover:border-black"
                >
                  Copy to Clipboard
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleDownloadSnapshot}
                  loading={downloadingSnapshot}
                  icon={<DownloadSimple size={15} weight="bold" />}
                  className="bg-[#1b1717] hover:bg-black text-white font-bold"
                >
                  Download PNG
                </Button>
                <button
                  type="button"
                  onClick={() => setSnapshotModalOpen(false)}
                  className="p-1.5 rounded-xl border border-neutral-300 hover:bg-neutral-200 text-neutral-600 transition-colors ml-2 cursor-pointer"
                  title="Close Snapshot"
                >
                  <X size={18} weight="bold" />
                </button>
              </div>
            </div>

            {/* Modal Body: Scrollable Canvas container */}
            <div className="flex-1 overflow-auto p-6 bg-neutral-100 flex items-center justify-center">
              {/* Snapshot Canvas targeted by html-to-image */}
              <div
                ref={snapshotGridRef}
                className="bg-white p-8 rounded-3xl border border-neutral-200 shadow-xl w-full max-w-6xl space-y-6"
                style={{ minWidth: snapshotVisibleCards.length <= 3 ? "760px" : "1040px" }}
              >
                {/* Snapshot Brand & Vehicle Header */}
                <div className="flex items-start justify-between border-b-2 border-[#1b1717] pb-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-black bg-[#1b1717] text-white px-2.5 py-1 rounded-md tracking-widest">
                        RISK-LOCKER
                      </span>
                      <h2 className="text-lg font-black tracking-tight text-[#1b1717]">
                        MOTOR QUOTATION COMPARISON REPORT
                      </h2>
                    </div>
                    <p className="text-xs text-[#6e6e73]">
                      Market Underwriter Benchmarking · Policy Period: {tenure.coverage_period_formatted}
                    </p>
                  </div>

                  <div className="text-right space-y-0.5">
                    <div className="inline-block bg-[#f5f5f7] border border-[#e5e5ea] px-3 py-1 rounded-lg">
                      <span className="font-mono font-bold text-base text-[#1b1717]">
                        {tenure.vehicle_no || tenure.chassis_no || "Unregistered Vehicle"}
                      </span>
                    </div>
                    <p className="font-bold text-xs text-[#1b1717]">{tenure.customer_name}</p>
                    <p className="text-[11px] text-[#6e6e73]">{tenure.vehicle_model} · {tenure.engine_cc}</p>
                    <p className="text-[10px] font-semibold text-[#6e6e73]">
                      Road Tax: RM {tenure.road_tax.toFixed(2)} · Runner Fee: RM {tenure.runner_fee.toFixed(2)}
                    </p>
                  </div>
                </div>

                {/* Visible Cards Grid (strictly ordered by rank) */}
                <div
                  className={`grid gap-4 ${
                    snapshotVisibleCards.length === 1
                      ? "grid-cols-1 max-w-sm mx-auto"
                      : snapshotVisibleCards.length === 2
                      ? "grid-cols-2"
                      : snapshotVisibleCards.length === 3
                      ? "grid-cols-3"
                      : snapshotVisibleCards.length === 4
                      ? "grid-cols-4"
                      : snapshotVisibleCards.length === 5
                      ? "grid-cols-5"
                      : "grid-cols-2 md:grid-cols-3 lg:grid-cols-4"
                  }`}
                >
                  {snapshotVisibleCards.map((card, idx) => {
                    const isWinner = card.is_recommended;
                    const rankNum = visibleRanksMap[card.id] || card.rank || idx + 1;
                    return (
                      <div
                        key={card.id}
                        className={`rounded-2xl p-4 flex flex-col justify-between border-2 transition-all ${
                          isWinner
                            ? "border-[#1b1717] bg-white ring-2 ring-[#1b1717]/10 shadow-md"
                            : "border-neutral-200 bg-[#fbfbfb]"
                        }`}
                      >
                        <div className="space-y-3">
                          {/* Rank Badge & Winner Pill */}
                          <div className="flex items-center justify-between gap-1.5">
                            <span
                              className={`text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full ${
                                rankNum === 1
                                  ? "bg-amber-100 text-amber-900 border border-amber-300"
                                  : "bg-neutral-100 text-neutral-700 border border-neutral-200"
                              }`}
                            >
                              {`Rank #${rankNum}`}
                            </span>
                            {isWinner && (
                              <span className="text-[10px] font-bold uppercase bg-emerald-100 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded-full">
                                Recommended
                              </span>
                            )}
                          </div>

                          {/* Company Name */}
                          <div>
                            <h4 className="font-black text-sm text-[#1b1717] tracking-tight uppercase truncate">
                              {card.company_name}
                            </h4>
                            <p className="text-[11px] text-[#6e6e73] font-mono">
                              {card.is_takaful ? "Islamic Takaful" : "Conventional"}
                            </p>
                          </div>

                          {/* Premium Pricing Block */}
                          <div className="rounded-xl bg-white p-3 border border-neutral-200 space-y-1">
                            <div className="flex justify-between items-baseline text-xs text-[#6e6e73]">
                              <span>Sum Insured:</span>
                              <span className="font-mono font-bold text-[#1b1717]">
                                RM {card.sum_insured.toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                            <div className="pt-1 border-t border-neutral-100 flex justify-between items-baseline">
                              <span className="text-xs font-bold text-[#1b1717]">Total Payable:</span>
                              <span className="font-mono font-black text-base text-[#1b1717]">
                                RM {card.total_payable.toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                            {(card.rate_factor_formatted || (card.sum_insured > 0 && card.basic_figure_amount != null)) && (
                              <div className="flex justify-between items-center text-[10px] text-neutral-500 pt-0.5">
                                <span>Rate:</span>
                                <span className="font-mono font-semibold">
                                  {card.sum_insured > 0 && card.basic_figure_amount != null
                                    ? (card.basic_figure_amount / card.sum_insured).toFixed(6)
                                    : card.rate_factor_formatted}
                                </span>
                              </div>
                            )}
                          </div>

                          {/* Benefit Highlights */}
                          <div className="space-y-1 text-[11px] pt-1 border-t border-neutral-200/60">
                            <div className="flex justify-between">
                              <span className="text-[#6e6e73]">Valuation:</span>
                              <span className="font-semibold text-[#1b1717]">
                                {card.valuation_type === "agreed_value" ? "Agreed Value 约定价" : "Market Value 市价"}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[#6e6e73]">NCD:</span>
                              <span className="font-mono font-bold text-[#1b1717]">
                                {tenure.ncd_percentage != null
                                  ? `${tenure.ncd_percentage}%`
                                  : data.ncd?.current != null
                                  ? `${data.ncd.current}%`
                                  : "0%"}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[#6e6e73]">Windscreen:</span>
                              <span className="font-mono font-semibold text-[#1b1717]">
                                {card.windscreen_sum_insured && card.windscreen_sum_insured > 0
                                  ? `RM ${card.windscreen_sum_insured.toLocaleString()}`
                                  : "None"}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[#6e6e73]">Flood / Perils:</span>
                              <span
                                className={`font-semibold ${
                                  card.special_perils && card.special_perils !== "0" && card.special_perils !== "None"
                                    ? "text-emerald-700"
                                    : "text-neutral-400"
                                  }`}
                              >
                                {card.special_perils && card.special_perils !== "0" && card.special_perils !== "None"
                                  ? "Covered"
                                  : "Not Included"}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[#6e6e73]">Betterment:</span>
                              <span className="font-semibold text-[#1b1717]">
                                {card.betterment_display || (card.waiver_betterment ? "No (0%)" : "Yes")}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[#6e6e73]">LLP / LLOP:</span>
                              <span className="font-semibold text-[#1b1717]">
                                {card.llp_llop || "—"}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-[#6e6e73]">Towing Limit:</span>
                              <span className="font-mono font-semibold text-[#1b1717]">
                                {card.towing_limit || card.towing_km || "Standard"}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="pt-3 mt-3 border-t border-neutral-200 text-center">
                          <span className="text-[10px] font-mono text-neutral-400">
                            Ref:{" "}
                            {card.quotation_ref ||
                              card.notes ||
                              (card.session_id ? `ID: ${card.session_id.slice(0, 8)}` : "N/A")}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Footer disclaimer */}
                <div className="flex items-center justify-between text-[10px] text-neutral-400 pt-2 border-t border-neutral-200">
                  <span>Confidential quotation benchmarking prepared by Risk-Locker</span>
                  <span className="font-mono">
                    Generated {new Date().toLocaleDateString("en-MY")}, {new Date().toLocaleTimeString("en-MY", { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
              </div>
            </div>
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
        tenureStartDate={tenure?.coverage_start_date}
        onUploadSuccess={() => fetchComparison()}
      />
    </div>
  );
}
