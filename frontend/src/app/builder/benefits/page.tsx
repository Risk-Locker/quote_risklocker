"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  ArrowClockwise,
  ArrowCounterClockwise,
  Buildings,
  CaretRight,
  Check,
  CheckCircle,
  Copy,
  DownloadSimple,
  Eye,
  EyeSlash,
  FileDoc,
  FileXls,
  Funnel,
  Info,
  Lightning,
  MagnifyingGlass,
  Package as PackageIcon,
  PencilSimple,
  Plus,
  ShieldCheck,
  Sparkle,
  Table,
  Trash,
  TreeStructure,
  X,
} from "@phosphor-icons/react";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { AppShell } from "@/components/app-shell";
import { BuilderNav } from "@/components/builder-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
import { Select } from "@/components/ui/select";
import { PageLoading } from "@/components/ui/page-loading";
import { CanvasElementView, type CanvasElement } from "@/components/template-canvas/shared";
import { GuidedTour, type TourStep } from "@/components/guided-tour";
import { api, API_BASE, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import type {
  AssetSummary as Asset,
  CatalogRevisionSummary as CatalogRevision,
  CatalogSummary as Catalog,
  CatalogWorkspaceData as CatalogWorkspace,
  BenefitProfile,
  CompanyBenefitCondition,
  CompanyBenefitConfig,
  CompanyBenefitProfile,
  CompanySummary as Company,
  CompanyWorkspaceData as CompanyWorkspace,
  ConceptSummary as Concept,
  HierarchyItem,
  OfferingSummary as Offering,
  PackageEntity as Package,
  PackageSummary,
  ProductSummary as Product,
  TierSummary as Tier,
} from "@/types/benefits";
import type {
  Source,
  TemplateRecord,
  MatrixOffering,
  MatrixBundleItem,
  MatrixBundlePlan,
  MatrixBundle,
  MatrixScenario,
  CompanyMatrixData,
} from "./types";
import { ROLE_FALLBACK } from "./types";
import { BenefitConditionsTab } from "./components/benefit-conditions-tab";
import { OverviewMatrixTab } from "./components/overview-matrix-tab";
import { CompanyBenefitsTab } from "./components/company-benefits-tab";
import { BenefitsStepNavigator } from "./components/benefits-step-navigator";
import { BenefitsDialogs } from "./components/benefits-dialogs";

const BENEFITS_TOUR_STEPS: TourStep[] = [
  {
    target: "header",
    title: "Page purpose",
    body: "This is the Benefits & Add-ons cockpit. It assigns the global benefit library to one insurer's product, builds package tiers (package-system insurers), and configures add-on bundles. Nothing here is hardcoded — everything is saved to the database.",
  },
  {
    target: ".rl-tour-companies",
    title: "1. Insurance companies",
    body: "Pick an insurer to manage its products and benefits. The badge shows whether it uses a Package System (tier ladder) or a simple Add-on System.",
  },
  {
    target: ".rl-tour-product",
    title: "5. Product / configuration",
    body: "Choose the product configuration (or package tier) you want to edit. Each chip is one catalog.",
  },
  {
    target: ".rl-tour-ladder",
    title: "Package tier ladder",
    body: "For package-system insurers, this ladder shows every tier (Lite → Plus → Premier → All-Inclusive). Click a tier to switch which benefits you're editing. Higher tiers include more defaults and fewer add-ons.",
  },
  {
    target: ".rl-tour-defaults",
    title: "Default benefits",
    body: "Click any tile to toggle a benefit as an included default for this tier. These appear in the 'Your Benefits' grid of the final quotation.",
  },
  {
    target: ".rl-tour-addons",
    title: "Available add-ons",
    body: "Click any tile to offer a benefit as a payable add-on. These appear in the 'Available Add-ons' grid.",
  },
  {
    target: ".rl-tour-bundles",
    title: "Bundles & plans",
    body: "Create add-on bundles (e.g. Driver Protection Pack) and their plan levels A/B/C/D here. Each plan can upgrade existing benefits — adding the pack in a session upgrades them in place.",
  },
  {
    target: ".rl-tour-publish",
    title: "Save & Publish",
    body: "Publishing freezes this catalog revision (immutable). Quotations can only pin published revisions. Use 'New draft' to edit a published catalog again.",
  },
];

function effectiveRole(offering: Offering): string {
  return offering.role || ROLE_FALLBACK[offering.offering_kind] || "included";
}

let cachedReferenceData: {
  companies: Company[];
  segments: HierarchyItem[];
  vehicles: HierarchyItem[];
  concepts: Concept[];
  sources: Source[];
  templates: TemplateRecord[];
  timestamp: number;
} | null = null;

function BenefitsPageContent() {
  const params = useSearchParams();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyWorkspace, setCompanyWorkspace] = useState<CompanyWorkspace | null>(null);
  const [catalogWorkspace, setCatalogWorkspace] = useState<CatalogWorkspace | null>(null);
  const [segments, setSegments] = useState<HierarchyItem[]>([]);
  const [vehicles, setVehicles] = useState<HierarchyItem[]>([]);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");

  const [selectedCompanyId, setSelectedCompanyId] = useState(params.get("company") || "");
  const [selectedSegmentId, setSelectedSegmentId] = useState("");
  const [selectedVehicleId, setSelectedVehicleId] = useState("");
  const [selectedProductId, setSelectedProductId] = useState(params.get("product") || "");
  const [selectedCatalogId, setSelectedCatalogId] = useState(params.get("catalog") || "");
  const [selectedPackageId, setSelectedPackageId] = useState<string>("");
  const [selectedPackageKey, setSelectedPackageKey] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"structure" | "bundles">("structure");
  const [showLiveTemplate, setShowLiveTemplate] = useState(true);
  const [loading, setLoading] = useState(true);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [dialog, setDialog] = useState<"config" | "bundle" | "clone" | null>(null);
  const [builderCoverageFilter, setBuilderCoverageFilter] = useState<"comprehensive" | "tpft" | "tpo">("comprehensive");

  const mountedRef = useRef(true);
  const leftScrollRef = useRef<HTMLDivElement | null>(null);
  const rightScrollRef = useRef<HTMLDivElement | null>(null);
  const isSyncingScrollRef = useRef<boolean>(false);

  const handleLeftScroll = useCallback(() => {
    if (isSyncingScrollRef.current) return;
    const left = leftScrollRef.current;
    const right = rightScrollRef.current;
    if (!left || !right) return;

    const maxLeft = left.scrollHeight - left.clientHeight;
    const maxRight = right.scrollHeight - right.clientHeight;
    if (maxLeft <= 0 || maxRight <= 0) return;

    isSyncingScrollRef.current = true;
    const ratio = left.scrollTop / maxLeft;
    right.scrollTop = ratio * maxRight;
    requestAnimationFrame(() => {
      isSyncingScrollRef.current = false;
    });
  }, []);

  const handleRightScroll = useCallback(() => {
    if (isSyncingScrollRef.current) return;
    const left = leftScrollRef.current;
    const right = rightScrollRef.current;
    if (!left || !right) return;

    const maxLeft = left.scrollHeight - left.clientHeight;
    const maxRight = right.scrollHeight - right.clientHeight;
    if (maxLeft <= 0 || maxRight <= 0) return;

    isSyncingScrollRef.current = true;
    const ratio = right.scrollTop / maxRight;
    left.scrollTop = ratio * maxLeft;
    requestAnimationFrame(() => {
      isSyncingScrollRef.current = false;
    });
  }, []);

  // Form states
  const [formName, setFormName] = useState("");
  const [formPackageName, setFormPackageName] = useState("");
  const [formAsPackage, setFormAsPackage] = useState(false);
  const [formPackageKey, setFormPackageKey] = useState("");

  // Plan manager states
  const [planFormName, setPlanFormName] = useState("");
  const [expandedPlanId, setExpandedPlanId] = useState<string>("");
  const [planMemberOfferingId, setPlanMemberOfferingId] = useState<string>("");
  const [planMemberOverride, setPlanMemberOverride] = useState<string>("");
  const [planSaving, setPlanSaving] = useState(false);

  // 4 Core Cockpit Tabs: Company Benefits, Catalogs, Conditions, Matrix
  type ScreenTab = "company_benefits" | "catalogs" | "conditions" | "matrix";
  const [screenTab, setScreenTab] = useState<ScreenTab>("company_benefits");
  const [selectedEngineType, setSelectedEngineType] = useState<"ice" | "ev">("ice");

  // Profile governance states
  const [profiles, setProfiles] = useState<BenefitProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [profileActionLoading, setProfileActionLoading] = useState(false);
  const [cloneModalOpen, setCloneModalOpen] = useState(false);
  const [cloneName, setCloneName] = useState("");
  const [cloneNotes, setCloneNotes] = useState("");

  // Tab 1: Company-Based Benefits state
  const [companyConfigs, setCompanyConfigs] = useState<CompanyBenefitConfig[]>([]);
  const [configsLoading, setConfigsLoading] = useState(false);
  const [configsSaving, setConfigsSaving] = useState(false);
  const [configsSearch, setConfigsSearch] = useState("");
  const [configsCategoryFilter, setConfigsCategoryFilter] = useState<"all" | "default" | "addon">("all");
  const [customizingCostIds, setCustomizingCostIds] = useState<Set<string>>(new Set());

  // Tab 3: Company Conditions state
  const [companyConditions, setCompanyConditions] = useState<CompanyBenefitCondition[]>([]);
  const [conditionsLoading, setConditionsLoading] = useState(false);
  const [conditionDialog, setConditionDialog] = useState(false);
  const [conditionSaving, setConditionSaving] = useState(false);
  const [condFormName, setCondFormName] = useState("");
  const [condTriggerId, setCondTriggerId] = useState("");
  const [condPlanFilter, setCondPlanFilter] = useState("");
  const [condTargetId, setCondTargetId] = useState("");
  const [condActionType, setCondActionType] = useState<"replace_description" | "hide_target">("replace_description");
  const [condReplacement, setCondReplacement] = useState("");

  // Tab 4: Matrix and AI sync states
  const [matrixData, setMatrixData] = useState<CompanyMatrixData | null>(null);
  const [matrixLoading, setMatrixLoading] = useState(false);
  const [matrixSearch, setMatrixSearch] = useState("");
  const [matrixFilterCoverage, setMatrixFilterCoverage] = useState("All");
  const [showAiModal, setShowAiModal] = useState(false);
  const [aiModalTab, setAiModalTab] = useState<"spec" | "diff">("spec");
  const [aiDiffInput, setAiDiffInput] = useState("");
  const [aiDiffResult, setAiDiffResult] = useState<any>(null);
  const [aiDiffLoading, setAiDiffLoading] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [editingMatrixItem, setEditingMatrixItem] = useState<{
    catalog_id: string;
    offering_id: string;
    field: "display_value" | "description";
    value: string;
  } | null>(null);

  async function saveMatrixInlineEdit() {
    if (!editingMatrixItem) return;
    const { catalog_id, offering_id, field, value } = editingMatrixItem;
    const cleanVal = value.trim();

    setMatrixData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        scenarios: prev.scenarios.map((s) => {
          if (s.catalog_id !== catalog_id) return s;
          const updateOffering = (o: MatrixOffering) => {
            if (o.offering_id !== offering_id) return o;
            if (field === "display_value") {
              return { ...o, display_value: cleanVal };
            } else {
              return { ...o, description: cleanVal, is_custom_description: Boolean(cleanVal) };
            }
          };
          return {
            ...s,
            defaults: s.defaults.map(updateOffering),
            addons: s.addons.map(updateOffering),
          };
        }),
      };
    });

    setEditingMatrixItem(null);

    try {
      const payload: Record<string, unknown> = {
        id: offering_id,
        [field === "display_value" ? "display_value" : "description_override"]: cleanVal || null,
      };
      await api(`/business/catalogs/${catalog_id}/offerings`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    } catch (err) {
      setError(apiErrorMessage(err));
      if (selectedCompanyId) {
        void loadMatrix(selectedCompanyId);
      }
    }
  }

  // Derived profile status
  const selectedProfile = useMemo(() => {
    return profiles.find((p) => p.id === selectedProfileId) || profiles.find((p) => p.is_active) || profiles[0] || null;
  }, [profiles, selectedProfileId]);

  const isProfileArchived = selectedProfile?.status === "archived";

  const disabledConceptIdSet = useMemo(() => {
    return new Set(
      companyConfigs
        .filter((c) => c.is_enabled === false)
        .map((c) => c.concept_id)
    );
  }, [companyConfigs]);

  // ── 0. Queue & In-Flight Guards for fast reliable API calls ──────────
  const queueRef = useRef<Promise<void>>(Promise.resolve());
  const inFlightRef = useRef<Set<string>>(new Set());
  const companyCacheRef = useRef<Map<string, { workspace: CompanyWorkspace; ts: number }>>(new Map());
  const catalogCacheRef = useRef<Map<string, { workspace: CatalogWorkspace; ts: number }>>(new Map());
  const catalogWorkspaceRef = useRef<CatalogWorkspace | null>(null);
  catalogWorkspaceRef.current = catalogWorkspace;

  const enqueueTask = useCallback((task: () => Promise<void>) => {
    queueRef.current = queueRef.current.then(async () => {
      try {
        await task();
      } catch (err) {
        console.error("Queue task failed:", err);
      }
    });
  }, []);

  // ── 1. Callbacks ───────────────────────────────────────────────────────
  const loadCompanyConfigs = useCallback(async (companyId: string, profileId?: string) => {
    if (!companyId) return;
    setConfigsLoading(true);
    try {
      const url = profileId
        ? `/business/companies/${companyId}/benefit-configs?profile_id=${encodeURIComponent(profileId)}`
        : `/business/companies/${companyId}/benefit-configs`;
      const res = await api<{ configs: CompanyBenefitConfig[] }>(url);
      if (mountedRef.current) setCompanyConfigs(res.configs || []);
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
    } finally {
      if (mountedRef.current) setConfigsLoading(false);
    }
  }, []);

  const loadCompanyConditions = useCallback(async (companyId: string, profileId?: string) => {
    if (!companyId) return;
    setConditionsLoading(true);
    try {
      const url = profileId
        ? `/business/companies/${companyId}/conditions?profile_id=${encodeURIComponent(profileId)}`
        : `/business/companies/${companyId}/conditions`;
      const res = await api<{ conditions: CompanyBenefitCondition[] }>(url);
      if (mountedRef.current) setCompanyConditions(res.conditions || []);
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
    } finally {
      if (mountedRef.current) setConditionsLoading(false);
    }
  }, []);

  const loadBenefitProfiles = useCallback(async (preferredProfileId?: string) => {
    setProfilesLoading(true);
    try {
      const res = await api<{ profiles: BenefitProfile[] }>("/business/benefit-profiles");
      const list = res.profiles || [];
      if (mountedRef.current) setProfiles(list);
      const target = (preferredProfileId && list.find((p) => p.id === preferredProfileId))
        || list.find((p) => p.is_active)
        || list[0];
      const targetId = target ? target.id : "";
      if (mountedRef.current) setSelectedProfileId(targetId);
      return list;
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
      return [];
    } finally {
      if (mountedRef.current) setProfilesLoading(false);
    }
  }, []);

  const saveCompanyConfigs = useCallback(async () => {
    if (!selectedCompanyId) return;
    setConfigsSaving(true);
    setError("");
    try {
      const url = selectedProfileId
        ? `/business/companies/${selectedCompanyId}/benefit-configs?profile_id=${encodeURIComponent(selectedProfileId)}`
        : `/business/companies/${selectedCompanyId}/benefit-configs`;
      const payloadItems = companyConfigs.map((c) => {
        const rawCost = typeof c.baseline_cost === "string" ? c.baseline_cost.trim() : "";
        const lower = rawCost.toLowerCase();
        const norm = lower.replace(/^(rm|myr)\s*/, "").trim();
        const cleanCost = (!rawCost || ["", "0", "00", "0.0", "0.00", "null", "none", "quoted", "as quoted", "foc", "included"].includes(norm) || ["null", "none", "rm", "rm0", "rm00", "rm 0", "rm 0.0", "rm 0.00", "rm0.00", "rm quoted", "as quoted", "foc", "included"].includes(lower))
          ? null
          : rawCost;
        return {
          concept_id: c.concept_id,
          is_enabled: c.is_enabled,
          baseline_description: c.baseline_description ?? null,
          baseline_cost: cleanCost,
        };
      });
      const res = await api<{ configs: CompanyBenefitConfig[] }>(url, {
        method: "PUT",
        body: JSON.stringify({ items: payloadItems, configs: payloadItems }),
      });
      if (mountedRef.current) {
        setCompanyConfigs(res.configs || []);
      }
      const profRes = await api<{ profiles: BenefitProfile[] }>("/business/benefit-profiles");
      if (mountedRef.current) setProfiles(profRes.profiles || []);
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
    } finally {
      if (mountedRef.current) setConfigsSaving(false);
    }
  }, [selectedCompanyId, selectedProfileId, companyConfigs]);

  const saveCompanyCondition = useCallback(async () => {
    if (!selectedCompanyId || !condFormName.trim() || !condTriggerId || !condTargetId || !condReplacement.trim()) {
      setError("Please fill all required fields for the conditional rule.");
      return;
    }
    setConditionSaving(true);
    setError("");
    try {
      const url = selectedProfileId
        ? `/business/companies/${selectedCompanyId}/conditions?profile_id=${encodeURIComponent(selectedProfileId)}`
        : `/business/companies/${selectedCompanyId}/conditions`;
      await api(url, {
        method: "POST",
        body: JSON.stringify({
          name: condFormName.trim(),
          trigger_concept_id: condTriggerId,
          trigger_plan_filter: condPlanFilter.trim() || null,
          target_concept_id: condTargetId,
          action_type: condActionType,
          replacement_description: condActionType === "hide_target" ? (condReplacement.trim() || "[Hidden by condition rule]") : condReplacement.trim(),
          is_active: true,
        }),
      });
      setConditionDialog(false);
      setCondFormName("");
      setCondTriggerId("");
      setCondPlanFilter("");
      setCondTargetId("");
      setCondActionType("replace_description");
      setCondReplacement("");
      await loadCompanyConditions(selectedCompanyId, selectedProfileId);
      const profRes = await api<{ profiles: BenefitProfile[] }>("/business/benefit-profiles");
      if (mountedRef.current) setProfiles(profRes.profiles || []);
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
    } finally {
      if (mountedRef.current) setConditionSaving(false);
    }
  }, [selectedCompanyId, selectedProfileId, condFormName, condTriggerId, condPlanFilter, condTargetId, condActionType, condReplacement, loadCompanyConditions]);

  const deleteCompanyCondition = useCallback(async (conditionId: string) => {
    if (!selectedCompanyId) return;
    if (!window.confirm("Are you sure you want to delete this conditional rule?")) return;
    setConditionsLoading(true);
    try {
      await api(`/business/companies/${selectedCompanyId}/conditions/${conditionId}`, {
        method: "DELETE",
      });
      await loadCompanyConditions(selectedCompanyId, selectedProfileId);
      const profRes = await api<{ profiles: BenefitProfile[] }>("/business/benefit-profiles");
      if (mountedRef.current) setProfiles(profRes.profiles || []);
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
    } finally {
      if (mountedRef.current) setConditionsLoading(false);
    }
  }, [selectedCompanyId, selectedProfileId, loadCompanyConditions]);

  const handleActivateProfile = useCallback(async (profileId: string) => {
    if (!profileId) return;
    if (!window.confirm("Activate this benefit profile? It will become the live master configuration across all insurance companies for quotations and PDF generation.")) return;
    setProfileActionLoading(true);
    setError("");
    try {
      await api(`/business/benefit-profiles/${profileId}/activate`, {
        method: "POST",
      });
      await loadBenefitProfiles(profileId);
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
    } finally {
      if (mountedRef.current) setProfileActionLoading(false);
    }
  }, [loadBenefitProfiles]);

  const handleDeleteDraftProfile = useCallback(async (profileId: string) => {
    if (!profileId) return;
    if (!window.confirm("Are you sure you want to delete this benefit profile? This cannot be undone.")) return;
    setProfileActionLoading(true);
    setError("");
    try {
      await api(`/business/benefit-profiles/${profileId}`, {
        method: "DELETE",
      });
      await loadBenefitProfiles();
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
    } finally {
      if (mountedRef.current) setProfileActionLoading(false);
    }
  }, [loadBenefitProfiles]);

  const handleCloneProfile = useCallback(async () => {
    if (!selectedProfileId) return;
    setProfileActionLoading(true);
    setError("");
    try {
      const res = await api<{ profile: BenefitProfile }>(
        `/business/benefit-profiles/${selectedProfileId}/clone`,
        {
          method: "POST",
          body: JSON.stringify({
            name: cloneName.trim() || undefined,
            notes: cloneNotes.trim() || undefined,
          }),
        }
      );
      setCloneModalOpen(false);
      setCloneName("");
      setCloneNotes("");
      const newProfId = res.profile?.id;
      await loadBenefitProfiles(newProfId);
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
    } finally {
      if (mountedRef.current) setProfileActionLoading(false);
    }
  }, [selectedProfileId, cloneName, cloneNotes, loadBenefitProfiles]);

  const loadMatrix = useCallback(async (companyId: string) => {
    if (!companyId) return;
    setMatrixLoading(true);
    try {
      const res = await api<{ matrix: CompanyMatrixData }>(`/business/companies/${companyId}/matrix`);
      if (mountedRef.current) setMatrixData(res.matrix);
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
    } finally {
      if (mountedRef.current) setMatrixLoading(false);
    }
  }, []);

  function downloadDocx() {
    if (!selectedCompanyId) return;
    window.location.href = `${API_BASE}/business/companies/${selectedCompanyId}/export-matrix?format=docx`;
  }

  function downloadXlsx() {
    if (!selectedCompanyId) return;
    window.location.href = `${API_BASE}/business/companies/${selectedCompanyId}/export-matrix?format=xlsx`;
  }

  const syncUrl = useCallback((company: string, product = "", config = "") => {
    const next = new URLSearchParams();
    if (company) next.set("company", company);
    if (product) next.set("product", product);
    if (config) next.set("catalog", config);
    window.history.replaceState(null, "", `/builder/benefits${next.size ? `?${next}` : ""}`);
  }, []);

  const loadReferenceData = useCallback(async (force = false) => {
    if (!force && cachedReferenceData && Date.now() - cachedReferenceData.timestamp < 120000) {
      setCompanies(cachedReferenceData.companies);
      setSegments(cachedReferenceData.segments);
      setVehicles(cachedReferenceData.vehicles);
      setConcepts(cachedReferenceData.concepts);
      setSources(cachedReferenceData.sources);
      setTemplates(cachedReferenceData.templates);

      const preferredTpl =
        cachedReferenceData.templates.find((t) => (t.name || "").toLowerCase().includes("motor") || (t.name || "").toLowerCase().includes("copy of standard a4") || t.is_default) ||
        cachedReferenceData.templates[0] ||
        null;
      if (preferredTpl) setSelectedTemplateId(preferredTpl.id);

      setSelectedSegmentId((current) => current || cachedReferenceData!.segments.find((item) => item.key === "private")?.id || cachedReferenceData!.segments[0]?.id || "");
      setSelectedVehicleId((current) => current || cachedReferenceData!.vehicles.find((item) => item.key === "car")?.id || cachedReferenceData!.vehicles[0]?.id || "");

      return cachedReferenceData.companies;
    }

    const [companyResult, segmentResult, vehicleResult, conceptResult, sourceResult, templateResult] = await Promise.all([
      api<{ companies: { items: Company[] } }>("/business/companies?page=1&page_size=100"),
      api<{ segments: { items: HierarchyItem[] } }>("/business/segments?page=1&page_size=100"),
      api<{ vehicle_categories: { items: HierarchyItem[] } }>("/business/vehicle-categories?page=1&page_size=100"),
      api<{ benefit_concepts: { items: Concept[] } }>("/business/benefit-concepts?page=1&page_size=100"),
      api<{ sources: { items: Source[] } }>("/business/sources?page=1&page_size=100"),
      api<{ templates: TemplateRecord[] | { items: TemplateRecord[] } }>("/admin/templates?page=1&page_size=20").catch(() =>
        api<{ templates: TemplateRecord[] }>("/business/templates/published").catch(() => ({ templates: [] }))
      ),
    ]);

    const activeCompanies = companyResult.companies.items;
    const activeSegments = segmentResult.segments.items.filter((item) => item.status === "active");
    const activeVehicles = vehicleResult.vehicle_categories.items.filter((item) => item.status === "active");
    const filteredConcepts = conceptResult.benefit_concepts.items.filter((item) => item.status !== "retired");
    const allSources = sourceResult.sources.items;
    const rawTemplates = (templateResult as { templates?: TemplateRecord[] | { items?: TemplateRecord[] } })?.templates;
    const allTemplates: TemplateRecord[] = Array.isArray(rawTemplates)
      ? rawTemplates
      : (rawTemplates?.items || []);

    cachedReferenceData = {
      companies: activeCompanies,
      segments: activeSegments,
      vehicles: activeVehicles,
      concepts: filteredConcepts,
      sources: allSources,
      templates: allTemplates,
      timestamp: Date.now(),
    };

    setCompanies(activeCompanies);
    setSegments(activeSegments);
    setVehicles(activeVehicles);
    setConcepts(filteredConcepts);
    setSources(allSources);
    setTemplates(allTemplates);

    const preferredTpl =
      allTemplates.find((t) => (t.name || "").toLowerCase().includes("motor") || (t.name || "").toLowerCase().includes("copy of standard a4") || t.is_default) ||
      allTemplates[0] ||
      null;
    if (preferredTpl) setSelectedTemplateId(preferredTpl.id);

    setSelectedSegmentId((current) => current || activeSegments.find((item) => item.key === "private")?.id || activeSegments[0]?.id || "");
    setSelectedVehicleId((current) => current || activeVehicles.find((item) => item.key === "car")?.id || activeVehicles[0]?.id || "");

    return activeCompanies;
  }, []);

  const matchesCoverage = useCallback((cat: any, filter: "comprehensive" | "tpft" | "tpo") => {
    const covId = String(cat.coverage_type_id || "").toLowerCase();
    const covKey = String(cat.coverage_type_key || "").toLowerCase();
    const catName = String(cat.name || "").toLowerCase();
    const pkgKind = String(cat.package?.package_kind || "").toLowerCase();

    if (filter === "comprehensive") {
      if (covId === "d1111111-0000-4000-8000-000000000001" || covKey === "comprehensive" || pkgKind === "comprehensive") return true;
      if (covId === "d1111111-0000-4000-8000-000000000002" || covId === "d1111111-0000-4000-8000-000000000003") return false;
      if (catName.includes("tpft") || catName.includes("third party")) return false;
      return true;
    }
    if (filter === "tpft") {
      if (covId === "d1111111-0000-4000-8000-000000000002" || covKey === "tpft" || pkgKind === "tpft") return true;
      return catName.includes("tpft") || catName.includes("third party fire") || catName.includes("third party, fire");
    }
    if (filter === "tpo") {
      if (covId === "d1111111-0000-4000-8000-000000000003" || covKey === "third_party" || pkgKind === "tpo" || pkgKind === "third_party") return true;
      return catName.includes("third party") && !catName.includes("fire") && !catName.includes("theft");
    }
    return true;
  }, []);

  const loadCatalog = useCallback(
    async (catalogId: string, silent = false) => {
      if (!catalogId) {
        setCatalogWorkspace(null);
        catalogWorkspaceRef.current = null;
        return;
      }
      const cached = catalogCacheRef.current.get(catalogId);
      const isFresh = cached && Date.now() - cached.ts < 30000;
      if (cached) {
        setCatalogWorkspace(cached.workspace);
        catalogWorkspaceRef.current = cached.workspace;
        setSelectedCatalogId(catalogId);
        const prodId = cached.workspace.catalog?.product_id || "";
        setSelectedProductId(prodId);
        syncUrl(selectedCompanyId, prodId, catalogId);
        if (isFresh || silent) {
          if (isFresh) return;
        }
      } else if (!silent) {
        setWorkspaceLoading(true);
      }
      setError("");
      try {
        const result = await api<{ workspace: CatalogWorkspace }>(`/business/catalogs/${catalogId}/workspace`);
        if (!mountedRef.current) return;
        catalogCacheRef.current.set(catalogId, { workspace: result.workspace, ts: Date.now() });
        setCatalogWorkspace(result.workspace);
        catalogWorkspaceRef.current = result.workspace;
        setSelectedCatalogId(catalogId);
        const prodId = result.workspace.catalog?.product_id || "";
        setSelectedProductId(prodId);
        syncUrl(selectedCompanyId, prodId, catalogId);
      } catch (err) {
        if (mountedRef.current) setError(apiErrorMessage(err));
      } finally {
        if (!silent && mountedRef.current) setWorkspaceLoading(false);
      }
    },
    [selectedCompanyId, syncUrl]
  );

  const loadCompany = useCallback(
    async (companyId: string, preferredProduct = selectedProductId, preferredCatalog = selectedCatalogId) => {
      if (!companyId) return;
      const cached = companyCacheRef.current.get(companyId);
      const isFresh = cached && Date.now() - cached.ts < 60000;

      if (cached) {
        setCompanyWorkspace(cached.workspace);
        setSelectedCompanyId(companyId);

        const carVehId = "b1111111-0000-4000-8000-000000000001";
        const targetVehicleId = selectedVehicleId || carVehId;
        const targetEngine = selectedEngineType || "ice";

        const matchingCatalogs = (cached.workspace.catalogs || []).filter((item) =>
          (!selectedSegmentId || !item.segment_id || item.segment_id === selectedSegmentId) &&
          (!targetVehicleId || item.vehicle_category_id === targetVehicleId) &&
          ((item.engine_type || "ice") === targetEngine) &&
          matchesCoverage(item, builderCoverageFilter)
        );

        const catalog =
          (preferredCatalog && matchingCatalogs.find((item) => item.id === preferredCatalog)) ||
          matchingCatalogs[0] ||
          cached.workspace.catalogs.find((item) => (item.engine_type || "ice") === targetEngine && (!targetVehicleId || item.vehicle_category_id === targetVehicleId)) ||
          cached.workspace.catalogs.find((item) => (item.engine_type || "ice") === targetEngine) ||
          cached.workspace.catalogs[0];

        const prodId = catalog?.product_id || preferredProduct || "";
        setSelectedProductId(prodId);
        if (catalog?.id) {
          setSelectedCatalogId(catalog.id);
          syncUrl(companyId, prodId, catalog.id);
          void loadCatalog(catalog.id, true);
        }

        if (isFresh) {
          return;
        }
      } else {
        setWorkspaceLoading(true);
      }

      setError("");
      try {
        const result = await api<{ workspace: CompanyWorkspace }>(`/business/companies/${companyId}/workspace`);
        if (!mountedRef.current) return;
        companyCacheRef.current.set(companyId, { workspace: result.workspace, ts: Date.now() });
        setCompanyWorkspace(result.workspace);
        setSelectedCompanyId(companyId);

        const carVehId = "b1111111-0000-4000-8000-000000000001";
        const targetVehicleId = selectedVehicleId || carVehId;
        const targetEngine = selectedEngineType || "ice";

        // Filter catalogs matching current vehicle, engine, segment, and coverage preferences
        const matchingCatalogs = (result.workspace.catalogs || []).filter((item) =>
          (!selectedSegmentId || !item.segment_id || item.segment_id === selectedSegmentId) &&
          (!targetVehicleId || item.vehicle_category_id === targetVehicleId) &&
          ((item.engine_type || "ice") === targetEngine) &&
          matchesCoverage(item, builderCoverageFilter)
        );

        const catalog =
          (preferredCatalog && matchingCatalogs.find((item) => item.id === preferredCatalog)) ||
          matchingCatalogs[0] ||
          result.workspace.catalogs.find((item) => (item.engine_type || "ice") === targetEngine && (!targetVehicleId || item.vehicle_category_id === targetVehicleId)) ||
          result.workspace.catalogs.find((item) => (item.engine_type || "ice") === targetEngine) ||
          result.workspace.catalogs[0];

        const prodId = catalog?.product_id || preferredProduct || "";
        setSelectedProductId(prodId);
        if (catalog?.id) {
          setSelectedCatalogId(catalog.id);
          syncUrl(companyId, prodId, catalog.id);
          await loadCatalog(catalog.id);
        }
      } catch (err) {
        if (mountedRef.current) setError(apiErrorMessage(err));
      } finally {
        if (!mountedRef.current) return;
        setWorkspaceLoading(false);
      }
    },
    [builderCoverageFilter, loadCatalog, matchesCoverage, selectedCatalogId, selectedEngineType, selectedProductId, selectedSegmentId, selectedVehicleId, syncUrl]
  );

  useEffect(() => {
    loadBenefitProfiles();
  }, [loadBenefitProfiles]);

  useEffect(() => {
    const handleProfileUpdated = () => {
      loadBenefitProfiles();
      if (selectedCompanyId) {
        loadCompany(selectedCompanyId);
      }
    };
    window.addEventListener("risklocker:profile-updated", handleProfileUpdated);
    return () => window.removeEventListener("risklocker:profile-updated", handleProfileUpdated);
  }, [loadBenefitProfiles, loadCompany, selectedCompanyId]);

  useEffect(() => {
    if (selectedCompanyId && selectedProfileId) {
      loadCompanyConfigs(selectedCompanyId, selectedProfileId);
      loadCompanyConditions(selectedCompanyId, selectedProfileId);
    }
  }, [selectedCompanyId, selectedProfileId, loadCompanyConfigs, loadCompanyConditions]);

  useEffect(() => {
    if (screenTab === "matrix" && selectedCompanyId) {
      loadMatrix(selectedCompanyId);
    }
  }, [screenTab, selectedCompanyId, loadMatrix]);

  const filteredMatrixScenarios = useMemo(() => {
    if (!matrixData) return [];
    return matrixData.scenarios.filter((s) => {
      if (matrixFilterCoverage !== "All") {
        if (!s.coverage_type_name.toLowerCase().includes(matrixFilterCoverage.toLowerCase())) {
          return false;
        }
      }
      if (matrixSearch.trim()) {
        const q = matrixSearch.toLowerCase();
        const inScenario = s.scenario_name.toLowerCase().includes(q) || s.product_name.toLowerCase().includes(q);
        const inDefaults = s.defaults.some((d) => d.label.toLowerCase().includes(q) || d.display_value.toLowerCase().includes(q));
        const inAddons = s.addons.some((a) => a.label.toLowerCase().includes(q) || a.display_value.toLowerCase().includes(q));
        const inBundles = s.bundles.some((b) => b.name.toLowerCase().includes(q));
        if (!inScenario && !inDefaults && !inAddons && !inBundles) return false;
      }
      return true;
    });
  }, [matrixData, matrixFilterCoverage, matrixSearch]);

  const aiMarkdownTable = useMemo(() => {
    if (!matrixData) return "";
    let md = `### Insurer Catalog Matrix: ${matrixData.company.name}\n\n`;
    md += `| Product / Scenario | Coverage | Segment / Vehicle | Defaults (Included, 0 RM) | Add-on Riders & Exact Base Cost | Bundled Plans |\n`;
    md += `| :--- | :--- | :--- | :--- | :--- | :--- |\n`;
    for (const s of matrixData.scenarios) {
      const defs = s.defaults.map((d) => `• ${d.label}: ${d.display_value} (Cost: 0 RM)`).join("<br>");
      const adds = s.addons.map((a) => `• ${a.label}: ${a.display_value} (Cost: ${a.price_text})`).join("<br>");
      const bundles = s.bundles.map((b) => `• ${b.name}: ${b.plans.map((p) => p.name).join(", ")}`).join("<br>") || "None";
      md += `| **${s.scenario_name}** | ${s.coverage_type_name} | ${s.segment_name} ${s.vehicle_category_name} | ${defs || "None"} | ${adds || "None"} | ${bundles} |\n`;
    }
    return md;
  }, [matrixData]);

  const aiSyncPrompt = useMemo(() => {
    if (!matrixData) return "";
    return `You are an Underwriting Assistant for ${matrixData.company.name}.
Review the current package and benefits matrix below.
When provided with a new product brochure or pricing update, DO NOT reseed existing unchanged values.
Return a JSON object specifying ONLY additions or changes:
{
  "scenarios": [
    {
      "scenario_name": "<matching or new scenario name>",
      "defaults": [
        {"concept_key": "<benefit_concept_key>", "display_value": "<coverage_limit>"}
      ],
      "addons": [
        {"concept_key": "<benefit_concept_key>", "display_value": "<coverage_limit>", "price": 150.0}
      ]
    }
  ]
}

CURRENT MATRIX TABLE:
${aiMarkdownTable}`;
  }, [matrixData, aiMarkdownTable]);

  function copyAiPrompt() {
    navigator.clipboard.writeText(aiSyncPrompt);
    setCopiedPrompt(true);
    setTimeout(() => setCopiedPrompt(false), 2500);
  }

  async function runAiDiffCheck() {
    if (!selectedCompanyId || !aiDiffInput.trim()) return;
    setAiDiffLoading(true);
    setAiDiffResult(null);
    try {
      const parsed = JSON.parse(aiDiffInput);
      const res = await api<{ diff: any }>(`/business/companies/${selectedCompanyId}/diff-matrix`, {
        method: "POST",
        body: JSON.stringify(parsed),
      });
      setAiDiffResult(res.diff);
    } catch (err) {
      setAiDiffResult({ error: apiErrorMessage(err) });
    } finally {
      setAiDiffLoading(false);
    }
  }

  // ── 2. Memos ───────────────────────────────────────────────────────────
  // Filter concepts by company-enabled benefits pool (Tab 1)
  const enabledConceptIds = useMemo(() => {
    if (!companyConfigs || companyConfigs.length === 0) return null;
    return new Set(companyConfigs.filter((c) => c.is_enabled).map((c) => c.concept_id));
  }, [companyConfigs]);

  // Lookup map of company baseline costs for catalog offering price fallbacks
  const baselineCostMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of companyConfigs || []) {
      if (c.concept_id && c.baseline_cost && c.baseline_cost.trim()) {
        map.set(c.concept_id, c.baseline_cost.trim());
      }
    }
    return map;
  }, [companyConfigs]);

  // Lookup map of company baseline descriptions for catalog offering description fallbacks
  const baselineDescMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of companyConfigs || []) {
      if (c.concept_id && c.baseline_description && c.baseline_description.trim()) {
        map.set(c.concept_id, c.baseline_description.trim());
      }
    }
    return map;
  }, [companyConfigs]);


  const toggleConfigEnabled = useCallback((conceptId: string, enabled: boolean) => {
    setCompanyConfigs((prev) => {
      const idx = prev.findIndex((item) => item.concept_id === conceptId);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = { ...copy[idx], is_enabled: enabled };
        return copy;
      }
      return [
        ...prev,
        {
          id: `temp-${conceptId}`,
          company_id: selectedCompanyId,
          concept_id: conceptId,
          is_enabled: enabled,
          baseline_description: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ];
    });
  }, [selectedCompanyId]);

  const updateConfigBaseline = useCallback((conceptId: string, text: string) => {
    setCompanyConfigs((prev) => {
      const idx = prev.findIndex((item) => item.concept_id === conceptId);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = { ...copy[idx], baseline_description: text };
        return copy;
      }
      return [
        ...prev,
        {
          id: `temp-${conceptId}`,
          company_id: selectedCompanyId,
          concept_id: conceptId,
          is_enabled: true,
          baseline_description: text,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ];
    });
  }, [selectedCompanyId]);

  const updateConfigBaselineCost = useCallback((conceptId: string, cost: string) => {
    setCompanyConfigs((prev) => {
      const idx = prev.findIndex((item) => item.concept_id === conceptId);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = { ...copy[idx], baseline_cost: cost };
        return copy;
      }
      return [
        ...prev,
        {
          id: `temp-${conceptId}`,
          company_id: selectedCompanyId,
          concept_id: conceptId,
          is_enabled: true,
          baseline_description: null,
          baseline_cost: cost,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ];
    });
  }, [selectedCompanyId]);

  const setAllConfigsEnabled = useCallback((enabled: boolean) => {
    setCompanyConfigs((prev) => {
      const configMap = new Map(prev.map((c) => [c.concept_id, c]));
      return concepts.map((c) => {
        const existing = configMap.get(c.id);
        if (existing) {
          return { ...existing, is_enabled: enabled };
        }
        return {
          id: `temp-${c.id}`,
          company_id: selectedCompanyId,
          concept_id: c.id,
          is_enabled: enabled,
          baseline_description: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
      });
    });
  }, [concepts, selectedCompanyId]);

  const enabledConfigsCount = useMemo(() => {
    const configMap = new Map(companyConfigs.map((c) => [c.concept_id, c]));
    return concepts.filter((c) => {
      if (c.status === "retired") return false;
      const cfg = configMap.get(c.id);
      return cfg ? cfg.is_enabled : false;
    }).length;
  }, [concepts, companyConfigs]);

  const filteredCompanyBenefitRows = useMemo(() => {
    const configMap = new Map(companyConfigs.map((c) => [c.concept_id, c]));
    return concepts
      .filter((c) => {
        if (c.status === "retired") return false;
        const cfg = configMap.get(c.id);
        const isDefault = c.value_schema?.category === "default" || c.category === "default" || (c.sort_order !== undefined && c.sort_order <= 11);
        if (configsCategoryFilter === "default" && !isDefault) return false;
        if (configsCategoryFilter === "addon" && isDefault) return false;
        if (configsSearch.trim()) {
          const q = configsSearch.toLowerCase();
          const labelMatch = c.label?.toLowerCase().includes(q);
          const keyMatch = c.concept_key?.toLowerCase().includes(q);
          const descMatch = (cfg?.baseline_description || c.description || "").toLowerCase().includes(q);
          if (!labelMatch && !keyMatch && !descMatch) return false;
        }
        return true;
      })
      .map((c) => {
        const cfg = configMap.get(c.id);
        return {
          concept: c,
          config: cfg,
          isEnabled: cfg ? cfg.is_enabled : true,
          baselineDescription: cfg?.baseline_description ?? null,
          baselineCost: cfg?.baseline_cost ?? null,
        };
      })
      .sort((a, b) => {
        if (a.isEnabled !== b.isEnabled) {
          return a.isEnabled ? -1 : 1;
        }
        return (a.concept.sort_order ?? 99) - (b.concept.sort_order ?? 99);
      });
  }, [concepts, companyConfigs, configsCategoryFilter, configsSearch]);

  const productConfigs = useMemo(() => {
    const carVehId = "b1111111-0000-4000-8000-000000000001";
    const targetVehicleId = selectedVehicleId || carVehId;
    const items = (companyWorkspace?.catalogs || []).filter(
      (item) =>
        item.status !== "archived" &&
        item.status !== "retired" &&
        (!selectedSegmentId || !item.segment_id || item.segment_id === selectedSegmentId) &&
        (!targetVehicleId || !item.vehicle_category_id || item.vehicle_category_id === targetVehicleId) &&
        ((item.engine_type || "ice") === selectedEngineType) &&
        matchesCoverage(item, builderCoverageFilter)
    );

    // If packaged catalogs exist for this company scenario, deduplicate and prioritize packaged catalogs
    const hasPackages = items.some((item) => Boolean(item.package));
    const finalItems = hasPackages ? items.filter((item) => Boolean(item.package)) : items;

    // Deduplicate by package ID or package name
    const seenPackages = new Set<string>();
    const deduplicated = finalItems.filter((item) => {
      if (item.package) {
        const key = item.package.id || item.package.name;
        if (seenPackages.has(key)) return false;
        seenPackages.add(key);
      }
      return true;
    });

    return deduplicated.sort((a, b) => {
      const aOrder = a.package?.sort_order ?? 0;
      const bOrder = b.package?.sort_order ?? 0;
      const aName = a.package?.name || a.name || "";
      const bName = b.package?.name || b.name || "";
      return aOrder - bOrder || aName.localeCompare(bName);
    });
  }, [companyWorkspace, selectedSegmentId, selectedVehicleId, selectedEngineType, builderCoverageFilter, matchesCoverage]);

  useEffect(() => {
    if (!productConfigs || productConfigs.length === 0) {
      setCatalogWorkspace(null);
      return;
    }
    const exists = productConfigs.some((c) => c.id === selectedCatalogId);
    if (!exists && productConfigs[0]) {
      loadCatalog(productConfigs[0].id);
    }
  }, [productConfigs, selectedCatalogId, loadCatalog]);

  const selectedCatalog = catalogWorkspace?.catalog || null;

  const comprehensivePackages = useMemo(() => {
    return (catalogWorkspace?.packages || [])
      .filter((p) => p && p.status === "active" && p.package_kind !== "addon_bundle")
      .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0));
  }, [catalogWorkspace]);

  const siblingPackageConfigs = useMemo(() => {
    if (!selectedCatalog || !selectedCatalog.package_id) return [];
    return (companyWorkspace?.catalogs || [])
      .filter((c) =>
        c.package &&
        c.package.package_kind === "comprehensive" &&
        (!selectedCatalog.vehicle_category_id || c.vehicle_category_id === selectedCatalog.vehicle_category_id) &&
        ((c.engine_type || "ice") === (selectedCatalog.engine_type || "ice")) &&
        (c.coverage_type_id === selectedCatalog.coverage_type_id || !c.coverage_type_id || !selectedCatalog.coverage_type_id)
      )
      .sort((a, b) => (a.package?.sort_order ?? 0) - (b.package?.sort_order ?? 0));
  }, [companyWorkspace, selectedCatalog]);

  const hasMultiCatalogPackages = comprehensivePackages.length <= 1 && siblingPackageConfigs.length > 1;

  const isPackaged = Boolean(selectedCatalog?.package_id || comprehensivePackages.length > 0 || siblingPackageConfigs.length > 0);

  const activePackage = useMemo(() => {
    if (!isPackaged) return null;
    if (hasMultiCatalogPackages) {
      const match = siblingPackageConfigs.find((c) => c.id === selectedCatalog?.id);
      if (match?.package) return match.package;
    }
    const found = comprehensivePackages.find(
      (p) =>
        (selectedPackageId && p.id === selectedPackageId) ||
        (selectedPackageKey && (p.package_key === selectedPackageKey || p.name === selectedPackageKey))
    );
    if (found) return found;
    const byCatalog = comprehensivePackages.find((p) => p.id === selectedCatalog?.package_id);
    return byCatalog || comprehensivePackages[0] || null;
  }, [comprehensivePackages, isPackaged, selectedPackageId, selectedPackageKey, selectedCatalog, hasMultiCatalogPackages, siblingPackageConfigs]);

  useEffect(() => {
    if (activePackage) {
      if (activePackage.id !== selectedPackageId) {
        setSelectedPackageId(activePackage.id);
      }
      const key = activePackage.package_key || activePackage.name;
      if (key && key !== selectedPackageKey) {
        setSelectedPackageKey(key);
      }
    }
  }, [activePackage, selectedPackageId, selectedPackageKey]);

  const allOfferings = useMemo(() => catalogWorkspace?.offerings || [], [catalogWorkspace]);

  const retiredConceptIdSet = useMemo(() => {
    const set = new Set<string>();
    for (const c of concepts) {
      if (c.status === "retired") set.add(c.id);
    }
    return set;
  }, [concepts]);

  const currentPackageOfferings = useMemo(() => {
    if (!selectedCatalog) return [];
    const targetPkgId = activePackage?.id;
    return (allOfferings || []).filter((item) => {
      if (!item || item.status === "retired") return false;
      if (item.concept?.status === "retired") return false;
      if (item.concept_id && retiredConceptIdSet.has(item.concept_id)) return false;
      if (isPackaged && targetPkgId) {
        return item.applies_to_id === targetPkgId;
      }
      return !item.applies_to_id || item.applies_to_id === selectedCatalog.product_id || item.applies_to_type === "product";
    });
  }, [allOfferings, selectedCatalog, isPackaged, activePackage, retiredConceptIdSet]);

  const defaultOfferings = useMemo(() => {
    return (currentPackageOfferings || [])
      .filter((item) => effectiveRole(item) === "included" && item.concept?.status !== "retired" && (!item.concept_id || !retiredConceptIdSet.has(item.concept_id)))
      .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || String(a.offering_key || "").localeCompare(String(b.offering_key || "")));
  }, [currentPackageOfferings, retiredConceptIdSet]);

  const addonOfferings = useMemo(() => {
    return (currentPackageOfferings || [])
      .filter((item) => effectiveRole(item) === "addon_option" && item.concept?.status !== "retired" && (!item.concept_id || !retiredConceptIdSet.has(item.concept_id)))
      .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || String(a.offering_key || "").localeCompare(String(b.offering_key || "")));
  }, [currentPackageOfferings, retiredConceptIdSet]);

  const activeConceptIdSet = useMemo(() => {
    const map = new Map<string, Offering>();
    for (const off of (currentPackageOfferings || [])) {
      if (off && off.concept_id) {
        map.set(off.concept_id, off);
      }
    }
    return map;
  }, [currentPackageOfferings]);

  const defaultConcepts = useMemo(() => {
    return concepts.filter((c) => {
      if (c.status === "retired") return false;
      if (enabledConceptIds && !enabledConceptIds.has(c.id)) return false;
      const offering = activeConceptIdSet.get(c.id);
      if (offering) {
        return effectiveRole(offering) === "included";
      }
      const cat = c.value_schema?.category || c.category || (c.sort_order && c.sort_order <= 11 ? "default" : "addon");
      return cat === "default";
    });
  }, [concepts, enabledConceptIds, activeConceptIdSet]);

  const addonConcepts = useMemo(() => {
    return concepts.filter((c) => {
      if (c.status === "retired") return false;
      if (enabledConceptIds && !enabledConceptIds.has(c.id)) return false;
      const offering = activeConceptIdSet.get(c.id);
      if (offering) {
        return effectiveRole(offering) === "addon_option";
      }
      const cat = c.value_schema?.category || c.category || (c.sort_order && c.sort_order <= 11 ? "default" : "addon");
      return cat === "addon";
    });
  }, [concepts, enabledConceptIds, activeConceptIdSet]);

  const bundles = useMemo(
    () => (catalogWorkspace?.packages || []).filter((item) => item && item.package_kind === "addon_bundle" && item.status === "active"),
    [catalogWorkspace]
  );

  const selectedCompany = useMemo(() => companies.find((item) => item.id === selectedCompanyId) || null, [companies, selectedCompanyId]);
  const selectedProduct = useMemo(() => companyWorkspace?.products.find((item) => item.id === selectedProductId) || null, [companyWorkspace, selectedProductId]);
  const selectedSegment = useMemo(() => segments.find((item) => item.id === selectedSegmentId) || null, [segments, selectedSegmentId]);
  const selectedVehicle = useMemo(() => vehicles.find((item) => item.id === selectedVehicleId) || null, [vehicles, selectedVehicleId]);
  const activeTemplate = useMemo(() => templates.find((t) => t.id === selectedTemplateId) || templates[0] || null, [templates, selectedTemplateId]);

  const previewVariableValues = useMemo(() => ({
    insurance_company: selectedCompany?.name || "Insurance Company",
    insurer_name: selectedCompany?.name || "Insurance Company",
    insurer: selectedCompany?.name || "Insurer",
    product_name: isPackaged && activePackage ? activePackage.name : (selectedProduct?.name || "Private Car Comprehensive"),
    vehicle_model: selectedVehicle?.name ? `${selectedVehicle.name} (${selectedSegment?.name || "Private"})` : "Perodua Myvi 1.5 AV (Auto)",
    vehicle_registration: "VAB 1234",
    quotation_reference: "RL-202609-00101",
    issue_date: new Date().toLocaleDateString("en-GB"),
    insured_name: "Ahmad Bin Abdullah",
    id_number: "900101-14-1234",
    postcode: "50480",
    coverage_type: "Comprehensive",
    sum_insured: "RM 55,000.00",
    total_premium: "RM 1,450.00",
  }), [selectedCompany, selectedProduct, selectedVehicle, selectedSegment, isPackaged, activePackage]);

  // Real template preview data (mirrors the sessions workspace benefit cards)
  const previewBenefitData = useMemo(
    () => ({
      current_benefits: defaultOfferings.map((o) => ({
        label: o.label_override || o.concept?.label || o.offering_key,
        value: o.display_value || "Included",
        description: (o.concept as any)?.description || "",
        asset_id: o.concept?.default_asset?.id || null,
        concept_key: o.concept?.concept_key || "",
        is_detected: false,
        price: o.optional_price,
        optional_price: o.optional_price,
        display_overrides: (o as any).display_overrides || {},
      })),
      available_addons: addonOfferings.map((o) => ({
        label: o.label_override || o.concept?.label || o.offering_key,
        value: o.display_value || "Optional",
        description: (o.concept as any)?.description || "",
        asset_id: o.concept?.default_asset?.id || null,
        concept_key: o.concept?.concept_key || "",
        is_detected: false,
        price: o.optional_price,
        optional_price: o.optional_price,
        display_overrides: (o as any).display_overrides || {},
      })),
      displayOptions: (activeTemplate as any)?.config?.display_options || (activeTemplate?.fixed_fields as any)?.display_options || {},
    }),
    [defaultOfferings, addonOfferings, activeTemplate]
  );

  const previewConceptAssets = useMemo(() => {
    const map: Record<string, string> = {};
    for (const c of concepts) {
      const url = c.default_asset?.url || (c.default_asset?.id ? `/business/assets/${c.default_asset.id}/content?profile=ui` : null);
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
  }, [concepts]);

  const previewTemplateElements = useMemo(
    () => (activeTemplate?.fixed_fields?.canvas?.elements || []).slice().sort((a, b) => (a.z || 1) - (b.z || 1)),
    [activeTemplate]
  );

  const previewTemplateAssets = useMemo(() => {
    if (!activeTemplate?.fixed_fields) return [];
    const list: Array<{ id: string; label: string; url: string }> = Object.entries(activeTemplate.fixed_fields.assets || {}).map(([key, id]) => ({
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
    for (const el of activeTemplate.fixed_fields.canvas?.elements || []) {
      if (el.assetId && !list.some((a) => a.id === el.assetId)) {
        list.push({
          id: el.assetId,
          label: el.name || "Asset",
          url: el.assetId.includes("-") ? `/business/assets/${el.assetId}/content?profile=ui` : `/template-assets/${el.assetId}`,
        });
      }
    }
    return list;
  }, [activeTemplate]);

  // ── 3. Effects ─────────────────────────────────────────────────────────
  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;
    loadReferenceData()
      .then((items) => {
        if (cancelled) return;
        const companyId = selectedCompanyId && items.some((item) => item.id === selectedCompanyId) ? selectedCompanyId : items[0]?.id || "";
        if (companyId) return loadCompany(companyId);
      })
      .catch((err) => !cancelled && setError(apiErrorMessage(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
      mountedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function refreshCurrent() {
    return loadCompany(selectedCompanyId, selectedProductId, selectedCatalogId);
  }

  function offeringTarget(): { applies_to_type: string | null; applies_to_id: string | null } {
    if (isPackaged) {
      const targetPkg = activePackage || comprehensivePackages[0];
      if (targetPkg) {
        return { applies_to_type: "package", applies_to_id: targetPkg.id };
      }
    }
    return { applies_to_type: selectedCatalog?.product_id ? "product" : null, applies_to_id: selectedCatalog?.product_id || null };
  }

  // ── 1-Click Fast Toggle Sticker Handler (Optimistic UI, Zero Reload) ───
  async function toggleConceptFast(concept: Concept, targetRole: "included" | "addon_option") {
    if (inFlightRef.current.has(concept.id)) {
      return;
    }
    inFlightRef.current.add(concept.id);

    enqueueTask(async () => {
      try {
        const currentWorkspace = catalogWorkspaceRef.current || catalogWorkspace;
        const currentCatalog = currentWorkspace?.catalog || selectedCatalog;
        if (!currentCatalog || !currentWorkspace) return;

        const target = offeringTarget();
        const targetPkgId = target.applies_to_id;
        const currentOfferings = currentWorkspace.offerings || [];
        const existing = currentOfferings.find((o) => {
          if (o.concept_id !== concept.id) return false;
          if (isPackaged && targetPkgId) return o.applies_to_id === targetPkgId;
          return !o.applies_to_id || o.applies_to_id === currentCatalog.product_id || o.applies_to_type === "product";
        });

        setSaving(true);
        setError("");

        if (existing) {
          // 1. Optimistic Delete (0ms delay)
          const prevWorkspace = currentWorkspace;
          const nextRevision = (currentCatalog.revision || 1) + 1;
          const updatedWorkspace: CatalogWorkspace = {
            ...currentWorkspace,
            catalog: { ...currentCatalog, revision: nextRevision },
            offerings: currentOfferings.filter((o) => o.id !== existing.id),
          };
          setCatalogWorkspace(updatedWorkspace);
          catalogWorkspaceRef.current = updatedWorkspace;
          catalogCacheRef.current.set(currentCatalog.id, { workspace: updatedWorkspace, ts: Date.now() });

          try {
            await api(`/business/catalogs/${currentCatalog.id}/offerings/${existing.id}?base_revision=${currentCatalog.revision}`, {
              method: "DELETE",
            });
          } catch (err) {
            // Rollback on error
            setCatalogWorkspace(prevWorkspace);
            catalogWorkspaceRef.current = prevWorkspace;
            catalogCacheRef.current.set(currentCatalog.id, { workspace: prevWorkspace, ts: Date.now() });
            setError(apiErrorMessage(err));
          }
        } else {
          // 2. Optimistic Add (0ms delay)
          const tempId = `temp-${Date.now()}`;
          const variantStr = concept.variants && concept.variants.length > 0 ? concept.variants[0] : "";
          const labelOverride = variantStr ? `${concept.label} (${variantStr})` : null;

          const optimisticOffering: Offering = {
            id: tempId,
            catalog_revision_id: currentWorkspace.active_revision.id,
            offering_key: `${concept.concept_key}-${Date.now()}`,
            concept_id: concept.id,
            offering_kind: targetRole === "included" ? "base" : "optional",
            applies_to_type: target.applies_to_type,
            applies_to_id: targetPkgId,
            role: targetRole,
            label_override: labelOverride,
            display_value: null,
            sort_order: currentPackageOfferings.length + 1,
            status: "active",
            source_aliases: [],
            source_citation: {},
            presentation_facet_ids: [],
            concept: concept,
          };

          const prevWorkspace = currentWorkspace;
          const nextRevision = (currentCatalog.revision || 1) + 1;
          const updatedWorkspace: CatalogWorkspace = {
            ...currentWorkspace,
            catalog: { ...currentCatalog, revision: nextRevision },
            offerings: [...currentOfferings, optimisticOffering],
          };
          setCatalogWorkspace(updatedWorkspace);
          catalogWorkspaceRef.current = updatedWorkspace;
          catalogCacheRef.current.set(currentCatalog.id, { workspace: updatedWorkspace, ts: Date.now() });

          const payload: Record<string, unknown> = {
            base_revision: currentCatalog.revision,
            offering_key: optimisticOffering.offering_key,
            concept_id: concept.id,
            offering_kind: targetRole === "included" ? "base" : "optional",
            applies_to_type: target.applies_to_type,
            applies_to_id: targetPkgId,
            role: targetRole,
            label_override: labelOverride,
            display_value: null,
            sort_order: currentPackageOfferings.length + 1,
            status: "active",
          };

          try {
            const res = await api<{ offering: Offering }>(`/business/catalogs/${currentCatalog.id}/offerings`, {
              method: "POST",
              body: JSON.stringify(payload),
            });
            const finalWorkspace: CatalogWorkspace = {
              ...updatedWorkspace,
              offerings: updatedWorkspace.offerings.map((o) => (o.id === tempId ? { ...res.offering, concept } : o)),
            };
            setCatalogWorkspace(finalWorkspace);
            catalogWorkspaceRef.current = finalWorkspace;
            catalogCacheRef.current.set(currentCatalog.id, { workspace: finalWorkspace, ts: Date.now() });
          } catch (err) {
            // Rollback on error
            setCatalogWorkspace(prevWorkspace);
            catalogWorkspaceRef.current = prevWorkspace;
            catalogCacheRef.current.set(currentCatalog.id, { workspace: prevWorkspace, ts: Date.now() });
            setError(apiErrorMessage(err));
          }
        }
      } finally {
        inFlightRef.current.delete(concept.id);
        setSaving(false);
      }
    });
  }

  // ── Plan Variant Switcher (Optimistic UI, Zero Reload) ─────────────────
  async function updatePlanVariantInline(offering: Offering, variant: string) {
    enqueueTask(async () => {
      const currentWorkspace = catalogWorkspaceRef.current || catalogWorkspace;
      const currentCatalog = currentWorkspace?.catalog || selectedCatalog;
      if (!currentCatalog || !currentWorkspace) return;
      setSaving(true);
      setError("");
      const concept = concepts.find((c) => c.id === offering.concept_id);
      const label = `${concept?.label || offering.offering_key} (${variant})`;
      const prevWorkspace = currentWorkspace;
      const nextRevision = (currentCatalog.revision || 1) + 1;

      const updatedWorkspace: CatalogWorkspace = {
        ...currentWorkspace,
        catalog: { ...currentCatalog, revision: nextRevision },
        offerings: currentWorkspace.offerings.map((o) => (o.id === offering.id ? { ...o, label_override: label } : o)),
      };
      setCatalogWorkspace(updatedWorkspace);
      catalogWorkspaceRef.current = updatedWorkspace;
      catalogCacheRef.current.set(currentCatalog.id, { workspace: updatedWorkspace, ts: Date.now() });

      try {
        const payload = {
          id: offering.id,
          offering_key: offering.offering_key,
          offering_kind: offering.offering_kind,
          concept_id: offering.concept_id,
          applies_to_type: offering.applies_to_type,
          applies_to_id: offering.applies_to_id,
          role: offering.role,
          base_revision: currentCatalog.revision,
          label_override: label,
        };
        await api(`/business/catalogs/${currentCatalog.id}/offerings`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } catch (err) {
        setCatalogWorkspace(prevWorkspace);
        catalogWorkspaceRef.current = prevWorkspace;
        catalogCacheRef.current.set(currentCatalog.id, { workspace: prevWorkspace, ts: Date.now() });
        setError(apiErrorMessage(err));
      } finally {
        setSaving(false);
      }
    });
  }

  const cleanCoverageValue = (val?: string | null) => {
    if (!val) return "";
    const s = String(val).trim();
    if (/\d/.test(s) || /^unlimited$/i.test(s)) {
      if (/^(?:included|optional|foc|as quoted|selected|standard)$/i.test(s)) return "";
      return s;
    }
    return "";
  };

  // ── Inline Display Value Editor (Optimistic UI, Zero Reload) ──────────
  async function updateOfferingValueInline(offering: Offering, newValue: string) {
    enqueueTask(async () => {
      const currentWorkspace = catalogWorkspaceRef.current || catalogWorkspace;
      const currentCatalog = currentWorkspace?.catalog || selectedCatalog;
      if (!currentCatalog || !currentWorkspace) return;
      setSaving(true);
      setError("");
      const prevWorkspace = currentWorkspace;
      const trimmed = newValue.trim();
      const isValid = Boolean(trimmed && (/\d/.test(trimmed) || /^unlimited$/i.test(trimmed)) && !/^(?:included|optional|foc|as quoted|selected|standard)$/i.test(trimmed));
      const cleanVal = isValid ? trimmed : null;
      const nextRevision = (currentCatalog.revision || 1) + 1;

      const updatedWorkspace: CatalogWorkspace = {
        ...currentWorkspace,
        catalog: { ...currentCatalog, revision: nextRevision },
        offerings: currentWorkspace.offerings.map((o) => (o.id === offering.id ? { ...o, display_value: cleanVal } : o)),
      };
      setCatalogWorkspace(updatedWorkspace);
      catalogWorkspaceRef.current = updatedWorkspace;
      catalogCacheRef.current.set(currentCatalog.id, { workspace: updatedWorkspace, ts: Date.now() });

      try {
        const payload = {
          id: offering.id,
          offering_key: offering.offering_key,
          offering_kind: offering.offering_kind,
          concept_id: offering.concept_id,
          applies_to_type: offering.applies_to_type,
          applies_to_id: offering.applies_to_id,
          role: offering.role,
          base_revision: currentCatalog.revision,
          display_value: cleanVal,
          typed_value: cleanVal ? { type: "custom", display_text: cleanVal } : null,
        };
        await api(`/business/catalogs/${currentCatalog.id}/offerings`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } catch (err) {
        setCatalogWorkspace(prevWorkspace);
        catalogWorkspaceRef.current = prevWorkspace;
        catalogCacheRef.current.set(currentCatalog.id, { workspace: prevWorkspace, ts: Date.now() });
        setError(apiErrorMessage(err));
      } finally {
        setSaving(false);
      }
    });
  }

  // ── Inline Price / Cost Editor (Optimistic UI, Zero Reload) ───────────
  async function updateOfferingPriceInline(offering: Offering, newPriceStr: string) {
    enqueueTask(async () => {
      const currentWorkspace = catalogWorkspaceRef.current || catalogWorkspace;
      const currentCatalog = currentWorkspace?.catalog || selectedCatalog;
      if (!currentCatalog || !currentWorkspace) return;
      setSaving(true);
      setError("");
      const prevWorkspace = currentWorkspace;
      const trimmed = newPriceStr.trim();
      let priceObj: any = null;
      if (trimmed.includes("%")) {
        priceObj = { type: "formula", formula: trimmed, display_text: trimmed };
      } else {
        const cleanStr = trimmed.replace(/RM/i, "").replace(/,/g, "").trim();
        const num = cleanStr ? parseFloat(cleanStr) : null;
        priceObj = num !== null && !isNaN(num) && num > 0 ? { type: "money", value: num, currency: "MYR" } : null;
      }
      const nextRevision = (currentCatalog.revision || 1) + 1;

      const updatedWorkspace: CatalogWorkspace = {
        ...currentWorkspace,
        catalog: { ...currentCatalog, revision: nextRevision },
        offerings: currentWorkspace.offerings.map((o) => (o.id === offering.id ? { ...o, optional_price: priceObj } : o)),
      };
      setCatalogWorkspace(updatedWorkspace);
      catalogWorkspaceRef.current = updatedWorkspace;
      catalogCacheRef.current.set(currentCatalog.id, { workspace: updatedWorkspace, ts: Date.now() });

      try {
        const payload = {
          id: offering.id,
          offering_key: offering.offering_key,
          offering_kind: offering.offering_kind,
          concept_id: offering.concept_id,
          applies_to_type: offering.applies_to_type,
          applies_to_id: offering.applies_to_id,
          role: offering.role,
          base_revision: currentCatalog.revision,
          display_value: offering.display_value || undefined,
          typed_value: offering.typed_value || undefined,
          optional_price: priceObj,
        };
        await api(`/business/catalogs/${currentCatalog.id}/offerings`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } catch (err) {
        setCatalogWorkspace(prevWorkspace);
        catalogWorkspaceRef.current = prevWorkspace;
        catalogCacheRef.current.set(currentCatalog.id, { workspace: prevWorkspace, ts: Date.now() });
        setError(apiErrorMessage(err));
      } finally {
        setSaving(false);
      }
    });
  }

  // ── Inline Short Description Editor (Optimistic UI, Zero Reload) ───────────
  async function updateOfferingDescriptionInline(offering: Offering, newDesc: string) {
    enqueueTask(async () => {
      const currentWorkspace = catalogWorkspaceRef.current || catalogWorkspace;
      const currentCatalog = currentWorkspace?.catalog || selectedCatalog;
      if (!currentCatalog || !currentWorkspace) return;
      setSaving(true);
      setError("");
      const prevWorkspace = currentWorkspace;
      const cleanDesc = newDesc && newDesc.trim().length > 0 ? newDesc.trim() : null;
      const nextRevision = (currentCatalog.revision || 1) + 1;

      const updatedWorkspace: CatalogWorkspace = {
        ...currentWorkspace,
        catalog: { ...currentCatalog, revision: nextRevision },
        offerings: currentWorkspace.offerings.map((o) => (o.id === offering.id ? { ...o, description_override: cleanDesc } : o)),
      };
      setCatalogWorkspace(updatedWorkspace);
      catalogWorkspaceRef.current = updatedWorkspace;
      catalogCacheRef.current.set(currentCatalog.id, { workspace: updatedWorkspace, ts: Date.now() });

      try {
        const payload = {
          id: offering.id,
          offering_key: offering.offering_key,
          offering_kind: offering.offering_kind,
          concept_id: offering.concept_id,
          applies_to_type: offering.applies_to_type,
          applies_to_id: offering.applies_to_id,
          role: offering.role,
          base_revision: currentCatalog.revision,
          display_value: offering.display_value || undefined,
          typed_value: offering.typed_value || undefined,
          optional_price: offering.optional_price || undefined,
          description_override: cleanDesc,
        };
        await api(`/business/catalogs/${currentCatalog.id}/offerings`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } catch (err) {
        setCatalogWorkspace(prevWorkspace);
        catalogWorkspaceRef.current = prevWorkspace;
        catalogCacheRef.current.set(currentCatalog.id, { workspace: prevWorkspace, ts: Date.now() });
        setError(apiErrorMessage(err));
      } finally {
        setSaving(false);
      }
    });
  }

  async function resetToDefaultOfferings() {
    if (!selectedCatalog || !selectedCompany) return;
    setSaving(true);
    setError("");
    try {
      await loadCompany(selectedCompanyId, selectedProductId, selectedCatalogId);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function createConfig() {
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {
        company_id: selectedCompanyId,
        product_id: selectedProductId || null,
        name: formName.trim() || `${selectedProduct?.name || "Product"} · ${selectedVehicle?.name || "Vehicle"}`,
        segment_id: selectedSegmentId || null,
        vehicle_category_id: selectedVehicleId || null,
        engine_type: selectedEngineType || "ice",
      };
      const config = await api<{ catalog: Catalog }>("/business/catalogs", { method: "POST", body: JSON.stringify(payload) });
      const configId = config.catalog.id;
      if (formAsPackage && formPackageName.trim()) {
        await api(`/business/catalogs/${configId}/packages`, {
          method: "POST",
          body: JSON.stringify({
            base_revision: 1,
            name: formPackageName.trim(),
            package_key: formPackageKey.trim() || undefined,
            ...(builderCoverageFilter === "tpft"
              ? { package_kind: "tpft" }
              : builderCoverageFilter === "tpo"
              ? { package_kind: "tpo" }
              : { package_kind: "comprehensive" }),
          }),
        });
      }
      setDialog(null);
      await loadCompany(selectedCompanyId, selectedProductId, configId);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function publishConfig() {
    if (!selectedCatalog) return;
    setSaving(true);
    setError("");
    try {
      await api(`/business/catalogs/${selectedCatalog.id}/publish`, { method: "POST", body: JSON.stringify({ base_revision: selectedCatalog.revision }) });
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function openNewDraft() {
    if (!selectedCatalog) return;
    setSaving(true);
    setError("");
    try {
      await api(`/business/catalogs/${selectedCatalog.id}/new-draft`, { method: "POST", body: JSON.stringify({ base_revision: selectedCatalog.revision }) });
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function createBundle() {
    if (!selectedCatalog) return;
    setSaving(true);
    setError("");
    try {
      await api(`/business/catalogs/${selectedCatalog.id}/packages`, {
        method: "POST",
        body: JSON.stringify({ base_revision: selectedCatalog.revision, name: formName.trim(), package_key: formPackageKey.trim() || undefined, package_kind: "addon_bundle" }),
      });
      setDialog(null);
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  // ── Package Plan Manager (ladder variants of an add-on bundle) ────────
  async function createPlan(bundle: Package) {
    if (!selectedCatalog) return;
    const name = planFormName.trim();
    if (!name) {
      setError("Enter a plan name (e.g. Driver Protection Plan A).");
      return;
    }
    setPlanSaving(true);
    setError("");
    try {
      await api(`/business/catalogs/${selectedCatalog.id}/packages/${bundle.id}/plans`, {
        method: "POST",
        body: JSON.stringify({ base_revision: selectedCatalog.revision, name }),
      });
      setPlanFormName("");
      setExpandedPlanId(bundle.id);
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setPlanSaving(false);
    }
  }

  async function retirePlan(bundle: Package, plan: Record<string, unknown>) {
    if (!selectedCatalog) return;
    if (!window.confirm(`Retire plan "${plan.name}"? Existing quotations keep their pinned revision.`)) return;
    setPlanSaving(true);
    setError("");
    try {
      await api(`/business/catalogs/${selectedCatalog.id}/packages/${bundle.id}/plans/${plan.id}`, { method: "DELETE" });
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setPlanSaving(false);
    }
  }

  async function addPlanItem(bundle: Package, plan: Record<string, unknown>) {
    if (!selectedCatalog) return;
    if (!planMemberOfferingId) {
      setError("Choose a benefit offering to add to this plan.");
      return;
    }
    setPlanSaving(true);
    setError("");
    try {
      const items = planItemsFor(plan).map((item) => ({
        offering_id: item.offering_id,
        typed_value_override: item.typed_value_override || null,
        sort_order: item.sort_order || 0,
      }));
      items.push({ offering_id: planMemberOfferingId, typed_value_override: parseOverride(), sort_order: items.length });
      await api(`/business/catalogs/${selectedCatalog.id}/packages/${bundle.id}/plans/${plan.id}/items`, {
        method: "PUT",
        body: JSON.stringify({ base_revision: selectedCatalog.revision, items }),
      });
      setPlanMemberOfferingId("");
      setPlanMemberOverride("");
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setPlanSaving(false);
    }
  }

  async function removePlanItem(bundle: Package, plan: Record<string, unknown>, item: Record<string, unknown>) {
    if (!selectedCatalog) return;
    setPlanSaving(true);
    setError("");
    try {
      const items = planItemsFor(plan)
        .filter((entry) => entry.id !== item.id)
        .map((entry, index) => ({
          offering_id: entry.offering_id,
          typed_value_override: entry.typed_value_override || null,
          sort_order: index,
        }));
      await api(`/business/catalogs/${selectedCatalog.id}/packages/${bundle.id}/plans/${plan.id}/items`, {
        method: "PUT",
        body: JSON.stringify({ base_revision: selectedCatalog.revision, items }),
      });
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setPlanSaving(false);
    }
  }

  async function updatePlanItemOverride(bundle: Package, plan: Record<string, unknown>, item: Record<string, unknown>, override: string) {
    if (!selectedCatalog) return;
    setPlanSaving(true);
    setError("");
    try {
      const items = planItemsFor(plan).map((entry) => ({
        offering_id: entry.offering_id,
        typed_value_override: entry.id === item.id ? parseOverride(override) : entry.typed_value_override || null,
        sort_order: entry.sort_order || 0,
      }));
      await api(`/business/catalogs/${selectedCatalog.id}/packages/${bundle.id}/plans/${plan.id}/items`, {
        method: "PUT",
        body: JSON.stringify({ base_revision: selectedCatalog.revision, items }),
      });
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setPlanSaving(false);
    }
  }

  function parseOverride(raw?: string): Record<string, unknown> | null {
    const text = (raw ?? planMemberOverride).trim();
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch {
      return { type: "text", display_text: text, value: text };
    }
  }

  function formatOverrideDisplay(override: any): string {
    if (!override) return "";
    if (typeof override === "string") return override;
    if (override.display_text) return String(override.display_text);
    if (override.value !== undefined) return String(override.value);
    return JSON.stringify(override);
  }

  function plansFor(bundle: Package): Array<Record<string, any>> {
    return (catalogWorkspace?.plans || [])
      .filter((plan) => plan.package_id === bundle.id && plan.status !== "retired")
      .sort((a, b) => (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0));
  }

  function planItemsFor(plan: Record<string, any>): Array<Record<string, any>> {
    return (catalogWorkspace?.plan_items || [])
      .filter((item) => item.plan_id === plan.id)
      .sort((a, b) => (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0));
  }

  function offeringLabel(offeringId: string): string {
    const offering = (catalogWorkspace?.offerings || []).find((item) => item.id === offeringId);
    if (!offering) return offeringId;
    const concept = (catalogWorkspace?.offerings || []).find((item) => item.id === offeringId)?.concept;
    return offering.label_override || concept?.label || offering.offering_key || offeringId;
  }

  function bundleMemberOptions(bundle: Package): Offering[] {
    return (catalogWorkspace?.offerings || []).filter((item) => {
      if (!item || item.status === "retired") return false;
      return true;
    });
  }

  async function clonePackage() {
    if (!selectedCatalog) return;
    setSaving(true);
    setError("");
    try {
      const sourcePackage = activePackage || selectedCatalog.package;
      if (!sourcePackage) {
        setError("This configuration has no package to clone.");
        return;
      }
      const target = await api<{ catalog: Catalog }>("/business/catalogs", {
        method: "POST",
        body: JSON.stringify({
          company_id: selectedCompanyId,
          product_id: selectedProductId || null,
          name: `${formName.trim()} · ${selectedVehicle?.name || "Vehicle"}`,
          segment_id: selectedCatalog.segment_id || selectedSegmentId || null,
          vehicle_category_id: selectedCatalog.vehicle_category_id || selectedVehicleId || null,
        }),
      });
      await api(`/business/catalogs/${target.catalog.id}/packages/${sourcePackage.id}/clone`, {
        method: "POST",
        body: JSON.stringify({ base_revision: 1, name: formName.trim(), package_key: formPackageKey.trim() || undefined }),
      });
      setDialog(null);
      await loadCompany(selectedCompanyId, selectedProductId, target.catalog.id);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function renamePackage(pkg: Package | PackageSummary) {
    if (!selectedCatalog) return;
    const next = window.prompt("Rename bundle / package", pkg.name);
    if (!next || !next.trim() || next.trim() === pkg.name) return;
    setSaving(true);
    setError("");
    try {
      await api(`/business/catalogs/${selectedCatalog.id}/packages/${pkg.id}`, {
        method: "PUT",
        body: JSON.stringify({
          base_revision: selectedCatalog.revision,
          name: next.trim(),
          package_key: pkg.package_key || undefined,
          package_kind: pkg.package_kind,
          sort_order: pkg.sort_order || 0,
          status: pkg.status || "active",
        }),
      });
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function retireBundle(bundle: Package) {
    if (!selectedCatalog) return;
    if (!window.confirm(`Retire bundle "${bundle.name}" and all its plans? Existing quotations keep their pinned revision.`)) return;
    setSaving(true);
    setError("");
    try {
      await api(`/business/catalogs/${selectedCatalog.id}/packages/${bundle.id}`, { method: "DELETE" });
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function renamePlan(bundle: Package, plan: Record<string, any>) {
    if (!selectedCatalog) return;
    const next = window.prompt("Rename plan", plan.name);
    if (!next || !next.trim() || next.trim() === plan.name) return;
    setPlanSaving(true);
    setError("");
    try {
      await api(`/business/catalogs/${selectedCatalog.id}/packages/${bundle.id}/plans/${plan.id}`, {
        method: "PUT",
        body: JSON.stringify({
          base_revision: selectedCatalog.revision,
          name: next.trim(),
          plan_key: plan.plan_key || undefined,
          sort_order: plan.sort_order || 0,
          status: plan.status || "active",
        }),
      });
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setPlanSaving(false);
    }
  }

  async function retireCatalog(catalog: Catalog) {
    if (!window.confirm(`Retire catalog "${catalog.name}"? It will be archived and hidden from the active builder.`)) return;
    setSaving(true);
    setError("");
    try {
      await api(`/business/catalogs/${catalog.id}`, { method: "DELETE" });
      await loadCompany(selectedCompanyId, selectedProductId);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <AppShell>
        <BuilderNav />
        <div className="flex min-h-[calc(100vh-120px)] items-center justify-center">
          <PageLoading />
        </div>
      </AppShell>
    );
  }

  // ── Template Canvas Dimensions ──
  const canvasW = 794;
  const canvasH = 1123;

  return (
    <AppShell>
      <BuilderNav />

      {/* ── Top Calm Apple Header ─────────────────────────────────────── */}
      <div className="border-b border-[var(--rl-border)] bg-[var(--rl-surface)] px-6 py-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--rl-text-muted)]">
              <span>Builder</span>
              <CaretRight size={12} weight="bold" />
              <span>Product Benefits Configuration</span>
            </div>
            <h1 className="mt-0.5 text-xl font-bold tracking-tight text-[var(--rl-text-strong)]">
              Benefits & Add-ons Architecture
            </h1>
            <p className="text-xs text-[var(--rl-text-muted)]">
              Fast, mouse-driven benefit allocation for motor comprehensive products and packages.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* View Switcher: 4 Tabs */}
            <div className="flex items-center rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-0.5 text-xs font-semibold">
              <button
                type="button"
                onClick={() => {
                  setScreenTab("company_benefits");
                  if (selectedCompanyId && selectedProfileId) loadCompanyConfigs(selectedCompanyId, selectedProfileId);
                }}
                className={`flex items-center gap-1.5 rounded-[3px] px-3 py-1.5 transition-all ${
                  screenTab === "company_benefits"
                    ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] shadow-sm font-bold border border-[var(--rl-border)]"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                <Buildings size={14} weight={screenTab === "company_benefits" ? "bold" : "regular"} />
                <span>1. Company Benefits</span>
              </button>
              <button
                type="button"
                onClick={() => setScreenTab("catalogs")}
                className={`flex items-center gap-1.5 rounded-[3px] px-3 py-1.5 transition-all ${
                  screenTab === "catalogs"
                    ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] shadow-sm font-bold border border-[var(--rl-border)]"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                <TreeStructure size={14} weight={screenTab === "catalogs" ? "bold" : "regular"} />
                <span>2. Company Catalogs</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setScreenTab("conditions");
                  if (selectedCompanyId && selectedProfileId) loadCompanyConditions(selectedCompanyId, selectedProfileId);
                }}
                className={`flex items-center gap-1.5 rounded-[3px] px-3 py-1.5 transition-all ${
                  screenTab === "conditions"
                    ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] shadow-sm font-bold border border-[var(--rl-border)]"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                <Lightning size={14} weight={screenTab === "conditions" ? "bold" : "regular"} />
                <span>3. Benefit Conditions</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setScreenTab("matrix");
                  if (selectedCompanyId) loadMatrix(selectedCompanyId);
                }}
                className={`flex items-center gap-1.5 rounded-[3px] px-3 py-1.5 transition-all ${
                  screenTab === "matrix"
                    ? "bg-[var(--rl-black)] text-white shadow-sm font-bold"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                <Table size={14} weight={screenTab === "matrix" ? "bold" : "regular"} />
                <span>4. Overview Matrix</span>
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-3 flex items-center justify-between rounded-[var(--rl-radius-sm)] border border-[var(--rl-red)] bg-[var(--rl-red-light)] px-3.5 py-2 text-xs text-[var(--rl-red)]">
            <span>{error}</span>
            <button onClick={() => setError("")} className="hover:opacity-80">
              <X size={14} />
            </button>
          </div>
        )}

        {/* ── Apple-Style Step Flow Navigator ─────────────────────────── */}
        <BenefitsStepNavigator
          companies={companies}
          selectedCompanyId={selectedCompanyId}
          selectedCompany={selectedCompany}
          companyWorkspace={companyWorkspace}
          loadCompany={loadCompany}
          profiles={profiles}
          profilesLoading={profilesLoading}
          selectedProfileId={selectedProfileId}
          setSelectedProfileId={setSelectedProfileId}
          selectedProfile={selectedProfile}
          companyConfigs={companyConfigs}
          companyConditions={companyConditions}
          loadCompanyConfigs={loadCompanyConfigs}
          loadCompanyConditions={loadCompanyConditions}
          profileActionLoading={profileActionLoading}
          handleActivateProfile={handleActivateProfile}
          handleDeleteDraftProfile={handleDeleteDraftProfile}
          setCloneName={setCloneName}
          setCloneNotes={setCloneNotes}
          setCloneModalOpen={setCloneModalOpen}
          screenTab={screenTab}
          segments={segments}
          selectedSegmentId={selectedSegmentId}
          setSelectedSegmentId={setSelectedSegmentId}
          selectedEngineType={selectedEngineType}
          setSelectedEngineType={setSelectedEngineType}
          vehicles={vehicles}
          selectedVehicleId={selectedVehicleId}
          setSelectedVehicleId={setSelectedVehicleId}
          builderCoverageFilter={builderCoverageFilter}
          setBuilderCoverageFilter={setBuilderCoverageFilter}
          productConfigs={productConfigs}
          selectedCatalogId={selectedCatalogId}
          loadCatalog={loadCatalog}
          fileUrl={fileUrl}
        />
      </div>

      {/* ── Main Workspace Body ────────────────────────────────────────── */}
      <div className="p-6">
        {screenTab === "company_benefits" ? (
          <CompanyBenefitsTab
            selectedProfile={selectedProfile}
            isProfileArchived={isProfileArchived}
            selectedCompany={selectedCompany}
            concepts={concepts}
            companyConfigs={companyConfigs}
            configsLoading={configsLoading}
            configsSaving={configsSaving}
            configsSearch={configsSearch}
            setConfigsSearch={setConfigsSearch}
            configsCategoryFilter={configsCategoryFilter}
            setConfigsCategoryFilter={setConfigsCategoryFilter}
            setAllConfigsEnabled={setAllConfigsEnabled}
            saveCompanyConfigs={saveCompanyConfigs}
            customizingCostIds={customizingCostIds}
            setCustomizingCostIds={setCustomizingCostIds}
            toggleConfigEnabled={toggleConfigEnabled}
            updateConfigBaseline={updateConfigBaseline}
            updateConfigBaselineCost={updateConfigBaselineCost}
          />
        ) : screenTab === "conditions" ? (
          <BenefitConditionsTab
            isProfileArchived={isProfileArchived}
            selectedProfile={selectedProfile}
            selectedCompany={selectedCompany}
            companyConditions={companyConditions}
            conditionsLoading={conditionsLoading}
            concepts={concepts}
            onOpenAddConditionDialog={() => setConditionDialog(true)}
            onQuickCreateUnlimitedTowingRule={() => {
              setCondFormName("DPP -> Unlimited Towing Upgrade");
              const dpp = concepts.find((c) => c.concept_key === "driver_passenger_protection");
              const towing = concepts.find((c) => c.concept_key === "towing_assistance" || c.concept_key === "breakdown_assist");
              if (dpp) setCondTriggerId(dpp.id);
              if (towing) setCondTargetId(towing.id);
              setCondActionType("replace_description");
              setCondReplacement("Unlimited towing distance within Malaysia");
              setConditionDialog(true);
            }}
            onDeleteCondition={deleteCompanyCondition}
          />
        ) : screenTab === "matrix" ? (
          <OverviewMatrixTab
            matrixData={matrixData}
            matrixLoading={matrixLoading}
            matrixFilterCoverage={matrixFilterCoverage}
            setMatrixFilterCoverage={setMatrixFilterCoverage}
            matrixSearch={matrixSearch}
            setMatrixSearch={setMatrixSearch}
            downloadDocx={downloadDocx}
            downloadXlsx={downloadXlsx}
            editingMatrixItem={editingMatrixItem}
            setEditingMatrixItem={setEditingMatrixItem}
            saveMatrixInlineEdit={saveMatrixInlineEdit}
          />
        ) : workspaceLoading ? (
          <PageLoading />
        ) : !selectedCatalog ? (
          <div className="grid min-h-[360px] place-items-center rounded-[var(--rl-radius)] border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface)] p-8 text-center">
            <div className="max-w-md">
              <TreeStructure size={36} className="mx-auto text-[var(--rl-text-muted)] opacity-60" />
              <h2 className="mt-3 text-base font-bold text-[var(--rl-text-strong)]">
                Select an Insurer and Product to Configure
              </h2>
              <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                Choose one of the insurance companies above to load confirmed default benefits and available add-ons.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* ── Catalog Toolbar: Actions & Publication ───────────────────── */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3.5 shadow-sm">
              <div className="flex items-center gap-2 text-xs">
                <span className="font-bold text-[var(--rl-text-strong)]">
                  {selectedCatalog?.name || "Product Catalog"}
                </span>
                {catalogWorkspace?.active_revision && (
                  <Badge variant={catalogWorkspace.active_revision.state === "published" ? "success" : "default"}>
                    Rev {catalogWorkspace.active_revision.revision_number} ({catalogWorkspace.active_revision.state})
                  </Badge>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowLiveTemplate(!showLiveTemplate)}
                  className="gap-1.5 text-xs h-8"
                >
                  {showLiveTemplate ? <EyeSlash size={14} weight="bold" /> : <Eye size={14} weight="bold" />}
                  <span>{showLiveTemplate ? "Hide Template Preview" : "Live Template Preview"}</span>
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={refreshCurrent}
                  disabled={workspaceLoading || saving}
                  className="gap-1.5 text-xs h-8"
                >
                  <ArrowClockwise size={14} className={workspaceLoading ? "animate-spin" : ""} />
                  <span>Refresh</span>
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setFormName("");
                    setFormPackageName("");
                    setFormAsPackage(false);
                    setDialog("config");
                  }}
                  className="gap-1.5 text-xs h-8"
                >
                  <Plus size={14} weight="bold" />
                  <span>Add configuration</span>
                </Button>
                {isPackaged && activePackage && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setFormName(`${activePackage.name} Copy`);
                      setFormPackageKey("");
                      setDialog("clone");
                    }}
                    className="gap-1.5 text-xs h-8"
                  >
                    <Copy size={14} />
                    <span>Clone package</span>
                  </Button>
                )}
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setFormName("");
                    setFormPackageKey("");
                    setDialog("bundle");
                  }}
                  className="gap-1.5 text-xs h-8"
                >
                  <PackageIcon size={14} />
                  <span>New bundle</span>
                </Button>
                <GuidedTour
                  storageKey="tour:builder-benefits"
                  title="Benefits & Add-ons Architecture"
                  description="Configure which global benefits each insurer product includes by default and offers as add-ons, build package tiers, and create add-on bundles with plan levels."
                  steps={BENEFITS_TOUR_STEPS}
                />
                {selectedCatalog && (
                  (catalogWorkspace?.active_revision?.state === "published" && selectedCatalog.status === "published") ? (
                    <Button variant="secondary" size="sm" onClick={openNewDraft} disabled={saving} className="gap-1.5 text-xs h-8">
                      <PencilSimple size={14} weight="bold" />
                      <span>New draft</span>
                    </Button>
                  ) : (
                    <Button size="sm" onClick={publishConfig} disabled={saving} className="gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm font-semibold text-xs h-8">
                      <CheckCircle size={14} weight="bold" />
                      <span>Publish Changes</span>
                    </Button>
                  )
                )}
              </div>
            </div>

            {/* ── Package Tier Ladder (For Package System) ────────────────── */}
            {isPackaged && (comprehensivePackages.length > 0 || hasMultiCatalogPackages) && (
              <div className="rl-tour-ladder rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                      Package Tier Ladder ({hasMultiCatalogPackages ? siblingPackageConfigs.length : comprehensivePackages.length} Tiers)
                    </h3>
                    <p className="text-[11px] text-[var(--rl-text-muted)]">
                      Click any tier below to instantly switch package view. Tier 1 has minimal defaults, progressing to Top Tier with all defaults.
                    </p>
                  </div>
                  <span className="rounded-full bg-[var(--rl-bg)] border border-[var(--rl-border)] px-2.5 py-1 text-[10px] font-semibold text-[var(--rl-text-muted)]">
                    Instant Zero-Reload Switching
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {hasMultiCatalogPackages
                    ? siblingPackageConfigs.map((cfg, idx) => {
                        const isCurrent = cfg.id === selectedCatalogId;
                        const isTopTier = idx === siblingPackageConfigs.length - 1;
                        const pkgName = cfg.package?.name || cfg.name;
                        const defCount = isCurrent ? defaultOfferings.length : null;
                        const addCount = isCurrent ? addonOfferings.length : null;

                        return (
                          <button
                            key={cfg.id}
                            onClick={() => loadCatalog(cfg.id)}
                            className={`flex flex-col justify-between rounded-[var(--rl-radius-sm)] border p-3.5 text-left transition-all ${
                              isCurrent
                                ? "border-[var(--rl-black)] bg-[var(--rl-bg)] shadow-md ring-2 ring-[var(--rl-black)]"
                                : "border-[var(--rl-border)] bg-[var(--rl-surface)] opacity-80 hover:opacity-100 hover:border-[var(--rl-text-muted)]"
                            }`}
                          >
                            <div>
                              <div className="flex items-center justify-between">
                                <span className="rounded-[4px] bg-[var(--rl-surface)] border border-[var(--rl-border)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--rl-text-muted)]">
                                  Tier {idx + 1} {isTopTier ? "· Top Tier" : idx === 0 ? "· Base Tier" : ""}
                                </span>
                                {isCurrent && (
                                  <span className="flex items-center gap-1 text-[11px] font-bold text-[var(--rl-black)]">
                                    <Check size={12} weight="bold" /> Active
                                  </span>
                                )}
                              </div>
                              <h4 className="mt-2 font-bold text-xs text-[var(--rl-text-strong)]">{pkgName}</h4>
                            </div>
                            <div className="mt-3 pt-2 border-t border-[var(--rl-border)] flex items-center justify-between text-[11px]">
                              {isCurrent ? (
                                <>
                                  <span className="font-semibold text-emerald-700">{defCount} Defaults</span>
                                  <span className={`font-semibold ${addCount === 0 ? "text-[var(--rl-text-muted)] italic" : "text-blue-700"}`}>
                                    {addCount === 0 ? "0 Add-ons" : `${addCount} Add-ons`}
                                  </span>
                                </>
                              ) : (
                                <span className="text-[10px] text-[var(--rl-text-muted)] italic">
                                  Click to view tier benefits
                                </span>
                              )}
                            </div>
                          </button>
                        );
                      })
                    : comprehensivePackages.map((pkg, idx) => {
                        const isCurrent = pkg.id === (activePackage?.id || selectedPackageId);
                        const pkgOfferings = allOfferings.filter((o) => o.status !== "retired" && o.applies_to_id === pkg.id);
                        const defCount = pkgOfferings.filter((o) => effectiveRole(o) === "included").length;
                        const addCount = pkgOfferings.filter((o) => effectiveRole(o) === "addon_option").length;
                        const isTopTier = idx === comprehensivePackages.length - 1;

                        return (
                          <button
                            key={pkg.id}
                            onClick={() => {
                              setSelectedPackageId(pkg.id);
                              setSelectedPackageKey(pkg.package_key || pkg.name);
                            }}
                            className={`flex flex-col justify-between rounded-[var(--rl-radius-sm)] border p-3.5 text-left transition-all ${isCurrent
                              ? "border-[var(--rl-black)] bg-[var(--rl-bg)] shadow-md ring-2 ring-[var(--rl-black)]"
                              : "border-[var(--rl-border)] bg-[var(--rl-surface)] opacity-80 hover:opacity-100 hover:border-[var(--rl-text-muted)]"
                              }`}
                          >
                            <div>
                              <div className="flex items-center justify-between">
                                <span className="rounded-[4px] bg-[var(--rl-surface)] border border-[var(--rl-border)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--rl-text-muted)]">
                                  Tier {idx + 1} {isTopTier ? "· Top Tier" : idx === 0 ? "· Base Tier" : ""}
                                </span>
                                {isCurrent && (
                                  <span className="flex items-center gap-1 text-[11px] font-bold text-[var(--rl-black)]">
                                    <Check size={12} weight="bold" /> Active
                                  </span>
                                )}
                              </div>
                              <h4 className="mt-2 font-bold text-xs text-[var(--rl-text-strong)]">{pkg.name}</h4>
                            </div>
                            <div className="mt-3 pt-2 border-t border-[var(--rl-border)] flex items-center justify-between text-[11px]">
                              <span className="font-semibold text-emerald-700">{defCount} Defaults</span>
                              <span className={`font-semibold ${addCount === 0 ? "text-[var(--rl-text-muted)] italic" : "text-blue-700"}`}>
                                {addCount === 0 ? "0 Add-ons" : `${addCount} Add-ons`}
                              </span>
                            </div>
                          </button>
                        );
                      })}
                </div>
              </div>
            )}

            {/* ── Summary & Quick Actions Strip ────────────────────────── */}
            <div className="flex flex-wrap items-center justify-between rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-sm gap-4">
              <div className="flex items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-[var(--rl-radius-sm)] bg-[var(--rl-bg)] border border-[var(--rl-border)] p-1 shrink-0">
                  {selectedCompany?.logo?.url ? (
                    <img src={fileUrl(selectedCompany.logo.url)} alt={selectedCompany.name} loading="lazy" className="h-full w-full object-contain" />
                  ) : (
                    <Buildings size={20} className="text-[var(--rl-text-strong)]" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-[var(--rl-text-strong)]">
                      {isPackaged && activePackage ? activePackage.name : selectedCatalog.name}
                    </h2>
                    {isPackaged && activePackage && comprehensivePackages.findIndex((p) => p.id === activePackage.id) >= 0 && (
                      <span className="rounded-[4px] bg-[var(--rl-black)] text-white px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider">
                        Tier {comprehensivePackages.findIndex((p) => p.id === activePackage.id) + 1} of {comprehensivePackages.length}
                      </span>
                    )}
                    {isPackaged && activePackage && (
                      <button
                        type="button"
                        onClick={() => renamePackage(activePackage)}
                        className="flex items-center gap-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)] hover:text-[var(--rl-text-strong)]"
                        title="Rename this tier"
                      >
                        <PencilSimple size={12} weight="bold" /> Rename
                      </button>
                    )}
                  </div>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    {selectedCompany?.name} · {selectedSegment?.name || "Private"} · {selectedVehicle?.name || "Car"} ·{" "}
                    {isPackaged ? "Package System" : "Add-on System"} · {defaultOfferings.length} Included Defaults · {addonOfferings.length} Available Add-ons
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {saving && (
                  <span className="text-xs font-semibold text-[var(--rl-text-muted)] flex items-center gap-1.5">
                    <ArrowClockwise size={12} className="animate-spin" />
                    Saving...
                  </span>
                )}
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowLiveTemplate(true)}
                  disabled={showLiveTemplate}
                  className="gap-1.5"
                  title="Open the live template preview"
                >
                  <Eye size={14} />
                  {showLiveTemplate ? "Preview open" : "Show preview"}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={resetToDefaultOfferings}
                  disabled={saving}
                  className="gap-1.5 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                >
                  <ArrowCounterClockwise size={14} />
                  Reset to Default
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => retireCatalog(selectedCatalog)}
                  disabled={saving}
                  className="gap-1.5 text-[var(--rl-red)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)]"
                  title="Retire this entire catalog"
                >
                  <Trash size={14} />
                  Retire Catalog
                </Button>
                <Button size="sm" onClick={publishConfig} disabled={saving} className="gap-1.5">
                  <Check size={14} weight="bold" />
                  Save & Publish
                </Button>
              </div>
            </div>

            {/* ── Real Interactive Template Slot Preview (When Toggled) ─── */}
            
            {showLiveTemplate ? (
              <PanelGroup orientation="horizontal" className="min-h-[600px] h-[80vh] rounded-[var(--rl-radius)] border border-[var(--rl-border)] shadow-sm bg-[var(--rl-surface)] mb-6">
                <Panel defaultSize={60} minSize={40} className="flex flex-col overflow-hidden">
                  <div ref={leftScrollRef} onScroll={handleLeftScroll} className="flex-1 flex flex-col gap-6 p-5 overflow-y-auto">
                    {/* ── Fast Bulk Clicker: Category 1 (Default Benefits) ──────── */}
            <div className="rl-tour-defaults rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
              <div className="mb-4 flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
                <div>
                  <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">
                    Category 1: Core Defaults ({defaultConcepts.length} items)
                  </h3>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Click any tile to toggle on/off standard included policy coverages for {isPackaged && activePackage ? activePackage.name : "this configuration"}.
                  </p>
                </div>
                <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                  {defaultOfferings.length} / {defaultConcepts.length} Active in this tier
                </span>
              </div>

              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {defaultConcepts.map((concept) => {
                  const offering = activeConceptIdSet.get(concept.id);
                  const isActive = Boolean(offering && effectiveRole(offering) === "included");

                  return (
                    <div
                      key={concept.id}
                      onClick={() => toggleConceptFast(concept, "included")}
                      className={`group relative flex flex-col justify-between rounded-[var(--rl-radius-sm)] border p-3 cursor-pointer transition-all ${isActive
                        ? "border-[var(--rl-black)] bg-[var(--rl-bg)] shadow-sm ring-1 ring-[var(--rl-black)]"
                        : "border-[var(--rl-border)] bg-[var(--rl-surface)] opacity-70 hover:opacity-100 hover:border-[var(--rl-text-muted)]"
                        }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div
                            className={`grid h-7 w-7 shrink-0 place-items-center rounded-[4px] border ${isActive
                              ? "bg-[var(--rl-black)] text-white border-[var(--rl-black)]"
                              : "bg-[var(--rl-bg)] text-[var(--rl-text-muted)] border-[var(--rl-border)]"
                              }`}
                          >
                            {concept.default_asset?.url ? (
                              <img src={fileUrl(concept.default_asset.url)} alt={concept.label} loading="lazy" className="h-4 w-4 object-contain" />
                            ) : (
                              <ShieldCheck size={16} />
                            )}
                          </div>
                          <span className="font-semibold text-xs text-[var(--rl-text-strong)] truncate">
                            {concept.label}
                          </span>
                          {disabledConceptIdSet.has(concept.id) && (
                            <span
                              className="rounded bg-amber-100 text-amber-900 border border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800 px-1 py-0.2 text-[8.5px] font-bold uppercase tracking-wider shrink-0"
                              title="Excluded by active benefit profile cascade"
                            >
                              Excluded
                            </span>
                          )}
                        </div>

                        <div
                          className={`h-4 w-4 rounded-[4px] border grid place-items-center ${isActive
                            ? "bg-[var(--rl-black)] border-[var(--rl-black)] text-white"
                            : "border-[var(--rl-border)] bg-[var(--rl-surface)]"
                            }`}
                        >
                          {isActive && <Check size={12} weight="bold" />}
                        </div>
                      </div>

                      <div className="mt-2.5 flex items-center justify-between gap-1.5 text-[11px] pt-1.5 border-t border-[var(--rl-border)]/60">
                        {isActive ? (
                          <>
                            <input
                              type="text"
                              defaultValue={cleanCoverageValue(offering?.display_value)}
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingValueInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-bold text-[var(--rl-text-strong)] flex-1 min-w-0"
                              placeholder="RM 0.00 (empty if none)"
                              title="Coverage value / limit"
                            />
                            <input
                              type="text"
                              defaultValue={
                                offering?.optional_price?.type === "formula"
                                  ? (offering.optional_price.display_text || offering.optional_price.formula || "")
                                  : (offering?.optional_price?.value
                                    ? `RM ${Number(offering.optional_price.value).toFixed(2)}`
                                    : (offering?.optional_price?.amount ? `RM ${offering.optional_price.amount}` : ""))
                              }
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingPriceInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-bold text-[var(--rl-red)] w-20 text-right shrink-0"
                              placeholder={
                                (offering?.concept_id ? baselineCostMap.get(offering.concept_id) : null) || "Free"
                              }
                              title="Cost / Price (empty for catalog baseline)"
                            />
                          </>
                        ) : (
                          <span className="text-[11px] text-[var(--rl-text-muted)]">Click to add</span>
                        )}
                        <span className="text-[10px] font-semibold text-[var(--rl-text-muted)] shrink-0">Default</span>
                      </div>

                      {isActive ? (() => {
                        const companyBaselineDesc = offering?.concept_id ? baselineDescMap.get(offering.concept_id) : null;
                        const activeDesc = companyBaselineDesc || offering?.description_override || concept.description || "";
                        return (
                        <div className="mt-2 pt-1.5 border-t border-[var(--rl-border)]/50 space-y-1" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-between text-[10px]">
                            <span className="text-[var(--rl-text-muted)] font-medium">Description:</span>
                            {companyBaselineDesc ? (
                              <span className="rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 px-1 py-0.2 text-[9.5px] font-semibold" title="Inherited from Tab 1 Company Baseline">
                                Company Baseline
                              </span>
                            ) : offering?.description_override ? (
                              <div className="flex items-center gap-1">
                                <span className="rounded bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 px-1 py-0.2 text-[9.5px] font-semibold">
                                  Catalog Custom
                                </span>
                                <button
                                  type="button"
                                  title="Reset to global default"
                                  onClick={() => {
                                    if (offering) updateOfferingDescriptionInline(offering, "");
                                  }}
                                  className="text-[var(--rl-text-muted)] hover:text-[var(--rl-red)] transition-colors p-0.5"
                                >
                                  <ArrowCounterClockwise size={11} />
                                </button>
                              </div>
                            ) : (
                              <span className="rounded bg-[var(--rl-bg)] border border-[var(--rl-border)] text-[var(--rl-text-muted)] px-1 py-0.2 text-[9.5px]">
                                Global Default
                              </span>
                            )}
                          </div>
                          <input
                            type="text"
                            defaultValue={activeDesc}
                            key={`${offering?.id}-${activeDesc}`}
                            onBlur={(e) => {
                              if (offering) {
                                const val = e.target.value.trim();
                                const current = offering.description_override || "";
                                if (val !== current) {
                                  updateOfferingDescriptionInline(offering, val);
                                }
                              }
                            }}
                            className="w-full rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[10.5px] text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)] placeholder:italic focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
                            placeholder={companyBaselineDesc || concept.description || "Enter short description..."}
                            title="Short benefit description shown on quote cards"
                          />
                        </div>
                        );
                      })() : (
                        (() => {
                          const fallbackDesc = (offering?.concept_id ? baselineDescMap.get(offering.concept_id) : null) || concept.description;
                          return fallbackDesc ? (
                            <div className="mt-1.5 text-[10px] text-[var(--rl-text-muted)] truncate" title={fallbackDesc}>
                              {fallbackDesc}
                            </div>
                          ) : null;
                        })()
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* ── Fast Bulk Clicker: Category 2 (Unique Add-ons) ─────────── */}
            <div className="rl-tour-addons rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
              <div className="mb-4 flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
                <div>
                  <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">
                    Category 2: Optional Riders & Add-ons ({addonConcepts.length} items)
                  </h3>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Click any tile to toggle on/off optional endorsements and select plan variations (Plan A/B/C/D, etc.) in 1 click.
                  </p>
                </div>
                <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                  {addonOfferings.length} / {addonConcepts.length} Active in this tier
                </span>
              </div>

              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {addonConcepts.map((concept) => {
                  const offering = activeConceptIdSet.get(concept.id);
                  const isActive = Boolean(offering && effectiveRole(offering) === "addon_option");
                  const hasVariants = Boolean(concept.variants && concept.variants.length > 0);

                  return (
                    <div
                      key={concept.id}
                      onClick={() => toggleConceptFast(concept, "addon_option")}
                      className={`group relative flex flex-col justify-between rounded-[var(--rl-radius-sm)] border p-3 cursor-pointer transition-all ${isActive
                        ? "border-[var(--rl-black)] bg-[var(--rl-bg)] shadow-sm ring-1 ring-[var(--rl-black)]"
                        : "border-[var(--rl-border)] bg-[var(--rl-surface)] opacity-70 hover:opacity-100 hover:border-[var(--rl-text-muted)]"
                        }`}
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div
                              className={`grid h-7 w-7 shrink-0 place-items-center rounded-[4px] border ${isActive
                                ? "bg-[var(--rl-black)] text-white border-[var(--rl-black)]"
                                : "bg-[var(--rl-bg)] text-[var(--rl-text-muted)] border-[var(--rl-border)]"
                                }`}
                            >
                              {concept.default_asset?.url ? (
                                <img src={fileUrl(concept.default_asset.url)} alt={concept.label} loading="lazy" className="h-4 w-4 object-contain" />
                              ) : (
                                <Sparkle size={16} />
                              )}
                            </div>
                            <span className="font-semibold text-xs text-[var(--rl-text-strong)] truncate">
                              {concept.label}
                            </span>
                            {disabledConceptIdSet.has(concept.id) && (
                              <span
                                className="rounded bg-amber-100 text-amber-900 border border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800 px-1 py-0.2 text-[8.5px] font-bold uppercase tracking-wider shrink-0"
                                title="Excluded by active benefit profile cascade"
                              >
                                Excluded
                              </span>
                            )}
                          </div>

                          <div
                            className={`h-4 w-4 rounded-[4px] border grid place-items-center ${isActive
                              ? "bg-[var(--rl-black)] border-[var(--rl-black)] text-white"
                              : "border-[var(--rl-border)] bg-[var(--rl-surface)]"
                              }`}
                          >
                            {isActive && <Check size={12} weight="bold" />}
                          </div>
                        </div>

                        {/* Plan Variations 1-Click Switcher */}
                        {hasVariants && (
                          <div
                            className="mt-2 flex flex-wrap gap-1"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {concept.variants!.map((variant) => {
                              const isVariantActive = offering?.label_override?.includes(variant);
                              return (
                                <button
                                  key={variant}
                                  onClick={() => {
                                    if (offering) {
                                      updatePlanVariantInline(offering, variant);
                                    } else {
                                      toggleConceptFast(concept, "addon_option");
                                    }
                                  }}
                                  className={`rounded-[4px] px-1.5 py-0.5 text-[10px] font-semibold transition-all ${isVariantActive
                                    ? "bg-[var(--rl-black)] text-white"
                                    : "bg-[var(--rl-surface)] border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                                    }`}
                                >
                                  {variant}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      <div className="mt-2.5 flex items-center justify-between gap-1.5 text-[11px] pt-1.5 border-t border-[var(--rl-border)]/60">
                        {isActive ? (
                          <>
                            <input
                              type="text"
                              defaultValue={cleanCoverageValue(offering?.display_value)}
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingValueInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-bold text-[var(--rl-text-strong)] flex-1 min-w-0"
                              placeholder="RM 0.00 (empty if none)"
                              title="Coverage value / limit"
                            />
                            <input
                              type="text"
                              defaultValue={
                                offering?.optional_price?.type === "formula"
                                  ? (offering.optional_price.display_text || offering.optional_price.formula || "")
                                  : (offering?.optional_price?.value
                                    ? `RM ${Number(offering.optional_price.value).toFixed(2)}`
                                    : (offering?.optional_price?.amount ? `RM ${offering.optional_price.amount}` : ""))
                              }
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingPriceInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-bold text-[var(--rl-red)] w-20 text-right shrink-0"
                              placeholder={
                                (offering?.concept_id ? baselineCostMap.get(offering.concept_id) : null) || "Optional"
                              }
                              title="Cost / Price (empty for catalog baseline)"
                            />
                          </>
                        ) : (
                          <span className="text-[11px] text-[var(--rl-text-muted)]">Click to add</span>
                        )}
                        <span className="text-[10px] font-semibold text-[var(--rl-text-muted)] shrink-0">Add-on</span>
                      </div>

                      {isActive ? (() => {
                        const companyBaselineDesc = offering?.concept_id ? baselineDescMap.get(offering.concept_id) : null;
                        const activeDesc = companyBaselineDesc || offering?.description_override || concept.description || "";
                        return (
                        <div className="mt-2 pt-1.5 border-t border-[var(--rl-border)]/50 space-y-1" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-between text-[10px]">
                            <span className="text-[var(--rl-text-muted)] font-medium">Description:</span>
                            {companyBaselineDesc ? (
                              <span className="rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 px-1 py-0.2 text-[9.5px] font-semibold" title="Inherited from Tab 1 Company Baseline">
                                Company Baseline
                              </span>
                            ) : offering?.description_override ? (
                              <div className="flex items-center gap-1">
                                <span className="rounded bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 px-1 py-0.2 text-[9.5px] font-semibold">
                                  Catalog Custom
                                </span>
                                <button
                                  type="button"
                                  title="Reset to global default"
                                  onClick={() => {
                                    if (offering) updateOfferingDescriptionInline(offering, "");
                                  }}
                                  className="text-[var(--rl-text-muted)] hover:text-[var(--rl-red)] transition-colors p-0.5"
                                >
                                  <ArrowCounterClockwise size={11} />
                                </button>
                              </div>
                            ) : (
                              <span className="rounded bg-[var(--rl-bg)] border border-[var(--rl-border)] text-[var(--rl-text-muted)] px-1 py-0.2 text-[9.5px]">
                                Global Default
                              </span>
                            )}
                          </div>
                          <input
                            type="text"
                            defaultValue={activeDesc}
                            key={`${offering?.id}-${activeDesc}`}
                            onBlur={(e) => {
                              if (offering) {
                                const val = e.target.value.trim();
                                const current = offering.description_override || "";
                                if (val !== current) {
                                  updateOfferingDescriptionInline(offering, val);
                                }
                              }
                            }}
                            className="w-full rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[10.5px] text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)] placeholder:italic focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
                            placeholder={companyBaselineDesc || concept.description || "Enter short description..."}
                            title="Short benefit description shown on quote cards"
                          />
                        </div>
                        );
                      })() : (
                        (() => {
                          const fallbackDesc = (offering?.concept_id ? baselineDescMap.get(offering.concept_id) : null) || concept.description;
                          return fallbackDesc ? (
                            <div className="mt-1.5 text-[10px] text-[var(--rl-text-muted)] truncate" title={fallbackDesc}>
                              {fallbackDesc}
                            </div>
                          ) : null;
                        })()
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
                  </div>
                </Panel>
                
                <PanelResizeHandle className="w-1 bg-[var(--rl-border)] hover:bg-[var(--rl-text-muted)] transition-colors cursor-col-resize flex-shrink-0" />
                
                <Panel defaultSize={40} minSize={30} className="bg-[#f5f5f7] border-l border-[var(--rl-border)] shadow-inner relative flex flex-col overflow-hidden">
                  <div className="bg-[var(--rl-surface)] p-4 border-b border-[var(--rl-border)] shrink-0">
                    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-3">
                  <div>
                    <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">
                      Quotation Template Slot Preview
                    </h3>
                    <p className="text-xs text-[var(--rl-text-muted)]">
                      Live preview into template canvas: <span className="font-semibold text-[var(--rl-text-strong)]">{activeTemplate?.name || "Copy of Standard A4 _ testing purpose"}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {templates.length > 0 && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-semibold text-[var(--rl-text-muted)]">Template:</span>
                        <select
                          value={selectedTemplateId}
                          onChange={(e) => setSelectedTemplateId(e.target.value)}
                          className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2.5 py-1 text-xs font-medium text-[var(--rl-text-strong)] shadow-sm focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
                        >
                          {templates.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                    <Button variant="secondary" size="sm" onClick={() => setShowLiveTemplate(false)}>
                      Close Preview
                    </Button>
                  </div>
                </div>
                  </div>
                  <div ref={rightScrollRef} onScroll={handleRightScroll} className="flex-1 p-6 overflow-y-auto overflow-x-hidden">
                    <div className="flex flex-col items-center justify-start w-full min-h-full py-2">
                    {previewTemplateElements.length === 0 ? (
                      <div className="grid h-full min-h-[420px] w-full place-items-center text-center text-xs text-[var(--rl-text-muted)]">
                        <div>
                          <p className="font-semibold text-[var(--rl-text-strong)]">No template canvas elements</p>
                          <p className="mt-1">This template has no renderable elements. Pick another template above.</p>
                        </div>
                      </div>
                    ) : (
                      <div
                        className="relative w-full max-w-[620px] bg-white shadow-card rounded-[4px] overflow-hidden border border-neutral-300 outline outline-1 outline-transparent hover:outline-[var(--rl-border)] transition-all duration-200"
                        style={{ aspectRatio: `${canvasW} / ${canvasH}` }}
                      >
                        <div
                          className="absolute left-0 top-0"
                          style={{
                            width: canvasW,
                            height: canvasH,
                            transform: `scale(${Math.min(1, 620 / canvasW)})`,
                            transformOrigin: "top left",
                          }}
                        >
                          {previewTemplateElements.map((element) => (
                            <CanvasElementView
                              key={element.id}
                              element={element}
                              selected={false}
                              readOnly={true}
                              onPointerDown={() => { }}
                              config={activeTemplate?.fixed_fields || (activeTemplate as any)?.config}
                              variableValues={previewVariableValues}
                              benefitData={previewBenefitData}
                              conceptAssets={previewConceptAssets}
                              assets={previewTemplateAssets}
                            />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  </div>
                </Panel>
              </PanelGroup>
            ) : (
              <div className="space-y-6 mb-6">
                {/* ── Fast Bulk Clicker: Category 1 (Default Benefits) ──────── */}
            <div className="rl-tour-defaults rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
              <div className="mb-4 flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
                <div>
                  <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">
                    Category 1: Default / Global Benefits (11 items)
                  </h3>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Click any tile to toggle on/off standard included policy coverages for {isPackaged && activePackage ? activePackage.name : "this configuration"}.
                  </p>
                </div>
                <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                  {defaultOfferings.length} / 11 Active in this tier
                </span>
              </div>

              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {defaultConcepts.map((concept) => {
                  const offering = activeConceptIdSet.get(concept.id);
                  const isActive = Boolean(offering && effectiveRole(offering) === "included");

                  return (
                    <div
                      key={concept.id}
                      onClick={() => toggleConceptFast(concept, "included")}
                      className={`group relative flex flex-col justify-between rounded-[var(--rl-radius-sm)] border p-3 cursor-pointer transition-all ${isActive
                        ? "border-[var(--rl-black)] bg-[var(--rl-bg)] shadow-sm ring-1 ring-[var(--rl-black)]"
                        : "border-[var(--rl-border)] bg-[var(--rl-surface)] opacity-70 hover:opacity-100 hover:border-[var(--rl-text-muted)]"
                        }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div
                            className={`grid h-7 w-7 shrink-0 place-items-center rounded-[4px] border ${isActive
                              ? "bg-[var(--rl-black)] text-white border-[var(--rl-black)]"
                              : "bg-[var(--rl-bg)] text-[var(--rl-text-muted)] border-[var(--rl-border)]"
                              }`}
                          >
                            {concept.default_asset?.url ? (
                              <img src={fileUrl(concept.default_asset.url)} alt={concept.label} loading="lazy" className="h-4 w-4 object-contain" />
                            ) : (
                              <ShieldCheck size={16} />
                            )}
                          </div>
                          <span className="font-semibold text-xs text-[var(--rl-text-strong)] truncate">
                            {concept.label}
                          </span>
                          {disabledConceptIdSet.has(concept.id) && (
                            <span
                              className="rounded bg-amber-100 text-amber-900 border border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800 px-1 py-0.2 text-[8.5px] font-bold uppercase tracking-wider shrink-0"
                              title="Excluded by active benefit profile cascade"
                            >
                              Excluded
                            </span>
                          )}
                        </div>

                        <div
                          className={`h-4 w-4 rounded-[4px] border grid place-items-center ${isActive
                            ? "bg-[var(--rl-black)] border-[var(--rl-black)] text-white"
                            : "border-[var(--rl-border)] bg-[var(--rl-surface)]"
                            }`}
                        >
                          {isActive && <Check size={12} weight="bold" />}
                        </div>
                      </div>

                      <div className="mt-2.5 flex items-center justify-between gap-1.5 text-[11px] pt-1.5 border-t border-[var(--rl-border)]/60">
                        {isActive ? (
                          <>
                            <input
                              type="text"
                              defaultValue={cleanCoverageValue(offering?.display_value)}
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingValueInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-bold text-[var(--rl-text-strong)] flex-1 min-w-0"
                              placeholder="RM 0.00 (empty if none)"
                              title="Coverage value / limit"
                            />
                            <input
                              type="text"
                              defaultValue={
                                offering?.optional_price?.type === "formula"
                                  ? (offering.optional_price.display_text || offering.optional_price.formula || "")
                                  : (offering?.optional_price?.value
                                    ? `RM ${Number(offering.optional_price.value).toFixed(2)}`
                                    : (offering?.optional_price?.amount ? `RM ${offering.optional_price.amount}` : ""))
                              }
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingPriceInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-bold text-[var(--rl-red)] w-20 text-right shrink-0"
                              placeholder={
                                (offering?.concept_id ? baselineCostMap.get(offering.concept_id) : null) || "Free"
                              }
                              title="Cost / Price (empty for catalog baseline)"
                            />
                          </>
                        ) : (
                          <span className="text-[11px] text-[var(--rl-text-muted)]">Click to add</span>
                        )}
                        <span className="text-[10px] font-semibold text-[var(--rl-text-muted)] shrink-0">Default</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* ── Fast Bulk Clicker: Category 2 (Unique Add-ons) ─────────── */}
            <div className="rl-tour-addons rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
              <div className="mb-4 flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
                <div>
                  <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">
                    Category 2: Unique Add-ons & Multi-Plan Variations (23 items)
                  </h3>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Click any tile to toggle on/off optional endorsements and select plan variations (Plan A/B/C/D, etc.) in 1 click.
                  </p>
                </div>
                <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                  {addonOfferings.length} / 23 Active in this tier
                </span>
              </div>

              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {addonConcepts.map((concept) => {
                  const offering = activeConceptIdSet.get(concept.id);
                  const isActive = Boolean(offering && effectiveRole(offering) === "addon_option");
                  const hasVariants = Boolean(concept.variants && concept.variants.length > 0);

                  return (
                    <div
                      key={concept.id}
                      onClick={() => toggleConceptFast(concept, "addon_option")}
                      className={`group relative flex flex-col justify-between rounded-[var(--rl-radius-sm)] border p-3 cursor-pointer transition-all ${isActive
                        ? "border-[var(--rl-black)] bg-[var(--rl-bg)] shadow-sm ring-1 ring-[var(--rl-black)]"
                        : "border-[var(--rl-border)] bg-[var(--rl-surface)] opacity-70 hover:opacity-100 hover:border-[var(--rl-text-muted)]"
                        }`}
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div
                              className={`grid h-7 w-7 shrink-0 place-items-center rounded-[4px] border ${isActive
                                ? "bg-[var(--rl-black)] text-white border-[var(--rl-black)]"
                                : "bg-[var(--rl-bg)] text-[var(--rl-text-muted)] border-[var(--rl-border)]"
                                }`}
                            >
                              {concept.default_asset?.url ? (
                                <img src={fileUrl(concept.default_asset.url)} alt={concept.label} loading="lazy" className="h-4 w-4 object-contain" />
                              ) : (
                                <Sparkle size={16} />
                              )}
                            </div>
                            <span className="font-semibold text-xs text-[var(--rl-text-strong)] truncate">
                              {concept.label}
                            </span>
                            {disabledConceptIdSet.has(concept.id) && (
                              <span
                                className="rounded bg-amber-100 text-amber-900 border border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800 px-1 py-0.2 text-[8.5px] font-bold uppercase tracking-wider shrink-0"
                                title="Excluded by active benefit profile cascade"
                              >
                                Excluded
                              </span>
                            )}
                          </div>

                          <div
                            className={`h-4 w-4 rounded-[4px] border grid place-items-center ${isActive
                              ? "bg-[var(--rl-black)] border-[var(--rl-black)] text-white"
                              : "border-[var(--rl-border)] bg-[var(--rl-surface)]"
                              }`}
                          >
                            {isActive && <Check size={12} weight="bold" />}
                          </div>
                        </div>

                        {/* Plan Variations 1-Click Switcher */}
                        {hasVariants && (
                          <div
                            className="mt-2 flex flex-wrap gap-1"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {concept.variants!.map((variant) => {
                              const isVariantActive = offering?.label_override?.includes(variant);
                              return (
                                <button
                                  key={variant}
                                  onClick={() => {
                                    if (offering) {
                                      updatePlanVariantInline(offering, variant);
                                    } else {
                                      toggleConceptFast(concept, "addon_option");
                                    }
                                  }}
                                  className={`rounded-[4px] px-1.5 py-0.5 text-[10px] font-semibold transition-all ${isVariantActive
                                    ? "bg-[var(--rl-black)] text-white"
                                    : "bg-[var(--rl-surface)] border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                                    }`}
                                >
                                  {variant}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      <div className="mt-2.5 flex items-center justify-between gap-1.5 text-[11px] pt-1.5 border-t border-[var(--rl-border)]/60">
                        {isActive ? (
                          <>
                            <input
                              type="text"
                              defaultValue={cleanCoverageValue(offering?.display_value)}
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingValueInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-bold text-[var(--rl-text-strong)] flex-1 min-w-0"
                              placeholder="RM 0.00 (empty if none)"
                              title="Coverage value / limit"
                            />
                            <input
                              type="text"
                              defaultValue={
                                offering?.optional_price?.type === "formula"
                                  ? (offering.optional_price.display_text || offering.optional_price.formula || "")
                                  : (offering?.optional_price?.value
                                    ? `RM ${Number(offering.optional_price.value).toFixed(2)}`
                                    : (offering?.optional_price?.amount ? `RM ${offering.optional_price.amount}` : ""))
                              }
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingPriceInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-bold text-[var(--rl-red)] w-20 text-right shrink-0"
                              placeholder={
                                (offering?.concept_id ? baselineCostMap.get(offering.concept_id) : null) || "Optional"
                              }
                              title="Cost / Price (empty for catalog baseline)"
                            />
                          </>
                        ) : (
                          <span className="text-[11px] text-[var(--rl-text-muted)]">Click to add</span>
                        )}
                        <span className="text-[10px] font-semibold text-[var(--rl-text-muted)] shrink-0">Add-on</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
              </div>
            )}

            {/* ── Revisions & Bundles Overview ─────────────────────────── */}
            <div className="rl-tour-bundles rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5">
              <div className="flex items-center gap-4 border-b border-[var(--rl-border)] pb-3 text-xs">
                <button
                  onClick={() => setActiveTab("structure")}
                  className={`font-semibold transition-colors ${activeTab === "structure"
                    ? "text-[var(--rl-text-strong)] border-b-2 border-[var(--rl-black)] pb-1"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    }`}
                >
                  Structure Overview
                </button>
                <button
                  onClick={() => setActiveTab("bundles")}
                  className={`font-semibold transition-colors ${activeTab === "bundles"
                    ? "text-[var(--rl-text-strong)] border-b-2 border-[var(--rl-black)] pb-1"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    }`}
                >
                  Bundles ({bundles.length})
                </button>
              </div>

              {activeTab === "bundles" && (
                <div className="mt-4 space-y-4 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3">
                    <div>
                      <h4 className="font-bold text-[var(--rl-text-strong)] flex items-center gap-1.5">
                        <PackageIcon size={16} weight="fill" className="text-[var(--rl-red)]" />
                        Custom Add-on Bundles ({bundles.length})
                      </h4>
                      <p className="text-[11px] text-[var(--rl-text-muted)] mt-0.5">
                        Package multiple add-ons (e.g. Driver Passenger Protector / DPA) into tiered multi-benefit bundles with custom prices and limits.
                      </p>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => {
                        setFormName("Driver Passenger Protector");
                        setFormPackageKey("driver-passenger-protector");
                        setDialog("bundle");
                      }}
                      className="gap-1.5"
                    >
                      <Plus size={14} weight="bold" />
                      Create Custom Bundle
                    </Button>
                  </div>

                  {bundles.length === 0 ? (
                    <div className="rounded-[var(--rl-radius-sm)] border border-dashed border-[var(--rl-border)] p-6 text-center text-[var(--rl-text-muted)]">
                      <p className="font-medium text-[var(--rl-text-strong)]">No custom addon bundles configured yet.</p>
                      <p className="mt-1 text-[11px]">Click &quot;Create Custom Bundle&quot; to create a multi-benefit package (e.g. Driver Passenger Protector) with tiered plan levels A/B/C/D.</p>
                    </div>
                  ) : (
                    bundles.map((b) => {
                      const plans = plansFor(b);
                      const expanded = expandedPlanId === b.id;
                      const isCarOnly = b.package_key.toLowerCase().includes("driver") || b.name.toLowerCase().includes("driver");
                      return (
                        <div key={b.id} className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] shadow-sm">
                          <div className="flex flex-wrap items-center justify-between gap-2 p-3.5 border-b border-[var(--rl-border)]/60">
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="grid h-7 w-7 place-items-center rounded-[4px] bg-[var(--rl-red-light)] text-[var(--rl-red)]">
                                <PackageIcon size={16} weight="fill" />
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <span className="font-bold text-xs text-[var(--rl-text-strong)]">{b.name}</span>
                                  <span className="font-mono text-[10px] text-[var(--rl-text-muted)]">({b.package_key})</span>
                                  <span className="rounded-[4px] bg-[var(--rl-surface)] border border-[var(--rl-border)] px-2 py-0.5 text-[10px] font-bold text-[var(--rl-text-muted)]">
                                    {plans.length} plan tier{plans.length === 1 ? "" : "s"}
                                  </span>
                                  {isCarOnly && (
                                    <span className="rounded-[4px] bg-blue-50 text-blue-700 border border-blue-200 px-1.5 py-0.5 text-[10px] font-semibold">
                                      🚗 4-Wheelers (Car Only)
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <button
                                type="button"
                                onClick={() => renamePackage(b)}
                                className="flex items-center gap-1 rounded px-2 py-1 font-semibold text-[var(--rl-text-muted)] hover:bg-[var(--rl-surface)] hover:text-[var(--rl-text-strong)] transition-colors"
                                title="Rename bundle"
                              >
                                <PencilSimple size={13} weight="bold" />
                                Rename
                              </button>
                              <button
                                type="button"
                                onClick={() => retireBundle(b)}
                                className="flex items-center gap-1 rounded px-2 py-1 font-semibold text-[var(--rl-red)] hover:bg-[var(--rl-red-light)] transition-colors"
                                title="Retire bundle"
                              >
                                <Trash size={13} weight="bold" />
                                Retire
                              </button>
                              <button
                                type="button"
                                onClick={() => setExpandedPlanId(expanded ? "" : b.id)}
                                className="flex items-center gap-1 rounded px-2 py-1 font-semibold text-[var(--rl-text-muted)] hover:bg-[var(--rl-surface)] hover:text-[var(--rl-text-strong)] transition-colors"
                              >
                                {expanded ? <EyeSlash size={14} weight="bold" /> : <Eye size={14} weight="bold" />}
                                {expanded ? "Collapse Plans" : "Manage Plans & Limits"}
                              </button>
                            </div>
                          </div>

                          {expanded && (
                            <div className="grid gap-3.5 p-4 bg-[var(--rl-surface)]">
                              {/* Create Plan Tier */}
                              <div className="flex flex-wrap items-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3">
                                <span className="font-semibold text-xs text-[var(--rl-text-strong)]">Add Plan Tier:</span>
                                <Input
                                  value={planFormName}
                                  onChange={(e) => setPlanFormName(e.target.value)}
                                  placeholder="e.g. Plan A (RM 70)"
                                  className="max-w-xs text-xs"
                                  onKeyDown={(e) => { if (e.key === "Enter") createPlan(b); }}
                                />
                                <Button size="sm" onClick={() => createPlan(b)} disabled={planSaving} icon={<Plus size={14} weight="bold" />}>
                                  Add Tier Level
                                </Button>
                              </div>

                              {plans.length === 0 ? (
                                <p className="text-[var(--rl-text-muted)] italic">No plan levels yet. Add Plan A first, then B, C, D as upgrades.</p>
                              ) : (
                                <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                                  {plans.map((plan) => {
                                    const items = planItemsFor(plan);
                                    const memberOptions = bundleMemberOptions(b);
                                    return (
                                      <div key={plan.id} className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3.5 shadow-sm space-y-3">
                                        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--rl-border)]/60 pb-2.5">
                                          <div className="flex items-center gap-2">
                                            <span className="font-bold text-xs text-[var(--rl-text-strong)]">{plan.name}</span>
                                            <span className="rounded-[4px] bg-[var(--rl-surface)] border border-[var(--rl-border)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--rl-text-muted)]">
                                              {items.length} benefit{items.length === 1 ? "" : "s"}
                                            </span>
                                          </div>
                                          <div className="flex items-center gap-1">
                                            <button
                                              type="button"
                                              onClick={() => renamePlan(b, plan)}
                                              disabled={planSaving}
                                              className="rounded px-2 py-1 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:bg-[var(--rl-surface)] hover:text-[var(--rl-text-strong)] transition-colors flex items-center gap-1"
                                              title="Rename plan"
                                            >
                                              <PencilSimple size={12} weight="bold" /> Rename
                                            </button>
                                            <button
                                              type="button"
                                              onClick={() => retirePlan(b, plan)}
                                              disabled={planSaving}
                                              className="rounded px-2 py-1 text-[11px] font-semibold text-[var(--rl-red)] hover:bg-[var(--rl-red-light)] transition-colors flex items-center gap-1"
                                            >
                                              <Trash size={12} weight="bold" /> Retire
                                            </button>
                                          </div>
                                        </div>

                                        {/* Member Benefits List */}
                                        <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                                          {items.length === 0 ? (
                                            <p className="text-[11px] text-[var(--rl-text-muted)] italic">No benefits attached to this tier yet.</p>
                                          ) : (
                                            items.map((item) => (
                                              <div key={item.id} className="flex items-center justify-between gap-2 rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2.5 py-1.5 text-[11px]">
                                                <span className="min-w-0 font-medium text-[var(--rl-text-strong)] truncate">
                                                  {offeringLabel(String(item.offering_id))}
                                                </span>
                                                <div className="flex items-center gap-1.5 shrink-0">
                                                  <input
                                                    defaultValue={formatOverrideDisplay(item.typed_value_override)}
                                                    onBlur={(e) => updatePlanItemOverride(b, plan, item, e.target.value)}
                                                    placeholder="Limit / Description"
                                                    className="w-36 rounded border border-[var(--rl-border)] bg-[var(--rl-bg)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--rl-text-strong)] text-right"
                                                    title="Coverage limit / Short description"
                                                  />
                                                  <button
                                                    type="button"
                                                    onClick={() => removePlanItem(b, plan, item)}
                                                    disabled={planSaving}
                                                    className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)]"
                                                    title="Remove benefit from plan"
                                                  >
                                                    <X size={13} weight="bold" />
                                                  </button>
                                                </div>
                                              </div>
                                            ))
                                          )}
                                        </div>

                                        {/* Add Member Benefit */}
                                        <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-[var(--rl-border)]/60">
                                          <select
                                            value={planMemberOfferingId}
                                            onChange={(e) => setPlanMemberOfferingId(e.target.value)}
                                            className="min-w-0 flex-1 rounded border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2 py-1 text-xs text-[var(--rl-text-strong)]"
                                          >
                                            <option value="">+ Choose benefit to add…</option>
                                            {memberOptions.map((off) => (
                                              <option key={off.id} value={off.id}>
                                                {off.label_override || off.concept?.label || off.offering_key}
                                              </option>
                                            ))}
                                          </select>
                                          <Input
                                            value={planMemberOverride}
                                            onChange={(e) => setPlanMemberOverride(e.target.value)}
                                            placeholder="Limit (e.g. RM 10,000)"
                                            className="w-32 text-xs"
                                          />
                                          <Button size="sm" variant="secondary" onClick={() => addPlanItem(b, plan)} disabled={planSaving} icon={<Plus size={13} weight="bold" />}>
                                            Add
                                          </Button>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {activeTab === "structure" && (
                <div className="mt-3 text-xs text-[var(--rl-text-muted)]">
                  All 34 canonical benefit concepts (11 Default Benefits and 23 Add-ons) are populated from the active database catalog.
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <BenefitsDialogs
        dialog={dialog}
        setDialog={setDialog}
        formName={formName}
        setFormName={setFormName}
        formAsPackage={formAsPackage}
        setFormAsPackage={setFormAsPackage}
        formPackageName={formPackageName}
        setFormPackageName={setFormPackageName}
        createConfig={createConfig}
        clonePackage={clonePackage}
        createBundle={createBundle}
        saving={saving}
        showAiModal={showAiModal}
        setShowAiModal={setShowAiModal}
        matrixData={matrixData}
        aiModalTab={aiModalTab}
        setAiModalTab={setAiModalTab}
        copyAiPrompt={copyAiPrompt}
        copiedPrompt={copiedPrompt}
        aiSyncPrompt={aiSyncPrompt}
        aiDiffInput={aiDiffInput}
        setAiDiffInput={setAiDiffInput}
        runAiDiffCheck={runAiDiffCheck}
        aiDiffLoading={aiDiffLoading}
        aiDiffResult={aiDiffResult}
        conditionDialog={conditionDialog}
        setConditionDialog={setConditionDialog}
        selectedCompany={selectedCompany}
        condFormName={condFormName}
        setCondFormName={setCondFormName}
        condTriggerId={condTriggerId}
        setCondTriggerId={setCondTriggerId}
        concepts={concepts}
        condPlanFilter={condPlanFilter}
        setCondPlanFilter={setCondPlanFilter}
        condTargetId={condTargetId}
        setCondTargetId={setCondTargetId}
        condActionType={condActionType}
        setCondActionType={setCondActionType}
        condReplacement={condReplacement}
        setCondReplacement={setCondReplacement}
        saveCompanyCondition={saveCompanyCondition}
        conditionSaving={conditionSaving}
        cloneModalOpen={cloneModalOpen}
        setCloneModalOpen={setCloneModalOpen}
        selectedProfile={selectedProfile}
        cloneName={cloneName}
        setCloneName={setCloneName}
        cloneNotes={cloneNotes}
        setCloneNotes={setCloneNotes}
        handleCloneProfile={handleCloneProfile}
        profileActionLoading={profileActionLoading}
      />
    </AppShell>
  );
}

export default function BenefitsPage() {
  return (
    <Suspense fallback={<PageLoading />}>
      <BenefitsPageContent />
    </Suspense>
  );
}

