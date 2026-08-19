"use client";

import { useEffect, useRef, useState } from "react";
import { Plus, DownloadSimple, UploadSimple, FloppyDisk, Trash, PencilSimple } from "@phosphor-icons/react";
import { ExtractionNav } from "@/components/extraction-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api, API_BASE } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type FieldAlias = { id: string; field_name: string; aliases: string[] };

export default function FieldAliasesPage() {
  const [items, setItems] = useState<FieldAlias[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newField, setNewField] = useState("");
  const [newAliases, setNewAliases] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editField, setEditField] = useState("");
  const [editAliases, setEditAliases] = useState("");
  const [pendingDelete, setPendingDelete] = useState<FieldAlias | null>(null);
  const [runnerFee, setRunnerFee] = useState("20");
  const [savingFee, setSavingFee] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  async function load() {
    const result = await api<{ field_aliases: FieldAlias[] }>("/admin/dictionaries");
    setItems(result.field_aliases);
  }

  useEffect(() => {
    load().catch(() => {});
    api<{ amount: number }>("/admin/settings/runner-fee").then((r) => setRunnerFee(String(r.amount))).catch(() => {});
  }, []);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/admin/dictionaries/field-aliases", {
        method: "POST",
        body: JSON.stringify({ field_name: newField, aliases: newAliases.split(/[,\n]/).map((s) => s.trim()).filter(Boolean) }),
      });
      setNewField(""); setNewAliases(""); setShowCreate(false);
      toast("Alias created.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function saveEdit(event: React.FormEvent) {
    event.preventDefault();
    if (!editingId) return;
    setError("");
    try {
      await api("/admin/dictionaries/field-aliases", {
        method: "POST",
        body: JSON.stringify({ id: editingId, field_name: editField, aliases: editAliases.split(/[,\n]/).map((s) => s.trim()).filter(Boolean) }),
      });
      setEditingId(null);
      toast("Alias updated.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function remove() {
    if (!pendingDelete) return;
    try {
      await api(`/admin/dictionaries/field-aliases/${encodeURIComponent(pendingDelete.field_name)}`, { method: "DELETE" });
      toast(`"${pendingDelete.field_name}" deleted.`, "success");
      setPendingDelete(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not delete."); }
    await load();
  }

  function startEdit(item: FieldAlias) {
    setEditingId(item.id);
    setEditField(item.field_name);
    setEditAliases((item.aliases || []).join(", "));
  }

  function exportCsv() {
    window.location.href = `${API_BASE}/admin/dictionaries/field-aliases/export`;
  }

  async function importCsv(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/admin/dictionaries/field-aliases/import`, { method: "POST", body: form, credentials: "include" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Import failed.");
      toast(`Import done: ${data.created || 0} created, ${data.updated || 0} updated.`, "success");
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Import failed."); }
    if (fileRef.current) fileRef.current.value = "";
  }

  async function saveRunnerFee() {
    setSavingFee(true);
    setError("");
    try {
      const res = await api<{ amount: number }>("/admin/settings/runner-fee", {
        method: "POST",
        body: JSON.stringify({ amount: Number(runnerFee) || 0 }),
      });
      setRunnerFee(String(res.amount));
      toast("Runner fee default saved.", "success");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save runner fee."); }
    finally { setSavingFee(false); }
  }

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Field Aliases</h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">Manage extraction synonyms so OCR can match more variants.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" icon={<DownloadSimple size={14} weight="bold" />} onClick={exportCsv}>Export CSV</Button>
            <Button variant="secondary" size="sm" icon={<UploadSimple size={14} weight="bold" />} onClick={() => fileRef.current?.click()}>Import CSV/Excel</Button>
            <input ref={fileRef} className="hidden" type="file" accept=".csv,.xlsx" onChange={importCsv} />
            <Button size="sm" icon={<Plus size={14} weight="bold" />} onClick={() => setShowCreate((v) => !v)}>New alias</Button>
          </div>
        </div>
        <ExtractionNav />

        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <h2 className="text-[15px] font-bold text-[var(--rl-text-strong)]">Runner fee default (RM)</h2>
              <p className="mt-0.5 text-[13px] text-[var(--rl-text-muted)]">
                Used when the runner fee is not detected on a quotation. Staff still confirms it during Check Values.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                step="0.01"
                min="0"
                className="w-32"
                value={runnerFee}
                onChange={(e) => setRunnerFee(e.target.value)}
                aria-label="Runner fee default"
              />
              <Button size="sm" loading={savingFee} icon={<FloppyDisk size={14} weight="bold" />} onClick={saveRunnerFee}>Save</Button>
            </div>
          </div>
        </Card>

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

        {showCreate ? (
          <Card>
            <form className="grid gap-4 p-4" onSubmit={create}>
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Create field alias</h2>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Field name</label>
                <Input placeholder="e.g. customer_name" value={newField} onChange={(e) => setNewField(e.target.value)} required />
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Accepted variants (comma or newline separated)</label>
                <Textarea className="min-h-20" placeholder="insured name, name, customer" value={newAliases} onChange={(e) => setNewAliases(e.target.value)} />
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" icon={<FloppyDisk size={14} weight="bold" />}>Save</Button>
                <Button variant="secondary" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
              </div>
            </form>
          </Card>
        ) : null}

        <Card>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[500px]">
              <thead>
                <tr>
                  <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Field Name</th>
                  <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Accepted Variants</th>
                  <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider w-24">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  editingId === item.id ? (
                    <tr key={item.id} className="bg-[var(--rl-bg)]">
                      <td className="px-4 py-2.5"><Input value={editField} onChange={(e) => setEditField(e.target.value)} required /></td>
                      <td className="px-4 py-2.5"><Textarea className="min-h-[40px]" value={editAliases} onChange={(e) => setEditAliases(e.target.value)} /></td>
                      <td className="px-4 py-2.5">
                        <div className="flex gap-1">
                          <Button size="sm" icon={<FloppyDisk size={14} weight="bold" />} onClick={saveEdit} />
                          <Button variant="secondary" size="sm" onClick={() => setEditingId(null)}>Cancel</Button>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    <tr key={item.id}>
                      <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)] font-mono">{item.field_name}</td>
                      <td className="px-4 py-2.5 text-[14px]">
                        <div className="flex flex-wrap gap-1">
                          {(item.aliases || []).map((a, i) => (
                            <Badge key={i}>{a}</Badge>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-[14px]">
                        <div className="flex gap-1">
                          <Button variant="ghost" size="sm" icon={<PencilSimple size={14} weight="bold" />} onClick={() => startEdit(item)} title="Edit" />
                          <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setPendingDelete(item)} title="Delete" />
                        </div>
                      </td>
                    </tr>
                  )
                ))}
                {!items.length ? <tr><td colSpan={3} className="px-4 py-2.5 text-center text-[14px] text-[var(--rl-text-muted)]">No field aliases yet.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      {pendingDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingDelete(null); }}
          title={`Delete field alias "${pendingDelete.field_name}"?`}
          onConfirm={remove}
        />
      ) : null}
    </AppShell>
  );
}
