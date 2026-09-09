"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowClockwise, ArrowCounterClockwise, Check, CheckCircle, FloppyDisk, ImageSquare, MagnifyingGlass, Plus, ShieldCheck, Tag, Trash, X } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { BuilderNav } from "@/components/builder-nav";
import { GuidedTour } from "@/components/guided-tour";
import { TagEditor } from "@/components/tag-editor";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Toggle } from "@/components/ui/toggle";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Asset = { id: string; label: string; asset_kind: string; status: string; url: string };
type GlobalBenefit = {
  id: string;
  concept_key: string;
  label: string;
  category?: "default" | "addon";
  variants?: string[];
  description: string | null;
  match_dataset: string[];
  sort_order: number;
  default_asset: Asset | null;
  display_overrides?: Record<string, boolean>;
  revision: number;
  status: string;
};

function slugify(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function EmptyPanel({ title, detail, action }: { title: string; detail: string; action?: React.ReactNode }) {
  return (
    <div className="grid min-h-56 place-items-center border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface)] p-8 text-center">
      <div className="max-w-sm">
        <p className="font-semibold text-[var(--rl-text-strong)]">{title}</p>
        <p className="mt-1 text-[13px] text-[var(--rl-text-muted)]">{detail}</p>
        {action ? <div className="mt-4">{action}</div> : null}
      </div>
    </div>
  );
}

export default function GlobalBenefitsPage() {
  const [benefits, setBenefits] = useState<GlobalBenefit[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [companies, setCompanies] = useState<Array<{ id: string; name: string }>>([]);
  const [companyIdFilter, setCompanyIdFilter] = useState("all");
  const [companyWorkspace, setCompanyWorkspace] = useState<any>(null);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<"all" | "default" | "addon">("all");
  const [statusFilter, setStatusFilter] = useState("active");
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [justSaved, setJustSaved] = useState(false);
  const [isNew, setIsNew] = useState(false);
  const mountedRef = useRef(true);

  // Form State
  const [formLabel, setFormLabel] = useState("");
  const [formKey, setFormKey] = useState("");
  const [formCategory, setFormCategory] = useState<"default" | "addon">("default");
  const [formVariants, setFormVariants] = useState<string[]>([]);
  const [newVariantInput, setNewVariantInput] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formAssetId, setFormAssetId] = useState("");
  const [formMatch, setFormMatch] = useState<string[]>([]);
  const [formDisplayOverrides, setFormDisplayOverrides] = useState<Record<string, boolean>>({});
  const [formSort, setFormSort] = useState(0);
  const [formActive, setFormActive] = useState(true);

  const loadReferenceData = useCallback(async () => {
    const [benefitResult, assetResult, companyResult] = await Promise.all([
      api<{ benefit_concepts: { items: GlobalBenefit[] } }>("/business/benefit-concepts?page=1&page_size=100"),
      api<{ assets: { items: Asset[] } }>("/business/assets?kind=benefit_art&page=1&page_size=100"),
      api<{ companies: { items: Array<{ id: string; name: string }> } }>("/business/companies?page_size=100"),
    ]);
    return {
      benefits: benefitResult.benefit_concepts.items,
      assets: assetResult.assets.items,
      companies: companyResult.companies?.items || [],
    };
  }, []);

  const refresh = useCallback(async (keepSelection = true) => {
    setError("");
    try {
      const { benefits: next, assets: nextAssets, companies: nextCompanies } = await loadReferenceData();
      if (!mountedRef.current) return;
      setBenefits(next);
      setAssets(nextAssets);
      setCompanies(nextCompanies);
      if (keepSelection && selectedId && !next.some((item) => item.id === selectedId)) {
        setSelectedId("");
        setIsNew(false);
      }
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
    }
  }, [loadReferenceData, selectedId]);

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;
    loadReferenceData()
      .then(({ benefits: next, assets: nextAssets, companies: nextCompanies }) => {
        if (cancelled) return;
        setBenefits(next);
        setAssets(nextAssets);
        setCompanies(nextCompanies);
        if (next.length) selectBenefit(next[0]);
      })
      .catch((err) => !cancelled && setError(apiErrorMessage(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; mountedRef.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (companyIdFilter === "all") {
      setCompanyWorkspace(null);
      return;
    }
    let cancelled = false;
    api<{ workspace: any }>(`/business/companies/${companyIdFilter}/workspace`)
      .then((res) => {
        if (!cancelled) setCompanyWorkspace(res.workspace);
      })
      .catch(() => {
        if (!cancelled) setCompanyWorkspace(null);
      });
    return () => { cancelled = true; };
  }, [companyIdFilter]);

  const insurerConceptKeys = useMemo(() => {
    if (!companyWorkspace) return null;
    const keys = new Set<string>();
    for (const cat of (companyWorkspace.catalogs || [])) {
      for (const off of (cat.offerings || [])) {
        if (off.concept_key) keys.add(off.concept_key);
        if (off.concept?.concept_key) keys.add(off.concept.concept_key);
        if (off.concept_id) keys.add(off.concept_id);
        if (off.concept?.id) keys.add(off.concept.id);
      }
    }
    return keys;
  }, [companyWorkspace]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return benefits.filter((item) => {
      if (insurerConceptKeys && !insurerConceptKeys.has(item.concept_key) && !insurerConceptKeys.has(item.id)) return false;
      const cat = item.category || (item.sort_order <= 11 ? "default" : "addon");
      if (categoryFilter !== "all" && cat !== categoryFilter) return false;
      if (statusFilter !== "all" && item.status !== statusFilter) return false;
      if (!term) return true;
      return (
        item.label.toLowerCase().includes(term) ||
        item.concept_key.toLowerCase().includes(term) ||
        (item.variants || []).some((v) => v.toLowerCase().includes(term))
      );
    });
  }, [benefits, search, categoryFilter, statusFilter, insurerConceptKeys]);

  const activeCount = useMemo(() => benefits.filter((b) => b.status === "active").length, [benefits]);
  const defaultCount = useMemo(() => benefits.filter((b) => b.status === "active" && (b.category || (b.sort_order <= 11 ? "default" : "addon")) === "default").length, [benefits]);
  const addonCount = useMemo(() => benefits.filter((b) => b.status === "active" && (b.category || (b.sort_order <= 11 ? "default" : "addon")) === "addon").length, [benefits]);
  const trashCount = useMemo(() => benefits.filter((b) => b.status === "retired").length, [benefits]);

  const selected = benefits.find((item) => item.id === selectedId) || null;

  function selectBenefit(item: GlobalBenefit) {
    setSelectedId(item.id);
    setIsNew(false);
    setError("");
    setSuccessMessage("");
    setJustSaved(false);
    setFormLabel(item.label);
    setFormKey(item.concept_key);
    setFormCategory(item.category || (item.sort_order <= 11 ? "default" : "addon"));
    setFormVariants([...(item.variants || [])]);
    setNewVariantInput("");
    setFormDescription(item.description || "");
    setFormAssetId(item.default_asset?.id || "");
    setFormMatch([...item.match_dataset]);
    setFormDisplayOverrides(item.display_overrides || {});
    setFormSort(item.sort_order || 0);
    setFormActive(item.status === "active");
  }

  function newBenefit() {
    setSelectedId("");
    setIsNew(true);
    setError("");
    setSuccessMessage("");
    setJustSaved(false);
    setFormLabel("");
    setFormKey("");
    setFormCategory(categoryFilter === "addon" ? "addon" : "default");
    setFormVariants([]);
    setNewVariantInput("");
    setFormDescription("");
    setFormAssetId("");
    setFormMatch([]);
    setFormDisplayOverrides({});
    setFormSort(benefits.length + 1);
    setFormActive(true);
  }

  function addVariant() {
    const val = newVariantInput.trim();
    if (!val || formVariants.includes(val)) return;
    setFormVariants([...formVariants, val]);
    setNewVariantInput("");
  }

  function removeVariant(index: number) {
    setFormVariants(formVariants.filter((_, i) => i !== index));
  }

  function toggleFormDisplayOverride(key: string) {
    setFormDisplayOverrides((prev) => {
      const next: Record<string, boolean> = { ...prev };
      if (key === "enabled") {
        const nextEnabled = !prev.enabled;
        next.enabled = nextEnabled;
        if (nextEnabled) {
          next.showCoverage = prev.showCoverage !== false;
          next.showDescription = prev.showDescription !== false;
          next.showCost = prev.showCost !== false;
          next.showAsset = prev.showAsset !== false;
          next.showGroup = prev.showGroup !== false;
        }
        return next;
      }
      next[key] = !(prev[key] !== false);
      return next;
    });
  }

  const isDirty = useMemo(() => {
    if (isNew) {
      return Boolean(
        formLabel.trim() ||
        formKey.trim() ||
        formDescription.trim() ||
        formAssetId ||
        formVariants.length > 0 ||
        formMatch.length > 0
      );
    }
    if (!selected) return false;
    const baseCategory = selected.category || (selected.sort_order <= 11 ? "default" : "addon");
    if (formLabel.trim() !== (selected.label || "").trim()) return true;
    if (formKey.trim() !== (selected.concept_key || "").trim()) return true;
    if (formCategory !== baseCategory) return true;
    if ((formDescription || "").trim() !== (selected.description || "").trim()) return true;
    if ((formAssetId || "") !== (selected.default_asset?.id || "")) return true;
    if (Number(formSort) !== Number(selected.sort_order || 0)) return true;
    if (formActive !== (selected.status === "active")) return true;

    // Compare variants
    const origVariants = selected.variants || [];
    if (formVariants.length !== origVariants.length) return true;
    for (let i = 0; i < formVariants.length; i++) {
      if (formVariants[i] !== origVariants[i]) return true;
    }

    // Compare match_dataset
    const origMatch = selected.match_dataset || [];
    if (formMatch.length !== origMatch.length) return true;
    for (let i = 0; i < formMatch.length; i++) {
      if (formMatch[i] !== origMatch[i]) return true;
    }

    // Compare display_overrides
    const origOverrides = selected.display_overrides || {};
    const curKeys = Object.keys(formDisplayOverrides);
    const origKeys = Object.keys(origOverrides);
    const allKeys = new Set([...curKeys, ...origKeys]);
    for (const k of allKeys) {
      if (Boolean(formDisplayOverrides[k]) !== Boolean(origOverrides[k])) return true;
    }

    return false;
  }, [
    isNew,
    selected,
    formLabel,
    formKey,
    formCategory,
    formDescription,
    formAssetId,
    formSort,
    formActive,
    formVariants,
    formMatch,
    formDisplayOverrides,
  ]);

  async function saveBenefit() {
    if (!formLabel.trim()) {
      setError("Enter a benefit name.");
      return;
    }
    const key = formKey.trim() || slugify(formLabel);
    if (!key) {
      setError("Enter a stable key for this benefit.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccessMessage("");
    try {
      const payload: Record<string, unknown> = {
        concept_key: key,
        label: formLabel.trim(),
        category: formCategory,
        variants: formVariants,
        description: formDescription.trim() || null,
        default_asset_id: formAssetId || null,
        display_template: "{label}",
        required_variables: [],
        match_dataset: formMatch,
        demo_value: null,
        display_overrides: formDisplayOverrides,
        sort_order: Math.max(0, Number(formSort) || 0),
        status: formActive ? "active" : "inactive",
      };
      if (!isNew && selected) {
        payload.id = selected.id;
        payload.base_revision = selected.revision;
      }
      const saved = await api<{ benefit_concept: GlobalBenefit }>("/business/benefit-concepts", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await refresh(false);
      selectBenefit(saved.benefit_concept);
      setJustSaved(true);
      setSuccessMessage(`Benefit "${saved.benefit_concept.label}" successfully saved!`);
      setTimeout(() => {
        setJustSaved(false);
      }, 3500);
      setTimeout(() => {
        setSuccessMessage("");
      }, 5000);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const [deleting, setDeleting] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  async function handleDeleteConcept() {
    if (!selected) return;
    setDeleting(true);
    setError("");
    try {
      await api(`/business/benefit-concepts/${selected.id}`, { method: "DELETE" });
      setShowDeleteConfirm(false);
      const deletedLabel = selected.label;
      await refresh(false);
      setSelectedId("");
      setIsNew(false);
      setSuccessMessage(`Benefit "${deletedLabel}" was moved to Trash.`);
      setTimeout(() => setSuccessMessage(""), 5000);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  }

  async function handleRestoreConcept() {
    if (!selected) return;
    setRestoring(true);
    setError("");
    try {
      await api(`/business/benefit-concepts/${selected.id}/restore`, { method: "POST" });
      const restoredLabel = selected.label;
      await refresh(false);
      setSuccessMessage(`Benefit "${restoredLabel}" restored to active library!`);
      setTimeout(() => setSuccessMessage(""), 5000);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setRestoring(false);
    }
  }

  if (loading) {
    return <AppShell><PageLoading /></AppShell>;
  }

  return (
    <AppShell>
      <section className="grid gap-5 max-w-6xl mx-auto pb-16">
        <header>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--rl-red)]">
                Builder & Catalog
              </p>
              <h1 className="m-0 font-[var(--font-manrope)] text-[30px] font-bold text-[var(--rl-text-strong)]">
                Benefit Library & Categories
              </h1>
              <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
                The canonical catalog of 11 Default / Global Benefits and 23 Unique Add-ons. Multi-plan add-ons maintain internal plan variations without polluting the catalog list.
              </p>
            </div>
            <GuidedTour
              storageKey="tour:global-benefits"
              title="Benefit Library & Categories"
              description="This is the master dictionary of every benefit that exists across all insurers. Each benefit (Towing, Windscreen, LLP…) is defined once here with its detection words, artwork, and value type. The builder/benefits page then assigns these to each company's product."
              steps={[
                { target: "header", title: "Page purpose", body: "The master benefit dictionary. Every benefit concept across all insurers lives here — create, rename, categorize, and maintain them. Nothing here is company-specific." },
                { target: ".rl-tour-list", title: "Benefit list", body: "All global benefits, filterable by category (Default vs Add-on) and status. Click one to edit its definition." },
                { target: ".rl-tour-form", title: "Benefit definition", body: "Set the label, category, detection words (match_dataset), artwork, and value type. These drive AI extraction and rendering everywhere." },
              ]}
            />
          </div>
        </header>
        <BuilderNav />

        {error ? (
          <div role="alert" className="flex items-center justify-between gap-3 border-l-4 border-[var(--rl-red)] bg-[var(--rl-red-light)] px-4 py-3 text-[13px] font-medium text-[var(--rl-red)]">
            <span>{error}</span>
            <Button variant="ghost" size="sm" icon={<ArrowClockwise size={14} />} onClick={() => refresh()}>Retry</Button>
          </div>
        ) : null}

        {/* Category Tabs & Insurer Filter Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-2.5 shadow-xs">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => { setCategoryFilter("all"); setStatusFilter("active"); }}
              className={`rounded-md px-3 py-1.5 text-xs font-bold transition-all ${categoryFilter === "all" && statusFilter === "active"
                  ? "bg-[var(--rl-black)] text-white shadow-xs"
                  : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
            >
              All Active ({activeCount})
            </button>
            <button
              type="button"
              onClick={() => { setCategoryFilter("default"); setStatusFilter("active"); }}
              className={`rounded-md px-3 py-1.5 text-xs font-bold transition-all ${categoryFilter === "default" && statusFilter === "active"
                  ? "bg-[var(--rl-black)] text-white shadow-xs"
                  : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
            >
              Default / Global Benefits ({defaultCount})
            </button>
            <button
              type="button"
              onClick={() => { setCategoryFilter("addon"); setStatusFilter("active"); }}
              className={`rounded-md px-3 py-1.5 text-xs font-bold transition-all ${categoryFilter === "addon" && statusFilter === "active"
                  ? "bg-[var(--rl-black)] text-white shadow-xs"
                  : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                }`}
            >
              Unique Add-ons ({addonCount})
            </button>
            <button
              type="button"
              onClick={() => { setCategoryFilter("all"); setStatusFilter("retired"); }}
              className={`rounded-md px-3 py-1.5 text-xs font-bold transition-all ${statusFilter === "retired"
                  ? "bg-red-600 text-white shadow-xs"
                  : "bg-white border border-red-200 text-red-700 hover:bg-red-50"
                }`}
            >
              🗑️ Trash ({trashCount})
            </button>

            {companies.length > 0 ? (
              <select
                aria-label="Filter by insurance company"
                value={companyIdFilter}
                onChange={(e) => setCompanyIdFilter(e.target.value)}
                className="h-8 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white px-2 text-xs font-semibold text-[var(--rl-text-strong)] shadow-xs focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
              >
                <option value="all">🏢 All Insurers</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    🏢 {c.name}
                  </option>
                ))}
              </select>
            ) : null}
          </div>

          <Button size="sm" icon={<Plus size={14} weight="bold" />} onClick={newBenefit}>
            + Add New Concept
          </Button>
        </div>

        <div className="min-h-[680px] overflow-hidden border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-card xl:grid xl:grid-cols-[330px_minmax(400px,1fr)]">
          {/* SIDEBAR LIST */}
          <aside className="rl-tour-list border-b border-[var(--rl-border)] bg-[#fafafa] xl:border-b-0 xl:border-r" aria-label="Global benefits list">
            <div className="border-b border-[var(--rl-border)] p-3">
              <div className="grid gap-2">
                <label className="relative block">
                  <MagnifyingGlass size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
                  <Input aria-label="Search benefits" className="h-8 pl-8 text-xs" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, key, or plan..." />
                </label>
                <Select aria-label="Filter by status" className="h-8 text-xs" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="active">Active only</option>
                  <option value="retired">Trash / Deleted ({trashCount})</option>
                  <option value="all">All (Including Trash)</option>
                  <option value="inactive">Inactive only</option>
                </Select>
              </div>
            </div>

            <div className="max-h-[580px] overflow-y-auto p-2">
              {filtered.length ? filtered.map((item) => {
                const active = item.id === selectedId;
                const hasVariants = (item.variants || []).length > 0;

                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => selectBenefit(item)}
                    className={`mb-1.5 grid w-full grid-cols-[36px_1fr] items-center gap-2.5 rounded border-l-2 p-2 text-left transition ${active
                        ? "border-[var(--rl-red)] bg-white shadow-xs ring-1 ring-[var(--rl-border)]"
                        : "border-transparent hover:bg-white"
                      }`}
                  >
                    <span className="grid h-9 w-9 place-items-center rounded border border-[var(--rl-border)] bg-[var(--rl-bg)]">
                      {item.default_asset ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={fileUrl(item.default_asset.url)} alt="" loading="lazy" className="max-h-7 max-w-7 object-contain" />
                      ) : (
                        <ShieldCheck size={16} className="text-[var(--rl-text-muted)]" />
                      )}
                    </span>
                    <div className="min-w-0">
                      <span className="block truncate text-xs font-bold text-[var(--rl-text-strong)]">{item.label}</span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="truncate font-mono text-[10px] text-[var(--rl-text-muted)]">#{item.sort_order} · {item.concept_key}</span>
                        {item.status === "retired" ? (
                          <span className="shrink-0 rounded bg-red-50 px-1 text-[9px] font-bold text-red-700 border border-red-200">
                            Trash
                          </span>
                        ) : null}
                        {hasVariants ? (
                          <span className="shrink-0 rounded bg-[var(--rl-bg)] px-1 text-[9px] font-semibold text-[var(--rl-text-strong)] border border-[var(--rl-border)]">
                            {item.variants?.length} Plans
                          </span>
                        ) : null}
                      </div>
                      {item.description && (
                        <p className="mt-0.5 truncate text-[10px] text-[var(--rl-text-muted)] italic leading-snug">
                          {item.description}
                        </p>
                      )}
                    </div>

                  </button>
                );
              }) : (
                <p className="p-4 text-xs text-[var(--rl-text-muted)] text-center">No benefits match your filter.</p>
              )}
            </div>
          </aside>

          {/* MAIN EDIT PANEL */}
          <main className="rl-tour-form min-w-0 p-5 bg-white">
            {isNew || selected ? (
              <div className="grid gap-5">
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--rl-border)] pb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">{isNew ? "New Benefit Definition" : selected?.label}</h2>
                      {selected?.status === "retired" && (
                        <span className="rounded-full bg-red-50 border border-red-200 px-2.5 py-0.5 text-[10px] font-bold text-red-700">
                          In Trash / Deleted
                        </span>
                      )}
                      <span className="rounded-full bg-[var(--rl-bg)] border border-[var(--rl-border)] px-2.5 py-0.5 text-[10px] font-bold text-[var(--rl-text-strong)]">
                        {formCategory === "default" ? "Category 1: Default Benefit" : "Category 2: Unique Add-on"}
                      </span>
                      {isDirty ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                          <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                          Unsaved Changes
                        </span>
                      ) : justSaved ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                          <Check size={10} weight="bold" className="text-emerald-600" />
                          Saved
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-gray-50 border border-gray-200 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                          <Check size={10} weight="bold" className="text-gray-400" />
                          All changes saved
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-xs text-[var(--rl-text-muted)]">Reusable global definition. Specific values/tariffs are configured per product package in the Builder.</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Link href="/extraction/benefit-aliases" className="inline-flex h-8 items-center gap-1.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] px-3 text-xs font-semibold text-[var(--rl-text-muted)] hover:border-[var(--rl-black)] hover:text-[var(--rl-text-strong)]">
                      Manage aliases
                    </Link>
                    {!isNew && selected && (
                      selected.status === "retired" ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          loading={restoring}
                          className="text-emerald-700 hover:bg-emerald-50 border-emerald-300 font-bold"
                          onClick={handleRestoreConcept}
                          icon={<ArrowCounterClockwise size={14} weight="bold" />}
                        >
                          Restore
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)] font-semibold"
                          onClick={() => setShowDeleteConfirm(true)}
                          icon={<Trash size={14} />}
                        >
                          Delete
                        </Button>
                      )
                    )}
                    <Button variant="secondary" size="sm" onClick={newBenefit} icon={<Plus size={14} />}>New</Button>
                    <Button
                      size="sm"
                      loading={saving}
                      disabled={!isDirty || saving}
                      onClick={saveBenefit}
                      icon={
                        justSaved ? (
                          <Check size={14} weight="bold" className="text-emerald-500" />
                        ) : isDirty ? (
                          <FloppyDisk size={14} weight="bold" />
                        ) : (
                          <Check size={14} weight="bold" className="text-gray-400" />
                        )
                      }
                      className={
                        isDirty
                          ? "bg-[var(--rl-red)] text-white hover:bg-[var(--rl-red-hover)] border-[var(--rl-red)] shadow-xs transition-all"
                          : "bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed opacity-60"
                      }
                      title={isDirty ? "Save changes to server" : "No unsaved changes"}
                    >
                      {justSaved ? "Saved!" : isDirty ? (isNew ? "Save Benefit" : "Save Changes") : "Saved"}
                    </Button>
                  </div>
                </div>

                {successMessage ? (
                  <div
                    role="status"
                    className="flex items-center justify-between gap-3 rounded-[var(--rl-radius-sm)] border-l-4 border-emerald-600 bg-emerald-50 px-4 py-3 text-[13px] font-semibold text-emerald-800 shadow-xs"
                  >
                    <div className="flex items-center gap-2">
                      <CheckCircle size={18} weight="fill" className="text-emerald-600 shrink-0" />
                      <span>{successMessage}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSuccessMessage("")}
                      className="text-emerald-700 hover:text-emerald-900 transition-colors"
                      aria-label="Dismiss alert"
                    >
                      <X size={14} weight="bold" />
                    </button>
                  </div>
                ) : null}

                <div className="grid gap-5">
                  {/* 3 Core Fields Card */}
                  <div className="grid gap-4 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-5 bg-white shadow-xs">
                    <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
                      <div>
                        <h3 className="text-xs font-bold uppercase tracking-[0.12em] text-[var(--rl-text-strong)]">
                          Core Benefit Properties
                        </h3>
                        <p className="text-[12px] text-[var(--rl-text-muted)]">
                          The 3 essential properties defined for this global benefit concept.
                        </p>
                      </div>
                      <span className="rounded-full bg-[var(--rl-bg)] border border-[var(--rl-border)] px-3 py-1 text-[11px] font-bold text-[var(--rl-text-strong)]">
                        {formCategory === "default" ? "🛡️ Default Benefit" : "✨ Add-on Benefit"}
                      </span>
                    </div>

                    {/* 1. Image / Artwork */}
                    <div className="grid gap-1.5">
                      <label className="text-xs font-bold text-[var(--rl-text-strong)] flex items-center justify-between">
                        <span>1. Benefit Image / Icon <span className="text-[var(--rl-red)]">*</span></span>
                        <span className="text-[11px] font-normal text-[var(--rl-text-muted)]">Artwork badge for quotation cards</span>
                      </label>
                      <div className="flex items-center gap-3 p-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)]">
                        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-lg border border-[var(--rl-border)] bg-white shadow-xs">
                          {formAssetId ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={fileUrl(assets.find((a) => a.id === formAssetId)?.url || "")} alt="" className="max-h-9 max-w-9 object-contain" />
                          ) : (
                            <ImageSquare size={24} className="text-[var(--rl-text-muted)]" />
                          )}
                        </span>
                        <div className="flex-1 min-w-0">
                          <Select value={formAssetId} onChange={(e) => setFormAssetId(e.target.value)} className="text-xs font-medium bg-white">
                            <option value="">(Select Artwork Icon...)</option>
                            {assets.map((asset) => (
                              <option key={asset.id} value={asset.id}>
                                🖼️ {asset.label}
                              </option>
                            ))}
                          </Select>
                          <p className="mt-1 text-[11px] text-[var(--rl-text-muted)] truncate">
                            {formAssetId ? `Selected: ${assets.find((a) => a.id === formAssetId)?.label}` : "Select a standard icon badge for this benefit."}
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* 2. Benefit Title */}
                    <div className="grid gap-1.5">
                      <label className="text-xs font-bold text-[var(--rl-text-strong)] flex items-center justify-between">
                        <span>2. Benefit Title <span className="text-[var(--rl-red)]">*</span></span>
                        <span className="text-[11px] font-normal text-[var(--rl-text-muted)]">Official display title</span>
                      </label>
                      <Input
                        value={formLabel}
                        onChange={(e) => {
                          setFormLabel(e.target.value);
                          if (isNew) setFormKey(slugify(e.target.value));
                        }}
                        placeholder="e.g. Towing Assistance, Windscreen, Legal Liability..."
                        className="text-xs font-semibold h-9"
                      />
                    </div>

                    {/* 3. Short Description */}
                    <div className="grid gap-1.5">
                      <label className="text-xs font-bold text-[var(--rl-text-strong)] flex items-center justify-between">
                        <span>3. Benefit Short Description <span className="text-[var(--rl-red)]">*</span></span>
                        <span className="text-[11px] font-normal text-[var(--rl-text-muted)]">Clear summary of coverage / limit</span>
                      </label>
                      <Textarea
                        value={formDescription}
                        onChange={(e) => setFormDescription(e.target.value)}
                        rows={3}
                        placeholder="e.g. 24/7 emergency towing assistance to nearest workshop or preferred location..."
                        className="text-xs"
                      />
                    </div>
                  </div>

                  {/* Template Display Defaults (Overrides) */}
                  <div className="grid gap-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex flex-col">
                        <span className="text-xs font-bold text-[var(--rl-text-strong)]">Hard Display Override</span>
                        <span className="text-[11px] font-normal text-[var(--rl-text-muted)]">Force visibility regardless of draft settings</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => toggleFormDisplayOverride("enabled")}
                        className={`text-[10px] font-bold px-2 py-0.5 rounded transition-all ${
                          formDisplayOverrides.enabled ? "bg-emerald-100 text-emerald-800" : "bg-[var(--rl-border)] text-[var(--rl-text-muted)]"
                        }`}
                      >
                        {formDisplayOverrides.enabled ? "ENABLED" : "DISABLED"}
                      </button>
                    </div>
                    {formDisplayOverrides.enabled && (
                      <div className="grid grid-cols-5 gap-2 text-xs pt-2 border-t border-[var(--rl-border)] mt-1">
                        <button
                          type="button"
                          onClick={() => toggleFormDisplayOverride("showCoverage")}
                          className={`rounded border py-2 text-center font-bold transition-all ${
                            formDisplayOverrides.showCoverage !== false ? "bg-red-50 border-red-300 text-red-700" : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-[var(--rl-text-muted)]"
                          }`}
                        >
                          Coverage: {formDisplayOverrides.showCoverage !== false ? "ON" : "OFF"}
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleFormDisplayOverride("showDescription")}
                          className={`rounded border py-2 text-center font-bold transition-all ${
                            formDisplayOverrides.showDescription !== false ? "bg-blue-50 border-blue-300 text-blue-700" : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-[var(--rl-text-muted)]"
                          }`}
                        >
                          Desc: {formDisplayOverrides.showDescription !== false ? "ON" : "OFF"}
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleFormDisplayOverride("showCost")}
                          className={`rounded border py-2 text-center font-bold transition-all ${
                            formDisplayOverrides.showCost !== false ? "bg-emerald-50 border-emerald-300 text-emerald-700" : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-[var(--rl-text-muted)]"
                          }`}
                        >
                          Cost: {formDisplayOverrides.showCost !== false ? "ON" : "OFF"}
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleFormDisplayOverride("showAsset")}
                          className={`rounded border py-2 text-center font-bold transition-all ${
                            formDisplayOverrides.showAsset !== false ? "bg-purple-50 border-purple-300 text-purple-700" : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-[var(--rl-text-muted)]"
                          }`}
                        >
                          Icon: {formDisplayOverrides.showAsset !== false ? "ON" : "OFF"}
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleFormDisplayOverride("showGroup")}
                          className={`rounded border py-2 text-center font-bold transition-all ${
                            formDisplayOverrides.showGroup !== false ? "bg-amber-50 border-amber-300 text-amber-700" : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-[var(--rl-text-muted)]"
                          }`}
                        >
                          Group: {formDisplayOverrides.showGroup !== false ? "ON" : "OFF"}
                        </button>
                      </div>
                    )}
                  </div>

                  {/* System Classification & Controls */}
                  <div className="grid sm:grid-cols-2 gap-4 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-4 bg-gray-50/70">
                    <div className="grid gap-1.5">
                      <label className="text-xs font-semibold text-[var(--rl-text-strong)]">Category</label>
                      <Select value={formCategory} onChange={(e) => setFormCategory(e.target.value as "default" | "addon")} className="text-xs bg-white">
                        <option value="default">Default / Base Family (Included in Quote)</option>
                        <option value="addon">Add-on Family (Optional Extra)</option>
                      </Select>
                    </div>
                    <div className="flex items-center pt-5">
                      <Toggle
                        checked={formActive}
                        onChange={setFormActive}
                        label={formActive ? "Active in Global Library" : "Inactive / Draft"}
                        description="Controls visibility in product catalog builders."
                      />
                    </div>
                  </div>

                  {/* Sticky Save Action Bar when Dirty */}
                  {isDirty ? (
                    <div className="sticky bottom-4 z-30 mt-4 flex items-center justify-between gap-3 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50/95 p-3.5 shadow-lg backdrop-blur-xs">
                      <div className="flex items-center gap-2">
                        <span className="flex h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                        <span className="text-xs font-semibold text-amber-900">
                          You have unsaved changes to this benefit concept.
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            if (isNew) {
                              newBenefit();
                            } else if (selected) {
                              selectBenefit(selected);
                            }
                          }}
                        >
                          Discard
                        </Button>
                        <Button
                          size="sm"
                          loading={saving}
                          onClick={saveBenefit}
                          className="bg-[var(--rl-red)] text-white hover:bg-[var(--rl-red-hover)] border-[var(--rl-red)] font-bold shadow-xs"
                          icon={<FloppyDisk size={14} weight="bold" />}
                        >
                          Save Changes
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : (
              <EmptyPanel
                title="Select a benefit concept"
                detail="Choose any of the 11 Default Benefits or 23 Add-ons to inspect and edit its details."
                action={<Button size="sm" icon={<Plus size={14} />} onClick={newBenefit}>New Benefit Definition</Button>}
              />
            )}
          </main>
        </div>
      </section>

      <ConfirmDialog
        open={showDeleteConfirm}
        onOpenChange={setShowDeleteConfirm}
        title="Delete Benefit Concept"
        message={`Are you sure you want to delete "${selected?.label}"? It will be removed from active catalogs and stored in Trash, where it can be restored anytime.`}
        confirmLabel="Delete to Trash"
        loading={deleting}
        onConfirm={handleDeleteConcept}
      />
    </AppShell>
  );
}
