"use client";

import React from "react";
import { TenureTimelineDrawer } from "@/components/tenures/tenure-timeline-drawer";
import { EditVehicleDealModal } from "@/components/tenures/edit-vehicle-deal-modal";
import type { useLedgerState } from "./useLedgerState";
import type { useLedgerModals } from "./useLedgerModals";

// Re-export modular modal components for backward compatibility
export { MissModal, type MissModalProps } from "./modals/RecordMissModal";
export { IssuePolicyModal, type IssuePolicyModalProps } from "./modals/IssuePolicyModal";
export { HitConfirmModal, type HitConfirmModalProps } from "./modals/ConfirmHitModal";
export { DeleteConfirmModal, type DeleteConfirmModalProps } from "./modals/DeleteConfirmModal";
export { CoverNoteUploadModal, type CoverNoteUploadModalProps } from "./modals/UploadCoverNoteModal";
export { AddCustomVehicleModal, type AddCustomVehicleModalProps } from "./modals/NewVehicleModal";

import { MissModal } from "./modals/RecordMissModal";
import { IssuePolicyModal } from "./modals/IssuePolicyModal";
import { HitConfirmModal } from "./modals/ConfirmHitModal";
import { DeleteConfirmModal } from "./modals/DeleteConfirmModal";
import { CoverNoteUploadModal } from "./modals/UploadCoverNoteModal";
import { AddCustomVehicleModal } from "./modals/NewVehicleModal";

// =========================================================================
// COMPOSITE MODALS CONTAINER (<150 Lines)
// =========================================================================

export interface LedgerModalsContainerProps {
  modals: ReturnType<typeof useLedgerModals>;
  state: ReturnType<typeof useLedgerState>;
}

export function LedgerModalsContainer({ modals, state }: LedgerModalsContainerProps) {
  return (
    <>
      {modals.activeDrawerTenureId && (
        <TenureTimelineDrawer
          tenureId={modals.activeDrawerTenureId}
          isOpen={Boolean(modals.activeDrawerTenureId)}
          onClose={() => modals.setActiveDrawerTenureId(null)}
          onUpdate={async () => {
            state.loadTenures();
            state.loadStageSummary();
            state.loadMonths();
            state.loadYoyStats();
          }}
        />
      )}

      {modals.editingTenure && (
        <EditVehicleDealModal
          isOpen={Boolean(modals.editingTenure)}
          onClose={() => modals.setEditingTenure(null)}
          tenure={modals.editingTenure}
          pics={state.pics}
          onSave={async (id, updates) => {
            await state.patchTenureField(id, updates);
            state.loadTenures();
            modals.setEditingTenure(null);
          }}
        />
      )}

      <MissModal
        tenure={modals.missModalTenure}
        keepClientChoice={modals.keepClientChoice}
        setKeepClientChoice={modals.setKeepClientChoice}
        createNextYearDeal={modals.createNextYearDeal}
        setCreateNextYearDeal={modals.setCreateNextYearDeal}
        externalInsurer={modals.externalInsurer}
        setExternalInsurer={modals.setExternalInsurer}
        missReason={modals.missReason}
        setMissReason={modals.setMissReason}
        savingMissOutcome={modals.savingMissOutcome}
        onConfirmMiss={modals.handleConfirmMiss}
        onClose={() => modals.setMissModalTenure(null)}
      />

      <IssuePolicyModal
        tenure={modals.issuePolicyModalTenure}
        selectedWinnerQuote={modals.selectedWinnerQuote}
        setSelectedWinnerQuote={modals.setSelectedWinnerQuote}
        policyStartDate={modals.policyStartDate}
        setPolicyStartDate={modals.setPolicyStartDate}
        savingIssuePolicy={modals.savingIssuePolicy}
        onConfirmIssuePolicy={modals.handleConfirmIssuePolicy}
        onClose={() => modals.setIssuePolicyModalTenure(null)}
      />

      <HitConfirmModal
        tenure={modals.hitConfirmTenure}
        hitConfirmedInsurer={modals.hitConfirmedInsurer}
        setHitConfirmedInsurer={modals.setHitConfirmedInsurer}
        hitConfirmedStartDate={modals.hitConfirmedStartDate}
        setHitConfirmedStartDate={modals.setHitConfirmedStartDate}
        hitConfirmedEndDate={modals.hitConfirmedEndDate}
        setHitConfirmedEndDate={modals.setHitConfirmedEndDate}
        savingHitConfirm={modals.savingHitConfirm}
        onConfirmHit={modals.handleConfirmHit}
        onClose={() => modals.setHitConfirmTenure(null)}
      />

      <DeleteConfirmModal
        target={modals.deleteConfirmTarget}
        deletingVehicle={modals.deletingVehicle}
        onConfirmDelete={modals.handleConfirmDelete}
        onClose={() => modals.setDeleteConfirmTarget(null)}
      />

      <CoverNoteUploadModal
        tenure={modals.covernoteUploadTenure}
        uploadingCovernote={modals.uploadingCovernote}
        onUploadCovernote={modals.handleUploadCovernoteForTenure}
        onClose={() => modals.setCovernoteUploadTenure(null)}
      />

      <AddCustomVehicleModal
        isOpen={modals.addVehicleModalOpen}
        onClose={() => modals.setAddVehicleModalOpen(false)}
        newVehPlate={modals.newVehPlate}
        setNewVehPlate={modals.setNewVehPlate}
        newVehCustomerName={modals.newVehCustomerName}
        setNewVehCustomerName={modals.setNewVehCustomerName}
        newVehIcNo={modals.newVehIcNo}
        setNewVehIcNo={modals.setNewVehIcNo}
        newVehBrand={modals.newVehBrand}
        setNewVehBrand={modals.setNewVehBrand}
        newVehCustomBrand={modals.newVehCustomBrand}
        setNewVehCustomBrand={modals.setNewVehCustomBrand}
        newVehModel={modals.newVehModel}
        setNewVehModel={modals.setNewVehModel}
        newVehYom={modals.newVehYom}
        setNewVehYom={modals.setNewVehYom}
        newVehEngineCc={modals.newVehEngineCc}
        setNewVehEngineCc={modals.setNewVehEngineCc}
        newVehStartDate={modals.newVehStartDate}
        onStartDateChange={modals.handleNewVehStartDateChange}
        newVehEndDate={modals.newVehEndDate}
        onEndDateChange={modals.handleNewVehEndDateChange}
        newVehWindscreen={modals.newVehWindscreen}
        setNewVehWindscreen={modals.setNewVehWindscreen}
        savingNewVehicle={modals.savingNewVehicle}
        onCreateVehicle={modals.handleCreateCustomVehicle}
      />
    </>
  );
}
