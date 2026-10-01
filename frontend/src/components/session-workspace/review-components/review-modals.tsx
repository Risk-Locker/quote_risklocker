"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SendToClientDialog } from "@/components/insights/send-to-client-dialog";
import {
  CheckCircle,
  MagnifyingGlass,
  Sparkle,
  UserSwitch,
  X,
} from "@phosphor-icons/react";

export interface ReviewModalsProps {
  showGlobalModal: boolean;
  setShowGlobalModal: (val: boolean) => void;
  modalTarget: "current" | "available_addon";
  globalSearch: string;
  setGlobalSearch: (val: string) => void;
  modalFilter: "all" | "insurer" | "global" | "addons";
  setModalFilter: (val: "all" | "insurer" | "global" | "addons") => void;
  companyName: string | null | undefined;
  globalConcepts: any[];
  isExcludedForVehicle: (c: any) => boolean;
  insurerConceptKeys: Set<string>;
  GLOBAL_BENEFIT_KEYS: Set<string>;
  filteredConcepts: any[];
  fileUrl: (path?: string | null) => string;
  addConceptAsBenefit: (concept: any, target: "current" | "available_addon") => void;
  conflictModalOpen: boolean;
  setConflictModalOpen: (val: boolean) => void;
  ownershipConflict: any;
  selectedResolution: "car_sold_new_owner" | "old_quote_mistake" | "pending_verification";
  setSelectedResolution: (val: "car_sold_new_owner" | "old_quote_mistake" | "pending_verification") => void;
  resolutionNotes: string;
  setResolutionNotes: (val: string) => void;
  resolvingConflict: boolean;
  handleResolveConflict: () => void;
  toastMessage: string | null;
  pendingExportAction: "download_pdf" | "copy_png" | "download_png" | null;
  setPendingExportAction: (val: "download_pdf" | "copy_png" | "download_png" | null) => void;
  confirmAndExecuteExport: (isSentToClient: boolean) => void;
}

export function ReviewModals({
  showGlobalModal,
  setShowGlobalModal,
  modalTarget,
  globalSearch,
  setGlobalSearch,
  modalFilter,
  setModalFilter,
  companyName,
  globalConcepts,
  isExcludedForVehicle,
  insurerConceptKeys,
  GLOBAL_BENEFIT_KEYS,
  filteredConcepts,
  fileUrl,
  addConceptAsBenefit,
  conflictModalOpen,
  setConflictModalOpen,
  ownershipConflict,
  selectedResolution,
  setSelectedResolution,
  resolutionNotes,
  setResolutionNotes,
  resolvingConflict,
  handleResolveConflict,
  toastMessage,
  pendingExportAction,
  setPendingExportAction,
  confirmAndExecuteExport,
}: ReviewModalsProps) {
  return (
    <>
      {/* 1. Global Benefit Library Modal */}
      {showGlobalModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in">
          <Card className="flex flex-col max-h-[85vh] w-full max-w-3xl border border-[var(--rl-border)] bg-white shadow-xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-[var(--rl-border)] p-4">
              <div>
                <h3 className="text-base font-bold text-[var(--rl-text-strong)]">
                  Global Benefits &amp; Add-ons Library
                </h3>
                <p className="text-xs text-[var(--rl-text-muted)]">
                  Currently adding to:{" "}
                  <strong className="text-[var(--rl-text-strong)]">
                    {modalTarget === "current" ? "Default / FOC Benefits" : "Optional Add-ons"}
                  </strong>
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowGlobalModal(false)}
                className="rounded-full p-1 text-[var(--rl-text-muted)] hover:bg-gray-100 cursor-pointer"
              >
                <X size={18} weight="bold" />
              </button>
            </div>

            {/* Modal Controls: Search & Category Filter */}
            <div className="p-4 border-b border-[var(--rl-border)] bg-gray-50/50 flex flex-wrap items-center justify-between gap-3">
              <div className="relative flex-1 min-w-[220px]">
                <MagnifyingGlass
                  size={16}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]"
                />
                <Input
                  value={globalSearch}
                  placeholder="Search benefits (Towing, Windscreen, Flood, CART)..."
                  className="pl-9 text-xs"
                  onChange={(e) => setGlobalSearch(e.target.value)}
                  autoFocus
                />
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setModalFilter("insurer")}
                  className={`rounded-md px-2.5 py-1 text-xs font-bold transition-all cursor-pointer ${
                    modalFilter === "insurer"
                      ? "bg-[var(--rl-black)] text-white"
                      : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  🏢 {companyName ? `${companyName}` : "This Insurer"} (
                  {
                    globalConcepts.filter(
                      (c) =>
                        !isExcludedForVehicle(c) &&
                        (insurerConceptKeys.has(c.concept_key) || insurerConceptKeys.has(c.id))
                    ).length
                  }
                  )
                </button>
                <button
                  type="button"
                  onClick={() => setModalFilter("all")}
                  className={`rounded-md px-2.5 py-1 text-xs font-bold transition-all cursor-pointer ${
                    modalFilter === "all"
                      ? "bg-[var(--rl-black)] text-white"
                      : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  All ({globalConcepts.filter((c) => !isExcludedForVehicle(c)).length})
                </button>
                <button
                  type="button"
                  onClick={() => setModalFilter("global")}
                  className={`rounded-md px-2.5 py-1 text-xs font-bold transition-all cursor-pointer ${
                    modalFilter === "global"
                      ? "bg-[var(--rl-black)] text-white"
                      : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  Table 1: Global (
                  {
                    globalConcepts.filter(
                      (c) => !isExcludedForVehicle(c) && GLOBAL_BENEFIT_KEYS.has(c.concept_key)
                    ).length
                  }
                  )
                </button>
                <button
                  type="button"
                  onClick={() => setModalFilter("addons")}
                  className={`rounded-md px-2.5 py-1 text-xs font-bold transition-all cursor-pointer ${
                    modalFilter === "addons"
                      ? "bg-[var(--rl-black)] text-white"
                      : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  Table 2: Add-ons (
                  {
                    globalConcepts.filter(
                      (c) => !isExcludedForVehicle(c) && !GLOBAL_BENEFIT_KEYS.has(c.concept_key)
                    ).length
                  }
                  )
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 grid gap-2 sm:grid-cols-2">
              {filteredConcepts.map((concept) => (
                <div
                  key={concept.id}
                  className="group flex items-center justify-between gap-2.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-2.5 transition-all hover:border-[var(--rl-border-strong)] hover:bg-gray-50/70"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-md border border-[var(--rl-border)] bg-white p-1">
                      {concept.default_asset?.url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={fileUrl(concept.default_asset.url)}
                          alt={concept.label}
                          className="h-full w-full object-contain"
                        />
                      ) : (
                        <Sparkle size={18} className="text-[var(--rl-text-muted)]" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <h4 className="truncate text-xs font-bold text-[var(--rl-text-strong)]">
                        {concept.label}
                      </h4>
                      <p className="truncate text-[10px] text-[var(--rl-text-muted)] font-mono">
                        {concept.concept_key}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => addConceptAsBenefit(concept, "current")}
                      className="text-[10px] h-7 px-2 cursor-pointer"
                      title="Add to Default / FOC Benefits"
                    >
                      + Default
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => addConceptAsBenefit(concept, "available_addon")}
                      className="text-[10px] h-7 px-2 cursor-pointer"
                      title="Add to Optional Add-ons"
                    >
                      + Add-on
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end border-t border-[var(--rl-border)] p-3 bg-gray-50">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowGlobalModal(false)}
                className="cursor-pointer"
              >
                Close
              </Button>
            </div>
          </Card>
        </div>
      ) : null}

      {/* 2. Vehicle Ownership Conflict Resolution Modal */}
      {conflictModalOpen && ownershipConflict && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in">
          <Card className="w-full max-w-xl bg-white shadow-2xl rounded-[var(--rl-radius-lg)] border border-[var(--rl-border)] overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-5 border-b border-[var(--rl-border)] bg-[var(--rl-surface-muted)] flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-amber-100 text-amber-800 flex items-center justify-center shrink-0">
                  <UserSwitch size={18} weight="bold" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-[var(--rl-text-strong)]">
                    Vehicle Ownership Conflict Gate
                  </h3>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Vehicle {ownershipConflict.vehicle_no} matches an existing vehicle with a different owner.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setConflictModalOpen(false)}
                className="text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] p-1.5 rounded cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4">
              {/* Conflict Comparison Box */}
              <div className="grid grid-cols-2 gap-3 p-3.5 rounded-[var(--rl-radius-sm)] bg-[var(--rl-surface-muted)] border border-[var(--rl-border)] text-xs">
                <div className="space-y-1">
                  <span className="text-[10px] uppercase font-bold text-[var(--rl-text-muted)] tracking-wider">
                    Existing Record
                  </span>
                  <p className="font-bold text-[var(--rl-text-strong)] text-sm truncate">
                    {ownershipConflict.previous_owner}
                  </p>
                  <p className="text-[11px] text-[var(--rl-text-muted)]">
                    Inception: {ownershipConflict.previous_policy_date}
                  </p>
                  {ownershipConflict.previous_session_ref && (
                    <span className="inline-block text-[10px] font-mono text-[var(--rl-text-muted)] bg-white px-1.5 py-0.5 rounded border border-[var(--rl-border)]">
                      {ownershipConflict.previous_session_ref}
                    </span>
                  )}
                </div>

                <div className="space-y-1 border-l border-[var(--rl-border)] pl-3">
                  <span className="text-[10px] uppercase font-bold text-amber-600 tracking-wider">
                    Incoming New Quote
                  </span>
                  <p className="font-bold text-[var(--rl-text-strong)] text-sm truncate">
                    {ownershipConflict.new_customer}
                  </p>
                  <p className="text-[11px] text-[var(--rl-text-muted)]">
                    Registration: {ownershipConflict.vehicle_no}
                  </p>
                  <span className="inline-block text-[10px] font-bold text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                    Conflict Detected
                  </span>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-[var(--rl-text-strong)]">
                  Select Resolution Action
                </label>
                <p className="text-[11px] text-[var(--rl-text-muted)]">
                  Please specify how RiskLocker should manage this vehicle record:
                </p>
              </div>

              {/* 3 Resolution Options */}
              <div className="space-y-2.5">
                <label
                  onClick={() => setSelectedResolution("car_sold_new_owner")}
                  className={`block p-3 rounded-[var(--rl-radius-sm)] border text-xs cursor-pointer transition-all ${
                    selectedResolution === "car_sold_new_owner"
                      ? "border-[var(--rl-black)] bg-neutral-50 shadow-2xs"
                      : "border-[var(--rl-border)] hover:bg-neutral-50/60"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="radio"
                      name="ownership_resolution"
                      checked={selectedResolution === "car_sold_new_owner"}
                      onChange={() => setSelectedResolution("car_sold_new_owner")}
                      className="mt-0.5 text-[var(--rl-black)] focus:ring-0 cursor-pointer"
                    />
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-[var(--rl-text-strong)]">
                          Car Sold / New Owner (Transfer)
                        </span>
                        <Badge variant="success" className="text-[10px] py-0 px-1.5">
                          Recommended
                        </Badge>
                      </div>
                      <p className="text-[11px] text-[var(--rl-text-muted)] leading-relaxed">
                        The vehicle was legitimately transferred or sold. Set{" "}
                        <strong>{ownershipConflict.new_customer}</strong> as the current owner and
                        archive <strong>{ownershipConflict.previous_owner}</strong> in vehicle
                        history.
                      </p>
                    </div>
                  </div>
                </label>

                <label
                  onClick={() => setSelectedResolution("old_quote_mistake")}
                  className={`block p-3 rounded-[var(--rl-radius-sm)] border text-xs cursor-pointer transition-all ${
                    selectedResolution === "old_quote_mistake"
                      ? "border-[var(--rl-black)] bg-neutral-50 shadow-2xs"
                      : "border-[var(--rl-border)] hover:bg-neutral-50/60"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="radio"
                      name="ownership_resolution"
                      checked={selectedResolution === "old_quote_mistake"}
                      onChange={() => setSelectedResolution("old_quote_mistake")}
                      className="mt-0.5 text-[var(--rl-black)] focus:ring-0 cursor-pointer"
                    />
                    <div className="space-y-0.5">
                      <span className="font-bold text-[var(--rl-text-strong)]">
                        Data Correction (Old Quote Was Mistake)
                      </span>
                      <p className="text-[11px] text-[var(--rl-text-muted)] leading-relaxed">
                        The previous quote under <strong>{ownershipConflict.previous_owner}</strong>{" "}
                        was entered with an erroneous plate or typo. Establish{" "}
                        <strong>{ownershipConflict.new_customer}</strong> as the sole owner and
                        detach old record.
                      </p>
                    </div>
                  </div>
                </label>

                <label
                  onClick={() => setSelectedResolution("pending_verification")}
                  className={`block p-3 rounded-[var(--rl-radius-sm)] border text-xs cursor-pointer transition-all ${
                    selectedResolution === "pending_verification"
                      ? "border-[var(--rl-black)] bg-neutral-50 shadow-2xs"
                      : "border-[var(--rl-border)] hover:bg-neutral-50/60"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="radio"
                      name="ownership_resolution"
                      checked={selectedResolution === "pending_verification"}
                      onChange={() => setSelectedResolution("pending_verification")}
                      className="mt-0.5 text-[var(--rl-black)] focus:ring-0 cursor-pointer"
                    />
                    <div className="space-y-0.5">
                      <span className="font-bold text-[var(--rl-text-strong)]">
                        Keep on Pending (Geran Verification Required)
                      </span>
                      <p className="text-[11px] text-[var(--rl-text-muted)] leading-relaxed">
                        Unlock PDF export immediately for the client, but keep ownership record
                        unverified pending vehicle registration grant (geran) review.
                      </p>
                    </div>
                  </div>
                </label>
              </div>

              {/* Notes Input */}
              <div className="space-y-1 pt-1">
                <label className="text-[11px] font-semibold text-[var(--rl-text-muted)]">
                  Resolution Notes (Optional)
                </label>
                <Input
                  type="text"
                  placeholder="e.g. Geran verified on 21 Sep; ownership changed in JPJ"
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  className="text-xs h-8"
                />
              </div>
            </div>

            <div className="p-4 border-t border-[var(--rl-border)] bg-[var(--rl-surface-muted)] flex items-center justify-end gap-2 shrink-0">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setConflictModalOpen(false)}
                disabled={resolvingConflict}
                className="cursor-pointer"
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleResolveConflict}
                disabled={resolvingConflict}
                className="bg-[var(--rl-black)] hover:bg-neutral-800 text-white font-semibold cursor-pointer"
              >
                {resolvingConflict ? "Resolving..." : "Confirm & Unlock PDF Export"}
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* 3. Floating Action Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 rounded-[var(--rl-radius-sm)] border border-neutral-800 bg-neutral-900/95 px-4 py-3 text-xs font-semibold text-white shadow-2xl backdrop-blur-md transition-all">
          <CheckCircle size={16} weight="fill" className="text-emerald-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* 4. Outbound Quotation Export Prompt (Sent to Client vs Internal Save) */}
      <SendToClientDialog
        open={pendingExportAction !== null}
        onClose={() => setPendingExportAction(null)}
        onConfirm={confirmAndExecuteExport}
        actionTitle={
          pendingExportAction === "download_pdf"
            ? "Download Quotation PDF"
            : pendingExportAction === "copy_png"
            ? "Copy Quotation as PNG"
            : "Download Quotation PNG"
        }
      />
    </>
  );
}
