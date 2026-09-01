"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MagnifyingGlass, Plus, ShieldCheck, Trash, Tag, Globe, Buildings, Package as PackageIcon, Cube, Sparkle } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { ExtractionNav } from "@/components/extraction-nav";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { Select } from "@/components/ui/select";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Concept = { id: string; concept_key: string; label: string; status: string };
type Alias = {
  id: string;
  benefit_id: string;
  benefit_label: string;
  phrase: string;
  normalized_phrase: string;
  scope: string;
  company_id?: string | null;
  company_name?: string | null;
  product_id?: string | null;
  product_name?: string | null;
  package_id?: string | null;
  package_name?: string | null;
  status: string;
};
type Company = { id: string; name: string };
type Product = { id: string; name: string };
type PackageSummary = { id: string; name: string; package_kind: string };
type Catalog = { id: string; package?: PackageSummary | null };

const SCOPE_CONFIG: Record<string, { label: string; icon: typeof Globe; variant: "default" | "success" | "warning" | "danger" | "info" }> = {
  global: { label: "Global", icon: Globe, variant: "default" },
  company: { label: "Company", icon: Buildings, variant: "info" },
  product: { label: "Product", icon: Cube, variant: "warning" },
  package: { label: "Package", icon: PackageIcon, variant: "success" },
};

function EmptyPanel({ title, detail, icon: Icon = Tag }: { title: string; detail: string; icon?: typeof Tag }) {
  return (
    <div className="grid min-h-[280px] place-items-center rounded-[var(--rl-radius)] border border-dashed border-[var(--rl-border)] bg-[var(--rl-bg)] p-8 text-center">
      <div className="max-w-md flex flex-col items-center">
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--rl-surface)] shadow-card text-[var(--rl-text-muted)]">
          <Icon size={24} weight="duotone" />
        </div>
        <p className="font-semibold text-[15px] text-[var(--rl-text-strong)]">{title}</p>
        <p className="mt-1 text-[13px] text-[var(--rl-text-muted)] leading-relaxed">{detail}</p>
      </div>
    </div>
  );
}

export default function BenefitAliasesPage() {
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [packages, setPackages] = useState<PackageSummary[]>([]);
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [search, setSearch] = useState("");
  const [selectedBenefitId, setSelectedBenefitId] = useState("");
  const [scope, setScope] = useState("global");
  const [phrase, setPhrase] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [productId, setProductId] = useState("");
  const [packageId, setPackageId] = useState("");
  const [aliasSearch, setAliasSearch] = useState("");
  const [scopeFilter, setScopeFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Alias | null>(null);
  const mountedRef = useRef(true);
  const { toast } = useToast();

  const loadAliases = useCallback(async (benefitId: string) => {
    if (!benefitId) {
      setAliases([]);
      return;
    }
    try {
      const result = await api<{ benefit_aliases: { items: Alias[] } }>(
        `/business/benefit-aliases?benefit_id=${benefitId}&page=1&page_size=100`,
      );
      if (!mountedRef.current) return;
      setAliases(result.benefit_aliases.items.filter((item) => item.status === "active"));
    } catch (err) {
      if (mountedRef.current) setError(apiErrorMessage(err));
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;
    Promise.all([
      api<{ benefit_concepts: { items: Concept[] } }>("/business/benefit-concepts?page=1&page_size=100"),
      api<{ companies: { items: Company[] } }>("/business/companies?page=1&page_size=100"),
    ])
      .then(([conceptResult, companyResult]) => {
        if (cancelled) return;
        const items = conceptResult.benefit_concepts.items;
        setConcepts(items);
        setCompanies(companyResult.companies.items);
        if (items.length) {
          setSelectedBenefitId(items[0].id);
          return loadAliases(items[0].id);
        }
      })
      .catch((err) => !cancelled && setError(apiErrorMessage(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
      mountedRef.current = false;
    };
  }, [loadAliases]);

  useEffect(() => {
    if (!companyId) {
      setProducts([]);
      setPackages([]);
      return;
    }
    let cancelled = false;
    api<{ workspace: { products: Product[]; catalogs: Catalog[] } }>(`/business/companies/${companyId}/workspace`)
      .then((result) => {
        if (cancelled) return;
        setProducts(result.workspace.products);
        setPackages(
          result.workspace.catalogs
            .map((catalog) => catalog.package)
            .filter((item): item is PackageSummary => Boolean(item)),
        );
      })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [companyId]);

  const filteredConcepts = useMemo(() => {
    const term = search.trim().toLowerCase();
    return term
      ? concepts.filter((item) => item.label.toLowerCase().includes(term) || item.concept_key.toLowerCase().includes(term))
      : concepts;
  }, [concepts, search]);

  const filteredAliases = useMemo(() => {
    let list = aliases;
    if (scopeFilter !== "all") {
      list = list.filter((a) => a.scope === scopeFilter);
    }
    const term = aliasSearch.trim().toLowerCase();
    if (term) {
      list = list.filter((a) => a.phrase.toLowerCase().includes(term) || (a.company_name && a.company_name.toLowerCase().includes(term)));
    }
    return list;
  }, [aliases, scopeFilter, aliasSearch]);

  const selectedBenefit = concepts.find((item) => item.id === selectedBenefitId);

  function selectBenefit(benefitId: string) {
    setSelectedBenefitId(benefitId);
    setError("");
    loadAliases(benefitId);
  }

  function resetScope() {
    setCompanyId("");
    setProductId("");
    setPackageId("");
  }

  async function addAlias() {
    if (!selectedBenefitId || !phrase.trim()) return;
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = { benefit_id: selectedBenefitId, phrase: phrase.trim(), scope };
      if (scope === "company" && companyId) payload.company_id = companyId;
      if (scope === "product" && productId) payload.product_id = productId;
      if (scope === "package" && packageId) payload.package_id = packageId;
      await api("/business/benefit-aliases", { method: "POST", body: JSON.stringify(payload) });
      setPhrase("");
      toast("Alias added successfully.", "success");
      await loadAliases(selectedBenefitId);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function removeAlias(alias: Alias) {
    setError("");
    try {
      await api(`/business/benefit-aliases/${alias.id}`, { method: "DELETE" });
      setAliases((items) => items.filter((item) => item.id !== alias.id));
      setPendingDelete(null);
      toast("Alias removed.", "info");
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  function scopeTargetName(alias: Alias): string {
    if (alias.scope === "company") return alias.company_name || "Specific Company";
    if (alias.scope === "product") return alias.product_name || "Specific Product";
    if (alias.scope === "package") return alias.package_name || "Specific Package";
    return "All Insurers";
  }

  if (loading) {
    return (
      <AppShell>
        <PageLoading />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="grid gap-6">
        <header>
          <h1 className="m-0 text-[28px] font-bold tracking-tight text-[var(--rl-text-strong)]">Benefit Aliases</h1>
          <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
            Configure insurer quotation wording that maps automatically to standard Global Benefits during extraction.
          </p>
        </header>

        <ExtractionNav />

        {error ? (
          <div role="alert" className="flex items-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-red)]/20 bg-[var(--rl-red-light)] px-4 py-3 text-[13px] font-medium text-[var(--rl-red)]">
            <span>{error}</span>
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          {/* Left Column: Benefit Concepts Directory */}
          <Card className="flex flex-col overflow-hidden max-h-[820px]">
            <div className="border-b border-[var(--rl-border)] p-4 bg-[var(--rl-bg)]/40">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                  Global Benefits ({concepts.length})
                </span>
              </div>
              <div className="relative">
                <MagnifyingGlass size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)] pointer-events-none" />
                <Input
                  aria-label="Search benefits"
                  className="h-9 pl-9 text-[13px] bg-[var(--rl-surface)]"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search benefit name or key..."
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2 divide-y divide-[var(--rl-border)]/40">
              {filteredConcepts.map((concept) => {
                const active = concept.id === selectedBenefitId;
                return (
                  <button
                    key={concept.id}
                    type="button"
                    onClick={() => selectBenefit(concept.id)}
                    className={`w-full flex items-center justify-between gap-3 px-3 py-2.5 text-left rounded-[var(--rl-radius-sm)] transition-colors ${
                      active
                        ? "bg-[var(--rl-red-light)] text-[var(--rl-red)] font-medium shadow-sm ring-1 ring-[var(--rl-red)]/30"
                        : "hover:bg-[var(--rl-bg)] text-[var(--rl-text-strong)]"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${active ? "bg-[var(--rl-red)] text-white" : "bg-[var(--rl-bg)] text-[var(--rl-text-muted)]"}`}>
                        <ShieldCheck size={16} weight={active ? "fill" : "bold"} />
                      </div>
                      <div className="min-w-0">
                        <span className="block truncate text-[13px] font-semibold">{concept.label}</span>
                        <span className="block truncate font-mono text-[10px] text-[var(--rl-text-muted)]">{concept.concept_key}</span>
                      </div>
                    </div>
                  </button>
                );
              })}
              {!filteredConcepts.length ? (
                <p className="p-6 text-center text-[13px] text-[var(--rl-text-muted)]">No benefits match search.</p>
              ) : null}
            </div>
          </Card>

          {/* Right Column: Aliases Management */}
          <div className="grid gap-6 content-start">
            {selectedBenefit ? (
              <>
                {/* Benefit Details Header */}
                <Card className="p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-4 mb-4">
                    <div>
                      <div className="flex items-center gap-2.5">
                        <h2 className="text-[19px] font-bold text-[var(--rl-text-strong)]">{selectedBenefit.label}</h2>
                        <Badge variant="default" className="font-mono text-[11px]">
                          {selectedBenefit.concept_key}
                        </Badge>
                      </div>
                      <p className="mt-1 text-[13px] text-[var(--rl-text-muted)]">
                        Add alternative phrases found on insurer PDF quotations that should map to this global benefit.
                      </p>
                    </div>
                    <Badge variant="info">
                      {aliases.length} {aliases.length === 1 ? "Alias" : "Aliases"}
                    </Badge>
                  </div>

                  {/* Add New Alias Form */}
                  <form
                    className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)]/50 p-4 grid gap-3"
                    onSubmit={(event) => {
                      event.preventDefault();
                      addAlias();
                    }}
                  >
                    <div className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                      <Plus size={14} weight="bold" className="text-[var(--rl-red)]" />
                      Add New Alias Phrase
                    </div>

                    <div className="grid gap-3 sm:grid-cols-[160px_1fr_auto]">
                      <Select
                        aria-label="Alias scope"
                        value={scope}
                        onChange={(event) => {
                          setScope(event.target.value);
                          resetScope();
                        }}
                      >
                        <option value="global">🌐 Global (All Insurers)</option>
                        <option value="company">🏢 Specific Company</option>
                        <option value="product">📦 Specific Product</option>
                        <option value="package">🎁 Specific Package</option>
                      </Select>

                      <Input
                        aria-label="Alias phrase"
                        value={phrase}
                        onChange={(event) => setPhrase(event.target.value)}
                        placeholder="e.g. 24/7 Breakdown & Towing Assistance"
                      />

                      <Button size="sm" type="submit" loading={saving} disabled={!phrase.trim()}>
                        <Plus size={14} weight="bold" className="mr-1" />
                        Add Alias
                      </Button>
                    </div>

                    {/* Cascading Scope Selectors */}
                    {scope === "company" ? (
                      <div className="pt-1">
                        <Select aria-label="Company" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
                          <option value="">Choose the insurance company...</option>
                          {companies.map((company) => (
                            <option key={company.id} value={company.id}>{company.name}</option>
                          ))}
                        </Select>
                      </div>
                    ) : null}

                    {scope === "product" ? (
                      <div className="grid gap-3 sm:grid-cols-2 pt-1">
                        <Select aria-label="Company" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
                          <option value="">Choose the insurance company...</option>
                          {companies.map((company) => (
                            <option key={company.id} value={company.id}>{company.name}</option>
                          ))}
                        </Select>
                        <Select aria-label="Product" value={productId} onChange={(event) => setProductId(event.target.value)} disabled={!companyId}>
                          <option value="">Choose the product...</option>
                          {products.map((product) => (
                            <option key={product.id} value={product.id}>{product.name}</option>
                          ))}
                        </Select>
                      </div>
                    ) : null}

                    {scope === "package" ? (
                      <div className="grid gap-3 sm:grid-cols-3 pt-1">
                        <Select aria-label="Company" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
                          <option value="">Choose company...</option>
                          {companies.map((company) => (
                            <option key={company.id} value={company.id}>{company.name}</option>
                          ))}
                        </Select>
                        <Select aria-label="Product" value={productId} onChange={(event) => setProductId(event.target.value)} disabled={!companyId}>
                          <option value="">Choose product...</option>
                          {products.map((product) => (
                            <option key={product.id} value={product.id}>{product.name}</option>
                          ))}
                        </Select>
                        <Select aria-label="Package" value={packageId} onChange={(event) => setPackageId(event.target.value)} disabled={!productId}>
                          <option value="">Choose package...</option>
                          {packages.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.name} {item.package_kind === "addon_bundle" ? "(Bundle)" : ""}
                            </option>
                          ))}
                        </Select>
                      </div>
                    ) : null}
                  </form>
                </Card>

                {/* Aliases List Header & Filters */}
                <Card className="p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                    <div className="flex items-center gap-2">
                      <span className="text-[14px] font-bold text-[var(--rl-text-strong)]">Mapped Aliases</span>
                      <Badge variant="default" className="text-[11px]">
                        {filteredAliases.length}
                      </Badge>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <div className="relative w-48">
                        <MagnifyingGlass size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)] pointer-events-none" />
                        <Input
                          className="h-8 pl-7 text-[12px]"
                          placeholder="Filter aliases..."
                          value={aliasSearch}
                          onChange={(e) => setAliasSearch(e.target.value)}
                        />
                      </div>
                      <Select
                        className="h-8 text-[12px] w-36"
                        value={scopeFilter}
                        onChange={(e) => setScopeFilter(e.target.value)}
                      >
                        <option value="all">All Scopes</option>
                        <option value="global">Global</option>
                        <option value="company">Company</option>
                        <option value="product">Product</option>
                        <option value="package">Package</option>
                      </Select>
                    </div>
                  </div>

                  {filteredAliases.length ? (
                    <div className="grid gap-2.5">
                      {filteredAliases.map((alias) => {
                        const scopeMeta = SCOPE_CONFIG[alias.scope] || SCOPE_CONFIG.global;
                        const ScopeIcon = scopeMeta.icon;
                        return (
                          <div
                            key={alias.id}
                            className="flex items-center justify-between gap-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3 shadow-sm hover:border-[var(--rl-text-muted)]/40 transition-colors"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <Badge variant={scopeMeta.variant} className="gap-1 text-[11px] shrink-0 font-medium">
                                <ScopeIcon size={12} weight="bold" />
                                {scopeMeta.label}
                              </Badge>
                              <div className="min-w-0">
                                <span className="block truncate text-[13px] font-semibold text-[var(--rl-text-strong)]">
                                  &ldquo;{alias.phrase}&rdquo;
                                </span>
                                <span className="block text-[11px] text-[var(--rl-text-muted)] mt-0.5">
                                  Scope: <strong className="text-[var(--rl-text-strong)]">{scopeTargetName(alias)}</strong>
                                </span>
                              </div>
                            </div>

                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-[var(--rl-text-muted)] hover:text-[var(--rl-red)] hover:bg-[var(--rl-red-light)] rounded-full"
                              onClick={() => setPendingDelete(alias)}
                              aria-label={`Delete alias ${alias.phrase}`}
                            >
                              <Trash size={15} />
                            </Button>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <EmptyPanel
                      title={aliasSearch || scopeFilter !== "all" ? "No matching aliases found" : "No aliases configured yet"}
                      detail={
                        aliasSearch || scopeFilter !== "all"
                          ? "Try changing your search keywords or scope filter."
                          : "Add phrases from insurer quotations above to map them to this Global Benefit."
                      }
                      icon={Sparkle}
                    />
                  )}
                </Card>
              </>
            ) : (
              <EmptyPanel
                title="Select a Global Benefit"
                detail="Choose a benefit from the library on the left to view and manage its quotation aliases."
                icon={ShieldCheck}
              />
            )}
          </div>
        </div>

        {/* Delete Confirmation Dialog */}
        <ConfirmDialog
          open={Boolean(pendingDelete)}
          onOpenChange={(open) => !open && setPendingDelete(null)}
          title="Delete Benefit Alias"
          message={`Are you sure you want to remove the alias "${pendingDelete?.phrase}"? Quotations containing this phrase will no longer automatically map to ${selectedBenefit?.label}.`}
          confirmLabel="Delete Alias"
          onConfirm={() => pendingDelete && removeAlias(pendingDelete)}
        />
      </div>
    </AppShell>
  );
}
