"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowsClockwise,
  ArrowSquareOut,
  CaretDown,
  CaretUp,
  Check,
  CheckCircle,
  Clock,
  Copy,
  DownloadSimple,
  FilePdf,
  MagnifyingGlass,
  NotePencil,
  PencilSimpleLine,
  Sparkle,
  Table,
  Target,
  Trash,
  User,
  X,
  XCircle,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { PageLoading } from "@/components/ui/page-loading";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { api, apiRaw } from "@/lib/api";
import { useToast } from "@/components/ui/toast";

const PAGE_SIZE = 50;

type Session = {
  id: string;
  draft_id: string;
  uploaded_file_id: string;
  filename: string;
  detected_company?: string | null;
  status: string;
  draft_status: string;
  insured_name?: string | null;
  vehicle_plate?: string | null;
  vehicle_model?: string | null;
  total_premium?: string | null;
  quotation_ref?: string | null;
  quotation_status?: string | null;
  miss_reason?: string | null;
  coverage_start_date?: string | null;
  coverage_end_date?: string | null;
  created_at: string;
  updated_at: string;
  created_by?: string;
  created_by_email?: string;
  last_edited_by?: string | null;
  last_edited_by_email?: string | null;
  last_edited_at?: string | null;
  is_edited?: boolean;
  is_test?: boolean;
};

type UserOption = {
  id: string;
  name: string;
  email: string;
  role?: string;
};

type FilterOptions = {
  companies: string[];
  users: UserOption[];
  staff?: UserOption[];
};

interface VehicleGroup {
  plate: string;
  customerName: string;
  vehicleModel: string;
  sessions: Session[];
}

function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const day = d.getDate().toString().padStart(2, "0");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"];
  const month = months[d.getMonth()];
  const year = d.getFullYear();
  const hours = d.getHours().toString().padStart(2, "0");
  const mins = d.getMinutes().toString().padStart(2, "0");
  const secs = d.getSeconds().toString().padStart(2, "0");
  return `${day} ${month} ${year}, ${hours}:${mins}:${secs}`;
}

function formatDateHeader(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "Unknown Date";
  const day = d.getDate().toString().padStart(2, "0");
  const months = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  const month = months[d.getMonth()];
  const year = d.getFullYear();
  return `${day} ${month} ${year}`;
}

function groupSessionsByVehicle(sessions: Session[]): VehicleGroup[] {
  const map = new Map<string, VehicleGroup>();

  for (const s of sessions) {
    const rawPlate = (s.vehicle_plate || "").trim().toUpperCase();
    const key = rawPlate || "__NO_PLATE__";

    if (!map.has(key)) {
      map.set(key, {
        plate: rawPlate,
        customerName: s.insured_name || "",
        vehicleModel: s.vehicle_model || "",
        sessions: [],
      });
    }

    const group = map.get(key)!;
    if (!group.customerName && s.insured_name) {
      group.customerName = s.insured_name;
    }
    if (!group.vehicleModel && s.vehicle_model) {
      group.vehicleModel = s.vehicle_model;
    }
    group.sessions.push(s);
  }

  const list = Array.from(map.values());
  list.sort((a, b) => {
    if (!a.plate && b.plate) return 1;
    if (a.plate && !b.plate) return -1;
    return 0;
  });
  return list;
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [total, setTotal] = useState(0);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({ companies: [], users: [] });

  // Filters
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [company, setCompany] = useState("");
  const [userId, setUserId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [sortBy, setSortBy] = useState("date_desc");

  // States
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Session | null>(null);
  const [pendingBulkDelete, setPendingBulkDelete] = useState(false);
  const [pendingRescan, setPendingRescan] = useState<Session | null>(null);
  const [rescanning, setRescanning] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [expandedVehicles, setExpandedVehicles] = useState<Set<string>>(new Set());
  const { toast } = useToast();

  // Fleet & Bulk Action States
  const [downloadingZip, setDownloadingZip] = useState(false);
  const [batchStatusOpen, setBatchStatusOpen] = useState(false);
  const [batchStatusTarget, setBatchStatusTarget] = useState<"hit" | "miss">("hit");
  const [batchCoverageStart, setBatchCoverageStart] = useState(() => new Date().toISOString().slice(0, 10));
  const [batchCoverageEnd, setBatchCoverageEnd] = useState(() => {
    const nextYear = new Date();
    nextYear.setFullYear(nextYear.getFullYear() + 1);
    return nextYear.toISOString().slice(0, 10);
  });
  const [batchMissReason, setBatchMissReason] = useState("Competitor cheaper rate");
  const [batchUpdating, setBatchUpdating] = useState(false);

  async function handleRescanConfirm(
    targetSession: Session,
    mode: "in_place" | "new_session",
    engine: "auto" | "native" | "ai"
  ) {
    setRescanning(targetSession.id);
    try {
      const res = await api<{
        success: boolean;
        session_id: string;
        quotation_ref: string;
        mode: string;
        engine_used: string;
        detected_company?: string;
        message: string;
      }>(`/sessions/${targetSession.id}/rescan`, {
        method: "POST",
        body: JSON.stringify({ mode, engine }),
      });

      toast(
        mode === "new_session"
          ? (res.message || `New session created (${res.quotation_ref}).`)
          : (res.message || `Quotation ${res.quotation_ref} renewed successfully.`),
        "success"
      );

      setPendingRescan(null);

      if (mode === "new_session" && res.session_id) {
        window.open(`/sessions/${res.session_id}`, "_blank");
      }

      await load(true);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not rescan session.", "error");
    } finally {
      setRescanning(null);
    }
  }

  async function load(
    reset: boolean,
    overrides?: {
      searchTerm?: string;
      companyFilter?: string;
      userFilter?: string;
      statusVal?: string;
      typeVal?: string;
      sortVal?: string;
    }
  ) {
    if (reset) setLoading(true);
    else setLoadingMore(true);
    setError("");
    try {
      const offset = reset ? 0 : sessions.length;
      const params = new URLSearchParams();
      params.set("limit", String(PAGE_SIZE));
      params.set("offset", String(offset));

      const s = overrides?.searchTerm !== undefined ? overrides.searchTerm : appliedSearch;
      if (s) params.set("search", s);

      const c = overrides?.companyFilter !== undefined ? overrides.companyFilter : company;
      if (c) params.set("company", c);

      const u = overrides?.userFilter !== undefined ? overrides.userFilter : userId;
      if (u) params.set("user_id", u);

      const stat = overrides?.statusVal !== undefined ? overrides.statusVal : statusFilter;
      if (stat) params.set("status", stat);

      const t = overrides?.typeVal !== undefined ? overrides.typeVal : typeFilter;
      if (t) params.set("type_filter", t);

      const srt = overrides?.sortVal !== undefined ? overrides.sortVal : sortBy;
      if (srt) params.set("sort_by", srt);

      const result = await api<{
        sessions: Session[];
        total: number;
        filter_options: FilterOptions;
      }>(`/sessions?${params.toString()}`);

      setSessions((current) => (reset ? result.sessions : [...current, ...result.sessions]));
      setTotal(result.total);

      if (offset === 0 && result.filter_options) {
        const rawUsers = result.filter_options.users || result.filter_options.staff || [];
        setFilterOptions((prev) => ({
          companies: result.filter_options.companies?.length ? result.filter_options.companies : prev.companies,
          users: rawUsers.length ? rawUsers : prev.users,
        }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load sessions.");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  function handleSearchSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSelected(new Set());
    const term = search.trim();
    setAppliedSearch(term);
    load(true, { searchTerm: term });
  }

  function handleClearSearch() {
    setSearch("");
    setAppliedSearch("");
    setSelected(new Set());
    load(true, { searchTerm: "" });
  }

  function handleCompanyChange(val: string) {
    setCompany(val);
    setSelected(new Set());
    load(true, { companyFilter: val });
  }

  function handleUserChange(val: string) {
    setUserId(val);
    setSelected(new Set());
    load(true, { userFilter: val });
  }

  function handleStatusChange(val: string) {
    setStatusFilter(val);
    setSelected(new Set());
    load(true, { statusVal: val });
  }

  function handleTypeChange(val: string) {
    setTypeFilter(val);
    setSelected(new Set());
    load(true, { typeVal: val });
  }

  function handleSortChange(val: string) {
    setSortBy(val);
    setSelected(new Set());
    load(true, { sortVal: val });
  }

  function handleResetAllFilters() {
    setSearch("");
    setAppliedSearch("");
    setCompany("");
    setUserId("");
    setStatusFilter("");
    setTypeFilter("");
    setSortBy("date_desc");
    setSelected(new Set());
    load(true, {
      searchTerm: "",
      companyFilter: "",
      userFilter: "",
      statusVal: "",
      typeVal: "",
      sortVal: "date_desc",
    });
  }

  function copyText(text: string, key: string) {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  }

  function toggleVehicleExpand(plateKey: string) {
    setExpandedVehicles((prev) => {
      const next = new Set(prev);
      if (next.has(plateKey)) next.delete(plateKey);
      else next.add(plateKey);
      return next;
    });
  }

  async function remove(session: Session) {
    setDeleting(session.id);
    setError("");
    try {
      await api(`/records/${session.uploaded_file_id}`, { method: "DELETE" });
      toast("Session moved to Trash.", "success");
      setPendingDelete(null);
      await load(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete session.");
    } finally {
      setDeleting(null);
    }
  }

  async function removeSelected() {
    const ids = sessions.filter((s) => selected.has(s.id)).map((s) => s.id);
    if (!ids.length) return;
    setDeleting("bulk");
    setError("");
    try {
      await api("/sessions/bulk-delete", { method: "POST", body: JSON.stringify({ item_ids: ids }) });
      toast(`${ids.length} session${ids.length > 1 ? "s" : ""} deleted forever.`, "success");
      setSelected(new Set());
      setPendingBulkDelete(false);
      await load(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete sessions.");
    } finally {
      setDeleting(null);
    }
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selected.size === sessions.length && sessions.length > 0) {
      setSelected(new Set());
    } else {
      setSelected(new Set(sessions.map((s) => s.id)));
    }
  }

  // Fleet & Bulk Action Handlers
  function copySelectedPdfLinks() {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const links = Array.from(selected).map((id) => `${origin}/api/sessions/${id}/pdf`);
    navigator.clipboard.writeText(links.join("\n"));
    toast(`Copied ${links.length} PDF link${links.length > 1 ? "s" : ""} to clipboard.`, "success");
  }

  function copySelectedFleetSummary() {
    const selectedSessions = sessions.filter((s) => selected.has(s.id));
    if (!selectedSessions.length) return;
    const origin = typeof window !== "undefined" ? window.location.origin : "";

    const headers = [
      "Vehicle Plate",
      "Customer / Fleet",
      "Vehicle Model",
      "Insurer",
      "Premium (RM)",
      "Quotation Status",
      "Quotation Ref",
      "PDF Direct Link",
    ];
    const rows = selectedSessions.map((s) => [
      s.vehicle_plate || "—",
      s.insured_name || "—",
      s.vehicle_model || "—",
      s.detected_company || "—",
      s.total_premium || "—",
      (s.quotation_status || s.status || "pending").toUpperCase(),
      s.quotation_ref || "—",
      `${origin}/api/sessions/${s.id}/pdf`,
    ]);

    const tsvText = [headers.join("\t"), ...rows.map((r) => r.join("\t"))].join("\n");
    navigator.clipboard.writeText(tsvText);
    toast(
      `Copied summary table for ${selectedSessions.length} quotation(s) (ready for Excel/Sheets or WhatsApp).`,
      "success"
    );
  }

  async function downloadSelectedZip() {
    if (selected.size === 0) return;
    setDownloadingZip(true);
    try {
      toast(`Preparing ZIP archive for ${selected.size} quotation(s)...`, "info");
      const res = await apiRaw("/sessions/bulk-download-zip", {
        method: "POST",
        body: JSON.stringify({ session_ids: Array.from(selected) }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson?.error?.message || errJson?.detail || "Failed to generate ZIP archive.");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = res.headers.get("Content-Disposition");
      let filename = `Risklocker_Quotations_${new Date().toISOString().slice(0, 10)}.zip`;
      if (disposition && disposition.includes("filename=")) {
        const match = disposition.match(/filename="?([^"]+)"?/);
        if (match && match[1]) filename = match[1];
      }
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast(`Downloaded ${filename} successfully!`, "success");
    } catch (err: any) {
      toast(err?.message || "Failed to download ZIP archive.", "error");
    } finally {
      setDownloadingZip(false);
    }
  }

  async function handleBatchStatusSubmit() {
    if (selected.size === 0) return;
    setBatchUpdating(true);
    try {
      const res = await api<{ updated_count: number; error_count: number; errors: string[] }>(
        "/sessions/bulk-status",
        {
          method: "POST",
          body: JSON.stringify({
            session_ids: Array.from(selected),
            status: batchStatusTarget,
            coverage_start_date: batchStatusTarget === "hit" ? batchCoverageStart : undefined,
            coverage_end_date: batchStatusTarget === "hit" ? batchCoverageEnd : undefined,
            miss_reason: batchStatusTarget === "miss" ? batchMissReason : undefined,
          }),
        }
      );
      toast(
        `Successfully updated ${res.updated_count} quotation(s) to ${batchStatusTarget.toUpperCase()}.${
          batchStatusTarget === "hit" ? " Competitor quotes automatically marked as superseded." : ""
        }`,
        "success"
      );
      setBatchStatusOpen(false);
      setSelected(new Set());
      await load(true);
    } catch (err: any) {
      toast(err?.message || "Failed to update batch quotation status.", "error");
    } finally {
      setBatchUpdating(false);
    }
  }

  useEffect(() => {
    load(true).catch((err) => setError(err instanceof Error ? err.message : "Could not load sessions."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isVehicleView = sortBy === "vehicle";
  const isTimelineView = sortBy === "date_desc" || sortBy === "date_asc";

  const vehicleGroups = isVehicleView ? groupSessionsByVehicle(sessions) : [];

  const dateGroups: Record<string, Session[]> = {};
  if (isTimelineView) {
    for (const s of sessions) {
      const label = formatDateHeader(s.created_at);
      if (!dateGroups[label]) dateGroups[label] = [];
      dateGroups[label].push(s);
    }
  }

  const hasActiveFilters = Boolean(
    appliedSearch || company || userId || statusFilter || typeFilter || sortBy !== "date_desc"
  );
  const allSelected = sessions.length > 0 && selected.size === sessions.length;

  return (
    <AppShell>
      <section className="grid gap-6">
        {/* Header Title & Bulk Action */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)] tracking-tight">
              Quotation Sessions
            </h1>
            <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
              Browse quotations grouped by vehicle, inspect insurer rate comparisons, and track staff authorship.
            </p>
          </div>
          {selected.size > 0 ? (
            <div className="flex flex-wrap items-center gap-2 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-2 shadow-sm animate-in fade-in">
              <span className="text-[12px] font-bold text-[var(--rl-text-strong)] px-2.5 py-1 rounded bg-[var(--rl-bg)] border border-[var(--rl-border)]">
                {selected.size} selected
              </span>

              <Button
                variant="ghost"
                size="sm"
                icon={<Copy size={15} weight="bold" />}
                onClick={copySelectedPdfLinks}
                title="Copy newline-separated PDF links to clipboard"
              >
                Copy PDF Links
              </Button>

              <Button
                variant="ghost"
                size="sm"
                icon={<Table size={15} weight="bold" />}
                onClick={copySelectedFleetSummary}
                title="Copy structured fleet summary table for Excel, Sheets, or WhatsApp"
              >
                Copy Fleet Table
              </Button>

              <Button
                variant="ghost"
                size="sm"
                loading={downloadingZip}
                icon={<DownloadSimple size={15} weight="bold" />}
                onClick={downloadSelectedZip}
                title="Download all selected quotation PDFs in a single ZIP archive"
              >
                Download ZIP
              </Button>

              <Button
                variant="secondary"
                size="sm"
                icon={<Target size={15} weight="bold" />}
                onClick={() => setBatchStatusOpen(true)}
                className="font-medium text-emerald-700 dark:text-emerald-300"
              >
                Batch Status
              </Button>

              <div className="h-4 w-px bg-[var(--rl-border)] mx-1" />

              <Button
                variant="danger"
                size="sm"
                loading={deleting === "bulk"}
                icon={<Trash aria-hidden="true" size={15} weight="bold" />}
                onClick={() => setPendingBulkDelete(true)}
              >
                Delete ({selected.size})
              </Button>

              <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
                Deselect all
              </Button>
            </div>
          ) : null}
        </div>

        {/* Top Filter Toolbar */}
        <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-sm">
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Search Input Form */}
            <form onSubmit={handleSearchSubmit} className="flex flex-1 min-w-[240px] items-center gap-1.5">
              <div className="relative flex-1">
                <Input
                  className="h-9 pr-8 text-[13px]"
                  placeholder="Search vehicle plate, customer, quotation ref…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                {search ? (
                  <button
                    type="button"
                    onClick={handleClearSearch}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    title="Clear search"
                  >
                    <X size={14} weight="bold" />
                  </button>
                ) : null}
              </div>
              <Button type="submit" variant="secondary" size="sm" icon={<MagnifyingGlass weight="bold" size={15} />}>
                Search
              </Button>
            </form>

            {/* Insurer Company Dropdown */}
            <select
              aria-label="Filter by Insurance Company"
              value={company}
              onChange={(e) => handleCompanyChange(e.target.value)}
              className="h-9 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2.5 text-[13px] font-medium text-[var(--rl-text-strong)] transition-colors hover:border-[var(--rl-text-muted)] focus:border-[var(--rl-black)] focus:outline-none"
            >
              <option value="">All Insurers</option>
              {filterOptions.companies.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>

            {/* Users Dropdown (Shows actual user names: Admin, Nina, Alex) */}
            <select
              aria-label="Filter by User"
              value={userId}
              onChange={(e) => handleUserChange(e.target.value)}
              className="h-9 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2.5 text-[13px] font-medium text-[var(--rl-text-strong)] transition-colors hover:border-[var(--rl-text-muted)] focus:border-[var(--rl-black)] focus:outline-none"
            >
              <option value="">All Users</option>
              {filterOptions.users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>

            {/* Status Dropdown: Strictly real system draft statuses */}
            <select
              aria-label="Filter by Status"
              value={statusFilter}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="h-9 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2.5 text-[13px] font-medium text-[var(--rl-text-strong)] transition-colors hover:border-[var(--rl-text-muted)] focus:border-[var(--rl-black)] focus:outline-none"
            >
              <option value="">All Statuses</option>
              <option value="Ready">Ready</option>
              <option value="Check Needed">Check Needed</option>
              <option value="Generated">Generated</option>
              <option value="Preparing">Preparing</option>
            </select>

            {/* Type Dropdown: All Uploads, Live Only, Test Only */}
            <select
              aria-label="Filter by Upload Type"
              value={typeFilter}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="h-9 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2.5 text-[13px] font-medium text-[var(--rl-text-strong)] transition-colors hover:border-[var(--rl-text-muted)] focus:border-[var(--rl-black)] focus:outline-none"
            >
              <option value="">All Uploads</option>
              <option value="live">Live Only</option>
              <option value="test">Test Uploads Only</option>
            </select>

            {/* View / Sort Dropdown */}
            <select
              aria-label="View and sort mode"
              value={sortBy}
              onChange={(e) => handleSortChange(e.target.value)}
              className="h-9 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2.5 text-[13px] font-semibold text-[var(--rl-text-strong)] transition-colors hover:border-[var(--rl-text-muted)] focus:border-[var(--rl-black)] focus:outline-none"
            >
              <option value="date_desc">Newest Upload (Timeline)</option>
              <option value="vehicle">Group by Vehicle</option>
              <option value="date_asc">Oldest Upload</option>
              <option value="customer_asc">Customer Name (A-Z)</option>
              <option value="ref_asc">Quote Ref (A-Z)</option>
            </select>

            {/* Reset Filters Button */}
            {hasActiveFilters ? (
              <Button
                variant="ghost"
                size="sm"
                icon={<X size={14} weight="bold" />}
                onClick={handleResetAllFilters}
                className="text-[13px] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              >
                Reset
              </Button>
            ) : null}
          </div>

          {/* Active Summary & Select All Bar */}
          <div className="mt-3 flex flex-wrap items-center justify-between border-t border-[var(--rl-border)]/60 pt-2.5 text-[13px] text-[var(--rl-text-muted)]">
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  aria-label="Select all sessions on page"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  className="h-4 w-4 rounded accent-[var(--rl-red)] cursor-pointer"
                />
                <span className="font-medium text-[var(--rl-text)]">Select all on page</span>
              </label>
              {isVehicleView && vehicleGroups.length > 0 ? (
                <span className="text-[var(--rl-text-muted)]">
                  • Grouped under <strong className="text-[var(--rl-text-strong)]">{vehicleGroups.length}</strong> vehicles
                </span>
              ) : null}
            </div>
            <div>
              {!loading ? (
                <span>
                  Showing <strong className="text-[var(--rl-text-strong)]">{sessions.length}</strong> of{" "}
                  <strong className="text-[var(--rl-text-strong)]">{total}</strong> quotation{total === 1 ? "" : "s"}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {/* Error Notification */}
        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        {/* Content Area */}
        {loading ? (
          <PageLoading />
        ) : sessions.length === 0 && !error ? (
          <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-12 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--rl-bg)] text-[var(--rl-text-muted)]">
              <MagnifyingGlass size={24} weight="bold" />
            </div>
            <p className="font-bold text-[16px] text-[var(--rl-text-strong)]">
              {hasActiveFilters ? "No matching quotations found." : "No quotation sessions yet."}
            </p>
            <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
              {hasActiveFilters
                ? "Try adjusting your search terms or resetting filters."
                : "Upload a quotation PDF from the Upload page to start a new session."}
            </p>
            {hasActiveFilters ? (
              <div className="mt-4">
                <Button variant="secondary" size="sm" onClick={handleResetAllFilters}>
                  Clear all filters
                </Button>
              </div>
            ) : null}
          </div>
        ) : isVehicleView ? (
          /* =========================================================================
             VIEW MODE 1: GROUP BY VEHICLE (All quotes for JMC8218 grouped together)
             ========================================================================= */
          <div className="grid gap-5">
            {vehicleGroups.map((vg) => {
              const isPlateMissing = !vg.plate;
              const plateKey = vg.plate || "NO_PLATE";
              const isExpanded = expandedVehicles.has(plateKey);

              // If vehicle has more than 3 quotes, collapse older ones unless expanded
              const maxInitial = 2;
              const hasManyQuotes = vg.sessions.length > maxInitial;
              const visibleSessions = hasManyQuotes && !isExpanded ? vg.sessions.slice(0, maxInitial) : vg.sessions;
              const hiddenCount = vg.sessions.length - visibleSessions.length;

              // Distinct companies that quoted for this car
              const distinctCompanies = Array.from(
                new Set(vg.sessions.map((s) => s.detected_company).filter(Boolean))
              );

              return (
                <div
                  key={plateKey}
                  className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-sm overflow-hidden"
                >
                  {/* Vehicle Dossier Header */}
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] bg-[var(--rl-bg)]/50 px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2.5">
                      {/* Monospace Vehicle Plate Badge */}
                      <span className="inline-flex items-center font-mono text-[14px] font-bold tracking-wider px-2.5 py-1 rounded bg-[var(--rl-surface)] text-[var(--rl-text-strong)] border border-[var(--rl-border-strong)] shadow-xs">
                        {isPlateMissing ? "[ UNASSIGNED VEHICLE ]" : `[ ${vg.plate} ]`}
                      </span>

                      {!isPlateMissing && (
                        <button
                          type="button"
                          onClick={() => copyText(vg.plate, `plate_${plateKey}`)}
                          className="text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] p-1 rounded hover:bg-[var(--rl-surface)] transition-colors"
                          title="Copy vehicle plate"
                        >
                          {copiedKey === `plate_${plateKey}` ? (
                            <Check size={14} className="text-emerald-600 font-bold" />
                          ) : (
                            <Copy size={14} />
                          )}
                        </button>
                      )}

                      {/* Insured Customer Name */}
                      {vg.customerName ? (
                        <span className="text-[15px] font-bold text-[var(--rl-text-strong)]">
                          {vg.customerName}
                        </span>
                      ) : null}

                      {/* Vehicle Model */}
                      {vg.vehicleModel ? (
                        <>
                          <span className="text-[var(--rl-text-muted)]">•</span>
                          <span className="text-[13px] font-medium text-[var(--rl-text)]">
                            {vg.vehicleModel}
                          </span>
                        </>
                      ) : null}
                    </div>

                    {/* Right side: Quotation Count & Insurer Summary */}
                    <div className="flex flex-wrap items-center gap-2">
                      {distinctCompanies.length > 0 && (
                        <div className="hidden sm:flex items-center gap-1">
                          {distinctCompanies.map((comp) => (
                            <span
                              key={comp}
                              className="text-[11px] font-bold px-2 py-0.5 rounded-[var(--rl-radius-sm)] bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-2xs tracking-wide"
                            >
                              {comp}
                            </span>
                          ))}
                        </div>
                      )}

                      <span className="text-[12px] font-bold text-[var(--rl-text-muted)] bg-[var(--rl-surface)] px-2.5 py-1 rounded border border-[var(--rl-border)]">
                        {vg.sessions.length} quotation{vg.sessions.length === 1 ? "" : "s"}
                      </span>
                    </div>
                  </div>

                  {/* Vehicle Quotes Rows */}
                  <div className="divide-y divide-[var(--rl-border)]/60">
                    {visibleSessions.map((s) => (
                      <QuotationRow
                        key={s.id}
                        session={s}
                        isSelected={selected.has(s.id)}
                        isDeleting={deleting === s.id}
                        isRescanning={rescanning === s.id}
                        onToggleSelect={() => toggleSelect(s.id)}
                        onDeleteClick={() => setPendingDelete(s)}
                        onRescanClick={() => setPendingRescan(s)}
                        onCopyRef={(ref) => copyText(ref, `ref_${s.id}`)}
                        isRefCopied={copiedKey === `ref_${s.id}`}
                      />
                    ))}
                  </div>

                  {/* Expand / Collapse Footer for Cars with Many Quotes */}
                  {hasManyQuotes && (
                    <div className="border-t border-[var(--rl-border)]/70 bg-[var(--rl-bg)]/30 px-4 py-2 text-center">
                      <button
                        type="button"
                        onClick={() => toggleVehicleExpand(plateKey)}
                        className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] transition-colors"
                      >
                        {isExpanded ? (
                          <>
                            <CaretUp size={14} weight="bold" />
                            Show less
                          </>
                        ) : (
                          <>
                            <CaretDown size={14} weight="bold" />
                            Show all {vg.sessions.length} quotations ({hiddenCount} more)
                          </>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : isTimelineView ? (
          /* =========================================================================
             VIEW MODE 2: TIMELINE BY DATE (Chronological daily feed)
             ========================================================================= */
          Object.entries(dateGroups).map(([date, items]) => (
            <div key={date} className="grid gap-2.5">
              <h2 className="flex items-center gap-2 text-[12px] font-bold text-[var(--rl-text-muted)] uppercase tracking-wider">
                <span>{date}</span>
                <span className="h-px flex-1 bg-[var(--rl-border)]" />
                <span className="font-mono text-[11px] lowercase tracking-normal">
                  {items.length} quotation{items.length === 1 ? "" : "s"}
                </span>
              </h2>

              <div className="grid gap-2.5">
                {items.map((s) => (
                  <QuotationCard
                    key={s.id}
                    session={s}
                    isSelected={selected.has(s.id)}
                    isDeleting={deleting === s.id}
                    isRescanning={rescanning === s.id}
                    onToggleSelect={() => toggleSelect(s.id)}
                    onDeleteClick={() => setPendingDelete(s)}
                    onRescanClick={() => setPendingRescan(s)}
                    onCopyRef={(ref) => copyText(ref, `ref_${s.id}`)}
                    isRefCopied={copiedKey === `ref_${s.id}`}
                  />
                ))}
              </div>
            </div>
          ))
        ) : (
          /* =========================================================================
             VIEW MODE 3: FLAT LIST (Sorted by Customer Name or Quotation Ref)
             ========================================================================= */
          <div className="grid gap-2.5">
            {sessions.map((s) => (
              <QuotationCard
                key={s.id}
                session={s}
                isSelected={selected.has(s.id)}
                isDeleting={deleting === s.id}
                isRescanning={rescanning === s.id}
                onToggleSelect={() => toggleSelect(s.id)}
                onDeleteClick={() => setPendingDelete(s)}
                onRescanClick={() => setPendingRescan(s)}
                onCopyRef={(ref) => copyText(ref, `ref_${s.id}`)}
                isRefCopied={copiedKey === `ref_${s.id}`}
              />
            ))}
          </div>
        )}

        {/* Load More Pagination */}
        {!loading && sessions.length < total ? (
          <div className="flex justify-center pt-2">
            <Button variant="secondary" loading={loadingMore} onClick={() => load(false)}>
              Load more ({sessions.length} of {total})
            </Button>
          </div>
        ) : null}
      </section>

      {/* Single Delete Confirmation */}
      {pendingDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => {
            if (!open) setPendingDelete(null);
          }}
          title={`Delete quotation session?`}
          message={`Are you sure you want to delete quotation "${pendingDelete.insured_name || pendingDelete.filename}" (${pendingDelete.vehicle_plate || "No plate"})? This session moves to Trash and can be restored later.`}
          loading={deleting === pendingDelete.id}
          onConfirm={() => remove(pendingDelete)}
        />
      ) : null}

      {/* Bulk Delete Confirmation */}
      {pendingBulkDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => {
            if (!open) setPendingBulkDelete(false);
          }}
          title={`Delete ${selected.size} selected quotation${selected.size > 1 ? "s" : ""}?`}
          message="Selected sessions will be permanently deleted from the active workspace. This action cannot be undone."
          loading={deleting === "bulk"}
          onConfirm={removeSelected}
        />
      ) : null}

      {/* Batch Status Update Modal */}
      <Dialog
        open={batchStatusOpen}
        onOpenChange={setBatchStatusOpen}
        title={`Batch Update Status (${selected.size} Quotations)`}
        description="Update hit/miss policy outcomes for the selected quotations. For corporate fleets with multiple quotes for the same vehicle, winning one will automatically mark competing underwriter quotes as superseded."
      >
        <div className="space-y-4 pt-2">
          {/* Target Status Toggle */}
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setBatchStatusTarget("hit")}
              className={`flex items-center justify-center gap-2 rounded-[var(--rl-radius-sm)] border p-3 text-sm font-semibold transition-all ${
                batchStatusTarget === "hit"
                  ? "border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
                  : "border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-muted)] hover:bg-[var(--rl-surface-sunken)]"
              }`}
            >
              <CheckCircle size={18} weight="bold" className={batchStatusTarget === "hit" ? "text-emerald-600" : ""} />
              <span>Mark Won (HIT)</span>
            </button>
            <button
              type="button"
              onClick={() => setBatchStatusTarget("miss")}
              className={`flex items-center justify-center gap-2 rounded-[var(--rl-radius-sm)] border p-3 text-sm font-semibold transition-all ${
                batchStatusTarget === "miss"
                  ? "border-rose-500 bg-rose-50 text-rose-900 dark:bg-rose-950/40 dark:text-rose-200"
                  : "border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-muted)] hover:bg-[var(--rl-surface-sunken)]"
              }`}
            >
              <XCircle size={18} weight="bold" className={batchStatusTarget === "miss" ? "text-rose-600" : ""} />
              <span>Mark Lost (MISS)</span>
            </button>
          </div>

          {batchStatusTarget === "hit" ? (
            <div className="space-y-3 rounded-[var(--rl-radius-sm)] border border-emerald-200 bg-emerald-50/50 p-3 dark:border-emerald-900 dark:bg-emerald-950/20">
              <p className="text-xs text-emerald-800 dark:text-emerald-300">
                <strong>Multi-Quote Auto Resolution:</strong> Any alternative quotes for the same vehicles in this deal cycle will be automatically marked as <strong>superseded</strong>, preventing false active policy conflicts.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[var(--rl-text-strong)] mb-1">Coverage Start Date</label>
                  <Input
                    type="date"
                    value={batchCoverageStart}
                    onChange={(e) => setBatchCoverageStart(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--rl-text-strong)] mb-1">Coverage End Date</label>
                  <Input
                    type="date"
                    value={batchCoverageEnd}
                    onChange={(e) => setBatchCoverageEnd(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-2 rounded-[var(--rl-radius-sm)] border border-rose-200 bg-rose-50/50 p-3 dark:border-rose-900 dark:bg-rose-950/20">
              <label className="block text-xs font-semibold text-[var(--rl-text-strong)]">Reason for Miss / Lost Deal</label>
              <select
                value={batchMissReason}
                onChange={(e) => setBatchMissReason(e.target.value)}
                className="w-full h-9 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2 text-xs font-medium text-[var(--rl-text-strong)]"
              >
                <option value="Competitor cheaper rate">Competitor cheaper rate</option>
                <option value="Client renewed directly with insurer">Client renewed directly with insurer</option>
                <option value="Vehicle sold / disposed">Vehicle sold / disposed</option>
                <option value="Client uncontactable / ghosted">Client uncontactable / ghosted</option>
                <option value="Excessive loading / insurer rejected">Excessive loading / insurer rejected</option>
                <option value="Other">Other reason</option>
              </select>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-[var(--rl-border)]">
            <Button variant="ghost" size="sm" onClick={() => setBatchStatusOpen(false)}>
              Cancel
            </Button>
            <Button
              variant={batchStatusTarget === "hit" ? "primary" : "danger"}
              size="sm"
              loading={batchUpdating}
              onClick={handleBatchStatusSubmit}
            >
              Apply to {selected.size} Quotes
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Rescan Quotation Session Modal */}
      <RescanSessionModal
        session={pendingRescan}
        open={Boolean(pendingRescan)}
        onOpenChange={(open) => {
          if (!open) setPendingRescan(null);
        }}
        loading={Boolean(rescanning)}
        onConfirm={handleRescanConfirm}
      />
    </AppShell>
  );
}

// Subcomponent: Quotation Row inside a Vehicle Group Card
function QuotationRow({
  session: s,
  isSelected,
  isDeleting,
  isRescanning,
  onToggleSelect,
  onDeleteClick,
  onRescanClick,
  onCopyRef,
  isRefCopied,
}: {
  session: Session;
  isSelected: boolean;
  isDeleting: boolean;
  isRescanning?: boolean;
  onToggleSelect: () => void;
  onDeleteClick: () => void;
  onRescanClick: () => void;
  onCopyRef: (ref: string) => void;
  isRefCopied: boolean;
}) {
  return (
    <div
      className={`p-4 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
        isSelected ? "bg-red-50/30" : "hover:bg-[var(--rl-bg)]/40"
      }`}
    >
      <div className="flex items-start gap-3 min-w-0">
        <input
          type="checkbox"
          aria-label={`Select quotation for ${s.quotation_ref || s.filename}`}
          className="mt-1 h-4 w-4 rounded accent-[var(--rl-red)] cursor-pointer"
          checked={isSelected}
          onChange={onToggleSelect}
        />

        <div className="grid gap-1 min-w-0">
          {/* Insurer, Premium, Ref, and Real Status Line */}
          <div className="flex flex-wrap items-center gap-2">
            {s.is_test ? (
              <span
                className="inline-flex items-center gap-1 rounded bg-amber-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-900 dark:text-amber-300 border border-amber-500/30"
                title="Test upload: isolated from customer records and hit & miss tracking"
              >
                <Sparkle size={11} weight="fill" className="text-amber-600" />
                Test Upload
              </span>
            ) : null}

            {s.detected_company ? (
              <span
                className="inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded-[var(--rl-radius-sm)] bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-2xs tracking-wide"
                title="Underwriting Insurer"
              >
                {s.detected_company}
              </span>
            ) : null}

            {s.total_premium ? (
              <span className="font-bold text-[14px] text-emerald-700 dark:text-emerald-400 font-mono">
                RM {s.total_premium}
              </span>
            ) : null}

            {s.quotation_ref ? (
              <span className="inline-flex items-center gap-1 font-mono text-[11px] font-semibold text-[var(--rl-text-muted)] bg-[var(--rl-surface)] px-2 py-0.5 rounded border border-[var(--rl-border)]">
                <span>{s.quotation_ref}</span>
                <button
                  type="button"
                  onClick={() => onCopyRef(s.quotation_ref!)}
                  className="text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  title="Copy quotation reference"
                >
                  {isRefCopied ? <Check size={12} className="text-emerald-600 font-bold" /> : <Copy size={12} />}
                </button>
              </span>
            ) : null}

            {/* Real Status Badge from database */}
            <StatusBadge status={s.draft_status || s.status} />

            {/* Hit / Miss / Superseded Outcome Badge */}
            {s.quotation_status && s.quotation_status !== "pending" ? (
              <span
                className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                  s.quotation_status === "hit"
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
                    : s.quotation_status === "miss"
                    ? "bg-rose-100 text-rose-800 dark:bg-rose-950/70 dark:text-rose-300 border border-rose-300 dark:border-rose-800"
                    : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700"
                }`}
                title={s.miss_reason ? `Reason: ${s.miss_reason}` : undefined}
              >
                {s.quotation_status === "hit" && <CheckCircle size={12} weight="bold" />}
                {s.quotation_status === "miss" && <XCircle size={12} weight="bold" />}
                {s.quotation_status}
              </span>
            ) : null}
          </div>

          {/* Attribution & Exact Second Timestamp */}
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12px] text-[var(--rl-text-muted)] pt-0.5">
            <span
              className="inline-flex items-center gap-1 font-medium text-[var(--rl-text-strong)]"
              title={`Uploaded on ${formatDateTime(s.created_at)}`}
            >
              <Clock size={13} className="text-[var(--rl-text-muted)]" />
              <span>{formatDateTime(s.created_at)}</span>
            </span>

            <span className="text-[var(--rl-text-muted)]">•</span>

            <span
              className="inline-flex items-center gap-1"
              title={s.created_by_email ? `Created by ${s.created_by} (${s.created_by_email})` : undefined}
            >
              <User size={13} className="text-[var(--rl-text-muted)]" />
              <span>
                Created by <strong className="text-[var(--rl-text-strong)]">{s.created_by || "System"}</strong>
              </span>
            </span>

            {s.is_edited ? (
              <>
                <span className="text-[var(--rl-text-muted)]">•</span>
                <span
                  className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-1.5 py-0.5 text-[11px] font-semibold text-amber-800 dark:text-amber-300 border border-amber-500/25"
                  title={`Last edited on ${formatDateTime(s.last_edited_at)} by ${s.last_edited_by || "User"}`}
                >
                  <PencilSimpleLine size={12} weight="bold" />
                  <span>
                    Edited by <strong>{s.last_edited_by || "User"}</strong> ({formatDateTime(s.last_edited_at)})
                  </span>
                </span>
              </>
            ) : null}
          </div>
        </div>
      </div>

      {/* Action Buttons Column */}
      <div className="flex items-center gap-2 pt-1 sm:pt-0 sm:self-center pl-7 sm:pl-0">
        <a
          href={`/api/sessions/${s.id}/pdf`}
          target="_blank"
          rel="noopener noreferrer"
          title="View / Download Quotation PDF"
          aria-label="View / Download Quotation PDF"
          className="inline-flex size-8.5 sm:size-9 items-center justify-center rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] text-red-600 transition-all hover:bg-red-50 hover:border-red-300 active:scale-95 shadow-xs"
        >
          <FilePdf aria-hidden="true" size={17} weight="bold" />
        </a>

        <a
          href={`/sessions/${s.id}`}
          target="_blank"
          rel="noopener noreferrer"
          title="Open in new tab"
          aria-label="Open in new tab"
          className="inline-flex size-8.5 sm:size-9 items-center justify-center rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] transition-all hover:bg-[var(--rl-bg)] hover:text-black hover:border-black/40 active:scale-95 shadow-xs"
        >
          <ArrowSquareOut aria-hidden="true" size={20} weight="bold" />
        </a>

        <Link
          href={`/sessions/${s.id}`}
          className="inline-flex h-8 items-center justify-center gap-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-3 text-[12px] font-semibold text-[var(--rl-text-strong)] shadow-xs transition-all hover:bg-[var(--rl-bg)] hover:border-[var(--rl-border-strong)] active:scale-95"
        >
          <NotePencil aria-hidden="true" size={14} weight="bold" />
          Review
        </Link>

        <Button
          variant="secondary"
          size="sm"
          loading={isRescanning}
          icon={<ArrowsClockwise aria-hidden="true" size={13} weight="bold" className={isRescanning ? "animate-spin" : ""} />}
          onClick={onRescanClick}
          className="inline-flex h-8 items-center justify-center gap-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2.5 text-[12px] font-semibold text-[var(--rl-text-strong)] shadow-xs transition-all hover:bg-[var(--rl-bg)] hover:border-[var(--rl-border-strong)] active:scale-95"
          title="Rescan quotation from source PDF"
        >
          Rescan
        </Button>

        <Button
          variant="ghost"
          size="sm"
          loading={isDeleting}
          icon={<Trash aria-hidden="true" size={14} weight="bold" />}
          onClick={onDeleteClick}
          className="h-8 px-2 text-[var(--rl-red)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)]"
          title="Delete quotation"
        />
      </div>
    </div>
  );
}

// Subcomponent: Quotation Card for Flat / Timeline Views
function QuotationCard({
  session: s,
  isSelected,
  isDeleting,
  isRescanning,
  onToggleSelect,
  onDeleteClick,
  onRescanClick,
  onCopyRef,
  isRefCopied,
}: {
  session: Session;
  isSelected: boolean;
  isDeleting: boolean;
  isRescanning?: boolean;
  onToggleSelect: () => void;
  onDeleteClick: () => void;
  onRescanClick: () => void;
  onCopyRef: (ref: string) => void;
  isRefCopied: boolean;
}) {
  return (
    <Card
      key={s.id}
      hover
      className={`p-4 transition-all ${
        isSelected ? "border-[var(--rl-red)] bg-red-50/20 shadow-sm" : "border-[var(--rl-border)]"
      }`}
    >
      <div className="grid gap-3 sm:grid-cols-[auto_1fr_auto] sm:items-center">
        <div className="flex items-center pt-0.5 sm:pt-0">
          <input
            type="checkbox"
            aria-label={`Select quotation for ${s.vehicle_plate || s.filename}`}
            className="h-4 w-4 rounded accent-[var(--rl-red)] cursor-pointer"
            checked={isSelected}
            onChange={onToggleSelect}
          />
        </div>

        <div className="grid gap-1.5 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {s.is_test ? (
              <span
                className="inline-flex items-center gap-1 rounded bg-amber-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-900 dark:text-amber-300 border border-amber-500/30"
                title="Test upload: isolated from customer records and hit & miss tracking"
              >
                <Sparkle size={11} weight="fill" className="text-amber-600" />
                Test Upload
              </span>
            ) : null}

            <span
              className="inline-flex items-center font-mono text-[13px] font-bold tracking-wider px-2 py-0.5 rounded bg-[var(--rl-black)]/[0.05] text-[var(--rl-text-strong)] border border-[var(--rl-border-strong)]"
              title="Vehicle Registration Number"
            >
              {s.vehicle_plate ? `[ ${s.vehicle_plate} ]` : "[ NO PLATE ]"}
            </span>

            {s.quotation_ref ? (
              <span className="inline-flex items-center gap-1 font-mono text-[11px] font-semibold text-[var(--rl-text-muted)] bg-[var(--rl-surface)] px-2 py-0.5 rounded border border-[var(--rl-border)]">
                <span>{s.quotation_ref}</span>
                <button
                  type="button"
                  onClick={() => onCopyRef(s.quotation_ref!)}
                  className="text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  title="Copy quotation reference"
                >
                  {isRefCopied ? <Check size={11} className="text-emerald-600 font-bold" /> : <Copy size={11} />}
                </button>
              </span>
            ) : null}

            {s.detected_company ? (
              <span
                className="inline-flex items-center text-[12px] font-semibold px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-500/20"
                title="Underwriting Insurer"
              >
                {s.detected_company}
              </span>
            ) : null}

            <StatusBadge status={s.draft_status || s.status} />

            {/* Hit / Miss / Superseded Outcome Badge */}
            {s.quotation_status && s.quotation_status !== "pending" ? (
              <span
                className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                  s.quotation_status === "hit"
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
                    : s.quotation_status === "miss"
                    ? "bg-rose-100 text-rose-800 dark:bg-rose-950/70 dark:text-rose-300 border border-rose-300 dark:border-rose-800"
                    : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700"
                }`}
                title={s.miss_reason ? `Reason: ${s.miss_reason}` : undefined}
              >
                {s.quotation_status === "hit" && <CheckCircle size={12} weight="bold" />}
                {s.quotation_status === "miss" && <XCircle size={12} weight="bold" />}
                {s.quotation_status}
              </span>
            ) : null}
          </div>

          <div className="flex flex-wrap items-baseline gap-2">
            <h3 className="text-[15px] font-bold text-[var(--rl-text-strong)] truncate">
              {s.insured_name || s.filename}
            </h3>
            {s.insured_name && s.filename !== s.insured_name ? (
              <span className="text-[12px] text-[var(--rl-text-muted)] truncate max-w-sm font-mono" title={s.filename}>
                {s.filename}
              </span>
            ) : null}
          </div>

          {(s.vehicle_model || s.total_premium) && (
            <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[13px] text-[var(--rl-text)]">
              {s.vehicle_model ? (
                <span className="font-medium text-[var(--rl-text-strong)]">{s.vehicle_model}</span>
              ) : null}
              {s.vehicle_model && s.total_premium ? <span className="text-[var(--rl-text-muted)]">•</span> : null}
              {s.total_premium ? (
                <span className="font-bold text-emerald-700 dark:text-emerald-400 font-mono">
                  RM {s.total_premium}
                </span>
              ) : null}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 pt-1 text-[12px] text-[var(--rl-text-muted)] border-t border-[var(--rl-border)]/50 mt-1">
            <span
              className="inline-flex items-center gap-1 font-medium text-[var(--rl-text-strong)]"
              title={`Uploaded on ${formatDateTime(s.created_at)}`}
            >
              <Clock size={13} className="text-[var(--rl-text-muted)]" />
              <span>{formatDateTime(s.created_at)}</span>
            </span>

            <span className="text-[var(--rl-text-muted)]">•</span>

            <span
              className="inline-flex items-center gap-1"
              title={s.created_by_email ? `Created by ${s.created_by} (${s.created_by_email})` : undefined}
            >
              <User size={13} className="text-[var(--rl-text-muted)]" />
              <span>
                Created by <strong className="text-[var(--rl-text-strong)]">{s.created_by || "System"}</strong>
              </span>
            </span>

            {s.is_edited ? (
              <>
                <span className="text-[var(--rl-text-muted)]">•</span>
                <span
                  className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold text-amber-800 dark:text-amber-300 border border-amber-500/25"
                  title={`Last edited on ${formatDateTime(s.last_edited_at)} by ${s.last_edited_by || "User"}`}
                >
                  <PencilSimpleLine size={12} weight="bold" />
                  <span>
                    Edited by <strong>{s.last_edited_by || "User"}</strong> ({formatDateTime(s.last_edited_at)})
                  </span>
                </span>
              </>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-2 sm:pt-0 sm:justify-end">
          <a
            href={`/api/sessions/${s.id}/pdf`}
            target="_blank"
            rel="noopener noreferrer"
            title="View / Download Quotation PDF"
            aria-label="View / Download Quotation PDF"
            className="inline-flex size-9 items-center justify-center rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] text-red-600 transition-all hover:bg-red-50 hover:border-red-300 active:scale-95 shadow-xs"
          >
            <FilePdf aria-hidden="true" size={18} weight="bold" />
          </a>

          <a
            href={`/sessions/${s.id}`}
            target="_blank"
            rel="noopener noreferrer"
            title="Open in new tab"
            aria-label="Open in new tab"
            className="inline-flex size-9 items-center justify-center rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] transition-all hover:bg-[var(--rl-bg)] hover:text-black hover:border-black/40 active:scale-95 shadow-xs"
          >
            <ArrowSquareOut aria-hidden="true" size={20} weight="bold" />
          </a>

          <Link
            href={`/sessions/${s.id}`}
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-3.5 text-[13px] font-semibold text-[var(--rl-text-strong)] shadow-xs transition-all hover:bg-[var(--rl-bg)] hover:border-[var(--rl-border-strong)] active:scale-95"
          >
            <NotePencil aria-hidden="true" size={16} weight="bold" />
            Review
          </Link>

          <Button
            variant="secondary"
            size="sm"
            loading={isRescanning}
            icon={<ArrowsClockwise aria-hidden="true" size={14} weight="bold" className={isRescanning ? "animate-spin" : ""} />}
            onClick={onRescanClick}
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-3 text-[13px] font-semibold text-[var(--rl-text-strong)] shadow-xs transition-all hover:bg-[var(--rl-bg)] hover:border-[var(--rl-border-strong)] active:scale-95"
            title="Rescan quotation from source PDF"
          >
            Rescan
          </Button>

          <Button
            variant="ghost"
            size="sm"
            loading={isDeleting}
            icon={<Trash aria-hidden="true" size={15} weight="bold" />}
            onClick={onDeleteClick}
            className="h-9 px-2.5 text-[var(--rl-red)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)]"
            title="Delete session"
          />
        </div>
      </div>
    </Card>
  );
}

// Subcomponent: Rescan Quotation Session Modal
function RescanSessionModal({
  session,
  open,
  onOpenChange,
  loading,
  onConfirm,
}: {
  session: Session | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  loading: boolean;
  onConfirm: (session: Session, mode: "in_place" | "new_session", engine: "auto" | "native" | "ai") => void;
}) {
  const [mode, setMode] = useState<"in_place" | "new_session">("in_place");
  const [useAi, setUseAi] = useState(false);

  if (!session) return null;

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!loading) onOpenChange(v);
      }}
      title="Rescan Quotation Session"
      description={`Re-evaluate and extract values from the original source PDF for ${
        session.vehicle_plate ? `[${session.vehicle_plate}]` : session.insured_name || session.filename
      }.`}
    >
      <div className="space-y-4 pt-1">
        {/* Session Reference Dossier */}
        <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-md bg-[var(--rl-bg)] border border-[var(--rl-border)] text-[13px]">
          <div className="flex items-center gap-2 min-w-0">
            <FilePdf size={18} className="text-red-600 shrink-0" weight="fill" />
            <span className="font-semibold text-[var(--rl-text-strong)] truncate max-w-[220px]" title={session.filename}>
              {session.filename}
            </span>
          </div>
          {session.quotation_ref && (
            <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-[var(--rl-surface)] border border-[var(--rl-border-strong)] text-[var(--rl-text-muted)] shrink-0">
              {session.quotation_ref}
            </span>
          )}
        </div>

        {/* Mode Selector Cards */}
        <div className="grid gap-2.5">
          <label
            onClick={() => setMode("in_place")}
            className={`flex items-start gap-3 p-3.5 rounded-lg border cursor-pointer transition-all ${
              mode === "in_place"
                ? "border-[var(--rl-red)] bg-red-50/20 ring-1 ring-[var(--rl-red)]/40"
                : "border-[var(--rl-border)] hover:bg-[var(--rl-bg)]/50"
            }`}
          >
            <input
              type="radio"
              name="rescan_mode"
              checked={mode === "in_place"}
              onChange={() => setMode("in_place")}
              className="mt-1 h-4 w-4 accent-[var(--rl-red)] cursor-pointer"
            />
            <div className="grid gap-0.5 min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[13px] font-bold text-[var(--rl-text-strong)] flex items-center gap-1.5">
                  <ArrowsClockwise size={15} weight="bold" className="text-[var(--rl-red)]" />
                  Renew this Session (In-Place)
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  Recommended
                </span>
              </div>
              <p className="text-[12px] text-[var(--rl-text-muted)] leading-relaxed">
                Clears old/empty extraction data and re-runs catalog mapping. Retains the internal quotation reference ({session.quotation_ref || "RL..."}).
              </p>
            </div>
          </label>

          <label
            onClick={() => setMode("new_session")}
            className={`flex items-start gap-3 p-3.5 rounded-lg border cursor-pointer transition-all ${
              mode === "new_session"
                ? "border-[var(--rl-red)] bg-red-50/20 ring-1 ring-[var(--rl-red)]/40"
                : "border-[var(--rl-border)] hover:bg-[var(--rl-bg)]/50"
            }`}
          >
            <input
              type="radio"
              name="rescan_mode"
              checked={mode === "new_session"}
              onChange={() => setMode("new_session")}
              className="mt-1 h-4 w-4 accent-[var(--rl-red)] cursor-pointer"
            />
            <div className="grid gap-0.5 min-w-0 flex-1">
              <span className="text-[13px] font-bold text-[var(--rl-text-strong)] flex items-center gap-1.5">
                <ArrowSquareOut size={15} weight="bold" className="text-blue-600" />
                Rescan as New Session (Open in New Tab)
              </span>
              <p className="text-[12px] text-[var(--rl-text-muted)] leading-relaxed">
                Preserves this session untouched, assigns a brand new quotation reference sequence, and opens the new session in a new tab.
              </p>
            </div>
          </label>
        </div>

        {/* AI Reading Toggle */}
        <div className="pt-1">
          <label className="flex items-start gap-2.5 p-3 rounded-lg border border-[var(--rl-border)] bg-[var(--rl-bg)]/40 cursor-pointer hover:bg-[var(--rl-bg)] transition-colors">
            <input
              type="checkbox"
              checked={useAi}
              onChange={(e) => setUseAi(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded accent-[var(--rl-red)] cursor-pointer"
            />
            <div className="grid gap-0.5 text-[12px]">
              <span className="font-bold text-[var(--rl-text-strong)] flex items-center gap-1.5">
                <Sparkle size={14} weight="fill" className="text-amber-500" />
                Deep AI Reading (Google Gemini)
              </span>
              <span className="text-[var(--rl-text-muted)]">
                Recommended if the PDF was previously blank or difficult for native OCR to parse.
              </span>
            </div>
          </label>
        </div>

        {/* Action Buttons */}
        <div className="mt-5 flex gap-2 justify-end pt-2 border-t border-[var(--rl-border)]/70">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={loading}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            size="sm"
            loading={loading}
            icon={<ArrowsClockwise size={14} weight="bold" className={loading ? "animate-spin" : ""} />}
            onClick={() => onConfirm(session, mode, useAi ? "ai" : "auto")}
          >
            {loading ? "Rescanning..." : mode === "new_session" ? "Rescan & Open New Tab" : "Start Rescan"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

