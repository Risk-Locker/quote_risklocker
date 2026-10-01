"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import {
  Users,
  UserCheck,
  Buildings,
  Car,
  Plus,
  MagnifyingGlass,
  PencilSimple,
  Trash,
  Phone,
  Envelope,
  Tag,
  Columns,
  CaretRight,
  Sparkle,
  CircleNotch,
  X,
  Check,
  Briefcase,
  UserCircle,
  CurrencyDollar,
  NotePencil,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

interface ClientDossierItem {
  client_id: string;
  name: string;
  client_type: "individual" | "corporate";
  id_number?: string;
  phone?: string;
  email?: string;
  active_vehicles_count: number;
  total_policies: number;
  assigned_pic_name?: string;
  assigned_pic_agency?: string;
  coverage_preference_notes?: string;
  latest_tenure_id?: string;
  latest_expiry_month?: string;
}

interface PicItem {
  id: string;
  name: string;
  type: "subagent" | "company_personnel" | "client_self" | "external_contact";
  agency_group: string | null;
  commission_rate: number;
  phone: string | null;
  email: string | null;
  notes: string | null;
  tenures_count: number;
  clients_count: number;
}

export default function ClientRecordsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"clients" | "pics">("clients");

  // Clients Tab State
  const [clientFilter, setClientFilter] = useState<"all" | "individual" | "corporate">("all");
  const [clientSearch, setClientSearch] = useState("");
  const [clients, setClients] = useState<ClientDossierItem[]>([]);
  const [loadingClients, setLoadingClients] = useState(false);

  // PICs Tab State
  const [picFilter, setPicFilter] = useState<string>("all");
  const [picSearch, setPicSearch] = useState("");
  const [pics, setPics] = useState<PicItem[]>([]);
  const [loadingPics, setLoadingPics] = useState(false);

  // Modal State for Add / Edit PIC
  const [isPicModalOpen, setIsPicModalOpen] = useState(false);
  const [editingPic, setEditingPic] = useState<PicItem | null>(null);
  const [picFormData, setPicFormData] = useState({
    name: "",
    type: "subagent",
    agency_group: "",
    commission_rate: 0.0,
    phone: "",
    email: "",
    notes: "",
  });
  const [savingPic, setSavingPic] = useState(false);

  // Modal State for Edit Client
  const [isClientModalOpen, setIsClientModalOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<ClientDossierItem | null>(null);
  const [clientFormData, setClientFormData] = useState({
    canonical_name: "",
    id_number: "",
    phone: "",
    email: "",
    notes: "",
  });
  const [savingClient, setSavingClient] = useState(false);

  // Fetch Clients
  const loadClients = useCallback(async () => {
    setLoadingClients(true);
    try {
      const params = new URLSearchParams();
      if (clientSearch.trim()) params.set("search", clientSearch.trim());
      if (clientFilter !== "all") params.set("client_type", clientFilter);
      params.set("page_size", "100");

      const res = await api<{ clients: ClientDossierItem[] }>(`/insights/clients?${params.toString()}`);
      setClients(res.clients || []);
    } catch (err) {
      console.error("Failed to load client records:", err);
    } finally {
      setLoadingClients(false);
    }
  }, [clientSearch, clientFilter]);

  // Fetch PICs
  const loadPics = useCallback(async () => {
    setLoadingPics(true);
    try {
      const params = new URLSearchParams();
      if (picFilter !== "all") params.set("type", picFilter);
      if (picSearch.trim()) params.set("search", picSearch.trim());

      const res = await api<PicItem[]>(`/pics?${params.toString()}`);
      setPics(res || []);
    } catch (err) {
      console.error("Failed to load PICs:", err);
    } finally {
      setLoadingPics(false);
    }
  }, [picFilter, picSearch]);

  useEffect(() => {
    if (activeTab === "clients") {
      loadClients();
    } else {
      loadPics();
    }
  }, [activeTab, loadClients, loadPics]);

  function handleOpenAddPic() {
    setEditingPic(null);
    setPicFormData({
      name: "",
      type: "subagent",
      agency_group: "",
      commission_rate: 2.0,
      phone: "",
      email: "",
      notes: "",
    });
    setIsPicModalOpen(true);
  }

  function handleOpenEditPic(pic: PicItem) {
    setEditingPic(pic);
    setPicFormData({
      name: pic.name,
      type: pic.type,
      agency_group: pic.agency_group || "",
      commission_rate: pic.commission_rate || 0.0,
      phone: pic.phone || "",
      email: pic.email || "",
      notes: pic.notes || "",
    });
    setIsPicModalOpen(true);
  }

  function handleOpenEditClient(client: ClientDossierItem) {
    setEditingClient(client);
    setClientFormData({
      canonical_name: client.name || "",
      id_number: client.id_number || "",
      phone: client.phone || "",
      email: client.email || "",
      notes: client.coverage_preference_notes || "",
    });
    setIsClientModalOpen(true);
  }

  async function handleSaveClient(e: React.FormEvent) {
    e.preventDefault();
    if (!editingClient || !clientFormData.canonical_name.trim()) return;
    setSavingClient(true);
    try {
      await api(`/insights/customers/${editingClient.client_id}`, {
        method: "PATCH",
        body: JSON.stringify(clientFormData),
      });
      setIsClientModalOpen(false);
      loadClients();
    } catch (err) {
      console.error("Failed to update client account:", err);
      alert("Failed to update client account. Please check your connection.");
    } finally {
      setSavingClient(false);
    }
  }

  async function handleSavePic(e: React.FormEvent) {
    e.preventDefault();
    if (!picFormData.name.trim()) return;
    setSavingPic(true);

    try {
      if (editingPic) {
        await api(`/pics/${editingPic.id}`, {
          method: "PATCH",
          body: JSON.stringify(picFormData),
        });
      } else {
        await api("/pics", {
          method: "POST",
          body: JSON.stringify(picFormData),
        });
      }
      setIsPicModalOpen(false);
      loadPics();
    } catch (err) {
      console.error("Failed to save PIC:", err);
    } finally {
      setSavingPic(false);
    }
  }

  async function handleDeletePic(picId: string) {
    if (!confirm("Are you sure you want to remove this Person in Charge? Any associated tenures will be kept.")) return;
    try {
      await api(`/pics/${picId}`, { method: "DELETE" });
      loadPics();
    } catch (err) {
      console.error("Failed to delete PIC:", err);
    }
  }

  return (
    <AppShell>
      <div className="grid w-full max-w-7xl mx-auto gap-6 pb-12">
        {/* Header */}
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--rl-border)] pb-4">
          <div>
            <h1 className="font-[var(--font-manrope)] text-[26px] font-bold text-[var(--rl-text-strong)] flex items-center gap-2.5">
              <Users size={28} weight="bold" className="text-[var(--rl-text-strong)]" />
              Client Records &amp; Directory
            </h1>
            <p className="mt-1 text-sm text-[var(--rl-text-muted)]">
              Unified relationship management for Individual Clients, Corporate Fleets, and Persons In Charge (PIC) / SubAgents.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            {activeTab === "pics" ? (
              <Button
                variant="primary"
                size="md"
                onClick={handleOpenAddPic}
                icon={<Plus size={16} weight="bold" />}
                className="bg-[var(--rl-black)] hover:bg-black text-white font-semibold text-xs gap-1.5 shadow-xs"
              >
                Add SubAgent / PIC
              </Button>
            ) : (
              <Button
                variant="primary"
                size="md"
                onClick={() => router.push("/upload?mode=comparison" as Route)}
                icon={<Sparkle size={16} weight="bold" />}
                className="bg-[var(--rl-black)] hover:bg-black text-white font-semibold text-xs gap-1.5 shadow-xs"
              >
                New Quotation Deal
              </Button>
            )}
          </div>
        </header>

        {/* Top-Level Tabs (Clients vs PICs & SubAgents) */}
        <div className="flex items-center justify-between gap-4 border-b border-[var(--rl-border)]">
          <div className="flex items-center gap-6">
            <button
              type="button"
              onClick={() => setActiveTab("clients")}
              className={`flex items-center gap-2 pb-3 text-sm font-bold border-b-2 transition-all cursor-pointer ${
                activeTab === "clients"
                  ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
                  : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              <Users size={18} weight={activeTab === "clients" ? "bold" : "regular"} />
              Master Clients Directory
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("pics")}
              className={`flex items-center gap-2 pb-3 text-sm font-bold border-b-2 transition-all cursor-pointer ${
                activeTab === "pics"
                  ? "border-[var(--rl-black)] text-[var(--rl-text-strong)]"
                  : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              <UserCheck size={18} weight={activeTab === "pics" ? "bold" : "regular"} />
              Person In Charge (PIC) &amp; SubAgents
            </button>
          </div>
        </div>

        {/* ================================================================== */}
        {/* TAB 1: CLIENTS DIRECTORY                                           */}
        {/* ================================================================== */}
        {activeTab === "clients" && (
          <div className="grid gap-5">
            {/* Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3.5 rounded-[var(--rl-radius)] border border-[var(--rl-border)] shadow-xs">
              {/* Type Pill Toggle */}
              <div className="flex items-center gap-1 rounded-lg border border-[var(--rl-border)] bg-[var(--rl-bg-surface)] p-1">
                <button
                  type="button"
                  onClick={() => setClientFilter("all")}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                    clientFilter === "all"
                      ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  All Clients
                </button>
                <button
                  type="button"
                  onClick={() => setClientFilter("individual")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                    clientFilter === "individual"
                      ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  <UserCircle size={14} weight="bold" />
                  Individual
                </button>
                <button
                  type="button"
                  onClick={() => setClientFilter("corporate")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                    clientFilter === "corporate"
                      ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  <Buildings size={14} weight="bold" />
                  Corporate Fleet
                </button>
              </div>

              {/* Search */}
              <div className="relative w-72">
                <MagnifyingGlass size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
                <input
                  type="text"
                  value={clientSearch}
                  onChange={(e) => setClientSearch(e.target.value)}
                  placeholder="Search by client name, IC, BRN..."
                  className="w-full rounded-lg border border-[var(--rl-border)] bg-[var(--rl-bg)] pl-9 pr-3 py-1.5 text-xs text-[var(--rl-text-strong)] focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
                />
              </div>
            </div>

            {/* Clients Grid / Empty State */}
            {loadingClients ? (
              <div className="flex h-64 items-center justify-center">
                <CircleNotch className="size-8 animate-spin text-[var(--rl-text-muted)]" />
              </div>
            ) : clients.length === 0 ? (
              <Card className="p-12 text-center border border-[var(--rl-border)] bg-white space-y-3">
                <div className="size-12 rounded-full bg-neutral-100 flex items-center justify-center mx-auto text-neutral-500">
                  <Users size={24} />
                </div>
                <h3 className="text-base font-bold text-[var(--rl-text-strong)]">No Client Records Found</h3>
                <p className="text-xs text-[var(--rl-text-muted)] max-w-md mx-auto">
                  Clients are automatically registered when you intake quotations or create new deals in Marketing Comparison.
                </p>
                <Button
                  size="sm"
                  onClick={() => router.push("/upload?mode=comparison" as Route)}
                  className="bg-[var(--rl-black)] hover:bg-black text-white text-xs font-semibold"
                >
                  Start First Comparison Deal
                </Button>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {clients.map((c) => (
                  <Card
                    key={c.client_id}
                    className="p-4 border border-[var(--rl-border)] bg-white hover:border-black/40 hover:shadow-md transition-all flex flex-col justify-between gap-3"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <Badge
                          variant={c.client_type === "corporate" ? "default" : "info"}
                          className="text-[10px] uppercase font-bold"
                        >
                          {c.client_type === "corporate" ? "🏢 Corporate Fleet" : "👤 Individual"}
                        </Badge>
                        <span className="font-mono text-xs font-bold text-[var(--rl-text-muted)]">
                          {c.active_vehicles_count} Vehicle{c.active_vehicles_count > 1 ? "s" : ""}
                        </span>
                      </div>

                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className="text-sm font-bold text-[var(--rl-text-strong)] line-clamp-1">{c.name}</h3>
                          {c.id_number && (
                            <p className="font-mono text-xs text-[var(--rl-text-muted)] mt-0.5">{c.id_number}</p>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleOpenEditClient(c)}
                          className="p-1 rounded text-neutral-400 hover:text-neutral-900 hover:bg-neutral-100 transition-colors cursor-pointer shrink-0"
                          title="Edit Customer Profile (propagates to all tenures & quotes)"
                        >
                          <PencilSimple size={14} weight="bold" />
                        </button>
                      </div>

                      {/* Assigned SubAgent / PIC Tag */}
                      <div className="mt-3 flex items-center gap-2 text-xs">
                        <span className="text-[var(--rl-text-muted)] font-medium">PIC:</span>
                        <span className="font-semibold text-[var(--rl-text-strong)] bg-neutral-100 px-2 py-0.5 rounded text-[11px]">
                          {c.assigned_pic_name || "Unassigned"}
                        </span>
                        {c.assigned_pic_agency && (
                          <span className="bg-amber-100 text-amber-900 border border-amber-300 px-1.5 py-0.5 rounded font-bold text-[10px]">
                            {c.assigned_pic_agency}
                          </span>
                        )}
                      </div>

                      {/* Coverage Habit Notes */}
                      {c.coverage_preference_notes && (
                        <div className="mt-2.5 p-2 rounded bg-neutral-50 border border-neutral-100 text-[11px] text-[var(--rl-text-muted)]">
                          <strong>Habit:</strong> {c.coverage_preference_notes}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-[var(--rl-border)] text-xs">
                      <span className="text-[var(--rl-text-muted)] text-[11px]">
                        {c.latest_expiry_month ? `Exp: ${c.latest_expiry_month}` : "No active tenure"}
                      </span>

                      {c.latest_tenure_id ? (
                        <Link
                          href={`/comparison?tenure_id=${c.latest_tenure_id}` as Route}
                          className="font-bold text-[var(--rl-black)] hover:underline inline-flex items-center gap-1 text-xs"
                        >
                          <Columns size={13} weight="bold" />
                          Open Matrix →
                        </Link>
                      ) : (
                        <span className="text-neutral-400 text-xs">No Matrix</span>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ================================================================== */}
        {/* TAB 2: PERSON IN CHARGE (PIC) & SUBAGENTS DIRECTORY                */}
        {/* ================================================================== */}
        {activeTab === "pics" && (
          <div className="grid gap-5">
            {/* Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3.5 rounded-[var(--rl-radius)] border border-[var(--rl-border)] shadow-xs">
              <div className="flex items-center gap-1 rounded-lg border border-[var(--rl-border)] bg-[var(--rl-bg-surface)] p-1">
                <button
                  type="button"
                  onClick={() => setPicFilter("all")}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                    picFilter === "all"
                      ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  All PICs
                </button>
                <button
                  type="button"
                  onClick={() => setPicFilter("subagent")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                    picFilter === "subagent"
                      ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  <Briefcase size={14} weight="bold" />
                  SubAgents
                </button>
                <button
                  type="button"
                  onClick={() => setPicFilter("company_personnel")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                    picFilter === "company_personnel"
                      ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  <Buildings size={14} weight="bold" />
                  Company PICs
                </button>
                <button
                  type="button"
                  onClick={() => setPicFilter("client_self")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                    picFilter === "client_self"
                      ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  <UserCircle size={14} weight="bold" />
                  Self Managed
                </button>
              </div>

              <div className="relative w-72">
                <MagnifyingGlass size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
                <input
                  type="text"
                  value={picSearch}
                  onChange={(e) => setPicSearch(e.target.value)}
                  placeholder="Search by name, BNI group, phone..."
                  className="w-full rounded-lg border border-[var(--rl-border)] bg-[var(--rl-bg)] pl-9 pr-3 py-1.5 text-xs text-[var(--rl-text-strong)] focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
                />
              </div>
            </div>

            {/* PICs Cards Grid */}
            {loadingPics ? (
              <div className="flex h-64 items-center justify-center">
                <CircleNotch className="size-8 animate-spin text-[var(--rl-text-muted)]" />
              </div>
            ) : pics.length === 0 ? (
              <Card className="p-12 text-center border border-[var(--rl-border)] bg-white space-y-3">
                <div className="size-12 rounded-full bg-neutral-100 flex items-center justify-center mx-auto text-neutral-500">
                  <UserCheck size={24} />
                </div>
                <h3 className="text-base font-bold text-[var(--rl-text-strong)]">No SubAgents or PICs Recorded</h3>
                <p className="text-xs text-[var(--rl-text-muted)] max-w-md mx-auto">
                  Register SubAgents (e.g. Gina Tee, Brian, Dr Edwin, BNI teams) with referral commission rates to manage client deals.
                </p>
                <Button
                  size="sm"
                  onClick={handleOpenAddPic}
                  className="bg-[var(--rl-black)] hover:bg-black text-white text-xs font-semibold"
                >
                  Add First SubAgent / PIC
                </Button>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {pics.map((p) => (
                  <Card
                    key={p.id}
                    className="p-4 border border-[var(--rl-border)] bg-white hover:border-black/40 hover:shadow-md transition-all flex flex-col justify-between gap-3"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="flex items-center gap-1.5">
                          <span
                            className={`size-2 rounded-full ${
                              p.type === "subagent"
                                ? "bg-amber-500"
                                : p.type === "company_personnel"
                                ? "bg-blue-500"
                                : "bg-emerald-500"
                            }`}
                          />
                          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                            {p.type === "subagent"
                              ? "SubAgent"
                              : p.type === "company_personnel"
                              ? "Company Personnel"
                              : "Client Self"}
                          </span>
                        </span>

                        {p.agency_group && (
                          <span className="rounded bg-amber-100 text-amber-900 border border-amber-300 px-2 py-0.5 font-bold text-[10px]">
                            {p.agency_group}
                          </span>
                        )}
                      </div>

                      <h3 className="text-base font-bold text-[var(--rl-text-strong)]">{p.name}</h3>

                      <div className="grid grid-cols-2 gap-2 mt-3 p-2.5 rounded-lg bg-[var(--rl-bg)] text-xs">
                        <div>
                          <p className="text-[10px] text-[var(--rl-text-muted)] font-semibold uppercase">Commission</p>
                          <p className="font-mono font-bold text-[var(--rl-text-strong)] mt-0.5">
                            {p.type === "subagent" ? `${p.commission_rate.toFixed(1)}%` : "0.0% (N/A)"}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] text-[var(--rl-text-muted)] font-semibold uppercase">Managed Deals</p>
                          <p className="font-mono font-bold text-[var(--rl-text-strong)] mt-0.5">
                            {p.tenures_count} Policies ({p.clients_count} Clients)
                          </p>
                        </div>
                      </div>

                      {/* Contact Info */}
                      {(p.phone || p.email) && (
                        <div className="mt-2.5 space-y-1 text-xs text-[var(--rl-text-muted)]">
                          {p.phone && (
                            <p className="flex items-center gap-1.5">
                              <Phone size={13} /> {p.phone}
                            </p>
                          )}
                          {p.email && (
                            <p className="flex items-center gap-1.5 truncate">
                              <Envelope size={13} /> {p.email}
                            </p>
                          )}
                        </div>
                      )}

                      {p.notes && (
                        <p className="mt-2 text-[11px] text-[var(--rl-text-muted)] italic line-clamp-2">
                          &ldquo;{p.notes}&rdquo;
                        </p>
                      )}
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-[var(--rl-border)]">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleOpenEditPic(p)}
                        className="text-xs font-semibold gap-1"
                      >
                        <PencilSimple size={14} /> Edit
                      </Button>

                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDeletePic(p.id)}
                        className="text-xs text-[var(--rl-red)] hover:bg-red-50 gap-1"
                      >
                        <Trash size={14} />
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Modal: Add / Edit PIC Dialog */}
        {isPicModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
            <div className="relative w-full max-w-md rounded-2xl bg-white border border-[var(--rl-border)] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
              <div className="flex items-center justify-between border-b border-[var(--rl-border)] px-6 py-4 bg-[var(--rl-bg)]">
                <div>
                  <h3 className="text-base font-bold text-[var(--rl-text-strong)]">
                    {editingPic ? "Edit Person In Charge / SubAgent" : "Add New Person In Charge"}
                  </h3>
                  <p className="text-xs text-[var(--rl-text-muted)] mt-0.5">
                    Assign client relationships and manage referral commission rates
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsPicModalOpen(false)}
                  className="rounded-lg p-1 text-[var(--rl-text-muted)] hover:bg-black/5 transition-colors cursor-pointer"
                >
                  <X size={18} weight="bold" />
                </button>
              </div>

              <form onSubmit={handleSavePic} className="p-6 space-y-4">
                <div>
                  <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                    Full Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={picFormData.name}
                    onChange={(e) => setPicFormData({ ...picFormData, name: e.target.value })}
                    placeholder="e.g. Gina Tee, Brian, Dr Edwin"
                    className="w-full rounded-lg border border-[var(--rl-border)] px-3 py-2 text-xs focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                      Role / Type
                    </label>
                    <select
                      value={picFormData.type}
                      onChange={(e) => setPicFormData({ ...picFormData, type: e.target.value as any })}
                      className="w-full rounded-lg border border-[var(--rl-border)] px-2.5 py-2 text-xs focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none bg-white font-medium"
                    >
                      <option value="subagent">SubAgent (Commission)</option>
                      <option value="company_personnel">Company PIC</option>
                      <option value="client_self">Client (Self)</option>
                      <option value="external_contact">External Contact</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                      Agency / Team
                    </label>
                    <input
                      type="text"
                      value={picFormData.agency_group}
                      onChange={(e) => setPicFormData({ ...picFormData, agency_group: e.target.value })}
                      placeholder="e.g. BNI, BNI_DJ"
                      className="w-full rounded-lg border border-[var(--rl-border)] px-3 py-2 text-xs focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none"
                    />
                  </div>
                </div>

                {picFormData.type === "subagent" && (
                  <div>
                    <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                      Commission Rate (%)
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="100"
                        value={picFormData.commission_rate}
                        onChange={(e) => setPicFormData({ ...picFormData, commission_rate: parseFloat(e.target.value) || 0 })}
                        className="w-full rounded-lg border border-[var(--rl-border)] pl-3 pr-8 py-2 text-xs font-mono font-bold focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-bold text-[var(--rl-text-muted)]">%</span>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                      Phone Number
                    </label>
                    <input
                      type="text"
                      value={picFormData.phone}
                      onChange={(e) => setPicFormData({ ...picFormData, phone: e.target.value })}
                      placeholder="+6012-345 6789"
                      className="w-full rounded-lg border border-[var(--rl-border)] px-3 py-2 text-xs focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                      Email Address
                    </label>
                    <input
                      type="email"
                      value={picFormData.email}
                      onChange={(e) => setPicFormData({ ...picFormData, email: e.target.value })}
                      placeholder="name@agency.com"
                      className="w-full rounded-lg border border-[var(--rl-border)] px-3 py-2 text-xs focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                    Operational Notes
                  </label>
                  <textarea
                    rows={2}
                    value={picFormData.notes}
                    onChange={(e) => setPicFormData({ ...picFormData, notes: e.target.value })}
                    placeholder="e.g. Always requests hardcopy roadtax, handles Johor corporate accounts"
                    className="w-full rounded-lg border border-[var(--rl-border)] px-3 py-2 text-xs focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-[var(--rl-border)]">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setIsPicModalOpen(false)}
                    disabled={savingPic}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={savingPic}
                    className="bg-[var(--rl-black)] hover:bg-black text-white text-xs font-semibold px-5"
                  >
                    {savingPic ? "Saving..." : editingPic ? "Save Changes" : "Create Record"}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
        {/* Edit Client Account Modal */}
        {isClientModalOpen && editingClient && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
            <div className="relative w-full max-w-lg bg-white rounded-xl shadow-2xl border border-[var(--rl-border)] overflow-hidden my-8 animate-in fade-in zoom-in-95 duration-200">
              <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--rl-border)] bg-[var(--rl-bg-surface)]">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-lg bg-[var(--rl-black)] text-white">
                    <UserCircle size={18} weight="bold" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-[var(--rl-text-strong)]">
                      Edit Customer Profile
                    </h2>
                    <p className="text-xs text-[var(--rl-text-muted)]">
                      Propagates across all tenures, quotations, and ledger records
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsClientModalOpen(false)}
                  className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-700 hover:bg-neutral-200/60 transition-colors cursor-pointer"
                >
                  <X size={18} weight="bold" />
                </button>
              </div>

              <form onSubmit={handleSaveClient} className="p-6 space-y-4">
                <div className="p-3.5 rounded-lg bg-blue-50/60 border border-blue-100 text-xs text-blue-900 leading-relaxed">
                  <strong>Master Customer Record:</strong> Updating this name or IC will synchronize across all policy tenures, marketing comparison matrices, and generated quotes for this customer.
                </div>

                <div>
                  <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                    Customer / Client Full Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={clientFormData.canonical_name}
                    onChange={(e) => setClientFormData({ ...clientFormData, canonical_name: e.target.value })}
                    placeholder="e.g. TAN JIN AUN"
                    className="w-full rounded-lg border border-[var(--rl-border)] px-3 py-2 text-xs focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                    Government ID / IC / Passport / BRN
                  </label>
                  <input
                    type="text"
                    value={clientFormData.id_number}
                    onChange={(e) => setClientFormData({ ...clientFormData, id_number: e.target.value })}
                    placeholder="e.g. 821021085432"
                    className="w-full font-mono rounded-lg border border-[var(--rl-border)] px-3 py-2 text-xs focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                      Phone Number
                    </label>
                    <input
                      type="text"
                      value={clientFormData.phone}
                      onChange={(e) => setClientFormData({ ...clientFormData, phone: e.target.value })}
                      placeholder="e.g. +60123456789"
                      className="w-full rounded-lg border border-[var(--rl-border)] px-3 py-2 text-xs focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                      Email Address
                    </label>
                    <input
                      type="email"
                      value={clientFormData.email}
                      onChange={(e) => setClientFormData({ ...clientFormData, email: e.target.value })}
                      placeholder="e.g. client@example.com"
                      className="w-full rounded-lg border border-[var(--rl-border)] px-3 py-2 text-xs focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-bold text-[var(--rl-text-strong)] block mb-1">
                    Notes / Habitual Preferences
                  </label>
                  <textarea
                    rows={2}
                    value={clientFormData.notes}
                    onChange={(e) => setClientFormData({ ...clientFormData, notes: e.target.value })}
                    placeholder="e.g. Always requests windscreen RM1,700 and flood cover"
                    className="w-full rounded-lg border border-[var(--rl-border)] px-3 py-2 text-xs focus:ring-1 focus:ring-[var(--rl-black)] focus:outline-none"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-[var(--rl-border)]">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setIsClientModalOpen(false)}
                    disabled={savingClient}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={savingClient}
                    className="bg-[var(--rl-black)] hover:bg-black text-white text-xs font-semibold px-5"
                  >
                    {savingClient ? "Saving..." : "Save & Propagate Everywhere"}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
