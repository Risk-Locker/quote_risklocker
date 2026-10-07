"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import {
  Car,
  ClockCounterClockwise,
  MagnifyingGlass,
  Columns,
  ArrowsClockwise,
  CheckCircle,
  FilePdf,
  ArrowRight,
  ShieldCheck,
  CalendarBlank,
  FunnelSimple,
  Plus,
  Tag,
  CurrencyDollar,
  Sparkle,
  Trash,
  FileText,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { getVehicleDisplayName } from "@/lib/vehicle-utils";

interface SessionItem {
  id: string;
  owner_id?: string;
  is_test: boolean;
  created_by?: string;
  created_by_email?: string;
  last_edited_by?: string | null;
  last_edited_by_email?: string | null;
  last_edited_at?: string | null;
  uploaded_file_id?: string | null;
  draft_id?: string | null;
  template_id?: string | null;
  template_name?: string | null;
  tenure_id?: string | null;
  customer_id?: string | null;
  tracked_vehicle_id?: string | null;
  detected_company?: string | null;
  quotation_ref?: string | null;
  filename?: string | null;
  status: string;
  draft_status?: string | null;
  insured_name?: string | null;
  vehicle_plate?: string | null;
  chassis_no?: string | null;
  vehicle_model?: string | null;
  total_premium?: string | null;
  quotation_status?: string;
  miss_reason?: string | null;
  coverage_start_date?: string | null;
  coverage_end_date?: string | null;
  created_at: string;
  updated_at: string;
}

interface StaffOption {
  id: string;
  name: string;
  email: string;
}

export default function SessionsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<"all" | "single" | "comparison" | "test">("all");
  const [staffFilter, setStaffFilter] = useState<string>("all");
  const [staffOptions, setStaffOptions] = useState<StaffOption[]>([]);

  const fetchSessions = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.set("limit", "100");
      params.set("offset", "0");
      if (search.trim()) {
        params.set("search", search.trim());
      }
      if (activeTab === "test") {
        params.set("type_filter", "test");
      }
      if (staffFilter && staffFilter !== "all") {
        params.set("staff_id", staffFilter);
      }

      const res = await api<{
        sessions: SessionItem[];
        total: number;
        filter_options?: { staff?: StaffOption[] };
      }>(`/sessions?${params.toString()}`);
      setSessions(res.sessions || []);
      setTotalCount(res.total || 0);
      if (res.filter_options?.staff?.length) {
        setStaffOptions(res.filter_options.staff);
      }
    } catch (err) {
      console.error("Failed to load sessions:", err);
      setSessions([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [search, activeTab, staffFilter]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Filter sessions locally by comparison vs single if selected
  const filteredSessions = useMemo(() => {
    if (activeTab === "comparison") {
      return sessions.filter((s) => Boolean(s.tenure_id));
    }
    if (activeTab === "single") {
      return sessions.filter((s) => !s.tenure_id);
    }
    return sessions;
  }, [sessions, activeTab]);

  const stats = useMemo(() => {
    const total = sessions.length;
    const testQuotes = sessions.filter((s) => s.is_test).length;
    const comparisons = sessions.filter((s) => Boolean(s.tenure_id)).length;
    const singles = total - comparisons;
    return { total, testQuotes, comparisons, singles };
  }, [sessions]);

  function formatDate(dateStr?: string | null) {
    if (!dateStr) return "—";
    try {
      const dt = new Date(dateStr);
      return dt.toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  }

  return (
    <AppShell>
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Header Ribbon */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-200/80 pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-neutral-500 mb-1">
              <ClockCounterClockwise size={16} weight="bold" />
              <span>Quotes &amp; Sessions Log</span>
            </div>
            <h1 className="text-2xl font-black tracking-tight text-neutral-900">
              Recent Quotations &amp; Uploads
            </h1>
            <p className="text-xs text-neutral-500 mt-0.5">
              Access all processed insurance quotes, test sessions, and marketing comparisons in one place
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => fetchSessions()}
              className="text-xs font-semibold h-9 px-3 gap-1.5 cursor-pointer shadow-2xs"
            >
              <ArrowsClockwise size={14} weight="bold" className={loading ? "animate-spin" : ""} />
              <span>Refresh</span>
            </Button>
            <Button
              type="button"
              onClick={() => router.push("/upload" as Route)}
              className="text-xs font-bold h-9 px-4 bg-[#1b1717] hover:bg-black text-white gap-1.5 cursor-pointer shadow-2xs"
            >
              <Plus size={14} weight="bold" />
              <span>Upload New Quote</span>
            </Button>
          </div>
        </div>

        {/* Quick Filter Tabs */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 overflow-x-auto bg-neutral-100 p-1 rounded-xl w-fit border border-neutral-200/70">
            <button
              type="button"
              onClick={() => setActiveTab("all")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === "all" ? "bg-white text-neutral-900 shadow-2xs" : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              All Quotes ({stats.total})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("single")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === "single" ? "bg-white text-neutral-900 shadow-2xs" : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              Single Quotes ({stats.singles})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("comparison")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === "comparison"
                  ? "bg-amber-100 text-amber-950 border border-amber-300 shadow-2xs"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              Comparison Quotes ({stats.comparisons})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("test")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === "test"
                  ? "bg-purple-100 text-purple-950 border border-purple-300 shadow-2xs"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              Test Sessions ({stats.testQuotes})
            </button>
          </div>

          {/* Controls: Staff Filter & Search Box */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 w-full sm:w-auto">
            {/* Filter by Staff */}
            <div className="relative">
              <select
                aria-label="Filter quotations by staff member"
                value={staffFilter}
                onChange={(e) => setStaffFilter(e.target.value)}
                className="h-8.5 px-3 text-xs font-semibold rounded-xl border border-neutral-200 bg-white text-neutral-800 focus:outline-none focus:ring-1 focus:ring-neutral-900 shadow-2xs cursor-pointer w-full sm:w-auto"
              >
                <option value="all">👥 All Staff Members</option>
                {staffOptions.map((s) => (
                  <option key={s.id} value={s.id}>
                    👤 {s.name} ({s.email})
                  </option>
                ))}
              </select>
            </div>

            {/* Search Box */}
            <div className="relative w-full sm:w-80">
              <MagnifyingGlass size={15} weight="bold" className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search plate, chassis, client, or ref..."
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border border-neutral-200 bg-white focus:outline-none focus:ring-1 focus:ring-neutral-900 shadow-2xs"
              />
            </div>
          </div>
        </div>

        {/* Sessions Feed */}
        {loading ? (
          <div className="bg-white rounded-2xl border border-neutral-200/80 p-16 text-center text-xs text-neutral-500 shadow-2xs">
            <ArrowsClockwise size={24} className="animate-spin mx-auto mb-2 text-neutral-400" />
            <span>Loading quotes and sessions...</span>
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="bg-white rounded-2xl border-2 border-dashed border-neutral-200 p-16 text-center flex flex-col items-center justify-center gap-3">
            <div className="size-12 rounded-full bg-neutral-100 text-neutral-600 flex items-center justify-center">
              <Car size={24} weight="duotone" />
            </div>
            <h3 className="text-base font-bold text-neutral-900">No Quotes Found</h3>
            <p className="text-xs text-neutral-500 max-w-sm">
              {search
                ? `No sessions match "${search}". Try resetting the search.`
                : "No quotations recorded yet. Upload a schedule or quotation PDF to get started."}
            </p>
            {search && (
              <Button type="button" variant="secondary" size="sm" onClick={() => setSearch("")}>
                Clear Search
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredSessions.map((s) => {
              const vehicleDisplay = getVehicleDisplayName(s.vehicle_plate, s.chassis_no);
              const isChassis = vehicleDisplay.startsWith("Chassis:");
              const isBlank = vehicleDisplay === "No Plate (Blank)";
              const isComparison = Boolean(s.tenure_id);

              return (
                <div
                  key={s.id}
                  className="bg-white rounded-xl border border-neutral-200/80 hover:border-neutral-400 p-4 shadow-2xs hover:shadow-xs transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 group"
                >
                  {/* Left: Vehicle Plate / Chassis & Customer */}
                  <div className="flex items-start gap-3.5 min-w-[280px]">
                    <div className="size-10 rounded-xl bg-neutral-100 border border-neutral-200 flex items-center justify-center text-neutral-800 shrink-0 group-hover:bg-[#1b1717] group-hover:text-white transition-colors">
                      <Car size={20} weight="bold" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`font-mono font-black text-sm tracking-wide ${isBlank ? "text-neutral-400 italic" : "text-neutral-900"}`}>
                          {vehicleDisplay}
                        </span>
                        {isChassis && (
                          <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-amber-100 text-amber-900 border border-amber-200">
                            CHASSIS ONLY
                          </span>
                        )}
                        {isBlank && (
                          <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-neutral-200 text-neutral-700">
                            BLANK SESSION
                          </span>
                        )}
                        {s.is_test && (
                          <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-purple-100 text-purple-900 border border-purple-200">
                            TEST QUOTE
                          </span>
                        )}
                        {isComparison ? (
                          <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-amber-50 text-amber-800 border border-amber-200">
                            COMPARISON
                          </span>
                        ) : (
                          <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-blue-50 text-blue-800 border border-blue-200">
                            SINGLE QUOTE
                          </span>
                        )}
                      </div>

                      <p className="text-xs font-bold text-neutral-800 mt-1">
                        {s.insured_name || "Unassigned Customer"}
                      </p>

                      <div className="flex items-center gap-2 flex-wrap text-[11px] mt-1.5">
                        <span className="inline-flex items-center gap-1.5 bg-neutral-100/90 border border-neutral-200 px-2 py-0.5 rounded text-neutral-700">
                          <span className="text-[10px] uppercase font-bold text-neutral-400 tracking-wider">Uploaded</span>
                          <span className="font-semibold text-neutral-900">{s.created_by_email || s.created_by || "System"}</span>
                          <span className="text-neutral-400 font-mono text-[10px]">({formatDate(s.created_at)})</span>
                        </span>
                        {s.last_edited_by_email || s.last_edited_by ? (
                          <span className="inline-flex items-center gap-1.5 bg-amber-50/90 border border-amber-200 px-2 py-0.5 rounded text-amber-900">
                            <span className="text-[10px] uppercase font-bold text-amber-700 tracking-wider">Last Edited</span>
                            <span className="font-bold text-amber-950">{s.last_edited_by_email || s.last_edited_by}</span>
                            {s.last_edited_at && <span className="text-amber-700 font-mono text-[10px]">({formatDate(s.last_edited_at)})</span>}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>

                  {/* Middle: Insurer, Quotation Ref & Premium */}
                  <div className="flex-1 min-w-[220px]">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-extrabold text-neutral-900 px-2 py-0.5 rounded bg-neutral-100 border border-neutral-200">
                        {s.detected_company || "Unknown Insurer"}
                      </span>
                      {s.quotation_ref && (
                        <span className="font-mono text-xs font-bold text-blue-700">
                          {s.quotation_ref}
                        </span>
                      )}
                      {s.template_name && (
                        <span className="text-[10px] font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded flex items-center gap-1">
                          <FileText size={11} weight="bold" />
                          {s.template_name}
                        </span>
                      )}
                    </div>

                    <div className="mt-1 flex items-baseline gap-2">
                      {s.total_premium ? (
                        <span className="text-sm font-black font-mono text-emerald-700">
                          RM {s.total_premium}
                        </span>
                      ) : (
                        <span className="text-xs text-neutral-400 italic">No price calculated</span>
                      )}
                      {s.vehicle_model && (
                        <span className="text-[11px] text-neutral-500">
                          · {s.vehicle_model}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Right: Quick Action Buttons */}
                  <div className="flex items-center gap-2 shrink-0 flex-wrap">
                    {/* Direct Single Quote Review */}
                    <Link
                      href={`/sessions/${s.id}` as Route}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-neutral-100 hover:bg-neutral-200 text-neutral-800 text-xs font-bold transition-colors cursor-pointer"
                      title="Open quotation review and editor"
                    >
                      <span>Review &amp; Edit</span>
                    </Link>

                    {/* Direct Comparison Matrix if linked */}
                    {s.tenure_id && (
                      <Link
                        href={`/comparison?tenure_id=${s.tenure_id}` as Route}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-colors shadow-2xs cursor-pointer"
                        title="Open comparison matrix for this vehicle"
                      >
                        <Columns size={13} weight="bold" />
                        <span>Compare</span>
                        <ArrowRight size={12} weight="bold" />
                      </Link>
                    )}

                    {/* Direct PDF Download if available */}
                    <a
                      href={`/api/sessions/${s.id}/pdf?download=true`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-neutral-200 hover:bg-neutral-50 text-neutral-700 text-xs font-semibold transition-colors"
                      title="Download PDF quotation"
                    >
                      <FilePdf size={14} className="text-red-600" />
                      <span>PDF</span>
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}
