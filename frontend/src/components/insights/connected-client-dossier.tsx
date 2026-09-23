"use client";

import { useEffect, useState } from "react";
import {
  Car,
  CheckCircle,
  Clock,
  CurrencyDollar,
  Eye,
  Funnel,
  MagnifyingGlass,
  ArrowSquareOut,
  User,
  Users,
  XCircle,
  ArrowsClockwise,
  Buildings,
  Copy,
  DownloadSimple,
  FilePdf,
  Table,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { api, apiRaw } from "@/lib/api";
import { useToast } from "@/components/ui/toast";

interface ConnectedVehicle {
  vehicle_no: string;
  model: string;
  is_current?: boolean;
  is_pending_verification?: boolean;
}

interface ConnectedQuotation {
  session_id: string;
  quotation_number: string;
  created_at: string | null;
  company: string;
  vehicle_no: string;
  car_model: string;
  gross_premium: string;
  status: string;
  miss_reason?: string | null;
  closed_at?: string | null;
}

interface FleetBreakdown {
  lorry: number;
  motorcycle: number;
  suv: number;
  sedan: number;
  ev: number;
  other: number;
}

interface ClientDossier {
  customer_name: string;
  is_corporate?: boolean;
  client_type?: string;
  fleet_breakdown?: FleetBreakdown;
  connected_vehicles: ConnectedVehicle[];
  quotations: ConnectedQuotation[];
  stats: {
    total_quotations: number;
    hits: number;
    misses: number;
    pending: number;
    hit_rate_percent: number;
    won_premium_total: number;
    lost_premium_total: number;
  };
}

interface ClientDossierResponse {
  clients: ClientDossier[];
  pagination: {
    page: number;
    page_size: number;
    total_clients: number;
    total_pages: number;
  };
  summary: {
    total_unique_clients: number;
    total_connected_vehicles: number;
    total_quotations: number;
    global_hit_rate_percent: number;
    total_won_premium: number;
    total_lost_premium: number;
  };
}

export function ConnectedClientDossier({
  onOpenVehicleHistory,
}: {
  onOpenVehicleHistory: (vehicleNo: string) => void;
}) {
  const { toast } = useToast();
  const [data, setData] = useState<ClientDossierResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [clientTypeFilter, setClientTypeFilter] = useState<"all" | "Company" | "Individual">("all");
  const [page, setPage] = useState(1);
  const [expandedClient, setExpandedClient] = useState<string | null>(null);
  const [downloadingClientZip, setDownloadingClientZip] = useState<string | null>(null);

  async function fetchClients() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (clientTypeFilter !== "all") params.set("client_type", clientTypeFilter);
      params.set("page", String(page));
      params.set("page_size", "25");

      const res = await api<ClientDossierResponse>(`/insights/clients?${params.toString()}`);
      setData(res);
      // Auto expand first client if search returns 1
      if (res.clients.length === 1) {
        setExpandedClient(res.clients[0].customer_name);
      }
    } catch (e: any) {
      toast(e?.message || "Could not retrieve connected client records", "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchClients();
  }, [page, statusFilter, clientTypeFilter]);

  function copyClientPdfLinks(client: ClientDossier) {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const links = client.quotations.map((q) => `${origin}/api/sessions/${q.session_id}/pdf`);
    navigator.clipboard.writeText(links.join("\n"));
    toast(`Copied ${links.length} PDF link${links.length > 1 ? "s" : ""} for ${client.customer_name}.`, "success");
  }

  function copyClientFleetTable(client: ClientDossier) {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const headers = ["Vehicle Plate", "Model", "Insurer", "Gross Premium", "Quotation Number", "Status", "Date", "PDF Link"];
    const rows = client.quotations.map((q) => [
      q.vehicle_no || "—",
      q.car_model || "—",
      q.company || "—",
      q.gross_premium || "—",
      q.quotation_number || "—",
      q.status.toUpperCase(),
      q.created_at ? new Date(q.created_at).toLocaleDateString() : "—",
      `${origin}/api/sessions/${q.session_id}/pdf`,
    ]);
    const tsv = [headers.join("\t"), ...rows.map((r) => r.join("\t"))].join("\n");
    navigator.clipboard.writeText(tsv);
    toast(`Copied fleet table with ${client.quotations.length} quote(s) for Excel/Sheets.`, "success");
  }

  async function downloadClientZip(client: ClientDossier) {
    const sessionIds = client.quotations.map((q) => q.session_id);
    if (!sessionIds.length) return;
    setDownloadingClientZip(client.customer_name);
    try {
      toast(`Bundling ${sessionIds.length} quotation PDF(s) into ZIP...`, "info");
      const res = await apiRaw("/sessions/bulk-download-zip", {
        method: "POST",
        body: JSON.stringify({ session_ids: sessionIds }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson?.error?.message || "Failed to download client ZIP archive.");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safeName = client.customer_name.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 40);
      a.download = `Fleet_Quotes_${safeName}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast(`Downloaded ${a.download} successfully!`, "success");
    } catch (e: any) {
      toast(e?.message || "Could not download client ZIP archive.", "error");
    } finally {
      setDownloadingClientZip(null);
    }
  }

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    fetchClients();
  }

  function toggleExpand(name: string) {
    setExpandedClient((prev) => (prev === name ? null : name));
  }

  return (
    <div className="space-y-6">
      {/* Top Controls & Search Bar */}
      <div className="bg-white border border-neutral-200/90 rounded-lg p-4 shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-neutral-900 tracking-tight flex items-center gap-2">
            <Users size={17} className="text-[#1b1717]" />
            <span>Connected Client Records &amp; Vehicle Details</span>
          </h2>
          <p className="text-xs text-neutral-500">
            Intelligent CRM linking clients, sequential vehicle ownerships, past quotations, and hit/miss conversion.
          </p>
        </div>

        <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
          <div className="relative">
            <MagnifyingGlass size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              placeholder="Search client, plate, insurer..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="text-xs pl-8 pr-3 h-8 rounded-md border border-neutral-200 w-64 bg-white focus:ring-1 focus:ring-neutral-900 text-neutral-900"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="text-xs h-8 border border-neutral-200 rounded-md px-2 bg-white text-neutral-800"
          >
            <option value="all">All Outcomes</option>
            <option value="hit">Has Hits (Won)</option>
            <option value="miss">Has Misses (Lost)</option>
            <option value="pending">Pending Only</option>
          </select>

          <select
            value={clientTypeFilter}
            onChange={(e) => {
              setClientTypeFilter(e.target.value as any);
              setPage(1);
            }}
            className="text-xs h-8 border border-neutral-200 rounded-md px-2 bg-white text-neutral-800 font-medium"
          >
            <option value="all">All Account Types</option>
            <option value="Company">🏢 Corporate Fleets</option>
            <option value="Individual">👤 Private Individuals</option>
          </select>

          <Button
            type="submit"
            size="sm"
            variant="secondary"
            className="text-xs h-8 px-3 border-neutral-200 text-neutral-700 hover:bg-neutral-50"
          >
            Search
          </Button>

          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => {
              setSearch("");
              setStatusFilter("all");
              setClientTypeFilter("all");
              setPage(1);
              fetchClients();
            }}
            className="text-xs h-8 px-2 border-neutral-200 text-neutral-500 hover:text-neutral-900"
            title="Reset filters"
          >
            <ArrowsClockwise size={13} />
          </Button>
        </form>
      </div>

      {/* KPI Cards Header */}
      {data?.summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="p-3 bg-white border border-neutral-200/90 rounded-lg shadow-xs">
            <div className="text-[11px] font-medium text-neutral-500">Unique Clients</div>
            <div className="text-lg font-bold text-neutral-900 mt-0.5">
              {data.summary.total_unique_clients}
            </div>
          </div>

          <div className="p-3 bg-white border border-neutral-200/90 rounded-lg shadow-xs">
            <div className="text-[11px] font-medium text-neutral-500">Connected Vehicles</div>
            <div className="text-lg font-bold text-neutral-900 mt-0.5">
              {data.summary.total_connected_vehicles}
            </div>
          </div>

          <div className="p-3 bg-white border border-neutral-200/90 rounded-lg shadow-xs">
            <div className="text-[11px] font-medium text-neutral-500">Total Quotations</div>
            <div className="text-lg font-bold text-neutral-900 mt-0.5">
              {data.summary.total_quotations}
            </div>
          </div>

          <div className="p-3 bg-white border border-neutral-200/90 rounded-lg shadow-xs">
            <div className="text-[11px] font-medium text-neutral-500">Client Win Rate</div>
            <div className="text-lg font-bold text-emerald-600 mt-0.5">
              {data.summary.global_hit_rate_percent}%
            </div>
          </div>

          <div className="p-3 bg-white border border-neutral-200/90 rounded-lg shadow-xs">
            <div className="text-[11px] font-medium text-neutral-500">Total Won Premium</div>
            <div className="text-lg font-bold text-emerald-700 mt-0.5">
              RM {data.summary.total_won_premium.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
          </div>

          <div className="p-3 bg-white border border-neutral-200/90 rounded-lg shadow-xs">
            <div className="text-[11px] font-medium text-neutral-500">Total Lost Premium</div>
            <div className="text-lg font-bold text-rose-700 mt-0.5">
              RM {data.summary.total_lost_premium.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
          </div>
        </div>
      )}

      {/* Clients Dossier List */}
      {loading ? (
        <div className="bg-white border border-neutral-200 rounded-lg p-16 text-center shadow-sm">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-neutral-300 border-t-[#1b1717] mb-3" />
          <p className="text-xs text-neutral-500 font-medium">Loading connected client records and vehicles...</p>
        </div>
      ) : !data || data.clients.length === 0 ? (
        <div className="bg-white border border-neutral-200 rounded-lg p-12 text-center shadow-sm space-y-2">
          <p className="text-xs font-semibold text-neutral-700">No client records found.</p>
          <p className="text-xs text-neutral-500">
            Upload new quotations or run "Sync Past Sessions" to connect historical clients.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.clients.map((client) => {
            const isExpanded = expandedClient === client.customer_name;
            const initials = client.customer_name
              .split(" ")
              .slice(0, 2)
              .map((n) => n[0])
              .join("")
              .toUpperCase();

            return (
              <div
                key={client.customer_name}
                className="bg-white border border-neutral-200 rounded-lg shadow-xs overflow-hidden transition-all"
              >
                {/* Client Card Header */}
                <div
                  onClick={() => toggleExpand(client.customer_name)}
                  className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 cursor-pointer hover:bg-neutral-50/70 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-md bg-[#1b1717] text-white font-bold text-xs flex items-center justify-center shrink-0">
                      {initials || <User size={16} />}
                    </div>

                    <div>
                      <h3 className="text-sm font-bold text-neutral-900 flex items-center gap-2 flex-wrap">
                        <span>{client.customer_name}</span>
                        {client.is_corporate ? (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 uppercase tracking-wide">
                            🏢 Corporate Fleet
                          </span>
                        ) : null}
                        <span className="text-[11px] font-medium px-2 py-0.2 rounded-md bg-neutral-100 text-neutral-600 border border-neutral-200">
                          {client.stats.total_quotations} {client.stats.total_quotations === 1 ? "quote" : "quotes"}
                        </span>
                      </h3>

                      {/* Fleet Breakdown Mix Pills for Corporate Accounts */}
                      {client.is_corporate && client.fleet_breakdown && (
                        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                          <span className="text-[10px] text-indigo-700 font-bold uppercase tracking-wider">
                            Fleet Mix:
                          </span>
                          {client.fleet_breakdown.lorry > 0 && (
                            <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-neutral-100 text-neutral-700 border border-neutral-200">
                              🚚 {client.fleet_breakdown.lorry} {client.fleet_breakdown.lorry === 1 ? "Lorry" : "Lorries"}
                            </span>
                          )}
                          {client.fleet_breakdown.motorcycle > 0 && (
                            <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-neutral-100 text-neutral-700 border border-neutral-200">
                              🏍️ {client.fleet_breakdown.motorcycle} {client.fleet_breakdown.motorcycle === 1 ? "Motorcycle" : "Motorcycles"}
                            </span>
                          )}
                          {client.fleet_breakdown.suv > 0 && (
                            <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-neutral-100 text-neutral-700 border border-neutral-200">
                              🚙 {client.fleet_breakdown.suv} SUVs
                            </span>
                          )}
                          {client.fleet_breakdown.sedan > 0 && (
                            <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-neutral-100 text-neutral-700 border border-neutral-200">
                              🚗 {client.fleet_breakdown.sedan} Sedans
                            </span>
                          )}
                          {client.fleet_breakdown.ev > 0 && (
                            <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                              ⚡ {client.fleet_breakdown.ev} EVs
                            </span>
                          )}
                        </div>
                      )}

                      {/* Connected Vehicles Pills */}
                      <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                        <span className="text-[10px] text-neutral-400 font-semibold uppercase tracking-wider">
                          Vehicles:
                        </span>
                        {client.connected_vehicles.length === 0 ? (
                          <span className="text-[11px] text-neutral-400">None tracked</span>
                        ) : (
                          client.connected_vehicles.map((v) => (
                            <button
                              key={v.vehicle_no}
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                onOpenVehicleHistory(v.vehicle_no);
                              }}
                              className="inline-flex items-center gap-1.5 text-[11px] font-mono px-2 py-0.5 rounded bg-neutral-50 border border-neutral-200 text-neutral-800 hover:bg-neutral-100 hover:border-neutral-300 transition-colors"
                              title="View Vehicle Timeline"
                            >
                              <Car size={13} className="text-neutral-500" />
                              <span className="font-bold">{v.vehicle_no}</span>
                              {v.is_pending_verification && (
                                <span className="text-[9px] font-sans font-medium px-1 rounded bg-amber-50 text-amber-700 border border-amber-200">
                                  Pending Verification
                                </span>
                              )}
                            </button>
                          ))
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right Conversion Stats */}
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right">
                      <div className="text-xs font-bold text-neutral-900">
                        {client.stats.hits} Won · {client.stats.misses} Lost
                      </div>
                      <div className="text-[11px] text-emerald-700 font-semibold">
                        RM {client.stats.won_premium_total.toLocaleString()} Won
                      </div>
                    </div>

                    <span
                      className={`text-xs font-bold px-2.5 py-1 rounded-md border ${
                        client.stats.hit_rate_percent >= 50
                          ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                          : client.stats.hit_rate_percent > 0
                          ? "bg-amber-50 text-amber-800 border-amber-200"
                          : "bg-neutral-100 text-neutral-600 border-neutral-200"
                      }`}
                    >
                      {client.stats.hit_rate_percent}% Win
                    </span>
                  </div>
                </div>

                {/* Collapsible Quotations Table */}
                {isExpanded && (
                  <div className="border-t border-neutral-200 bg-neutral-50/50 p-4 space-y-3">
                    <div className="text-xs font-semibold text-neutral-700 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span>Connected Quotations ({client.quotations.length})</span>
                        <span className="text-[11px] text-neutral-400 font-normal">Click session to open workspace</span>
                      </div>

                      {/* Quick 1-Click Fleet Export Actions */}
                      <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => copyClientPdfLinks(client)}
                          className="text-xs h-7 px-2 border-neutral-200 text-neutral-700 hover:bg-neutral-100"
                          title="Copy direct PDF links to clipboard"
                        >
                          <Copy size={13} />
                          Copy PDF Links
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => copyClientFleetTable(client)}
                          className="text-xs h-7 px-2 border-neutral-200 text-neutral-700 hover:bg-neutral-100"
                          title="Copy structured table for Excel, Google Sheets, or WhatsApp"
                        >
                          <Table size={13} />
                          Copy Fleet Table
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={downloadingClientZip === client.customer_name}
                          onClick={() => downloadClientZip(client)}
                          className="text-xs h-7 px-2 border-neutral-200 text-neutral-700 hover:bg-neutral-100"
                          title="Download all quotation PDFs in a single ZIP file"
                        >
                          <DownloadSimple size={13} />
                          Download ZIP
                        </Button>
                      </div>
                    </div>

                    <div className="bg-white border border-neutral-200 rounded-md overflow-hidden">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-neutral-100 text-neutral-600 border-b border-neutral-200 font-semibold text-[11px]">
                          <tr>
                            <th className="p-2.5">Quotation Ref</th>
                            <th className="p-2.5">Date</th>
                            <th className="p-2.5">Vehicle</th>
                            <th className="p-2.5">Insurer</th>
                            <th className="p-2.5">Premium</th>
                            <th className="p-2.5">Status</th>
                            <th className="p-2.5 text-right">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-100">
                          {client.quotations.map((q) => {
                            const isHit = q.status === "hit";
                            const isMiss = q.status === "miss";

                            return (
                              <tr key={q.session_id} className="hover:bg-neutral-50/70 transition-colors">
                                <td className="p-2.5 font-bold text-neutral-900">{q.quotation_number}</td>
                                <td className="p-2.5 text-neutral-500">
                                  {q.created_at ? new Date(q.created_at).toLocaleDateString() : "—"}
                                </td>
                                <td className="p-2.5 font-mono text-neutral-800 font-semibold">{q.vehicle_no}</td>
                                <td className="p-2.5 text-neutral-700">{q.company}</td>
                                <td className="p-2.5 font-semibold text-neutral-900">{q.gross_premium || "—"}</td>
                                <td className="p-2.5">
                                  {isHit && (
                                    <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                                      <CheckCircle size={12} weight="bold" />
                                      HIT
                                    </span>
                                  )}
                                  {isMiss && (
                                    <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-200">
                                      <XCircle size={12} weight="bold" />
                                      MISS {q.miss_reason ? `(${q.miss_reason})` : ""}
                                    </span>
                                  )}
                                  {!isHit && !isMiss && (
                                    <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-neutral-100 text-neutral-700">
                                      Pending
                                    </span>
                                  )}
                                </td>
                                <td className="p-2.5 text-right">
                                  <div className="inline-flex items-center gap-1">
                                    <a
                                      href={`/api/sessions/${q.session_id}/pdf`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      title="View / Download PDF"
                                      className="inline-flex items-center gap-1 text-xs text-red-600 hover:text-red-800 font-medium px-2 py-1 rounded border border-neutral-200 hover:bg-red-50 transition-colors"
                                    >
                                      <FilePdf size={13} weight="bold" />
                                      PDF
                                    </a>
                                    <a
                                      href={`/sessions/${q.session_id}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-xs text-neutral-700 hover:text-neutral-950 font-medium px-2 py-1 rounded border border-neutral-200 hover:bg-neutral-100 transition-colors"
                                    >
                                      <ArrowSquareOut size={13} />
                                      Open
                                    </a>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Pagination Controls */}
          {data.pagination && data.pagination.total_pages > 1 && (
            <div className="p-4 border-t border-neutral-200 flex items-center justify-between text-xs text-neutral-600">
              <div>
                Page {data.pagination.page} of {data.pagination.total_pages} ({data.pagination.total_clients} clients total)
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="text-xs h-7"
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page >= data.pagination.total_pages}
                  onClick={() => setPage((p) => Math.min(data.pagination.total_pages, p + 1))}
                  className="text-xs h-7"
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
