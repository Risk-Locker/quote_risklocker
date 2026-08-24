"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ImageSquare, MagnifyingGlass, Plus, UploadSimple } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { BuilderNav } from "@/components/builder-nav";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { PageLoading } from "@/components/ui/page-loading";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Asset = {
  id: string;
  asset_key: string;
  asset_kind: string;
  label: string;
  width_px?: number | null;
  height_px?: number | null;
  status: string;
  url: string;
};

const kinds = [
  { value: "", label: "All assets" },
  { value: "benefit_art", label: "Benefit artwork" },
  { value: "company_logo", label: "Company logos" },
  { value: "template_background", label: "Template backgrounds" },
  { value: "decorative", label: "Decorative" },
];

export default function AssetLibraryPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [kind, setKind] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadLabel, setUploadLabel] = useState("");
  const [uploadKind, setUploadKind] = useState("benefit_art");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isAssetDragging, setIsAssetDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async (nextPage = page, nextSearch = appliedSearch, nextKind = kind) => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ page: String(nextPage), page_size: "48" });
      if (nextSearch) query.set("search", nextSearch);
      if (nextKind) query.set("kind", nextKind);
      const result = await api<{ assets: { items: Asset[]; total: number } }>(`/business/assets?${query}`);
      setAssets(result.assets.items);
      setTotal(result.assets.total);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [appliedSearch, kind, page]);

  useEffect(() => { load(); }, [load]);

  function applyFilters(nextSearch: string, nextKind: string) {
    setAppliedSearch(nextSearch);
    setKind(nextKind);
    setPage(1);
  }

  async function upload() {
    if (!uploadFile || !uploadLabel.trim()) return;
    setUploading(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", uploadFile);
      body.append("label", uploadLabel.trim());
      body.append("kind", uploadKind);
      await api("/business/assets", { method: "POST", body });
      setUploadOpen(false);
      setUploadFile(null);
      setUploadLabel("");
      await load(1, appliedSearch, kind);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  const pages = Math.max(1, Math.ceil(total / 48));

  return (
    <AppShell>
      <section className="grid gap-5">
        <header className="flex items-center justify-between gap-4">
          <div>
            <h1 className="font-[var(--font-manrope)] text-[22px] font-bold text-[var(--rl-text-strong)]">Asset library</h1>
            <p className="mt-1 text-[13px] text-[var(--rl-text-muted)]">Upload and audit logos, benefit art, and template backdrops used across published layouts.</p>
          </div>
          <Button onClick={() => setUploadOpen(true)}><Plus size={16} weight="bold" />Add asset</Button>
        </header>

        <BuilderNav />

        {error ? <div className="border border-[var(--rl-danger)] bg-[var(--rl-danger)]/10 p-3 text-[13px] text-[var(--rl-danger)]">{error}</div> : null}

        <div className="flex flex-wrap items-center gap-3">
          <label className="relative min-w-64 flex-1">
            <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
            <Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") applyFilters(search.trim(), kind); }} placeholder="Search label or source filename" />
          </label>
          <Select className="w-52" value={kind} onChange={(event) => applyFilters(search.trim(), event.target.value)} aria-label="Asset kind">{kinds.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</Select>
          <Button variant="secondary" onClick={() => applyFilters(search.trim(), kind)}>Search</Button>
          <span className="ml-auto text-[12px] text-[var(--rl-text-muted)]">{total} asset{total === 1 ? "" : "s"}</span>
        </div>

        {loading ? <PageLoading /> : assets.length ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
            {assets.map((asset) => (
              <article key={asset.id} className="group overflow-hidden border border-[var(--rl-border)] bg-[var(--rl-surface)] hover:border-[var(--rl-border-strong)] hover:shadow-card">
                <div className="grid aspect-[4/3] place-items-center bg-[linear-gradient(45deg,#f3f3f4_25%,transparent_25%),linear-gradient(-45deg,#f3f3f4_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#f3f3f4_75%),linear-gradient(-45deg,transparent_75%,#f3f3f4_75%)] bg-[length:18px_18px] bg-[position:0_0,0_9px,9px_-9px,-9px_0px] p-4">
                  <img src={fileUrl(asset.url)} alt={asset.label} loading="lazy" className="max-h-full max-w-full object-contain" />
                </div>
                <div className="border-t border-[var(--rl-border)] p-3">
                  <h2 className="truncate text-[12px] font-bold text-[var(--rl-text-strong)]" title={asset.label}>{asset.label}</h2>
                  <div className="mt-1 flex items-center justify-between gap-2 text-[10px] uppercase tracking-[0.06em] text-[var(--rl-text-muted)]">
                    <span>{asset.asset_kind.replaceAll("_", " ")}</span>
                    <span>{asset.width_px && asset.height_px ? `${asset.width_px}×${asset.height_px}` : ""}</span>
                  </div>
                  <p className={`mt-2 text-[11px] font-semibold ${asset.status === "unassigned" ? "text-[var(--rl-warning)]" : "text-[var(--rl-success)]"}`}>{asset.status === "unassigned" ? "Available · not assigned" : "Active"}</p>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="grid min-h-72 place-items-center border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface)] text-center">
            <div><ImageSquare size={30} className="mx-auto text-[var(--rl-text-muted)]" /><p className="mt-3 font-semibold text-[var(--rl-text-strong)]">No assets match</p><p className="mt-1 text-[12px] text-[var(--rl-text-muted)]">Clear the filters or add a validated image.</p></div>
          </div>
        )}

        {pages > 1 ? <nav className="flex items-center justify-center gap-3" aria-label="Asset pages"><Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><span className="text-[12px] text-[var(--rl-text-muted)]">Page {page} of {pages}</span><Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Next</Button></nav> : null}
      </section>

      <Dialog open={uploadOpen} onOpenChange={setUploadOpen} title="Add asset" description="Files are signature-checked, deduplicated, and stored privately with non-cropped UI and PDF derivatives." onConfirm={upload} confirmLabel="Upload asset" loading={uploading}>
        <div className="grid gap-3">
          <label className="grid gap-1"><span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Display name</span><Input value={uploadLabel} onChange={(event) => setUploadLabel(event.target.value)} /></label>
          <label className="grid gap-1"><span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Purpose</span><Select value={uploadKind} onChange={(event) => setUploadKind(event.target.value)}><option value="benefit_art">Benefit artwork</option><option value="company_logo">Company logo</option><option value="template_background">Template background</option><option value="decorative">Decorative</option></Select></label>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; setIsAssetDragging(true); }}
            onDragLeave={(e) => { e.preventDefault(); setIsAssetDragging(false); }}
            onDrop={(e) => {
              e.preventDefault();
              setIsAssetDragging(false);
              const file = e.dataTransfer.files?.[0] || null;
              if (file) {
                setUploadFile(file);
                if (!uploadLabel) setUploadLabel(file.name.replace(/\.[^.]+$/, ""));
              }
            }}
            className={`grid min-h-32 place-items-center border-2 border-dashed p-4 text-center transition-all ${
              isAssetDragging
                ? "border-[var(--rl-black)] bg-[var(--rl-black)]/[0.04] scale-[1.01]"
                : "border-[var(--rl-border)] bg-[var(--rl-bg)] hover:border-[var(--rl-black)]"
            }`}
          >
            <span className="pointer-events-none">
              <UploadSimple size={24} className={`mx-auto transition-transform ${isAssetDragging ? "scale-110 text-[var(--rl-text-strong)]" : "text-[var(--rl-text-muted)]"}`} />
              <span className="mt-2 block text-[12px] font-semibold text-[var(--rl-text-strong)]">
                {uploadFile?.name || (isAssetDragging ? "Drop image file here" : "Choose or drag PNG, JPG, or WebP")}
              </span>
              <span className="mt-1 block text-[11px] text-[var(--rl-text-muted)]">Maximum 10 MiB and 32 megapixels</span>
            </span>
          </button>
          <input ref={inputRef} type="file" className="sr-only" accept=".png,.jpg,.jpeg,.webp" onChange={(event) => { const file = event.target.files?.[0] || null; setUploadFile(file); if (file && !uploadLabel) setUploadLabel(file.name.replace(/\.[^.]+$/, "")); }} />
        </div>
      </Dialog>
    </AppShell>
  );
}
