"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowArcLeft,
  ArrowArcRight,
  ArrowLeft,
  DownloadSimple,
  FloppyDisk,
  LockKey,
  MagicWand,
  WarningCircle,
} from "@phosphor-icons/react";
import { SessionPhaseBar } from "@/components/session-phase-bar";
import {
  CanvasElementView,
  SNAP,
  snapValue,
  type CanvasElement,
  type CanvasStyle,
} from "@/components/template-canvas/shared";
import {
  useWorkspaceActions,
  useWorkspaceData,
  useWorkspaceMutation,
} from "@/components/session-workspace/provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type TemplateConfig = {
  version?: number;
  variables?: Array<{ id: string; label: string; field?: string; source?: string }>;
  cards?: Record<string, { title?: string }>;
  assets?: Record<string, string>;
  canvas: { width: number; height: number; elements: CanvasElement[] };
  [key: string]: unknown;
};

type TemplatePayload = {
  template_id: string;
  template_revision_id: string;
  revision_number: number;
  config_hash: string;
  source: "session_override" | "template_revision";
  config: TemplateConfig;
  binding: { template_id: string; template_revision_id: string; base_hash: string };
};

type AssetRecord = { id: string; label: string; url: string };
type Gesture = {
  kind: "drag" | "resize";
  id: string;
  handle?: string;
  pointerId: number;
  startClientX: number;
  startClientY: number;
  startElement: CanvasElement;
  before: CanvasElement[];
};
type GenerationJob = {
  id: string;
  state: string;
  phase?: string;
  progress?: number;
  elapsed_seconds?: number;
  attempt?: number;
  error?: { message?: string } | null;
};

const MAX_HISTORY = 40;

function cloneElements(elements: CanvasElement[]): CanvasElement[] {
  return elements.map((element) => ({ ...element, style: element.style ? { ...element.style } : undefined }));
}

function sameElements(left: CanvasElement[], right: CanvasElement[]): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

function fieldValues(fields: Record<string, { value?: string | null }>): Record<string, string> {
  return Object.fromEntries(Object.entries(fields).map(([name, field]) => [name, String(field.value ?? "")]));
}

export function PreviewPhase({ id, onBack }: { id: string; onBack: () => void }) {
  const { workspace, loading: workspaceLoading, loadError } = useWorkspaceData();
  const { queueOperation, reload, save } = useWorkspaceActions();
  const mutation = useWorkspaceMutation();

  const [template, setTemplate] = useState<TemplatePayload | null>(null);
  const [elements, setElements] = useState<CanvasElement[]>([]);
  const [templateLoading, setTemplateLoading] = useState(true);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(0.72);
  const [history, setHistory] = useState<CanvasElement[][]>([]);
  const [future, setFuture] = useState<CanvasElement[][]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [authoritativePreviewUrl, setAuthoritativePreviewUrl] = useState<string | null>(null);
  const [generationJob, setGenerationJob] = useState<GenerationJob | null>(null);
  const gestureRef = useRef<Gesture | null>(null);
  const elementsRef = useRef<CanvasElement[]>([]);
  const generationRequestRef = useRef<{ revision: number; key: string } | null>(null);
  const generationCancelledRef = useRef(false);

  const canvasWidth = Number(template?.config.canvas?.width || 794);
  const canvasHeight = Number(template?.config.canvas?.height || 1123);
  const selected = elements.find((element) => element.id === selectedId) || null;
  const canEditLayout = Boolean(workspace?.capabilities.can_edit_layout);
  const latestVersion = workspace?.versions.at(-1) || null;

  useEffect(() => {
    elementsRef.current = elements;
  }, [elements]);

  const assets = useMemo<AssetRecord[]>(() => {
    if (!template) return [];
    const ids = new Set<string>();
    for (const assetId of Object.values(template.config.assets || {})) if (assetId) ids.add(assetId);
    for (const element of elements) if (element.assetId) ids.add(element.assetId);
    return [...ids].map((assetId) => ({ id: assetId, label: assetId, url: `/template-assets/${assetId}` }));
  }, [elements, template]);

  const loadTemplate = useCallback(async () => {
    setTemplateLoading(true);
    setTemplateError(null);
    try {
      const response = await api<{ template: TemplatePayload }>(`/sessions/${id}/template-config`);
      const nextElements = cloneElements(response.template.config.canvas?.elements || []);
      setTemplate(response.template);
      elementsRef.current = nextElements;
      setElements(nextElements);
      setSelectedId(null);
      setHistory([]);
      setFuture([]);
    } catch (error) {
      setTemplateError(apiErrorMessage(error));
    } finally {
      setTemplateLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!workspaceLoading && workspace) loadTemplate().catch(() => undefined);
  }, [loadTemplate, workspace?.template?.revision_id, workspaceLoading]);

  const queueLayout = useCallback((nextElements: CanvasElement[]) => {
    if (!template) return;
    const layout: TemplateConfig = {
      ...template.config,
      canvas: { ...template.config.canvas, elements: cloneElements(nextElements) },
    };
    queueOperation(
      {
        op: "layout_override",
        layout,
        template_id: template.binding.template_id,
        template_revision_id: template.binding.template_revision_id,
        base_hash: template.binding.base_hash,
      },
      "layout_override",
    );
  }, [queueOperation, template]);

  const commitElements = useCallback((before: CanvasElement[], next: CanvasElement[]) => {
    if (sameElements(before, next)) return;
    setHistory((current) => [...current.slice(-(MAX_HISTORY - 1)), cloneElements(before)]);
    setFuture([]);
    elementsRef.current = next;
    setElements(next);
    queueLayout(next);
  }, [queueLayout]);

  const undo = useCallback(() => {
    const previous = history.at(-1);
    if (!previous) return;
    const current = cloneElements(elements);
    const next = cloneElements(previous);
    setHistory((items) => items.slice(0, -1));
    setFuture((items) => [current, ...items].slice(0, MAX_HISTORY));
    elementsRef.current = next;
    setElements(next);
    queueLayout(next);
  }, [elements, history, queueLayout]);

  const redo = useCallback(() => {
    const nextState = future[0];
    if (!nextState) return;
    const current = cloneElements(elements);
    const next = cloneElements(nextState);
    setHistory((items) => [...items.slice(-(MAX_HISTORY - 1)), current]);
    setFuture((items) => items.slice(1));
    elementsRef.current = next;
    setElements(next);
    queueLayout(next);
  }, [elements, future, queueLayout]);

  function beginGesture(event: React.PointerEvent, element: CanvasElement, kind: "drag" | "resize", handle?: string) {
    if (!canEditLayout || element.locked) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    setSelectedId(element.id);
    gestureRef.current = {
      kind,
      id: element.id,
      handle,
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startElement: { ...element, style: element.style ? { ...element.style } : undefined },
      before: cloneElements(elements),
    };
  }

  function moveGesture(event: React.PointerEvent) {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    event.preventDefault();
    const dx = (event.clientX - gesture.startClientX) / zoom;
    const dy = (event.clientY - gesture.startClientY) / zoom;
    const start = gesture.startElement;
    let x = start.x;
    let y = start.y;
    let w = start.w;
    let h = start.h;

    if (gesture.kind === "drag") {
      x = snapValue(clamp(start.x + dx, 0, canvasWidth - start.w), SNAP, []).value;
      y = snapValue(clamp(start.y + dy, 0, canvasHeight - start.h), SNAP, []).value;
      x = clamp(x, 0, canvasWidth - start.w);
      y = clamp(y, 0, canvasHeight - start.h);
    } else {
      const handle = gesture.handle || "se";
      if (handle.includes("e")) w = clamp(start.w + dx, 24, canvasWidth - start.x);
      if (handle.includes("s")) h = clamp(start.h + dy, 24, canvasHeight - start.y);
      if (handle.includes("w")) {
        x = clamp(start.x + dx, 0, start.x + start.w - 24);
        w = start.w + (start.x - x);
      }
      if (handle.includes("n")) {
        y = clamp(start.y + dy, 0, start.y + start.h - 24);
        h = start.h + (start.y - y);
      }
    }

    const next = gesture.before.map((item) => item.id === gesture.id ? { ...item, x, y, w, h } : item);
    elementsRef.current = next;
    setElements(next);
  }

  function finishGesture(event?: React.PointerEvent) {
    const gesture = gestureRef.current;
    if (!gesture) return;
    if (event && gesture.pointerId !== event.pointerId) return;
    gestureRef.current = null;
    commitElements(gesture.before, elementsRef.current);
  }

  function updateSelected(patch: Partial<CanvasElement>, stylePatch?: Partial<CanvasStyle>) {
    if (!selected || selected.locked || !canEditLayout) return;
    const before = cloneElements(elements);
    const next = elements.map((element) => element.id === selected.id
      ? { ...element, ...patch, style: stylePatch ? { ...(element.style || {}), ...stylePatch } : element.style }
      : element);
    commitElements(before, next);
  }

  async function saveLayout() {
    setActionError(null);
    try {
      await save();
    } catch (error) {
      setActionError(apiErrorMessage(error));
    }
  }

  async function generatePdf() {
    if (!workspace) return;
    setGenerating(true);
    setActionError(null);
    try {
      const saved = await save();
      if (saved.generation_blockers.length) {
        throw new Error("Resolve every generation blocker before creating the PDF.");
      }
      generationCancelledRef.current = false;
      if (generationRequestRef.current?.revision !== saved.revision) {
        generationRequestRef.current = { revision: saved.revision, key: crypto.randomUUID() };
      }
      const idempotencyKey = generationRequestRef.current.key;
      const requested = await api<{ job?: { id: string }; version?: { id: string } }>(`/sessions/${id}/versions`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ draft_revision: saved.revision }),
      });
      const jobId = requested.job?.id;
      if (jobId) {
        setGenerationJob({ id: jobId, state: "queued", phase: "queued", progress: 0 });
        let completed = false;
        for (let attempt = 0; attempt < 90; attempt += 1) {
          if (generationCancelledRef.current) throw new Error("PDF generation was cancelled.");
          const status = await api<{ job: GenerationJob }>(`/jobs/${jobId}`);
          setGenerationJob(status.job);
          if (status.job.state === "completed") {
            completed = true;
            break;
          }
          if (status.job.state === "failed" || status.job.state === "cancelled") {
            throw new Error(status.job.error?.message || "PDF generation did not complete.");
          }
          await new Promise((resolve) => window.setTimeout(resolve, 1_000));
        }
        if (!completed) throw new Error("PDF generation is still processing. Check this quotation again shortly.");
      }
      await reload();
      generationRequestRef.current = null;
    } catch (error) {
      setActionError(apiErrorMessage(error));
    } finally {
      setGenerating(false);
    }
  }

  async function cancelGeneration() {
    const jobId = generationJob?.id;
    if (!jobId) return;
    generationCancelledRef.current = true;
    try {
      await api(`/jobs/${jobId}/cancel`, { method: "POST" });
    } catch {
      // A completed job wins the race; the next reload will show its version.
    }
    setGenerationJob((current) => current ? { ...current, state: "cancelled", phase: "cancelled" } : current);
  }

  async function renderAuthoritativePreview() {
    setPreviewLoading(true);
    setActionError(null);
    try {
      const saved = await save();
      const result = await api<{ preview_url: string }>(`/sessions/${id}/preview-render`, {
        method: "POST",
        body: JSON.stringify({ draft_revision: saved.revision }),
      });
      setAuthoritativePreviewUrl(fileUrl(result.preview_url));
    } catch (error) {
      setActionError(apiErrorMessage(error));
    } finally {
      setPreviewLoading(false);
    }
  }

  if (workspaceLoading) return <PageLoading />;
  if (loadError || !workspace) {
    return (
      <Card className="grid gap-3 p-6" role="alert">
        <h1 className="text-xl font-bold">Could not load quotation</h1>
        <p className="text-sm text-[var(--rl-text)]">{loadError || "The quotation workspace is unavailable."}</p>
        <Button className="w-fit" onClick={() => reload().catch(() => undefined)}>Retry</Button>
      </Card>
    );
  }

  if (templateLoading) return <PageLoading />;
  if (templateError || !template) {
    return (
      <section className="grid gap-4">
        <SessionPhaseBar sessionId={id} current="preview" hasVersion={Boolean(latestVersion)} onStep={(key) => { if (key === "extraction") onBack(); }} />
        <Card className="grid gap-3 p-6" role="alert">
          <h1 className="text-xl font-bold">Preview is not ready</h1>
          <p className="text-sm text-[var(--rl-text)]">{templateError || "Choose a published template before opening Preview."}</p>
          <div className="flex gap-2">
            <Button onClick={onBack}>Return to Check Values</Button>
            <Button variant="secondary" onClick={() => loadTemplate().catch(() => undefined)}>Retry</Button>
          </div>
        </Card>
      </section>
    );
  }

  const generationBlocked = workspace.generation_blockers.length > 0;

  return (
    <section className="grid gap-4">
      <SessionPhaseBar sessionId={id} current="preview" hasVersion={Boolean(latestVersion)} onStep={(key) => { if (key === "extraction") onBack(); }} />

      <Card className="sticky top-[68px] z-20 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[22px] font-bold text-[var(--rl-text-strong)]">Preview and generate</h1>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant="info">Draft revision {workspace.revision}</Badge>
              <Badge variant="info">Template revision {template.revision_number}</Badge>
              {mutation.dirty ? <Badge variant="warning">Unsaved layout</Badge> : <Badge variant="success">Saved</Badge>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={<ArrowLeft weight="bold" />} onClick={onBack}>
              Check Values
            </Button>
            <Button variant="secondary" loading={previewLoading} disabled={generationBlocked} onClick={renderAuthoritativePreview}>
              Render final preview
            </Button>
            <Button variant="secondary" icon={<FloppyDisk weight="bold" />} loading={mutation.saving} disabled={!mutation.dirty} onClick={saveLayout}>
              Save layout
            </Button>
            {latestVersion ? (
              <a
                href={fileUrl(`/versions/${latestVersion.id}/pdf`)}
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-4 text-sm font-semibold text-[var(--rl-text-strong)]"
              >
                <DownloadSimple weight="bold" /> Download latest PDF
              </a>
            ) : null}
            <Button
              icon={<MagicWand weight="bold" />}
              loading={generating}
              disabled={generationBlocked || !workspace.capabilities.can_generate}
              onClick={generatePdf}
            >
              Generate PDF
            </Button>
          </div>
        </div>
      </Card>

      {actionError || mutation.saveError ? (
        <div role="alert" className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] p-3 text-sm font-semibold text-[var(--rl-red)]">
          {actionError || mutation.saveError}
        </div>
      ) : null}

      {generationBlocked ? (
        <Card className="p-4" role="status">
          <h2 className="flex items-center gap-2 font-bold text-[var(--rl-text-strong)]">
            <WarningCircle className="text-amber-600" weight="fill" /> Generation needs attention
          </h2>
          <ul className="mt-2 grid gap-1 text-sm text-[var(--rl-text)]">
            {workspace.generation_blockers.map((blocker, index) => <li key={`${blocker.path}-${index}`}>{blocker.message}</li>)}
          </ul>
          <Button className="mt-3" size="sm" onClick={onBack}>Fix in Check Values</Button>
        </Card>
      ) : null}

      {generationJob && ["queued", "processing"].includes(generationJob.state) ? (
        <Card className="grid gap-3 p-4" role="status" aria-live="polite">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="font-bold text-[var(--rl-text-strong)]">Generating PDF</h2><p className="mt-1 text-sm text-[var(--rl-text-muted)]">{String(generationJob.phase || generationJob.state).replaceAll("_", " ")} · {Math.round(generationJob.progress || 0)}% · {Math.round(generationJob.elapsed_seconds || 0)}s elapsed</p></div>
            <Button variant="secondary" size="sm" onClick={cancelGeneration}>Cancel generation</Button>
          </div>
          <progress className="h-2 w-full accent-[var(--rl-red)]" max={100} value={generationJob.progress || 0} aria-label="PDF generation progress" />
        </Card>
      ) : null}

      {authoritativePreviewUrl ? (
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="font-bold text-[var(--rl-text-strong)]">Final rendered preview</h2>
            <a className="text-sm font-semibold text-[var(--rl-red)] underline" href={authoritativePreviewUrl} target="_blank" rel="noreferrer">Open preview in a new tab</a>
          </div>
          <iframe title="Final rendered preview" src={authoritativePreviewUrl} className="min-h-[720px] w-full border border-[var(--rl-border)] bg-white" />
        </Card>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <Card className="min-w-0 overflow-auto p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" icon={<ArrowArcLeft />} disabled={!history.length} onClick={undo}>Undo</Button>
              <Button variant="secondary" size="sm" icon={<ArrowArcRight />} disabled={!future.length} onClick={redo}>Redo</Button>
            </div>
            <label className="flex items-center gap-2 text-sm font-semibold">
              Zoom
              <input
                aria-label="Canvas zoom"
                type="range"
                min="0.35"
                max="1"
                step="0.05"
                value={zoom}
                onChange={(event) => setZoom(Number(event.target.value))}
              />
              {Math.round(zoom * 100)}%
            </label>
          </div>

          <div className="mb-3 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50 p-3 text-sm lg:hidden">
            Canvas editing requires a viewport at least 1024px wide. You can still review readiness and generate a saved layout here.
          </div>

          <div className="hidden min-w-max place-items-center overflow-auto bg-[#ececec] p-8 lg:grid">
            <div
              className="relative"
              style={{ width: canvasWidth * zoom, height: canvasHeight * zoom }}
            >
              <div
                className="absolute left-0 top-0 origin-top-left overflow-hidden bg-white shadow-lift"
                style={{ width: canvasWidth, height: canvasHeight, transform: `scale(${zoom})` }}
                onPointerMove={moveGesture}
                onPointerUp={finishGesture}
                onPointerCancel={finishGesture}
                onLostPointerCapture={finishGesture}
                onClick={() => setSelectedId(null)}
              >
                {elements.map((element) => (
                  <CanvasElementView
                    key={element.id}
                    element={element}
                    selected={element.id === selectedId}
                    assets={assets}
                    config={template.config}
                    variableValues={fieldValues(workspace.fields)}
                    readOnly={!canEditLayout || Boolean(element.locked)}
                    onPointerDown={(event) => beginGesture(event, element, "drag")}
                    onResizePointerDown={(event, handle) => beginGesture(event, element, "resize", handle)}
                  />
                ))}
              </div>
            </div>
          </div>
        </Card>

        <aside className="grid content-start gap-4">
          <Card className="p-4">
            <h2 className="font-bold text-[var(--rl-text-strong)]">Quotation layout override</h2>
            <p className="mt-2 text-sm text-[var(--rl-text)]">
              Changes here affect only this quotation. Master templates are edited in Template Builder.
            </p>
            {!canEditLayout ? (
              <p className="mt-3 flex items-center gap-2 text-sm font-semibold text-[var(--rl-text-muted)]"><LockKey /> Layout editing is not permitted.</p>
            ) : null}
          </Card>

          <Card className="p-4">
            <h2 className="font-bold text-[var(--rl-text-strong)]">Layers</h2>
            <div className="mt-3 grid max-h-72 gap-1 overflow-auto">
              {[...elements].sort((left, right) => (right.z || 0) - (left.z || 0)).map((element) => (
                <button
                  key={element.id}
                  type="button"
                  className={`flex min-h-9 items-center justify-between rounded-[var(--rl-radius-sm)] border px-2 text-left text-xs ${selectedId === element.id ? "border-[var(--rl-red)] bg-[var(--rl-red-light)]" : "border-[var(--rl-border)]"}`}
                  onClick={() => setSelectedId(element.id)}
                >
                  <span className="truncate">{element.text || element.variableId || element.id}</span>
                  {element.locked ? <LockKey aria-label="Locked layer" /> : null}
                </button>
              ))}
            </div>
          </Card>

          <Card className="p-4">
            <h2 className="font-bold text-[var(--rl-text-strong)]">Selected element</h2>
            {!selected ? <p className="mt-2 text-sm text-[var(--rl-text-muted)]">Select an existing layer to adjust it.</p> : (
              <fieldset disabled={selected.locked || !canEditLayout} className="mt-3 grid grid-cols-2 gap-3 disabled:opacity-60">
                {(["x", "y", "w", "h"] as const).map((property) => (
                  <label key={property} className="grid gap-1 text-xs font-semibold uppercase">
                    {property}
                    <Input
                      type="number"
                      min={property === "w" || property === "h" ? 24 : 0}
                      value={Math.round(selected[property])}
                      onChange={(event) => updateSelected({ [property]: Number(event.target.value) })}
                    />
                  </label>
                ))}
                <label className="col-span-2 grid gap-1 text-xs font-semibold">
                  Font size
                  <Input type="number" min="6" max="200" value={selected.style?.fontSize || 14} onChange={(event) => updateSelected({}, { fontSize: Number(event.target.value) })} />
                </label>
                <label className="grid gap-1 text-xs font-semibold">
                  Text color
                  <Input type="color" value={selected.style?.color || "#111111"} onChange={(event) => updateSelected({}, { color: event.target.value })} />
                </label>
                <label className="grid gap-1 text-xs font-semibold">
                  Background
                  <Input type="color" value={selected.style?.background && selected.style.background !== "transparent" ? selected.style.background : "#ffffff"} onChange={(event) => updateSelected({}, { background: event.target.value })} />
                </label>
              </fieldset>
            )}
          </Card>
        </aside>
      </div>
    </section>
  );
}
