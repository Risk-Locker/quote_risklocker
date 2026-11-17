"use client";

import React from "react";
import { CheckCircle } from "@phosphor-icons/react";
import type { TenureRow, PicItem } from "../types";
import { formatDateSafe, formatDateTimeSafe, formatRelativeTime } from "../types";

interface PicDisplay {
  name: string;
  agency: string | null;
  whatsapp: string | null;
}

function resolvePicDisplay(t: TenureRow, pics: PicItem[]): PicDisplay | null {
  const matched = pics.find((p) => p.id === t.pic_id);
  if (matched) {
    return { name: matched.name, agency: matched.agency_group, whatsapp: matched.whatsapp_number ?? null };
  }
  if (t.sub_agent_name) {
    return { name: t.sub_agent_name, agency: t.pic_agency || null, whatsapp: null };
  }
  return null;
}

/** PIC + settled payment milestones. Unpaid states are the default and are not rendered as noise. */
export function PicCell({ tenure, pics }: { tenure: TenureRow; pics: PicItem[] }) {
  const pic = resolvePicDisplay(tenure, pics);
  const settled = [
    tenure.client_payment_received ? "Client paid" : null,
    tenure.agency_payment_done ? "Agency paid" : null,
  ].filter((label): label is string => Boolean(label));

  return (
    <div className="space-y-1 min-w-[130px]">
      {pic ? (
        <div className="flex items-center gap-1 flex-wrap">
          <span className="font-bold text-xs text-neutral-900">{pic.name}</span>
          {pic.agency && (
            <span className="text-[9px] text-neutral-500 font-medium bg-neutral-100 px-1 rounded">{pic.agency}</span>
          )}
          {pic.whatsapp && (
            <a
              href={`https://wa.me/${pic.whatsapp.replace(/[^0-9]/g, "")}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-emerald-700 hover:text-emerald-900 text-[10px] font-bold bg-emerald-50 px-1.5 rounded border border-emerald-200"
              title={`WhatsApp ${pic.whatsapp}`}
            >
              WA
            </a>
          )}
        </div>
      ) : (
        <span className="text-neutral-400 italic text-[11px]">Unassigned</span>
      )}

      {settled.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap">
          {settled.map((label) => (
            <span
              key={label}
              className="inline-flex items-center gap-0.5 text-[9.5px] font-semibold text-emerald-700"
            >
              <CheckCircle size={10} weight="fill" /> {label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function CreatedAtCell({ createdAt }: { createdAt?: string }) {
  if (!createdAt) return <span className="text-neutral-400 italic text-[11px]">—</span>;
  const parsed = new Date(createdAt);
  const label = Number.isNaN(parsed.getTime())
    ? formatDateSafe(createdAt)
    : parsed.toLocaleDateString("en-MY", { day: "2-digit", month: "short", year: "numeric" });
  return (
    <div>
      <div className="text-xs font-mono font-medium text-neutral-800" title={`Full Timestamp: ${formatDateTimeSafe(createdAt)}`}>
        {label}
      </div>
      <div className="text-[10px] text-neutral-400 font-mono mt-0.5">{formatRelativeTime(createdAt)}</div>
    </div>
  );
}
