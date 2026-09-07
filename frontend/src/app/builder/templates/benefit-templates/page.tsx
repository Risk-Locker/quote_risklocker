"use client";

import Link from "next/link";
import type { Route } from "next";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowCounterClockwise,
  Article,
  CopySimple,
  CurrencyCircleDollar,
  Eye,
  EyeSlash,
  FilePdf,
  FloppyDisk,
  ImageSquare,
  Info,
  PaintBrush,
  Plus,
  ShieldCheck,
  Sparkle,
  Star,
  TextT,
  Trash,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { BuilderNav } from "@/components/builder-nav";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Tooltip } from "@/components/ui/tooltip";
import { useToast } from "@/components/ui/toast";
import { api, fileUrl } from "@/lib/api";
import {
  BenefitCardStyle,
  BenefitSectionVisibility,
  SectionComponentVisibility,
  SYSTEM_BENEFIT_PRESETS,
  getAllBenefitPresets,
  getBenefitPreset,
  normalizeSectionVisibility,
  resetPresetToDefault,
  savePresetOverride,
} from "@/lib/benefit-presets";

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

type BenefitSectionKey = "default" | "addedAddons" | "optionalAddons";

export default function BenefitCardTemplatesPage() {
  const { toast } = useToast();

  // Presets state
  const [allPresets, setAllPresets] = useState<BenefitCardStyle[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string>("signature-2col");
  const [customStyle, setCustomStyle] = useState<BenefitCardStyle>(() => {
    const initial = SYSTEM_BENEFIT_PRESETS.find((p) => p.id === "signature-2col") || SYSTEM_BENEFIT_PRESETS[0];
    return {
      ...initial,
      sectionVisibility: normalizeSectionVisibility(initial.sectionVisibility, initial),
    };
  });
  const [pendingDeletePreset, setPendingDeletePreset] = useState<BenefitCardStyle | null>(null);

  // Active section tab in the 3-section 5-component control panel
  const [activeSectionTab, setActiveSectionTab] = useState<BenefitSectionKey>("default");

  // Real Global Benefits for Live Asset Preview
  const [globalBenefits, setGlobalBenefits] = useState<GlobalBenefit[]>([]);
  const [, setLoadingBenefits] = useState(false);

  // Load all presets (System + Overrides + Custom)
  const refreshPresets = useCallback((targetId?: string) => {
    const presets = getAllBenefitPresets();
    setAllPresets(presets);
    const target = targetId || selectedPresetId;
    const found = presets.find((p) => p.id === target) || presets[0];
    if (found) {
      setSelectedPresetId(found.id);
      setCustomStyle({
        ...found,
        sectionVisibility: normalizeSectionVisibility(found.sectionVisibility, found),
      });
    }
  }, [selectedPresetId]);

  useEffect(() => {
    refreshPresets();
  }, [refreshPresets]);

  const systemPresets = useMemo(() => {
    return allPresets.filter((p) => !p.is_custom);
  }, [allPresets]);

  const customPresets = useMemo(() => {
    return allPresets.filter((p) => p.is_custom);
  }, [allPresets]);

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
    void loadGlobalBenefits();
  }, [loadGlobalBenefits]);

  function handleSelectPreset(preset: BenefitCardStyle) {
    setSelectedPresetId(preset.id);
    setCustomStyle({
      ...preset,
      sectionVisibility: normalizeSectionVisibility(preset.sectionVisibility, preset),
    });
  }

  // Save changes to current preset
  function saveCurrentPreset() {
    savePresetOverride(customStyle.id, customStyle);
    refreshPresets(customStyle.id);
    toast(`Saved changes to "${customStyle.name}".`, "success");
  }

  // Reset current system preset to default
  function resetCurrentPreset() {
    resetPresetToDefault(customStyle.id);
    refreshPresets(customStyle.id);
    toast(`"${customStyle.name}" reset to factory system defaults.`, "info");
  }

  // Save as new custom preset
  function saveAsNewBenefitPreset() {
    const name = window.prompt("Enter a name for this custom benefit card preset:", `${customStyle.name} (Copy)`);
    if (!name?.trim()) return;
    const newId = `custom-${Date.now()}`;
    const newPreset: BenefitCardStyle = {
      ...customStyle,
      id: newId,
      name: name.trim(),
      shortName: name.trim().slice(0, 16),
      is_default: false,
      is_custom: true,
      is_system_modified: false,
      sectionVisibility: normalizeSectionVisibility(customStyle.sectionVisibility, customStyle),
    };
    const saved = localStorage.getItem("risklocker_benefit_card_presets");
    const list: BenefitCardStyle[] = saved ? JSON.parse(saved) : [];
    list.push(newPreset);
    try {
      localStorage.setItem("risklocker_benefit_card_presets", JSON.stringify(list));
    } catch {}
    refreshPresets(newId);
    toast(`Preset "${newPreset.name}" created successfully.`, "success");
  }

  // Set preset as global default
  function setAsDefaultBenefitPreset() {
    try {
      localStorage.setItem("risklocker_default_benefit_preset", customStyle.id);
    } catch {}
    toast(`"${customStyle.name}" set as default benefit style for quotations and builder.`, "success");
  }

  // Delete custom preset
  function deleteCustomPreset(preset: BenefitCardStyle) {
    const saved = localStorage.getItem("risklocker_benefit_card_presets");
    const list: BenefitCardStyle[] = saved ? JSON.parse(saved) : [];
    const updated = list.filter((p) => p.id !== preset.id);
    try {
      localStorage.setItem("risklocker_benefit_card_presets", JSON.stringify(updated));
    } catch {}
    refreshPresets(systemPresets[0]?.id || "masonry-flow");
    setPendingDeletePreset(null);
    toast(`Preset "${preset.name}" removed.`, "success");
  }

  // Toggle single component for a given section
  function toggleComponentVisibility(section: BenefitSectionKey, comp: keyof SectionComponentVisibility) {
    const norm = normalizeSectionVisibility(customStyle.sectionVisibility, customStyle);
    const updatedSec: SectionComponentVisibility = {
      ...norm[section],
      [comp]: !norm[section][comp],
    };
    const updatedVis: BenefitSectionVisibility = {
      ...norm,
      [section]: updatedSec,
    };
    setCustomStyle({
      ...customStyle,
      sectionVisibility: updatedVis,
    });
  }

  // Bulk toggle for a given section
  function setSectionAllVisibility(section: BenefitSectionKey, value: boolean) {
    const norm = normalizeSectionVisibility(customStyle.sectionVisibility, customStyle);
    const updatedSec: SectionComponentVisibility = {
      showAsset: value,
      showTitle: value,
      showCoverage: value,
      showDescription: value,
      showCost: value,
    };
    const updatedVis: BenefitSectionVisibility = {
      ...norm,
      [section]: updatedSec,
    };
    setCustomStyle({
      ...customStyle,
      sectionVisibility: updatedVis,
    });
  }

  // Render Shape Style Helper
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

  // 3-Section 5-Attribute Mock Data (Default, Added Add-ons, Available Add-ons)
  const SAMPLE_3SEC_BENEFITS = [
    // 1. Default Benefits (FOC)
    {
      id: "b1",
      label: "Own Damage",
      sectionKind: "default" as const,
      category: "default" as const,
      coverage: "RM 50,000.00",
      description: "Accidental collision, overturning, fire, explosion & theft protection.",
      cost: "Included (FOC)",
      costStatus: "foc" as const,
    },
    {
      id: "b2",
      label: "Third Party Bodily Injury",
      sectionKind: "default" as const,
      category: "default" as const,
      coverage: "Statutory Unlimited",
      description: "Unlimited coverage for third-party injury, hospitalization & accidental death.",
      cost: "Included (FOC)",
      costStatus: "foc" as const,
    },
    {
      id: "b3",
      label: "Third Party Property Damage",
      sectionKind: "default" as const,
      category: "default" as const,
      coverage: "RM 3,000,000.00",
      description: "Third-party vehicle, roadside fixture, and public property damage.",
      cost: "Included (FOC)",
      costStatus: "foc" as const,
    },
    {
      id: "b4",
      label: "Emergency Towing Assistance",
      sectionKind: "default" as const,
      category: "default" as const,
      coverage: "200 km / RM 500",
      description: "24/7 unlimited breakdown roadside towing to nearest authorized workshop.",
      cost: "Included (FOC)",
      costStatus: "foc" as const,
    },
    // 2. Added Add-ons (Selected Extras)
    {
      id: "b5",
      label: "Windscreen & Glass Protection",
      sectionKind: "addedAddons" as const,
      category: "addon" as const,
      coverage: "RM 1,000.00",
      description: "Repair & replacement of front, rear and all side door glass with 0% excess.",
      cost: "+RM 150.00",
      costStatus: "paid" as const,
    },
    {
      id: "b6",
      label: "Special Perils (Flood & Storm)",
      sectionKind: "addedAddons" as const,
      category: "addon" as const,
      coverage: "RM 50,000.00",
      description: "Full protection against floods, typhoons, landslides, fallen trees & tempests.",
      cost: "+RM 125.00",
      costStatus: "paid" as const,
    },
    // 3. Add-on Section (Available Optional Add-ons)
    {
      id: "b7",
      label: "Driver Passenger Protector (DPP)",
      sectionKind: "optionalAddons" as const,
      category: "addon" as const,
      coverage: "RM 20,000.00",
      description: "Personal accident, accidental death, disablement & medical reimbursement.",
      cost: "RM 70.00 / yr",
      costStatus: "paid" as const,
    },
    {
      id: "b8",
      label: "Legal Liability to Passengers",
      sectionKind: "optionalAddons" as const,
      category: "addon" as const,
      coverage: "Statutory Unlimited",
      description: "Legal protection against third-party negligence lawsuits by passengers.",
      cost: "RM 20.00 / yr",
      costStatus: "paid" as const,
    },
  ];

  // Active preview list: blend real DB Global Benefits with 3-section structure
  const previewItems = useMemo(() => {
    if (globalBenefits.length) {
      const defs = globalBenefits.filter((gb) => (gb.category || (gb.sort_order <= 11 ? "default" : "addon")) === "default").slice(0, 4);
      const addeds = globalBenefits.filter((gb) => (gb.category || (gb.sort_order <= 11 ? "default" : "addon")) !== "default").slice(0, 2);
      const optionals = globalBenefits.filter((gb) => (gb.category || (gb.sort_order <= 11 ? "default" : "addon")) !== "default").slice(2, 4);

      const mappedDefs = defs.map((gb, idx) => ({
        id: gb.id,
        label: gb.label || SAMPLE_3SEC_BENEFITS[idx].label,
        sectionKind: "default" as const,
        category: "default" as const,
        coverage: gb.variants?.[0] || SAMPLE_3SEC_BENEFITS[idx].coverage,
        description: gb.description || SAMPLE_3SEC_BENEFITS[idx].description,
        cost: "Included (FOC)",
        costStatus: "foc" as const,
        asset_url: gb.default_asset?.url || null,
      }));

      const mappedAddeds = addeds.map((gb, idx) => ({
        id: gb.id,
        label: gb.label || SAMPLE_3SEC_BENEFITS[4 + idx].label,
        sectionKind: "addedAddons" as const,
        category: "addon" as const,
        coverage: gb.variants?.[0] ? `Limit: ${gb.variants[0]}` : SAMPLE_3SEC_BENEFITS[4 + idx].coverage,
        description: gb.description || SAMPLE_3SEC_BENEFITS[4 + idx].description,
        cost: SAMPLE_3SEC_BENEFITS[4 + idx].cost,
        costStatus: "paid" as const,
        asset_url: gb.default_asset?.url || null,
      }));

      const mappedOptionals = optionals.map((gb, idx) => ({
        id: gb.id,
        label: gb.label || SAMPLE_3SEC_BENEFITS[6 + idx].label,
        sectionKind: "optionalAddons" as const,
        category: "addon" as const,
        coverage: gb.variants?.[0] ? `Limit: ${gb.variants[0]}` : SAMPLE_3SEC_BENEFITS[6 + idx].coverage,
        description: gb.description || SAMPLE_3SEC_BENEFITS[6 + idx].description,
        cost: SAMPLE_3SEC_BENEFITS[6 + idx].cost,
        costStatus: "paid" as const,
        asset_url: gb.default_asset?.url || null,
      }));

      return [...mappedDefs, ...mappedAddeds, ...mappedOptionals];
    }
    return SAMPLE_3SEC_BENEFITS.map((item) => ({ ...item, asset_url: null }));
  }, [globalBenefits]);

  // Current normalized visibility map
  const activeVisibility = useMemo(() => {
    return normalizeSectionVisibility(customStyle.sectionVisibility, customStyle);
  }, [customStyle]);

  function renderBenefitCardPreview(benefit: (typeof previewItems)[0]) {
    const isDark = customStyle.bgColor === "#0f172a" || customStyle.bgColor === "#1b1717";
    const textColor = isDark ? "#ffffff" : customStyle.textColor;
    const subTextColor = isDark ? "#94a3b8" : "#64748b";

    // 5-component visibility resolution for this specific section
    const secVis = activeVisibility[benefit.sectionKind];
    const showAsset = secVis.showAsset;
    const showTitle = secVis.showTitle;
    const showCoverage = secVis.showCoverage;
    const showDescription = secVis.showDescription;
    const showCost = secVis.showCost;

    const isDefault = benefit.sectionKind === "default";
    const isAdded = benefit.sectionKind === "addedAddons";

    // If all 5 components are switched off for this section
    const allHidden = !showAsset && !showTitle && !showCoverage && !showDescription && !showCost;

    if (allHidden) {
      return (
        <div
          key={benefit.id}
          style={{
            borderRadius: getCardRadius(customStyle.shape),
            borderColor: customStyle.borderColor,
            borderWidth: `${customStyle.borderWidth}px`,
            borderStyle: "dashed",
          }}
          className="p-3 text-center text-xs text-[var(--rl-text-muted)] bg-neutral-50/50"
        >
          <span className="italic opacity-60">All 5 card components hidden for this section</span>
        </div>
      );
    }

    // 1. Signature 2-Column or Masonry (Merged 2-Column)
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
            minHeight: customStyle.uniformHeight ? `${customStyle.uniformHeight}px` : "auto",
            ...(customStyle.layout === "masonry" ? { breakInside: "avoid" as const, marginBottom: "12px" } : {}),
          }}
          className={`flex flex-col justify-between p-3.5 transition-all ${
            isAdded
              ? isDark ? "border-amber-500/40 bg-amber-950/10" : "border-amber-300/80 bg-amber-50/20"
              : benefit.sectionKind === "optionalAddons"
              ? isDark ? "border-sky-500/40 bg-sky-950/10" : "border-sky-200 bg-sky-50/20"
              : ""
          }`}
        >
          {/* Row 1: Full-Width Title (no redundant category badge) */}
          {showTitle && (
            <div className="mb-2 pb-1.5 border-b border-black/5 dark:border-white/10">
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
            </div>
          )}

          {/* Row 2: Image Left + Details Stack Right */}
          <div className="flex items-start gap-3 min-h-0 flex-1">
            {/* Benefit Image (Component 1) */}
            {showAsset && (
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
                    className={customStyle.iconPadShape === "dark" ? "text-white" : isAdded ? "text-[var(--rl-red)]" : "text-sky-600"}
                  />
                )}
              </div>
            )}

            {/* Right Column: Coverage, Description, Cost */}
            <div className="flex-1 min-w-0 flex flex-col justify-start">
              {/* Coverage Info (Component 3) */}
              {showCoverage && (
                <span
                  className="font-bold tracking-tight text-[var(--rl-red)] leading-tight"
                  style={{ fontSize: `${Math.max(11, customStyle.titleSize)}px` }}
                >
                  {benefit.coverage}
                </span>
              )}

              {/* Description (Component 4) */}
              {showDescription && benefit.description && (
                <p
                  style={{ color: subTextColor }}
                  className="text-[10.5px] leading-snug mt-0.5"
                >
                  {benefit.description}
                </p>
              )}

              {/* Costing (Component 5) */}
              {showCost && (
                <div className="mt-1.5 flex items-center gap-1.5">
                  <span
                    className={`inline-block rounded px-2 py-0.5 text-[9.5px] font-bold border ${
                      isDefault
                        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                        : "bg-red-50 text-red-600 border-red-200"
                    }`}
                  >
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
            minHeight: customStyle.uniformHeight ? `${customStyle.uniformHeight}px` : "auto",
          }}
          className="flex flex-col items-center text-center justify-between p-4 transition-all"
        >
          {showAsset && (
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
          )}

          {showTitle && (
            <h5
              style={{ fontSize: `${customStyle.titleSize}px`, color: textColor }}
              className="font-bold truncate w-full"
            >
              {benefit.label}
            </h5>
          )}

          {showCoverage && (
            <span className="text-[11px] font-bold text-[var(--rl-red)] mt-0.5 block truncate w-full">
              {benefit.coverage}
            </span>
          )}

          {showDescription && benefit.description && (
            <p style={{ color: subTextColor }} className="text-[10px] line-clamp-2 mt-1 w-full leading-snug">
              {benefit.description}
            </p>
          )}

          {showCost && (
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
            minHeight: customStyle.uniformHeight ? `${customStyle.uniformHeight}px` : "auto",
          }}
          className="flex items-center justify-between p-3 transition-all gap-3"
        >
          <div className="flex items-center gap-3 min-w-0 flex-1">
            {showAsset && (
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
            )}
            <div className="min-w-0 flex-1">
              {showTitle && (
                <h5 style={{ fontSize: `${customStyle.titleSize}px`, color: textColor }} className="font-bold truncate">
                  {benefit.label}
                </h5>
              )}
              {showCoverage && (
                <span className="text-[11px] font-bold text-[var(--rl-red)] block truncate">
                  {benefit.coverage}
                </span>
              )}
              {showDescription && (
                <p style={{ color: subTextColor }} className="text-[10px] truncate leading-snug">
                  {benefit.description}
                </p>
              )}
            </div>
          </div>
          {showCost && (
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
          minHeight: customStyle.uniformHeight ? `${customStyle.uniformHeight}px` : "auto",
        }}
        className="flex items-center justify-between px-3.5 py-2 transition-all gap-2"
      >
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          {showAsset && (
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
          )}
          <div className="min-w-0 flex-1">
            {showTitle && (
              <h5 style={{ fontSize: `${customStyle.titleSize}px`, color: textColor }} className="font-bold truncate">
                {benefit.label}
              </h5>
            )}
            {showCoverage && (
              <span className="text-[10.5px] font-bold text-[var(--rl-red)] truncate block">
                {benefit.coverage}
              </span>
            )}
          </div>
        </div>
        {showCost && (
          <span className="shrink-0 text-[9.5px] font-bold rounded px-1.5 py-0.5 bg-red-50 text-red-600 border border-red-200">
            {benefit.cost}
          </span>
        )}
      </div>
    );
  }

  const isCurrentSystemModified = customStyle.is_system_modified || (!customStyle.is_custom && typeof window !== "undefined" && Boolean(localStorage.getItem("risklocker_benefit_preset_overrides")?.includes(customStyle.id)));

  return (
    <AppShell>
      <section className="grid gap-6">
        {/* Top Header */}
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--rl-red)]">Builder</p>
            <h1 className="m-0 font-[var(--font-manrope)] text-[30px] font-bold text-[var(--rl-text-strong)]">Benefit Templates</h1>
            <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
              Design, preview, and configure benefit card component styles and 3-section visibility for quotation displays.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {isCurrentSystemModified && (
              <Button variant="secondary" size="sm" icon={<ArrowCounterClockwise size={14} />} onClick={resetCurrentPreset}>
                Reset to Default
              </Button>
            )}
            <Button variant="secondary" size="sm" icon={<FloppyDisk size={14} />} onClick={saveCurrentPreset}>
              Save Changes to Preset
            </Button>
            <Button variant="secondary" size="sm" icon={<CopySimple size={14} />} onClick={saveAsNewBenefitPreset}>
              Save as New Preset
            </Button>
            <Button size="sm" icon={<Star size={14} weight="fill" />} onClick={setAsDefaultBenefitPreset}>
              Set as Default Template
            </Button>
          </div>
        </header>

        <BuilderNav />

        {/* Top Subtabs Navigation: Quotation Templates vs Benefit Templates */}
        <div className="flex items-center gap-2 border-b border-[var(--rl-border)] pb-2">
          <Link
            href={"/builder/templates/quotation-templates" as Route}
            className="flex items-center gap-2 rounded-t-[var(--rl-radius-sm)] border border-transparent bg-transparent px-4 py-2 text-xs font-bold text-[var(--rl-text-muted)] transition-all hover:bg-neutral-100 hover:text-[var(--rl-text-strong)]"
          >
            <FilePdf size={16} weight="bold" />
            <span>Quotation Templates</span>
          </Link>

          <Link
            href={"/builder/templates/benefit-templates" as Route}
            className="flex items-center gap-2 rounded-t-[var(--rl-radius-sm)] bg-[var(--rl-black)] px-4 py-2 text-xs font-bold text-white shadow-sm transition-all"
          >
            <ShieldCheck size={16} weight="bold" />
            <span>Benefit Templates</span>
            <span className="ml-1 rounded-full bg-white/20 px-1.5 py-0.5 text-[10px] font-bold text-white">
              {systemPresets.length + customPresets.length}
            </span>
          </Link>
        </div>

        {/* BENEFIT CARD COMPONENT TEMPLATES DESIGNER */}
        <div className="space-y-6">
          {/* Presets Organized into 2 Distinct Rows (System vs Custom) */}
          <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm space-y-4">
            {/* Row 1: System Presets */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                  System Presets (Permanent)
                </h3>
                <span className="text-[11px] text-[var(--rl-text-muted)]">Out-of-the-box templates · Click to select & customize</span>
              </div>

              <div className="flex flex-wrap gap-2">
                {systemPresets.map((preset) => {
                  const isCurrent = preset.id === selectedPresetId;
                  const isModified = preset.is_system_modified;
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
                      {isModified && (
                        <span className={`rounded px-1.5 py-0.2 text-[9px] font-bold uppercase ${isCurrent ? "bg-amber-400 text-black" : "bg-amber-100 text-amber-800 border border-amber-300"}`}>
                          Modified
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
                  Custom Saved Presets ({customPresets.length})
                </h3>
                <span className="text-[11px] text-[var(--rl-text-muted)]">User-created styles saved in browser</span>
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
            {/* Left Column (5 cols): Style Controls & 3-Section 5-Component Visibility */}
            <div className="lg:col-span-5 space-y-4">
              {/* SECTION COMPONENT VISIBILITY (QUOTATION SYNC) */}
              <div className="rounded-[var(--rl-radius)] border-2 border-[var(--rl-red)] bg-[var(--rl-surface)] p-4 shadow-sm space-y-4">
                <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2.5">
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-red)] flex items-center gap-1.5">
                      <ShieldCheck size={16} weight="bold" />
                      <span>3-Section Component Visibility</span>
                    </h4>
                    <p className="text-[11px] text-[var(--rl-text-muted)] mt-0.5">
                      Control which of the 5 card elements appear in each quotation section.
                    </p>
                  </div>
                  <Tooltip content="Configures which of the 5 elements (Image, Title, Coverage, Description, Costing) display in the 3 quotation benefit sections.">
                    <Info size={14} className="text-[var(--rl-text-muted)]" />
                  </Tooltip>
                </div>

                {/* 3 Section Selector Tabs */}
                <div className="grid grid-cols-3 gap-1 rounded-[var(--rl-radius-sm)] bg-neutral-100 p-1 text-xs font-bold">
                  {[
                    { key: "default" as const, label: "1. Default Benefits", sub: "FOC" },
                    { key: "addedAddons" as const, label: "2. Added Add-ons", sub: "Extras" },
                    { key: "optionalAddons" as const, label: "3. Optional Add-ons", sub: "Available" },
                  ].map((tab) => {
                    const isActive = activeSectionTab === tab.key;
                    return (
                      <button
                        key={tab.key}
                        type="button"
                        onClick={() => setActiveSectionTab(tab.key)}
                        className={`rounded-[var(--rl-radius-sm)] px-2 py-2 text-center transition-all ${
                          isActive
                            ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                            : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                        }`}
                      >
                        <div className="leading-tight">{tab.label}</div>
                        <div className={`text-[9px] font-semibold mt-0.5 ${isActive ? "text-[var(--rl-red)]" : "text-neutral-400"}`}>
                          {tab.sub}
                        </div>
                      </button>
                    );
                  })}
                </div>

                {/* Quick Toggle Helpers for active section */}
                <div className="flex items-center justify-between text-[11px] text-[var(--rl-text-muted)] px-1">
                  <span>
                    Configuring: <strong className="text-[var(--rl-text-strong)]">
                      {activeSectionTab === "default" ? "Default Benefits (FOC)" : activeSectionTab === "addedAddons" ? "Added Add-ons (Extras)" : "Available Optional Add-ons"}
                    </strong>
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setSectionAllVisibility(activeSectionTab, true)}
                      className="text-[10px] font-bold text-emerald-700 hover:underline"
                    >
                      All ON
                    </button>
                    <span>·</span>
                    <button
                      type="button"
                      onClick={() => setSectionAllVisibility(activeSectionTab, false)}
                      className="text-[10px] font-bold text-red-600 hover:underline"
                    >
                      All OFF
                    </button>
                  </div>
                </div>

                {/* 5 Component Switches for Active Section */}
                <div className="space-y-2">
                  {[
                    {
                      key: "showAsset" as const,
                      label: "1. Benefit Image / Icon",
                      desc: "High-resolution icon container or insurer artwork",
                      icon: <ImageSquare size={16} weight="bold" className="text-sky-600" />,
                    },
                    {
                      key: "showTitle" as const,
                      label: "2. Benefit Title / Header",
                      desc: "Main benefit endorsement name and typography styling",
                      icon: <TextT size={16} weight="bold" className="text-violet-600" />,
                    },
                    {
                      key: "showCoverage" as const,
                      label: "3. Coverage Info / Limit (RM)",
                      desc: "Sum insured limit or statutory unlimited entitlement",
                      icon: <ShieldCheck size={16} weight="bold" className="text-emerald-600" />,
                    },
                    {
                      key: "showDescription" as const,
                      label: "4. Benefit Description",
                      desc: "Explanatory legal coverage and terms bullet points",
                      icon: <Article size={16} weight="bold" className="text-amber-600" />,
                    },
                    {
                      key: "showCost" as const,
                      label: "5. Costing / Price Tag",
                      desc: "Included (FOC) badge or calculated annual premium fee",
                      icon: <CurrencyCircleDollar size={16} weight="bold" className="text-red-600" />,
                    },
                  ].map((comp) => {
                    const isEnabled = activeVisibility[activeSectionTab][comp.key];
                    return (
                      <div
                        key={comp.key}
                        onClick={() => toggleComponentVisibility(activeSectionTab, comp.key)}
                        className={`flex items-center justify-between p-3 rounded-[var(--rl-radius-sm)] border cursor-pointer select-none transition-all ${
                          isEnabled
                            ? "border-emerald-200 bg-emerald-50/30 hover:border-emerald-300"
                            : "border-neutral-200 bg-neutral-50/60 opacity-70 hover:opacity-100"
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0 pr-2">
                          <div className="p-1.5 rounded bg-white shadow-2xs shrink-0 border border-black/5">
                            {comp.icon}
                          </div>
                          <div className="min-w-0">
                            <div className="text-xs font-bold text-[var(--rl-text-strong)] flex items-center gap-1.5">
                              <span>{comp.label}</span>
                              {isEnabled ? (
                                <Eye size={13} className="text-emerald-600" />
                              ) : (
                                <EyeSlash size={13} className="text-neutral-400" />
                              )}
                            </div>
                            <div className="text-[10.5px] text-[var(--rl-text-muted)] truncate">
                              {comp.desc}
                            </div>
                          </div>
                        </div>

                        {/* Interactive Toggle Pill */}
                        <div
                          className={`relative inline-flex h-5 w-10 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                            isEnabled ? "bg-emerald-600" : "bg-neutral-300"
                          }`}
                        >
                          <span
                            className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                              isEnabled ? "translate-x-5" : "translate-x-0"
                            }`}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Section 0: Layout Architecture & Presentation */}
              <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                    0. Layout Architecture & Flow
                  </h4>
                  <span className="rounded bg-red-50 border border-red-200 px-1.5 py-0.2 text-[9px] font-bold uppercase text-[var(--rl-red)]">
                    Dynamic Flow
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

              {/* Section 2: Asset / Image Fitting & Sizing (Up to 60px) */}
              <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                    2. Image Size & Asset Fit
                  </h4>
                  <Tooltip content="Choose how uploaded benefit artwork fits inside the icon container (contain vs cover crop) and size up to 60px">
                    <Info size={13} className="text-[var(--rl-text-muted)]" />
                  </Tooltip>
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-[var(--rl-text-strong)]">Icon Artwork Size</label>
                    <span className="text-xs font-bold text-[var(--rl-red)]">{customStyle.iconSize}px</span>
                  </div>
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

              {/* Section 3: Typography & Text Settings */}
              <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-sm space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                  3. Typography & Badges
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
            <div className="lg:col-span-7 space-y-5">
              <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm space-y-4">
                <div className="flex flex-wrap items-center justify-between border-b border-[var(--rl-border)] pb-3 gap-2">
                  <div>
                    <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">
                      Live Benefit Cards Template Preview
                    </h3>
                    <p className="text-xs text-[var(--rl-text-muted)]">
                      Visualizing with: <span className="font-semibold text-[var(--rl-text-strong)]">{customStyle.name}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-red-50 border border-red-200 px-2 py-0.5 text-xs font-bold text-[var(--rl-red)] uppercase">
                      {customStyle.layout.toUpperCase()}
                    </span>
                    <span className="rounded bg-[var(--rl-bg)] border border-[var(--rl-border)] px-2 py-0.5 text-xs font-bold text-[var(--rl-text-strong)]">
                      {customStyle.shape.toUpperCase()} · {customStyle.iconSize}px ICON
                    </span>
                  </div>
                </div>

                {/* Section 1: Default Benefits (4 items) */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-emerald-500" />
                      <span className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                        Section 1: Default Benefits (FOC)
                      </span>
                    </div>
                    <span className="text-[11px] text-[var(--rl-text-muted)]">
                      {previewItems.filter((i) => i.sectionKind === "default").length} cards
                    </span>
                  </div>

                  {customStyle.layout === "masonry" ? (
                    <div style={{ columnCount: 2, columnGap: "12px" }}>
                      {previewItems.filter((i) => i.sectionKind === "default").map((b) => renderBenefitCardPreview(b))}
                    </div>
                  ) : (
                    <div className={`grid gap-3 ${customStyle.layout === "tile" ? "grid-cols-1 sm:grid-cols-2 md:grid-cols-3" : "grid-cols-1 sm:grid-cols-2"}`}>
                      {previewItems.filter((i) => i.sectionKind === "default").map((b) => renderBenefitCardPreview(b))}
                    </div>
                  )}
                </div>

                {/* Section 2: Added Add-ons (2 items) */}
                <div className="border-t border-[var(--rl-border)] pt-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-amber-500" />
                      <span className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                        Section 2: Added Add-ons (Selected Extras)
                      </span>
                    </div>
                    <span className="text-[11px] text-[var(--rl-text-muted)]">
                      {previewItems.filter((i) => i.sectionKind === "addedAddons").length} cards
                    </span>
                  </div>

                  {customStyle.layout === "masonry" ? (
                    <div style={{ columnCount: 2, columnGap: "12px" }}>
                      {previewItems.filter((i) => i.sectionKind === "addedAddons").map((b) => renderBenefitCardPreview(b))}
                    </div>
                  ) : (
                    <div className={`grid gap-3 ${customStyle.layout === "tile" ? "grid-cols-1 sm:grid-cols-2 md:grid-cols-3" : "grid-cols-1 sm:grid-cols-2"}`}>
                      {previewItems.filter((i) => i.sectionKind === "addedAddons").map((b) => renderBenefitCardPreview(b))}
                    </div>
                  )}
                </div>

                {/* Section 3: Available Optional Add-ons (2 items) */}
                <div className="border-t border-[var(--rl-border)] pt-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-sky-500" />
                      <span className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                        Section 3: Add-on Section (Available Endorsements)
                      </span>
                    </div>
                    <span className="text-[11px] text-[var(--rl-text-muted)]">
                      {previewItems.filter((i) => i.sectionKind === "optionalAddons").length} cards
                    </span>
                  </div>

                  {customStyle.layout === "masonry" ? (
                    <div style={{ columnCount: 2, columnGap: "12px" }}>
                      {previewItems.filter((i) => i.sectionKind === "optionalAddons").map((b) => renderBenefitCardPreview(b))}
                    </div>
                  ) : (
                    <div className={`grid gap-3 ${customStyle.layout === "tile" ? "grid-cols-1 sm:grid-cols-2 md:grid-cols-3" : "grid-cols-1 sm:grid-cols-2"}`}>
                      {previewItems.filter((i) => i.sectionKind === "optionalAddons").map((b) => renderBenefitCardPreview(b))}
                    </div>
                  )}
                </div>
              </div>

              {/* Quotation Canvas Integration Visualizer */}
              <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                    Quotation A4 Layout Integration
                  </h4>
                  <span className="text-[11px] text-[var(--rl-text-muted)]">
                    Live dynamic preview in quotation benefit slot · {customStyle.iconSize}px icon
                  </span>
                </div>

                <div className="rounded-[var(--rl-radius-sm)] border border-dashed border-[var(--rl-red)] bg-[#fafafc] p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-red)]">
                      Your Benefits (Dynamic Slot · 3-Section Sync)
                    </span>
                    <span className="text-[10px] text-[var(--rl-text-muted)]">A4 Canvas Bounding Box</span>
                  </div>

                  <div className="grid grid-cols-2 gap-2.5">
                    {previewItems.slice(0, 4).map((benefit) => {
                      const secVis = activeVisibility[benefit.sectionKind];
                      return (
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
                          {secVis.showAsset && (
                            <div
                              style={{ width: `${customStyle.iconSize}px`, height: `${customStyle.iconSize}px` }}
                              className="grid place-items-center rounded bg-neutral-100 border border-neutral-200 shrink-0 overflow-hidden"
                            >
                              {benefit.asset_url ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                  src={fileUrl(benefit.asset_url)}
                                  alt={benefit.label}
                                  style={{ width: "100%", height: "100%", objectFit: customStyle.imageFit }}
                                />
                              ) : (
                                <ShieldCheck size={customStyle.iconSize * 0.55} className="text-[var(--rl-black)]" />
                              )}
                            </div>
                          )}
                          <div className="min-w-0 flex-1">
                            {secVis.showTitle && (
                              <div className="flex items-center justify-between gap-1">
                                <span className="text-xs font-bold text-[var(--rl-text-strong)] truncate">
                                  {benefit.label}
                                </span>
                                {secVis.showCost && (
                                  <span className="text-[9px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-1 shrink-0">
                                    {benefit.cost}
                                  </span>
                                )}
                              </div>
                            )}
                            {secVis.showCoverage && (
                              <span className="text-[11px] font-bold text-[var(--rl-red)] block truncate mt-0.5">
                                {benefit.coverage}
                              </span>
                            )}
                            {secVis.showDescription && (
                              <p className="text-[9.5px] text-neutral-500 truncate leading-snug">
                                {benefit.description}
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

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
