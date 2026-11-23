"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

export interface RedetectStepStatus {
  key: string;
  label: string;
  status: "pending" | "active" | "done" | "skipped";
}

export interface RedetectJobState {
  job_id: string;
  scope: "session" | "comparison";
  target_id: string;
  status: "running" | "completed" | "cancelled" | "failed";
  progress_pct: number;
  current_step_key: string;
  current_step_label: string;
  why_waiting: string;
  current_quote_index: number;
  total_quotes: number;
  current_quote_name: string;
  steps: RedetectStepStatus[];
  result_summary?: Record<string, any> | null;
  error?: string | null;
}

export function useDeepRedetect(options?: {
  onCompleted?: (job: RedetectJobState) => Promise<void> | void;
  onCancelled?: (job: RedetectJobState) => void;
  onFailed?: (message: string) => void;
}) {
  const [job, setJob] = useState<RedetectJobState | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const pollRef = useRef<number | null>(null);
  const callbacksRef = useRef(options);
  callbacksRef.current = options;

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  useEffect(() => {
    if (job?.status !== "running") return;
    setElapsedSeconds(0);
    const id = window.setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [job?.job_id, job?.status]);

  const startPolling = useCallback(
    (jobId: string) => {
      stopPolling();
      const pollOnce = async () => {
        try {
          const res = await api<{ job: RedetectJobState }>(`/redetect-jobs/${jobId}`);
          const next = res?.job;
          if (!next) return;
          setJob(next);
          if (next.status === "completed") {
            stopPolling();
            setCancelling(false);
            await callbacksRef.current?.onCompleted?.(next);
          } else if (next.status === "cancelled") {
            stopPolling();
            setCancelling(false);
            callbacksRef.current?.onCancelled?.(next);
          } else if (next.status === "failed") {
            stopPolling();
            setCancelling(false);
            callbacksRef.current?.onFailed?.(next.error || "Re-detection failed.");
          }
        } catch {
          // Keep polling on transient network blip
        }
      };
      pollRef.current = window.setInterval(() => void pollOnce(), 600);
    },
    [stopPolling]
  );

  const startSessionRedetect = useCallback(
    async (sessionId: string) => {
      stopPolling();
      setCancelling(false);
      const res = await api<{ job_id: string; job: RedetectJobState }>(`/sessions/${sessionId}/redetect`, {
        method: "POST",
      });
      if (res?.job) {
        setJob(res.job);
        if (res.job.status === "running") {
          startPolling(res.job_id);
        } else if (res.job.status === "completed") {
          await callbacksRef.current?.onCompleted?.(res.job);
        }
      }
      return res?.job || null;
    },
    [startPolling, stopPolling]
  );

  const startComparisonRedetect = useCallback(
    async (tenureId: string, sessionId?: string | null) => {
      stopPolling();
      setCancelling(false);
      const res = await api<{ job_id: string; job: RedetectJobState }>(`/comparison/${tenureId}/redetect`, {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId || null, deep: true }),
      });
      if (res?.job) {
        setJob(res.job);
        if (res.job.status === "running") {
          startPolling(res.job_id);
        } else if (res.job.status === "completed") {
          await callbacksRef.current?.onCompleted?.(res.job);
        }
      }
      return res?.job || null;
    },
    [startPolling, stopPolling]
  );

  const cancelRedetect = useCallback(async () => {
    if (!job?.job_id || job.status !== "running" || cancelling) return;
    setCancelling(true);
    try {
      const res = await api<{ cancelled: boolean; job: RedetectJobState }>(`/redetect-jobs/${job.job_id}/cancel`, {
        method: "POST",
      });
      if (res?.job) setJob(res.job);
    } catch {
      setCancelling(false);
    }
  }, [cancelling, job]);

  const dismissBanner = useCallback(() => {
    if (job?.status === "running") return;
    setJob(null);
  }, [job?.status]);

  return {
    job,
    isRunning: job?.status === "running",
    cancelling,
    elapsedSeconds,
    startSessionRedetect,
    startComparisonRedetect,
    cancelRedetect,
    dismissBanner,
  };
}
