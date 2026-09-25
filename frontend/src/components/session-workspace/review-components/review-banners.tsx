"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CheckCircle, Lock, UserSwitch } from "@phosphor-icons/react";
import type { WorkspaceSnapshot } from "../types";

export interface ReviewBannersProps {
  ownershipConflict: any;
  setConflictModalOpen: (open: boolean) => void;
  formValues: Record<string, string>;
  workspace: WorkspaceSnapshot;
  learnPrompt: { field: string; value: string } | null;
  learnValue: () => void;
  setLearnPrompt: (val: null) => void;
}

export function ReviewBanners({
  ownershipConflict,
  setConflictModalOpen,
  formValues,
  workspace,
  learnPrompt,
  learnValue,
  setLearnPrompt,
}: ReviewBannersProps) {
  return (
    <>
      {/* Vehicle Ownership Conflict Gate Banner */}
      {ownershipConflict?.has_conflict && !ownershipConflict?.resolved ? (
        <div
          role="alert"
          className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-4 bg-amber-50 border-2 border-amber-400 rounded-[var(--rl-radius-md)] text-amber-950 shadow-sm"
        >
          <div className="flex items-start gap-3.5">
            <div className="w-9 h-9 rounded-full bg-amber-200 text-amber-900 flex items-center justify-center shrink-0 mt-0.5">
              <Lock size={18} weight="bold" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-bold text-amber-950 text-sm">
                  Action Required: Vehicle Ownership Conflict Gate
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-200 text-amber-900 px-2 py-0.5 rounded">
                  PDF Export Locked
                </span>
              </div>
              <p className="text-xs text-amber-900/90 leading-relaxed">
                Vehicle <span className="font-mono font-bold bg-white/80 px-1.5 py-0.5 rounded border border-amber-200">{ownershipConflict.vehicle_no || formValues.vehicle_no}</span>
                {ownershipConflict.car_model ? ` (${ownershipConflict.car_model})` : ""} was previously registered to{" "}
                <span className="font-bold text-amber-950">{ownershipConflict.previous_owner}</span> (Inception: {ownershipConflict.previous_date || "Past Policy"}).{" "}
                This quotation is issued for <span className="font-bold text-amber-950">{ownershipConflict.current_owner || formValues.customer_name}</span>. Please verify ownership before issuing.
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={() => setConflictModalOpen(true)}
            className="bg-amber-800 hover:bg-amber-900 text-white shrink-0 font-semibold text-xs shadow-xs"
          >
            Resolve Ownership Conflict
          </Button>
        </div>
      ) : null}

      {/* Vehicle Ownership Resolution Confirmation Banner */}
      {ownershipConflict?.resolved && ownershipConflict.resolution ? (
        <div
          role="status"
          className="flex items-center justify-between gap-3 px-3.5 py-2.5 bg-emerald-50 border border-emerald-300 rounded-[var(--rl-radius-sm)] text-xs text-emerald-950"
        >
          <div className="flex items-center gap-2.5">
            <CheckCircle size={16} weight="fill" className="text-emerald-600 shrink-0" />
            <span>
              Ownership verified:{" "}
              <strong>
                {ownershipConflict.resolution.type === "car_sold_new_owner"
                  ? "Car Sold / Ownership Transferred"
                  : ownershipConflict.resolution.type === "old_quote_mistake"
                  ? "Corrected (Old Quote Was Mistake)"
                  : "Pending Geran Verification"}
              </strong>{" "}
              ({ownershipConflict.resolution.new_customer || formValues.customer_name})
            </span>
          </div>
          <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-100/80 px-2 py-0.5 rounded">
            PDF Unlocked
          </span>
        </div>
      ) : null}

      {/* Sequential Owner Transfer Alert Banner */}
      {workspace?.display_options && (workspace.display_options as Record<string, any>).owner_change_alert ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 p-3.5 bg-amber-50/90 border border-amber-200 rounded-[var(--rl-radius-sm)]"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-amber-100 flex items-center justify-center text-amber-800 shrink-0">
              <UserSwitch size={18} weight="bold" />
            </div>
            <div className="text-sm">
              <span className="font-semibold text-amber-900">Owner Changed: </span>
              {String((workspace.display_options as Record<string, any>).owner_change_alert.message || "Ownership discrepancy noted.")}
            </div>
          </div>
          <span className="text-xs bg-amber-200/70 text-amber-900 font-semibold px-2.5 py-1 rounded">
            Ownership Updated
          </span>
        </div>
      ) : null}

      {learnPrompt ? (
        <Card role="status" className="flex flex-wrap items-center justify-between gap-3 border-amber-500/30 bg-amber-500/10 p-3">
          <p className="text-sm font-semibold text-[var(--rl-text-strong)]">
            Save &quot;{learnPrompt.value}&quot; to the {learnPrompt.field === "car_brand" ? "vehicle brand list" : "database"} for future quotes?
          </p>
          <div className="flex gap-2">
            <Button size="sm" onClick={learnValue}>Yes, add it</Button>
            <Button variant="secondary" size="sm" onClick={() => setLearnPrompt(null)}>No</Button>
          </div>
        </Card>
      ) : null}
    </>
  );
}
