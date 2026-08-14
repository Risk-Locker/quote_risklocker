"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ClockCountdown, Sparkle, Upload, X } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";

type UploadLimits = { max_source_pdf_bytes: number; max_upload_bytes?: number };
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

const PHASE_LABELS: Record<string, string> = {
  queued: "Waiting for worker",
  starting: "Starting preparation",
  validating_source: "Checking PDF",
  extracting: "Reading quotation",
  saving_review: "Preparing review",
  retry_wait: "Waiting to retry",
  completed: "Quotation ready",
  failed: "Preparation failed",
  cancelled: "Preparation cancelled",
};

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

function phaseLabel(job: JobStatus | null) {
  if (!job) return "Uploading PDF";
  return PHASE_LABELS[job.phase || job.state] || "Preparing quotation";
}

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [enhanced, setEnhanced] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [limits, setLimits] = useState<UploadLimits | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
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
        router.push(`/sessions/${result.session_id}/review`);
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
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
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
    if (jobId) {
      try {
        await api(`/jobs/${jobId}/cancel`, { method: "POST" });
      } catch {
        // The worker may have completed between the click and this request.
      }
    }
    setLoading(false);
    setJob((current) => current ? { ...current, state: "cancelled", phase: "cancelled" } : current);
    setError("Preparation cancelled. The uploaded source remains available in Sessions.");
  }

  const elapsed = job?.elapsed_seconds ?? (pollingStartedAt.current ? (Date.now() - pollingStartedAt.current) / 1000 : 0);
  const maximum = limits?.max_source_pdf_bytes || limits?.max_upload_bytes || 20 * 1024 * 1024;

  return (
    <AppShell>
      <div className="grid gap-6">
        <header>
          <h1 className="font-[var(--font-manrope)] text-[30px] font-bold text-[var(--rl-text-strong)]">Upload quotation PDF</h1>
          <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">Upload one insurer quotation. Risklocker will prepare the values and facilities for review.</p>
        </header>

        <Card className="p-6">
          <form onSubmit={submit} className="grid gap-5">
            <label className="grid min-h-[160px] cursor-pointer place-items-center rounded-[var(--rl-radius)] border-2 border-dashed border-[var(--rl-border)] bg-[var(--rl-bg)] p-8 text-center transition-colors hover:border-[var(--rl-black)]/30">
              <span className="grid justify-items-center gap-3">
                <span className="grid size-12 place-items-center rounded-[var(--rl-radius)] bg-[var(--rl-black)]/6">
                  <Upload aria-hidden="true" size={24} weight="bold" />
                </span>
                <span className="font-[var(--font-manrope)] text-[16px] font-semibold text-[var(--rl-text-strong)]">Choose one PDF quotation</span>
                <span className="text-[13px] text-[var(--rl-text-muted)]">PDF only, up to {formatBytes(maximum)}</span>
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
              <div className="flex items-center justify-between gap-4 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] px-4 py-3">
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

            <label className="flex items-center gap-3">
              <input className="h-4 w-4 accent-[var(--rl-red)]" type="checkbox" checked={enhanced} disabled={loading} onChange={(event) => setEnhanced(event.target.checked)} />
              <span className="inline-flex items-center gap-1.5 text-[14px] font-medium text-[var(--rl-text)]">
                <Sparkle aria-hidden="true" size={16} weight="fill" />
                Use enhanced reading
              </span>
            </label>

            {loading ? (
              <div role="status" aria-live="polite" className="grid gap-2 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-4">
                <div className="flex items-center justify-between gap-4">
                  <span className="font-semibold text-[var(--rl-text-strong)]">{phaseLabel(job)}</span>
                  <span className="inline-flex items-center gap-1.5 font-mono text-[12px] text-[var(--rl-text-muted)]">
                    <ClockCountdown aria-hidden="true" size={15} /> Elapsed {formatElapsed(elapsed)}
                  </span>
                </div>
                <div
                  role="progressbar"
                  aria-label="Quotation preparation"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={job?.progress || 0}
                  className="h-2 overflow-hidden rounded-[2px] bg-[var(--rl-border)]"
                >
                  <div className="h-full bg-[var(--rl-red)] transition-[width] duration-300" style={{ width: `${job?.progress || 2}%` }} />
                </div>
              </div>
            ) : null}

            {error ? <div role="alert" className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div> : null}

            <div className="flex flex-wrap gap-2">
              <Button type="submit" loading={loading} disabled={!file || loading} size="md">
                <Upload aria-hidden="true" size={16} weight="bold" />
                {loading ? "Preparing quotation" : error && file ? "Retry upload" : "Upload quotation PDF"}
              </Button>
              {loading ? <Button type="button" variant="secondary" size="md" onClick={cancelPreparation}>Cancel preparation</Button> : null}
            </div>
          </form>
        </Card>
      </div>
    </AppShell>
  );
}
