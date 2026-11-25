"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import type { TenureRow } from "./types";
import type { useLedgerState } from "./useLedgerState";

/** Pure UTC leap-safe 1-year policy end date (start + 1 year - 1 day). Zero timezone drift. */
function addOnePolicyYear(yyyyMmDd: string): string {
  const clean = (yyyyMmDd || "").split("T")[0];
  const parts = clean.split("-");
  if (parts.length !== 3) return clean;
  const y = parseInt(parts[0], 10);
  const m = parseInt(parts[1], 10);
  const d = parseInt(parts[2], 10);
  if (isNaN(y) || isNaN(m) || isNaN(d)) return clean;
  if (m === 2 && d === 29) {
    return `${y + 1}-02-28`;
  }
  const dt = new Date(Date.UTC(y + 1, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() - 1);
  return dt.toISOString().split("T")[0];
}

function todayLocalYyyyMmDd(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function useLedgerModals(state: ReturnType<typeof useLedgerState>) {
  const { toast } = useToast();
  // Drawer & Edit Modal State
  const [activeDrawerTenureId, setActiveDrawerTenureId] = useState<string | null>(null);
  const [editingTenure, setEditingTenure] = useState<TenureRow | null>(null);

  // Miss Outcome Modal State
  const [missModalTenure, setMissModalTenure] = useState<TenureRow | null>(null);
  const [keepClientChoice, setKeepClientChoice] = useState<"keep" | "discard">("keep");
  const [createNextYearDeal, setCreateNextYearDeal] = useState<boolean>(true);
  const [externalInsurer, setExternalInsurer] = useState<string>("");
  const [missReason, setMissReason] = useState<string>("");
  const [savingMissOutcome, setSavingMissOutcome] = useState<boolean>(false);

  // Issue Policy Confirmation Modal State
  const [issuePolicyModalTenure, setIssuePolicyModalTenure] = useState<TenureRow | null>(null);
  const [selectedWinnerQuote, setSelectedWinnerQuote] = useState<string>("");
  const [policyStartDate, setPolicyStartDate] = useState<string>("");
  const [savingIssuePolicy, setSavingIssuePolicy] = useState<boolean>(false);

  // Hit Confirmation Modal State
  const [hitConfirmTenure, setHitConfirmTenure] = useState<TenureRow | null>(null);
  const [hitConfirmedStartDate, setHitConfirmedStartDate] = useState<string>("");
  const [hitConfirmedEndDate, setHitConfirmedEndDate] = useState<string>("");
  const [hitConfirmedInsurer, setHitConfirmedInsurer] = useState<string>("");
  const [savingHitConfirm, setSavingHitConfirm] = useState<boolean>(false);

  // Delete Target Modal State
  const [deleteConfirmTarget, setDeleteConfirmTarget] = useState<{
    id: string;
    vehicleNo: string;
    allIds: string[];
  } | null>(null);
  const [deletingVehicle, setDeletingVehicle] = useState<boolean>(false);

  // Cover Note Upload Modal State
  const [covernoteUploadTenure, setCovernoteUploadTenure] = useState<TenureRow | null>(null);
  const [uploadingCovernote, setUploadingCovernote] = useState(false);

  // Add Custom Vehicle Modal State
  const [addVehicleModalOpen, setAddVehicleModalOpen] = useState(false);
  const [newVehPlate, setNewVehPlate] = useState("");
  const [newVehCustomerName, setNewVehCustomerName] = useState("");
  const [newVehIcNo, setNewVehIcNo] = useState("");
  const [newVehBrand, setNewVehBrand] = useState("Perodua");
  const [newVehCustomBrand, setNewVehCustomBrand] = useState("");
  const [newVehModel, setNewVehModel] = useState("");
  const [newVehYom, setNewVehYom] = useState(String(new Date().getFullYear()));
  const [newVehEngineCc, setNewVehEngineCc] = useState("1496 CC");
  const [newVehStartDate, setNewVehStartDate] = useState(() => todayLocalYyyyMmDd());
  const [newVehEndDate, setNewVehEndDate] = useState(() => addOnePolicyYear(todayLocalYyyyMmDd()));
  const [newVehWindscreen, setNewVehWindscreen] = useState("");
  const [savingNewVehicle, setSavingNewVehicle] = useState(false);

  const handleNewVehStartDateChange = (val: string) => {
    setNewVehStartDate(val);
    if (!val) return;
    setNewVehEndDate(addOnePolicyYear(val));
  };

  const handleNewVehEndDateChange = (val: string) => {
    setNewVehEndDate(val);
    if (!val) return;
    try {
      const parts = val.split("-");
      if (parts.length === 3) {
        const y = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10);
        const d = parseInt(parts[2], 10);
        if (!isNaN(y) && !isNaN(m) && !isNaN(d)) {
          const dt = new Date(Date.UTC(y - 1, m - 1, d));
          dt.setUTCDate(dt.getUTCDate() + 1);
          setNewVehStartDate(dt.toISOString().split("T")[0]);
        }
      }
    } catch { }
  };

  useEffect(() => {
    if (!addVehicleModalOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !savingNewVehicle) {
        setAddVehicleModalOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [addVehicleModalOpen, savingNewVehicle]);

  // Modal Action Handlers
  const handleConfirmMiss = async () => {
    if (!missModalTenure) return;
    setSavingMissOutcome(true);
    try {
      await api(`/tenures/${missModalTenure.id}/ledger-fields`, {
        method: "PATCH",
        body: JSON.stringify({
          stage: "Close - Lose",
          status: "miss",
          is_discarded: keepClientChoice === "discard",
          create_next_year_deal: keepClientChoice === "keep" ? createNextYearDeal : false,
          external_insurer: externalInsurer.trim() || undefined,
          miss_reason: missReason.trim() || undefined,
        }),
      });
      toast("Deal outcome saved.", "success");
      setMissModalTenure(null);
      state.loadTenures();
      state.loadStageSummary();
      state.loadMonths();
      state.loadYoyStats();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast("Failed to record miss outcome: " + msg, "error");
    } finally {
      setSavingMissOutcome(false);
    }
  };

  const handleConfirmIssuePolicy = async () => {
    if (!issuePolicyModalTenure) return;
    if (!policyStartDate) {
      toast("Please select an insurance start date.", "warning");
      return;
    }
    setSavingIssuePolicy(true);
    try {
      const startStr = policyStartDate.split("T")[0];
      const endStr = addOnePolicyYear(startStr);

      await state.patchTenureField(issuePolicyModalTenure.id, {
        stage: "Issue Policy",
        coverage_start_date: startStr,
        coverage_end_date: endStr,
      });

      toast("Policy period updated to Issue Policy.", "success");
      setIssuePolicyModalTenure(null);
      state.loadTenures();
      state.loadStageSummary();
      state.loadMonths();
      state.loadYoyStats();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast("Failed to confirm issue policy: " + msg, "error");
    } finally {
      setSavingIssuePolicy(false);
    }
  };

  const handleConfirmHit = async () => {
    if (!hitConfirmTenure) return;
    setSavingHitConfirm(true);
    try {
      const tenureId = hitConfirmTenure.id;
      await api(`/tenures/${tenureId}/ledger-fields`, {
        method: "PATCH",
        body: JSON.stringify({
          stage: "Close - Win",
          status: "hit",
          coverage_start_date: hitConfirmedStartDate ? hitConfirmedStartDate.split("T")[0] : undefined,
          coverage_end_date: hitConfirmedEndDate ? hitConfirmedEndDate.split("T")[0] : undefined,
          winning_company_name: hitConfirmedInsurer.trim() || undefined,
        }),
      });
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("rl_policy_issued", { detail: { tenureId } }));
      }
      toast("Deal confirmed as HIT! Next-year renewal updated.", "success");
      setHitConfirmTenure(null);
      state.loadTenures();
      state.loadStageSummary();
      state.loadMonths();
      state.loadYoyStats();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast("Failed to confirm hit: " + msg, "error");
    } finally {
      setSavingHitConfirm(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteConfirmTarget) return;
    setDeletingVehicle(true);
    try {
      await api("/tenures/bulk", {
        method: "DELETE",
        body: JSON.stringify({ tenure_ids: deleteConfirmTarget.allIds }),
      });
      toast("Moved deal to 30-day Trash.", "success");
      setDeleteConfirmTarget(null);
      state.loadTenures();
      state.loadStageSummary();
      state.loadMonths();
      state.loadYoyStats();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast("Failed to delete deal: " + msg, "error");
    } finally {
      setDeletingVehicle(false);
    }
  };

  const handleUploadCovernoteForTenure = async (file: File) => {
    if (!covernoteUploadTenure) return;
    setUploadingCovernote(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("document_type", "covernote");
      formData.append("tenure_id", covernoteUploadTenure.id);

      const idempotencyKey =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `cn-${Date.now()}-${Math.random().toString(36).slice(2)}`;

      const uploadRes = await api<{ session_id?: string; job_id?: string }>(
        "/uploads",
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey },
          body: formData,
        }
      );

      toast("Cover Note queued for extraction. Opening workspace...", "success");
      setCovernoteUploadTenure(null);
      state.loadTenures();
      state.loadStageSummary();
      state.loadMonths();
      state.loadYoyStats();

      if (uploadRes?.session_id) {
        window.open(`/sessions/${uploadRes.session_id}/review`, "_blank");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast("Cover Note upload failed: " + msg, "error");
    } finally {
      setUploadingCovernote(false);
    }
  };

  const handleCreateCustomVehicle = async (openComparison: boolean) => {
    const cleanPlate = newVehPlate.trim().toUpperCase().replace(/\s+/g, "");
    const cleanName = newVehCustomerName.trim();
    if (!cleanPlate) {
      toast("Please enter a vehicle registration number (e.g. WVV 1234 or JDR2263).", "warning");
      return;
    }
    if (!cleanName) {
      toast("Please enter the customer / policyholder name.", "warning");
      return;
    }

    setSavingNewVehicle(true);
    try {
      const finalBrand =
        newVehBrand === "Other" ? newVehCustomBrand.trim() : newVehBrand.trim();
      const payload: Record<string, unknown> = {
        vehicle_no: cleanPlate,
        customer_name: cleanName,
        ic_no: newVehIcNo.trim() || undefined,
        car_brand: finalBrand || undefined,
        car_model: newVehModel.trim() || undefined,
        manufacture_year: newVehYom ? parseInt(newVehYom, 10) : undefined,
        engine_cc: newVehEngineCc.trim() || undefined,
        coverage_start_date: newVehStartDate || undefined,
        coverage_end_date: newVehEndDate || undefined,
        windscreen_target: newVehWindscreen ? parseFloat(newVehWindscreen) : undefined,
      };

      const res = await api<{ id?: string; tenure?: { id: string } }>("/tenures", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      const createdId = res?.id || res?.tenure?.id;
      toast("Vehicle added to ledger.", "success");
      setAddVehicleModalOpen(false);
      state.loadTenures();
      state.loadMonths();
      state.loadStageSummary();
      state.loadYoyStats();

      if (openComparison && createdId) {
        window.open(`/comparison?tenure_id=${createdId}`, "_blank");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast("Failed to create vehicle: " + msg, "error");
    } finally {
      setSavingNewVehicle(false);
    }
  };

  const handleOpenHitModal = (tenure: TenureRow) => {
    setHitConfirmTenure(tenure);
    const winningQ = tenure.sourced_quotes?.find(
      (q) =>
        q.is_winner ||
        q.company === tenure.winning_company_name ||
        q.company === tenure.winning_company_id
    );
    const startCandidate = (
      tenure.covernote_policy?.coverage_start_date ||
      winningQ?.coverage_start_date ||
      tenure.coverage_start_date ||
      todayLocalYyyyMmDd()
    ).split("T")[0];
    setHitConfirmedStartDate(startCandidate);
    const endCandidate =
      tenure.covernote_policy?.coverage_end_date ||
      winningQ?.coverage_end_date ||
      tenure.coverage_end_date;
    if (endCandidate) {
      setHitConfirmedEndDate(endCandidate.split("T")[0]);
    } else {
      setHitConfirmedEndDate(addOnePolicyYear(startCandidate));
    }
    setHitConfirmedInsurer(
      tenure.covernote_policy?.company ||
      tenure.winning_company_name ||
      tenure.winning_company_id ||
      winningQ?.company ||
      tenure.sourced_quotes?.[0]?.company ||
      ""
    );
  };

  const handleOpenMissModal = (tenure: TenureRow) => {
    setMissModalTenure(tenure);
    setKeepClientChoice("keep");
    setCreateNextYearDeal(true);
    setExternalInsurer("");
    setMissReason("");
  };

  return {
    activeDrawerTenureId,
    setActiveDrawerTenureId,
    editingTenure,
    setEditingTenure,

    missModalTenure,
    setMissModalTenure,
    keepClientChoice,
    setKeepClientChoice,
    createNextYearDeal,
    setCreateNextYearDeal,
    externalInsurer,
    setExternalInsurer,
    missReason,
    setMissReason,
    savingMissOutcome,
    handleConfirmMiss,
    handleOpenMissModal,

    issuePolicyModalTenure,
    setIssuePolicyModalTenure,
    selectedWinnerQuote,
    setSelectedWinnerQuote,
    policyStartDate,
    setPolicyStartDate,
    savingIssuePolicy,
    handleConfirmIssuePolicy,

    hitConfirmTenure,
    setHitConfirmTenure,
    hitConfirmedStartDate,
    setHitConfirmedStartDate,
    hitConfirmedEndDate,
    setHitConfirmedEndDate,
    hitConfirmedInsurer,
    setHitConfirmedInsurer,
    savingHitConfirm,
    handleConfirmHit,
    handleOpenHitModal,

    deleteConfirmTarget,
    setDeleteConfirmTarget,
    deletingVehicle,
    handleConfirmDelete,

    covernoteUploadTenure,
    setCovernoteUploadTenure,
    uploadingCovernote,
    handleUploadCovernoteForTenure,

    addVehicleModalOpen,
    setAddVehicleModalOpen,
    newVehPlate,
    setNewVehPlate,
    newVehCustomerName,
    setNewVehCustomerName,
    newVehIcNo,
    setNewVehIcNo,
    newVehBrand,
    setNewVehBrand,
    newVehCustomBrand,
    setNewVehCustomBrand,
    newVehModel,
    setNewVehModel,
    newVehYom,
    setNewVehYom,
    newVehEngineCc,
    setNewVehEngineCc,
    newVehStartDate,
    handleNewVehStartDateChange,
    newVehEndDate,
    handleNewVehEndDateChange,
    newVehWindscreen,
    setNewVehWindscreen,
    savingNewVehicle,
    handleCreateCustomVehicle,
  };
}
