"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { MagnifyingGlass, PencilSimple, Plus, Trash, X } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { SettingsNav } from "@/components/settings-nav";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Company = { id: string; name: string; status: string };
type CompanyAlias = {
  id: string;
  company_id: string;
  company_name: string;
  alias: string;
  normalized_alias: string;
  alias_kind: string;
  status: string;
};

const EMPTY_FORM = { id: "", company_id: "", alias: "", alias_kind: "detection", status: "active" };

export default function CompanyDetectionPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [aliases, setAliases] = useState<CompanyAlias[]>([]);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<CompanyAlias | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [companyResult, aliasResult] = await Promise.all([
        api<{ companies: { items: Company[] } }>("/business/companies?page=1&page_size=100"),
        api<{ aliases: { items: CompanyAlias[] } }>("/business/company-aliases?page=1&page_size=100"),
      ]);
      setCompanies(companyResult.companies.items);
      setAliases(aliasResult.aliases.items);
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    if (!term) return aliases;
    return aliases.filter((item) => `${item.alias} ${item.company_name} ${item.alias_kind}`.toLocaleLowerCase().includes(term));
  }, [aliases, search]);

  function startCreate() {
    setForm({ ...EMPTY_FORM, company_id: companies[0]?.id || "" });
    setShowForm(true);
  }

  function startEdit(item: CompanyAlias) {
    setForm({ id: item.id, company_id: item.company_id, alias: item.alias, alias_kind: item.alias_kind, status: item.status });
    setShowForm(true);
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!form.company_id || !form.alias.trim()) return;
    setSaving(true);
    setError("");
    try {
      await api("/business/company-aliases", {
        method: "POST",
        body: JSON.stringify({ ...form, id: form.id || undefined, alias: form.alias.trim() }),
      });
      setShowForm(false);
      setForm(EMPTY_FORM);
      await load();
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  async function retire() {
    if (!pendingDelete) return;
    setError("");
    try {
      await api(`/business/company-aliases/${pendingDelete.id}`, { method: "DELETE" });
      setPendingDelete(null);
      await load();
    } catch (reason) {
      setError(apiErrorMessage(reason));
    }
  }

  return (
    <AppShell>
      <section className="grid gap-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--rl-red)]">Settings / Extraction</p>
            <h1 className="m-0 font-[var(--font-manrope)] text-[30px] font-bold text-[var(--rl-text-strong)]">Company Detection</h1>
            <p className="mt-1 max-w-3xl text-[14px] text-[var(--rl-text-muted)]">Map the names printed in insurer documents to a company. These phrases help detection only; benefits come from the selected catalog.</p>
          </div>
          <Button icon={<Plus size={16} weight="bold" />} onClick={startCreate}>Add phrase</Button>
        </header>
        <SettingsNav />

        {error ? <div role="alert" className="border-l-2 border-[var(--rl-red)] bg-[var(--rl-red-light)] px-4 py-3 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div> : null}

        {showForm ? (
          <form onSubmit={save} className="grid gap-4 border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-card lg:grid-cols-[1fr_1fr_180px_auto] lg:items-end">
            <label className="grid gap-1.5 text-[12px] font-semibold text-[var(--rl-text-strong)]">Printed phrase
              <Input value={form.alias} onChange={(event) => setForm((current) => ({ ...current, alias: event.target.value }))} placeholder="e.g. QBE Insurance (Malaysia) Berhad" required />
            </label>
            <label className="grid gap-1.5 text-[12px] font-semibold text-[var(--rl-text-strong)]">Resolves to
              <Select value={form.company_id} onChange={(event) => setForm((current) => ({ ...current, company_id: event.target.value }))} required>
                <option value="">Select company</option>
                {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
              </Select>
            </label>
            <label className="grid gap-1.5 text-[12px] font-semibold text-[var(--rl-text-strong)]">Phrase type
              <Select value={form.alias_kind} onChange={(event) => setForm((current) => ({ ...current, alias_kind: event.target.value }))}>
                <option value="detection">Detection</option>
                <option value="legal_name">Legal name</option>
                <option value="brand">Brand</option>
                <option value="product">Product</option>
              </Select>
            </label>
            <div className="flex gap-2">
              <Button type="submit" loading={saving}>{form.id ? "Save" : "Add"}</Button>
              <Button variant="secondary" aria-label="Cancel editing" icon={<X size={15} />} onClick={() => setShowForm(false)}><span className="sr-only">Cancel</span></Button>
            </div>
          </form>
        ) : null}

        <div className="border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] p-4">
            <label className="relative block min-w-[280px] max-w-xl flex-1">
              <MagnifyingGlass size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
              <Input aria-label="Search company detection phrases" className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search phrase or company" />
            </label>
            <span className="text-[12px] font-semibold text-[var(--rl-text-muted)]">{filtered.length} phrase{filtered.length === 1 ? "" : "s"}</span>
          </div>
          {loading ? (
            <p role="status" className="p-6 text-[14px] text-[var(--rl-text-muted)]">Loading detection phrases…</p>
          ) : filtered.length ? (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead><tr className="border-b border-[var(--rl-border)] bg-[#fafafa] text-[11px] uppercase tracking-[0.1em] text-[var(--rl-text-muted)]"><th className="px-4 py-3">Printed phrase</th><th className="px-4 py-3">Company</th><th className="px-4 py-3">Type</th><th className="w-24 px-4 py-3"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>{filtered.map((item) => (
                  <tr key={item.id} className="border-b border-[var(--rl-border)] last:border-0">
                    <td className="px-4 py-3 text-[13px] font-semibold text-[var(--rl-text-strong)]">{item.alias}</td>
                    <td className="px-4 py-3 text-[13px] text-[var(--rl-text)]">{item.company_name}</td>
                    <td className="px-4 py-3 text-[12px] capitalize text-[var(--rl-text-muted)]">{item.alias_kind.replace("_", " ")}</td>
                    <td className="px-4 py-2"><div className="flex justify-end gap-1"><Button variant="ghost" size="sm" aria-label={`Edit ${item.alias}`} icon={<PencilSimple size={14} />} onClick={() => startEdit(item)}><span className="sr-only">Edit</span></Button><Button variant="ghost" size="sm" aria-label={`Retire ${item.alias}`} icon={<Trash size={14} />} className="text-[var(--rl-red)]" onClick={() => setPendingDelete(item)}><span className="sr-only">Retire</span></Button></div></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          ) : <p className="p-8 text-center text-[14px] text-[var(--rl-text-muted)]">No detection phrases match this search.</p>}
        </div>
      </section>

      {pendingDelete ? <ConfirmDialog open onOpenChange={(open) => { if (!open) setPendingDelete(null); }} title={`Retire “${pendingDelete.alias}”?`} message="Future extraction will stop using this phrase. Existing records are unchanged." confirmLabel="Retire phrase" onConfirm={retire} /> : null}
    </AppShell>
  );
}
