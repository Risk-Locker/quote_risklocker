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
  CaretDown,
  CaretUp,
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
  ClipboardText,
  CheckCircle,
} from "@phosphor-icons/react";
import { toBlob, toPng } from "html-to-image";
import { api, fileUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ManualQuoteModal } from "./manual-quote-modal";
import { UnlinkCovernoteModal } from "./components/UnlinkCovernoteModal";
import { DetectionLogsModal } from "./components/DetectionLogsModal";
import { NcdEntitlementModal } from "./components/NcdEntitlementModal";
import { SnapshotPreviewModal } from "./components/SnapshotPreviewModal";
import { SourcePdfViewerPane } from "./components/SourcePdfViewerPane";
import { UnderwriterQuoteCard } from "./components/UnderwriterQuoteCard";
import { CustomerVehicleLedgerPane } from "./components/CustomerVehicleLedgerPane";
import { PreviousPolicyValuationPane } from "./components/PreviousPolicyValuationPane";
import { decodeMalaysianIC } from "@/lib/mykad";
import { formatBenefitCoverage, formatShortInsurerName } from "@/lib/benefit-utils";

function formatExpiryDateDisplay(tenure?: any, prevPolicy?: any): string {
  if (prevPolicy?.coverage_end_date) {
    const d = new Date(prevPolicy.coverage_end_date);
    if (!isNaN(d.getTime())) {
      const day = String(d.getDate()).padStart(2, "0");
      const month = String(d.getMonth() + 1).padStart(2, "0");
      return `${day}/${month}/${d.getFullYear()}`;
    }
  }
  if (tenure?.coverage_end_date) {
    const d = new Date(tenure.coverage_end_date);
    if (!isNaN(d.getTime())) {
      const day = String(d.getDate()).padStart(2, "0");
      const month = String(d.getMonth() + 1).padStart(2, "0");
      return `${day}/${month}/${d.getFullYear()}`;
    }
  }
  if (tenure?.expiry_month && tenure.expiry_month.includes("-")) {
    const [y, m] = tenure.expiry_month.split("-");
    if (y && m) return `${m.padStart(2, "0")}/${y}`;
  }
  return tenure?.expiry_month || "—";
}

function formatLlpLlop(val: string | null | undefined): string {
  if (!val) return "Not Included";
  const trimmed = val.trim();
  if (
    !trimmed ||
    trimmed === "-" ||
    trimmed === "—" ||
    trimmed.toLowerCase() === "none" ||
    trimmed.toLowerCase() === "not included"
  ) {
    return "Not Included";
  }
  return trimmed;
}

function isLlpLlopIncluded(val: string | null | undefined): boolean {
  if (!val) return false;
  const trimmed = val.trim().toLowerCase();
  return (
    trimmed !== "" &&
    trimmed !== "-" &&
    trimmed !== "—" &&
    trimmed !== "none" &&
    trimmed !== "not included"
  );
}

interface ComparisonMatrixProps {
  tenureId: string;
}

interface TenureSpec {
  id: string;
  vehicle_no: string;
  is_plate_undetected?: boolean;
  tracking_by_chassis?: boolean;
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
  car_brand?: string | null;
  vehicle_model: string;
  vehicle_type: string;
  winning_file_id?: string | null;
  winning_file_name?: string | null;
  policy_number?: string | null;
  covernote_session_id?: string | null;
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
  source_quotation_no?: string | null;
  is_takaful?: boolean;
  ncd_percentage?: number | null;
  customer_name?: string | null;
  customer_address?: string | null;
  ic_or_brn?: string | null;
  vehicle_no?: string | null;
  engine_no?: string | null;
  chassis_no?: string | null;
  vehicle_year?: string | null;
  engine_cc?: string | null;
  vehicle_age?: number | null;
  detailed_perils?: Array<{
    name: string;
    coverage_limit?: string | number | null;
    premium_cost?: number;
    has_cost?: boolean;
    is_included?: boolean;
  }>;
  coverage_start_date?: string | null;
  coverage_end_date?: string | null;
  coverage_period_formatted?: string | null;
  uploaded_file_id?: string | null;
  original_filename?: string | null;
}

export function ComparisonMatrix({ tenureId }: ComparisonMatrixProps) {
  const router = useRouter();
  const [data, setData] = useState<{
    tenure: TenureSpec;
    entries: ComparisonEntry[];
    previous_policy: any;
    recommended_sum_insured: Record<string, number>;
    ncd: { current: number | null; next: number | null; current_period?: string; next_period?: string; has_previous_policy?: boolean };
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
    covernote_policy?: {
      session_id: string;
      document_type: string;
      policy_number?: string | null;
      company_name: string;
      company_id?: string | null;
      sum_insured: number;
      valuation_type: string;
      motor_premium: number;
      road_tax: number;
      runner_fee: number;
      total_payable: number;
      rounded_total_payable?: number | null;
      towing_limit: string;
      towing_km?: string;
      agreed_value: boolean;
      excess: number;
      windscreen_sum_insured: number | null;
      canonical_perils: string[];
      canonical_perils_formatted: string;
      coverage_start_date?: string | null;
      coverage_end_date?: string | null;
      coverage_period_formatted?: string | null;
      uploaded_file_id?: string | null;
      original_filename?: string | null;
      is_covernote: boolean;
    } | null;
    unlinked_covernotes?: Array<{
      session_id: string;
      company_name: string;
      policy_number: string;
      uploaded_file_id: string | null;
      uploaded_file_name: string;
      coverage_period_formatted: string;
      created_at: string | null;
    }>;
    detection_logs?: {
      vehicle?: {
        model?: string;
        engine_capacity?: string;
        propulsion?: string;
        vehicle_type?: string;
        entity_type?: string;
        region?: string;
        calculated_road_tax?: string;
        jpj_status?: string;
      };
      verifications?: Array<{
        company_name?: string;
        version?: number;
        basic_figure?: string;
        sum_insured?: string;
        rate_factor?: string;
        ncd?: string;
        excess?: string;
        excess_note?: string;
        perils_breakdown?: string[];
        math_balanced?: boolean;
      }>;
    };
  } | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedWhatsapp, setCopiedWhatsapp] = useState(false);
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState<ComparisonEntry | null>(null);
  const [isUnlinkingCovernote, setIsUnlinkingCovernote] = useState(false);
  const [promotingEntryId, setPromotingEntryId] = useState<string | null>(null);

  const [showUnlinkModal, setShowUnlinkModal] = useState(false);

  const performUnlink = async () => {
    try {
      setIsUnlinkingCovernote(true);
      await api(`/comparison/${tenureId}/covernote`, {
        method: "DELETE",
      });
      triggerStatus("success", "Cover Note Removed", "The cover note was removed and policy stage reverted to Quotations.");
      setShowUnlinkModal(false);
      await fetchComparison(true);
    } catch (err: any) {
      alert("Failed to remove cover note: " + (err.message || String(err)));
    } finally {
      setIsUnlinkingCovernote(false);
    }
  };

  const handleDownloadAndUnlink = () => {
    const cn = data?.covernote_policy;
    if (cn?.uploaded_file_id) {
      const link = document.createElement("a");
      link.href = fileUrl(`/uploaded-files/${cn.uploaded_file_id}/content`);
      link.download = (cn as any).file_name || `${cn.company_name || "policy"}_covernote.pdf`;
      link.target = "_blank";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
    setTimeout(() => {
      performUnlink();
    }, 400);
  };

  const handleUnlinkCovernote = () => {
    setShowUnlinkModal(true);
  };

  const handlePromoteToCovernote = async (entry: ComparisonEntry) => {
    if (!entry.session_id) {
      alert("This quotation does not have an attached PDF session.");
      return;
    }
    if (!confirm(`Mark ${entry.company_name} as the official issued Cover Note / Policy for this vehicle? This will move it from the comparison matrix into the Current Policy section and transition the tenure to Issued Policy.`)) {
      return;
    }
    try {
      setPromotingEntryId(entry.id);
      await api(`/comparison/${tenureId}/sessions/${entry.session_id}/convert-type`, {
        method: "POST",
        body: JSON.stringify({ document_type: "covernote" }),
      });
      triggerStatus("success", "Cover Note Issued", `${entry.company_name} is now designated as the official issued Cover Note.`);
      await fetchComparison(true);
    } catch (err: any) {
      alert("Failed to convert document type: " + (err.message || String(err)));
    } finally {
      setPromotingEntryId(null);
    }
  };

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
  const [splitModeByCompany, setSplitModeByCompany] = useState<Record<string, boolean>>({});
  const [expandedBreakdownId, setExpandedBreakdownId] = useState<Record<string, boolean>>({});
  const [rescanningQuoteId, setRescanningQuoteId] = useState<string | null>(null);
  const [showDetectionLogsModal, setShowDetectionLogsModal] = useState(false);

  // 30-Second Real-Time Process Notification Toast
  const [operationStatus, setOperationStatus] = useState<{
    id: string;
    type: "info" | "success" | "loading" | "error";
    title: string;
    message: string;
    step?: string;
  } | null>(null);

  useEffect(() => {
    if (!operationStatus || operationStatus.type === "loading") return;
    const timer = setTimeout(() => {
      setOperationStatus(null);
    }, 30000); // 30s persistent display as requested
    return () => clearTimeout(timer);
  }, [operationStatus]);

  const triggerStatus = (
    type: "info" | "success" | "loading" | "error",
    title: string,
    message: string,
    step?: string
  ) => {
    setOperationStatus({
      id: Math.random().toString(),
      type,
      title,
      message,
      step,
    });
  };

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
  const [refreshingLedger, setRefreshingLedger] = useState(false);
  const [customerNameInput, setCustomerNameInput] = useState("");
  const [icNoInput, setIcNoInput] = useState("");
  const [vehicleNoInput, setVehicleNoInput] = useState("");
  const [carBrandInput, setCarBrandInput] = useState("");
  const [roadTaxInput, setRoadTaxInput] = useState("70");
  const [runnerFeeInput, setRunnerFeeInput] = useState("50");
  const [windscreenInput, setWindscreenInput] = useState("");
  const [currentPolicyDiscount, setCurrentPolicyDiscount] = useState<number>(0);
  const [previousPolicyDiscount, setPreviousPolicyDiscount] = useState<number>(0);
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
    setVehicleNoInput(tenure.vehicle_no && tenure.vehicle_no !== "UNPLATED" ? tenure.vehicle_no : "");
    setCarBrandInput(tenure.car_brand || "");
    setCustomerNameInput(tenure.customer_name || "");
    setIcNoInput(tenure.ic_no || "");
    setRoadTaxInput(String(tenure.road_tax));
    setRunnerFeeInput(String(tenure.runner_fee));
    setWindscreenInput(tenure.windscreen_target ? String(tenure.windscreen_target) : "");
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

  const handleRefreshLedger = async () => {
    if (!tenureId) return;
    try {
      setRefreshingLedger(true);
      const res = await api<any>(`/comparison/${tenureId}/refresh-ledger`, {
        method: "POST",
      });
      setData(res);
      if (res.tenure) {
        populateEditInputs(res.tenure);
      }
    } catch (err: any) {
      alert("Failed to refresh ledger: " + (err.message || String(err)));
    } finally {
      setRefreshingLedger(false);
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

  // NCD Entitlement & Previous Policy Edit State
  const [showNcdModal, setShowNcdModal] = useState(false);
  const [editCurrentNcd, setEditCurrentNcd] = useState<string>("");
  const [editNextNcd, setEditNextNcd] = useState<string>("");
  const [pastingPolicyText, setPastingPolicyText] = useState("");
  const [savingNcd, setSavingNcd] = useState(false);

  const handleOpenNcdModal = () => {
    if (data?.ncd) {
      setEditCurrentNcd(data.ncd.current != null ? String(data.ncd.current) : "");
      setEditNextNcd(data.ncd.next != null ? String(data.ncd.next) : "");
    }
    setPastingPolicyText("");
    setShowNcdModal(true);
  };

  const handleSaveNcd = async () => {
    if (!data?.tenure) return;
    try {
      setSavingNcd(true);
      const currVal = editCurrentNcd.trim() !== "" ? parseFloat(editCurrentNcd) : null;
      const nextVal = editNextNcd.trim() !== "" ? parseFloat(editNextNcd) : null;

      await api(`/comparison/${data.tenure.id}/fixed-costs`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          road_tax: data.tenure.road_tax,
          runner_fee: data.tenure.runner_fee,
          windscreen_target: data.tenure.windscreen_target,
          ncd_percentage: nextVal,
          current_ncd: currVal,
        }),
      });

      triggerStatus("success", "NCD Entitlement Updated", "Current NCD and Next NCD entitlement were successfully saved.");
      setShowNcdModal(false);
      await fetchComparison(true);
    } catch (err: any) {
      triggerStatus("error", "Failed to Save NCD", err.message || String(err));
    } finally {
      setSavingNcd(false);
    }
  };

  const searchParams = useSearchParams();
  const isFromUpload = searchParams.get("from_upload") === "true";
  const [isCompilingBatch, setIsCompilingBatch] = useState(isFromUpload);

  useEffect(() => {
    if (!tenureId) return;
    fetchComparison();
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
          vehicle_no: vehicleNoInput.trim() ? vehicleNoInput.trim().toUpperCase() : undefined,
          car_brand: carBrandInput.trim() || undefined,
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
      triggerStatus(
        "loading",
        "Rescanning Quotations",
        "Analyzing chunk-aware text blocks, verifying JPJ road tax math, and detecting perils & schedule excess with 100% precision...",
        "Processing"
      );
      const updated = await api<any>(`/comparison/${tenureId}/rescan`, {
        method: "POST",
      });
      if (updated) setData(updated);
      await fetchComparison(true);
      triggerStatus(
        "success",
        "Rescan Complete",
        "All quotations rescanned and verified against Malaysian underwriter schedules with zero hallucinations."
      );
    } catch (err: any) {
      triggerStatus("error", "Rescan Failed", err.message || String(err));
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
    if (payload.id && payload.company_name) {
      const cName = String(payload.company_name).trim();
      setActiveVersionsByCompany((prev) => ({
        ...prev,
        [cName]: [payload.id],
      }));
    }
  };

  const handleDeleteEntry = async (entryId: string, deleteAllVersions: boolean = true) => {
    const promptMsg = deleteAllVersions
      ? "Are you sure you want to completely remove this underwriter and all its quotes from comparison?"
      : "Are you sure you want to remove this quotation version from comparison?";
    if (!confirm(promptMsg)) return;
    try {
      const updated = await api<any>(`/comparison/${tenureId}/entry/${entryId}?all_versions=${deleteAllVersions}`, {
        method: "DELETE",
      });
      setData(updated);
      setActiveVersionsByCompany((prev) => {
        const next = { ...prev };
        for (const [cName, ids] of Object.entries(next)) {
          next[cName] = ids.filter((id) => id !== entryId);
        }
        return next;
      });
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

      const target = data?.entries.find((e) => e.id === entryId);
      const isNowRecommended = !target?.is_recommended;

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
      triggerStatus(
        "success",
        isNowRecommended ? "Winner Selected" : "Winner Cleared",
        isNowRecommended
          ? `${target?.company_name || "Underwriter"} designated as the recommended focus policy.`
          : "Winner designation cleared. Natural comparison preserved."
      );
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
      triggerStatus("info", "Rank Override Updated", `Manual rank set to #${rankVal || "Auto"} for ${entry.company_name}.`);
    } catch (err: any) {
      alert("Failed to update manual rank: " + err.message);
      await fetchComparison(true);
    }
  };

  const handleRerank = async () => {
    try {
      setReranking(true);
      triggerStatus(
        "loading",
        "Re-ranking Quotes",
        "Evaluating natural pricing hierarchy and manual rank overrides...",
        "Ordering columns..."
      );
      await api(`/comparison/${tenureId}/rerank`, { method: "POST" });
      await fetchComparison(true);
      triggerStatus(
        "success",
        "Re-ranking Complete",
        "Quotation ranking hierarchy recalculated and updated."
      );
    } catch (err: any) {
      triggerStatus("error", "Re-ranking Failed", err.message || String(err));
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

  // Helper to get active entry IDs for a company group (single column per insurer, latest version or winner by default)
  const getActiveEntryIdsForGroup = (group: { companyName: string; entries: ComparisonEntry[] }): string[] => {
    const customIds = activeVersionsByCompany[group.companyName];
    if (customIds && customIds.length > 0) {
      const found = group.entries.find((e) => e.id === customIds[0]);
      if (found) return [found.id];
    }
    const winner = group.entries.find((e) => e.is_recommended);
    if (winner) return [winner.id];
    const sortedByVer = [...group.entries].sort((a, b) => (b.version || 0) - (a.version || 0));
    return sortedByVer[0] ? [sortedByVer[0].id] : [];
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
  }, [companyGroups, activeVersionsByCompany, splitModeByCompany, showHiddenCards]);

  // Strict dynamic ranking computed ONLY among cards currently visible in the UI
  // Decoupled from winner selection: Natural price sorting or manual rank determines order
  const visibleRanksMap = useMemo(() => {
    const sorted = [...visibleDisplayEntries].sort((a, b) => {
      if (a.manual_rank != null && b.manual_rank != null) return a.manual_rank - b.manual_rank;
      if (a.manual_rank != null) return -1;
      if (b.manual_rank != null) return 1;
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

  const activeWinnerPeriod = useMemo(() => {
    if (data?.covernote_policy?.coverage_period_formatted) {
      return data.covernote_policy.coverage_period_formatted;
    }
    if (data?.covernote_policy?.coverage_start_date) {
      const s = new Date(data.covernote_policy.coverage_start_date).toLocaleDateString("en-GB");
      const e = data.covernote_policy.coverage_end_date
        ? new Date(data.covernote_policy.coverage_end_date).toLocaleDateString("en-GB")
        : "";
      return e ? `${s} - ${e}` : s;
    }
    if (currentPolicyWinner?.coverage_period_formatted) {
      return currentPolicyWinner.coverage_period_formatted;
    }
    if (currentPolicyWinner?.coverage_start_date) {
      const s = new Date(currentPolicyWinner.coverage_start_date).toLocaleDateString("en-GB");
      const e = currentPolicyWinner.coverage_end_date
        ? new Date(currentPolicyWinner.coverage_end_date).toLocaleDateString("en-GB")
        : "";
      return e ? `${s} - ${e}` : s;
    }
    return data?.tenure?.coverage_period_formatted || "—";
  }, [data?.covernote_policy, currentPolicyWinner, data?.tenure?.coverage_period_formatted]);

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
    return (
      <UnderwriterQuoteCard
        key={entry.id}
        entry={entry}
        group={group}
        activeIds={activeIds}
        isViewingPdf={activePdfSession?.sessionId === entry.session_id}
        visibleRanksMap={visibleRanksMap}
        visibleDisplayEntriesCount={visibleDisplayEntries.length}
        editingRankEntryId={editingRankEntryId}
        tenure={tenure}
        selectingWinnerId={selectingWinnerId}
        promotingEntryId={promotingEntryId}
        rescanningQuoteId={rescanningQuoteId}
        isRescanning={isRescanning}
        onToggleHideEntry={handleToggleHideEntry}
        onSetManualRank={handleSetManualRank}
        onSetEditingRankEntryId={setEditingRankEntryId}
        onSelectActiveVersion={(companyName, id) => {
          setActiveVersionsByCompany((prev) => ({
            ...prev,
            [companyName]: [id],
          }));
        }}
        onViewPdf={(session) => setActivePdfSession(session)}
        onRescanQuote={async (quoteEntry) => {
          try {
            setRescanningQuoteId(quoteEntry.id);
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
        onSelectWinner={handleSelectWinner}
        onEditEntry={(quoteEntry) => {
          setEditingEntry(quoteEntry);
          setIsManualModalOpen(true);
        }}
        onPromoteToCovernote={handlePromoteToCovernote}
        onDeleteEntry={handleDeleteEntry}
      />
    );
  };

  return (
    <div className="flex gap-4 items-start relative w-full">
      <div className="flex-1 min-w-0 space-y-6 pb-12 overflow-x-hidden print:overflow-visible">
        {/* Print-Only Executive Comparison Header */}
        <div className="hidden print:block mb-6 border-b-2 border-[#1b1717] pb-4 space-y-4">
          <div className="relative flex items-center justify-between">
            <div className="flex items-center">
              <img src="/assets/brand/logo-black.png" alt="Risklocker" className="h-9 w-auto object-contain" />
            </div>
            <div className="absolute left-1/2 -translate-x-1/2 text-center pointer-events-none">
              <h1 className="text-xl font-black tracking-tight text-[#1b1717] uppercase">
                MOTOR QUOTATION COMPARISON
              </h1>
            </div>
            <div className="text-right">
              <div className="inline-block bg-[#f5f5f7] border border-[#e5e5ea] px-3.5 py-1 rounded-lg">
                <span className="font-mono font-bold text-base text-[#1b1717]">
                  {tenure.is_plate_undetected || tenure.vehicle_no === "N/A"
                    ? `N/A · Chassis: ${tenure.chassis_no || "N/A"}`
                    : (tenure.vehicle_no || tenure.chassis_no || "Unregistered Vehicle")}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-end justify-between text-xs pt-1">
            <div className="space-y-0.5">
              <p className="text-xs font-semibold text-[#454545]">
                Commercial General Insurance
              </p>
              <p className="text-[11px] text-[#6e6e73]">
                Your Shield Against The Unexpected
              </p>
              <p className="text-xs text-[#454545]">
                Coverage Period :{" "}
                <span className="font-mono font-bold text-[#1b1717]">{activeWinnerPeriod}</span>
              </p>
            </div>
            <div className="text-right space-y-0.5">
              <p className="font-bold text-xs text-[#1b1717]">{tenure.customer_name} {tenure.ic_no ? `(${tenure.ic_no})` : ""}</p>
              <p className="text-[11px] text-[#6e6e73]">{tenure.vehicle_model} · {tenure.engine_cc}</p>
              <p className="text-[11px] font-semibold text-[#454545]">
                Roadtax and Runner fee :{" "}
                <span className="font-mono font-bold text-[#1b1717]">
                  RM {(tenure.road_tax + tenure.runner_fee).toFixed(2)}
                </span>
              </p>
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
        <div id="tour-stepper" className="rounded-2xl border border-[#e5e5ea] bg-white p-3 shadow-xs no-print print:hidden">
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
                  ? `Recommended: ${formatShortInsurerName(winnerEntries[0].company_name)}`
                  : `${winnerEntries.length} Recommendations Selected ★`}
              </span>
              <span className="text-[11px] text-[#6e6e73] block truncate">
                {winnerEntries.length === 0
                  ? "Click any quote to recommend"
                  : winnerEntries.map((w) => formatShortInsurerName(w.company_name)).join(", ")}
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
                    ? `Issue ${formatShortInsurerName(winnerEntries[0].company_name)} Quotation`
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
                      <span>{formatShortInsurerName(w.company_name)}</span>
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
              const qNames = batch.quotes.map((q) => `${formatShortInsurerName(q.company_name)} v${q.version}`).join(", ");
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

      {/* 30-Second Real-Time Process Notification Toast */}
      {operationStatus && (
        <div
          className={`rounded-xl border p-4 shadow-sm flex items-start justify-between gap-3 no-print animate-in fade-in slide-in-from-top-2 duration-200 ${
            operationStatus.type === "loading"
              ? "bg-amber-50 border-amber-200 text-amber-900"
              : operationStatus.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-900"
              : operationStatus.type === "error"
              ? "bg-rose-50 border-rose-200 text-rose-900"
              : "bg-blue-50 border-blue-200 text-blue-900"
          }`}
        >
          <div className="flex items-start gap-3">
            <div className="mt-0.5 shrink-0">
              {operationStatus.type === "loading" ? (
                <CircleNotch size={20} weight="bold" className="animate-spin text-amber-600" />
              ) : operationStatus.type === "success" ? (
                <CheckCircle size={20} weight="fill" className="text-emerald-600" />
              ) : operationStatus.type === "error" ? (
                <WarningCircle size={20} weight="fill" className="text-rose-600" />
              ) : (
                <Info size={20} weight="fill" className="text-blue-600" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-xs font-bold uppercase tracking-wider">{operationStatus.title}</h4>
                {operationStatus.step && (
                  <span className="text-[10px] font-semibold bg-white/70 px-2 py-0.5 rounded-full border border-black/5">
                    {operationStatus.step}
                  </span>
                )}
              </div>
              <p className="text-xs mt-0.5 opacity-90 leading-relaxed font-medium">{operationStatus.message}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setOperationStatus(null)}
            className="text-neutral-400 hover:text-neutral-700 p-1 rounded transition-colors cursor-pointer shrink-0"
            title="Dismiss notification"
          >
            <X size={16} weight="bold" />
          </button>
        </div>
      )}

      {/* Vehicle Info & Action Header */}
      <div className="rounded-2xl border border-[#e5e5ea] bg-white p-5 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            {tenure.is_plate_undetected || tenure.vehicle_no === "N/A" ? (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="rounded-lg bg-neutral-100 px-3 py-1 font-mono text-sm font-bold text-neutral-600 border border-neutral-300">
                  N/A
                </span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-50 text-amber-900 border border-amber-300 shadow-2xs">
                  <span className="size-2 rounded-full bg-amber-500 animate-pulse" />
                  <span>Plate Undetected · Tracking by Chassis: {tenure.chassis_no || "N/A"}</span>
                </span>
              </div>
            ) : (
              <span className="rounded-lg bg-[#f5f5f7] px-3 py-1 font-mono text-sm font-bold text-[#1b1717] border border-[#e5e5ea]">
                {tenure.vehicle_no}
              </span>
            )}
            <h1 className="text-xl font-bold tracking-tight text-[#1b1717]">
              {tenure.customer_name}
            </h1>
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-rose-50 px-2.5 py-1 text-xs font-bold text-rose-700 border border-rose-200/90 shadow-2xs">
              <span className="size-1.5 rounded-full bg-rose-500 animate-pulse" />
              <span>Expiry Date: {formatExpiryDateDisplay(tenure, previous_policy)}</span>
            </span>
          </div>
          <div className="text-xs text-[#6e6e73] mt-2 flex items-center gap-2 flex-wrap">
            <span>Period: <strong className="text-[#1b1717] font-mono">{activeWinnerPeriod}</strong></span>
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
            onClick={() => setShowDetectionLogsModal(true)}
            icon={<ClipboardText size={15} weight="bold" className="text-blue-600" />}
            className="border-[#e5e5ea] bg-white hover:border-[#1b1717] text-[#1b1717] font-semibold"
            title="Inspect autonomous 100% precision detection audit: JPJ road tax math, perils pricing breakdown, and schedule policy excess"
          >
            Detection Logs
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

          {/* Single Unified Upload PDF Action */}
          <Link
            href={`/upload?mode=comparison&tenure_id=${tenure.id}` as Route}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#e5e5ea] bg-white hover:bg-neutral-50 text-xs font-semibold text-[#1b1717] transition-colors shadow-2xs"
            title="Upload underwriter quotation or cover note PDF for this vehicle"
          >
            <UploadSimple size={15} weight="bold" />
            <span>Upload PDF</span>
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
        <CustomerVehicleLedgerPane
          tenure={tenure}
          covernotePolicy={data.covernote_policy}
          vehicleAge={data.vehicle_age}
          decodedIc={decodedIc}
          activeWinnerPeriod={activeWinnerPeriod}
          editingFixedCosts={editingFixedCosts}
          setEditingFixedCosts={setEditingFixedCosts}
          refreshingLedger={refreshingLedger}
          onRefreshLedger={handleRefreshLedger}
          customerNameInput={customerNameInput}
          setCustomerNameInput={setCustomerNameInput}
          icNoInput={icNoInput}
          setIcNoInput={setIcNoInput}
          vehicleNoInput={vehicleNoInput}
          setVehicleNoInput={setVehicleNoInput}
          carBrandInput={carBrandInput}
          setCarBrandInput={setCarBrandInput}
          roadTaxInput={roadTaxInput}
          setRoadTaxInput={setRoadTaxInput}
          runnerFeeInput={runnerFeeInput}
          setRunnerFeeInput={setRunnerFeeInput}
          windscreenInput={windscreenInput}
          setWindscreenInput={setWindscreenInput}
          engineCcInput={engineCcInput}
          setEngineCcInput={setEngineCcInput}
          engineNoInput={engineNoInput}
          setEngineNoInput={setEngineNoInput}
          chassisNoInput={chassisNoInput}
          setChassisNoInput={setChassisNoInput}
          vehicleModelInput={vehicleModelInput}
          setVehicleModelInput={setVehicleModelInput}
          manufactureYearInput={manufactureYearInput}
          setManufactureYearInput={setManufactureYearInput}
          startDateInput={startDateInput}
          endDateInput={endDateInput}
          onStartDateChange={handleStartDateChange}
          onEndDateChange={handleEndDateChange}
          savingFixedCosts={savingFixedCosts}
          onSaveFixedCosts={handleSaveFixedCosts}
          onPopulateEditInputs={() => populateEditInputs(tenure)}
        />

        {/* ============================================================== */}
        {/* CENTER PANE: Dynamic Side-by-Side Underwriter Columns           */}
        {/* ============================================================== */}
        <div id="tour-comparison-matrix" className="min-w-0 overflow-x-auto pb-4 print:overflow-visible print:w-full">
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

            {/* Empty State: Marketing Comparison Table Dropzone */}
            {companyGroups.length === 0 && (
              <>
                <div className="flex-1 min-w-[340px] max-w-[540px] p-8 rounded-2xl border-2 border-dashed border-[#e5e5ea] bg-white text-center flex flex-col items-center justify-center gap-4">
                  <div className="size-14 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center">
                    <Columns size={28} weight="duotone" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-[#1b1717]">
                      {isCompilingBatch || (data?.pending_jobs_count && data.pending_jobs_count > 0)
                        ? "Extracting Quotation Documents..."
                        : `${tenure.coverage_start_date ? new Date(tenure.coverage_start_date).getFullYear() : "2027"} Renewal Intake Workspace`}
                    </h3>
                    <p className="text-xs text-[#6e6e73] max-w-sm mt-1 leading-relaxed">
                      {isCompilingBatch || (data?.pending_jobs_count && data.pending_jobs_count > 0)
                        ? "Our extraction pipeline is reading underwriter PDFs, extracting sums insured, motor premiums, and benefit riders. This matrix will refresh automatically."
                        : `Showing previous year policy details as baseline for ${tenure.vehicle_no}. Upload incoming underwriter quotation PDFs or enter portal quotes manually.`}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 pt-2">
                    <Link
                      href={`/upload?mode=comparison&tenure_id=${tenureId}` as Route}
                      className="bg-[#1b1717] hover:bg-black text-white text-xs font-bold px-4 py-2 rounded-xl cursor-pointer inline-flex items-center gap-1.5"
                    >
                      <UploadSimple size={14} weight="bold" />
                      <span>Upload PDF</span>
                    </Link>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => fetchComparison()}
                      className="text-xs font-semibold px-3 py-2 rounded-xl cursor-pointer"
                    >
                      <ArrowsClockwise size={14} weight="bold" className="mr-1" />
                      Refresh
                    </Button>
                  </div>
                </div>
              </>
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
        <PreviousPolicyValuationPane
          tenure={tenure}
          previous_policy={previous_policy}
          covernote_policy={data.covernote_policy}
          recommended_sum_insured={recommended_sum_insured}
          ncd={ncd}
          tenureId={tenureId}
          isUnlinkingCovernote={isUnlinkingCovernote}
          onOpenNcdModal={handleOpenNcdModal}
          onUnlinkCovernote={handleUnlinkCovernote}
        />
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

      {/* Source PDF Viewer Pane (Docked or Floating Overlay) */}
      <SourcePdfViewerPane
        activePdfSession={activePdfSession}
        dockMode={pdfDockMode}
        panelWidth={pdfPanelWidth}
        onSetDockMode={setPdfDockMode}
        onClose={() => setActivePdfSession(null)}
        onStartResizing={() => setIsResizing(true)}
      />


      {/* High-Resolution NxM Comparison Snapshot Grid Modal */}
      <SnapshotPreviewModal
        isOpen={snapshotModalOpen}
        onClose={() => setSnapshotModalOpen(false)}
        onCopy={handleCopySnapshot}
        isCopying={copyingSnapshot}
        onDownload={handleDownloadSnapshot}
        isDownloading={downloadingSnapshot}
        gridRef={snapshotGridRef}
        tenure={tenure}
        snapshotVisibleCards={snapshotVisibleCards}
        activeWinnerPeriod={activeWinnerPeriod}
        visibleRanksMap={visibleRanksMap}
        ncdData={data?.ncd}
      />

      {/* 100% Precision Autonomous Detection Logs Modal */}
      <DetectionLogsModal
        isOpen={showDetectionLogsModal}
        onClose={() => setShowDetectionLogsModal(false)}
        detectionLogs={data.detection_logs}
        tenure={{
          vehicle_model: tenure.vehicle_model,
          engine_cc: tenure.engine_cc,
          road_tax: tenure.road_tax,
        }}
      />

      {/* Add / Edit Insurer Quote Modal (Dual-Mode: Upload PDF + Manual Portal Entry) */}
      <ManualQuoteModal
        isOpen={isManualModalOpen}
        onClose={() => {
          setIsManualModalOpen(false);
          setEditingEntry(null);
        }}
        onSave={handleSaveEntry}
        initialData={editingEntry ? { ...editingEntry, vehicle_age: editingEntry.vehicle_age ?? data?.vehicle_age } : null}
        tenureId={tenureId}
        tenureStartDate={tenure?.coverage_start_date}
        onUploadSuccess={() => fetchComparison()}
      />

      {/* Unlink Cover Note Confirmation Modal with Download Option */}
      <UnlinkCovernoteModal
        isOpen={showUnlinkModal}
        onClose={() => setShowUnlinkModal(false)}
        onUnlink={performUnlink}
        onDownloadAndUnlink={handleDownloadAndUnlink}
        isUnlinking={isUnlinkingCovernote}
        vehicleNo={tenure?.vehicle_no}
      />

      {/* NCD Entitlement & Previous Policy Edit Modal */}
      <NcdEntitlementModal
        isOpen={showNcdModal}
        onClose={() => setShowNcdModal(false)}
        tenureId={tenureId}
        ncdData={{
          current_period: data?.ncd?.current_period,
          next_period: data?.ncd?.next_period,
        }}
        editCurrentNcd={editCurrentNcd}
        setEditCurrentNcd={setEditCurrentNcd}
        editNextNcd={editNextNcd}
        setEditNextNcd={setEditNextNcd}
        pastingPolicyText={pastingPolicyText}
        setPastingPolicyText={setPastingPolicyText}
        onSave={handleSaveNcd}
        isSaving={savingNcd}
      />
    </div>
  );
}
