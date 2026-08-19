"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MagnifyingGlass, ShieldCheck, X } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { ExtractionNav } from "@/components/extraction-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Concept = { id: string; concept_key: string; label: string; status: string };
type Alias = {
  id: string; benefit_id: string; benefit_label: string; phrase: string; normalized_phrase: string;
  scope: string; company_id?: string | null; company_name?: string | null;
  product_id?: string | null; product_name?: string | null;
  package_id?: string | null; package_name?: string | null; status: string;
};
type Company = { id: string; name: string };
type Product = { id: string; name: string };
type PackageSummary = { id: string; name: string; package_kind: string };
type Catalog = { id: string; package?: PackageSummary | null };

const SCOPE_LABELS: Record<string, string> = {
  global: "Global",
  company: "Company",
  product: "Product",
  package: "Package",
};

function EmptyPanel({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="grid min-h-56 place-items-center border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface)] p-8 text-center">
      <div className="max-w-sm">
        <p className="font-semibold text-[var(--rl-text-strong)]">{title}</p>
        <p className="mt-1 text-[13px] text-[var(--rl-text-muted)]">{detail}</p>
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
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const mountedRef = useRef(true);

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
    return () => { cancelled = true; mountedRef.current = false; };
    // Initial hydration only; selection changes call loadAliases explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    return term ? concepts.filter((item) => item.label.toLowerCase().includes(term) || item.concept_key.toLowerCase().includes(term)) : concepts;
  }, [concepts, search]);

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
      await loadAliases(selectedBenefitId);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function removeAlias(aliasId: string) {
    setError("");
    try {
      await api(`/business/benefit-aliases/${aliasId}`, { method: "DELETE" });
      setAliases((items) => items.filter((item) => item.id !== aliasId));
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  function scopeTargetName(alias: Alias): string {
    if (alias.scope === "company") return alias.company_name || "Company";
    if (alias.scope === "product") return alias.product_name || "Product";
    if (alias.scope === "package") return alias.package_name || "Package";
    return "All insurers";
  }

  if (loading) {
    return <AppShell><PageLoading /></AppShell>;
  }

  return (
    <AppShell>
      <section className="grid gap-5">
        <header>
          <h1 className="m-0 text-[30px] font-bold text-[var(--rl-text-strong)]">Benefit Aliases</h1>
          <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">Insurer wording that maps to a Global Benefit. Fully synced with the Global Benefits library — the same aliases apply everywhere.</p>
        </header>
        <ExtractionNav />

        {error ? (
          <div role="alert" className="border-l-4 border-[var(--rl-red)] bg-[var(--rl-red-light)] px-4 py-3 text-[13px] font-medium text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        <div className="min-h-[560px] overflow-hidden border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-card xl:grid xl:grid-cols-[300px_minmax(380px,1fr)]">
          <aside className="border-b border-[var(--rl-border)] bg-[#fafafa] xl:border-b-0 xl:border-r" aria-label="Global benefits">
            <div className="border-b border-[var(--rl-border)] p-3">
              <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--rl-text-muted)]">Benefits</span>
              <label className="relative mt-3 block">
                <MagnifyingGlass size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
                <Input aria-label="Search benefits" className="h-9 pl-8 text-[12px]" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search" />
              </label>
            </div>
            <div className="max-h-[480px] overflow-y-auto p-2">
              {filteredConcepts.map((concept) => {
                const active = concept.id === selectedBenefitId;
                return (
                  <button key={concept.id} type="button" onClick={() => selectBenefit(concept.id)} className={`mb-1 grid w-full grid-cols-[30px_1fr] items-center gap-2 border-l-2 px-2 py-2 text-left ${active ? "border-[var(--rl-red)] bg-white" : "border-transparent hover:bg-white"}`}>
                    <ShieldCheck size={14} className={active ? "text-[var(--rl-red)]" : "text-[var(--rl-text-muted)]"} />
                    <span className="min-w-0">
                      <span className="block truncate text-[13px] font-semibold text-[var(--rl-text-strong)]">{concept.label}</span>
                      <span className="block truncate font-mono text-[10px] text-[var(--rl-text-muted)]">{concept.concept_key}</span>
                    </span>
                  </button>
                );
              })}
              {!filteredConcepts.length ? <p className="p-3 text-[12px] text-[var(--rl-text-muted)]">No benefits match.</p> : null}
            </div>
          </aside>

          <main className="min-w-0 p-5">
            {selectedBenefit ? (
              <div className="grid gap-4">
                <div>
                  <h2 className="text-[20px] font-bold text-[var(--rl-text-strong)]">Aliases · {selectedBenefit.label}</h2>
                  <p className="mt-0.5 text-[12px] text-[var(--rl-text-muted)]">Global aliases apply everywhere; company/product/package aliases only in their scope. The most specific scope wins during extraction.</p>
                </div>

                <form className="grid gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-3" onSubmit={(event) => { event.preventDefault(); addAlias(); }}>
                  <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                    <Select aria-label="Alias scope" value={scope} onChange={(event) => { setScope(event.target.value); resetScope(); }}>
                      <option value="global">Global — all insurers</option>
                      <option value="company">Company</option>
                      <option value="product">Product</option>
                      <option value="package">Package</option>
                    </Select>
                    <Input aria-label="Alias phrase" value={phrase} onChange={(event) => setPhrase(event.target.value)} placeholder="e.g. 24/7 Towing Assistance" />
                    <Button size="sm" type="submit" loading={saving} disabled={!phrase.trim()}>Add alias</Button>
                  </div>
                  {scope === "company" ? (
                    <Select aria-label="Company" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
                      <option value="">Choose the insurance company</option>
                      {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
                    </Select>
                  ) : null}
                  {scope === "product" ? (
                    <div className="grid gap-2 sm:grid-cols-2">
                      <Select aria-label="Company" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
                        <option value="">Choose the insurance company</option>
                        {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
                      </Select>
                      <Select aria-label="Product" value={productId} onChange={(event) => setProductId(event.target.value)} disabled={!companyId}>
                        <option value="">Choose the product</option>
                        {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
                      </Select>
                    </div>
                  ) : null}
                  {scope === "package" ? (
                    <div className="grid gap-2 sm:grid-cols-3">
                      <Select aria-label="Company" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
                        <option value="">Choose the insurance company</option>
                        {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
                      </Select>
                      <Select aria-label="Product" value={productId} onChange={(event) => setProductId(event.target.value)} disabled={!companyId}>
                        <option value="">Choose the product</option>
                        {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
                      </Select>
                      <Select aria-label="Package" value={packageId} onChange={(event) => setPackageId(event.target.value)} disabled={!productId}>
                        <option value="">Choose the package</option>
                        {packages.map((item) => <option key={item.id} value={item.id}>{item.name}{item.package_kind === "addon_bundle" ? " (bundle)" : ""}</option>)}
                      </Select>
                    </div>
                  ) : null}
                </form>

                {aliases.length ? aliases.map((alias) => (
                  <div key={alias.id} className="flex items-center justify-between gap-3 border border-[var(--rl-border)] px-3 py-2">
                    <div className="min-w-0">
                      <span className="block truncate text-[12px] font-semibold text-[var(--rl-text-strong)]">{alias.phrase}</span>
                      <span className="block text-[11px] text-[var(--rl-text-muted)]">
                        → {alias.benefit_label} · <span className="font-semibold">{SCOPE_LABELS[alias.scope] || alias.scope}</span> · {scopeTargetName(alias)}
                      </span>
                    </div>
                    <button type="button" aria-label={`Remove alias ${alias.phrase}`} onClick={() => removeAlias(alias.id)} className="rounded-full p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)]">
                      <X size={14} weight="bold" />
                    </button>
                  </div>
                )) : (
                  <EmptyPanel title="No aliases for this benefit" detail="Add insurer wording that should resolve to this benefit during extraction." />
                )}
              </div>
            ) : (
              <EmptyPanel title="Choose a benefit" detail="Pick a Global Benefit from the library to manage its aliases." />
            )}
          </main>
        </div>
      </section>
    </AppShell>
  );
}
