"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  CheckCircle,
  DownloadSimple,
  Image as ImageIcon,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
  Printer,
  Sparkle,
  WarningCircle,
} from "@phosphor-icons/react";
import { Panel, Group, Separator } from "react-resizable-panels";
import { toPng } from "html-to-image";
import { SessionPhaseBar } from "@/components/session-phase-bar";
import {
  type CanvasElement,
} from "@/components/template-canvas/shared";
import { Design2CanvasView } from "@/components/template-canvas/design2-canvas";
import { buildUnifiedMatrixCards } from "@/lib/unified-addon-engine";
import {
  useWorkspaceActions,
  useWorkspaceData,
} from "@/components/session-workspace/provider";
import type { PanelImperativeHandle } from "react-resizable-panels";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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

type GenerationJob = {
  id: string;
  state: string;
  phase?: string;
  progress?: number;
  elapsed_seconds?: number;
  attempt?: number;
  error?: { message?: string } | null;
  result?: { version_id?: string; version_number?: number } | null;
};

function fieldValues(fields: Record<string, { value?: string | null }>): Record<string, string> {
  return Object.fromEntries(Object.entries(fields || {}).map(([name, field]) => [name, String(field?.value ?? "")]));
}

function formatMoney(amount: string | number | null | undefined): string {
  if (!amount) return "RM 0.00";
  const str = String(amount).replace(/[^0-9.]/g, "");
  const num = parseFloat(str);
  if (isNaN(num)) return "RM 0.00";
  return `RM ${num.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function PreviewPhase({ id, onBack }: { id: string; onBack: () => void }) {
  const { workspace, loading: workspaceLoading, loadError } = useWorkspaceData();
  const { reload, save } = useWorkspaceActions();

  const [template, setTemplate] = useState<TemplatePayload | null>(null);
  const [templateLoading, setTemplateLoading] = useState(true);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(0.75);
  const [actionError, setActionError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generationJob, setGenerationJob] = useState<GenerationJob | null>(null);
  const generationRequestRef = useRef<{ revision: number; key: string } | null>(null);
  const generationCancelledRef = useRef(false);
  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const leftPanelRef = useRef<PanelImperativeHandle>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const canvasWidth = Number(template?.config?.canvas?.width || 794);
  const baseCanvasHeight = Number(template?.config?.canvas?.height || 1123);
  const latestVersion = workspace?.versions?.at(-1) || null;

  const loadTemplate = useCallback(async () => {
    setTemplateLoading(true);
    setTemplateError(null);
    try {
      const response = await api<{ template: TemplatePayload }>(`/sessions/${id}/template-config`);
      setTemplate(response.template);
    } catch (error) {
      setTemplateError(apiErrorMessage(error));
    } finally {
      setTemplateLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!workspaceLoading && workspace) {
      loadTemplate().catch(() => undefined);
    }
  }, [loadTemplate, workspace?.template?.revision_id, workspaceLoading]);

  // Direct trigger download helper
  const triggerBrowserDownload = useCallback((url: string, filename?: string) => {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || `quotation_${id}.pdf`;
    link.target = "_blank";
    link.rel = "noreferrer";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [id]);

  // Main Generate & Download Function
  async function handleDownloadPdf() {
    if (!workspace) return;
    setGenerating(true);
    setActionError(null);

    try {
      const conflict = await api<{ has_conflict: boolean; resolved: boolean }>(`/sessions/${id}/ownership-conflict`).catch(() => null);
      if (conflict?.has_conflict && !conflict?.resolved) {
        throw new Error("Action Required: Vehicle ownership conflict detected. Please resolve it on the Review step before generating the PDF.");
      }

      const saved = await save();
      const nonFatalBlockers = saved.generation_blockers.filter(
        (b) => b.code !== "scalar_check_needed" && b.code !== "missing_catalog"
      );
      if (nonFatalBlockers.length > 0) {
        throw new Error(nonFatalBlockers[0].message || "Resolve generation blockers before creating the PDF.");
      }

      generationCancelledRef.current = false;
      const idempotencyKey = crypto.randomUUID();

      const requested = await api<{ job?: { id: string }; version?: { id: string } }>(
        `/sessions/${id}/versions`,
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey },
          body: JSON.stringify({ draft_revision: saved.revision }),
        }
      );

      let completedVersionId: string | undefined = requested.version?.id;
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
            completedVersionId = status.job.result?.version_id;
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

      if (completedVersionId) {
        triggerBrowserDownload(fileUrl(`/versions/${completedVersionId}/pdf?download=true`));
      } else {
        triggerBrowserDownload(fileUrl(`/sessions/${id}/pdf?download=true`));
      }
    } catch (error) {
      setActionError(apiErrorMessage(error));
    } finally {
      setGenerating(false);
    }
  }

  async function renderAuthoritativePreview() {
    setActionError(null);
    try {
      const saved = await save();
      const result = await api<{ preview_url: string }>(`/sessions/${id}/preview-render`, {
        method: "POST",
        body: JSON.stringify({ draft_revision: saved.revision }),
      });
      const url = fileUrl(result.preview_url);
      window.open(url, "_blank");
    } catch (error) {
      setActionError(apiErrorMessage(error));
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
  if (templateError && !template) {
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

  const values = fieldValues(workspace.fields);
  const customerName = values.customer_name || "VALUED CUSTOMER";
  const vehicleNo = values.vehicle_no || "ABC 1234";
  const carModel = values.car_model || "Motor Vehicle";
  const vehicleType = values.vehicle_type || "Car";
  const insuranceCompany = values.insurance_company || workspace.pinned_names?.company_name || "Motor Insurance";
  const coverageType = values.coverage_type || "Comprehensive Private";
  const coverPeriod = values.cover_period || "Standard Annual";
  const valuationType = values.valuation_type || "Market Value";
  const sumInsured = formatMoney(values.coverage_amount || values.sum_insured || "0.00");
  const dispOpts = workspace.display_options as Record<string, unknown> | undefined;
  const effPremStr = values.premium || "0.00";
  const sfRaw = values.service_fee || values.runner_fee || "";
  const effTotalStr = values.total_amount || values.total_premium_adjusted || values.gross_premium || "0.00";

  const premium = formatMoney(effPremStr || "0.00");
  const roadtax = formatMoney(values.roadtax || "0.00");
  const runnerFee = formatMoney(sfRaw || "0.00");
  const totalPayable = formatMoney(effTotalStr);

  const design2Fields: Record<string, unknown> = {
    ...workspace.fields,
    ...(workspace.discount_summary
      ? {
          motor_discount_pct: workspace.discount_summary.motor_discount_pct,
          motor_discount_amount: workspace.discount_summary.pct_discount_amount,
          quotation_discount: workspace.discount_summary.flat_discount_amount,
          effective_discount: workspace.discount_summary.effective_discount,
          net_motor_premium: workspace.discount_summary.net_motor_premium,
        }
      : {}),
    ...(effPremStr ? { premium: effPremStr, coverage_premium: effPremStr } : {}),
    ...(effTotalStr ? { total_amount: effTotalStr, total_premium_adjusted: effTotalStr } : {}),
  };

  const currentBenefits = workspace.benefit_cards?.current_benefits || [];
  const addonBenefits = workspace.benefit_cards?.available_addons || [];
  
  const allBenefits = [
    ...currentBenefits.map(b => ({ ...b, isAddon: false })),
    ...addonBenefits.map(b => ({ ...b, isAddon: true }))
  ];

  const isDesign2 = Boolean(
    template?.config?.layout_engine === "design2" ||
    template?.config?.template_key === "motor_modern_design_2" ||
    String(template?.config?.template_key || "").startsWith("motor_modern_design_2") ||
    String((template?.config as any)?.v7_master_key || "").startsWith("motor_modern_design_2") ||
    String((template?.config as any)?.template_name || "").toLowerCase().includes("design 2") ||
    String((template?.config as any)?.template_name || "").toLowerCase().includes("design2")
  );
  const design2HideAddons = Boolean((template?.config as any)?.hide_addon_upgrades);
  const design2BaseH = Number(
    (template?.config as any)?.page_profile?.height ||
      template?.config?.canvas?.height ||
      (design2HideAddons ? 580 : 1123)
  );
  const design2IncludeSchedule = !design2HideAddons && Boolean(dispOpts?.include_benefit_schedule);
  const design2CardCount = isDesign2 && !design2HideAddons
    ? buildUnifiedMatrixCards(currentBenefits, addonBenefits, undefined, 24, 24, insuranceCompany).length
    : 0;
  const design2CanvasH = design2IncludeSchedule ? design2BaseH * 2 + 16 : design2BaseH;
  
  const dynamicCanvasHeight = Math.max(baseCanvasHeight, 350 + allBenefits.length * 56 + 100);
  const canvasHeight = dynamicCanvasHeight;

  return (
    <section className="grid gap-5">
      <SessionPhaseBar
        sessionId={id}
        current="preview"
        hasVersion={Boolean(latestVersion)}
        onStep={(key) => { if (key === "extraction") onBack(); }}
      />

      {/* Top Header Card */}
      <Card className="sticky top-[68px] z-20 p-4 shadow-sm border border-[var(--rl-border)] bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-[var(--rl-text-strong)]">Final Quotation Preview</h1>
              <Badge variant="success">Ready to Generate</Badge>
            </div>
            <p className="mt-0.5 text-xs text-[var(--rl-text-muted)]">
              Final rendered preview · {insuranceCompany}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" size="sm" icon={<ArrowLeft weight="bold" />} onClick={onBack}>
              Check Values
            </Button>
            
            <Button
              variant="secondary"
              size="sm"
              icon={<Printer weight="bold" />}
              onClick={() => window.print()}
              title="Print quotation document"
            >
              Print
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={renderAuthoritativePreview}
              title="Open full-resolution HTML render in a new window"
            >
              Open HTML View
            </Button>

            {latestVersion ? (
              <a
                href={fileUrl(`/versions/${latestVersion.id}/pdf?download=true`)}
                download={`quotation_${id}_v${latestVersion.version_number}.pdf`}
                className="inline-flex h-8 items-center justify-center gap-1.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white px-3 text-xs font-semibold text-[var(--rl-text-strong)] hover:bg-gray-50 transition-all active:scale-[0.98]"
              >
                <DownloadSimple weight="bold" size={14} /> Download latest PDF
              </a>
            ) : null}

            <Button
              variant="primary"
              size="sm"
              icon={<DownloadSimple weight="bold" />}
              loading={generating}
              onClick={handleDownloadPdf}
              className="bg-[var(--rl-red)] text-white hover:bg-[var(--rl-red-dark)] shadow-sm font-bold"
            >
              {generating ? "Generating PDF..." : "Generate PDF"}
            </Button>
          </div>
        </div>
      </Card>

      {actionError ? (
        <div role="alert" className="flex items-center gap-2 rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] p-3 text-xs font-semibold text-[var(--rl-red)]">
          <WarningCircle size={16} weight="fill" className="shrink-0" />
          <span>{actionError}</span>
        </div>
      ) : null}

      {generationJob && ["queued", "processing"].includes(generationJob.state) ? (
        <Card className="grid gap-2 p-3.5 border-blue-200 bg-blue-50/50" role="status">
          <div className="flex items-center justify-between text-xs font-semibold text-blue-900">
            <span>Rendering PDF · {Math.round(generationJob.progress || 0)}% completed</span>
            <span className="font-mono">{Math.round(generationJob.elapsed_seconds || 0)}s elapsed</span>
          </div>
          <progress className="h-1.5 w-full accent-[var(--rl-red)]" max={100} value={generationJob.progress || 0} />
        </Card>
      ) : null}

      {/* Main Responsive Workspace */}
      <Group orientation="horizontal" className="min-h-[580px] items-stretch gap-5 !flex-col lg:!flex-row">
        
        {/* Left Column: Quotation Summary & Included Add-ons */}
        <Panel 
          panelRef={leftPanelRef}
          collapsible={true}
          onResize={() => setIsSidebarCollapsed(leftPanelRef.current?.isCollapsed() ?? false)}
          defaultSize="34%" 
          minSize="25%" 
          maxSize="50%" 
          className="grid gap-4 content-start w-full"
        >
          
          {/* Policy Summary Card */}
          <Card className="grid gap-3 p-4 border border-[var(--rl-border)] bg-white shadow-xs">
            <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)] border-b border-[var(--rl-border)] pb-2">
              Quotation Summary
            </h2>

            <div className="grid gap-2 text-xs">
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-[var(--rl-text-muted)] font-medium">Insured Name:</span>
                <span className="font-bold text-[var(--rl-text-strong)] text-right max-w-[180px] truncate">{customerName}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-[var(--rl-text-muted)] font-medium">Vehicle No / Plate:</span>
                <span className="font-bold text-[var(--rl-text-strong)] font-mono">{vehicleNo}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-[var(--rl-text-muted)] font-medium">Vehicle Type:</span>
                <span className="font-semibold text-[var(--rl-text-strong)]">{vehicleType}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-[var(--rl-text-muted)] font-medium">Vehicle Model:</span>
                <span className="font-semibold text-[var(--rl-text-strong)] text-right max-w-[180px] truncate">{carModel}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-[var(--rl-text-muted)] font-medium">Coverage Type:</span>
                <span className="font-semibold text-[var(--rl-text-strong)]">{coverageType}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-[var(--rl-text-muted)] font-medium">Period of Cover:</span>
                <span className="font-semibold text-[var(--rl-text-strong)] font-mono">{coverPeriod}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-[var(--rl-text-muted)] font-medium">Valuation Type:</span>
                <span className="font-semibold text-[var(--rl-text-strong)]">{valuationType}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-[var(--rl-text-muted)] font-medium">Vehicle Sum Insured:</span>
                <span className="font-semibold text-[var(--rl-text-strong)] font-mono">{sumInsured}</span>
              </div>
            </div>

            {/* Premium Calculation Breakdown Box */}
            <div className="mt-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-gray-50/80 p-3 grid gap-1.5 text-xs">
              <div className="flex justify-between text-[var(--rl-text)] font-medium">
                <span>Insurance Premium:</span>
                <span className="font-mono font-semibold">{premium}</span>
              </div>
              <div className="flex justify-between text-[var(--rl-text)] font-medium">
                <span>Road Tax:</span>
                <span className="font-mono font-semibold">{roadtax}</span>
              </div>
              <div className="flex justify-between text-[var(--rl-text)] font-medium">
                <span>Runner Fee:</span>
                <span className="font-mono font-semibold">{runnerFee}</span>
              </div>
              <div className="mt-1 flex justify-between border-t border-[var(--rl-border)] pt-2 text-sm font-bold text-[var(--rl-text-strong)]">
                <span>Total Payable:</span>
                <span className="font-mono text-[var(--rl-red)] text-base">{totalPayable}</span>
              </div>
            </div>
          </Card>

          {/* Included Benefits Summary Card */}
          <Card className="grid gap-3 p-4 border border-[var(--rl-border)] bg-white shadow-xs">
            <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2">
              <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                Included Benefits (FOC)
              </h2>
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                {currentBenefits.length} active
              </span>
            </div>

            <div className="grid max-h-[260px] gap-1.5 overflow-y-auto pr-1">
              {currentBenefits.length === 0 ? (
                <p className="text-xs text-[var(--rl-text-muted)] italic py-2">No special benefits included.</p>
              ) : (
                currentBenefits.map((benefit, idx) => (
                  <div
                    key={benefit.card_key || idx}
                    className="flex items-center justify-between rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white px-2.5 py-1.5 text-xs shadow-2xs"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <CheckCircle size={14} weight="fill" className="text-emerald-600 shrink-0" />
                      <span className="font-semibold text-[var(--rl-text-strong)] truncate">{benefit.label}</span>
                    </div>
                    <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded shrink-0 font-mono">
                      {benefit.value || "FOC"}
                    </span>
                  </div>
                ))
              )}
            </div>
          </Card>

          {/* Optional Add-ons Card (if any) */}
          {addonBenefits.length > 0 ? (
            <Card className="grid gap-3 p-4 border border-[var(--rl-border)] bg-white shadow-xs">
              <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2">
                <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                  Optional Add-on Covers
                </h2>
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-800">
                  {addonBenefits.length}
                </span>
              </div>
              <div className="grid max-h-[180px] gap-1.5 overflow-y-auto pr-1">
                {addonBenefits.map((addon, idx) => (
                  <div
                    key={addon.card_key || idx}
                    className="flex items-center justify-between rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white px-2.5 py-1.5 text-xs shadow-2xs"
                  >
                    <span className="font-medium text-[var(--rl-text-strong)] truncate">{addon.label}</span>
                    <span className="text-[10px] font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded shrink-0 font-mono">
                      {addon.value || "Optional"}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          ) : null}
        </Panel>

        <Separator className="w-2 rounded-full bg-[var(--rl-border)] hover:bg-[var(--rl-red)] transition-colors opacity-50 hover:opacity-100 cursor-col-resize self-stretch hidden lg:block" />

        {/* Right Column: Complete High-Fidelity SVG Quotation Canvas */}
        <Panel defaultSize="66%" minSize="40%" className="grid place-items-center rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[#ececee] p-6 shadow-inner relative overflow-hidden w-full h-full">
          
          {/* Zoom & View Controls Bar */}
          <div className="mb-4 flex w-full max-w-[640px] items-center justify-between rounded-md bg-white/90 px-3 py-1.5 shadow-xs backdrop-blur-xs border border-neutral-200">
            <div className="flex items-center gap-1.5 text-xs font-bold text-[var(--rl-text-strong)]">
              <button
                type="button"
                onClick={() => {
                  if (isSidebarCollapsed) {
                    leftPanelRef.current?.expand();
                  } else {
                    leftPanelRef.current?.collapse();
                  }
                }}
                className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-gray-100 transition-colors mr-2 hidden lg:block"
                title={isSidebarCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
              >
                <ArrowLeft size={16} weight="bold" className={`transition-transform ${isSidebarCollapsed ? 'rotate-180' : ''}`} />
              </button>
              <Sparkle size={14} className="text-amber-500" />
              <span>A4 Motor Quotation Document</span>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setZoom((z) => Math.max(0.4, z - 0.1))}
                className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-gray-100 transition-colors"
                title="Zoom Out"
              >
                <MagnifyingGlassMinus size={15} />
              </button>
              <span className="w-10 text-center font-mono text-[11px] font-bold text-[var(--rl-text-muted)]">
                {Math.round(zoom * 100)}%
              </span>
              <button
                type="button"
                onClick={() => setZoom((z) => Math.min(2.0, z + 0.1))}
                className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-gray-100 transition-colors"
                title="Zoom In"
              >
                <MagnifyingGlassPlus size={15} />
              </button>
              <button
                type="button"
                onClick={() => setZoom(0.75)}
                className="rounded px-1.5 py-0.5 text-[10px] font-bold text-[var(--rl-text-muted)] hover:bg-gray-100 transition-colors"
              >
                Fit
              </button>
            </div>
          </div>

          {/* High-Fidelity Quotation Canvas Container */}
          <div
            ref={canvasContainerRef}
            className="w-full max-w-[640px] bg-white shadow-card rounded-[4px] overflow-auto border border-neutral-300 transition-all duration-200"
            style={{
              transform: `scale(${zoom / 0.75})`,
              transformOrigin: "top center",
            }}
          >
            <div style={{ width: "640px", height: `${Math.round(design2CanvasH * (640 / 794))}px`, overflow: "hidden" }}>
              <div style={{ width: "794px", transform: `scale(${640 / 794})`, transformOrigin: "top left" }}>
                <Design2CanvasView
                  fields={design2Fields}
                  config={template?.config}
                  height={design2CanvasH}
                  currentBenefits={currentBenefits}
                  availableAddons={addonBenefits}
                  companyName={insuranceCompany}
                  includeSchedule={design2IncludeSchedule}
                />
              </div>
            </div>
          </div>
        </Panel>

      </Group>
    </section>
  );
}
