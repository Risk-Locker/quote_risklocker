"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowSquareOut,
  CheckCircle,
  CircleNotch,
  ClockCountdown,
  Files,
  FileText,
  Sparkle,
  Trash,
  Upload,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { GuidedTour } from "@/components/guided-tour";
import { GeminiQuotaInfoButton } from "@/components/gemini-quota-meter";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type UploadLimits = {
  max_source_pdf_bytes: number;
  max_upload_bytes?: number;
  max_bulk_upload_files?: number;
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

interface BulkFileItem {
  id: string;
  file: File;
  status: "staged" | "uploading" | "processing" | "completed" | "failed";
  progress: number;
  phase?: string;
  sessionId?: string;
  jobId?: string;
  plate?: string;
  insurer?: string;
  premium?: string | number;
  ref?: string;
  error?: string;
}

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

  // Mode state: 'single' (default) or 'bulk'
  const [mode, setMode] = useState<"single" | "bulk">("single");

  // Single upload state (100% original workflow preserved)
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
  const activeSessionId = useRef<string | null>(null);

  // Bulk upload state
  const [bulkFiles, setBulkFiles] = useState<BulkFileItem[]>([]);
  const [bulkProcessing, setBulkProcessing] = useState(false);
  const [bulkNotice, setBulkNotice] = useState("");

  const maximum = limits?.max_source_pdf_bytes || limits?.max_upload_bytes || 20 * 1024 * 1024;
  const maxBulkLimit = limits?.max_bulk_upload_files || 5;
  const gemini = limits?.gemini;

  useEffect(() => {
    api<UploadLimits>("/settings/limits").then(setLimits).catch(() => setLimits(null));
    return () => {
      mounted.current = false;
      cancelRequested.current = true;
    };
  }, []);

  // --------------------------------------------------------------------------
  // Single Upload Handlers (Preserved 100%)
  // --------------------------------------------------------------------------
  function selectFile(nextFile: File | null) {
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

  function handleSingleDragEnter(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current += 1;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  }

  function handleSingleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
    if (!isDragging) {
      setIsDragging(true);
    }
  }

  function handleSingleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  }

  function handleSingleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);
    if (loading) return;

    // If user drops multiple files while in single mode, auto-switch to bulk!
    const dropped = Array.from(e.dataTransfer.files || []);
    if (dropped.length > 1) {
      setMode("bulk");
      addBulkFiles(dropped);
      return;
    }

    const droppedFile = dropped[0] || null;
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
        const stepName = PIPELINE_STEPS.find((s) => s.key === response.job.phase)?.label;
        const prefix = stepName ? `Failed at [${stepName}]: ` : "";
        throw new Error(prefix + (response.job.error?.message || "The quotation could not be prepared. Try again."));
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

  async function submitSingle(event: React.FormEvent) {
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
      activeSessionId.current = result.session_id;
      await waitForJob(result);
    } catch (err) {
      if (!cancelRequested.current) {
        setError(apiErrorMessage(err));
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }

  async function cancelPreparation() {
    cancelRequested.current = true;
    const jobId = activeJobId.current;
    const sessionId = activeSessionId.current;
    activeJobId.current = null;
    activeSessionId.current = null;
    setLoading(false);
    setJob(null);
    setFile(null);
    setError("");
    if (sessionId) {
      try {
        await api(`/sessions/${sessionId}`, { method: "DELETE" });
      } catch {
        if (jobId) {
          api(`/jobs/${jobId}/cancel`, { method: "POST" }).catch(() => {});
        }
      }
    } else if (jobId) {
      try {
        await api(`/jobs/${jobId}/cancel`, { method: "POST" });
      } catch {
        // Ignored
      }
    }
  }

  // --------------------------------------------------------------------------
  // Bulk Upload Handlers
  // --------------------------------------------------------------------------
  function addBulkFiles(newFiles: File[]) {
    setBulkNotice("");
    const validPdfs: File[] = [];
    let oversizedCount = 0;
    let nonPdfCount = 0;

    for (const f of newFiles) {
      if (!f.name.toLowerCase().endsWith(".pdf") && f.type !== "application/pdf") {
        nonPdfCount += 1;
        continue;
      }
      if (f.size > maximum) {
        oversizedCount += 1;
        continue;
      }
      validPdfs.push(f);
    }

    if (nonPdfCount > 0 || oversizedCount > 0) {
      setBulkNotice(
        `Ignored ${nonPdfCount ? `${nonPdfCount} non-PDF file(s)` : ""}${nonPdfCount && oversizedCount ? " and " : ""}${
          oversizedCount ? `${oversizedCount} file(s) exceeding ${formatBytes(maximum)}` : ""
        }.`
      );
    }

    setBulkFiles((prev) => {
      const currentCount = prev.length;
      const availableSlots = Math.max(0, maxBulkLimit - currentCount);

      if (availableSlots <= 0) {
        setBulkNotice(`Bulk upload limit reached (${maxBulkLimit} PDFs maximum).`);
        return prev;
      }

      const toAdd = validPdfs.slice(0, availableSlots);
      if (validPdfs.length > availableSlots) {
        setBulkNotice(
          `Added ${availableSlots} PDF(s). Remaining ${validPdfs.length - availableSlots} file(s) omitted (limit is ${maxBulkLimit}).`
        );
      }

      const newItems: BulkFileItem[] = toAdd.map((f) => ({
        id: crypto.randomUUID(),
        file: f,
        status: "staged",
        progress: 0,
      }));

      return [...prev, ...newItems];
    });
  }

  function removeBulkFile(id: string) {
    if (bulkProcessing) return;
    setBulkFiles((prev) => prev.filter((item) => item.id !== id));
    setBulkNotice("");
  }

  function clearBulkFiles() {
    if (bulkProcessing) return;
    setBulkFiles([]);
    setBulkNotice("");
  }

  async function cancelBulkItem(item: BulkFileItem) {
    // Remove from UI state immediately
    setBulkFiles((prev) => prev.filter((i) => i.id !== item.id));

    // Delete session from database if created so it doesn't linger in /sessions
    if (item.sessionId) {
      try {
        await api(`/sessions/${item.sessionId}`, { method: "DELETE" });
      } catch {
        if (item.jobId) {
          api(`/jobs/${item.jobId}/cancel`, { method: "POST" }).catch(() => {});
        }
      }
    } else if (item.jobId) {
      api(`/jobs/${item.jobId}/cancel`, { method: "POST" }).catch(() => {});
    }
  }

  async function cancelAllBulk() {
    const activeItems = bulkFiles.filter(
      (i) => (i.status === "uploading" || i.status === "processing") && i.sessionId
    );
    setBulkProcessing(false);
    setBulkFiles([]);
    setBulkNotice("Batch stopped. Cancelled sessions have been deleted.");
    for (const item of activeItems) {
      if (item.sessionId) {
        api(`/sessions/${item.sessionId}`, { method: "DELETE" }).catch(() => {});
      }
    }
  }

  async function startBulkUpload() {
    if (bulkFiles.length === 0 || bulkProcessing) return;
    setBulkProcessing(true);
    setBulkNotice("");

    const stagedItems = bulkFiles.filter((f) => f.status === "staged" || f.status === "failed");
    if (stagedItems.length === 0) {
      setBulkProcessing(false);
      return;
    }

    // Mark all staged items as uploading immediately
    setBulkFiles((prev) =>
      prev.map((i) =>
        stagedItems.some((s) => s.id === i.id) ? { ...i, status: "uploading", progress: 10 } : i
      )
    );

    // Parallel intake & polling across all files at the same time
    await Promise.all(
      stagedItems.map(async (item) => {
        try {
          const form = new FormData();
          form.append("file", item.file);
          form.append("enhanced_reading", String(enhanced));

          const result = await api<UploadResult>("/uploads", {
            method: "POST",
            headers: { "Idempotency-Key": crypto.randomUUID() },
            body: form,
          });

          // Set session & job details and mark processing
          setBulkFiles((prev) =>
            prev.map((i) =>
              i.id === item.id
                ? {
                    ...i,
                    sessionId: result.session_id,
                    jobId: result.job_id,
                    status: "processing",
                    progress: 25,
                  }
                : i
            )
          );

          // Poll job concurrently without blocking other uploads
          await pollBulkJob(item.id, result.session_id, result.job_id);
        } catch (err) {
          setBulkFiles((prev) =>
            prev.map((i) =>
              i.id === item.id
                ? { ...i, status: "failed", error: apiErrorMessage(err) }
                : i
            )
          );
        }
      })
    );

    setBulkProcessing(false);
  }

  async function pollBulkJob(itemId: string, sessionId: string, jobId: string) {
    const start = Date.now();
    while (mounted.current) {
      if (Date.now() - start > MAX_JOB_WAIT_MS) {
        setBulkFiles((prev) =>
          prev.map((i) =>
            i.id === itemId ? { ...i, status: "failed", error: "Extraction timed out." } : i
          )
        );
        return;
      }

      try {
        const res = await api<{ job: JobStatus }>(`/jobs/${jobId}`);
        const currentJob = res.job;

        if (currentJob.state === "completed") {
          // Fetch session details for rich feedback
          try {
            const sRes = await api<{
              session: {
                vehicle_plate?: string;
                detected_company?: string;
                total_premium?: string | number;
                quotation_ref?: string;
              };
            }>(`/sessions/${sessionId}`);

            setBulkFiles((prev) =>
              prev.map((i) =>
                i.id === itemId
                  ? {
                      ...i,
                      status: "completed",
                      progress: 100,
                      plate: sRes.session.vehicle_plate || undefined,
                      insurer: sRes.session.detected_company || undefined,
                      premium: sRes.session.total_premium || undefined,
                      ref: sRes.session.quotation_ref || undefined,
                    }
                  : i
              )
            );
          } catch {
            setBulkFiles((prev) =>
              prev.map((i) => (i.id === itemId ? { ...i, status: "completed", progress: 100 } : i))
            );
          }
          return;
        }

        if (currentJob.state === "failed" || currentJob.state === "cancelled") {
          setBulkFiles((prev) =>
            prev.map((i) =>
              i.id === itemId
                ? {
                    ...i,
                    status: "failed",
                    error: currentJob.error?.message || "Extraction failed.",
                  }
                : i
            )
          );
          return;
        }

        // Still processing
        setBulkFiles((prev) =>
          prev.map((i) =>
            i.id === itemId
              ? {
                  ...i,
                  status: "processing",
                  progress: Math.max(i.progress, currentJob.progress || 30),
                  phase: currentJob.phase,
                }
              : i
          )
        );
      } catch {
        // Network blip, retry next iteration
      }

      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
  }

  function openAllInNewTabs() {
    const completedItems = bulkFiles.filter((f) => f.status === "completed" && f.sessionId);
    for (const item of completedItems) {
      if (item.sessionId) {
        window.open(`/sessions/${item.sessionId}`, "_blank");
      }
    }
  }

  const elapsed = job?.elapsed_seconds ?? (pollingStartedAt.current ? (Date.now() - pollingStartedAt.current) / 1000 : 0);
  const currentProgress = job?.progress || 0;

  const completedCount = bulkFiles.filter((f) => f.status === "completed").length;
  const failedCount = bulkFiles.filter((f) => f.status === "failed").length;
  const inProgressCount = bulkFiles.filter((f) => f.status === "uploading" || f.status === "processing").length;
  const isAnyBulkComplete = completedCount > 0;
  const isAllBulkDone = bulkFiles.length > 0 && completedCount + failedCount === bulkFiles.length;

  return (
    <AppShell>
      <div className="grid max-w-4xl mx-auto gap-6">
        <header>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="font-[var(--font-manrope)] text-[26px] font-bold text-[var(--rl-text-strong)]">
                Upload Quotation
              </h1>
              <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
                Upload insurer quotation PDFs. Risklocker AI auto-extracts vehicle details, rates, and benefits.
              </p>
            </div>

            {/* Mode Switcher Tabs */}
            <div className="flex items-center gap-1 rounded-lg border border-[var(--rl-border)] bg-[var(--rl-bg-surface)] p-1">
              <button
                type="button"
                onClick={() => setMode("single")}
                className={`flex items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition-all ${
                  mode === "single"
                    ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                <FileText size={15} weight={mode === "single" ? "bold" : "regular"} />
                Single Upload
              </button>
              <button
                type="button"
                onClick={() => setMode("bulk")}
                className={`flex items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition-all ${
                  mode === "bulk"
                    ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                <Files size={15} weight={mode === "bulk" ? "bold" : "regular"} />
                Bulk Upload
                <span className="rounded bg-black/5 px-1.5 py-0.5 text-[10px] font-bold text-[var(--rl-text-muted)]">
                  Up to {maxBulkLimit}
                </span>
              </button>
            </div>
          </div>
        </header>

        {/* AI Engine Status Banner */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white p-4 shadow-xs">
          <div className="flex items-center gap-3">
            <span
              className={`grid size-9 place-items-center rounded-[var(--rl-radius-sm)] ${
                gemini?.active ? "bg-[var(--rl-black)] text-white" : "bg-gray-100 text-gray-500"
              }`}
            >
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
                  ? `Active Model: ${gemini.model} · ${gemini.key_count} Key${
                      gemini.key_count > 1 ? "s" : ""
                    } · Quota: ${gemini.rpm_per_key} RPM / ${gemini.total_rpd.toLocaleString()} RPD`
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

        {/* ================================================================== */}
        {/* MODE 1: SINGLE UPLOAD (Original Workflow)                          */}
        {/* ================================================================== */}
        {mode === "single" && (
          <Card className="p-6 border border-[var(--rl-border)] shadow-xs">
            <form onSubmit={submitSingle} className="grid gap-5">
              <label
                onDragEnter={handleSingleDragEnter}
                onDragOver={handleSingleDragOver}
                onDragLeave={handleSingleDragLeave}
                onDrop={handleSingleDrop}
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
                    <p className="truncate text-[14px] font-semibold text-[var(--rl-text-strong)]">
                      {file.name}
                    </p>
                    <p className="text-[12px] text-[var(--rl-text-muted)]">{formatBytes(file.size)}</p>
                  </div>
                  {!loading ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label="Remove selected PDF"
                      onClick={() => selectFile(null)}
                    >
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
                      <Sparkle
                        aria-hidden="true"
                        size={15}
                        weight="fill"
                        className="text-[var(--rl-text-strong)]"
                      />
                      Multimodal AI Deep Extraction
                    </span>
                    <p className="text-xs text-[var(--rl-text-muted)]">
                      Intelligently reads customer name, exact car model/variant, NCD, and insurer benefit packages.
                    </p>
                  </div>
                </label>
                <GeminiQuotaInfoButton quota={limits?.gemini} />
              </div>

              {loading ? (
                <div
                  role="status"
                  aria-live="polite"
                  className="rl-tour-progress grid gap-3.5 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white p-4.5 shadow-xs"
                >
                  <div className="flex items-center justify-between gap-4">
                    <span className="font-semibold text-sm text-[var(--rl-text-strong)] flex items-center gap-2">
                      <CircleNotch size={16} weight="bold" className="animate-spin text-[var(--rl-black)]" />
                      {job?.phase === "retry_wait" ? "Retrying step..." : "Preparing Quotation with AI"}
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
                    <div
                      className="h-full bg-[var(--rl-black)] transition-[width] duration-300"
                      style={{ width: `${Math.max(currentProgress, 5)}%` }}
                    />
                  </div>

                  <div className="grid gap-2 border-t border-[var(--rl-border)] pt-3 text-xs">
                    {PIPELINE_STEPS.map((step, idx) => {
                      const stepProgress = (idx + 1) * 20;
                      const isDone = currentProgress >= stepProgress;
                      const isCurrent = currentProgress >= stepProgress - 20 && currentProgress < stepProgress;
                      return (
                        <div key={step.key} className="flex items-center justify-between text-[12px]">
                          <span
                            className={`flex items-center gap-2 ${
                              isDone
                                ? "text-[var(--rl-text-strong)] font-medium"
                                : isCurrent
                                ? "text-[var(--rl-black)] font-bold"
                                : "text-[var(--rl-text-muted)] opacity-60"
                            }`}
                          >
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
                <div
                  role="alert"
                  className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] border border-[var(--rl-red)]/20 px-4 py-3 text-[13px] font-semibold text-[var(--rl-red)]"
                >
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
        )}

        {/* ================================================================== */}
        {/* MODE 2: BULK UPLOAD                                                */}
        {/* ================================================================== */}
        {mode === "bulk" && (
          <div className="grid gap-5">
            {/* Bulk Dropzone (only shown before/during staging if below limit) */}
            {!bulkProcessing && bulkFiles.length < maxBulkLimit && (
              <Card className="p-6 border border-[var(--rl-border)] shadow-xs">
                <label
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "copy";
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    addBulkFiles(Array.from(e.dataTransfer.files || []));
                  }}
                  className="grid min-h-[160px] cursor-pointer place-items-center rounded-[var(--rl-radius)] border-2 border-dashed border-[var(--rl-border)] bg-[var(--rl-bg)] p-8 text-center transition-all hover:border-[var(--rl-black)]/30 hover:bg-[var(--rl-black)]/[0.01]"
                >
                  <span className="grid justify-items-center gap-3 pointer-events-none">
                    <span className="grid size-12 place-items-center rounded-[var(--rl-radius)] bg-[var(--rl-black)]/6 text-[var(--rl-text-strong)]">
                      <Files aria-hidden="true" size={24} weight="bold" />
                    </span>
                    <div>
                      <span className="font-[var(--font-manrope)] text-[15px] font-semibold text-[var(--rl-text-strong)] block">
                        Drag and drop multiple quotation PDFs here
                      </span>
                      <span className="text-[13px] text-[var(--rl-text-muted)] block mt-0.5">
                        Upload up to {maxBulkLimit} PDFs at once · Up to {formatBytes(maximum)} each
                      </span>
                    </div>
                  </span>
                  <input
                    className="sr-only"
                    accept="application/pdf,.pdf"
                    type="file"
                    multiple
                    disabled={bulkProcessing}
                    onChange={(event) => {
                      if (event.target.files) {
                        addBulkFiles(Array.from(event.target.files));
                      }
                    }}
                  />
                </label>
              </Card>
            )}

            {/* Bulk Notice Banner */}
            {bulkNotice && (
              <div className="flex items-center gap-2 rounded-[var(--rl-radius-sm)] border border-amber-200 bg-amber-50 px-4 py-2.5 text-[13px] font-medium text-amber-800">
                <WarningCircle size={17} weight="bold" className="shrink-0" />
                <span>{bulkNotice}</span>
              </div>
            )}

            {/* Staged / In-Flight Files List */}
            {bulkFiles.length > 0 && (
              <Card className="p-5 border border-[var(--rl-border)] bg-white shadow-xs grid gap-4">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-3">
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">
                      Bulk Queue ({bulkFiles.length} of {maxBulkLimit} Max)
                    </h2>
                    {isAllBulkDone ? (
                      <Badge variant="success">All Finished</Badge>
                    ) : bulkProcessing ? (
                      <Badge variant="default">
                        <CircleNotch size={12} weight="bold" className="animate-spin mr-1" />
                        Extracting {inProgressCount} in progress
                      </Badge>
                    ) : (
                      <Badge variant="default">Ready to Upload</Badge>
                    )}
                  </div>

                  {!bulkProcessing && (
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={clearBulkFiles}
                        className="text-[var(--rl-text-muted)] hover:text-[var(--rl-red)] text-xs gap-1.5"
                      >
                        <Trash size={14} /> Clear All
                      </Button>
                    </div>
                  )}
                </div>

                {/* Checklist Rows */}
                <div className="grid gap-2.5">
                  {bulkFiles.map((item, idx) => {
                    const isDone = item.status === "completed";
                    const isFailed = item.status === "failed";
                    const isWorking = item.status === "uploading" || item.status === "processing";

                    return (
                      <div
                        key={item.id}
                        className={`flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius-sm)] border p-3.5 transition-colors ${
                          isDone
                            ? "border-emerald-200 bg-emerald-50/40"
                            : isFailed
                            ? "border-red-200 bg-red-50/40"
                            : isWorking
                            ? "border-blue-200 bg-blue-50/20"
                            : "border-[var(--rl-border)] bg-[var(--rl-bg)]"
                        }`}
                      >
                        {/* File details & extracted info */}
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-white text-xs font-mono font-bold text-[var(--rl-text-muted)] border border-[var(--rl-border)]">
                            {idx + 1}
                          </span>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="truncate text-[13px] font-semibold text-[var(--rl-text-strong)]">
                                {item.file.name}
                              </p>
                              {item.plate && (
                                <span className="rounded bg-black px-1.5 py-0.5 font-mono text-[11px] font-bold text-white uppercase tracking-wider">
                                  {item.plate}
                                </span>
                              )}
                              {item.insurer && (
                                <span className="rounded bg-gray-200 px-1.5 py-0.5 text-[10px] font-bold text-gray-800">
                                  {item.insurer}
                                </span>
                              )}
                              {item.premium && (
                                <span className="font-mono text-[11px] font-bold text-emerald-700">
                                  RM {Number(item.premium).toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 mt-0.5 text-[11px] text-[var(--rl-text-muted)]">
                              <span>{formatBytes(item.file.size)}</span>
                              {item.ref && <span>· Ref: {item.ref}</span>}
                              {item.error && <span className="text-[var(--rl-red)] font-semibold">· {item.error}</span>}
                            </div>
                          </div>
                        </div>

                        {/* Status badge & Individual Actions */}
                        <div className="flex items-center gap-2 shrink-0">
                          {item.status === "staged" && (
                            <>
                              <span className="text-xs font-medium text-[var(--rl-text-muted)]">Staged</span>
                              {!bulkProcessing && (
                                <button
                                  type="button"
                                  onClick={() => removeBulkFile(item.id)}
                                  className="flex size-8 items-center justify-center rounded-[var(--rl-radius-sm)] text-[var(--rl-text-muted)] hover:bg-red-50 hover:text-[var(--rl-red)] transition-colors cursor-pointer"
                                  title="Remove file"
                                  aria-label="Remove file"
                                >
                                  <X size={16} weight="bold" />
                                </button>
                              )}
                            </>
                          )}

                          {isWorking && (
                            <div className="flex items-center gap-3">
                              <div className="flex items-center gap-2 font-mono text-xs text-blue-700">
                                <CircleNotch size={14} weight="bold" className="animate-spin text-blue-600" />
                                <span>{item.status === "uploading" ? "Uploading..." : `Extracting (${item.progress}%)`}</span>
                              </div>
                              <button
                                type="button"
                                onClick={() => cancelBulkItem(item)}
                                className="flex size-8 items-center justify-center rounded-[var(--rl-radius-sm)] border border-red-200 bg-red-50 text-[var(--rl-red)] hover:bg-red-100 transition-colors cursor-pointer"
                                title="Stop and delete this session"
                                aria-label="Stop and delete this session"
                              >
                                <X size={15} weight="bold" />
                              </button>
                            </div>
                          )}

                          {isDone && item.sessionId && (
                            <div className="flex items-center gap-2">
                              <Button
                                type="button"
                                size="sm"
                                variant="secondary"
                                onClick={() => router.push(`/sessions/${item.sessionId}`)}
                                className="min-h-[36px] px-3.5 text-xs font-semibold"
                              >
                                Review
                              </Button>
                              <button
                                type="button"
                                onClick={() => window.open(`/sessions/${item.sessionId}`, "_blank")}
                                className="flex size-9 items-center justify-center rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white text-[var(--rl-text-strong)] hover:border-black/40 hover:bg-[var(--rl-bg)] hover:text-black shadow-xs transition-all active:scale-95 cursor-pointer"
                                title="Open in new tab"
                                aria-label="Open in new tab"
                              >
                                <ArrowSquareOut size={20} weight="bold" />
                              </button>
                            </div>
                          )}

                          {isFailed && (
                            <div className="flex items-center gap-2">
                              <Badge variant="danger" className="text-[10px]">
                                Failed
                              </Badge>
                              <button
                                type="button"
                                onClick={() => cancelBulkItem(item)}
                                className="flex size-7 items-center justify-center rounded text-[var(--rl-text-muted)] hover:text-[var(--rl-red)]"
                                title="Remove from list"
                              >
                                <X size={14} weight="bold" />
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Batch Action Bar */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--rl-border)] pt-4">
                  <div>
                    {!bulkProcessing && !isAllBulkDone && (
                      <Button
                        type="button"
                        onClick={startBulkUpload}
                        className="bg-[var(--rl-black)] hover:bg-black text-white font-semibold px-6 gap-2"
                      >
                        <Sparkle size={16} weight="fill" />
                        Upload & Extract All ({bulkFiles.length} Quotation{bulkFiles.length > 1 ? "s" : ""})
                      </Button>
                    )}

                    {bulkProcessing && (
                      <div className="flex flex-wrap items-center gap-3">
                        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--rl-text-strong)]">
                          <CircleNotch size={16} weight="bold" className="animate-spin text-[var(--rl-black)]" />
                          Extracting batch in parallel ({completedCount} of {bulkFiles.length} ready)...
                        </div>
                        <Button
                          type="button"
                          variant="danger"
                          size="sm"
                          onClick={cancelAllBulk}
                          className="text-xs font-semibold gap-1.5"
                          title="Stop and delete all remaining uploads"
                        >
                          <X size={14} weight="bold" />
                          Stop & Cancel All
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* Post-completion actions */}
                  {isAnyBulkComplete && (
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        type="button"
                        onClick={openAllInNewTabs}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold gap-2 text-xs shadow-xs min-h-[36px] px-4"
                      >
                        <ArrowSquareOut size={18} weight="bold" />
                        Open All in New Tabs ({completedCount})
                      </Button>

                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => router.push("/sessions")}
                        className="text-xs font-semibold"
                      >
                        View in Sessions
                      </Button>

                      {isAllBulkDone && (
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => {
                            setBulkFiles([]);
                            setBulkNotice("");
                          }}
                          className="text-xs font-medium text-[var(--rl-text-muted)]"
                        >
                          Upload Another Batch
                        </Button>
                      )}
                    </div>
                  )}
                </div>

                {/* Pop-up advisory note */}
                {isAnyBulkComplete && (
                  <p className="text-[11px] text-[var(--rl-text-muted)] border-t border-[var(--rl-border)] pt-2.5">
                    💡 <strong>Tip:</strong> If &quot;Open All in New Tabs&quot; opens only 1 tab, click the pop-up icon in your browser address bar and select &quot;Always allow pop-ups for this site&quot;.
                  </p>
                )}
              </Card>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
