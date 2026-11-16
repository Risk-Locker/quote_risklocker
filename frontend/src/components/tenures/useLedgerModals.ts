"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import type { TenureRow } from "./types";
import type { useLedgerState } from "./useLedgerState";

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
  const [newVehStartDate, setNewVehStartDate] = useState(new Date().toISOString().split("T")[0]);
  const [newVehEndDate, setNewVehEndDate] = useState(() => {
    const d = new Date();
    d.setFullYear(d.getFullYear() + 1);
    d.setDate(d.getDate() - 1);
    return d.toISOString().split("T")[0];
  });
  const [newVehWindscreen, setNewVehWindscreen] = useState("");
  const [savingNewVehicle, setSavingNewVehicle] = useState(false);

  const handleNewVehStartDateChange = (val: string) => {
    setNewVehStartDate(val);
    if (!val) return;
    try {
      const parts = val.split("-");
      if (parts.length === 3) {
        const y = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10);
        const d = parseInt(parts[2], 10);
        if (!isNaN(y) && !isNaN(m) && !isNaN(d)) {
          const dt = new Date(Date.UTC(y + 1, m - 1, d));
          dt.setUTCDate(dt.getUTCDate() - 1);
          setNewVehEndDate(dt.toISOString().split("T")[0]);
        }
      }
    } catch { }
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
      await api(`/tenures/${missModalTenure.id}/miss-outcome`, {
        method: "POST",
        body: JSON.stringify({
          keep_client: keepClientChoice === "keep",
          create_next_year_deal: keepClientChoice === "keep" ? createNextYearDeal : false,
          external_insurer: externalInsurer.trim() || undefined,
          miss_reason: missReason.trim() || undefined,
        }),
      });
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
      const startDt = new Date(policyStartDate);
      const endDt = new Date(startDt);
      endDt.setFullYear(endDt.getFullYear() + 1);
      endDt.setDate(endDt.getDate() - 1);
      const startStr = startDt.toISOString().split("T")[0];
      const endStr = endDt.toISOString().split("T")[0];

      await state.patchTenureField(issuePolicyModalTenure.id, {
        stage: "Issue Policy",
        coverage_start_date: startStr,
        coverage_end_date: endStr,
      });

      setIssuePolicyModalTenure(null);
      state.loadTenures();
      state.loadStageSummary();
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
      await api(`/tenures/${hitConfirmTenure.id}/confirm-hit`, {
        method: "POST",
        body: JSON.stringify({
          coverage_start_date: hitConfirmedStartDate,
          coverage_end_date: hitConfirmedEndDate,
          confirmed_company: hitConfirmedInsurer,
        }),
      });
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
      formData.append("tenure_id", covernoteUploadTenure.id);

      const uploadRes = await api<{ session_id?: string; tenure_id?: string }>(
        "/upload?mode=covernote",
        {
          method: "POST",
          body: formData,
        }
      );

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
        brand: finalBrand || undefined,
        model: newVehModel.trim() || undefined,
        manufacture_year: newVehYom ? parseInt(newVehYom, 10) : undefined,
        engine_cc: newVehEngineCc.trim() || undefined,
        coverage_start_date: newVehStartDate || undefined,
        coverage_end_date: newVehEndDate || undefined,
        target_windscreen: newVehWindscreen ? parseFloat(newVehWindscreen) : undefined,
      };

      const res = await api<{ tenure_id: string }>("/tenures/custom", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setAddVehicleModalOpen(false);
      state.loadTenures();
      state.loadMonths();
      state.loadStageSummary();
      state.loadYoyStats();

      if (openComparison && res?.tenure_id) {
        window.open(`/comparison?tenure_id=${res.tenure_id}`, "_blank");
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
    const startCandidate =
      tenure.covernote_policy?.coverage_start_date ||
      winningQ?.coverage_start_date ||
      tenure.coverage_start_date ||
      new Date().toISOString().split("T")[0];
    setHitConfirmedStartDate(startCandidate);
    if (
      tenure.covernote_policy?.coverage_end_date ||
      winningQ?.coverage_end_date ||
      tenure.coverage_end_date
    ) {
      setHitConfirmedEndDate(
        tenure.covernote_policy?.coverage_end_date ||
        winningQ?.coverage_end_date ||
        tenure.coverage_end_date
      );
    } else {
      const endD = new Date(startCandidate);
      endD.setDate(endD.getDate() + 364);
      setHitConfirmedEndDate(endD.toISOString().split("T")[0]);
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
