"use client";

import React, { useState } from "react";
import { CheckCircle, Trash, DownloadSimple } from "@phosphor-icons/react";
import type { TenureRow } from "./types";
import { formatDateSafe } from "./types";
import { formatBrandAndModel } from "@/lib/vehicle-utils";

export interface TenureBulkActionsProps {
  selectedTenureIds: string[];
  tenures: TenureRow[];
  onBulkConfirmHit: () => Promise<void>;
  onBulkDelete: () => Promise<void>;
  onClearSelection: () => void;
  confirmingBulk?: boolean;
  deletingBulk?: boolean;
}

export function TenureBulkActions({
  selectedTenureIds,
  tenures,
  onBulkConfirmHit,
  onBulkDelete,
  onClearSelection,
  confirmingBulk = false,
  deletingBulk = false,
}: TenureBulkActionsProps) {
  const [exporting, setExporting] = useState(false);

  if (selectedTenureIds.length === 0) {
    return null;
  }

  const handleExportCSV = () => {
    try {
      setExporting(true);
      const targetTenures =
        selectedTenureIds.length > 0
          ? tenures.filter((t) => selectedTenureIds.includes(t.id))
          : tenures;

      const headers = [
        "Vehicle No",
        "Customer Name",
        "IC / Passport",
        "Make & Model",
        "Coverage Start",
        "Coverage End",
        "Stage",
        "Status",
        "Winning Insurer",
        "Won Premium (RM)",
        "Road Tax (RM)",
        "Runner Fee (RM)",
        "PIC / Agent",
        "Policy Number",
      ];

      const escapeCsv = (val: unknown) => {
        if (val === null || val === undefined) return '""';
        const str = String(val).replace(/"/g, '""');
        return `"${str}"`;
      };

      const rows = targetTenures.map((t) => {
        const vehicleDisplay = t.vehicle_no || t.chassis_no || t.engine_no || "—";
        const brandModel = formatBrandAndModel(t.car_brand, t.car_model) || "—";
        const policyNo = t.policy_number || t.covernote_policy?.policy_number || "—";
        const winningInsurer =
          t.winning_company_name || t.covernote_policy?.company || "—";
        const wonPrem = t.won_premium != null ? t.won_premium.toFixed(2) : "—";
        const roadTax = t.road_tax != null ? t.road_tax.toFixed(2) : "0.00";
        const runnerFee = t.runner_fee != null ? t.runner_fee.toFixed(2) : "0.00";
        const pic = t.sub_agent_name || "—";

        return [
          escapeCsv(vehicleDisplay),
          escapeCsv(t.customer_name || "—"),
          escapeCsv(t.customer_ic_no || "—"),
          escapeCsv(brandModel),
          escapeCsv(formatDateSafe(t.coverage_start_date)),
          escapeCsv(formatDateSafe(t.coverage_end_date)),
          escapeCsv(t.stage),
          escapeCsv(t.status),
          escapeCsv(winningInsurer),
          escapeCsv(wonPrem),
          escapeCsv(roadTax),
          escapeCsv(runnerFee),
          escapeCsv(pic),
          escapeCsv(policyNo),
        ].join(",");
      });

      const csvContent = "\uFEFF" + [headers.join(","), ...rows].join("\r\n");
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const dateStr = new Date().toISOString().split("T")[0];
      link.setAttribute("href", url);
      link.setAttribute("download", `risklocker-tenures-${dateStr}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export CSV error:", err);
      alert("Failed to export CSV");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex items-center gap-2 bg-neutral-900 text-white px-3 py-1.5 rounded-[var(--rl-radius-sm)] shadow-md animate-fadeIn flex-wrap">
      <span className="text-xs font-bold text-neutral-200">
        {selectedTenureIds.length} selected
      </span>
      <button
        type="button"
        onClick={onBulkConfirmHit}
        disabled={confirmingBulk}
        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all shadow-xs cursor-pointer disabled:opacity-50"
        title="Confirm policy as Hit (Won / Issued Policy) for all selected deals in one go"
      >
        <CheckCircle size={13} weight="bold" />
        <span>
          {confirmingBulk
            ? "Confirming..."
            : `Bulk Confirm Hit (${selectedTenureIds.length})`}
        </span>
      </button>
      <button
        type="button"
        onClick={onBulkDelete}
        disabled={deletingBulk}
        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-all shadow-xs cursor-pointer disabled:opacity-50"
        title="Delete all selected deals"
      >
        <Trash size={13} weight="bold" />
        <span>{deletingBulk ? "Deleting..." : "Delete Selected"}</span>
      </button>
      <button
        type="button"
        onClick={handleExportCSV}
        disabled={exporting}
        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-neutral-700 hover:bg-neutral-600 text-white text-xs font-bold transition-all shadow-xs cursor-pointer disabled:opacity-50"
        title="Export selected tenures to CSV"
      >
        <DownloadSimple size={13} weight="bold" />
        <span>{exporting ? "Exporting..." : "Export CSV"}</span>
      </button>
      <button
        type="button"
        onClick={onClearSelection}
        className="text-[11px] text-neutral-400 hover:text-white underline cursor-pointer"
      >
        Clear
      </button>
    </div>
  );
}
