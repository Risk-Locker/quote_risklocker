"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { GeminiQuota } from "@/components/gemini-quota-meter";

export interface UseQuotationConflictAndAiOptions {
  id: string;
  reload: () => Promise<void>;
  setToastMessage: (msg: string | null) => void;
}

export function useQuotationConflictAndAi({
  id,
  reload,
  setToastMessage,
}: UseQuotationConflictAndAiOptions) {
  const [ownershipConflict, setOwnershipConflict] = useState<{
    has_conflict: boolean;
    resolved: boolean;
    vehicle_no?: string;
    resolution?: { type: string; resolved_at: string; notes?: string; new_customer?: string };
  } | null>(null);
  const [conflictModalOpen, setConflictModalOpen] = useState(false);
  const [selectedResolution, setSelectedResolution] = useState<
    "car_sold_new_owner" | "old_quote_mistake" | "pending_verification"
  >("car_sold_new_owner");
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [resolvingConflict, setResolvingConflict] = useState(false);

  const [geminiExtracting, setGeminiExtracting] = useState(false);
  const [geminiQuotaInfo, setGeminiQuotaInfo] = useState<GeminiQuota | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    api<{ has_conflict: boolean; resolved: boolean; [key: string]: any }>(`/sessions/${id}/ownership-conflict`)
      .then((data) => {
        if (!cancelled) setOwnershipConflict(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function handleResolveConflict() {
    setResolvingConflict(true);
    try {
      const res = await api<{ success: boolean; resolution: any }>(`/sessions/${id}/resolve-ownership`, {
        method: "POST",
        body: JSON.stringify({
          resolution_type: selectedResolution,
          notes: resolutionNotes || undefined,
        }),
      });
      setOwnershipConflict({ has_conflict: false, resolved: true, resolution: res.resolution });
      setConflictModalOpen(false);
      setToastMessage("Vehicle ownership conflict resolved!");
    } finally {
      setResolvingConflict(false);
    }
  }

  async function triggerGeminiExtraction() {
    setGeminiExtracting(true);
    try {
      const res = await api<{ quota: GeminiQuota; message?: string }>(`/sessions/${id}/extract-gemini`, {
        method: "POST",
      });
      setGeminiQuotaInfo(res.quota);
      setToastMessage(res.message || "Gemini extraction completed");
      await reload();
    } finally {
      setGeminiExtracting(false);
    }
  }

  return {
    ownershipConflict,
    setOwnershipConflict,
    conflictModalOpen,
    setConflictModalOpen,
    selectedResolution,
    setSelectedResolution,
    resolutionNotes,
    setResolutionNotes,
    resolvingConflict,
    handleResolveConflict,
    geminiExtracting,
    geminiQuotaInfo,
    triggerGeminiExtraction,
  };
}
