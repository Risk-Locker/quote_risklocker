"use client";

import { useEffect, useRef, useState } from "react";
import { Plus, FloppyDisk, Trash, PencilSimple, DownloadSimple, UploadSimple } from "@phosphor-icons/react";
import { ExtractionNav } from "@/components/extraction-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api, API_BASE } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type RoadTaxRule = {
  id: string;
  vehicle_type: string;
  owner_type: string;
  jurisdiction: string;
  min_cc: number;
  max_cc: number | null;
  base_rate: number;
  formula: string | null;
  source: string | null;
  effective_from: string | null;
  effective_to: string | null;
  status: string;
};

const VEHICLE_TYPES = ["Car", "Motorcycle", "Lorry"];
const OWNER_TYPES = ["Individual", "Company"];
const JURISDICTIONS = ["West Malaysia", "Sabah", "Sarawak", "Labuan"];

const RATE_TABLES = [
  { vehicle: "Car", owner: "Individual", title: "Car — Private" },
  { vehicle: "Car", owner: "Company", title: "Car — Company" },
  { vehicle: "Motorcycle", owner: "Individual", title: "Motorcycle — Private" },
  { vehicle: "Motorcycle", owner: "Company", title: "Motorcycle — Company" },
] as const;

function formatEffective(r: RoadTaxRule) {
  if (!r.effective_from && !r.effective_to) return "-";
  const from = r.effective_from ?? "—";
  const to = r.effective_to ?? "—";
  return `${from} – ${to}`;
}

export default function RoadTaxPage() {
  const [rules, setRules] = useState<RoadTaxRule[]>([]);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<RoadTaxRule | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [f, setF] = useState({ vehicle_type: "Car", owner_type: "Individual", jurisdiction: "West Malaysia", min_cc: "0", max_cc: "", base_rate: "0", formula: "", source: "", effective_from: "", effective_to: "", status: "active" });
  const fileRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  async function load() {
    const data = await api<{ rules: RoadTaxRule[] }>("/admin/road-tax-rules");
    setRules(data.rules);
  }
  useEffect(() => { load().catch(() => {}); }, []);

  function exportCsv() {
    window.location.href = `${API_BASE}/admin/road-tax-rules/export`;
  }

  async function importFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/admin/road-tax-rules/import`, { method: "POST", body: form, credentials: "include" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Import failed.");
      toast(`Import done: ${data.created || 0} created, ${data.updated || 0} updated${data.errors?.length ? `, ${data.errors.length} errors` : ""}.`, "success");
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Import failed."); }
    if (fileRef.current) fileRef.current.value = "";
  }

  function reset() { setF({ vehicle_type: "Car", owner_type: "Individual", jurisdiction: "West Malaysia", min_cc: "0", max_cc: "", base_rate: "0", formula: "", source: "", effective_from: "", effective_to: "", status: "active" }); setEditId(null); setShowForm(false); }

  function startEdit(r: RoadTaxRule) {
    setEditId(r.id);
    setF({ vehicle_type: r.vehicle_type, owner_type: r.owner_type, jurisdiction: r.jurisdiction, min_cc: String(r.min_cc), max_cc: r.max_cc != null ? String(r.max_cc) : "", base_rate: String(r.base_rate), formula: r.formula || "", source: r.source || "", effective_from: r.effective_from || "", effective_to: r.effective_to || "", status: r.status });
    setShowForm(true);
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const payload: Record<string, string | number | null> = {
        vehicle_type: f.vehicle_type, owner_type: f.owner_type, jurisdiction: f.jurisdiction,
        min_cc: parseInt(f.min_cc) || 0, max_cc: f.max_cc ? parseInt(f.max_cc) : null,
        base_rate: parseFloat(f.base_rate) || 0, formula: f.formula || null, source: f.source || null,
        effective_from: f.effective_from || null, effective_to: f.effective_to || null, status: f.status,
      };
      if (editId) payload.id = editId;
      await api("/admin/road-tax-rules", { method: "POST", body: JSON.stringify(payload) });
      reset();
      toast(editId ? "Rule updated." : "Rule created.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function remove() {
    if (!pendingDelete) return;
    setError("");
    try {
      await api(`/admin/road-tax-rules/${pendingDelete.id}`, { method: "DELETE" });
      toast("Rule deleted.", "success");
      setPendingDelete(null);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  const lorryRules = rules.filter((r) => r.vehicle_type === "Lorry");

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Road Tax</h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">Manage road-tax rates by vehicle type, owner type, jurisdiction and CC range.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" icon={<DownloadSimple size={14} weight="bold" />} onClick={exportCsv}>Export CSV</Button>
            <Button variant="secondary" size="sm" icon={<UploadSimple size={14} weight="bold" />} onClick={() => fileRef.current?.click()}>Import CSV/Excel</Button>
            <input ref={fileRef} className="hidden" type="file" accept=".csv,.xlsx" onChange={importFile} />
            <Button size="sm" icon={<Plus size={14} weight="bold" />} onClick={() => { reset(); setShowForm((v) => !v); }}>New rule</Button>
          </div>
        </div>
        <ExtractionNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

        {showForm ? (
          <Card>
            <form className="grid gap-4 p-4" onSubmit={save}>
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">{editId ? "Edit rule" : "New road-tax rule"}</h2>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Vehicle type</label>
                  <Select value={f.vehicle_type} onChange={(e) => setF({ ...f, vehicle_type: e.target.value })}>{VEHICLE_TYPES.map((t) => <option key={t}>{t}</option>)}</Select>
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Owner type</label>
                  <Select value={f.owner_type} onChange={(e) => setF({ ...f, owner_type: e.target.value })}>{OWNER_TYPES.map((t) => <option key={t}>{t}</option>)}</Select>
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Jurisdiction</label>
                  <Select value={f.jurisdiction} onChange={(e) => setF({ ...f, jurisdiction: e.target.value })}>{JURISDICTIONS.map((t) => <option key={t}>{t}</option>)}</Select>
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Min CC</label>
                  <Input type="number" value={f.min_cc} onChange={(e) => setF({ ...f, min_cc: e.target.value })} />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Max CC (blank = no limit)</label>
                  <Input type="number" value={f.max_cc} onChange={(e) => setF({ ...f, max_cc: e.target.value })} placeholder="No limit" />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Status</label>
                  <Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="active">Active</option><option value="inactive">Inactive</option></Select>
                </div>
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Base rate (RM)</label>
                <Input type="number" step="0.01" value={f.base_rate} onChange={(e) => setF({ ...f, base_rate: e.target.value })} />
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Effective from</label>
                <Input type="date" value={f.effective_from} onChange={(e) => setF({ ...f, effective_from: e.target.value })} />
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Effective to</label>
                <Input type="date" value={f.effective_to} onChange={(e) => setF({ ...f, effective_to: e.target.value })} />
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Formula (optional, e.g. 280 + 0.50 * (cc - 1800))</label>
                <Input value={f.formula} onChange={(e) => setF({ ...f, formula: e.target.value })} placeholder="Leave blank to use base rate" />
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Source / reference</label>
                <Input value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })} placeholder="e.g. JPJ 2024 Schedule" />
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" icon={<FloppyDisk size={14} weight="bold" />}>Save</Button>
                <Button variant="secondary" size="sm" onClick={reset}>Cancel</Button>
              </div>
            </form>
          </Card>
        ) : null}

        {RATE_TABLES.map(({ vehicle, owner, title }) => {
          const items = rules
            .filter((r) => r.vehicle_type === vehicle && r.owner_type === owner)
            .sort((a, b) => a.min_cc - b.min_cc);

          return (
            <div key={title} className="grid gap-3">
              <h2 className="text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">{title} ({items.length})</h2>
              <Card>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[800px]">
                    <thead>
                      <tr>
                        <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">CC Range</th>
                        <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Rate</th>
                        <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Jurisdiction</th>
                        <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Effective</th>
                        <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Status</th>
                        <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="px-4 py-4 text-center text-[13px] text-[var(--rl-text-muted)]">No rules yet.</td>
                        </tr>
                      ) : (
                        items.map((r) => (
                          <tr key={r.id} className={r.status !== "active" ? "opacity-50" : ""}>
                            <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{r.min_cc}{r.max_cc != null ? ` – ${r.max_cc}` : "+"}</td>
                            <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">RM {r.base_rate.toFixed(2)}</td>
                            <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{r.jurisdiction}</td>
                            <td className="px-4 py-2.5 text-[13px] text-[var(--rl-text-muted)]">{formatEffective(r)}</td>
                            <td className="px-4 py-2.5">
                              <Badge variant={r.status === "active" ? "success" : "default"}>{r.status}</Badge>
                            </td>
                            <td className="px-4 py-2.5">
                              <div className="flex gap-1">
                                <Button variant="ghost" size="sm" icon={<PencilSimple size={14} weight="bold" />} onClick={() => startEdit(r)} title="Edit" />
                                <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setPendingDelete(r)} title="Delete" />
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          );
        })}

        {lorryRules.length > 0 ? (
          <div className="grid gap-3">
            <h2 className="text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Lorry ({lorryRules.length})</h2>
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[800px]">
                  <thead>
                    <tr>
                      <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">CC Range</th>
                      <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Rate</th>
                      <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Owner</th>
                      <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Jurisdiction</th>
                      <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Effective</th>
                      <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Status</th>
                      <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {lorryRules.map((r) => (
                      <tr key={r.id} className={r.status !== "active" ? "opacity-50" : ""}>
                        <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{r.min_cc}{r.max_cc != null ? ` – ${r.max_cc}` : "+"}</td>
                        <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">RM {r.base_rate.toFixed(2)}</td>
                        <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{r.owner_type}</td>
                        <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{r.jurisdiction}</td>
                        <td className="px-4 py-2.5 text-[13px] text-[var(--rl-text-muted)]">{formatEffective(r)}</td>
                        <td className="px-4 py-2.5">
                          <Badge variant={r.status === "active" ? "success" : "default"}>{r.status}</Badge>
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex gap-1">
                            <Button variant="ghost" size="sm" icon={<PencilSimple size={14} weight="bold" />} onClick={() => startEdit(r)} title="Edit" />
                            <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setPendingDelete(r)} title="Delete" />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        ) : null}
      </section>

      {pendingDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingDelete(null); }}
          title="Delete this road-tax rule?"
          message={`${pendingDelete.vehicle_type} · ${pendingDelete.owner_type} · ${pendingDelete.jurisdiction} · ${pendingDelete.min_cc}cc+`}
          onConfirm={remove}
        />
      ) : null}
    </AppShell>
  );
}
