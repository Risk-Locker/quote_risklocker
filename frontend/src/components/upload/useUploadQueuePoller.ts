"use client";

import { useEffect, useRef } from "react";
import { api } from "@/lib/api";

export interface PollableBulkItem {
  id: string;
  file: File;
  status: "staged" | "uploading" | "processing" | "completed" | "failed";
  progress: number;
  phase?: string;
  sessionId?: string;
  jobId?: string;
  queuePosition?: number;
  otherUsersCount?: number;
  tenureId?: string;
  plate?: string;
  insurer?: string;
  premium?: string | number;
  ref?: string;
  error?: string;
  estimatedTokens?: number;
  pageCount?: number;
  isEligible?: boolean;
  warning?: string;
}

interface BatchJobInfo {
  id: string;
  state: "queued" | "processing" | "completed" | "failed" | "cancelled";
  progress: number;
  phase?: string;
  queue_position?: number;
  other_users_count?: number;
  error?: { message?: string } | null;
}

interface UseUploadQueuePollerOptions<T extends PollableBulkItem> {
  bulkFiles: T[];
  setBulkFiles: React.Dispatch<React.SetStateAction<T[]>>;
  existingTenureId?: string | null;
}

const MAX_BATCH_IDS = 50;
const POLL_INTERVAL_MS = 2500;
const MAX_CONCURRENT_HYDRATES = 4;

export function useUploadQueuePoller<T extends PollableBulkItem>({
  bulkFiles,
  setBulkFiles,
  existingTenureId,
}: UseUploadQueuePollerOptions<T>) {
  const filesRef = useRef<T[]>(bulkFiles);
  filesRef.current = bulkFiles;
  const hydratingSessionsRef = useRef<Set<string>>(new Set());
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const hasActiveJobs = bulkFiles.some(
    (item) => (item.status === "processing" || item.status === "uploading") && Boolean(item.jobId)
  );
  const hasUnhydratedCompleted = bulkFiles.some(
    (item) => item.status === "completed" && Boolean(item.sessionId) && !item.tenureId
  );

  useEffect(() => {
    if (!hasActiveJobs && !hasUnhydratedCompleted) return;
    let cancelled = false;
    let inFlight = false;

    async function hydrateCompletedSession(item: T) {
      if (!item.sessionId || hydratingSessionsRef.current.has(item.id)) return;
      hydratingSessionsRef.current.add(item.id);
      try {
        const sRes = await api<{
          session: {
            vehicle_plate?: string;
            detected_company?: string;
            total_premium?: string | number;
            quotation_ref?: string;
            tenure_id?: string;
            document_type?: string;
          };
        }>(`/sessions/${item.sessionId}`);

        if (!isMountedRef.current) return;
        const resolvedTenureId = sRes?.session?.tenure_id || existingTenureId || undefined;
        const isCoverNote =
          sRes?.session?.document_type === "covernote" ||
          /cover[\s_-]*note/i.test(item.file?.name || "");

        if (isCoverNote && resolvedTenureId) {
          const currentPlate = sRes?.session?.vehicle_plate || item.file?.name || "Vehicle";
          let existingBatch: any = null;
          try {
            const raw = localStorage.getItem("rl_latest_policy_issue");
            if (raw) {
              const parsed = JSON.parse(raw);
              if (parsed && parsed.timestamp && Date.now() - parsed.timestamp < 15000) {
                existingBatch = parsed;
              }
            }
          } catch { }

          const count = (existingBatch?.count || 0) + 1;
          const vehicles = Array.from(new Set([...(existingBatch?.vehicles || []), currentPlate]));
          const eventData = {
            tenure_id: resolvedTenureId,
            vehicle_no: currentPlate,
            company: sRes?.session?.detected_company || "Underwriter",
            timestamp: Date.now(),
            count,
            vehicles,
          };
          try {
            localStorage.setItem("rl_latest_policy_issue", JSON.stringify(eventData));
            window.dispatchEvent(new CustomEvent("rl_policy_issued", { detail: eventData }));
          } catch { }
        }

        setBulkFiles((prev) =>
          prev.map((curr) =>
            curr.id === item.id
              ? {
                ...curr,
                status: "completed",
                progress: 100,
                plate: sRes?.session?.vehicle_plate || curr.plate,
                tenureId: resolvedTenureId || curr.tenureId,
                insurer: sRes?.session?.detected_company || curr.insurer,
                premium: sRes?.session?.total_premium || curr.premium,
                ref: sRes?.session?.quotation_ref || curr.ref,
                phase: undefined,
                error: undefined,
              }
              : curr
          )
        );
      } catch {
        if (!isMountedRef.current) return;
        setBulkFiles((prev) =>
          prev.map((curr) =>
            curr.id === item.id
              ? { ...curr, status: "completed", progress: 100, phase: undefined }
              : curr
          )
        );
      } finally {
        hydratingSessionsRef.current.delete(item.id);
      }
    }

    async function pollBatch() {
      if (cancelled || inFlight) return;
      const unhydratedDone = filesRef.current.filter(
        (item) => item.status === "completed" && Boolean(item.sessionId) && !item.tenureId
      );
      if (unhydratedDone.length > 0) {
        void Promise.all(unhydratedDone.slice(0, MAX_CONCURRENT_HYDRATES).map((it) => hydrateCompletedSession(it)));
      }

      const activeItems = filesRef.current.filter(
        (item) => (item.status === "processing" || item.status === "uploading") && Boolean(item.jobId)
      );
      if (activeItems.length === 0) return;

      inFlight = true;
      try {
        const jobIds = Array.from(new Set(activeItems.map((i) => i.jobId!).filter(Boolean)));
        const mergedJobs: Record<string, BatchJobInfo> = {};

        for (let i = 0; i < jobIds.length; i += MAX_BATCH_IDS) {
          const chunk = jobIds.slice(i, i + MAX_BATCH_IDS);
          const res = await api<{ jobs: Record<string, BatchJobInfo> }>(
            `/jobs/status?ids=${encodeURIComponent(chunk.join(","))}`
          );
          if (res?.jobs) {
            Object.assign(mergedJobs, res.jobs);
          }
        }

        if (cancelled) return;

        // Compute completed items cleanly outside setBulkFiles updater so React 18 batching is deterministic
        const newlyCompleted = activeItems.filter(
          (item) => item.jobId && mergedJobs[item.jobId]?.state === "completed"
        );

        setBulkFiles((prev) =>
          prev.map((item) => {
            if (!item.jobId || (item.status !== "processing" && item.status !== "uploading")) {
              return item;
            }
            const jobInfo = mergedJobs[item.jobId];
            if (!jobInfo) return item;

            if (jobInfo.state === "completed") {
              // Keep 'processing' until hydrateCompletedSession resolves tenureId so Compare links are never blank
              if (item.sessionId && !item.tenureId && !existingTenureId) {
                return {
                  ...item,
                  status: "processing",
                  progress: 98,
                  phase: "Linking comparison workspace...",
                  error: undefined,
                };
              }
              return {
                ...item,
                status: "completed",
                progress: 100,
                tenureId: item.tenureId || existingTenureId || undefined,
                phase: undefined,
                error: undefined,
              };
            }
            if (jobInfo.state === "failed" || jobInfo.state === "cancelled") {
              return {
                ...item,
                status: "failed",
                error: jobInfo.error?.message || "Extraction failed.",
              };
            }
            return {
              ...item,
              status: "processing",
              progress: Math.max(item.progress, jobInfo.progress || 25),
              phase: jobInfo.phase || item.phase,
              queuePosition: jobInfo.queue_position ?? item.queuePosition,
              otherUsersCount: jobInfo.other_users_count ?? item.otherUsersCount,
            };
          })
        );

        if (newlyCompleted.length > 0) {
          await Promise.all(newlyCompleted.map((item) => hydrateCompletedSession(item)));
        }
      } catch {
        // Network blip during batch poll; retry next tick
      } finally {
        inFlight = false;
      }
    }

    pollBatch();
    const timer = window.setInterval(pollBatch, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [hasActiveJobs, hasUnhydratedCompleted, existingTenureId, setBulkFiles]);
}
