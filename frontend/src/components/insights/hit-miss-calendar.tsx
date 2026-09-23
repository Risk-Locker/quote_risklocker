"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Calendar,
  CheckCircle,
  XCircle,
  Clock,
  Car,
  PaperPlaneRight,
  MagnifyingGlass,
  Funnel,
  ArrowSquareOut,
  User,
  CaretRight,
  CaretLeft,
  X,
  Buildings,
  CurrencyDollar,
  ArrowsClockwise,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface ActivityItem {
  id: string;
  session_id: string;
  vehicle_no: string;
  customer_name: string;
  action_type: string;
  timestamp: string;
  time_display: string;
  version_number: number;
  sent_to_client: boolean;
  summary: string;
  addons_snapshot: any[];
  status: "pending" | "hit" | "miss" | "superseded";
  miss_reason: string | null;
  won_premium: number | null;
  total_premium: string;
  company: string;
  notes: string | null;
  user_email: string | null;
}

interface CalendarResponse {
  dates: Record<string, ActivityItem[]>;
  total_activities: number;
}

interface VehicleHistoryData {
  found: boolean;
  vehicle: {
    id: string;
    vehicle_no: string;
    car_brand: string | null;
    car_model: string | null;
    engine_cc: string | null;
    current_owner_name: string | null;
  } | null;
  ownerships: Array<{
    id: string;
    customer_name: string;
    valid_until: string | null;
    is_current: boolean;
    sequence_order: number;
    sequence_label: string;
    created_at: string | null;
  }>;
  sessions_count: number;
}

const LOSS_REASONS = [
  "Price too high / Competitor cheaper",
  "Client renewed elsewhere",
  "Delay in decision / Thinking over",
  "Vehicle sold / Transfer of ownership",
  "Client unreachable / No response",
  "Purchased directly with insurer",
  "Other",
];

export function HitMissCalendar() {
  const [data, setData] = useState<CalendarResponse>({ dates: {}, total_activities: 0 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [companyFilter, setCompanyFilter] = useState("all");
  const [sentOnly, setSentOnly] = useState(false);

  // Status update modal state
  const [statusModalItem, setStatusModalItem] = useState<ActivityItem | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState<"hit" | "miss">("hit");
  const [selectedReason, setSelectedReason] = useState(LOSS_REASONS[0]);
  const [customReason, setCustomReason] = useState("");
  const [savingStatus, setSavingStatus] = useState(false);

  // Vehicle history modal state
  const [inspectPlate, setInspectPlate] = useState<string | null>(null);
  const [vehicleHistory, setVehicleHistory] = useState<VehicleHistoryData | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const fetchActivities = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      if (statusFilter !== "all") params.append("status", statusFilter);
      if (sentOnly) params.append("sent_only", "true");

      const res = await api<CalendarResponse>(`/insights/calendar?${params.toString()}`);
      setData(res);
    } catch (err) {
      console.error("Failed to load calendar activities:", err);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, sentOnly]);

  useEffect(() => {
    fetchActivities();
  }, [fetchActivities]);

  const [coverageStartDate, setCoverageStartDate] = useState<string>("");
  const [coverageEndDate, setCoverageEndDate] = useState<string>("");

  const handleOpenStatusModal = (item: ActivityItem, newStatus: "hit" | "miss") => {
    setStatusModalItem(item);
    setUpdatingStatus(newStatus);
    setSelectedReason(LOSS_REASONS[0]);
    setCustomReason("");
    const todayStr = new Date().toISOString().split("T")[0];
    setCoverageStartDate(todayStr);
    const nextYear = new Date();
    nextYear.setFullYear(nextYear.getFullYear() + 1);
    nextYear.setDate(nextYear.getDate() - 1);
    setCoverageEndDate(nextYear.toISOString().split("T")[0]);
  };

  const handleConfirmStatusUpdate = async () => {
    if (!statusModalItem) return;
    setSavingStatus(true);
    try {
      const reason = selectedReason === "Other" && customReason.trim() ? customReason.trim() : selectedReason;
      await api(`/insights/sessions/${statusModalItem.session_id}/status`, {
        method: "POST",
        body: JSON.stringify({
          status: updatingStatus,
          miss_reason: updatingStatus === "miss" ? reason : null,
          won_premium: updatingStatus === "hit" ? parseFloat(statusModalItem.total_premium.replace(/[^0-9.]/g, "")) || null : null,
          coverage_start_date: updatingStatus === "hit" ? coverageStartDate : null,
          coverage_end_date: updatingStatus === "hit" ? coverageEndDate : null,
        }),
      });
      setStatusModalItem(null);
      await fetchActivities();
    } catch (err) {
      console.error("Failed to update quotation status:", err);
    } finally {
      setSavingStatus(false);
    }
  };

  const handleReopen = async (item: ActivityItem) => {
    try {
      await api(`/insights/sessions/${item.session_id}/status`, {
        method: "POST",
        body: JSON.stringify({ status: "pending" }),
      });
      await fetchActivities();
    } catch (err) {
      console.error("Failed to reopen quotation:", err);
    }
  };

  const handleInspectVehicle = async (plate: string) => {
    if (!plate || plate === "UNKNOWN") return;
    setInspectPlate(plate);
    setLoadingHistory(true);
    try {
      const res = await api<VehicleHistoryData>(`/insights/vehicles/${encodeURIComponent(plate)}/history`);
      setVehicleHistory(res);
    } catch (err) {
      console.error("Failed to load vehicle history:", err);
      setVehicleHistory(null);
    } finally {
      setLoadingHistory(false);
    }
  };

  const availableCompanies = React.useMemo(() => {
    if (!data?.dates) return [];
    const set = new Set<string>();
    for (const items of Object.values(data.dates)) {
      for (const i of items) {
        if (i.company) set.add(i.company);
      }
    }
    return Array.from(set).sort();
  }, [data]);

  const filteredDates = React.useMemo(() => {
    if (companyFilter === "all") return data.dates;
    const result: Record<string, ActivityItem[]> = {};
    for (const [dStr, items] of Object.entries(data.dates)) {
      const match = items.filter(
        (i) => (i.company || "").toLowerCase() === companyFilter.toLowerCase()
      );
      if (match.length > 0) {
        result[dStr] = match;
      }
    }
    return result;
  }, [data.dates, companyFilter]);

  const dateKeys = Object.keys(filteredDates).sort((a, b) => b.localeCompare(a));

  return (
    <div className="space-y-6">
      {/* Controls / Filter bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 rounded-lg border border-neutral-200/80 shadow-xs">
        <div className="relative flex-1 max-w-md">
          <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input
            type="text"
            placeholder="Search plate, client name, or notes..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-neutral-50 rounded border border-neutral-200 focus:outline-none focus:ring-1 focus:ring-neutral-400 focus:bg-white transition-all"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1 bg-neutral-100 p-0.5 rounded border border-neutral-200 text-xs">
            {(["all", "hit", "miss", "pending"] as const).map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 rounded font-medium transition-all ${
                  statusFilter === st
                    ? "bg-white text-neutral-900 shadow-xs"
                    : "text-neutral-500 hover:text-neutral-800"
                }`}
              >
                {st === "all" ? "All Status" : st.charAt(0).toUpperCase() + st.slice(1)}
              </button>
            ))}
          </div>

          {availableCompanies.length > 0 && (
            <select
              value={companyFilter}
              onChange={(e) => setCompanyFilter(e.target.value)}
              className="text-xs h-8 border border-neutral-200 rounded-md px-2 bg-white text-neutral-800"
            >
              <option value="all">All Insurers</option>
              {availableCompanies.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          )}

          <label className="flex items-center gap-1.5 text-xs text-neutral-600 cursor-pointer select-none px-2 py-1 rounded hover:bg-neutral-50 border border-transparent hover:border-neutral-200">
            <input
              type="checkbox"
              checked={sentOnly}
              onChange={(e) => setSentOnly(e.target.checked)}
              className="rounded border-neutral-300 text-neutral-900 focus:ring-neutral-400"
            />
            <span>Sent to Client only</span>
          </label>

          <Button
            size="sm"
            variant="ghost"
            onClick={() => fetchActivities()}
            className="text-xs text-neutral-600 hover:text-neutral-900 h-8 px-2"
            title="Refresh activities"
          >
            <ArrowsClockwise size={14} />
          </Button>
        </div>
      </div>

      {/* Chronological Activity Feed by Date */}
      {loading ? (
        <div className="p-12 text-center text-xs text-neutral-400">Loading quotation activities...</div>
      ) : dateKeys.length === 0 ? (
        <div className="p-12 text-center bg-white rounded-lg border border-neutral-200/80">
          <Calendar size={32} className="mx-auto text-neutral-300 mb-2" />
          <p className="text-sm font-semibold text-neutral-800">No quotation activities found</p>
          <p className="text-xs text-neutral-400 mt-1">Upload a quotation or run backfill to populate past sessions.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {dateKeys.map((dateStr) => {
            const items = filteredDates[dateStr] || [];
            return (
              <div key={dateStr} className="space-y-2">
                {/* Date Header Badge */}
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 px-2.5 py-1 bg-neutral-900 text-white rounded text-xs font-semibold shadow-xs">
                    <Calendar size={13} weight="bold" />
                    <span>{dateStr}</span>
                  </div>
                  <span className="text-[11px] text-neutral-400 font-medium">
                    {items.length} event{items.length === 1 ? "" : "s"}
                  </span>
                  <div className="flex-1 h-px bg-neutral-200/70" />
                </div>

                {/* Date Items Cards */}
                <div className="grid gap-2">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3.5 bg-white rounded-lg border border-neutral-200/80 hover:border-neutral-300 shadow-2xs transition-all"
                    >
                      {/* Left: Time + Plate + Client Info */}
                      <div className="flex items-start md:items-center gap-3">
                        <div className="flex flex-col items-center justify-center min-w-[64px] px-2 py-1 bg-neutral-50 rounded border border-neutral-100 text-neutral-600">
                          <span className="text-[10px] text-neutral-400 flex items-center gap-0.5">
                            <Clock size={10} />
                            Time
                          </span>
                          <span className="text-xs font-semibold text-neutral-800 tracking-tight">
                            {item.time_display}
                          </span>
                        </div>

                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            {/* Vehicle Plate (Click to inspect history) */}
                            <button
                              type="button"
                              onClick={() => handleInspectVehicle(item.vehicle_no)}
                              className="font-mono text-xs font-bold text-neutral-900 px-2 py-0.5 bg-neutral-100 hover:bg-neutral-200 rounded border border-neutral-200/80 transition-colors flex items-center gap-1 cursor-pointer"
                              title="Click to view sequential owner transfer history"
                            >
                              <Car size={13} className="text-neutral-500" />
                              <span>{item.vehicle_no}</span>
                            </button>

                            {/* Client Name */}
                            <span className="text-xs font-medium text-neutral-800 flex items-center gap-1">
                              <User size={12} className="text-neutral-400" />
                              {item.customer_name}
                            </span>

                            {/* Sent to client badge */}
                            {item.sent_to_client ? (
                              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
                                <PaperPlaneRight size={10} weight="bold" />
                                Sent to Client
                              </span>
                            ) : (
                              <span className="inline-flex items-center text-[10px] font-medium text-neutral-500 bg-neutral-100 px-1.5 py-0.5 rounded">
                                Internal Save
                              </span>
                            )}

                            {item.version_number > 1 && (
                              <span className="text-[10px] text-neutral-400 font-mono">
                                v{item.version_number}
                              </span>
                            )}
                          </div>

                          <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-neutral-500">
                            {item.company && (
                              <span className="flex items-center gap-1">
                                <Buildings size={12} className="text-neutral-400" />
                                {item.company}
                              </span>
                            )}
                            {item.total_premium && (
                              <span className="font-semibold text-neutral-900">
                                {item.total_premium}
                              </span>
                            )}
                            <span className="text-neutral-400 text-[11px] truncate max-w-sm">
                              {item.summary}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Right: Outcome Status & Quick Actions */}
                      <div className="flex items-center gap-2 self-end md:self-center">
                        {/* Status Chip */}
                        {item.status === "hit" ? (
                          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded text-xs font-semibold">
                            <CheckCircle size={14} weight="fill" className="text-emerald-600" />
                            <span>HIT (Won)</span>
                          </div>
                        ) : item.status === "miss" ? (
                          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-rose-50 border border-rose-200 text-rose-800 rounded text-xs font-semibold">
                            <XCircle size={14} weight="fill" className="text-rose-600" />
                            <span>MISS: {item.miss_reason || "Lost"}</span>
                          </div>
                        ) : item.status === "superseded" ? (
                          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-purple-50 border border-purple-200 text-purple-800 rounded text-xs font-semibold" title="Alternative quote superseded by winning policy">
                            <CheckCircle size={14} weight="bold" className="text-purple-600" />
                            <span>Superceded</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-neutral-100 text-neutral-600 rounded text-xs font-medium">
                            <Clock size={13} />
                            <span>Pending</span>
                          </div>
                        )}

                        {/* Status Action Buttons */}
                        {item.status !== "hit" && (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => handleOpenStatusModal(item, "hit")}
                            className="text-xs h-7 px-2 border-emerald-200 text-emerald-700 hover:bg-emerald-50 gap-1"
                          >
                            <CheckCircle size={13} weight="bold" />
                            Hit
                          </Button>
                        )}

                        {item.status !== "miss" && item.status !== "superseded" && (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => handleOpenStatusModal(item, "miss")}
                            className="text-xs h-7 px-2 border-rose-200 text-rose-700 hover:bg-rose-50 gap-1"
                          >
                            <XCircle size={13} weight="bold" />
                            Miss
                          </Button>
                        )}

                        {item.status !== "pending" && (
                          <button
                            type="button"
                            onClick={() => handleReopen(item)}
                            className="text-[11px] text-neutral-400 hover:text-neutral-700 underline px-1 cursor-pointer"
                          >
                            Reopen
                          </button>
                        )}

                        {/* Direct link to session workspace */}
                        <a
                          href={`/sessions/${item.session_id}/review`}
                          className="p-1.5 text-neutral-400 hover:text-neutral-900 rounded hover:bg-neutral-100 transition-colors"
                          title="Open Session Workspace"
                        >
                          <ArrowSquareOut size={15} />
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal: Mark Hit / Miss Outcome */}
      {statusModalItem && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in"
        >
          <div className="w-full max-w-md bg-white rounded-lg shadow-xl border border-neutral-200 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-neutral-100">
              <h3 className="text-sm font-semibold text-neutral-900 flex items-center gap-2">
                {updatingStatus === "hit" ? (
                  <>
                    <CheckCircle size={16} weight="fill" className="text-emerald-600" />
                    <span>Confirm Won Policy (HIT)</span>
                  </>
                ) : (
                  <>
                    <XCircle size={16} weight="fill" className="text-rose-600" />
                    <span>Record Unconverted Quotation (MISS)</span>
                  </>
                )}
              </h3>
              <button
                onClick={() => setStatusModalItem(null)}
                className="text-neutral-400 hover:text-neutral-600 p-1 rounded"
              >
                <X size={16} />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div className="p-3 bg-neutral-50 rounded border border-neutral-200/80 text-xs text-neutral-700 space-y-1">
                <div className="flex justify-between">
                  <span className="text-neutral-400">Vehicle:</span>
                  <span className="font-mono font-bold text-neutral-900">{statusModalItem.vehicle_no}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-400">Client:</span>
                  <span className="font-medium text-neutral-900">{statusModalItem.customer_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-400">Premium:</span>
                  <span className="font-bold text-neutral-900">{statusModalItem.total_premium || "RM 0.00"}</span>
                </div>
              </div>

              {updatingStatus === "hit" ? (
                <div className="space-y-3">
                  <p className="text-xs text-neutral-600">
                    Confirming as Won finalizes this policy for vehicle <b>{statusModalItem.vehicle_no}</b>.
                    Any competing quote options for this vehicle will be marked as superceded, and a <b>9-month renewal reminder</b> will be scheduled.
                  </p>

                  <div className="grid grid-cols-2 gap-3 pt-1">
                    <div>
                      <label className="block text-[11px] font-semibold text-neutral-700 mb-1">
                        Coverage Start Date
                      </label>
                      <input
                        type="date"
                        value={coverageStartDate}
                        onChange={(e) => setCoverageStartDate(e.target.value)}
                        className="w-full text-xs h-8 px-2 rounded border border-neutral-300 bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-neutral-700 mb-1">
                        Coverage End Date
                      </label>
                      <input
                        type="date"
                        value={coverageEndDate}
                        onChange={(e) => setCoverageEndDate(e.target.value)}
                        className="w-full text-xs h-8 px-2 rounded border border-neutral-300 bg-white"
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 text-[11px] text-neutral-500">
                    <span>Quick Period:</span>
                    <button
                      type="button"
                      onClick={() => {
                        const s = new Date(coverageStartDate || new Date());
                        const e = new Date(s);
                        e.setFullYear(e.getFullYear() + 1);
                        e.setDate(e.getDate() - 1);
                        setCoverageEndDate(e.toISOString().split("T")[0]);
                      }}
                      className="px-2 py-0.5 rounded border border-neutral-200 bg-neutral-100 hover:bg-neutral-200 text-neutral-800 font-medium cursor-pointer"
                    >
                      1 Year
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const s = new Date(coverageStartDate || new Date());
                        const e = new Date(s);
                        e.setMonth(e.getMonth() + 6);
                        e.setDate(e.getDate() - 1);
                        setCoverageEndDate(e.toISOString().split("T")[0]);
                      }}
                      className="px-2 py-0.5 rounded border border-neutral-200 bg-neutral-100 hover:bg-neutral-200 text-neutral-800 font-medium cursor-pointer"
                    >
                      6 Months
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <label className="block text-xs font-semibold text-neutral-800">
                    Reason Client Did Not Take Up Policy
                  </label>
                  <div className="space-y-1.5">
                    {LOSS_REASONS.map((r) => (
                      <label
                        key={r}
                        className={`flex items-center gap-2.5 p-2 rounded border text-xs cursor-pointer transition-colors ${
                          selectedReason === r
                            ? "border-neutral-900 bg-neutral-50 font-medium text-neutral-900"
                            : "border-neutral-200 hover:bg-neutral-50 text-neutral-700"
                        }`}
                      >
                        <input
                          type="radio"
                          name="loss_reason"
                          checked={selectedReason === r}
                          onChange={() => setSelectedReason(r)}
                          className="text-neutral-900 focus:ring-neutral-400"
                        />
                        <span>{r}</span>
                      </label>
                    ))}
                  </div>

                  {selectedReason === "Other" && (
                    <input
                      type="text"
                      placeholder="Specify custom reason..."
                      value={customReason}
                      onChange={(e) => setCustomReason(e.target.value)}
                      className="w-full px-3 py-1.5 text-xs bg-white rounded border border-neutral-300 focus:outline-none focus:ring-1 focus:ring-neutral-500"
                    />
                  )}
                </div>
              )}
            </div>

            <div className="px-5 py-3.5 bg-neutral-50 border-t border-neutral-100 flex items-center justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setStatusModalItem(null)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                loading={savingStatus}
                onClick={handleConfirmStatusUpdate}
                className={`text-xs ${
                  updatingStatus === "hit"
                    ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                    : "bg-rose-600 hover:bg-rose-700 text-white"
                }`}
              >
                Confirm {updatingStatus === "hit" ? "Won" : "Lost"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Vehicle Ownership History */}
      {inspectPlate && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in"
        >
          <div className="w-full max-w-lg bg-white rounded-lg shadow-xl border border-neutral-200 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-neutral-100">
              <div className="flex items-center gap-2">
                <Car size={18} className="text-neutral-700" />
                <h3 className="text-sm font-semibold text-neutral-900">
                  Vehicle Tracking &amp; Ownership History
                </h3>
              </div>
              <button
                onClick={() => {
                  setInspectPlate(null);
                  setVehicleHistory(null);
                }}
                className="text-neutral-400 hover:text-neutral-600 p-1 rounded"
              >
                <X size={16} />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {loadingHistory ? (
                <div className="py-8 text-center text-xs text-neutral-400">Loading vehicle history...</div>
              ) : !vehicleHistory || !vehicleHistory.found ? (
                <div className="py-8 text-center text-xs text-neutral-500">
                  No previous ownership record registered for plate <span className="font-mono font-bold">{inspectPlate}</span>.
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Vehicle Header Card */}
                  <div className="p-3 bg-neutral-50 rounded-lg border border-neutral-200/80 flex items-center justify-between">
                    <div>
                      <span className="font-mono text-base font-bold text-neutral-900 tracking-wide">
                        {vehicleHistory.vehicle?.vehicle_no}
                      </span>
                      <p className="text-xs text-neutral-500 mt-0.5">
                        {[vehicleHistory.vehicle?.car_brand, vehicleHistory.vehicle?.car_model]
                          .filter(Boolean)
                          .join(" ") || "Vehicle"}
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="text-[10px] text-neutral-400 uppercase tracking-wider block">Current Owner</span>
                      <span className="text-xs font-semibold text-neutral-900">
                        {vehicleHistory.vehicle?.current_owner_name || "Unknown"}
                      </span>
                    </div>
                  </div>

                  {/* Sequential Ownership Timeline */}
                  <div>
                    <h4 className="text-xs font-semibold text-neutral-700 mb-2">
                      Sequential Owners Across Time
                    </h4>
                    <div className="space-y-2">
                      {vehicleHistory.ownerships.map((o) => (
                        <div
                          key={o.id}
                          className={`flex items-center justify-between p-3 rounded-lg border text-xs ${
                            o.is_current
                              ? "bg-emerald-50/70 border-emerald-200 text-emerald-950"
                              : "bg-neutral-50/50 border-neutral-200 text-neutral-600"
                          }`}
                        >
                          <div className="flex items-center gap-2.5">
                            <span
                              className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                                o.is_current
                                  ? "bg-emerald-600 text-white"
                                  : "bg-neutral-200 text-neutral-700"
                              }`}
                            >
                              {vehicleHistory.ownerships.length === 1 ? "Owner" : o.sequence_label}
                            </span>
                            <span className="font-semibold">{o.customer_name}</span>
                          </div>

                          <div className="flex items-center gap-3 text-right">
                            {o.valid_until && (
                              <span className="text-[11px] text-neutral-500">
                                Covered until {o.valid_until}
                              </span>
                            )}
                            {o.is_current && (
                              <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-1.5 py-0.5 rounded">
                                Active
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="px-5 py-3 bg-neutral-50 border-t border-neutral-100 flex justify-end">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setInspectPlate(null);
                  setVehicleHistory(null);
                }}
                className="text-xs"
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
