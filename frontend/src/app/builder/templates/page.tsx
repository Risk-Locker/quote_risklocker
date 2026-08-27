"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Check,
  CheckCircle,
  CopySimple,
  Crown,
  Eye,
  FilePdf,
  FilePlus,
  ImageSquare,
  Info,
  MagnifyingGlass,
  PaintBrush,
  PencilSimple,
  Plus,
  ShieldCheck,
  Sparkle,
  Square,
  Star,
  Trash,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { BuilderNav } from "@/components/builder-nav";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Tooltip } from "@/components/ui/tooltip";
import { useToast } from "@/components/ui/toast";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Revision = {
  id: string;
  revision_number: number;
  state: "draft" | "published" | "retired" | "compatibility";
  published_at?: string | null;
  page_profile?: { name: string; width: number; height: number; unit: string } | null;
};

type CanvasNode = {
  id: string;
  type: string;
  x: number;
  y: number;
  w: number;
  h: number;
  text?: string;
  variableId?: string;
  gridKind?: string;
  shapeKind?: string;
  style?: { background?: string; color?: string; borderColor?: string; borderWidth?: number; fontSize?: number };
};

type TemplateRecord = {
  id: string;
  revision: number;
  name: string;
  status: string;
  locked: boolean;
  is_default: boolean;
  fixed_fields: {
    version?: number;
    canvas?: { width?: number; height?: number; elements?: CanvasNode[] };
    page_profile?: { name?: string; width?: number; height?: number; unit?: string };
  };
  template_revisions: Revision[];
  latest_published_revision?: Revision | null;
};

export type GlobalBenefit = {
  id: string;
  concept_key: string;
  label: string;
  category?: "default" | "addon";
  variants?: string[];
  description?: string | null;
  sort_order: number;
  status: string;
  default_asset?: {
    id: string;
    file_name: string;
    url: string;
  } | null;
};

export type BenefitCardStyle = {
  id: string;
  name: string;
  is_default?: boolean;
  is_custom?: boolean;
  shape: "rounded" | "racetrack" | "square" | "soft" | "oval";
  layout: "merged-2col" | "masonry" | "horizontal" | "tile" | "compact";
  borderWidth: number;
  borderStyle: "solid" | "dashed" | "none";
  elevation: "flat" | "shadow" | "lift";
  uniformHeight: number; // in px, e.g. 0 for auto, 72, 84, 96, 110
  iconSize: number; // in px, e.g. 28, 32, 40, 48, 56
  imageFit: "contain" | "cover" | "scale-down";
  iconPadShape: "box" | "circle" | "none" | "dark";
  titleSize: number;
  titleWeight: "medium" | "semibold" | "bold";
  textWrap: "truncate" | "wrap";
  valueBadgeStyle: "green" | "pill" | "subtle" | "red" | "hidden";
  showDescription: boolean;
  showCoverage: boolean;
  showCost: boolean;
  bgColor: string;
  borderColor: string;
  textColor: string;
  accentColor: string;
};

const SYSTEM_BENEFIT_PRESETS: BenefitCardStyle[] = [
  {
    id: "signature-2col",
    name: "Signature 2-Column (Default)",
    is_default: true,
    is_custom: false,
    shape: "rounded",
    layout: "merged-2col",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "shadow",
    uniformHeight: 0,
    iconSize: 44,
    imageFit: "contain",
    iconPadShape: "box",
    titleSize: 12,
    titleWeight: "bold",
    textWrap: "wrap",
    valueBadgeStyle: "red",
    showDescription: true,
    showCoverage: true,
    showCost: true,
    bgColor: "#ffffff",
    borderColor: "#e2e8f0",
    textColor: "#0f172a",
    accentColor: "#dc2626",
  },
  {
    id: "masonry-flow",
    name: "Masonry Flow (Dynamic)",
    is_custom: false,
    shape: "rounded",
    layout: "masonry",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "shadow",
    uniformHeight: 0,
    iconSize: 40,
    imageFit: "contain",
    iconPadShape: "box",
    titleSize: 12,
    titleWeight: "bold",
    textWrap: "wrap",
    valueBadgeStyle: "green",
    showDescription: true,
    showCoverage: true,
    showCost: true,
    bgColor: "#ffffff",
    borderColor: "#e2e8f0",
    textColor: "#0f172a",
    accentColor: "#dc2626",
  },
  {
    id: "elevated-3d",
    name: "Elevated 3D Card (Shadow)",
    is_custom: false,
    shape: "soft",
    layout: "merged-2col",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "lift",
    uniformHeight: 0,
    iconSize: 44,
    imageFit: "contain",
    iconPadShape: "box",
    titleSize: 13,
    titleWeight: "bold",
    textWrap: "wrap",
    valueBadgeStyle: "red",
    showDescription: true,
    showCoverage: true,
    showCost: true,
    bgColor: "#ffffff",
    borderColor: "#e2e8f0",
    textColor: "#0f172a",
    accentColor: "#dc2626",
  },
  {
    id: "grid-tile",
    name: "Grid Tile (Vertical Icon)",
    is_custom: false,
    shape: "rounded",
    layout: "tile",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "flat",
    uniformHeight: 0,
    iconSize: 48,
    imageFit: "contain",
    iconPadShape: "circle",
    titleSize: 12,
    titleWeight: "bold",
    textWrap: "wrap",
    valueBadgeStyle: "pill",
    showDescription: true,
    showCoverage: true,
    showCost: true,
    bgColor: "#f8fafc",
    borderColor: "#e2e8f0",
    textColor: "#0f172a",
    accentColor: "#dc2626",
  },
  {
    id: "compact-minimal",
    name: "Compact Minimalist Row",
    is_custom: false,
    shape: "square",
    layout: "compact",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "flat",
    uniformHeight: 52,
    iconSize: 28,
    imageFit: "contain",
    iconPadShape: "none",
    titleSize: 11,
    titleWeight: "semibold",
    textWrap: "truncate",
    valueBadgeStyle: "subtle",
    showDescription: false,
    showCoverage: true,
    showCost: true,
    bgColor: "#ffffff",
    borderColor: "#f1f5f9",
    textColor: "#0f172a",
    accentColor: "#6e6e73",
  },
  {
    id: "dark-signature",
    name: "Dark Luxury Executive",
    is_custom: false,
    shape: "rounded",
    layout: "merged-2col",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "shadow",
    uniformHeight: 0,
    iconSize: 44,
    imageFit: "contain",
    iconPadShape: "dark",
    titleSize: 12,
    titleWeight: "bold",
    textWrap: "truncate",
    valueBadgeStyle: "red",
    showDescription: true,
    showCoverage: true,
    showCost: true,
    bgColor: "#0f172a",
    borderColor: "#334155",
    textColor: "#ffffff",
    accentColor: "#ef4444",
  },
];


function templateState(template: TemplateRecord) {
  if (template.status === "retired") return "retired";
  return template.latest_published_revision?.state || (template.fixed_fields.version === 7 ? "draft" : "compatibility");
}

function pageProfile(template: TemplateRecord) {
  const published = template.latest_published_revision?.page_profile;
  if (published) return published;
  const page = template.fixed_fields.page_profile;
  const canvas = template.fixed_fields.canvas;
  return {
    name: page?.name || (Number(canvas?.height || 1123) > 1200 ? "Custom portrait" : "A4"),
    width: Number(page?.width || canvas?.width || 794),
    height: Number(page?.height || canvas?.height || 1123),
    unit: page?.unit || "px",
  };
}

function TemplateThumbnail({ template, large = false }: { template: TemplateRecord; large?: boolean }) {
  const page = pageProfile(template);
  const elements = (template.fixed_fields.canvas?.elements || []).filter((item) => item.type !== "layer-group");
  const textNodes = elements.filter((item) => item.type === "text" || item.type === "variable").slice(0, large ? 80 : 42);
  const shapeNodes = elements.filter((item) => !["text", "variable", "layer-group"].includes(item.type)).slice(0, large ? 100 : 60);
  return (
    <div className={`grid place-items-center bg-[#ececee] ${large ? "h-[68vh] p-8" : "h-[300px] p-6"}`}>
      <svg viewBox={`0 0 ${page.width} ${page.height}`} className="h-full max-w-full bg-white shadow-card" role="img" aria-label={`Preview of ${template.name}`}>
        <rect x="0" y="0" width={page.width} height={page.height} fill="white" />
        {shapeNodes.map((node) => {
          const fill = node.style?.background || (node.type === "benefit-grid" ? "#fff7f7" : "#f0f0f1");
          const stroke = node.type === "benefit-grid" ? "#ed1c24" : (node.style?.borderColor || "#d1d1d4");
          const strokeWidth = Math.max(1, Number(node.style?.borderWidth || 1));
          if (node.type === "line") return <line key={node.id} x1={node.x} y1={node.y} x2={node.x + node.w} y2={node.y + node.h} stroke={node.style?.color || "#171717"} strokeWidth={strokeWidth} />;
          if (node.type === "ellipse" || node.shapeKind === "circle") return <ellipse key={node.id} cx={node.x + node.w / 2} cy={node.y + node.h / 2} rx={node.w / 2} ry={node.h / 2} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />;
          if (node.type === "triangle" || node.shapeKind === "triangle") return <polygon key={node.id} points={`${node.x + node.w / 2},${node.y} ${node.x + node.w},${node.y + node.h} ${node.x},${node.y + node.h}`} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />;
          if (node.type === "diamond" || node.shapeKind === "diamond") return <polygon key={node.id} points={`${node.x + node.w / 2},${node.y} ${node.x + node.w / 2},${node.y + node.h / 2} ${node.x + node.w / 2},${node.y + node.h} ${node.x},${node.y + node.h / 2}`} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />;
          return <rect key={node.id} x={node.x} y={node.y} width={node.w} height={node.h} fill={fill} stroke={stroke} strokeWidth={strokeWidth} strokeDasharray={node.type === "benefit-grid" ? "7 5" : undefined} />;
        })}
        {textNodes.map((node) => (
          <text key={node.id} x={node.x} y={node.y + Math.min(node.h, Number(node.style?.fontSize || 14))} fill={node.type === "variable" ? "#ed1c24" : (node.style?.color || "#171717")} fontSize={Math.max(7, Number(node.style?.fontSize || 14))} fontWeight={node.type === "variable" ? 600 : 400}>
            {(node.type === "variable" ? `{${node.variableId || "variable"}}` : (node.text || "Text")).slice(0, 70)}
          </text>
        ))}
      </svg>
    </div>
  );
}

export default function BuilderTemplatesPage() {
  const [activeMasterTab, setActiveMasterTab] = useState<"quotation" | "benefits">("quotation");

  // Quotation Templates State
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [profileFilter, setProfileFilter] = useState("all");
  const [newName, setNewName] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [preview, setPreview] = useState<TemplateRecord | null>(null);
  const [pendingRetire, setPendingRetire] = useState<TemplateRecord | null>(null);
  const [pendingRename, setPendingRename] = useState<TemplateRecord | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<TemplateRecord | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { toast } = useToast();

  // Benefit Card Templates State
  const [systemPresets] = useState<BenefitCardStyle[]>(SYSTEM_BENEFIT_PRESETS);
  const [customPresets, setCustomPresets] = useState<BenefitCardStyle[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string>("signature-2col");
  const [customStyle, setCustomStyle] = useState<BenefitCardStyle>(SYSTEM_BENEFIT_PRESETS[0]);
  const [pendingDeletePreset, setPendingDeletePreset] = useState<BenefitCardStyle | null>(null);

  // Real Global Benefits for Live Asset Preview
  const [globalBenefits, setGlobalBenefits] = useState<GlobalBenefit[]>([]);
  const [loadingBenefits, setLoadingBenefits] = useState(false);

  // Load saved custom presets from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem("risklocker_benefit_card_presets");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          setCustomPresets(parsed);
        }
      }
    } catch {
      // ignore JSON parse errors
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api<{ templates: TemplateRecord[] }>("/admin/templates");
      setTemplates(result.templates);
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadGlobalBenefits = useCallback(async () => {
    setLoadingBenefits(true);
    try {
      const res = await api<{ benefit_concepts: { items: GlobalBenefit[] } }>("/business/benefit-concepts?page=1&page_size=100");
      setGlobalBenefits(res.benefit_concepts.items || []);
    } catch {
      // keep fallback
    } finally {
      setLoadingBenefits(false);
    }
  }, []);

  useEffect(() => {
    void load();
    void loadGlobalBenefits();
  }, [load, loadGlobalBenefits]);

  const profiles = useMemo(() => [...new Set(templates.map((item) => pageProfile(item).name))].sort(), [templates]);
  const visibleTemplates = useMemo(() => {
    return templates.filter((template) => {
      const matchesText = !search.trim() || template.name.toLowerCase().includes(search.trim().toLowerCase());
      const matchesStatus = statusFilter === "all" || templateState(template) === statusFilter;
      const matchesProfile = profileFilter === "all" || pageProfile(template).name === profileFilter;
      return matchesText && matchesStatus && matchesProfile;
    });
  }, [profileFilter, search, statusFilter, templates]);

  async function createTemplate(event: React.FormEvent) {
    event.preventDefault();
    setCreating(true);
    setError("");
    try {
      const result = await api<{ template: TemplateRecord }>("/admin/templates", {
        method: "POST",
        body: JSON.stringify({ name: newName.trim(), insurance_type: "Motor" }),
      });
      window.location.assign(`/builder/templates/${result.template.id}/builder`);
    } catch (reason) {
      setError(apiErrorMessage(reason));
      setCreating(false);
    }
  }

  async function cloneTemplate(template: TemplateRecord) {
    setError("");
    try {
      const result = await api<{ template: TemplateRecord }>(`/admin/templates/${template.id}/copy`, { method: "POST", body: "{}" });
      toast("Template cloned as a new editable draft.", "success");
      window.location.assign(`/builder/templates/${result.template.id}/builder`);
    } catch (reason) {
      setError(apiErrorMessage(reason));
    }
  }

  async function handleRenameSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!pendingRename || !renameValue.trim()) return;
    setRenaming(true);
    setError("");
    try {
      await api(`/admin/templates/${pendingRename.id}`, {
        method: "PATCH",
        body: JSON.stringify({ base_revision: pendingRename.revision, name: renameValue.trim() }),
      });
      toast("Template renamed successfully.", "success");
      setPendingRename(null);
      await load();
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setRenaming(false);
    }
  }

  async function handleDeleteTemplate() {
    if (!pendingDelete) return;
    setDeleting(true);
    setError("");
    try {
      await api(`/admin/templates/${pendingDelete.id}`, { method: "DELETE" });
      toast("Template deleted successfully.", "success");
      setPendingDelete(null);
      await load();
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setDeleting(false);
    }
  }

  async function retireTemplate() {
    if (!pendingRetire) return;
    setError("");
    try {
      await api(`/admin/templates/${pendingRetire.id}`, {
        method: "PATCH",
        body: JSON.stringify({ base_revision: pendingRetire.revision, status: "retired" }),
      });
      setPendingRetire(null);
      toast("Template retired. Published revisions remain available to pinned quotations.", "success");
      await load();
    } catch (reason) {
      setError(apiErrorMessage(reason));
    }
  }

  function handleSelectPreset(preset: BenefitCardStyle) {
    setSelectedPresetId(preset.id);
    setCustomStyle({ ...preset });
  }

  function saveAsNewBenefitPreset() {
    const name = window.prompt("Enter a name for this custom benefit card preset:", `${customStyle.name} (Copy)`);
    if (!name?.trim()) return;
    const newId = `custom-${Date.now()}`;
    const newPreset: BenefitCardStyle = {
      ...customStyle,
      id: newId,
      name: name.trim(),
      is_default: false,
      is_custom: true,
    };
    const updated = [...customPresets, newPreset];
    setCustomPresets(updated);
    try {
      localStorage.setItem("risklocker_benefit_card_presets", JSON.stringify(updated));
    } catch {}
    setSelectedPresetId(newId);
    toast(`Preset "${newPreset.name}" saved.`, "success");
  }

  function setAsDefaultBenefitPreset() {
    toast(`"${customStyle.name}" set as default benefit style for all quotations.`, "success");
  }

  function deleteCustomPreset(preset: BenefitCardStyle) {
    const updated = customPresets.filter((p) => p.id !== preset.id);
    setCustomPresets(updated);
    try {
      localStorage.setItem("risklocker_benefit_card_presets", JSON.stringify(updated));
    } catch {}
    if (selectedPresetId === preset.id) {
      handleSelectPreset(systemPresets[0]);
    }
    setPendingDeletePreset(null);
    toast(`Preset "${preset.name}" removed.`, "success");
  }

  // ── Render Shape Style Helper ──
  function getCardRadius(shape: BenefitCardStyle["shape"]) {
    switch (shape) {
      case "racetrack": return "999px";
      case "oval": return "24px / 14px";
      case "soft": return "12px";
      case "square": return "0px";
      case "rounded":
      default:
        return "8px";
    }
  }

  function getCardShadow(elevation: BenefitCardStyle["elevation"]) {
    switch (elevation) {
      case "shadow": return "0 4px 12px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0,0,0,0.04)";
      case "lift": return "0 8px 20px rgba(0, 0, 0, 0.12)";
      case "flat":
      default:
        return "none";
    }
  }

  // Fallback 5-Attribute standard mock data with full coverage, descriptions & pricing
  const SAMPLE_5ATTR_BENEFITS = [
    {
      id: "b1",
      label: "Own Damage",
      category: "default" as const,
      coverage: "RM 50,000.00",
      description: "Accidental collision, overturning, fire, explosion & theft protection.",
      cost: "Included (FOC)",
      costStatus: "foc" as const,
    },
    {
      id: "b2",
      label: "Third Party Bodily Injury",
      category: "default" as const,
      coverage: "Statutory Unlimited",
      description: "Unlimited coverage for third-party injury, hospitalization & accidental death.",
      cost: "Included (FOC)",
      costStatus: "foc" as const,
    },
    {
      id: "b3",
      label: "Third Party Property Damage",
      category: "default" as const,
      coverage: "RM 3,000,000.00",
      description: "Third-party vehicle, roadside fixture, and public property damage.",
      cost: "Included (FOC)",
      costStatus: "foc" as const,
    },
    {
      id: "b4",
      label: "Emergency Towing Assistance",
      category: "default" as const,
      coverage: "200 km / RM 500",
      description: "24/7 unlimited breakdown roadside towing to nearest authorized workshop.",
      cost: "Included (FOC)",
      costStatus: "foc" as const,
    },
    {
      id: "b5",
      label: "Windscreen & Glass Protection",
      category: "addon" as const,
      coverage: "RM 1,000.00",
      description: "Repair & replacement of front, rear and all side door glass with 0% excess.",
      cost: "+RM 150.00",
      costStatus: "paid" as const,
    },
    {
      id: "b6",
      label: "Special Perils (Flood & Storm)",
      category: "addon" as const,
      coverage: "RM 50,000.00",
      description: "Full protection against floods, typhoons, landslides, fallen trees & tempests.",
      cost: "+RM 125.00",
      costStatus: "paid" as const,
    },
    {
      id: "b7",
      label: "Driver Passenger Protector (DPP)",
      category: "addon" as const,
      coverage: "RM 20,000.00",
      description: "Personal accident, accidental death, disablement & medical reimbursement.",
      cost: "+RM 70.00",
      costStatus: "paid" as const,
    },
    {
      id: "b8",
      label: "Legal Liability to Passengers",
      category: "addon" as const,
      coverage: "Statutory Unlimited",
      description: "Legal protection against third-party negligence lawsuits by passengers.",
      cost: "+RM 20.00",
      costStatus: "paid" as const,
    },
  ];

  // Active preview list: blend real DB Global Benefits with 5-attribute structure
  const previewItems = useMemo(() => {
    if (globalBenefits.length) {
      const defs = globalBenefits.filter(gb => (gb.category || (gb.sort_order <= 11 ? "default" : "addon")) === "default").slice(0, 4);
      const adds = globalBenefits.filter(gb => (gb.category || (gb.sort_order <= 11 ? "default" : "addon")) !== "default").slice(0, 4);
      return [...defs, ...adds].map((gb, idx) => {
        const fallback = SAMPLE_5ATTR_BENEFITS[idx % SAMPLE_5ATTR_BENEFITS.length];
        const isDefault = (gb.category || (gb.sort_order <= 11 ? "default" : "addon")) === "default";
        return {
          id: gb.id,
          label: gb.label || fallback.label,
          category: isDefault ? ("default" as const) : ("addon" as const),
          coverage: isDefault
            ? (gb.variants?.[0] || fallback.coverage)
            : (gb.variants?.[0] ? `Limit: ${gb.variants[0]}` : fallback.coverage),
          description: gb.description || fallback.description,
          cost: isDefault ? "Included (FOC)" : fallback.cost,
          costStatus: isDefault ? ("foc" as const) : ("paid" as const),
          asset_url: gb.default_asset?.url || null,
        };
      });
    }
    return SAMPLE_5ATTR_BENEFITS.map((item) => ({ ...item, asset_url: null }));
  }, [globalBenefits]);

  function renderBenefitCardPreview(benefit: (typeof previewItems)[0]) {
    const isDark = customStyle.bgColor === "#0f172a" || customStyle.bgColor === "#1b1717";
    const textColor = isDark ? "#ffffff" : customStyle.textColor;
    const subTextColor = isDark ? "#94a3b8" : "#64748b";
    const isDefault = benefit.category === "default";

    // 1. Signature 2-Column or Masonry (Merged 2-Column: Title Top, Image Left, Stacked Details Right)
    if (customStyle.layout === "merged-2col" || customStyle.layout === "masonry") {
      return (
        <div
          key={benefit.id}
          style={{
            borderRadius: getCardRadius(customStyle.shape),
            boxShadow: getCardShadow(customStyle.elevation),
            backgroundColor: customStyle.bgColor,
            borderColor: customStyle.borderColor,
            borderWidth: `${customStyle.borderWidth}px`,
            borderStyle: customStyle.borderStyle,
            height: customStyle.uniformHeight ? `${customStyle.uniformHeight}px` : "auto",
            ...(customStyle.layout === "masonry" ? { breakInside: "avoid" as const, marginBottom: "12px" } : {}),
          }}
          className={`flex flex-col justify-between p-3.5 transition-all ${
            benefit.category === "addon"
              ? isDark ? "border-amber-500/40 bg-amber-950/10" : "border-amber-300/80 bg-amber-50/20"
              : ""
          }`}
        >
          {/* Row 1: Full-Width Title & Category Badge */}
          <div className="flex items-center justify-between gap-2 mb-2 pb-1.5 border-b border-black/5 dark:border-white/10">
            <h5
              style={{
                fontSize: `${customStyle.titleSize}px`,
                fontWeight: customStyle.titleWeight === "bold" ? 700 : customStyle.titleWeight === "semibold" ? 600 : 500,
                color: textColor,
              }}
              className={customStyle.textWrap === "truncate" ? "truncate" : "leading-tight"}
              title={benefit.label}
            >
              {benefit.label}
            </h5>
            <span
              className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
                isDefault
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : "bg-amber-50 text-amber-800 border border-amber-200"
              }`}
            >
              {isDefault ? "Default" : "Add-on"}
            </span>
          </div>

          {/* Row 2: Image Left + Details Stack Right */}
          <div className="flex items-start gap-3 min-h-0 flex-1">
            {/* Benefit Image */}
            <div
              style={{
                width: `${customStyle.iconSize}px`,
                height: `${customStyle.iconSize}px`,
                borderRadius: customStyle.iconPadShape === "circle" ? "999px" : customStyle.iconPadShape === "box" ? "6px" : "0px",
                backgroundColor:
                  customStyle.iconPadShape === "dark"
                    ? "#020617"
                    : customStyle.iconPadShape === "box" || customStyle.iconPadShape === "circle"
                    ? isDark ? "#1e293b" : "#f1f5f9"
                    : "transparent",
              }}
              className="grid place-items-center shrink-0 overflow-hidden border border-black/5"
            >
              {benefit.asset_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={fileUrl(benefit.asset_url)}
                  alt={benefit.label}
                  style={{
                    width: `${customStyle.iconSize}px`,
                    height: `${customStyle.iconSize}px`,
                    objectFit: customStyle.imageFit,
                  }}
                  className="transition-all"
                />
              ) : isDefault ? (
                <ShieldCheck
                  size={customStyle.iconSize * 0.58}
                  weight="bold"
                  className={customStyle.iconPadShape === "dark" ? "text-white" : isDark ? "text-white" : "text-[var(--rl-black)]"}
                />
              ) : (
                <Sparkle
                  size={customStyle.iconSize * 0.58}
                  weight="bold"
                  className={customStyle.iconPadShape === "dark" ? "text-white" : "text-[var(--rl-red)]"}
                />
              )}
            </div>

            {/* Right Column: Coverage, Description, Cost */}
            <div className="flex-1 min-w-0 flex flex-col justify-start">
              {customStyle.showCoverage && (
                <span
                  className="font-bold tracking-tight text-[var(--rl-red)] leading-tight"
                  style={{ fontSize: `${Math.max(11, customStyle.titleSize)}px` }}
                >
                  {benefit.coverage}
                </span>
              )}

              {customStyle.showDescription && benefit.description && (
                <p
                  style={{ color: subTextColor }}
                  className="text-[10.5px] leading-snug mt-0.5"
                >
                  {benefit.description}
                </p>
              )}

              {customStyle.showCost && benefit.costStatus !== "foc" && (
                <div className="mt-1.5 flex items-center gap-1.5">
                  <span className="inline-block rounded bg-red-50 border border-red-200 px-2 py-0.5 text-[9.5px] font-bold text-red-600">
                    {benefit.cost}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      );
    }

    // 2. Vertical Tile Layout
    if (customStyle.layout === "tile") {
      return (
        <div
          key={benefit.id}
          style={{
            borderRadius: getCardRadius(customStyle.shape),
            boxShadow: getCardShadow(customStyle.elevation),
            backgroundColor: customStyle.bgColor,
            borderColor: customStyle.borderColor,
            borderWidth: `${customStyle.borderWidth}px`,
            borderStyle: customStyle.borderStyle,
            height: customStyle.uniformHeight ? `${customStyle.uniformHeight}px` : "auto",
          }}
          className="flex flex-col items-center text-center justify-between p-4 transition-all"
        >
          <div
            style={{
              width: `${customStyle.iconSize}px`,
              height: `${customStyle.iconSize}px`,
              borderRadius: customStyle.iconPadShape === "circle" ? "999px" : "6px",
              backgroundColor: isDark ? "#1e293b" : "#f1f5f9",
            }}
            className="grid place-items-center shrink-0 overflow-hidden mb-2"
          >
            {benefit.asset_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={fileUrl(benefit.asset_url)} alt="" style={{ width: "100%", height: "100%", objectFit: customStyle.imageFit }} />
            ) : isDefault ? (
              <ShieldCheck size={customStyle.iconSize * 0.55} weight="bold" className="text-[var(--rl-black)]" />
            ) : (
              <Sparkle size={customStyle.iconSize * 0.55} weight="bold" className="text-[var(--rl-red)]" />
            )}
          </div>

          <h5
            style={{ fontSize: `${customStyle.titleSize}px`, color: textColor }}
            className="font-bold truncate w-full"
          >
            {benefit.label}
          </h5>

          {customStyle.showCoverage && (
            <span className="text-[11px] font-bold text-[var(--rl-red)] mt-0.5 block truncate w-full">
              {benefit.coverage}
            </span>
          )}

          {customStyle.showDescription && benefit.description && (
            <p style={{ color: subTextColor }} className="text-[10px] line-clamp-2 mt-1 w-full leading-snug">
              {benefit.description}
            </p>
          )}

          {customStyle.showCost && benefit.costStatus !== "foc" && (
            <div className="mt-2">
              <span className="text-[9px] font-bold rounded px-2 py-0.5 bg-red-50 text-red-600 border border-red-200">
                {benefit.cost}
              </span>
            </div>
          )}
        </div>
      );
    }

    // 3. Horizontal Split Layout
    if (customStyle.layout === "horizontal") {
      return (
        <div
          key={benefit.id}
          style={{
            borderRadius: getCardRadius(customStyle.shape),
            boxShadow: getCardShadow(customStyle.elevation),
            backgroundColor: customStyle.bgColor,
            borderColor: customStyle.borderColor,
            borderWidth: `${customStyle.borderWidth}px`,
            borderStyle: customStyle.borderStyle,
            height: customStyle.uniformHeight ? `${customStyle.uniformHeight}px` : "auto",
          }}
          className="flex items-center justify-between p-3 transition-all gap-3"
        >
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <div
              style={{ width: `${customStyle.iconSize}px`, height: `${customStyle.iconSize}px` }}
              className="grid place-items-center rounded bg-neutral-100 shrink-0 overflow-hidden"
            >
              {benefit.asset_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={fileUrl(benefit.asset_url)} alt="" style={{ width: "100%", height: "100%", objectFit: customStyle.imageFit }} />
              ) : isDefault ? (
                <ShieldCheck size={customStyle.iconSize * 0.55} weight="bold" className="text-[var(--rl-black)]" />
              ) : (
                <Sparkle size={customStyle.iconSize * 0.55} weight="bold" className="text-[var(--rl-red)]" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <h5 style={{ fontSize: `${customStyle.titleSize}px`, color: textColor }} className="font-bold truncate">
                {benefit.label}
              </h5>
              {customStyle.showCoverage && (
                <span className="text-[11px] font-bold text-[var(--rl-red)] block truncate">
                  {benefit.coverage}
                </span>
              )}
              {customStyle.showDescription && (
                <p style={{ color: subTextColor }} className="text-[10px] truncate leading-snug">
                  {benefit.description}
                </p>
              )}
            </div>
          </div>
          {customStyle.showCost && benefit.costStatus !== "foc" && (
            <span className="shrink-0 text-[10px] font-bold rounded px-2 py-0.5 bg-red-50 text-red-600 border border-red-200">
              {benefit.cost}
            </span>
          )}
        </div>
      );
    }

    // 4. Compact Minimalist Row
    return (
      <div
        key={benefit.id}
        style={{
          borderRadius: getCardRadius(customStyle.shape),
          boxShadow: getCardShadow(customStyle.elevation),
          backgroundColor: customStyle.bgColor,
          borderColor: customStyle.borderColor,
          borderWidth: `${customStyle.borderWidth}px`,
          borderStyle: customStyle.borderStyle,
          height: customStyle.uniformHeight ? `${customStyle.uniformHeight}px` : "auto",
        }}
        className="flex items-center justify-between px-3.5 py-2 transition-all gap-2"
      >
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <div
            style={{ width: `${Math.min(customStyle.iconSize, 32)}px`, height: `${Math.min(customStyle.iconSize, 32)}px` }}
            className="grid place-items-center rounded bg-neutral-100 shrink-0 overflow-hidden"
          >
            {benefit.asset_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={fileUrl(benefit.asset_url)} alt="" style={{ width: "100%", height: "100%", objectFit: customStyle.imageFit }} />
            ) : (
              <ShieldCheck size={16} weight="bold" className="text-[var(--rl-black)]" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <h5 style={{ fontSize: `${customStyle.titleSize}px`, color: textColor }} className="font-bold truncate">
              {benefit.label}
            </h5>
            {customStyle.showCoverage && (
              <span className="text-[10.5px] font-bold text-[var(--rl-red)] truncate block">
                {benefit.coverage}
              </span>
            )}
          </div>
        </div>
        {customStyle.showCost && benefit.costStatus !== "foc" && (
          <span className="shrink-0 text-[9.5px] font-bold rounded px-1.5 py-0.5 bg-red-50 text-red-600 border border-red-200">
            {benefit.cost}
          </span>
        )}
      </div>
    );
  }

  return (

    <AppShell>
      <section className="grid gap-6">
        {/* ── Top Header ────────────────────────────────────────────── */}
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--rl-red)]">Builder</p>
            <h1 className="m-0 font-[var(--font-manrope)] text-[30px] font-bold text-[var(--rl-text-strong)]">Templates</h1>
            <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
              Design and configure master quotation page templates and benefit card component styles.
            </p>
          </div>
          {activeMasterTab === "quotation" ? (
            <Button icon={<FilePlus size={16} weight="bold" />} onClick={() => { setNewName(""); setShowCreate(true); }}>New template</Button>
          ) : (
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" icon={<CopySimple size={14} />} onClick={saveAsNewBenefitPreset}>
                Save as New Preset
              </Button>
              <Button size="sm" icon={<Star size={14} weight="fill" />} onClick={setAsDefaultBenefitPreset}>
                Set as Default Template
              </Button>
            </div>
          )}
        </header>

        <BuilderNav />

        {/* ── Top Master Switcher: Quotation Templates vs Benefit Templates ── */}
        <div className="flex items-center gap-3 border-b border-[var(--rl-border)] pb-2">
          <button
            type="button"
            onClick={() => setActiveMasterTab("quotation")}
            className={`flex items-center gap-2 rounded-t-[var(--rl-radius-sm)] px-4 py-2.5 text-xs font-bold transition-all ${
              activeMasterTab === "quotation"
                ? "bg-[var(--rl-black)] text-white shadow-sm"
                : "border border-transparent bg-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
          >
            <FilePdf size={16} weight="bold" />
            <span>1. Quotation Templates ({templates.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveMasterTab("benefits")}
            className={`flex items-center gap-2 rounded-t-[var(--rl-radius-sm)] px-4 py-2.5 text-xs font-bold transition-all ${
              activeMasterTab === "benefits"
                ? "bg-[var(--rl-black)] text-white shadow-sm"
                : "border border-transparent bg-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
          >
            <ShieldCheck size={16} weight="bold" />
            <span>2. Benefit Card Templates ({systemPresets.length + customPresets.length} Styles)</span>
          </button>
        </div>

        {error ? <div role="alert" className="border-l-2 border-[var(--rl-red)] bg-[var(--rl-red-light)] px-4 py-3 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div> : null}

        {/* ══════════════════════════════════════════════════════════════ */}
        {/* TAB 1: QUOTATION MASTER TEMPLATES                              */}
        {/* ══════════════════════════════════════════════════════════════ */}
        {activeMasterTab === "quotation" && (
          <div className="space-y-6">
            <div className="grid gap-3 border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-card md:grid-cols-[minmax(260px,1fr)_190px_190px_auto] md:items-center">
              <label className="relative block">
                <MagnifyingGlass size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
                <Input aria-label="Search templates" className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search templates" />
              </label>
              <Select aria-label="Filter by publication status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="all">All statuses</option><option value="published">Published</option><option value="draft">Draft</option><option value="compatibility">Legacy compatibility</option><option value="retired">Retired</option>
              </Select>
              <Select aria-label="Filter by page profile" value={profileFilter} onChange={(event) => setProfileFilter(event.target.value)}><option value="all">All page profiles</option>{profiles.map((profile) => <option key={profile} value={profile}>{profile}</option>)}</Select>
              <span className="text-right text-[12px] font-semibold text-[var(--rl-text-muted)]">{visibleTemplates.length} template{visibleTemplates.length === 1 ? "" : "s"}</span>
            </div>

            {loading ? <p role="status" className="border border-[var(--rl-border)] bg-white p-8 text-center text-[14px] text-[var(--rl-text-muted)]">Loading template previews…</p> : null}
            {!loading && visibleTemplates.length ? (
              <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
                {visibleTemplates.map((template) => {
                  const state = templateState(template);
                  const page = pageProfile(template);
                  const published = template.latest_published_revision;
                  return (
                    <article key={template.id} className="group overflow-hidden border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-card">
                      <button type="button" className="block w-full text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--rl-red)]" onClick={() => setPreview(template)} aria-label={`Preview ${template.name}`}>
                        <TemplateThumbnail template={template} />
                      </button>
                      <div className="grid gap-4 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <h2 className="m-0 truncate text-[17px] font-bold text-[var(--rl-text-strong)]">{template.name}</h2>
                              {template.is_default ? <Star aria-label="Default template" size={15} weight="fill" className="shrink-0 text-[var(--rl-red)]" /> : null}
                            </div>
                            <p className="mt-1 text-[12px] text-[var(--rl-text-muted)]">{page.name} · {Math.round(page.width)} × {Math.round(page.height)} {page.unit}</p>
                          </div>
                          <span className={`border-l-2 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.08em] ${state === "published" ? "border-emerald-600 text-emerald-700" : state === "draft" ? "border-amber-500 text-amber-700" : "border-[var(--rl-border-strong)] text-[var(--rl-text-muted)]"}`}>{state}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3 border-t border-[var(--rl-border)] pt-3">
                          <p className="m-0 text-[11px] text-[var(--rl-text-muted)]">{published ? `Published revision ${published.revision_number}` : `Working revision ${template.revision}`}</p>
                          <div className="flex flex-wrap gap-1 items-center">
                            <Button variant="ghost" size="sm" icon={<Eye size={14} />} onClick={() => setPreview(template)}>Preview</Button>
                            <Button variant="secondary" size="sm" icon={<PencilSimple size={14} />} onClick={() => { setPendingRename(template); setRenameValue(template.name); }}>Rename</Button>
                            <Button variant="secondary" size="sm" icon={<CopySimple size={14} />} onClick={() => cloneTemplate(template)}>Clone</Button>
                            {!template.locked && template.status !== "retired" ? <Link href={`/builder/templates/${template.id}/builder`}><Button size="sm" icon={<PencilSimple size={14} />}>Open</Button></Link> : null}
                            {!template.locked && template.status !== "retired" ? <Button variant="ghost" size="sm" aria-label={`Delete ${template.name}`} icon={<Trash size={14} />} className="text-[var(--rl-red)]" onClick={() => setPendingDelete(template)}><span className="sr-only">Delete</span></Button> : null}
                          </div>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : null}
            {!loading && !visibleTemplates.length ? <p className="border border-dashed border-[var(--rl-border)] p-12 text-center text-[14px] text-[var(--rl-text-muted)]">No templates match these filters.</p> : null}
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════ */}
        {/* TAB 2: BENEFIT CARD COMPONENT TEMPLATES DESIGNER               */}
        {/* ══════════════════════════════════════════════════════════════ */}
        {activeMasterTab === "benefits" && (
          <div className="space-y-6">
            {/* Presets Organized into 2 Distinct Rows (System vs Custom) */}
            <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm space-y-4">
              {/* Row 1: System Presets */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                    1. System Presets (Permanent)
                  </h3>
                  <span className="text-[11px] text-[var(--rl-text-muted)]">Out-of-the-box templates</span>
                </div>

                <div className="flex flex-wrap gap-2">
                  {systemPresets.map((preset) => {
                    const isCurrent = preset.id === selectedPresetId;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => handleSelectPreset(preset)}
                        className={`flex items-center gap-2 rounded-[var(--rl-radius-sm)] px-3.5 py-2 text-xs font-semibold transition-all ${
                          isCurrent
                            ? "bg-[var(--rl-black)] text-white shadow-sm ring-1 ring-[var(--rl-black)]"
                            : "border border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                        }`}
                      >
                        <PaintBrush size={14} className={isCurrent ? "text-white" : "text-[var(--rl-text-muted)]"} />
                        <span>{preset.name}</span>
                        {preset.is_default && (
                          <span className={`rounded px-1.5 py-0.2 text-[9px] font-bold uppercase ${isCurrent ? "bg-white/20 text-white" : "bg-neutral-200 text-neutral-800"}`}>
                            Default
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Row 2: Custom Saved Presets */}
              <div className="border-t border-[var(--rl-border)] pt-3">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                    2. Custom Saved Presets ({customPresets.length})
                  </h3>
                  <span className="text-[11px] text-[var(--rl-text-muted)]">User-created styles</span>
                </div>

                {customPresets.length ? (
                  <div className="flex flex-wrap gap-2">
                    {customPresets.map((preset) => {
                      const isCurrent = preset.id === selectedPresetId;
                      return (
                        <div
                          key={preset.id}
                          className={`flex items-center rounded-[var(--rl-radius-sm)] border text-xs font-semibold transition-all ${
                            isCurrent
                              ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white shadow-sm ring-1 ring-[var(--rl-black)]"
                              : "border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                          }`}
                        >
                          <button
                            type="button"
                            onClick={() => handleSelectPreset(preset)}
                            className="flex items-center gap-2 px-3 py-2 text-left"
                          >
                            <Sparkle size={14} className={isCurrent ? "text-white" : "text-[var(--rl-red)]"} />
                            <span>{preset.name}</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => setPendingDeletePreset(preset)}
                            title={`Delete preset ${preset.name}`}
                            className={`px-2 py-2 text-xs transition-colors hover:text-red-500 ${isCurrent ? "text-white/70 hover:text-white" : "text-neutral-400"}`}
                          >
                            <Trash size={13} weight="bold" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex items-center justify-between rounded-[var(--rl-radius-sm)] border border-dashed border-[var(--rl-border)] bg-[#fafafa] px-4 py-3 text-xs text-[var(--rl-text-muted)]">
                    <span>No custom presets saved yet. Customize any style and click &quot;Save as New Preset&quot; above.</span>
                    <Button variant="secondary" size="sm" icon={<Plus size={13} />} onClick={saveAsNewBenefitPreset}>
                      Create Preset
                    </Button>
                  </div>
                )}
              </div>
            </div>

            {/* Customizer + Live Preview 2-Column Split */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
              {/* Left Column (5 cols): Click-First Style Controls */}
              <div className="lg:col-span-5 space-y-4">

                {/* Section 0: Layout Architecture & Presentation */}
                <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                      0. Layout Architecture & Flow
                    </h4>
                    <span className="rounded bg-red-50 border border-red-200 px-1.5 py-0.2 text-[9px] font-bold uppercase text-[var(--rl-red)]">
                      5-Attribute
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-1.5 text-xs">
                    {[
                      { key: "merged-2col", label: "★ Signature 2-Col" },
                      { key: "masonry", label: "Masonry Flow" },
                      { key: "horizontal", label: "Horizontal Split" },
                      { key: "tile", label: "Vertical Grid Tile" },
                      { key: "compact", label: "Compact Row" },
                    ].map((item) => (
                      <button
                        key={item.key}
                        type="button"
                        onClick={() => setCustomStyle({ ...customStyle, layout: item.key as BenefitCardStyle["layout"] })}
                        className={`rounded-[var(--rl-radius-sm)] border p-2 text-center text-xs font-medium transition-all ${
                          customStyle.layout === item.key
                            ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white shadow-xs font-bold"
                            : "border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Section 1: Container & Shape */}
                <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-sm space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                    1. Container Shape & Elevation
                  </h4>

                  <div>
                    <label className="block text-xs font-semibold text-[var(--rl-text-strong)]">Shape Style</label>
                    <div className="mt-1.5 grid grid-cols-3 gap-1.5 text-xs">
                      {[
                        { key: "rounded", label: "Rounded 8px" },
                        { key: "racetrack", label: "Racetrack (Pill)" },
                        { key: "soft", label: "Soft Card (12px)" },
                        { key: "oval", label: "Oval" },
                        { key: "square", label: "Square 0px" },
                      ].map((item) => (
                        <button
                          key={item.key}
                          type="button"
                          onClick={() => setCustomStyle({ ...customStyle, shape: item.key as BenefitCardStyle["shape"] })}
                          className={`rounded-[var(--rl-radius-sm)] border p-2 text-center text-xs font-medium transition-all ${
                            customStyle.shape === item.key
                              ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white shadow-xs font-bold"
                              : "border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[var(--rl-text-strong)]">Elevation & Shadow</label>
                    <div className="mt-1.5 grid grid-cols-3 gap-1.5 text-xs">
                      {[
                        { key: "flat", label: "Flat (No Shadow)" },
                        { key: "shadow", label: "Subtle 3D Lift" },
                        { key: "lift", label: "Elevated 3D Card" },
                      ].map((item) => (
                        <button
                          key={item.key}
                          type="button"
                          onClick={() => setCustomStyle({ ...customStyle, elevation: item.key as BenefitCardStyle["elevation"] })}
                          className={`rounded-[var(--rl-radius-sm)] border p-2 text-center text-xs font-medium transition-all ${
                            customStyle.elevation === item.key
                              ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white font-bold"
                              : "border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-[var(--rl-text-strong)]">
                        Uniform Height Across All Benefits
                      </label>
                      <span className="text-xs font-bold text-[var(--rl-text-muted)]">
                        {customStyle.uniformHeight ? `${customStyle.uniformHeight}px` : "Auto"}
                      </span>
                    </div>
                    <div className="mt-1.5 grid grid-cols-5 gap-1 text-xs">
                      {[
                        { val: 0, label: "Auto" },
                        { val: 68, label: "68px" },
                        { val: 84, label: "84px" },
                        { val: 96, label: "96px" },
                        { val: 112, label: "112px" },
                      ].map((item) => (
                        <button
                          key={item.val}
                          type="button"
                          onClick={() => setCustomStyle({ ...customStyle, uniformHeight: item.val })}
                          className={`rounded-[var(--rl-radius-sm)] border py-1.5 text-center text-xs font-medium transition-all ${
                            customStyle.uniformHeight === item.val
                              ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white font-bold"
                              : "border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Section 2: Asset / Image Fitting & Sizing */}
                <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                      2. Image Size & Asset Fit
                    </h4>
                    <Tooltip content="Choose how uploaded benefit artwork fits inside the icon container (contain vs cover crop)">
                      <Info size={13} className="text-[var(--rl-text-muted)]" />
                    </Tooltip>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[var(--rl-text-strong)]">Icon Artwork Size</label>
                    <div className="mt-1.5 grid grid-cols-5 gap-1 text-xs">
                      {[28, 36, 44, 52, 60].map((size) => (
                        <button
                          key={size}
                          type="button"
                          onClick={() => setCustomStyle({ ...customStyle, iconSize: size })}
                          className={`rounded-[var(--rl-radius-sm)] border py-1.5 text-center text-xs font-medium transition-all ${
                            customStyle.iconSize === size
                              ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white font-bold"
                              : "border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                          }`}
                        >
                          {size}px
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[var(--rl-text-strong)]">
                      Image Behavior / Crop Ratio
                    </label>
                    <div className="mt-1.5 grid grid-cols-3 gap-1.5 text-xs">
                      {[
                        { key: "contain", label: "Contain (Fit all)" },
                        { key: "cover", label: "Cover (Crop to fill)" },
                        { key: "scale-down", label: "Original Scale" },
                      ].map((item) => (
                        <button
                          key={item.key}
                          type="button"
                          onClick={() => setCustomStyle({ ...customStyle, imageFit: item.key as BenefitCardStyle["imageFit"] })}
                          className={`rounded-[var(--rl-radius-sm)] border p-2 text-center text-xs font-medium transition-all ${
                            customStyle.imageFit === item.key
                              ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white font-bold"
                              : "border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[var(--rl-text-strong)]">Icon Pad Background</label>
                    <div className="mt-1.5 grid grid-cols-4 gap-1 text-xs">
                      {[
                        { key: "box", label: "Gray Box" },
                        { key: "circle", label: "Circle Pad" },
                        { key: "dark", label: "Dark Pad" },
                        { key: "none", label: "No Pad" },
                      ].map((item) => (
                        <button
                          key={item.key}
                          type="button"
                          onClick={() => setCustomStyle({ ...customStyle, iconPadShape: item.key as BenefitCardStyle["iconPadShape"] })}
                          className={`rounded-[var(--rl-radius-sm)] border py-1.5 text-center text-xs font-medium transition-all ${
                            customStyle.iconPadShape === item.key
                              ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white font-bold"
                              : "border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Section 3: Typography & 5-Attribute Visibility */}
                <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-sm space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                    3. Typography & 5-Attribute Visibility
                  </h4>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <label className="block font-semibold text-[var(--rl-text-strong)]">Title Size</label>
                      <div className="mt-1.5 grid grid-cols-4 gap-1">
                        {[11, 12, 13, 14].map((size) => (
                          <button
                            key={size}
                            type="button"
                            onClick={() => setCustomStyle({ ...customStyle, titleSize: size })}
                            className={`rounded border py-1 text-center font-medium ${
                              customStyle.titleSize === size ? "bg-[var(--rl-black)] text-white font-bold" : "bg-[var(--rl-bg)] border-[var(--rl-border)]"
                            }`}
                          >
                            {size}px
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="block font-semibold text-[var(--rl-text-strong)]">Text Wrap</label>
                      <div className="mt-1.5 grid grid-cols-2 gap-1">
                        {[
                          { key: "truncate", label: "1-Line" },
                          { key: "wrap", label: "2-Lines" },
                        ].map((item) => (
                          <button
                            key={item.key}
                            type="button"
                            onClick={() => setCustomStyle({ ...customStyle, textWrap: item.key as "truncate" | "wrap" })}
                            className={`rounded border py-1 text-center font-medium ${
                              customStyle.textWrap === item.key ? "bg-[var(--rl-black)] text-white font-bold" : "bg-[var(--rl-bg)] border-[var(--rl-border)]"
                            }`}
                          >
                            {item.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* 5-Attribute Feature Visibility Toggles */}
                  <div className="pt-2 border-t border-[var(--rl-border)] space-y-1.5">
                    <label className="block text-xs font-semibold text-[var(--rl-text-strong)]">5-Attribute Visibility</label>
                    <div className="grid grid-cols-3 gap-1.5 text-xs">
                      <button
                        type="button"
                        onClick={() => setCustomStyle({ ...customStyle, showCoverage: !customStyle.showCoverage })}
                        className={`rounded border py-1.5 text-center font-medium transition-all ${
                          customStyle.showCoverage ? "bg-red-50 border-red-300 text-red-700 font-bold" : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-neutral-500"
                        }`}
                      >
                        Coverage: {customStyle.showCoverage ? "ON" : "OFF"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setCustomStyle({ ...customStyle, showDescription: !customStyle.showDescription })}
                        className={`rounded border py-1.5 text-center font-medium transition-all ${
                          customStyle.showDescription ? "bg-blue-50 border-blue-300 text-blue-700 font-bold" : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-neutral-500"
                        }`}
                      >
                        Desc: {customStyle.showDescription ? "ON" : "OFF"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setCustomStyle({ ...customStyle, showCost: !customStyle.showCost })}
                        className={`rounded border py-1.5 text-center font-medium transition-all ${
                          customStyle.showCost ? "bg-emerald-50 border-emerald-300 text-emerald-700 font-bold" : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-neutral-500"
                        }`}
                      >
                        Cost: {customStyle.showCost ? "ON" : "OFF"}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[var(--rl-text-strong)]">Cost / Tag Badge Style</label>
                    <div className="mt-1.5 grid grid-cols-4 gap-1 text-xs">
                      {[
                        { key: "red", label: "Red Accent" },
                        { key: "green", label: "Green FOC" },
                        { key: "pill", label: "Dark Pill" },
                        { key: "subtle", label: "Subtle Gray" },
                      ].map((item) => (
                        <button
                          key={item.key}
                          type="button"
                          onClick={() => setCustomStyle({ ...customStyle, valueBadgeStyle: item.key as BenefitCardStyle["valueBadgeStyle"] })}
                          className={`rounded-[var(--rl-radius-sm)] border py-1.5 text-center text-xs font-medium transition-all ${
                            customStyle.valueBadgeStyle === item.key
                              ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white font-bold"
                              : "border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Section 4: Color Customization */}
                <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-sm space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                    4. Color Palette
                  </h4>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <label className="block font-semibold text-[var(--rl-text-strong)]">Card Background</label>
                      <div className="mt-1.5 flex gap-1.5">
                        {["#ffffff", "#fafafc", "#f8fafc", "#0f172a"].map((col) => (
                          <button
                            key={col}
                            type="button"
                            onClick={() => setCustomStyle({ ...customStyle, bgColor: col })}
                            className={`h-7 w-7 rounded-full border shadow-xs transition-all ${
                              customStyle.bgColor === col ? "ring-2 ring-[var(--rl-red)] ring-offset-2 scale-110" : "border-neutral-300"
                            }`}
                            style={{ backgroundColor: col }}
                            title={col}
                          />
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="block font-semibold text-[var(--rl-text-strong)]">Border Color</label>
                      <div className="mt-1.5 flex gap-1.5">
                        {["#e2e8f0", "#d1d5db", "#334155", "#dc2626"].map((col) => (
                          <button
                            key={col}
                            type="button"
                            onClick={() => setCustomStyle({ ...customStyle, borderColor: col })}
                            className={`h-7 w-7 rounded-full border shadow-xs transition-all ${
                              customStyle.borderColor === col ? "ring-2 ring-[var(--rl-red)] ring-offset-2 scale-110" : "border-neutral-300"
                            }`}
                            style={{ backgroundColor: col }}
                            title={col}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column (7 cols): Live Dynamic Benefit Cards Grid Preview */}
              <div className="lg:col-span-7 space-y-4">
                <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
                  <div className="mb-4 flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
                    <div>
                      <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">
                        Live Benefit Cards Template Preview
                      </h3>
                      <p className="text-xs text-[var(--rl-text-muted)]">
                        Rendering 5-attribute presentation using: <span className="font-semibold text-[var(--rl-text-strong)]">{customStyle.name}</span>
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-red-50 border border-red-200 px-2 py-0.5 text-xs font-bold text-[var(--rl-red)] uppercase">
                        {customStyle.layout.toUpperCase()}
                      </span>
                      <span className="rounded bg-[var(--rl-bg)] border border-[var(--rl-border)] px-2 py-0.5 text-xs font-bold text-[var(--rl-text-strong)]">
                        {customStyle.shape.toUpperCase()} · {customStyle.uniformHeight ? `${customStyle.uniformHeight}px` : "AUTO"}
                      </span>
                    </div>
                  </div>

                  {/* Dynamic Benefit Cards Container based on Layout Mode */}
                  {customStyle.layout === "masonry" ? (
                    <div style={{ columnCount: 2, columnGap: "12px" }}>
                      {previewItems.map((benefit) => renderBenefitCardPreview(benefit))}
                    </div>
                  ) : (
                    <div className={`grid gap-3 ${customStyle.layout === "tile" ? "grid-cols-1 sm:grid-cols-2 md:grid-cols-3" : "grid-cols-1 sm:grid-cols-2"}`}>
                      {previewItems.map((benefit) => renderBenefitCardPreview(benefit))}
                    </div>
                  )}

                  {/* Admin Guidance Box */}
                  <div className="mt-5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3 text-xs text-[var(--rl-text-muted)] space-y-1">
                    <div className="flex items-center gap-1.5 font-bold text-[var(--rl-text-strong)]">
                      <ImageSquare size={15} />
                      <span>5-Attribute Presentation Spec:</span>
                    </div>
                    <p className="text-[11px] leading-relaxed">
                      Every card displays <span className="font-bold text-[var(--rl-text-strong)]">1) Benefit Image</span>, <span className="font-bold text-[var(--rl-text-strong)]">2) Title</span>, <span className="font-bold text-[var(--rl-red)]">3) Coverage Limit (RM)</span>, <span className="font-bold text-[var(--rl-text-strong)]">4) Short Description</span>, and <span className="font-bold text-emerald-700">5) Cost Structure</span>. All artwork scales via <span className="font-semibold">{customStyle.imageFit}</span> at <span className="font-semibold">{customStyle.iconSize}px</span>.
                    </p>
                  </div>
                </div>

                {/* Quotation Canvas Integration Visualizer */}
                <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                      Quotation A4 Layout Integration
                    </h4>
                    <span className="text-[11px] text-[var(--rl-text-muted)]">
                      Live preview in quotation benefit grid slot
                    </span>
                  </div>

                  <div className="rounded-[var(--rl-radius-sm)] border border-dashed border-[var(--rl-red)] bg-[#fafafc] p-4">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-red)]">
                        Your Benefits (Dynamic Slot · 5-Attribute)
                      </span>
                      <span className="text-[10px] text-[var(--rl-text-muted)]">A4 Canvas Bounding Box</span>
                    </div>

                    <div className="grid grid-cols-2 gap-2.5">
                      {previewItems.slice(0, 4).map((benefit) => (
                        <div
                          key={`canvas-${benefit.id}`}
                          style={{
                            borderRadius: getCardRadius(customStyle.shape),
                            boxShadow: getCardShadow(customStyle.elevation),
                            backgroundColor: customStyle.bgColor,
                            borderColor: customStyle.borderColor,
                            borderWidth: `${customStyle.borderWidth}px`,
                            borderStyle: customStyle.borderStyle,
                          }}
                          className="flex items-start gap-2.5 p-2.5 text-xs shadow-xs"
                        >
                          <div
                            style={{ width: "36px", height: "36px" }}
                            className="grid place-items-center rounded bg-neutral-100 border border-neutral-200 shrink-0 overflow-hidden"
                          >
                            {benefit.asset_url ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img
                                src={fileUrl(benefit.asset_url)}
                                alt={benefit.label}
                                style={{ width: "36px", height: "36px", objectFit: customStyle.imageFit }}
                              />
                            ) : (
                              <ShieldCheck size={18} className="text-[var(--rl-black)]" />
                            )}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-1">
                              <span className="text-xs font-bold text-[var(--rl-text-strong)] truncate">
                                {benefit.label}
                              </span>
                              <span className="text-[9px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-1 shrink-0">
                                {benefit.cost}
                              </span>
                            </div>
                            <span className="text-[11px] font-bold text-[var(--rl-red)] block truncate mt-0.5">
                              {benefit.coverage}
                            </span>
                            <p className="text-[9.5px] text-neutral-500 truncate leading-snug">
                              {benefit.description}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

      </section>

      {/* ── Dialogs for Quotation Templates ──────────────────────────── */}
      <Dialog open={showCreate} onOpenChange={setShowCreate} title="Create an insurer-independent template" description="Start with a clean Standard A4 draft. Page profile and layout can be changed inside the Builder.">
        <form onSubmit={createTemplate} className="grid gap-4"><label className="grid gap-1.5 text-[12px] font-semibold text-[var(--rl-text-strong)]">Template name<Input autoFocus value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="e.g. Standard A4" required /></label><div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setShowCreate(false)}>Cancel</Button><Button type="submit" loading={creating}>Create and open</Button></div></form>
      </Dialog>

      <Dialog open={Boolean(pendingRename)} onOpenChange={(open) => { if (!open) setPendingRename(null); }} title={`Rename “${pendingRename?.name || ""}”`} description="Update the display name of this quotation template.">
        <form onSubmit={handleRenameSubmit} className="grid gap-4">
          <label className="grid gap-1.5 text-[12px] font-semibold text-[var(--rl-text-strong)]">
            New Template Name
            <Input autoFocus value={renameValue} onChange={(e) => setRenameValue(e.target.value)} placeholder="e.g. AmAssurance Custom Quotation" required />
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setPendingRename(null)}>Cancel</Button>
            <Button type="submit" loading={renaming}>Rename Template</Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={Boolean(preview)} onOpenChange={(open) => { if (!open) setPreview(null); }} title={preview?.name || "Template preview"} description={preview ? `${pageProfile(preview).name} · ${templateState(preview)}` : undefined}>{preview ? <TemplateThumbnail template={preview} large /> : null}</Dialog>

      {pendingRetire ? <ConfirmDialog open onOpenChange={(open) => { if (!open) setPendingRetire(null); }} title={`Retire “${pendingRetire.name}”?`} message="Pinned quotations keep their immutable published revision. This working template disappears from new selection." confirmLabel="Retire template" onConfirm={retireTemplate} /> : null}

      {pendingDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingDelete(null); }}
          title={`Delete Template “${pendingDelete.name}”?`}
          message="Are you sure you want to delete this template? Any quotations that have pinned published revisions will continue to work, but this working template will be removed."
          confirmLabel="Delete Template"
          onConfirm={handleDeleteTemplate}
        />
      ) : null}

      {/* Delete Custom Benefit Preset Dialog */}
      {pendingDeletePreset ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingDeletePreset(null); }}
          title={`Delete Preset “${pendingDeletePreset.name}”?`}
          message="Are you sure you want to delete this custom benefit preset? This action cannot be undone."
          confirmLabel="Delete Preset"
          onConfirm={() => deleteCustomPreset(pendingDeletePreset)}
        />
      ) : null}
    </AppShell>
  );
}
