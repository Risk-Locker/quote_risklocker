"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowArcLeft,
  ArrowArcRight,
  ArrowLeft,
  BracketsCurly,
  CaretDoubleDown,
  CaretDoubleUp,
  CaretDown,
  CaretUp,
  Circle,
  CopySimple,
  Diamond,
  FloppyDisk,
  GridFour,
  Image,
  LineSegment,
  MagnifyingGlass,
  Plus,
  Square,
  TextIndent,
  TextOutdent,
  TextT,
  Trash,
  Triangle,
  UploadSimple,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { api, fileUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CanvasElementView, FONT_LIBRARY, type CanvasElement, type CanvasStyle, SNAP, snapValue, computeGuides } from "@/components/template-canvas/shared";

type TemplateVariable = { id: string; label: string; type: string; source: string; field?: string; fixed_value?: string };
type BenefitCard = { icon?: string; title?: string; subtitle?: string; lines?: string[]; asset_id?: string };
type PackageConfig = { name: string; included_cards?: string[]; add_on_cards?: string[]; included?: string[]; add_ons?: string[] };
type TemplateConfig = { variables: TemplateVariable[]; cards: Record<string, BenefitCard>; packages: PackageConfig[]; assets: Record<string, string>; canvas: { width: number; height: number; elements: CanvasElement[] } };
type TemplateRecord = { id: string; name: string; insurance_type: string; status: string; locked: boolean; fixed_fields: TemplateConfig };
type AssetRecord = { id: string; label: string; filename: string; url: string; source?: string; folder?: string };
type DragState = { id: string; mode: "move" | "resize"; startX: number; startY: number; start: CanvasElement; handle?: string; members: Set<string>; memberStart: Map<string, { x: number; y: number }> };
type VariantItem = { id: string; special_id: string; label: string; secondary_label?: string | null; value_text?: string | null; icon_asset_id?: string | null; shape?: string | null; bg_color?: string | null; text_color?: string | null; border_width?: string | null; border_color?: string | null; shadow?: string | null; status: string };
type SpecialItem = { id: string; label: string; category: string; status: string; variants: VariantItem[] };

const assetSlots = ["risklocker_logo", "insurer_logo", "bank_logo", "all_driver_icon", "background"];
const variableTypes = ["text", "money", "number", "date", "percent", "image", "boolean", "choice", "benefit_card"];
const sourceFields = ["customer_name", "vehicle_no", "insurance_company", "coverage_type", "cover_period", "car_model", "ncd_percent", "coverage_amount", "premium", "roadtax", "service_fee", "total_amount", "valid_until"];

function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)); }
function makeId(prefix: string) { return `${prefix}_${Math.random().toString(36).slice(2, 9)}`; }
function slug(value: string) { return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || makeId("var"); }

function layerLabel(element: CanvasElement): string {
  switch (element.type) {
    case "text": return element.text ? (element.text.replace(/\s+/g, " ").slice(0, 24) || "Text") : "Text";
    case "variable": return `Var: ${element.variableId || "?"}`;
    case "image": return element.assetSlot ? `Image: ${element.assetSlot}` : "Image";
    case "line": return "Line";
    case "group": return "Box";
    case "shape": return "Shape";
    case "benefit-section": return element.section === "add_ons" ? "Add-on section" : "Specials section";
    case "special": return element.variant_label ? `Special: ${element.variant_label}` : "Special";
    case "benefit-card": return "Benefit card";
    default: return element.type;
  }
}
function defaultStyle(type: string): CanvasStyle {
  if (type === "special") return { fontSize: 12, fontWeight: "600", color: "#111111", textAlign: "center", background: "#F6F8FB", borderWidth: 1, borderColor: "#D8DDE6" };
  return {
    fontSize: type === "text" ? 16 : 14,
    fontWeight: "400",
    color: "#111111",
    textAlign: "left",
    borderWidth: type === "group" || type === "shape" ? 1 : 0,
    borderColor: "#111111",
    background: type === "group" || type === "shape" ? "#ffffff" : "transparent"
  };
}

export default function TemplateBuilderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { toast } = useToast();

  const [template, setTemplate] = useState<TemplateRecord | null>(null);
  const [assets, setAssets] = useState<AssetRecord[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [primaryId, setPrimaryId] = useState("");
  const [rightTab, setRightTab] = useState<"layers" | "properties">("layers");
  const [showLeft, setShowLeft] = useState(true);
  const [showRight, setShowRight] = useState(true);
  const [editingTextId, setEditingTextId] = useState<string | null>(null);
  const [rulerGuides, setRulerGuides] = useState<{ x: number[]; y: number[] }>({ x: [], y: [] });
  const [rulerDrag, setRulerDrag] = useState<{ axis: "x" | "y"; pos: number; active: boolean } | null>(null);
  const [marquee, setMarquee] = useState<{ startX: number; startY: number; curX: number; curY: number } | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const suppressClickRef = useRef(false);
  const [zoom, setZoom] = useState(0.72);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<TemplateConfig[]>([]);
  const [future, setFuture] = useState<TemplateConfig[]>([]);
  const [newVariable, setNewVariable] = useState({ label: "", type: "text", field: "" });
  const [showGrid, setShowGrid] = useState(true);
  const [previewMode, setPreviewMode] = useState(false);
  const [guides, setGuides] = useState<{ x: number; y: number }[]>([]);
  const [uploading, setUploading] = useState(false);
  const [assetFolder, setAssetFolder] = useState("Uncategorized");
  const [specials, setSpecials] = useState<SpecialItem[]>([]);
  const [specialSearch, setSpecialSearch] = useState("");
  const dragRef = useRef<DragState | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function load() {
    const [templateResult, assetResult, specialsResult] = await Promise.all([
      api<{ template: TemplateRecord }>(`/admin/templates/${id}`),
      api<{ assets: AssetRecord[] }>("/admin/template-assets"),
      api<{ our_specials: SpecialItem[] }>("/admin/our-specials"),
    ]);
    setTemplate(templateResult.template);
    setAssets(assetResult.assets);
    setSpecials(specialsResult.our_specials);
    selectOnly(templateResult.template.fixed_fields.canvas.elements[0]?.id || "");
  }

  useEffect(() => {
    if (authLoading || !user) return;
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load template builder."));
  }, [id, authLoading, user]);

  const config = template?.fixed_fields;
  const elements = config?.canvas?.elements || [];
  const selected = elements.find((item) => item.id === primaryId) || null;
  const selection = elements.filter((item) => selectedIds.has(item.id));
  const readOnly = Boolean(template?.locked) || previewMode;
  const selectedCard = selected?.cardId && config?.cards ? config.cards[selected.cardId] : null;
  const sortedElements = useMemo(() => [...elements].sort((a, b) => (a.z || 1) - (b.z || 1)), [elements]);

  function selectOnly(id: string) {
    setSelectedIds(new Set([id]));
    setPrimaryId(id);
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setPrimaryId(id);
  }

  function addToSelection(ids: string[]) {
    if (!ids.length) return;
    setSelectedIds((prev) => new Set([...prev, ...ids]));
    setPrimaryId(ids[ids.length - 1]);
  }

  function clearSelection() {
    setSelectedIds(new Set());
    setPrimaryId("");
  }

  function commit(updater: (current: TemplateConfig) => TemplateConfig) {
    if (!template || readOnly) return;
    setTemplate((current) => {
      if (!current) return current;
      setHistory((items) => [...items.slice(-30), clone(current.fixed_fields)]);
      setFuture([]);
      return { ...current, fixed_fields: updater(clone(current.fixed_fields)) };
    });
  }

  function updateElement(elementId: string, patch: Partial<CanvasElement>) {
    commit((current) => {
      current.canvas.elements = current.canvas.elements.map((item) => item.id === elementId ? { ...item, ...patch, style: { ...(item.style || {}), ...(patch.style || {}) } } : item);
      return current;
    });
  }

  function updateStyle(elementId: string, patch: Partial<CanvasStyle>) {
    updateElement(elementId, { style: patch });
  }

  function addSpecialElement(variant: VariantItem) {
    const element: CanvasElement = {
      id: makeId("special"),
      type: "special",
      x: 80, y: 120, w: 160, h: 80,
      z: Math.max(1, ...elements.map((item) => item.z || 1)) + 1,
      style: defaultStyle("special"),
      variantId: variant.id,
      variant_label: variant.label,
      variant_secondary_label: variant.secondary_label || undefined,
      variant_value_text: variant.value_text || undefined,
      variant_icon_asset_id: variant.icon_asset_id || undefined,
      variant_shape: variant.shape || undefined,
      variant_bg_color: variant.bg_color || undefined,
      variant_text_color: variant.text_color || undefined,
      variant_border_width: variant.border_width || undefined,
      variant_border_color: variant.border_color || undefined,
      variant_shadow: variant.shadow || undefined,
    };
    commit((current) => { current.canvas.elements.push(element); return current; });
    selectOnly(element.id);
  }

  function handleCanvasDragOver(event: React.DragEvent) { event.preventDefault(); }
  function handleCanvasDrop(event: React.DragEvent) {
    event.preventDefault();
    const raw = event.dataTransfer.getData("application/variant");
    if (!raw) return;
    try {
      const variant: VariantItem = JSON.parse(raw);
      const rect = canvasRef.current?.getBoundingClientRect();
      const dx = rect ? (event.clientX - rect.left) / zoom : 80;
      const dy = rect ? (event.clientY - rect.top) / zoom : 120;
      const element: CanvasElement = {
        id: makeId("special"),
        type: "special",
        x: Math.round(dx - 24), y: Math.round(dy - 24), w: 160, h: 80,
        z: Math.max(1, ...elements.map((item) => item.z || 1)) + 1,
        style: defaultStyle("special"),
        variantId: variant.id,
        variant_label: variant.label,
        variant_secondary_label: variant.secondary_label || undefined,
        variant_value_text: variant.value_text || undefined,
        variant_icon_asset_id: variant.icon_asset_id || undefined,
        variant_shape: variant.shape || undefined,
        variant_bg_color: variant.bg_color || undefined,
        variant_text_color: variant.text_color || undefined,
        variant_border_width: variant.border_width || undefined,
        variant_border_color: variant.border_color || undefined,
        variant_shadow: variant.shadow || undefined,
      };
      commit((current) => { current.canvas.elements.push(element); return current; });
      selectOnly(element.id);
    } catch { /* ignore invalid drop data */ }
  }

  function addElement(type: string, patch: Partial<CanvasElement> = {}) {
    const element: CanvasElement = {
      id: makeId(type),
      type,
      x: 80,
      y: 120,
      w: type === "line" ? 260 : 180,
      h: type === "line" ? 2 : 48,
      z: Math.max(1, ...elements.map((item) => item.z || 1)) + 1,
      style: defaultStyle(type),
      ...patch
    };
    commit((current) => { current.canvas.elements.push(element); return current; });
    selectOnly(element.id);
  }

  function updateElements(ids: Set<string>, patch: (el: CanvasElement) => Partial<CanvasElement>) {
    commit((current) => {
      current.canvas.elements = current.canvas.elements.map((item) => ids.has(item.id) ? { ...item, ...patch(item) } : item);
      return current;
    });
  }

  function moveSelectionIds(): Set<string> {
    const ids = new Set(selection.map((e) => e.id));
    const groupIds = new Set(selection.filter((e) => e.type === "group").map((e) => e.id));
    for (const el of elements) {
      if (el.groupId && groupIds.has(el.groupId)) ids.add(el.id);
    }
    return ids;
  }

  function deleteSelection() {
    if (!selectedIds.size || readOnly) return;
    const groupIds = new Set(selection.filter((e) => e.type === "group").map((e) => e.id));
    commit((current) => {
      current.canvas.elements = current.canvas.elements
        .filter((item) => !selectedIds.has(item.id))
        .filter((item) => !(item.groupId && groupIds.has(item.groupId)));
      return current;
    });
    clearSelection();
  }

  function duplicateSelection() {
    if (!selectedIds.size || readOnly) return;
    const idMap = new Map<string, string>();
    const copies = selection.map((el) => {
      const copy = { ...clone(el), id: makeId(el.type), x: el.x + 18, y: el.y + 18, z: (el.z || 1) + 1 };
      if (el.type === "group") idMap.set(el.id, copy.id);
      return copy;
    }).map((el) => {
      if (el.groupId && idMap.has(el.groupId)) return { ...el, groupId: idMap.get(el.groupId) };
      if (el.groupId) {
        const copy = { ...el };
        delete copy.groupId;
        return copy;
      }
      return el;
    });
    commit((current) => { current.canvas.elements.push(...copies); return current; });
    selectOnly(copies[copies.length - 1].id);
  }

  function groupSelection() {
    const members = selection.filter((e) => e.type !== "group");
    if (members.length < 2 || readOnly) return;
    const minX = Math.min(...members.map((m) => m.x));
    const minY = Math.min(...members.map((m) => m.y));
    const maxX = Math.max(...members.map((m) => m.x + m.w));
    const maxY = Math.max(...members.map((m) => m.y + m.h));
    const gid = makeId("group");
    const count = elements.filter((e) => e.type === "group").length;
    const groupEl: CanvasElement = {
      id: gid,
      type: "group",
      groupName: `Group ${count + 1}`,
      x: Math.floor(minX - 8), y: Math.floor(minY - 8),
      w: Math.ceil(maxX - minX + 16), h: Math.ceil(maxY - minY + 16),
      z: Math.max(1, Math.min(...members.map((m) => m.z || 1)) - 1),
      style: { background: "transparent", borderWidth: 1, borderColor: "#94a3b8" },
    };
    commit((current) => {
      current.canvas.elements = current.canvas.elements.map((e) => selectedIds.has(e.id) && e.type !== "group" ? { ...e, groupId: gid } : e);
      current.canvas.elements.push(groupEl);
      return current;
    });
    selectOnly(gid);
  }

  function ungroup() {
    const groupIds = new Set(selection.filter((e) => e.type === "group").map((e) => e.id));
    if (!groupIds.size || readOnly) return;
    commit((current) => {
      current.canvas.elements = current.canvas.elements
        .filter((e) => !groupIds.has(e.id))
        .map((e) => (e.groupId && groupIds.has(e.groupId)) ? { ...e, groupId: undefined } : e);
      return current;
    });
    clearSelection();
  }

  function undo() {
    if (!template || !history.length) return;
    const previous = history[history.length - 1];
    setFuture((items) => [clone(template.fixed_fields), ...items]);
    setHistory((items) => items.slice(0, -1));
    setTemplate({ ...template, fixed_fields: previous });
  }

  function redo() {
    if (!template || !future.length) return;
    const next = future[0];
    setHistory((items) => [...items, clone(template.fixed_fields)]);
    setFuture((items) => items.slice(1));
    setTemplate({ ...template, fixed_fields: next });
  }

  function bringForward() {
    if (!selection.length || readOnly) return;
    const maxZ = Math.max(0, ...elements.map((item) => item.z || 1));
    if (!selection.some((e) => (e.z || 1) < maxZ)) return;
    updateElements(moveSelectionIds(), (e) => ({ z: (e.z || 1) + 1 }));
  }

  function bringToFront() {
    if (!selection.length || readOnly) return;
    const maxZ = Math.max(0, ...elements.map((item) => item.z || 1));
    updateElements(moveSelectionIds(), () => ({ z: maxZ + 1 }));
  }

  function sendBackward() {
    if (!selection.length || readOnly) return;
    if (!selection.some((e) => (e.z || 1) > 1)) return;
    updateElements(moveSelectionIds(), (e) => ({ z: Math.max(1, (e.z || 1) - 1) }));
  }

  function sendToBack() {
    if (!selection.length || readOnly) return;
    updateElements(moveSelectionIds(), () => ({ z: 1 }));
  }

  function clampPos(pos: number, axis: "x" | "y") {
    const max = axis === "x" ? (config?.canvas.width || 794) : (config?.canvas.height || 1123);
    return Math.max(0, Math.min(max, pos));
  }

  function startRulerDrag(event: React.PointerEvent, axis: "x" | "y") {
    if (readOnly) return;
    event.preventDefault();
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const pos = axis === "x" ? (event.clientX - rect.left) / zoom : (event.clientY - rect.top) / zoom;
    setRulerDrag({ axis, pos: clampPos(pos, axis), active: true });
  }

  function moveRulerDrag(event: React.PointerEvent) {
    if (!rulerDrag?.active) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const pos = rulerDrag.axis === "x" ? (event.clientX - rect.left) / zoom : (event.clientY - rect.top) / zoom;
    setRulerDrag((current) => (current ? { ...current, pos: clampPos(pos, current.axis) } : current));
  }

  function endRulerDrag() {
    if (!rulerDrag?.active) return;
    const axis = rulerDrag.axis;
    const pos = Math.round(rulerDrag.pos);
    setRulerGuides((current) => {
      const list = current[axis];
      const existing = list.find((p) => Math.abs(p - pos) <= 3);
      const next = existing ? list : [...list, pos].sort((a, b) => a - b);
      return { ...current, [axis]: next };
    });
    setRulerDrag(null);
  }

  function pointerDown(event: React.PointerEvent, element: CanvasElement, mode: "move" | "resize", handle?: string) {
    if (readOnly) return;
    if (element.type === "image" && element.assetSlot === "background" && mode === "move") return;
    event.preventDefault();
    event.stopPropagation();
    if (event.shiftKey && mode === "move") {
      toggleSelect(element.id);
    } else if (!selectedIds.has(element.id)) {
      selectOnly(element.id);
    }
    const members = mode === "move" ? moveSelectionIds() : new Set([element.id]);
    const memberStart = new Map<string, { x: number; y: number }>();
    for (const el of elements) {
      if (members.has(el.id)) memberStart.set(el.id, { x: el.x, y: el.y });
    }
    dragRef.current = { id: element.id, mode, startX: event.clientX, startY: event.clientY, start: clone(element), handle, members, memberStart };
  }

  function pointerMove(event: React.PointerEvent) {
    const drag = dragRef.current;
    if (!drag || !template) return;
    const dx = (event.clientX - drag.startX) / zoom;
    const dy = (event.clientY - drag.startY) / zoom;

    if (drag.mode === "move") {
      let nx = Math.round(drag.start.x + dx);
      let ny = Math.round(drag.start.y + dy);
      const { value: sx, guide: gx } = snapValue(nx, SNAP, []);
      const { value: sy, guide: gy } = snapValue(ny, SNAP, []);
      nx = gx ?? sx;
      ny = gy ?? sy;
      const guides = computeGuides(drag.start, { x: nx, y: ny }, elements, config?.canvas.width || 794, (config?.canvas.width || 794) / 2);
      setGuides(guides);
      const ddx = nx - drag.start.x;
      const ddy = ny - drag.start.y;
      setTemplate((current) => {
        if (!current) return current;
        const next = clone(current);
        next.fixed_fields.canvas.elements = next.fixed_fields.canvas.elements.map((item: CanvasElement) => {
          if (!drag.members.has(item.id)) return item;
          const start = drag.memberStart.get(item.id);
          return start ? { ...item, x: Math.round(start.x + ddx), y: Math.round(start.y + ddy) } : item;
        });
        return { ...current, fixed_fields: next.fixed_fields };
      });
    } else {
      const patch: Partial<CanvasElement> = {};
      if (drag.handle?.includes("e")) patch.w = Math.max(8, Math.round(drag.start.w + dx));
      if (drag.handle?.includes("s")) patch.h = Math.max(2, Math.round(drag.start.h + dy));
      if (drag.handle?.includes("w")) {
        const nw = Math.max(8, Math.round(drag.start.w - dx));
        patch.w = nw;
        patch.x = drag.start.x + drag.start.w - nw;
      }
      if (drag.handle?.includes("n")) {
        const nh = Math.max(2, Math.round(drag.start.h - dy));
        patch.h = nh;
        patch.y = drag.start.y + drag.start.h - nh;
      }
      const guides = computeGuides(drag.start, patch, elements, config?.canvas.width || 794, (config?.canvas.width || 794) / 2);
      setGuides(guides);
      setTemplate((current) => {
        if (!current) return current;
        const next = clone(current);
        next.fixed_fields.canvas.elements = next.fixed_fields.canvas.elements.map((item: CanvasElement) => item.id === drag.id ? { ...item, ...patch } : item);
        return { ...current, fixed_fields: next.fixed_fields };
      });
    }
  }

  function canvasPointerDown(event: React.PointerEvent) {
    if (readOnly || previewMode) return;
    suppressClickRef.current = false;
    const target = event.target as HTMLElement;
    const isBackgroundImage = !!target.closest("[data-bg='1']");
    if (target !== event.currentTarget && !isBackgroundImage) return;
    event.preventDefault();
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    setMarquee({
      startX: (event.clientX - rect.left) / zoom,
      startY: (event.clientY - rect.top) / zoom,
      curX: (event.clientX - rect.left) / zoom,
      curY: (event.clientY - rect.top) / zoom,
    });
  }

  function canvasPointerMove(event: React.PointerEvent) {
    if (!marquee) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    setMarquee((m) => m ? {
      ...m,
      curX: Math.max(0, Math.min((config?.canvas.width || 794), (event.clientX - rect.left) / zoom)),
      curY: Math.max(0, Math.min((config?.canvas.height || 1123), (event.clientY - rect.top) / zoom)),
    } : m);
  }

  function canvasPointerUp() {
    if (!marquee) return;
    const x0 = Math.min(marquee.startX, marquee.curX);
    const y0 = Math.min(marquee.startY, marquee.curY);
    const x1 = Math.max(marquee.startX, marquee.curX);
    const y1 = Math.max(marquee.startY, marquee.curY);
    setMarquee(null);
    if (x1 - x0 < 4 && y1 - y0 < 4) return;
    const hits = elements.filter((el) => el.x < x1 && el.x + el.w > x0 && el.y < y1 && el.y + el.h > y0).map((el) => el.id);
    if (!hits.length) return;
    setSelectedIds(new Set(hits));
    setPrimaryId(hits[hits.length - 1]);
    suppressClickRef.current = true;
  }

  function pointerUp() {
    const drag = dragRef.current;
    dragRef.current = null;
    setGuides([]);
    if (drag) suppressClickRef.current = true;
    if (drag && template) {
      const element = template.fixed_fields.canvas.elements.find((item) => item.id === drag.id);
      if (element) {
        setHistory((items) => [...items.slice(-30), clone(template.fixed_fields)]);
      }
    }
  }

  async function copyLocked() {
    if (!template) return;
    const result = await api<{ template: TemplateRecord }>(`/admin/templates/${template.id}/copy`, { method: "POST", body: JSON.stringify({}) });
    window.location.href = `/builder/templates/${result.template.id}/builder`;
  }

  async function save(status?: string) {
    if (!template) return;
    const result = await api<{ template: TemplateRecord }>(`/admin/templates/${template.id}`, {
      method: "PATCH",
      body: JSON.stringify({ name: template.name, insurance_type: template.insurance_type, status: status || template.status, fixed_fields: template.fixed_fields })
    });
    setTemplate(result.template);
    toast(status === "active" ? "Template published." : "Template saved.", "success");
  }

  async function uploadAsset(file: File) {
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("label", file.name.replace(/\.[^.]+$/, ""));
      form.append("folder", assetFolder.trim() || "Uncategorized");
      const result = await api<{ asset: AssetRecord }>("/admin/template-assets", { method: "POST", body: form });
      setAssets((current) => [result.asset, ...current]);
      toast(`Asset uploaded to "${result.asset.folder || "Uncategorized"}" folder.`, "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  function addVariable() {
    if (!newVariable.label.trim()) return;
    const variable: TemplateVariable = { id: slug(newVariable.label), label: newVariable.label.trim(), type: newVariable.type, source: newVariable.field ? "field" : "manual", field: newVariable.field || undefined };
    commit((current) => { if (!current.variables.some((item) => item.id === variable.id)) current.variables.push(variable); return current; });
    setNewVariable({ label: "", type: "text", field: "" });
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (readOnly) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable)) {
        return;
      }
      const meta = event.ctrlKey || event.metaKey;
      if (meta && event.key.toLowerCase() === "z") { event.preventDefault(); if (event.shiftKey) redo(); else undo(); return; }
      if (meta && event.key.toLowerCase() === "y") { event.preventDefault(); redo(); return; }
      if (meta && event.key.toLowerCase() === "d") { event.preventDefault(); duplicateSelection(); return; }
      if (!selectedIds.size) return;
      if (event.key === "Delete" || event.key === "Backspace") { event.preventDefault(); deleteSelection(); return; }
      const step = event.shiftKey ? 10 : 1;
      if (event.key === "ArrowUp") { event.preventDefault(); updateElements(moveSelectionIds(), (e) => ({ y: (e.y || 0) - step })); }
      else if (event.key === "ArrowDown") { event.preventDefault(); updateElements(moveSelectionIds(), (e) => ({ y: (e.y || 0) + step })); }
      else if (event.key === "ArrowLeft") { event.preventDefault(); updateElements(moveSelectionIds(), (e) => ({ x: (e.x || 0) - step })); }
      else if (event.key === "ArrowRight") { event.preventDefault(); updateElements(moveSelectionIds(), (e) => ({ x: (e.x || 0) + step })); }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedIds, readOnly, history, future, elements]);

  useEffect(() => {
    if (!authLoading && user === null) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  if (authLoading || user === null) {
    return (
      <div className="grid min-h-screen place-items-center bg-[var(--rl-bg)]">
        <div className="flex items-center gap-2 text-sm text-[var(--rl-text-muted)]">
          <Spinner size={16} />
          Checking session...
        </div>
      </div>
    );
  }

  return (
    <main className="flex h-dvh flex-col overflow-hidden bg-[var(--rl-bg)] text-[var(--rl-text)]">
      <div className="z-30 flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] bg-[var(--rl-surface)]/95 px-4 py-3 backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="ghost"
            icon={<ArrowLeft weight="bold" size={16} />}
            onClick={() => router.push("/builder/templates")}
          >
            Templates
          </Button>
          <Input
            className="w-72 font-bold"
            value={template?.name || ""}
            disabled={readOnly}
            onChange={(event) => setTemplate((current) => current ? { ...current, name: event.target.value } : current)}
          />
          {template?.locked ? <Badge variant="warning">Locked default</Badge> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={<TextOutdent weight="bold" size={14} />}
            onClick={() => setShowLeft((v) => !v)}
            title={showLeft ? "Hide left panel" : "Show left panel"}
          >
            Panels
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={<TextIndent weight="bold" size={14} />}
            onClick={() => setShowRight((v) => !v)}
            title={showRight ? "Hide right panel" : "Show right panel"}
          >
            Inspector
          </Button>
          <Button
            variant={showGrid ? "primary" : "secondary"}
            size="sm"
            icon={<GridFour weight="bold" size={16} />}
            onClick={() => setShowGrid((v) => !v)}
          >
            Grid
          </Button>
          <Button
            variant={previewMode ? "primary" : "secondary"}
            size="sm"
            icon={<MagnifyingGlass weight="bold" size={16} />}
            onClick={() => setPreviewMode((v) => !v)}
          >
            {previewMode ? "Edit" : "Preview"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={<ArrowArcLeft weight="bold" size={16} />}
            onClick={undo}
            disabled={!history.length || readOnly}
          >
            Undo
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={<ArrowArcRight weight="bold" size={16} />}
            onClick={redo}
            disabled={!future.length || readOnly}
          >
            Redo
          </Button>
          {template?.locked ? (
            <Button
              variant="primary"
              size="sm"
              icon={<CopySimple weight="bold" size={16} />}
              onClick={copyLocked}
            >
              Copy to edit
            </Button>
          ) : (
            <>
              <Button
                variant="secondary"
                size="sm"
                icon={<FloppyDisk weight="bold" size={16} />}
                onClick={() => save()}
              >
                Save draft
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => save("active")}
              >
                Publish
              </Button>
            </>
          )}
        </div>
      </div>

      {error ? (
        <div className="m-4 shrink-0 rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
          {error}
        </div>
      ) : null}

      <div className={`grid min-h-0 flex-1 ${showLeft && showRight ? "grid-cols-[280px_minmax(0,1fr)_320px]" : showLeft ? "grid-cols-[280px_minmax(0,1fr)]" : showRight ? "grid-cols-[minmax(0,1fr)_320px]" : "grid-cols-1"}`}>
        {!previewMode && showLeft ? (
          <aside className="min-h-0 overflow-y-auto border-r border-[var(--rl-border)] bg-[var(--rl-surface)] p-4">
            <PanelSection title="Elements">
              <div className="grid grid-cols-2 gap-2">
              <Button
                variant="secondary"
                size="sm"
                icon={<TextT weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("text", { text: "Text block" })}
                className="justify-start"
              >
                Text
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<BracketsCurly weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("variable", { variableId: config?.variables?.[0]?.id || "customer_name" })}
                className="justify-start"
              >
                Variable
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<Image weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("image", { w: 120, h: 80 })}
                className="justify-start"
              >
                Image
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<Square weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("group", { w: 180, h: 80 })}
                className="justify-start"
              >
                Box
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<LineSegment weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("line", { w: 280, h: 2, style: { borderWidth: 2 } })}
                className="justify-start"
              >
                Line
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<Circle weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("shape", { shapeKind: "circle", w: 100, h: 100, style: { background: "#F6F8FB", borderWidth: 1, borderColor: "#D8DDE6" } })}
                className="justify-start"
              >
                Circle
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<Triangle weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("shape", { shapeKind: "triangle", w: 100, h: 90, style: { background: "#F6F8FB" } })}
                className="justify-start"
              >
                Triangle
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<Diamond weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("shape", { shapeKind: "diamond", w: 100, h: 100, style: { background: "#F6F8FB", borderWidth: 1, borderColor: "#D8DDE6" } })}
                className="justify-start"
              >
                Diamond
              </Button>
              </div>
            </PanelSection>

            <PanelSection title="Variables">
              <div className="grid gap-2">
              <Input
                placeholder="Variable label"
                value={newVariable.label}
                disabled={readOnly}
                onChange={(event) => setNewVariable((current) => ({ ...current, label: event.target.value }))}
              />
              <Select
                value={newVariable.type}
                disabled={readOnly}
                onChange={(event) => setNewVariable((current) => ({ ...current, type: event.target.value }))}
              >
                {variableTypes.map((item) => <option key={item} value={item}>{item}</option>)}
              </Select>
              <Select
                value={newVariable.field}
                disabled={readOnly}
                onChange={(event) => setNewVariable((current) => ({ ...current, field: event.target.value }))}
              >
                <option value="">Manual only</option>
                {sourceFields.map((field) => <option key={field} value={field}>{field}</option>)}
              </Select>
              <Button variant="secondary" size="sm" disabled={readOnly} onClick={addVariable}>
                <Plus weight="bold" size={14} /> Add variable
              </Button>
              <div className="grid max-h-48 gap-1 overflow-auto text-sm">
                {config?.variables?.map((variable) => (
                  <button
                    key={variable.id}
                    className="rounded border border-[var(--rl-border)] px-2 py-1 text-left hover:bg-[var(--rl-bg)]"
                    type="button"
                    onClick={() => addElement("variable", { variableId: variable.id })}
                  >
                    {variable.label}
                  </button>
                ))}
              </div>
              </div>
            </PanelSection>

            <PanelSection title="Assets">
              <div className="grid gap-2">
              <div className="grid gap-1.5">
                <label className="text-xs font-semibold text-[var(--rl-text-muted)]">Upload to folder</label>
                <Input
                  className="text-sm"
                  value={assetFolder}
                  disabled={readOnly}
                  list="asset-folders"
                  placeholder="Uncategorized"
                  onChange={(e) => setAssetFolder(e.target.value)}
                />
                <datalist id="asset-folders">
                  {[...new Set(assets.map((a) => a.folder || "Uncategorized"))].sort().map((folder) => (
                    <option key={folder} value={folder} />
                  ))}
                </datalist>
                <p className="text-[11px] text-[var(--rl-text-muted)]">Leave empty or pick an existing folder; a new folder name is created on upload.</p>
              </div>
              <input ref={fileInputRef} className="sr-only" type="file" accept=".png,.jpg,.jpeg,.svg" onChange={(event) => event.target.files?.[0] && uploadAsset(event.target.files[0])} />
              <Button
                variant="secondary"
                size="sm"
                icon={<UploadSimple weight="bold" size={16} />}
                disabled={readOnly || uploading}
                onClick={() => fileInputRef.current?.click()}
                className="justify-start"
              >
                {uploading ? "Uploading" : "Upload asset"}
              </Button>
              <div className="grid max-h-64 gap-2 overflow-auto">
                {Object.entries(
                  assets.reduce<Record<string, AssetRecord[]>>((groups, asset) => {
                    const folder = asset.folder || "Uncategorized";
                    (groups[folder] ||= []).push(asset);
                    return groups;
                  }, {})
                ).sort(([a], [b]) => a.localeCompare(b)).map(([folder, items]) => (
                  <div key={folder} className="grid gap-1">
                    <div className="text-[10px] font-bold uppercase text-[var(--rl-text-muted)]">{folder} ({items.length})</div>
                    {items.map((asset) => (
                      <button
                        key={asset.id}
                        className="grid grid-cols-[44px_1fr] items-center gap-2 rounded border border-[var(--rl-border)] p-2 text-left text-xs hover:bg-[var(--rl-bg)]"
                        type="button"
                        disabled={readOnly}
                        onClick={() => addElement("image", { assetId: asset.id, w: 120, h: 70 })}
                      >
                        <img className="h-10 w-10 object-contain" src={fileUrl(asset.url)} alt="" />
                        <span>{asset.label}</span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
              </div>
            </PanelSection>

            <PanelSection title="Our Specials">
              <div className="grid gap-2">
              <Input
                className="text-sm"
                placeholder="Search variants..."
                value={specialSearch}
                disabled={readOnly}
                onChange={(e) => setSpecialSearch(e.target.value)}
              />
              <div className="grid max-h-72 gap-2 overflow-auto">
                {specials.flatMap((sp) => {
                  const filtered = specialSearch
                    ? sp.variants.filter((v) =>
                        v.label.toLowerCase().includes(specialSearch.toLowerCase()) ||
                        sp.label.toLowerCase().includes(specialSearch.toLowerCase()))
                    : sp.variants;
                  if (!filtered.length) return [];
                  return (
                    <div key={sp.id} className="grid gap-1">
                      <div className="text-[10px] font-bold uppercase text-[var(--rl-text-muted)]">{sp.label} ({sp.category})</div>
                      {filtered.map((v) => (
                        <div
                          key={v.id}
                          className="grid cursor-grab grid-cols-[36px_1fr] items-center gap-2 rounded border border-[var(--rl-border)] bg-[var(--rl-surface)] p-1.5 text-left text-xs hover:bg-[var(--rl-bg)] active:cursor-grabbing"
                          draggable={!readOnly}
                          onDragStart={(e) => {
                            e.dataTransfer.setData("application/variant", JSON.stringify(v));
                            e.dataTransfer.effectAllowed = "copy";
                          }}
                          onClick={(e) => { e.stopPropagation(); if (!readOnly) addSpecialElement(v); }}
                        >
                          {v.icon_asset_id ? (
                            <img className="h-8 w-8 object-contain" src={fileUrl(`/template-assets/${v.icon_asset_id}`)} alt="" />
                          ) : (
                            <div className="flex h-8 w-8 items-center justify-center rounded border border-[var(--rl-border)] bg-[var(--rl-bg)] text-[9px] text-[var(--rl-text-muted)]">IC</div>
                          )}
                          <div className="grid gap-0.5 leading-tight">
                            <span className="font-bold">{v.label}</span>
                            {v.value_text ? <span className="text-[10px] text-[var(--rl-text-muted)]">{v.value_text}</span> : null}
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                })}
                {!specials.length ? <p className="text-xs text-[var(--rl-text-muted)]">No specials yet. Create them in Our Specials.</p> : null}
              </div>
              </div>
            </PanelSection>
          </aside>
        ) : <div />}

        <section className="overflow-auto p-6">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-bold text-[var(--rl-text-strong)]">Canvas</div>
            <label className="flex items-center gap-2 text-sm font-bold">
              Zoom
              <input className="w-32" type="range" min="0.45" max="1.1" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} />
            </label>
          </div>
          <div className="mx-auto w-fit rounded-md bg-neutral-300 p-6 shadow-inner" style={{ minHeight: ((config?.canvas.height || 1123) * zoom) + 60 }}>
            <div className="relative" style={{ width: (config?.canvas.width || 794) * zoom, height: (config?.canvas.height || 1123) * zoom }}>
              {!previewMode ? (
                <>
                  <div className="absolute -top-6 left-0 h-5 w-full select-none overflow-hidden border-b border-[var(--rl-border)] bg-[var(--rl-surface)]"
                    onPointerDown={(event) => startRulerDrag(event, "x")}
                    onPointerMove={(event) => moveRulerDrag(event)}
                    onPointerUp={endRulerDrag}
                  >
                    {Array.from({ length: Math.ceil((config?.canvas.width || 794) / 25) + 1 }, (_, i) => {
                      const px = i * 25 * zoom;
                      const major = i % 4 === 0;
                      return <span key={i} className={`absolute top-0 ${major ? "h-3 w-px" : "h-1.5 w-px"} bg-[var(--rl-text-muted)]`} style={{ left: px }} />;
                    })}
                    {Array.from({ length: Math.ceil((config?.canvas.width || 794) / 100) + 1 }, (_, i) => (
                      <span key={`l${i}`} className="absolute top-1 text-[8px] leading-none text-[var(--rl-text-muted)]" style={{ left: i * 100 * zoom + 2 }}>{i * 100}</span>
                    ))}
                    {rulerDrag?.axis === "x" && rulerDrag.active ? (
                      <span className="absolute top-0 h-full w-px bg-[var(--rl-red)]" style={{ left: rulerDrag.pos * zoom }} />
                    ) : null}
                  </div>
                  <div className="absolute -left-6 top-0 w-5 select-none overflow-hidden border-r border-[var(--rl-border)] bg-[var(--rl-surface)]"
                    onPointerDown={(event) => startRulerDrag(event, "y")}
                    onPointerMove={(event) => moveRulerDrag(event)}
                    onPointerUp={endRulerDrag}
                  >
                    {Array.from({ length: Math.ceil((config?.canvas.height || 1123) / 25) + 1 }, (_, i) => {
                      const py = i * 25 * zoom;
                      const major = i % 4 === 0;
                      return <span key={i} className={`absolute left-0 ${major ? "w-3 h-px" : "w-1.5 h-px"} bg-[var(--rl-text-muted)]`} style={{ top: py }} />;
                    })}
                    {Array.from({ length: Math.ceil((config?.canvas.height || 1123) / 100) + 1 }, (_, i) => (
                      <span key={`l${i}`} className="absolute left-1 text-[8px] leading-none text-[var(--rl-text-muted)]" style={{ top: i * 100 * zoom + 2 }}>{i * 100}</span>
                    ))}
                    {rulerDrag?.axis === "y" && rulerDrag.active ? (
                      <span className="absolute left-0 h-px w-full bg-[var(--rl-red)]" style={{ top: rulerDrag.pos * zoom }} />
                    ) : null}
                  </div>
                  <div className="absolute -top-6 -left-6 h-6 w-6 border-b border-r border-[var(--rl-border)] bg-[var(--rl-surface)]" />
                </>
              ) : null}
              <div
                ref={canvasRef}
                className="relative origin-top-left overflow-hidden bg-white shadow-xl"
                style={{ width: config?.canvas.width || 794, height: config?.canvas.height || 1123, transform: `scale(${zoom})` }}
                onPointerDown={canvasPointerDown}
                onPointerMove={(event) => { pointerMove(event); canvasPointerMove(event); }}
                onPointerUp={(event) => { pointerUp(); canvasPointerUp(); }}
                onPointerLeave={pointerUp}
                onDragOver={handleCanvasDragOver}
                onDrop={handleCanvasDrop}
                onClick={() => { if (suppressClickRef.current) { suppressClickRef.current = false; return; } clearSelection(); setEditingTextId(null); }}
              >
                {showGrid && !previewMode && (
                  <div className="pointer-events-none absolute inset-0 opacity-10" style={{ backgroundImage: `linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)`, backgroundSize: `${SNAP * zoom}px ${SNAP * zoom}px` }} />
                )}
                {guides.map((guide, index) => (
                  guide.x > 0 ? (
                    <div key={`v${index}`} className="pointer-events-none absolute top-0 bottom-0 border-l border-dashed" style={{ left: guide.x, zIndex: 9999, borderColor: "var(--rl-red)" }} />
                  ) : (
                    <div key={`h${index}`} className="pointer-events-none absolute left-0 right-0 border-t border-dashed" style={{ top: guide.y, zIndex: 9999, borderColor: "var(--rl-red)" }} />
                  )
                ))}
                {!previewMode && rulerGuides.x.map((x) => (
                  <div key={`gx${x}`} className="pointer-events-none absolute top-0 bottom-0 border-l border-dashed" style={{ left: x, zIndex: 9998, borderColor: "#3b82f6" }} />
                ))}
                {!previewMode && rulerGuides.y.map((y) => (
                  <div key={`gy${y}`} className="pointer-events-none absolute left-0 right-0 border-t border-dashed" style={{ top: y, zIndex: 9998, borderColor: "#3b82f6" }} />
                ))}
                {marquee ? (
                  <div
                    className="pointer-events-none absolute border border-[#3b82f6] bg-[#3b82f6]/10"
                    style={{
                      left: Math.min(marquee.startX, marquee.curX),
                      top: Math.min(marquee.startY, marquee.curY),
                      width: Math.abs(marquee.curX - marquee.startX),
                      height: Math.abs(marquee.curY - marquee.startY),
                      zIndex: 9997,
                    }}
                  />
                ) : null}
                {sortedElements.map((element) => (
                  <CanvasElementView
                    key={element.id}
                    element={element}
                    selected={!previewMode && selectedIds.has(element.id)}
                    assets={assets}
                    config={config}
                    readOnly={readOnly}
                    onPointerDown={(event) => pointerDown(event, element, "move")}
                    onResizePointerDown={(event, handle) => pointerDown(event, element, "resize", handle)}
                    onDoubleClick={(event) => {
                      if (element.type !== "text" || readOnly) return;
                      event.stopPropagation();
                      selectOnly(element.id);
                      setEditingTextId(element.id);
                    }}
                    editingText={element.type === "text" && editingTextId === element.id}
                    onTextCommit={(text) => {
                      updateElement(element.id, { text });
                      setEditingTextId(null);
                    }}
                  />
                ))}
              </div>
            </div>
          </div>
        </section>

        {!previewMode && showRight ? (
          <aside className="flex min-h-0 flex-col overflow-hidden border-l border-[var(--rl-border)] bg-[var(--rl-surface)]">
            <div className="flex shrink-0 gap-1 border-b border-[var(--rl-border)] p-2">
              <button
                type="button"
                onClick={() => setRightTab("layers")}
                className={`flex-1 rounded-[var(--rl-radius-sm)] px-3 py-2 text-[13px] font-bold transition-all ${rightTab === "layers" ? "bg-[var(--rl-black)] text-white" : "text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)]"}`}
              >
                Layers
              </button>
              <button
                type="button"
                onClick={() => setRightTab("properties")}
                className={`flex-1 rounded-[var(--rl-radius-sm)] px-3 py-2 text-[13px] font-bold transition-all ${rightTab === "properties" ? "bg-[var(--rl-black)] text-white" : "text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)]"}`}
              >
                Properties
              </button>
            </div>

            {rightTab === "layers" ? (
              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                <h2 className="font-bold text-[var(--rl-text-strong)]">Layers</h2>
                <p className="mt-1 text-[12px] text-[var(--rl-text-muted)]">Top of the list sits on top of the canvas.</p>
                <div className="mt-3 grid gap-1">
                  {elements.length === 0 ? (
                    <p className="text-xs text-[var(--rl-text-muted)]">No elements yet. Add one from the left sidebar.</p>
                  ) : (
                    <>
                      {selection.length > 1 ? (
                        <div className="mb-2 flex flex-wrap items-center gap-1.5 rounded border border-[#3b82f6] bg-[#eff6ff] p-1.5">
                          <span className="px-1 text-[11px] font-bold text-[#3b82f6]">{selection.length} selected</span>
                          <button type="button" className="rounded bg-[#3b82f6] px-2 py-0.5 text-[11px] font-bold text-white disabled:opacity-40" disabled={readOnly} onClick={groupSelection}>Group</button>
                          <button type="button" className="rounded border border-[var(--rl-border)] bg-white px-2 py-0.5 text-[11px] font-bold" disabled={readOnly} onClick={duplicateSelection}>Duplicate</button>
                          <button type="button" className="rounded border border-[var(--rl-red)] bg-white px-2 py-0.5 text-[11px] font-bold text-[var(--rl-red)]" disabled={readOnly} onClick={deleteSelection}>Delete</button>
                        </div>
                      ) : null}
                      {selection.some((e) => e.type === "group") ? (
                        <button type="button" className="mb-1 w-full rounded border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2 py-1 text-[11px] font-bold text-[var(--rl-text-strong)] hover:bg-[var(--rl-bg)] disabled:opacity-40" disabled={readOnly} onClick={ungroup}>
                          Ungroup selected
                        </button>
                      ) : null}
                      {(() => {
                        const groups = elements.filter((e) => e.type === "group").sort((a, b) => (b.z || 1) - (a.z || 1));
                        const members = (gid: string) => elements.filter((e) => e.groupId === gid).sort((a, b) => (b.z || 1) - (a.z || 1));
                        const ungrouped = elements.filter((e) => !e.groupId && e.type !== "group").sort((a, b) => (b.z || 1) - (a.z || 1));
                        const rowClass = (id: string) => `flex items-center gap-1 rounded border px-1.5 py-1 text-xs transition-colors ${selectedIds.has(id) ? "border-[#3b82f6] bg-[#eff6ff]" : "border-[var(--rl-border)] bg-[var(--rl-surface)] hover:bg-[var(--rl-bg)]"}`;
                        const labelButton = (el: CanvasElement, indent: boolean) => (
                          <button
                            type="button"
                            className={`min-w-0 flex-1 truncate text-left font-medium text-[var(--rl-text-strong)] ${indent ? "pl-4" : ""}`}
                            onClick={(e) => { if (e.shiftKey) toggleSelect(el.id); else selectOnly(el.id); }}
                            title={layerLabel(el)}
                          >
                            <span className="mr-1.5 text-[var(--rl-text-muted)]">z{el.z || 1}</span>
                            {layerLabel(el)}
                          </button>
                        );
                        const zButtons = (el: CanvasElement) => (
                          <>
                            <button
                              type="button"
                              className="rounded p-0.5 text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)] hover:text-[var(--rl-text-strong)] disabled:opacity-30"
                              disabled={readOnly || (el.z || 1) >= Math.max(1, ...elements.map((e) => e.z || 1))}
                              title="Bring forward"
                              onClick={() => { selectOnly(el.id); bringForward(); }}
                            >
                              <CaretUp size={13} weight="bold" />
                            </button>
                            <button
                              type="button"
                              className="rounded p-0.5 text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)] hover:text-[var(--rl-text-strong)] disabled:opacity-30"
                              disabled={readOnly || (el.z || 1) <= 1}
                              title="Send backward"
                              onClick={() => { selectOnly(el.id); sendBackward(); }}
                            >
                              <CaretDown size={13} weight="bold" />
                            </button>
                          </>
                        );
                        return (
                          <>
                            {groups.map((group) => {
                              const kids = members(group.id);
                              const open = !collapsedGroups.has(group.id);
                              return (
                                <div key={group.id} className="grid gap-1">
                                  <div className={rowClass(group.id)}>
                                    <button
                                      type="button"
                                      className="rounded p-0.5 text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)]"
                                      onClick={() => setCollapsedGroups((prev) => { const n = new Set(prev); if (n.has(group.id)) n.delete(group.id); else n.add(group.id); return n; })}
                                      title={open ? "Collapse group" : "Expand group"}
                                    >
                                      <CaretDown size={13} weight="bold" className={`transition-transform ${open ? "" : "-rotate-90"}`} />
                                    </button>
                                    <button
                                      type="button"
                                      className="min-w-0 flex-1 truncate text-left font-bold text-[var(--rl-text-strong)]"
                                      onClick={(e) => { if (e.shiftKey) toggleSelect(group.id); else selectOnly(group.id); }}
                                      title={`${group.groupName || layerLabel(group)} (${kids.length})`}
                                    >
                                      <span className="mr-1.5 text-[var(--rl-text-muted)]">z{group.z || 1}</span>
                                      {group.groupName || layerLabel(group)} ({kids.length})
                                    </button>
                                    {zButtons(group)}
                                  </div>
                                  {open ? kids.map((kid) => (
                                    <div key={kid.id} className={`${rowClass(kid.id)} ml-4`}>
                                      {labelButton(kid, true)}
                                      {zButtons(kid)}
                                    </div>
                                  )) : null}
                                </div>
                              );
                            })}
                            {ungrouped.map((el) => (
                              <div key={el.id} className={rowClass(el.id)}>
                                {labelButton(el, false)}
                                {zButtons(el)}
                              </div>
                            ))}
                          </>
                        );
                      })()}
                    </>
                  )}
                </div>
              </div>
            ) : (
              <div className="min-h-0 flex-1 overflow-y-auto p-4">
            <h2 className="font-bold text-[var(--rl-text-strong)]">Properties</h2>
            {selection.length > 1 ? (
              <p className="mt-1 rounded-[var(--rl-radius-sm)] border border-[#3b82f6] bg-[#eff6ff] px-2 py-1.5 text-[12px] font-semibold text-[#3b82f6]">
                Editing 1 of {selection.length} selected — edits apply to the last-clicked element.
              </p>
            ) : null}
            {selected ? (
              <div className="mt-3 grid gap-3">
                {selected.type === "group" ? (
                  <label className="grid gap-1 font-bold">
                    Group name
                    <Input value={selected.groupName || ""} disabled={readOnly} onChange={(event) => updateElement(selected.id, { groupName: event.target.value })} />
                  </label>
                ) : null}
                <div className="grid grid-cols-2 gap-2">
                  {(["x", "y", "w", "h", "z", "opacity"] as const).map((key) => (
                    <label key={key} className="grid gap-1 text-xs font-bold uppercase">
                      {key}
                      <Input
                        type="number"
                        value={key === "opacity" ? (selected.opacity ?? 1) : selected[key] || 0}
                        disabled={readOnly}
                        onChange={(event) => updateElement(selected.id, { [key]: Number(event.target.value) })}
                      />
                    </label>
                  ))}
                  <label className="grid gap-1 text-xs font-bold uppercase">
                    rotate°
                    <Input
                      type="number"
                      value={selected.style?.rotation || 0}
                      disabled={readOnly}
                      onChange={(event) => updateStyle(selected.id, { rotation: Number(event.target.value) })}
                    />
                  </label>
                </div>
                {selected.type === "text" ? (
                  <label className="grid gap-1 font-bold">
                    Text
                    <Textarea
                      className="min-h-24"
                      value={selected.text || ""}
                      disabled={readOnly}
                      onChange={(event) => updateElement(selected.id, { text: event.target.value })}
                    />
                  </label>
                ) : null}
                {selected.type === "variable" ? (
                  <>
                    <label className="grid gap-1 font-bold">
                      Variable
                      <Select
                        value={selected.variableId || ""}
                        disabled={readOnly}
                        onChange={(event) => updateElement(selected.id, { variableId: event.target.value })}
                      >
                        {config?.variables?.map((variable) => <option key={variable.id} value={variable.id}>{variable.label}</option>)}
                      </Select>
                    </label>
                    <Input
                      placeholder="Prefix"
                      value={selected.prefix || ""}
                      disabled={readOnly}
                      onChange={(event) => updateElement(selected.id, { prefix: event.target.value })}
                    />
                    <Input
                      placeholder="Suffix"
                      value={selected.suffix || ""}
                      disabled={readOnly}
                      onChange={(event) => updateElement(selected.id, { suffix: event.target.value })}
                    />
                  </>
                ) : null}
                {selected.type === "image" ? (
                  <>
                    <label className="grid gap-1 font-bold">
                      Asset slot
                      <Select
                        value={selected.assetSlot || ""}
                        disabled={readOnly}
                        onChange={(event) => updateElement(selected.id, { assetSlot: event.target.value, assetId: "" })}
                      >
                        <option value="">Direct asset</option>
                        {assetSlots.map((slot) => <option key={slot} value={slot}>{slot}</option>)}
                      </Select>
                    </label>
                    <label className="grid gap-1 font-bold">
                      Asset
                      <Select
                        value={selected.assetId || ""}
                        disabled={readOnly}
                        onChange={(event) => updateElement(selected.id, { assetId: event.target.value, assetSlot: "" })}
                      >
                        <option value="">Choose asset</option>
                        {assets.map((asset) => <option key={asset.id} value={asset.id}>{asset.label}</option>)}
                      </Select>
                    </label>
                  </>
                ) : null}
                {selected.type === "benefit-section" ? (
                  <>
                    <label className="grid gap-1 font-bold">
                      Section
                      <Select
                        value={selected.section || "specials"}
                        disabled={readOnly}
                        onChange={(event) => updateElement(selected.id, { section: event.target.value as "specials" | "add_ons" })}
                      >
                        <option value="specials">Our Specials</option>
                        <option value="add_ons">You May Add On</option>
                      </Select>
                    </label>
                    <label className="grid gap-1 font-bold">
                      Columns
                      <Input
                        type="number"
                        min={1}
                        max={3}
                        value={selected.columns || 2}
                        disabled={readOnly}
                        onChange={(event) => updateElement(selected.id, { columns: Number(event.target.value) })}
                      />
                    </label>
                  </>
                ) : null}
                {selected.type === "benefit-card" ? (
                  <>
                    <label className="grid gap-1 font-bold">
                      Card
                      <Select
                        value={selected.cardId || ""}
                        disabled={readOnly}
                        onChange={(event) => updateElement(selected.id, { cardId: event.target.value })}
                      >
                        {Object.entries(config?.cards || {}).map(([cardId, card]) => <option key={cardId} value={cardId}>{card.title || cardId}</option>)}
                      </Select>
                    </label>
                    {selectedCard ? <CardEditor cardId={selected.cardId || ""} card={selectedCard} assets={assets} readOnly={readOnly} onChange={(cardId, card) => commit((current) => { current.cards[cardId] = card; return current; })} /> : null}
                  </>
                ) : null}
                {selected.type === "special" ? (
                  <div className="grid gap-2 rounded-md border border-[var(--rl-border)] p-3">
                    <h3 className="font-bold text-[var(--rl-text-strong)]">Our Special variant</h3>
                    {selected.variant_icon_asset_id ? (
                      <img className="mx-auto h-12 w-12 object-contain" src={fileUrl(`/template-assets/${selected.variant_icon_asset_id}`)} alt="" />
                    ) : null}
                    <p className="text-sm font-bold text-[var(--rl-text-strong)]">{selected.variant_label || "Unnamed"}</p>
                    {selected.variant_value_text ? <p className="text-xs text-[var(--rl-text-muted)]">{selected.variant_value_text}</p> : null}
                    {selected.variant_secondary_label ? <p className="text-xs text-[var(--rl-text-muted)]">{selected.variant_secondary_label}</p> : null}
                    <p className="text-[11px] text-[var(--rl-text-muted)]">Card style (colors, border, shape, shadow) is managed in Our Specials.</p>
                  </div>
                ) : null}
                {["text", "variable"].includes(selected.type) ? (
                  <TextStyleEditor style={selected.style} readOnly={readOnly} onChange={(patch) => updateStyle(selected.id, patch)} />
                ) : null}
                {["group", "shape", "box"].includes(selected.type) ? (
                  <BoxStyleEditor style={selected.style} readOnly={readOnly} onChange={(patch) => updateStyle(selected.id, patch)} />
                ) : null}
                {selected.type === "line" ? (
                  <LineStyleEditor style={selected.style} readOnly={readOnly} onChange={(patch) => updateStyle(selected.id, patch)} />
                ) : null}
                {selected.type === "image" ? (
                  <ImageStyleEditor style={selected.style} readOnly={readOnly} onChange={(patch) => updateStyle(selected.id, patch)} />
                ) : null}
                <div className="grid gap-2 rounded-md border border-[var(--rl-border)] p-3">
                  <h3 className="font-bold text-[var(--rl-text-strong)]">Layer</h3>
                  <div className="grid grid-cols-2 gap-2">
                    <Button variant="secondary" size="sm" icon={<CaretDoubleUp weight="bold" size={14} />} disabled={readOnly} onClick={bringToFront}>Front</Button>
                    <Button variant="secondary" size="sm" icon={<CaretUp weight="bold" size={14} />} disabled={readOnly} onClick={bringForward}>Forward</Button>
                    <Button variant="secondary" size="sm" icon={<CaretDown weight="bold" size={14} />} disabled={readOnly} onClick={sendBackward}>Back</Button>
                    <Button variant="secondary" size="sm" icon={<CaretDoubleDown weight="bold" size={14} />} disabled={readOnly} onClick={sendToBack}>Bottom</Button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" size="sm" icon={<CopySimple weight="bold" size={14} />} disabled={readOnly} onClick={duplicateSelection}>Duplicate</Button>
                  <Button variant="danger" size="sm" icon={<Trash weight="bold" size={14} />} disabled={readOnly} onClick={deleteSelection}>Delete</Button>
                </div>
              </div>
            ) : <p className="mt-3 text-sm text-[var(--rl-text-muted)]">Select an element on the canvas.</p>}
              </div>
            )}
          </aside>
        ) : <div />}
      </div>
    </main>
  );
}

type StylePatch = Partial<CanvasStyle>;

function PanelSection({ title, defaultOpen = true, children }: { title: string; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="mt-5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between font-bold text-[var(--rl-text-strong)]"
      >
        {title}
        <CaretDown size={14} weight="bold" className={`text-[var(--rl-text-muted)] transition-transform ${open ? "" : "-rotate-90"}`} />
      </button>
      {open ? <div className="mt-3">{children}</div> : null}
    </section>
  );
}

function EditorShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-2 rounded-md border border-[var(--rl-border)] p-3">
      <h3 className="font-bold text-[var(--rl-text-strong)]">{title}</h3>
      {children}
    </div>
  );
}

function NumField({ label, value, disabled, onChange }: { label: string; value: number; disabled: boolean; onChange: (value: number) => void }) {
  return (
    <label className="grid gap-1 text-xs font-bold uppercase">
      {label}
      <Input type="number" value={value} disabled={disabled} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function ColorField({ label, value, disabled, onChange }: { label: string; value: string; disabled: boolean; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-1 text-xs font-bold uppercase">
      {label}
      <Input className="h-11" type="color" value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function BorderStyleField({ value, disabled, onChange }: { value?: string; disabled: boolean; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-1 text-xs font-bold uppercase">
      Border style
      <Select value={value || "solid"} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        <option value="solid">Solid</option>
        <option value="dashed">Dashed</option>
        <option value="dotted">Dotted</option>
      </Select>
    </label>
  );
}

function ShadowField({ value, disabled, onChange }: { value?: string; disabled: boolean; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-1 text-xs font-bold uppercase">
      Shadow
      <Select value={value || "none"} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        <option value="none">None</option>
        <option value="0 1px 3px rgba(0,0,0,0.12)">Small</option>
        <option value="0 4px 12px rgba(0,0,0,0.15)">Medium</option>
        <option value="0 8px 24px rgba(0,0,0,0.18)">Large</option>
      </Select>
    </label>
  );
}

function BorderFields({ style, readOnly, onChange }: { style?: CanvasStyle; readOnly: boolean; onChange: (patch: StylePatch) => void }) {
  const s = style || {};
  return (
    <>
      <div className="grid grid-cols-2 gap-2">
        <NumField label="Border w" value={s.borderWidth || 0} disabled={readOnly} onChange={(v) => onChange({ borderWidth: v })} />
        <NumField label="Radius" value={s.borderRadius || 0} disabled={readOnly} onChange={(v) => onChange({ borderRadius: v })} />
      </div>
      <BorderStyleField value={s.borderStyle} disabled={readOnly} onChange={(v) => onChange({ borderStyle: v })} />
      <ColorField label="Border color" value={s.borderColor || "#111111"} disabled={readOnly} onChange={(v) => onChange({ borderColor: v })} />
    </>
  );
}

function TextStyleEditor({ style, readOnly, onChange }: { style?: CanvasStyle; readOnly: boolean; onChange: (patch: StylePatch) => void }) {
  const s = style || {};
  return (
    <EditorShell title="Text style">
      <div className="grid grid-cols-2 gap-2">
        <NumField label="Font size" value={s.fontSize || 14} disabled={readOnly} onChange={(v) => onChange({ fontSize: v })} />
        <NumField label="Weight" value={Number(s.fontWeight) || 400} disabled={readOnly} onChange={(v) => onChange({ fontWeight: String(v) })} />
      </div>
      <label className="grid gap-1 text-xs font-bold uppercase">
        Font family
        <Select value={s.fontFamily || ""} disabled={readOnly} onChange={(event) => onChange({ fontFamily: event.target.value || undefined })}>
          <option value="">Default (Inter)</option>
          {FONT_LIBRARY.map((font) => <option key={font} value={font}>{font}</option>)}
        </Select>
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="grid gap-1 text-xs font-bold uppercase">
          Style
          <Select value={s.fontStyle || "normal"} disabled={readOnly} onChange={(event) => onChange({ fontStyle: event.target.value as CanvasStyle["fontStyle"] })}>
            <option value="normal">Normal</option>
            <option value="italic">Italic</option>
          </Select>
        </label>
        <label className="grid gap-1 text-xs font-bold uppercase">
          Case
          <Select value={s.textTransform || "none"} disabled={readOnly} onChange={(event) => onChange({ textTransform: event.target.value as CanvasStyle["textTransform"] })}>
            <option value="none">Normal</option>
            <option value="uppercase">UPPERCASE</option>
            <option value="lowercase">lowercase</option>
            <option value="capitalize">Capitalize</option>
          </Select>
        </label>
      </div>
      <ColorField label="Text color" value={s.color || "#111111"} disabled={readOnly} onChange={(v) => onChange({ color: v })} />
      <label className="grid gap-1 text-xs font-bold uppercase">
        Align
        <Select value={s.textAlign || "left"} disabled={readOnly} onChange={(event) => onChange({ textAlign: event.target.value as CanvasStyle["textAlign"] })}>
          <option value="left">Left</option>
          <option value="center">Center</option>
          <option value="right">Right</option>
        </Select>
      </label>
      <div className="grid grid-cols-2 gap-2">
        <NumField label="Letter space" value={s.letterSpacing || 0} disabled={readOnly} onChange={(v) => onChange({ letterSpacing: v })} />
        <NumField label="Line height" value={s.lineHeight || 1.3} disabled={readOnly} onChange={(v) => onChange({ lineHeight: v })} />
      </div>
      <NumField label="Padding" value={s.padding || 0} disabled={readOnly} onChange={(v) => onChange({ padding: v })} />
      <ColorField label="Background" value={s.background && s.background !== "transparent" ? s.background : "#ffffff"} disabled={readOnly} onChange={(v) => onChange({ background: v })} />
      <BorderFields style={s} readOnly={readOnly} onChange={onChange} />
      <ShadowField value={s.boxShadow} disabled={readOnly} onChange={(v) => onChange({ boxShadow: v })} />
    </EditorShell>
  );
}

function BoxStyleEditor({ style, readOnly, onChange }: { style?: CanvasStyle; readOnly: boolean; onChange: (patch: StylePatch) => void }) {
  const s = style || {};
  return (
    <EditorShell title="Box style">
      <ColorField label="Background" value={s.background && s.background !== "transparent" ? s.background : "#ffffff"} disabled={readOnly} onChange={(v) => onChange({ background: v })} />
      <BorderFields style={s} readOnly={readOnly} onChange={onChange} />
      <ShadowField value={s.boxShadow} disabled={readOnly} onChange={(v) => onChange({ boxShadow: v })} />
      <NumField label="Padding" value={s.padding || 0} disabled={readOnly} onChange={(v) => onChange({ padding: v })} />
    </EditorShell>
  );
}

function LineStyleEditor({ style, readOnly, onChange }: { style?: CanvasStyle; readOnly: boolean; onChange: (patch: StylePatch) => void }) {
  const s = style || {};
  return (
    <EditorShell title="Line style">
      <ColorField label="Color" value={s.color || "#111111"} disabled={readOnly} onChange={(v) => onChange({ color: v })} />
      <BorderStyleField value={s.borderStyle} disabled={readOnly} onChange={(v) => onChange({ borderStyle: v })} />
      <p className="text-[11px] text-[var(--rl-text-muted)]">Thickness is the element height (drag the bottom handle).</p>
    </EditorShell>
  );
}

function ImageStyleEditor({ style, readOnly, onChange }: { style?: CanvasStyle; readOnly: boolean; onChange: (patch: StylePatch) => void }) {
  const s = style || {};
  return (
    <EditorShell title="Image style">
      <BorderFields style={s} readOnly={readOnly} onChange={onChange} />
      <ShadowField value={s.boxShadow} disabled={readOnly} onChange={(v) => onChange({ boxShadow: v })} />
      <p className="text-[11px] text-[var(--rl-text-muted)]">Rotation and opacity are in the common fields above.</p>
    </EditorShell>
  );
}

function CardEditor({ cardId, card, assets, readOnly, onChange }: { cardId: string; card: BenefitCard; assets: AssetRecord[]; readOnly: boolean; onChange: (cardId: string, card: BenefitCard) => void }) {
  function patch(update: Partial<BenefitCard>) { onChange(cardId, { ...card, ...update }); }
  return (
    <div className="grid gap-2 rounded-md border border-[var(--rl-border)] p-3">
      <h3 className="font-bold text-[var(--rl-text-strong)]">Card content</h3>
      <Input value={card.title || ""} disabled={readOnly} onChange={(event) => patch({ title: event.target.value })} />
      <Input value={card.subtitle || ""} disabled={readOnly} onChange={(event) => patch({ subtitle: event.target.value })} />
      <Textarea className="min-h-20" value={(card.lines || []).join("\n")} disabled={readOnly} onChange={(event) => patch({ lines: event.target.value.split(/\r?\n/).filter(Boolean) })} />
      <Select value={card.asset_id || ""} disabled={readOnly} onChange={(event) => patch({ asset_id: event.target.value })}>
        <option value="">Auto icon asset</option>
        {assets.map((asset) => <option key={asset.id} value={asset.id}>{asset.label}</option>)}
      </Select>
    </div>
  );
}
