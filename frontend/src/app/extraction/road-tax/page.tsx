"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import {
  Plus,
  FloppyDisk,
  Trash,
  PencilSimple,
  DownloadSimple,
  UploadSimple,
  Calculator,
  ArrowClockwise,
  Sparkle,
  Info,
  CheckCircle,
} from "@phosphor-icons/react";
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

type CalculationBreakdown = {
  engine_cc: number;
  vehicle_type: string;
  owner_type: string;
  jurisdiction: string;
  base_rate: number;
  progressive_rate: number;
  excess_cc: number;
  progressive_amount: number;
  total_road_tax: number;
  formula_text: string;
  matched_tier: string;
};

const VEHICLE_TYPES = ["Car", "Motorcycle", "Lorry"];
const OWNER_TYPES = ["Individual", "Company"];
const JURISDICTIONS = ["West Malaysia", "Sabah", "Sarawak", "Labuan"];
const JURISDICTION_TABS = ["All", "West Malaysia", "Sabah", "Sarawak", "Labuan"] as const;

const RATE_TABLES = [
  { vehicle: "Car", owner: "Individual", title: "Car — Private (Individual)" },
  { vehicle: "Car", owner: "Company", title: "Car — Company (Corporate)" },
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
  const [selectedJurisdiction, setSelectedJurisdiction] = useState<string>("All");
  const [isSeeding, setIsSeeding] = useState(false);

  // Live Calculator State
  const [calcVehicle, setCalcVehicle] = useState("Car");
  const [calcOwner, setCalcOwner] = useState("Individual");
  const [calcJur, setCalcJur] = useState("West Malaysia");
  const [calcCc, setCalcCc] = useState<number | string>(1998);
  const [breakdown, setBreakdown] = useState<CalculationBreakdown | null>(null);
  const [calculating, setCalculating] = useState(false);

  const [f, setF] = useState({
    vehicle_type: "Car",
    owner_type: "Individual",
    jurisdiction: "West Malaysia",
    min_cc: "0",
    max_cc: "",
    base_rate: "0",
    formula: "",
    source: "",
    effective_from: "",
    effective_to: "",
    status: "active",
  });
  const fileRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const load = useCallback(async () => {
    try {
      const data = await api<{ rules: RoadTaxRule[] }>("/admin/road-tax-rules");
      setRules(data.rules);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }, []);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  // Trigger calculation whenever calculator inputs change
  const runLiveCalculation = useCallback(async () => {
    const numCc = typeof calcCc === "string" ? parseInt(calcCc, 10) : calcCc;
    if (!numCc || isNaN(numCc) || numCc <= 0) {
      setBreakdown(null);
      return;
    }
    setCalculating(true);
    try {
      const res = await api<{ breakdown: CalculationBreakdown }>("/admin/road-tax-rules/calculate", {
        method: "POST",
        body: JSON.stringify({
          cc: numCc,
          vehicle_type: calcVehicle,
          owner_type: calcOwner,
          jurisdiction: calcJur,
        }),
      });
      setBreakdown(res.breakdown);
    } catch {
      // Fallback
    } finally {
      setCalculating(false);
    }
  }, [calcCc, calcVehicle, calcOwner, calcJur]);

  useEffect(() => {
    const timer = setTimeout(() => {
      runLiveCalculation();
    }, 250);
    return () => clearTimeout(timer);
  }, [runLiveCalculation]);

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
      const res = await fetch(`${API_BASE}/admin/road-tax-rules/import`, {
        method: "POST",
        body: form,
        credentials: "include",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Import failed.");
      toast(
        `Import done: ${data.created || 0} created, ${data.updated || 0} updated${
          data.errors?.length ? `, ${data.errors.length} errors` : ""
        }.`,
        "success"
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed.");
    }
    if (fileRef.current) fileRef.current.value = "";
  }

  async function handleSeedStandard() {
    setIsSeeding(true);
    setError("");
    try {
      const res = await api<{ result: { created: number; updated: number; total: number } }>(
        "/admin/road-tax-rules/seed-standard",
        { method: "POST" }
      );
      toast(
        `Standard JPJ Rules seeded! ${res.result.created} created, ${res.result.updated} updated (${res.result.total} rules).`,
        "success"
      );
      await load();
      runLiveCalculation();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setIsSeeding(false);
    }
  }

  function reset() {
    setF({
      vehicle_type: "Car",
      owner_type: "Individual",
      jurisdiction: "West Malaysia",
      min_cc: "0",
      max_cc: "",
      base_rate: "0",
      formula: "",
      source: "",
      effective_from: "",
      effective_to: "",
      status: "active",
    });
    setEditId(null);
    setShowForm(false);
  }

  function startEdit(r: RoadTaxRule) {
    setEditId(r.id);
    setF({
      vehicle_type: r.vehicle_type,
      owner_type: r.owner_type,
      jurisdiction: r.jurisdiction,
      min_cc: String(r.min_cc),
      max_cc: r.max_cc != null ? String(r.max_cc) : "",
      base_rate: String(r.base_rate),
      formula: r.formula || "",
      source: r.source || "",
      effective_from: r.effective_from || "",
      effective_to: r.effective_to || "",
      status: r.status,
    });
    setShowForm(true);
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const payload: Record<string, string | number | null> = {
        vehicle_type: f.vehicle_type,
        owner_type: f.owner_type,
        jurisdiction: f.jurisdiction,
        min_cc: parseInt(f.min_cc) || 0,
        max_cc: f.max_cc ? parseInt(f.max_cc) : null,
        base_rate: parseFloat(f.base_rate) || 0,
        formula: f.formula || null,
        source: f.source || null,
        effective_from: f.effective_from || null,
        effective_to: f.effective_to || null,
        status: f.status,
      };
      if (editId) payload.id = editId;
      await api("/admin/road-tax-rules", { method: "POST", body: JSON.stringify(payload) });
      reset();
      toast(editId ? "Rule updated." : "Rule created.", "success");
      await load();
      runLiveCalculation();
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

  // Filter rules by selected jurisdiction tab
  const filteredRules = useMemo(() => {
    if (selectedJurisdiction === "All") return rules;
    return rules.filter((r) => r.jurisdiction === selectedJurisdiction);
  }, [rules, selectedJurisdiction]);

  const lorryRules = useMemo(() => {
    return filteredRules.filter((r) => r.vehicle_type === "Lorry");
  }, [filteredRules]);

  return (
    <AppShell>
      <section className="grid gap-6">
        {/* Top Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[28px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">
              Malaysian Road Tax Schedule & Formulas
            </h1>
            <p className="text-[13px] text-[var(--rl-text-muted)]">
              Official JPJ schedules across West Malaysia, Sabah, Sarawak, and Labuan. Progressive formulas calculate road tax automatically even when missing from insurer quotes.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon={<Sparkle size={14} weight="fill" className={isSeeding ? "animate-spin" : "text-amber-500"} />}
              onClick={handleSeedStandard}
              disabled={isSeeding}
              title="Populate/restore all official JPJ schedules across all regions"
            >
              {isSeeding ? "Seeding..." : "Seed Standard JPJ Rules"}
            </Button>
            <Button variant="secondary" size="sm" icon={<DownloadSimple size={14} weight="bold" />} onClick={exportCsv}>
              Export CSV
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={<UploadSimple size={14} weight="bold" />}
              onClick={() => fileRef.current?.click()}
            >
              Import CSV/Excel
            </Button>
            <input ref={fileRef} className="hidden" type="file" accept=".csv,.xlsx" onChange={importFile} />
            <Button
              size="sm"
              icon={<Plus size={14} weight="bold" />}
              onClick={() => {
                reset();
                setShowForm((v) => !v);
              }}
            >
              New rule
            </Button>
          </div>
        </div>

        <ExtractionNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        {/* ── Interactive Live Road Tax Calculator Card ───────────────── */}
        <Card className="border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-3">
            <div className="flex items-center gap-2">
              <div className="grid h-8 w-8 place-items-center rounded-[var(--rl-radius-sm)] bg-[var(--rl-black)] text-white">
                <Calculator size={18} weight="bold" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">
                  Live Dynamic Road Tax Tester
                </h3>
                <p className="text-[11px] text-[var(--rl-text-muted)]">
                  Simulate any vehicle, engine CC, ownership type, and jurisdiction to test formula calculation in real time.
                </p>
              </div>
            </div>
            <Badge variant="success">Formula-Driven Engine</Badge>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                Vehicle Type
              </label>
              <Select value={calcVehicle} onChange={(e) => setCalcVehicle(e.target.value)} className="mt-1 text-xs">
                {VEHICLE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                Ownership
              </label>
              <Select value={calcOwner} onChange={(e) => setCalcOwner(e.target.value)} className="mt-1 text-xs">
                {OWNER_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                Jurisdiction / Region
              </label>
              <Select value={calcJur} onChange={(e) => setCalcJur(e.target.value)} className="mt-1 text-xs">
                {JURISDICTIONS.map((j) => (
                  <option key={j} value={j}>
                    {j}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                Engine Capacity (CC)
              </label>
              <Input
                type="number"
                value={calcCc}
                onChange={(e) => setCalcCc(e.target.value)}
                placeholder="e.g. 1998"
                className="mt-1 text-xs font-mono font-bold"
              />
            </div>
          </div>

          {/* Result Strip */}
          {breakdown && (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-[var(--rl-radius-sm)] border border-emerald-200 bg-emerald-50/70 p-3.5 text-emerald-950">
              <div className="flex items-center gap-3">
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-emerald-600 text-white">
                  <CheckCircle size={20} weight="fill" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-emerald-800">
                      Calculated Malaysian Road Tax:
                    </span>
                    <span className="font-mono text-lg font-bold text-emerald-900">
                      RM {breakdown.total_road_tax.toFixed(2)}
                    </span>
                    <span className="rounded bg-emerald-200/80 px-2 py-0.5 text-[10px] font-bold text-emerald-900">
                      {breakdown.matched_tier}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-emerald-700">
                    <span className="font-semibold">Calculation Breakdown:</span> {breakdown.formula_text}
                    {breakdown.progressive_rate > 0 && (
                      <span className="ml-1 text-[11px] text-emerald-800 font-medium">
                        (Base: RM {breakdown.base_rate.toFixed(2)} + Excess: RM {breakdown.progressive_amount.toFixed(2)})
                      </span>
                    )}
                  </p>
                </div>
              </div>

              <div className="text-right">
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700">
                  {breakdown.jurisdiction} · {breakdown.vehicle_type} ({breakdown.owner_type})
                </span>
                <p className="font-mono text-xs font-bold text-emerald-900">
                  {breakdown.engine_cc} cc
                </p>
              </div>
            </div>
          )}
        </Card>

        {/* ── Edit / Create Form ──────────────────────────────────────── */}
        {showForm ? (
          <Card>
            <form className="grid gap-4 p-4" onSubmit={save}>
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">
                {editId ? "Edit road-tax rule" : "New road-tax rule"}
              </h2>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Vehicle type</label>
                  <Select value={f.vehicle_type} onChange={(e) => setF({ ...f, vehicle_type: e.target.value })}>
                    {VEHICLE_TYPES.map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Owner type</label>
                  <Select value={f.owner_type} onChange={(e) => setF({ ...f, owner_type: e.target.value })}>
                    {OWNER_TYPES.map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Jurisdiction</label>
                  <Select value={f.jurisdiction} onChange={(e) => setF({ ...f, jurisdiction: e.target.value })}>
                    {JURISDICTIONS.map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Min CC</label>
                  <Input type="number" value={f.min_cc} onChange={(e) => setF({ ...f, min_cc: e.target.value })} />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Max CC (blank = no limit)</label>
                  <Input
                    type="number"
                    value={f.max_cc}
                    onChange={(e) => setF({ ...f, max_cc: e.target.value })}
                    placeholder="No limit"
                  />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Status</label>
                  <Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </Select>
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Base rate (RM)</label>
                  <Input
                    type="number"
                    step="0.01"
                    value={f.base_rate}
                    onChange={(e) => setF({ ...f, base_rate: e.target.value })}
                  />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">
                    Progressive Formula (e.g. 280 + ((cc - 1800) * 0.50))
                  </label>
                  <Input
                    value={f.formula}
                    onChange={(e) => setF({ ...f, formula: e.target.value })}
                    placeholder="Leave blank for flat base rate"
                  />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Effective from</label>
                  <Input
                    type="date"
                    value={f.effective_from}
                    onChange={(e) => setF({ ...f, effective_from: e.target.value })}
                  />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Effective to</label>
                  <Input
                    type="date"
                    value={f.effective_to}
                    onChange={(e) => setF({ ...f, effective_to: e.target.value })}
                  />
                </div>
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Source / Reference</label>
                <Input
                  value={f.source}
                  onChange={(e) => setF({ ...f, source: e.target.value })}
                  placeholder="e.g. JPJ Peninsular Schedule"
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" icon={<FloppyDisk size={14} weight="bold" />}>
                  Save
                </Button>
                <Button variant="secondary" size="sm" onClick={reset}>
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        ) : null}

        {/* ── Jurisdiction Filter Tabs ─────────────────────────────────── */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-2">
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mr-1">
              Filter Region:
            </span>
            {JURISDICTION_TABS.map((tab) => {
              const active = selectedJurisdiction === tab;
              const count = tab === "All" ? rules.length : rules.filter((r) => r.jurisdiction === tab).length;
              return (
                <button
                  key={tab}
                  onClick={() => setSelectedJurisdiction(tab)}
                  className={`flex items-center gap-1.5 rounded-[var(--rl-radius-sm)] px-3 py-1 text-xs font-semibold transition-all ${
                    active
                      ? "bg-[var(--rl-black)] text-white shadow-sm"
                      : "border border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                  }`}
                >
                  <span>{tab}</span>
                  <span className={`text-[10px] ${active ? "text-neutral-300" : "text-[var(--rl-text-muted)]"}`}>
                    ({count})
                  </span>
                </button>
              );
            })}
          </div>

          <span className="text-xs font-semibold text-[var(--rl-text-muted)]">
            Showing {filteredRules.length} of {rules.length} configured rules
          </span>
        </div>

        {/* ── Main Rate Tables (Car & Motorcycle) ─────────────────────── */}
        {RATE_TABLES.map(({ vehicle, owner, title }) => {
          const items = filteredRules
            .filter((r) => r.vehicle_type === vehicle && r.owner_type === owner)
            .sort((a, b) => a.min_cc - b.min_cc);

          return (
            <div key={title} className="grid gap-3">
              <div className="flex items-center justify-between">
                <h2 className="text-[12px] font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                  {title} ({items.length} Rules)
                </h2>
                {selectedJurisdiction !== "All" && (
                  <span className="text-[11px] font-medium text-[var(--rl-text-muted)]">
                    Region: {selectedJurisdiction}
                  </span>
                )}
              </div>

              <Card>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[860px]">
                    <thead>
                      <tr className="border-b border-[var(--rl-border)] bg-[var(--rl-bg)]">
                        <th className="px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                          CC Range
                        </th>
                        <th className="px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                          Base Rate
                        </th>
                        <th className="px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                          Progressive Calculation Formula
                        </th>
                        <th className="px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                          Jurisdiction
                        </th>
                        <th className="px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                          Source / Schedule
                        </th>
                        <th className="px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                          Status
                        </th>
                        <th className="px-4 py-2.5 text-right text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--rl-border)]/60">
                      {items.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="px-4 py-6 text-center text-xs text-[var(--rl-text-muted)] italic">
                            No rules found for {title} in {selectedJurisdiction}. Click &quot;Seed Standard JPJ Rules&quot; above to restore.
                          </td>
                        </tr>
                      ) : (
                        items.map((r) => (
                          <tr
                            key={r.id}
                            className={`hover:bg-[var(--rl-bg)]/50 transition-colors ${
                              r.status !== "active" ? "opacity-50" : ""
                            }`}
                          >
                            <td className="px-4 py-2.5 text-[13px] font-mono font-bold text-[var(--rl-text-strong)]">
                              {r.min_cc}
                              {r.max_cc != null ? ` – ${r.max_cc} cc` : "+ cc"}
                            </td>
                            <td className="px-4 py-2.5 text-[13px] font-semibold text-emerald-700">
                              RM {r.base_rate.toFixed(2)}
                            </td>
                            <td className="px-4 py-2.5 text-[12px] font-mono text-[var(--rl-text-muted)]">
                              {r.formula ? (
                                <span className="rounded bg-blue-50 text-blue-800 border border-blue-200 px-1.5 py-0.5">
                                  {r.formula}
                                </span>
                              ) : (
                                <span className="text-[var(--rl-text-muted)] italic">Flat rate</span>
                              )}
                            </td>
                            <td className="px-4 py-2.5 text-[12px] font-medium text-[var(--rl-text-strong)]">
                              {r.jurisdiction}
                            </td>
                            <td className="px-4 py-2.5 text-[11px] text-[var(--rl-text-muted)] truncate max-w-[180px]">
                              {r.source || "JPJ Schedule"}
                            </td>
                            <td className="px-4 py-2.5">
                              <Badge variant={r.status === "active" ? "success" : "default"}>
                                {r.status}
                              </Badge>
                            </td>
                            <td className="px-4 py-2.5 text-right">
                              <div className="flex items-center justify-end gap-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={<PencilSimple size={14} weight="bold" />}
                                  onClick={() => startEdit(r)}
                                  title="Edit"
                                />
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={<Trash size={14} weight="bold" />}
                                  onClick={() => setPendingDelete(r)}
                                  title="Delete"
                                  className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]"
                                />
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

        {/* ── Commercial Lorry Section ─────────────────────────────────── */}
        {lorryRules.length > 0 && (
          <div className="grid gap-3">
            <h2 className="text-[12px] font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
              Commercial Lorry & Goods Vehicles ({lorryRules.length} Rules)
            </h2>
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[860px]">
                  <thead>
                    <tr className="border-b border-[var(--rl-border)] bg-[var(--rl-bg)]">
                      <th className="px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                        CC Range
                      </th>
                      <th className="px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                        Base Rate
                      </th>
                      <th className="px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                        Ownership
                      </th>
                      <th className="px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                        Jurisdiction
                      </th>
                      <th className="px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                        Status
                      </th>
                      <th className="px-4 py-2.5 text-right text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--rl-border)]/60">
                    {lorryRules.map((r) => (
                      <tr
                        key={r.id}
                        className={`hover:bg-[var(--rl-bg)]/50 transition-colors ${
                          r.status !== "active" ? "opacity-50" : ""
                        }`}
                      >
                        <td className="px-4 py-2.5 text-[13px] font-mono font-bold text-[var(--rl-text-strong)]">
                          {r.min_cc}
                          {r.max_cc != null ? ` – ${r.max_cc} cc` : "+ cc"}
                        </td>
                        <td className="px-4 py-2.5 text-[13px] font-semibold text-emerald-700">
                          RM {r.base_rate.toFixed(2)}
                        </td>
                        <td className="px-4 py-2.5 text-[12px] font-medium text-[var(--rl-text-strong)]">
                          {r.owner_type}
                        </td>
                        <td className="px-4 py-2.5 text-[12px] font-medium text-[var(--rl-text-strong)]">
                          {r.jurisdiction}
                        </td>
                        <td className="px-4 py-2.5">
                          <Badge variant={r.status === "active" ? "success" : "default"}>
                            {r.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              icon={<PencilSimple size={14} weight="bold" />}
                              onClick={() => startEdit(r)}
                              title="Edit"
                            />
                            <Button
                              variant="ghost"
                              size="sm"
                              icon={<Trash size={14} weight="bold" />}
                              onClick={() => setPendingDelete(r)}
                              title="Delete"
                              className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]"
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        )}
      </section>

      {pendingDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => {
            if (!open) setPendingDelete(null);
          }}
          title="Delete this road-tax rule?"
          message={`${pendingDelete.vehicle_type} · ${pendingDelete.owner_type} · ${pendingDelete.jurisdiction} · ${pendingDelete.min_cc}cc+`}
          onConfirm={remove}
        />
      ) : null}
    </AppShell>
  );
}
