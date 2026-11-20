"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { WorkspaceSnapshot } from "../types";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { buildUnifiedMatrixCards } from "@/lib/unified-addon-engine";
import {
  applyPresetToCanvasElement,
  getAllBenefitPresets,
  getBenefitPreset,
  type BenefitCardStyle,
} from "@/lib/benefit-presets";
import {
  balanceBenefitGridElements,
  type CanvasElement,
} from "@/components/template-canvas/shared";
import type {
  PublishedTemplateOption,
  TemplateSelectionImpact,
} from "./TemplateConfigCard";

export interface UseReviewCatalogAndTemplateOptions {
  id: string;
  workspace: WorkspaceSnapshot | null;
  formValues: Record<string, string>;
  setFormValues: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  currentVehicleCategory: "Car" | "Motorcycle" | "Lorry";
  currentCards: any[];
  addonCards: any[];
  showDesign2Schedule: boolean;
  extrasDisplayMode?: "itemized" | "lump_sum" | "none";
  queueOperation: (op: Record<string, unknown> & { op: string }, path: string) => void;
  save: () => Promise<any>;
  commitFieldDirectly: (name: string, value: string) => void;
  setSyncHighlight: (val: { field: "vehicle_type" | "product_package"; prev: string; next: string; timestamp: number } | null) => void;
  decideField: (name: string, decision: any, value?: any) => void;
  onQueue: (op: Record<string, unknown> & { op: string }, path: string) => void;
}

export function useReviewCatalogAndTemplate({
  id,
  workspace,
  formValues,
  setFormValues,
  currentVehicleCategory,
  currentCards,
  addonCards,
  showDesign2Schedule,
  extrasDisplayMode,
  queueOperation,
  save,
  commitFieldDirectly,
  setSyncHighlight,
  decideField,
  onQueue,
}: UseReviewCatalogAndTemplateOptions) {
  const [companies, setCompanies] = useState<Array<{ id: string; name: string; logo_asset_id?: string | null }>>([]);
  const [companyWorkspace, setCompanyWorkspace] = useState<any | null>(null);
  const [pinLoading, setPinLoading] = useState(false);

  const [publishedTemplates, setPublishedTemplates] = useState<PublishedTemplateOption[]>([]);
  const [selectedRevisionId, setSelectedRevisionId] = useState<string | null>(null);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [templateImpact, setTemplateImpact] = useState<TemplateSelectionImpact | null>(null);

  const [previewTemplate, setPreviewTemplate] = useState<any | null>(null);
  const [previewZoom, setPreviewZoom] = useState(0.80);
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewScrollRef = useRef<HTMLDivElement | null>(null);
  const userPickedRevisionRef = useRef(false);

  const [allBenefitPresets, setAllBenefitPresets] = useState<BenefitCardStyle[]>(() => getAllBenefitPresets());
  const [selectedBenefitPreset, setSelectedBenefitPreset] = useState<string>(() => {
    try {
      return (workspace?.fields?.benefit_preset as any)?.value || localStorage.getItem("risklocker_default_benefit_preset") || "masonry-flow";
    } catch {
      return "masonry-flow";
    }
  });

  const handleSelectBenefitPreset = useCallback(
    (presetId: string) => {
      setSelectedBenefitPreset(presetId);
      try {
        localStorage.setItem("risklocker_default_benefit_preset", presetId);
      } catch {}
      decideField("benefit_preset", "edit", presetId);
      const cfg = getBenefitPreset(presetId);
      decideField("benefit_preset_config", "edit", JSON.stringify(cfg));
    },
    [decideField]
  );

  const isCurrentEV = useMemo(
    () => String(formValues?.vehicle_type || workspace?.fields?.vehicle_type?.value || "").toUpperCase().startsWith("EV"),
    [formValues?.vehicle_type, workspace?.fields?.vehicle_type]
  );

  const productOptions = useMemo(() => {
    const raw = companyWorkspace?.products || [];
    const valid = raw.filter((p: any) => {
      if (p.status === "archived" || p.status === "retired" || (p.name && /^product-/i.test(p.name))) return false;
      const isEvProduct = /\(ev\)|(\bev\b)|electric/i.test(p.name || "");
      return isCurrentEV ? isEvProduct : !isEvProduct;
    });

    // Ensure currently pinned product is never dropped from dropdown options
    const pinnedId = workspace?.pinned.product_id;
    if (pinnedId && !valid.some((p: any) => p.id === pinnedId)) {
      const pinnedName = workspace?.pinned_names.product_name || "Current Package";
      valid.push({ id: pinnedId, name: pinnedName, status: "active" });
    }

    const seen = new Set<string>();
    return valid.filter((p: any) => {
      const key = (p.name || "").trim().toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [companyWorkspace, isCurrentEV, workspace?.pinned.product_id, workspace?.pinned_names.product_name]);

  const categorizedProducts = useMemo(() => {
    const cars: typeof productOptions = [];
    const motorcycles: typeof productOptions = [];
    const lorries: typeof productOptions = [];
    for (const prod of productOptions) {
      const lower = (prod.name || "").toLowerCase();
      if (/motorcycle|bike|motosikal/i.test(lower)) motorcycles.push(prod);
      else if (/lorry|truck|commercial|c\s*permit|haulage/i.test(lower)) lorries.push(prod);
      else cars.push(prod);
    }
    return { cars, motorcycles, lorries };
  }, [productOptions]);

  const tierOptions = useMemo(
    () => (companyWorkspace?.tiers || []).filter((t: any) => t.product_id === workspace?.pinned.product_id),
    [companyWorkspace, workspace?.pinned.product_id]
  );

  const isDesign2 = useMemo(() => {
    const tKey = String((previewTemplate?.config as any)?.template_key || (previewTemplate?.config as any)?.v7_master_key || "");
    return Boolean(
      previewTemplate?.config?.layout_engine === "design2" ||
      tKey === "motor_modern_design_2" ||
      tKey.startsWith("motor_modern_design_2") ||
      previewTemplate?.config?.template_name?.toLowerCase().includes("design 2") ||
      previewTemplate?.config?.template_name?.toLowerCase().includes("design2")
    );
  }, [previewTemplate]);

  const design2CardCount = useMemo(() => {
    if (!isDesign2) return 0;
    const compName = String((workspace?.fields?.insurance_company as any)?.value || workspace?.pinned_names?.company_name || workspace?.hierarchy?.company_name || "");
    return buildUnifiedMatrixCards(currentCards, addonCards, undefined, 24, 24, compName).length;
  }, [isDesign2, currentCards, addonCards, workspace?.fields, workspace?.pinned_names?.company_name, workspace?.hierarchy?.company_name]);

  const balancedElements = useMemo(() => {
    if (!previewTemplate?.config?.canvas) return [];
    const rawElements = (previewTemplate.config.canvas.elements || []).map((el: any) =>
      el.type === "benefit-grid" ? applyPresetToCanvasElement(el, selectedBenefitPreset) : el
    );
    const effDisplayOptions = {
      ...workspace?.display_options,
      ...(extrasDisplayMode ? { extras_mode: extrasDisplayMode } : {}),
      ...(showDesign2Schedule ? { include_benefit_schedule: true } : {}),
    };
    return balanceBenefitGridElements(rawElements, {
      ...workspace?.benefit_cards,
      current_benefits: currentCards,
      available_addons: addonCards,
      extras: workspace?.extras,
      displayOptions: effDisplayOptions,
    } as any);
  }, [previewTemplate, workspace?.benefit_cards, workspace?.extras, selectedBenefitPreset, workspace?.display_options, showDesign2Schedule, extrasDisplayMode, currentCards, addonCards]);

  const canvasH = useMemo(() => {
    if (isDesign2) {
      const hideAddons = Boolean((previewTemplate?.config as any)?.hide_addon_upgrades);
      const baseD2H = Number(
        (previewTemplate?.config as any)?.page_profile?.height ||
          previewTemplate?.config?.canvas?.height ||
          (hideAddons ? 580 : 1123)
      );
      return showDesign2Schedule && !hideAddons ? baseD2H * 2 + 16 : baseD2H;
    }
    const baseH = previewTemplate?.config?.canvas?.height || 1123;
    if (!balancedElements.length) return baseH;
    const maxB = Math.max(0, ...balancedElements.map((e: any) => (e.y || 0) + (e.h || 0)));
    return maxB + 30 > baseH ? maxB + 30 : baseH;
  }, [isDesign2, showDesign2Schedule, balancedElements, previewTemplate]);

  const previewTemplateAssets = useMemo(() => {
    if (!previewTemplate?.config) return [];
    const list: Array<{ id: string; label: string; url: string }> = Object.entries(previewTemplate.config.assets || {}).map(([key, id]) => ({
      id: String(id),
      label: key,
      url: String(id).includes("-") ? `/business/assets/${id}/content?profile=ui` : `/template-assets/${id}`,
    }));
    return list;
  }, [previewTemplate]);

  async function pinCatalog(
    companyId: string,
    productId?: string | null,
    tierId?: string | null,
    options?: { stageOnly?: boolean },
  ) {
    setPinLoading(true);
    const company = companies.find((c) => c.id === companyId);
    const product = productId ? productOptions.find((p: any) => p.id === productId) : null;
    const tier = tierId ? tierOptions.find((t: any) => t.id === tierId) : null;
    if (company) setFormValues((v) => ({ ...v, insurance_company: company.name }));
    onQueue({
      op: "pin_catalog",
      company_id: companyId,
      ...(productId ? { product_id: productId } : {}),
      ...(tierId ? { tier_id: tierId } : {}),
      company_name: company?.name || workspace?.pinned_names.company_name,
      ...(product ? { product_name: product.name } : {}),
      ...(tier ? { tier_name: tier.name } : {}),
    }, "catalog");
    if (options?.stageOnly) {
      setPinLoading(false);
      return;
    }
    try { await save(); } catch {} finally { setPinLoading(false); }
  }

  function handlePackageSelect(productId: string) {
    if (!productId || !workspace?.pinned.company_id) {
      if (workspace?.pinned.company_id) pinCatalog(workspace.pinned.company_id as string, null);
      return;
    }
    const selectedProd = productOptions.find((p: any) => p.id === productId);
    if (selectedProd) {
      const lower = (selectedProd.name || "").toLowerCase();
      const targetCat = /motorcycle|bike/i.test(lower) ? "Motorcycle" : /lorry|commercial/i.test(lower) ? "Lorry" : "Car";
      const curCat = currentVehicleCategory;
      if (targetCat !== curCat) {
        const isEv = String(formValues.vehicle_type || "").startsWith("EV");
        const newV = isEv ? (targetCat === "Motorcycle" ? "EVMotorcycle" : targetCat === "Lorry" ? "EVCommercial" : "EVSaloonCar") : (targetCat === "Motorcycle" ? "Motorcycle" : targetCat === "Lorry" ? "Lorry" : "Car");
        setSyncHighlight({ field: "vehicle_type", prev: curCat, next: targetCat, timestamp: Date.now() });
        setFormValues((v) => ({ ...v, vehicle_type: newV }));
        commitFieldDirectly("vehicle_type", newV);
      }
    }
    pinCatalog(workspace.pinned.company_id as string, productId);
  }

  async function pinPackageTier(packageId: string) {
    if (!workspace?.pinned.company_id) return;
    setPinLoading(true);
    onQueue({ op: "select_package_tier", package_id: packageId }, "package_tier");
    try { await save(); } catch {} finally { setPinLoading(false); }
  }

  async function selectTemplateDirectly(templateRevisionId: string) {
    setTemplateError(null);
    setTemplateImpact(null);
    if (!templateRevisionId) return;
    userPickedRevisionRef.current = true;
    const option = publishedTemplates.find((t) => t.template_revision_id === templateRevisionId) || publishedTemplates[0];
    if (!option) return;
    setSelectedRevisionId(option.template_revision_id);
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
    save().catch(() => undefined);
  }

  useEffect(() => {
    let cancelled = false;
    api<{ companies: { items: Array<{ id: string; name: string }> } }>("/business/companies?page_size=100")
      .then((res) => { if (!cancelled) setCompanies(res.companies?.items || []); });
    api<{ templates: PublishedTemplateOption[] }>("/business/templates/published")
      .then((res) => {
        if (!cancelled && res.templates?.length) {
          setPublishedTemplates(res.templates);
          const pinned = workspace?.pinned.template_revision_id;
          const match =
            (pinned ? res.templates.find((t) => t.template_revision_id === pinned) : null) ||
            res.templates.find((t) => t.is_default) ||
            res.templates.find((t) => t.config?.layout_engine === "design2" || t.name.toLowerCase().includes("design 2")) ||
            res.templates[0];
          if (match && !selectedRevisionId) {
            setSelectedRevisionId(match.template_revision_id);
            if (match.config) setPreviewTemplate({ template_id: match.template_id, template_revision_id: match.template_revision_id, revision_number: match.revision_number, config_hash: match.config_hash, source: "template_revision", config: match.config, binding: { template_id: match.template_id, template_revision_id: match.template_revision_id, base_hash: match.config_hash } });
          }
        }
      }).catch((e) => { if (!cancelled) setTemplateError(apiErrorMessage(e)); })
      .finally(() => { if (!cancelled) setTemplatesLoading(false); });
    return () => { cancelled = true; };
  }, [workspace?.pinned.template_revision_id]);

  useEffect(() => {
    const compId = workspace?.pinned.company_id;
    if (!compId) { setCompanyWorkspace(null); return; }
    let cancelled = false;
    api<{ workspace: any }>(`/business/companies/${compId}/workspace`)
      .then((r) => { if (!cancelled) setCompanyWorkspace(r.workspace); });
    return () => { cancelled = true; };
  }, [workspace?.pinned.company_id]);

  return {
    companies,
    companyWorkspace,
    pinLoading,
    publishedTemplates,
    selectedRevisionId,
    templatesLoading,
    templateError,
    templateImpact,
    setTemplateImpact,
    previewTemplate,
    previewZoom,
    setPreviewZoom,
    previewLoading,
    previewScrollRef,
    allBenefitPresets,
    selectedBenefitPreset,
    handleSelectBenefitPreset,
    productOptions,
    categorizedProducts,
    isDesign2,
    design2CardCount,
    canvasH,
    balancedElements,
    previewTemplateAssets,
    pinCatalog,
    handlePackageSelect,
    pinPackageTier,
    selectTemplateDirectly,
  };
}
