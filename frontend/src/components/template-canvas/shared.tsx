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
  gridKind?: "current_benefits" | "available_addons";
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
  emptyState?: "hide" | "message";
  emptyMessage?: string;
  prefix?: string;
  suffix?: string;
  rowHeight?: number;
  labels?: { premium?: string; roadtax?: string; runner?: string; total?: string };
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
    comfortable: { padding: 14, gap: 12, icon: 52, label: 17, value: 14 },
    normal: { padding: 12, gap: 10, icon: 48, label: 16, value: 13 },
    compact: { padding: 8, gap: 6, icon: 40, label: 14, value: 11 },
  }[element.textDensity || "normal"];
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
        asset ? (
          <img className="h-full w-full object-contain" src={fileUrl(asset.url)} alt="" />
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
        element.text
      ) : null}
      {element.type === "variable" ? (
        <span className="text-[var(--rl-red)]">
          {element.prefix || ""}
          {variableValues && (element.variableId || "") in variableValues
            ? variableValues[element.variableId || ""]
            : `{${element.variableId || "variable"}}`}
          {element.suffix || ""}
        </span>
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
          const items = benefitData
            ? (isAddons ? benefitData.available_addons : benefitData.current_benefits)
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
                actualLayout.cards.map((card, idx) => {
                  const b = orderedItems[idx];
                  const label = b ? b.label : `Benefit ${card.index + 1}`;
                  const val = b ? (b.value || "Included") : "Coverage value";
                  const assetUrl = b
                    ? b.asset_url ||
                    (b.asset_id ? `/business/assets/${b.asset_id}/content?profile=ui` : null) ||
                    (conceptAssets?.[b.concept_key] || conceptAssets?.[b.concept_id] || null) ||
                    (b.label ? conceptAssets?.[b.label.toLowerCase()] || conceptAssets?.[b.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")] || null : null) ||
                    (assets.find((a) => a.id === b.asset_id)?.url || null)
                    : null;

                  return (
                    <article key={card.index} className="absolute grid place-items-center overflow-hidden" style={{ left: card.x, top: card.y, width: card.width, height: card.height }}>
                      <div
                        className={`${b?.is_detected
                            ? "border-2 border-amber-400 bg-amber-50/40 shadow-sm ring-2 ring-amber-300/50"
                            : element.cardStyle === "minimal"
                              ? "bg-transparent"
                              : element.cardStyle === "soft"
                                ? "bg-[#f3f0f0] shadow-sm"
                                : "border border-[var(--rl-border)] bg-white"
                          } grid grid-cols-[58px_minmax(0,1fr)] items-center rounded-[10px]`}
                        style={{ width: element.packing?.referenceWidth || 180, height: element.packing?.referenceHeight || 124, transform: `scale(${card.scale})`, transformOrigin: "center", padding: density.padding, gap: density.gap }}
                      >
                        <div className="flex items-center justify-center overflow-hidden shrink-0" style={{ width: density.icon, height: density.icon }}>
                          {assetUrl ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={fileUrl(assetUrl)}
                              alt={label}
                              className="h-full w-full object-contain"
                              onError={(e) => {
                                (e.currentTarget as HTMLElement).style.display = "none";
                              }}
                            />
                          ) : (
                            <span
                              className="grid place-items-center rounded-full bg-[var(--rl-red-light)] font-black text-[var(--rl-red)]"
                              style={{ width: density.icon, height: density.icon, fontSize: Math.max(9, density.label - 4) }}
                            >
                              {label ? label.slice(0, 2).toUpperCase() : `B${card.index + 1}`}
                            </span>
                          )}
                        </div>
                        <span className="min-w-0 flex flex-col justify-center">
                          <strong
                            className="block font-bold leading-tight break-words text-[var(--rl-text-strong)]"
                            style={{
                              fontSize: label.length > 28 ? Math.max(10, density.label - 3) : label.length > 18 ? Math.max(11, density.label - 1.5) : density.label,
                            }}
                          >
                            {label}
                          </strong>
                          {val ? (
                            <span className="block text-[var(--rl-text-muted)] leading-tight break-words mt-0.5" style={{ fontSize: density.value }}>
                              {val}
                            </span>
                          ) : null}
                        </span>
                      </div>
                    </article>
                  );
                })
              )}
            </div>
          );
        })()
      ) : null}
      {element.type === "premium-info-block" ? (
        (() => {
          const extras = benefitData?.extras || [];
          const fmtMoney = (price?: { amount?: number | string; currency?: string }) => {
            const amount = price?.amount;
            if (amount === undefined || amount === null || amount === "") return "";
            const number = typeof amount === "string" ? Number(amount.replace(/,/g, "")) : Number(amount);
            return `RM ${isFinite(number) ? number.toLocaleString("en-MY") : ""}`.trim();
          };
          const rows: Array<{ kind: string; label: string; value: string }> = [];
          extras.slice(0, 3).forEach((extra) => rows.push({ kind: "extra", label: String(extra?.label || ""), value: fmtMoney(extra?.price) }));
          if (extras.length > 3) rows.push({ kind: "extra", label: `+${extras.length - 3} more`, value: "" });
          const labels = element.labels || {};
          const premium = variableValues?.premium || "";
          const roadtax = variableValues?.roadtax || "";
          const runner = variableValues?.service_fee || "";
          const total = variableValues?.total_premium_adjusted || variableValues?.total_amount || "";
          rows.push({ kind: "premium", label: labels.premium || "Coverage Premium / 保费", value: premium ? `RM ${premium}` : "" });
          rows.push({ kind: "divider", label: "", value: "" });
          rows.push({ kind: "roadtax", label: labels.roadtax || "Roadtax", value: roadtax ? `RM ${roadtax}` : "" });
          rows.push({ kind: "runner", label: labels.runner || "Runner Fee", value: runner ? `RM ${runner}` : "" });
          rows.push({ kind: "total", label: labels.total || "Total Premium 总额", value: total ? `RM ${total}` : "" });
          const rowHeight = Number(element.rowHeight) || 14;
          return (
            <>
              {rows.map((row, index) => {
                const top = Number(element.y) + index * rowHeight;
                if (row.kind === "divider") {
                  return <div key={`divider-${index}`} className="absolute" style={{ left: element.x, top, width: element.w, height: 1, background: "#E2E8F0" }} />;
                }
                const labelStyle =
                  row.kind === "total"
                    ? { fontSize: 11, fontWeight: 800, color: "#0F172A" }
                    : row.kind === "extra"
                      ? { fontSize: 9.5, fontWeight: 600, color: "#B91C1C" }
                      : { fontSize: 9.5, fontWeight: 600, color: "#334155" };
                const valueStyle =
                  row.kind === "total"
                    ? { fontSize: 13, fontWeight: 800, color: "#DC2626" }
                    : { fontSize: 10, fontWeight: 700, color: "#0F172A" };
                return (
                  <div key={`row-${index}`} className="absolute flex items-center justify-between" style={{ left: element.x, top, width: element.w, height: rowHeight }}>
                    <span style={labelStyle}>{row.label}</span>
                    <span style={valueStyle}>{row.value}</span>
                  </div>
                );
              })}
            </>
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
