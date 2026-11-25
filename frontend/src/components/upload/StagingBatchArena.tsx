"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import {
  ArrowLeft,
  ArrowsClockwise,
  ArrowSquareOut,
  CircleNotch,
  ClockCountdown,
  Columns,
  FileArrowUp,
  Pause,
  Play,
  WarningCircle,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { DeepRedetectProgressBanner } from "@/components/redetect/DeepRedetectProgressBanner";
import { useDeepRedetect } from "@/components/redetect/useDeepRedetect";
import { LiveFleetInspector } from "@/components/upload/LiveFleetInspector";
import { useRealtimeSync } from "@/hooks/useRealtimeSync";
import { useOpenInNewTabPreference, openTargetRoute } from "@/hooks/useOpenInNewTabPreference";
import { api } from "@/lib/api";

interface StagingItem {
  job_id: string;
  session_id?: string | null;
  uploaded_file_id?: string | null;
  filename: string;
  size_bytes: number;
  state: "queued" | "processing" | "paused_quota" | "paused_user" | "completed" | "failed" | "cancelled";
  progress: number;
  phase: string;
  paused_reason?: string | null;
  error?: string | null;
  tenure_id?: string | null;
  document_type?: string | null;
  insurer?: string | null;
  plate?: string | null;
  premium?: string | number | null;
  ref?: string | null;
  draft_status?: string | null;
}

interface UploadRunDetailResponse {
  run: {
    id: string;
    title: string;
    mode: string;
    status: string;
    tenure_id?: string | null;
    is_test: boolean;
    total_files: number;
    counts: {
      total: number;
      queued: number;
      processing: number;
      paused_quota: number;
      paused_user: number;
      completed: number;
      needs_review: number;
      failed: number;
      cancelled: number;
    };
    created_at?: string | null;
  };
  items: StagingItem[];
  eta_seconds: number;
  active_lanes_count: number;
  total_lanes_count: number;
  seconds_until_pt_reset: number;
}

function formatDuration(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rem = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${rem.toString().padStart(2, "0")}s`;
  return `${rem}s`;
}

function itemBadge(state: StagingItem["state"]): { label: string; variant: "default" | "success" | "warning" | "danger" | "info" } {
  switch (state) {
    case "completed":
      return { label: "Completed", variant: "success" };
    case "processing":
      return { label: "Processing", variant: "default" };
    case "queued":
      return { label: "Queued", variant: "info" };
    case "paused_quota":
      return { label: "Paused · Quota", variant: "warning" };
    case "paused_user":
      return { label: "Paused", variant: "warning" };
    case "failed":
      return { label: "Failed", variant: "danger" };
    case "cancelled":
      return { label: "Cancelled", variant: "info" };
    default:
      return { label: state, variant: "info" };
  }
}

export function StagingBatchArena({ runId }: { runId: string }) {
  const router = useRouter();
  const { toast } = useToast();
  const { openInNewTab } = useOpenInNewTabPreference();
  const [detail, setDetail] = useState<UploadRunDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [redetectingSessionId, setRedetectingSessionId] = useState<string | null>(null);
  const [replacingSessionId, setReplacingSessionId] = useState<string | null>(null);
  const replaceInputRef = useRef<HTMLInputElement | null>(null);
  const replaceTargetRef = useRef<StagingItem | null>(null);

  const loadDetail = useCallback(async () => {
    try {
      const res = await api<UploadRunDetailResponse>(`/upload-runs/${runId}`);
      setDetail(res);
      setError(null);
    } catch (err: any) {
      setError(err?.message || "Failed to load staging batch.");
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const counts = detail?.run?.counts;
  const shouldPoll = Boolean(
    counts && (counts.queued > 0 || counts.processing > 0 || counts.paused_quota > 0)
  );

  useEffect(() => {
    if (!shouldPoll) return;
    const timer = window.setInterval(() => {
      void loadDetail();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [shouldPoll, loadDetail]);

  useRealtimeSync({
    scope: "upload_runs",
    resourceId: runId,
    onRemoteUpdate: () => void loadDetail(),
  });

  const deepRedetect = useDeepRedetect({
    onCompleted: async () => {
      setRedetectingSessionId(null);
      toast("Re-detection completed inside staging batch.", "success");
      await loadDetail();
    },
    onCancelled: () => {
      setRedetectingSessionId(null);
      toast("Re-detection cancelled.", "info");
    },
    onFailed: (msg) => {
      setRedetectingSessionId(null);
      toast(`Re-detection failed: ${msg}`, "error");
    },
  });

  async function runBatchAction(kind: "pause" | "resume" | "retry-failed") {
    setActionLoading(kind);
    try {
      await api(`/upload-runs/${runId}/${kind}`, { method: "POST" });
      toast(
        kind === "pause"
          ? "Batch queued jobs paused."
          : kind === "resume"
            ? "Batch resumed and queued."
            : "Failed items re-queued for extraction.",
        "success"
      );
      await loadDetail();
    } catch (err: any) {
      toast(err?.message || "Action failed.", "error");
    } finally {
      setActionLoading(null);
    }
  }

  function triggerReplacePdf(item: StagingItem) {
    replaceTargetRef.current = item;
    if (replaceInputRef.current) {
      replaceInputRef.current.value = "";
      replaceInputRef.current.click();
    }
  }

  async function handleReplaceFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    const target = replaceTargetRef.current;
    if (!file || !target || !detail) return;

    setReplacingSessionId(target.session_id || target.job_id);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("enhanced_reading", "true");
      form.append("is_test", String(detail.run.is_test));
      form.append("upload_run_id", detail.run.id);
      form.append("upload_mode", detail.run.mode);
      if (target.tenure_id || detail.run.tenure_id) {
        form.append("tenure_id", String(target.tenure_id || detail.run.tenure_id));
      }
      if (target.session_id) {
        form.append("replace_session_id", target.session_id);
      }
      await api("/uploads", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: form,
      });
      toast(`Replaced with ${file.name} and queued for extraction.`, "success");
      await loadDetail();
    } catch (err: any) {
      toast(err?.message || "Failed to replace PDF.", "error");
    } finally {
      setReplacingSessionId(null);
      replaceTargetRef.current = null;
    }
  }

  if (loading && !detail) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-12 text-center text-xs text-[var(--rl-text-muted)]">
        <CircleNotch size={24} className="animate-spin mx-auto mb-2" />
        <span>Loading staging batch...</span>
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12">
        <Card className="p-6 border-red-200 bg-red-50 text-xs text-red-900 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <WarningCircle size={18} weight="bold" />
            <span>{error}</span>
          </div>
          <Link href={"/sessions" as Route} className="underline font-semibold">
            Back to Sessions
          </Link>
        </Card>
      </div>
    );
  }

  const run = detail!.run;
  const items = detail!.items;

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-6 space-y-5">
      <input
        ref={replaceInputRef}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden"
        onChange={(e) => void handleReplaceFileChange(e)}
      />

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--rl-border)] pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-[var(--rl-text-muted)] mb-1">
            <Link href={"/sessions?tab=batches" as Route} className="inline-flex items-center gap-1 hover:text-[var(--rl-text-strong)]">
              <ArrowLeft size={13} weight="bold" />
              <span>Staging Batches</span>
            </Link>
            <span>·</span>
            <span className="uppercase font-mono">{run.mode}</span>
          </div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-2xl font-bold tracking-tight text-[var(--rl-text-strong)]">{run.title}</h1>
            <LiveFleetInspector uploadRunId={run.id} />
          </div>
          <p className="text-xs text-[var(--rl-text-muted)] mt-0.5">
            Server-persisted staging batch · Safe to close this tab anytime · ETA{" "}
            {detail!.eta_seconds > 0 ? `~${formatDuration(detail!.eta_seconds)}` : "Idle"} ({detail!.active_lanes_count}/{detail!.total_lanes_count} active lanes)
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {(run.counts.queued > 0 || run.counts.paused_quota > 0) && (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              loading={actionLoading === "pause"}
              onClick={() => void runBatchAction("pause")}
              icon={<Pause size={14} weight="bold" />}
            >
              Pause Batch
            </Button>
          )}
          {(run.counts.paused_user > 0 || run.counts.paused_quota > 0) && (
            <Button
              type="button"
              size="sm"
              variant="primary"
              loading={actionLoading === "resume"}
              onClick={() => void runBatchAction("resume")}
              icon={<Play size={14} weight="bold" />}
            >
              Resume Batch
            </Button>
          )}
          {run.counts.failed > 0 && (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              loading={actionLoading === "retry-failed"}
              onClick={() => void runBatchAction("retry-failed")}
              icon={<ArrowsClockwise size={14} weight="bold" />}
            >
              Retry Failed ({run.counts.failed})
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => void loadDetail()}
            icon={<ArrowsClockwise size={14} weight="bold" />}
          >
            Refresh
          </Button>
        </div>
      </div>

      <DeepRedetectProgressBanner
        job={deepRedetect.job}
        elapsedSeconds={deepRedetect.elapsedSeconds}
        cancelling={deepRedetect.cancelling}
        onCancel={() => void deepRedetect.cancelRedetect()}
        onDismiss={deepRedetect.dismissBanner}
      />

      {run.counts.paused_quota > 0 ? (
        <Card className="p-4 border-amber-300 bg-amber-50/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-2.5 text-xs text-amber-950">
            <ClockCountdown size={18} weight="bold" className="text-amber-700 shrink-0 mt-0.5" />
            <div>
              <div className="font-bold">Daily Quota Reached — Auto-Resume Scheduled</div>
              <div className="mt-0.5">
                {run.counts.paused_quota} PDF(s) are safely paused and will auto-resume at Pacific Time midnight (4:00 PM MYT, in {formatDuration(detail!.seconds_until_pt_reset)}).
              </div>
            </div>
          </div>
          <Link
            href={"/settings?tab=ai-fleet" as Route}
            className="text-xs font-bold px-3 py-2 rounded-[var(--rl-radius-sm)] bg-amber-900 text-white hover:bg-black shrink-0"
          >
            Add API Key to Resume Now
          </Link>
        </Card>
      ) : null}

      {/* Summary Counters */}
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-2.5">
        {[
          { label: "Total", value: run.counts.total },
          { label: "Queued", value: run.counts.queued },
          { label: "Processing", value: run.counts.processing },
          { label: "Paused Quota", value: run.counts.paused_quota },
          { label: "Completed", value: run.counts.completed },
          { label: "Failed", value: run.counts.failed },
        ].map((c) => (
          <Card key={c.label} className="p-3">
            <div className="text-[11px] uppercase tracking-wider text-[var(--rl-text-muted)] font-semibold">{c.label}</div>
            <div className="text-lg font-mono font-bold text-[var(--rl-text-strong)] mt-0.5">{c.value}</div>
          </Card>
        ))}
      </div>

      {/* Interactive Staging Items */}
      <Card className="p-4 space-y-2.5">
        {items.length === 0 ? (
          <div className="py-10 text-center text-xs text-[var(--rl-text-muted)]">No files recorded in this staging batch.</div>
        ) : (
          items.map((item, idx) => {
            const b = itemBadge(item.state);
            const sessionRoute = item.session_id
              ? `${run.is_test ? "/sessions/sandbox" : "/sessions"}/${item.session_id}`
              : null;
            const isBusyRow = item.state === "processing" || replacingSessionId === (item.session_id || item.job_id);
            return (
              <div
                key={item.job_id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3.5"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-white text-xs font-mono font-bold text-[var(--rl-text-muted)] border border-[var(--rl-border)]">
                    {idx + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="truncate text-[13px] font-semibold text-[var(--rl-text-strong)]">{item.filename}</p>
                      <Badge variant={b.variant} className="text-[10px] px-2 py-0 min-h-[22px]">
                        {b.label}
                      </Badge>
                      {item.plate ? (
                        <span className="rounded bg-black px-1.5 py-0.5 font-mono text-[11px] font-bold text-white uppercase">
                          {item.plate}
                        </span>
                      ) : null}
                      {item.insurer ? (
                        <span className="rounded bg-neutral-200 px-1.5 py-0.5 text-[10px] font-bold text-neutral-800">
                          {item.insurer}
                        </span>
                      ) : null}
                      {item.premium ? (
                        <span className="font-mono text-[11px] font-bold text-emerald-700">
                          RM {Number(item.premium).toLocaleString("en-MY", { minimumFractionDigits: 2 })}
                        </span>
                      ) : null}
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-[var(--rl-text-muted)] flex-wrap">
                      <span className="font-mono">{item.progress}% · {item.phase}</span>
                      {item.ref ? <span>· Ref: {item.ref}</span> : null}
                      {item.paused_reason ? <span className="text-amber-800">· {item.paused_reason}</span> : null}
                      {item.error ? <span className="text-[var(--rl-red)] font-semibold">· {item.error}</span> : null}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0 flex-wrap">
                  {isBusyRow ? <CircleNotch size={15} className="animate-spin text-[var(--rl-text-muted)]" /> : null}

                  {item.session_id ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      disabled={redetectingSessionId === item.session_id}
                      onClick={() => {
                        setRedetectingSessionId(item.session_id!);
                        void deepRedetect.startSessionRedetect(item.session_id!);
                      }}
                      icon={<ArrowsClockwise size={13} weight="bold" className={redetectingSessionId === item.session_id ? "animate-spin" : ""} />}
                    >
                      Re-detect
                    </Button>
                  ) : null}

                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={replacingSessionId === (item.session_id || item.job_id)}
                    onClick={() => triggerReplacePdf(item)}
                    icon={<FileArrowUp size={13} weight="bold" />}
                  >
                    Replace PDF
                  </Button>

                  {item.tenure_id ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => openTargetRoute(`/comparison?tenure_id=${item.tenure_id}`, { openInNewTab, router })}
                      icon={<Columns size={13} weight="bold" />}
                    >
                      Compare
                    </Button>
                  ) : null}

                  {sessionRoute ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="primary"
                      onClick={() => openTargetRoute(sessionRoute, { openInNewTab, router })}
                      icon={<ArrowSquareOut size={13} weight="bold" />}
                    >
                      Open
                    </Button>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </Card>
    </div>
  );
}
