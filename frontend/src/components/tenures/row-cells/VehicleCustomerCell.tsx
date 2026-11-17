"use client";

import React from "react";
import { Car } from "@phosphor-icons/react";
import { getVehicleDisplayName, shouldDisplayBrand } from "@/lib/vehicle-utils";
import type { VehicleGroup, TenureRow } from "../types";
import { HighlightText } from "../HighlightText";

interface VehicleCustomerCellProps {
  group: VehicleGroup;
  mainTenure: TenureRow;
  isCompact: boolean;
  search: string;
}

const IDENTIFIER_BADGES: Record<string, { label: string; className: string }> = {
  chassis: { label: "CHASSIS", className: "bg-amber-100 text-amber-900" },
  engine: { label: "ENGINE", className: "bg-indigo-100 text-indigo-900" },
  blank: { label: "NO PLATE", className: "bg-neutral-100 text-neutral-600" },
};

function resolveIdentifierKind(displayName: string): keyof typeof IDENTIFIER_BADGES | null {
  if (displayName.startsWith("Chassis:")) return "chassis";
  if (displayName.startsWith("Engine:")) return "engine";
  if (displayName === "No Plate (Blank)") return "blank";
  return null;
}

function formatEngineCapacity(raw?: string | null): string {
  const cleaned = (raw || "").trim();
  if (!cleaned) return "";
  return /(?:cc|kw|kg)$/i.test(cleaned) ? cleaned : `${cleaned} CC`;
}

function VehicleSpecLine({ group, search, isCompact }: { group: VehicleGroup; search: string; isCompact: boolean }) {
  const hasSpecs = group.car_brand || group.car_model || group.engine_cc || group.manufacture_year;
  if (!hasSpecs) return null;
  const capLabel = formatEngineCapacity(group.engine_cc);
  return (
    <div className="text-[10px] text-neutral-500 font-medium mt-0.5 truncate" title={[group.car_brand, group.car_model].filter(Boolean).join(" ")}>
      {shouldDisplayBrand(group.car_brand, group.car_model) ? <><HighlightText text={group.car_brand!} query={search} /> </> : ""}
      {group.car_model ? <HighlightText text={group.car_model} query={search} /> : ""}
      {capLabel ? ` · ${capLabel}` : ""}
      {group.manufacture_year ? ` · ${isCompact ? "" : "YOM "}${group.manufacture_year}` : ""}
    </div>
  );
}

export function VehicleCustomerCell({ group, mainTenure, isCompact, search }: VehicleCustomerCellProps) {
  const displayName = getVehicleDisplayName(group.vehicle_no, group.chassis_no, group.engine_no);
  const identifierKind = resolveIdentifierKind(displayName);
  const badge = identifierKind ? IDENTIFIER_BADGES[identifierKind] : null;

  return (
    <div className={`min-w-0 ${isCompact ? "max-w-[176px]" : "max-w-[220px]"}`}>
      <div className="flex items-center gap-1.5 min-w-0">
        <Car className="w-3.5 h-3.5 text-neutral-600 shrink-0" />
        <span
          className={`font-bold text-neutral-900 font-mono truncate ${isCompact ? "text-xs" : "text-sm"}`}
          title={displayName}
        >
          <HighlightText text={displayName} query={search} />
        </span>
        {badge && (
          <span className={`px-1.5 rounded font-sans text-[9px] font-bold shrink-0 ${badge.className}`}>
            {badge.label}
          </span>
        )}
      </div>

      <div className="text-xs font-semibold text-neutral-800 mt-0.5 truncate" title={group.customer_name || undefined}>
        {group.customer_name ? (
          <HighlightText text={group.customer_name} query={search} />
        ) : (
          <span className="text-neutral-400 italic font-normal">No customer name</span>
        )}
        {isCompact && group.customer_ic_no ? (
          <span className="text-[10px] text-neutral-400 font-mono font-normal">
            {" · "}
            <HighlightText text={group.customer_ic_no} query={search} />
          </span>
        ) : null}
      </div>

      {!isCompact && group.customer_ic_no && (
        <div className="text-[10px] text-neutral-400 font-mono mt-0.5 truncate">
          IC: <HighlightText text={group.customer_ic_no} query={search} />
        </div>
      )}

      <VehicleSpecLine group={group} search={search} isCompact={isCompact} />

      {!isCompact && mainTenure.created_by_email && (
        <div className="text-[10px] text-neutral-400 font-medium mt-0.5 truncate">
          By: <span className="text-neutral-600 font-semibold">{mainTenure.created_by_email}</span>
        </div>
      )}
    </div>
  );
}
