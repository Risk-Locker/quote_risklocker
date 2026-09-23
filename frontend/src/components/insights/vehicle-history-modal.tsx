"use client";

import { useEffect, useState } from "react";
import { Car, Clock, User, X, CheckCircle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface VehicleHistoryResponse {
  found: boolean;
  vehicle: {
    id: string;
    vehicle_no: string;
    car_brand?: string | null;
    car_model?: string | null;
    current_owner_name?: string | null;
  } | null;
  ownerships: Array<{
    id: string;
    customer_name: string;
    valid_until?: string | null;
    is_current: boolean;
    sequence_order: number;
    sequence_label: string;
    source_session_id?: string | null;
  }>;
  sessions_count: number;
}

export function VehicleHistoryModal({
  vehicleNo,
  onClose,
}: {
  vehicleNo: string | null;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<VehicleHistoryResponse | null>(null);

  useEffect(() => {
    if (!vehicleNo) {
      setData(null);
      return;
    }
    let cancelled = false;
    async function loadHistory() {
      setLoading(true);
      try {
        const res = await api<VehicleHistoryResponse>(
          `/insights/vehicles/${encodeURIComponent(vehicleNo!)}/history`
        );
        if (!cancelled) setData(res);
      } catch (err) {
        console.error("Failed to load vehicle history:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadHistory();
    return () => {
      cancelled = true;
    };
  }, [vehicleNo]);

  if (!vehicleNo) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
      <div className="bg-white rounded-lg border border-neutral-200 shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-100">
        {/* Header */}
        <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between bg-neutral-50/70">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-[#1b1717] text-white flex items-center justify-center font-bold">
              <Car size={16} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-neutral-900 tracking-tight font-mono">
                {vehicleNo}
              </h3>
              <p className="text-[11px] text-neutral-500">
                Sequential vehicle ownership timeline &amp; transfer audit
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-700 p-1"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 max-h-[75vh] overflow-y-auto">
          {loading ? (
            <div className="py-12 text-center">
              <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-neutral-300 border-t-[#1b1717] mb-2" />
              <p className="text-xs text-neutral-500 font-medium">Retrieving ownership records...</p>
            </div>
          ) : !data || !data.found ? (
            <div className="py-8 text-center text-xs text-neutral-500 space-y-1">
              <p className="font-semibold text-neutral-700">No vehicle tracking profile found.</p>
              <p>This vehicle number has not yet been registered or backfilled.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Vehicle Specs Overview */}
              <div className="p-3 bg-neutral-50 rounded-lg border border-neutral-200/80 text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-neutral-500">Model:</span>
                  <span className="font-semibold text-neutral-900">
                    {[data.vehicle?.car_brand, data.vehicle?.car_model].filter(Boolean).join(" ") || "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Current Owner:</span>
                  <span className="font-bold text-emerald-800">
                    {data.vehicle?.current_owner_name || "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Total Linked Quotes:</span>
                  <span className="font-medium text-neutral-800">{data.sessions_count} sessions</span>
                </div>
              </div>

              {/* Ownership Timeline */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-neutral-900 uppercase tracking-wider flex items-center gap-1.5">
                  <Clock size={14} className="text-neutral-500" />
                  <span>Sequential Ownership Timeline</span>
                </h4>

                <div className="space-y-2">
                  {data.ownerships.map((o) => (
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
                          {data.ownerships.length === 1 ? "Owner" : o.sequence_label}
                        </span>
                        <span className="font-semibold">{o.customer_name}</span>
                      </div>

                      <div className="flex items-center gap-3 text-right">
                        {o.valid_until && (
                          <span className="text-[11px] text-neutral-500">
                            Valid until {o.valid_until}
                          </span>
                        )}
                        {o.is_current && (
                          <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-1.5 py-0.5 rounded flex items-center gap-1">
                            <CheckCircle size={11} weight="fill" />
                            Current
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

        {/* Footer */}
        <div className="px-5 py-3 bg-neutral-50 border-t border-neutral-100 flex justify-end">
          <Button variant="secondary" size="sm" onClick={onClose} className="text-xs">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
