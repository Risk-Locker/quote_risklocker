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
import { AppShell } from "@/components/app-shell";
import { BuilderNav } from "@/components/builder-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
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
type Source = { id: string; title: string; issuer: string; verification_status: string };
type TemplateRecord = {
  id: string;
  name: string;
  is_default?: boolean;
  status: string;
  fixed_fields: {
    canvas?: { width?: number; height?: number; elements?: CanvasElement[] };
    page_profile?: { name?: string; width?: number; height?: number; unit?: string };
    assets?: Record<string, string>;
  };
};

const ROLE_FALLBACK: Record<string, string> = {
  base: "included",
  optional: "addon_option",
  package_component: "bundle_component",
  upgrade: "upgrade",
};

type MatrixOffering = {
  offering_id: string;
  offering_key: string;
  concept_key: string;
  label: string;
  description: string;
  display_value: string;
  price: number;
  price_text: string;
};

type MatrixBundleItem = {
  offering_key: string;
  label: string;
  override_value: string;
};

type MatrixBundlePlan = {
  plan_id: string;
  plan_key: string;
  name: string;
  items: MatrixBundleItem[];
};

type MatrixBundle = {
  package_id: string;
  package_key: string;
  name: string;
  package_kind: string;
  plans: MatrixBundlePlan[];
};

type MatrixScenario = {
  catalog_id: string;
  product_id: string | null;
  product_name: string;
  product_key: string;
  scenario_name: string;
  segment_name: string;
  segment_key: string;
  vehicle_category_name: string;
  vehicle_category_key: string;
  coverage_type_name: string;
  coverage_type_key: string;
  system_type: string;
  revision_number: number;
  state: string;
  defaults: MatrixOffering[];
  addons: MatrixOffering[];
  bundles: MatrixBundle[];
};

type CompanyMatrixData = {
  company: {
    id: string;
    name: string;
    slug: string;
    category: string;
  };
  summary: {
    total_products: number;
    total_scenarios: number;
    total_defaults: number;
    total_addons: number;
    total_bundles: number;
  };
  scenarios: MatrixScenario[];
};

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
  const [activeTab, setActiveTab] = useState<"structure" | "bundles" | "revisions">("structure");
  const [showLiveTemplate, setShowLiveTemplate] = useState(true);
  const [loading, setLoading] = useState(true);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [dialog, setDialog] = useState<"config" | "bundle" | "clone" | null>(null);
  const mountedRef = useRef(true);

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

  // Matrix and AI sync states
  const [screenTab, setScreenTab] = useState<"builder" | "matrix">("builder");
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

  // ── 1. Callbacks ───────────────────────────────────────────────────────
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

  const loadReferenceData = useCallback(async () => {
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
    const rawTemplates = (templateResult as { templates?: TemplateRecord[] | { items?: TemplateRecord[] } })?.templates;
    const allTemplates: TemplateRecord[] = Array.isArray(rawTemplates)
      ? rawTemplates
      : (rawTemplates?.items || []);

    setCompanies(activeCompanies);
    setSegments(activeSegments);
    setVehicles(activeVehicles);
    setConcepts(conceptResult.benefit_concepts.items);
    setSources(sourceResult.sources.items);
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

  const loadCatalog = useCallback(
    async (catalogId: string, silent = false) => {
      if (!catalogId) {
        setCatalogWorkspace(null);
        return;
      }
      if (!silent) setWorkspaceLoading(true);
      setError("");
      try {
        const result = await api<{ workspace: CatalogWorkspace }>(`/business/catalogs/${catalogId}/workspace`);
        if (!mountedRef.current) return;
        setCatalogWorkspace(result.workspace);
        setSelectedCatalogId(catalogId);
        syncUrl(selectedCompanyId, selectedProductId, catalogId);
      } catch (err) {
        if (mountedRef.current) setError(apiErrorMessage(err));
      } finally {
        if (!silent && mountedRef.current) setWorkspaceLoading(false);
      }
    },
    [selectedCompanyId, selectedProductId, syncUrl]
  );

  const loadCompany = useCallback(
    async (companyId: string, preferredProduct = selectedProductId, preferredCatalog = selectedCatalogId) => {
      if (!companyId) return;
      setWorkspaceLoading(true);
      setError("");
      try {
        const result = await api<{ workspace: CompanyWorkspace }>(`/business/companies/${companyId}/workspace`);
        if (!mountedRef.current) return;
        setCompanyWorkspace(result.workspace);
        setSelectedCompanyId(companyId);
        const product = result.workspace.products.find((item) => item.id === preferredProduct) || result.workspace.products[0];
        setSelectedProductId(product?.id || "");
        const catalogs = result.workspace.catalogs.filter((item) => !product || !item.product_id || item.product_id === product.id);
        const catalog = catalogs.find((item) => item.id === preferredCatalog) || catalogs[0];
        syncUrl(companyId, product?.id || "", catalog?.id || "");
        await loadCatalog(catalog?.id || "");
      } catch (err) {
        if (mountedRef.current) setError(apiErrorMessage(err));
      } finally {
        if (!mountedRef.current) return;
        setWorkspaceLoading(false);
      }
    },
    [loadCatalog, selectedCatalogId, selectedProductId, syncUrl]
  );

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
  const defaultConcepts = useMemo(
    () => concepts.filter((c) => (c.category || (c.sort_order && c.sort_order <= 11 ? "default" : "addon")) === "default"),
    [concepts]
  );

  const addonConcepts = useMemo(
    () => concepts.filter((c) => (c.category || (c.sort_order && c.sort_order <= 11 ? "default" : "addon")) === "addon"),
    [concepts]
  );

  const productConfigs = useMemo(() => {
    const items = (companyWorkspace?.catalogs || []).filter(
      (item) => !item.tier_id && (!selectedProductId || !item.product_id || item.product_id === selectedProductId)
    );
    return items.sort((a, b) => {
      const aOrder = a.package?.sort_order ?? 0;
      const bOrder = b.package?.sort_order ?? 0;
      const aName = a.package?.name || a.name || "";
      const bName = b.package?.name || b.name || "";
      return aOrder - bOrder || aName.localeCompare(bName);
    });
  }, [companyWorkspace, selectedProductId]);

  const selectedCatalog = catalogWorkspace?.catalog || null;

  const comprehensivePackages = useMemo(() => {
    return (catalogWorkspace?.packages || [])
      .filter((p) => p && p.package_kind === "comprehensive" && p.status === "active")
      .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0));
  }, [catalogWorkspace]);

  const isPackaged = comprehensivePackages.length > 0;

  const activePackage = useMemo(() => {
    if (!isPackaged) return null;
    const found = comprehensivePackages.find((p) => p.id === selectedPackageId);
    if (found) return found;
    const byCatalog = comprehensivePackages.find((p) => p.id === selectedCatalog?.package_id);
    return byCatalog || comprehensivePackages[0] || null;
  }, [comprehensivePackages, isPackaged, selectedPackageId, selectedCatalog?.package_id]);

  const allOfferings = useMemo(() => catalogWorkspace?.offerings || [], [catalogWorkspace]);

  const currentPackageOfferings = useMemo(() => {
    if (!selectedCatalog) return [];
    const targetPkgId = activePackage?.id;
    return (allOfferings || []).filter((item) => {
      if (!item || item.status === "retired") return false;
      if (isPackaged && targetPkgId) {
        return item.applies_to_id === targetPkgId;
      }
      return !item.applies_to_id;
    });
  }, [allOfferings, selectedCatalog, isPackaged, activePackage]);

  const defaultOfferings = useMemo(() => {
    return (currentPackageOfferings || [])
      .filter((item) => effectiveRole(item) === "included")
      .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || String(a.offering_key || "").localeCompare(String(b.offering_key || "")));
  }, [currentPackageOfferings]);

  const addonOfferings = useMemo(() => {
    return (currentPackageOfferings || [])
      .filter((item) => effectiveRole(item) === "addon_option")
      .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || String(a.offering_key || "").localeCompare(String(b.offering_key || "")));
  }, [currentPackageOfferings]);

  const activeConceptIdSet = useMemo(() => {
    const map = new Map<string, Offering>();
    for (const off of (currentPackageOfferings || [])) {
      if (off && off.concept_id) {
        map.set(off.concept_id, off);
      }
    }
    return map;
  }, [currentPackageOfferings]);

  const bundles = useMemo(
    () => (catalogWorkspace?.packages || []).filter((item) => item && item.package_kind === "addon_bundle" && item.status === "active"),
    [catalogWorkspace]
  );

  const selectedCompany = useMemo(() => companies.find((item) => item.id === selectedCompanyId) || null, [companies, selectedCompanyId]);
  const selectedProduct = useMemo(() => companyWorkspace?.products.find((item) => item.id === selectedProductId) || null, [companyWorkspace, selectedProductId]);
  const selectedSegment = useMemo(() => segments.find((item) => item.id === selectedSegmentId) || null, [segments, selectedSegmentId]);
  const selectedVehicle = useMemo(() => vehicles.find((item) => item.id === selectedVehicleId) || null, [vehicles, selectedVehicleId]);
  const activeTemplate = useMemo(() => templates.find((t) => t.id === selectedTemplateId) || templates[0] || null, [templates, selectedTemplateId]);

  // Real template preview data (mirrors the sessions workspace benefit cards)
  const previewBenefitData = useMemo(
    () => ({
      current_benefits: defaultOfferings.map((o) => ({
        label: o.label_override || o.concept?.label || o.offering_key,
        value: o.display_value || "Included",
        asset_id: o.concept?.default_asset?.id || null,
        concept_key: o.concept?.concept_key || "",
        is_detected: false,
      })),
      available_addons: addonOfferings.map((o) => ({
        label: o.label_override || o.concept?.label || o.offering_key,
        value: o.display_value || "Optional",
        asset_id: o.concept?.default_asset?.id || null,
        concept_key: o.concept?.concept_key || "",
        is_detected: false,
      })),
    }),
    [defaultOfferings, addonOfferings]
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
    return isPackaged && activePackage
      ? { applies_to_type: "package", applies_to_id: activePackage.id }
      : { applies_to_type: null, applies_to_id: null };
  }

  // ── 1-Click Fast Toggle Sticker Handler (Optimistic UI, Zero Reload) ───
  async function toggleConceptFast(concept: Concept, targetRole: "included" | "addon_option") {
    if (!selectedCatalog || !catalogWorkspace) return;
    const existing = activeConceptIdSet.get(concept.id);
    const target = offeringTarget();
    const targetPkgId = target.applies_to_id;

    setSaving(true);
    setError("");

    if (existing) {
      // 1. Optimistic Delete (0ms delay)
      const prevOfferings = catalogWorkspace.offerings;
      setCatalogWorkspace((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          offerings: prev.offerings.filter((o) => o.id !== existing.id),
        };
      });

      try {
        await api(`/business/catalogs/${selectedCatalog.id}/offerings/${existing.id}?base_revision=${selectedCatalog.revision}`, {
          method: "DELETE",
        });
        await loadCatalog(selectedCatalog.id, true);
      } catch (err) {
        // Rollback on error
        setCatalogWorkspace((prev) => (prev ? { ...prev, offerings: prevOfferings } : prev));
        setError(apiErrorMessage(err));
      } finally {
        setSaving(false);
      }
    } else {
      // 2. Optimistic Add (0ms delay)
      const tempId = `temp-${Date.now()}`;
      const defaultVal = targetRole === "included" ? "Included" : "Optional";
      const variantStr = concept.variants && concept.variants.length > 0 ? concept.variants[0] : "";
      const labelOverride = variantStr ? `${concept.label} (${variantStr})` : null;

      const optimisticOffering: Offering = {
        id: tempId,
        catalog_revision_id: catalogWorkspace.active_revision.id,
        offering_key: `${concept.concept_key}-${Date.now()}`,
        concept_id: concept.id,
        offering_kind: targetRole === "included" ? "base" : "optional",
        applies_to_type: target.applies_to_type,
        applies_to_id: targetPkgId,
        role: targetRole,
        label_override: labelOverride,
        display_value: defaultVal,
        sort_order: currentPackageOfferings.length + 1,
        status: "active",
        source_aliases: [],
        source_citation: {},
        presentation_facet_ids: [],
        concept: concept,
      };

      const prevOfferings = catalogWorkspace.offerings;
      setCatalogWorkspace((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          offerings: [...prev.offerings, optimisticOffering],
        };
      });

      const payload: Record<string, unknown> = {
        base_revision: selectedCatalog.revision,
        offering_key: optimisticOffering.offering_key,
        concept_id: concept.id,
        offering_kind: targetRole === "included" ? "base" : "optional",
        applies_to_type: target.applies_to_type,
        applies_to_id: targetPkgId,
        role: targetRole,
        label_override: labelOverride,
        typed_value: { type: "custom", display_text: defaultVal },
        display_value: defaultVal,
        sort_order: currentPackageOfferings.length + 1,
        status: "active",
      };

      try {
        const res = await api<{ offering: Offering }>(`/business/catalogs/${selectedCatalog.id}/offerings`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setCatalogWorkspace((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            offerings: prev.offerings.map((o) => (o.id === tempId ? { ...res.offering, concept } : o)),
          };
        });
        await loadCatalog(selectedCatalog.id, true);
      } catch (err) {
        // Rollback on error
        setCatalogWorkspace((prev) => (prev ? { ...prev, offerings: prevOfferings } : prev));
        setError(apiErrorMessage(err));
      } finally {
        setSaving(false);
      }
    }
  }

  // ── Plan Variant Switcher (Optimistic UI, Zero Reload) ─────────────────
  async function updatePlanVariantInline(offering: Offering, variant: string) {
    if (!selectedCatalog || !catalogWorkspace) return;
    setSaving(true);
    setError("");
    const concept = concepts.find((c) => c.id === offering.concept_id);
    const label = `${concept?.label || offering.offering_key} (${variant})`;
    const prevOfferings = catalogWorkspace.offerings;

    // Optimistic label update
    setCatalogWorkspace((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        offerings: prev.offerings.map((o) => (o.id === offering.id ? { ...o, label_override: label } : o)),
      };
    });

    try {
      const payload = {
        id: offering.id,
        offering_key: offering.offering_key,
        offering_kind: offering.offering_kind,
        concept_id: offering.concept_id,
        role: offering.role,
        base_revision: selectedCatalog.revision,
        label_override: label,
      };
      await api(`/business/catalogs/${selectedCatalog.id}/offerings`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setCatalogWorkspace((prev) => (prev ? { ...prev, offerings: prevOfferings } : prev));
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  // ── Inline Display Value Editor (Optimistic UI, Zero Reload) ──────────
  async function updateOfferingValueInline(offering: Offering, newValue: string) {
    if (!selectedCatalog || !catalogWorkspace) return;
    setSaving(true);
    setError("");
    const prevOfferings = catalogWorkspace.offerings;
    const trimmed = newValue.trim();

    // Optimistic value update
    setCatalogWorkspace((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        offerings: prev.offerings.map((o) => (o.id === offering.id ? { ...o, display_value: trimmed || null } : o)),
      };
    });

    try {
      const payload = {
        id: offering.id,
        offering_key: offering.offering_key,
        offering_kind: offering.offering_kind,
        concept_id: offering.concept_id,
        role: offering.role,
        base_revision: selectedCatalog.revision,
        display_value: trimmed || null,
        typed_value: trimmed ? { type: "custom", display_text: trimmed } : null,
      };
      await api(`/business/catalogs/${selectedCatalog.id}/offerings`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setCatalogWorkspace((prev) => (prev ? { ...prev, offerings: prevOfferings } : prev));
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  // ── Inline Price / Cost Editor (Optimistic UI, Zero Reload) ───────────
  async function updateOfferingPriceInline(offering: Offering, newPriceStr: string) {
    if (!selectedCatalog || !catalogWorkspace) return;
    setSaving(true);
    setError("");
    const prevOfferings = catalogWorkspace.offerings;
    const cleanStr = newPriceStr.replace(/RM/i, "").replace(/,/g, "").trim();
    const num = cleanStr ? parseFloat(cleanStr) : null;
    const priceObj = num !== null && !isNaN(num) && num > 0 ? { type: "money", value: num, currency: "MYR" } : null;

    setCatalogWorkspace((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        offerings: prev.offerings.map((o) => (o.id === offering.id ? { ...o, optional_price: priceObj } : o)),
      };
    });

    try {
      const payload = {
        id: offering.id,
        offering_key: offering.offering_key,
        offering_kind: offering.offering_kind,
        concept_id: offering.concept_id,
        role: offering.role,
        base_revision: selectedCatalog.revision,
        display_value: offering.display_value || undefined,
        typed_value: offering.typed_value || undefined,
        optional_price: priceObj,
      };
      await api(`/business/catalogs/${selectedCatalog.id}/offerings`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await loadCatalog(selectedCatalog.id, true);
    } catch (err) {
      setCatalogWorkspace((prev) => (prev ? { ...prev, offerings: prevOfferings } : prev));
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
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
      };
      const config = await api<{ catalog: Catalog }>("/business/catalogs", { method: "POST", body: JSON.stringify(payload) });
      const configId = config.catalog.id;
      if (formAsPackage && formPackageName.trim()) {
        await api(`/business/catalogs/${configId}/packages`, {
          method: "POST",
          body: JSON.stringify({ base_revision: 1, name: formPackageName.trim(), package_key: formPackageKey.trim() || undefined, package_kind: "comprehensive" }),
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

  async function renamePackage(pkg: Package) {
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
        <PageLoading />
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

          <div className="flex flex-wrap items-center gap-2">
            {/* View Switcher: Interactive Builder vs Company Overview Matrix */}
            <div className="flex items-center rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-0.5 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setScreenTab("builder")}
                className={`flex items-center gap-1.5 rounded-[3px] px-3 py-1 transition-all ${
                  screenTab === "builder"
                    ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] shadow-sm font-bold border border-[var(--rl-border)]"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                <TreeStructure size={14} weight={screenTab === "builder" ? "bold" : "regular"} />
                <span>Interactive Builder</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setScreenTab("matrix");
                  if (selectedCompanyId) loadMatrix(selectedCompanyId);
                }}
                className={`flex items-center gap-1.5 rounded-[3px] px-3 py-1 transition-all ${
                  screenTab === "matrix"
                    ? "bg-[var(--rl-black)] text-white shadow-sm font-bold"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                <Table size={14} weight={screenTab === "matrix" ? "bold" : "regular"} />
                <span>Company Overview Matrix</span>
              </button>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowLiveTemplate(!showLiveTemplate)}
              className="gap-1.5"
            >
              {showLiveTemplate ? <EyeSlash size={14} weight="bold" /> : <Eye size={14} weight="bold" />}
              {showLiveTemplate ? "Hide Template Preview" : "Live Template Preview"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={refreshCurrent}
              disabled={workspaceLoading || saving}
              className="gap-1.5"
            >
              <ArrowClockwise size={14} className={workspaceLoading ? "animate-spin" : ""} />
              Refresh
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
              className="gap-1.5"
            >
              <Plus size={14} weight="bold" />
              Add configuration
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
                className="gap-1.5"
              >
                <Copy size={14} />
                Clone package
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
              className="gap-1.5"
            >
              <PackageIcon size={14} />
              New bundle
            </Button>
            <GuidedTour
              storageKey="tour:builder-benefits"
              title="Benefits & Add-ons Architecture"
              description="Configure which global benefits each insurer product includes by default and offers as add-ons, build package tiers, and create add-on bundles with plan levels."
              steps={BENEFITS_TOUR_STEPS}
            />
            {selectedCatalog && (
              selectedCatalog.revisions?.[0]?.state === "published" ? (
                <Button variant="secondary" size="sm" onClick={openNewDraft} disabled={saving} className="gap-1.5">
                  <PencilSimple size={14} weight="bold" />
                  New draft
                </Button>
              ) : (
                <Button size="sm" onClick={publishConfig} disabled={saving} className="gap-1.5">
                  <CheckCircle size={14} weight="bold" />
                  Publish
                </Button>
              )
            )}
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
        <div className="mt-4 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3.5 space-y-3.5">
          {/* Row 1: Insurance companies (Full-width, scalable for many companies) */}
          <div className="rl-tour-companies flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                1. Insurance companies ({companies.length})
              </span>
              <span className="text-[11px] text-[var(--rl-text-muted)]">
                Click an insurer to manage products & policy benefits
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {companies.map((c) => {
                const active = c.id === selectedCompanyId;
                const isPkgSystem = Boolean(companyWorkspace?.catalogs?.some((cat) => cat.company_id === c.id && cat.package_id));
                return (
                  <button
                    key={c.id}
                    onClick={() => loadCompany(c.id)}
                    className={`flex items-center gap-2.5 rounded-[var(--rl-radius-sm)] px-3.5 py-2 text-left font-medium transition-all ${active
                      ? "bg-[var(--rl-black)] text-white shadow-sm"
                      : "border border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                      }`}
                  >
                    {c.logo?.url ? (
                      <img src={fileUrl(c.logo.url)} alt={c.name} className="h-4 w-4 rounded-[2px] object-contain bg-white" />
                    ) : (
                      <Buildings size={15} className={active ? "text-white" : "text-[var(--rl-text-muted)]"} />
                    )}
                    <span className="text-xs font-semibold">{c.name}</span>
                    <span
                      className={`rounded-[4px] px-1.5 py-0.5 text-[10px] font-semibold uppercase ${active
                        ? "bg-white/20 text-white"
                        : "bg-[var(--rl-bg)] text-[var(--rl-text-muted)] border border-[var(--rl-border)]"
                        }`}
                    >
                      {isPkgSystem ? "Package System" : "Add-on System"}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Row 2: Segment + Vehicle Type + Coverage (Clear separate parameters row) */}
          <div className="flex flex-wrap items-center gap-4 border-t border-[var(--rl-border)] pt-3 text-xs">
            {/* Step 2: Segment */}
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                  2. Segment:
                </span>
                <Tooltip content="Choose private vs commercial vehicle policy scope">
                  <Info size={11} className="text-[var(--rl-text-muted)]" />
                </Tooltip>
              </div>
              <div className="flex gap-1">
                {segments.map((seg) => {
                  const active = seg.id === selectedSegmentId;
                  return (
                    <button
                      key={seg.id}
                      onClick={() => setSelectedSegmentId(seg.id)}
                      className={`rounded-[var(--rl-radius-sm)] px-2.5 py-1 text-xs font-medium transition-all ${active
                        ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] border border-[var(--rl-border)] shadow-sm font-semibold"
                        : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                        }`}
                    >
                      {seg.key === "private" ? "Private" : "Company / Commercial"}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="hidden h-5 w-px bg-[var(--rl-border)] sm:block" />

            {/* Step 3: Vehicle Type */}
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                3. Vehicle type:
              </span>
              <div className="flex gap-1">
                {vehicles.map((v) => {
                  const active = v.id === selectedVehicleId;
                  return (
                    <button
                      key={v.id}
                      onClick={() => setSelectedVehicleId(v.id)}
                      className={`rounded-[var(--rl-radius-sm)] px-2.5 py-1 text-xs font-medium transition-all ${active
                        ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] border border-[var(--rl-border)] shadow-sm font-semibold"
                        : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                        }`}
                    >
                      {v.name}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="hidden h-5 w-px bg-[var(--rl-border)] sm:block" />

            {/* Step 4: Coverage Type */}
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                4. Coverage:
              </span>
              <div className="flex items-center gap-1.5">
                <span className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-surface)] border border-[var(--rl-border)] px-2.5 py-1 text-xs font-semibold text-[var(--rl-text-strong)]">
                  Comprehensive
                </span>
                <span className="text-[11px] text-[var(--rl-text-muted)]">(Third Party available)</span>
              </div>
            </div>
          </div>

          {/* Row 3: Product / Configuration Selection */}
          <div className="rl-tour-product flex flex-wrap items-center gap-2 border-t border-[var(--rl-border)] pt-3">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
              5. Product:
            </span>

            {productConfigs.length === 0 ? (
              <span className="text-xs text-[var(--rl-text-muted)]">No configurations for this product yet.</span>
            ) : (
              productConfigs.map((config) => {
                const active = config.id === selectedCatalogId;
                const displayName = config.package ? config.package.name : "Single";
                return (
                  <button
                    key={config.id}
                    onClick={() => loadCatalog(config.id)}
                    className={`flex items-center gap-2 rounded-[var(--rl-radius-sm)] px-3 py-1.5 text-xs font-semibold transition-all ${active
                      ? "bg-[var(--rl-black)] text-white shadow-sm"
                      : "border border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                      }`}
                  >
                    <TreeStructure size={14} className={active ? "text-white" : "text-[var(--rl-text-muted)]"} />
                    <span>{displayName}</span>
                    <span className={`text-[10px] font-normal ${active ? "text-neutral-300" : "text-[var(--rl-text-muted)]"}`}>
                      {config.package ? "Package mode" : "Single mode"}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* ── Main Workspace Body ────────────────────────────────────────── */}
      <div className="p-6">
        {screenTab === "matrix" ? (
          <div className="space-y-6">
            {/* Header & Stats Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">
                    {matrixData?.company.name || "Insurance Company"} — Benefits & Packages Matrix
                  </h2>
                  <Badge variant="default">Underwriting Source of Truth</Badge>
                </div>
                <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                  Total comprehensive matrix view of all packages, included defaults (Cost: 0 RM), add-on riders, and bundled plan options for this company.
                </p>
              </div>

              {/* Action Buttons: Export DOCX, Export XLSX, AI Seed Spec */}
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={downloadDocx}
                  icon={<FileDoc size={15} weight="fill" className="text-blue-600" />}
                  title="Download standard Word catalog formatted like canonical policy catalogs"
                >
                  Download Word (.docx)
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={downloadXlsx}
                  icon={<FileXls size={15} weight="fill" className="text-emerald-600" />}
                  title="Download Excel spreadsheet with summary and detailed offering sheets"
                >
                  Download Excel (.xlsx)
                </Button>
                <Button
                  size="sm"
                  onClick={() => setShowAiModal(true)}
                  icon={<Sparkle size={15} weight="fill" className="text-amber-300" />}
                  className="bg-[var(--rl-black)] text-white hover:opacity-90"
                >
                  AI Seed & Sync Spec
                </Button>
              </div>
            </div>

            {/* Stats Badges & Filter Controls */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-3">
              {/* Coverage Filter Pills */}
              <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mr-1">
                  Coverage:
                </span>
                {["All", "Comprehensive", "Third Party, Fire & Theft", "Third Party"].map((cov) => {
                  const active = matrixFilterCoverage === cov;
                  return (
                    <button
                      key={cov}
                      onClick={() => setMatrixFilterCoverage(cov)}
                      className={`rounded-[var(--rl-radius-sm)] px-2.5 py-1 transition-all ${
                        active
                          ? "bg-[var(--rl-black)] text-white shadow-sm"
                          : "border border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                      }`}
                    >
                      {cov === "Third Party, Fire & Theft" ? "TPFT" : cov}
                    </button>
                  );
                })}
              </div>

              {/* Search Bar & Counter */}
              <div className="flex items-center gap-3">
                <div className="relative w-64">
                  <MagnifyingGlass size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
                  <Input
                    type="text"
                    value={matrixSearch}
                    onChange={(e) => setMatrixSearch(e.target.value)}
                    placeholder="Search package, default or rider..."
                    className="pl-8 text-xs h-8"
                  />
                  {matrixSearch && (
                    <button
                      onClick={() => setMatrixSearch("")}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
                <span className="text-xs font-semibold text-[var(--rl-text-muted)]">
                  {filteredMatrixScenarios.length} Scenarios
                </span>
              </div>
            </div>

            {/* Matrix Loading State */}
            {matrixLoading ? (
              <div className="py-12">
                <PageLoading />
              </div>
            ) : filteredMatrixScenarios.length === 0 ? (
              <div className="rounded-[var(--rl-radius)] border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface)] p-8 text-center text-xs text-[var(--rl-text-muted)]">
                No policy scenarios found matching your filters.
              </div>
            ) : (
              /* The Comprehensive Matrix Table */
              <Card className="overflow-hidden border border-[var(--rl-border)] shadow-sm">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[1040px] text-xs">
                    <thead>
                      <tr className="border-b border-[var(--rl-border)] bg-[#1F2937] text-white">
                        <th className="w-[24%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                          Product & Policy Scenario
                        </th>
                        <th className="w-[36%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                          Default Benefits (Included — Cost: 0 RM)
                        </th>
                        <th className="w-[30%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                          Add-on Benefits & Exact Base Cost
                        </th>
                        <th className="w-[10%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                          Bundled Add-ons
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--rl-border)]/70 bg-[var(--rl-surface)]">
                      {filteredMatrixScenarios.map((s) => {
                        const covBadgeVariant = s.coverage_type_key.includes("comp")
                          ? "success"
                          : s.coverage_type_key.includes("fire") || s.coverage_type_key.includes("tpft")
                          ? "warning"
                          : "default";

                        return (
                          <tr key={s.catalog_id} className="hover:bg-[var(--rl-bg)]/40 transition-colors">
                            {/* Col 1: Product / Scenario */}
                            <td className="px-4 py-3.5 align-top">
                              <div className="space-y-1.5">
                                <div className="font-bold text-[13px] text-[var(--rl-text-strong)] leading-snug">
                                  {s.scenario_name}
                                </div>
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <Badge variant={covBadgeVariant}>
                                    {s.coverage_type_name}
                                  </Badge>
                                  <span className="rounded bg-[var(--rl-bg)] border border-[var(--rl-border)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--rl-text-muted)]">
                                    {s.system_type}
                                  </span>
                                </div>
                                <div className="text-[11px] text-[var(--rl-text-muted)] space-y-0.5 pt-1">
                                  <div>• <span className="font-medium text-[var(--rl-text-strong)]">Segment:</span> {s.segment_name}</div>
                                  <div>• <span className="font-medium text-[var(--rl-text-strong)]">Vehicle:</span> {s.vehicle_category_name}</div>
                                  <div>• <span className="font-medium text-[var(--rl-text-strong)]">Revision:</span> rev {s.revision_number} ({s.state})</div>
                                </div>
                              </div>
                            </td>

                            {/* Col 2: Defaults */}
                            <td className="px-4 py-3.5 align-top">
                              {s.defaults.length === 0 ? (
                                <span className="text-[var(--rl-text-muted)] italic text-[11px]">
                                  No default benefits configured.
                                </span>
                              ) : (
                                <div className="space-y-2">
                                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-emerald-800 uppercase tracking-wider">
                                    <ShieldCheck size={13} weight="fill" />
                                    <span>{s.defaults.length} Included Benefits</span>
                                  </div>
                                  <div className="grid grid-cols-1 gap-1.5">
                                    {s.defaults.map((d) => (
                                      <div
                                        key={d.offering_id}
                                        className="rounded border border-emerald-200/80 bg-emerald-50/50 p-2 text-emerald-950"
                                      >
                                        <div className="flex items-center justify-between gap-1">
                                          <span className="font-bold text-[12px] text-emerald-950 leading-tight">
                                            {d.label}
                                          </span>
                                          <span className="shrink-0 rounded bg-emerald-600 px-1.5 py-0.5 text-[9px] font-bold uppercase text-white">
                                            0 RM
                                          </span>
                                        </div>
                                        <div className="mt-0.5 text-[11px] text-emerald-800">
                                          {d.display_value || d.description || "Included in base policy"}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </td>

                            {/* Col 3: Addons */}
                            <td className="px-4 py-3.5 align-top">
                              {s.addons.length === 0 ? (
                                <span className="text-[var(--rl-text-muted)] italic text-[11px]">
                                  No optional riders configured.
                                </span>
                              ) : (
                                <div className="space-y-2">
                                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-blue-800 uppercase tracking-wider">
                                    <Plus size={13} weight="bold" />
                                    <span>{s.addons.length} Optional Riders</span>
                                  </div>
                                  <div className="grid grid-cols-1 gap-1.5">
                                    {s.addons.map((a) => (
                                      <div
                                        key={a.offering_id}
                                        className="rounded border border-blue-200/80 bg-blue-50/50 p-2 text-blue-950"
                                      >
                                        <div className="flex items-center justify-between gap-1">
                                          <span className="font-bold text-[12px] text-blue-950 leading-tight">
                                            {a.label}
                                          </span>
                                          <span className="shrink-0 rounded bg-blue-600 px-1.5 py-0.5 text-[9px] font-bold text-white">
                                            {a.price_text}
                                          </span>
                                        </div>
                                        <div className="mt-0.5 text-[11px] text-blue-800">
                                          {a.display_value || a.description || "Optional payable endorsement"}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </td>

                            {/* Col 4: Bundles */}
                            <td className="px-4 py-3.5 align-top">
                              {s.bundles.length === 0 ? (
                                <span className="text-[var(--rl-text-muted)] italic text-[11px]">
                                  None
                                </span>
                              ) : (
                                <div className="space-y-2">
                                  {s.bundles.map((b) => (
                                    <div
                                      key={b.package_id}
                                      className="rounded border border-purple-200 bg-purple-50/60 p-2 text-purple-950"
                                    >
                                      <div className="font-bold text-[11px] text-purple-950">
                                        {b.name}
                                      </div>
                                      {b.plans.length > 0 && (
                                        <div className="mt-1 space-y-0.5">
                                          {b.plans.map((p) => (
                                            <div key={p.plan_id} className="text-[10px] font-medium text-purple-800">
                                              • {p.name}
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </div>
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
            {/* ── Package Tier Ladder (For Package System) ────────────────── */}
            {isPackaged && comprehensivePackages.length > 0 && (
              <div className="rl-tour-ladder rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                      Package Tier Ladder ({comprehensivePackages.length} Tiers)
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
                  {comprehensivePackages.map((pkg, idx) => {
                    const isCurrent = pkg.id === (activePackage?.id || selectedPackageId);
                    const pkgOfferings = allOfferings.filter((o) => o.status !== "retired" && o.applies_to_id === pkg.id);
                    const defCount = pkgOfferings.filter((o) => effectiveRole(o) === "included").length;
                    const addCount = pkgOfferings.filter((o) => effectiveRole(o) === "addon_option").length;
                    const isTopTier = idx === comprehensivePackages.length - 1;

                    return (
                      <button
                        key={pkg.id}
                        onClick={() => setSelectedPackageId(pkg.id)}
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
                    <img src={fileUrl(selectedCompany.logo.url)} alt={selectedCompany.name} className="h-full w-full object-contain" />
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
            {showLiveTemplate && (
              <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
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

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
                  {/* Left (4 cols): Template Slots Summary */}
                  <div className="lg:col-span-4 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-4 space-y-4">
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                        Template Slots Summary
                      </h4>
                      <p className="mt-0.5 text-[11px] text-[var(--rl-text-muted)]">
                        Real-time binding to quotation schedule slots.
                      </p>
                    </div>

                    <div className="text-xs space-y-2 border-t border-[var(--rl-border)] pt-3">
                      <div>
                        <span className="font-semibold text-[var(--rl-text-strong)]">Detected Insurer: </span>
                        <span>{selectedCompany?.name}</span>
                      </div>
                      <div>
                        <span className="font-semibold text-[var(--rl-text-strong)]">Product / Plan: </span>
                        <span>{isPackaged && activePackage ? activePackage.name : selectedCatalog.name}</span>
                      </div>
                      <div>
                        <span className="font-semibold text-[var(--rl-text-strong)]">Vehicle: </span>
                        <span>{selectedVehicle?.name || "Car"} ({selectedSegment?.name || "Private"})</span>
                      </div>
                    </div>

                    <div className="border-t border-[var(--rl-border)] pt-3">
                      <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                        Your Benefits Slot ({defaultOfferings.length} items)
                      </span>
                      <div className="mt-2 max-h-48 overflow-y-auto space-y-1 pr-1 text-[11px]">
                        {defaultOfferings.length === 0 ? (
                          <span className="text-[var(--rl-text-muted)] italic">No default benefits selected.</span>
                        ) : (
                          defaultOfferings.map((o) => (
                            <div key={o.id} className="flex justify-between rounded bg-[var(--rl-surface)] p-1.5 border border-[var(--rl-border)]">
                              <span className="font-medium text-[var(--rl-text-strong)] truncate">
                                {o.label_override || o.concept?.label || o.offering_key}
                              </span>
                              <span className="text-[var(--rl-text-muted)] shrink-0 ml-2 font-semibold">
                                {o.display_value || "Included"}
                              </span>
                            </div>
                          ))
                        )}
                      </div>
                    </div>

                    <div className="border-t border-[var(--rl-border)] pt-3">
                      <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                        Available Add-ons Slot ({addonOfferings.length} items)
                      </span>
                      <div className="mt-2 max-h-48 overflow-y-auto space-y-1 pr-1 text-[11px]">
                        {addonOfferings.length === 0 ? (
                          <span className="text-[var(--rl-text-muted)] italic">No add-ons selected (all included).</span>
                        ) : (
                          addonOfferings.map((o) => (
                            <div key={o.id} className="flex justify-between rounded bg-[var(--rl-surface)] p-1.5 border border-[var(--rl-border)]">
                              <span className="font-medium text-[var(--rl-text-strong)] truncate">
                                {o.label_override || o.concept?.label || o.offering_key}
                              </span>
                              <span className="text-[var(--rl-text-muted)] shrink-0 ml-2 font-semibold">
                                {o.display_value || "Optional"}
                              </span>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right (8 cols): Real Template Canvas Preview */}
                  <div className="lg:col-span-8 grid place-items-center rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[#ececee] p-6 shadow-inner min-h-[580px]">
                    {previewTemplateElements.length === 0 ? (
                      <div className="grid h-full min-h-[420px] w-full place-items-center text-center text-xs text-[var(--rl-text-muted)]">
                        <div>
                          <p className="font-semibold text-[var(--rl-text-strong)]">No template canvas elements</p>
                          <p className="mt-1">This template has no renderable elements. Pick another template above.</p>
                        </div>
                      </div>
                    ) : (
                      <div
                        className="relative w-full max-w-[620px] bg-white shadow-card rounded-[4px] overflow-hidden border border-neutral-300"
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
                              variableValues={{}}
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
              </div>
            )}

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
                              <img src={fileUrl(concept.default_asset.url)} alt={concept.label} className="h-4 w-4 object-contain" />
                            ) : (
                              <ShieldCheck size={16} />
                            )}
                          </div>
                          <span className="font-semibold text-xs text-[var(--rl-text-strong)] truncate">
                            {concept.label}
                          </span>
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
                              defaultValue={offering?.display_value || "Included"}
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingValueInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--rl-text-strong)] flex-1 min-w-0"
                              placeholder="Included"
                              title="Coverage value / limit"
                            />
                            <input
                              type="text"
                              defaultValue={offering?.optional_price?.value ? `RM ${Number(offering.optional_price.value).toFixed(2)}` : (offering?.optional_price?.amount ? `RM ${offering.optional_price.amount}` : "")}
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingPriceInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--rl-text-strong)] w-16 text-right shrink-0"
                              placeholder="RM 0"
                              title="Cost / Price (empty if free)"
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
                                <img src={fileUrl(concept.default_asset.url)} alt={concept.label} className="h-4 w-4 object-contain" />
                              ) : (
                                <Sparkle size={16} />
                              )}
                            </div>
                            <span className="font-semibold text-xs text-[var(--rl-text-strong)] truncate">
                              {concept.label}
                            </span>
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
                              defaultValue={offering?.display_value || "Optional"}
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingValueInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--rl-text-strong)] flex-1 min-w-0"
                              placeholder="Optional"
                              title="Coverage value / limit"
                            />
                            <input
                              type="text"
                              defaultValue={offering?.optional_price?.value ? `RM ${Number(offering.optional_price.value).toFixed(2)}` : (offering?.optional_price?.amount ? `RM ${offering.optional_price.amount}` : "")}
                              onClick={(e) => e.stopPropagation()}
                              onBlur={(e) => {
                                if (offering) updateOfferingPriceInline(offering, e.target.value);
                              }}
                              className="rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--rl-text-strong)] w-16 text-right shrink-0"
                              placeholder="RM 0"
                              title="Cost / Price (empty if free)"
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
                <button
                  onClick={() => setActiveTab("revisions")}
                  className={`font-semibold transition-colors ${activeTab === "revisions"
                    ? "text-[var(--rl-text-strong)] border-b-2 border-[var(--rl-black)] pb-1"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    }`}
                >
                  Revisions ({selectedCatalog.revisions?.length || 1})
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

              {activeTab === "revisions" && (
                <div className="mt-4 space-y-2 text-xs">
                  {(selectedCatalog.revisions || []).map((rev) => (
                    <div key={rev.id} className="flex items-center justify-between rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-3">
                      <div>
                        <span className="font-semibold text-[var(--rl-text-strong)]">Revision #{rev.revision_number}</span>
                        <span className="ml-2 text-[var(--rl-text-muted)]">{rev.content_hash.slice(0, 12)}...</span>
                      </div>
                      <span className="rounded-[4px] bg-[var(--rl-bg)] border border-[var(--rl-border)] px-2 py-0.5 text-[10px] uppercase font-bold text-[var(--rl-text-muted)]">
                        {rev.state}
                      </span>
                    </div>
                  ))}
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

      {/* ── Dialog: Add Configuration ────────────────────────────────── */}
      {dialog === "config" && (
        <Dialog open={dialog === "config"} onOpenChange={() => setDialog(null)} title="Add Configuration">
          <div className="max-w-md p-6">
            <p className="text-xs text-[var(--rl-text-muted)]">
              Create a new product configuration or package tier.
            </p>
            <div className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)]">Configuration Name</label>
                <Input
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Private Car Protector"
                  className="mt-1 w-full"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="formAsPackage"
                  checked={formAsPackage}
                  onChange={(e) => setFormAsPackage(e.target.checked)}
                />
                <label htmlFor="formAsPackage" className="font-medium text-[var(--rl-text-strong)]">
                  Create as named package (Package mode)
                </label>
              </div>
              {formAsPackage && (
                <div>
                  <label className="block font-semibold text-[var(--rl-text-strong)]">Package Name</label>
                  <Input
                    value={formPackageName}
                    onChange={(e) => setFormPackageName(e.target.value)}
                    placeholder="e.g. auto365 Comprehensive Lite"
                    className="mt-1 w-full"
                  />
                </div>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" size="sm" onClick={() => setDialog(null)}>
                  Cancel
                </Button>
                <Button size="sm" onClick={createConfig} disabled={saving}>
                  {saving ? "Creating..." : "Create"}
                </Button>
              </div>
            </div>
          </div>
        </Dialog>
      )}

      {/* ── Dialog: Clone Package ────────────────────────────────────── */}
      {dialog === "clone" && (
        <Dialog open={dialog === "clone"} onOpenChange={() => setDialog(null)} title="Clone Package">
          <div className="max-w-md p-6">
            <p className="text-xs text-[var(--rl-text-muted)]">
              Create a duplicate package tier based on this active configuration.
            </p>
            <div className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)]">New Package Name</label>
                <Input
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="mt-1 w-full"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" size="sm" onClick={() => setDialog(null)}>
                  Cancel
                </Button>
                <Button size="sm" onClick={clonePackage} disabled={saving}>
                  {saving ? "Cloning..." : "Clone"}
                </Button>
              </div>
            </div>
          </div>
        </Dialog>
      )}

      {/* ── Dialog: New Bundle ───────────────────────────────────────── */}
      {dialog === "bundle" && (
        <Dialog open={dialog === "bundle"} onOpenChange={() => setDialog(null)} title="New Addon Bundle">
          <div className="max-w-md p-6">
            <p className="text-xs text-[var(--rl-text-muted)]">
              Create a grouped bundle of add-on offerings.
            </p>
            <div className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-[var(--rl-text-strong)]">Bundle Name</label>
                <Input
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Safety Protection Bundle"
                  className="mt-1 w-full"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" size="sm" onClick={() => setDialog(null)}>
                  Cancel
                </Button>
                <Button size="sm" onClick={createBundle} disabled={saving}>
                  {saving ? "Creating..." : "Create Bundle"}
                </Button>
              </div>
            </div>
          </div>
        </Dialog>
      )}

      {/* ── Dialog: AI Seed & Sync Spec Modal ───────────────────────── */}
      {showAiModal && (
        <Dialog
          open={showAiModal}
          onOpenChange={setShowAiModal}
          title={`AI Seed & Sync Specification — ${matrixData?.company.name || "Insurer"}`}
        >
          <div className="max-w-4xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setAiModalTab("spec")}
                  className={`rounded-[var(--rl-radius-sm)] px-3 py-1.5 text-xs font-semibold transition-all ${
                    aiModalTab === "spec"
                      ? "bg-[var(--rl-black)] text-white"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  1. AI Seed Spec & Markdown Table
                </button>
                <button
                  type="button"
                  onClick={() => setAiModalTab("diff")}
                  className={`rounded-[var(--rl-radius-sm)] px-3 py-1.5 text-xs font-semibold transition-all ${
                    aiModalTab === "diff"
                      ? "bg-[var(--rl-black)] text-white"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  2. Non-Destructive Diff Tester
                </button>
              </div>

              {aiModalTab === "spec" && (
                <Button
                  size="sm"
                  onClick={copyAiPrompt}
                  icon={copiedPrompt ? <Check size={14} weight="bold" /> : <Copy size={14} weight="bold" />}
                  className="bg-emerald-700 text-white hover:bg-emerald-800"
                >
                  {copiedPrompt ? "Copied Prompt & Table!" : "Copy AI Prompt & Table"}
                </Button>
              )}
            </div>

            {aiModalTab === "spec" ? (
              <div className="space-y-3">
                <div className="rounded-[var(--rl-radius-sm)] border border-blue-200 bg-blue-50/70 p-3 text-xs text-blue-950">
                  <p className="font-semibold">How to use this with an AI agent (Claude, ChatGPT, Gemini):</p>
                  <p className="mt-1 text-[11px] text-blue-900">
                    Click <strong>&quot;Copy AI Prompt & Table&quot;</strong> above, then paste it along with any new insurer brochure or policy schedule into your chat.
                    The AI will understand the exact structure and return only the changes or new benefits needed without re-seeding existing catalog rows!
                  </p>
                </div>

                <div className="relative">
                  <pre className="max-h-[420px] overflow-y-auto rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3.5 font-mono text-[11px] text-[var(--rl-text-strong)] leading-relaxed whitespace-pre-wrap">
                    {aiSyncPrompt}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="rounded-[var(--rl-radius-sm)] border border-emerald-200 bg-emerald-50/70 p-3 text-xs text-emerald-950">
                  <p className="font-semibold">Non-Destructive Delta Sync Inspector:</p>
                  <p className="mt-1 text-[11px] text-emerald-900">
                    Paste the JSON payload returned by an AI or drafted manually to test which benefits will be added or modified in the database.
                  </p>
                </div>

                <div className="grid gap-1.5">
                  <label className="text-xs font-semibold text-[var(--rl-text-strong)]">
                    Incoming Delta JSON:
                  </label>
                  <textarea
                    value={aiDiffInput}
                    onChange={(e) => setAiDiffInput(e.target.value)}
                    placeholder={`{\n  "scenarios": [\n    {\n      "scenario_name": "Private Car Protector",\n      "defaults": [\n        {"concept_key": "new_breakdown_assist", "display_value": "Free Towing 100km"}\n      ],\n      "addons": [\n        {"concept_key": "windscreen", "display_value": "RM 1,200", "price": 180.0}\n      ]\n    }\n  ]\n}`}
                    className="h-44 w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3 font-mono text-xs text-[var(--rl-text-strong)] focus:outline-none"
                  />
                </div>

                <div className="flex justify-end gap-2">
                  <Button
                    size="sm"
                    onClick={runAiDiffCheck}
                    disabled={aiDiffLoading || !aiDiffInput.trim()}
                    icon={<Lightning size={14} weight="fill" />}
                    className="bg-[var(--rl-black)] text-white"
                  >
                    {aiDiffLoading ? "Analyzing Changes..." : "Run Diff Check"}
                  </Button>
                </div>

                {aiDiffResult && (
                  <div className="mt-3 space-y-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3.5 text-xs">
                    {aiDiffResult.error ? (
                      <div className="text-[var(--rl-red)] font-semibold">{aiDiffResult.error}</div>
                    ) : (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2">
                          <span className="font-bold text-[var(--rl-text-strong)]">
                            Diff Analysis Result: {aiDiffResult.total_changes || 0} change(s) detected
                          </span>
                          <Badge variant={aiDiffResult.total_changes > 0 ? "success" : "default"}>
                            {aiDiffResult.total_changes > 0 ? "Incremental Updates Ready" : "Up-to-date"}
                          </Badge>
                        </div>

                        {aiDiffResult.scenarios_diff?.map((sd: any, idx: number) => (
                          <div key={idx} className="rounded border border-[var(--rl-border)] p-2.5 space-y-1.5 bg-[var(--rl-bg)]">
                            <div className="font-bold text-[12px] text-[var(--rl-text-strong)]">
                              Scenario: {sd.scenario_name} ({sd.status})
                            </div>
                            {sd.added_defaults?.length > 0 && (
                              <div className="text-emerald-800 text-[11px]">
                                + Added Defaults: {sd.added_defaults.map((d: any) => d.concept_key).join(", ")}
                              </div>
                            )}
                            {sd.added_addons?.length > 0 && (
                              <div className="text-blue-800 text-[11px]">
                                + Added Add-ons: {sd.added_addons.map((a: any) => `${a.concept_key} (${a.price ? `RM ${a.price}` : a.display_value})`).join(", ")}
                              </div>
                            )}
                            {sd.modified_addons?.length > 0 && (
                              <div className="text-amber-800 text-[11px]">
                                • Modified Add-on Pricing: {sd.modified_addons.map((m: any) => `${m.to.concept_key}: RM ${m.from.price} → RM ${m.to.price}`).join(", ")}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </Dialog>
      )}
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

