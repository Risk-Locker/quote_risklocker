"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowArcLeft,
  ArrowArcRight,
  ArrowLeft,
  BracketsCurly,
  Cards,
  CaretDoubleDown,
  CaretDoubleUp,
  CaretDown,
  CaretUp,
  CopySimple,
  FloppyDisk,
  GridFour,
  Image,
  LineSegment,
  MagnifyingGlass,
  Plus,
  Square,
  TextT,
  Trash,
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
import { CanvasElementView, type CanvasElement, type CanvasStyle, SNAP, snapValue, computeGuides } from "@/components/template-canvas/shared";

type TemplateVariable = { id: string; label: string; type: string; source: string; field?: string; fixed_value?: string };
type BenefitCard = { icon?: string; title?: string; subtitle?: string; lines?: string[]; asset_id?: string };
type PackageConfig = { name: string; included_cards?: string[]; add_on_cards?: string[]; included?: string[]; add_ons?: string[] };
type TemplateConfig = { variables: TemplateVariable[]; cards: Record<string, BenefitCard>; packages: PackageConfig[]; assets: Record<string, string>; canvas: { width: number; height: number; elements: CanvasElement[] } };
type TemplateRecord = { id: string; name: string; insurance_type: string; status: string; locked: boolean; fixed_fields: TemplateConfig };
type AssetRecord = { id: string; label: string; filename: string; url: string; source?: string };
type DragState = { id: string; mode: "move" | "resize"; startX: number; startY: number; start: CanvasElement; handle?: string };
type VariantItem = { id: string; special_id: string; label: string; secondary_label?: string | null; value_text?: string | null; icon_asset_id?: string | null; shape?: string | null; bg_color?: string | null; text_color?: string | null; border_width?: string | null; border_color?: string | null; shadow?: string | null; status: string };
type SpecialItem = { id: string; label: string; category: string; status: string; variants: VariantItem[] };

const assetSlots = ["risklocker_logo", "insurer_logo", "bank_logo", "all_driver_icon", "background"];
const variableTypes = ["text", "money", "number", "date", "percent", "image", "boolean", "choice", "benefit_card"];
const sourceFields = ["customer_name", "vehicle_no", "insurance_company", "coverage_type", "cover_period", "car_model", "ncd_percent", "coverage_amount", "premium", "roadtax", "service_fee", "total_amount", "valid_until"];

function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)); }
function makeId(prefix: string) { return `${prefix}_${Math.random().toString(36).slice(2, 9)}`; }
function slug(value: string) { return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || makeId("var"); }
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
  const [selectedId, setSelectedId] = useState("");
  const [zoom, setZoom] = useState(0.72);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<TemplateConfig[]>([]);
  const [future, setFuture] = useState<TemplateConfig[]>([]);
  const [newVariable, setNewVariable] = useState({ label: "", type: "text", field: "" });
  const [showGrid, setShowGrid] = useState(true);
  const [previewMode, setPreviewMode] = useState(false);
  const [guides, setGuides] = useState<{ x: number; y: number }[]>([]);
  const [uploading, setUploading] = useState(false);
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
    setSelectedId(element.id);
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
      setSelectedId(element.id);
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
      const guides = computeGuides(drag.start, { x: nx, y: ny }, elements, config?.canvas.width || 794, (config?.canvas.width || 794) / 2);
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
    toast(status === "active" ? "Template published." : "Template saved.", "success");
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
      <div className="grid min-h-screen place-items-center bg-[var(--rl-bg)]">
        <div className="flex items-center gap-2 text-sm text-[var(--rl-text-muted)]">
          <Spinner size={16} />
          Checking session...
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--rl-bg)] text-[var(--rl-text)]">
      <div className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] bg-[var(--rl-surface)]/95 px-4 py-3 backdrop-blur-md">
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
        <div className="m-4 rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
          {error}
        </div>
      ) : null}

      <div className="grid min-h-[calc(100vh-73px)] grid-cols-[280px_minmax(0,1fr)_320px]">
        {!previewMode ? (
          <aside className="overflow-auto border-r border-[var(--rl-border)] bg-[var(--rl-surface)] p-4">
            <h2 className="font-bold text-[var(--rl-text-strong)]">Elements</h2>
            <div className="mt-3 grid grid-cols-2 gap-2">
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
                icon={<Cards weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("benefit-section", { section: "specials", w: 520, h: 180 })}
                className="justify-start"
              >
                Specials
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<Plus weight="bold" size={16} />}
                disabled={readOnly}
                onClick={() => addElement("benefit-section", { section: "add_ons", w: 520, h: 180 })}
                className="justify-start"
              >
                Add-ons
              </Button>
            </div>

            <h2 className="mt-6 font-bold text-[var(--rl-text-strong)]">Variables</h2>
            <div className="mt-3 grid gap-2">
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

            <h2 className="mt-6 font-bold text-[var(--rl-text-strong)]">Assets</h2>
            <div className="mt-3 grid gap-2">
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
                {assets.map((asset) => (
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
            </div>

            <h2 className="mt-6 font-bold text-[var(--rl-text-strong)]">Our Specials</h2>
            <div className="mt-3 grid gap-2">
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
            <div
              ref={canvasRef}
              className="relative origin-top-left overflow-hidden bg-white shadow-xl"
              style={{ width: config?.canvas.width || 794, height: config?.canvas.height || 1123, transform: `scale(${zoom})` }}
              onPointerMove={pointerMove}
              onPointerUp={pointerUp}
              onPointerLeave={pointerUp}
              onDragOver={handleCanvasDragOver}
              onDrop={handleCanvasDrop}
              onClick={() => setSelectedId("")}
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
              {sortedElements.map((element) => (
                <CanvasElementView key={element.id} element={element} selected={!previewMode && element.id === selectedId} assets={assets} config={config} readOnly={readOnly} onPointerDown={(event) => pointerDown(event, element, "move")} onResizePointerDown={(event, handle) => pointerDown(event, element, "resize", handle)} />
              ))}
            </div>
          </div>
        </section>

        {!previewMode ? (
          <aside className="overflow-auto border-l border-[var(--rl-border)] bg-[var(--rl-surface)] p-4">
            <h2 className="font-bold text-[var(--rl-text-strong)]">Properties</h2>
            {selected ? (
              <div className="mt-3 grid gap-3">
                <div className="grid grid-cols-2 gap-2">
                  {(["x", "y", "w", "h", "z"] as const).map((key) => (
                    <label key={key} className="grid gap-1 text-xs font-bold uppercase">
                      {key}
                      <Input
                        type="number"
                        value={selected[key] || 0}
                        disabled={readOnly}
                        onChange={(event) => updateElement(selected.id, { [key]: Number(event.target.value) })}
                      />
                    </label>
                  ))}
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
                  </div>
                ) : null}
                <StyleEditor selected={selected} readOnly={readOnly} onChange={(style) => updateElement(selected.id, { style })} />
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
                  <Button variant="secondary" size="sm" icon={<CopySimple weight="bold" size={14} />} disabled={readOnly} onClick={duplicateSelected}>Duplicate</Button>
                  <Button variant="danger" size="sm" icon={<Trash weight="bold" size={14} />} disabled={readOnly} onClick={deleteSelected}>Delete</Button>
                </div>
              </div>
            ) : <p className="mt-3 text-sm text-[var(--rl-text-muted)]">Select an element on the canvas.</p>}
          </aside>
        ) : <div />}
      </div>
    </main>
  );
}

function StyleEditor({ selected, readOnly, onChange }: { selected: CanvasElement; readOnly: boolean; onChange: (style: CanvasStyle) => void }) {
  const style = selected.style || {};
  return (
    <div className="grid gap-2 rounded-md border border-[var(--rl-border)] p-3">
      <h3 className="font-bold text-[var(--rl-text-strong)]">Style</h3>
      <label className="grid gap-1 text-xs font-bold uppercase">
        Font size
        <Input type="number" value={style.fontSize || 14} disabled={readOnly} onChange={(event) => onChange({ fontSize: Number(event.target.value) })} />
      </label>
      <label className="grid gap-1 text-xs font-bold uppercase">
        Weight
        <Input value={style.fontWeight || "400"} disabled={readOnly} onChange={(event) => onChange({ fontWeight: event.target.value })} />
      </label>
      <label className="grid gap-1 text-xs font-bold uppercase">
        Text color
        <Input className="h-11" type="color" value={style.color || "#111111"} disabled={readOnly} onChange={(event) => onChange({ color: event.target.value })} />
      </label>
      <label className="grid gap-1 text-xs font-bold uppercase">
        Background
        <Input className="h-11" type="color" value={style.background && style.background !== "transparent" ? style.background : "#ffffff"} disabled={readOnly} onChange={(event) => onChange({ background: event.target.value })} />
      </label>
      <label className="grid gap-1 text-xs font-bold uppercase">
        Border
        <Input type="number" value={style.borderWidth || 0} disabled={readOnly} onChange={(event) => onChange({ borderWidth: Number(event.target.value) })} />
      </label>
    </div>
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
