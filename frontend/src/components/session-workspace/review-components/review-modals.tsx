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

    </>
  );
}
