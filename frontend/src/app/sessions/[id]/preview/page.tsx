"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  TextT, BracketsCurly, Image, Square, LineSegment, ArrowLeft,
  FloppyDisk, DownloadSimple, FileImage, ArrowArcLeft, ArrowArcRight,
  Trash, Plus, PencilSimple, X, CaretUp, CaretDown,
} from "@phosphor-icons/react";
import {
  CanvasElementView, shapeRadii, shadowMap,
  SNAP, snapValue, computeGuides,
} from "@/components/template-canvas/shared";
import type { CanvasElement, CanvasStyle } from "@/components/template-canvas/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { SessionPhaseBar } from "@/components/session-phase-bar";
import { api, apiRaw, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type TemplateConfig = {
  variables: Array<{ id: string; label: string; field?: string; source?: string }>;
  canvas: { width: number; height: number; elements: CanvasElement[] };
  assets: Record<string, string>;
};
type AssetRecord = { id: string; label: string; filename: string; url: string; source?: string };
type VariantItem = {
  id: string; special_id: string; label: string; secondary_label?: string | null;
  value_text?: string | null; icon_asset_id?: string | null; shape?: string | null;
  bg_color?: string | null; text_color?: string | null;
  border_width?: string | null; border_color?: string | null; shadow?: string | null;
};
type SpecialItem = { id: string; label: string; category: string; variants: VariantItem[] };
type DraftField = { value?: string | null };
type TemplateRecord = { id: string; name: string; insurance_company_name?: string | null; fixed_fields: TemplateConfig };
type DragState = { id: string; startX: number; startY: number; startEl: CanvasElement };
type ResizeState = { id: string; handle: string; startX: number; startY: number; startEl: CanvasElement };

const MAX_HISTORY = 30;

function makeId(prefix: string) { return `${prefix}_${Math.random().toString(36).slice(2, 9)}`; }
function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)); }

export default function SessionPreviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { toast } = useToast();

  const [elements, setElements] = useState<CanvasElement[]>([]);
  const [fields, setFields] = useState<Record<string, DraftField>>({});
  const [config, setConfig] = useState<TemplateConfig | null>(null);
  const [template, setTemplate] = useState<TemplateRecord | null>(null);
  const [draftId, setDraftId] = useState("");
  const [assets, setAssets] = useState<AssetRecord[]>([]);
  const [specials, setSpecials] = useState<SpecialItem[]>([]);
  const [zoom, setZoom] = useState(0.65);
  const [selectedId, setSelectedId] = useState("");
  const [history, setHistory] = useState<CanvasElement[][]>([]);
  const [future, setFuture] = useState<CanvasElement[][]>([]);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [templateName, setTemplateName] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyPdf, setBusyPdf] = useState(false);
  const [busyPng, setBusyPng] = useState(false);

  const dragRef = useRef<DragState | null>(null);
  const resizeRef = useRef<ResizeState | null>(null);
  const pendingElementsRef = useRef<CanvasElement[]>([]);

  const canvasW = config?.canvas?.width || 794;
  const canvasH = config?.canvas?.height || 1123;
  const selected = elements.find((e) => e.id === selectedId) || null;

  function pushHistory(els: CanvasElement[]) {
    setHistory((h) => (h.length >= MAX_HISTORY ? [...h.slice(1), els] : [...h, els]));
    setFuture([]);
  }

  const undo = useCallback(() => {
    if (history.length === 0) return;
    const prev = history[history.length - 1];
    setFuture((f) => [clone(elements), ...f]);
    setElements(prev);
    setHistory((h) => h.slice(0, -1));
  }, [history, elements]);

  const redo = useCallback(() => {
    if (future.length === 0) return;
    const next = future[0];
    setHistory((h) => [...h, clone(elements)]);
    setElements(next);
    setFuture((f) => f.slice(1));
  }, [future, elements]);

  const addElement = useCallback((type: string, patch?: Partial<CanvasElement>) => {
    const maxZ = Math.max(1, ...elements.map((e) => e.z || 1)) + 1;
    const el: CanvasElement = {
      id: makeId(type), type, x: 80, y: 120, w: type === "line" ? 200 : 160, h: type === "line" ? 2 : type === "image" ? 120 : 60,
      z: maxZ, text: type === "text" ? "Text" : undefined,
      style: { fontSize: type === "text" ? 16 : 14, fontWeight: "400", color: "#111", textAlign: "left", borderWidth: 0, borderColor: "#111", background: "transparent" },
      ...patch,
    };
    pushHistory(clone(elements));
    setElements((els) => [...els, el]);
    setSelectedId(el.id);
  }, [elements]);

  const updateElement = useCallback((eid: string, patch: Partial<CanvasElement>) => {
    pushHistory(clone(elements));
    setElements((els) => els.map((e) => e.id === eid ? { ...e, ...patch } : e));
  }, [elements]);

  const addSpecial = useCallback((variant: VariantItem) => {
    const el: CanvasElement = {
      id: makeId("special"), type: "special", x: 80, y: 120, w: 160, h: 80,
      z: Math.max(1, ...elements.map((e) => e.z || 1)) + 1,
      variantId: variant.id, variant_label: variant.label,
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
    pushHistory(clone(elements));
    setElements((els) => [...els, el]);
    setSelectedId(el.id);
  }, [elements]);

  const deleteSelected = useCallback(() => {
    if (!selected) return;
    pushHistory(clone(elements));
    setElements((els) => els.filter((e) => e.id !== selected.id));
    setSelectedId("");
  }, [selected, elements]);

  function pointerDown(event: React.PointerEvent, el: CanvasElement) {
    event.preventDefault();
    event.stopPropagation();
    setSelectedId(el.id);
    dragRef.current = { id: el.id, startX: event.clientX, startY: event.clientY, startEl: clone(el) };
    pendingElementsRef.current = clone(elements);
  }

  function onResizePointerDown(event: React.PointerEvent, handle: string) {
    event.preventDefault();
    event.stopPropagation();
    if (!selected) return;
    resizeRef.current = { id: selected.id, handle, startX: event.clientX, startY: event.clientY, startEl: clone(selected) };
    pendingElementsRef.current = clone(elements);
  }

  function pointerMove(event: React.PointerEvent) {
    const d = dragRef.current;
    const r = resizeRef.current;
    if (!d && !r) return;
    event.preventDefault();

    if (d) {
      const dx = (event.clientX - d.startX) / zoom;
      const dy = (event.clientY - d.startY) / zoom;
      let nx = d.startEl.x + dx;
      let ny = d.startEl.y + dy;
      const allEdges = elements.filter((e) => e.id !== d.id).flatMap((e) => [e.x, e.x + e.w, e.y, e.y + e.h]);
      const sx = snapValue(nx, SNAP, allEdges.filter((_, i) => i % 4 < 2));
      const sy = snapValue(ny, SNAP, allEdges.filter((_, i) => i % 4 >= 2));
      nx = sx.value;
      ny = sy.value;
      pendingElementsRef.current = pendingElementsRef.current.map((e) =>
        e.id === d.id ? { ...e, x: nx, y: ny } : e
      );
      const updated = pendingElementsRef.current.find((e) => e.id === d.id);
      if (updated) {
        const guides = computeGuides(d.startEl, { x: nx, y: ny }, elements, canvasW, canvasW / 2);
      }
    }

    if (r) {
      const dx = (event.clientX - r.startX) / zoom;
      const dy = (event.clientY - r.startY) / zoom;
      let { x, y, w, h } = r.startEl;
      const eh = r.handle;
      if (eh.includes("e")) w = Math.max(20, r.startEl.w + dx);
      if (eh.includes("w")) { const dw = r.startEl.w - dx; w = Math.max(20, dw); x = r.startEl.x + (r.startEl.w - w); }
      if (eh.includes("s")) h = Math.max(10, r.startEl.h + dy);
      if (eh.includes("n")) { const dh = r.startEl.h - dy; h = Math.max(10, dh); y = r.startEl.y + (r.startEl.h - h); }
      if (eh === "e" || eh === "w") { y = r.startEl.y; h = r.startEl.h; }
      if (eh === "n" || eh === "s") { x = r.startEl.x; w = r.startEl.w; }
      pendingElementsRef.current = pendingElementsRef.current.map((e) =>
        e.id === r.id ? { ...e, x, y, w, h } : e
      );
    }
  }

  function pointerUp() {
    if (dragRef.current) {
      const final = pendingElementsRef.current.find((e) => e.id === dragRef.current!.id);
      if (final) {
        const prev = clone(elements);
        setElements(pendingElementsRef.current);
        pushHistory(prev);
      }
    }
    if (resizeRef.current) {
      const final = pendingElementsRef.current.find((e) => e.id === resizeRef.current!.id);
      if (final) {
        const prev = clone(elements);
        setElements(pendingElementsRef.current);
        pushHistory(prev);
      }
    }
    dragRef.current = null;
    resizeRef.current = null;
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;
      if ((e.key === "Delete" || e.key === "Backspace") && selected) { e.preventDefault(); deleteSelected(); }
      if (e.key === "z" && (e.ctrlKey || e.metaKey) && !e.shiftKey) { e.preventDefault(); undo(); }
      if (e.key === "z" && (e.ctrlKey || e.metaKey) && e.shiftKey) { e.preventDefault(); redo(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected, elements, history, future, deleteSelected, undo, redo]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const sess = await api<{ session: { draft_id: string } }>(`/sessions/${id}`);
        const dId = sess.session.draft_id;
        setDraftId(dId);
        const [draftRes, assetsRes, specialsRes] = await Promise.all([
          api<{ draft: { fields: Record<string, DraftField>; selected_template_id?: string | null; available_templates: TemplateRecord[] } }>(`/drafts/${dId}`),
          api<{ assets: AssetRecord[] }>("/admin/template-assets"),
          api<{ our_specials: SpecialItem[] }>("/admin/our-specials"),
        ]);
        if (cancelled) return;
        const draft = draftRes.draft;
        setFields(draft.fields);
        setAssets(assetsRes.assets);
        setSpecials(specialsRes.our_specials);
        const tId = draft.selected_template_id;
        if (tId) {
          const tRes = await api<{ template: TemplateRecord }>(`/admin/templates/${tId}`);
          if (cancelled) return;
          setTemplate(tRes.template);
          setConfig(tRes.template.fixed_fields);
          setElements(clone(tRes.template.fixed_fields.canvas.elements || []));
          setSelectedId(tRes.template.fixed_fields.canvas.elements[0]?.id || "");
          setHistory([clone(tRes.template.fixed_fields.canvas.elements || [])]);
        }
      } catch (err) {
        toast(apiErrorMessage(err), "error");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [id]);

  const downloadPdf = useCallback(async () => {
    setBusyPdf(true);
    try {
      const res = await api<{ version: { download_url: string } }>(`/drafts/${draftId}/generate`, { method: "POST", body: JSON.stringify({}) });
      window.location.href = fileUrl(res.version.download_url);
    } catch (err) { toast(apiErrorMessage(err), "error"); setBusyPdf(false); }
  }, [draftId, toast]);

  const downloadPng = useCallback(async () => {
    setBusyPng(true);
    try {
      const res = await apiRaw(`/drafts/${draftId}/preview-png`, { method: "POST" });
      if (!res.ok) throw new Error("PNG generation failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "preview.png"; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { toast(apiErrorMessage(err), "error"); }
    finally { setBusyPng(false); }
  }, [draftId, toast]);

  const saveAsTemplate = useCallback(async () => {
    if (!templateName.trim()) return;
    if (!config) { toast("Template config not loaded.", "error"); return; }
    try {
      const result = await api<{ template: { id: string } }>("/admin/templates", {
        method: "POST",
        body: JSON.stringify({ name: templateName, fixed_fields: { ...config, canvas: { width: canvasW, height: canvasH, elements } }, insurance_type: "Motor" }),
      });
      toast("Template saved.", "success");
      router.push(`/builder/templates/${result.template.id}/builder`);
    } catch (err) { toast(apiErrorMessage(err), "error"); }
  }, [templateName, config, canvasW, canvasH, elements, toast, router]);

  const updateStyle = useCallback((eid: string, key: keyof CanvasStyle, value: string | number) => {
    setElements((els) => els.map((e) => e.id === eid ? { ...e, style: { ...e.style, [key]: value } } : e));
  }, []);

  const filteredSpecials = specials.flatMap((sp) =>
    sp.variants.map((v) => ({ ...v, _parent: sp.label, _category: sp.category }))
  );

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-[var(--rl-bg)]">
        <div className="z-20 flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] bg-[var(--rl-surface)] px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="ghost" icon={<ArrowLeft size={16} weight="bold" />} onClick={() => router.push(`/sessions/${id}/review`)}>
              Review
            </Button>
            <h1 className="text-[20px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Preview &amp; Edit</h1>
            {template && <Badge variant="info">{template.name}</Badge>}
          </div>
          <SessionPhaseBar sessionId={id} current="preview" hasVersion={false} />
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 text-[13px] font-semibold text-[var(--rl-text-strong)]">
              Zoom
              <input className="w-24" type="range" min="0.45" max="1.1" step="0.05" value={zoom} onChange={(e) => setZoom(Number(e.target.value))} />
            </label>
            <Button variant="secondary" size="sm" icon={<ArrowArcLeft size={14} weight="bold" />} onClick={undo} disabled={history.length === 0}>Undo</Button>
            <Button variant="secondary" size="sm" icon={<ArrowArcRight size={14} weight="bold" />} onClick={redo} disabled={future.length === 0}>Redo</Button>
            <Button variant="danger" size="sm" icon={<Trash size={14} weight="bold" />} onClick={deleteSelected} disabled={!selected}>Delete</Button>
            <Button variant="secondary" size="sm" loading={busyPdf} icon={<DownloadSimple size={14} weight="bold" />} onClick={downloadPdf}>{busyPdf ? "Generating PDF" : "PDF"}</Button>
            <Button variant="secondary" size="sm" loading={busyPng} icon={<FileImage size={14} weight="bold" />} onClick={downloadPng}>{busyPng ? "Rendering PNG" : "PNG"}</Button>
            <Button size="sm" icon={<FloppyDisk size={14} weight="bold" />} onClick={() => setShowSaveModal(true)}>Save as template</Button>
          </div>
        </div>

        {/* ---------- LOADING ---------- */}
        {loading && (
          <div className="flex flex-1 items-center justify-center gap-3 text-[var(--rl-text-muted)]">
            <Spinner /> Loading preview...
          </div>
        )}

        {/* ---------- EDITOR BODY ---------- */}
        {!loading && (
          <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr] overflow-hidden">
            {/* SIDEBAR */}
            <aside className="flex flex-col overflow-hidden border-r border-[var(--rl-border)] bg-[var(--rl-surface)]">
              <div className="flex-1 overflow-auto p-4 space-y-5">
                {/* --- Element toolbar --- */}
                <div>
                  <h2 className="mb-2 font-bold text-[13px] text-[var(--rl-text-strong)]">Add Elements</h2>
                  <div className="flex flex-wrap gap-1.5">
                    <Button variant="secondary" size="sm" icon={<TextT size={13} weight="bold" />} onClick={() => addElement("text")}>Text</Button>
                    <Button variant="secondary" size="sm" icon={<BracketsCurly size={13} weight="bold" />} onClick={() => addElement("variable")}>Variable</Button>
                    <Button variant="secondary" size="sm" icon={<Image size={13} weight="bold" />} onClick={() => addElement("image")}>Image</Button>
                    <Button variant="secondary" size="sm" icon={<LineSegment size={13} weight="bold" />} onClick={() => addElement("line")}>Line</Button>
                    <Button variant="secondary" size="sm" icon={<Square size={13} weight="bold" />} onClick={() => addElement("box")}>Box</Button>
                  </div>
                </div>

                {/* --- Asset picker (image elements) --- */}
                {selected?.type === "image" && (
                  <div>
                    <h2 className="mb-1.5 font-bold text-[13px] text-[var(--rl-text-strong)]">Image Asset</h2>
                    {assets.length === 0 ? (
                      <p className="text-[12px] text-[var(--rl-text-muted)]">Loading assets...</p>
                    ) : (
                      <Select
                        value={selected.assetId || ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (val) updateElement(selected.id, { assetId: val });
                        }}
                      >
                        <option value="">None</option>
                        {assets.map((a) => (
                          <option key={a.id} value={a.id}>{a.label || a.filename}</option>
                        ))}
                      </Select>
                    )}
                  </div>
                )}

                {/* --- Property panel --- */}
                {selected && (
                  <div>
                    <h2 className="mb-2 font-bold text-[13px] text-[var(--rl-text-strong)]">Properties</h2>
                    <div className="grid gap-2">
                      <div className="grid grid-cols-[28px_1fr] items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--rl-text-muted)]">X</span>
                        <Input type="number" className="min-h-[32px] text-[12px]" value={Math.round(selected.x)} onChange={(e) => updateElement(selected.id, { x: Number(e.target.value) || 0 })} />
                      </div>
                      <div className="grid grid-cols-[28px_1fr] items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--rl-text-muted)]">Y</span>
                        <Input type="number" className="min-h-[32px] text-[12px]" value={Math.round(selected.y)} onChange={(e) => updateElement(selected.id, { y: Number(e.target.value) || 0 })} />
                      </div>
                      <div className="grid grid-cols-[28px_1fr] items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--rl-text-muted)]">W</span>
                        <Input type="number" className="min-h-[32px] text-[12px]" value={Math.round(selected.w)} onChange={(e) => updateElement(selected.id, { w: Number(e.target.value) || 1 })} />
                      </div>
                      <div className="grid grid-cols-[28px_1fr] items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--rl-text-muted)]">H</span>
                        <Input type="number" className="min-h-[32px] text-[12px]" value={Math.round(selected.h)} onChange={(e) => updateElement(selected.id, { h: Number(e.target.value) || 1 })} />
                      </div>
                      <div className="grid grid-cols-[60px_1fr] items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--rl-text-muted)]">Font Size</span>
                        <Input type="number" className="min-h-[32px] text-[12px]" value={selected.style?.fontSize || 14} onChange={(e) => updateStyle(selected.id, "fontSize", Number(e.target.value) || 1)} />
                      </div>
                      <div className="grid grid-cols-[60px_1fr] items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--rl-text-muted)]">Color</span>
                        <Input type="color" className="min-h-[32px] p-0.5 text-[12px]" value={selected.style?.color || "#111111"} onChange={(e) => updateStyle(selected.id, "color", e.target.value)} />
                      </div>
                      <div className="grid grid-cols-[60px_1fr] items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--rl-text-muted)]">Background</span>
                        <Input type="color" className="min-h-[32px] p-0.5 text-[12px]" value={selected.style?.background || "#ffffff"} onChange={(e) => updateStyle(selected.id, "background", e.target.value)} />
                      </div>
                      <div className="grid grid-cols-[60px_1fr] items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--rl-text-muted)]">Border W</span>
                        <Input type="number" className="min-h-[32px] text-[12px]" value={selected.style?.borderWidth || 0} onChange={(e) => updateStyle(selected.id, "borderWidth", Number(e.target.value) || 0)} />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* --- Our Specials sidebar --- */}
              <div className="border-t border-[var(--rl-border)] p-4 max-h-[280px] overflow-auto">
                <h2 className="mb-1 font-bold text-[13px] text-[var(--rl-text-strong)]">Our Specials</h2>
                <p className="text-[11px] text-[var(--rl-text-muted)]">Click to add to canvas</p>
                <div className="mt-2 grid gap-1.5">
                  {specials.map((sp) => (
                    <div key={sp.id}>
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--rl-text-muted)]">{sp.label} ({sp.category})</div>
                      <div className="grid gap-1 mt-0.5">
                        {sp.variants.map((v) => (
                          <button
                            key={v.id}
                            type="button"
                            className="grid cursor-pointer grid-cols-[36px_1fr] items-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-1.5 text-left text-[12px] hover:bg-[var(--rl-bg)] transition-colors"
                            onClick={() => addSpecial(v)}
                          >
                            {v.icon_asset_id ? (
                              <img className="h-8 w-8 object-contain" src={fileUrl(`/template-assets/${v.icon_asset_id}`)} alt="" />
                            ) : (
                              <div
                                className="flex h-8 w-8 items-center justify-center rounded-[var(--rl-radius-sm)] text-[9px] font-bold text-[var(--rl-text-strong)]"
                                style={{
                                  borderRadius: shapeRadii[v.shape || "rounded"] || "12px",
                                  backgroundColor: v.bg_color || "#F6F8FB",
                                  color: v.text_color || "#1B1717",
                                  boxShadow: shadowMap[v.shadow || "none"] || "none",
                                  border: v.border_width && v.border_width !== "none" ? `${v.border_width} solid ${v.border_color || "#D8DDE6"}` : undefined,
                                }}
                              >
                                IC
                              </div>
                            )}
                            <div className="leading-tight">
                              <span className="font-bold text-[var(--rl-text-strong)]">{v.label}</span>
                              {v.value_text && <span className="block text-[10px] text-[var(--rl-text-muted)]">{v.value_text}</span>}
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </aside>

            {/* ---------- CANVAS AREA ---------- */}
            <section className="overflow-auto p-6" onClick={() => setSelectedId("")}>
              <div className="mx-auto w-fit rounded-[var(--rl-radius)] bg-neutral-300 p-6 shadow-inner" style={{ minHeight: (canvasH * zoom) + 60 }}>
                <div
                  className="relative origin-top-left overflow-hidden bg-white shadow-xl"
                  style={{ width: canvasW, height: canvasH, transform: `scale(${zoom})` }}
                  onPointerMove={pointerMove}
                  onPointerUp={pointerUp}
                  onPointerLeave={pointerUp}
                >
                  {elements.map((el) => (
                    <CanvasElementView
                      key={el.id}
                      element={el}
                      selected={el.id === selectedId}
                      assets={assets}
                      config={config || undefined}
                      readOnly={false}
                      onPointerDown={(e) => pointerDown(e, el)}
                      onResizePointerDown={onResizePointerDown}
                    />
                  ))}
                </div>
              </div>
            </section>
          </div>
        )}

        {/* ---------- SAVE MODAL ---------- */}
        {showSaveModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowSaveModal(false)}>
            <div className="w-full max-w-md rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-6 shadow-card" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Save as new template</h2>
                <button type="button" className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)]" onClick={() => setShowSaveModal(false)}><X size={16} weight="bold" /></button>
              </div>
              <p className="mt-2 text-[14px] text-[var(--rl-text-muted)]">This creates a new template with the current canvas layout.</p>
              <Input className="mt-3" placeholder="Template name" value={templateName} onChange={(e) => setTemplateName(e.target.value)} autoFocus />
              <div className="mt-4 flex gap-2">
                <Button size="sm" icon={<FloppyDisk size={14} weight="bold" />} onClick={saveAsTemplate}>Save</Button>
                <Button variant="secondary" size="sm" onClick={() => setShowSaveModal(false)}>Cancel</Button>
              </div>
            </div>
          </div>
        )}
      </div>
  );
}
