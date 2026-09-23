"use client";

import { useEffect, useState, useMemo } from "react";
import {
  CheckCircle,
  Database,
  Warning,
  X,
  MagnifyingGlass,
  ArrowRight,
  ArrowsClockwise,
  Car,
  User,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";

interface BackfillSessionItem {
  session_id: string;
  quotation_number: string;
  created_at: string;
  raw_plate: string;
  normalized_plate: string;
  customer_name: string;
  validity_date: string;
  model: string;
  company: string;
  premium: string;
  status: string;
  is_ready: boolean;
  issues: string[];
  proposed_action: string;
}

interface BackfillPreviewResponse {
  total_detected: number;
  ready_count: number;
  ambiguous_count: number;
  sessions: BackfillSessionItem[];
}

export function SyncSessionsModal({
  isOpen,
  onClose,
  onSyncComplete,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSyncComplete: () => void;
}) {
  const { toast } = useToast();
  const [loadingPreview, setLoadingPreview] = useState(true);
  const [preview, setPreview] = useState<BackfillPreviewResponse | null>(null);
  const [selectedSessionIds, setSelectedSessionIds] = useState<Set<string>>(new Set());
  const [filterTab, setFilterTab] = useState<"all" | "ready" | "ambiguous">("all");
  const [search, setSearch] = useState("");

  // User manual inline edits: session_id -> { vehicle_no, customer_name, validity_date }
  const [edits, setEdits] = useState<Record<string, { vehicle_no?: string; customer_name?: string; validity_date?: string }>>({});

  const [confirming, setConfirming] = useState(false);

  async function fetchPreview() {
    setLoadingPreview(true);
    try {
      const res = await api<BackfillPreviewResponse>("/insights/backfill/preview");
      setPreview(res);
      // Pre-select all ready sessions
      const initialSelected = new Set<string>();
      for (const s of res.sessions) {
        if (s.is_ready) {
          initialSelected.add(s.session_id);
        }
      }
      setSelectedSessionIds(initialSelected);
    } catch (e: any) {
      toast(e?.message || "Could not retrieve historical session preview", "error");
    } finally {
      setLoadingPreview(false);
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchPreview();
      setEdits({});
    }
  }, [isOpen]);

  // Toggle selection
  function toggleSession(id: string) {
    const next = new Set(selectedSessionIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelectedSessionIds(next);
  }

  function handleSelectAllReady() {
    if (!preview) return;
    const next = new Set<string>();
    for (const s of preview.sessions) {
      if (s.is_ready) next.add(s.session_id);
    }
    setSelectedSessionIds(next);
  }

  function handleSelectAll() {
    if (!preview) return;
    const next = new Set<string>();
    for (const s of preview.sessions) {
      next.add(s.session_id);
    }
    setSelectedSessionIds(next);
  }

  function handleDeselectAll() {
    setSelectedSessionIds(new Set());
  }

  function updateInlineEdit(sessionId: string, field: "vehicle_no" | "customer_name" | "validity_date", val: string) {
    setEdits((prev) => ({
      ...prev,
      [sessionId]: {
        ...prev[sessionId],
        [field]: val,
      },
    }));
  }

  // Filtered session list
  const filteredSessions = useMemo(() => {
    if (!preview?.sessions) return [];
    return preview.sessions.filter((s) => {
      if (filterTab === "ready" && !s.is_ready) return false;
      if (filterTab === "ambiguous" && s.is_ready) return false;

      if (search.trim()) {
        const st = search.trim().toLowerCase();
        const plate = edits[s.session_id]?.vehicle_no || s.normalized_plate;
        const name = edits[s.session_id]?.customer_name || s.customer_name;
        return (
          plate.toLowerCase().includes(st) ||
          name.toLowerCase().includes(st) ||
          s.quotation_number.toLowerCase().includes(st) ||
          s.company.toLowerCase().includes(st)
        );
      }
      return true;
    });
  }, [preview, filterTab, search, edits]);

  // Execute confirmation
  async function handleConfirmSync() {
    if (selectedSessionIds.size === 0) {
      toast("Please select at least one quotation session to sync.", "warning");
      return;
    }

    setConfirming(true);
    try {
      const payload = {
        session_ids: Array.from(selectedSessionIds),
        manual_overrides: edits,
      };

      const res = await api<{ sessions_processed: number; vehicles_tracked: number; activities_created: number }>(
        "/insights/backfill/confirm",
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      );

      toast(
        `Successfully processed ${res.sessions_processed} sessions, tracked ${res.vehicles_tracked} vehicles, and generated ${res.activities_created} activity records.`,
        "success"
      );

      onSyncComplete();
      onClose();
    } catch (e: any) {
      toast(e?.message || "Failed to backfill historical quotation sessions", "error");
    } finally {
      setConfirming(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
      <div className="bg-white rounded-lg border border-neutral-200 shadow-2xl max-w-4xl w-full flex flex-col max-h-[90vh] animate-in fade-in zoom-in-95 duration-150 overflow-hidden">
        {/* Modal Top Header */}
        <div className="p-4 border-b border-neutral-200/90 flex items-center justify-between bg-neutral-50/70">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-[#1b1717] text-white flex items-center justify-center">
              <Database size={17} weight="bold" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-neutral-900 tracking-tight">
                Historical Sessions Sync &amp; Verification
              </h2>
              <p className="text-xs text-neutral-500">
                Inspect detected vehicle numbers and dates before confirming synchronization into the activity ledger.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-700 p-1 rounded"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        {loadingPreview ? (
          <div className="p-16 text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-neutral-300 border-t-[#1b1717] mb-3" />
            <p className="text-xs font-semibold text-neutral-800">Analyzing past quotation sessions...</p>
            <p className="text-xs text-neutral-500 mt-1">
              Extracting vehicle registration plates, dates, customer names, and sequential ownership.
            </p>
          </div>
        ) : !preview ? (
          <div className="p-12 text-center text-xs text-neutral-500">
            No past sessions available to scan.
          </div>
        ) : (
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Summary Stat Badges & Tab Controls */}
            <div className="p-4 border-b border-neutral-200/80 bg-white space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                {/* Stats */}
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md bg-neutral-100 text-neutral-800 font-semibold border border-neutral-200">
                    <Database size={13} />
                    <span>Total Detected: {preview.total_detected}</span>
                  </span>

                  <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-800 font-semibold border border-emerald-200">
                    <CheckCircle size={13} weight="fill" />
                    <span>Ready to Sync: {preview.ready_count}</span>
                  </span>

                  {preview.ambiguous_count > 0 && (
                    <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md bg-amber-50 text-amber-800 font-semibold border border-amber-200">
                      <Warning size={13} weight="fill" />
                      <span>Needs Attention: {preview.ambiguous_count}</span>
                    </span>
                  )}
                </div>

                {/* Bulk Select Actions */}
                <div className="flex items-center gap-1.5 text-xs">
                  <button
                    type="button"
                    onClick={handleSelectAllReady}
                    className="px-2 py-1 rounded border border-neutral-200 text-neutral-700 hover:bg-neutral-50 font-medium"
                  >
                    Select Ready Only
                  </button>
                  <button
                    type="button"
                    onClick={handleSelectAll}
                    className="px-2 py-1 rounded border border-neutral-200 text-neutral-700 hover:bg-neutral-50 font-medium"
                  >
                    Select All
                  </button>
                  <button
                    type="button"
                    onClick={handleDeselectAll}
                    className="px-2 py-1 rounded border border-neutral-200 text-neutral-700 hover:bg-neutral-50 font-medium"
                  >
                    Deselect
                  </button>
                </div>
              </div>

              {/* Subtabs & Search */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pt-1">
                <div className="flex items-center rounded-md border border-neutral-200 bg-neutral-100 p-0.5 text-xs font-medium w-fit">
                  <button
                    type="button"
                    onClick={() => setFilterTab("all")}
                    className={`px-3 py-1 rounded transition-all ${
                      filterTab === "all" ? "bg-white text-neutral-900 shadow-2xs font-bold" : "text-neutral-600"
                    }`}
                  >
                    All ({preview.total_detected})
                  </button>
                  <button
                    type="button"
                    onClick={() => setFilterTab("ready")}
                    className={`px-3 py-1 rounded transition-all ${
                      filterTab === "ready" ? "bg-white text-neutral-900 shadow-2xs font-bold" : "text-neutral-600"
                    }`}
                  >
                    Ready ({preview.ready_count})
                  </button>
                  <button
                    type="button"
                    onClick={() => setFilterTab("ambiguous")}
                    className={`px-3 py-1 rounded transition-all ${
                      filterTab === "ambiguous" ? "bg-white text-neutral-900 shadow-2xs font-bold" : "text-neutral-600"
                    }`}
                  >
                    Needs Attention ({preview.ambiguous_count})
                  </button>
                </div>

                <div className="relative">
                  <MagnifyingGlass size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
                  <input
                    type="text"
                    placeholder="Search plate, client, ref..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="text-xs pl-8 pr-3 h-7 rounded border border-neutral-200 w-56 focus:ring-1 focus:ring-neutral-900 bg-white"
                  />
                </div>
              </div>
            </div>

            {/* Sessions Table */}
            <div className="flex-1 overflow-y-auto divide-y divide-neutral-100">
              {filteredSessions.length === 0 ? (
                <div className="p-8 text-center text-xs text-neutral-500">
                  No sessions match the selected filter.
                </div>
              ) : (
                filteredSessions.map((s) => {
                  const isChecked = selectedSessionIds.has(s.session_id);
                  const editedPlate = edits[s.session_id]?.vehicle_no ?? s.normalized_plate;
                  const editedCustomer = edits[s.session_id]?.customer_name ?? s.customer_name;

                  return (
                    <div
                      key={s.session_id}
                      className={`p-3.5 flex flex-col md:flex-row md:items-center gap-3 transition-colors ${
                        isChecked ? "bg-white" : "bg-neutral-50/40 opacity-75"
                      }`}
                    >
                      {/* Checkbox */}
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleSession(s.session_id)}
                          className="w-4 h-4 rounded text-[#1b1717] focus:ring-neutral-900 border-neutral-300"
                        />

                        {/* Status Icon */}
                        {s.is_ready ? (
                          <span title="Ready to sync">
                            <CheckCircle size={16} className="text-emerald-600 shrink-0" weight="fill" />
                          </span>
                        ) : (
                          <span title={s.issues.join(", ")}>
                            <Warning size={16} className="text-amber-500 shrink-0" weight="fill" />
                          </span>
                        )}

                        <div>
                          <div className="font-bold text-xs text-neutral-900 flex items-center gap-2">
                            <span>{s.quotation_number}</span>
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-neutral-100 text-neutral-600 font-normal">
                              {s.company}
                            </span>
                          </div>
                          <div className="text-[11px] text-neutral-400">{s.created_at}</div>
                        </div>
                      </div>

                      {/* Plate & Customer Fields (with inline edit) */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 md:flex-1">
                        <div>
                          <label className="text-[10px] font-semibold text-neutral-500 block mb-0.5">
                            Vehicle Plate
                          </label>
                          <input
                            type="text"
                            value={editedPlate}
                            onChange={(e) => updateInlineEdit(s.session_id, "vehicle_no", e.target.value)}
                            placeholder="Enter plate (e.g. JMC 8218)"
                            className={`text-xs h-7 px-2 rounded border w-full font-mono ${
                              !editedPlate ? "border-amber-400 bg-amber-50/40" : "border-neutral-200 bg-white"
                            }`}
                          />
                        </div>

                        <div>
                          <label className="text-[10px] font-semibold text-neutral-500 block mb-0.5">
                            Customer Name
                          </label>
                          <input
                            type="text"
                            value={editedCustomer}
                            onChange={(e) => updateInlineEdit(s.session_id, "customer_name", e.target.value)}
                            placeholder="Enter client name"
                            className={`text-xs h-7 px-2 rounded border w-full ${
                              !editedCustomer ? "border-amber-400 bg-amber-50/40" : "border-neutral-200 bg-white"
                            }`}
                          />
                        </div>
                      </div>

                      {/* Proposed Action / Issue Badge */}
                      <div className="md:w-60 shrink-0 text-right md:text-left">
                        {s.is_ready ? (
                          <div className="text-[11px] text-emerald-800 font-medium bg-emerald-50 px-2 py-1 rounded border border-emerald-200">
                            {s.proposed_action}
                          </div>
                        ) : (
                          <div className="text-[11px] text-amber-800 font-medium bg-amber-50 px-2 py-1 rounded border border-amber-200">
                            {s.issues.join("; ")}
                          </div>
                        )}
                        {s.premium && (
                          <div className="text-[10px] text-neutral-400 mt-0.5">
                            Premium: {s.premium}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Modal Bottom Footer */}
            <div className="p-4 border-t border-neutral-200/90 bg-neutral-50 flex items-center justify-between">
              <div className="text-xs text-neutral-600 font-medium">
                <span>{selectedSessionIds.size} of {preview.total_detected} sessions selected</span>
              </div>

              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={onClose} className="text-xs">
                  Cancel
                </Button>
                <Button
                  size="sm"
                  loading={confirming}
                  onClick={handleConfirmSync}
                  className="text-xs bg-[#1b1717] hover:bg-[#2c2727] text-white gap-1.5 shadow-sm"
                >
                  <CheckCircle size={14} weight="bold" />
                  Confirm &amp; Sync ({selectedSessionIds.size})
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
