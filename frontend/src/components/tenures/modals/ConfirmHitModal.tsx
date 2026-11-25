"use client";

import React from "react";
import { CheckCircle, FilePdf } from "@phosphor-icons/react";
import { fileUrl } from "@/lib/api";
import type { TenureRow } from "../types";

export interface HitConfirmModalProps {
  tenure: TenureRow | null;
  hitConfirmedInsurer: string;
  setHitConfirmedInsurer: (val: string) => void;
  hitConfirmedStartDate: string;
  setHitConfirmedStartDate: (val: string) => void;
  hitConfirmedEndDate: string;
  setHitConfirmedEndDate: (val: string) => void;
  savingHitConfirm: boolean;
  onConfirmHit: () => Promise<void>;
  onClose: () => void;
}

export function HitConfirmModal({
  tenure,
  hitConfirmedInsurer,
  setHitConfirmedInsurer,
  hitConfirmedStartDate,
  setHitConfirmedStartDate,
  hitConfirmedEndDate,
  setHitConfirmedEndDate,
  savingHitConfirm,
  onConfirmHit,
  onClose,
}: HitConfirmModalProps) {
  if (!tenure) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
      <div className="bg-white rounded-[var(--rl-radius)] border border-neutral-200 shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="p-4 border-b border-neutral-100 bg-[#fbfbfd] flex items-center justify-between">
          <div>
            <div className="flex items-center gap-1.5">
              <CheckCircle size={16} weight="fill" className="text-emerald-600" />
              <h3 className="font-bold text-sm text-neutral-900">
                Confirm Policy &amp; Mark as HIT (Won)
              </h3>
            </div>
            <p className="text-xs text-neutral-500 font-mono mt-0.5">
              {tenure.vehicle_no} · {tenure.customer_name}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-700 text-sm font-bold p-1 cursor-pointer"
          >
            ✕
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-bold text-neutral-800 block mb-1">
              1. Confirmed Insurer
            </label>
            <input
              type="text"
              value={hitConfirmedInsurer}
              onChange={(e) => setHitConfirmedInsurer(e.target.value)}
              placeholder="e.g. Allianz General Insurance, Zurich Takaful..."
              className="w-full h-9 px-3 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900 font-semibold"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-neutral-800 block mb-1">
              2. Confirmed Insurance Period (Tempoh Insurans)
            </label>
            <p className="text-[11px] text-neutral-500 mb-2">
              Verify or adjust the policy dates extracted from the quotation PDF:
            </p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-[10px] font-bold text-neutral-600 block mb-1">Start Date</span>
                <input
                  type="date"
                  value={hitConfirmedStartDate}
                  onChange={(e) => {
                    const newStart = e.target.value;
                    setHitConfirmedStartDate(newStart);
                    if (newStart) {
                      const [yy, mm, dd] = newStart.split("T")[0].split("-").map(Number);
                      if (yy && mm && dd) {
                        if (mm === 2 && dd === 29) {
                          setHitConfirmedEndDate(`${yy + 1}-02-28`);
                        } else {
                          const d = new Date(Date.UTC(yy + 1, mm - 1, dd));
                          d.setUTCDate(d.getUTCDate() - 1);
                          setHitConfirmedEndDate(d.toISOString().split("T")[0]);
                        }
                      }
                    }
                  }}
                  className="w-full h-8 px-2.5 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900 font-mono"
                />
              </div>
              <div>
                <span className="text-[10px] font-bold text-neutral-600 block mb-1">End Date</span>
                <input
                  type="date"
                  value={hitConfirmedEndDate}
                  onChange={(e) => setHitConfirmedEndDate(e.target.value)}
                  className="w-full h-8 px-2.5 text-xs rounded border border-neutral-300 focus:outline-none focus:border-neutral-900 font-mono"
                />
              </div>
            </div>

            {hitConfirmedStartDate && hitConfirmedEndDate && (
              <div className="mt-2.5 p-2 bg-emerald-50 border border-emerald-200 rounded text-[11px] text-emerald-950 font-mono flex items-center justify-between">
                <span>
                  Period: {hitConfirmedStartDate} → {hitConfirmedEndDate}
                </span>
                <span className="text-[10px] font-bold text-emerald-700 bg-white px-1.5 py-0.5 rounded border border-emerald-300">
                  1 Year
                </span>
              </div>
            )}
          </div>

          <div>
            <label className="text-xs font-bold text-neutral-800 block mb-1">
              3.{" "}
              {tenure.covernote_policy
                ? "Official Cover Note / Policy PDF"
                : "Accepted Quotation PDF"}
            </label>
            {tenure.covernote_policy?.uploaded_file_id ? (
              <div className="p-2.5 bg-emerald-50/60 border border-emerald-300 rounded flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 truncate">
                  <FilePdf size={16} weight="fill" className="text-emerald-700 shrink-0" />
                  <span className="font-bold text-emerald-950 truncate">
                    {tenure.covernote_policy.file_name ||
                      `${tenure.covernote_policy.company} Cover Note`}
                  </span>
                </div>
                <a
                  href={fileUrl(
                    `/uploaded-files/${tenure.covernote_policy.uploaded_file_id}/content`
                  )}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-emerald-800 hover:text-emerald-950 font-bold text-[11px] underline shrink-0 ml-2"
                >
                  View Policy PDF ↗
                </a>
              </div>
            ) : tenure.winning_file_id ? (
              <div className="p-2.5 bg-neutral-50 border border-neutral-200 rounded flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 truncate">
                  <FilePdf size={16} weight="fill" className="text-emerald-600 shrink-0" />
                  <span className="font-medium text-neutral-900 truncate">
                    {tenure.winning_file_name || "Accepted Quotation PDF"}
                  </span>
                </div>
                <a
                  href={fileUrl(`/uploaded-files/${tenure.winning_file_id}/content`)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-emerald-700 hover:text-emerald-900 font-bold text-[11px] underline shrink-0 ml-2"
                >
                  View PDF ↗
                </a>
              </div>
            ) : tenure.sourced_quotes?.find((q) => q.uploaded_file_id) ? (
              (() => {
                const winQuote =
                  tenure.sourced_quotes.find((q) => q.is_winner && q.uploaded_file_id) ||
                  tenure.sourced_quotes.find((q) => q.uploaded_file_id);
                return winQuote?.uploaded_file_id ? (
                  <div className="p-2.5 bg-neutral-50 border border-neutral-200 rounded flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5 truncate">
                      <FilePdf size={16} weight="fill" className="text-blue-600 shrink-0" />
                      <span className="font-medium text-neutral-900 truncate">
                        {winQuote.file_name || `${winQuote.company} Quote`}
                      </span>
                    </div>
                    <a
                      href={fileUrl(`/uploaded-files/${winQuote.uploaded_file_id}/content`)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-700 hover:text-blue-900 font-bold text-[11px] underline shrink-0 ml-2"
                    >
                      View PDF ↗
                    </a>
                  </div>
                ) : (
                  <div className="p-2.5 bg-neutral-50 rounded border border-neutral-200 text-xs text-neutral-500 italic">
                    No PDF uploaded for this quote.
                  </div>
                );
              })()
            ) : (
              <div className="p-2.5 bg-neutral-50 rounded border border-neutral-200 text-xs text-neutral-500 italic">
                No PDF uploaded for this quote.
              </div>
            )}
          </div>

          <div className="p-2.5 bg-amber-50 rounded border border-amber-200 text-[11px] text-amber-900 leading-relaxed">
            Confirming this policy issuance will mark the deal as <strong>HIT (Won)</strong> and
            automatically create the next-year renewal in the Motor Timeline.
          </div>
        </div>

        <div className="p-3 bg-neutral-50 border-t border-neutral-200 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs font-medium text-neutral-600 hover:text-neutral-900 cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirmHit}
            disabled={savingHitConfirm}
            className="px-4 py-1.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded shadow-xs cursor-pointer disabled:opacity-50 flex items-center gap-1"
          >
            <CheckCircle size={13} weight="bold" />
            <span>{savingHitConfirm ? "Confirming..." : "Confirm & Mark as HIT (Won)"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
