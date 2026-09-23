"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckSquare,
  Folder,
  FolderPlus,
  ImageSquare,
  Images,
  MagnifyingGlass,
  PencilSimple,
  Plus,
  Square,
  Trash,
  UploadSimple,
  WarningCircle,
  CheckCircle,
  X,
} from "@phosphor-icons/react";
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
  original_filename?: string;
  size_bytes?: number;
  category?: string;
  width_px?: number | null;
  height_px?: number | null;
  status: string;
  url: string;
};

type CategoryInfo = {
  category?: string;
  name?: string;
  count: number;
};

const kinds = [
  { value: "", label: "All purposes" },
  { value: "benefit_art", label: "Benefit artwork" },
  { value: "company_logo", label: "Company logos" },
  { value: "template_background", label: "Template backgrounds" },
  { value: "decorative", label: "Decorative" },
];

export default function AssetLibraryPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [kind, setKind] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successToast, setSuccessToast] = useState("");

  // Multi-Selection State
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Single upload state
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadLabel, setUploadLabel] = useState("");
  const [uploadKind, setUploadKind] = useState("benefit_art");
  const [uploadCategory, setUploadCategory] = useState("General");
  const [uploadCustomCategory, setUploadCustomCategory] = useState("");
  const [uploadDuplicateMode, setUploadDuplicateMode] = useState<"rename" | "replace">("rename");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isAssetDragging, setIsAssetDragging] = useState(false);
  const singleInputRef = useRef<HTMLInputElement>(null);

  // Batch upload state
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchUploading, setBatchUploading] = useState(false);
  const [batchKind, setBatchKind] = useState("benefit_art");
  const [batchCategory, setBatchCategory] = useState("General");
  const [batchCustomCategory, setBatchCustomCategory] = useState("");
  const [batchDuplicateMode, setBatchDuplicateMode] = useState<"rename" | "replace">("rename");
  const [batchFiles, setBatchFiles] = useState<File[]>([]);
  const [isBatchDragging, setIsBatchDragging] = useState(false);
  const [batchSuccessMsg, setBatchSuccessMsg] = useState("");
  const batchInputRef = useRef<HTMLInputElement>(null);

  // Edit Asset Modal
  const [editOpen, setEditOpen] = useState(false);
  const [editingAsset, setEditingAsset] = useState<Asset | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [editCategory, setEditCategory] = useState("General");
  const [editCustomCategory, setEditCustomCategory] = useState("");
  const [editKind, setEditKind] = useState("benefit_art");
  const [editSaving, setEditSaving] = useState(false);
  const [replacementFile, setReplacementFile] = useState<File | null>(null);
  const [replacementPreview, setReplacementPreview] = useState<string | null>(null);

  // Single Delete Modal
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletingAsset, setDeletingAsset] = useState<Asset | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Bulk Delete Modal
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // Bulk Move Modal
  const [bulkMoveOpen, setBulkMoveOpen] = useState(false);
  const [bulkMoveCategory, setBulkMoveCategory] = useState("General");
  const [bulkMoveCustomCategory, setBulkMoveCustomCategory] = useState("");
  const [bulkMoving, setBulkMoving] = useState(false);

  // Rename Folder Modal
  const [renameFolderOpen, setRenameFolderOpen] = useState(false);
  const [folderToRename, setFolderToRename] = useState("");
  const [folderNewName, setFolderNewName] = useState("");
  const [renamingFolder, setRenamingFolder] = useState(false);

  // Delete Folder Modal
  const [deleteFolderOpen, setDeleteFolderOpen] = useState(false);
  const [folderToDelete, setFolderToDelete] = useState("");
  const [deleteFolderAction, setDeleteFolderAction] = useState<"move_to_general" | "delete_all">("move_to_general");
  const [deletingFolder, setDeletingFolder] = useState(false);

  const showToast = (msg: string) => {
    setSuccessToast(msg);
    setTimeout(() => setSuccessToast(""), 3500);
  };

  const loadCategories = useCallback(async () => {
    try {
      const res = await api<{ categories: CategoryInfo[] }>("/business/assets/categories");
      setCategories(res.categories || []);
    } catch {
      // Non-fatal if categories fail
    }
  }, []);

  const load = useCallback(async (
    nextPage = page,
    nextSearch = appliedSearch,
    nextKind = kind,
    nextCategory = selectedCategory
  ) => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ page: String(nextPage), page_size: "48" });
      if (nextSearch) query.set("search", nextSearch);
      if (nextKind) query.set("kind", nextKind);
      if (nextCategory) query.set("category", nextCategory);
      const result = await api<{ assets: { items: Asset[]; total: number } }>(`/business/assets?${query}`);
      setAssets(result.assets.items);
      setTotal(result.assets.total);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [appliedSearch, kind, page, selectedCategory]);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    load(page, appliedSearch, kind, selectedCategory);
  }, [load, page, appliedSearch, kind, selectedCategory]);

  function applyFilters(nextSearch: string, nextKind: string, nextCategory = selectedCategory) {
    setAppliedSearch(nextSearch);
    setKind(nextKind);
    setSelectedCategory(nextCategory);
    setPage(1);
    setSelectedIds(new Set());
  }

  function handleCategoryClick(cat: string) {
    setSelectedCategory(cat);
    setPage(1);
    setSelectedIds(new Set());
  }

  // --- Selection Handlers ---
  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAllOnPage() {
    setSelectedIds(new Set(assets.map((a) => a.id)));
  }

  function clearSelection() {
    setSelectedIds(new Set());
  }

  // --- Upload Handlers ---
  async function uploadSingle() {
    if (!uploadFile || !uploadLabel.trim()) return;
    setUploading(true);
    setError("");
    try {
      const finalCategory = uploadCategory === "__new__" ? uploadCustomCategory.trim() || "General" : uploadCategory;
      const body = new FormData();
      body.append("file", uploadFile);
      body.append("label", uploadLabel.trim());
      body.append("kind", uploadKind);
      body.append("category", finalCategory);
      body.append("on_duplicate", uploadDuplicateMode);
      await api("/business/assets", { method: "POST", body });
      setUploadOpen(false);
      setUploadFile(null);
      setUploadLabel("");
      setUploadCustomCategory("");
      showToast(`Asset "${uploadLabel.trim()}" uploaded successfully.`);
      await loadCategories();
      await load(1, appliedSearch, kind, selectedCategory);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  async function uploadBatch() {
    if (!batchFiles.length) return;
    setBatchUploading(true);
    setError("");
    setBatchSuccessMsg("");
    try {
      const finalCategory = batchCategory === "__new__" ? batchCustomCategory.trim() || "General" : batchCategory;
      const body = new FormData();
      for (const file of batchFiles) {
        body.append("files", file);
      }
      body.append("kind", batchKind);
      body.append("category", finalCategory);
      body.append("on_duplicate", batchDuplicateMode);

      const res = await api<{ count: number; category: string }>("/business/assets/batch", {
        method: "POST",
        body,
      });

      setBatchSuccessMsg(`Successfully uploaded ${res.count} assets into folder "${res.category}"!`);
      setTimeout(() => {
        setBatchOpen(false);
        setBatchFiles([]);
        setBatchCustomCategory("");
        setBatchSuccessMsg("");
      }, 1200);

      await loadCategories();
      setSelectedCategory(res.category);
      await load(1, appliedSearch, kind, res.category);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBatchUploading(false);
    }
  }

  // --- Asset Edit & Delete Handlers ---
  function openEditModal(asset: Asset) {
    setEditingAsset(asset);
    setEditLabel(asset.label);
    setEditCategory(asset.category || "General");
    setEditCustomCategory("");
    setEditKind(asset.asset_kind || "benefit_art");
    setReplacementFile(null);
    if (replacementPreview) {
      URL.revokeObjectURL(replacementPreview);
      setReplacementPreview(null);
    }
    setEditOpen(true);
  }

  async function handleUpdateAsset() {
    if (!editingAsset || !editLabel.trim()) return;
    setEditSaving(true);
    setError("");
    try {
      const finalCategory = editCategory === "__new__" ? editCustomCategory.trim() || "General" : editCategory;

      // 1. If replacement image file is selected, upload it first
      if (replacementFile) {
        const formData = new FormData();
        formData.append("file", replacementFile);
        await api(`/business/assets/${editingAsset.id}/replace-file`, {
          method: "POST",
          body: formData,
        });
      }

      // 2. Update metadata
      await api(`/business/assets/${editingAsset.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          label: editLabel.trim(),
          category: finalCategory,
          kind: editKind,
        }),
      });
      setEditOpen(false);
      setEditingAsset(null);
      setReplacementFile(null);
      if (replacementPreview) {
        URL.revokeObjectURL(replacementPreview);
        setReplacementPreview(null);
      }
      showToast(replacementFile ? `Replaced image and updated "${editLabel.trim()}".` : `Updated "${editLabel.trim()}".`);
      await loadCategories();
      await load(page, appliedSearch, kind, selectedCategory);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setEditSaving(false);
    }
  }

  function openDeleteModal(asset: Asset) {
    setDeletingAsset(asset);
    setDeleteOpen(true);
  }

  async function handleDeleteSingle() {
    if (!deletingAsset) return;
    setDeleting(true);
    setError("");
    try {
      await api(`/business/assets/${deletingAsset.id}`, { method: "DELETE" });
      setDeleteOpen(false);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(deletingAsset.id);
        return next;
      });
      showToast(`Deleted "${deletingAsset.label}".`);
      setDeletingAsset(null);
      await loadCategories();
      await load(page, appliedSearch, kind, selectedCategory);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  }

  // --- Bulk Operations Handlers ---
  async function handleBulkDelete() {
    if (!selectedIds.size) return;
    setBulkDeleting(true);
    setError("");
    try {
      const count = selectedIds.size;
      await api("/business/assets/bulk-delete", {
        method: "POST",
        body: JSON.stringify({ asset_ids: Array.from(selectedIds) }),
      });
      setBulkDeleteOpen(false);
      setSelectedIds(new Set());
      showToast(`Permanently deleted ${count} assets.`);
      await loadCategories();
      await load(page, appliedSearch, kind, selectedCategory);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBulkDeleting(false);
    }
  }

  async function handleBulkMove() {
    if (!selectedIds.size) return;
    setBulkMoving(true);
    setError("");
    try {
      const finalCategory = bulkMoveCategory === "__new__" ? bulkMoveCustomCategory.trim() || "General" : bulkMoveCategory;
      const count = selectedIds.size;
      await api("/business/assets/bulk-move", {
        method: "POST",
        body: JSON.stringify({
          asset_ids: Array.from(selectedIds),
          target_category: finalCategory,
        }),
      });
      setBulkMoveOpen(false);
      setSelectedIds(new Set());
      showToast(`Moved ${count} assets to "${finalCategory}".`);
      await loadCategories();
      setSelectedCategory(finalCategory);
      await load(1, appliedSearch, kind, finalCategory);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBulkMoving(false);
    }
  }

  // --- Folder Management Handlers ---
  function openRenameFolder(catName: string) {
    setFolderToRename(catName);
    setFolderNewName(catName);
    setRenameFolderOpen(true);
  }

  async function handleRenameFolder() {
    if (!folderToRename || !folderNewName.trim()) return;
    setRenamingFolder(true);
    setError("");
    try {
      await api("/business/assets/folders", {
        method: "PATCH",
        body: JSON.stringify({
          old_name: folderToRename,
          new_name: folderNewName.trim(),
        }),
      });
      setRenameFolderOpen(false);
      showToast(`Folder renamed to "${folderNewName.trim()}".`);
      if (selectedCategory.toLowerCase() === folderToRename.toLowerCase()) {
        setSelectedCategory(folderNewName.trim());
      }
      await loadCategories();
      await load(1, appliedSearch, kind, folderNewName.trim());
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setRenamingFolder(false);
    }
  }

  function openDeleteFolder(catName: string) {
    setFolderToDelete(catName);
    setDeleteFolderAction("move_to_general");
    setDeleteFolderOpen(true);
  }

  async function handleDeleteFolder() {
    if (!folderToDelete) return;
    setDeletingFolder(true);
    setError("");
    try {
      await api("/business/assets/folders", {
        method: "DELETE",
        body: JSON.stringify({
          category: folderToDelete,
          action: deleteFolderAction,
        }),
      });
      setDeleteFolderOpen(false);
      showToast(
        deleteFolderAction === "move_to_general"
          ? `Folder "${folderToDelete}" deleted. Assets moved to General.`
          : `Folder "${folderToDelete}" and all its assets were deleted.`
      );
      if (selectedCategory.toLowerCase() === folderToDelete.toLowerCase()) {
        setSelectedCategory("");
      }
      await loadCategories();
      await load(1, appliedSearch, kind, "");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setDeletingFolder(false);
    }
  }

  const pages = Math.max(1, Math.ceil(total / 48));
  const totalInAllCategories = categories.reduce((sum, c) => sum + c.count, 0);

  return (
    <AppShell>
      <section className="grid gap-5">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="font-[var(--font-manrope)] text-[22px] font-bold text-[var(--rl-text-strong)]">
              Asset library & folders
            </h1>
            <p className="mt-1 text-[13px] text-[var(--rl-text-muted)]">
              Organize, modify, rename, and curate visual assets into cohesive folders for quotation templates and visual profiles.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setBatchCategory(selectedCategory || "General");
                setBatchOpen(true);
              }}
            >
              <Images size={16} weight="bold" />
              Batch upload to folder
            </Button>
            <Button
              onClick={() => {
                setUploadCategory(selectedCategory || "General");
                setUploadOpen(true);
              }}
            >
              <Plus size={16} weight="bold" />
              Add single asset
            </Button>
          </div>
        </header>

        <BuilderNav />

        {/* Global Toast / Error messages */}
        {error ? (
          <div className="flex items-center justify-between gap-2 border border-[var(--rl-danger)] bg-[var(--rl-danger)]/10 p-3 text-[13px] text-[var(--rl-danger)] rounded">
            <div className="flex items-center gap-2">
              <WarningCircle size={18} weight="bold" />
              <span>{error}</span>
            </div>
            <button type="button" onClick={() => setError("")} className="hover:opacity-75">
              <X size={14} />
            </button>
          </div>
        ) : null}

        {successToast ? (
          <div className="flex items-center justify-between gap-2 border border-[var(--rl-success)] bg-[var(--rl-success)]/10 p-3 text-[13px] text-[var(--rl-success)] font-medium rounded animate-fade-in">
            <span>✓ {successToast}</span>
            <button type="button" onClick={() => setSuccessToast("")} className="hover:opacity-75">
              <X size={14} />
            </button>
          </div>
        ) : null}

        {/* Floating Bulk Action Bar */}
        {selectedIds.size > 0 ? (
          <div className="sticky top-2 z-20 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--rl-primary)] bg-[var(--rl-surface)] p-3 shadow-lift animate-fade-in">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1.5 text-[13px] font-bold text-[var(--rl-primary)]">
                <CheckSquare size={18} weight="fill" />
                {selectedIds.size} asset{selectedIds.size === 1 ? "" : "s"} selected
              </span>
              <button
                type="button"
                onClick={selectAllOnPage}
                className="text-[12px] font-medium text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:underline"
              >
                Select all on page ({assets.length})
              </button>
              <span className="text-[var(--rl-border)]">|</span>
              <button
                type="button"
                onClick={clearSelection}
                className="text-[12px] font-medium text-[var(--rl-text-muted)] hover:text-[var(--rl-danger)] hover:underline"
              >
                Deselect all
              </button>
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setBulkMoveCategory(selectedCategory || "General");
                  setBulkMoveOpen(true);
                }}
              >
                <Folder size={14} weight="bold" />
                Move to folder...
              </Button>
              <Button size="sm" variant="danger" onClick={() => setBulkDeleteOpen(true)}>
                <Trash size={14} weight="bold" />
                Delete selected ({selectedIds.size})
              </Button>
            </div>
          </div>
        ) : null}

        {/* Layout: Left folder sidebar + Right asset grid */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-[220px_1fr]">
          {/* Folders Navigation */}
          <aside className="flex flex-col gap-2 rounded-lg border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3 h-fit">
            <div className="flex items-center justify-between pb-2 border-b border-[var(--rl-border)]">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                Asset Folders
              </span>
              <button
                type="button"
                onClick={() => {
                  setBatchCategory("__new__");
                  setBatchOpen(true);
                }}
                title="Create new folder"
                className="text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] transition-colors"
              >
                <FolderPlus size={16} weight="bold" />
              </button>
            </div>

            <nav className="flex flex-col gap-1">
              <button
                type="button"
                onClick={() => handleCategoryClick("")}
                className={`flex items-center justify-between rounded px-2.5 py-1.5 text-left text-[12px] transition-colors ${
                  selectedCategory === ""
                    ? "bg-[var(--rl-black)] text-white font-semibold shadow-xs"
                    : "text-[var(--rl-text-strong)] hover:bg-[var(--rl-surface-hover)] font-medium"
                }`}
              >
                <span className="flex items-center gap-2 truncate">
                  <Folder
                    size={14}
                    weight={selectedCategory === "" ? "fill" : "regular"}
                    className={selectedCategory === "" ? "text-white" : "text-[var(--rl-text-muted)]"}
                  />
                  <span>All Folders</span>
                </span>
                <span
                  className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                    selectedCategory === "" ? "bg-white/20 text-white" : "bg-[var(--rl-border)]/60 text-[var(--rl-text-muted)]"
                  }`}
                >
                  {totalInAllCategories}
                </span>
              </button>

              {categories.map((c) => {
                const catName = c.category || c.name || "General";
                const isSelected = (selectedCategory || "").toLowerCase() === catName.toLowerCase();
                const isGeneral = catName.toLowerCase() === "general";

                return (
                  <div
                    key={catName}
                    className={`group/folder flex items-center justify-between rounded px-2.5 py-1.5 text-[12px] transition-colors ${
                      isSelected
                        ? "bg-[var(--rl-black)] text-white font-semibold shadow-xs"
                        : "text-[var(--rl-text-strong)] hover:bg-[var(--rl-surface-hover)] font-medium"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => handleCategoryClick(catName)}
                      className="flex items-center gap-2 truncate flex-1 text-left"
                      title={catName}
                    >
                      <Folder
                        size={14}
                        weight={isSelected ? "fill" : "regular"}
                        className={isSelected ? "text-white" : "text-[var(--rl-text-muted)]"}
                      />
                      <span className="truncate">{catName}</span>
                    </button>

                    <div className="flex items-center gap-1.5">
                      {/* Folder Action Buttons on Hover (except General) */}
                      {!isGeneral ? (
                        <div className="flex items-center gap-0.5 opacity-0 group-hover/folder:opacity-100 transition-opacity">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              openRenameFolder(catName);
                            }}
                            title="Rename folder"
                            className={`p-1 rounded hover:bg-black/10 ${isSelected ? "text-white hover:text-white" : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"}`}
                          >
                            <PencilSimple size={12} weight="bold" />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              openDeleteFolder(catName);
                            }}
                            title="Delete folder"
                            className={`p-1 rounded hover:bg-black/10 ${isSelected ? "text-red-300 hover:text-red-100" : "text-[var(--rl-text-muted)] hover:text-[var(--rl-danger)]"}`}
                          >
                            <Trash size={12} weight="bold" />
                          </button>
                        </div>
                      ) : null}

                      <span
                        className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                          isSelected ? "bg-white/20 text-white" : "bg-[var(--rl-border)]/60 text-[var(--rl-text-muted)]"
                        }`}
                      >
                        {c.count}
                      </span>
                    </div>
                  </div>
                );
              })}
            </nav>
          </aside>

          {/* Right main panel */}
          <main className="grid gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <label className="relative min-w-56 flex-1">
                <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
                <Input
                  className="pl-9 text-[13px]"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") applyFilters(search.trim(), kind);
                  }}
                  placeholder={`Search in ${selectedCategory || "all folders"}...`}
                />
              </label>

              <Select
                className="w-48 text-[13px]"
                value={kind}
                onChange={(event) => applyFilters(search.trim(), event.target.value)}
                aria-label="Asset purpose"
              >
                {kinds.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </Select>

              <Button variant="secondary" onClick={() => applyFilters(search.trim(), kind)}>
                Filter
              </Button>

              <span className="ml-auto text-[12px] text-[var(--rl-text-muted)]">
                {total} asset{total === 1 ? "" : "s"} {selectedCategory ? `in "${selectedCategory}"` : ""}
              </span>
            </div>

            {loading ? (
              <PageLoading />
            ) : assets.length ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
                {assets.map((asset) => {
                  const isSelected = selectedIds.has(asset.id);

                  return (
                    <article
                      key={asset.id}
                      onClick={() => {
                        if (selectedIds.size > 0) toggleSelect(asset.id);
                      }}
                      className={`group relative overflow-hidden rounded border bg-[var(--rl-surface)] transition-all ${
                        isSelected
                          ? "border-[var(--rl-primary)] ring-2 ring-[var(--rl-primary)]/40 shadow-sm"
                          : "border-[var(--rl-border)] hover:border-[var(--rl-border-strong)] hover:shadow-card"
                      }`}
                    >
                      {/* Top Action Header on Card */}
                      <div className="relative aspect-[4/3] grid place-items-center bg-[linear-gradient(45deg,#f3f3f4_25%,transparent_25%),linear-gradient(-45deg,#f3f3f4_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#f3f3f4_75%),linear-gradient(-45deg,transparent_75%,#f3f3f4_75%)] bg-[length:18px_18px] bg-[position:0_0,0_9px,9px_-9px,-9px_0px] p-4">
                        {/* Checkbox: Top Left */}
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleSelect(asset.id);
                          }}
                          className={`absolute left-2 top-2 z-10 rounded p-1 transition-opacity ${
                            isSelected || selectedIds.size > 0
                              ? "opacity-100 text-[var(--rl-primary)] bg-white/90 shadow-xs"
                              : "opacity-0 group-hover:opacity-100 text-[var(--rl-text-muted)] bg-white/80 hover:text-[var(--rl-text-strong)]"
                          }`}
                          title={isSelected ? "Deselect" : "Select"}
                        >
                          {isSelected ? (
                            <CheckSquare size={16} weight="fill" />
                          ) : (
                            <Square size={16} weight="regular" />
                          )}
                        </button>

                        {/* Card Hover Action Buttons: Top Right */}
                        <div className="absolute right-2 top-2 z-10 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity bg-white/90 backdrop-blur-xs p-0.5 rounded shadow-xs border border-[var(--rl-border)]">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              openEditModal(asset);
                            }}
                            title="Edit / Rename asset"
                            className="p-1 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-[var(--rl-bg)] rounded transition-colors"
                          >
                            <PencilSimple size={14} weight="bold" />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              openDeleteModal(asset);
                            }}
                            title="Delete asset"
                            className="p-1 text-[var(--rl-text-muted)] hover:text-[var(--rl-danger)] hover:bg-[var(--rl-bg)] rounded transition-colors"
                          >
                            <Trash size={14} weight="bold" />
                          </button>
                        </div>

                        <img
                          src={fileUrl(asset.url)}
                          alt={asset.label}
                          loading="lazy"
                          className="max-h-full max-w-full object-contain transition-transform group-hover:scale-105"
                        />
                      </div>

                      {/* Card Details Footer */}
                      <div className="border-t border-[var(--rl-border)] p-2.5">
                        <h2 className="truncate text-[12px] font-bold text-[var(--rl-text-strong)]" title={asset.label}>
                          {asset.label}
                        </h2>
                        <div className="mt-1 flex items-center justify-between gap-2 text-[10px] uppercase tracking-[0.06em] text-[var(--rl-text-muted)]">
                          <span className="truncate">{asset.category || "General"}</span>
                          <span>{asset.width_px && asset.height_px ? `${asset.width_px}×${asset.height_px}` : ""}</span>
                        </div>
                        <p
                          className={`mt-1 text-[10px] font-semibold ${
                            asset.status === "unassigned" ? "text-[var(--rl-warning)]" : "text-[var(--rl-success)]"
                          }`}
                        >
                          {asset.status === "unassigned" ? "Available · not mapped" : "Active"}
                        </p>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="grid min-h-72 place-items-center border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface)] text-center p-6 rounded-lg">
                <div>
                  <ImageSquare size={36} className="mx-auto text-[var(--rl-text-muted)]" />
                  <p className="mt-3 font-semibold text-[var(--rl-text-strong)]">No assets found</p>
                  <p className="mt-1 text-[12px] text-[var(--rl-text-muted)]">
                    {selectedCategory
                      ? `The folder "${selectedCategory}" is currently empty.`
                      : "No assets match your search criteria."}
                  </p>
                  <div className="mt-4 flex justify-center gap-2">
                    <Button
                      size="sm"
                      onClick={() => {
                        setBatchCategory(selectedCategory || "General");
                        setBatchOpen(true);
                      }}
                    >
                      <Images size={14} weight="bold" />
                      Batch upload here
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {pages > 1 ? (
              <nav className="flex items-center justify-center gap-3 pt-2" aria-label="Asset pages">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => {
                    setPage((value) => value - 1);
                    setSelectedIds(new Set());
                  }}
                >
                  Previous
                </Button>
                <span className="text-[12px] text-[var(--rl-text-muted)]">
                  Page {page} of {pages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= pages}
                  onClick={() => {
                    setPage((value) => value + 1);
                    setSelectedIds(new Set());
                  }}
                >
                  Next
                </Button>
              </nav>
            ) : null}
          </main>
        </div>
      </section>

      {/* Edit Asset Dialog */}
      <Dialog
        open={editOpen}
        onOpenChange={setEditOpen}
        title="Edit Asset Details"
        description="Update the display name, move to another folder, or adjust asset purpose."
        onConfirm={handleUpdateAsset}
        confirmLabel={editSaving ? "Saving..." : "Save changes"}
        loading={editSaving}
      >
        <div className="grid gap-3.5">
          <label className="grid gap-1">
            <span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Display Label</span>
            <Input value={editLabel} onChange={(e) => setEditLabel(e.target.value)} />
          </label>

          <div className="grid gap-1">
            <span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Destination Folder</span>
            <Select value={editCategory} onChange={(e) => setEditCategory(e.target.value)}>
              {categories.map((c) => {
                const catName = c.category || c.name || "General";
                return (
                  <option key={catName} value={catName}>
                    📁 {catName}
                  </option>
                );
              })}
              <option value="__new__">+ Create New Folder...</option>
            </Select>
            {editCategory === "__new__" ? (
              <Input
                placeholder="Enter new folder name..."
                value={editCustomCategory}
                onChange={(e) => setEditCustomCategory(e.target.value)}
                className="mt-1"
                autoFocus
              />
            ) : null}
          </div>

          <label className="grid gap-1">
            <span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Asset Purpose</span>
            <Select value={editKind} onChange={(e) => setEditKind(e.target.value)}>
              <option value="benefit_art">Benefit artwork</option>
              <option value="company_logo">Company logo</option>
              <option value="template_background">Template background</option>
              <option value="decorative">Decorative</option>
            </Select>
          </label>

          {/* Image Replacement Section */}
          {editingAsset ? (
            <div className="rounded border border-[var(--rl-border)] p-3 space-y-2.5 bg-[var(--rl-surface-muted)]">
              <span className="text-[11px] font-semibold text-[var(--rl-text-strong)] uppercase tracking-wider block">
                Artwork / Image File
              </span>
              <div className="flex items-center gap-3">
                {/* Current or Replaced Preview */}
                <div className="w-16 h-16 rounded border border-[var(--rl-border)] bg-white flex items-center justify-center p-1.5 overflow-hidden shrink-0 shadow-xs">
                  {replacementPreview ? (
                    <img
                      src={replacementPreview}
                      alt="Replacement Preview"
                      className="max-h-full max-w-full object-contain"
                    />
                  ) : (
                    <img
                      src={fileUrl(editingAsset.url)}
                      alt={editingAsset.label}
                      className="max-h-full max-w-full object-contain"
                    />
                  )}
                </div>

                {/* Details & Actions */}
                <div className="flex-1 min-w-0 space-y-1.5">
                  {replacementFile ? (
                    <div>
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700">
                        <CheckCircle size={14} weight="fill" />
                        <span>Ready to replace with:</span>
                      </div>
                      <p className="text-[11px] font-mono text-[var(--rl-text-strong)] truncate">
                        {replacementFile.name} ({(replacementFile.size / 1024).toFixed(1)} KB)
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          setReplacementFile(null);
                          if (replacementPreview) {
                            URL.revokeObjectURL(replacementPreview);
                            setReplacementPreview(null);
                          }
                        }}
                        className="text-[10px] text-[var(--rl-red)] hover:underline mt-0.5"
                      >
                        Keep current image
                      </button>
                    </div>
                  ) : (
                    <div>
                      <p className="text-xs text-[var(--rl-text)] font-medium">
                        Current: <span className="font-mono text-[var(--rl-text-muted)]">{editingAsset.original_filename || "current-image"}</span>
                      </p>
                      <p className="text-[10px] text-[var(--rl-text-muted)]">
                        Select a new PNG, JPG, or WebP to swap this image while keeping its ID.
                      </p>
                    </div>
                  )}

                  <label className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white hover:bg-[var(--rl-bg)] text-xs font-medium text-[var(--rl-text-strong)] cursor-pointer transition-colors shadow-xs">
                    <UploadSimple size={13} />
                    <span>{replacementFile ? "Choose Different Image" : "Replace Image File..."}</span>
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp,image/svg+xml"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          setReplacementFile(file);
                          if (replacementPreview) URL.revokeObjectURL(replacementPreview);
                          setReplacementPreview(URL.createObjectURL(file));
                        }
                      }}
                    />
                  </label>
                </div>
              </div>
            </div>
          ) : null}

          {editingAsset ? (
            <div className="rounded border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3 text-[11px] text-[var(--rl-text-muted)] grid gap-1">
              <span className="font-semibold text-[var(--rl-text-strong)] uppercase tracking-wider text-[10px]">
                Technical Information
              </span>
              <div>Original file: <span className="font-mono text-[var(--rl-text-strong)]">{editingAsset.original_filename || "N/A"}</span></div>
              <div>Dimensions: <span className="font-medium text-[var(--rl-text-strong)]">{editingAsset.width_px && editingAsset.height_px ? `${editingAsset.width_px} × ${editingAsset.height_px} px` : "Unknown"}</span></div>
              {editingAsset.size_bytes ? (
                <div>File size: <span className="font-medium text-[var(--rl-text-strong)]">{(editingAsset.size_bytes / 1024).toFixed(1)} KB</span></div>
              ) : null}
            </div>
          ) : null}
        </div>
      </Dialog>

      {/* Single Delete Confirmation Dialog */}
      <Dialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete Asset"
        description={`Are you sure you want to permanently delete "${deletingAsset?.label}"? This will remove the image file from storage and unlink it from any visual profiles.`}
        onConfirm={handleDeleteSingle}
        confirmLabel={deleting ? "Deleting..." : "Delete asset"}
        confirmVariant="danger"
        loading={deleting}
      />

      {/* Bulk Delete Confirmation Dialog */}
      <Dialog
        open={bulkDeleteOpen}
        onOpenChange={setBulkDeleteOpen}
        title="Delete Selected Assets"
        description={`Are you sure you want to permanently delete ${selectedIds.size} selected assets? This will purge all of them from storage and unlink any profile mappings.`}
        onConfirm={handleBulkDelete}
        confirmLabel={bulkDeleting ? "Deleting..." : `Delete ${selectedIds.size} assets`}
        confirmVariant="danger"
        loading={bulkDeleting}
      />

      {/* Bulk Move Dialog */}
      <Dialog
        open={bulkMoveOpen}
        onOpenChange={setBulkMoveOpen}
        title={`Move ${selectedIds.size} Assets to Folder`}
        description="Choose a destination folder for all selected assets."
        onConfirm={handleBulkMove}
        confirmLabel={bulkMoving ? "Moving..." : `Move ${selectedIds.size} assets`}
        loading={bulkMoving}
      >
        <div className="grid gap-2">
          <label className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Destination Folder</label>
          <Select value={bulkMoveCategory} onChange={(e) => setBulkMoveCategory(e.target.value)}>
            {categories.map((c) => {
              const catName = c.category || c.name || "General";
              return (
                <option key={catName} value={catName}>
                  📁 {catName}
                </option>
              );
            })}
            <option value="__new__">+ Create New Folder...</option>
          </Select>
          {bulkMoveCategory === "__new__" ? (
            <Input
              placeholder="Enter new folder name..."
              value={bulkMoveCustomCategory}
              onChange={(e) => setBulkMoveCustomCategory(e.target.value)}
              className="mt-1"
              autoFocus
            />
          ) : null}
        </div>
      </Dialog>

      {/* Rename Folder Dialog */}
      <Dialog
        open={renameFolderOpen}
        onOpenChange={setRenameFolderOpen}
        title="Rename Folder"
        description={`Rename folder "${folderToRename}". All assets and bound visual profiles will be updated automatically.`}
        onConfirm={handleRenameFolder}
        confirmLabel={renamingFolder ? "Renaming..." : "Rename folder"}
        loading={renamingFolder}
      >
        <div className="grid gap-2">
          <label className="text-[12px] font-semibold text-[var(--rl-text-strong)]">New Folder Name</label>
          <Input
            value={folderNewName}
            onChange={(e) => setFolderNewName(e.target.value)}
            placeholder="e.g. 3D Isometric v2"
            autoFocus
          />
        </div>
      </Dialog>

      {/* Delete Folder Dialog */}
      <Dialog
        open={deleteFolderOpen}
        onOpenChange={setDeleteFolderOpen}
        title={`Delete Folder "${folderToDelete}"`}
        description="How would you like to handle the assets inside this folder?"
        onConfirm={handleDeleteFolder}
        confirmLabel={deletingFolder ? "Deleting folder..." : "Confirm & Delete"}
        confirmVariant="danger"
        loading={deletingFolder}
      >
        <div className="grid gap-3">
          <label className="flex items-start gap-2.5 rounded border border-[var(--rl-border)] p-3 cursor-pointer hover:bg-[var(--rl-bg)]">
            <input
              type="radio"
              name="folderDeleteAction"
              checked={deleteFolderAction === "move_to_general"}
              onChange={() => setDeleteFolderAction("move_to_general")}
              className="mt-0.5 text-[var(--rl-primary)]"
            />
            <div className="text-[12px]">
              <span className="font-semibold text-[var(--rl-text-strong)] block">
                Move assets to &quot;General&quot; folder (Safe)
              </span>
              <span className="text-[var(--rl-text-muted)] text-[11px] block mt-0.5">
                Removes this folder but preserves all its image assets under the General folder.
              </span>
            </div>
          </label>

          <label className="flex items-start gap-2.5 rounded border border-[var(--rl-danger)]/40 p-3 cursor-pointer hover:bg-[var(--rl-danger)]/5">
            <input
              type="radio"
              name="folderDeleteAction"
              checked={deleteFolderAction === "delete_all"}
              onChange={() => setDeleteFolderAction("delete_all")}
              className="mt-0.5 text-[var(--rl-danger)]"
            />
            <div className="text-[12px]">
              <span className="font-semibold text-[var(--rl-danger)] block">
                Delete folder and all its assets permanently
              </span>
              <span className="text-[var(--rl-text-muted)] text-[11px] block mt-0.5">
                Permanently purges all files in this folder from storage.
              </span>
            </div>
          </label>
        </div>
      </Dialog>

      {/* Direct Multi-File Batch Upload Dialog */}
      <Dialog
        open={batchOpen}
        onOpenChange={setBatchOpen}
        title="Batch upload to folder"
        description="Select multiple images at once (up to 75 files). They will be automatically placed into your chosen folder."
        onConfirm={uploadBatch}
        confirmLabel={batchUploading ? "Uploading..." : `Upload ${batchFiles.length} file${batchFiles.length === 1 ? "" : "s"}`}
        loading={batchUploading}
      >
        <div className="grid gap-3.5">
          {batchSuccessMsg ? (
            <div className="rounded bg-[var(--rl-success)]/15 border border-[var(--rl-success)] p-3 text-[13px] font-semibold text-[var(--rl-success)]">
              {batchSuccessMsg}
            </div>
          ) : null}

          {/* Folder Target */}
          <div className="grid gap-1.5">
            <label className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Destination Folder</label>
            <Select
              value={batchCategory}
              onChange={(e) => setBatchCategory(e.target.value)}
            >
              {categories.map((c) => {
                const catName = c.category || c.name || "General";
                return (
                  <option key={catName} value={catName}>
                    📁 {catName} ({c.count} items)
                  </option>
                );
              })}
              <option value="__new__">+ Create New Folder / Category...</option>
            </Select>
            {batchCategory === "__new__" ? (
              <Input
                placeholder="Enter folder name (e.g. Minimal Line Art, gbv1)..."
                value={batchCustomCategory}
                onChange={(e) => setBatchCustomCategory(e.target.value)}
                className="mt-1"
                autoFocus
              />
            ) : null}
          </div>

          {/* Duplicate resolution selector */}
          <div className="grid gap-1.5 rounded border border-[var(--rl-border)] p-2.5 bg-[var(--rl-bg)]">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-[var(--rl-text-strong)]">
              Duplicate File Handling
            </label>
            <div className="grid grid-cols-2 gap-2 text-[12px]">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="batchDuplicateMode"
                  checked={batchDuplicateMode === "rename"}
                  onChange={() => setBatchDuplicateMode("rename")}
                  className="text-[var(--rl-primary)]"
                />
                <span>Keep both (add (1), (2)...)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="batchDuplicateMode"
                  checked={batchDuplicateMode === "replace"}
                  onChange={() => setBatchDuplicateMode("replace")}
                  className="text-[var(--rl-primary)]"
                />
                <span>Replace existing</span>
              </label>
            </div>
          </div>

          {/* Purpose */}
          <div className="grid gap-1.5">
            <label className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Asset Purpose</label>
            <Select value={batchKind} onChange={(e) => setBatchKind(e.target.value)}>
              <option value="benefit_art">Benefit artwork (Icons & Illustration sets)</option>
              <option value="company_logo">Company logo</option>
              <option value="template_background">Template background</option>
              <option value="decorative">Decorative</option>
            </Select>
          </div>

          {/* Drag & Drop Upload Zone */}
          <button
            type="button"
            onClick={() => batchInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              e.dataTransfer.dropEffect = "copy";
              setIsBatchDragging(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setIsBatchDragging(false);
            }}
            onDrop={(e) => {
              e.preventDefault();
              setIsBatchDragging(false);
              const droppedFiles = Array.from(e.dataTransfer.files || []).filter((f) =>
                /\.(png|jpe?g|webp)$/i.test(f.name)
              );
              if (droppedFiles.length) {
                setBatchFiles(droppedFiles);
              }
            }}
            className={`grid min-h-36 place-items-center rounded-lg border-2 border-dashed p-4 text-center transition-all ${
              isBatchDragging
                ? "border-[var(--rl-black)] bg-[var(--rl-black)]/[0.04] scale-[1.01]"
                : "border-[var(--rl-border)] bg-[var(--rl-bg)] hover:border-[var(--rl-black)]"
            }`}
          >
            <span className="pointer-events-none">
              <UploadSimple
                size={28}
                className={`mx-auto transition-transform ${
                  isBatchDragging ? "scale-110 text-[var(--rl-black)]" : "text-[var(--rl-text-muted)]"
                }`}
              />
              <span className="mt-2 block text-[13px] font-semibold text-[var(--rl-text-strong)]">
                {batchFiles.length
                  ? `${batchFiles.length} file${batchFiles.length === 1 ? "" : "s"} selected`
                  : isBatchDragging
                  ? "Drop all image files here"
                  : "Click or drag 1 to 75 image files here"}
              </span>
              <span className="mt-1 block text-[11px] text-[var(--rl-text-muted)]">
                Supports PNG, JPG, JPEG, WebP up to 10 MiB per file. No ZIP needed!
              </span>
            </span>
          </button>

          <input
            ref={batchInputRef}
            type="file"
            multiple
            className="sr-only"
            accept=".png,.jpg,.jpeg,.webp"
            onChange={(event) => {
              const files = Array.from(event.target.files || []);
              if (files.length) {
                setBatchFiles(files);
              }
            }}
          />

          {/* Files preview list */}
          {batchFiles.length ? (
            <div className="max-h-36 overflow-y-auto rounded border border-[var(--rl-border)] bg-[var(--rl-surface)] p-2 text-[11px]">
              <div className="flex items-center justify-between pb-1 border-b border-[var(--rl-border)] font-semibold text-[var(--rl-text-strong)]">
                <span>Selected {batchFiles.length} files:</span>
                <button
                  type="button"
                  onClick={() => setBatchFiles([])}
                  className="flex items-center gap-1 text-[var(--rl-danger)] hover:underline"
                >
                  <Trash size={12} /> Clear all
                </button>
              </div>
              <ul className="mt-1 divide-y divide-[var(--rl-border)]/50">
                {batchFiles.slice(0, 10).map((f, i) => (
                  <li key={i} className="py-1 flex items-center justify-between text-[var(--rl-text-muted)]">
                    <span className="truncate max-w-[280px]">{f.name}</span>
                    <span>{(f.size / 1024).toFixed(0)} KB</span>
                  </li>
                ))}
                {batchFiles.length > 10 ? (
                  <li className="py-1 font-medium text-[var(--rl-text-strong)]">
                    ... and {batchFiles.length - 10} more files
                  </li>
                ) : null}
              </ul>
            </div>
          ) : null}
        </div>
      </Dialog>

      {/* Single Asset Upload Dialog */}
      <Dialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        title="Add single asset"
        description="Upload a single asset with a custom display label and destination folder."
        onConfirm={uploadSingle}
        confirmLabel={uploading ? "Uploading..." : "Upload asset"}
        loading={uploading}
      >
        <div className="grid gap-3">
          <label className="grid gap-1">
            <span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Display name</span>
            <Input value={uploadLabel} onChange={(event) => setUploadLabel(event.target.value)} />
          </label>

          {/* Folder Target */}
          <div className="grid gap-1">
            <span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Destination Folder</span>
            <Select value={uploadCategory} onChange={(e) => setUploadCategory(e.target.value)}>
              {categories.map((c) => {
                const catName = c.category || c.name || "General";
                return (
                  <option key={catName} value={catName}>
                    📁 {catName}
                  </option>
                );
              })}
              <option value="__new__">+ Create New Folder...</option>
            </Select>
            {uploadCategory === "__new__" ? (
              <Input
                placeholder="Enter folder name..."
                value={uploadCustomCategory}
                onChange={(e) => setUploadCustomCategory(e.target.value)}
                className="mt-1"
                autoFocus
              />
            ) : null}
          </div>

          {/* Duplicate resolution selector */}
          <div className="grid gap-1.5 rounded border border-[var(--rl-border)] p-2.5 bg-[var(--rl-bg)]">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-[var(--rl-text-strong)]">
              Duplicate File Handling
            </label>
            <div className="grid grid-cols-2 gap-2 text-[12px]">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="uploadDuplicateMode"
                  checked={uploadDuplicateMode === "rename"}
                  onChange={() => setUploadDuplicateMode("rename")}
                  className="text-[var(--rl-primary)]"
                />
                <span>Keep both (add (1))</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="uploadDuplicateMode"
                  checked={uploadDuplicateMode === "replace"}
                  onChange={() => setUploadDuplicateMode("replace")}
                  className="text-[var(--rl-primary)]"
                />
                <span>Replace existing</span>
              </label>
            </div>
          </div>

          <label className="grid gap-1">
            <span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Purpose</span>
            <Select value={uploadKind} onChange={(event) => setUploadKind(event.target.value)}>
              <option value="benefit_art">Benefit artwork</option>
              <option value="company_logo">Company logo</option>
              <option value="template_background">Template background</option>
              <option value="decorative">Decorative</option>
            </Select>
          </label>

          <button
            type="button"
            onClick={() => singleInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              e.dataTransfer.dropEffect = "copy";
              setIsAssetDragging(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setIsAssetDragging(false);
            }}
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
              <UploadSimple
                size={24}
                className={`mx-auto transition-transform ${
                  isAssetDragging ? "scale-110 text-[var(--rl-text-strong)]" : "text-[var(--rl-text-muted)]"
                }`}
              />
              <span className="mt-2 block text-[12px] font-semibold text-[var(--rl-text-strong)]">
                {uploadFile?.name || (isAssetDragging ? "Drop image file here" : "Choose or drag PNG, JPG, or WebP")}
              </span>
              <span className="mt-1 block text-[11px] text-[var(--rl-text-muted)]">
                Maximum 10 MiB and 32 megapixels
              </span>
            </span>
          </button>
          <input
            ref={singleInputRef}
            type="file"
            className="sr-only"
            accept=".png,.jpg,.jpeg,.webp"
            onChange={(event) => {
              const file = event.target.files?.[0] || null;
              setUploadFile(file);
              if (file && !uploadLabel) setUploadLabel(file.name.replace(/\.[^.]+$/, ""));
            }}
          />
        </div>
      </Dialog>
    </AppShell>
  );
}
