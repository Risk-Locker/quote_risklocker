"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowArcLeft,
  ArrowArcRight,
  ArrowCounterClockwise,
  ArrowRight,
  ArrowsInSimple,
  ArrowsOutSimple,
  ArrowSquareOut,
  CaretDown,
  CaretLeft,
  CaretRight,
  CaretUp,
  Check,
  CheckCircle,
  Copy,
  DownloadSimple,
  Eye,
  EyeClosed,
  FilePdf,
  FloppyDisk,
  Lightning,
  Lock,
  MagnifyingGlass,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
  Package as PackageIcon,
  PencilSimple,
  Plus,
  Sparkle,
  UserSwitch,
  X,
} from "@phosphor-icons/react";
import { toBlob, toPng } from "html-to-image";
import jsPDF from "jspdf";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GuidedTour } from "@/components/guided-tour";
import { SendToClientDialog } from "@/components/insights/send-to-client-dialog";
import { Card } from "@/components/ui/card";
import { GeminiQuotaInfoButton, type GeminiQuota } from "@/components/gemini-quota-meter";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { Select } from "@/components/ui/select";
import {
  CanvasElementView,
  balanceBenefitGridElements,
  isPaidExtraBenefitCard,
  type CanvasElement,
} from "@/components/template-canvas/shared";
import {
  SYSTEM_BENEFIT_PRESETS,
  applyPresetToCanvasElement,
  getAllBenefitPresets,
  getBenefitPreset,
  type BenefitCardStyle,
} from "@/lib/benefit-presets";
import {
  useWorkspaceActions,
  useWorkspaceData,
  useWorkspaceMutation,
} from "@/components/session-workspace/provider";
import type { BenefitCardSummary, WorkspaceField } from "@/components/session-workspace/types";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

import {
  FORM_FIELDS,
  type FieldKind,
  type FormField,
  detectEVCategory,
  computeMalaysianRoadTax,
  isNonSaloonCarModel,
  inferCCFromCarModel,
  PolicyFieldsCard,
} from "./review-components/policy-fields-card";

// The 7 Core Baseline Comprehensive Benefits
const BASELINE_COMPREHENSIVE_KEYS = [
  "special-perils",
  "repair-allowance-cart",
  "legal-liability-to-passengers",
  "strike-riot-civil-commotion",
  "roadside-assistance",
  "special-perils",
  "repair-workmanship-warranty",
];

const GLOBAL_BENEFIT_KEYS = new Set([
  "special-perils",
  "roadside-assistance",
  "repair-workmanship-warranty",
  "all-drivers",
  "personal-accident",
  "repair-allowance-cart",
  "betterment-protection",
  "flood-relief-allowance",
  "total-loss-theft-allowance",
  "key-replacement",
  "ambulance-fees",
  "personal-belongings-theft",
  "falling-object-damage",
  "document-replacement",
]);

type CompanyOption = { id: string; name: string };
type CompanyWorkspace = {
  company: { id: string; name: string };
  products: Array<{ id: string; name: string; status?: string }>;
  tiers: Array<{ id: string; product_id: string; name: string }>;
  catalogs?: Array<{
    id: string;
    product_id?: string;
    status?: string;
    offerings?: Array<{ id: string; concept_key?: string; concept_id?: string; concept?: { id?: string; concept_key?: string } }>;
  }>;
};

type PublishedTemplateOption = {
  template_id: string;
  template_revision_id: string;
  name: string;
  revision_number: number;
  config_hash: string;
  config?: TemplateConfig;
  page_profile: { name: string; width: number; height: number; unit: string };
  is_default?: boolean;
};

type TemplateSelectionImpact = {
  current_template_revision_id: string | null;
  target: { template_id: string; template_revision_id: string; revision_number: number; name: string; config_hash: string };
  will_reset_layout_override: boolean;
  requires_confirmation: boolean;
  messages: string[];
};

type GlobalConcept = {
  id: string;
  concept_key: string;
  label: string;
  description: string | null;
  sort_order: number;
  default_asset_id?: string | null;
  default_asset?: { id: string; label: string; url: string } | null;
};

type TemplateConfig = {
  canvas: { width: number; height: number; elements: CanvasElement[] };
  assets?: Record<string, string>;
  [key: string]: unknown;
};

type TemplatePayload = {
  template_id: string;
  template_revision_id: string;
  revision_number: number;
  config_hash: string;
  source: string;
  config: TemplateConfig;
  binding: { template_id: string; template_revision_id: string; base_hash: string };
};

const LEARNABLE = new Map<string, string>([
  ["car_model", "car_model"],
  ["car_brand", "car_brand"],
]);

function formatMoney(raw: string | null | undefined): string {
  const number = Number(String(raw ?? "").replace(/[^0-9.-]/g, ""));
  if (!raw || Number.isNaN(number)) return "";
  return number.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(raw: string | null | undefined): string {
  const value = String(raw ?? "").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-");
    return `${day}-${month}-${year}`;
  }
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(value)) {
    return value.replace(/\//g, "-");
  }
  return value;
}

function formatCoverPeriod(raw: string | null | undefined): string {
  const value = String(raw ?? "").trim();
  if (!value) return "";
  return value
    .replace(/(\d{4})-(\d{2})-(\d{2})/g, "$3-$2-$1")
    .replace(/(\d{2})\/(\d{2})\/(\d{4})/g, "$1-$2-$3");
}



function displayValue(kind: FieldKind, value: string | null | undefined): string {
  if (kind === "money") return formatMoney(value);
  if (kind === "date") return formatDate(value);
  if (kind === "percent") return value ? `${String(value).replace(/%/g, "")}%` : "";
  if (kind === "vehicle_type") return String(value || "Car");
  return formatCoverPeriod(String(value ?? ""));
}

import { IncludedCard, AddonCard } from "./review-components/benefit-cards";
import { ReviewHeader } from "./review-components/review-header";
import { ReviewBanners } from "./review-components/review-banners";
import { ReviewModals } from "./review-components/review-modals";
import { ExtractedBenefitsCard } from "./review-components/extracted-benefits-card";
import { BenefitsManagerPanel } from "./review-components/benefits-manager-panel";

export function ReviewPhase({ id, onNext }: { id: string; onNext: () => void }) {
  const { workspace, loading, loadError } = useWorkspaceData();
  const { decideField, save, reload, queueOperation } = useWorkspaceActions();
  const mutation = useWorkspaceMutation();

  const [pdfOpen, setPdfOpen] = useState(false);
  const [formValues, setFormValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(FORM_FIELDS.map((field) => [field.name, ""]))
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [companyWorkspace, setCompanyWorkspace] = useState<CompanyWorkspace | null>(null);
  const [pinLoading, setPinLoading] = useState(false);
  const [globalConcepts, setGlobalConcepts] = useState<GlobalConcept[]>([]);
  const [showGlobalModal, setShowGlobalModal] = useState(false);
  const [globalSearch, setGlobalSearch] = useState("");
  const [modalFilter, setModalFilter] = useState<"all" | "insurer" | "global" | "addons">("all");
  const [undoStack, setUndoStack] = useState<{ op: Record<string, unknown> & { op: string }; path: string; desc: string; revertOp?: Record<string, unknown> & { op: string } }[]>([]);
  const [redoStack, setRedoStack] = useState<{ op: Record<string, unknown> & { op: string }; path: string; desc: string; revertOp?: Record<string, unknown> & { op: string } }[]>([]);
  const [activeTab, setActiveTab] = useState<"included" | "addons">("included");
  const [modalTarget, setModalTarget] = useState<"current" | "available_addon">("current");
  const [benefitsViewMode, setBenefitsViewMode] = useState<"defaults" | "addons" | "both">("both");
  const [previewExpanded, setPreviewExpanded] = useState(false);
  const [benefitsExpanded, setBenefitsExpanded] = useState(false);
  const [templateCollapsed, setTemplateCollapsed] = useState(false);
  const [extractedValuesCollapsed, setExtractedValuesCollapsed] = useState(false);
  const [extractedBenefitsCollapsed, setExtractedBenefitsCollapsed] = useState(false);
  // RL-DISABLED extractedBenefitsViewMode — disabled 2026-08-28; unused after removing evidence tab
  const [previewCollapsed, setPreviewCollapsed] = useState(false);
  const [benefitsCollapsed, setBenefitsCollapsed] = useState(false);

  const [packPlanSelections, setPackPlanSelections] = useState<Record<string, string>>({});
  const [customPrice, setCustomPrice] = useState("");

  // Two-way synchronization highlight state showing what changed and the previous value
  const [syncHighlight, setSyncHighlight] = useState<{
    field: "vehicle_type" | "product_package";
    prev: string;
    next: string;
    timestamp: number;
  } | null>(null);

  const currentVehicleCategory = useMemo(() => {
    const raw = String(formValues?.vehicle_type || workspace?.fields?.vehicle_type?.value || "").toLowerCase();
    if (raw.includes("motor") || raw.includes("bike")) return "Motorcycle";
    if (raw.includes("lorry") || raw.includes("commercial") || raw.includes("truck") || raw.includes("haulage")) return "Lorry";
    return "Car";
  }, [formValues?.vehicle_type, workspace?.fields?.vehicle_type]);

  const isExcludedForVehicle = useCallback(
    (item: { label?: string; title?: string; concept_key?: string } | null | undefined) => {
      if (!item) return false;
      const text = `${item.label || ""} ${item.title || ""} ${item.concept_key || ""}`.toLowerCase();
      if (currentVehicleCategory === "Motorcycle" && text.includes("windscreen")) return true;
      if (currentVehicleCategory === "Lorry" && (text.includes("towing") || text.includes("breakdown"))) return true;
      return false;
    },
    [currentVehicleCategory]
  );

  const currentCards = useMemo(() => {
    if (!workspace?.benefit_cards?.current_benefits) return [];
    return workspace.benefit_cards.current_benefits.filter((card) => !isExcludedForVehicle(card));
  }, [workspace?.benefit_cards?.current_benefits, isExcludedForVehicle]);

  const addonCards = useMemo(() => {
    if (!workspace?.benefit_cards?.available_addons) return [];
    return workspace.benefit_cards.available_addons.filter((card) => !isExcludedForVehicle(card));
  }, [workspace?.benefit_cards?.available_addons, isExcludedForVehicle]);

  const focCards = useMemo(() => {
    return currentCards.filter((card) => !isPaidExtraBenefitCard(card));
  }, [currentCards]);

  const purchasedAddonCards = useMemo(() => {
    return currentCards.filter((card) => isPaidExtraBenefitCard(card));
  }, [currentCards]);

  // Quick Action Export States (PNG / PDF)
  const debouncedSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /** Coalesce rapid benefit mutations into a single save after 800ms idle. */
  const scheduleSave = useCallback(() => {
    if (debouncedSaveRef.current !== null) clearTimeout(debouncedSaveRef.current);
    debouncedSaveRef.current = setTimeout(() => {
      debouncedSaveRef.current = null;
      save().catch(() => undefined);
    }, 800);
  }, [save]);

  function onQueue(op: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) {
    queueOperation(op, path);
    setUndoStack((prev) => [...prev, { op, path, revertOp, desc: "Benefit update" }]);
    setRedoStack([]);
    scheduleSave();
  }

  const [roundTotal, setRoundTotal] = useState<boolean>(() =>
    Boolean((workspace?.display_options as Record<string, unknown> | undefined)?.round_total)
  );

  useEffect(() => {
    if (workspace?.display_options && "round_total" in workspace.display_options) {
      setRoundTotal(Boolean((workspace.display_options as Record<string, unknown>).round_total));
    }
  }, [workspace?.display_options]);

  const toggleRoundTotal = useCallback(() => {
    const nextVal = !roundTotal;
    setRoundTotal(nextVal);
    queueOperation(
      { op: "update_display_options", options: { round_total: nextVal } },
      "display_options"
    );
    scheduleSave();
  }, [roundTotal, queueOperation, scheduleSave]);

  const previousValuesRef = useRef<Record<string, string>>({});

  const getDetectedValue = useCallback((fieldName: string): string => {
    if (!workspace?.fields) return "";
    const f = workspace.fields[fieldName] as (WorkspaceField & { detected_value?: string }) | undefined;
    let det = f?.detected_value ?? f?.value ?? "";
    if (fieldName === "sum_insured") {
      const numDet = parseFloat(String(det || "").replace(/[^0-9.]/g, ""));
      const covF = workspace.fields["coverage_amount"] as (WorkspaceField & { detected_value?: string }) | undefined;
      const covDet = covF?.detected_value ?? covF?.value ?? "";
      const numCov = parseFloat(String(covDet || "").replace(/[^0-9.]/g, ""));
      if ((!det || numDet < 1000) && numCov >= 1000) {
        det = covDet;
      }
    }
    const formField = FORM_FIELDS.find((item) => item.name === fieldName);
    return displayValue(formField?.kind || "text", det);
  }, [workspace?.fields]);

  const isFieldModified = useCallback((fieldName: string): boolean => {
    const current = String(formValues[fieldName] ?? "").trim();
    const detected = String(getDetectedValue(fieldName)).trim();
    const prev = String(previousValuesRef.current[fieldName] ?? "").trim();
    if (current === "" && detected === "") return false;
    return (detected !== "" && current !== detected) || (prev !== "" && current !== prev);
  }, [formValues, getDetectedValue]);

  const [copyingPng, setCopyingPng] = useState(false);
  const [copiedPng, setCopiedPng] = useState(false);
  const [copiedInfo, setCopiedInfo] = useState(false);
  const [downloadingPng, setDownloadingPng] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [viewLoading, setViewLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [pendingExportAction, setPendingExportAction] = useState<"copy_png" | "download_png" | "download_pdf" | null>(null);

  // Vehicle Ownership Conflict Gate State
  const [ownershipConflict, setOwnershipConflict] = useState<{
    has_conflict: boolean;
    resolved: boolean;
    vehicle_no?: string;
    car_brand?: string;
    car_model?: string;
    engine_cc?: string;
    previous_owner?: string;
    previous_policy_date?: string;
    previous_session_id?: string;
    previous_session_ref?: string;
    new_customer?: string;
    new_policy_date?: string;
    new_session_id?: string;
    new_session_ref?: string;
    resolution?: {
      type: string;
      resolved_at: string;
      notes?: string;
      new_customer?: string;
    };
  } | null>(null);
  const [conflictModalOpen, setConflictModalOpen] = useState(false);
  const [selectedResolution, setSelectedResolution] = useState<
    "car_sold_new_owner" | "old_quote_mistake" | "pending_verification"
  >("car_sold_new_owner");
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [resolvingConflict, setResolvingConflict] = useState(false);

  useEffect(() => {
    if (!id) return;
    api<{ has_conflict: boolean; resolved: boolean; [key: string]: any }>(`/sessions/${id}/ownership-conflict`)
      .then((data) => setOwnershipConflict(data))
      .catch((err) => console.warn("Could not check ownership conflict:", err));
  }, [id]);

  async function handleResolveConflict() {
    if (!id) return;
    setResolvingConflict(true);
    try {
      const res = await api<{ success: boolean; resolution: any }>(`/sessions/${id}/resolve-ownership`, {
        method: "POST",
        body: JSON.stringify({
          resolution_type: selectedResolution,
          notes: resolutionNotes || undefined,
        }),
      });
      setOwnershipConflict({
        has_conflict: false,
        resolved: true,
        resolution: res.resolution,
      });
      setConflictModalOpen(false);
      setToastMessage("Vehicle ownership conflict resolved! PDF generation is unlocked.");
    } catch (err: unknown) {
      alert("Failed to resolve conflict: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setResolvingConflict(false);
    }
  }

  // Gemini AI Extraction & Quota State
  const [geminiExtracting, setGeminiExtracting] = useState(false);
  const [geminiQuotaInfo, setGeminiQuotaInfo] = useState<GeminiQuota | null>(null);

  useEffect(() => {
    api<{ gemini?: GeminiQuota }>("/settings/limits")
      .then((res) => {
        if (res.gemini) setGeminiQuotaInfo(res.gemini);
      })
      .catch(() => { });
  }, []);

  async function triggerGeminiExtraction() {
    setGeminiExtracting(true);
    try {
      const res = await api<{
        success: boolean;
        message: string;
        quota: GeminiQuota;
        gemini_result: Record<string, unknown>;
      }>(`/sessions/${id}/extract-gemini`, { method: "POST" });
      setGeminiQuotaInfo(res.quota);
      setToastMessage(res.message || "Gemini AI extracted values successfully!");
      await reload();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Gemini extraction failed. Check your API key in .env.");
    } finally {
      setGeminiExtracting(false);
    }
  }

  useEffect(() => {
    if (!toastMessage) return;
    const timer = setTimeout(() => setToastMessage(null), 3000);
    return () => clearTimeout(timer);
  }, [toastMessage]);

  // Pure Flexbox Drag-to-Resize State
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState<"pdf" | "main" | "pdf-preview" | null>(null);
  const [colSizes, setColSizes] = useState({ pdf: 28, middle: 36, right: 36 });
  const [splitPdfPreview, setSplitPdfPreview] = useState(50); // when form is collapsed: PDF vs Preview %
  const [splitPdfForm, setSplitPdfForm] = useState(40); // when preview is collapsed: PDF vs Form %
  const [split2Col, setSplit2Col] = useState(45); // when PDF is closed: Form vs Preview %
  const [formCollapsed, setFormCollapsed] = useState(false);
  const [previewColCollapsed, setPreviewColCollapsed] = useState(false);
  const [isDesktop, setIsDesktop] = useState(true);

  // Dynamic responsive panel widths across all 7 combination states
  const pdfWidth = useMemo(() => {
    if (!pdfOpen) return "0%";
    if (formCollapsed && previewColCollapsed) return "100%";
    if (formCollapsed) return `${splitPdfPreview}%`;
    if (previewColCollapsed) return `${splitPdfForm}%`;
    return `${colSizes.pdf}%`;
  }, [pdfOpen, formCollapsed, previewColCollapsed, splitPdfPreview, splitPdfForm, colSizes.pdf]);

  const formWidth = useMemo(() => {
    if (formCollapsed) return "0%";
    if (!pdfOpen && previewColCollapsed) return "100%";
    if (!pdfOpen) return `${split2Col}%`;
    if (previewColCollapsed) return `${100 - splitPdfForm}%`;
    return `${colSizes.middle}%`;
  }, [formCollapsed, pdfOpen, previewColCollapsed, split2Col, splitPdfForm, colSizes.middle]);

  const previewWidth = useMemo(() => {
    if (previewColCollapsed) return "0%";
    if (!pdfOpen && formCollapsed) return "100%";
    if (!pdfOpen) return `${100 - split2Col}%`;
    if (formCollapsed) return `${100 - splitPdfPreview}%`;
    return `${colSizes.right}%`;
  }, [previewColCollapsed, pdfOpen, formCollapsed, split2Col, splitPdfPreview, colSizes.right]);

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(typeof window !== "undefined" ? window.innerWidth >= 1024 : true);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const handlePointerDown = useCallback((which: "pdf" | "main" | "pdf-preview") => (e: React.PointerEvent) => {
    e.preventDefault();
    setIsDragging(which);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handlePointerMove = (e: PointerEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const totalWidth = rect.width;
      if (totalWidth <= 0) return;

      const offsetX = e.clientX - rect.left;
      const percent = Math.max(10, Math.min(90, (offsetX / totalWidth) * 100));

      // Case 1: PDF + Preview open (Middle Form collapsed)
      if (isDragging === "pdf-preview") {
        const newPdf = Math.max(20, Math.min(80, percent));
        setSplitPdfPreview(newPdf);
        return;
      }

      // Case 2: All 3 panels open
      if (pdfOpen && !formCollapsed && !previewColCollapsed) {
        if (isDragging === "pdf") {
          const newPdf = Math.max(15, Math.min(45, percent));
          setColSizes((prev) => {
            const remaining = 100 - newPdf;
            const currentMiddleRight = prev.middle + prev.right || 1;
            const middleRatio = prev.middle / currentMiddleRight;
            const newMiddle = Math.max(20, Math.min(remaining - 20, remaining * middleRatio));
            const newRight = remaining - newMiddle;
            return { pdf: newPdf, middle: newMiddle, right: newRight };
          });
        } else if (isDragging === "main") {
          setColSizes((prev) => {
            const minMiddle = 20;
            const maxMiddle = 100 - prev.pdf - 20;
            const newMiddle = Math.max(minMiddle, Math.min(maxMiddle, percent - prev.pdf));
            const newRight = Math.max(20, 100 - prev.pdf - newMiddle);
            return { ...prev, middle: newMiddle, right: newRight };
          });
        }
        return;
      }

      // Case 3: PDF closed, Form + Preview open
      if (!pdfOpen && !formCollapsed && !previewColCollapsed) {
        if (isDragging === "main") {
          const newForm = Math.max(20, Math.min(80, percent));
          setSplit2Col(newForm);
        }
        return;
      }

      // Case 4: Preview collapsed, PDF + Form open
      if (pdfOpen && !formCollapsed && previewColCollapsed) {
        if (isDragging === "pdf") {
          const newPdf = Math.max(20, Math.min(80, percent));
          setSplitPdfForm(newPdf);
        }
        return;
      }
    };

    const handlePointerUp = () => {
      setIsDragging(null);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isDragging, pdfOpen, formCollapsed, previewColCollapsed]);


  const [customLabel, setCustomLabel] = useState("");
  const [customValue, setCustomValue] = useState("");
  const [learnPrompt, setLearnPrompt] = useState<{ field: string; value: string } | null>(null);
  const promptedRef = useRef<Set<string>>(new Set());

  const [publishedTemplates, setPublishedTemplates] = useState<PublishedTemplateOption[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [templateImpact, setTemplateImpact] = useState<TemplateSelectionImpact | null>(null);

  // Live Canvas Preview state
  const [previewTemplate, setPreviewTemplate] = useState<TemplatePayload | null>(null);
  const [previewZoom, setPreviewZoom] = useState(0.48);
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewScrollRef = useRef<HTMLDivElement | null>(null);

  // Active native wheel listener for Ctrl / Cmd + Mouse Wheel canvas zooming (bypasses passive listener limitation)
  useEffect(() => {
    const handleWheel = (e: WheelEvent) => {
      if (!previewScrollRef.current || !previewScrollRef.current.contains(e.target as Node)) return;
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const step = 0.08;
        const delta = e.deltaY < 0 ? step : -step;
        setPreviewZoom((z) => Math.min(2.5, Math.max(0.25, Number((z + delta).toFixed(2)))));
      }
    };

    window.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      window.removeEventListener("wheel", handleWheel);
    };
  }, []);

  const [allBenefitPresets, setAllBenefitPresets] = useState<BenefitCardStyle[]>(() => {
    return getAllBenefitPresets();
  });

  // Re-fetch benefit presets on focus so user edits from /builder/templates/benefit-templates are picked up instantly
  useEffect(() => {
    const updatePresets = () => setAllBenefitPresets(getAllBenefitPresets());
    window.addEventListener("focus", updatePresets);
    return () => window.removeEventListener("focus", updatePresets);
  }, []);

  const [selectedBenefitPreset, setSelectedBenefitPreset] = useState<string>(() => {
    try {
      const stored = (workspace?.fields?.benefit_preset as any)?.value;
      if (stored) return stored;
      return localStorage.getItem("risklocker_default_benefit_preset") || "masonry-flow";
    } catch {
      return "masonry-flow";
    }
  });

  const handleSelectBenefitPreset = useCallback((presetId: string) => {
    setSelectedBenefitPreset(presetId);
    try {
      localStorage.setItem("risklocker_default_benefit_preset", presetId);
    } catch {}
    decideField("benefit_preset", "edit", presetId);
    const cfg = getBenefitPreset(presetId);
    decideField("benefit_preset_config", "edit", JSON.stringify(cfg));
  }, [decideField]);

  const displayOptions = useMemo(() => {
    if (workspace?.display_options && Object.keys(workspace.display_options).length > 0) {
      return workspace.display_options;
    }
    return (previewTemplate?.config as any)?.display_options || {};
  }, [workspace?.display_options, previewTemplate?.config]);

  const balancedElements = useMemo(() => {
    if (!previewTemplate?.config?.canvas) return [];
    const rawElements = (previewTemplate.config.canvas.elements || []).map((el: any) => {
      if (el.type === "benefit-grid") {
        return applyPresetToCanvasElement(el, selectedBenefitPreset);
      }
      return el;
    });
    return balanceBenefitGridElements(rawElements, {
      ...workspace?.benefit_cards,
      current_benefits: currentCards,
      available_addons: addonCards,
      extras: workspace?.extras,
      displayOptions,
    } as any);
  }, [previewTemplate, workspace?.benefit_cards, workspace?.extras, selectedBenefitPreset, displayOptions, allBenefitPresets, currentCards, addonCards]);

  const canvasH = useMemo(() => {
    const baseHeight = previewTemplate?.config?.canvas?.height || 1123;
    if (!balancedElements.length) return baseHeight;
    const maxElementBottom = Math.max(0, ...balancedElements.map((e: any) => (e.y || 0) + (e.h || 0)));
    return maxElementBottom + 30 > baseHeight ? maxElementBottom + 30 : baseHeight;
  }, [balancedElements, previewTemplate]);

  const syncForm = useCallback(() => {
    if (!workspace) return;
    const values: Record<string, string> = {};
    for (const field of FORM_FIELDS) {
      let stored = (workspace.fields[field.name] as WorkspaceField | undefined)?.value;
      if (field.name === "sum_insured") {
        const numStored = parseFloat(String(stored || "").replace(/[^0-9.]/g, ""));
        const altCov = (workspace.fields["coverage_amount"] as WorkspaceField | undefined)?.value;
        const numAlt = parseFloat(String(altCov || "").replace(/[^0-9.]/g, ""));
        if ((!stored || numStored < 1000) && numAlt >= 1000) {
          stored = altCov;
        } else if (!stored) {
          stored = (workspace.fields["market_value"] as WorkspaceField | undefined)?.value ||
                   (workspace.fields["agreed_value"] as WorkspaceField | undefined)?.value;
        }
      }
      if (field.name === "quotation_reference") {
        const qrefCandidate = stored || workspace.quotation_ref;
        if (qrefCandidate && (!stored || !String(stored).startsWith("RL"))) {
          stored = workspace.quotation_ref || stored;
        }
      }
      values[field.name] = displayValue(field.kind, stored ?? null);
    }

    if (!values.excess_amount || values.excess_amount.trim() === "" || values.excess_amount === "—") {
      values.excess_amount = "0.00";
    }

    if (!values.compulsory_excess || values.compulsory_excess.trim() === "" || values.compulsory_excess === "—") {
      values.compulsory_excess = "0.00";
    }

    // Auto-compute road tax if missing, 0, or corporate mismatch
    const custName = values.insured_name || values.customer_name || (workspace.fields?.insured_name as WorkspaceField | undefined)?.value || "";
    const clientType = values.client_type || (workspace.fields?.client_type as WorkspaceField | undefined)?.value || "";
    const isCorpName = /(SDN\s*BHD|BHD|ENTERPRISE|TRADING|LTD|LLC|PLT|COMPANY|ENT\.|CORP|HOLDINGS|CO\.)/i.test(String(custName));
    const isCorp = String(clientType).toLowerCase().includes("company") || String(clientType).toLowerCase().includes("corp") || isCorpName;

    const carModel = values.car_model || (workspace.fields?.car_model as WorkspaceField | undefined)?.value || "";
    const carBrand = values.car_brand || (workspace.fields?.car_brand as WorkspaceField | undefined)?.value || "";
    let vtype = values.vehicle_type || (workspace.fields?.vehicle_type as WorkspaceField | undefined)?.value || "Car";

    const ccStr = values.engine_cc || (workspace.fields?.engine_cc as WorkspaceField | undefined)?.value || "";
    const evCat = detectEVCategory(carBrand, carModel, ccStr);

    if (vtype.startsWith("EV") || evCat) {
      vtype = vtype.startsWith("EV") ? vtype : (evCat || "EVSaloonCar");
      values.vehicle_type = vtype;
    } else if (isNonSaloonCarModel(carModel) || vtype.toLowerCase().includes("nonsaloon") || vtype.toLowerCase().includes("non-saloon") || vtype.toLowerCase().includes("suv") || vtype.toLowerCase().includes("mpv")) {
      vtype = "NonSaloonCar";
      values.vehicle_type = "NonSaloonCar";
    } else if (isCorp && (vtype === "Car" || vtype.toLowerCase().includes("saloon"))) {
      vtype = "CompanyCar";
      values.vehicle_type = "CompanyCar";
    } else if (isCorp && vtype === "Motorcycle") {
      vtype = "CompanyMotorcycle";
      values.vehicle_type = "CompanyMotorcycle";
    }
    if (isCorp && !values.client_type) {
      values.client_type = "Company";
    }

    const isEV = vtype.startsWith("EV");
    const rawParsed = ccStr ? parseFloat(String(ccStr).replace(/[^0-9.]/g, "")) : (isEV ? null : inferCCFromCarModel(carModel));
    if (rawParsed && rawParsed > 0) {
      if (isEV) {
        if (rawParsed >= 1000) {
          const kw = rawParsed / 1000;
          values.engine_cc = `${Number.isInteger(kw) ? kw : kw.toFixed(1)} kW`;
        } else if (!values.engine_cc?.includes("kW")) {
          values.engine_cc = `${Number.isInteger(rawParsed) ? rawParsed : rawParsed.toFixed(1)} kW`;
        }
        const computedRT = computeMalaysianRoadTax(rawParsed, vtype, "Individual");
        if (computedRT > 0) {
          values.roadtax = computedRT.toFixed(2);
        }
      } else if (rawParsed <= 7000) {
        const parsedCC = Math.round(rawParsed);
        const isCompany = isCorp || String(vtype).toLowerCase().includes("company") || String(vtype).toLowerCase().includes("corp");
        const baseType = vtype === "NonSaloonCar" ? "NonSaloonCar" : String(vtype).toLowerCase().includes("motor") ? "Motorcycle" : (String(vtype).toLowerCase().includes("lorry") || String(vtype).toLowerCase().includes("other")) ? "Lorry" : "Car";
        const computedRT = computeMalaysianRoadTax(parsedCC, baseType, isCompany ? "Company" : "Individual");
        if (computedRT > 0) {
          const currentRT = parseFloat(String(values.roadtax || "").replace(/[^0-9.]/g, "")) || 0;
          if (currentRT === 0 || currentRT > 10000 || (isCompany && currentRT < computedRT) || vtype === "NonSaloonCar") {
            values.roadtax = computedRT.toFixed(2);
          }
        }
      }
    }

    // Sync Total Premium with roadtax, runner fee, and extras
    const pNum = parseFloat(String(values.premium || "").replace(/[^0-9.]/g, "")) || 0;
    const rtNum = parseFloat(String(values.roadtax || "").replace(/[^0-9.]/g, "")) || 0;
    const sfNum = parseFloat(String(values.service_fee || "").replace(/[^0-9.]/g, "")) || 0;
    const extrasTotal = (workspace.extras || []).reduce((acc, ex) => {
      const amt = (ex as Record<string, unknown>)?.price;
      const val = typeof amt === "object" && amt !== null ? ((amt as Record<string, unknown>).amount ?? (amt as Record<string, unknown>).value) : amt;
      const num = typeof val === "string" ? parseFloat(val.replace(/,/g, "")) : (typeof val === "number" ? val : 0);
      return acc + (Number.isFinite(num) ? num : 0);
    }, 0);

    if (pNum > 0) {
      const combinedPremium = pNum + extrasTotal;
      values.insurance_premium_total = combinedPremium > 0 ? combinedPremium.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "";
      values.total_amount = (pNum + rtNum + sfNum + extrasTotal).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else if (workspace.total_premium_adjusted) {
      values.total_amount = formatMoney(workspace.total_premium_adjusted);
    }

    setFormValues(values);
  }, [workspace]);

  useEffect(() => {
    syncForm();
  }, [syncForm, mutation.lastSavedAt]);

  useEffect(() => {
    let cancelled = false;
    api<{ companies: { items: Array<{ id: string; name: string }> } }>("/business/companies?page_size=100")
      .then((result) => { if (!cancelled) setCompanies(result.companies?.items || []); })
      .catch(() => undefined);

    api<{ benefit_concepts: { items: GlobalConcept[] } }>("/business/benefit-concepts?page=1&page_size=100")
      .then((res) => { if (!cancelled) setGlobalConcepts(res.benefit_concepts?.items || []); })
      .catch(() => undefined);

    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const companyId = workspace?.pinned.company_id;
    if (!companyId) {
      setCompanyWorkspace(null);
      return;
    }
    let cancelled = false;
    api<{ workspace: CompanyWorkspace }>(`/business/companies/${companyId}/workspace`)
      .then((result) => { if (!cancelled) setCompanyWorkspace(result.workspace); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [workspace?.pinned.company_id]);

  useEffect(() => {
    let cancelled = false;
    setTemplatesLoading(true);
    api<{ templates: PublishedTemplateOption[] }>("/business/templates/published")
      .then((result) => {
        if (!cancelled) {
          const list = result.templates || [];
          setPublishedTemplates(list);
          if (list.length > 0) {
            const currentRevisionId = workspace?.pinned.template_revision_id;
            const matching = list.find((item) => item.template_revision_id === currentRevisionId) || list[0];
            if (matching.config && !previewTemplate) {
              setPreviewTemplate({
                template_id: matching.template_id,
                template_revision_id: matching.template_revision_id,
                revision_number: matching.revision_number,
                config_hash: matching.config_hash,
                source: "template_revision",
                config: matching.config,
                binding: { template_id: matching.template_id, template_revision_id: matching.template_revision_id, base_hash: matching.config_hash },
              });
            }
          }
        }
      })
      .catch((error) => { if (!cancelled) setTemplateError(apiErrorMessage(error)); })
      .finally(() => { if (!cancelled) setTemplatesLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // Load template config for real-time live preview
  useEffect(() => {
    let cancelled = false;
    setPreviewLoading(true);
    api<{ template: TemplatePayload | null }>(`/sessions/${id}/template-config`)
      .then((res) => {
        if (!cancelled && res.template) setPreviewTemplate(res.template);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => { cancelled = true; };
  }, [id, workspace?.pinned.template_revision_id]);

  async function selectTemplate(templateRevisionId: string) {
    setTemplateError(null);
    if (!templateRevisionId || templateRevisionId === workspace?.pinned.template_revision_id) return;
    const option = publishedTemplates.find((item) => item.template_revision_id === templateRevisionId);
    if (!option) return;
    try {
      const res = await api<{ impact: TemplateSelectionImpact }>(`/sessions/${id}/template-selection-impact`, {
        method: "POST",
        body: JSON.stringify({ base_revision: workspace?.revision || 1, template_revision_id: option.template_revision_id }),
      });
      if (res.impact.requires_confirmation) {
        setTemplateImpact(res.impact);
      } else {
        await selectTemplateDirectly(templateRevisionId);
      }
    } catch {
      await selectTemplateDirectly(templateRevisionId);
    }
  }

  async function selectTemplateDirectly(templateRevisionId: string, customList?: PublishedTemplateOption[]) {
    setTemplateError(null);
    setTemplateImpact(null);
    if (!templateRevisionId) return;
    const pool = customList && customList.length > 0 ? customList : publishedTemplates;
    const option = pool.find((item) => item.template_revision_id === templateRevisionId) || pool[0];
    if (!option) {
      return;
    }
    if (option.config) {
      setPreviewTemplate({
        template_id: option.template_id,
        template_revision_id: option.template_revision_id,
        revision_number: option.revision_number,
        config_hash: option.config_hash,
        source: "template_revision",
        config: option.config,
        binding: { template_id: option.template_id, template_revision_id: option.template_revision_id, base_hash: option.config_hash },
      });
    }
    if (templateRevisionId === workspace?.pinned.template_revision_id) return;
    queueOperation({
      op: "template_selection",
      template_revision_id: option.template_revision_id,
      template_id: option.template_id,
      revision_number: option.revision_number,
      config_hash: option.config_hash,
      confirmed: true,
    }, "template_revision_id");

    try {
      await save();
    } catch {
      // optimistic state active
    }
  }

  function confirmTemplateSelection() {
    if (!templateImpact) return;
    const option = publishedTemplates.find((item) => item.template_revision_id === templateImpact.target.template_revision_id);
    if (!option) {
      setTemplateError("That published template is no longer available. Refresh this page.");
      return;
    }
    queueOperation({
      op: "template_selection",
      template_revision_id: option.template_revision_id,
      template_id: option.template_id,
      revision_number: option.revision_number,
      config_hash: option.config_hash,
      confirmed: true,
    }, "template_revision_id");
    setTemplateImpact(null);
    save().catch(() => undefined);
  }

  function getProductVehicleCategory(productName: string): "Car" | "Motorcycle" | "Lorry" {
    const lower = (productName || "").toLowerCase();
    if (/motorcycle|motor\s*cycle|motosikal|bike/i.test(lower)) {
      return "Motorcycle";
    }
    if (/lorry|truck|rigid|trailer|tipper|prime mover|haulage|commercial\s*vehicle|c\s*permit|a\s*permit/i.test(lower)) {
      return "Lorry";
    }
    return "Car";
  }

  function formatProductLabel(rawName: string): string {
    let label = rawName;
    if (!/\b(Comprehensive|TPFT|TPO|Third Party)\b/i.test(rawName)) {
      const lowerName = rawName.toLowerCase();
      let covLabel = "Comprehensive";
      if (lowerName.includes("tpft") || (lowerName.includes("third party") && lowerName.includes("fire"))) {
        covLabel = "TPFT";
      } else if (lowerName.includes("third") || lowerName.includes("tpo") || lowerName.includes("party")) {
        covLabel = "TPO";
      }
      label = `${rawName} (${covLabel})`;
    }
    return label;
  }

  const isCurrentEV = useMemo(() => {
    const vtype = String(formValues?.vehicle_type || workspace?.fields?.vehicle_type?.value || "").toUpperCase();
    return vtype.startsWith("EV");
  }, [formValues?.vehicle_type, workspace?.fields?.vehicle_type]);

  const productOptions = useMemo(() => {
    const raw = companyWorkspace?.products || [];
    const catalogs = companyWorkspace?.catalogs || [];
    const validProductIds = new Set(
      catalogs
        .filter((cat) => cat.status !== "archived" && cat.status !== "retired")
        .map((cat) => cat.product_id)
        .filter(Boolean)
    );

    // Filter by:
    // 1. Not archived or retired
    // 2. Has at least one non-archived catalog in this company (if catalogs exist)
    // 3. Not a junk mock product (e.g. Product-...)
    // 4. Matches active powertrain (EV vs ICE)
    const validProducts = raw.filter((p) => {
      if (p.status === "archived" || p.status === "retired") return false;
      if (p.name && /^product-/i.test(p.name)) return false;
      if (validProductIds.size > 0 && !validProductIds.has(p.id)) return false;
      const isEvProduct = /\(ev\)|(\bev\b)|electric/i.test(p.name || "");
      return isCurrentEV ? isEvProduct : !isEvProduct;
    });

    // Deduplicate by clean name
    const seen = new Set<string>();
    return validProducts.filter((p) => {
      const key = (p.name || "").trim().toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [companyWorkspace, isCurrentEV]);

  const categorizedProducts = useMemo(() => {
    const cars: typeof productOptions = [];
    const motorcycles: typeof productOptions = [];
    const lorries: typeof productOptions = [];

    for (const prod of productOptions) {
      const cat = getProductVehicleCategory(prod.name || "");
      if (cat === "Motorcycle") {
        motorcycles.push(prod);
      } else if (cat === "Lorry") {
        lorries.push(prod);
      } else {
        cars.push(prod);
      }
    }
    return { cars, motorcycles, lorries };
  }, [productOptions]);

  const tierOptions = useMemo(
    () => (companyWorkspace?.tiers || []).filter((tier) => tier.product_id === workspace?.pinned.product_id),
    [companyWorkspace, workspace?.pinned.product_id],
  );

  const companyName = workspace?.pinned_names.company_name;

  const insurerConceptKeys = useMemo(() => {
    const keys = new Set<string>();
    if (companyWorkspace?.catalogs) {
      for (const cat of companyWorkspace.catalogs) {
        for (const off of (cat.offerings || [])) {
          if (off.concept_key) keys.add(String(off.concept_key));
          if (off.concept?.concept_key) keys.add(String(off.concept.concept_key));
          if (off.concept_id) keys.add(String(off.concept_id));
          if (off.concept?.id) keys.add(String(off.concept.id));
        }
      }
    }
    if ((workspace as any)?.catalog_offerings) {
      for (const off of ((workspace as any).catalog_offerings as any[])) {
        if (off.concept_key) keys.add(String(off.concept_key));
        if (off.concept?.concept_key) keys.add(String(off.concept.concept_key));
        if (off.concept_id) keys.add(String(off.concept_id));
      }
    }
    if (workspace?.benefits) {
      for (const b of workspace.benefits) {
        if (b && typeof b === "object") {
          const cKey = (b as any).concept_key;
          const cId = (b as any).concept_id;
          if (cKey && typeof cKey === "string") keys.add(cKey);
          if (cId && typeof cId === "string") keys.add(cId);
        }
      }
    }
    return keys;
  }, [companyWorkspace, workspace]);

  const filteredConcepts = useMemo(() => {
    return globalConcepts.filter((c) => {
      if (isExcludedForVehicle(c)) return false;
      if (modalFilter === "insurer" && !insurerConceptKeys.has(c.concept_key) && !insurerConceptKeys.has(c.id)) return false;
      if (modalFilter === "global" && !GLOBAL_BENEFIT_KEYS.has(c.concept_key)) return false;
      if (modalFilter === "addons" && GLOBAL_BENEFIT_KEYS.has(c.concept_key)) return false;
      if (!globalSearch.trim()) return true;
      const term = globalSearch.toLowerCase();
      return c.label.toLowerCase().includes(term) || c.concept_key.toLowerCase().includes(term);
    });
  }, [globalConcepts, modalFilter, globalSearch, insurerConceptKeys, isExcludedForVehicle]);

  const conceptAssets = useMemo(() => {
    const map: Record<string, string> = {};
    for (const c of globalConcepts) {
      const url = c.default_asset?.url || (c.default_asset_id ? `/business/assets/${c.default_asset_id}/content?profile=ui` : null);
      if (url) {
        if (c.concept_key) map[c.concept_key] = url;
        if (c.id) map[c.id] = url;
        if (c.label) {
          map[c.label.toLowerCase()] = url;
          map[c.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")] = url;
        }
      }
    }
    return map;
  }, [globalConcepts]);

  const previewTemplateAssets = useMemo(() => {
    if (!previewTemplate?.config) return [];
    const list: Array<{ id: string; label: string; url: string }> = Object.entries(previewTemplate.config.assets || {}).map(([key, id]) => ({
      id,
      label: key,
      url: id.includes("-") ? `/business/assets/${id}/content?profile=ui` : `/template-assets/${id}`,
    }));
    const systemDefaults: Array<{ id: string; label: string; url: string }> = [
      { id: "e9685e1f-ac95-410c-a2e9-eccb7ca35d5f", label: "risklocker_logo", url: "/business/assets/e9685e1f-ac95-410c-a2e9-eccb7ca35d5f/content?profile=ui" },
      { id: "2168eaee-3e56-4903-8c4f-841f01ff2407", label: "bank_logo", url: "/business/assets/2168eaee-3e56-4903-8c4f-841f01ff2407/content?profile=ui" },
      { id: "3653a3b861c06f00", label: "risklocker_logo", url: "/template-assets/3653a3b861c06f00" },
      { id: "c4d540c072507abc", label: "bank_logo", url: "/template-assets/c4d540c072507abc" },
      { id: "91116a7dc3540d62", label: "all_driver_icon", url: "/template-assets/91116a7dc3540d62" },
      { id: "49e754a6faa949c2", label: "background", url: "/template-assets/49e754a6faa949c2" },
    ];
    for (const sys of systemDefaults) {
      if (!list.some((a) => a.id === sys.id)) {
        list.push(sys);
      }
    }
    for (const el of previewTemplate.config.canvas?.elements || []) {
      if (el.assetId && !list.some((a) => a.id === el.assetId)) {
        list.push({
          id: el.assetId,
          label: el.name || "Asset",
          url: el.assetId.includes("-") ? `/business/assets/${el.assetId}/content?profile=ui` : `/template-assets/${el.assetId}`,
        });
      }
    }
    return list;
  }, [previewTemplate]);

  const previewFields = useMemo(() => {
    const fields: Record<string, string> = {};
    if (workspace?.fields) {
      for (const [name, field] of Object.entries(workspace.fields)) {
        fields[name] = String(field?.value ?? "");
      }
    }
    // Overlay real-time active form values on every keystroke
    for (const [name, val] of Object.entries(formValues)) {
      if (val !== undefined && val !== null && String(val).trim() !== "") {
        fields[name] = String(val);
      }
    }

    // Quotation reference aliases
    const qref = formValues["quotation_reference"] || fields["quotation_reference"] || formValues["quotation_ref"] || fields["quotation_ref"] || "";
    if (qref) {
      fields["quotation_reference"] = qref;
      fields["quotation_ref"] = qref;
      fields["quote_ref"] = qref;
      fields["reference_no"] = qref;
    }

    // Vehicle plate aliases
    const plate = formValues["vehicle_no"] || fields["vehicle_no"] || "";
    if (plate) {
      fields["vehicle_no"] = plate;
      fields["vehicle_plate"] = plate;
      fields["car_plate"] = plate;
      fields["plate_no"] = plate;
    }

    // Insurer name aliases
    const effectiveCompany = formValues["insurance_company"] || fields["insurance_company"] || companyName || workspace?.pinned_names?.company_name || "";
    if (effectiveCompany) {
      const upperCompany = effectiveCompany.toUpperCase();
      fields["insurance_company"] = upperCompany;
      fields["insurance_name"] = upperCompany;
      fields["company_name"] = upperCompany;
      fields["insurer_name"] = upperCompany;
    }

    // Sum insured / coverage amount
    const sumIns = formValues["sum_insured"] || fields["sum_insured"] || formValues["coverage_amount"] || fields["coverage_amount"] || "";
    if (sumIns) {
      fields["sum_insured"] = sumIns;
      fields["coverage_amount"] = sumIns;
    }

    // Engine CC aliases
    const cc = formValues["engine_cc"] || fields["engine_cc"] || "";
    if (cc) {
      fields["engine_cc"] = cc;
      fields["vehicle_cc"] = cc;
      fields["engine_capacity"] = cc;
    }

    // NCD aliases
    const ncd = formValues["ncd_percent"] || fields["ncd_percent"] || formValues["ncd_percentage"] || fields["ncd_percentage"] || "";
    if (ncd) {
      fields["ncd_percent"] = ncd;
      fields["ncd_percentage"] = ncd;
    }

    // Premium aliases
    const prem = formValues["premium"] || fields["premium"] || formValues["coverage_premium"] || fields["coverage_premium"] || "";
    if (prem) {
      fields["premium"] = prem;
      fields["coverage_premium"] = prem;
      fields["basic_premium_vehicle"] = prem;
    }

    // Road tax aliases
    const custName = formValues["insured_name"] || formValues["customer_name"] || fields["insured_name"] || fields["customer_name"] || "";
    const clientType = formValues["client_type"] || fields["client_type"] || "";
    const isCorpName = /(SDN\s*BHD|BHD|ENTERPRISE|TRADING|LTD|LLC|PLT|COMPANY|ENT\.|CORP|HOLDINGS|CO\.)/i.test(String(custName));
    const isCorp = String(clientType).toLowerCase().includes("company") || String(clientType).toLowerCase().includes("corp") || isCorpName;

    const carModel = formValues["car_model"] || fields["car_model"] || "";
    const carBrand = formValues["car_brand"] || fields["car_brand"] || (workspace?.fields?.car_brand as WorkspaceField | undefined)?.value || "";
    let rtax = formValues["roadtax"] || fields["roadtax"] || formValues["road_tax_amount"] || fields["road_tax_amount"] || "";
    const ccStr = formValues["engine_cc"] || fields["engine_cc"] || "";
    let vtype = formValues["vehicle_type"] || fields["vehicle_type"] || "Car";
    const evCat = detectEVCategory(carBrand, carModel, ccStr);

    if (vtype.startsWith("EV") || evCat) {
      vtype = vtype.startsWith("EV") ? vtype : (evCat || "EVSaloonCar");
      formValues["vehicle_type"] = vtype;
      fields["vehicle_type"] = vtype;
    } else if (isNonSaloonCarModel(carModel) || vtype.toLowerCase().includes("nonsaloon") || vtype.toLowerCase().includes("non-saloon") || vtype.toLowerCase().includes("suv") || vtype.toLowerCase().includes("mpv")) {
      vtype = "NonSaloonCar";
      formValues["vehicle_type"] = "NonSaloonCar";
      fields["vehicle_type"] = "NonSaloonCar";
    } else if (isCorp && (vtype === "Car" || vtype.toLowerCase().includes("saloon"))) {
      vtype = "CompanyCar";
      formValues["vehicle_type"] = "CompanyCar";
      fields["vehicle_type"] = "CompanyCar";
    }

    const isEV = vtype.startsWith("EV");
    const rawParsed = ccStr ? parseFloat(String(ccStr).replace(/[^0-9.]/g, "")) : (isEV ? null : inferCCFromCarModel(carModel));
    if (rawParsed && rawParsed > 0) {
      if (isEV) {
        const computedRT = computeMalaysianRoadTax(rawParsed, vtype, "Individual");
        if (computedRT > 0) {
          rtax = computedRT.toFixed(2);
        }
      } else if (rawParsed <= 7000) {
        const parsedCC = Math.round(rawParsed);
        const isCompany = isCorp || String(vtype).toLowerCase().includes("company") || String(vtype).toLowerCase().includes("corp");
        const baseType = vtype === "NonSaloonCar" ? "NonSaloonCar" : String(vtype).toLowerCase().includes("motor") ? "Motorcycle" : (String(vtype).toLowerCase().includes("lorry") || String(vtype).toLowerCase().includes("other")) ? "Lorry" : "Car";
        const computedRT = computeMalaysianRoadTax(parsedCC, baseType, isCompany ? "Company" : "Individual");
        if (computedRT > 0) {
          const currentRT = parseFloat(String(rtax || "").replace(/[^0-9.]/g, "")) || 0;
          if (currentRT === 0 || currentRT > 10000 || (isCompany && currentRT < computedRT) || vtype === "NonSaloonCar") {
            rtax = computedRT.toFixed(2);
          }
        }
      }
    }
    if (rtax) {
      fields["roadtax"] = rtax;
      fields["road_tax_amount"] = rtax;
    }

    // Runner / Service fee aliases
    const sfee = formValues["service_fee"] || fields["service_fee"] || formValues["runner_fee"] || fields["runner_fee"] || "";
    if (sfee) {
      fields["service_fee"] = sfee;
      fields["runner_fee"] = sfee;
    }

    // Compute live total premium (Insurance Premium + Roadtax + Runner Fee + Extras)
    const pNum = parseFloat(String(fields["premium"] || "").replace(/[^0-9.]/g, "")) || 0;
    const rtNum = parseFloat(String(fields["roadtax"] || "").replace(/[^0-9.]/g, "")) || 0;
    const sfNum = parseFloat(String(fields["service_fee"] || "").replace(/[^0-9.]/g, "")) || 0;
    const extrasTotal = (workspace?.extras || []).reduce((acc, ex) => {
      const amt = (ex as Record<string, unknown>)?.price;
      const val = typeof amt === "object" && amt !== null ? ((amt as Record<string, unknown>).amount ?? (amt as Record<string, unknown>).value) : amt;
      const num = typeof val === "string" ? parseFloat(val.replace(/,/g, "")) : (typeof val === "number" ? val : 0);
      return acc + (Number.isFinite(num) ? num : 0);
    }, 0);

    const calculatedTotal = pNum + extrasTotal + rtNum + sfNum;
    const isRound = roundTotal || Boolean((workspace?.display_options as Record<string, unknown> | undefined)?.round_total);
    const finalTotalNum = isRound && calculatedTotal > 0 ? Math.round(calculatedTotal) : calculatedTotal;
    let effTotal = "";
    if (finalTotalNum > 0) {
      effTotal = finalTotalNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else {
      const rawTot = formValues["total_amount"] || fields["total_amount"] || workspace?.total_premium_adjusted || "";
      const rawNum = parseFloat(String(rawTot).replace(/[^0-9.]/g, ""));
      if (isRound && rawNum > 0) {
        effTotal = Math.round(rawNum).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      } else {
        effTotal = rawTot;
      }
    }

    const calculatedPremium = pNum + extrasTotal;
    fields["insurance_premium_total"] = calculatedPremium > 0
      ? calculatedPremium.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : "";

    // Validity date aliases
    const vUntil = formValues["valid_until"] || fields["valid_until"] || formValues["quotation_validity"] || fields["quotation_validity"] || "";
    if (vUntil) {
      fields["valid_until"] = vUntil;
      fields["quotation_validity"] = vUntil;
    }

    fields["total_amount"] = effTotal;
    fields["total_premium_adjusted"] = effTotal;
    return fields;
  }, [workspace?.fields, workspace?.total_premium_adjusted, workspace?.extras, workspace?.pinned_names?.company_name, workspace?.display_options, formValues, companyName, roundTotal]);

  function commitField(field: FormField) {
    const current = formValues[field.name];
    if (current === undefined) return;
    if (field.kind === "total") return;
    
    if (current.trim() === "") {
      decideField(field.name, "clear", "");
    } else {
      decideField(field.name, "edit", current);
    }

    if (field.name === "sum_insured") {
      decideField("coverage_amount", "edit", current);
      decideField("market_value", "edit", current);
      decideField("agreed_value", "edit", current);
    }

    if (field.name === "insurance_company") {
      const match = companies.find(
        (c) => c.name.toLowerCase().trim() === current.toLowerCase().trim()
      );
      if (match && match.id !== workspace?.pinned.company_id) {
        pinCatalog(match.id);
      }
    }
  }

  function commitFieldDirectly(name: string, value: string) {
    if (value === undefined) return;
    if (value.trim() === "") {
      decideField(name, "clear", "");
      if (name === "sum_insured") {
        decideField("coverage_amount", "clear", "");
        decideField("market_value", "clear", "");
        decideField("agreed_value", "clear", "");
      }
      return;
    }
    decideField(name, "edit", value);
    if (name === "sum_insured") {
      decideField("coverage_amount", "edit", value);
      decideField("market_value", "edit", value);
      decideField("agreed_value", "edit", value);
    }
    if (name === "insurance_company") {
      const match = companies.find(
        (c) => c.name.toLowerCase().trim() === value.toLowerCase().trim()
      );
      if (match && match.id !== workspace?.pinned.company_id) {
        pinCatalog(match.id);
      }
    }
  }

  const handleResetField = useCallback((field: FormField) => {
    const detVal = getDetectedValue(field.name);
    const targetVal = detVal !== "" ? detVal : (previousValuesRef.current[field.name] || "");
    setFormValues((prev) => ({ ...prev, [field.name]: targetVal }));
    commitFieldDirectly(field.name, targetVal);
    if (field.name === "sum_insured") {
      commitFieldDirectly("coverage_amount", targetVal);
      commitFieldDirectly("market_value", targetVal);
      commitFieldDirectly("agreed_value", targetVal);
    }
    delete previousValuesRef.current[field.name];
  }, [getDetectedValue]);

  async function pinCatalog(companyId: string, productId?: string | null, tierId?: string | null) {
    setPinLoading(true);
    const company = companies.find((item) => item.id === companyId);
    const product = productId ? productOptions.find((item) => item.id === productId) : null;
    const tier = tierId ? tierOptions.find((item) => item.id === tierId) : null;

    if (company) {
      setFormValues((prev) => ({
        ...prev,
        insurance_company: company.name,
      }));
    }

    onQueue({
      op: "pin_catalog",
      company_id: companyId,
      ...(productId ? { product_id: productId } : {}),
      ...(tierId ? { tier_id: tierId } : {}),
      company_name: company?.name || workspace?.pinned_names.company_name,
      ...(product ? { product_name: product.name } : {}),
      ...(tier ? { tier_name: tier.name } : {}),
    }, "catalog");

    try {
      await save();
    } catch {
      // Best effort
    } finally {
      setPinLoading(false);
    }
  }

  function handlePackageSelect(productId: string) {
    if (!productId || !workspace?.pinned.company_id) {
      if (workspace?.pinned.company_id) {
        pinCatalog(workspace.pinned.company_id as string, null);
      }
      return;
    }
    const selectedProd = productOptions.find((p) => p.id === productId);
    if (selectedProd) {
      const targetCat = getProductVehicleCategory(selectedProd.name || "");
      const currentVtype = String(formValues.vehicle_type || "");
      const isEv = currentVtype.startsWith("EV");
      const currentCat = currentVtype.includes("Motor")
        ? "Motorcycle"
        : (currentVtype.toLowerCase().includes("lorry") || currentVtype.toLowerCase().includes("other") ? "Lorry" : "Car");

      if (targetCat !== currentCat) {
        let newVtype = "Car";
        if (isEv) {
          newVtype = targetCat === "Motorcycle" ? "EVMotorcycle" : (targetCat === "Lorry" ? "EVCommercial" : "EVSaloonCar");
        } else {
          newVtype = targetCat === "Motorcycle" ? "Motorcycle" : (targetCat === "Lorry" ? "Lorry" : "Car");
        }

        const prevLabel = currentCat === "Motorcycle" ? "Motorcycle" : (currentCat === "Lorry" ? "Lorry / Commercial" : "Car");
        const nextLabel = targetCat === "Motorcycle" ? "Motorcycle" : (targetCat === "Lorry" ? "Lorry / Commercial" : "Car");

        setSyncHighlight({
          field: "vehicle_type",
          prev: prevLabel,
          next: nextLabel,
          timestamp: Date.now(),
        });

        setFormValues((v) => ({ ...v, vehicle_type: newVtype }));
        commitFieldDirectly("vehicle_type", newVtype);

        const currentCCStr = formValues["engine_cc"] || (workspace.fields["engine_cc"] as WorkspaceField | undefined)?.value;
        const isEVType = newVtype.startsWith("EV");
        const rawParsed = currentCCStr ? parseFloat(String(currentCCStr).replace(/[^0-9.]/g, "")) : (isEVType ? null : inferCCFromCarModel(formValues["car_model"] || (workspace.fields["car_model"] as WorkspaceField | undefined)?.value));
        if (rawParsed && rawParsed > 0) {
          if (isEVType) {
            const computedRT = computeMalaysianRoadTax(rawParsed, newVtype, "Individual");
            if (computedRT > 0) {
              const rtFormatted = computedRT.toFixed(2);
              setFormValues((values) => ({ ...values, roadtax: rtFormatted }));
              commitFieldDirectly("roadtax", rtFormatted);
            }
          } else if (rawParsed <= 7000) {
            const parsedCC = Math.round(rawParsed);
            const baseType = newVtype === "NonSaloonCar" ? "NonSaloonCar" : newVtype.toLowerCase().includes("motor") ? "Motorcycle" : (newVtype.toLowerCase().includes("lorry") || newVtype.toLowerCase().includes("other")) ? "Lorry" : "Car";
            const computedRT = computeMalaysianRoadTax(parsedCC, baseType, "Individual");
            if (computedRT > 0) {
              const rtFormatted = computedRT.toFixed(2);
              setFormValues((values) => ({ ...values, roadtax: rtFormatted }));
              commitFieldDirectly("roadtax", rtFormatted);
            }
          }
        }
      }
    }

    pinCatalog(workspace.pinned.company_id as string, productId);
  }

  // Auto-select canonical package when company is pinned but product is unselected
  const autoSelectedCompanyRef = useRef<string | null>(null);
  useEffect(() => {
    const compId = workspace?.pinned.company_id;
    if (!compId || !companyWorkspace || !productOptions.length || pinLoading) return;

    // If product is already selected and exists in valid options, do nothing
    if (workspace?.pinned.product_id && productOptions.some((p) => p.id === workspace.pinned.product_id)) {
      return;
    }

    // Avoid multiple auto-select triggers for the same company if already pinned
    if (autoSelectedCompanyRef.current === compId && workspace?.pinned.product_id) {
      return;
    }

    const pool = currentVehicleCategory === "Motorcycle"
      ? categorizedProducts.motorcycles
      : (currentVehicleCategory === "Lorry" ? categorizedProducts.lorries : categorizedProducts.cars);

    const candidates = pool.length > 0 ? pool : productOptions;
    if (!candidates.length) return;

    const canonical = candidates.find((p) =>
      /private car protector|auto365.*lite|sompo motor|private car secure|comprehensive private car|takaful mymotor|tune protect motor easy|commercial lorry.*own goods.*c permit|c permit|own goods|motorcycle policy \(private\)/i.test(p.name)
    ) || candidates.find((p) => /comprehensive/i.test(p.name)) || candidates[0];

    if (canonical && canonical.id !== workspace?.pinned.product_id) {
      autoSelectedCompanyRef.current = compId;
      pinCatalog(compId, canonical.id);
    }
  }, [
    workspace?.pinned.company_id,
    workspace?.pinned.product_id,
    companyWorkspace,
    productOptions,
    categorizedProducts,
    currentVehicleCategory,
    pinLoading,
  ]);

  // Pin a specific package tier (package-system insurers) by its package_id.
  async function pinPackageTier(packageId: string) {
    if (!workspace?.pinned.company_id) return;
    setPinLoading(true);
    onQueue({
      op: "select_package_tier",
      package_id: packageId,
    }, "package_tier");
    try {
      await save();
    } catch {
      // Best effort
    } finally {
      setPinLoading(false);
    }
  }

  function addConceptAsBenefit(
    concept: GlobalConcept,
    state: "current" | "available_addon" = "current",
    price?: { amount: number; currency: string } | null,
    coverageLimit?: string | null
  ) {
    const key = `concept:${concept.concept_key}:${crypto.randomUUID().slice(0, 8)}`;
    const costStatus = price ? "paid" : state === "current" ? "included" : "paid";
    const cleanLimit = coverageLimit && typeof coverageLimit === "string" && !coverageLimit.includes("[object") ? coverageLimit.trim() : "";
    const typedValue = cleanLimit
      ? { type: "custom", display_text: cleanLimit.startsWith("RM") ? cleanLimit : `RM ${cleanLimit}` }
      : { type: "custom", display_text: concept.label };
    const op = {
      op: "create_custom_benefit",
      selection_key: key,
      concept_id: concept.id,
      concept_key: concept.concept_key,
      label: concept.label,
      typed_value: typedValue,
      cost_status: costStatus,
      state,
      price: price || null,
    };
    onQueue(op, `benefits.${key}`);
    setRedoStack([]);
    setShowGlobalModal(false);
  }

  // Reset all benefits back to company defaults and detected extraction items (idempotent)
  function handleReset() {
    if (!workspace) return;
    const op = { op: "reset_benefits" };
    queueOperation(op, "benefits");
    setUndoStack((prev) => [...prev, { op, path: "benefits", desc: "Reset benefits" }]);
    setRedoStack([]);
    scheduleSave();
  }

  const handleUndo = useCallback(async () => {
    if (!undoStack.length) return;
    const last = undoStack[undoStack.length - 1];
    setUndoStack((prev) => prev.slice(0, -1));
    setRedoStack((prev) => [...prev, last]);
    if (last.revertOp) {
      queueOperation(last.revertOp, last.path);
    } else if (last.op.selection_id) {
      queueOperation({ op: "revert_benefit", selection_id: last.op.selection_id }, last.path);
    } else if (last.op.op === "create_custom_benefit" && (last.op as any).selection_key) {
      // Undo a custom benefit by removing it via its selection_key (not a UUID selection_id)
      queueOperation({ op: "benefit_update", selection_id: (last.op as any).selection_key, state: "removed" }, last.path);
    } else if (last.op.op === "select_catalog_offering" && last.op.offering_id) {
      queueOperation({ op: "select_catalog_offering", offering_id: last.op.offering_id, state: "removed", cost_status: "included" }, last.path);
    } else {
      queueOperation({ op: "reset_benefits" }, "benefits");
    }
    try {
      scheduleSave();
      setToastMessage("Undid benefit change.");
    } catch {}
  }, [undoStack, queueOperation, scheduleSave]);

  const handleRedo = useCallback(async () => {
    if (!redoStack.length) return;
    const next = redoStack[redoStack.length - 1];
    setRedoStack((prev) => prev.slice(0, -1));
    setUndoStack((prev) => [...prev, next]);
    queueOperation(next.op, next.path);
    try {
      scheduleSave();
      setToastMessage("Redid benefit change.");
    } catch {}
  }, [redoStack, queueOperation, scheduleSave]);

  function addCustomBenefit(targetState: "current" | "available_addon" = "current") {
    const label = customLabel.trim();
    if (!label) return;
    const isAddon = targetState === "available_addon";
    const key = `custom:${crypto.randomUUID()}`;
    const priceText = customPrice.trim();
    const price = priceText
      ? { amount: priceText.replace(/,/g, ""), currency: "MYR" }
      : undefined;
    const costStatus = price ? "paid" : isAddon ? "paid" : "included";
    const op = {
      op: "create_custom_benefit",
      selection_key: key,
      label,
      typed_value: customValue.trim() ? { type: "custom", display_text: customValue.trim() } : { type: "custom", display_text: label },
      cost_status: costStatus,
      state: targetState,
      ...(price ? { price } : {}),
    };
    queueOperation(op, `benefits.${key}`);
    setUndoStack((prev) => [...prev, { op, path: `benefits.${key}`, desc: `Added ${label}` }]);
    setRedoStack([]);
    setCustomLabel("");
    setCustomValue("");
    setCustomPrice("");
    scheduleSave();
  }

  // ── Benefit Pack (bundle plan) actions ─────────────────────────────────
  function addPack(pack: { package_id: string; name: string }, planId: string) {
    if (!planId) return;
    queueOperation({
      op: "select_package_plan",
      package_id: pack.package_id,
      plan_id: planId,
      cost_status: "paid",
    }, `benefits.plan.${planId}`);
    scheduleSave();
  }

  function removePack(planId: string) {
    queueOperation({ op: "remove_package_plan", plan_id: planId }, `benefits.plan.${planId}`);
    scheduleSave();
  }

  async function saveAndCheckLearning() {
    setActionError(null);
    try {
      await save();
      if (!workspace) return;
      for (const fieldName of LEARNABLE.keys()) {
        const stored = (workspace.fields[fieldName] as WorkspaceField | undefined)?.value;
        const value = String(stored ?? "").trim();
        if (!value || promptedRef.current.has(`${fieldName}:${value}`)) continue;
        promptedRef.current.add(`${fieldName}:${value}`);
        try {
          const known = await api<{ known: boolean }>(`/business/dictionaries/contains?field=${encodeURIComponent(LEARNABLE.get(fieldName) || fieldName)}&value=${encodeURIComponent(value)}`);
          if (!known.known) {
            setLearnPrompt({ field: LEARNABLE.get(fieldName) || fieldName, value });
            break;
          }
        } catch {
          // Best effort
        }
      }
    } catch (error) {
      setActionError(apiErrorMessage(error));
    }
  }

  async function learnValue() {
    if (!learnPrompt) return;
    try {
      await api(`/business/dictionaries/learn`, {
        method: "POST",
        body: JSON.stringify({ field: learnPrompt.field, value: learnPrompt.value }),
      });
    } catch {
      // Best effort
    }
    setLearnPrompt(null);
  }

  async function generateCanvasBlob(): Promise<Blob | null> {
    const live = document.getElementById("rl-live-canvas-inner");
    if (!live || !previewTemplate) return null;

    const width = previewTemplate.config.canvas?.width || 794;
    const height = canvasH;

    return await toBlob(live, {
      cacheBust: false,
      backgroundColor: "#ffffff",
      width,
      height,
      pixelRatio: 4,
      skipFonts: false,
      style: {
        transform: "none",
        transformOrigin: "top left",
        width: `${width}px`,
        height: `${height}px`,
        margin: "0",
        position: "static",
      },
    });
  }

  function triggerDownload(url: string, filename: string) {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  async function flushActiveInput() {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
      // Give React a tiny tick to process the onBlur before continuing
      await new Promise(resolve => setTimeout(resolve, 50));
    }
  }

  async function executeCopyPng() {
    await flushActiveInput();
    if (mutation.dirty) {
      try {
        await save();
      } catch (err) {
        console.warn("Could not save workspace before copying PNG, proceeding with live canvas:", err);
      }
    }
    setCopyingPng(true);
    setActionError(null);
    try {
      const blob = await generateCanvasBlob();
      if (!blob) throw new Error("Could not capture quotation template canvas.");

      if (typeof ClipboardItem !== "undefined" && navigator.clipboard && typeof navigator.clipboard.write === "function") {
        await navigator.clipboard.write([
          new ClipboardItem({ "image/png": blob }),
        ]);
        setCopiedPng(true);
        setToastMessage("High-definition quotation PNG copied to clipboard!");
        setTimeout(() => setCopiedPng(false), 2500);
        return;
      }

      const url = URL.createObjectURL(blob);
      triggerDownload(url, `quotation_${formValues.vehicle_no || id}.png`);
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      setToastMessage("Quotation PNG downloaded (clipboard was restricted by browser).");
    } catch (err: unknown) {
      console.error("[handleCopyPng error]", err);
      setActionError("Could not export quotation PNG: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setCopyingPng(false);
    }
  }

  async function executeDownloadPng() {
    await flushActiveInput();
    if (mutation.dirty) {
      try {
        await save();
      } catch (err) {
        console.warn("Could not save workspace before downloading PNG, proceeding with live canvas:", err);
      }
    }
    setDownloadingPng(true);
    setActionError(null);
    try {
      const blob = await generateCanvasBlob();
      if (!blob) throw new Error("Could not generate quotation image blob");
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      triggerDownload(url, `quotation_${formValues.vehicle_no || id}.png`);
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      setToastMessage("High-definition quotation PNG opened in new tab and downloaded!");
    } catch (err: unknown) {
      console.error("[handleDownloadPng error]", err);
      setActionError("Could not generate PNG for download: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setDownloadingPng(false);
    }
  }

  const handleCopyExtractedInfo = useCallback(() => {
    const lines: string[] = [];

    // 1. Core Policy & Vehicle Fields
    for (const field of FORM_FIELDS) {
      const val = field.kind === "total"
        ? (previewFields[field.name] || formValues[field.name] || "")
        : (formValues[field.name] ?? "");
      lines.push(`${field.label}: ${val || "—"}`);
    }

    // 2. Custom Fields (if any)
    const customEntries = Object.entries(workspace?.fields || {}).filter(
      ([k]) => !FORM_FIELDS.some((f) => f.name === k) && !k.startsWith("_")
    );
    if (customEntries.length > 0) {
      lines.push("");
      lines.push("--- Custom Fields ---");
      for (const [k, v] of customEntries) {
        const valStr = typeof v === "object" && v !== null && "value" in v ? String((v as any).value || "") : String(v || "");
        lines.push(`${k}: ${valStr || "—"}`);
      }
    }

    // 3. Extra Benefits Detected
    const extras = workspace?.extracted_benefits_section?.extras || [];
    if (extras.length > 0) {
      lines.push("");
      lines.push("--- Extra Benefits Detected ---");
      for (const extra of extras) {
        const parts: string[] = [extra.label];
        if (extra.coverage_limit) parts.push(`Limit: RM ${extra.coverage_limit}`);
        if (extra.cost) parts.push(`Cost: RM ${extra.cost}`);
        else parts.push("Cost: Included");
        if (extra.is_applied) parts.push("(Included in Grid)");
        lines.push(`- ${parts.join(" | ")}`);
      }
    }

    const textToCopy = lines.join("\n");
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(textToCopy).then(() => {
        setCopiedInfo(true);
        setToastMessage("All extracted information copied to clipboard!");
        setTimeout(() => setCopiedInfo(false), 2000);
      }).catch(() => {
        const textarea = document.createElement("textarea");
        textarea.value = textToCopy;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
        setCopiedInfo(true);
        setToastMessage("All extracted information copied to clipboard!");
        setTimeout(() => setCopiedInfo(false), 2000);
      });
    }
  }, [formValues, previewFields, workspace]);

  async function executeDownloadPdf() {
    await flushActiveInput();
    if (!workspace) return;
    setPdfLoading(true);
    setActionError(null);

    // Auto-save any dirty changes
    if (mutation.dirty) {
      try {
        await save();
      } catch (err) {
        console.warn("Could not save workspace before exporting PDF, proceeding with live canvas:", err);
      }
    }

    try {
      const live = document.getElementById("rl-live-canvas-inner");
      if (!live) throw new Error("Could not capture quotation template canvas.");

      const width = previewTemplate?.config.canvas?.width || 794;
      const height = canvasH || 1123;

      // Capture 4K ultra-high-definition canvas at 4x pixel ratio for maximum print & display clarity
      const imgData = await toPng(live, {
        cacheBust: false,
        backgroundColor: "#ffffff",
        pixelRatio: 4,
        width,
        height,
        style: {
          transform: "none",
          transformOrigin: "top left",
          width: `${width}px`,
          height: `${height}px`,
          margin: "0",
          position: "static",
        },
      });

      // Create PDF scaled to match the exact canvas layout
      const pdf = new jsPDF({
        orientation: "portrait",
        unit: "pt",
        format: [width * 0.75, height * 0.75],
      });

      const pdfW = pdf.internal.pageSize.getWidth();
      const pdfH = pdf.internal.pageSize.getHeight();

      pdf.addImage(imgData, "PNG", 0, 0, pdfW, pdfH, undefined, "SLOW");

      const blob = pdf.output("blob");
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      triggerDownload(url, `quotation_${formValues.vehicle_no || id}.pdf`);
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      setToastMessage("Official quotation PDF generated, opened in new tab, and downloaded!");

      // Asynchronously trigger server version archiving in the background
      api(`/sessions/${id}/versions`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ draft_revision: workspace.revision }),
      }).catch((e) => console.log("Background version archived:", e));

    } catch (err: unknown) {
      console.error("[handleDownloadPdf error]", err);
      setActionError("Could not generate PDF for download: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setPdfLoading(false);
    }
  }

  async function confirmAndExecuteExport(sentToClient: boolean) {
    const action = pendingExportAction;
    setPendingExportAction(null);
    if (!action) return;

    // Log quotation activity to backend insights ledger (skipped for test uploads)
    if (!workspace?.is_test) {
      api(`/insights/sessions/${id}/activity`, {
        method: "POST",
        body: JSON.stringify({
          action_type: action === "download_pdf" ? "pdf_export" : "png_export",
          sent_to_client: sentToClient,
          summary: sentToClient
            ? `Sent quotation to client (${action === "download_pdf" ? "PDF" : "PNG"})`
            : `Internal save / export (${action === "download_pdf" ? "PDF" : "PNG"})`,
          version_number: (workspace?.versions?.length || 0) + 1,
        }),
      }).catch((err) => console.warn("Could not log export activity:", err));
    }

    if (action === "copy_png") {
      await executeCopyPng();
    } else if (action === "download_png") {
      await executeDownloadPng();
    } else if (action === "download_pdf") {
      await executeDownloadPdf();
    }
  }

  function handleCopyPng() {
    if (ownershipConflict?.has_conflict && !ownershipConflict?.resolved) {
      setConflictModalOpen(true);
      setToastMessage("Action Required: Please resolve the vehicle ownership conflict before exporting.");
      return;
    }
    setPendingExportAction("copy_png");
  }

  function handleDownloadPng() {
    if (ownershipConflict?.has_conflict && !ownershipConflict?.resolved) {
      setConflictModalOpen(true);
      setToastMessage("Action Required: Please resolve the vehicle ownership conflict before exporting.");
      return;
    }
    setPendingExportAction("download_png");
  }

  function handleDownloadPdf() {
    if (ownershipConflict?.has_conflict && !ownershipConflict?.resolved) {
      setConflictModalOpen(true);
      setToastMessage("Action Required: Please resolve the vehicle ownership conflict before exporting PDF.");
      return;
    }
    setPendingExportAction("download_pdf");
  }

  if (loading) return <PageLoading />;
  if (loadError || !workspace) {
    return (
      <Card className="grid gap-3 p-6" role="alert">
        <h1 className="text-xl font-bold text-[var(--rl-text-strong)]">Could not load quotation</h1>
        <p className="text-sm text-[var(--rl-text)]">{loadError || "The quotation workspace is unavailable."}</p>
        <Button className="w-fit" onClick={() => reload().catch(() => undefined)}>Retry</Button>
      </Card>
    );
  }



  return (
    <>
      <ReviewHeader
        workspace={workspace}
        companyName={companyName}
        mutation={mutation}
        formValues={formValues}
        pdfOpen={pdfOpen}
        setPdfOpen={setPdfOpen}
        formCollapsed={formCollapsed}
        setFormCollapsed={setFormCollapsed}
        previewColCollapsed={previewColCollapsed}
        setPreviewColCollapsed={setPreviewColCollapsed}
        saveAndCheckLearning={saveAndCheckLearning}
        copiedPng={copiedPng}
        copyingPng={copyingPng}
        handleCopyPng={handleCopyPng}
        downloadingPng={downloadingPng}
        handleDownloadPng={handleDownloadPng}
        ownershipConflict={ownershipConflict}
        handleDownloadPdf={handleDownloadPdf}
        pdfLoading={pdfLoading}
      />
      <section className="grid gap-4 w-full max-w-[1800px] mx-auto pb-12 pt-6 px-4 sm:px-6">

      {actionError || mutation.saveError ? (
        <div role="alert" className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] p-3 text-sm font-semibold text-[var(--rl-red)]">
          {actionError || mutation.saveError}
        </div>
      ) : null}

      <ReviewBanners
        ownershipConflict={ownershipConflict}
        setConflictModalOpen={setConflictModalOpen}
        formValues={formValues}
        workspace={workspace}
        learnPrompt={learnPrompt}
        learnValue={learnValue}
        setLearnPrompt={setLearnPrompt}
      />

      {/* 3-Column Resizable Workspace with Draggable Flexbox Sliders */}
      <div
        ref={containerRef}
        className={`flex flex-col lg:flex-row items-stretch min-h-[580px] w-full gap-0 relative ${isDragging ? "select-none" : ""}`}
      >
        {/* Column 1 (Optional): Source Quotation PDF */}
        {pdfOpen ? (
          <>
            <div
              style={{ width: isDesktop ? pdfWidth : "100%" }}
              className="w-full lg:w-auto min-w-0 flex-shrink-0 relative overflow-hidden pr-0 lg:pr-1"
            >
              <div className="relative min-w-0 h-full">
                <Card className="sticky top-[140px] h-[calc(100vh-180px)] p-2">
                  <div className="flex items-center justify-between px-1 pb-1.5 border-b border-[var(--rl-border)] mb-1">
                    <span className="text-xs font-bold text-[var(--rl-text-strong)]">Source Quotation PDF</span>
                    <div className="flex items-center gap-1">
                      <Button
                        size="sm"
                        variant="secondary"
                        className="h-6 px-2 text-[11px] gap-1"
                        onClick={() => {
                          const srcUrl = fileUrl(`/uploaded-files/${workspace.uploaded_file_id}/content`);
                          window.open(srcUrl, "_blank");
                          triggerDownload(srcUrl, `source_quotation_${formValues.vehicle_no || id}.pdf`);
                        }}
                        title="Open source PDF in new tab and download"
                      >
                        <DownloadSimple size={12} weight="bold" />
                        Download Source PDF
                      </Button>
                      <button
                        type="button"
                        onClick={() => setPdfOpen(false)}
                        className="hidden lg:flex items-center justify-center p-1 text-[11px] font-semibold text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded border border-transparent hover:border-gray-200 transition-all cursor-pointer ml-0.5"
                        title="Close PDF Panel"
                      >
                        <X size={14} weight="bold" />
                      </button>
                    </div>
                  </div>
                  <iframe
                    title="Source quotation PDF"
                    src={fileUrl(`/uploaded-files/${workspace.uploaded_file_id}/content`)}
                    className={`h-[calc(100%-32px)] w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white ${isDragging ? "pointer-events-none" : ""}`}
                  />
                </Card>
              </div>
            </div>
            {/* Draggable Slider 1 (between PDF and Form) */}
            {pdfOpen && !formCollapsed ? (
              <div
                onPointerDown={handlePointerDown("pdf")}
                role="separator"
                aria-orientation="vertical"
                className="group w-3.5 -mx-1 flex items-center justify-center cursor-col-resize self-stretch z-10 shrink-0 hidden lg:flex"
                title="Drag to resize PDF and Form panels"
              >
                <div className={`w-1 h-full rounded-full transition-colors ${isDragging === "pdf" ? "bg-[var(--rl-red)]" : "bg-[var(--rl-border)] group-hover:bg-[var(--rl-red)]"}`} />
              </div>
            ) : null}

            {/* Draggable Slider between PDF and Preview when Form is collapsed */}
            {pdfOpen && formCollapsed && !previewColCollapsed ? (
              <div
                onPointerDown={handlePointerDown("pdf-preview")}
                role="separator"
                aria-orientation="vertical"
                className="group w-3.5 -mx-1 flex items-center justify-center cursor-col-resize self-stretch z-10 shrink-0 hidden lg:flex"
                title="Drag to resize PDF and Live Preview panels"
              >
                <div className={`w-1 h-full rounded-full transition-colors ${isDragging === "pdf-preview" ? "bg-[var(--rl-red)]" : "bg-[var(--rl-border)] group-hover:bg-[var(--rl-red)]"}`} />
              </div>
            ) : null}
          </>
        ) : null}

        {/* Column 2: Master Template + Extracted Values */}
        <div
          style={{
            width: isDesktop ? formWidth : "100%",
            opacity: isDesktop && formCollapsed ? 0 : 1,
            pointerEvents: isDesktop && formCollapsed ? "none" : "auto",
            transition: isDragging ? "none" : "width 400ms cubic-bezier(0.4, 0, 0.2, 1), opacity 300ms ease-in-out, padding 400ms ease-in-out",
          }}
          className={`w-full lg:w-auto min-w-0 flex-shrink-0 ${formCollapsed ? "overflow-hidden px-0" : "px-0 lg:px-2"}`}
        >

          <section aria-label="Template configuration and extracted values" className="grid grid-cols-1 gap-4 content-start">
            {/* Hierarchy & Quotation Context Overview Bar */}
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-2.5 text-xs shadow-xs">
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-1.5 font-semibold text-[var(--rl-text-strong)]">
                  <span className="text-[var(--rl-text-muted)] text-[11px]">Insurer:</span>
                  <span className="rounded bg-gray-100 px-2 py-0.5 font-bold text-gray-900 border border-gray-200">
                    {workspace.hierarchy?.company_name || companyName || "Etiqa"}
                  </span>
                </div>
                <div className="h-3 w-px bg-[var(--rl-border)]" />
                <div className="flex items-center gap-1.5 font-semibold text-[var(--rl-text-strong)]">
                  <span className="text-[var(--rl-text-muted)] text-[11px]">Vehicle:</span>
                  <span className="rounded bg-blue-50 px-2 py-0.5 font-bold text-blue-700 border border-blue-200">
                    {workspace.hierarchy?.vehicle_category || (formValues.vehicle_type || "Private Car")}
                  </span>
                </div>
                <div className="h-3 w-px bg-[var(--rl-border)]" />
                <div className="flex items-center gap-1.5 font-semibold text-[var(--rl-text-strong)]">
                  <span className="text-[var(--rl-text-muted)] text-[11px]">Usage:</span>
                  <span className="rounded bg-emerald-50 px-2 py-0.5 font-bold text-emerald-700 border border-emerald-200">
                    {workspace.hierarchy?.segment || "Private"}
                  </span>
                </div>
                <div className="h-3 w-px bg-[var(--rl-border)]" />
                <div className="flex items-center gap-1.5 font-semibold text-[var(--rl-text-strong)]">
                  <span className="text-[var(--rl-text-muted)] text-[11px]">Coverage:</span>
                  <span className="rounded bg-purple-50 px-2 py-0.5 font-bold text-purple-700 border border-purple-200">
                    {workspace.hierarchy?.coverage_type || (formValues.coverage_type || "Comprehensive")}
                  </span>
                </div>
                <div className="h-3 w-px bg-[var(--rl-border)]" />
                <div className="flex items-center gap-1.5 font-semibold text-[var(--rl-text-strong)] min-w-0">
                  <span className="text-[var(--rl-text-muted)] text-[11px]">Model:</span>
                  <strong className="truncate font-bold text-gray-900">{formValues.car_model || workspace.hierarchy?.car_model || "—"}</strong>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setFormCollapsed(true)}
                className="hidden lg:flex items-center justify-center p-1 ml-auto text-[11px] font-semibold text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded border border-transparent hover:border-gray-200 transition-all cursor-pointer"
                title="Close Form Panel"
              >
                <X size={14} weight="bold" />
              </button>
            </div>

            {/* Row 1: Master Template Selection */}
            <Card className="rl-tour-template grid gap-3 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Master template</h2>
                  <p className="text-xs text-[var(--rl-text-muted)]">Pins the exact published revision used for rendering.</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="default">Published</Badge>
                  <button
                    type="button"
                    onClick={() => setTemplateCollapsed((v) => !v)}
                    className="flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors"
                    title={templateCollapsed ? "Expand Master Template" : "Collapse Master Template"}
                  >
                    {templateCollapsed ? <CaretDown size={14} weight="bold" /> : <CaretUp size={14} weight="bold" />}
                    <span>{templateCollapsed ? "Expand" : "Collapse"}</span>
                  </button>
                </div>
              </div>

              {templateCollapsed ? (
                <div className="flex flex-wrap items-center justify-between text-xs text-[var(--rl-text-muted)] pt-2 border-t border-[var(--rl-border)]">
                  <span>Template: <strong className="text-[var(--rl-text-strong)] font-semibold">{publishedTemplates.find((t) => t.template_revision_id === workspace.pinned.template_revision_id)?.name || "Master Template"}</strong></span>
                  <span>Insurer: <strong className="text-[var(--rl-text-strong)] font-semibold">{companyName || "Standard Motor"}</strong></span>
                </div>
              ) : (
                <>
                  <label className="grid gap-1.5 text-xs font-semibold text-[var(--rl-text-strong)]">
                    Published template revision
                    <Select
                      value={workspace.pinned.template_revision_id || (publishedTemplates[0]?.template_revision_id ?? "")}
                      disabled={templatesLoading || !publishedTemplates.length}
                      onChange={(event) => selectTemplateDirectly(event.target.value)}
                    >
                      {publishedTemplates.map((option) => (
                        <option key={option.template_revision_id} value={option.template_revision_id}>
                          {option.name} {option.is_default ? "★ (Default)" : ""} · r{option.revision_number} · {option.page_profile.name}
                        </option>
                      ))}
                    </Select>
                  </label>

                  {templateError ? <p role="alert" className="text-xs font-semibold text-[var(--rl-red)]">{templateError}</p> : null}

                  {templateImpact ? (
                    <div className="grid gap-2 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50 p-3">
                      <p className="text-sm font-bold text-[var(--rl-text-strong)]">Change to {templateImpact.target.name} revision {templateImpact.target.revision_number}?</p>
                      {templateImpact.messages.map((message) => <p key={message} className="text-xs font-semibold text-amber-800">{message}</p>)}
                      <div className="flex flex-wrap gap-2 pt-1">
                        <Button size="sm" onClick={confirmTemplateSelection}>Confirm template change</Button>
                        <Button variant="secondary" size="sm" onClick={() => setTemplateImpact(null)}>Cancel</Button>
                      </div>
                    </div>
                  ) : null}

                  {/* Insurer / Product Context Selectors */}
                  <div className="grid grid-cols-2 gap-2 pt-1 border-t border-[var(--rl-border)]">
                    <label className="grid gap-1 text-xs font-semibold text-[var(--rl-text-strong)]">
                      Insurer catalog
                      <Select
                        value={workspace.pinned.company_id || ""}
                        disabled={pinLoading || !companies.length}
                        onChange={(event) => pinCatalog(event.target.value)}
                      >
                        <option value="">Choose insurer</option>
                        {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
                      </Select>
                    </label>

                    <label className="grid gap-1 text-xs font-semibold text-[var(--rl-text-strong)]">
                      <span className="flex items-center justify-between">
                        <span>Product / Package</span>
                        {syncHighlight && syncHighlight.field === "product_package" && Date.now() - syncHighlight.timestamp < 6000 ? (
                          <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-50 border border-emerald-300 px-2 py-0.5 text-[11px] font-semibold text-emerald-800 shadow-xs animate-pulse">
                            <span className="text-[10px] text-emerald-600 font-bold uppercase tracking-wider">Auto-selected</span>
                            <span className="line-through text-slate-400 font-normal truncate max-w-[110px]" title={syncHighlight.prev}>{syncHighlight.prev}</span>
                            <span className="text-emerald-500 font-bold">→</span>
                            <span className="bg-emerald-100 text-emerald-900 px-1 rounded font-bold truncate max-w-[140px]" title={syncHighlight.next}>{syncHighlight.next}</span>
                          </span>
                        ) : null}
                      </span>
                      <Select
                        value={workspace.pinned.product_id || ""}
                        disabled={pinLoading || !productOptions.length}
                        onChange={(event) => handlePackageSelect(event.target.value)}
                        className={`transition-all duration-300 ${
                          syncHighlight && syncHighlight.field === "product_package" && Date.now() - syncHighlight.timestamp < 6000
                            ? "border-emerald-500 ring-2 ring-emerald-300 bg-emerald-50/20"
                            : ""
                        }`}
                      >
                        <option value="">{productOptions.length ? "Choose package" : "Standard Motor"}</option>
                        {categorizedProducts.cars.length > 0 ? (
                          <optgroup label="🚗 Cars (Saloon / Sedan / SUV / MPV / Company)">
                            {categorizedProducts.cars.map((product) => (
                              <option key={product.id} value={product.id}>
                                {formatProductLabel(product.name || "")}
                              </option>
                            ))}
                          </optgroup>
                        ) : null}
                        {categorizedProducts.motorcycles.length > 0 ? (
                          <optgroup label="🏍️ Motorcycles / Bikes">
                            {categorizedProducts.motorcycles.map((product) => (
                              <option key={product.id} value={product.id}>
                                {formatProductLabel(product.name || "")}
                              </option>
                            ))}
                          </optgroup>
                        ) : null}
                        {categorizedProducts.lorries.length > 0 ? (
                          <optgroup label="🚛 Commercial Vehicles / Lorries">
                            {categorizedProducts.lorries.map((product) => (
                              <option key={product.id} value={product.id}>
                                {formatProductLabel(product.name || "")}
                              </option>
                            ))}
                          </optgroup>
                        ) : null}
                      </Select>
                    </label>
                  </div>

                  {/* Package Tier Ladder (package-system insurers) */}
                  {workspace.package_tiers.length > 1 ? (
                    <div className="grid gap-2 pt-1 border-t border-[var(--rl-border)]">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                          Package tier
                        </span>
                        <span className="text-[10px] text-[var(--rl-text-muted)]">
                          {workspace.package_tiers.length} tiers · click to switch
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                        {workspace.package_tiers.map((tier, idx) => {
                          const active = tier.is_current;
                          const isTop = idx === workspace.package_tiers.length - 1;
                          return (
                            <button
                              key={tier.package_id}
                              type="button"
                              disabled={pinLoading}
                              onClick={() => pinPackageTier(tier.package_id)}
                              className={`flex flex-col justify-between rounded-[var(--rl-radius-sm)] border p-2.5 text-left transition-all ${active
                                  ? "border-[var(--rl-black)] bg-[var(--rl-bg)] shadow-sm ring-1 ring-[var(--rl-black)]"
                                  : "border-[var(--rl-border)] bg-white hover:border-[var(--rl-text-muted)]"
                                }`}
                            >
                              <div className="flex items-center justify-between gap-1">
                                <span className="rounded-[4px] bg-[var(--rl-surface)] border border-[var(--rl-border)] px-1.5 py-0.5 text-[9px] font-bold text-[var(--rl-text-muted)]">
                                  Tier {idx + 1} {isTop ? "· Top" : ""}
                                </span>
                                {active ? (
                                  <span className="flex items-center gap-0.5 text-[10px] font-bold text-[var(--rl-black)]">
                                    <Check size={11} weight="bold" /> Active
                                  </span>
                                ) : null}
                              </div>
                              <span className="mt-1.5 text-[11px] font-bold leading-tight text-[var(--rl-text-strong)]">
                                {tier.name}
                              </span>
                              <span className="mt-1 text-[10px] text-[var(--rl-text-muted)]">
                                {tier.defaults_count} defaults · {tier.addons_count} add-ons
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}

                  {/* Benefits Card Template Switcher */}
                  <div className="grid gap-2 pt-2 border-t border-[var(--rl-border)]">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-[var(--rl-text-strong)] flex items-center gap-1.5">
                        <Sparkle size={13} className="text-[var(--rl-red)]" weight="fill" />
                        Benefits Card Template
                      </label>
                      <span className="text-[11px] text-[var(--rl-text-muted)] font-medium">
                        {allBenefitPresets.find((p) => p.id === selectedBenefitPreset)?.name || "Masonry Flow"}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                      {allBenefitPresets.map((preset) => {
                        const isSelected = selectedBenefitPreset === preset.id;
                        return (
                          <button
                            key={preset.id}
                            type="button"
                            onClick={() => handleSelectBenefitPreset(preset.id)}
                            title={preset.description}
                            className={`flex flex-col items-start rounded-[var(--rl-radius-sm)] border p-2 text-left transition-all ${
                              isSelected
                                ? "border-[var(--rl-red)] bg-red-50/70 shadow-xs ring-1 ring-[var(--rl-red)]/30"
                                : "border-[var(--rl-border)] bg-white hover:border-gray-300 hover:bg-gray-50/80"
                            }`}
                          >
                            <span className={`text-[11px] font-bold leading-tight ${isSelected ? "text-[var(--rl-red)]" : "text-[var(--rl-text-strong)]"}`}>
                              {preset.shortName}
                            </span>
                            <span className="text-[9.5px] text-[var(--rl-text-muted)] mt-0.5 leading-snug line-clamp-2">
                              {preset.description}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                </>
              )}
            </Card>

            {/* Row 2: Extracted Policy & Vehicle Values */}
            <PolicyFieldsCard
              workspace={workspace}
              formValues={formValues}
              setFormValues={setFormValues}
              previousValuesRef={previousValuesRef}
              extractedValuesCollapsed={extractedValuesCollapsed}
              setExtractedValuesCollapsed={setExtractedValuesCollapsed}
              copiedInfo={copiedInfo}
              handleCopyExtractedInfo={handleCopyExtractedInfo}
              geminiExtracting={geminiExtracting}
              triggerGeminiExtraction={triggerGeminiExtraction}
              geminiQuotaInfo={geminiQuotaInfo}
              previewFields={previewFields}
              companies={companies}
              roundTotal={roundTotal}
              toggleRoundTotal={toggleRoundTotal}
              isFieldModified={isFieldModified}
              getDetectedValue={getDetectedValue}
              handleResetField={handleResetField}
              commitField={commitField}
              commitFieldDirectly={commitFieldDirectly}
              syncHighlight={syncHighlight}
              setSyncHighlight={setSyncHighlight}
              companyWorkspace={companyWorkspace}
              categorizedProducts={categorizedProducts}
              pinCatalog={pinCatalog}
            />

            {/* Card 3: Extracted Benefits, Extras & Packages */}
            <ExtractedBenefitsCard
              workspace={workspace}
              extractedBenefitsCollapsed={extractedBenefitsCollapsed}
              setExtractedBenefitsCollapsed={setExtractedBenefitsCollapsed}
              pinLoading={pinLoading}
              pinPackageTier={pinPackageTier}
              globalConcepts={globalConcepts}
              addConceptAsBenefit={addConceptAsBenefit}
            />
          </section>
        </div>

        {/* Draggable Slider 2 (between Form and Live Preview) */}
        {!formCollapsed && !previewColCollapsed ? (
          <div
            onPointerDown={handlePointerDown("main")}
            role="separator"
            aria-orientation="vertical"
            className="group w-3.5 -mx-1 flex items-center justify-center cursor-col-resize self-stretch z-10 shrink-0 hidden lg:flex"
            title="Drag to resize Form and Live Preview panels"
          >
            <div className={`w-1 h-full rounded-full transition-colors ${isDragging === "main" ? "bg-[var(--rl-red)]" : "bg-[var(--rl-border)] group-hover:bg-[var(--rl-red)]"}`} />
          </div>
        ) : null}

        {/* Column 3: Live Quotation Preview + Insurer Benefits */}
        <div
          style={{
            width: isDesktop ? previewWidth : "100%",
            opacity: isDesktop && previewColCollapsed ? 0 : 1,
            pointerEvents: isDesktop && previewColCollapsed ? "none" : "auto",
            transition: isDragging ? "none" : "width 400ms cubic-bezier(0.4, 0, 0.2, 1), opacity 300ms ease-in-out, padding 400ms ease-in-out",
          }}
          className={`w-full lg:w-auto min-w-0 flex-1 ${previewColCollapsed ? "overflow-hidden px-0" : "pl-0 lg:pl-2"}`}
        >

          <section aria-label="Live preview and benefits manager" className="grid grid-cols-1 gap-4 content-start">
            {/* Row 1: Real-time Live Preview Canvas */}
            <Card className="rl-tour-preview grid gap-2.5 p-3.5 overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Live Quotation Preview</h2>
                  <span className="flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    Real-time
                  </span>
                  <button
                    type="button"
                    onClick={() => setPreviewZoom(0.48)}
                    className="hidden sm:inline-flex items-center gap-1 text-[10px] font-mono text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] bg-gray-100 hover:bg-gray-200 px-1.5 py-0.5 rounded border border-gray-200 cursor-pointer transition-colors"
                    title="Click to reset zoom (Default 48%). Or hold Ctrl and scroll mouse wheel inside canvas to zoom in/out"
                  >
                    <span>{Math.round(previewZoom * 100)}%</span>
                    <ArrowCounterClockwise size={10} className="text-gray-400" />
                  </button>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {!previewCollapsed ? (
                    <>
                      <div className="flex items-center gap-1 bg-gray-100/90 rounded px-1.5 py-0.5 border border-gray-200 text-[10px]">
                        <span className="font-bold text-[var(--rl-text-muted)] text-[9px] uppercase tracking-wider">Zoom</span>
                        <button
                          type="button"
                          onClick={() => setPreviewZoom((z) => Math.max(0.25, Number((z - 0.1).toFixed(2))))}
                          className="rounded p-0.5 text-[var(--rl-text-muted)] hover:bg-gray-200 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
                          title="Zoom Out (or Ctrl + Wheel Down)"
                        >
                          <MagnifyingGlassMinus size={13} weight="bold" />
                        </button>
                        <input
                          type="range"
                          min="0.25"
                          max="2.5"
                          step="0.05"
                          value={previewZoom}
                          onChange={(e) => setPreviewZoom(parseFloat(e.target.value))}
                          className="w-16 h-1 cursor-pointer accent-[var(--rl-red)]"
                          title="Zoom slider (25% - 250%)"
                        />
                        <button
                          type="button"
                          onClick={() => setPreviewZoom((z) => Math.min(2.5, Number((z + 0.1).toFixed(2))))}
                          className="rounded p-0.5 text-[var(--rl-text-muted)] hover:bg-gray-200 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
                          title="Zoom In (or Ctrl + Wheel Up)"
                        >
                          <MagnifyingGlassPlus size={13} weight="bold" />
                        </button>
                      </div>
                      <div className="flex items-center gap-1 bg-gray-100/90 rounded px-1.5 py-0.5 border border-gray-200 text-[10px]">
                        <span className="font-bold text-[var(--rl-text-muted)]">Style:</span>
                        <select
                          value={selectedBenefitPreset}
                          onChange={(e) => handleSelectBenefitPreset(e.target.value)}
                          className="bg-transparent font-semibold text-[var(--rl-text-strong)] cursor-pointer outline-hidden text-[10px]"
                        >
                          {allBenefitPresets.map((p) => (
                            <option key={p.id} value={p.id}>{p.shortName}</option>
                          ))}
                        </select>
                      </div>
                      <button
                        type="button"
                        onClick={() => setPreviewExpanded((v) => !v)}
                        className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors border border-gray-200 shadow-2xs cursor-pointer"
                        title={previewExpanded ? "Compress live preview" : "Expand live preview"}
                      >
                        {previewExpanded ? <ArrowsInSimple size={13} weight="bold" /> : <ArrowsOutSimple size={13} weight="bold" />}
                        <span>{previewExpanded ? "Compress" : "Expand"}</span>
                      </button>
                    </>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => setPreviewCollapsed((v) => !v)}
                    className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors border border-gray-200 shadow-2xs cursor-pointer"
                    title={previewCollapsed ? "Expand live preview canvas" : "Collapse live preview canvas"}
                  >
                    {previewCollapsed ? <CaretDown size={13} weight="bold" /> : <CaretUp size={13} weight="bold" />}
                    <span>{previewCollapsed ? "Expand" : "Collapse"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setPreviewColCollapsed(true)}
                    className="hidden lg:flex items-center justify-center p-1 text-[11px] font-semibold text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded border border-transparent hover:border-gray-200 transition-all cursor-pointer ml-1"
                    title="Close Preview Panel"
                  >
                    <X size={14} weight="bold" />
                  </button>
                </div>
              </div>

              {previewCollapsed ? (
                <div className="flex items-center justify-center p-3.5 text-xs text-[var(--rl-text-muted)] italic bg-gray-50/70 rounded">
                  Live quotation preview canvas is collapsed. Click Expand to preview document.
                </div>
              ) : (
                /* Canvas Render Container */
                <div
                  ref={previewScrollRef}
                  className={`relative ${previewExpanded ? "h-[680px]" : "h-[450px]"} w-full overflow-auto rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-gray-50/80 p-4 transition-all duration-200`}
                >
                  {previewLoading && !previewTemplate ? (
                    <div className="flex h-full items-center justify-center text-xs text-[var(--rl-text-muted)]">
                      Loading preview template...
                    </div>
                  ) : previewTemplate ? (
                    <div className="inline-block min-w-full text-center">
                      <div
                        className="inline-block text-left shrink-0"
                        style={{
                          width: (previewTemplate.config.canvas?.width || 794) * previewZoom,
                          height: canvasH * previewZoom,
                          position: "relative",
                          backgroundColor: "#ffffff",
                          boxShadow: "0 4px 14px rgba(0,0,0,0.08)",
                          borderRadius: "4px",
                          overflow: "hidden",
                        }}
                      >
                        <div
                          id="rl-live-canvas-inner"
                          style={{
                            width: previewTemplate.config.canvas?.width || 794,
                            height: canvasH,
                            transform: `scale(${previewZoom})`,
                            transformOrigin: "top left",
                            position: "relative",
                          }}
                        >
                          {balancedElements.map((element: CanvasElement) => (
                            <CanvasElementView
                              key={element.id}
                              element={element}
                              selected={false}
                              readOnly={true}
                              onPointerDown={() => { }}
                              config={previewTemplate.config}
                              variableValues={previewFields}
                              benefitData={{ ...workspace.benefit_cards, current_benefits: currentCards, available_addons: addonCards, extras: workspace.extras, displayOptions }}
                              conceptAssets={conceptAssets}
                              assets={previewTemplateAssets}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-[var(--rl-text-muted)]">
                      Select a template to generate live preview
                    </div>
                  )}
                </div>
              )}

            </Card>

            {/* Row 2: Interactive Benefits & Add-ons Manager with Tabs */}
            <BenefitsManagerPanel
              companyName={companyName}
              benefitsCollapsed={benefitsCollapsed}
              setBenefitsCollapsed={setBenefitsCollapsed}
              benefitsViewMode={benefitsViewMode}
              setBenefitsViewMode={setBenefitsViewMode}
              currentCards={currentCards}
              addonCards={addonCards}
              focCards={focCards}
              purchasedAddonCards={purchasedAddonCards}
              handleReset={handleReset}
              handleUndo={handleUndo}
              handleRedo={handleRedo}
              undoStack={undoStack}
              redoStack={redoStack}
              setModalTarget={setModalTarget}
              setShowGlobalModal={setShowGlobalModal}
              workspace={workspace}
              globalConcepts={globalConcepts}
              conceptAssets={conceptAssets}
              onQueue={onQueue}
              packPlanSelections={packPlanSelections}
              setPackPlanSelections={setPackPlanSelections}
              removePack={removePack}
              addPack={addPack}
              customLabel={customLabel}
              setCustomLabel={setCustomLabel}
              customValue={customValue}
              setCustomValue={setCustomValue}
              customPrice={customPrice}
              setCustomPrice={setCustomPrice}
              addCustomBenefit={addCustomBenefit}
            />
          </section>
        </div>

        {/* Empty fallback if all 3 panels are collapsed */}
        {!pdfOpen && formCollapsed && previewColCollapsed ? (
          <div className="flex flex-col items-center justify-center w-full py-24 text-center text-sm text-[var(--rl-text-muted)] gap-3 bg-[var(--rl-surface)] rounded-[var(--rl-radius)] border border-[var(--rl-border)]">
            <p className="font-semibold text-neutral-700">All workspace panels are currently hidden.</p>
            <p className="text-xs text-neutral-500 max-w-sm">Use the layout switcher in the top header or click below to restore panels:</p>
            <div className="flex items-center gap-2 mt-1">
              <Button size="sm" variant="secondary" onClick={() => setPdfOpen(true)}>Open PDF</Button>
              <Button size="sm" variant="secondary" onClick={() => setFormCollapsed(false)}>Open Form</Button>
              <Button size="sm" variant="primary" onClick={() => setPreviewColCollapsed(false)}>Open Live Preview</Button>
            </div>
          </div>
        ) : null}
      </div>


      <ReviewModals
        showGlobalModal={showGlobalModal}
        setShowGlobalModal={setShowGlobalModal}
        modalTarget={modalTarget}
        globalSearch={globalSearch}
        setGlobalSearch={setGlobalSearch}
        modalFilter={modalFilter}
        setModalFilter={setModalFilter}
        companyName={companyName}
        globalConcepts={globalConcepts}
        isExcludedForVehicle={isExcludedForVehicle}
        insurerConceptKeys={insurerConceptKeys}
        GLOBAL_BENEFIT_KEYS={GLOBAL_BENEFIT_KEYS}
        filteredConcepts={filteredConcepts}
        fileUrl={fileUrl}
        addConceptAsBenefit={addConceptAsBenefit}
        conflictModalOpen={conflictModalOpen}
        setConflictModalOpen={setConflictModalOpen}
        ownershipConflict={ownershipConflict}
        selectedResolution={selectedResolution}
        setSelectedResolution={setSelectedResolution}
        resolutionNotes={resolutionNotes}
        setResolutionNotes={setResolutionNotes}
        resolvingConflict={resolvingConflict}
        handleResolveConflict={handleResolveConflict}
        toastMessage={toastMessage}
        pendingExportAction={pendingExportAction}
        setPendingExportAction={setPendingExportAction}
        confirmAndExecuteExport={confirmAndExecuteExport}
      />
    </section>
    </>
  );
}

