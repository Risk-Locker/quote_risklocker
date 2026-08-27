"use client";

import { useEffect, useRef } from "react";

import { fileUrl } from "@/lib/api";
import { packFixedGrid } from "./grid-layout";

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
  emptyState?: "hide" | "message";
  emptyMessage?: string;
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
  roadtax: ["road_tax_amount", "road_tax"],
  road_tax_amount: ["roadtax", "road_tax"],
  service_fee: ["runner_fee", "runner"],
  runner_fee: ["service_fee", "runner"],
  ncd_percent: ["ncd_percentage", "ncd"],
  ncd_percentage: ["ncd_percent", "ncd"],
  total_amount: ["total_premium_adjusted", "gross_premium", "total_payable"],
  total_premium_adjusted: ["total_amount", "gross_premium", "total_payable"],
  engine_cc: ["vehicle_cc", "engine_capacity", "cubic_capacity"],
  excess_amount: ["policy_excess", "compulsory_excess", "excess", "lebihan", "ekses", "ekses_polisi"],
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
  if (variableId in variableValues && variableValues[variableId] !== undefined && String(variableValues[variableId]).trim() !== "") {
    return String(variableValues[variableId]).trim();
  }
  for (const alias of VARIABLE_FALLBACK_MAP[variableId] || []) {
    if (alias in variableValues && variableValues[alias] !== undefined && String(variableValues[alias]).trim() !== "") {
      return String(variableValues[alias]).trim();
    }
  }
  return null;
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
  };
  conceptAssets?: Record<string, string>;
}) {
  if (element.type === "layer-group" || element.visible === false) return null;
  const assetId = element.assetId || (element.assetSlot ? config?.assets?.[element.assetSlot] : "");
  const asset = assets.find((item) => item.id === assetId);
  const resolvedUrl = asset?.url || (assetId ? (
    typeof assetId === "string" && (assetId.startsWith("http://") || assetId.startsWith("https://") || assetId.startsWith("/") || assetId.startsWith("data:"))
      ? assetId
      : String(assetId).includes("-")
        ? `/business/assets/${assetId}/content?profile=ui`
        : `/template-assets/${assetId}`
  ) : "");
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
    overflow: "hidden",
    whiteSpace: "pre-wrap",
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
    comfortable: { padding: 12, gap: 8,  icon: 56, label: 13, value: 11, desc: 9.5 },
    normal:      { padding: 9,  gap: 6,  icon: 48, label: 12, value: 10, desc: 9   },
    compact:     { padding: 6,  gap: 4,  icon: 36, label: 11, value: 9,  desc: 8   },
  }[element.textDensity || "normal"]!
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
      {element.type === "image" ? (
        resolvedUrl ? (
          <img className="h-full w-full object-contain" src={fileUrl(resolvedUrl)} alt="" />
        ) : element.assetSlot ? (
          <div className="flex h-full w-full items-center justify-center rounded border border-dashed border-gray-200 bg-gray-50/60 p-1 text-center font-bold text-gray-500 text-[10px]">
            {element.assetSlot === "risklocker_logo" ? (
              <span className="text-red-600 font-black tracking-tight text-[11px]">RISKLOCKER</span>
            ) : element.assetSlot === "insurer_logo" ? (
              <span className="text-slate-800 font-bold text-[11px]">{variableValues?.insurance_company || variableValues?.insurance_name || "INSURER"}</span>
            ) : (
              element.assetSlot
            )}
          </div>
        ) : null
      ) : null}
      {element.type === "text" && editingText && !readOnly ? (
        <EditableText
          initial={element.text || ""}
          onCommit={(text) => onTextCommit?.(text)}
        />
      ) : element.type === "text" ? (
        (() => {
          let text = element.text || "";
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
          if (raw === null && (element.variableId === "excess_amount" || element.variableId === "excess")) {
            raw = "0.00";
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
          const items = benefitData
            ? (isAddons
                ? benefitData.available_addons || []
                : isExtras
                  ? currentCards.filter((b: any) => b.price || b.badge || b.cost_status === "paid")
                  : currentCards)
            : [];
          const groups = !isAddons && benefitData?.groups?.length ? benefitData.groups : [];
          const groupById = new Map(groups.map((g) => [String(g.plan_id), g]));
          const orderedItems = groups.length
            ? [
              ...items.filter((item) => !item?.group_id || !groupById.has(String(item.group_id))),
              ...groups.flatMap((g) => items.filter((item) => String(item?.group_id || "") === String(g.plan_id))),
            ]
            : items;
          const actualCount = benefitData ? orderedItems.length : scenarioCount;
          const actualLayout = packFixedGrid(actualCount, element.w, element.h, element.packing);
          const groupRects = new Map<string, { x1: number; y1: number; x2: number; y2: number }>();
          actualLayout.cards.forEach((card, idx) => {
            const item = orderedItems[idx];
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
              ) : (
                element.layoutMode === "masonry" ? (
                  <div
                    style={{
                      columnCount: element.columns ?? 2,
                      columnGap: density.gap,
                      width: "100%",
                      height: "100%",
                      overflow: "hidden",
                    }}
                  >
                    {orderedItems.map((b: any, idx: number) => {
                      const label = b ? b.label : `Benefit ${idx + 1}`;
                      const val = b?.value && !["", "Included standard cover", "Included", "FOC", "As quoted"].includes(b.value) ? b.value : "";
                      const descRaw = b?.description || "";
                      const desc = descRaw.length > 95 ? descRaw.substring(0, 92) + "..." : descRaw;
                      const assetUrl = b
                        ? b.asset_url ||
                          (b.asset_id ? `/business/assets/${b.asset_id}/content?profile=ui` : null) ||
                          (conceptAssets?.[b.concept_key] || conceptAssets?.[b.concept_id] || null) ||
                          null
                        : null;
                      const costBadge = b?.price?.amount
                        ? `Cost : MYR ${Number(b.price.amount).toLocaleString("en-MY", { minimumFractionDigits: 2 })}`
                        : null;
                      return (
                        <div
                          key={idx}
                          className="box-border"
                          style={{ breakInside: "avoid", marginBottom: density.gap }}
                        >
                          <div
                            className={`flex flex-col rounded-[8px] ${
                              b?.is_detected
                                ? "border-2 border-amber-400 bg-amber-50/40"
                                : element.cardStyle === "minimal"
                                  ? "bg-transparent border border-transparent"
                                  : element.cardStyle === "soft"
                                    ? "bg-[#f3f0f0] border border-gray-200 shadow-xs"
                                    : "border border-[var(--rl-border)] bg-white shadow-xs"
                            }`}
                            style={{ padding: density.padding }}
                          >
                            <div
                              className="font-bold leading-snug text-[var(--rl-text-strong)]"
                              style={{ fontSize: density.label, marginBottom: 4 }}
                            >
                              {label}
                            </div>
                            <div className="flex gap-1.5 items-start min-h-0">
                              <div
                                className="shrink-0 overflow-hidden rounded"
                                style={{ width: density.icon, height: density.icon }}
                              >
                                {assetUrl ? (
                                  <img
                                    src={fileUrl(assetUrl)}
                                    alt={label}
                                    className="h-full w-full object-contain"
                                    onError={(e) => { (e.currentTarget as HTMLElement).style.display = "none"; }}
                                  />
                                ) : (
                                  <span
                                    className="grid h-full w-full place-items-center rounded bg-[var(--rl-red-light)] font-black text-[var(--rl-red)]"
                                    style={{ fontSize: density.desc }}
                                  >
                                    {label ? label.slice(0, 2).toUpperCase() : `B${idx + 1}`}
                                  </span>
                                )}
                              </div>
                              <div className="flex flex-col min-w-0 flex-1 overflow-hidden">
                                {val && (
                                  <span
                                    className="font-bold leading-tight text-[var(--rl-red)]"
                                    style={{ fontSize: density.value }}
                                  >
                                    {val}
                                  </span>
                                )}
                                {desc && (
                                  <span
                                    className="leading-snug text-[var(--rl-text-muted)]"
                                    style={{ fontSize: density.desc }}
                                  >
                                    {desc}
                                  </span>
                                )}
                                {costBadge && (
                                  <span
                                    className={`mt-0.5 inline-block self-start font-semibold whitespace-nowrap text-slate-900`}
                                    style={{ fontSize: density.desc }}
                                  >
                                    {costBadge}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  actualLayout.cards.map((card, idx) => {
                    const b = orderedItems[idx];
                    const label = b ? b.label : `Benefit ${card.index + 1}`;
                    const val = b?.value && !["", "Included standard cover", "Included", "FOC", "As quoted"].includes(b.value) ? b.value : "";
                    const descRaw = b?.description || "";
                    const desc = descRaw.length > 95 ? descRaw.substring(0, 92) + "..." : descRaw;
                    const assetUrl = b
                      ? b.asset_url ||
                        (b.asset_id ? `/business/assets/${b.asset_id}/content?profile=ui` : null) ||
                        (conceptAssets?.[b.concept_key] || conceptAssets?.[b.concept_id] || null) ||
                        (b.label ? conceptAssets?.[b.label.toLowerCase()] || conceptAssets?.[b.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")] || null : null) ||
                        (assets.find((a) => a.id === b.asset_id)?.url || null)
                      : null;
                    const price = b?.price?.amount
                      ? `Cost : MYR ${Number(b.price.amount).toLocaleString("en-MY", { minimumFractionDigits: 2 })}`
                      : b?.is_detected && b?.detected_cost
                        ? `Cost : MYR ${String(b.detected_cost).replace(/RM\s*/i, "")}`
                        : null;
                    const costBadge = price || null;

                    return (
                      <article
                        key={card.index}
                        className="absolute box-border"
                        style={{ left: card.x, top: card.y, width: card.width, height: card.height }}
                      >
                        <div
                          className={`w-full h-full flex flex-col rounded-[8px] overflow-hidden ${
                            b?.is_detected
                              ? "border-2 border-amber-400 bg-amber-50/40 shadow-xs ring-1 ring-amber-300/50"
                              : element.cardStyle === "minimal"
                                ? "bg-transparent border border-transparent"
                                : element.cardStyle === "soft"
                                  ? "bg-[#f3f0f0] border border-gray-200 shadow-xs"
                                  : "border border-[var(--rl-border)] bg-white shadow-xs"
                          }`}
                          style={{ padding: density.padding }}
                        >
                          <div
                            className="font-bold leading-snug text-[var(--rl-text-strong)] shrink-0"
                            style={{ fontSize: density.label, marginBottom: 4 }}
                          >
                            {label}
                          </div>
                          <div className="flex flex-1 min-h-0 gap-1.5 items-start overflow-hidden">
                            <div
                              className="shrink-0 overflow-hidden rounded"
                              style={{ width: density.icon, height: density.icon }}
                            >
                              {assetUrl ? (
                                <img
                                  src={fileUrl(assetUrl)}
                                  alt={label}
                                  className="h-full w-full object-contain"
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
                            <div className="flex flex-col min-w-0 flex-1 overflow-hidden justify-start">
                              {val && (
                                <span
                                  className="font-bold leading-tight text-[var(--rl-red)]"
                                  style={{ fontSize: density.value }}
                                >
                                  {val}
                                </span>
                              )}
                              {desc && (
                                <span
                                  className="leading-snug text-[var(--rl-text-muted)]"
                                  style={{ fontSize: density.desc }}
                                >
                                  {desc}
                                </span>
                              )}
                              {costBadge && (
                                <span
                                  className={`mt-0.5 inline-block self-start font-semibold whitespace-nowrap text-slate-900`}
                                  style={{ fontSize: density.desc }}
                                >
                                  {costBadge}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </article>
                    );
                  })
                )
              )}
            </div>
          );
        })()
      ) : null}
      {element.type === "premium-info-block" ? (
        (() => {
          const extras = benefitData?.extras || [];
          const fmtMoney = (price?: { amount?: number | string; currency?: string; value?: number | string }) => {
            const amount = price?.amount ?? price?.value;
            if (amount === undefined || amount === null || amount === "") return "";
            const number = typeof amount === "string" ? Number(amount.replace(/,/g, "")) : Number(amount);
            return `RM ${isFinite(number) ? number.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : ""}`.trim();
          };
          const labels = element.labels || {};
          const rows: Array<{ kind: string; label: string; limit?: string; value: string }> = [];
          if (extras.length > 0) {
            rows.push({ kind: "extras_header", label: labels.extras || "Extras / 附加项目", value: "" });
            extras.slice(0, 3).forEach((extra) => {
              const rawLimit = (extra as any)?.coverage_limit || ((extra as any)?.typed_value_override?.value ? String((extra as any)?.typed_value_override?.value) : "");
              let limitLabel = "";
              if (rawLimit) {
                const s = String(rawLimit).trim().replace(/^RM\s*/i, "");
                const num = parseFloat(s.replace(/,/g, ""));
                limitLabel = Number.isFinite(num) ? ` (RM ${num.toLocaleString("en-MY")})` : ` (RM ${s})`;
              }
              rows.push({
                kind: "extra",
                label: String(extra?.label || "") + limitLabel,
                value: fmtMoney(extra?.price),
              });
            });
            if (extras.length > 3) rows.push({ kind: "extra", label: `+${extras.length - 3} more`, value: "" });
          }
          const premium = variableValues?.premium || "";
          const roadtax = variableValues?.roadtax || "";
          const runner = variableValues?.service_fee || "";

          const pNum = parseFloat(String(premium).replace(/[^0-9.]/g, "")) || 0;
          const rtNum = parseFloat(String(roadtax).replace(/[^0-9.]/g, "")) || 0;
          const sfNum = parseFloat(String(runner).replace(/[^0-9.]/g, "")) || 0;
          const extrasTotal = extras.reduce((acc, ex) => {
            const price = ex?.price as { amount?: string | number; value?: string | number } | undefined;
            const amt = typeof price === "object" && price !== null ? (price.amount ?? price.value) : price;
            const num = typeof amt === "string" ? parseFloat(amt.replace(/,/g, "")) : (typeof amt === "number" ? amt : 0);
            return acc + (Number.isFinite(num) ? num : 0);
          }, 0);

          let total = variableValues?.total_premium_adjusted || "";
          if (!total && pNum > 0) {
            total = (pNum + rtNum + sfNum + extrasTotal).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          } else if (!total) {
            total = variableValues?.total_amount || "";
          }
          rows.push({ kind: "premium", label: labels.premium || "Coverage Premium / 保费", value: premium ? `RM ${premium}` : "" });
          rows.push({ kind: "divider", label: "", value: "" });
          rows.push({ kind: "roadtax", label: labels.roadtax || "Roadtax", value: roadtax ? `RM ${roadtax}` : "" });
          rows.push({ kind: "runner", label: labels.runner || "Runner Fee", value: runner ? `RM ${runner}` : "" });
          rows.push({ kind: "total", label: labels.total || "Total Premium 总额", value: total ? `RM ${total}` : "" });
          const rowHeight = Number(element.rowHeight) || 14;
          return (
            <div className="relative w-full h-full flex flex-col justify-start">
              {rows.map((row, index) => {
                if (row.kind === "divider") {
                  return <div key={`divider-${index}`} className="w-full my-0.5" style={{ height: 1, background: "#E2E8F0" }} />;
                }
                const labelStyle =
                  row.kind === "total"
                    ? { fontSize: 10.5, fontWeight: 800, color: "#0F172A" }
                    : row.kind === "extras_header"
                      ? { fontSize: 8.5, fontWeight: 700, color: "#DC2626", textTransform: "uppercase" as const, letterSpacing: "0.5px" }
                      : row.kind === "extra"
                        ? { fontSize: 9, fontWeight: 600, color: "#B91C1C" }
                        : { fontSize: 9, fontWeight: 600, color: "#334155" };
                const valueStyle =
                  row.kind === "total"
                    ? { fontSize: 11.5, fontWeight: 800, color: "#DC2626" }
                    : row.kind === "extras_header"
                      ? { fontSize: 8.5, fontWeight: 700, color: "#DC2626" }
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
  const extraShift = (extras.length + (extras.length > 0 ? 1 : 0)) * 14;
  if (!benefitData && extraShift === 0) return elements;
  const currentCards = benefitData?.current_benefits || [];
  const addonCards = benefitData?.available_addons || [];

  // Separate true FOC benefits from purchased extras / priced add-ons
  const extrasCards = currentCards.filter((c: any) => c.price || c.badge || c.cost_status === "paid");
  const focCards = extrasCards.length > 0
    ? currentCards.filter((c: any) => !(c.price || c.badge || c.cost_status === "paid"))
    : currentCards;

  const grid1 = elements.find((e) => e.type === "benefit-grid" && e.gridKind === "current_benefits");
  const grid2 = elements.find((e) => e.type === "benefit-grid" && e.gridKind === "available_addons");
  if (!grid1 || !grid2) return elements;

  const hdr1Bg = elements.find((e) => e.id === "specials_header_bg");
  const hdr1Txt = elements.find((e) => e.id === "specials_header_txt");
  const hdr2Bg = elements.find((e) => e.id === "addons_header_bg");
  const hdr2Txt = elements.find((e) => e.id === "addons_header_txt");

  const baseTop = hdr1Bg ? Number(hdr1Bg.y || 414) : Number(grid1.y || 444);
  const yTop = baseTop + extraShift;
  const yBottom = Number(grid2.y || 796) + Number(grid2.h || 262);

  const hdrH = 26;
  const gap = 6;
  const pad = 3;

  const hasExplicitExtrasGrid = elements.some((e) => e.gridKind === "extras" || e.gridKind === "purchased_extras");
  const hasExtrasSection = hasExplicitExtrasGrid && extrasCards.length > 0;

  if (hasExtrasSection) {
    const n1 = focCards.length;
    const nExt = extrasCards.length;
    const n2 = addonCards.length;

    const rows1 = n1 > 0 ? Math.max(1, Math.ceil(n1 / 2)) : 0;
    const rowsExt = nExt > 0 ? Math.max(1, Math.ceil(nExt / 2)) : 0;
    const rows2 = n2 > 0 ? Math.max(1, Math.ceil(n2 / 2)) : 0;

    const rowHeight = 100;
    const h1 = rows1 > 0 ? rows1 * rowHeight : 50;
    const hExt = rowsExt > 0 ? rowsExt * rowHeight : 50;
    const h2 = rows2 > 0 ? rows2 * rowHeight : 50;

    const yG1 = yTop + hdrH + pad;
    const yHExt = yG1 + h1 + gap;
    const yGExt = yHExt + hdrH + pad;
    const yH2 = yGExt + hExt + gap;
    const yG2 = yH2 + hdrH + pad;

    const adjusted: CanvasElement[] = [];
    for (const elem of elements) {
      const e = { ...elem };
      if (e.id === "cov_table_bg" && extraShift > 0) {
        e.h = Number(e.h || 246) + extraShift;
      } else if (e.id === "specials_header_bg" && hdr1Bg) {
        e.y = yTop;
        e.h = hdrH;
      } else if (e.id === "specials_header_txt" && hdr1Txt) {
        e.y = yTop + 5;
      } else if (e.type === "benefit-grid" && e.gridKind === "current_benefits") {
        e.y = yG1;
        e.h = h1;
        adjusted.push(e);
        // Insert Extras section
        adjusted.push({
          id: "extras_header_bg",
          type: "rectangle",
          x: 40,
          y: yHExt,
          w: 714,
          h: hdrH,
          z: 2,
          style: { background: "#1E293B", borderWidth: 0, borderColor: "transparent", borderRadius: 4 },
        });
        adjusted.push({
          id: "extras_header_txt",
          type: "text",
          text: "Purchased Extras & Add-ons / 额外附加保障",
          x: 52,
          y: yHExt + 5,
          w: 690,
          h: 16,
          z: 5,
          style: { fontSize: 10.5, fontWeight: "700", color: "#FFFFFF", textAlign: "left" },
        });
        adjusted.push({
          id: "extras_grid",
          type: "benefit-grid",
          gridKind: "extras",
          x: 40,
          y: yGExt,
          w: 714,
          h: hExt,
          z: 4,
          packing: grid1.packing || {
            strategy: "balanced",
            alignment: "center",
            aspectRatio: 1.45,
            referenceWidth: 180,
            referenceHeight: 124,
            gapRatio: 0.035,
            paddingRatio: 0.012,
            staggerRatio: 0.5,
          },
          cardStyle: grid1.cardStyle || "standard",
          textDensity: grid1.textDensity || "compact",
          emptyState: "hide",
        });
        continue;
      } else if (e.id === "addons_header_bg" && hdr2Bg) {
        e.y = yH2;
        e.h = hdrH;
      } else if (e.id === "addons_header_txt" && hdr2Txt) {
        e.y = yH2 + 5;
      } else if (e.type === "benefit-grid" && e.gridKind === "available_addons") {
        e.y = yG2;
        e.h = h2;
      }
      adjusted.push(e);
    }
    return adjusted;
  }

  // Standard 2-section layout when no extras exist
  const n1 = currentCards.length;
  const n2 = addonCards.length;
  const rows1 = n1 > 0 ? Math.max(1, Math.ceil(n1 / 2)) : 0;
  const rows2 = n2 > 0 ? Math.max(1, Math.ceil(n2 / 2)) : 0;

  const rowHeight = 100;
  const h1 = rows1 > 0 ? rows1 * rowHeight : 50;
  const h2 = rows2 > 0 ? rows2 * rowHeight : 50;

  const yG1 = yTop + hdrH + pad;
  const yH2 = yG1 + h1 + gap;
  const yG2 = yH2 + hdrH + pad;

  return elements.map((elem) => {
    const e = { ...elem };
    if (e.id === "cov_table_bg" && extraShift > 0) {
      e.h = Number(e.h || 246) + extraShift;
    } else if (e.id === "specials_header_bg" && hdr1Bg) {
      e.y = yTop;
      e.h = hdrH;
    } else if (e.id === "specials_header_txt" && hdr1Txt) {
      e.y = yTop + 5;
    } else if (e.type === "benefit-grid" && e.gridKind === "current_benefits") {
      e.y = yG1;
      e.h = h1;
    } else if (e.id === "addons_header_bg" && hdr2Bg) {
      e.y = yH2;
      e.h = hdrH;
    } else if (e.id === "addons_header_txt" && hdr2Txt) {
      e.y = yH2 + 5;
    } else if (e.type === "benefit-grid" && e.gridKind === "available_addons") {
      e.y = yG2;
      e.h = h2;
    }
    return e;
  });
}
