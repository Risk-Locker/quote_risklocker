export type BenefitCardStyle = {
  id: string;
  name: string;
  shortName: string;
  description: string;
  is_default?: boolean;
  is_custom?: boolean;
  shape: "rounded" | "racetrack" | "square" | "soft" | "oval";
  layout: "merged-2col" | "masonry" | "horizontal" | "tile" | "compact";
  borderWidth: number;
  borderStyle: "solid" | "dashed" | "none";
  elevation: "flat" | "shadow" | "lift";
  uniformHeight: number; // in px, e.g. 0 for auto, 38, 52, 60
  iconSize: number; // in px
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
};

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

export function getBenefitPreset(presetId: string | null | undefined): BenefitCardStyle {
  if (!presetId) return SYSTEM_BENEFIT_PRESETS[0];
  const found = SYSTEM_BENEFIT_PRESETS.find((p) => p.id === presetId);
  return found || SYSTEM_BENEFIT_PRESETS[0];
}

export function applyPresetToCanvasElement(elem: any, presetId: string): any {
  if (elem.type !== "benefit-grid") return elem;
  const preset = getBenefitPreset(presetId);
  return {
    ...elem,
    benefitPreset: preset.id,
    layoutMode: preset.layoutMode,
    columns: preset.columns,
    cardStyle: preset.cardStyle,
    textDensity: preset.textDensity,
    packing: {
      ...(elem.packing || {}),
      strategy: preset.layoutMode === "masonry" ? "balanced" : (elem.packing?.strategy || "balanced"),
    },
  };
}
