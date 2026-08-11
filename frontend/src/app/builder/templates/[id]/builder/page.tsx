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
  ClipboardText,
  CodeSimple,
  CopySimple,
  Diamond,
  FloppyDisk,
  FolderSimple,
  GridFour,
  Image,
  LineSegment,
  LockSimple,
  LockSimpleOpen,
  MagnifyingGlass,
  Plus,
  Square,
  Star,
  TextIndent,
  TextOutdent,
  TextT,
  Trash,
  Triangle,
  UploadSimple,
  X,
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
  const [draftText, setDraftText] = useState("");
  const [rightTab, setRightTab] = useState<"layers" | "properties">("layers");
  const [showLeft, setShowLeft] = useState(true);
  const [showRight, setShowRight] = useState(true);
  const [leftWidth, setLeftWidth] = useState(280);
  const [rightWidth, setRightWidth] = useState(320);
  const [editingTextId, setEditingTextId] = useState<string | null>(null);
  const [rulerGuides, setRulerGuides] = useState<{ x: number[]; y: number[] }>({ x: [], y: [] });
  const [rulerDrag, setRulerDrag] = useState<{ axis: "x" | "y"; pos: number; active: boolean } | null>(null);
  const [marquee, setMarquee] = useState<{ startX: number; startY: number; curX: number; curY: number } | null>(null);
  const [drawLineMode, setDrawLineMode] = useState(false);
  const [lineThickness, setLineThickness] = useState(2);
  const [drawPreview, setDrawPreview] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const drawRef = useRef<{ x: number; y: number } | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const [dragOverGroup, setDragOverGroup] = useState<string | null>(null);
  const suppressClickRef = useRef(false);
  const [zoom, setZoom] = useState(0.72);
  const [error, setError] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState("");
  const [importError, setImportError] = useState("");
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
  const canvasW = config?.canvas.width || 794;
  const canvasH = config?.canvas.height || 1123;
  const selected = elements.find((item) => item.id === primaryId) || null;
  const selection = elements.filter((item) => selectedIds.has(item.id));
  const readOnly = Boolean(template?.locked) || previewMode;
  const selectedCard = selected?.cardId && config?.cards ? config.cards[selected.cardId] : null;
  const sortedElements = useMemo(() => [...elements].sort((a, b) => (a.z || 1) - (b.z || 1)), [elements]);

  function nextZ() {
    return Math.max(1, ...elements.map((item) => item.z || 1)) + 1;
  }

  function selectedGroupIds() {
    return new Set(selection.filter((e) => e.type === "group").map((e) => e.id));
  }

  function buildSpecialElement(variant: VariantItem, x: number, y: number): CanvasElement {
    return {
      id: makeId("special"),
      type: "special",
      x, y, w: 160, h: 80,
      z: nextZ(),
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
  }

  useEffect(() => {
    setDraftText(selected?.text || "");
  }, [selected?.id]);

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

  function assignToGroup(elementId: string, groupId: string | null) {
    if (readOnly) return;
    const source = elements.find((e) => e.id === elementId);
    if (!source || source.type === "group") return;
    const targets = selection.length > 1 && selectedIds.has(elementId)
      ? selection.filter((e) => e.type !== "group").map((e) => e.id)
      : [elementId];
    updateElements(new Set(targets), () => ({ groupId: groupId ?? undefined }));
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
    const element = buildSpecialElement(variant, 80, 120);
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
      const element = buildSpecialElement(variant, Math.round(dx - 24), Math.round(dy - 24));
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
      z: nextZ(),
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
    const ids = new Set(selection.filter((e) => !e.locked).map((e) => e.id));
    const groupIds = new Set(selection.filter((e) => e.type === "group").map((e) => e.id));
    for (const el of elements) {
      if (el.groupId && groupIds.has(el.groupId) && !el.locked) ids.add(el.id);
    }
    return ids;
  }

  function toggleLock(id: string) {
    if (readOnly) return;
    const target = elements.find((e) => e.id === id);
    if (!target) return;
    const next = !target.locked;
    updateElements(new Set([id]), () => ({ locked: next }));
    if (next && selectedIds.has(id)) {
      setSelectedIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
      if (primaryId === id) setPrimaryId("");
    }
  }

  function deleteSelection() {
    if (!selectedIds.size || readOnly) return;
    const groupIds = new Set(selection.filter((e) => e.type === "group").map((e) => e.id));
    const targets = new Set(selection.filter((e) => !e.locked).map((e) => e.id));
    commit((current) => {
      current.canvas.elements = current.canvas.elements
        .filter((item) => !targets.has(item.id))
        .filter((item) => !(item.groupId && groupIds.has(item.groupId)));
      return current;
    });
    clearSelection();
  }

  function duplicateSelection() {
    if (!selectedIds.size || readOnly) return;
    const idMap = new Map<string, string>();
    const copies = selection.filter((el) => !el.locked).map((el) => {
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
    const members = selection.filter((e) => e.type !== "group" && !e.locked);
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
      current.canvas.elements = current.canvas.elements.map((e) => members.some((m) => m.id === e.id) ? { ...e, groupId: gid } : e);
      current.canvas.elements.push(groupEl);
      return current;
    });
    selectOnly(gid);
  }

  function ungroup() {
    const groupIds = selectedGroupIds();
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
    const max = axis === "x" ? (canvasW) : (canvasH);
    return Math.max(0, Math.min(max, pos));
  }

  function startPanelResize(side: "left" | "right") {
    return (event: React.PointerEvent) => {
      event.preventDefault();
      if (side === "left" && !showLeft) setShowLeft(true);
      if (side === "right" && !showRight) setShowRight(true);
      const startX = event.clientX;
      const startWidth = side === "left" ? leftWidth : rightWidth;
      const onMove = (e: PointerEvent) => {
        const dx = e.clientX - startX;
        const width = side === "left" ? startWidth + dx : startWidth - dx;
        const clamped = Math.max(200, Math.min(520, width));
        if (side === "left") setLeftWidth(clamped);
        else setRightWidth(clamped);
      };
      const onUp = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    };
  }

  function removeRulerGuide(axis: "x" | "y", pos: number) {
    setRulerGuides((current) => ({ ...current, [axis]: current[axis].filter((p) => p !== pos) }));
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
    if (drawLineMode) return;
    if (element.locked) return;
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
      if (!event.altKey) {
        const { value: sx, guide: gx } = snapValue(nx, SNAP, []);
        const { value: sy, guide: gy } = snapValue(ny, SNAP, []);
        nx = gx ?? sx;
        ny = gy ?? sy;
      }
      const guides = event.altKey ? [] : computeGuides(drag.start, { x: nx, y: ny }, elements, canvasW, canvasW / 2);
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
      const guides = computeGuides(drag.start, patch, elements, canvasW, (canvasW) / 2);
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
    if (drawLineMode) {
      drawRef.current = {
        x: Math.max(0, Math.min(canvasW, (event.clientX - rect.left) / zoom)),
        y: Math.max(0, Math.min(canvasH, (event.clientY - rect.top) / zoom)),
      };
      setDrawPreview({ x: drawRef.current.x, y: drawRef.current.y, w: lineThickness, h: lineThickness });
      return;
    }
    setMarquee({
      startX: (event.clientX - rect.left) / zoom,
      startY: (event.clientY - rect.top) / zoom,
      curX: (event.clientX - rect.left) / zoom,
      curY: (event.clientY - rect.top) / zoom,
    });
  }

  function canvasPointerMove(event: React.PointerEvent) {
    if (drawLineMode && drawRef.current) {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const cx = Math.max(0, Math.min(canvasW, (event.clientX - rect.left) / zoom));
      const cy = Math.max(0, Math.min(canvasH, (event.clientY - rect.top) / zoom));
      const s = drawRef.current;
      const dx = cx - s.x;
      const dy = cy - s.y;
      if (Math.abs(dx) >= Math.abs(dy)) {
        setDrawPreview({ x: Math.min(s.x, cx), y: s.y - (lineThickness - 2) / 2, w: Math.max(2, Math.abs(dx)), h: lineThickness });
      } else {
        setDrawPreview({ x: s.x - (lineThickness - 2) / 2, y: Math.min(s.y, cy), w: lineThickness, h: Math.max(2, Math.abs(dy)) });
      }
      return;
    }
    if (!marquee) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    setMarquee((m) => m ? {
      ...m,
      curX: Math.max(0, Math.min((canvasW), (event.clientX - rect.left) / zoom)),
      curY: Math.max(0, Math.min((canvasH), (event.clientY - rect.top) / zoom)),
    } : m);
  }

  function finishDrawLine() {
    if (!drawLineMode || !drawRef.current) return;
    const s = drawRef.current;
    const p = drawPreview || { x: s.x, y: s.y, w: lineThickness, h: lineThickness };
    const element: CanvasElement = {
      id: makeId("line"),
      type: "line",
      x: Math.round(p.x),
      y: Math.round(p.y),
      w: Math.max(lineThickness, Math.round(p.w)),
      h: Math.max(lineThickness, Math.round(p.h)),
      z: Math.max(1, ...elements.map((item) => item.z || 1)) + 1,
      style: defaultStyle("line"),
    };
    commit((current) => { current.canvas.elements.push(element); return current; });
    selectOnly(element.id);
    drawRef.current = null;
    setDrawPreview(null);
    setDrawLineMode(false);
  }

  function canvasPointerUp() {
    if (drawLineMode) {
      finishDrawLine();
      return;
    }
    if (!marquee) return;
    const x0 = Math.min(marquee.startX, marquee.curX);
    const y0 = Math.min(marquee.startY, marquee.curY);
    const x1 = Math.max(marquee.startX, marquee.curX);
    const y1 = Math.max(marquee.startY, marquee.curY);
    setMarquee(null);
    if (x1 - x0 < 4 && y1 - y0 < 4) return;
    const hits = elements.filter((el) => !el.locked && el.x < x1 && el.x + el.w > x0 && el.y < y1 && el.y + el.h > y0).map((el) => el.id);
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

  function exportTemplateJson() {
    if (!template) return;
    const blob = new Blob([JSON.stringify(template.fixed_fields, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${template.name.replace(/[^a-z0-9]+/gi, "_").toLowerCase() || "template"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function applyImportedConfig(config: TemplateConfig): boolean {
    const raw = JSON.parse(importText) as unknown;
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      setImportError("The JSON must be an object with a canvas section.");
      return false;
    }
    const input = raw as Record<string, unknown>;
    const canvas = input.canvas as Record<string, unknown> | undefined;
    if (!canvas || typeof canvas !== "object" || !Array.isArray(canvas.elements)) {
      setImportError("Missing or invalid \"canvas.elements\" array.");
      return false;
    }
    const knownTypes = new Set(["text", "variable", "image", "line", "group", "shape", "benefit-section", "benefit-card", "special"]);
    const num = (value: unknown, fallback: number) => (typeof value === "number" && Number.isFinite(value) ? value : fallback);
    const str = (value: unknown) => (typeof value === "string" ? value : undefined);
    const elements = (canvas.elements as unknown[]).map((entry, index) => {
      const el = entry as Record<string, unknown>;
      if (!el || typeof el !== "object" || !knownTypes.has(String(el.type))) {
        throw new Error(`Element ${index + 1} has an unknown type "${String(el?.type)}".`);
      }
      return {
        ...el,
        id: str(el.id) || `imported_${index + 1}_${Math.random().toString(36).slice(2, 7)}`,
        type: String(el.type),
        x: num(el.x, 80),
        y: num(el.y, 120),
        w: num(el.w, 180),
        h: num(el.h, 48),
        z: el.z === undefined ? undefined : num(el.z, 1),
      };
    });
    const imported: TemplateConfig = {
      ...(config || {}),
      ...input,
      canvas: {
        width: num(canvas.width, canvasW),
        height: num(canvas.height, canvasH),
        elements,
      },
    };
    // An imported layout never locks or defaults the current template.
    (imported as Record<string, unknown>).is_default = false;
    (imported as Record<string, unknown>).locked = false;
    if (!imported.variables || !imported.variables.length) imported.variables = config?.variables || [];
    setTemplate((current) => current ? { ...current, fixed_fields: imported } : current);
    return true;
  }

  function importTemplate() {
    setImportError("");
    try {
      if (applyImportedConfig(config as TemplateConfig)) {
        toast("Template layout imported. Review it, then Save to persist.", "success");
        setShowImport(false);
      }
    } catch (err) {
      setImportError(err instanceof Error ? err.message : "The JSON could not be read.");
    }
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
      const meta = event.ctrlKey || event.metaKey;
      if (meta && event.key.toLowerCase() === "z") { event.preventDefault(); if (event.shiftKey) redo(); else undo(); return; }
      if (meta && event.key.toLowerCase() === "y") { event.preventDefault(); redo(); return; }
      if (meta && event.key.toLowerCase() === "d") { event.preventDefault(); duplicateSelection(); return; }
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable)) {
        return;
      }
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
            icon={<CodeSimple weight="bold" size={14} />}
            onClick={exportTemplateJson}
            title="Download the template layout as JSON"
            disabled={!template}
          >
            Export JSON
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={<ClipboardText weight="bold" size={14} />}
            onClick={() => { setImportText(""); setImportError(""); setShowImport(true); }}
            title="Paste a JSON layout generated by an AI or exported from another template"
            disabled={readOnly}
          >
            Import JSON
          </Button>
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

      <div
        className="grid min-h-0 flex-1"
        style={{
          gridTemplateColumns: `${showLeft && !previewMode ? leftWidth : 0}px 6px minmax(0,1fr) 6px ${showRight && !previewMode ? rightWidth : 0}px`,
          transition: "grid-template-columns 160ms ease",
        }}
      >
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

        <div
          className="z-10 cursor-col-resize border-x border-[var(--rl-border)] bg-[var(--rl-bg)] transition-colors hover:bg-[var(--rl-border)]"
          onPointerDown={startPanelResize("left")}
          title="Drag to resize the left panel"
        />

        <section className="flex overflow-auto p-6">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-[var(--rl-text-strong)]">Canvas</span>
              <Button
                variant={drawLineMode ? "primary" : "secondary"}
                size="sm"
                icon={<LineSegment weight="bold" size={14} />}
                onClick={() => { setDrawLineMode((v) => !v); setDrawPreview(null); drawRef.current = null; }}
                title={drawLineMode ? "Click and drag on the canvas to draw a straight line" : "Draw a line by dragging on the canvas"}
              >
                {drawLineMode ? "Drawing… (click canvas)" : "Draw line"}
              </Button>
              {drawLineMode ? (
                <div className="flex items-center gap-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-1">
                  {[1, 2, 4, 6].map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setLineThickness(t)}
                      title={`${t}px line`}
                      className={`grid h-6 w-6 place-items-center rounded-[var(--rl-radius-sm)] transition-colors ${lineThickness === t ? "bg-[var(--rl-black)]" : "hover:bg-[var(--rl-bg)]"}`}
                    >
                      <span className="rounded-full bg-current" style={{ width: Math.max(2, t), height: Math.max(2, t), color: lineThickness === t ? "#fff" : "#6e6e73" }} />
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm font-bold">
                Zoom
                <input className="w-32" type="range" min="0.25" max="2" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} />
              </label>
              {rulerGuides.x.length + rulerGuides.y.length > 0 ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setRulerGuides({ x: [], y: [] })}
                  title="Remove all guides"
                >
                  Clear guides ({rulerGuides.x.length + rulerGuides.y.length})
                </Button>
              ) : null}
            </div>
          </div>
          <div className="m-auto w-fit flex-shrink-0 rounded-md bg-neutral-300 p-6 shadow-inner" style={{ minHeight: ((canvasH) * zoom) + 60 }}>
            <div className="relative" style={{ width: (canvasW) * zoom, height: (canvasH) * zoom }}>
              {!previewMode ? (
                <>
                  <div className="absolute -top-6 left-0 h-5 w-full select-none overflow-hidden border-b border-[var(--rl-border)] bg-[var(--rl-surface)]"
                    onPointerDown={(event) => startRulerDrag(event, "x")}
                    onPointerMove={(event) => moveRulerDrag(event)}
                    onPointerUp={endRulerDrag}
                    onContextMenu={(event) => {
                      event.preventDefault();
                      const rect = canvasRef.current?.getBoundingClientRect();
                      if (!rect) return;
                      const pos = (event.clientX - rect.left) / zoom;
                      const nearest = rulerGuides.x.reduce<number | null>((best, g) => (Math.abs(g - pos) <= 6 && (best === null || Math.abs(g - pos) < Math.abs(best - pos)) ? g : best), null);
                      if (nearest !== null) removeRulerGuide("x", nearest);
                    }}
                  >
                    {Array.from({ length: Math.ceil((canvasW) / 25) + 1 }, (_, i) => {
                      const px = i * 25 * zoom;
                      const major = i % 4 === 0;
                      return <span key={i} className={`absolute top-0 ${major ? "h-3 w-px" : "h-1.5 w-px"} bg-[var(--rl-text-muted)]`} style={{ left: px }} />;
                    })}
                    {Array.from({ length: Math.ceil((canvasW) / 100) + 1 }, (_, i) => (
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
                    onContextMenu={(event) => {
                      event.preventDefault();
                      const rect = canvasRef.current?.getBoundingClientRect();
                      if (!rect) return;
                      const pos = (event.clientY - rect.top) / zoom;
                      const nearest = rulerGuides.y.reduce<number | null>((best, g) => (Math.abs(g - pos) <= 6 && (best === null || Math.abs(g - pos) < Math.abs(best - pos)) ? g : best), null);
                      if (nearest !== null) removeRulerGuide("y", nearest);
                    }}
                  >
                    {Array.from({ length: Math.ceil((canvasH) / 25) + 1 }, (_, i) => {
                      const py = i * 25 * zoom;
                      const major = i % 4 === 0;
                      return <span key={i} className={`absolute left-0 ${major ? "w-3 h-px" : "w-1.5 h-px"} bg-[var(--rl-text-muted)]`} style={{ top: py }} />;
                    })}
                    {Array.from({ length: Math.ceil((canvasH) / 100) + 1 }, (_, i) => (
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
                style={{ width: canvasW, height: canvasH, transform: `scale(${zoom})` }}
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
                {drawPreview ? (
                  <>
                    <div
                      className="pointer-events-none absolute bg-[#3b82f6]"
                      style={{ left: drawPreview.x, top: drawPreview.y, width: drawPreview.w, height: drawPreview.h, zIndex: 9997 }}
                    />
                    <div
                      className="pointer-events-none absolute h-2 w-2 rounded-full border-2 border-[#3b82f6] bg-white"
                      style={{ left: drawPreview.x - 4, top: drawPreview.y + drawPreview.h / 2 - 4, zIndex: 9997 }}
                    />
                    <div
                      className="pointer-events-none absolute h-2 w-2 rounded-full border-2 border-[#3b82f6] bg-white"
                      style={{ left: drawPreview.x + drawPreview.w - 4, top: drawPreview.y + drawPreview.h / 2 - 4, zIndex: 9997 }}
                    />
                  </>
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

        <div
          className="z-10 cursor-col-resize border-x border-[var(--rl-border)] bg-[var(--rl-bg)] transition-colors hover:bg-[var(--rl-border)]"
          onPointerDown={startPanelResize("right")}
          title="Drag to resize the inspector panel"
        />

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
                <p className="mt-1 text-[12px] text-[var(--rl-text-muted)]">
                  Top of the list sits on top of the canvas. Tick boxes or Shift-click to multi-select; drag a row onto a group folder to organise.
                </p>
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
                        const members = (gid: string) => elements.filter((e) => e.groupId === gid && e.type !== "group").sort((a, b) => (b.z || 1) - (a.z || 1));
                        const ungrouped = elements.filter((e) => !e.groupId && e.type !== "group").sort((a, b) => (b.z || 1) - (a.z || 1));
                        const rowClass = (id: string) => `flex items-center gap-1 rounded border px-1.5 py-1 text-xs transition-colors ${selectedIds.has(id) ? "border-[#3b82f6] bg-[#eff6ff]" : "border-[var(--rl-border)] bg-[var(--rl-surface)] hover:bg-[var(--rl-bg)]"}`;
                        const typeIcon = (el: CanvasElement) => {
                          switch (el.type) {
                            case "group": return <FolderSimple size={13} weight="bold" className="shrink-0 text-[var(--rl-text-muted)]" />;
                            case "text": return <TextT size={13} weight="bold" className="shrink-0 text-[var(--rl-text-muted)]" />;
                            case "variable": return <BracketsCurly size={13} weight="bold" className="shrink-0 text-[var(--rl-red)]" />;
                            case "image": return <Image size={13} weight="bold" className="shrink-0 text-[var(--rl-text-muted)]" />;
                            case "line": return <LineSegment size={13} weight="bold" className="shrink-0 text-[var(--rl-text-muted)]" />;
                            case "special": return <Star size={13} weight="bold" className="shrink-0 text-[var(--rl-text-muted)]" />;
                            default: return <Square size={13} weight="bold" className="shrink-0 text-[var(--rl-text-muted)]" />;
                          }
                        };
                        const dragProps = (el: CanvasElement) => ({
                          draggable: !readOnly,
                          onDragStart: (event: React.DragEvent) => {
                            event.dataTransfer.setData("application/risklocker-layer", el.id);
                            event.dataTransfer.effectAllowed = "move";
                          },
                        });
                        const dropProps = (groupId: string | null) => ({
                          onDragOver: (event: React.DragEvent) => event.preventDefault(),
                          onDragEnter: () => setDragOverGroup(groupId),
                          onDragLeave: () => setDragOverGroup((current) => (current === groupId ? null : current)),
                          onDrop: (event: React.DragEvent) => {
                            event.preventDefault();
                            setDragOverGroup(null);
                            const id = event.dataTransfer.getData("application/risklocker-layer");
                            if (id) assignToGroup(id, groupId);
                          },
                        });
                        const checkbox = (el: CanvasElement) => (
                          <input
                            type="checkbox"
                            aria-label={`Select ${layerLabel(el)}`}
                            className="h-3.5 w-3.5 shrink-0 accent-[var(--rl-red)]"
                            checked={selectedIds.has(el.id)}
                            onChange={() => toggleSelect(el.id)}
                            onClick={(e) => e.stopPropagation()}
                          />
                        );
                        const labelButton = (el: CanvasElement, indent: boolean) => (
                          <button
                            type="button"
                            className={`flex min-w-0 flex-1 items-center gap-1.5 truncate text-left font-medium text-[var(--rl-text-strong)] ${indent ? "pl-2" : ""}`}
                            onClick={(e) => { if (e.shiftKey) toggleSelect(el.id); else selectOnly(el.id); }}
                            title={layerLabel(el)}
                          >
                            {typeIcon(el)}
                            <span className="shrink-0 text-[10px] text-[var(--rl-text-muted)]">z{el.z || 1}</span>
                            <span className="truncate">{layerLabel(el)}</span>
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
                        const lockButton = (el: CanvasElement) => (
                          <button
                            type="button"
                            className={`rounded p-0.5 ${el.locked ? "text-[var(--rl-red)]" : "text-[var(--rl-text-muted)]"} hover:bg-[var(--rl-bg)]`}
                            disabled={readOnly}
                            title={el.locked ? "Unlock layer" : "Lock layer (cannot be selected, moved or deleted)"}
                            onClick={(e) => { e.stopPropagation(); toggleLock(el.id); }}
                          >
                            {el.locked ? <LockSimple size={13} weight="fill" /> : <LockSimpleOpen size={13} weight="bold" />}
                          </button>
                        );
                        return (
                          <>
                            {groups.length > 0 ? (
                              <div className="grid gap-1">
                                <h3 className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">Groups ({groups.length})</h3>
                                {groups.map((group) => {
                                  const kids = members(group.id);
                                  const open = !collapsedGroups.has(group.id);
                                  const dropActive = dragOverGroup === group.id;
                                  return (
                                    <div key={group.id} className="grid gap-1">
                                      <div
                                        className={`${rowClass(group.id)} ${dropActive ? "border-[#3b82f6] bg-[#dbeafe]" : ""}`}
                                        {...dropProps(group.id)}
                                        {...dragProps(group)}
                                      >
                                        <button
                                          type="button"
                                          className="rounded p-0.5 text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)]"
                                          onClick={() => setCollapsedGroups((prev) => { const n = new Set(prev); if (n.has(group.id)) n.delete(group.id); else n.add(group.id); return n; })}
                                          title={open ? "Collapse group" : "Expand group"}
                                        >
                                          <CaretDown size={13} weight="bold" className={`transition-transform ${open ? "" : "-rotate-90"}`} />
                                        </button>
                                        {checkbox(group)}
                                        {typeIcon(group)}
                                        <button
                                          type="button"
                                          className="min-w-0 flex-1 truncate text-left font-bold text-[var(--rl-text-strong)]"
                                          onClick={(e) => { if (e.shiftKey) toggleSelect(group.id); else selectOnly(group.id); }}
                                          title={`${group.groupName || layerLabel(group)} (${kids.length})`}
                                        >
                                          <span className="mr-1.5 text-[10px] text-[var(--rl-text-muted)]">z{group.z || 1}</span>
                                          {group.groupName || layerLabel(group)} ({kids.length})
                                        </button>
                                        {zButtons(group)}
                                        {lockButton(group)}
                                      </div>
                                      {open ? (
                                        <div className={`ml-3 border-l border-[var(--rl-border)] pl-1.5 ${dropActive ? "rounded-r border-[#3b82f6] bg-[#dbeafe]/60" : ""}`} {...dropProps(group.id)}>
                                          {kids.map((kid) => (
                                            <div key={kid.id} className={`${rowClass(kid.id)} mb-1`} {...(!kid.locked ? dragProps(kid) : {})}>
                                              {checkbox(kid)}
                                              {labelButton(kid, true)}
                                              {zButtons(kid)}
                                              {lockButton(kid)}
                                            </div>
                                          ))}
                                          {kids.length === 0 ? (
                                            <p className="px-1 py-1 text-[11px] italic text-[var(--rl-text-muted)]">Empty — drag elements here to add them to this group.</p>
                                          ) : null}
                                        </div>
                                      ) : null}
                                    </div>
                                  );
                                })}
                              </div>
                            ) : null}
                            {ungrouped.length > 0 ? (
                              <div className="grid gap-1">
                                <h3
                                  className={`text-[11px] font-bold uppercase tracking-wider ${dragOverGroup === null ? "text-[var(--rl-red)]" : "text-[var(--rl-text-muted)]"}`}
                                  {...dropProps(null)}
                                >
                                  Ungrouped ({ungrouped.length})
                                </h3>
                                {ungrouped.map((el) => (
                                  <div key={el.id} className={rowClass(el.id)} {...(!el.locked ? dragProps(el) : {})}>
                                    {checkbox(el)}
                                    {labelButton(el, false)}
                                    {zButtons(el)}
                                    {lockButton(el)}
                                  </div>
                                ))}
                              </div>
                            ) : null}
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
                {selected.locked ? (
                  <div className="flex items-center justify-between rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] px-3 py-2">
                    <span className="flex items-center gap-1.5 text-[12px] font-semibold text-[var(--rl-text-muted)]">
                      <LockSimple size={14} weight="fill" /> This layer is locked
                    </span>
                    <button
                      type="button"
                      className="text-[12px] font-bold text-[var(--rl-red)] hover:underline"
                      onClick={() => toggleLock(selected.id)}
                    >
                      Unlock
                    </button>
                  </div>
                ) : null}
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
                        disabled={readOnly || Boolean(selected.locked)}
                        onChange={(event) => updateElement(selected.id, { [key]: Number(event.target.value) })}
                      />
                    </label>
                  ))}
                  <label className="grid gap-1 text-xs font-bold uppercase">
                    rotate°
                    <Input
                      type="number"
                      value={selected.style?.rotation || 0}
                      disabled={readOnly || Boolean(selected.locked)}
                      onChange={(event) => updateStyle(selected.id, { rotation: Number(event.target.value) })}
                    />
                  </label>
                </div>
                {selected.type === "shape" ? (
                  <label className="grid gap-1 font-bold">
                    Shape
                    <Select
                      value={selected.shapeKind || ""}
                      disabled={readOnly || Boolean(selected.locked)}
                      onChange={(event) => updateElement(selected.id, { shapeKind: (event.target.value || undefined) as CanvasElement["shapeKind"] })}
                    >
                      <option value="">Rectangle</option>
                      <option value="circle">Circle</option>
                      <option value="triangle">Triangle</option>
                      <option value="diamond">Diamond</option>
                    </Select>
                  </label>
                ) : null}
                {selected.type === "line" ? (
                  <div className="grid grid-cols-3 gap-2">
                    <label className="grid gap-1 text-xs font-bold uppercase">
                      Length
                      <Input type="number" value={Math.round(selected.w)} disabled={readOnly || Boolean(selected.locked)} onChange={(event) => updateElement(selected.id, { w: Math.max(2, Number(event.target.value) || 2) })} />
                    </label>
                    <label className="grid gap-1 text-xs font-bold uppercase">
                      Thickness
                      <Input type="number" value={Math.round(selected.h)} disabled={readOnly || Boolean(selected.locked)} onChange={(event) => updateElement(selected.id, { h: Math.max(1, Number(event.target.value) || 1) })} />
                    </label>
                    <label className="grid gap-1 text-xs font-bold uppercase">
                      Angle°
                      <Input type="number" value={selected.style?.rotation || 0} disabled={readOnly || Boolean(selected.locked)} onChange={(event) => updateStyle(selected.id, { rotation: Number(event.target.value) })} />
                    </label>
                  </div>
                ) : null}
                {selected.type === "text" ? (
                  <label className="grid gap-1 font-bold">
                    Text
                    <Textarea
                      className="min-h-24"
                      value={draftText}
                      disabled={readOnly || Boolean(selected.locked)}
                      onChange={(event) => setDraftText(event.target.value)}
                      onBlur={() => {
                        if (draftText !== (selected.text || "")) updateElement(selected.id, { text: draftText });
                      }}
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
                  <TextStyleEditor style={selected.style} readOnly={readOnly || Boolean(selected.locked)} onChange={(patch) => updateStyle(selected.id, patch)} />
                ) : null}
                {["group", "shape", "box"].includes(selected.type) ? (
                  <BoxStyleEditor style={selected.style} readOnly={readOnly || Boolean(selected.locked)} onChange={(patch) => updateStyle(selected.id, patch)} />
                ) : null}
                {selected.type === "line" ? (
                  <LineStyleEditor style={selected.style} readOnly={readOnly || Boolean(selected.locked)} thickness={selected.h} onThickness={(v) => updateElement(selected.id, { h: Math.max(1, v) })} onChange={(patch) => updateStyle(selected.id, patch)} />
                ) : null}
                {selected.type === "image" ? (
                  <ImageStyleEditor style={selected.style} readOnly={readOnly || Boolean(selected.locked)} onChange={(patch) => updateStyle(selected.id, patch)} />
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

      {showImport ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowImport(false)}>
          <div className="w-full max-w-2xl rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-6 shadow-card" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Import template layout (JSON)</h2>
              <button type="button" className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)]" onClick={() => setShowImport(false)}>
                <X size={16} weight="bold" />
              </button>
            </div>
            <p className="mt-2 text-[13px] text-[var(--rl-text-muted)]">
              Paste JSON generated by an AI (export any template here as an example) or exported from another template.
              Only <code className="rounded bg-[var(--rl-bg)] px-1">canvas.elements</code> is required — variables and other
              sections are optional and merge with this template. Imported layouts never lock the template.
              Nothing is saved until you click Save.
            </p>
            <Textarea
              className="mt-3 min-h-64 font-mono text-[12px]"
              placeholder='{"canvas": {"width": 794, "height": 1123, "elements": [{"type": "text", "x": 80, "y": 120, "w": 180, "h": 48, "text": "Hello"}]}}'
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
            />
            {importError ? (
              <p className="mt-2 rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2 text-[13px] font-semibold text-[var(--rl-red)]">{importError}</p>
            ) : null}
            <div className="mt-4 flex gap-2">
              <Button icon={<ClipboardText weight="bold" size={14} />} onClick={importTemplate}>Import into canvas</Button>
              <Button variant="secondary" onClick={() => setShowImport(false)}>Cancel</Button>
            </div>
          </div>
        </div>
      ) : null}
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
  const weight = Number(s.fontWeight) || 400;
  return (
    <EditorShell title="Text style">
      <div className="grid grid-cols-2 gap-2">
        <NumField label="Font size" value={s.fontSize || 14} disabled={readOnly} onChange={(v) => onChange({ fontSize: v })} />
        <label className="grid gap-1 text-xs font-bold uppercase">
          Weight
          <Select value={String(weight)} disabled={readOnly} onChange={(event) => onChange({ fontWeight: event.target.value })}>
            <option value="100">Thin (100)</option>
            <option value="300">Light (300)</option>
            <option value="400">Regular (400)</option>
            <option value="500">Medium (500)</option>
            <option value="600">Semibold (600)</option>
            <option value="700">Bold (700)</option>
            <option value="800">Extra bold (800)</option>
            <option value="900">Black (900)</option>
          </Select>
        </label>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          disabled={readOnly}
          onClick={() => onChange({ fontWeight: weight >= 700 ? "400" : "700" })}
          className={`rounded-[var(--rl-radius-sm)] border px-3 py-2 text-[13px] font-bold transition-all disabled:opacity-40 ${weight >= 700 ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white" : "border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:bg-[var(--rl-bg)]"}`}
        >
          Bold {weight >= 700 ? "on" : "off"}
        </button>
        <button
          type="button"
          disabled={readOnly}
          onClick={() => onChange({ fontStyle: s.fontStyle === "italic" ? "normal" : "italic" })}
          className={`rounded-[var(--rl-radius-sm)] border px-3 py-2 text-[13px] font-bold italic transition-all disabled:opacity-40 ${s.fontStyle === "italic" ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white" : "border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:bg-[var(--rl-bg)]"}`}
        >
          Italic {s.fontStyle === "italic" ? "on" : "off"}
        </button>
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

function LineStyleEditor({ style, readOnly, thickness, onThickness, onChange }: { style?: CanvasStyle; readOnly: boolean; thickness?: number; onThickness?: (value: number) => void; onChange: (patch: StylePatch) => void }) {
  const s = style || {};
  return (
    <EditorShell title="Line style">
      <div className="grid grid-cols-2 gap-2">
        <ColorField label="Color" value={s.color || "#111111"} disabled={readOnly} onChange={(v) => onChange({ color: v })} />
        <label className="grid gap-1 text-xs font-bold uppercase">
          Thickness
          <div className="flex items-center gap-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-1">
            {[1, 2, 4, 6].map((t) => (
              <button
                key={t}
                type="button"
                disabled={readOnly}
                onClick={() => onThickness?.(t)}
                title={`${t}px`}
                className={`grid h-7 flex-1 place-items-center rounded-[var(--rl-radius-sm)] transition-colors disabled:opacity-40 ${(thickness ?? 2) === t ? "bg-[var(--rl-black)]" : "hover:bg-[var(--rl-surface)]"}`}
              >
                <span className="rounded-full bg-current" style={{ width: Math.max(2, t), height: Math.max(2, t), color: (thickness ?? 2) === t ? "#fff" : "#6e6e73" }} />
              </button>
            ))}
          </div>
        </label>
      </div>
      <BorderStyleField value={s.borderStyle} disabled={readOnly} onChange={(v) => onChange({ borderStyle: v })} />
      <p className="text-[11px] text-[var(--rl-text-muted)]">Use Length / Angle in the common fields above to aim the line.</p>
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
