"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { FolderPlus, Image, MagnifyingGlass, Plus, Trash, UploadSimple } from "@phosphor-icons/react";
import { BuilderNav } from "@/components/builder-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { api, fileUrl } from "@/lib/api";

const PAGE_SIZE = 50;

type Asset = {
  id: string;
  label: string;
  filename: string;
  url: string;
  folder?: string;
  source?: string;
  created_at?: string | null;
  size_bytes?: number;
};
type FolderSummary = { folder: string; count: number };

function formatDate(iso?: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString();
}

function formatBytes(bytes?: number) {
  if (!bytes) return "";
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function BuilderAssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [folders, setFolders] = useState<FolderSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [folderMode, setFolderMode] = useState<"pick" | "new">("pick");
  const [uploadFolder, setUploadFolder] = useState("");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [folderFilter, setFolderFilter] = useState("");
  const [appliedFolder, setAppliedFolder] = useState("");
  const [sort, setSort] = useState("recent");
  const [pendingDelete, setPendingDelete] = useState<Asset | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  async function load(reset: boolean, term = appliedSearch, folder = appliedFolder) {
    if (reset) setLoading(true);
    else setLoadingMore(true);
    setError("");
    try {
      const offset = reset ? 0 : assets.length;
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
      if (term) params.set("search", term);
      if (folder) params.set("folder", folder);
      const result = await api<{ assets: Asset[]; total: number; folders: FolderSummary[] }>(`/admin/template-assets?${params}`);
      setAssets((current) => (reset ? result.assets : [...current, ...result.assets.filter((a) => !current.some((c) => c.id === a.id))]));
      setFolders(result.folders);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load assets.");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  useEffect(() => {
    load(true);
  }, []);

  const defaults = useMemo(() => assets.filter((a) => a.source === "local"), [assets]);
  const uploads = useMemo(() => assets.filter((a) => a.source !== "local"), [assets]);

  const filtered = useMemo(() => {
    const items = [...uploads];
    if (sort === "recent") items.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    else if (sort === "oldest") items.sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
    else if (sort === "name") items.sort((a, b) => a.label.localeCompare(b.label));
    else if (sort === "folder") items.sort((a, b) => (a.folder || "").localeCompare(b.folder || ""));
    return items;
  }, [uploads, sort]);

  const recent = useMemo(() => {
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
    return filtered.filter((a) => a.created_at && new Date(a.created_at).getTime() >= cutoff);
  }, [filtered]);

  function applyFilters(term: string, folder: string) {
    setAppliedSearch(term);
    setAppliedFolder(folder);
    setAssets([]);
    load(true, term, folder);
  }

  async function uploadFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    setUploading(true);
    setError("");
    const targetFolder = uploadFolder.trim();
    try {
      for (const file of list) {
        const form = new FormData();
        form.append("file", file);
        form.append("label", file.name.replace(/\.[^.]+$/, ""));
        form.append("folder", targetFolder || "Uncategorized");
        await api<{ asset: Asset }>("/admin/template-assets", { method: "POST", body: form });
      }
      toast(`${list.length} asset${list.length > 1 ? "s" : ""} uploaded to "${targetFolder || "Uncategorized"}".`, "success");
      setUploadFolder("");
      setFolderMode("pick");
      applyFilters(appliedSearch, appliedFolder);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function remove() {
    if (!pendingDelete) return;
    setError("");
    try {
      await api(`/admin/template-assets/${pendingDelete.id}`, { method: "DELETE" });
      toast("Asset moved to Trash.", "success");
      setPendingDelete(null);
      applyFilters(appliedSearch, appliedFolder);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete asset.");
    }
  }

  function AssetGrid({ items, emptyText }: { items: Asset[]; emptyText: string }) {
    if (!items.length) {
      return (
        <div className="rounded-[var(--rl-radius)] border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface)] p-8 text-center">
          <p className="text-[14px] text-[var(--rl-text-muted)]">{emptyText}</p>
        </div>
      );
    }
    return (
      <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))" }}>
        {items.map((asset) => (
          <Card key={asset.id} className="group overflow-hidden">
            <div className="grid h-28 place-items-center bg-[var(--rl-bg)] p-3">
              <img className="max-h-24 max-w-full object-contain" src={fileUrl(asset.url)} alt={asset.label} />
            </div>
            <div className="grid gap-1 p-3">
              <p className="truncate text-[13px] font-bold text-[var(--rl-text-strong)]" title={asset.label}>{asset.label}</p>
              <p className="text-[11px] text-[var(--rl-text-muted)]">{asset.folder || "Uncategorized"}</p>
              <p className="text-[11px] text-[var(--rl-text-muted)]">{formatDate(asset.created_at)}</p>
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className="text-[11px] text-[var(--rl-text-muted)]">{formatBytes(asset.size_bytes)}</span>
                {asset.source !== "local" ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    loading={pendingDelete?.id === asset.id}
                    icon={<Trash size={14} weight="bold" />}
                    onClick={() => setPendingDelete(asset)}
                    className="px-1.5 text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]"
                    title="Move to Trash"
                  >
                    <span className="text-[11px] font-semibold">Move to Trash</span>
                  </Button>
                ) : null}
              </div>
            </div>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <AppShell>
      <section className="grid gap-6">
        <div>
          <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Assets</h1>
          <p className="mt-2 max-w-3xl text-[14px] text-[var(--rl-text-muted)]">
            Every logo, symbol, SVG and background image for your quotation templates lives here. Upload them, sort them into
            folders, and they become available everywhere in the template builder. Default assets are read-only.
          </p>
        </div>
        <BuilderNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

        <Card className="p-4">
          <h2 className="text-[15px] font-bold text-[var(--rl-text-strong)]">Upload images</h2>
          <div className="mt-3 grid gap-3">
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                if (e.dataTransfer.files?.length) uploadFiles(e.dataTransfer.files);
              }}
              onClick={() => fileInputRef.current?.click()}
              className={`grid cursor-pointer place-items-center gap-2 rounded-[var(--rl-radius)] border-2 border-dashed p-10 text-center transition-colors
                ${dragOver ? "border-[var(--rl-red)] bg-[var(--rl-red-light)]" : "border-[var(--rl-border)] bg-[var(--rl-bg)] hover:border-[var(--rl-black)]/30"}`}
            >
              <UploadSimple size={28} weight="bold" className="text-[var(--rl-text-muted)]" />
              <p className="font-semibold text-[var(--rl-text-strong)]">
                {uploading ? "Uploading…" : dragOver ? "Drop to upload" : "Drag & drop images here, or click to browse"}
              </p>
              <p className="text-[12px] text-[var(--rl-text-muted)]">PNG, JPG or SVG · up to 10 MB each · you can drop several at once</p>
            </div>
            <input
              ref={fileInputRef}
              className="sr-only"
              type="file"
              multiple
              accept=".png,.jpg,.jpeg,.svg"
              onChange={(event) => event.target.files && uploadFiles(event.target.files)}
            />

            <div className="grid gap-2 sm:grid-cols-[220px_1fr] sm:items-end">
              <label className="grid gap-1.5">
                <span className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Save to folder</span>
                <Select
                  value={folderMode === "new" ? "__new__" : uploadFolder}
                  onChange={(e) => {
                    if (e.target.value === "__new__") {
                      setFolderMode("new");
                      setUploadFolder("");
                    } else {
                      setFolderMode("pick");
                      setUploadFolder(e.target.value);
                    }
                  }}
                >
                  <option value="">Uncategorized</option>
                  {folders.map((f) => <option key={f.folder} value={f.folder}>{f.folder} ({f.count})</option>)}
                  <option value="__new__">＋ New folder…</option>
                </Select>
              </label>
              {folderMode === "new" ? (
                <label className="grid gap-1.5">
                  <span className="text-[13px] font-semibold text-[var(--rl-text-strong)]">New folder name</span>
                  <div className="flex gap-2">
                    <Input placeholder="e.g. Insurer logos" value={uploadFolder} onChange={(e) => setUploadFolder(e.target.value)} />
                    <Button variant="secondary" icon={<FolderPlus size={16} weight="bold" />} onClick={() => { setFolderMode("pick"); toast("Folder ready — next upload goes there.", "success"); }}>
                      Ready
                    </Button>
                  </div>
                </label>
              ) : (
                <p className="text-[12px] text-[var(--rl-text-muted)]">Pick a folder to keep uploads organised. Everything without a folder lands in Uncategorized.</p>
              )}
            </div>
          </div>
        </Card>

        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <MagnifyingGlass aria-hidden="true" size={16} weight="bold" className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
            <Input
              className="pl-9"
              placeholder="Search assets…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") applyFilters(search.trim(), folderFilter); }}
            />
          </div>
          <Button variant="secondary" size="sm" onClick={() => applyFilters(search.trim(), folderFilter)}>Search</Button>
          <Select
            value={folderFilter}
            onChange={(e) => { setFolderFilter(e.target.value); applyFilters(search.trim(), e.target.value); }}
            className="w-56"
            aria-label="Filter by folder"
          >
            <option value="">All folders</option>
            {folders.map((f) => <option key={f.folder} value={f.folder}>{f.folder} ({f.count})</option>)}
          </Select>
          <Select value={sort} onChange={(e) => setSort(e.target.value)} className="w-52" aria-label="Sort by">
            <option value="recent">Sort: Newest first</option>
            <option value="oldest">Sort: Oldest first</option>
            <option value="name">Sort: Name A–Z</option>
            <option value="folder">Sort: Folder</option>
          </Select>
          <span className="text-[12px] text-[var(--rl-text-muted)]">
            {appliedSearch || appliedFolder ? `${total} result${total === 1 ? "" : "s"}` : `${total} upload${total === 1 ? "" : "s"}`}
          </span>
        </div>

        {loading ? (
          <PageLoading />
        ) : (
          <div className="grid gap-8">
            <div className="grid gap-3">
              <h2 className="flex items-center gap-2 text-[13px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                <Image size={15} weight="bold" /> Default assets ({defaults.length}) — read-only
              </h2>
              <AssetGrid items={defaults} emptyText="No default assets." />
            </div>

            {!appliedSearch && !appliedFolder ? (
              <div className="grid gap-3">
                <h2 className="text-[13px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                  Recently uploaded ({recent.length}) — last 7 days
                </h2>
                <AssetGrid items={recent} emptyText="Nothing uploaded in the last 7 days. Drop your first images in the box above." />
              </div>
            ) : null}

            <div className="grid gap-3">
              <h2 className="text-[13px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                {appliedSearch || appliedFolder ? "Matching uploads" : "All uploads"} ({filtered.length} of {total})
              </h2>
              <AssetGrid items={filtered} emptyText="No uploads match. Try a different search or folder." />
            </div>

            {uploads.length < total ? (
              <div className="flex justify-center">
                <Button variant="secondary" loading={loadingMore} onClick={() => load(false)}>
                  Load more ({uploads.length} of {total})
                </Button>
              </div>
            ) : null}
          </div>
        )}
      </section>

      {pendingDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingDelete(null); }}
          title={`Move "${pendingDelete.label}" to Trash?`}
          message="You can restore it later from the Trash page."
          confirmLabel="Move to Trash"
          onConfirm={remove}
        />
      ) : null}
    </AppShell>
  );
}
