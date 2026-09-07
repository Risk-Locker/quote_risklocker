export type SectionComponentVisibility = {
  showAsset: boolean;
  showTitle: boolean;
  showCoverage: boolean;
  showDescription: boolean;
  showCost: boolean;
};

export type BenefitSectionVisibility = {
  default: SectionComponentVisibility;
  addedAddons: SectionComponentVisibility;
  optionalAddons: SectionComponentVisibility;
};

export type BenefitCardStyle = {
  id: string;
  name: string;
  shortName: string;
  description: string;
  is_default?: boolean;
  is_custom?: boolean;
  is_system_modified?: boolean;
  shape: "rounded" | "racetrack" | "square" | "soft" | "oval";
  layout: "merged-2col" | "masonry" | "horizontal" | "tile" | "compact";
  borderWidth: number;
  borderStyle: "solid" | "dashed" | "none";
  elevation: "flat" | "shadow" | "lift";
  uniformHeight: number; // in px, e.g. 0 for auto, 38, 52, 60
  iconSize: number; // in px (28 - 60px)
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
  columns: number;
  layoutMode: "masonry" | "normal";
  textDensity: "compact" | "normal" | "comfortable";
  cardStyle: "standard" | "outlined" | "soft" | "minimal";
  rowHeight: number;
  sectionVisibility?: BenefitSectionVisibility;
};

export function normalizeSectionVisibility(
  vis?: Partial<BenefitSectionVisibility>,
  fallback?: Partial<BenefitCardStyle>
): BenefitSectionVisibility {
  const defDesc = fallback?.showDescription ?? true;
  const defCov = fallback?.showCoverage ?? true;
  const defCost = fallback?.showCost ?? true;

  const defaultComp: SectionComponentVisibility = {
    showAsset: true,
    showTitle: true,
    showCoverage: defCov,
    showDescription: defDesc,
    showCost: defCost,
  };

  return {
    default: {
      showAsset: vis?.default?.showAsset ?? defaultComp.showAsset,
      showTitle: vis?.default?.showTitle ?? defaultComp.showTitle,
      showCoverage: vis?.default?.showCoverage ?? defaultComp.showCoverage,
      showDescription: vis?.default?.showDescription ?? defaultComp.showDescription,
      showCost: vis?.default?.showCost ?? defaultComp.showCost,
    },
    addedAddons: {
      showAsset: vis?.addedAddons?.showAsset ?? defaultComp.showAsset,
      showTitle: vis?.addedAddons?.showTitle ?? defaultComp.showTitle,
      showCoverage: vis?.addedAddons?.showCoverage ?? defaultComp.showCoverage,
      showDescription: vis?.addedAddons?.showDescription ?? defaultComp.showDescription,
      showCost: vis?.addedAddons?.showCost ?? defaultComp.showCost,
    },
    optionalAddons: {
      showAsset: vis?.optionalAddons?.showAsset ?? defaultComp.showAsset,
      showTitle: vis?.optionalAddons?.showTitle ?? defaultComp.showTitle,
      showCoverage: vis?.optionalAddons?.showCoverage ?? defaultComp.showCoverage,
      showDescription: vis?.optionalAddons?.showDescription ?? defaultComp.showDescription,
      showCost: vis?.optionalAddons?.showCost ?? defaultComp.showCost,
    },
  };
}

export const SYSTEM_BENEFIT_PRESETS: BenefitCardStyle[] = [
  {
    id: "masonry-flow",
    name: "Masonry Flow (Dynamic)",
    shortName: "Masonry Flow",
    description: "3-column fluid masonry, natural card heights, zero wasted space",
    is_default: true,
    is_custom: false,
    shape: "rounded",
    layout: "masonry",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "shadow",
    uniformHeight: 0,
    iconSize: 20,
    imageFit: "contain",
    iconPadShape: "box",
    titleSize: 10.5,
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
    columns: 3,
    layoutMode: "masonry",
    textDensity: "compact",
    cardStyle: "standard",
    rowHeight: 66,
  },
  {
    id: "compact-minimal",
    name: "Compact Minimalist (1-Page Fit)",
    shortName: "Compact Minimal",
    description: "Ultra-compact single-line rows, fits 35+ items cleanly on 1 page",
    is_custom: false,
    shape: "square",
    layout: "compact",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "flat",
    uniformHeight: 38,
    iconSize: 18,
    imageFit: "contain",
    iconPadShape: "none",
    titleSize: 9.5,
    titleWeight: "semibold",
    textWrap: "truncate",
    valueBadgeStyle: "subtle",
    showDescription: false,
    showCoverage: true,
    showCost: true,
    bgColor: "#ffffff",
    borderColor: "#f1f5f9",
    textColor: "#0f172a",
    accentColor: "#dc2626",
    columns: 3,
    layoutMode: "masonry",
    textDensity: "compact",
    cardStyle: "minimal",
    rowHeight: 40,
  },
  {
    id: "signature-2col",
    name: "Signature 2-Column (Classic)",
    shortName: "Signature 2-Col",
    description: "Classic 2-column balanced grid with prominent card titles",
    is_custom: false,
    shape: "rounded",
    layout: "merged-2col",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "shadow",
    uniformHeight: 0,
    iconSize: 24,
    imageFit: "contain",
    iconPadShape: "box",
    titleSize: 11,
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
    columns: 2,
    layoutMode: "normal",
    textDensity: "normal",
    cardStyle: "standard",
    rowHeight: 68,
  },
  {
    id: "elevated-3d",
    name: "Elevated 3D Card (Shadow Lift)",
    shortName: "Elevated 3D",
    description: "Soft cards with modern 3D elevation, subtle drop shadows",
    is_custom: false,
    shape: "soft",
    layout: "masonry",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "lift",
    uniformHeight: 0,
    iconSize: 22,
    imageFit: "contain",
    iconPadShape: "box",
    titleSize: 10.5,
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
    columns: 3,
    layoutMode: "masonry",
    textDensity: "compact",
    cardStyle: "soft",
    rowHeight: 68,
  },
  {
    id: "grid-tile",
    name: "Grid Tile (Modern Outlined)",
    shortName: "Grid Tile",
    description: "Clean outlined cards with circular icon pads and pill values",
    is_custom: false,
    shape: "rounded",
    layout: "masonry",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "flat",
    uniformHeight: 0,
    iconSize: 22,
    imageFit: "contain",
    iconPadShape: "circle",
    titleSize: 10,
    titleWeight: "bold",
    textWrap: "wrap",
    valueBadgeStyle: "pill",
    showDescription: true,
    showCoverage: true,
    showCost: true,
    bgColor: "#f8fafc",
    borderColor: "#cbd5e1",
    textColor: "#0f172a",
    accentColor: "#dc2626",
    columns: 3,
    layoutMode: "masonry",
    textDensity: "compact",
    cardStyle: "outlined",
    rowHeight: 68,
  },
  {
    id: "dark-signature",
    name: "Dark Luxury Executive",
    shortName: "Dark Luxury",
    description: "Executive dark slate cards with high-contrast amber highlights",
    is_custom: false,
    shape: "rounded",
    layout: "masonry",
    borderWidth: 1,
    borderStyle: "solid",
    elevation: "shadow",
    uniformHeight: 0,
    iconSize: 20,
    imageFit: "contain",
    iconPadShape: "box",
    titleSize: 10.5,
    titleWeight: "bold",
    textWrap: "wrap",
    valueBadgeStyle: "red",
    showDescription: true,
    showCoverage: true,
    showCost: true,
    bgColor: "#0f172a",
    borderColor: "#334155",
    textColor: "#ffffff",
    accentColor: "#f59e0b",
    columns: 3,
    layoutMode: "masonry",
    textDensity: "compact",
    cardStyle: "standard",
    rowHeight: 66,
  },
  {
    id: "dynamic-masonry",
    name: "Dynamic Expandable Masonry",
    shortName: "Dynamic Masonry",
    description: "Auto-expanding masonry grid that dynamically fits benefit boxes of varying heights",
    is_custom: false,
    shape: "rounded",
    layout: "masonry",
    borderWidth: 1,
    borderStyle: "dashed",
    elevation: "flat",
    uniformHeight: 0,
    iconSize: 22,
    imageFit: "contain",
    iconPadShape: "circle",
    titleSize: 11,
    titleWeight: "semibold",
    textWrap: "wrap",
    valueBadgeStyle: "subtle",
    showDescription: true,
    showCoverage: true,
    showCost: true,
    bgColor: "#ffffff",
    borderColor: "#e2e8f0",
    textColor: "#0f172a",
    accentColor: "#dc2626",
    columns: 2,
    layoutMode: "masonry",
    textDensity: "comfortable",
    cardStyle: "soft",
    rowHeight: 75,
  },
];

export function getAllBenefitPresets(): BenefitCardStyle[] {
  if (typeof window === "undefined") {
    return SYSTEM_BENEFIT_PRESETS.map((p) => ({
      ...p,
      sectionVisibility: normalizeSectionVisibility(p.sectionVisibility, p),
    }));
  }
  try {
    const overridesRaw = localStorage.getItem("risklocker_benefit_preset_overrides");
    const overrides: Record<string, Partial<BenefitCardStyle>> = overridesRaw ? JSON.parse(overridesRaw) : {};

    const mergedSystem = SYSTEM_BENEFIT_PRESETS.map((sys) => {
      if (overrides[sys.id]) {
        const merged: BenefitCardStyle = {
          ...sys,
          ...overrides[sys.id],
          is_system_modified: true,
        };
        return {
          ...merged,
          sectionVisibility: normalizeSectionVisibility(merged.sectionVisibility, merged),
        };
      }
      return {
        ...sys,
        sectionVisibility: normalizeSectionVisibility(sys.sectionVisibility, sys),
      };
    });

    const customRaw = localStorage.getItem("risklocker_benefit_card_presets");
    const customList: BenefitCardStyle[] = customRaw ? JSON.parse(customRaw) : [];
    const normalizedCustom = customList.map((c) => ({
      ...c,
      sectionVisibility: normalizeSectionVisibility(c.sectionVisibility, c),
    }));

    return [...mergedSystem, ...normalizedCustom];
  } catch (e) {
    console.warn("Failed to load benefit presets from localStorage:", e);
    return SYSTEM_BENEFIT_PRESETS.map((p) => ({
      ...p,
      sectionVisibility: normalizeSectionVisibility(p.sectionVisibility, p),
    }));
  }
}

export function getBenefitPreset(presetId: string | null | undefined): BenefitCardStyle {
  const all = getAllBenefitPresets();
  if (!presetId) return all[0];
  const found = all.find((p) => p.id === presetId);
  return found || all[0];
}

export function savePresetOverride(presetId: string, updates: Partial<BenefitCardStyle>): void {
  if (typeof window === "undefined") return;
  const isSystem = SYSTEM_BENEFIT_PRESETS.some((p) => p.id === presetId);
  if (isSystem) {
    try {
      const overridesRaw = localStorage.getItem("risklocker_benefit_preset_overrides");
      const overrides: Record<string, Partial<BenefitCardStyle>> = overridesRaw ? JSON.parse(overridesRaw) : {};
      overrides[presetId] = {
        ...(overrides[presetId] || {}),
        ...updates,
      };
      localStorage.setItem("risklocker_benefit_preset_overrides", JSON.stringify(overrides));
    } catch (e) {
      console.error("Failed to save system preset override:", e);
    }
  } else {
    try {
      const customRaw = localStorage.getItem("risklocker_benefit_card_presets");
      const customList: BenefitCardStyle[] = customRaw ? JSON.parse(customRaw) : [];
      const updated = customList.map((c) => (c.id === presetId ? { ...c, ...updates } : c));
      localStorage.setItem("risklocker_benefit_card_presets", JSON.stringify(updated));
    } catch (e) {
      console.error("Failed to update custom preset:", e);
    }
  }
}

export function resetPresetToDefault(presetId: string): void {
  if (typeof window === "undefined") return;
  try {
    const overridesRaw = localStorage.getItem("risklocker_benefit_preset_overrides");
    if (overridesRaw) {
      const overrides: Record<string, Partial<BenefitCardStyle>> = JSON.parse(overridesRaw);
      delete overrides[presetId];
      localStorage.setItem("risklocker_benefit_preset_overrides", JSON.stringify(overrides));
    }
  } catch (e) {
    console.error("Failed to reset preset:", e);
  }
}

export function applyPresetToCanvasElement(elem: any, presetInput: string | BenefitCardStyle): any {
  if (elem.type !== "benefit-grid") return elem;
  const preset = typeof presetInput === "string" ? getBenefitPreset(presetInput) : presetInput;
  const secVis = normalizeSectionVisibility(preset.sectionVisibility, preset);

  return {
    ...elem,
    benefitPreset: preset.id,
    layoutMode: preset.layoutMode,
    columns: preset.columns,
    cardStyle: preset.cardStyle,
    textDensity: preset.textDensity,
    // Visual styling properties:
    shape: preset.shape,
    borderWidth: preset.borderWidth,
    borderStyle: preset.borderStyle,
    elevation: preset.elevation,
    uniformHeight: preset.uniformHeight,
    iconSize: preset.iconSize,
    imageFit: preset.imageFit,
    iconPadShape: preset.iconPadShape,
    titleSize: preset.titleSize,
    titleWeight: preset.titleWeight,
    textWrap: preset.textWrap,
    valueBadgeStyle: preset.valueBadgeStyle,
    bgColor: preset.bgColor,
    borderColor: preset.borderColor,
    textColor: preset.textColor,
    accentColor: preset.accentColor,
    rowHeight: preset.rowHeight,
    // Section-component visibility:
    sectionVisibility: secVis,
    showDescription: preset.showDescription,
    showCoverage: preset.showCoverage,
    showCost: preset.showCost,
    packing: {
      ...(elem.packing || {}),
      strategy: preset.layoutMode === "masonry" ? "balanced" : (elem.packing?.strategy || "balanced"),
    },
  };
}
