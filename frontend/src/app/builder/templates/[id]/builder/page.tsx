"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  BringToFront,
  Copy,
  Download,
  Grid3x3,
  ImageIcon,
  Layers,
  Redo2,
  Save,
  SendToBack,
  Square,
  TextCursorInput,
  Trash2,
  Undo2,
  Upload,
  Variable,
  X,
} from "lucide-react";
import { api, fileUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type CanvasStyle = { fontSize?: number; fontWeight?: string; color?: string; textAlign?: string; borderWidth?: number; borderColor?: string; background?: string };
type CanvasElement = {
  id: string; type: string; x: number; y: number; w: number; h: number; z?: number;
  text?: string; variableId?: string; assetId?: string; assetSlot?: string; cardId?: string;
  section?: "specials" | "add_ons"; columns?: number; prefix?: string; suffix?: string; opacity?: number; style?: CanvasStyle;
};
type TemplateVariable = { id: string; label: string; type: string; source: string; field?: string; fixed_value?: string };
type BenefitCard = { icon?: string; title?: string; subtitle?: string; lines?: string[]; asset_id?: string };
type PackageConfig = { name: string; included_cards?: string[]; add_on_cards?: string[]; included?: string[]; add_ons?: string[] };
type TemplateConfig = { variables: TemplateVariable[]; cards: Record<string, BenefitCard>; packages: PackageConfig[]; assets: Record<string, string>; canvas: { width: number; height: number; elements: CanvasElement[] } };
type TemplateRecord = { id: string; name: string; insurance_type: string; status: string; locked: boolean; fixed_fields: TemplateConfig };
type AssetRecord = { id: string; label: string; filename: string; url: string; source?: string };
type DragState = { id: string; mode: "move" | "resize"; startX: number; startY: number; start: CanvasElement; handle?: string };

const assetSlots = ["risklocker_logo", "insurer_logo", "bank_logo", "all_driver_icon", "background"];
const variableTypes = ["text", "money", "number", "date", "percent", "image", "boolean", "choice", "benefit_card"];
const sourceFields = ["customer_name", "vehicle_no", "insurance_company", "coverage_type", "cover_period", "car_model", "ncd_percent", "coverage_amount", "premium", "roadtax", "service_fee", "total_amount", "valid_until"];

function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)); }
function makeId(prefix: string) { return `${prefix}_${Math.random().toString(36).slice(2, 9)}`; }
function slug(value: string) { return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || makeId("var"); }
function defaultStyle(type: string): CanvasStyle {
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

const SNAP = 8;
const GUIDE_THRESHOLD = 6;

export default function TemplateBuilderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [template, setTemplate] = useState<TemplateRecord | null>(null);
  const [assets, setAssets] = useState<AssetRecord[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [zoom, setZoom] = useState(0.72);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [history, setHistory] = useState<TemplateConfig[]>([]);
  const [future, setFuture] = useState<TemplateConfig[]>([]);
  const [newVariable, setNewVariable] = useState({ label: "", type: "text", field: "" });
  const [showGrid, setShowGrid] = useState(true);
  const [previewMode, setPreviewMode] = useState(false);
  const [guides, setGuides] = useState<{ x: number; y: number }[]>([]);
  const [uploading, setUploading] = useState(false);
  const dragRef = useRef<DragState | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function load() {
    const [templateResult, assetResult] = await Promise.all([
      api<{ template: TemplateRecord }>(`/admin/templates/${id}`),
      api<{ assets: AssetRecord[] }>("/admin/template-assets")
    ]);
    setTemplate(templateResult.template);
    setAssets(assetResult.assets);
    setSelectedId(templateResult.template.fixed_fields.canvas.elements[0]?.id || "");
  }

  useEffect(() => {
    if (authLoading || !user) return;
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load template builder."));
  }, [id, authLoading, user]);

  const config = template?.fixed_fields;
  const elements = config?.canvas?.elements || [];
  const selected = elements.find((item) => item.id === selectedId) || null;
  const readOnly = Boolean(template?.locked) || previewMode;
  const selectedCard = selected?.cardId && config?.cards ? config.cards[selected.cardId] : null;
  const sortedElements = useMemo(() => [...elements].sort((a, b) => (a.z || 1) - (b.z || 1)), [elements]);

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
    setSelectedId(element.id);
  }

  function deleteSelected() {
    if (!selected || readOnly) return;
    commit((current) => { current.canvas.elements = current.canvas.elements.filter((item) => item.id !== selected.id); return current; });
    setSelectedId("");
  }

  function duplicateSelected() {
    if (!selected || readOnly) return;
    const copy = { ...clone(selected), id: makeId(selected.type), x: selected.x + 18, y: selected.y + 18, z: (selected.z || 1) + 1 };
    commit((current) => { current.canvas.elements.push(copy); return current; });
    setSelectedId(copy.id);
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
    if (!selected || readOnly) return;
    const maxZ = Math.max(0, ...elements.map((item) => item.z || 1));
    if ((selected.z || 1) >= maxZ) return;
    updateElement(selected.id, { z: (selected.z || 1) + 1 });
  }

  function bringToFront() {
    if (!selected || readOnly) return;
    const maxZ = Math.max(0, ...elements.map((item) => item.z || 1));
    updateElement(selected.id, { z: maxZ + 1 });
  }

  function sendBackward() {
    if (!selected || readOnly) return;
    if ((selected.z || 1) <= 1) return;
    updateElement(selected.id, { z: (selected.z || 1) - 1 });
  }

  function sendToBack() {
    if (!selected || readOnly) return;
    updateElement(selected.id, { z: 1 });
  }

  function snapValue(value: number, grid: number, otherEdges: number[]) {
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

  function computeGuides(moving: CanvasElement, next: Partial<CanvasElement>) {
    const rect = { x: next.x ?? moving.x, y: next.y ?? moving.y, w: next.w ?? moving.w, h: next.h ?? moving.h };
    const edges = [0, (config?.canvas.width || 794) / 2, config?.canvas.width || 794];
    const myEdges = [rect.x, rect.x + rect.w / 2, rect.x + rect.w, rect.y, rect.y + rect.h / 2, rect.y + rect.h];
    const guidePositions: { x: number; y: number }[] = [];
    for (const el of elements) {
      if (el.id === moving.id) continue;
      const ex = [el.x, el.x + el.w / 2, el.x + el.w, el.y, el.y + el.h / 2, el.y + el.h];
      for (const a of myEdges.slice(0, 3)) for (const b of ex.slice(0, 3)) if (Math.abs(a - b) <= GUIDE_THRESHOLD) guidePositions.push({ x: b, y: 0 });
      for (const a of myEdges.slice(3)) for (const b of ex.slice(3)) if (Math.abs(a - b) <= GUIDE_THRESHOLD) guidePositions.push({ x: 0, y: b });
    }
    for (const e of edges) {
      for (const a of [rect.x, rect.x + rect.w / 2, rect.x + rect.w]) if (Math.abs(a - e) <= GUIDE_THRESHOLD) guidePositions.push({ x: e, y: 0 });
      for (const a of [rect.y, rect.y + rect.h / 2, rect.y + rect.h]) if (Math.abs(a - e) <= GUIDE_THRESHOLD) guidePositions.push({ x: 0, y: e });
    }
    return guidePositions;
  }

  function pointerDown(event: React.PointerEvent, element: CanvasElement, mode: "move" | "resize", handle?: string) {
    if (readOnly) return;
    event.preventDefault();
    event.stopPropagation();
    setSelectedId(element.id);
    dragRef.current = { id: element.id, mode, startX: event.clientX, startY: event.clientY, start: clone(element), handle };
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
      const guides = computeGuides(drag.start, { x: nx, y: ny });
      setGuides(guides);
      setTemplate((current) => {
        if (!current) return current;
        const next = clone(current);
        next.fixed_fields.canvas.elements = next.fixed_fields.canvas.elements.map((item: CanvasElement) => item.id === drag.id ? { ...item, x: nx, y: ny } : item);
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
      const guides = computeGuides(drag.start, patch);
      setGuides(guides);
      setTemplate((current) => {
        if (!current) return current;
        const next = clone(current);
        next.fixed_fields.canvas.elements = next.fixed_fields.canvas.elements.map((item: CanvasElement) => item.id === drag.id ? { ...item, ...patch } : item);
        return { ...current, fixed_fields: next.fixed_fields };
      });
    }
  }

  function pointerUp() {
    const drag = dragRef.current;
    dragRef.current = null;
    setGuides([]);
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
    setMessage(status === "active" ? "Template published." : "Template saved.");
  }

  async function uploadAsset(file: File) {
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("label", file.name.replace(/\.[^.]+$/, ""));
      const result = await api<{ asset: AssetRecord }>("/admin/template-assets", { method: "POST", body: form });
      setAssets((current) => [result.asset, ...current]);
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
      const meta = event.ctrlKey || event.metaKey;
      if (meta && event.key.toLowerCase() === "z") { event.preventDefault(); if (event.shiftKey) redo(); else undo(); return; }
      if (meta && event.key.toLowerCase() === "y") { event.preventDefault(); redo(); return; }
      if (meta && event.key.toLowerCase() === "d") { event.preventDefault(); duplicateSelected(); return; }
      if (!selected) return;
      if (event.key === "Delete" || event.key === "Backspace") { event.preventDefault(); deleteSelected(); return; }
      const step = event.shiftKey ? 10 : 1;
      if (event.key === "ArrowUp") { event.preventDefault(); updateElement(selected.id, { y: selected.y - step }); }
      else if (event.key === "ArrowDown") { event.preventDefault(); updateElement(selected.id, { y: selected.y + step }); }
      else if (event.key === "ArrowLeft") { event.preventDefault(); updateElement(selected.id, { x: selected.x - step }); }
      else if (event.key === "ArrowRight") { event.preventDefault(); updateElement(selected.id, { x: selected.x + step }); }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selected, readOnly, history, future, elements]);

  useEffect(() => {
    if (!authLoading && user === null) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  if (authLoading || user === null) {
    return (
      <div className="grid min-h-screen place-items-center bg-rl-soft">
        <p className="text-sm text-rl-text">Checking session…</p>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-rl-soft text-rl-text">
      <div className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-3 border-b border-rl-line bg-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <Link className="rl-button rl-button-secondary" href="/builder/templates"><ArrowLeft aria-hidden="true" size={18} />Templates</Link>
          <input className="rl-input w-72 font-bold" value={template?.name || ""} disabled={readOnly} onChange={(event) => setTemplate((current) => current ? { ...current, name: event.target.value } : current)} />
          {template?.locked ? <span className="rounded-md border border-rl-line px-2 py-1 text-sm font-bold">Locked default</span> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className={`rl-button rl-button-secondary ${showGrid ? "bg-rl-soft" : ""}`} type="button" onClick={() => setShowGrid((v) => !v)} title="Toggle grid"><Grid3x3 aria-hidden="true" size={18} />Grid</button>
          <button className={`rl-button rl-button-secondary ${previewMode ? "bg-rl-soft" : ""}`} type="button" onClick={() => setPreviewMode((v) => !v)} title="Preview"><Layers aria-hidden="true" size={18} />{previewMode ? "Edit" : "Preview"}</button>
          <button className="rl-button rl-button-secondary" type="button" onClick={undo} disabled={!history.length || readOnly}><Undo2 aria-hidden="true" size={18} />Undo</button>
          <button className="rl-button rl-button-secondary" type="button" onClick={redo} disabled={!future.length || readOnly}><Redo2 aria-hidden="true" size={18} />Redo</button>
          {template?.locked ? (
            <button className="rl-button" type="button" onClick={copyLocked}><Copy aria-hidden="true" size={18} />Copy to edit</button>
          ) : (
            <>
              <button className="rl-button rl-button-secondary" type="button" onClick={() => save()}><Save aria-hidden="true" size={18} />Save draft</button>
              <button className="rl-button" type="button" onClick={() => save("active")}>Publish</button>
            </>
          )}
        </div>
      </div>

      {error ? <p className="m-4 rounded-md border border-rl-red bg-red-50 p-3 font-bold text-rl-red">{error}</p> : null}
      {message ? <p className="m-4 rounded-md border border-rl-success bg-green-50 p-3 font-bold text-rl-success">{message}</p> : null}

      <div className="grid min-h-[calc(100vh-73px)] grid-cols-[280px_minmax(0,1fr)_320px]">
        {!previewMode ? (
          <aside className="overflow-auto border-r border-rl-line bg-white p-4">
            <h2 className="font-bold text-rl-textStrong">Elements</h2>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button className="rl-button rl-button-secondary justify-start" type="button" disabled={readOnly} onClick={() => addElement("text", { text: "Text block" })}><TextCursorInput aria-hidden="true" size={16} />Text</button>
              <button className="rl-button rl-button-secondary justify-start" type="button" disabled={readOnly} onClick={() => addElement("variable", { variableId: config?.variables?.[0]?.id || "customer_name" })}><Variable aria-hidden="true" size={16} />Variable</button>
              <button className="rl-button rl-button-secondary justify-start" type="button" disabled={readOnly} onClick={() => addElement("image", { w: 120, h: 80 })}><ImageIcon aria-hidden="true" size={16} />Image</button>
              <button className="rl-button rl-button-secondary justify-start" type="button" disabled={readOnly} onClick={() => addElement("group", { w: 180, h: 80 })}><Square aria-hidden="true" size={16} />Box</button>
              <button className="rl-button rl-button-secondary justify-start" type="button" disabled={readOnly} onClick={() => addElement("line", { w: 280, h: 2, style: { borderWidth: 2 } })}>Line</button>
              <button className="rl-button rl-button-secondary justify-start" type="button" disabled={readOnly} onClick={() => addElement("benefit-section", { section: "specials", w: 520, h: 180 })}>Specials</button>
              <button className="rl-button rl-button-secondary justify-start" type="button" disabled={readOnly} onClick={() => addElement("benefit-section", { section: "add_ons", w: 520, h: 180 })}>Add-ons</button>
            </div>

            <h2 className="mt-6 font-bold text-rl-textStrong">Variables</h2>
            <div className="mt-3 grid gap-2">
              <input className="rl-input" placeholder="Variable label" value={newVariable.label} disabled={readOnly} onChange={(event) => setNewVariable((current) => ({ ...current, label: event.target.value }))} />
              <select className="rl-input" value={newVariable.type} disabled={readOnly} onChange={(event) => setNewVariable((current) => ({ ...current, type: event.target.value }))}>{variableTypes.map((item) => <option key={item} value={item}>{item}</option>)}</select>
              <select className="rl-input" value={newVariable.field} disabled={readOnly} onChange={(event) => setNewVariable((current) => ({ ...current, field: event.target.value }))}>
                <option value="">Manual only</option>
                {sourceFields.map((field) => <option key={field} value={field}>{field}</option>)}
              </select>
              <button className="rl-button rl-button-secondary" type="button" disabled={readOnly} onClick={addVariable}>Add variable</button>
              <div className="grid max-h-48 gap-1 overflow-auto text-sm">
                {config?.variables?.map((variable) => <button key={variable.id} className="rounded border border-rl-line px-2 py-1 text-left hover:bg-rl-soft" type="button" onClick={() => addElement("variable", { variableId: variable.id })}>{variable.label}</button>)}
              </div>
            </div>

            <h2 className="mt-6 font-bold text-rl-textStrong">Assets</h2>
            <div className="mt-3 grid gap-2">
              <input ref={fileInputRef} className="sr-only" type="file" accept=".png,.jpg,.jpeg,.svg" onChange={(event) => event.target.files?.[0] && uploadAsset(event.target.files[0])} />
              <button className="rl-button rl-button-secondary justify-start" type="button" disabled={readOnly || uploading} onClick={() => fileInputRef.current?.click()}><Upload aria-hidden="true" size={16} />{uploading ? "Uploading" : "Upload asset"}</button>
              <div className="grid max-h-64 gap-2 overflow-auto">
                {assets.map((asset) => (
                  <button key={asset.id} className="grid grid-cols-[44px_1fr] items-center gap-2 rounded border border-rl-line p-2 text-left text-xs hover:bg-rl-soft" type="button" disabled={readOnly} onClick={() => addElement("image", { assetId: asset.id, w: 120, h: 70 })}>
                    <img className="h-10 w-10 object-contain" src={fileUrl(asset.url)} alt="" />
                    <span>{asset.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <h2 className="mt-6 font-bold text-rl-textStrong">Benefit Cards</h2>
            <div className="mt-3 grid max-h-64 gap-2 overflow-auto">
              {Object.entries(config?.cards || {}).map(([cardId, card]) => (
                <button key={cardId} className="rounded border border-rl-line p-2 text-left text-xs hover:bg-rl-soft" type="button" disabled={readOnly} onClick={() => addElement("benefit-card", { cardId, w: 310, h: 58 })}>
                  <strong>{card.title || cardId}</strong>
                  {card.subtitle ? <span className="block">{card.subtitle}</span> : null}
                </button>
              ))}
            </div>
          </aside>
        ) : <div />}

        <section className="overflow-auto p-6">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-bold text-rl-textStrong">Canvas</div>
            <label className="flex items-center gap-2 text-sm font-bold">Zoom<input className="w-32" type="range" min="0.45" max="1.1" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
          </div>
          <div className="mx-auto w-fit rounded-md bg-neutral-300 p-6 shadow-inner">
            <div
              ref={canvasRef}
              className="relative origin-top-left overflow-hidden bg-white shadow-xl"
              style={{ width: config?.canvas.width || 794, height: config?.canvas.height || 1123, transform: `scale(${zoom})`, marginBottom: `${((config?.canvas.height || 1123) * zoom) - (config?.canvas.height || 1123)}px` }}
              onPointerMove={pointerMove}
              onPointerUp={pointerUp}
              onPointerLeave={pointerUp}
              onClick={() => setSelectedId("")}
            >
              {showGrid && !previewMode && (
                <div className="pointer-events-none absolute inset-0 opacity-10" style={{ backgroundImage: `linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)`, backgroundSize: `${SNAP * zoom}px ${SNAP * zoom}px` }} />
              )}
              {guides.map((guide, index) => (
                guide.x > 0 ? (
                  <div key={`v${index}`} className="pointer-events-none absolute top-0 bottom-0 border-l border-dashed border-rl-red" style={{ left: guide.x, zIndex: 9999 }} />
                ) : (
                  <div key={`h${index}`} className="pointer-events-none absolute left-0 right-0 border-t border-dashed border-rl-red" style={{ top: guide.y, zIndex: 9999 }} />
                )
              ))}
              {sortedElements.map((element) => (
                <CanvasElementView key={element.id} element={element} selected={!previewMode && element.id === selectedId} assets={assets} config={config} readOnly={readOnly} onPointerDown={(event) => pointerDown(event, element, "move")} onResizePointerDown={(event, handle) => pointerDown(event, element, "resize", handle)} />
              ))}
            </div>
          </div>
        </section>

        {!previewMode ? (
          <aside className="overflow-auto border-l border-rl-line bg-white p-4">
            <h2 className="font-bold text-rl-textStrong">Properties</h2>
            {selected ? (
              <div className="mt-3 grid gap-3">
                <div className="grid grid-cols-2 gap-2">
                  {(["x", "y", "w", "h", "z"] as const).map((key) => <label key={key} className="grid gap-1 text-xs font-bold uppercase">{key}<input className="rl-input" type="number" value={selected[key] || 0} disabled={readOnly} onChange={(event) => updateElement(selected.id, { [key]: Number(event.target.value) })} /></label>)}
                </div>
                {selected.type === "text" ? <label className="grid gap-1 font-bold">Text<textarea className="rl-input min-h-24" value={selected.text || ""} disabled={readOnly} onChange={(event) => updateElement(selected.id, { text: event.target.value })} /></label> : null}
                {selected.type === "variable" ? (
                  <>
                    <label className="grid gap-1 font-bold">Variable<select className="rl-input" value={selected.variableId || ""} disabled={readOnly} onChange={(event) => updateElement(selected.id, { variableId: event.target.value })}>{config?.variables?.map((variable) => <option key={variable.id} value={variable.id}>{variable.label}</option>)}</select></label>
                    <input className="rl-input" placeholder="Prefix" value={selected.prefix || ""} disabled={readOnly} onChange={(event) => updateElement(selected.id, { prefix: event.target.value })} />
                    <input className="rl-input" placeholder="Suffix" value={selected.suffix || ""} disabled={readOnly} onChange={(event) => updateElement(selected.id, { suffix: event.target.value })} />
                  </>
                ) : null}
                {selected.type === "image" ? (
                  <>
                    <label className="grid gap-1 font-bold">Asset slot<select className="rl-input" value={selected.assetSlot || ""} disabled={readOnly} onChange={(event) => updateElement(selected.id, { assetSlot: event.target.value, assetId: "" })}><option value="">Direct asset</option>{assetSlots.map((slot) => <option key={slot} value={slot}>{slot}</option>)}</select></label>
                    <label className="grid gap-1 font-bold">Asset<select className="rl-input" value={selected.assetId || ""} disabled={readOnly} onChange={(event) => updateElement(selected.id, { assetId: event.target.value, assetSlot: "" })}><option value="">Choose asset</option>{assets.map((asset) => <option key={asset.id} value={asset.id}>{asset.label}</option>)}</select></label>
                  </>
                ) : null}
                {selected.type === "benefit-section" ? (
                  <>
                    <label className="grid gap-1 font-bold">Section<select className="rl-input" value={selected.section || "specials"} disabled={readOnly} onChange={(event) => updateElement(selected.id, { section: event.target.value as "specials" | "add_ons" })}><option value="specials">Our Specials</option><option value="add_ons">You May Add On</option></select></label>
                    <label className="grid gap-1 font-bold">Columns<input className="rl-input" type="number" min={1} max={3} value={selected.columns || 2} disabled={readOnly} onChange={(event) => updateElement(selected.id, { columns: Number(event.target.value) })} /></label>
                  </>
                ) : null}
                {selected.type === "benefit-card" ? (
                  <>
                    <label className="grid gap-1 font-bold">Card<select className="rl-input" value={selected.cardId || ""} disabled={readOnly} onChange={(event) => updateElement(selected.id, { cardId: event.target.value })}>{Object.entries(config?.cards || {}).map(([cardId, card]) => <option key={cardId} value={cardId}>{card.title || cardId}</option>)}</select></label>
                    {selectedCard ? <CardEditor cardId={selected.cardId || ""} card={selectedCard} assets={assets} readOnly={readOnly} onChange={(cardId, card) => commit((current) => { current.cards[cardId] = card; return current; })} /> : null}
                  </>
                ) : null}
                <StyleEditor selected={selected} readOnly={readOnly} onChange={(style) => updateElement(selected.id, { style })} />
                <div className="grid gap-2 rounded-md border border-rl-line p-3">
                  <h3 className="font-bold text-rl-textStrong">Layer</h3>
                  <div className="grid grid-cols-2 gap-2">
                    <button className="rl-button rl-button-secondary" type="button" disabled={readOnly} onClick={bringToFront}><BringToFront size={16} />Front</button>
                    <button className="rl-button rl-button-secondary" type="button" disabled={readOnly} onClick={bringForward}><Layers size={16} />Forward</button>
                    <button className="rl-button rl-button-secondary" type="button" disabled={readOnly} onClick={sendBackward}><Layers size={16} />Back</button>
                    <button className="rl-button rl-button-secondary" type="button" disabled={readOnly} onClick={sendToBack}><SendToBack size={16} />Bottom</button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button className="rl-button rl-button-secondary" type="button" disabled={readOnly} onClick={duplicateSelected}><Copy aria-hidden="true" size={16} />Duplicate</button>
                  <button className="rl-button rl-button-secondary" type="button" disabled={readOnly} onClick={deleteSelected}><Trash2 aria-hidden="true" size={16} />Delete</button>
                </div>
              </div>
            ) : <p className="mt-3 text-sm">Select an element on the canvas.</p>}
          </aside>
        ) : <div />}
      </div>
    </main>
  );
}

function CanvasElementView({ element, selected, assets, config, readOnly, onPointerDown, onResizePointerDown }: { element: CanvasElement; selected: boolean; assets: AssetRecord[]; config?: TemplateConfig; readOnly: boolean; onPointerDown: (event: React.PointerEvent) => void; onResizePointerDown: (event: React.PointerEvent, handle: string) => void }) {
  const assetId = element.assetId || (element.assetSlot ? config?.assets?.[element.assetSlot] : "");
  const asset = assets.find((item) => item.id === assetId);
  const style = element.style || {};
  const common: React.CSSProperties = {
    position: "absolute", left: element.x, top: element.y, width: element.w, height: element.h, zIndex: element.z || 1,
    fontSize: style.fontSize || 14, fontWeight: style.fontWeight || "400", color: style.color || "#111111",
    textAlign: (style.textAlign || "left") as React.CSSProperties["textAlign"],
    border: `${style.borderWidth || 0}px solid ${style.borderColor || "#111111"}`,
    background: style.background || "transparent", opacity: element.opacity ?? 1, overflow: "hidden", whiteSpace: "pre-wrap"
  };
  const handles = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];
  return (
    <div className={selected ? "outline outline-2 outline-rl-blue" : "outline outline-1 outline-transparent hover:outline-rl-line"} style={common} onPointerDown={onPointerDown} onClick={(event) => event.stopPropagation()}>
      {element.type === "image" && asset ? <img className="h-full w-full object-contain" src={fileUrl(asset.url)} alt="" /> : null}
      {element.type === "text" ? element.text : null}
      {element.type === "variable" ? <span className="text-rl-blue">{element.prefix || ""}{`{${element.variableId || "variable"}}`}{element.suffix || ""}</span> : null}
      {element.type === "benefit-section" ? <div className="p-1 text-xs font-bold text-rl-blue">{element.section === "add_ons" ? "Add-on card section" : "Special card section"}</div> : null}
      {element.type === "benefit-card" ? <div className="p-1 text-xs font-bold">{config?.cards?.[element.cardId || ""]?.title || "Benefit card"}</div> : null}
      {selected && !readOnly ? handles.map((handle) => {
        const pos = { nw: "top-0 left-0", n: "top-0 left-1/2 -translate-x-1/2", ne: "top-0 right-0", e: "top-1/2 right-0 -translate-y-1/2", se: "bottom-0 right-0", s: "bottom-0 left-1/2 -translate-x-1/2", sw: "bottom-0 left-0", w: "top-1/2 left-0 -translate-y-1/2" }[handle];
        return <span key={handle} className={`absolute ${pos} h-3 w-3 cursor-${handle.includes("n") || handle.includes("s") ? (handle.includes("e") || handle.includes("w") ? "nwse-resize" : "ns-resize") : "ew-resize"} border border-rl-blue bg-white`} onPointerDown={(event) => onResizePointerDown(event, handle)} />;
      }) : null}
    </div>
  );
}

function StyleEditor({ selected, readOnly, onChange }: { selected: CanvasElement; readOnly: boolean; onChange: (style: CanvasStyle) => void }) {
  const style = selected.style || {};
  return (
    <div className="grid gap-2 rounded-md border border-rl-line p-3">
      <h3 className="font-bold text-rl-textStrong">Style</h3>
      <label className="grid gap-1 text-xs font-bold uppercase">Font size<input className="rl-input" type="number" value={style.fontSize || 14} disabled={readOnly} onChange={(event) => onChange({ fontSize: Number(event.target.value) })} /></label>
      <label className="grid gap-1 text-xs font-bold uppercase">Weight<input className="rl-input" value={style.fontWeight || "400"} disabled={readOnly} onChange={(event) => onChange({ fontWeight: event.target.value })} /></label>
      <label className="grid gap-1 text-xs font-bold uppercase">Text color<input className="rl-input h-11" type="color" value={style.color || "#111111"} disabled={readOnly} onChange={(event) => onChange({ color: event.target.value })} /></label>
      <label className="grid gap-1 text-xs font-bold uppercase">Background<input className="rl-input h-11" type="color" value={style.background && style.background !== "transparent" ? style.background : "#ffffff"} disabled={readOnly} onChange={(event) => onChange({ background: event.target.value })} /></label>
      <label className="grid gap-1 text-xs font-bold uppercase">Border<input className="rl-input" type="number" value={style.borderWidth || 0} disabled={readOnly} onChange={(event) => onChange({ borderWidth: Number(event.target.value) })} /></label>
    </div>
  );
}

function CardEditor({ cardId, card, assets, readOnly, onChange }: { cardId: string; card: BenefitCard; assets: AssetRecord[]; readOnly: boolean; onChange: (cardId: string, card: BenefitCard) => void }) {
  function patch(update: Partial<BenefitCard>) { onChange(cardId, { ...card, ...update }); }
  return (
    <div className="grid gap-2 rounded-md border border-rl-line p-3">
      <h3 className="font-bold text-rl-textStrong">Card content</h3>
      <input className="rl-input" value={card.title || ""} disabled={readOnly} onChange={(event) => patch({ title: event.target.value })} />
      <input className="rl-input" value={card.subtitle || ""} disabled={readOnly} onChange={(event) => patch({ subtitle: event.target.value })} />
      <textarea className="rl-input min-h-20" value={(card.lines || []).join("\n")} disabled={readOnly} onChange={(event) => patch({ lines: event.target.value.split(/\r?\n/).filter(Boolean) })} />
      <select className="rl-input" value={card.asset_id || ""} disabled={readOnly} onChange={(event) => patch({ asset_id: event.target.value })}>
        <option value="">Auto icon asset</option>
        {assets.map((asset) => <option key={asset.id} value={asset.id}>{asset.label}</option>)}
      </select>
    </div>
  );
}
