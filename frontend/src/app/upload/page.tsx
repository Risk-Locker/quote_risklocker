"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle, CircleNotch, ClockCountdown, Sparkle, Upload, X } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { GuidedTour } from "@/components/guided-tour";
import { GeminiQuotaInfoButton } from "@/components/gemini-quota-meter";
import { api } from "@/lib/api";

type UploadLimits = {
  max_source_pdf_bytes: number;
  max_upload_bytes?: number;
  gemini?: {
    active: boolean;
    model: string;
    key_count: number;
    rpm_per_key: number;
    rpd_per_key: number;
    total_rpd: number;
    message: string;
  };
};
type UploadResult = { session_id: string; job_id: string; uploaded_file_id: string; created: boolean };
type JobStatus = {
  state: "queued" | "processing" | "completed" | "failed" | "cancelled";
  progress: number;
  phase?: string;
  heartbeat_at?: string | null;
  elapsed_seconds?: number;
  error?: { message?: string } | null;
};

const MAX_JOB_WAIT_MS = 15 * 60 * 1000;
const STALE_HEARTBEAT_MS = 60 * 1000;

const PIPELINE_STEPS = [
  { key: "validating_source", label: "PDF Verification & Integrity Check" },
  { key: "extracting", label: "Native Document Layout Analysis" },
  { key: "gemini_ai", label: "Gemini Multimodal AI Extraction" },
  { key: "mapping_benefits", label: "Insurer Policy & Benefit Matching" },
  { key: "saving_review", label: "Workspace Draft Finalization" },
];

function formatBytes(value: number) {
  if (value < 1024 * 1024) return `${Math.max(0, value / 1024).toFixed(0)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatElapsed(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return minutes ? `${minutes}m ${remainder.toString().padStart(2, "0")}s` : `${remainder}s`;
}

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [enhanced, setEnhanced] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [limits, setLimits] = useState<UploadLimits | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);
  const mounted = useRef(true);
  const cancelRequested = useRef(false);
  const idempotencyKey = useRef("");
  const pollingStartedAt = useRef(0);
  const activeJobId = useRef<string | null>(null);

  useEffect(() => {
    api<UploadLimits>("/settings/limits").then(setLimits).catch(() => setLimits(null));
    return () => {
      mounted.current = false;
      cancelRequested.current = true;
    };
  }, []);

  function selectFile(nextFile: File | null) {
    const maximum = limits?.max_source_pdf_bytes || limits?.max_upload_bytes || 20 * 1024 * 1024;
    setError("");
    setJob(null);
    activeJobId.current = null;
    cancelRequested.current = false;
    if (nextFile && nextFile.type !== "application/pdf" && !nextFile.name.toLowerCase().endsWith(".pdf")) {
      setFile(null);
      setError("Choose a PDF quotation.");
      return;
    }
    if (nextFile && nextFile.size > maximum) {
      setFile(null);
      setError(`This PDF exceeds the ${formatBytes(maximum)} upload limit.`);
      return;
    }
    setFile(nextFile);
    idempotencyKey.current = nextFile ? crypto.randomUUID() : "";
  }

  function handleDragEnter(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current += 1;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
    if (!isDragging) {
      setIsDragging(true);
    }
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);
    if (loading) return;
    const droppedFile = e.dataTransfer.files?.[0] || null;
    if (droppedFile) {
      selectFile(droppedFile);
    }
  }

  async function waitForJob(result: UploadResult) {
    activeJobId.current = result.job_id;
    pollingStartedAt.current = Date.now();
    while (mounted.current && !cancelRequested.current) {
      if (Date.now() - pollingStartedAt.current > MAX_JOB_WAIT_MS) {
        throw new Error("Preparation is taking longer than expected. The job is still safe; open Sessions to check it.");
      }
      const response = await api<{ job: JobStatus }>(`/jobs/${result.job_id}`);
      if (!mounted.current || cancelRequested.current) return;
      setJob(response.job);
      if (response.job.state === "completed") {
        router.push(`/sessions/${result.session_id}`);
        return;
      }
      if (response.job.state === "failed" || response.job.state === "cancelled") {
        throw new Error(response.job.error?.message || "The quotation could not be prepared. Try again.");
      }
      if (response.job.state === "processing" && response.job.heartbeat_at) {
        const heartbeatAge = Date.now() - new Date(response.job.heartbeat_at).getTime();
        if (heartbeatAge > STALE_HEARTBEAT_MS) {
          throw new Error("The preparation worker stopped responding. The job can be retried safely from Sessions.");
        }
      }
      await new Promise((resolve) => window.setTimeout(resolve, 800));
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file || loading) return;
    if (!idempotencyKey.current) idempotencyKey.current = crypto.randomUUID();
    cancelRequested.current = false;
    setLoading(true);
    setError("");
    setJob(null);
    const form = new FormData();
    form.append("file", file);
    form.append("enhanced_reading", String(enhanced));
    try {
      const result = await api<UploadResult>("/uploads", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey.current },
        body: form,
      });
      await waitForJob(result);
    } catch (err) {
      if (!cancelRequested.current) {
        setError(err instanceof Error ? err.message : "Upload failed.");
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }

  async function cancelPreparation() {
    cancelRequested.current = true;
    const jobId = activeJobId.current;
    activeJobId.current = null;
    setLoading(false);
    setJob(null);
    setFile(null);
    setError("");
    if (jobId) {
      try {
        await api(`/jobs/${jobId}/cancel`, { method: "POST" });
      } catch {
        // Ignored
      }
    }
  }


  const elapsed = job?.elapsed_seconds ?? (pollingStartedAt.current ? (Date.now() - pollingStartedAt.current) / 1000 : 0);
  const maximum = limits?.max_source_pdf_bytes || limits?.max_upload_bytes || 20 * 1024 * 1024;
  const gemini = limits?.gemini;
  const currentProgress = job?.progress || 0;

  return (
    <AppShell>
      <div className="grid max-w-4xl mx-auto gap-6">
        <header>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="font-[var(--font-manrope)] text-[26px] font-bold text-[var(--rl-text-strong)]">Upload Quotation</h1>
              <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">Upload an insurer quotation. Risklocker AI will auto-extract all vehicle details, coverage, and benefits.</p>
            </div>
            <GuidedTour
              storageKey="tour:upload"
              title="Upload Quotation"
              description="Start every quotation here. Upload exactly one insurer PDF; the AI reads it, extracts the values, and opens the review workspace."
              steps={[
                { target: "header", title: "Page purpose", body: "Upload one insurer quotation PDF. This is the start of the Upload → Check Values → Generate PDF workflow." },
                { target: ".rl-tour-dropzone", title: "Drop zone", body: "Drop a single PDF here. The AI engine banner shows whether Gemini is connected and your daily quota." },
                { target: ".rl-tour-progress", title: "Live progress", body: "Watch the 5-step pipeline: PDF verification, layout analysis, Gemini AI reading, benefit matching, and review finalization." },
              ]}
            />
          </div>
        </header>

        {/* AI Engine Status Banner */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white p-4 shadow-xs">
          <div className="flex items-center gap-3">
            <span className={`grid size-9 place-items-center rounded-[var(--rl-radius-sm)] ${gemini?.active ? "bg-[var(--rl-black)] text-white" : "bg-gray-100 text-gray-500"
              }`}>
              <Sparkle size={18} weight="fill" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-bold text-[var(--rl-text-strong)]">
                  {gemini?.active ? "Gemini AI Multimodal Engine" : "Gemini AI Engine"}
                </p>
                <Badge variant={gemini?.active ? "success" : "default"}>
                  {gemini?.active ? "Ready" : "Offline"}
                </Badge>
              </div>
              <p className="text-xs text-[var(--rl-text-muted)] mt-0.5">
                {gemini?.active
                  ? `Active Model: ${gemini.model} · ${gemini.key_count} Key${gemini.key_count > 1 ? "s" : ""} · Quota: ${gemini.rpm_per_key} RPM / ${gemini.total_rpd.toLocaleString()} RPD`
                  : "No GEMINI_API_KEY set in .env. Uploads will use offline fallback extraction."}
              </p>
            </div>
          </div>
          {gemini?.active ? (
            <span className="text-xs font-semibold text-[var(--rl-text-muted)]">
              Auto-Extraction Enabled
            </span>
          ) : null}
        </div>

        <Card className="p-6 border border-[var(--rl-border)] shadow-xs">
          <form onSubmit={submit} className="grid gap-5">
            <label
              onDragEnter={handleDragEnter}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`rl-tour-dropzone grid min-h-[170px] cursor-pointer place-items-center rounded-[var(--rl-radius)] border-2 border-dashed p-8 text-center transition-all duration-200 ${
                isDragging
                  ? "border-[var(--rl-black)] bg-[var(--rl-black)]/[0.04] scale-[1.01] ring-4 ring-[var(--rl-black)]/5 shadow-md"
                  : "border-[var(--rl-border)] bg-[var(--rl-bg)] hover:border-[var(--rl-black)]/30 hover:bg-[var(--rl-black)]/[0.01]"
              }`}
            >
              <span className="grid justify-items-center gap-3 pointer-events-none">
                <span
                  className={`grid size-12 place-items-center rounded-[var(--rl-radius)] transition-transform duration-200 ${
                    isDragging
                      ? "bg-[var(--rl-black)] text-white scale-110 shadow-sm"
                      : "bg-[var(--rl-black)]/6 text-[var(--rl-text-strong)]"
                  }`}
                >
                  <Upload aria-hidden="true" size={24} weight="bold" />
                </span>
                <div>
                  <span className="font-[var(--font-manrope)] text-[15px] font-semibold text-[var(--rl-text-strong)] block">
                    {isDragging ? "Drop your PDF quotation here" : "Choose one PDF quotation"}
                  </span>
                  <span className="text-[13px] text-[var(--rl-text-muted)] block mt-0.5">
                    Drag and drop or browse · PDF only, up to {formatBytes(maximum)}
                  </span>
                </div>
              </span>
              <input
                className="sr-only"
                accept="application/pdf,.pdf"
                type="file"
                disabled={loading}
                onChange={(event) => selectFile(event.target.files?.[0] || null)}
              />
            </label>

            {file ? (
              <div className="flex items-center justify-between gap-4 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-[14px] font-semibold text-[var(--rl-text-strong)]">{file.name}</p>
                  <p className="text-[12px] text-[var(--rl-text-muted)]">{formatBytes(file.size)}</p>
                </div>
                {!loading ? (
                  <Button type="button" variant="ghost" size="sm" aria-label="Remove selected PDF" onClick={() => selectFile(null)}>
                    <X aria-hidden="true" size={16} weight="bold" />
                  </Button>
                ) : null}
              </div>
            ) : null}

            <div className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white p-3.5 flex items-center justify-between gap-3">
              <label className="flex items-center gap-3 cursor-pointer flex-1 min-w-0">
                <input
                  className="h-4 w-4 accent-[var(--rl-black)] rounded shrink-0"
                  type="checkbox"
                  checked={enhanced}
                  disabled={loading}
                  onChange={(event) => setEnhanced(event.target.checked)}
                />
                <div>
                  <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-[var(--rl-text-strong)]">
                    <Sparkle aria-hidden="true" size={15} weight="fill" className="text-[var(--rl-text-strong)]" />
                    Multimodal AI Deep Extraction
                  </span>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Uses Gemini AI to intelligently read the insured customer name, full car model with body/transmission, NCD, and insurer benefit packages.
                  </p>
                </div>
              </label>
              <GeminiQuotaInfoButton quota={limits?.gemini} />
            </div>

            {loading ? (
              <div role="status" aria-live="polite" className="rl-tour-progress grid gap-3.5 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white p-4.5 shadow-xs">
                <div className="flex items-center justify-between gap-4">
                  <span className="font-semibold text-sm text-[var(--rl-text-strong)] flex items-center gap-2">
                    <CircleNotch size={16} weight="bold" className="animate-spin text-[var(--rl-black)]" />
                    Preparing Quotation with AI
                  </span>
                  <span className="inline-flex items-center gap-1.5 font-mono text-[12px] text-[var(--rl-text-muted)]">
                    <ClockCountdown aria-hidden="true" size={14} /> Elapsed {formatElapsed(elapsed)}
                  </span>
                </div>

                <div
                  role="progressbar"
                  aria-label="Quotation preparation"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={currentProgress}
                  className="h-2 overflow-hidden rounded-[2px] bg-gray-100"
                >
                  <div className="h-full bg-[var(--rl-black)] transition-[width] duration-300" style={{ width: `${Math.max(currentProgress, 5)}%` }} />
                </div>

                {/* Detailed Step-by-Step Log */}
                <div className="grid gap-2 border-t border-[var(--rl-border)] pt-3 text-xs">
                  {PIPELINE_STEPS.map((step, idx) => {
                    const stepProgress = (idx + 1) * 20;
                    const isDone = currentProgress >= stepProgress;
                    const isCurrent = currentProgress >= stepProgress - 20 && currentProgress < stepProgress;
                    return (
                      <div key={step.key} className="flex items-center justify-between text-[12px]">
                        <span className={`flex items-center gap-2 ${isDone
                            ? "text-[var(--rl-text-strong)] font-medium"
                            : isCurrent
                              ? "text-[var(--rl-black)] font-bold"
                              : "text-[var(--rl-text-muted)] opacity-60"
                          }`}>
                          {isDone ? (
                            <CheckCircle size={14} weight="fill" className="text-emerald-600" />
                          ) : isCurrent ? (
                            <CircleNotch size={14} weight="bold" className="animate-spin text-[var(--rl-black)]" />
                          ) : (
                            <span className="size-3.5 rounded-full border border-gray-300 inline-block" />
                          )}
                          {step.label}
                        </span>
                        <span className="font-mono text-[11px] text-[var(--rl-text-muted)]">
                          {isDone ? "Done" : isCurrent ? "Processing..." : "Pending"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {error ? (
              <div role="alert" className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] border border-[var(--rl-red)]/20 px-4 py-3 text-[13px] font-semibold text-[var(--rl-red)]">
                {error}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button
                type="submit"
                loading={loading}
                disabled={!file || loading}
                size="md"
                className="bg-[var(--rl-black)] hover:bg-black text-white font-semibold px-6 shadow-xs gap-2"
              >
                <Sparkle aria-hidden="true" size={16} weight="fill" />
                {loading ? "Preparing & Extracting with AI..." : error && file ? "Retry Upload" : "Upload & Extract"}
              </Button>
              {loading ? (
                <Button type="button" variant="secondary" size="md" onClick={cancelPreparation}>
                  Cancel preparation
                </Button>
              ) : null}
            </div>
          </form>
        </Card>
      </div>
    </AppShell>
  );
}
