"use client";

import { useEffect, useRef, useState } from "react";
import { Plus, DownloadSimple, FloppyDisk, Trash } from "@phosphor-icons/react";
import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
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
  const [error, setError] = useState("");
  const [showBrandForm, setShowBrandForm] = useState(false);
  const [showModelForm, setShowModelForm] = useState(false);
  const [brandName, setBrandName] = useState("");
  const [brandAliases, setBrandAliases] = useState("");
  const [modelName, setModelName] = useState("");
  const [modelAliases, setModelAliases] = useState("");
  const [modelBrandId, setModelBrandId] = useState("");
  const [pendingBrand, setPendingBrand] = useState<Brand | null>(null);
  const [pendingModel, setPendingModel] = useState<Model | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  async function load() {
    const data = await api<{ vehicle_brands: Brand[]; vehicle_models: Model[] }>("/admin/dictionaries");
    setBrands(data.vehicle_brands || []);
    setModels(data.vehicle_models || []);
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
      await api("/admin/dictionaries/vehicle-models", { method: "POST", body: JSON.stringify({ name: modelName, brand_id: modelBrandId || null, aliases: modelAliases.split(/[,\n]/).map((s) => s.trim()).filter(Boolean) }) });
      setModelName(""); setModelAliases(""); setModelBrandId(""); setShowModelForm(false);
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

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Vehicles</h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">Manage vehicle brand and model reference data with aliases.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" icon={<DownloadSimple size={14} weight="bold" />} onClick={exportCsv}>Export CSV</Button>
            <Button size="sm" icon={<Plus size={14} weight="bold" />} onClick={() => setShowBrandForm((v) => !v)}>New brand</Button>
            <Button variant="secondary" size="sm" icon={<Plus size={14} weight="bold" />} onClick={() => setShowModelForm((v) => !v)}>New model</Button>
          </div>
        </div>
        <SettingsNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

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

        {showBrandForm ? (
          <Card>
            <form className="grid gap-4 p-4" onSubmit={createBrand}>
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">New brand</h2>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Brand name</label>
                <Input placeholder="Brand name" value={brandName} onChange={(e) => setBrandName(e.target.value)} required />
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Aliases</label>
                <Textarea className="min-h-16" placeholder="Aliases (comma or newline)" value={brandAliases} onChange={(e) => setBrandAliases(e.target.value)} />
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" icon={<FloppyDisk size={14} weight="bold" />}>Save</Button>
                <Button variant="secondary" size="sm" onClick={() => setShowBrandForm(false)}>Cancel</Button>
              </div>
            </form>
          </Card>
        ) : null}

        {showModelForm ? (
          <Card>
            <form className="grid gap-4 p-4" onSubmit={createModel}>
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">New model</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Model name</label>
                  <Input placeholder="Model name" value={modelName} onChange={(e) => setModelName(e.target.value)} required />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Brand</label>
                  <Select value={modelBrandId} onChange={(e) => setModelBrandId(e.target.value)}>
                    <option value="">Select brand</option>
                    {brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </Select>
                </div>
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Aliases</label>
                <Textarea className="min-h-16" placeholder="Aliases (comma or newline)" value={modelAliases} onChange={(e) => setModelAliases(e.target.value)} />
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" icon={<FloppyDisk size={14} weight="bold" />}>Save</Button>
                <Button variant="secondary" size="sm" onClick={() => setShowModelForm(false)}>Cancel</Button>
              </div>
            </form>
          </Card>
        ) : null}

        <TableSection title="Brands" cols={["Name", "Aliases", ""]} rows={brands.map((b) => [b.name, (b.aliases || []).join(", "), ""])} onDelete={(i) => setPendingBrand(brands[i])} />

        {brands.map((brand) => {
          const brandModels = models.filter((m) => m.brand_id === brand.id);
          if (!brandModels.length) return null;
          return (
            <TableSection key={brand.id} title={`Models — ${brand.name}`} cols={["Name", "Aliases", ""]} rows={brandModels.map((m, i) => [m.name, (m.aliases || []).join(", "), ""])} onDelete={(i) => setPendingModel(brandModels[i])} />
          );
        })}
      </section>
    </AppShell>
  );
}

function TableSection({ title, cols, rows, onDelete }: { title: string; cols: string[]; rows: string[][]; onDelete: (i: number) => void }) {
  if (!rows.length) return null;
  return (
    <div className="grid gap-3">
      <h2 className="text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">{title} ({rows.length})</h2>
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[400px]">
            <thead>
              <tr>
                {cols.map((c, i) => (
                  <th key={i} className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  {r.map((cell, j) => (
                    <td key={j} className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{cell}</td>
                  ))}
                  <td className="px-4 py-2.5">
                    <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => onDelete(i)} title="Delete" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
