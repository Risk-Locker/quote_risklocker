"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import {
  ArrowsClockwise,
  ArrowSquareOut,
  CircleNotch,
  FolderOpen,
  Play,
  Stack,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

interface UploadRunSummary {
  id: string;
  title: string;
  mode: string;
  status: string;
  is_test: boolean;
  total_files: number;
  created_at?: string | null;
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
}

function statusBadge(status: string): { label: string; variant: "default" | "success" | "warning" | "danger" | "info" } {
  switch (status) {
    case "completed":
      return { label: "Completed", variant: "success" };
    case "paused_quota":
      return { label: "Paused · Quota", variant: "warning" };
    case "paused":
      return { label: "Paused", variant: "warning" };
    case "completed_with_errors":
      return { label: "Partial Errors", variant: "warning" };
    case "failed":
      return { label: "Failed", variant: "danger" };
    case "cancelled":
      return { label: "Cancelled", variant: "info" };
    default:
      return { label: "Active", variant: "default" };
  }
}

export function StagingBatchesTab({ searchQuery = "" }: { searchQuery?: string }) {
  const router = useRouter();
  const { toast } = useToast();
  const [runs, setRuns] = useState<UploadRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    try {
      setLoading(true);
      const qs = new URLSearchParams({ limit: "50" });
      if (searchQuery.trim()) qs.set("search", searchQuery.trim());
      const res = await api<{ runs: UploadRunSummary[] }>(`/upload-runs?${qs.toString()}`);
      setRuns(res?.runs || []);
    } catch (err: any) {
      toast(err?.message || "Could not load staging batches.", "error");
    } finally {
      setLoading(false);
    }
  }, [searchQuery, toast]);

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  async function handleQuickAction(runId: string, kind: "resume" | "retry-failed") {
    setBusyId(runId);
    try {
      await api(`/upload-runs/${runId}/${kind}`, { method: "POST" });
      toast(kind === "resume" ? "Batch resumed." : "Failed jobs re-queued.", "success");
      await loadRuns();
    } catch (err: any) {
      toast(err?.message || "Action failed.", "error");
    } finally {
      setBusyId(null);
    }
  }

  if (loading && runs.length === 0) {
    return (
      <Card className="p-12 text-center text-xs text-[var(--rl-text-muted)]">
        <CircleNotch size={22} className="animate-spin mx-auto mb-2" />
        <span>Loading staging batches...</span>
      </Card>
    );
  }

  if (runs.length === 0) {
    return (
      <Card className="p-12 text-center flex flex-col items-center gap-3">
        <div className="size-11 rounded-[var(--rl-radius)] bg-neutral-100 text-[var(--rl-text-strong)] flex items-center justify-center">
          <Stack size={22} weight="bold" />
        </div>
        <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">No Staging Batches Yet</h3>
        <p className="text-xs text-[var(--rl-text-muted)] max-w-sm">
          Every quotation upload run is automatically saved here so you can reopen its staging screen, retry failed PDFs, or replace files anytime.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {runs.map((run) => {
        const b = statusBadge(run.status);
        const total = Math.max(1, run.counts.total || run.total_files);
        const pct = Math.min(100, Math.round(((run.counts.completed + run.counts.failed) / total) * 100));
        return (
          <Card key={run.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="min-w-0 flex-1 space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-sm font-bold text-[var(--rl-text-strong)] truncate">{run.title}</h3>
                <Badge variant={b.variant} className="text-[10px] px-2 py-0 min-h-[22px]">{b.label}</Badge>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-neutral-100 text-[var(--rl-text-muted)]">
                  {run.mode}
                </span>
                {run.is_test ? <Badge variant="warning" className="text-[10px]">Sandbox</Badge> : null}
              </div>

              <div className="flex items-center gap-3 text-[11px] text-[var(--rl-text-muted)] flex-wrap font-mono">
                <span>Done: {run.counts.completed}/{run.counts.total || run.total_files}</span>
                {run.counts.processing > 0 ? <span className="text-neutral-900">Active: {run.counts.processing}</span> : null}
                {run.counts.queued > 0 ? <span>Queued: {run.counts.queued}</span> : null}
                {run.counts.paused_quota > 0 ? <span className="text-amber-700">Paused Quota: {run.counts.paused_quota}</span> : null}
                {run.counts.failed > 0 ? <span className="text-[var(--rl-red)]">Failed: {run.counts.failed}</span> : null}
                {run.created_at ? (
                  <span>· {new Date(run.created_at).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
                ) : null}
              </div>

              <div className="h-1.5 w-full max-w-md rounded-full bg-neutral-200 overflow-hidden">
                <div className="h-full bg-[var(--rl-black)] transition-all" style={{ width: `${pct}%` }} />
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0 flex-wrap">
              {(run.counts.paused_user > 0 || run.counts.paused_quota > 0) && (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  loading={busyId === run.id}
                  onClick={() => void handleQuickAction(run.id, "resume")}
                  icon={<Play size={13} weight="bold" />}
                >
                  Resume
                </Button>
              )}
              {run.counts.failed > 0 && (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  loading={busyId === run.id}
                  onClick={() => void handleQuickAction(run.id, "retry-failed")}
                  icon={<ArrowsClockwise size={13} weight="bold" />}
                >
                  Retry Failed
                </Button>
              )}
              <Button
                type="button"
                size="sm"
                variant="primary"
                onClick={() => router.push(`/upload/batches/${run.id}` as Route)}
                icon={<FolderOpen size={14} weight="bold" />}
              >
                Open Staging Arena
                <ArrowSquareOut size={12} weight="bold" />
              </Button>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
