"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import type { Route } from "next";
import {
  ArrowsClockwise,
  ArrowSquareOut,
  CheckCircle,
  CircleNotch,
  ClockCountdown,
  Columns,
  Files,
  FileText,
  Flask,
  Sparkle,
  Trash,
  Upload,
  Warning,
  WarningCircle,
  WarningOctagon,
  X,
  Plus,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { GeminiQuotaInfoButton, type GeminiQuota } from "@/components/gemini-quota-meter";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

export type UploadMode = "single" | "comparison" | "bulk";

interface UploadWorkspaceProps {
  defaultMode?: UploadMode;
}

type UploadLimits = {
  max_source_pdf_bytes: number;
  max_upload_bytes?: number;
  max_bulk_upload_files?: number;
  gemini?: GeminiQuota;
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
  tenureId?: string;
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

export function extractDateFromFilename(filename: string): { raw: string; formatted: string; iso: string } | null {
  // Matches YYYYMMDD at start or preceded by delimiter, e.g. 20230830_JRW1813_Quotation_STMB.pdf
  const match = filename.match(/(?:^|[_\-\s])(\d{4})(\d{2})(\d{2})(?:[_\-\s]|\.pdf)/i);
  if (match) {
    const [, year, month, day] = match;
    const y = parseInt(year, 10);
    const m = parseInt(month, 10);
    const d = parseInt(day, 10);
    if (y >= 2000 && y <= 2050 && m >= 1 && m <= 12 && d >= 1 && d <= 31) {
      return {
        raw: `${year}${month}${day}`,
        formatted: `${day.padStart(2, "0")}/${month.padStart(2, "0")}/${year}`,
        iso: `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`,
      };
    }
  }
  return null;
}

export function UploadWorkspace({ defaultMode = "comparison" }: UploadWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const existingTenureId = searchParams.get("tenure_id");

  const [mode, setMode] = useState<UploadMode>(defaultMode);

  useEffect(() => {
    setMode(defaultMode);
  }, [defaultMode]);

  const handleTabChange = (newMode: UploadMode) => {
    setMode(newMode);
    if (newMode === "comparison") {
      router.push("/upload/marketing-comparison" as Route);
    } else if (newMode === "single") {
      router.push("/upload/single" as Route);
    } else if (newMode === "bulk") {
      router.push("/upload/fleet" as Route);
    }
  };

  // Single upload state
  const [file, setFile] = useState<File | null>(null);
  const [enhanced, setEnhanced] = useState(true);
  const [isTestUpload, setIsTestUpload] = useState(false);
  const [loading, setLoading] = useState(false);
  const [creatingBlank, setCreatingBlank] = useState(false);
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
  const redirectedRef = useRef(false);

  // Bulk upload state
  const [bulkFiles, setBulkFiles] = useState<BulkFileItem[]>([]);
  const [bulkProcessing, setBulkProcessing] = useState(false);
  const [bulkNotice, setBulkNotice] = useState("");

  const maximum = limits?.max_source_pdf_bytes || limits?.max_upload_bytes || 20 * 1024 * 1024;
  const maxBulkLimit = mode === "comparison" ? 10 : (limits?.max_bulk_upload_files || 10);
  const gemini = limits?.gemini;

  useEffect(() => {
    api<UploadLimits>("/settings/limits").then(setLimits).catch(() => setLimits(null));
    return () => {
      mounted.current = false;
      cancelRequested.current = true;
    };
  }, []);

  const [probingGemini, setProbingGemini] = useState(false);

  async function handleProbeGemini() {
    setProbingGemini(true);
    try {
      const res = await api<{ gemini: GeminiQuota }>("/settings/gemini/probe", { method: "POST" });
      if (res?.gemini) {
        setLimits((prev) => (prev ? { ...prev, gemini: res.gemini } : prev));
      }
    } catch (err) {
      console.error("Gemini probe failed:", err);
    } finally {
      setProbingGemini(false);
    }
  }

  // --------------------------------------------------------------------------
  // Single Upload Handlers
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

    const dropped = Array.from(e.dataTransfer.files || []);
    if (dropped.length > 1) {
      handleTabChange("bulk");
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
    form.append("is_test", String(isTestUpload));
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
  // Bulk & Comparison Upload Handlers
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

    // In comparison mode: enforce identical tenure / quotation validity dates
    let targetDateInfo: { raw: string; formatted: string; iso: string } | null = null;
    if (mode === "comparison") {
      if (bulkFiles.length > 0) {
        targetDateInfo = extractDateFromFilename(bulkFiles[0].file.name);
      } else if (validPdfs.length > 0) {
        targetDateInfo = extractDateFromFilename(validPdfs[0].name);
      }
    }

    const eligiblePdfs: File[] = [];
    let disqualifiedCount = 0;

    for (const f of validPdfs) {
      if (mode === "comparison" && targetDateInfo) {
        const fileDate = extractDateFromFilename(f.name);
        if (fileDate && fileDate.raw !== targetDateInfo.raw) {
          disqualifiedCount += 1;
          continue; // Disqualify mismatched PDF immediately with no trace
        }
      }
      eligiblePdfs.push(f);
    }

    if (disqualifiedCount > 0 && targetDateInfo) {
      setBulkNotice(
        `Wrong PDFs were uploaded: insurance validity dates do not match. The first quotation period (${targetDateInfo.formatted}) was selected, and ${disqualifiedCount} mismatched PDF(s) were disqualified.`
      );
    }

    setBulkFiles((prev) => {
      const currentCount = prev.length;
      const availableSlots = Math.max(0, maxBulkLimit - currentCount);

      if (availableSlots <= 0) {
        setBulkNotice(`Bulk upload limit reached (${maxBulkLimit} PDFs maximum).`);
        return prev;
      }

      const toAdd = eligiblePdfs.slice(0, availableSlots);
      if (eligiblePdfs.length > availableSlots) {
        setBulkNotice(
          `Added ${availableSlots} PDF(s). Remaining ${eligiblePdfs.length - availableSlots} file(s) omitted (limit is ${maxBulkLimit}).`
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
    setBulkFiles((prev) => prev.filter((i) => i.id !== item.id));
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

    setBulkFiles((prev) =>
      prev.map((i) =>
        stagedItems.some((s) => s.id === i.id) ? { ...i, status: "uploading", progress: 10 } : i
      )
    );

    const CHUNK_SIZE = 5;
    for (let c = 0; c < stagedItems.length; c += CHUNK_SIZE) {
      const currentChunk = stagedItems.slice(c, c + CHUNK_SIZE);
      await Promise.all(
        currentChunk.map(async (item) => {
          try {
            const form = new FormData();
            form.append("file", item.file);
            form.append("enhanced_reading", String(enhanced));
            form.append("is_test", String(isTestUpload));
            if (existingTenureId) {
              form.append("tenure_id", existingTenureId);
            }

            const result = await api<UploadResult>("/uploads", {
              method: "POST",
              headers: { "Idempotency-Key": crypto.randomUUID() },
              body: form,
            });

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
    }

    setBulkProcessing(false);

    // Fallback: If in comparison mode and not yet redirected, auto-navigate to comparison
    if (mode === "comparison" && !redirectedRef.current) {
      const fallbackTenure = existingTenureId || bulkFiles.find((f) => f.tenureId)?.tenureId;
      if (fallbackTenure) {
        redirectedRef.current = true;
        router.push(`/comparison?tenure_id=${fallbackTenure}&from_upload=true` as Route);
      }
    }
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
          try {
            const sRes = await api<{
              session: {
                vehicle_plate?: string;
                detected_company?: string;
                total_premium?: string | number;
                quotation_ref?: string;
                tenure_id?: string;
              };
            }>(`/sessions/${sessionId}`);

            const resolvedTenureId = sRes.session.tenure_id || existingTenureId;

            setBulkFiles((prev) =>
              prev.map((i) =>
                i.id === itemId
                  ? {
                      ...i,
                      status: "completed",
                      progress: 100,
                      plate: sRes.session.vehicle_plate || undefined,
                      tenureId: resolvedTenureId || undefined,
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
        // Network blip, retry
      }

      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
  }

  // Create a blank comparison workspace tenure directly (for manual intake without PDFs)
  async function handleStartBlankComparison() {
    setCreatingBlank(true);
    try {
      const today = new Date().toISOString().split("T")[0];
      const endDate = new Date(Date.now() + 364 * 86400000).toISOString().split("T")[0];
      const res = await api<{ id?: string; tenure?: { id: string } }>("/tenures", {
        method: "POST",
        body: JSON.stringify({
          customer_name: "New Quotation Intake",
          vehicle_no: "UNPLATED",
          coverage_start_date: today,
          coverage_end_date: endDate,
        }),
      });
      const targetId = res?.id || res?.tenure?.id;
      if (targetId) {
        router.push(`/comparison?tenure_id=${targetId}` as Route);
      } else {
        router.push("/comparison" as Route);
      }
    } catch {
      router.push("/comparison" as Route);
    } finally {
      setCreatingBlank(false);
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
    <div className="grid w-full max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto gap-6">
      <header className="border-b border-[var(--rl-border)] pb-4">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="font-[var(--font-manrope)] text-[24px] font-bold text-[var(--rl-text-strong)] tracking-tight">
              {mode === "comparison"
                ? "Marketing Comparison Intake"
                : mode === "bulk"
                ? "Corporate Fleet Upload"
                : "Upload Quotation (Sandbox)"}
            </h1>
            <p className="mt-1 text-[13px] text-[var(--rl-text-muted)] line-clamp-2">
              {mode === "comparison"
                ? "Upload 1 to 10 insurer quotation PDFs for the same vehicle (e.g. Etiqa, Berjaya Sompo, AmAssurance) to compile your side-by-side marketing comparison matrix."
                : mode === "bulk"
                ? "High-speed parallel batch intake across 10 concurrent processing slots for corporate fleet deals."
                : "Single quote preview sandbox. Real client renewal quotes should be compiled in Marketing Comparison for multi-insurer comparisons and ledger tracking."}
            </p>
          </div>

          {/* Mode Switcher with Distinct URLs */}
          <div className="shrink-0 self-start lg:self-center flex items-center gap-1 rounded-lg border border-[var(--rl-border)] bg-[var(--rl-bg-surface)] p-1 shadow-2xs">
            <button
              type="button"
              onClick={() => handleTabChange("comparison")}
              className={`flex items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                mode === "comparison"
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              <Columns size={15} weight={mode === "comparison" ? "bold" : "regular"} />
              <span>Marketing Comparison</span>
              <span className="rounded bg-amber-100 text-amber-900 border border-amber-200/60 px-1.5 py-0.2 text-[10px] font-bold">
                1–10 Quotes
              </span>
            </button>
            <button
              type="button"
              onClick={() => handleTabChange("single")}
              className={`flex items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                mode === "single"
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              <FileText size={15} weight={mode === "single" ? "bold" : "regular"} />
              <span>Single Quote</span>
            </button>
            <button
              type="button"
              onClick={() => handleTabChange("bulk")}
              className={`flex items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                mode === "bulk"
                  ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              <Files size={15} weight={mode === "bulk" ? "bold" : "regular"} />
              <span>Corporate Fleet</span>
              <span className="rounded bg-emerald-50 text-emerald-800 border border-emerald-200 px-1.5 py-0.2 text-[10px] font-bold">
                10 Slots
              </span>
            </button>
          </div>
        </div>
      </header>

      {/* AI Engine Status Banner */}
      {gemini?.status === "denied" || gemini?.last_error_code === 403 ? (
        <div className="rounded-[var(--rl-radius)] border border-rose-200 bg-rose-50/80 p-4 shadow-xs">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-[var(--rl-radius-sm)] bg-rose-600 text-white shadow-xs">
                <WarningOctagon size={20} weight="fill" />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-bold text-rose-950">
                    Gemini AI Multimodal Engine · Access Denied (HTTP 403)
                  </p>
                  <span className="rounded-full bg-rose-600 px-2 py-0.5 text-[10px] font-semibold text-white">
                    Project Access Denied
                  </span>
                </div>
                <p className="mt-1 font-mono text-xs font-semibold text-rose-900 break-words">
                  Google API: &ldquo;{gemini.last_error || "Your project has been denied access. Please contact support."}&rdquo;
                </p>
                <p className="mt-1 text-xs text-rose-800/90 leading-relaxed">
                  Google has restricted or suspended this Google Cloud project. Quotation uploads are safely falling back to <strong>offline deterministic regex parsing</strong>.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 shrink-0">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={handleProbeGemini}
                disabled={probingGemini}
                className="text-xs border-rose-300 bg-white hover:bg-rose-100 text-rose-900 gap-1.5"
              >
                <ArrowsClockwise size={13} className={probingGemini ? "animate-spin" : ""} />
                {probingGemini ? "Testing live key..." : "Test Connection"}
              </Button>
              <a
                href="https://aistudio.google.com/apikey"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white rounded-[var(--rl-radius-sm)] px-2.5 py-1.5 shadow-xs transition-colors"
              >
                Get Free Key
                <ArrowSquareOut size={12} />
              </a>
              <a
                href="https://console.cloud.google.com/billing"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-semibold bg-white border border-rose-300 hover:bg-rose-100 text-rose-900 rounded-[var(--rl-radius-sm)] px-2.5 py-1.5 shadow-xs transition-colors"
              >
                Cloud Billing
                <ArrowSquareOut size={12} />
              </a>
            </div>
          </div>
        </div>
      ) : gemini?.status === "rate_limited" || gemini?.last_error_code === 429 ? (
        <div className="rounded-[var(--rl-radius)] border border-amber-200 bg-amber-50/80 p-4 shadow-xs">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-[var(--rl-radius-sm)] bg-amber-600 text-white shadow-xs">
                <Warning size={20} weight="fill" />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-bold text-amber-950">
                    Gemini AI Multimodal Engine · Rate Limited (HTTP 429)
                  </p>
                  <span className="rounded-full bg-amber-600 px-2 py-0.5 text-[10px] font-semibold text-white">
                    Rate Limited
                  </span>
                </div>
                <p className="mt-1 text-xs text-amber-900/90 leading-relaxed">
                  Daily free quota (1,500 RPD) or minute rate limit (15 RPM) reached. Offline regex fallback is active until reset.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={handleProbeGemini}
                disabled={probingGemini}
                className="text-xs border-amber-300 bg-white hover:bg-amber-100 text-amber-900 gap-1.5"
              >
                <ArrowsClockwise size={13} className={probingGemini ? "animate-spin" : ""} />
                {probingGemini ? "Probing..." : "Re-Check Quota"}
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white p-4 shadow-xs">
          <div className="flex items-center gap-3">
            <span
              className={`grid size-9 place-items-center rounded-[var(--rl-radius-sm)] ${
                gemini?.active
                  ? "bg-emerald-600 text-white shadow-xs"
                  : (gemini?.key_count ?? 0) > 0
                  ? "bg-amber-100 text-amber-700"
                  : "bg-gray-100 text-gray-500"
              }`}
            >
              <Sparkle size={18} weight="fill" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-bold text-[var(--rl-text-strong)]">
                  {gemini?.active ? "Gemini AI Multimodal Engine" : "Gemini AI Engine"}
                </p>
                <Badge
                  variant={
                    gemini?.active
                      ? "success"
                      : (gemini?.key_count ?? 0) > 0
                      ? "warning"
                      : "default"
                  }
                >
                  {gemini?.active
                    ? gemini?.status_label || "Ready · Active"
                    : (gemini?.key_count ?? 0) > 0
                    ? gemini?.status_label || "Needs Check"
                    : "Offline"}
                </Badge>
              </div>
              <p className="text-xs text-[var(--rl-text-muted)] mt-0.5">
                {gemini?.active
                  ? `Active Model: ${gemini.model} · ${gemini.key_count ?? 1} Key${
                      (gemini.key_count ?? 1) > 1 ? "s" : ""
                    } in Pool · Daily Quota: ${(gemini.rpd_remaining ?? 440).toLocaleString()} / ${(gemini.rpd_limit ?? 440).toLocaleString()} RPD`
                  : (gemini?.key_count ?? 0) > 0
                  ? `Configured with ${gemini?.key_count ?? 1} key${(gemini?.key_count ?? 1) > 1 ? "s" : ""}. Click 'Test Key' to verify live connection.`
                  : "No Gemini API key configured. Add a key in Settings or .env to enable high-speed AI extraction."}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {(gemini?.key_count ?? 0) > 0 ? (
              <>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={handleProbeGemini}
                  disabled={probingGemini}
                  className="text-xs gap-1.5 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                >
                  <ArrowsClockwise size={13} className={probingGemini ? "animate-spin" : ""} />
                  {probingGemini ? "Testing..." : "Test Key"}
                </Button>
                {gemini?.active ? (
                  <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
                    <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Auto-Extraction Enabled
                  </span>
                ) : (
                  <Link
                    href={"/settings/ai-engine" as Route}
                    className="inline-flex items-center gap-1 text-xs font-medium text-[var(--rl-primary)] hover:underline"
                  >
                    Manage Keys
                    <ArrowSquareOut size={12} />
                  </Link>
                )}
              </>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  href={"/settings/ai-engine" as Route}
                  className="inline-flex items-center gap-1 rounded-[var(--rl-radius-sm)] bg-[var(--rl-primary)] px-2.5 py-1.5 text-xs font-medium text-white shadow-xs hover:bg-[var(--rl-primary-hover)] transition-colors"
                >
                  Add Key in Settings
                  <ArrowSquareOut size={12} />
                </Link>
                <a
                  href="https://aistudio.google.com/apikey"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:underline"
                >
                  Get Free Key
                  <ArrowSquareOut size={12} />
                </a>
              </div>
            )}
          </div>
        </div>
      )}

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

            {/* Test Upload Option */}
            <div className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white p-3.5 flex items-center justify-between gap-3">
              <label className="flex items-center gap-3 cursor-pointer flex-1 min-w-0">
                <input
                  className="h-4 w-4 accent-amber-600 rounded shrink-0"
                  type="checkbox"
                  checked={isTestUpload}
                  disabled={loading}
                  onChange={(event) => setIsTestUpload(event.target.checked)}
                />
                <div>
                  <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-[var(--rl-text-strong)]">
                    <Flask
                      aria-hidden="true"
                      size={15}
                      weight="bold"
                      className="text-amber-600"
                    />
                    Test Upload Mode (Sandbox / No Client Records)
                  </span>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Saves session for preview and quotation editing, but will never record to Hit &amp; Miss analytics or Customer Records.
                  </p>
                </div>
              </label>
              <span className="rounded bg-amber-100 text-amber-900 text-[11px] font-bold px-2 py-0.5 border border-amber-300 shrink-0 uppercase tracking-wider">
                Test / Sandbox
              </span>
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
      {/* MODE 2: MULTI-QUOTE COMPARISON OR BULK UPLOAD                       */}
      {/* ================================================================== */}
      {(mode === "bulk" || mode === "comparison") && (
        <div className="grid gap-5">
          {/* Direct Link to Start Blank 3-Column Comparison Matrix */}
          {mode === "comparison" && (
            <div className="rounded-xl border border-amber-200/80 bg-amber-50/60 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs shadow-2xs">
              <div className="space-y-0.5">
                <span className="font-bold text-slate-900 block text-sm">
                  Working with manual figures from portal logins?
                </span>
                <span className="text-slate-600 block">
                  You do not need to wait for PDFs. You can open the 3-column Marketing Comparison workspace right now to input customer and underwriter figures directly.
                </span>
              </div>
              <Button
                type="button"
                onClick={handleStartBlankComparison}
                disabled={creatingBlank}
                className="bg-neutral-900 hover:bg-black text-white font-bold text-xs gap-1.5 shrink-0 px-4 py-2 cursor-pointer shadow-xs"
              >
                {creatingBlank ? (
                  <CircleNotch size={14} weight="bold" className="animate-spin" />
                ) : (
                  <Plus size={14} weight="bold" />
                )}
                <span>Open Blank 3-Column Matrix →</span>
              </Button>
            </div>
          )}

          {/* Test Upload Option */}
          <div className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white p-3.5 flex items-center justify-between gap-3 shadow-xs">
            <label className="flex items-center gap-3 cursor-pointer flex-1 min-w-0">
              <input
                className="h-4 w-4 accent-amber-600 rounded shrink-0 cursor-pointer"
                type="checkbox"
                checked={isTestUpload}
                disabled={bulkProcessing}
                onChange={(event) => setIsTestUpload(event.target.checked)}
              />
              <div>
                <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-[var(--rl-text-strong)]">
                  <Flask
                    aria-hidden="true"
                    size={15}
                    weight="bold"
                    className="text-amber-600"
                  />
                  Test Sandbox Mode (Excluded from Customer Records &amp; Analytics)
                </span>
                <p className="text-xs text-[var(--rl-text-muted)]">
                  {mode === "comparison"
                    ? "Uploaded quotes will compile into comparison matrix for testing without contaminating live DB metrics."
                    : "Saves sessions for preview and batch testing without recording to Hit & Miss analytics or live records."}
                </p>
              </div>
            </label>
            <span className="rounded bg-amber-100 text-amber-900 text-[11px] font-bold px-2 py-0.5 border border-amber-300 shrink-0 uppercase tracking-wider">
              Test / Sandbox
            </span>
          </div>

          {/* Bulk / Comparison Dropzone */}
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
                    {mode === "comparison" ? (
                      <Columns aria-hidden="true" size={24} weight="bold" />
                    ) : (
                      <Files aria-hidden="true" size={24} weight="bold" />
                    )}
                  </span>
                  <div>
                    <span className="font-[var(--font-manrope)] text-[15px] font-semibold text-[var(--rl-text-strong)] block">
                      {mode === "comparison"
                        ? "Drag and drop 1 to 10 quotation PDFs for this vehicle"
                        : "Drag and drop multiple quotation PDFs here"}
                    </span>
                    <span className="text-[13px] text-[var(--rl-text-muted)] block mt-0.5">
                      {mode === "comparison"
                        ? "Upload quotes from different underwriters (Etiqa, Berjaya Sompo, Allianz, Zurich, etc.) · Up to 10 files"
                        : `Upload up to ${maxBulkLimit} PDFs at once · Up to ${formatBytes(maximum)} each`}
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
                    {mode === "comparison" ? "Marketing Comparison Queue" : "Corporate Fleet Queue"} ({bulkFiles.length} of {maxBulkLimit} Max)
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
                            {mode === "comparison" && item.tenureId ? (
                              <Button
                                type="button"
                                size="sm"
                                onClick={() => router.push(`/comparison?tenure_id=${item.tenureId}` as Route)}
                                className="min-h-[34px] px-3.5 text-xs font-bold bg-amber-500 hover:bg-amber-600 text-slate-950 gap-1.5 cursor-pointer shadow-2xs"
                              >
                                <Columns size={13} weight="bold" />
                                Compare
                              </Button>
                            ) : (
                              <Button
                                type="button"
                                size="sm"
                                variant="secondary"
                                onClick={() => {
                                  if (item.tenureId) {
                                    router.push(`/comparison?tenure_id=${item.tenureId}` as Route);
                                  } else {
                                    router.push(`/comparison` as Route);
                                  }
                                }}
                                className="min-h-[34px] px-3 text-xs font-semibold cursor-pointer"
                              >
                                Compare Matrix
                              </Button>
                            )}
                            <button
                              type="button"
                              onClick={() => {
                                if (item.tenureId) {
                                  window.open(`/comparison?tenure_id=${item.tenureId}`, "_blank");
                                } else {
                                  window.open(`/comparison`, "_blank");
                                }
                              }}
                              className="flex size-8 items-center justify-center rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white text-[var(--rl-text-strong)] hover:border-black/40 hover:bg-[var(--rl-bg)] hover:text-black shadow-xs transition-all active:scale-95 cursor-pointer"
                              title="Open in new tab"
                              aria-label="Open in new tab"
                            >
                              <ArrowSquareOut size={16} weight="bold" />
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
                      Upload &amp; Extract All ({bulkFiles.length} Quotation{bulkFiles.length > 1 ? "s" : ""})
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
                        Stop &amp; Cancel All
                      </Button>
                    </div>
                  )}
                </div>

                {/* Post-completion actions */}
                {isAnyBulkComplete && (
                  <div className="flex flex-wrap items-center gap-2">
                    {mode === "comparison" ? (
                      <Button
                        type="button"
                        onClick={() => {
                          const tId = bulkFiles.find((f) => f.tenureId)?.tenureId;
                          if (tId) {
                            router.push(`/comparison?tenure_id=${tId}` as Route);
                          } else {
                            router.push("/comparison" as Route);
                          }
                        }}
                        className="bg-[#1b1717] hover:bg-black text-white font-bold gap-2 text-xs shadow-xs min-h-[36px] px-5 cursor-pointer"
                      >
                        <Columns size={16} weight="bold" />
                        <span>Open Marketing Comparison Matrix →</span>
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        onClick={openAllInNewTabs}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold gap-2 text-xs shadow-xs min-h-[36px] px-4 cursor-pointer"
                      >
                        <ArrowSquareOut size={18} weight="bold" />
                        <span>Open Comparison Tab ({completedCount})</span>
                      </Button>
                    )}

                    {mode !== "comparison" && (
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => router.push("/ledger" as Route)}
                        className="text-xs font-semibold cursor-pointer"
                      >
                        View in Motor Renewal Ledger
                      </Button>
                    )}

                    {isAllBulkDone && (
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => {
                          setBulkFiles([]);
                          setBulkNotice("");
                        }}
                        className="text-xs font-medium text-[var(--rl-text-muted)] cursor-pointer"
                      >
                        Upload Another Batch
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
