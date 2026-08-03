"use client";

import { useEffect, useState } from "react";
import { CaretDown, CaretUp, DownloadSimple, FloppyDisk, MagnifyingGlass, NotePencil, X } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type ClientRecord = {
  id: string;
  insurer_no: string;
  insurance_company?: string | null;
  vehicle_no?: string | null;
  customer_name?: string | null;
  coverage_type?: string | null;
  cover_period?: string | null;
  car_model?: string | null;
  ncd_percent?: string | null;
  ncd?: string | null;
  coverage_amount?: string | null;
  premium?: string | null;
  roadtax?: string | null;
  service_fee?: string | null;
  total_premium?: string | null;
  issue_date?: string | null;
  valid_until?: string | null;
  vehicle_year?: string | null;
  capacity?: string | null;
  engine_no?: string | null;
  chassis_no?: string | null;
  market_value?: string | null;
  agreed_value?: string | null;
  excess_amount?: string | null;
  basic_premium?: string | null;
  ncd_amount?: string | null;
  service_tax?: string | null;
  stamp_duty?: string | null;
  gross_premium?: string | null;
  optional_covers?: string | null;
  notes?: string | null;
  generated_at?: string | null;
  created_at: string;
};

const SORTABLE = [
  { key: "insurer_no", label: "Insurer No." },
  { key: "customer_name", label: "Customer" },
  { key: "vehicle_no", label: "Vehicle" },
  { key: "insurance_company", label: "Company" },
  { key: "created_at", label: "Date" },
];

const DETAIL_FIELDS: Array<[string, string]> = [
  ["customer_name", "Customer Name"], ["vehicle_no", "Vehicle No"], ["insurance_company", "Insurance Company"],
  ["coverage_type", "Coverage Type"], ["cover_period", "Cover Period"], ["car_model", "Car Model"],
  ["ncd_percent", "NCD %"], ["coverage_amount", "Coverage Amount"], ["premium", "Insurance Premium"],
  ["roadtax", "Roadtax"], ["service_fee", "Runner Fee"], ["total_premium", "Total Premium"],
  ["issue_date", "Issued Date"], ["valid_until", "Valid Until"], ["vehicle_year", "Vehicle Year"],
  ["capacity", "Capacity"], ["engine_no", "Engine/Motor No"], ["chassis_no", "Chassis No"],
  ["market_value", "Market Value"], ["agreed_value", "Agreed Value"], ["excess_amount", "Excess Amount"],
  ["basic_premium", "Basic Premium"], ["ncd_amount", "NCD Amount"], ["service_tax", "Service Tax"],
  ["stamp_duty", "Stamp Duty"], ["gross_premium", "Gross Premium"], ["optional_covers", "Optional Covers"],
  ["notes", "Notes"],
];

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-MY", { day: "2-digit", month: "short", year: "numeric" });
}

export default function ClientRecordsPage() {
  const [records, setRecords] = useState<ClientRecord[]>([]);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editInsurerNo, setEditInsurerNo] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    params.set("sort_by", sortBy);
    params.set("sort_dir", sortDir);
    const result = await api<{ records: ClientRecord[] }>(`/client-records?${params}`);
    setRecords(result.records);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load records."));
  }, [search, sortBy, sortDir]);

  function toggleSort(key: string) {
    if (sortBy === key) { setSortDir(sortDir === "asc" ? "desc" : "asc"); }
    else { setSortBy(key); setSortDir("asc"); }
  }

  function startEdit(record: ClientRecord) {
    setEditingId(record.id);
    setEditInsurerNo(record.insurer_no);
    setEditNotes(record.notes || "");
  }

  async function saveEdit(recordId: string) {
    setError("");
    setSaving(true);
    try {
      await api(`/client-records/${recordId}`, {
        method: "PATCH",
        body: JSON.stringify({ insurer_no: editInsurerNo, notes: editNotes }),
      });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function exportCsv() {
    const params = search ? `?search=${encodeURIComponent(search)}` : "";
    window.location.href = `${window.location.origin}/api/client-records/export${params}`;
  }

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">
              Client Records
            </h1>
            <p className="mt-2 text-[13px] text-[var(--rl-text-muted)]">
              {records.length} record{records.length !== 1 ? "s" : ""} &mdash; dashboard for confirmed quotations.
            </p>
          </div>
          <Button
            variant="secondary"
            icon={<DownloadSimple aria-hidden="true" size={18} weight="bold" />}
            onClick={exportCsv}
          >
            Export CSV
          </Button>
        </div>

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        <div className="relative">
          <MagnifyingGlass
            aria-hidden="true"
            size={18}
            weight="bold"
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]"
          />
          <Input
            className="pl-10 pr-10"
            placeholder="Search insurer no, customer, vehicle, company..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search ? (
            <button
              type="button"
              onClick={() => setSearch("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            >
              <X aria-hidden="true" size={16} weight="bold" />
            </button>
          ) : null}
        </div>

        <Card className="overflow-x-auto">
          <table className="min-w-[700px] w-full">
            <thead>
              <tr className="border-b border-[var(--rl-border)]">
                <th className="w-10 px-4 py-2.5" />
                {SORTABLE.map((col) => (
                  <th
                    key={col.key}
                    className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider cursor-pointer select-none"
                    onClick={() => toggleSort(col.key)}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      {sortBy === col.key ? (
                        sortDir === "asc" ? <CaretUp size={14} weight="bold" /> : <CaretDown size={14} weight="bold" />
                      ) : null}
                    </span>
                  </th>
                ))}
                <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {records.length === 0 ? (
                <tr>
                  <td colSpan={SORTABLE.length + 2} className="px-4 py-10 text-center text-[13px] text-[var(--rl-text-muted)]">
                    No records found. Generate a PDF to create a client record automatically.
                  </td>
                </tr>
              ) : (
                records.map((r) => {
                  const open = expandedId === r.id;
                  const editing = editingId === r.id;
                  return (
                    <tr key={r.id} className={`border-b border-[var(--rl-border)] last:border-0 ${editing ? "bg-[var(--rl-bg)]" : ""}`}>
                      <td className="px-4 py-2.5">
                        <button
                          type="button"
                          className="text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] transition-colors"
                          onClick={() => setExpandedId(open ? null : r.id)}
                        >
                          {open ? <CaretUp size={16} weight="bold" /> : <CaretDown size={16} weight="bold" />}
                        </button>
                      </td>
                      <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)] font-mono">
                        {editing ? (
                          <Input
                            className="w-44 text-sm"
                            value={editInsurerNo}
                            onChange={(e) => setEditInsurerNo(e.target.value)}
                          />
                        ) : (
                          r.insurer_no
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{r.customer_name || "-"}</td>
                      <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)] font-mono">{r.vehicle_no || "-"}</td>
                      <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{r.insurance_company || "-"}</td>
                      <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{formatDate(r.created_at)}</td>
                      <td className="px-4 py-2.5">
                        <div className="flex gap-1">
                          {editing ? (
                            <>
                              <Button
                                size="sm"
                                icon={<FloppyDisk size={14} weight="bold" />}
                                onClick={() => saveEdit(r.id)}
                                loading={saving}
                              >
                                Save
                              </Button>
                              <Button
                                variant="secondary"
                                size="sm"
                                icon={<X size={14} weight="bold" />}
                                onClick={() => setEditingId(null)}
                              />
                            </>
                          ) : (
                            <Button
                              variant="ghost"
                              size="sm"
                              icon={<NotePencil size={14} weight="bold" />}
                              onClick={() => startEdit(r)}
                            >
                              Edit
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </Card>

        {expandedId ? (
          <Card className="p-5">
            <RecordDetail
              record={records.find((r) => r.id === expandedId)!}
              onStartEdit={startEdit}
              onUpdate={async (id, notes) => {
                setError("");
                setSaving(true);
                try {
                  await api(`/client-records/${id}`, {
                    method: "PATCH",
                    body: JSON.stringify({ notes }),
                  });
                  await load();
                } catch (err) {
                  setError(apiErrorMessage(err));
                } finally {
                  setSaving(false);
                }
              }}
            />
          </Card>
        ) : null}
      </section>
    </AppShell>
  );
}

function RecordDetail({
  record,
  onStartEdit,
  onUpdate,
}: {
  record: ClientRecord;
  onStartEdit: (r: ClientRecord) => void;
  onUpdate: (id: string, notes: string) => Promise<void>;
}) {
  const [notes, setNotes] = useState(record.notes || "");
  const [savingNotes, setSavingNotes] = useState(false);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-bold text-[var(--rl-text-strong)]">
            {record.insurer_no}
            <Button
              variant="ghost"
              size="sm"
              className="ml-3"
              onClick={() => onStartEdit(record)}
            >
              <NotePencil aria-hidden="true" size={12} weight="bold" />
              <span className="text-[13px]">Edit insurer no.</span>
            </Button>
          </h2>
          {record.generated_at ? (
            <span className="text-[13px] text-[var(--rl-text-muted)]">Generated {formatDate(record.generated_at)}</span>
          ) : null}
        </div>
        <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2">
          {DETAIL_FIELDS.filter(([key]) => key !== "notes").map(([key, label]) => (
            <div key={key} className="grid grid-cols-[120px_1fr] gap-1 text-sm">
              <span className="font-bold text-[var(--rl-text-strong)]">{label}</span>
              <span className="text-[var(--rl-text)]">{record[key as keyof ClientRecord] || "-"}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <h3 className="font-bold text-[var(--rl-text-strong)]">Notes</h3>
        <Textarea
          className="mt-2 min-h-[128px]"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
        <Button
          className="mt-3"
          size="sm"
          loading={savingNotes}
          icon={<FloppyDisk size={14} weight="bold" />}
          onClick={async () => {
            setSavingNotes(true);
            await onUpdate(record.id, notes);
            setSavingNotes(false);
          }}
        >
          {savingNotes ? "Saving..." : "Save notes"}
        </Button>
      </div>
    </div>
  );
}
