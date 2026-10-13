"use client";

import { useState } from "react";
import { api } from "@/lib/api";

interface UseNcdHistoryOptions {
  tenureId?: string;
  roadTax?: number;
  runnerFee?: number;
  windscreenTarget?: number | null;
  initialCurrentNcd?: number | null;
  initialNextNcd?: number | null;
  onSuccess: () => Promise<void> | void;
  triggerStatus: (type: "success" | "error", title: string, message: string) => void;
}

export function useNcdHistory({
  tenureId,
  roadTax,
  runnerFee,
  windscreenTarget,
  initialCurrentNcd,
  initialNextNcd,
  onSuccess,
  triggerStatus,
}: UseNcdHistoryOptions) {
  const [showNcdModal, setShowNcdModal] = useState(false);
  const [editCurrentNcd, setEditCurrentNcd] = useState<string>("");
  const [editNextNcd, setEditNextNcd] = useState<string>("");
  const [pastingPolicyText, setPastingPolicyText] = useState("");
  const [savingNcd, setSavingNcd] = useState(false);

  const handleOpenNcdModal = () => {
    setEditCurrentNcd(initialCurrentNcd != null ? String(initialCurrentNcd) : "");
    setEditNextNcd(initialNextNcd != null ? String(initialNextNcd) : "");
    setPastingPolicyText("");
    setShowNcdModal(true);
  };

  const handleSaveNcd = async () => {
    if (!tenureId) return;
    try {
      setSavingNcd(true);
      const currVal = editCurrentNcd.trim() !== "" ? parseFloat(editCurrentNcd) : null;
      const nextVal = editNextNcd.trim() !== "" ? parseFloat(editNextNcd) : null;

      await api(`/comparison/${tenureId}/fixed-costs`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          road_tax: roadTax ?? 0,
          runner_fee: runnerFee ?? 0,
          windscreen_target: windscreenTarget ?? null,
          ncd_percentage: nextVal,
          current_ncd: currVal,
        }),
      });

      triggerStatus(
        "success",
        "NCD Entitlement Updated",
        "Current NCD and Next NCD entitlement were successfully saved."
      );
      setShowNcdModal(false);
      await onSuccess();
    } catch (err: any) {
      triggerStatus("error", "Failed to Save NCD", err.message || String(err));
    } finally {
      setSavingNcd(false);
    }
  };

  return {
    showNcdModal,
    setShowNcdModal,
    editCurrentNcd,
    setEditCurrentNcd,
    editNextNcd,
    setEditNextNcd,
    pastingPolicyText,
    setPastingPolicyText,
    savingNcd,
    handleOpenNcdModal,
    handleSaveNcd,
  };
}
