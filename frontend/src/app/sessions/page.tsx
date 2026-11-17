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
  FilePdf,
  ArrowRight,
  ShieldCheck,
  Plus,
  Flask,
  Trash,
  FileText,
  CaretLeft,
  CaretRight,
  FunnelSimple,
  X,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
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
  document_type?: string | null;
  policy_number?: string | null;
  insured_name?: string | null;
  vehicle_plate?: string | null;
  chassis_no?: string | null;
  vehicle_model?: string | null;
  total_premium?: string | null;
  quotation_status?: string;
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

interface TabCounts {
  all: number;
  live: number;
  quotations: number;
  covernotes: number;
  test: number;
}

type ActiveTab = "all" | "live" | "quotation" | "covernote" | "test";
type SortOption = "date_desc" | "edited_desc" | "vehicle" | "ref_desc";

const PAGE_SIZE = 50;

function formatRelativeOrExactDate(dateStr?: string | null): { relative: string; exact: string; bucket: string } {
  if (!dateStr) return { relative: "—", exact: "—", bucket: "Earlier" };
  try {
    const dt = new Date(dateStr);
    if (isNaN(dt.getTime())) return { relative: dateStr, exact: dateStr, bucket: "Earlier" };
    const now = new Date();
    const diffSec = Math.max(0, Math.floor((now.getTime() - dt.getTime()) / 1000));

    let relative = "";
    if (diffSec < 60) relative = "Just now";
    else if (diffSec < 3600) relative = `${Math.floor(diffSec / 60)}m ago`;
    else if (diffSec < 86400) relative = `${Math.floor(diffSec / 3600)}h ago`;
    else if (diffSec < 86400 * 7) relative = `${Math.floor(diffSec / 86400)}d ago`;

    const exact = dt.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

    const todayStr = now.toDateString();
    const yest = new Date(now);
    yest.setDate(now.getDate() - 1);
    const yestStr = yest.toDateString();

    let bucket = "Earlier";
    if (dt.toDateString() === todayStr) bucket = "Today";
    else if (dt.toDateString() === yestStr) bucket = "Yesterday";
    else if (diffSec < 86400 * 7) bucket = "Earlier This Week";

    return { relative: relative || exact, exact, bucket };
  } catch {
    return { relative: dateStr, exact: dateStr, bucket: "Earlier" };
  }
}

export default function SessionsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [tabCounts, setTabCounts] = useState<TabCounts>({
    all: 0,
    live: 0,
    quotations: 0,
    covernotes: 0,
    test: 0,
  });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [activeTab, setActiveTab] = useState<ActiveTab>("all");
  const [sortBy, setSortBy] = useState<SortOption>("date_desc");
  const [staffFilter, setStaffFilter] = useState<string>("all");
  const [companyFilter, setCompanyFilter] = useState<string>("all");
  const [staffOptions, setStaffOptions] = useState<StaffOption[]>([]);
  const [companyOptions, setCompanyOptions] = useState<string[]>([]);
  const [page, setPage] = useState(0);
  const [redetectingId, setRedetectingId] = useState<string | null>(null);
  const [purgeDialogOpen, setPurgeDialogOpen] = useState(false);
  const [purgingSandbox, setPurgingSandbox] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(0);
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchSessions = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.set("limit", String(PAGE_SIZE));
      params.set("offset", String(page * PAGE_SIZE));
      params.set("sort_by", sortBy);
      if (debouncedSearch) params.set("search", debouncedSearch);
      if (activeTab !== "all") params.set("type_filter", activeTab);
      if (staffFilter !== "all") params.set("staff_id", staffFilter);
      if (companyFilter !== "all") params.set("company", companyFilter);

      const res = await api<{
        sessions: SessionItem[];
        total: number;
        tab_counts?: TabCounts;
        filter_options?: { staff?: StaffOption[]; companies?: string[] };
      }>(`/sessions?${params.toString()}`);

      setSessions(res.sessions || []);
      setTotalCount(res.total || 0);
      if (res.tab_counts) setTabCounts(res.tab_counts);
      if (res.filter_options?.staff?.length) setStaffOptions(res.filter_options.staff);
      if (res.filter_options?.companies?.length) setCompanyOptions(res.filter_options.companies);
    } catch (err) {
      console.error("Failed to load sessions:", err);
      setSessions([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, activeTab, sortBy, staffFilter, companyFilter, page]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleRedetectSession = async (sessionId: string) => {
    setRedetectingId(sessionId);
    try {
      const res = await api<{ success: boolean; fields_count?: number }>(`/sessions/${sessionId}/rescan`, {
        method: "POST",
        body: JSON.stringify({ mode: "in_place", engine: "auto" }),
      });
      toast(
        res?.success
          ? `Re-detected quotation (${res.fields_count || 0} fields refreshed).`
          : "Re-detection completed.",
        "success"
      );
      await fetchSessions();
    } catch (err: any) {
      toast("Re-detection failed: " + (err?.message || "Server error"), "error");
    } finally {
      setRedetectingId(null);
    }
  };

  const handlePurgeTestSandbox = async () => {
    setPurgingSandbox(true);
    try {
      const res = await api<{ status: string; purged_count: number }>("/sessions/test-sandbox/purge", {
        method: "POST",
      });
      toast(`Cleared ${res?.purged_count || 0} test sandbox session(s) to Trash.`, "success");
      setPurgeDialogOpen(false);
      setPage(0);
      await fetchSessions();
    } catch (err: any) {
      toast("Failed to clear test sandbox: " + (err?.message || "Server error"), "error");
    } finally {
      setPurgingSandbox(false);
    }
  };

  const groupedSessions = useMemo(() => {
    if (sortBy !== "date_desc" && sortBy !== "edited_desc") {
      return [{ label: "Matching Sessions", items: sessions }];
    }
    const groups: Array<{ label: string; items: SessionItem[] }> = [];
    const map = new Map<string, SessionItem[]>();
    for (const item of sessions) {
      const refDate = sortBy === "edited_desc" ? (item.last_edited_at || item.created_at) : item.created_at;
      const { bucket } = formatRelativeOrExactDate(refDate);
      if (!map.has(bucket)) {
        const arr: SessionItem[] = [];
        map.set(bucket, arr);
        groups.push({ label: bucket, items: arr });
      }
      map.get(bucket)!.push(item);
    }
    return groups;
  }, [sessions, sortBy]);

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <AppShell>
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-6 space-y-5">
        {/* Header Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--rl-border)] pb-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mb-1">
              <ClockCounterClockwise size={15} weight="bold" />
              <span>Upload Activity &amp; Session Log</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-[var(--rl-text-strong)]">
              Recent Uploads &amp; Quotations
            </h1>
            <p className="text-xs text-[var(--rl-text-muted)] mt-0.5">
              Chronological feed of every uploaded quotation, issued cover note, and isolated sandbox test session.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {activeTab === "test" && tabCounts.test > 0 ? (
              <Button
                type="button"
                variant="danger"
                size="sm"
                icon={<Trash size={14} weight="bold" />}
                onClick={() => setPurgeDialogOpen(true)}
              >
                Empty Sandbox ({tabCounts.test})
              </Button>
            ) : null}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={<ArrowsClockwise size={14} weight="bold" className={loading ? "animate-spin" : ""} />}
              onClick={() => fetchSessions()}
            >
              Refresh
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              icon={<Plus size={14} weight="bold" />}
              onClick={() => router.push("/upload" as Route)}
            >
              Upload New PDF
            </Button>
          </div>
        </div>

        {/* Sandbox Isolation Notice when viewing Test Sessions */}
        {activeTab === "test" && (
          <Card className="p-4 border border-amber-300 bg-amber-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="size-8 rounded-[var(--rl-radius-sm)] bg-amber-600 text-white flex items-center justify-center shrink-0 mt-0.5">
                <Flask size={17} weight="fill" />
              </div>
              <div>
                <h2 className="text-xs font-bold uppercase tracking-wider text-amber-950">
                  Isolated Test Sandbox Dump (Zero Ledger Contamination)
                </h2>
                <p className="text-xs text-amber-900 mt-0.5">
                  Sessions uploaded in Test Mode use <code className="font-mono font-bold">TEST-RL</code> references and are strictly blocked from creating or modifying Monthly Renewal Ledger rows, Customer Records, or Vehicle Tracking.
                </p>
              </div>
            </div>
            {tabCounts.test > 0 && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<Trash size={13} weight="bold" />}
                onClick={() => setPurgeDialogOpen(true)}
                className="shrink-0 border-amber-300 text-amber-950 hover:bg-amber-100"
              >
                Clear All Test Sessions
              </Button>
            )}
          </Card>
        )}

        {/* Filter Tabs & Search/Sort Controls */}
        <div className="flex flex-col gap-3">
          <div
            role="tablist"
            aria-label="Session categories"
            className="flex flex-wrap items-center gap-1 bg-white p-1 rounded-[var(--rl-radius)] border border-[var(--rl-border)] shadow-2xs w-fit max-w-full"
          >
            {(
              [
                { key: "all", label: "All Uploads", count: tabCounts.all },
                { key: "live", label: "Live Production", count: tabCounts.live },
                { key: "quotation", label: "Quotations", count: tabCounts.quotations },
                { key: "covernote", label: "Cover Notes", count: tabCounts.covernotes },
                { key: "test", label: "Test Sandbox", count: tabCounts.test },
              ] as Array<{ key: ActiveTab; label: string; count: number }>
            ).map((tab) => {
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => {
                    setActiveTab(tab.key);
                    setPage(0);
                  }}
                  className={`shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--rl-radius-sm)] text-xs font-semibold transition-all cursor-pointer whitespace-nowrap ${
                    isActive
                      ? "bg-[var(--rl-black)] text-white shadow-2xs"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-neutral-100"
                  }`}
                >
                  <span className="shrink-0">{tab.label}</span>
                  <span
                    className={`shrink-0 px-1.5 py-0.5 rounded-[4px] font-mono tabular-nums text-[10px] font-bold leading-none ${
                      isActive ? "bg-white/20 text-white" : "bg-neutral-100 text-[var(--rl-text-muted)]"
                    }`}
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Search & Dropdown Filters */}
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Sort sessions"
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value as SortOption);
                setPage(0);
              }}
              className="h-9 px-2.5 text-xs font-semibold rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white text-[var(--rl-text-strong)] focus:outline-none focus:border-[var(--rl-black)] cursor-pointer"
            >
              <option value="date_desc">Sort: Newest Uploaded First</option>
              <option value="edited_desc">Sort: Recently Edited First</option>
              <option value="vehicle">Sort: Vehicle Plate (A–Z)</option>
              <option value="ref_desc">Sort: Quotation Reference</option>
            </select>

            <select
              aria-label="Filter by insurer"
              value={companyFilter}
              onChange={(e) => {
                setCompanyFilter(e.target.value);
                setPage(0);
              }}
              className="h-9 px-2.5 text-xs font-semibold rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white text-[var(--rl-text-strong)] focus:outline-none focus:border-[var(--rl-black)] cursor-pointer"
            >
              <option value="all">All Insurers</option>
              {companyOptions.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>

            <select
              aria-label="Filter by staff member"
              value={staffFilter}
              onChange={(e) => {
                setStaffFilter(e.target.value);
                setPage(0);
              }}
              className="h-9 px-2.5 text-xs font-semibold rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white text-[var(--rl-text-strong)] focus:outline-none focus:border-[var(--rl-black)] cursor-pointer"
            >
              <option value="all">All Staff</option>
              {staffOptions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>

            <div className="relative w-full sm:w-64">
              <MagnifyingGlass
                size={14}
                weight="bold"
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]"
              />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search plate, client, insurer, ref..."
                className="w-full h-9 pl-8 pr-7 text-xs rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white text-[var(--rl-text-strong)] focus:outline-none focus:border-[var(--rl-black)]"
              />
              {search ? (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  aria-label="Clear search"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] cursor-pointer"
                >
                  <X size={13} weight="bold" />
                </button>
              ) : null}
            </div>
          </div>
        </div>

        {/* Sessions Stream */}
        {loading ? (
          <Card className="p-14 text-center text-xs text-[var(--rl-text-muted)]">
            <ArrowsClockwise size={22} className="animate-spin mx-auto mb-2 text-[var(--rl-text-muted)]" />
            <span>Loading recent uploads...</span>
          </Card>
        ) : sessions.length === 0 ? (
          <Card className="p-14 text-center flex flex-col items-center justify-center gap-3">
            <div className="size-11 rounded-[var(--rl-radius)] bg-neutral-100 text-[var(--rl-text-strong)] flex items-center justify-center">
              <FunnelSimple size={22} weight="bold" />
            </div>
            <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">No Matching Sessions Found</h3>
            <p className="text-xs text-[var(--rl-text-muted)] max-w-sm">
              {debouncedSearch || companyFilter !== "all" || staffFilter !== "all"
                ? "No uploads match your active filters. Clear the filters to view all recent uploads."
                : activeTab === "test"
                ? "The Test Sandbox Dump is clean. Enable 'Test Upload Mode' when uploading a PDF to test without touching live records."
                : "Upload a quotation or policy schedule PDF to get started."}
            </p>
            {(debouncedSearch || companyFilter !== "all" || staffFilter !== "all") && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  setSearch("");
                  setCompanyFilter("all");
                  setStaffFilter("all");
                }}
              >
                Reset Filters
              </Button>
            )}
          </Card>
        ) : (
          <div className="space-y-5">
            {groupedSessions.map((group) => (
              <div key={group.label} className="space-y-2">
                <div className="sticky top-[56px] z-10 flex items-center justify-between bg-[var(--rl-bg)]/95 backdrop-blur-xs py-1.5 px-1">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                    {group.label}
                  </span>
                  <span className="text-[11px] font-mono text-[var(--rl-text-muted)]">
                    {group.items.length} {group.items.length === 1 ? "session" : "sessions"}
                  </span>
                </div>

                <div className="divide-y divide-[var(--rl-border)] rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white shadow-2xs overflow-hidden">
                  {group.items.map((s) => {
                    const vehicleDisplay = getVehicleDisplayName(s.vehicle_plate, s.chassis_no);
                    const isBlank = vehicleDisplay === "No Plate (Blank)";
                    const isCoverNote = s.document_type === "covernote";
                    const timeInfo = formatRelativeOrExactDate(s.created_at);

                    return (
                      <div
                        key={s.id}
                        className="p-3.5 hover:bg-neutral-50/80 transition-colors flex flex-col xl:flex-row xl:items-center justify-between gap-3"
                      >
                        {/* Left: Plate, Client & Upload Timestamp */}
                        <div className="flex items-start gap-3 min-w-0 flex-1">
                          <div className="size-9 rounded-[var(--rl-radius-sm)] bg-neutral-100 border border-[var(--rl-border)] flex items-center justify-center text-[var(--rl-text-strong)] shrink-0 mt-0.5">
                            {s.is_test ? (
                              <Flask size={18} weight="bold" className="text-amber-700" />
                            ) : isCoverNote ? (
                              <ShieldCheck size={18} weight="bold" className="text-emerald-700" />
                            ) : (
                              <Car size={18} weight="bold" />
                            )}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span
                                className={`font-mono font-bold text-sm ${
                                  isBlank ? "text-[var(--rl-text-muted)] italic" : "text-[var(--rl-text-strong)]"
                                }`}
                              >
                                {vehicleDisplay}
                              </span>
                              {s.is_test ? (
                                <Badge variant="warning">Sandbox Test</Badge>
                              ) : isCoverNote ? (
                                <Badge variant="success">Cover Note</Badge>
                              ) : (
                                <Badge variant="default">Quotation</Badge>
                              )}
                              {s.detected_company && (
                                <span className="text-[11px] font-bold text-[var(--rl-text-strong)] px-2 py-0.5 rounded-[var(--rl-radius-sm)] bg-neutral-100 border border-[var(--rl-border)]">
                                  {s.detected_company}
                                </span>
                              )}
                            </div>

                            <div className="flex items-center gap-2 flex-wrap mt-1 text-xs">
                              <span className="font-semibold text-[var(--rl-text-strong)] truncate max-w-[260px]">
                                {s.insured_name || "Unassigned Client"}
                              </span>
                              {s.vehicle_model && (
                                <span className="text-[var(--rl-text-muted)] truncate max-w-[220px]">
                                  · {s.vehicle_model}
                                </span>
                              )}
                            </div>

                            <div className="flex items-center gap-2 flex-wrap mt-1 text-[11px] text-[var(--rl-text-muted)]">
                              <span title={timeInfo.exact}>
                                Uploaded <strong className="text-[var(--rl-text-strong)]">{timeInfo.relative}</strong> ({timeInfo.exact}) by{" "}
                                <strong className="text-[var(--rl-text-strong)]">{s.created_by || "Staff"}</strong>
                              </span>
                              {s.filename && (
                                <span className="font-mono text-[10px] text-[var(--rl-text-muted)] truncate max-w-[220px]" title={s.filename}>
                                  · {s.filename}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Middle: Reference & Total Payable */}
                        <div className="flex items-center gap-4 lg:justify-end shrink-0">
                          <div className="text-left lg:text-right">
                            {s.quotation_ref && (
                              <div className="font-mono text-xs font-bold text-[var(--rl-text-strong)]">
                                {s.quotation_ref}
                              </div>
                            )}
                            {s.total_premium ? (
                              <div className="font-mono text-sm font-bold text-[var(--rl-red)]">
                                RM {s.total_premium}
                              </div>
                            ) : (
                              <div className="text-[11px] text-[var(--rl-text-muted)] italic">Pending price</div>
                            )}
                          </div>

                          {/* Right: Action Buttons */}
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              loading={redetectingId === s.id}
                              icon={<ArrowsClockwise size={13} weight="bold" />}
                              onClick={() => handleRedetectSession(s.id)}
                              title="Re-run AI extraction on this uploaded PDF"
                            >
                              Re-detect
                            </Button>

                            <Link
                              href={`/sessions/${s.id}` as Route}
                              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-[var(--rl-radius-sm)] bg-[var(--rl-black)] hover:bg-black text-white text-xs font-semibold transition-colors"
                            >
                              <FileText size={13} weight="bold" />
                              <span>Workspace</span>
                            </Link>

                            {s.tenure_id && !s.is_test && (
                              <Link
                                href={`/comparison?tenure_id=${s.tenure_id}` as Route}
                                className="inline-flex items-center gap-1 h-8 px-2.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white hover:bg-neutral-50 text-[var(--rl-text-strong)] text-xs font-semibold transition-colors"
                                title="Open multi-insurer comparison matrix for this vehicle"
                              >
                                <Columns size={13} weight="bold" />
                                <span>Compare</span>
                                <ArrowRight size={11} weight="bold" />
                              </Link>
                            )}

                            {s.uploaded_file_id && (
                              <a
                                href={`/api/uploaded-files/${s.uploaded_file_id}/content`}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 h-8 px-2.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white hover:bg-neutral-50 text-[var(--rl-text-strong)] text-xs font-semibold transition-colors"
                                title="Open source PDF in new tab"
                              >
                                <FilePdf size={14} weight="bold" className="text-[var(--rl-red)]" />
                                <span>Source PDF</span>
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}

            {/* Pagination Footer */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2 border-t border-[var(--rl-border)] text-xs text-[var(--rl-text-muted)]">
              <span>
                Showing <strong className="text-[var(--rl-text-strong)]">{page * PAGE_SIZE + 1}</strong>–
                <strong className="text-[var(--rl-text-strong)]">
                  {Math.min((page + 1) * PAGE_SIZE, totalCount)}
                </strong>{" "}
                of <strong className="text-[var(--rl-text-strong)]">{totalCount}</strong> sessions
              </span>

              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={page === 0}
                  icon={<CaretLeft size={13} weight="bold" />}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  Previous
                </Button>
                <span className="font-mono text-xs font-semibold text-[var(--rl-text-strong)] px-2">
                  Page {page + 1} / {totalPages}
                </span>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={page + 1 >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <span>Next</span>
                  <CaretRight size={13} weight="bold" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Radix Confirmation Dialog for Emptying Test Sandbox */}
      <Dialog
        open={purgeDialogOpen}
        onOpenChange={setPurgeDialogOpen}
        title="Empty Test Sandbox Dump?"
        description={`This will move all ${tabCounts.test} isolated Test Sandbox session(s) to Trash. Live production quotations and customer records will not be affected.`}
        onConfirm={handlePurgeTestSandbox}
        confirmLabel="Empty Sandbox"
        confirmVariant="danger"
        loading={purgingSandbox}
      />
    </AppShell>
  );
}
