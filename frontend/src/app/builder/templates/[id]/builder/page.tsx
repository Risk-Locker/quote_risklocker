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
  GridFour,
  Image,
  LineSegment,
  LockSimple,
  MagnifyingGlass,
  Plus,
  Square,
  TextIndent,
  TextOutdent,
  TextT,
  Trash,
  Triangle,
  X,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { api, fileUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CanvasElementView, FONT_LIBRARY, type CanvasElement, type CanvasStyle, SNAP, snapValue, computeGuides } from "@/components/template-canvas/shared";
import { LayersPanel, type LayerAction } from "@/components/template-builder/layers-panel";

type TemplateVariable = { id: string; label: string; type: string; source: string; field?: string; fixed_value?: string };
type BenefitCard = { icon?: string; title?: string; subtitle?: string; lines?: string[]; asset_id?: string };
type PackageConfig = { name: string; included_cards?: string[]; add_on_cards?: string[]; included?: string[]; add_ons?: string[] };
type PageProfile = { id?: string; profile_key: string; name: string; width: number; height: number; unit: "px"; safe_margins: { top?: number; right?: number; bottom?: number; left?: number }; background_behavior?: string };
type TemplateConfig = { version?: number; page_profile?: PageProfile; variables: TemplateVariable[]; cards: Record<string, BenefitCard>; packages: PackageConfig[]; assets: Record<string, string>; canvas: { width: number; height: number; elements: CanvasElement[] } };
type TemplateRecord = { id: string; revision: number; name: string; insurance_type: string; status: string; locked: boolean; fixed_fields: TemplateConfig };
type AssetRecord = { id: string; label: string; filename: string; url: string; source?: string; folder?: string };
type DragState = {
  id: string;
  mode: "move" | "resize";
  startX: number;
  startY: number;
  start: CanvasElement;
  handle?: string;
  members: Set<string>;
  memberStart: Map<string, { x: number; y: number; w: number; h: number }>;
  preview: Map<string, Partial<CanvasElement>>;
  historySnapshot: TemplateConfig;
  changed: boolean;
};

const assetSlots = ["risklocker_logo", "insurer_logo", "bank_logo", "all_driver_icon", "background"];
const variableTypes = ["text", "money", "number", "date", "percent", "image", "boolean", "choice", "benefit_card"];
const sourceFields = ["customer_name", "vehicle_no", "insurance_company", "coverage_type", "cover_period", "car_model", "ncd_percent", "coverage_amount", "premium", "roadtax", "service_fee", "total_amount", "valid_until"];

function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)); }
function templateFingerprint(value: TemplateRecord) { return JSON.stringify({ name: value.name, fixed_fields: value.fixed_fields }); }
function makeId(prefix: string) { return `${prefix}_${Math.random().toString(36).slice(2, 9)}`; }
function slug(value: string) { return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || makeId("var"); }

function convertLegacyNodes(config: TemplateConfig): TemplateConfig {
  const next = clone(config);
  const source = next.canvas.elements || [];
  const referenced = new Set(source.map((item) => item.groupId).filter(Boolean));
  const ids = new Set(source.map((item) => item.id));
  const converted: CanvasElement[] = [];
  source.forEach((item, index) => {
    if (item.type === "shape") {
      converted.push({ ...item, type: item.shapeKind === "circle" ? "ellipse" : item.shapeKind || "rectangle", shapeKind: undefined });
      return;
    }
    if (item.type !== "group") { converted.push(item); return; }
    if (!referenced.has(item.id)) {
      converted.push({ ...item, type: "rectangle", groupName: undefined });
      return;
    }
    converted.push({ id: item.id, type: "layer-group", name: item.groupName || item.name || `Group ${index + 1}`, groupName: item.groupName || item.name || `Group ${index + 1}`, x: 0, y: 0, w: 1, h: 1, z: item.z, order: item.order ?? item.z ?? index, visible: item.visible !== false, locked: item.locked });
    const style = item.style || {};
    const visibleBox = !["", "transparent", "none"].includes(String(style.background || "").toLowerCase()) || Number(style.borderWidth || 0) > 0;
    if (visibleBox) {
      let rectangleId = `${item.id}--rectangle`;
      let suffix = 2;
      while (ids.has(rectangleId)) { rectangleId = `${item.id}--rectangle-${suffix}`; suffix += 1; }
      ids.add(rectangleId);
      converted.push({ ...item, id: rectangleId, type: "rectangle", groupId: item.id, groupName: undefined });
    }
  });
  next.version = 7;
  next.canvas.elements = converted;
  return next;
}

function layerLabel(element: CanvasElement): string {
  switch (element.type) {
    case "text": return element.text ? (element.text.replace(/\s+/g, " ").slice(0, 24) || "Text") : "Text";
    case "variable": return `Var: ${element.variableId || "?"}`;
    case "image": return element.assetSlot ? `Image: ${element.assetSlot}` : "Image";
    case "line": return "Line";
    case "layer-group": return element.name || element.groupName || "Group";
    case "group": return "Legacy box";
    case "rectangle": return element.name || "Rectangle";
    case "ellipse": return element.name || "Ellipse";
    case "triangle": return element.name || "Triangle";
    case "diamond": return element.name || "Diamond";
    case "shape": return "Legacy shape";
    case "benefit-section": return element.section === "add_ons" ? "Add-on section" : "Specials section";
    case "special": return element.variant_label ? `Special: ${element.variant_label}` : "Special";
    case "benefit-card": return "Benefit card";
    case "benefit-grid": return element.gridKind === "available_addons" ? "Available add-ons grid" : "Current benefits grid";
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
    borderWidth: ["group", "shape", "rectangle", "ellipse", "triangle", "diamond"].includes(type) ? 1 : 0,
    borderColor: "#111111",
    background: ["group", "shape", "rectangle", "ellipse", "triangle", "diamond"].includes(type) ? "#ffffff" : "transparent"
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
  const [showLeft, setShowLeft] = useState(true);
  const [showRight, setShowRight] = useState(true);
  const [leftWidth, setLeftWidth] = useState(280);
  const [rightWidth, setRightWidth] = useState(320);
  const [editingTextId, setEditingTextId] = useState<string | null>(null);
  const [rulerGuides, setRulerGuides] = useState<{ x: number[]; y: number[] }>({ x: [], y: [] });
  const [rulerDrag, setRulerDrag] = useState<{ axis: "x" | "y"; pos: number; active: boolean; origin?: number; outside?: boolean } | null>(null);
  const [selectedRulerGuide, setSelectedRulerGuide] = useState<{ axis: "x" | "y"; pos: number } | null>(null);
  const [marquee, setMarquee] = useState<{ startX: number; startY: number; curX: number; curY: number } | null>(null);
  const [drawLineMode, setDrawLineMode] = useState(false);
  const [lineThickness, setLineThickness] = useState(2);
  const [drawPreview, setDrawPreview] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const drawRef = useRef<{ x: number; y: number } | null>(null);
  const suppressClickRef = useRef(false);
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState("");
  const [importError, setImportError] = useState("");
  const [history, setHistory] = useState<TemplateConfig[]>([]);
  const [future, setFuture] = useState<TemplateConfig[]>([]);
  const [newVariable, setNewVariable] = useState({ label: "", type: "text", field: "" });
  const [showGrid, setShowGrid] = useState(true);
  const [previewMode, setPreviewMode] = useState(false);
  const [pageProfiles, setPageProfiles] = useState<PageProfile[]>([]);
  const [scenarioCount, setScenarioCount] = useState(6);
  const [publishing, setPublishing] = useState(false);
  const [savedFingerprint, setSavedFingerprint] = useState("");
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [savingAndLeaving, setSavingAndLeaving] = useState(false);
  const [canvasMenu, setCanvasMenu] = useState<{ id: string; x: number; y: number } | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const propertyGestureRef = useRef<{ snapshot: TemplateConfig; changed: boolean } | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const snapGuideXRef = useRef<HTMLDivElement>(null);
  const snapGuideYRef = useRef<HTMLDivElement>(null);
  const workspaceRef = useRef<HTMLElement>(null);

  async function load() {
    const [templateResult, businessAssetResult, profilesResult] = await Promise.all([
      api<{ template: TemplateRecord }>(`/admin/templates/${id}`),
      api<{ assets: { items: Array<{ id: string; label: string; url: string; asset_kind: string }> } }>("/business/assets?page=1&page_size=100"),
      api<{ page_profiles: PageProfile[] }>("/business/template-page-profiles"),
    ]);
    const original = clone(templateResult.template);
    const loaded = clone(templateResult.template);
    if (!loaded.fixed_fields.page_profile) {
      loaded.fixed_fields.page_profile = {
        profile_key: "a4",
        name: "A4",
        width: loaded.fixed_fields.canvas.width || 794,
        height: loaded.fixed_fields.canvas.height || 1123,
        unit: "px",
        safe_margins: { top: 24, right: 24, bottom: 24, left: 24 },
      };
    }
    loaded.fixed_fields = convertLegacyNodes(loaded.fixed_fields);
    setTemplate(loaded);
    setSavedFingerprint(templateFingerprint(original));
    setAssets(businessAssetResult.assets.items.map((asset) => ({ ...asset, filename: asset.label, source: "business", folder: asset.asset_kind === "company_logo" ? "Company logos" : "Benefit artwork" })));
    setPageProfiles(profilesResult.page_profiles.length ? profilesResult.page_profiles : [{
      profile_key: "a4", name: "A4", width: 794, height: 1123, unit: "px",
      safe_margins: { top: 24, right: 24, bottom: 24, left: 24 },
    }]);
    selectOnly(loaded.fixed_fields.canvas.elements[0]?.id || "");
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
  const dirty = Boolean(template && savedFingerprint && templateFingerprint(template) !== savedFingerprint);
  const selectedCard = selected?.cardId && config?.cards ? config.cards[selected.cardId] : null;
  const sortedElements = useMemo(() => {
    const byId = new Map(elements.map((item) => [item.id, item]));
    const inheritedState = (groupId?: string, visited = new Set<string>()): { visible: boolean; locked: boolean } => {
      if (!groupId || visited.has(groupId)) return { visible: true, locked: false };
      visited.add(groupId);
      const group = byId.get(groupId);
      if (!group || group.type !== "layer-group") return { visible: true, locked: false };
      const parent = inheritedState(group.parentId, visited);
      return { visible: parent.visible && group.visible !== false, locked: parent.locked || Boolean(group.locked) };
    };
    return elements
      .filter((item) => item.type !== "layer-group")
      .map((item) => {
        const inherited = inheritedState(item.groupId);
        return { ...item, visible: inherited.visible && item.visible !== false, locked: inherited.locked || Boolean(item.locked) };
      })
      .sort((a, b) => (a.z || 1) - (b.z || 1));
  }, [elements]);

  function nextZ() {
    return Math.max(1, ...elements.map((item) => item.z || 1)) + 1;
  }

  function selectedGroupIds() {
    return new Set(selection.filter((e) => e.type === "layer-group").map((e) => e.id));
  }

  // RL-DISABLED new manual benefit cards — disabled 2026-08-14; legacy elements remain readable, while new content uses dynamic benefit grids.

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

  function nestLayer(elementId: string, groupId: string | null) {
    if (readOnly || elementId === groupId) return;
    const source = elements.find((item) => item.id === elementId);
    if (!source) return;
    if (source.type === "layer-group") {
      let parent = groupId ? elements.find((item) => item.id === groupId) : null;
      while (parent?.parentId) {
        if (parent.parentId === source.id) return;
        parent = elements.find((item) => item.id === parent?.parentId) || null;
      }
      updateElement(source.id, { parentId: groupId || undefined });
    } else {
      updateElement(source.id, { groupId: groupId || undefined });
    }
  }

  function reorderLayer(elementId: string, targetId: string, position: "before" | "after") {
    if (readOnly || elementId === targetId) return;
    const source = elements.find((item) => item.id === elementId);
    const target = elements.find((item) => item.id === targetId);
    if (!source || !target || (source.type === "layer-group") !== (target.type === "layer-group")) return;
    if (source.type === "layer-group") {
      const siblings = elements.filter((item) => item.type === "layer-group" && item.parentId === target.parentId && item.id !== source.id).sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
      const index = Math.max(0, siblings.findIndex((item) => item.id === target.id) + (position === "after" ? 1 : 0));
      siblings.splice(index, 0, source);
      commit((current) => { current.canvas.elements = current.canvas.elements.map((item) => { const order = siblings.findIndex((sibling) => sibling.id === item.id); return order >= 0 ? { ...item, order, parentId: target.parentId } : item; }); return current; });
      return;
    }
    const siblings = elements.filter((item) => item.type !== "layer-group" && item.groupId === target.groupId && item.id !== source.id).sort((a, b) => (a.z || 0) - (b.z || 0));
    const index = Math.max(0, siblings.findIndex((item) => item.id === target.id) + (position === "after" ? 1 : 0));
    siblings.splice(index, 0, source);
    commit((current) => { current.canvas.elements = current.canvas.elements.map((item) => { const order = siblings.findIndex((sibling) => sibling.id === item.id); return order >= 0 ? { ...item, z: order + 1, groupId: target.groupId } : item; }); return current; });
  }

  function toggleVisibility(id: string) {
    const target = elements.find((item) => item.id === id);
    if (target) updateElement(id, { visible: target.visible === false });
  }

  function layerAction(action: LayerAction, id: string) {
    const target = elements.find((item) => item.id === id);
    if (!target || readOnly) return;
    if (action === "group") { groupSelection(); return; }
    if (action === "ungroup") {
      commit((current) => { current.canvas.elements = current.canvas.elements.filter((item) => item.id !== id).map((item) => item.groupId === id ? { ...item, groupId: undefined } : item); return current; });
      clearSelection();
      return;
    }
    if (action === "lock") { toggleLock(id); return; }
    if (action === "visibility") { toggleVisibility(id); return; }
    if (action === "delete") {
      commit((current) => { current.canvas.elements = current.canvas.elements.filter((item) => item.id !== id && item.groupId !== id && item.parentId !== id); return current; });
      clearSelection();
      return;
    }
    if (action === "duplicate") {
      if (target.type === "benefit-grid") return;
      const copy = { ...clone(target), id: makeId(target.type), name: target.name ? `${target.name} copy` : undefined, x: Math.min(canvasW - target.w, target.x + 16), y: Math.min(canvasH - target.h, target.y + 16), z: nextZ() };
      commit((current) => { current.canvas.elements.push(copy); return current; });
      selectOnly(copy.id);
      return;
    }
    const z = target.z || 1;
    const max = Math.max(1, ...elements.filter((item) => item.type !== "layer-group").map((item) => item.z || 1));
    const next = action === "forward" ? Math.min(max, z + 1) : action === "backward" ? Math.max(1, z - 1) : action === "front" ? max + 1 : 1;
    updateElement(id, { z: next });
  }

  function commit(updater: (current: TemplateConfig) => TemplateConfig) {
    if (!template || readOnly) return;
    setTemplate((current) => {
      if (!current) return current;
      if (propertyGestureRef.current) propertyGestureRef.current.changed = true;
      else {
        setHistory((items) => [...items.slice(-30), clone(current.fixed_fields)]);
        setFuture([]);
      }
      return { ...current, fixed_fields: updater(clone(current.fixed_fields)) };
    });
  }

  function beginPropertyGesture() {
    if (!template || readOnly || propertyGestureRef.current) return;
    propertyGestureRef.current = { snapshot: clone(template.fixed_fields), changed: false };
  }

  function endPropertyGesture() {
    const gesture = propertyGestureRef.current;
    propertyGestureRef.current = null;
    if (!gesture?.changed) return;
    setHistory((items) => [...items.slice(-30), gesture.snapshot]);
    setFuture([]);
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

  function addBenefitGrid(gridKind: "current_benefits" | "available_addons") {
    const existing = elements.find((element) => element.type === "benefit-grid" && element.gridKind === gridKind);
    if (existing) {
      selectOnly(existing.id);
      toast("This template already has that dynamic grid.", "info");
      return;
    }
    const element: CanvasElement = {
      id: makeId("benefit_grid"),
      type: "benefit-grid",
      gridKind,
      x: 24,
      y: gridKind === "current_benefits" ? Math.round(canvasH * 0.42) : Math.round(canvasH * 0.69),
      w: Math.max(120, canvasW - 48),
      h: Math.max(100, Math.round(canvasH * 0.22)),
      z: nextZ(),
      packing: {
        strategy: "balanced",
        alignment: "center",
        aspectRatio: 1.45,
        referenceWidth: 180,
        referenceHeight: 124,
        gapRatio: 0.06,
        paddingRatio: 0.02,
        staggerRatio: 0.5,
      },
      cardStyle: "standard",
      textDensity: "normal",
      emptyState: "hide",
    };
    commit((current) => { current.canvas.elements.push(element); return current; });
    selectOnly(element.id);
  }

  function updatePageGeometry(profile: PageProfile) {
    commit((current) => {
      const width = Math.max(320, Math.round(profile.width));
      const height = Math.max(320, Math.round(profile.height));
      current.version = 7;
      current.page_profile = { ...profile, width, height, unit: "px" };
      current.canvas.width = width;
      current.canvas.height = height;
      current.canvas.elements = current.canvas.elements.map((element) => {
        const w = Math.min(Math.max(1, element.w), width);
        const h = Math.min(Math.max(1, element.h), height);
        return { ...element, w, h, x: Math.min(Math.max(0, element.x), width - w), y: Math.min(Math.max(0, element.y), height - h) };
      });
      return current;
    });
  }

  function updateSafeMargin(side: "top" | "right" | "bottom" | "left", value: number) {
    const maximum = Math.floor((side === "top" || side === "bottom" ? canvasH : canvasW) / 2) - 1;
    const margin = Math.max(0, Math.min(maximum, Math.round(Number.isFinite(value) ? value : 0)));
    commit((current) => {
      const page = current.page_profile || { profile_key: "custom", name: "Custom fixed page", width: canvasW, height: canvasH, unit: "px", safe_margins: {} };
      current.page_profile = { ...page, safe_margins: { ...(page.safe_margins || {}), [side]: margin } };
      return current;
    });
  }

  function updateElements(ids: Set<string>, patch: (el: CanvasElement) => Partial<CanvasElement>) {
    commit((current) => {
      current.canvas.elements = current.canvas.elements.map((item) => ids.has(item.id) ? { ...item, ...patch(item) } : item);
      return current;
    });
  }

  function moveSelectionIds(): Set<string> {
    const ids = new Set(selection.filter((e) => !e.locked).map((e) => e.id));
    const groupIds = new Set(selection.filter((e) => e.type === "layer-group").map((e) => e.id));
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
    const groupIds = new Set(selection.filter((e) => e.type === "layer-group").map((e) => e.id));
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
    const copies = selection.filter((el) => !el.locked && el.type !== "benefit-grid").map((el) => {
      const copy = { ...clone(el), id: makeId(el.type), x: el.x + 18, y: el.y + 18, z: (el.z || 1) + 1 };
      if (el.type === "layer-group") idMap.set(el.id, copy.id);
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
    if (!copies.length) {
      toast("Dynamic grids are unique. Add one of each grid kind from the left panel.", "info");
      return;
    }
    commit((current) => { current.canvas.elements.push(...copies); return current; });
    selectOnly(copies[copies.length - 1].id);
  }

  function groupSelection() {
    const members = selection.filter((e) => e.type !== "layer-group" && !e.locked);
    if (members.length < 2 || readOnly) return;
    const gid = makeId("group");
    const count = elements.filter((e) => e.type === "layer-group").length;
    const groupEl: CanvasElement = {
      id: gid,
      type: "layer-group",
      name: `Group ${count + 1}`,
      groupName: `Group ${count + 1}`,
      x: 0, y: 0, w: 1, h: 1,
      z: Math.max(1, Math.min(...members.map((m) => m.z || 1)) - 1),
      order: elements.length,
      visible: true,
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
    setSelectedRulerGuide((current) => current?.axis === axis && current.pos === pos ? null : current);
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

  function startExistingGuide(event: React.PointerEvent, axis: "x" | "y", pos: number) {
    if (readOnly) return;
    event.preventDefault();
    event.stopPropagation();
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    setSelectedRulerGuide({ axis, pos });
    setRulerDrag({ axis, pos, origin: pos, active: true, outside: false });
  }

  function moveRulerDrag(event: React.PointerEvent) {
    if (!rulerDrag?.active) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const raw = rulerDrag.axis === "x" ? (event.clientX - rect.left) / zoom : (event.clientY - rect.top) / zoom;
    const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
    setRulerDrag((current) => (current ? { ...current, pos: current.origin === undefined ? clampPos(raw, current.axis) : raw, outside } : current));
  }

  function endRulerDrag() {
    if (!rulerDrag?.active) return;
    const axis = rulerDrag.axis;
    const pos = Math.round(rulerDrag.pos);
    setRulerGuides((current) => {
      const list = rulerDrag.origin === undefined ? current[axis] : current[axis].filter((item) => item !== rulerDrag.origin);
      if (rulerDrag.outside || pos < 0 || pos > (axis === "x" ? canvasW : canvasH)) return { ...current, [axis]: list };
      const existing = list.find((p) => Math.abs(p - pos) <= 3);
      const next = existing ? list : [...list, pos].sort((a, b) => a - b);
      return { ...current, [axis]: next };
    });
    setSelectedRulerGuide(rulerDrag.outside ? null : { axis, pos });
    setRulerDrag(null);
  }

  function pointerDown(event: React.PointerEvent, element: CanvasElement, mode: "move" | "resize", handle?: string) {
    if (readOnly || !template) return;
    if (drawLineMode) return;
    if (element.locked) return;
    if (element.type === "image" && element.assetSlot === "background" && mode === "move") return;
    event.preventDefault();
    event.stopPropagation();
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    if (event.shiftKey && mode === "move") {
      toggleSelect(element.id);
    } else if (!selectedIds.has(element.id)) {
      selectOnly(element.id);
    }
    const members = mode === "move" ? moveSelectionIds() : new Set([element.id]);
    const memberStart = new Map<string, { x: number; y: number; w: number; h: number }>();
    for (const el of elements) {
      if (members.has(el.id)) memberStart.set(el.id, { x: el.x, y: el.y, w: el.w, h: el.h });
    }
    dragRef.current = {
      id: element.id,
      mode,
      startX: event.clientX,
      startY: event.clientY,
      start: clone(element),
      handle,
      members,
      memberStart,
      preview: new Map(),
      historySnapshot: clone(template.fixed_fields),
      changed: false,
    };
  }

  function showSnapGuides(next: { x: number; y: number }[]) {
    const x = next.find((guide) => guide.x !== 0)?.x;
    const y = next.find((guide) => guide.y !== 0)?.y;
    if (snapGuideXRef.current) {
      snapGuideXRef.current.style.display = x === undefined ? "none" : "block";
      if (x !== undefined) snapGuideXRef.current.style.left = `${x}px`;
    }
    if (snapGuideYRef.current) {
      snapGuideYRef.current.style.display = y === undefined ? "none" : "block";
      if (y !== undefined) snapGuideYRef.current.style.top = `${y}px`;
    }
  }

  function pointerMove(event: React.PointerEvent) {
    const drag = dragRef.current;
    if (!drag || !template) return;
    const dx = (event.clientX - drag.startX) / zoom;
    const dy = (event.clientY - drag.startY) / zoom;
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;

    if (drag.mode === "move") {
      let nx = Math.round(drag.start.x + dx);
      let ny = Math.round(drag.start.y + dy);
      if (!event.altKey) {
        const { value: sx, guide: gx } = snapValue(nx, SNAP, []);
        const { value: sy, guide: gy } = snapValue(ny, SNAP, []);
        nx = gx ?? sx;
        ny = gy ?? sy;
      }
      let ddx = nx - drag.start.x;
      let ddy = ny - drag.start.y;
      if (!event.altKey) {
        const xTargets = [0, canvasW / 2, canvasW];
        const yTargets = [0, canvasH / 2, canvasH];
        elements.forEach((item) => {
          if (drag.members.has(item.id) || item.type === "layer-group" || item.visible === false) return;
          xTargets.push(item.x, item.x + item.w / 2, item.x + item.w);
          yTargets.push(item.y, item.y + item.h / 2, item.y + item.h);
        });
        const xEdges = [drag.start.x + ddx, drag.start.x + ddx + drag.start.w / 2, drag.start.x + ddx + drag.start.w];
        const yEdges = [drag.start.y + ddy, drag.start.y + ddy + drag.start.h / 2, drag.start.y + ddy + drag.start.h];
        const nearest = (edges: number[], targets: number[]) => edges.flatMap((edge) => targets.map((target) => target - edge)).reduce<number | null>((best, delta) => Math.abs(delta) <= 6 && (best === null || Math.abs(delta) < Math.abs(best)) ? delta : best, null);
        ddx += nearest(xEdges, xTargets) ?? 0;
        ddy += nearest(yEdges, yTargets) ?? 0;
      }
      for (const bounds of drag.memberStart.values()) {
        ddx = Math.max(-bounds.x, Math.min(canvasW - bounds.w - bounds.x, ddx));
        ddy = Math.max(-bounds.y, Math.min(canvasH - bounds.h - bounds.y, ddy));
      }
      const guides = event.altKey ? [] : computeGuides(drag.start, { x: drag.start.x + ddx, y: drag.start.y + ddy }, elements, canvasW, canvasH);
      showSnapGuides(guides);
      drag.changed = drag.changed || ddx !== 0 || ddy !== 0;
      drag.members.forEach((id) => {
        const start = drag.memberStart.get(id);
        if (!start) return;
        const patch = { x: Math.round(start.x + ddx), y: Math.round(start.y + ddy) };
        drag.preview.set(id, patch);
        const node = canvasRef.current?.querySelector<HTMLElement>(`[data-element-id="${CSS.escape(id)}"]`);
        if (node) { node.style.left = `${patch.x}px`; node.style.top = `${patch.y}px`; }
      });
    } else {
      const patch: Partial<CanvasElement> = {};
      if (drag.handle?.includes("e")) patch.w = Math.min(canvasW - drag.start.x, Math.max(8, Math.round(drag.start.w + dx)));
      if (drag.handle?.includes("s")) patch.h = Math.min(canvasH - drag.start.y, Math.max(2, Math.round(drag.start.h + dy)));
      if (drag.handle?.includes("w")) {
        const right = drag.start.x + drag.start.w;
        patch.x = Math.max(0, Math.min(right - 8, Math.round(drag.start.x + dx)));
        patch.w = right - patch.x;
      }
      if (drag.handle?.includes("n")) {
        const bottom = drag.start.y + drag.start.h;
        patch.y = Math.max(0, Math.min(bottom - 2, Math.round(drag.start.y + dy)));
        patch.h = bottom - patch.y;
      }
      const guides = computeGuides(drag.start, patch, elements, canvasW, canvasH);
      showSnapGuides(guides);
      drag.changed = drag.changed || Object.entries(patch).some(([key, value]) => value !== drag.start[key as keyof CanvasElement]);
      drag.preview.set(drag.id, patch);
      const node = canvasRef.current?.querySelector<HTMLElement>(`[data-element-id="${CSS.escape(drag.id)}"]`);
      if (node) {
        if (patch.x !== undefined) node.style.left = `${patch.x}px`;
        if (patch.y !== undefined) node.style.top = `${patch.y}px`;
        if (patch.w !== undefined) node.style.width = `${patch.w}px`;
        if (patch.h !== undefined) node.style.height = `${patch.h}px`;
      }
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
    showSnapGuides([]);
    if (drag?.changed) {
      suppressClickRef.current = true;
      setTemplate((current) => current ? {
        ...current,
        fixed_fields: {
          ...current.fixed_fields,
          canvas: {
            ...current.fixed_fields.canvas,
            elements: current.fixed_fields.canvas.elements.map((item) => drag.preview.has(item.id) ? { ...item, ...drag.preview.get(item.id) } : item),
          },
        },
      } : current);
      setHistory((items) => [...items.slice(-30), drag.historySnapshot]);
      setFuture([]);
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
    const knownTypes = new Set(["text", "variable", "image", "line", "rectangle", "ellipse", "triangle", "diamond", "layer-group", "group", "shape", "benefit-grid", "benefit-section", "benefit-card", "special"]);
    const num = (value: unknown, fallback: number) => (typeof value === "number" && Number.isFinite(value) ? value : fallback);
    const str = (value: unknown) => (typeof value === "string" ? value : undefined);
    const elements = (canvas.elements as unknown[]).map((entry, index) => {
      const el = entry as Record<string, unknown>;
      if (!el || typeof el !== "object" || !knownTypes.has(String(el.type))) {
        throw new Error(`Element ${index + 1} has an unknown type "${String(el?.type)}".`);
      }
      const persisted = Object.fromEntries(
        Object.entries(el).filter(([key]) => !["scenarioMode", "scenarioData", "scenarioItems"].includes(key)),
      );
      return {
        ...persisted,
        id: str(el.id) || `imported_${index + 1}_${Math.random().toString(36).slice(2, 7)}`,
        type: String(el.type),
        x: num(el.x, 80),
        y: num(el.y, 120),
        w: num(el.w, 180),
        h: num(el.h, 48),
        z: el.z === undefined ? undefined : num(el.z, 1),
      };
    });
    const imported: TemplateConfig = convertLegacyNodes({
      ...(config || {}),
      ...input,
      canvas: {
        width: num(canvas.width, canvasW),
        height: num(canvas.height, canvasH),
        elements,
      },
    });
    // An imported layout never locks or defaults the current template.
    (imported as Record<string, unknown>).is_default = false;
    (imported as Record<string, unknown>).locked = false;
    delete (imported as Record<string, unknown>).scenarioMode;
    delete (imported as Record<string, unknown>).scenarioData;
    delete (imported as Record<string, unknown>).previewScenario;
    imported.version = 7;
    imported.page_profile = imported.page_profile || {
      profile_key: "custom",
      name: "Imported fixed page",
      width: imported.canvas.width,
      height: imported.canvas.height,
      unit: "px",
      safe_margins: { top: 24, right: 24, bottom: 24, left: 24 },
    };
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

  async function saveDraft(showToast = true): Promise<TemplateRecord> {
    if (!template) throw new Error("Template is not loaded.");
    setError("");
    const result = await api<{ template: TemplateRecord }>(`/admin/templates/${template.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        base_revision: template.revision,
        name: template.name,
        insurance_type: template.insurance_type,
        fixed_fields: template.fixed_fields,
      }),
    });
    setTemplate(result.template);
    setSavedFingerprint(templateFingerprint(result.template));
    if (showToast) toast("Template draft saved.", "success");
    return result.template;
  }

  async function publishTemplate() {
    if (!template || publishing) return;
    setPublishing(true);
    setError("");
    try {
      const saved = await saveDraft(false);
      const result = await api<{
        template: TemplateRecord;
        template_revision: { revision_number: number };
      }>(`/business/templates/${id}/publish`, {
        method: "POST",
        body: JSON.stringify({ base_revision: saved.revision }),
      });
      setTemplate(result.template);
      toast(`Published immutable revision ${result.template_revision.revision_number}.`, "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Template publication failed.");
    } finally {
      setPublishing(false);
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
      if ((event.key === "Delete" || event.key === "Backspace") && selectedRulerGuide) {
        event.preventDefault();
        removeRulerGuide(selectedRulerGuide.axis, selectedRulerGuide.pos);
        return;
      }
      const meta = event.ctrlKey || event.metaKey;
      if (meta && event.key.toLowerCase() === "z") { event.preventDefault(); if (event.shiftKey) redo(); else undo(); return; }
      if (meta && event.key.toLowerCase() === "y") { event.preventDefault(); redo(); return; }
      if (meta && event.key.toLowerCase() === "d") { event.preventDefault(); duplicateSelection(); return; }
      if (!selectedIds.size) return;
      if (event.key === "Delete" || event.key === "Backspace") { event.preventDefault(); deleteSelection(); return; }
      const step = event.shiftKey ? 10 : 1;
      if (event.key === "ArrowUp") { event.preventDefault(); updateElements(moveSelectionIds(), (e) => ({ y: Math.max(0, (e.y || 0) - step) })); }
      else if (event.key === "ArrowDown") { event.preventDefault(); updateElements(moveSelectionIds(), (e) => ({ y: Math.min(canvasH - e.h, (e.y || 0) + step) })); }
      else if (event.key === "ArrowLeft") { event.preventDefault(); updateElements(moveSelectionIds(), (e) => ({ x: Math.max(0, (e.x || 0) - step) })); }
      else if (event.key === "ArrowRight") { event.preventDefault(); updateElements(moveSelectionIds(), (e) => ({ x: Math.min(canvasW - e.w, (e.x || 0) + step) })); }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedIds, selectedRulerGuide, readOnly, history, future, elements]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  useEffect(() => {
    if (!canvasMenu) return;
    const close = () => setCanvasMenu(null);
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    window.addEventListener("pointerdown", close);
    window.addEventListener("keydown", escape);
    return () => { window.removeEventListener("pointerdown", close); window.removeEventListener("keydown", escape); };
  }, [canvasMenu]);

  const fitPage = useCallback(() => {
    const workspace = workspaceRef.current;
    if (!workspace) return;
    const width = Math.max(240, workspace.clientWidth - 96);
    const height = Math.max(240, workspace.clientHeight - 120);
    setZoom(Math.max(0.1, Math.min(1, width / canvasW, height / canvasH)));
  }, [canvasH, canvasW]);

  const fitSelection = useCallback(() => {
    const workspace = workspaceRef.current;
    if (!workspace || !selectedIds.size) return;
    const selectedGroups = new Set(elements.filter((item) => selectedIds.has(item.id) && item.type === "layer-group").map((item) => item.id));
    const selectedNodes = elements.filter((item) => item.type !== "layer-group" && (selectedIds.has(item.id) || Boolean(item.groupId && selectedGroups.has(item.groupId))));
    if (!selectedNodes.length) return;
    const left = Math.min(...selectedNodes.map((item) => item.x));
    const top = Math.min(...selectedNodes.map((item) => item.y));
    const right = Math.max(...selectedNodes.map((item) => item.x + item.w));
    const bottom = Math.max(...selectedNodes.map((item) => item.y + item.h));
    const availableWidth = Math.max(160, workspace.clientWidth - 144);
    const availableHeight = Math.max(160, workspace.clientHeight - 176);
    const nextZoom = Math.max(0.1, Math.min(2, availableWidth / Math.max(1, right - left), availableHeight / Math.max(1, bottom - top)));
    setZoom(nextZoom);
    requestAnimationFrame(() => {
      const node = canvasRef.current?.querySelector<HTMLElement>(`[data-element-id="${selectedNodes[0].id}"]`);
      node?.scrollIntoView({ block: "center", inline: "center" });
    });
  }, [elements, selectedIds]);

  useEffect(() => {
    if (!template) return;
    const frame = requestAnimationFrame(fitPage);
    const observer = new ResizeObserver(fitPage);
    if (workspaceRef.current) observer.observe(workspaceRef.current);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); };
  }, [fitPage, template?.id]);

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
            onClick={() => { if (dirty) setLeaveOpen(true); else router.push("/builder/templates"); }}
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
                disabled={publishing}
                onClick={() => saveDraft().catch((err) => setError(err instanceof Error ? err.message : "Template save failed."))}
              >
                Save draft
              </Button>
              <Button
                variant="primary"
                size="sm"
                loading={publishing}
                onClick={publishTemplate}
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

      <Dialog open={leaveOpen} onOpenChange={setLeaveOpen} title="Unsaved template changes" description="Save this draft before leaving, discard the working changes, or keep editing.">
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={() => setLeaveOpen(false)}>Keep editing</Button>
          <Button variant="danger" onClick={() => router.push("/builder/templates")}>Discard and leave</Button>
          <Button loading={savingAndLeaving} onClick={async () => { setSavingAndLeaving(true); try { await saveDraft(false); router.push("/builder/templates"); } catch (reason) { setError(reason instanceof Error ? reason.message : "Template save failed."); setSavingAndLeaving(false); setLeaveOpen(false); } }}>Save and leave</Button>
        </div>
      </Dialog>

      {canvasMenu ? (
        <div
          role="menu"
          aria-label="Canvas layer actions"
          className="fixed z-[120] min-w-48 border border-[var(--rl-border)] bg-white py-1 shadow-lift"
          style={{ left: Math.min(canvasMenu.x, window.innerWidth - 210), top: Math.min(canvasMenu.y, window.innerHeight - 360) }}
          onPointerDown={(event) => event.stopPropagation()}
        >
          {([
            ["duplicate", "Duplicate"], ["delete", "Delete"], ["group", "Group selection"], ["ungroup", "Ungroup"],
            ["lock", elements.find((item) => item.id === canvasMenu.id)?.locked ? "Unlock" : "Lock"],
            ["visibility", elements.find((item) => item.id === canvasMenu.id)?.visible === false ? "Show" : "Hide"],
            ["forward", "Bring forward"], ["backward", "Send backward"], ["front", "Bring to front"], ["back", "Send to back"],
          ] as Array<[LayerAction, string]>).map(([action, label]) => {
            const target = elements.find((item) => item.id === canvasMenu.id);
            const disabled = readOnly || (action === "group" && selection.filter((item) => item.type !== "layer-group").length < 2) || (action === "ungroup" && target?.type !== "layer-group") || (action === "duplicate" && target?.type === "benefit-grid");
            return <button key={action} role="menuitem" type="button" disabled={disabled} className={`block w-full px-3 py-2 text-left text-[12px] font-medium hover:bg-[var(--rl-bg)] disabled:opacity-35 ${action === "delete" ? "text-[var(--rl-red)]" : "text-[var(--rl-text-strong)]"}`} onClick={() => { layerAction(action, canvasMenu.id); setCanvasMenu(null); }}>{label}</button>;
          })}
        </div>
      ) : null}

      <div className="grid min-h-0 flex-1 place-items-center px-6 text-center lg:hidden">
        <div className="max-w-md border border-[var(--rl-border)] bg-[var(--rl-surface)] p-6 shadow-sm">
          <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Canvas editing needs a wider screen</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--rl-text-muted)]">Open Template Builder at 1024 px or wider. Tablet review and the rest of the quotation workflow remain available from 768 px.</p>
          <Button className="mt-4" variant="secondary" onClick={() => router.push("/builder/templates")}>Back to templates</Button>
        </div>
      </div>

      <div
        className="hidden min-h-0 flex-1 lg:grid"
        style={{
          gridTemplateColumns: `${showLeft && !previewMode ? leftWidth : 0}px 6px minmax(0,1fr) 6px ${showRight && !previewMode ? rightWidth : 0}px`,
          transition: "grid-template-columns 160ms ease",
        }}
      >
        {!previewMode && showLeft ? (
          <aside className="min-h-0 overflow-y-auto border-r border-[var(--rl-border)] bg-[var(--rl-surface)]">
            <div className="h-[44vh] min-h-52 overflow-hidden border-b border-[var(--rl-border)]">
              <LayersPanel
                elements={elements}
                selectedIds={selectedIds}
                readOnly={readOnly}
                onSelect={(layerId, additive) => additive ? toggleSelect(layerId) : selectOnly(layerId)}
                onRename={(layerId, name) => updateElement(layerId, { name, groupName: name })}
                onToggleLock={toggleLock}
                onToggleVisibility={toggleVisibility}
                onNest={nestLayer}
                onReorder={reorderLayer}
                onAction={layerAction}
              />
            </div>
            <div className="p-4">
            <PanelSection title="Fixed page">
              <div className="grid gap-3">
                <label className="grid gap-1 text-xs font-bold uppercase text-[var(--rl-text-muted)]">
                  Page profile
                  <Select
                    value={config?.page_profile?.profile_key || "custom"}
                    disabled={readOnly}
                    onChange={(event) => {
                      const profile = pageProfiles.find((item) => item.profile_key === event.target.value);
                      if (profile) updatePageGeometry(profile);
                    }}
                  >
                    {pageProfiles.map((profile) => (
                      <option key={profile.profile_key} value={profile.profile_key}>{profile.name} · {profile.width} × {profile.height}</option>
                    ))}
                    {!pageProfiles.some((profile) => profile.profile_key === config?.page_profile?.profile_key) ? (
                      <option value="custom">Custom fixed page</option>
                    ) : null}
                  </Select>
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="grid gap-1 text-xs font-bold uppercase text-[var(--rl-text-muted)]">
                    Width (px)
                    <Input
                      type="number"
                      min={320}
                      max={2400}
                      value={canvasW}
                      disabled={readOnly}
                      onChange={(event) => updatePageGeometry({
                        ...(config?.page_profile || { profile_key: "custom", name: "Custom fixed page", unit: "px", safe_margins: {} }),
                        profile_key: "custom",
                        name: "Custom fixed page",
                        width: Number(event.target.value) || canvasW,
                        height: canvasH,
                        unit: "px",
                      })}
                    />
                  </label>
                  <label className="grid gap-1 text-xs font-bold uppercase text-[var(--rl-text-muted)]">
                    Height (px)
                    <Input
                      type="number"
                      min={320}
                      max={5000}
                      value={canvasH}
                      disabled={readOnly}
                      onChange={(event) => updatePageGeometry({
                        ...(config?.page_profile || { profile_key: "custom", name: "Custom fixed page", unit: "px", safe_margins: {} }),
                        profile_key: "custom",
                        name: "Custom fixed page",
                        width: canvasW,
                        height: Number(event.target.value) || canvasH,
                        unit: "px",
                      })}
                    />
                  </label>
                </div>
                <fieldset className="grid grid-cols-2 gap-2 border-t border-[var(--rl-border)] pt-3">
                  <legend className="col-span-2 mb-1 text-[11px] font-bold uppercase tracking-[0.1em] text-[var(--rl-text-muted)]">Safe margins (px)</legend>
                  {(["top", "right", "bottom", "left"] as const).map((side) => (
                    <label key={side} className="grid gap-1 text-[11px] font-semibold capitalize text-[var(--rl-text-muted)]">
                      {side}
                      <Input type="number" min={0} max={Math.floor((side === "top" || side === "bottom" ? canvasH : canvasW) / 2) - 1} value={config?.page_profile?.safe_margins?.[side] || 0} disabled={readOnly} onChange={(event) => updateSafeMargin(side, Number(event.target.value))} />
                    </label>
                  ))}
                </fieldset>
                <p className="text-[11px] leading-relaxed text-[var(--rl-text-muted)]">The page never extends automatically. A longer quotation is a separate fixed master profile.</p>
              </div>
            </PanelSection>

            <PanelSection title="Benefit grids">
              <div className="grid gap-2">
                <Button variant="secondary" size="sm" disabled={readOnly} onClick={() => addBenefitGrid("current_benefits")} className="justify-start">
                  <GridFour weight="bold" size={16} /> Current benefits
                </Button>
                <Button variant="secondary" size="sm" disabled={readOnly} onClick={() => addBenefitGrid("available_addons")} className="justify-start">
                  <GridFour weight="bold" size={16} /> Available add-ons
                </Button>
                <p className="text-[11px] leading-relaxed text-[var(--rl-text-muted)]">At most one of each. Every card shrinks uniformly as rows and columns increase.</p>
              </div>
            </PanelSection>

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
                onClick={() => addElement("rectangle", { w: 180, h: 80 })}
                className="justify-start"
              >
                Rectangle
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
                onClick={() => addElement("ellipse", { w: 100, h: 100, style: { background: "#F6F8FB", borderWidth: 1, borderColor: "#D8DDE6" } })}
                className="justify-start"
              >
                Ellipse
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<Triangle weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("triangle", { w: 100, h: 90, style: { background: "#F6F8FB" } })}
                className="justify-start"
              >
                Triangle
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<Diamond weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("diamond", { w: 100, h: 100, style: { background: "#F6F8FB", borderWidth: 1, borderColor: "#D8DDE6" } })}
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
              <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2">
                <p className="text-[11px] leading-4 text-[var(--rl-text-muted)]">Choose from approved active assets. Uploading and metadata changes belong in Asset Library.</p>
                <Link className="shrink-0 text-[11px] font-bold text-[var(--rl-red)] underline-offset-2 hover:underline" href="/builder/assets">Manage assets</Link>
              </div>
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

            </div>
          </aside>
        ) : <div />}

        <div
          role="separator"
          aria-label="Resize layers and tools panel"
          aria-orientation="vertical"
          aria-valuemin={200}
          aria-valuemax={520}
          aria-valuenow={leftWidth}
          tabIndex={0}
          className="z-10 cursor-col-resize border-x border-[var(--rl-border)] bg-[var(--rl-bg)] transition-colors hover:bg-[var(--rl-border)]"
          onPointerDown={startPanelResize("left")}
          onKeyDown={(event) => { if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); setLeftWidth((value) => Math.max(200, Math.min(520, value + (event.key === "ArrowRight" ? 16 : -16)))); } }}
          title="Drag to resize the left panel"
        />

        <section ref={workspaceRef} className="flex min-h-0 flex-col overflow-auto p-4">
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
          </div>
          <div className="m-auto w-fit flex-shrink-0 rounded-md bg-neutral-300 p-6 shadow-inner" style={{ minHeight: ((canvasH) * zoom) + 60 }}>
            <div className="relative" style={{ width: (canvasW) * zoom, height: (canvasH) * zoom }}>
              {!previewMode ? (
                <>
                  <div data-testid="horizontal-ruler" className="absolute -top-6 left-0 h-5 w-full select-none overflow-hidden border-b border-[var(--rl-border)] bg-[var(--rl-surface)]"
                    onPointerDown={(event) => startRulerDrag(event, "x")}
                    onPointerMove={(event) => moveRulerDrag(event)}
                    onPointerUp={endRulerDrag}
                    onPointerCancel={endRulerDrag}
                    onLostPointerCapture={endRulerDrag}
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
                  <div data-testid="vertical-ruler" className="absolute -left-6 top-0 w-5 select-none overflow-hidden border-r border-[var(--rl-border)] bg-[var(--rl-surface)]"
                    onPointerDown={(event) => startRulerDrag(event, "y")}
                    onPointerMove={(event) => moveRulerDrag(event)}
                    onPointerUp={endRulerDrag}
                    onPointerCancel={endRulerDrag}
                    onLostPointerCapture={endRulerDrag}
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
                data-testid="template-canvas"
                className="relative origin-top-left overflow-hidden bg-white shadow-xl"
                style={{ width: canvasW, height: canvasH, transform: `scale(${zoom})` }}
                onPointerDown={canvasPointerDown}
                onPointerMove={(event) => { pointerMove(event); canvasPointerMove(event); }}
                onPointerUp={(event) => { pointerUp(); canvasPointerUp(); }}
                onPointerCancel={() => {
                  pointerUp();
                  setMarquee(null);
                  drawRef.current = null;
                  setDrawPreview(null);
                }}
                onLostPointerCapture={pointerUp}
                onClick={() => { if (suppressClickRef.current) { suppressClickRef.current = false; return; } clearSelection(); setSelectedRulerGuide(null); setEditingTextId(null); }}
              >
                {showGrid && !previewMode && (
                  <div className="pointer-events-none absolute inset-0 opacity-10" style={{ backgroundImage: `linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)`, backgroundSize: `${SNAP}px ${SNAP}px` }} />
                )}
                {!previewMode && config?.page_profile?.safe_margins ? (
                  <div
                    className="pointer-events-none absolute z-[9996] border border-dashed border-[var(--rl-red)]/60"
                    style={{
                      top: config.page_profile.safe_margins.top || 0,
                      right: config.page_profile.safe_margins.right || 0,
                      bottom: config.page_profile.safe_margins.bottom || 0,
                      left: config.page_profile.safe_margins.left || 0,
                    }}
                    aria-hidden="true"
                  />
                ) : null}
                <div ref={snapGuideXRef} className="pointer-events-none absolute bottom-0 top-0 hidden border-l border-dashed border-[var(--rl-red)]" style={{ zIndex: 9999 }} />
                <div ref={snapGuideYRef} className="pointer-events-none absolute left-0 right-0 hidden border-t border-dashed border-[var(--rl-red)]" style={{ zIndex: 9999 }} />
                {!previewMode && rulerGuides.x.map((x) => (
                  <button
                    key={`gx${x}`}
                    type="button"
                    aria-label={`Vertical guide at ${x} pixels`}
                    className="absolute -ml-[3px] w-[7px] cursor-col-resize border-0 bg-transparent p-0 before:absolute before:bottom-0 before:left-[3px] before:top-0 before:border-l before:border-dashed before:border-[var(--rl-red)]"
                    style={{ left: x, top: 0, bottom: 0, zIndex: 9998, opacity: selectedRulerGuide?.axis === "x" && selectedRulerGuide.pos === x ? 1 : 0.65 }}
                    onPointerDown={(event) => startExistingGuide(event, "x", x)}
                    onPointerMove={moveRulerDrag}
                    onPointerUp={endRulerDrag}
                    onPointerCancel={endRulerDrag}
                    onLostPointerCapture={endRulerDrag}
                    onClick={(event) => { event.stopPropagation(); setSelectedRulerGuide({ axis: "x", pos: x }); event.currentTarget.focus(); }}
                    onKeyDown={(event) => { if (event.key === "Delete" || event.key === "Backspace") { event.preventDefault(); event.stopPropagation(); removeRulerGuide("x", x); } }}
                    onContextMenu={(event) => { event.preventDefault(); event.stopPropagation(); removeRulerGuide("x", x); }}
                  />
                ))}
                {!previewMode && rulerGuides.y.map((y) => (
                  <button
                    key={`gy${y}`}
                    type="button"
                    aria-label={`Horizontal guide at ${y} pixels`}
                    className="absolute -mt-[3px] h-[7px] cursor-row-resize border-0 bg-transparent p-0 before:absolute before:left-0 before:right-0 before:top-[3px] before:border-t before:border-dashed before:border-[var(--rl-red)]"
                    style={{ top: y, left: 0, right: 0, zIndex: 9998, opacity: selectedRulerGuide?.axis === "y" && selectedRulerGuide.pos === y ? 1 : 0.65 }}
                    onPointerDown={(event) => startExistingGuide(event, "y", y)}
                    onPointerMove={moveRulerDrag}
                    onPointerUp={endRulerDrag}
                    onPointerCancel={endRulerDrag}
                    onLostPointerCapture={endRulerDrag}
                    onClick={(event) => { event.stopPropagation(); setSelectedRulerGuide({ axis: "y", pos: y }); event.currentTarget.focus(); }}
                    onKeyDown={(event) => { if (event.key === "Delete" || event.key === "Backspace") { event.preventDefault(); event.stopPropagation(); removeRulerGuide("y", y); } }}
                    onContextMenu={(event) => { event.preventDefault(); event.stopPropagation(); removeRulerGuide("y", y); }}
                  />
                ))}
                {marquee ? (
                  <div
                    className="pointer-events-none absolute border border-[var(--rl-red)] bg-[var(--rl-red-light)]/40"
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
                      className="pointer-events-none absolute bg-[var(--rl-red)]"
                      style={{ left: drawPreview.x, top: drawPreview.y, width: drawPreview.w, height: drawPreview.h, zIndex: 9997 }}
                    />
                    <div
                      className="pointer-events-none absolute h-2 w-2 rounded-full border-2 border-[var(--rl-red)] bg-white"
                      style={{ left: drawPreview.x - 4, top: drawPreview.y + drawPreview.h / 2 - 4, zIndex: 9997 }}
                    />
                    <div
                      className="pointer-events-none absolute h-2 w-2 rounded-full border-2 border-[var(--rl-red)] bg-white"
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
                    scenarioCount={scenarioCount}
                    readOnly={readOnly}
                    onPointerDown={(event) => pointerDown(event, element, "move")}
                    onResizePointerDown={(event, handle) => pointerDown(event, element, "resize", handle)}
                    onContextMenu={(event) => {
                      if (readOnly) return;
                      event.preventDefault();
                      event.stopPropagation();
                      if (!selectedIds.has(element.id)) selectOnly(element.id);
                      setCanvasMenu({ id: element.id, x: event.clientX, y: event.clientY });
                    }}
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
          <footer className="mt-3 flex shrink-0 flex-wrap items-center justify-between gap-3 border-t border-[var(--rl-border)] bg-[var(--rl-surface)] px-3 py-2" aria-label="Canvas view controls">
            <label className="flex items-center gap-2 text-[12px] font-bold">
              Scenario
              <Select className="w-24" value={String(scenarioCount)} onChange={(event) => setScenarioCount(Number(event.target.value))}>
                <option value="0">Empty</option><option value="1">1</option><option value="6">6</option><option value="12">12</option><option value="15">15</option><option value="20">20</option>
              </Select>
            </label>
            <div className="flex flex-wrap items-center gap-2">
              {rulerGuides.x.length + rulerGuides.y.length > 0 ? <Button variant="ghost" size="sm" onClick={() => { setRulerGuides({ x: [], y: [] }); setSelectedRulerGuide(null); }}>Clear guides ({rulerGuides.x.length + rulerGuides.y.length})</Button> : <span className="text-[11px] text-[var(--rl-text-muted)]">Drag from a ruler to add a guide</span>}
              <label className="flex items-center gap-2 text-[12px] font-bold">Zoom <input aria-label="Canvas zoom" className="w-28 accent-[var(--rl-red)]" type="range" min="0.1" max="2" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
              <output className="w-11 text-right text-[12px] tabular-nums">{Math.round(zoom * 100)}%</output>
              <Button variant="ghost" size="sm" onClick={() => setZoom(Math.max(0.1, zoom - 0.1))} aria-label="Zoom out">−</Button>
              <Button variant="ghost" size="sm" onClick={() => setZoom(Math.min(2, zoom + 0.1))} aria-label="Zoom in">+</Button>
              <Button variant="ghost" size="sm" onClick={() => setZoom(1)}>100%</Button>
              <Button variant="ghost" size="sm" onClick={fitPage}>Fit page</Button>
              <Button variant="ghost" size="sm" disabled={!selectedIds.size} onClick={fitSelection}>Fit selection</Button>
            </div>
          </footer>
        </section>

        <div
          role="separator"
          aria-label="Resize properties panel"
          aria-orientation="vertical"
          aria-valuemin={200}
          aria-valuemax={520}
          aria-valuenow={rightWidth}
          tabIndex={0}
          className="z-10 cursor-col-resize border-x border-[var(--rl-border)] bg-[var(--rl-bg)] transition-colors hover:bg-[var(--rl-border)]"
          onPointerDown={startPanelResize("right")}
          onKeyDown={(event) => { if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); setRightWidth((value) => Math.max(200, Math.min(520, value + (event.key === "ArrowLeft" ? 16 : -16)))); } }}
          title="Drag to resize the inspector panel"
        />

        {!previewMode && showRight ? (
          <aside className="flex min-h-0 flex-col overflow-hidden border-l border-[var(--rl-border)] bg-[var(--rl-surface)]">
            <div className="shrink-0 border-b border-[var(--rl-border)] px-4 py-3">
              <h2 className="m-0 text-[12px] font-bold uppercase tracking-[0.12em] text-[var(--rl-text-muted)]">Properties</h2>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {selection.length > 1 ? (
              <p className="mt-1 border-l-2 border-[var(--rl-red)] bg-[var(--rl-red-light)] px-2 py-1.5 text-[12px] font-semibold text-[var(--rl-text-strong)]">
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
                {selected.type === "layer-group" ? (
                  <label className="grid gap-1 font-bold">
                    Group name
                    <Input value={selected.name || selected.groupName || ""} disabled={readOnly} onChange={(event) => updateElement(selected.id, { name: event.target.value, groupName: event.target.value })} />
                  </label>
                ) : null}
                {selected.type !== "layer-group" ? <div className="grid grid-cols-2 gap-2">
                  {(["x", "y", "w", "h", "z"] as const).map((key) => (
                    <label key={key} className="grid gap-1 text-xs font-bold uppercase">
                      {key}
                      <Input
                        type="number"
                        min={key === "z" ? 1 : 0}
                        max={key === "x" ? canvasW - selected.w : key === "y" ? canvasH - selected.h : key === "w" ? canvasW - selected.x : key === "h" ? canvasH - selected.y : undefined}
                        value={selected[key] || 0}
                        disabled={readOnly || Boolean(selected.locked)}
                        onChange={(event) => {
                          const raw = Number(event.target.value);
                          const value = key === "x" ? Math.max(0, Math.min(canvasW - selected.w, raw)) : key === "y" ? Math.max(0, Math.min(canvasH - selected.h, raw)) : key === "w" ? Math.max(1, Math.min(canvasW - selected.x, raw)) : key === "h" ? Math.max(1, Math.min(canvasH - selected.y, raw)) : Math.max(1, raw);
                          updateElement(selected.id, { [key]: value });
                        }}
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
                </div> : null}
                {selected.type !== "layer-group" ? <RangeControl label="Opacity" value={selected.opacity ?? 1} min={0} max={1} step={0.05} unit="" disabled={readOnly || Boolean(selected.locked)} resetValue={1} onGestureStart={beginPropertyGesture} onGestureEnd={endPropertyGesture} onChange={(value) => updateElement(selected.id, { opacity: value })} /> : null}
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
                {selected.type === "benefit-grid" ? (
                  <EditorShell title="Dynamic benefit grid">
                    <label className="grid gap-1 font-bold">
                      Content
                      <Select value={selected.gridKind || "current_benefits"} disabled>
                        <option value="current_benefits">Current benefits</option>
                        <option value="available_addons">Available add-ons</option>
                      </Select>
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <label className="grid gap-1 text-xs font-bold uppercase">
                        Packing
                        <Select
                          value={selected.packing?.strategy || "balanced"}
                          disabled={readOnly || Boolean(selected.locked)}
                          onChange={(event) => updateElement(selected.id, { packing: { ...(selected.packing || {}), strategy: event.target.value as NonNullable<CanvasElement["packing"]>["strategy"] } })}
                        >
                          <option value="balanced">Balanced</option>
                          <option value="square_biased">Square biased</option>
                          <option value="staggered">Staggered</option>
                        </Select>
                      </label>
                      <label className="grid gap-1 text-xs font-bold uppercase">
                        Alignment
                        <Select
                          value={selected.packing?.alignment || "center"}
                          disabled={readOnly || Boolean(selected.locked)}
                          onChange={(event) => updateElement(selected.id, { packing: { ...(selected.packing || {}), alignment: event.target.value as NonNullable<CanvasElement["packing"]>["alignment"] } })}
                        >
                          <option value="start">Start</option>
                          <option value="center">Center</option>
                          <option value="end">End</option>
                        </Select>
                      </label>
                      <label className="grid gap-1 text-xs font-bold uppercase">
                        Card style
                        <Select
                          value={selected.cardStyle || "standard"}
                          disabled={readOnly || Boolean(selected.locked)}
                          onChange={(event) => updateElement(selected.id, { cardStyle: event.target.value as CanvasElement["cardStyle"] })}
                        >
                          <option value="standard">Standard</option>
                          <option value="outlined">Outlined</option>
                          <option value="soft">Soft</option>
                          <option value="minimal">Minimal</option>
                        </Select>
                      </label>
                      <label className="grid gap-1 text-xs font-bold uppercase">
                        Text density
                        <Select
                          value={selected.textDensity || "normal"}
                          disabled={readOnly || Boolean(selected.locked)}
                          onChange={(event) => updateElement(selected.id, { textDensity: event.target.value as CanvasElement["textDensity"] })}
                        >
                          <option value="comfortable">Comfortable</option>
                          <option value="normal">Normal</option>
                          <option value="compact">Compact</option>
                        </Select>
                      </label>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <NumField label="Aspect" value={selected.packing?.aspectRatio ?? 1.45} disabled={readOnly || Boolean(selected.locked)} onChange={(value) => updateElement(selected.id, { packing: { ...(selected.packing || {}), aspectRatio: Math.max(0.1, value) } })} />
                      <RangeControl label="Stagger" value={selected.packing?.staggerRatio ?? 0.5} min={0} max={1} step={0.05} unit="" disabled={readOnly || Boolean(selected.locked)} resetValue={0.5} onGestureStart={beginPropertyGesture} onGestureEnd={endPropertyGesture} onChange={(value) => updateElement(selected.id, { packing: { ...(selected.packing || {}), staggerRatio: value } })} />
                      <RangeControl label="Gap" value={selected.packing?.gapRatio ?? 0.06} min={0} max={0.3} step={0.01} unit="" disabled={readOnly || Boolean(selected.locked)} resetValue={0.06} onGestureStart={beginPropertyGesture} onGestureEnd={endPropertyGesture} onChange={(value) => updateElement(selected.id, { packing: { ...(selected.packing || {}), gapRatio: value } })} />
                      <RangeControl label="Padding" value={selected.packing?.paddingRatio ?? 0.02} min={0} max={0.2} step={0.01} unit="" disabled={readOnly || Boolean(selected.locked)} resetValue={0.02} onGestureStart={beginPropertyGesture} onGestureEnd={endPropertyGesture} onChange={(value) => updateElement(selected.id, { packing: { ...(selected.packing || {}), paddingRatio: value } })} />
                      <NumField label="Reference width" value={selected.packing?.referenceWidth ?? 180} disabled={readOnly || Boolean(selected.locked)} onChange={(value) => updateElement(selected.id, { packing: { ...(selected.packing || {}), referenceWidth: Math.max(1, value) } })} />
                      <NumField label="Reference height" value={selected.packing?.referenceHeight ?? 124} disabled={readOnly || Boolean(selected.locked)} onChange={(value) => updateElement(selected.id, { packing: { ...(selected.packing || {}), referenceHeight: Math.max(1, value) } })} />
                    </div>
                    <label className="grid gap-1 font-bold">
                      Empty state
                      <Select
                        value={selected.emptyState || "hide"}
                        disabled={readOnly || Boolean(selected.locked)}
                        onChange={(event) => updateElement(selected.id, { emptyState: event.target.value as CanvasElement["emptyState"] })}
                      >
                        <option value="hide">Hide grid</option>
                        <option value="message">Show message</option>
                      </Select>
                    </label>
                    {selected.emptyState === "message" ? (
                      <label className="grid gap-1 font-bold">
                        Empty message
                        <Input value={selected.emptyMessage || ""} disabled={readOnly || Boolean(selected.locked)} onChange={(event) => updateElement(selected.id, { emptyMessage: event.target.value })} />
                      </label>
                    ) : null}
                    <p className="text-[11px] leading-relaxed text-[var(--rl-text-muted)]">Scenario count is editor-only. It is never saved into the published template.</p>
                  </EditorShell>
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
                  <div className="border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3 text-[12px] leading-5 text-[var(--rl-text-muted)]">
                    Legacy benefit section retained for historical layout compatibility. Replace it with a Current Benefits or Available Add-ons grid before publication.
                  </div>
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
                  <div className="grid gap-2 border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3">
                    <h3 className="font-bold text-[var(--rl-text-strong)]">Legacy benefit card</h3>
                    <p className="text-[11px] leading-5 text-[var(--rl-text-muted)]">Read-only compatibility content. Replace it with a dynamic benefit grid before publication.</p>
                  </div>
                ) : null}
                {["text", "variable"].includes(selected.type) ? (
                  <TextStyleEditor style={selected.style} readOnly={readOnly || Boolean(selected.locked)} onChange={(patch) => updateStyle(selected.id, patch)} />
                ) : null}
                {["rectangle", "ellipse", "triangle", "diamond", "group", "shape", "box"].includes(selected.type) ? (
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

function RangeControl({ label, value, min, max, step, unit, disabled, resetValue, onGestureStart, onGestureEnd, onChange }: { label: string; value: number; min: number; max: number; step: number; unit: string; disabled: boolean; resetValue: number; onGestureStart?: () => void; onGestureEnd?: () => void; onChange: (value: number) => void }) {
  const clamped = Math.max(min, Math.min(max, Number.isFinite(value) ? value : resetValue));
  return (
    <fieldset className="col-span-full grid grid-cols-[1fr_84px_auto] items-end gap-2 border border-[var(--rl-border)] p-2">
      <legend className="px-1 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--rl-text-muted)]">{label}</legend>
      <label className="grid gap-1 text-[10px] font-semibold text-[var(--rl-text-muted)]">{min} to {max}{unit}
        <input aria-label={`${label} slider`} type="range" min={min} max={max} step={step} value={clamped} disabled={disabled} onPointerDown={onGestureStart} onPointerUp={onGestureEnd} onPointerCancel={onGestureEnd} onChange={(event) => onChange(Number(event.target.value))} className="h-8 w-full accent-[var(--rl-red)]" />
      </label>
      <label className="grid gap-1 text-[10px] font-semibold text-[var(--rl-text-muted)]">Value
        <span className="relative"><Input aria-label={`${label} value`} type="number" min={min} max={max} step={step} value={clamped} disabled={disabled} onChange={(event) => onChange(Math.max(min, Math.min(max, Number(event.target.value))))} className={unit ? "pr-7" : ""} />{unit ? <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[11px] text-[var(--rl-text-muted)]">{unit}</span> : null}</span>
      </label>
      <Button variant="ghost" size="sm" disabled={disabled || clamped === resetValue} onClick={() => onChange(resetValue)}>Reset</Button>
    </fieldset>
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
          className={`rounded-[var(--rl-radius-sm)] border px-3 py-2 text-[13px] font-bold transition-colors disabled:opacity-40 ${weight >= 700 ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white" : "border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:bg-[var(--rl-bg)]"}`}
        >
          Bold {weight >= 700 ? "on" : "off"}
        </button>
        <button
          type="button"
          disabled={readOnly}
          onClick={() => onChange({ fontStyle: s.fontStyle === "italic" ? "normal" : "italic" })}
          className={`rounded-[var(--rl-radius-sm)] border px-3 py-2 text-[13px] font-bold italic transition-colors disabled:opacity-40 ${s.fontStyle === "italic" ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white" : "border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:bg-[var(--rl-bg)]"}`}
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
