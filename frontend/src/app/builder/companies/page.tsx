"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowCounterClockwise,
  Buildings,
  CheckCircle,
  FloppyDisk,
  MagnifyingGlass,
  PencilSimple,
  Plus,
  Trash,
  X,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { BuilderNav } from "@/components/builder-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { Select } from "@/components/ui/select";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Asset = { id: string; label: string; asset_kind: string; status: string; url: string };
type Company = {
  id: string;
  name: string;
  slug?: string | null;
  revision: number;
  status: string;
  logo_asset_id?: string | null;
  logo?: Asset | null;
};
type CompanyAlias = {
  id: string;
  company_id: string;
  company_name: string;
  alias: string;
  normalized_alias: string;
  alias_kind: string;
  status: string;
  isNew?: boolean;
};

export default function CompaniesPage() {
  // Server persisted state
  const [originalCompanies, setOriginalCompanies] = useState<Company[]>([]);
  const [originalAliases, setOriginalAliases] = useState<CompanyAlias[]>([]);
  const [logos, setLogos] = useState<Asset[]>([]);

  // Working staging state
  const [companies, setCompanies] = useState<Company[]>([]);
  const [aliases, setAliases] = useState<CompanyAlias[]>([]);
  const [deletedCompanyIds, setDeletedCompanyIds] = useState<Set<string>>(new Set());

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [loading, setLoading] = useState(true);
  const [savingChanges, setSavingChanges] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  // Modal State
  const [modalMode, setModalMode] = useState<"create" | "edit" | null>(null);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [formName, setFormName] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [formStatus, setFormStatus] = useState<"active" | "inactive">("active");
  const [formLogoAssetId, setFormLogoAssetId] = useState("");
  const [formInitialAliases, setFormInitialAliases] = useState("");
  const [modalError, setModalError] = useState("");

  // Alias inline add
  const [addingAliasForCompany, setAddingAliasForCompany] = useState<string | null>(null);
  const [newAliasText, setNewAliasText] = useState("");

  // Deletion confirm state
  const [pendingDeleteCompany, setPendingDeleteCompany] = useState<Company | null>(null);
  const [pendingResetConfirm, setPendingResetConfirm] = useState(false);

  const load = useCallback(async (showSpinner = false) => {
    if (showSpinner) setLoading(true);
    setError("");
    try {
      const [compRes, aliasRes, logoRes] = await Promise.all([
        api<{ companies: { items: Company[] } }>("/business/companies?page=1&page_size=100"),
        api<{ aliases: { items: CompanyAlias[] } }>("/business/company-aliases?page=1&page_size=100"),
        api<{ assets: { items: Asset[] } }>("/business/assets?kind=company_logo&page=1&page_size=100"),
      ]);
      setOriginalCompanies(compRes.companies.items);
      setOriginalAliases(aliasRes.aliases.items);
      setCompanies(compRes.companies.items);
      setAliases(aliasRes.aliases.items);
      setDeletedCompanyIds(new Set());
      setLogos(logoRes.assets.items);
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(true);
  }, [load]);

  // Track if user made modifications compared to server baseline
  const hasChanges = useMemo(() => {
    if (deletedCompanyIds.size > 0) return true;
    if (companies.length !== originalCompanies.length) return true;
    for (const c of companies) {
      const orig = originalCompanies.find((o) => o.id === c.id);
      if (!orig) return true;
      if (orig.status !== c.status || orig.name !== c.name || orig.slug !== c.slug || orig.logo_asset_id !== c.logo_asset_id) {
        return true;
      }
    }
    const origAliasIds = new Set(originalAliases.map((a) => a.id));
    const currAliasIds = new Set(aliases.map((a) => a.id));
    if (origAliasIds.size !== currAliasIds.size) return true;
    for (const a of aliases) {
      if (a.isNew || !origAliasIds.has(a.id)) return true;
    }
    return false;
  }, [companies, aliases, originalCompanies, originalAliases, deletedCompanyIds]);

  const changeCount = useMemo(() => {
    let count = deletedCompanyIds.size;
    for (const c of companies) {
      const orig = originalCompanies.find((o) => o.id === c.id);
      if (!orig || orig.status !== c.status || orig.name !== c.name || orig.logo_asset_id !== c.logo_asset_id) {
        count++;
      }
    }
    const origAliasIds = new Set(originalAliases.map((a) => a.id));
    const currAliasIds = new Set(aliases.map((a) => a.id));
    for (const a of aliases) {
      if (a.isNew || !origAliasIds.has(a.id)) count++;
    }
    for (const a of originalAliases) {
      if (!currAliasIds.has(a.id)) count++;
    }
    return count;
  }, [companies, aliases, originalCompanies, originalAliases, deletedCompanyIds]);

  const aliasesByCompany = useMemo(() => {
    const map = new Map<string, CompanyAlias[]>();
    for (const alias of aliases) {
      const list = map.get(alias.company_id) || [];
      list.push(alias);
      map.set(alias.company_id, list);
    }
    return map;
  }, [aliases]);

  const filteredCompanies = useMemo(() => {
    const term = search.trim().toLowerCase();
    return companies
      .filter((c) => !deletedCompanyIds.has(c.id))
      .filter((c) => {
        if (statusFilter !== "all" && c.status !== statusFilter) return false;
        if (!term) return true;
        if (c.name.toLowerCase().includes(term) || (c.slug && c.slug.toLowerCase().includes(term))) return true;
        const compAliases = aliasesByCompany.get(c.id) || [];
        return compAliases.some((a) => a.alias.toLowerCase().includes(term));
      });
  }, [companies, aliasesByCompany, search, statusFilter, deletedCompanyIds]);

  const activeCount = useMemo(() => companies.filter((c) => !deletedCompanyIds.has(c.id) && c.status === "active").length, [companies, deletedCompanyIds]);
  const inactiveCount = useMemo(() => companies.filter((c) => !deletedCompanyIds.has(c.id) && c.status === "inactive").length, [companies, deletedCompanyIds]);

  function handleReset() {
    setCompanies([...originalCompanies]);
    setAliases([...originalAliases]);
    setDeletedCompanyIds(new Set());
    setError("");
    setPendingResetConfirm(false);
  }

  function openCreateModal() {
    setEditingCompany(null);
    setFormName("");
    setFormSlug("");
    setFormStatus("active");
    setFormLogoAssetId(logos[0]?.id || "");
    setFormInitialAliases("");
    setModalError("");
    setModalMode("create");
  }

  function openEditModal(company: Company) {
    setEditingCompany(company);
    setFormName(company.name);
    setFormSlug(company.slug || "");
    setFormStatus(company.status === "active" ? "active" : "inactive");
    setFormLogoAssetId(company.logo_asset_id || "");
    setFormInitialAliases("");
    setModalError("");
    setModalMode("edit");
  }

  function handleSaveCompanyFromModal() {
    const name = formName.trim();
    if (!name) return;

    if (modalMode === "create") {
      const tempId = `temp-comp-${Date.now()}`;
      const newComp: Company = {
        id: tempId,
        name,
        slug: formSlug.trim() || name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""),
        revision: 1,
        status: formStatus,
        logo_asset_id: formLogoAssetId || null,
        logo: logos.find((l) => l.id === formLogoAssetId) || null,
      };

      setCompanies((prev) => [newComp, ...prev]);

      const initialPhrases = formInitialAliases
        .split(/[,\n]/)
        .map((p) => p.trim())
        .filter(Boolean);

      if (initialPhrases.length > 0) {
        const newAliasList: CompanyAlias[] = initialPhrases.map((phrase, idx) => ({
          id: `temp-alias-${Date.now()}-${idx}`,
          company_id: tempId,
          company_name: name,
          alias: phrase,
          normalized_alias: phrase.toLowerCase(),
          alias_kind: "detection",
          status: "active",
          isNew: true,
        }));
        setAliases((prev) => [...prev, ...newAliasList]);
      }
    } else if (modalMode === "edit" && editingCompany) {
      setCompanies((prev) =>
        prev.map((c) =>
          c.id === editingCompany.id
            ? {
                ...c,
                name,
                slug: formSlug.trim() || c.slug,
                status: formStatus,
                logo_asset_id: formLogoAssetId || null,
                logo: logos.find((l) => l.id === formLogoAssetId) || null,
              }
            : c
        )
      );
    }

    setModalMode(null);
  }

  function handleToggleStatus(company: Company) {
    const nextStatus = company.status === "active" ? "inactive" : "active";
    setCompanies((prev) =>
      prev.map((c) => (c.id === company.id ? { ...c, status: nextStatus } : c))
    );
  }

  function stageDeleteCompany(company: Company) {
    setDeletedCompanyIds((prev) => new Set([...prev, company.id]));
    setPendingDeleteCompany(null);
  }

  function stageAddAlias(companyId: string) {
    const phrase = newAliasText.trim();
    if (!phrase || !companyId) return;
    const targetComp = companies.find((c) => c.id === companyId);
    const newAlias: CompanyAlias = {
      id: `temp-alias-${Date.now()}`,
      company_id: companyId,
      company_name: targetComp?.name || "Company",
      alias: phrase,
      normalized_alias: phrase.toLowerCase(),
      alias_kind: "detection",
      status: "active",
      isNew: true,
    };
    setAliases((prev) => [...prev, newAlias]);
    setNewAliasText("");
    setAddingAliasForCompany(null);
  }

  function stageDeleteAlias(aliasId: string) {
    setAliases((prev) => prev.filter((a) => a.id !== aliasId));
  }

  async function handleSaveAllChanges() {
    setSavingChanges(true);
    setError("");
    setSuccessMessage("");
    try {
      // 1. Process deletions
      for (const compId of deletedCompanyIds) {
        if (!compId.startsWith("temp-")) {
          await api(`/business/companies/${compId}`, { method: "DELETE" });
        }
      }

      const currentAliasIds = new Set(aliases.map((a) => a.id));
      for (const origAlias of originalAliases) {
        if (!currentAliasIds.has(origAlias.id) && !deletedCompanyIds.has(origAlias.company_id)) {
          await api(`/business/company-aliases/${origAlias.id}`, { method: "DELETE" });
        }
      }

      // 2. Process company updates and creations
      const companyIdMap = new Map<string, string>(); // maps tempId -> realId

      for (const comp of companies) {
        if (deletedCompanyIds.has(comp.id)) continue;

        if (comp.id.startsWith("temp-")) {
          const res = await api<{ company: Company }>("/business/companies", {
            method: "POST",
            body: JSON.stringify({
              name: comp.name,
              slug: comp.slug || undefined,
              status: comp.status,
              logo_asset_id: comp.logo_asset_id || null,
            }),
          });
          if (res.company?.id) {
            companyIdMap.set(comp.id, res.company.id);
          }
        } else {
          const orig = originalCompanies.find((o) => o.id === comp.id);
          if (
            orig &&
            (orig.name !== comp.name ||
              orig.slug !== comp.slug ||
              orig.status !== comp.status ||
              orig.logo_asset_id !== comp.logo_asset_id)
          ) {
            await api<{ company: Company }>("/business/companies", {
              method: "POST",
              body: JSON.stringify({
                id: comp.id,
                name: comp.name,
                slug: comp.slug || undefined,
                status: comp.status,
                logo_asset_id: comp.logo_asset_id || null,
              }),
            });
          }
        }
      }

      // 3. Process new aliases
      for (const alias of aliases) {
        if (alias.isNew || alias.id.startsWith("temp-")) {
          const targetCompId = companyIdMap.get(alias.company_id) || alias.company_id;
          if (!deletedCompanyIds.has(targetCompId) && !targetCompId.startsWith("temp-")) {
            await api("/business/company-aliases", {
              method: "POST",
              body: JSON.stringify({
                company_id: targetCompId,
                alias: alias.alias,
                alias_kind: "detection",
                status: "active",
              }),
            });
          }
        }
      }

      setSuccessMessage("All company and alias changes successfully saved to the server.");
      setTimeout(() => setSuccessMessage(""), 4000);
      await load(false);
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setSavingChanges(false);
    }
  }

  return (
    <AppShell>
      <section className="grid gap-6 max-w-6xl mx-auto pb-24 relative">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--rl-red)]">
              Builder & Catalog
            </p>
            <h1 className="m-0 font-[var(--font-manrope)] text-[30px] font-bold text-[var(--rl-text-strong)]">
              Insurance Companies
            </h1>
            <p className="mt-1 max-w-3xl text-[14px] text-[var(--rl-text-muted)]">
              Manage insurance companies, logos, active/inactive statuses, and resolution aliases. Modifications can be safely previewed before saving.
            </p>
          </div>
          <Button icon={<Plus size={16} weight="bold" />} onClick={openCreateModal}>
            + Add Insurance Company
          </Button>
        </header>

        <BuilderNav />

        {error ? (
          <div role="alert" className="rounded-[var(--rl-radius-sm)] border-l-2 border-[var(--rl-red)] bg-[var(--rl-red-light)] px-4 py-3 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        {successMessage ? (
          <div className="flex items-center gap-2 rounded-[var(--rl-radius-sm)] border-l-2 border-emerald-600 bg-emerald-50 px-4 py-3 text-[13px] font-semibold text-emerald-800">
            <CheckCircle size={18} weight="fill" className="text-emerald-600" />
            <span>{successMessage}</span>
          </div>
        ) : null}

        {/* Filter and Search Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3 shadow-xs">
          <div className="relative flex-1 min-w-[260px] max-w-md">
            <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
            <Input
              aria-label="Search companies or keywords"
              className="pl-9 text-xs"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search company name, slug, or alias..."
            />
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setStatusFilter("all")}
              className={`rounded-md px-2.5 py-1 text-xs font-bold transition-all ${statusFilter === "all" ? "bg-[var(--rl-black)] text-white" : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"}`}
            >
              All ({companies.length - deletedCompanyIds.size})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("active")}
              className={`rounded-md px-2.5 py-1 text-xs font-bold transition-all ${statusFilter === "active" ? "bg-emerald-700 text-white" : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"}`}
            >
              Active ({activeCount})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("inactive")}
              className={`rounded-md px-2.5 py-1 text-xs font-bold transition-all ${statusFilter === "inactive" ? "bg-gray-700 text-white" : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"}`}
            >
              Draft / Inactive ({inactiveCount})
            </button>
          </div>
        </div>

        {/* Company Cards Grid */}
        {loading ? (
          <PageLoading />
        ) : filteredCompanies.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {filteredCompanies.map((company) => {
              const compAliases = aliasesByCompany.get(company.id) || [];
              const isActive = company.status === "active";
              const isAddingAlias = addingAliasForCompany === company.id;
              const logoAsset = logos.find((l) => l.id === company.logo_asset_id) || company.logo;

              const orig = originalCompanies.find((o) => o.id === company.id);
              const isModified = !orig || orig.status !== company.status || orig.name !== company.name || orig.logo_asset_id !== company.logo_asset_id;

              return (
                <Card
                  key={company.id}
                  className={`flex flex-col justify-between p-4 border transition-all ${
                    isModified
                      ? "border-amber-300 bg-amber-50/30 ring-1 ring-amber-300"
                      : isActive
                      ? "border-[var(--rl-border)] bg-white shadow-xs"
                      : "border-dashed border-gray-300 bg-gray-50/60"
                  }`}
                >
                  <div>
                    {/* Header: Logo, Name, Badges, Actions */}
                    <div className="flex items-start justify-between border-b border-[var(--rl-border)] pb-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-md border border-[var(--rl-border)] bg-white p-1">
                          {logoAsset?.url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={fileUrl(logoAsset.url)} alt={company.name} className="h-full w-full object-contain" />
                          ) : (
                            <Buildings size={22} weight="duotone" className="text-[var(--rl-text-muted)]" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <h2 className="truncate text-base font-bold text-[var(--rl-text-strong)]">{company.name}</h2>
                            {isModified ? (
                              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800">
                                Staged
                              </span>
                            ) : null}
                          </div>
                          <p className="text-xs text-[var(--rl-text-muted)] font-mono">{company.slug || "no-slug"}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          type="button"
                          onClick={() => handleToggleStatus(company)}
                          title={`Click to set ${isActive ? "Inactive" : "Active"}`}
                          className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold transition-all ${
                            isActive
                              ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                          }`}
                        >
                          {isActive ? "● Active" : "○ Inactive"}
                        </button>
                        <button
                          type="button"
                          aria-label={`Edit ${company.name}`}
                          onClick={() => openEditModal(company)}
                          className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors"
                          title="Edit company"
                        >
                          <PencilSimple size={16} />
                        </button>
                        <button
                          type="button"
                          aria-label={`Delete ${company.name}`}
                          onClick={() => setPendingDeleteCompany(company)}
                          className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)] transition-colors"
                          title="Delete company from system"
                        >
                          <Trash size={16} />
                        </button>
                      </div>
                    </div>

                    {/* Detection Aliases Tag Chips */}
                    <div className="pt-3">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                          Detection Aliases ({compAliases.length})
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-1.5 min-h-[48px]">
                        {compAliases.length > 0 ? (
                          compAliases.map((item) => (
                            <span
                              key={item.id}
                              className={`group inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold transition-colors ${
                                item.isNew
                                  ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                                  : "border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:border-gray-400"
                              }`}
                            >
                              <span>{item.alias}</span>
                              <button
                                type="button"
                                aria-label={`Remove alias ${item.alias}`}
                                onClick={() => stageDeleteAlias(item.id)}
                                className="rounded-full p-0.5 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)] transition-colors"
                              >
                                <X size={12} weight="bold" />
                              </button>
                            </span>
                          ))
                        ) : (
                          <p className="text-xs text-[var(--rl-text-muted)] italic py-1">No detection aliases assigned yet.</p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Inline Add Alias Bar */}
                  <div className="mt-4 pt-3 border-t border-[var(--rl-border)]">
                    {isAddingAlias ? (
                      <div className="flex items-center gap-2">
                        <Input
                          value={newAliasText}
                          placeholder="e.g. STMB or AmGeneral"
                          className="text-xs h-8"
                          autoFocus
                          onChange={(e) => setNewAliasText(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              stageAddAlias(company.id);
                            } else if (e.key === "Escape") {
                              setAddingAliasForCompany(null);
                              setNewAliasText("");
                            }
                          }}
                        />
                        <Button
                          size="sm"
                          disabled={!newAliasText.trim()}
                          onClick={() => stageAddAlias(company.id)}
                        >
                          Add
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setAddingAliasForCompany(null);
                            setNewAliasText("");
                          }}
                        >
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          setAddingAliasForCompany(company.id);
                          setNewAliasText("");
                        }}
                        className="flex items-center gap-1.5 text-xs font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] transition-colors"
                      >
                        <Plus size={14} weight="bold" />
                        <span>Add detection alias</span>
                      </button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        ) : (
          <Card className="p-8 text-center text-sm text-[var(--rl-text-muted)]">
            No insurance companies match your search or filter.
          </Card>
        )}

        {/* Floating Save & Reset Action Bar */}
        {hasChanges ? (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 rounded-full border border-[var(--rl-border-strong)] bg-[var(--rl-black)] px-5 py-2.5 text-white shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-bottom-4">
            <span className="flex h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-xs font-medium text-gray-200">
              {changeCount} unsaved modification{changeCount === 1 ? "" : "s"}
            </span>
            <div className="h-4 w-px bg-gray-700 mx-1" />
            <Button
              size="sm"
              variant="secondary"
              className="bg-transparent border-gray-700 text-gray-300 hover:bg-gray-800 hover:text-white h-7 text-xs px-2.5"
              icon={<ArrowCounterClockwise size={14} />}
              onClick={() => setPendingResetConfirm(true)}
            >
              Reset
            </Button>
            <Button
              size="sm"
              loading={savingChanges}
              className="bg-[var(--rl-red)] hover:bg-[var(--rl-red-dark)] text-white font-bold h-7 text-xs px-3 shadow-sm"
              icon={<FloppyDisk size={14} weight="bold" />}
              onClick={handleSaveAllChanges}
            >
              Save Changes
            </Button>
          </div>
        ) : null}
      </section>

      {/* Add / Edit Company Modal */}
      {modalMode ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <Card className="w-full max-w-md border border-[var(--rl-border)] bg-white shadow-xl overflow-hidden p-6 grid gap-4">
            <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
              <div>
                <h3 className="text-base font-bold text-[var(--rl-text-strong)]">
                  {modalMode === "create" ? "Add Insurance Company" : `Edit ${editingCompany?.name}`}
                </h3>
                <p className="text-xs text-[var(--rl-text-muted)]">
                  {modalMode === "create" ? "Register a new insurer with logo and detection rules." : "Update company details, logo, and active status."}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setModalMode(null)}
                className="rounded-full p-1 text-[var(--rl-text-muted)] hover:bg-gray-100"
              >
                <X size={18} weight="bold" />
              </button>
            </div>

            {modalError ? (
              <div role="alert" className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] p-2.5 text-xs font-semibold text-[var(--rl-red)]">
                {modalError}
              </div>
            ) : null}

            <label className="grid gap-1.5 text-xs font-semibold text-[var(--rl-text-strong)]">
              Company Name <span className="text-[var(--rl-red)]">*</span>
              <Input
                value={formName}
                placeholder="e.g. Allianz General Insurance"
                className="text-xs"
                autoFocus
                onChange={(e) => {
                  setFormName(e.target.value);
                  if (modalMode === "create" && !formSlug) {
                    setFormSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""));
                  }
                }}
              />
            </label>

            <label className="grid gap-1.5 text-xs font-semibold text-[var(--rl-text-strong)]">
              Slug Identifier
              <Input
                value={formSlug}
                placeholder="e.g. allianz"
                className="text-xs font-mono"
                onChange={(e) => setFormSlug(e.target.value)}
              />
            </label>

            <div className="grid grid-cols-2 gap-3">
              <label className="grid gap-1.5 text-xs font-semibold text-[var(--rl-text-strong)]">
                Status
                <Select
                  value={formStatus}
                  onChange={(e) => setFormStatus(e.target.value as "active" | "inactive")}
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive / Draft</option>
                </Select>
              </label>

              <label className="grid gap-1.5 text-xs font-semibold text-[var(--rl-text-strong)]">
                Company Logo
                <Select
                  value={formLogoAssetId}
                  onChange={(e) => setFormLogoAssetId(e.target.value)}
                >
                  <option value="">No logo</option>
                  {logos.map((logo) => (
                    <option key={logo.id} value={logo.id}>
                      {logo.label}
                    </option>
                  ))}
                </Select>
              </label>
            </div>

            {modalMode === "create" ? (
              <label className="grid gap-1.5 text-xs font-semibold text-[var(--rl-text-strong)]">
                Initial Detection Phrases (Optional)
                <Input
                  value={formInitialAliases}
                  placeholder="e.g. Allianz, AGIC, Allianz General (comma separated)"
                  className="text-xs"
                  onChange={(e) => setFormInitialAliases(e.target.value)}
                />
                <span className="text-[11px] text-[var(--rl-text-muted)]">Keywords printed on quotation PDF headers.</span>
              </label>
            ) : null}

            <div className="flex justify-end gap-2 pt-2 border-t border-[var(--rl-border)]">
              <Button variant="secondary" size="sm" onClick={() => setModalMode(null)}>
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!formName.trim()}
                onClick={handleSaveCompanyFromModal}
              >
                {modalMode === "create" ? "Stage Company" : "Apply Changes"}
              </Button>
            </div>
          </Card>
        </div>
      ) : null}

      {/* Delete Company Confirmation Dialog */}
      {pendingDeleteCompany ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => {
            if (!open) setPendingDeleteCompany(null);
          }}
          title={`Remove “${pendingDeleteCompany.name}”?`}
          message="This will stage this company for removal. You can click 'Save Changes' to permanently delete it, or 'Reset' to discard."
          confirmLabel="Remove Company"
          onConfirm={() => stageDeleteCompany(pendingDeleteCompany)}
        />
      ) : null}

      {/* Reset Confirmation Dialog */}
      {pendingResetConfirm ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => {
            if (!open) setPendingResetConfirm(false);
          }}
          title="Discard all unsaved changes?"
          message="This will reset all company and alias modifications back to the server state."
          confirmLabel="Discard Changes"
          onConfirm={handleReset}
        />
      ) : null}
    </AppShell>
  );
}
