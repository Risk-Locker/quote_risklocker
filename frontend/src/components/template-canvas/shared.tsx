"use client";

import { useEffect, useRef } from "react";

import { fileUrl } from "@/lib/api";
import { packFixedGrid } from "./grid-layout";
import { getOfficialInsurerName, getInsurerShortName } from "@/lib/company-names";

export type CanvasStyle = {
  fontSize?: number;
  fontWeight?: string;
  fontFamily?: string;
  fontStyle?: string;
  textTransform?: string;
  color?: string;
  textAlign?: string;
  borderWidth?: number;
  borderColor?: string;
  borderStyle?: string;
  borderRadius?: number;
  background?: string;
  letterSpacing?: number;
  lineHeight?: number;
  padding?: number;
  boxShadow?: string;
  rotation?: number;
  whiteSpace?: string;
};

export const FONT_LIBRARY = [
  "Arial",
  "Arial Black",
  "Georgia",
  "Times New Roman",
  "Verdana",
  "Tahoma",
  "Trebuchet MS",
  "Impact",
  "Courier New",
  "Comic Sans MS",
  "Lucida Console",
  "Segoe UI",
  "Calibri",
  "Cambria",
  "Consolas",
  "Garamond",
  "Palatino Linotype",
  "Franklin Gothic Medium",
] as const;

export type CanvasElement = {
  componentRole?: string;
  id: string;
  type: string;
  x: number;
  y: number;
  w: number;
  h: number;
  z?: number;
  text?: string;
  variableId?: string;
  assetId?: string;
  assetSlot?: string;
  cardId?: string;
  variantId?: string;
  section?: "specials" | "add_ons";
  columns?: number;
  gridKind?: "current_benefits" | "available_addons" | "extras" | "purchased_extras";
  excludeExtras?: boolean;
  packing?: {
    strategy?: "balanced" | "square_biased" | "staggered";
    alignment?: "start" | "center" | "end";
    aspectRatio?: number;
    referenceWidth?: number;
    referenceHeight?: number;
    gapRatio?: number;
    paddingRatio?: number;
    staggerRatio?: number;
  };
  cardStyle?: "standard" | "outlined" | "soft" | "minimal";
  textDensity?: "comfortable" | "normal" | "compact";
  layoutMode?: "normal" | "masonry";
  benefitPreset?: string;
  textWrap?: "truncate" | "wrap" | "multi";
  descMaxLines?: number;
  shape?: string;
  borderWidth?: number;
  borderStyle?: string;
  elevation?: string;
  uniformHeight?: number;
  iconSize?: number;
  imageFit?: string;
  iconPadShape?: string;
  titleSize?: number;
  titleWeight?: string;
  titleColor?: string;
  coverageSize?: number;
  coverageColor?: string;
  descSize?: number;
  descWeight?: string;
  descColor?: string;
  costSize?: number;
  costColor?: string;
  costBgColor?: string;
  bgColor?: string;
  borderColor?: string;
  textColor?: string;
  accentColor?: string;
  showDescription?: boolean;
  showCoverage?: boolean;
  showCost?: boolean;
  sectionVisibility?: any;
  emptyState?: "hide" | "message";
  emptyMessage?: string;
  hideCoverage?: boolean;
  hideCost?: boolean;
  prefix?: string;
  suffix?: string;
  rowHeight?: number;
  labels?: { premium?: string; roadtax?: string; runner?: string; total?: string; extras?: string };
  opacity?: number;
  style?: CanvasStyle;
  variant_label?: string;
  variant_secondary_label?: string;
  variant_value_text?: string;
  variant_icon_asset_id?: string;
  variant_shape?: string;
  variant_bg_color?: string;
  variant_text_color?: string;
  variant_border_width?: string;
  variant_border_color?: string;
  variant_shadow?: string;
  shapeKind?: "circle" | "triangle" | "diamond";
  groupId?: string;
  groupName?: string;
  locked?: boolean;
  visible?: boolean;
  name?: string;
  parentId?: string;
  order?: number;
};

export const SHAPE_CLIP: Record<string, string> = {
  circle: "border-radius:50%",
  triangle: "clip-path:polygon(50% 0, 100% 100%, 0 100%)",
  diamond: "clip-path:polygon(50% 0, 100% 50%, 50% 100%, 0 50%)",
};

type AssetRecord = { id: string; label: string; url: string; source?: string };

type TemplateConfig = {
  variables?: Array<{ id: string; label: string }>;
  cards?: Record<string, { title?: string }>;
  assets?: Record<string, string>;
  canvas?: { width?: number; height?: number };
};

type BenefitCard = { icon?: string; title?: string; subtitle?: string; lines?: string[]; asset_id?: string };

export const shapeRadii: Record<string, string> = {
  rounded: "12px",
  capsule: "999px",
  square: "0",
};

export const VARIABLE_FALLBACK_MAP: Record<string, string[]> = {
  premium: ["coverage_premium", "basic_premium_vehicle", "basic_premium"],
  coverage_premium: ["premium", "basic_premium_vehicle", "basic_premium"],
  coverage_amount: ["sum_insured", "market_value", "agreed_value"],
  sum_insured: ["coverage_amount", "market_value", "agreed_value"],
  valuation_type: ["valuation_basis", "sum_insured_type", "basis_of_sum_insured"],
  roadtax: ["road_tax_amount", "road_tax"],
  road_tax_amount: ["roadtax", "road_tax"],
  service_fee: ["runner_fee", "runner"],
  runner_fee: ["service_fee", "runner"],
  ncd_percent: ["ncd_percentage", "ncd"],
  ncd_percentage: ["ncd_percent", "ncd"],
  total_amount: ["total_premium_adjusted", "gross_premium", "total_payable"],
  total_premium_adjusted: ["total_amount", "gross_premium", "total_payable"],
  engine_cc: ["vehicle_cc", "engine_capacity", "cubic_capacity"],
  excess_amount: ["policy_excess", "excess", "lebihan", "ekses", "ekses_polisi"],
  compulsory_excess: ["compulsory_excess_amount", "ekses_wajib", "ekses_mandatori"],
  valid_until: ["validity_date", "expiry_date", "validity", "quotation_validity", "valid_to", "expire_on"],
  insurance_company: ["company_name", "insurer_name", "insurance_name"],
  company_name: ["insurance_company", "insurer_name", "insurance_name"],
  quotation_reference: ["quotation_ref", "quote_ref", "reference_no", "quote_no"],
  quotation_ref: ["quotation_reference", "quote_ref", "reference_no", "quote_no"],
  vehicle_no: ["vehicle_plate", "car_plate", "plate_no", "registration_no"],
};

export function resolveVariableValue(
  variableValues: Record<string, string> | undefined,
  variableId: string | undefined
): string | null {
  if (!variableValues || !variableId) return null;
  let raw: string | null = null;
  if (variableId in variableValues && variableValues[variableId] !== undefined && String(variableValues[variableId]).trim() !== "") {
    raw = String(variableValues[variableId]).trim();
  } else {
    for (const alias of VARIABLE_FALLBACK_MAP[variableId] || []) {
      if (alias in variableValues && variableValues[alias] !== undefined && String(variableValues[alias]).trim() !== "") {
        raw = String(variableValues[alias]).trim();
        break;
      }
    }
  }
  if (!raw) {
    if (variableId === "authorized_driver" || variableId === "authorised_driver") {
      const allText = JSON.stringify(variableValues || {}).toLowerCase();
      if (allText.includes("named driver") || allText.includes("named_driver")) {
        return "Named Driver";
      }
      return "All Driver";
    }
    return null;
  }

  if (variableId === "insurance_company" || variableId === "company_name" || variableId === "insurer_name") {
    return getOfficialInsurerName(raw);
  }
  return raw;
}

export function formatVariableValue(value: string | null, prefix = "", suffix = ""): string {
  if (value === null || value === undefined || value === "") return "";
  let formatted = value.trim();

  // If this is a money value without formatting (e.g. "2522.42" or "53000.00"), format with commas
  if ((prefix.trim().toUpperCase() === "RM" || prefix.trim().toUpperCase() === "RM ") && /^\d+(?:\.\d+)?$/.test(formatted)) {
    try {
      const num = Number(formatted);
      if (isFinite(num)) {
        formatted = num.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      }
    } catch {
      // Keep original
    }
  }

  if (prefix) {
    const formattedStr = String(formatted);
    if (prefix.trim().toUpperCase() === "RM" || prefix.trim().toUpperCase() === "RM ") {
      if (!formattedStr.toUpperCase().startsWith("RM")) {
        const space = prefix.endsWith(" ") ? " " : " ";
        formatted = `RM${space}${formattedStr}`;
      }
    } else if (!formattedStr.startsWith(prefix)) {
      formatted = `${prefix}${formattedStr}`;
    }
  }
  if (suffix) {
    const formattedStr = String(formatted);
    if (suffix.trim() === "%") {
      if (!formattedStr.endsWith("%")) {
        formatted = `${formattedStr}${suffix}`;
      }
    } else if (suffix.trim().toLowerCase() === "cc") {
      if (!formattedStr.toLowerCase().endsWith("cc")) {
        formatted = `${formattedStr}${suffix}`;
      }
    } else if (!formattedStr.endsWith(suffix)) {
      formatted = `${formattedStr}${suffix}`;
    }
  }
  return formatted;
}

export const shadowMap: Record<string, string> = {
  none: "none",
  sm: "0 1px 3px rgba(0,0,0,0.12)",
  md: "0 4px 12px rgba(0,0,0,0.15)",
  lg: "0 8px 24px rgba(0,0,0,0.18)",
};

export const SNAP = 8;
export const GUIDE_THRESHOLD = 6;

export function snapValue(value: number, grid: number, otherEdges: number[]) {
  const mod = value % grid;
  const snapped = mod > grid / 2 ? value + (grid - mod) : value - mod;
  const nearest = otherEdges.reduce<{ dist: number; value: number } | null>((best, edge) => {
    const dist = Math.abs(edge - value);
    if (dist <= GUIDE_THRESHOLD && (!best || dist < best.dist)) return { dist, value: edge };
    return best;
  }, null);
  if (nearest) return { value: nearest.value, guide: nearest.value };
  return { value: snapped, guide: null };
}

export function computeGuides(
  moving: CanvasElement,
  next: Partial<CanvasElement>,
  elements: CanvasElement[],
  canvasWidth: number,
  canvasHeight: number,
) {
  const rect = { x: next.x ?? moving.x, y: next.y ?? moving.y, w: next.w ?? moving.w, h: next.h ?? moving.h };
  const xEdges = [0, canvasWidth / 2, canvasWidth];
  const yEdges = [0, canvasHeight / 2, canvasHeight];
  const myEdges = [rect.x, rect.x + rect.w / 2, rect.x + rect.w, rect.y, rect.y + rect.h / 2, rect.y + rect.h];
  const guidePositions: { x: number; y: number }[] = [];
  for (const el of elements) {
    if (el.id === moving.id) continue;
    const ex = [el.x, el.x + el.w / 2, el.x + el.w, el.y, el.y + el.h / 2, el.y + el.h];
    for (const a of myEdges.slice(0, 3))
      for (const b of ex.slice(0, 3)) if (Math.abs(a - b) <= GUIDE_THRESHOLD) guidePositions.push({ x: b, y: 0 });
    for (const a of myEdges.slice(3))
      for (const b of ex.slice(3)) if (Math.abs(a - b) <= GUIDE_THRESHOLD) guidePositions.push({ x: 0, y: b });
  }
  for (const e of xEdges) {
    for (const a of [rect.x, rect.x + rect.w / 2, rect.x + rect.w])
      if (Math.abs(a - e) <= GUIDE_THRESHOLD) guidePositions.push({ x: e, y: 0 });
  }
  for (const e of yEdges) {
    for (const a of [rect.y, rect.y + rect.h / 2, rect.y + rect.h])
      if (Math.abs(a - e) <= GUIDE_THRESHOLD) guidePositions.push({ x: 0, y: e });
  }
  return guidePositions;
}

export const SYSTEM_SLOT_DEFAULTS: Record<string, string> = {
  risklocker_logo: "e9685e1f-ac95-410c-a2e9-eccb7ca35d5f",
  bank_logo: "2168eaee-3e56-4903-8c4f-841f01ff2407",
  qr_code: "9ca8e404c89dd905",
  all_driver_icon: "91116a7dc3540d62",
  background: "49e754a6faa949c2",
  duitnow_payment_details: "c3003185-0000-4000-8000-000000000001",
  bank_qr_layout_dark: "c4003185-0000-4000-8000-000000000001",
  bank_qr_layout: "c4003185-0000-4000-8000-000000000001",
};

export function CanvasElementView({
  element,
  selected,
  assets,
  config,
  variableValues,
  readOnly,
  onPointerDown,
  onResizePointerDown,
  onContextMenu,
  onDoubleClick,
  editingText,
  onTextCommit,
  scenarioCount = 8,
  benefitData,
  conceptAssets,
}: {
  element: CanvasElement;
  selected: boolean;
  assets: AssetRecord[];
  config?: TemplateConfig;
  variableValues?: Record<string, string>;
  readOnly: boolean;
  onPointerDown: (event: React.PointerEvent) => void;
  onResizePointerDown?: (event: React.PointerEvent, handle: string) => void;
  onContextMenu?: (event: React.MouseEvent) => void;
  onDoubleClick?: (event: React.MouseEvent) => void;
  editingText?: boolean;
  onTextCommit?: (text: string) => void;
  scenarioCount?: number;
  benefitData?: {
    current_benefits: any[];
    available_addons: any[];
    groups?: Array<{ plan_id: string; plan_key: string; plan_label: string; cards: any[] }>;
    extras?: Array<{ label: string; price?: { amount?: number | string; currency?: string } }>;
    displayPreferences?: {
      defaults: { custom: boolean; coverage: boolean; price: boolean };
      addons: { custom: boolean; coverage: boolean; price: boolean };
    };
    displayOptions?: any;
  };
  conceptAssets?: Record<string, string>;
}) {
  if (element.type === "layer-group" || element.visible === false) return null;
  const eid = element.id || "";
  const isImageOrLogo =
    element.type === "image" ||
    ["pay_holder", "text_ltaa394", "pay_bank_sub", "text_ul2w5ka", "pay_bank_logo", "bank_logo", "risklocker_logo", "qr_code", "rc_b_qr_code", "payment_account_details_img", "rc_b_duitnow_img", "duitnow_img", "duitnow_card"].includes(eid);

  const slot =
    element.assetSlot ||
    ((element.componentRole === "risklocker_logo" || eid === "risklocker_logo") || (element.componentRole === "pay_holder" || eid === "pay_holder") || (element.componentRole === "text_ltaa394" || eid === "text_ltaa394")
      ? "risklocker_logo"
      : (element.componentRole === "bank_logo" || eid === "bank_logo") || (element.componentRole === "pay_bank_logo" || eid === "pay_bank_logo") || (element.componentRole === "pay_bank_sub" || eid === "pay_bank_sub") || (element.componentRole === "text_ul2w5ka" || eid === "text_ul2w5ka")
        ? "bank_logo"
        : (element.componentRole === "qr_code" || eid === "qr_code") || (element.componentRole === "rc_b_qr_code" || eid === "rc_b_qr_code")
          ? "qr_code"
          : (element.componentRole === "payment_account_details_img" || eid === "payment_account_details_img") || (element.componentRole === "rc_b_duitnow_img" || eid === "rc_b_duitnow_img") || (element.componentRole === "duitnow_img" || eid === "duitnow_img") || (element.componentRole === "duitnow_card" || eid === "duitnow_card")
            ? "duitnow_payment_details"
            : (element.componentRole === "driver_icon" || eid === "driver_icon")
              ? "all_driver_icon"
              : "");

  let assetId = element.assetId || (slot ? config?.assets?.[slot] : "");
  if ((!assetId || assetId === "None") && slot && SYSTEM_SLOT_DEFAULTS[slot]) {
    assetId = SYSTEM_SLOT_DEFAULTS[slot];
  }
  if (!assetId || assetId === "None") {
    if (slot && SYSTEM_SLOT_DEFAULTS[slot]) {
      assetId = SYSTEM_SLOT_DEFAULTS[slot];
    } else if (SYSTEM_SLOT_DEFAULTS[eid]) {
      assetId = SYSTEM_SLOT_DEFAULTS[eid];
    } else if ((element.componentRole === "pay_holder" || eid === "pay_holder") || (element.componentRole === "text_ltaa394" || eid === "text_ltaa394")) {
      assetId = SYSTEM_SLOT_DEFAULTS["risklocker_logo"];
    } else if ((element.componentRole === "pay_bank_logo" || eid === "pay_bank_logo") || (element.componentRole === "pay_bank_sub" || eid === "pay_bank_sub") || (element.componentRole === "text_ul2w5ka" || eid === "text_ul2w5ka")) {
      assetId = SYSTEM_SLOT_DEFAULTS["bank_logo"];
    } else if ((element.componentRole === "qr_code" || eid === "qr_code") || (element.componentRole === "rc_b_qr_code" || eid === "rc_b_qr_code")) {
      assetId = SYSTEM_SLOT_DEFAULTS["qr_code"];
    } else if ((element.componentRole === "payment_account_details_img" || eid === "payment_account_details_img") || (element.componentRole === "rc_b_duitnow_img" || eid === "rc_b_duitnow_img")) {
      assetId = slot === "bank_qr_layout_dark" || slot === "bank_qr_layout"
        ? SYSTEM_SLOT_DEFAULTS["bank_qr_layout_dark"]
        : SYSTEM_SLOT_DEFAULTS["duitnow_payment_details"];
    }
  }
  const asset = assets.find((item) => item.id === assetId);
  let resolvedUrl = asset?.url || (assetId ? (
    typeof assetId === "string" && (assetId.startsWith("http://") || assetId.startsWith("https://") || assetId.startsWith("/") || assetId.startsWith("data:"))
      ? assetId
      : String(assetId).includes("-")
        ? `/business/assets/${assetId}/content?profile=ui`
        : `/template-assets/${assetId}`
  ) : "");
  if (
    slot === "bank_qr_layout_dark" ||
    slot === "bank_qr_layout" ||
    slot === "duitnow_payment_details" ||
    slot === "qr_code" ||
    (element.componentRole === "payment_account_details_img" || eid === "payment_account_details_img") ||
    (element.componentRole === "rc_b_duitnow_img" || eid === "rc_b_duitnow_img") ||
    (element.componentRole === "qr_code" || eid === "qr_code") ||
    (element.componentRole === "rc_b_qr_code" || eid === "rc_b_qr_code") ||
    assetId === "c4003185-0000-4000-8000-000000000001" ||
    assetId === "c3003185-0000-4000-8000-000000000001" ||
    assetId === "9ca8e404c89dd905" ||
    assetId === "c2003185-0000-4000-8000-000000000001"
  ) {
    resolvedUrl = fileUrl("/assets/bank_qr_layout_dark.jpg");
  } else if (!resolvedUrl && slot && SYSTEM_SLOT_DEFAULTS[slot]) {
    const fallbackId = SYSTEM_SLOT_DEFAULTS[slot];
    resolvedUrl = `/business/assets/${fallbackId}/content?profile=ui`;
  }
  const isSpecial = element.type === "special";
  const isLine = element.type === "line";
  const style = element.style || {};
  const isLineDashed = isLine && (style.borderStyle === "dashed" || style.borderStyle === "dotted");
  const dashPx = style.borderStyle === "dotted" ? 2 : 6;
  const common: React.CSSProperties = {
    position: "absolute",
    left: element.x,
    top: element.y,
    width: element.w,
    height: isLine ? Math.max(2, element.h) : element.h,
    zIndex: element.z || 1,
    fontSize: style.fontSize || 14,
    fontWeight: style.fontWeight || "400",
    fontFamily: style.fontFamily || "inherit",
    fontStyle: style.fontStyle || "normal",
    textTransform: (style.textTransform || "none") as React.CSSProperties["textTransform"],
    color:
      isSpecial && element.variant_text_color
        ? element.variant_text_color
        : (style.color || "#111111"),
    textAlign: (style.textAlign || "left") as React.CSSProperties["textAlign"],
    border:
      isLine
        ? undefined
        : isSpecial && element.variant_border_width
          ? `${element.variant_border_width} solid ${element.variant_border_color || "#D8DDE6"}`
          : `${style.borderWidth || 0}px ${style.borderStyle || "solid"} ${style.borderColor || "#111111"}`,
    background:
      isSpecial && element.variant_bg_color
        ? element.variant_bg_color
        : isLineDashed
          ? `repeating-linear-gradient(90deg, ${style.color || "#111111"} 0 ${dashPx}px, transparent ${dashPx}px ${dashPx * 2}px)`
          : (style.background || "transparent"),
    borderRadius:
      element.type === "ellipse" || element.shapeKind === "circle"
        ? "50%"
        : isSpecial && element.variant_shape
          ? (shapeRadii[element.variant_shape] || "12px")
          : style.borderRadius
            ? `${style.borderRadius}px`
            : undefined,
    clipPath:
      element.type === "triangle" || element.shapeKind === "triangle"
        ? "polygon(50% 0, 100% 100%, 0 100%)"
        : element.type === "diamond" || element.shapeKind === "diamond"
          ? "polygon(50% 0, 100% 50%, 50% 100%, 0 50%)"
          : undefined,
    boxShadow:
      isSpecial && element.variant_shadow
        ? (shadowMap[element.variant_shadow] || "none")
        : (style.boxShadow || "none"),
    letterSpacing: style.letterSpacing ? `${style.letterSpacing}px` : undefined,
    lineHeight: style.lineHeight,
    transform: style.rotation ? `rotate(${style.rotation}deg)` : undefined,
    opacity: element.opacity ?? 1,
    overflow: element.type === "premium-info-block" || element.type === "benefit-grid" ? "visible" : "hidden",
    whiteSpace: (style.whiteSpace as any) || "pre-wrap",
    display: isSpecial ? "flex" : undefined,
    flexDirection: isSpecial ? "column" : undefined,
    alignItems: isSpecial ? "center" : undefined,
    justifyContent: isSpecial ? "center" : undefined,
    gap: isSpecial ? "6px" : undefined,
    padding: isSpecial ? "8px" : style.padding ? `${style.padding}px` : undefined,
  };
  const handles = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];
  const scenarioLayout = packFixedGrid(scenarioCount, element.w, element.h, element.packing);
  const density = {
    comfortable: { padding: 7, gap: 6,  icon: 24, label: 11,   value: 10,  desc: 8.5 },
    normal:      { padding: 5, gap: 5,  icon: 22, label: 10.5, value: 9.5, desc: 8   },
    compact:     { padding: 4, gap: 4.5, icon: 20, label: 10,   value: 9,   desc: 7.8 },
  }[element.textDensity || "compact"] || { padding: 4, gap: 4.5, icon: 20, label: 10, value: 9, desc: 7.8 };
  return (
    <div
      className={
        selected
          ? "outline outline-2 outline-[var(--rl-red)]"
          : "outline outline-1 outline-transparent hover:outline-[var(--rl-border)]"
      }
      data-bg={element.type === "image" && element.assetSlot === "background" ? "1" : undefined}
      data-element-id={element.id}
      style={common}
      onPointerDown={onPointerDown}
      onDoubleClick={onDoubleClick}
      onContextMenu={onContextMenu}
      onClick={(event) => event.stopPropagation()}
      role={readOnly ? undefined : "button"}
      tabIndex={readOnly ? undefined : 0}
      aria-label={readOnly ? undefined : element.name || `${element.type} layer`}
    >
      {isImageOrLogo ? (
        resolvedUrl ? (
          <img className={`h-full w-full object-contain ${(element.componentRole === "risklocker_logo" || eid === "risklocker_logo") || slot === "risklocker_logo" ? "object-left" : ""}`} src={fileUrl(resolvedUrl)} alt="" />
        ) : slot ? (
          <div className="flex h-full w-full items-center justify-center rounded border border-dashed border-gray-200 bg-gray-50/60 p-1 text-center font-bold text-gray-500 text-[10px]">
            {slot === "risklocker_logo" ? (
              <img className="h-full w-full object-contain object-left" src={fileUrl("/business/assets/e9685e1f-ac95-410c-a2e9-eccb7ca35d5f/content?profile=ui")} alt="Risklocker" />
            ) : slot === "bank_logo" ? (
              <img className="h-full w-full object-contain" src={fileUrl("/business/assets/2168eaee-3e56-4903-8c4f-841f01ff2407/content?profile=ui")} alt="Hong Leong Bank" />
            ) : slot === "duitnow_payment_details" || slot === "bank_qr_layout_dark" || slot === "bank_qr_layout" || slot === "qr_code" ? (
              <img className="h-full w-full object-contain" src={fileUrl("/assets/bank_qr_layout_dark.jpg")} alt="Bank QR Details" />
            ) : slot === "insurer_logo" ? (
              <span className="text-slate-800 font-bold text-[11px]">{getOfficialInsurerName(variableValues?.insurance_company || variableValues?.insurance_name)}</span>
            ) : (
              slot
            )}
          </div>
        ) : null
      ) : null}
      {element.type === "text" && !isImageOrLogo && editingText && !readOnly ? (
        <EditableText
          initial={element.text || ""}
          onCommit={(text) => onTextCommit?.(text)}
        />
      ) : element.type === "text" && !isImageOrLogo ? (
        (() => {
          let text = element.text || "";
          if ((element.componentRole === "lbl_engine_cc" || element.id === "lbl_engine_cc") || text.includes("Vehicle CC / 引擎容量") || (text.includes("Engine Capacity") && !text.includes("发动机排量"))) {
            text = "Engine Capacity / 发动机排量";
          }
          if ((element.componentRole === "specials_title" || element.id === "specials_title") || text.includes("Featured Standard Benefits") || text.includes("Featured standard") || text.includes("Our Specials")) {
            const shortName = getInsurerShortName(variableValues?.insurance_company || variableValues?.insurance_name || "QBE");
            text = `${shortName} Free Added Coverage`;
          }
          if ((element.componentRole === "extras_title" || element.id === "extras_title") || text.includes("Purchased Add-Ons & Extras") || text.includes("Purchased Addons and Extras")) {
            text = "Included Optional Add-On";
          }
          if ((element.componentRole === "addons_title" || element.id === "addons_title") || text.includes("You May Add On")) {
            text = "Recommended Add-On Upgrades :";
          }
          if (text.includes("{") && variableValues) {
            text = text.replace(/\{([a-zA-Z0-9_-]+)\}/g, (match, varName) => {
              const val = resolveVariableValue(variableValues, varName);
              return val !== null ? val : (varName === "valid_until" ? "30 Days" : match);
            });
          }
          return text;
        })()
      ) : null}
      {element.type === "variable" ? (
        (() => {
          let raw = resolveVariableValue(variableValues, element.variableId);
          if (raw === null && (element.variableId === "excess_amount" || element.variableId === "excess" || element.variableId === "compulsory_excess")) {
            raw = "0.00";
          }
          if (raw === null && (element.variableId === "authorized_driver" || element.variableId === "authorised_driver")) {
            raw = "All Driver";
          }
          if (element.variableId === "engine_cc" && raw !== null) {
            const vType = String(variableValues?.vehicle_type || "").toUpperCase();
            const cModel = String(variableValues?.car_model || variableValues?.vehicle_model || "").toUpperCase();
            const cBrand = String(variableValues?.car_brand || "").toUpperCase();
            const rawStr = String(raw).trim();
            const isEV = vType.includes("EV") || /\b(BYD|SEAL|ATTO|DOLPHIN|TESLA|MODEL 3|MODEL Y|ORA|GOOD CAT|NETA|IONIQ|EV6|TAYCAN|EQA|EQB|EQC|EQE|EQS|IX3|IX|E-TRON|ZEEKR|XPENG|LUMEN|BLUESHARK)\b/i.test(`${cBrand} ${cModel}`) || /\b(?:kw|kilowatt|watt|w)\b/i.test(rawStr);
            const cleanNum = rawStr.replace(/\s*(?:cc|kw|kilowatt|watt|w)\b/gi, "").trim();
            const num = parseFloat(cleanNum);
            let displayValue = cleanNum;
            if (!isNaN(num) && num > 0) {
              if (isEV) {
                const kw = num >= 1000 ? num / 1000 : num;
                displayValue = `${Number.isInteger(kw) ? kw : kw.toFixed(1)} kW`;
              } else {
                displayValue = `${Number.isInteger(num) ? num : num.toFixed(1)} cc`;
              }
            } else {
              displayValue = isEV ? `${cleanNum} kW` : `${cleanNum} cc`;
            }
            return (
              <span className="text-[var(--rl-red)]">
                {displayValue}
              </span>
            );
          }
          if (((element.componentRole === "ref_val" || eid === "ref_val") || (element.componentRole === "vehicle_no_val" || eid === "vehicle_no_val") || (element.componentRole === "header_insurer_name" || eid === "header_insurer_name")) && element.style?.textAlign === "right") {
            const prefix = element.prefix || "";
            const isInsurer = (element.componentRole === "header_insurer_name" || eid === "header_insurer_name");
            let val = raw !== null ? formatVariableValue(raw, "", element.suffix || "") : "";
            if (!val && (element.componentRole === "ref_val" || eid === "ref_val")) val = "RL260000341";
            else if (!val && (element.componentRole === "vehicle_no_val" || eid === "vehicle_no_val")) val = "JXS2820";
            else if (!val && (element.componentRole === "header_insurer_name" || eid === "header_insurer_name")) val = "QBE INSURANCE (MALAYSIA) BERHAD";
            return (
              <div className="w-full h-full flex items-center justify-end text-right overflow-hidden whitespace-nowrap">
                <span className="text-[10px] font-medium text-slate-500 mr-1 shrink-0">{prefix}</span>
                <span className={`text-[10px] font-bold text-red-600 truncate ${isInsurer ? "font-extrabold uppercase" : ""}`}>
                  {val}
                </span>
              </div>
            );
          }
          if (raw !== null) {
            return (
              <span className="text-[var(--rl-red)]">
                {formatVariableValue(raw, element.prefix || "", element.suffix || "")}
              </span>
            );
          }
          return (
            <span className="text-[var(--rl-red)]">
              {element.prefix || ""}{`{${element.variableId || "variable"}}`}{element.suffix || ""}
            </span>
          );
        })()
      ) : null}
      {element.type === "benefit-section" ? (
        <div className="p-1 text-xs font-bold text-[var(--rl-red)]">
          {element.section === "add_ons" ? "Add-on card section" : "Special card section"}
        </div>
      ) : null}
      {element.type === "benefit-card" ? (
        <div className="p-1 text-xs font-bold">
          {config?.cards?.[element.cardId || ""]?.title || "Benefit card"}
        </div>
      ) : null}
      {element.type === "benefit-grid" ? (
        (() => {
          const isAddons = element.gridKind === "available_addons";
          const isExtras = element.gridKind === "extras" || element.gridKind === "purchased_extras";
          const currentCards = benefitData?.current_benefits || [];
          const checkPaid = (b: any) => {
            if (b?.is_extra || b?.badge || b?.cost_status === "paid") return true;
            const p = b?.price ?? b?.optional_price;
            if (p !== null && p !== undefined) {
              if (typeof p === "object") {
                const amt = p.amount ?? p.value;
                const n = typeof amt === "string" ? parseFloat(amt.replace(/,/g, "")) : Number(amt);
                if (Number.isFinite(n) && n > 0) return true;
              } else if (typeof p === "number" && Number.isFinite(p) && p > 0) {
                return true;
              } else if (typeof p === "string") {
                const n = parseFloat(p.replace(/[^0-9.]/g, ""));
                if (Number.isFinite(n) && n > 0) return true;
              }
            }
            return false;
          };
          const items = benefitData
            ? (isAddons
                ? benefitData.available_addons || []
                : isExtras
                  ? currentCards.filter(checkPaid)
                  : ((element as any).excludeExtras || (element as any).extras_mode === "none" || (element as any).extras_mode === "lump_sum")
                    ? currentCards.filter((b: any) => !checkPaid(b))
                    : currentCards)
            : [];
          const groups = !isAddons && benefitData?.groups?.length ? benefitData.groups : [];
          const groupById = new Map(groups.map((g) => [String(g.plan_id), g]));
          const orderedItems = (groups.length
            ? [
              ...items.filter((item) => !item?.group_id || !groupById.has(String(item.group_id))),
              ...groups.flatMap((g) => items.filter((item) => String(item?.group_id || "") === String(g.plan_id))),
            ]
            : items).filter((b: any) => !b?.label || !/own damage|third\s?-?\s?party bodily|third\s?-?\s?party property/i.test(b.label));
          const dispOpts = (benefitData?.displayOptions && Object.keys(benefitData.displayOptions).length > 0)
            ? benefitData.displayOptions
            : ((config as any)?.display_options || {});
          const isGlobalEnabled = dispOpts?.enabled !== false;

          const getVis = (item: any, isAddonCard: boolean, key: string, defaultVal = true) => {
            const dispOvr = item?.display_overrides;
            if (dispOvr) {
              if (dispOvr.enabled) {
                if (key in dispOvr) {
                  return Boolean(dispOvr[key]);
                }
                if (["showGroup", "showAsset", "showTitle", "showCoverage", "showCost", "showDescription", "isVisible"].includes(key)) {
                  return true;
                }
              }
              if (dispOvr[key] === false) {
                return false;
              }
            }
            if ((element as any).sectionVisibility) {
              const secKey = isAddons
                ? "optionalAddons"
                : isAddonCard
                  ? "addedAddons"
                  : "default";
              const secVis = (element as any).sectionVisibility[secKey];
              if (secVis) {
                if (key === "showGroup" && "showTitle" in secVis) return Boolean(secVis.showTitle);
                if (key === "showAsset" && "showAsset" in secVis) return Boolean(secVis.showAsset);
                if (key === "showCoverage" && "showCoverage" in secVis) return Boolean(secVis.showCoverage);
                if (key === "showDescription" && "showDescription" in secVis) return Boolean(secVis.showDescription);
                if (key === "showCost" && "showCost" in secVis) return Boolean(secVis.showCost);
                if (key in secVis) return Boolean(secVis[key]);
              }
            }
            if (isGlobalEnabled && dispOpts) {
              const cat = isAddonCard ? "addon" : "default";
              const catOpts = dispOpts[cat];
              if (catOpts && key in catOpts) {
                return Boolean(catOpts[key]);
              }
              if (key in dispOpts) {
                return Boolean(dispOpts[key]);
              }
            }
            return defaultVal;
          };

          const visibleItems = orderedItems.filter((item: any) => {
            const isAddonCard = Boolean(isAddons || item?.is_addon || item?.price || (item?.cost_status === "paid") || item?.detected_cost);
            return getVis(item, isAddonCard, "isVisible", true);
          });

          const actualCount = benefitData ? visibleItems.length : scenarioCount;
          const actualLayout = packFixedGrid(actualCount, element.w, element.h, element.packing);
          const groupRects = new Map<string, { x1: number; y1: number; x2: number; y2: number }>();
          actualLayout.cards.forEach((card, idx) => {
            const item = visibleItems[idx];
            const groupId = item?.group_id ? String(item.group_id) : "";
            if (!groupById.has(groupId)) return;
            const prev = groupRects.get(groupId);
            groupRects.set(groupId, {
              x1: Math.min(prev?.x1 ?? Infinity, card.x),
              y1: Math.min(prev?.y1 ?? Infinity, card.y),
              x2: Math.max(prev?.x2 ?? -Infinity, card.x + card.width),
              y2: Math.max(prev?.y2 ?? -Infinity, card.y + card.height),
            });
          });

          return (
            <div className={`relative h-full w-full overflow-hidden ${benefitData ? "" : "border border-dashed border-[var(--rl-red)] bg-[var(--rl-red-light)]/20"}`}>
              <div className="hidden">
                <span>Dynamic benefit grid</span>
                <span>{isAddons ? "Available add-ons" : "Current benefits"} · {actualCount}</span>
              </div>
              {Array.from(groupRects.entries()).map(([groupId, rect]) => {
                const group = groupById.get(groupId);
                const pad = 7;
                const x = Math.max(0, rect.x1 - pad);
                const y = Math.max(0, rect.y1 - pad);
                const width = Math.max(0, rect.x2 - rect.x1 + pad * 2);
                const height = Math.max(0, rect.y2 - rect.y1 + pad * 2);
                return (
                  <div
                    key={`group-${groupId}`}
                    className="pointer-events-none absolute z-10 rounded-[10px] border-2 border-[var(--rl-red)] bg-[var(--rl-red)]/5"
                    style={{ left: x, top: y, width, height }}
                  >
                    <span className="absolute left-2 -top-[11px] rounded-[4px] bg-[var(--rl-red)] px-2 py-1 text-[10px] font-extrabold leading-none text-white whitespace-nowrap">
                      {group?.plan_label || "Package plan"}
                    </span>
                  </div>
                );
              })}
              {actualCount === 0 ? (
                element.emptyState === "message"
                  ? <div className="grid h-full place-items-center text-center text-[10px] text-[var(--rl-text-muted)]">{element.emptyMessage || "Empty grid message"}</div>
                  : <div className="grid h-full place-items-center text-[10px] text-[var(--rl-text-muted)]">Hidden when empty</div>
              ) : element.layoutMode === "normal" ? (
                /* Legacy Fixed Grid fallback */
                actualLayout.cards.map((card, idx) => {
                  const b = visibleItems[idx];
                  const label = b ? b.label : `Benefit ${card.index + 1}`;
                  let val = b?.value && !["", "Included standard cover", "Included", "FOC", "As quoted", "Optional"].includes(b.value) && (/\d/.test(b.value) || /unlimited/i.test(b.value)) ? b.value : "";
                  if (val) {
                    if (/towing|breakdown/i.test(label)) {
                      if (/unlimited/i.test(val)) val = "Unlimited";
                      else {
                        const m = val.match(/(\d+)\s*km/i);
                        if (m) val = m[0].toLowerCase();
                      }
                    } else if (/workmanship/i.test(label)) {
                      const m = val.match(/(\d+)[- ]year/i);
                      if (m) val = `${m[1]} years`;
                    } else if (/legal defense|flood|ambulance|belonging|theft|key/i.test(label)) {
                      let m = val.match(/RM\s*[\d,]+/i);
                      if (!m) m = val.match(/[\d,]+/);
                      if (m) val = val.includes("RM") ? m[0] : `RM ${m[0]}`;
                      if (/total loss|theft allowance/i.test(label) && val.includes("%")) {
                         const pctMatch = b?.value?.match(/\d+%/);
                         if (pctMatch) val = pctMatch[0];
                      }
                    }
                  }
                  const desc = b?.description || "";
                  const assetUrl = b
                    ? b.asset_url ||
                      (b.asset_id ? `/business/assets/${b.asset_id}/content?profile=ui` : null) ||
                      (conceptAssets?.[b.concept_key] || conceptAssets?.[b.concept_id] || null) ||
                      (b.label ? conceptAssets?.[b.label.toLowerCase()] || conceptAssets?.[b.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")] || null : null) ||
                      (assets.find((a) => a.id === b.asset_id)?.url || null)
                    : null;
                  const isAddonCard = Boolean(isAddons || b?.is_addon || b?.price || (b?.cost_status === "paid") || b?.detected_cost);
                  const showAsset = getVis(b, isAddonCard, "showAsset", true);
                  const showGroup = getVis(b, isAddonCard, "showGroup", true);
                  const showCoverage = getVis(b, isAddonCard, "showCoverage", true);
                  const showDescription = getVis(b, isAddonCard, "showDescription", true);
                  const showCost = getVis(b, isAddonCard, "showCost", true);
                  let extraMatch = null;
                  if (benefitData?.extras) {
                    extraMatch = benefitData.extras.find((ex: any) =>
                      (b?.concept_id && ex.concept_id === b.concept_id) ||
                      (b?.concept_key && ex.concept_key === b.concept_key) ||
                      (b?.label && ex.label?.toLowerCase() === b.label?.toLowerCase())
                    );
                  }
                  const extractCost = (item: any): number | null => {
                    if (!item) return null;
                    const p = item.price ?? item.optional_price;
                    if (p !== null && p !== undefined) {
                      if (typeof p === "object") {
                        if (p.type === "formula") return null;
                        const amt = p.amount ?? p.value;
                        if (amt !== null && amt !== undefined && amt !== "") {
                          const s = String(amt);
                          if (s.includes("%") || /sum\s*insured|sum\s*covered|tariff/i.test(s)) return null;
                          const n = typeof amt === "string" ? parseFloat(amt.replace(/,/g, "")) : Number(amt);
                          if (Number.isFinite(n) && n > 0) return n;
                        }
                      } else if (typeof p === "number" && Number.isFinite(p) && p > 0) {
                        return p;
                      } else if (typeof p === "string") {
                        if (p.includes("%") || /sum\s*insured|sum\s*covered|tariff/i.test(p)) return null;
                        const n = parseFloat(p.replace(/[^0-9.]/g, ""));
                        if (Number.isFinite(n) && n > 0) return n;
                      }
                    }
                    if (item.detected_cost) {
                      const s = String(item.detected_cost);
                      if (s.includes("%") || /sum\s*insured|sum\s*covered|tariff/i.test(s)) return null;
                      const n = parseFloat(s.replace(/[^0-9.]/g, ""));
                      if (Number.isFinite(n) && n > 0) return n;
                    }
                    return null;
                  };
                  const costNum = extractCost(b) ?? (extraMatch ? extractCost(extraMatch) : null);
                  // Paid extra strictly when it is a paid card AND not inside the Recommended Add-ons section
                  const isPaidExtra = isPaidExtraBenefitCard(b) && !isAddons;
                  // Free Added Coverage (Defaults) and Recommended Add-on Upgrades must NEVER show coverage amount or price badge
                  const costBadge = (isPaidExtra && costNum !== null)
                    ? `Cost : MYR ${costNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                    : null;

                  if (!isPaidExtra) {
                    val = "";
                  } else {
                    const rawLimit = b?.detected_limit || b?.coverage_limit;
                    if (rawLimit && typeof rawLimit === "string" && rawLimit.trim()) {
                      const s = rawLimit.trim();
                      if (/\d/.test(s) || /unlimited/i.test(s)) {
                        val = s.startsWith("RM") ? s : `RM ${s}`;
                      }
                    } else if (costNum !== null && val) {
                      const valNum = parseFloat(String(val).replace(/[^0-9.]/g, ""));
                      if (Number.isFinite(valNum) && Math.abs(valNum - costNum) < 0.01) {
                        val = "";
                      }
                    }
                    if (val && !(/\d/.test(val) || /unlimited/i.test(val))) {
                      val = "";
                    }
                    if (val === "RM 0" || val === "RM 0.00" || val === "0" || val === "0.00") {
                      val = "";
                    }
                  }

                  const isDark = element.benefitPreset === "dark-signature";
                  const customIconSize = (element as any).iconSize ? Number((element as any).iconSize) : 0;
                  const cardIconSize = customIconSize > 0 ? Math.min(60, Math.max(16, customIconSize)) : density.icon;
                  const cardShape = (element as any).shape;
                  const cardRadius = cardShape === "racetrack" ? "999px" : cardShape === "soft" ? "12px" : cardShape === "oval" ? "24px / 14px" : cardShape === "square" ? "0px" : "6px";
                  const cardElevation = (element as any).elevation;
                  const cardShadow = cardElevation === "shadow" ? "0 4px 12px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0,0,0,0.04)" : cardElevation === "lift" ? "0 8px 20px rgba(0, 0, 0, 0.12)" : undefined;
                  const cardBg = (element as any).bgColor;
                  const cardBorderColor = (element as any).borderColor;
                  const cardBorderWidth = (element as any).borderWidth;
                  const cardBorderStyle = (element as any).borderStyle;
                  const cardImageFit = (element as any).imageFit || "contain";
                  const cardIconPad = (element as any).iconPadShape;
                  const iconPadRadius = cardIconPad === "circle" ? "999px" : cardIconPad === "box" ? "6px" : cardIconPad === "none" ? "0px" : "4px";

                  return (
                    <article
                      key={card.index}
                      className="absolute box-border"
                      style={{ left: card.x, top: card.y, width: card.width, height: card.height }}
                    >
                      <div
                        className={`w-full h-full flex flex-col overflow-hidden ${
                          element.cardStyle === "minimal"
                            ? "bg-transparent border border-transparent"
                            : element.cardStyle === "soft"
                              ? "bg-[#f3f0f0] border border-gray-200 shadow-xs"
                              : "border border-[var(--rl-border)] bg-white shadow-xs"
                        }`}
                        style={{
                          padding: density.padding,
                          borderRadius: cardShape ? cardRadius : undefined,
                          boxShadow: cardElevation ? cardShadow : undefined,
                          backgroundColor: cardBg || undefined,
                          borderColor: cardBorderColor || undefined,
                          borderWidth: cardBorderWidth !== undefined ? `${cardBorderWidth}px` : undefined,
                          borderStyle: cardBorderStyle || undefined,
                        }}
                      >
                        {showGroup && (
                          <div
                            className={`font-bold leading-snug shrink-0 ${
                              (element as any).textWrap === "truncate"
                                ? "truncate"
                                : (element as any).textWrap === "wrap"
                                ? "line-clamp-2 leading-tight break-words"
                                : "leading-tight break-words"
                            }`}
                            style={{
                              fontSize: (element as any).titleSize || density.label,
                              marginBottom: 3,
                              color: (element as any).titleColor || (element as any).textColor || undefined,
                              display: (element as any).textWrap === "truncate" ? "block" : "-webkit-box",
                              WebkitLineClamp: (element as any).textWrap === "truncate" ? 1 : ((element as any).textWrap === "wrap" ? 2 : undefined),
                              WebkitBoxOrient: "vertical",
                              overflow: "hidden",
                            }}
                          >
                            {label}
                          </div>
                        )}
                        <div className="flex flex-1 min-h-0 gap-1.5 items-start overflow-hidden">
                          {showAsset && (
                            <div
                              className="shrink-0 overflow-hidden"
                              style={{
                                width: `${cardIconSize}px`,
                                height: `${cardIconSize}px`,
                                borderRadius: iconPadRadius,
                              }}
                            >
                              {assetUrl ? (
                                <img
                                  src={fileUrl(assetUrl)}
                                  alt={label}
                                  className="h-full w-full"
                                  style={{ objectFit: cardImageFit }}
                                  onError={(e) => { (e.currentTarget as HTMLElement).style.display = "none"; }}
                                />
                              ) : (
                                <span
                                  className="grid h-full w-full place-items-center rounded bg-[var(--rl-red-light)] font-black text-[var(--rl-red)]"
                                  style={{ fontSize: density.desc }}
                                >
                                  {label ? label.slice(0, 2).toUpperCase() : `B${card.index + 1}`}
                                </span>
                              )}
                            </div>
                          )}
                          <div className="flex flex-col min-w-0 flex-1 overflow-hidden justify-start">
                            {(() => {
                              const sectionPrefs = isAddonCard ? benefitData?.displayPreferences?.addons : benefitData?.displayPreferences?.defaults;
                              let computedHideCoverage = !showCoverage || element.hideCoverage || false;
                              let computedHideCost = !showCost || element.hideCost || false;
                              
                              if (sectionPrefs) {
                                if (sectionPrefs.custom) {
                                  computedHideCoverage = computedHideCoverage || !!b?.typed_value_override?.hideCoverage || !!b?.typed_value?.hideCoverage;
                                  computedHideCost = computedHideCost || !!b?.typed_value_override?.hideCost || !!b?.typed_value?.hideCost;
                                } else {
                                  computedHideCoverage = computedHideCoverage || !sectionPrefs.coverage;
                                  computedHideCost = computedHideCost || !sectionPrefs.price;
                                }
                              }

                              const customCovSize = (element as any).coverageSize ? Number((element as any).coverageSize) : density.value;
                              const customCovColor = (element as any).coverageColor;
                              const customDescSize = (element as any).descSize ? Number((element as any).descSize) : density.desc;
                              const customDescWeight = (element as any).descWeight;
                              const customDescColor = (element as any).descColor;
                              const customCostSize = (element as any).costSize ? Number((element as any).costSize) : Math.max(8.5, density.desc);
                              const customCostColor = (element as any).costColor;
                              const customCostBg = (element as any).costBgColor;

                              const customDescMaxLines = (element as any).descMaxLines !== undefined ? Number((element as any).descMaxLines) : 3;

                              const hasVal = Boolean(val && !computedHideCoverage);
                              const hasCost = Boolean(costBadge && !computedHideCost);

                              return (
                                <>
                                  {(hasVal || hasCost) && (
                                    <div className="flex items-center justify-between gap-1 min-w-0">
                                      {hasVal ? (
                                        <span
                                          className="font-bold leading-tight text-[var(--rl-text-strong)] truncate"
                                          style={{ fontSize: customCovSize, color: customCovColor || undefined }}
                                        >
                                          {val}
                                        </span>
                                      ) : <span />}
                                      {hasCost && (
                                        <span
                                          className={`inline-block rounded px-1 py-0.5 font-bold whitespace-nowrap leading-tight border text-[8px] ${
                                            customCostBg || customCostColor
                                              ? ""
                                              : isDark
                                                ? "bg-red-950/40 text-red-300 border-red-800/50"
                                                : "bg-red-50 text-red-600 border-red-200"
                                          }`}
                                          style={{
                                            fontSize: customCostSize ? Math.min(customCostSize, 9) : 8.5,
                                            color: customCostColor || undefined,
                                            backgroundColor: customCostBg || undefined,
                                            borderColor: customCostBg || undefined,
                                          }}
                                        >
                                          {costBadge}
                                        </span>
                                      )}
                                    </div>
                                  )}
                                  {desc && showDescription && (
                                    <span
                                      className={`leading-tight mt-0.5 text-[var(--rl-text-muted)] ${
                                        customDescMaxLines === 1 ? "line-clamp-1" :
                                        customDescMaxLines === 2 ? "line-clamp-2" :
                                        customDescMaxLines === 3 ? "line-clamp-3" :
                                        customDescMaxLines === 4 ? "line-clamp-4" :
                                        customDescMaxLines === 5 ? "line-clamp-5" :
                                        customDescMaxLines === 0 ? "" : "line-clamp-3"
                                      }`}
                                      style={{
                                        fontSize: customDescSize,
                                        fontWeight: customDescWeight ? (customDescWeight === "bold" ? 700 : customDescWeight === "semibold" ? 600 : customDescWeight === "medium" ? 500 : 400) : undefined,
                                        color: customDescColor || undefined,
                                        display: customDescMaxLines === 0 ? "block" : "-webkit-box",
                                        WebkitLineClamp: customDescMaxLines === 0 ? undefined : (customDescMaxLines || 3),
                                        WebkitBoxOrient: "vertical",
                                        overflow: "hidden",
                                      }}
                                    >
                                      {desc}
                                    </span>
                                  )}
                                </>
                              );
                            })()}
                          </div>
                        </div>
                      </div>
                    </article>
                  );
                })
              ) : (
                /* EQUAL-HEIGHT GRID SYSTEM */
                (() => {
                  const numCols = element.columns ?? 3;
                  const isDark = element.benefitPreset === "dark-signature";
                  const isMinimal = element.benefitPreset === "compact-minimal" || element.cardStyle === "minimal";
                  const isElevated = element.benefitPreset === "elevated-3d" || element.cardStyle === "soft";
                  const isGridTile = element.benefitPreset === "grid-tile" || element.cardStyle === "outlined";
                  const cardRowH = (element as any).rowHeight || (element as any).targetRowHeight || 0;
                  const customIconSize = (element as any).iconSize ? Number((element as any).iconSize) : 0;
                  const customTitleSize = (element as any).titleSize ? Number((element as any).titleSize) : 0;
                  const minCardNeeded = Math.max(
                    28,
                    customIconSize > 0 ? customIconSize + 18 : 28,
                    customTitleSize > 0 ? customTitleSize + 28 : 28
                  );
                  const effectiveCardRowH = cardRowH > 0
                    ? ((element as any).uniformHeight ? (element as any).uniformHeight : (customIconSize > 24 || customTitleSize > 10 ? Math.max(cardRowH, minCardNeeded) : cardRowH))
                    : 0;

                  return (
                    <div
                      className="grid w-full items-stretch"
                      style={{ 
                        gridTemplateColumns: `repeat(${numCols}, minmax(0, 1fr))`,
                        gridAutoRows: effectiveCardRowH > 0 ? `${effectiveCardRowH}px` : undefined,
                        gap: density.gap 
                      }}
                    >
                      {visibleItems.map((b: any, idx: number) => {
                            const label = b ? b.label : `Benefit ${idx + 1}`;
                            let val = b?.value && !["", "Included standard cover", "Included", "FOC", "As quoted", "Optional"].includes(b.value) && (/\d/.test(b.value) || /unlimited/i.test(b.value)) ? b.value : "";
                            if (val) {
                              if (/towing|breakdown/i.test(label)) {
                                if (/unlimited/i.test(val)) val = "Unlimited";
                                else {
                                  const m = val.match(/(\d+)\s*km/i);
                                  if (m) val = m[0].toLowerCase();
                                }
                              } else if (/workmanship/i.test(label)) {
                                const m = val.match(/(\d+)[- ]year/i);
                                if (m) val = `${m[1]} years`;
                              } else if (/legal defense|flood|ambulance|belonging|theft|key/i.test(label)) {
                                let cleanVal = val.replace(/up to/gi, "").trim();
                                let m = cleanVal.match(/RM\s*[\d,]+/i);
                                if (!m) m = cleanVal.match(/[\d,]+/);
                                if (m) val = cleanVal.includes("RM") ? m[0] : `RM ${m[0]}`;
                                if (/total loss|theft allowance/i.test(label) && val.includes("%")) {
                                   const pctMatch = b?.value?.match(/\d+%/);
                                   if (pctMatch) val = pctMatch[0];
                                }
                              }
                            }
                            const desc = b?.description || "";
                            const assetUrl = b
                              ? b.asset_url ||
                                (b.asset_id ? `/business/assets/${b.asset_id}/content?profile=ui` : null) ||
                                (conceptAssets?.[b.concept_key] || conceptAssets?.[b.concept_id] || null) ||
                                (b.label ? conceptAssets?.[b.label.toLowerCase()] || conceptAssets?.[b.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")] || null : null) ||
                                (assets.find((a) => a.id === b.asset_id)?.url || null)
                              : null;
                            const isAddonCard = Boolean(isAddons || b?.is_addon || b?.price || (b?.cost_status === "paid") || b?.detected_cost);
                            const showAsset = getVis(b, isAddonCard, "showAsset", true);
                            const showGroup = getVis(b, isAddonCard, "showGroup", true);
                            const showCoverage = getVis(b, isAddonCard, "showCoverage", true);
                            const showDescription = getVis(b, isAddonCard, "showDescription", true);
                            const showCost = getVis(b, isAddonCard, "showCost", true);
                            let extraMatch = null;
                            if (benefitData?.extras) {
                              extraMatch = benefitData.extras.find((ex: any) =>
                                (b?.concept_id && ex.concept_id === b.concept_id) ||
                                (b?.concept_key && ex.concept_key === b.concept_key) ||
                                (b?.label && ex.label?.toLowerCase() === b.label?.toLowerCase())
                              );
                            }
                            const extractCost = (item: any): number | null => {
                              if (!item) return null;
                              if (item.typed_value?.hide_price) return null;
                              const p = item.price ?? item.optional_price;
                              if (p !== null && p !== undefined) {
                                if (typeof p === "object") {
                                  if (p.type === "formula") return null;
                                  const amt = p.amount ?? p.value;
                                  if (amt !== null && amt !== undefined && amt !== "") {
                                    const s = String(amt);
                                    if (s.includes("%") || /sum\s*insured|sum\s*covered|tariff/i.test(s)) return null;
                                    const n = typeof amt === "string" ? parseFloat(amt.replace(/,/g, "")) : Number(amt);
                                    if (Number.isFinite(n) && n > 0) return n;
                                  }
                                } else if (typeof p === "number" && Number.isFinite(p) && p > 0) {
                                  return p;
                                } else if (typeof p === "string") {
                                  if (p.includes("%") || /sum\s*insured|sum\s*covered|tariff/i.test(p)) return null;
                                  const n = parseFloat(p.replace(/[^0-9.]/g, ""));
                                  if (Number.isFinite(n) && n > 0) return n;
                                }
                              }
                              if (item.detected_cost) {
                                const s = String(item.detected_cost);
                                if (s.includes("%") || /sum\s*insured|sum\s*covered|tariff/i.test(s)) return null;
                                const n = parseFloat(s.replace(/[^0-9.]/g, ""));
                                if (Number.isFinite(n) && n > 0) return n;
                              }
                              return null;
                            };
                            const costNum = extractCost(b) ?? (extraMatch ? extractCost(extraMatch) : null);
                            // Paid extra strictly when it is a paid card AND not inside the Recommended Add-ons section
                            const isPaidExtra = isPaidExtraBenefitCard(b) && !isAddons;
                            // Free Added Coverage (Defaults) and Recommended Add-on Upgrades must NEVER show coverage amount or price badge
                            const costBadge = (isPaidExtra && costNum !== null)
                              ? `Cost : MYR ${costNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                              : null;

                            if (!isPaidExtra) {
                              val = "";
                            } else {
                              let rawLimit = b?.detected_limit || b?.coverage_limit;
                              if (b?.typed_value?.hide_limit) {
                                rawLimit = null;
                                val = "";
                              }
                              if (rawLimit && typeof rawLimit === "string" && rawLimit.trim()) {
                                const s = rawLimit.trim();
                                if (/\d/.test(s) || /unlimited/i.test(s)) {
                                  val = s.startsWith("RM") ? s : `RM ${s}`;
                                }
                              } else if (costNum !== null && val) {
                                const valNum = parseFloat(String(val).replace(/[^0-9.]/g, ""));
                                if (Number.isFinite(valNum) && Math.abs(valNum - costNum) < 0.01) {
                                  val = "";
                                }
                              }
                              if (val && !(/\d/.test(val) || /unlimited/i.test(val))) {
                                val = "";
                              }
                              if (val === "RM 0" || val === "RM 0.00" || val === "0" || val === "0.00") {
                                val = "";
                              }
                            }

                        const customIconSize = (element as any).iconSize ? Number((element as any).iconSize) : 0;
                        const cardIconSize = customIconSize > 0
                          ? Math.min(60, Math.max(14, customIconSize))
                          : (cardRowH > 0
                            ? (cardRowH < 46 ? 14 : cardRowH < 64 ? 18 : 22)
                            : (isMinimal ? density.icon - 2 : density.icon));
                        const cardPadding = cardRowH > 0
                          ? (cardRowH < 46 ? "2px 4px" : cardRowH < 64 ? "3px 5px" : "4px 6px")
                          : (isMinimal ? "3px 5px" : density.padding);
                        const cardShape = (element as any).shape;
                        const cardRadius = cardShape === "racetrack" ? "999px" : cardShape === "soft" ? "12px" : cardShape === "oval" ? "24px / 14px" : cardShape === "square" ? "0px" : "6px";
                        const cardElevation = (element as any).elevation;
                        const cardShadow = cardElevation === "shadow" ? "0 4px 12px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0,0,0,0.04)" : cardElevation === "lift" ? "0 8px 20px rgba(0, 0, 0, 0.12)" : undefined;
                        const cardBg = (element as any).bgColor;
                        const cardBorderColor = (element as any).borderColor;
                        const cardBorderWidth = (element as any).borderWidth;
                        const cardBorderStyle = (element as any).borderStyle;
                        const cardImageFit = (element as any).imageFit || "contain";
                        const cardIconPad = (element as any).iconPadShape;
                        const iconPadRadius = cardIconPad === "circle" ? "999px" : cardIconPad === "box" ? "6px" : cardIconPad === "none" ? "0px" : (isGridTile ? "999px" : "4px");

                        const customTitleSize = (element as any).titleSize ? Number((element as any).titleSize) : 0;
                        const cardTitleSize = customTitleSize > 0
                          ? (label.length > 28 ? customTitleSize - 1.0 : (label.length > 18 ? customTitleSize - 0.5 : customTitleSize))
                          : (label.length > 28
                            ? 8.5
                            : (label.length > 18
                              ? 9.0
                              : (cardRowH > 0 && cardRowH < 46 ? 9.5 : Math.min(10, density.label))));
                        const cardTitleClamp = (element as any).textWrap === "truncate" ? 1 : 0;

                        return (
                          <article
                            key={`benefit-card-${idx}`}
                            className={`w-full flex flex-col overflow-hidden transition-all ${
                              isDark
                                ? "border border-slate-700 bg-slate-900 shadow-xs"
                                : isMinimal
                                  ? "border border-neutral-400 bg-white/90 shadow-none hover:border-neutral-500"
                                  : isElevated
                                    ? "border border-neutral-400 bg-white shadow-sm hover:shadow"
                                    : isGridTile
                                      ? "border border-neutral-400 bg-white shadow-none"
                                      : "border border-neutral-400 bg-white shadow-xs"
                            }`}
                            style={{
                              height: effectiveCardRowH > 0 ? `${effectiveCardRowH}px` : (cardRowH > 0 ? `${cardRowH}px` : "100%"),
                              maxHeight: effectiveCardRowH > 0 ? `${effectiveCardRowH}px` : (cardRowH > 0 ? `${cardRowH}px` : undefined),
                              padding: cardPadding,
                              borderRadius: cardShape ? cardRadius : "6px",
                              boxShadow: cardElevation ? cardShadow : undefined,
                              backgroundColor: cardBg || undefined,
                              borderColor: cardBorderColor || undefined,
                              borderWidth: cardBorderWidth !== undefined ? `${cardBorderWidth}px` : undefined,
                              borderStyle: cardBorderStyle || undefined,
                              boxSizing: "border-box",
                            }}
                          >
                            {showGroup && (
                              <div
                                className={`font-bold leading-tight ${
                                  cardTitleClamp === 1
                                    ? "truncate"
                                    : "leading-tight break-words"
                                } ${isDark ? "text-white" : "text-[var(--rl-text-strong)]"}`}
                                style={{
                                  fontSize: cardTitleSize,
                                  marginBottom: isMinimal ? 1 : 2,
                                  color: (element as any).titleColor || (element as any).textColor || undefined,
                                  display: "block",
                                }}
                              >
                                {label}
                              </div>
                            )}
                            <div className={`flex items-start ${isMinimal ? "gap-1" : "gap-1.5"}`}>
                              {showAsset && (
                                <div
                                  className="shrink-0 overflow-hidden"
                                  style={{
                                    width: `${cardIconSize}px`,
                                    height: `${cardIconSize}px`,
                                    borderRadius: iconPadRadius,
                                  }}
                                >
                                  {assetUrl ? (
                                    <img
                                      src={fileUrl(assetUrl)}
                                      alt={label}
                                      className="h-full w-full"
                                      style={{ objectFit: cardImageFit }}
                                      onError={(e) => { (e.currentTarget as HTMLElement).style.display = "none"; }}
                                    />
                                  ) : (
                                    <span
                                      className="grid h-full w-full place-items-center rounded bg-[var(--rl-red-light)] font-black text-[var(--rl-red)]"
                                      style={{ fontSize: density.desc }}
                                    >
                                      {label?.[0] || "?"}
                                    </span>
                                  )}
                                </div>
                              )}
                              <div className="flex flex-col min-w-0 flex-1 justify-start">
                                    {(() => {
                                      const sectionPrefs = isAddonCard ? benefitData?.displayPreferences?.addons : benefitData?.displayPreferences?.defaults;
                                      let computedHideCoverage = !showCoverage || element.hideCoverage || false;
                                      let computedHideCost = !showCost || element.hideCost || false;
                                      
                                      if (sectionPrefs) {
                                        if (sectionPrefs.custom) {
                                          computedHideCoverage = computedHideCoverage || !!b?.typed_value_override?.hideCoverage || !!b?.typed_value?.hideCoverage;
                                          computedHideCost = computedHideCost || !!b?.typed_value_override?.hideCost || !!b?.typed_value?.hideCost;
                                        } else {
                                          computedHideCoverage = computedHideCoverage || !sectionPrefs.coverage;
                                          computedHideCost = computedHideCost || !sectionPrefs.price;
                                        }
                                      }

                                      const customCovSize = (element as any).coverageSize ? Number((element as any).coverageSize) : density.value;
                                      const customCovColor = (element as any).coverageColor;
                                      const customDescSize = (element as any).descSize ? Number((element as any).descSize) : density.desc;
                                      const customDescWeight = (element as any).descWeight;
                                      const customDescColor = (element as any).descColor;
                                      const customCostSize = (element as any).costSize ? Number((element as any).costSize) : Math.max(8.5, density.desc);
                                      const customCostColor = (element as any).costColor;
                                      const customCostBg = (element as any).costBgColor;

                                      const hasVal = Boolean(val && !computedHideCoverage);
                                      const hasCost = Boolean(costBadge && !computedHideCost);

                                      return (
                                        <>
                                          {(hasVal || hasCost) && (
                                            <div className="flex items-center justify-between gap-1 min-w-0">
                                              {hasVal ? (
                                                <span
                                                  className={`font-bold leading-tight truncate ${isDark ? "text-white" : "text-[var(--rl-text-strong)]"}`}
                                                  style={{ fontSize: customCovSize, color: customCovColor || undefined }}
                                                >
                                                  {val}
                                                </span>
                                              ) : <span />}
                                              {hasCost && (
                                                <span
                                                  className={`inline-block rounded px-1 py-0.5 font-bold whitespace-nowrap leading-tight border text-[8px] ${
                                                    customCostBg || customCostColor
                                                      ? ""
                                                      : isDark
                                                        ? "bg-red-950/40 text-red-300 border-red-800/50"
                                                        : "bg-red-50 text-red-600 border-red-200"
                                                  }`}
                                                  style={{
                                                    fontSize: customCostSize ? Math.min(customCostSize, 9) : 8.5,
                                                    color: customCostColor || undefined,
                                                    backgroundColor: customCostBg || undefined,
                                                    borderColor: customCostBg || undefined,
                                                  }}
                                                >
                                                  {costBadge}
                                                </span>
                                              )}
                                            </div>
                                          )}
                                          {!isMinimal && desc && showDescription && (cardRowH <= 0 || cardRowH >= 46) && (
                                            <span
                                              className={`leading-tight mt-0.5 ${
                                                (element as any).descMaxLines > 0 ? `line-clamp-${(element as any).descMaxLines}` : ""
                                              } ${isDark ? "text-slate-400" : "text-[var(--rl-text-muted)]"}`}
                                              style={{ 
                                                fontSize: customDescSize,
                                                fontWeight: customDescWeight ? (customDescWeight === "bold" ? 700 : customDescWeight === "semibold" ? 600 : customDescWeight === "medium" ? 500 : 400) : undefined,
                                                color: customDescColor || undefined,
                                                display: (element as any).descMaxLines > 0 ? "-webkit-box" : "block",
                                                WebkitLineClamp: (element as any).descMaxLines > 0 ? (element as any).descMaxLines : undefined,
                                                WebkitBoxOrient: "vertical",
                                                overflow: "hidden",
                                              }}
                                            >
                                              {desc}
                                            </span>
                                          )}
                                        </>
                                      );
                                    })()}
                                  </div>
                                </div>
                              </article>
                            );
                          })}
                    </div>
                  );
                })()
              )}
            </div>
          );
        })()
      ) : null}
      {element.type === "premium-info-block" ? (
        (() => {
          const extras = benefitData?.extras || [];
          const extrasMode = String((element as any).extras_mode || (element as any).extrasMode || "itemized").toLowerCase();
          const fmtMoney = (price?: { amount?: number | string; currency?: string; value?: number | string }) => {
            const amount = price?.amount ?? price?.value;
            if (amount === undefined || amount === null || amount === "") return "";
            const number = typeof amount === "string" ? Number(amount.replace(/,/g, "")) : Number(amount);
            return `RM ${isFinite(number) ? number.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : ""}`.trim();
          };
          const labels = element.labels || {};
          const rows: Array<{ kind: string; label: string; limit?: string; value: string }> = [];
          if (extrasMode === "itemized" && extras.length > 0) {
            rows.push({ kind: "extras_header", label: labels.extras || "Extras / 附加项目", value: "" });
            const displayExtras = extras.slice(0, 3);
            const overflowExtras = extras.slice(3);
            displayExtras.forEach((extra) => {
              const dispOvr = (extra as any)?.display_overrides;
              const showCov = (extra as any)?.show_coverage !== false &&
                !(dispOvr?.enabled && dispOvr?.showCoverage === false) &&
                !(dispOvr?.showCoverage === false);
              const rawLimit = showCov ? ((extra as any)?.coverage_limit || ((extra as any)?.typed_value_override?.value ? String((extra as any)?.typed_value_override?.value) : "")) : "";
              let limitLabel = "";
              const isPlan = /\b(plan|tier|level|package|option)\s*\d+\b/i.test(String(extra?.label || "") + " " + String(rawLimit));
              if (rawLimit && !isPlan) {
                const clean = String(rawLimit).replace(/[()]/g, "").replace(/^RM\s*/i, "").trim();
                const num = parseFloat(clean.replace(/,/g, ""));
                if (Number.isFinite(num) && num >= 100) {
                  limitLabel = ` (RM ${num.toLocaleString("en-MY")})`;
                } else if (clean && !/^(included|foc|none|n\/a)$/i.test(clean) && /^RM\s*[\d,.]+/i.test(clean)) {
                  limitLabel = ` (${clean.startsWith("RM") ? clean : `RM ${clean}`})`;
                }
              }
              let extraLabel = String(extra?.label || "");
              if (!showCov) {
                extraLabel = extraLabel.replace(/\s*\(RM\s*[\d,.]+\)/gi, "").trim();
              } else {
                extraLabel = extraLabel.replace(/(\bplan\s*\d+)\s*\(RM\s*[\d,.]+\)/gi, "$1").trim();
              }
              rows.push({
                kind: "extra",
                label: extraLabel + limitLabel,
                value: fmtMoney(extra?.price),
              });
            });
            if (overflowExtras.length > 0) {
              let overflowSum = 0;
              overflowExtras.forEach((extra: any) => {
                const rawPrice = extra?.price;
                const amt = rawPrice?.amount ?? rawPrice?.value ?? rawPrice;
                if (amt !== undefined && amt !== null && amt !== "") {
                  const num = typeof amt === "string" ? Number(amt.replace(/[^0-9.]/g, "")) : Number(amt);
                  if (Number.isFinite(num)) {
                    overflowSum += num;
                  }
                }
              });
              rows.push({
                kind: "extra",
                label: `+ ${overflowExtras.length} more...`,
                value: overflowSum > 0 ? `RM ${overflowSum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "",
              });
            }
          }
          const premium = variableValues?.premium || "";
          let roadtax = variableValues?.roadtax || "";
          if (!roadtax || roadtax === "0" || roadtax === "0.00") {
            const ccStr = variableValues?.engine_cc || "";
            const cleanCC = ccStr ? parseFloat(String(ccStr).replace(/[^0-9.]/g, "")) : 0;
            if (cleanCC > 0) {
              const carModel = String(variableValues?.car_model || variableValues?.vehicle_model || "").toUpperCase();
              const custName = String(variableValues?.customer_name || variableValues?.insured_name || "").toUpperCase();
              const vType = String(variableValues?.vehicle_type || "").toUpperCase();
              const cType = String(variableValues?.client_type || "").toUpperCase();

              const isEVMotorcycle = vType.includes("EVMOTOR") || (vType.includes("EV") && (vType.includes("BIKE") || vType.includes("MOTOR")));
              const isEVNonSaloon = vType.includes("EVNONSALOON") || (vType.includes("EV") && (vType.includes("SUV") || vType.includes("MPV") || vType.includes("NON")));
              const isEVSaloon = vType.includes("EVSALOON") || (vType.includes("EV") && !isEVMotorcycle && !isEVNonSaloon);

              if (isEVMotorcycle || isEVNonSaloon || isEVSaloon) {
                const kw = cleanCC >= 1000 ? cleanCC / 1000 : cleanCC;
                if (isEVMotorcycle) {
                  if (kw <= 7.5) roadtax = "2.00";
                  else if (kw <= 10.0) roadtax = "9.00";
                  else if (kw <= 12.5) roadtax = "12.00";
                  else if (kw <= 25.0) roadtax = "30.00";
                  else if (kw <= 40.0) roadtax = "40.00";
                  else roadtax = "42.00";
                } else {
                  // Electric Passenger Cars (Saloon & Non-Saloon share official 2026 JPJ power bands)
                  let rate = 20;
                  if (kw <= 50.0) rate = 20;
                  else if (kw <= 100.0) rate = 20 + Math.ceil((kw - 50.0) / 10.0) * 10;
                  else if (kw <= 210.0) rate = 80 + (Math.ceil((kw - 100.0) / 10.0) - 1) * 20;
                  else if (kw <= 310.0) rate = 305 + (Math.ceil((kw - 210.0) / 10.0) - 1) * 30;
                  else if (kw <= 410.0) rate = 615 + (Math.ceil((kw - 310.0) / 10.0) - 1) * 50;
                  else if (kw <= 510.0) rate = 1140 + (Math.ceil((kw - 410.0) / 10.0) - 1) * 100;
                  else if (kw <= 610.0) rate = 2165 + (Math.ceil((kw - 510.0) / 10.0) - 1) * 150;
                  else if (kw <= 710.0) rate = 3695 + (Math.ceil((kw - 610.0) / 10.0) - 1) * 200;
                  else if (kw <= 810.0) rate = 5745 + (Math.ceil((kw - 710.0) / 10.0) - 1) * 250;
                  else if (kw <= 910.0) rate = 8295 + (Math.ceil((kw - 810.0) / 10.0) - 1) * 300;
                  else if (kw <= 1010.0) rate = 11345 + (Math.ceil((kw - 910.0) / 10.0) - 1) * 350;
                  else rate = 14895 + (Math.ceil((kw - 1010.0) / 10.0) - 1) * 400;
                  roadtax = rate.toFixed(2);
                }
              } else {
                const parsedCC = cleanCC <= 7000 ? Math.round(cleanCC) : 0;
                if (parsedCC > 0) {
                  const isNonSaloon = vType.includes("NONSALOON") || /(RANGER|HILUX|TRITON|D-MAX|NAVARA|BT-50|COLORADO|CR-V|HR-V|BR-V|X70|X50|X90|ARUZ|FORTUNER|CX-3|CX-5|CX-8|CX-9|SPORTAGE|TUCSON|SANTA FE|HARRIER|CROSS|RUSH|PAJERO|OUTLANDER|MU-X|EVEREST|TIGUAN|MACAN|CAYENNE|DEFENDER|DISCOVERY|EVOQUE|GLC|GLE|X1|X3|X4|X5|X6|XC40|XC60|XC90|ALZA|INNOVA|EXORA|VELLFIRE|ALPHARD|SERENA|ESTIMA|AVANZA|VELOZ|HIACE|URVAN|VAN|LORRY|TRUCK|MPV|SUV|4X4|4WD|PICKUP)/i.test(carModel);
                  const isCompany = cType.includes("COMPANY") || cType.includes("CORP") || vType.includes("COMPANY") || /(SDN\s*BHD|BHD|ENTERPRISE|TRADING|LTD|LLC|PLT|COMPANY|ENT\.|CORP|HOLDINGS|CO\.)/i.test(custName);

                  if (isNonSaloon) {
                    if (parsedCC <= 1000) roadtax = "20.00";
                    else if (parsedCC <= 1200) roadtax = "85.00";
                    else if (parsedCC <= 1400) roadtax = "100.00";
                    else if (parsedCC <= 1600) roadtax = "120.00";
                    else if (parsedCC <= 1800) roadtax = (300 + (parsedCC - 1600) * 0.30).toFixed(2);
                    else if (parsedCC <= 2000) roadtax = (360 + (parsedCC - 1800) * 0.40).toFixed(2);
                    else if (parsedCC <= 2500) roadtax = (440 + (parsedCC - 2000) * 0.80).toFixed(2);
                    else if (parsedCC <= 3000) roadtax = (840 + (parsedCC - 2500) * 1.60).toFixed(2);
                    else roadtax = (1640 + (parsedCC - 3000) * 1.60).toFixed(2);
                  } else if (isCompany) {
                    if (parsedCC <= 1000) roadtax = "20.00";
                    else if (parsedCC <= 1200) roadtax = "110.00";
                    else if (parsedCC <= 1400) roadtax = "140.00";
                    else if (parsedCC <= 1600) roadtax = "180.00";
                    else if (parsedCC <= 1800) roadtax = (400 + (parsedCC - 1600) * 0.80).toFixed(2);
                    else if (parsedCC <= 2000) roadtax = (560 + (parsedCC - 1800) * 1.00).toFixed(2);
                    else if (parsedCC <= 2500) roadtax = (760 + (parsedCC - 2000) * 3.00).toFixed(2);
                    else if (parsedCC <= 3000) roadtax = (2260 + (parsedCC - 2500) * 7.50).toFixed(2);
                    else roadtax = (6010 + (parsedCC - 3000) * 13.50).toFixed(2);
                  } else {
                    if (parsedCC <= 1000) roadtax = "20.00";
                    else if (parsedCC <= 1200) roadtax = "55.00";
                    else if (parsedCC <= 1400) roadtax = "70.00";
                    else if (parsedCC <= 1600) roadtax = "90.00";
                    else if (parsedCC <= 1800) roadtax = (200 + (parsedCC - 1600) * 0.40).toFixed(2);
                    else if (parsedCC <= 2000) roadtax = (280 + (parsedCC - 1800) * 0.50).toFixed(2);
                    else if (parsedCC <= 2500) roadtax = (380 + (parsedCC - 2000) * 1.00).toFixed(2);
                    else if (parsedCC <= 3000) roadtax = (840 + (parsedCC - 2500) * 2.50).toFixed(2);
                    else roadtax = (2130 + (parsedCC - 3000) * 4.50).toFixed(2);
                  }
                }
              }
            }
          }
          const runner = variableValues?.service_fee || "";

          const dispOpts = (benefitData?.displayOptions && Object.keys(benefitData.displayOptions).length > 0)
            ? benefitData.displayOptions
            : ((config as any)?.display_options || {});
          const shouldRoundTotal = dispOpts?.round_total !== false;

          const pNum = parseFloat(String(premium).replace(/[^0-9.]/g, "")) || 0;
          const rtNum = parseFloat(String(roadtax).replace(/[^0-9.]/g, "")) || 0;
          const sfNum = parseFloat(String(runner).replace(/[^0-9.]/g, "")) || 0;
          const extrasTotal = extras.reduce((acc, ex) => {
            const price = ex?.price as { amount?: string | number; value?: string | number } | undefined;
            const amt = typeof price === "object" && price !== null ? (price.amount ?? price.value) : price;
            const num = typeof amt === "string" ? parseFloat(amt.replace(/,/g, "")) : (typeof amt === "number" ? amt : 0);
            return acc + (Number.isFinite(num) ? num : 0);
          }, 0);

          let total = "";
          if (pNum > 0) {
            const rawSum = pNum + rtNum + sfNum + extrasTotal;
            const finalSum = shouldRoundTotal ? Math.round(rawSum) : rawSum;
            total = finalSum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          } else {
            const rawTot = variableValues?.total_premium_adjusted || variableValues?.total_amount || "";
            if (rawTot && shouldRoundTotal) {
              const cleanTot = parseFloat(String(rawTot).replace(/[^0-9.]/g, ""));
              if (Number.isFinite(cleanTot)) {
                total = Math.round(cleanTot).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
              } else {
                total = rawTot;
              }
            } else {
              total = rawTot;
            }
          }
          const combinedRoadtaxVal = rtNum + sfNum;
          const displayRoadtax = combinedRoadtaxVal > 0 ? combinedRoadtaxVal.toFixed(2) : (roadtax || "");

          if (extrasMode === "lump_sum" && extrasTotal > 0) {
            rows.push({
              kind: "extra_lump",
              label: labels.extras || "Extras / 附加项目",
              value: `RM ${extrasTotal.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
            });
          }

          const isV4 = Boolean(
            (element as any).v4_mode ||
            (element as any).isV4 ||
            (config as any)?.v4_mode ||
            (config as any)?.template_name?.toLowerCase?.()?.includes("v4") ||
            (config as any)?.name?.toLowerCase?.()?.includes("v4") ||
            (labels as any)?.v4_mode
          );

          let displayPremium = premium ? `RM ${premium}` : "";
          if (isV4) {
            const cleanTotalNum = parseFloat(String(total || "0").replace(/[^0-9.]/g, "")) || 0;
            const v4PremiumVal = Math.max(0, cleanTotalNum - combinedRoadtaxVal);
            displayPremium = v4PremiumVal > 0
              ? `RM ${v4PremiumVal.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
              : (premium ? `RM ${premium}` : "");
          } else if (extrasMode === "none") {
            const totalPremNum = pNum + extrasTotal;
            displayPremium = totalPremNum > 0 ? `RM ${totalPremNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : (premium ? `RM ${premium}` : "");
          }

          rows.push({ kind: "premium", label: labels.premium || "Coverage Premium / 保费", value: displayPremium });
          if (!isV4) {
            rows.push({ kind: "divider", label: "", value: "" });
          }
          rows.push({ kind: "roadtax", label: labels.roadtax || "Roadtax and Runner Fee / 路税及服务费", value: displayRoadtax ? `RM ${displayRoadtax}` : "" });
          if (isV4) {
            rows.push({ kind: "divider", label: "", value: "" });
          }
          rows.push({ kind: "total", label: (labels as any).total_premium || labels.total || "Total Payable / 应付总额", value: total ? `RM ${total}` : "" });
          const rowHeight = Number(element.rowHeight) || 14;
          return (
            <div className="relative w-full h-full flex flex-col justify-start">
              {rows.map((row, index) => {
                if (row.kind === "divider") {
                  return <div key={`divider-${index}`} className="w-full my-0.5" style={{ height: 1, background: "#E2E8F0" }} />;
                }
                if (row.kind === "divider_dark") {
                  return <div key={`divider-${index}`} className="w-full my-1" style={{ height: 1, background: "#111827" }} />;
                }
                const labelStyle =
                  row.kind === "total"
                    ? { fontSize: 10.5, fontWeight: 800, color: "#0F172A" }
                    : row.kind === "extra_lump"
                      ? { fontSize: 9.5, fontWeight: 700, color: "#DC2626" }
                      : row.kind === "extras_header"
                        ? { fontSize: 8.5, fontWeight: 700, color: "#DC2626", textTransform: "uppercase" as const, letterSpacing: "0.5px" }
                        : row.kind === "extra"
                          ? { fontSize: 9, fontWeight: 600, color: "#B91C1C" }
                          : { fontSize: 9, fontWeight: 600, color: "#334155" };
                const valueStyle =
                  row.kind === "total"
                    ? { fontSize: 11.5, fontWeight: 800, color: "#DC2626" }
                    : row.kind === "extra_lump"
                      ? { fontSize: 10, fontWeight: 700, color: isV4 ? "#94A3B8" : "#0F172A" }
                      : row.kind === "extras_header"
                        ? { fontSize: 8.5, fontWeight: 700, color: "#DC2626" }
                        : row.kind === "extra"
                          ? { fontSize: 9.5, fontWeight: 700, color: isV4 ? "#94A3B8" : "#0F172A" }
                          : { fontSize: 9.5, fontWeight: 700, color: "#0F172A" };
                if (row.kind === "extra") {
                  return (
                    <div key={`row-${index}`} className="flex items-center justify-between w-full pl-3" style={{ height: rowHeight }}>
                      <span style={labelStyle} className="truncate flex-1 min-w-0 pr-2">{row.label}</span>
                      <span style={valueStyle} className="whitespace-nowrap text-right">{row.value}</span>
                    </div>
                  );
                }
                return (
                  <div key={`row-${index}`} className="flex items-center justify-between w-full" style={{ height: rowHeight }}>
                    <span style={labelStyle}>{row.label}</span>
                    <span style={valueStyle}>{row.value}</span>
                  </div>
                );
              })}
            </div>
          );
        })()
      ) : null}
      {isSpecial ? (
        <>
          {element.variant_icon_asset_id ? (
            <img
              className="h-10 w-10 flex-shrink-0 object-contain"
              src={fileUrl(`/template-assets/${element.variant_icon_asset_id}`)}
              alt=""
            />
          ) : null}
          <span className="text-center text-xs font-bold leading-tight">{element.variant_label}</span>
          {element.variant_secondary_label ? (
            <span className="text-center text-[10px] leading-tight opacity-70">
              {element.variant_secondary_label}
            </span>
          ) : null}
          {element.variant_value_text ? (
            <span className="text-center text-[11px] font-bold">{element.variant_value_text}</span>
          ) : null}
        </>
      ) : null}
      {selected && !readOnly && onResizePointerDown
        ? handles.map((handle) => {
          const pos = {
            nw: "top-0 left-0",
            n: "top-0 left-1/2 -translate-x-1/2",
            ne: "top-0 right-0",
            e: "top-1/2 right-0 -translate-y-1/2",
            se: "bottom-0 right-0",
            s: "bottom-0 left-1/2 -translate-x-1/2",
            sw: "bottom-0 left-0",
            w: "top-1/2 left-0 -translate-y-1/2",
          }[handle];
          return (
            <button
              type="button"
              key={handle}
              className={`absolute ${pos} h-3 w-3 border border-[var(--rl-red)] bg-white ${handle.includes("n") || handle.includes("s")
                  ? handle.includes("e") || handle.includes("w")
                    ? "cursor-nwse-resize"
                    : "cursor-ns-resize"
                  : "cursor-ew-resize"
                }`}
              aria-label={`Resize ${element.name || element.type} from ${handle}`}
              onPointerDown={(event) => onResizePointerDown(event, handle)}
            />
          );
        })
        : null}
    </div>
  );
}

function EditableText({ initial, onCommit }: { initial: string; onCommit: (text: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const committed = useRef(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.textContent = initial;
    el.focus();
    const range = document.createRange();
    range.selectNodeContents(el);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
  }, []);
  return (
    <div
      ref={ref}
      contentEditable
      suppressContentEditableWarning
      className="h-full w-full cursor-text outline-none"
      onBlur={() => {
        if (committed.current) return;
        committed.current = true;
        onCommit(ref.current?.textContent || "");
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          committed.current = true;
          onCommit(initial);
        }
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          committed.current = true;
          onCommit(ref.current?.textContent || "");
        }
      }}
    />
  );
}

export function isPaidExtraBenefitCard(c: any): boolean {
  if (c?.is_extra || c?.badge || c?.cost_status === "paid") return true;
  const p = c?.price ?? c?.optional_price;
  if (p !== null && p !== undefined) {
    if (typeof p === "object") {
      const amt = p.amount ?? p.value;
      const n = typeof amt === "string" ? parseFloat(amt.replace(/,/g, "")) : Number(amt);
      if (Number.isFinite(n) && n > 0) return true;
    } else if (typeof p === "number" && Number.isFinite(p) && p > 0) {
      return true;
    } else if (typeof p === "string") {
      const n = parseFloat(p.replace(/[^0-9.]/g, ""));
      if (Number.isFinite(n) && n > 0) return true;
    }
  }
  const tv = c?.typed_value;
  if (tv && typeof tv === "object") {
    if (tv.semantic_role === "premium") {
      const n = parseFloat(String(tv.value || "").replace(/[^0-9.]/g, ""));
      if (Number.isFinite(n) && n > 0) return true;
    }
  }
  if (c?.detected_cost) {
    const n = parseFloat(String(c.detected_cost).replace(/[^0-9.]/g, ""));
    if (Number.isFinite(n) && n > 0) return true;
  }
  return false;
}

export function balanceBenefitGridElements(
  elements: CanvasElement[],
  benefitData?: {
    current_benefits?: any[];
    available_addons?: any[];
    extras?: any[];
    groups?: any[];
  },
): CanvasElement[] {
  const extras = benefitData?.extras || [];
  const pibElem = elements.find((e) => (e.componentRole === "premium_info_block" || e.id === "premium_info_block") || e.type === "premium-info-block");
  const extrasMode = String((pibElem as any)?.extras_mode || (pibElem as any)?.extrasMode || "itemized").toLowerCase();
  const pibY = pibElem ? Number(pibElem.y || 276) : 276;
  const totalPibRows = extrasMode === "none" ? 5 : (extrasMode === "lump_sum" ? (extras.length > 0 ? 6 : 5) : (extras.length > 0 ? extras.length + 6 : 5));
  const contentBottom = pibY + (totalPibRows * 14);
  const cardBottom = Math.max(380, contentBottom + 12);
  const covElem = elements.find((e) => (e.componentRole === "cov_table_bg" || e.id === "cov_table_bg"));
  const covTableY = covElem ? Number(covElem.y || 120) : 120;
  const covTableH = cardBottom - covTableY;
  const yTop = cardBottom + 10;
  const driversH = 74;
  const driversY = cardBottom - driversH;
  const qrY = 210;
  const qrH = (driversY - 8) - qrY;
  const qrCenterY = qrY + qrH / 2;
  const qrSize = Math.min(90, Math.max(70, qrH - 16));

  const currentCards = benefitData?.current_benefits || [];
  const currentConceptIds = new Set(
    currentCards.map((c: any) => String(c?.concept_id || "")).filter(Boolean)
  );
  const currentConceptKeys = new Set(
    currentCards.map((c: any) => String(c?.concept_key || "")).filter(Boolean)
  );
  const currentLabels = new Set(
    currentCards.map((c: any) => String(c?.label || "").trim().toLowerCase()).filter(Boolean)
  );
  const addonCards = (benefitData?.available_addons || []).filter((c: any) => {
    if (c?.concept_id && currentConceptIds.has(String(c.concept_id))) return false;
    if (c?.concept_key && currentConceptKeys.has(String(c.concept_key))) return false;
    if (c?.label && currentLabels.has(String(c.label).trim().toLowerCase())) return false;
    return true;
  });

  const isPaidExtra = isPaidExtraBenefitCard;

  // Separate true FOC benefits from purchased extras / priced add-ons
  const extrasCards = currentCards.filter(isPaidExtra);
  const focCards = extrasCards.length > 0
    ? currentCards.filter((c: any) => !isPaidExtra(c))
    : currentCards;

  const grid1 = elements.find((e) => e.type === "benefit-grid" && e.gridKind === "current_benefits");
  const grid2 = elements.find((e) => e.type === "benefit-grid" && e.gridKind === "available_addons");
  if (!grid1 || !grid2) return elements;

  const hdr1Bg = elements.find((e) => (e.componentRole === "specials_header_bg" || e.id === "specials_header_bg"));
  const hdr1Txt = elements.find((e) => (e.componentRole === "specials_header_txt" || e.id === "specials_header_txt"));
  const hdr2Bg = elements.find((e) => (e.componentRole === "addons_header_bg" || e.id === "addons_header_bg"));
  const hdr2Txt = elements.find((e) => (e.componentRole === "addons_header_txt" || e.id === "addons_header_txt"));

  const footerElem = elements.find((e) => (e.componentRole === "footer_terms" || e.id === "footer_terms") || String(e.id || "").startsWith("footer") || String(e.id || "").startsWith("tc_"));
  const footerY = footerElem ? Number(footerElem.y || 1068) : 1068;
  const safeBottom = Math.max(yTop + 160, footerY - 14);
  const availableH = safeBottom - yTop;

  const hdrH = 24;
  const pad = 3;
  const sectionGap = 8;
  const cardGap = 4.5;
  const isMinimal = grid1.benefitPreset === "compact-minimal" || grid1.cardStyle === "minimal";

  const hasExtrasSection = extrasCards.length > 0;

  const items1 = hasExtrasSection ? focCards : currentCards;
  const itemsExt = extrasCards;
  const items2 = addonCards;

  const n1 = items1.length;
  const nExt = hasExtrasSection ? itemsExt.length : 0;
  const n2 = items2.length;
  const totalCards = n1 + nExt + n2;

  const baseCols = Math.max(1, Number(grid1.columns || 3));
  const effectiveCols = baseCols;
  const extrasCols = nExt <= 2 ? Math.min(2, effectiveCols) : effectiveCols;

  const grid2Cols = Number(grid2.columns || 0);
  const autoPackAddons4Col = Boolean((grid2 as any)?.autoFourCol || (grid2 as any)?.adaptiveColumns) && n2 >= 9;
  const addonsCols = autoPackAddons4Col ? 4 : (grid2Cols > 0 ? grid2Cols : effectiveCols);

  const rows1 = n1 > 0 ? Math.ceil(n1 / effectiveCols) : 0;
  const rowsExt = hasExtrasSection && nExt > 0 ? Math.ceil(nExt / extrasCols) : 0;
  const rows2 = n2 > 0 ? Math.ceil(n2 / addonsCols) : 0;

  const activeSections = (rows1 > 0 ? 1 : 0) + (rowsExt > 0 ? 1 : 0) + (rows2 > 0 ? 1 : 0);
  const effectiveSections = Math.max(1, activeSections);
  const totalRows = Math.max(1, rows1 + rowsExt + rows2);

  const totalHeadersH = (effectiveSections * (hdrH + pad)) + (Math.max(0, effectiveSections - 1) * sectionGap);
  const cardsAvailH = Math.max(60, availableH - totalHeadersH);
  const totalRowGaps = (Math.max(0, rows1 - 1) + Math.max(0, rowsExt - 1) + Math.max(0, rows2 - 1)) * cardGap;
  const pureCardsH = Math.max(40, cardsAvailH - totalRowGaps);

  const customIconSz = Number((grid1 as any)?.iconSize || (grid2 as any)?.iconSize || 0);
  const customTitleSz = Number((grid1 as any)?.titleSize || (grid2 as any)?.titleSize || 0);
  const uniformH = Number((grid1 as any)?.uniformHeight || (grid1 as any)?.rowHeight || 0);
  const minCardNeeded = Math.max(28, customIconSz > 0 ? customIconSz + 18 : 28, customTitleSz > 0 ? customTitleSz + 28 : 28);
  const rawRowH = pureCardsH / totalRows;
  let targetRowH = isMinimal ? Math.min(38, Math.max(28, rawRowH)) : Math.min(74, Math.max(46, rawRowH));
  if (uniformH > 0) {
    targetRowH = uniformH;
  } else if (customIconSz > 24 || customTitleSz > 10) {
    targetRowH = Math.max(minCardNeeded, targetRowH);
  }
  targetRowH = Math.round(targetRowH * 100) / 100;

  const h1 = rows1 > 0 ? rows1 * targetRowH + Math.max(0, rows1 - 1) * cardGap : 0;
  const hExt = rowsExt > 0 ? rowsExt * targetRowH + Math.max(0, rowsExt - 1) * cardGap : 0;
  const h2 = rows2 > 0 ? rows2 * targetRowH + Math.max(0, rows2 - 1) * cardGap : 0;

  // Strict magnetic positioning — each section starts strictly after the previous section ends!
  let curY = yTop;

  const yHdr1 = curY;
  const yG1 = yHdr1 + hdrH + pad;
  const bottom1 = yG1 + h1;
  curY = bottom1 + sectionGap;

  let yHdrExt = 0;
  let yGExt = 0;
  let bottomExt = 0;
  if (hasExtrasSection && nExt > 0) {
    yHdrExt = curY;
    yGExt = yHdrExt + hdrH + pad;
    bottomExt = yGExt + hExt;
    curY = bottomExt + sectionGap;
  }

  const yHdr2 = curY;
  const yG2 = yHdr2 + hdrH + pad;

  const adjustCommon = (e: CanvasElement): CanvasElement => {
    if ((e.componentRole === "cov_table_bg" || e.id === "cov_table_bg")) {
      e.h = covTableH;
    } else if ((e.componentRole === "payment_account_details_img" || e.id === "payment_account_details_img") && !elements.some((x) => (x.componentRole === "all_driver_bg" || x.id === "all_driver_bg"))) {
      e.h = cardBottom - Number(e.y || 94);
    } else if ((e.componentRole === "premium_info_block" || e.id === "premium_info_block") || e.type === "premium-info-block") {
      e.h = totalPibRows * 14;
    } else if ((e.componentRole === "rc_container_payment" || e.id === "rc_container_payment")) {
      e.y = 134;
      e.h = 68;
    } else if ((e.componentRole === "rc_b_pay_title" || e.id === "rc_b_pay_title")) {
      e.y = 143;
      e.h = 14;
    } else if ((e.componentRole === "rc_b_pay_details" || e.id === "rc_b_pay_details")) {
      e.x = 517;
      e.y = 160;
      e.w = 150;
      e.h = 28;
    } else if ((e.componentRole === "rc_b_bank_logo" || e.id === "rc_b_bank_logo")) {
      e.x = 672;
      e.y = 160;
      e.w = 72;
      e.h = 28;
    } else if ((e.componentRole === "rc_container_qr" || e.id === "rc_container_qr")) {
      e.y = qrY;
      e.h = qrH;
    } else if ((e.componentRole === "rc_b_qr_code" || e.id === "rc_b_qr_code")) {
      e.x = 516;
      e.y = qrCenterY - qrSize / 2;
      e.w = qrSize;
      e.h = qrSize;
    } else if ((e.componentRole === "rc_b_qr_text" || e.id === "rc_b_qr_text")) {
      const textX = 516 + qrSize + 8;
      e.x = textX;
      e.y = qrCenterY - 27;
      e.w = 746 - textX;
      e.h = 54;
    } else if ((e.componentRole === "rc_container_drivers" || e.id === "rc_container_drivers")) {
      e.y = driversY;
      e.h = driversH;
    } else if ((e.componentRole === "rc_b_driver_title" || e.id === "rc_b_driver_title")) {
      e.y = driversY + 8;
    } else if ((e.componentRole === "rc_b_driver_sub" || e.id === "rc_b_driver_sub")) {
      e.y = driversY + 24;
    } else if ((e.componentRole === "rc_b_driver_divider" || e.id === "rc_b_driver_divider")) {
      e.y = driversY + 42;
    } else if ((e.componentRole === "rc_b_excess_val" || e.id === "rc_b_excess_val")) {
      e.y = driversY + 48;
    }
    return e;
  };

  const adjusted: CanvasElement[] = [];
  for (const elem of elements) {
    const e = adjustCommon({ ...elem });
    if ((e.componentRole === "specials_header_bg" || e.id === "specials_header_bg") && hdr1Bg) {
      e.y = yHdr1;
      e.h = hdrH;
    } else if ((e.componentRole === "specials_header_txt" || e.id === "specials_header_txt") && hdr1Txt) {
      e.y = yHdr1 + 5;
    } else if (e.type === "benefit-grid" && e.gridKind === "current_benefits") {
      e.y = yG1;
      e.h = h1;
      (e as any).rowHeight = targetRowH;
      (e as any).columns = effectiveCols;
      if (hasExtrasSection) {
        (e as any).excludeExtras = true;
      }
      adjusted.push(e);

      if (hasExtrasSection && nExt > 0) {
        // Insert Purchased Extras section magnetically below Section 1
        adjusted.push({
          id: "extras_header_bg",
          type: "rectangle",
          x: grid1.x || 40,
          y: yHdrExt,
          w: grid1.w || 714,
          h: hdrH,
          z: 2,
          style: { background: "#1E293B", borderWidth: 0, borderColor: "transparent", borderRadius: 4 },
        });
        adjusted.push({
          id: "extras_header_txt",
          type: "text",
          text: "Purchased Extras & Add-ons / 已附加特别项目",
          x: (grid1.x || 40) + 12,
          y: yHdrExt + 5,
          w: (grid1.w || 714) - 24,
          h: 16,
          z: 5,
          style: { fontSize: 10.5, fontWeight: "700", color: "#FFFFFF", textAlign: "left" },
        });
        adjusted.push({
          ...grid1,
          id: "extras_grid",
          type: "benefit-grid",
          gridKind: "extras",
          x: grid1.x ?? 40,
          y: yGExt,
          w: grid1.w ?? 714,
          h: hExt,
          z: 4,
          columns: extrasCols,
          rowHeight: targetRowH,
          emptyState: "hide",
        });
      }
      continue;
    } else if ((e.componentRole === "addons_header_bg" || e.id === "addons_header_bg") && hdr2Bg) {
      e.y = yHdr2;
      e.h = hdrH;
    } else if ((e.componentRole === "addons_header_txt" || e.id === "addons_header_txt") && hdr2Txt) {
      e.y = yHdr2 + 5;
    } else if (e.type === "benefit-grid" && e.gridKind === "available_addons") {
      e.y = yG2;
      e.h = h2;
      (e as any).rowHeight = targetRowH;
      (e as any).columns = addonsCols;
    }
    adjusted.push(e);
  }
  return adjusted;
}
