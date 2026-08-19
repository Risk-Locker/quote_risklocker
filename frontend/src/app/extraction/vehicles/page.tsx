"use client";

import { useEffect, useRef, useState } from "react";
import { Plus, DownloadSimple, UploadSimple, FloppyDisk, Trash, CaretRight } from "@phosphor-icons/react";
import { ExtractionNav } from "@/components/extraction-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api, API_BASE } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Brand = { id: string; name: string; aliases: string[] };
type Model = { id: string; brand_id: string | null; name: string; aliases: string[] };

export default function VehiclesPage() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [error, setError] = useState("");
  const [showBrandForm, setShowBrandForm] = useState(false);
  const [showModelForm, setShowModelForm] = useState(false);
  const [brandName, setBrandName] = useState("");
  const [brandAliases, setBrandAliases] = useState("");
  const [modelName, setModelName] = useState("");
  const [modelAliases, setModelAliases] = useState("");
  const [pendingBrand, setPendingBrand] = useState<Brand | null>(null);
  const [pendingModel, setPendingModel] = useState<Model | null>(null);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  async function load() {
    const data = await api<{ vehicle_brands: Brand[]; vehicle_models: Model[] }>("/admin/dictionaries");
    setBrands(data.vehicle_brands || []);
    setModels(data.vehicle_models || []);
    setSelectedBrandId((current) => {
      if (current && data.vehicle_brands.some((b) => b.id === current)) return current;
      return data.vehicle_brands[0]?.id || "";
    });
  }
  useEffect(() => { load().catch(() => {}); }, []);

  async function createBrand(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api("/admin/dictionaries/vehicle-brands", { method: "POST", body: JSON.stringify({ name: brandName, aliases: brandAliases.split(/[,\n]/).map((s) => s.trim()).filter(Boolean) }) });
      setBrandName(""); setBrandAliases(""); setShowBrandForm(false);
      toast("Brand created.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function createModel(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api("/admin/dictionaries/vehicle-models", { method: "POST", body: JSON.stringify({ name: modelName, brand_id: selectedBrandId || null, aliases: modelAliases.split(/[,\n]/).map((s) => s.trim()).filter(Boolean) }) });
      setModelName(""); setModelAliases(""); setShowModelForm(false);
      toast("Model created.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function removeBrand() {
    if (!pendingBrand) return;
    setError("");
    try {
      await api(`/admin/dictionaries/vehicle-brands/${pendingBrand.id}`, { method: "DELETE" });
      toast(`"${pendingBrand.name}" deleted.`, "success");
      setPendingBrand(null);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function removeModel() {
    if (!pendingModel) return;
    setError("");
    try {
      await api(`/admin/dictionaries/vehicle-models/${pendingModel.id}`, { method: "DELETE" });
      toast(`"${pendingModel.name}" deleted.`, "success");
      setPendingModel(null);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  function exportCsv() { window.location.href = `${API_BASE}/admin/dictionaries/vehicles/export`; }

  async function importFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/admin/dictionaries/vehicles/import`, { method: "POST", body: form, credentials: "include" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Import failed.");
      toast(`Import done: ${data.created || 0} created, ${data.updated || 0} updated${data.errors?.length ? `, ${data.errors.length} errors` : ""}.`, "success");
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Import failed."); }
    finally { setImporting(false); }
    if (fileRef.current) fileRef.current.value = "";
  }

  const selectedBrand = brands.find((b) => b.id === selectedBrandId) || null;
  const brandModels = models.filter((m) => m.brand_id === selectedBrandId);
  const ungroupedModels = models.filter((m) => !m.brand_id);

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Vehicles</h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">
              Brands on the left, their models on the right. Import a multi-sheet Excel file — one sheet per brand, model names as column headers, search terms below.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" loading={importing} icon={<UploadSimple size={14} weight="bold" />} onClick={() => fileRef.current?.click()}>
              Import Excel
            </Button>
            <input ref={fileRef} className="hidden" type="file" accept=".xlsx" onChange={importFile} />
            <Button variant="secondary" size="sm" icon={<DownloadSimple size={14} weight="bold" />} onClick={exportCsv}>Export CSV</Button>
            <Button size="sm" icon={<Plus size={14} weight="bold" />} onClick={() => setShowBrandForm((v) => !v)}>New brand</Button>
          </div>
        </div>
        <ExtractionNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

        {showBrandForm ? (
          <Card>
            <form className="grid gap-4 p-4" onSubmit={createBrand}>
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">New brand</h2>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Brand name</label>
                <Input placeholder="e.g. Proton" value={brandName} onChange={(e) => setBrandName(e.target.value)} required />
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Search terms (comma or newline)</label>
                <Textarea className="min-h-16" placeholder="proton, PROTON" value={brandAliases} onChange={(e) => setBrandAliases(e.target.value)} />
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" icon={<FloppyDisk size={14} weight="bold" />}>Save</Button>
                <Button variant="secondary" size="sm" onClick={() => setShowBrandForm(false)}>Cancel</Button>
              </div>
            </form>
          </Card>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <Card>
            <div className="flex items-center justify-between border-b border-[var(--rl-border)] px-4 py-3">
              <h2 className="text-[13px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">Brands ({brands.length})</h2>
            </div>
            <div className="max-h-[70vh] overflow-auto p-2">
              {brands.length === 0 ? (
                <p className="px-2 py-6 text-center text-[13px] text-[var(--rl-text-muted)]">No brands yet. Create one or import an Excel file.</p>
              ) : (
                brands.map((b) => {
                  const count = models.filter((m) => m.brand_id === b.id).length;
                  const active = b.id === selectedBrandId;
                  return (
                    <button
                      key={b.id}
                      type="button"
                      onClick={() => setSelectedBrandId(b.id)}
                      className={`mb-1 flex w-full items-center justify-between gap-2 rounded-[var(--rl-radius-sm)] px-3 py-2.5 text-left text-[14px] font-medium transition-colors
                        ${active ? "bg-[var(--rl-black)] text-white" : "text-[var(--rl-text-strong)] hover:bg-[var(--rl-bg)]"}`}
                    >
                      <span className="truncate">{b.name}</span>
                      <span className={`text-[12px] font-semibold ${active ? "text-white/70" : "text-[var(--rl-text-muted)]"}`}>{count} models</span>
                    </button>
                  );
                })
              )}
            </div>
          </Card>

          <div className="grid gap-4">
            {selectedBrand ? (
              <>
                <Card>
                  <div className="flex flex-wrap items-center justify-between gap-3 p-4">
                    <div>
                      <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">{selectedBrand.name}</h2>
                      <p className="mt-0.5 text-[13px] text-[var(--rl-text-muted)]">
                        {selectedBrand.aliases?.length ? `Search terms: ${selectedBrand.aliases.join(", ")}` : "No search terms."}
                        {" · "}{brandModels.length} model{brandModels.length === 1 ? "" : "s"}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="secondary" size="sm" icon={<Plus size={14} weight="bold" />} onClick={() => { setShowModelForm((v) => !v); }}>Add model</Button>
                      <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setPendingBrand(selectedBrand)} className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]">
                        Delete brand
                      </Button>
                    </div>
                  </div>
                </Card>

                {showModelForm ? (
                  <Card>
                    <form className="grid gap-4 p-4" onSubmit={createModel}>
                      <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Add model to {selectedBrand.name}</h2>
                      <div className="grid gap-1.5">
                        <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Model name</label>
                        <Input placeholder="e.g. Saga FLX" value={modelName} onChange={(e) => setModelName(e.target.value)} required />
                      </div>
                      <div className="grid gap-1.5">
                        <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Search terms (comma or newline)</label>
                        <Textarea className="min-h-16" placeholder="saga flx, flx" value={modelAliases} onChange={(e) => setModelAliases(e.target.value)} />
                      </div>
                      <div className="flex gap-2">
                        <Button type="submit" size="sm" icon={<FloppyDisk size={14} weight="bold" />}>Save</Button>
                        <Button variant="secondary" size="sm" onClick={() => setShowModelForm(false)}>Cancel</Button>
                      </div>
                    </form>
                  </Card>
                ) : null}

                <Card>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[420px]">
                      <thead>
                        <tr className="border-b border-[var(--rl-border)]">
                          <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Model</th>
                          <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Search terms</th>
                          <th className="px-4 py-2.5" />
                        </tr>
                      </thead>
                      <tbody>
                        {brandModels.length === 0 ? (
                          <tr>
                            <td colSpan={3} className="px-4 py-8 text-center text-[13px] text-[var(--rl-text-muted)]">
                              No models yet. Add one above or import an Excel file where this sheet holds the models.
                            </td>
                          </tr>
                        ) : (
                          brandModels.map((m) => (
                            <tr key={m.id} className="border-b border-[var(--rl-border)] last:border-0">
                              <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{m.name}</td>
                              <td className="px-4 py-2.5 text-[13px] text-[var(--rl-text-muted)]">{(m.aliases || []).join(", ") || "—"}</td>
                              <td className="px-4 py-2.5 text-right">
                                <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setPendingModel(m)} title="Delete model" />
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </>
            ) : (
              <Card>
                <p className="p-10 text-center text-[14px] text-[var(--rl-text-muted)]">Select a brand on the left to manage its models.</p>
              </Card>
            )}

            {ungroupedModels.length > 0 ? (
              <Card>
                <div className="flex items-center gap-1.5 border-b border-[var(--rl-border)] px-4 py-3">
                  <CaretRight size={14} weight="bold" className="text-[var(--rl-text-muted)]" />
                  <h2 className="text-[13px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">Models without a brand ({ungroupedModels.length})</h2>
                </div>
                <div className="grid gap-1 p-2">
                  {ungroupedModels.map((m) => (
                    <div key={m.id} className="flex items-center justify-between rounded-[var(--rl-radius-sm)] px-3 py-2 hover:bg-[var(--rl-bg)]">
                      <span className="text-[14px] font-medium text-[var(--rl-text-strong)]">{m.name}</span>
                      <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setPendingModel(m)} title="Delete model" />
                    </div>
                  ))}
                </div>
              </Card>
            ) : null}
          </div>
        </div>
      </section>

      {pendingBrand ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingBrand(null); }}
          title={`Delete brand "${pendingBrand.name}"?`}
          message="Its models are not deleted automatically."
          onConfirm={removeBrand}
        />
      ) : null}

      {pendingModel ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingModel(null); }}
          title={`Delete model "${pendingModel.name}"?`}
          onConfirm={removeModel}
        />
      ) : null}
    </AppShell>
  );
}
