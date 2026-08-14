"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  ArrowClockwise,
  Buildings,
  CaretRight,
  ImageSquare,
  MagnifyingGlass,
  Plus,
  ShieldCheck,
  TreeStructure,
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

type Asset = { id: string; label: string; asset_kind: string; status: string; url: string };
type Company = { id: string; name: string; slug?: string | null; revision: number; status: string; logo?: Asset | null };
type Product = { id: string; company_id: string; product_key: string; name: string; channel?: string | null; revision: number; status: string };
type Tier = { id: string; product_id: string; tier_key: string; name: string; revision: number; status: string };
type CatalogRevision = { id: string; revision_number: number; state: string; content_hash: string };
type Catalog = { id: string; company_id: string; product_id?: string | null; tier_id?: string | null; name: string; revision: number; status: string; revisions: CatalogRevision[] };
type Concept = {
  id: string;
  concept_key: string;
  label: string;
  value_schema: { type?: string };
  display_template: string;
  required_variables: string[];
  default_asset?: Asset | null;
};
type Offering = {
  id: string;
  offering_key: string;
  concept_id: string;
  offering_kind: "base" | "upgrade" | "optional" | "package_component";
  label_override?: string | null;
  typed_value?: Record<string, unknown> | null;
  source_document_id?: string | null;
  source_citation: Record<string, unknown>;
  sort_order: number;
  status: string;
  concept?: Concept | null;
};
type CompanyWorkspace = { company: Company; products: Product[]; tiers: Tier[]; catalogs: Catalog[] };
type CatalogWorkspace = {
  catalog: Catalog;
  active_revision: CatalogRevision;
  offerings: Offering[];
  relations: Array<{ id: string; from_offering_id: string; to_offering_id: string; relation_kind: string; branch_key?: string | null }>;
  packages: Array<{ id: string; name: string; package_key: string; status: string }>;
  plans: Array<{ id: string; package_id: string; name: string }>;
};
type Source = { id: string; title: string; issuer: string; verification_status: string };

const workspaceTabs = [
  { id: "base", label: "Base benefits" },
  { id: "addons", label: "Add-ons" },
  { id: "packages", label: "Packages" },
  { id: "variations", label: "Variations" },
] as const;
type WorkspaceTab = (typeof workspaceTabs)[number]["id"];

function formatValue(value?: Record<string, unknown> | null) {
  if (!value) return "Value not set";
  if (value.type === "distance") return value.unlimited ? `Unlimited${value.region ? ` · ${value.region}` : ""}` : `${Number(value.value).toLocaleString()} ${String(value.unit || "km")}`;
  if (value.type === "money") return `${String(value.currency || "MYR") === "MYR" ? "RM" : String(value.currency)} ${Number(value.value).toLocaleString()}`;
  if (value.type === "per_day") return `RM ${Number(value.value).toLocaleString()} / day · ${String(value.max_days)} days`;
  if (value.type === "custom") return String(value.display_text || "Custom value");
  if (value.value !== undefined) return `${String(value.value)}${value.unit ? ` ${String(value.unit)}` : ""}`;
  return String(value.type || "Value not set");
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

export default function BenefitsPage() {
  const params = useSearchParams();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyWorkspace, setCompanyWorkspace] = useState<CompanyWorkspace | null>(null);
  const [catalogWorkspace, setCatalogWorkspace] = useState<CatalogWorkspace | null>(null);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState(params.get("company") || "");
  const [selectedProductId, setSelectedProductId] = useState(params.get("product") || "");
  const [selectedTierId, setSelectedTierId] = useState(params.get("tier") || "");
  const [selectedCatalogId, setSelectedCatalogId] = useState(params.get("catalog") || "");
  const [selectedOfferingId, setSelectedOfferingId] = useState("");
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("base");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<"company" | "product" | "tier" | "catalog" | "concept" | "offering" | null>(null);
  const [saving, setSaving] = useState(false);
  const [formName, setFormName] = useState("");
  const [formKey, setFormKey] = useState("");
  const [formType, setFormType] = useState("distance");
  const [formConceptId, setFormConceptId] = useState("");
  const [formAssetId, setFormAssetId] = useState("");
  const [formValue, setFormValue] = useState("");
  const [formUnit, setFormUnit] = useState("km");
  const [formUnlimited, setFormUnlimited] = useState(false);
  const [formSourceId, setFormSourceId] = useState("");
  const [formCitation, setFormCitation] = useState("");
  const [publishing, setPublishing] = useState(false);
  const mountedRef = useRef(true);

  const syncUrl = useCallback((company: string, product = "", tier = "", catalog = "") => {
    const next = new URLSearchParams();
    if (company) next.set("company", company);
    if (product) next.set("product", product);
    if (tier) next.set("tier", tier);
    if (catalog) next.set("catalog", catalog);
    window.history.replaceState(null, "", `/builder/benefits${next.size ? `?${next}` : ""}`);
  }, []);

  const loadReferenceData = useCallback(async () => {
    const [companyResult, conceptResult, assetResult, sourceResult] = await Promise.all([
      api<{ companies: { items: Company[] } }>("/business/companies?page=1&page_size=100"),
      api<{ benefit_concepts: { items: Concept[] } }>("/business/benefit-concepts?page=1&page_size=100"),
      api<{ assets: { items: Asset[] } }>("/business/assets?kind=benefit_art&page=1&page_size=100"),
      api<{ sources: { items: Source[] } }>("/business/sources?page=1&page_size=100"),
    ]);
    setCompanies(companyResult.companies.items);
    setConcepts(conceptResult.benefit_concepts.items);
    setAssets(assetResult.assets.items);
    setSources(sourceResult.sources.items);
    return companyResult.companies.items;
  }, []);

  const loadCompany = useCallback(async (companyId: string, preferredProduct = selectedProductId, preferredTier = selectedTierId, preferredCatalog = selectedCatalogId) => {
    if (!companyId) return;
    setWorkspaceLoading(true);
    setError("");
    try {
      const result = await api<{ workspace: CompanyWorkspace }>(`/business/companies/${companyId}/workspace`);
      if (!mountedRef.current) return;
      setCompanyWorkspace(result.workspace);
      const product = result.workspace.products.find((item) => item.id === preferredProduct) || result.workspace.products[0];
      const tier = result.workspace.tiers.find((item) => item.id === preferredTier && (!product || item.product_id === product.id));
      const relevantCatalogs = result.workspace.catalogs.filter((item) => !product || !item.product_id || item.product_id === product.id);
      const catalog = relevantCatalogs.find((item) => item.id === preferredCatalog) || relevantCatalogs.find((item) => !tier || !item.tier_id || item.tier_id === tier.id) || relevantCatalogs[0];
      setSelectedCompanyId(companyId);
      setSelectedProductId(product?.id || "");
      setSelectedTierId(tier?.id || "");
      setSelectedCatalogId(catalog?.id || "");
      syncUrl(companyId, product?.id || "", tier?.id || "", catalog?.id || "");
      if (catalog) {
        const catalogResult = await api<{ workspace: CatalogWorkspace }>(`/business/catalogs/${catalog.id}/workspace`);
        if (!mountedRef.current) return;
        setCatalogWorkspace(catalogResult.workspace);
      } else {
        setCatalogWorkspace(null);
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setWorkspaceLoading(false);
    }
  }, [selectedCatalogId, selectedProductId, selectedTierId, syncUrl]);

  async function publishCatalog() {
    if (!catalogWorkspace) return;
    setPublishing(true);
    setError("");
    try {
      await api(`/business/catalogs/${catalogWorkspace.catalog.id}/publish`, {
        method: "POST",
        body: JSON.stringify({ base_revision: catalogWorkspace.catalog.revision }),
      });
      const result = await api<{ workspace: CatalogWorkspace }>(`/business/catalogs/${catalogWorkspace.catalog.id}/workspace`);
      if (!mountedRef.current) return;
      setCatalogWorkspace(result.workspace);
      await loadCompany(selectedCompanyId);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setPublishing(false);
    }
  }

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;
    loadReferenceData()
      .then((items) => {
        if (cancelled) return;
        const companyId = selectedCompanyId && items.some((item) => item.id === selectedCompanyId) ? selectedCompanyId : items[0]?.id || "";
        if (companyId) return loadCompany(companyId);
      })
      .catch((err) => !cancelled && setError(apiErrorMessage(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; mountedRef.current = false; };
    // Initial hydration only; selections are handled explicitly below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredCompanies = useMemo(() => {
    const term = search.trim().toLowerCase();
    return term ? companies.filter((item) => item.name.toLowerCase().includes(term)) : companies;
  }, [companies, search]);

  const productTiers = useMemo(
    () => companyWorkspace?.tiers.filter((item) => item.product_id === selectedProductId) || [],
    [companyWorkspace, selectedProductId],
  );
  const visibleOfferings = useMemo(() => {
    const items = catalogWorkspace?.offerings || [];
    if (activeTab === "base") return items.filter((item) => item.offering_kind === "base");
    if (activeTab === "addons") return items.filter((item) => item.offering_kind === "upgrade" || item.offering_kind === "optional");
    return [];
  }, [activeTab, catalogWorkspace]);
  const selectedOffering = catalogWorkspace?.offerings.find((item) => item.id === selectedOfferingId) || null;
  const selectedCompany = companies.find((item) => item.id === selectedCompanyId);
  const selectedProduct = companyWorkspace?.products.find((item) => item.id === selectedProductId);
  const selectedTier = productTiers.find((item) => item.id === selectedTierId);

  function resetForm() {
    setFormName(""); setFormKey(""); setFormType("distance"); setFormConceptId(""); setFormAssetId("");
    setFormValue(""); setFormUnit("km"); setFormUnlimited(false); setFormSourceId(""); setFormCitation("");
  }

  function openDialog(next: typeof dialog) {
    resetForm();
    if (next === "offering") setFormConceptId(concepts[0]?.id || "");
    setDialog(next);
  }

  async function refreshCurrentCompany() {
    await loadReferenceData();
    if (selectedCompanyId) await loadCompany(selectedCompanyId, selectedProductId, selectedTierId, selectedCatalogId);
  }

  function typedValue() {
    const concept = concepts.find((item) => item.id === formConceptId);
    const type = concept?.value_schema?.type || formType;
    if (type === "distance") return { type, value: formUnlimited ? null : formValue, unit: formUnit || "km", unlimited: formUnlimited };
    if (type === "money") return { type, value: formValue, currency: "MYR", semantic_role: "limit" };
    if (type === "per_day") return { type, value: formValue, currency: "MYR", max_days: Math.max(1, Number(formUnit) || 1) };
    if (type === "custom") return { type, display_text: formValue };
    return { type: "custom", display_text: formValue };
  }

  async function submitDialog() {
    setSaving(true);
    setError("");
    try {
      if (dialog === "company") {
        await api("/business/companies", { method: "POST", body: JSON.stringify({ name: formName }) });
      } else if (dialog === "product") {
        await api("/business/products", { method: "POST", body: JSON.stringify({ company_id: selectedCompanyId, name: formName, product_key: formKey || undefined }) });
      } else if (dialog === "tier") {
        await api("/business/tiers", { method: "POST", body: JSON.stringify({ product_id: selectedProductId, name: formName, tier_key: formKey || undefined }) });
      } else if (dialog === "catalog") {
        await api("/business/catalogs", { method: "POST", body: JSON.stringify({ company_id: selectedCompanyId, product_id: selectedProductId || null, tier_id: selectedTierId || null, name: formName }) });
      } else if (dialog === "concept") {
        const required = formType === "distance" ? ["value", "unit"] : formType === "money" ? ["value", "currency", "semantic_role"] : [];
        await api("/business/benefit-concepts", { method: "POST", body: JSON.stringify({
          concept_key: formKey || formName,
          label: formName,
          value_schema: { type: formType },
          display_template: formType === "distance" ? "{value} {unit}" : "{label}",
          required_variables: required,
          default_asset_id: formAssetId || null,
        }) });
      } else if (dialog === "offering" && catalogWorkspace) {
        await api(`/business/catalogs/${catalogWorkspace.catalog.id}/offerings`, { method: "POST", body: JSON.stringify({
          base_revision: catalogWorkspace.catalog.revision,
          offering_key: formKey || `${concepts.find((item) => item.id === formConceptId)?.concept_key || "benefit"}-${Date.now()}`,
          concept_id: formConceptId,
          offering_kind: activeTab === "base" ? "base" : "optional",
          typed_value: typedValue(),
          source_document_id: formSourceId || null,
          source_citation: formCitation ? { reference: formCitation } : {},
          sort_order: catalogWorkspace.offerings.length,
        }) });
      }
      setDialog(null);
      await refreshCurrentCompany();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <AppShell><PageLoading /></AppShell>;
  }

  return (
    <AppShell>
      <section className="grid gap-5">
        <header>
          <h1 className="m-0 text-[30px] font-bold text-[var(--rl-text-strong)]">Benefits</h1>
          <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">Build verified company catalogs. Artwork stays separate until you assign it to a benefit concept.</p>
        </header>
        <BuilderNav />

        {error ? (
          <div role="alert" className="flex items-center justify-between gap-3 border-l-4 border-[var(--rl-red)] bg-[var(--rl-red-light)] px-4 py-3 text-[13px] font-medium text-[var(--rl-red)]">
            <span>{error}</span>
            <Button variant="ghost" size="sm" icon={<ArrowClockwise size={14} />} onClick={refreshCurrentCompany}>Retry</Button>
          </div>
        ) : null}

        <div className="min-h-[680px] overflow-hidden border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-card xl:grid xl:grid-cols-[230px_230px_minmax(380px,1fr)_280px]">
          <aside className="border-b border-[var(--rl-border)] bg-[#fafafa] xl:border-b-0 xl:border-r" aria-label="Companies">
            <div className="border-b border-[var(--rl-border)] p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--rl-text-muted)]">Companies</span>
                <button type="button" onClick={() => openDialog("company")} className="grid h-7 w-7 place-items-center border border-[var(--rl-border)] bg-white text-[var(--rl-text-strong)] hover:border-[var(--rl-black)]" aria-label="Add company"><Plus size={14} weight="bold" /></button>
              </div>
              <label className="relative mt-3 block">
                <MagnifyingGlass size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
                <Input aria-label="Search companies" className="h-9 pl-8 text-[12px]" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search" />
              </label>
            </div>
            <div className="max-h-[610px] overflow-y-auto p-2">
              {filteredCompanies.map((company) => {
                const active = company.id === selectedCompanyId;
                return (
                  <button key={company.id} type="button" onClick={() => loadCompany(company.id, "", "", "")} className={`mb-1 grid w-full grid-cols-[34px_1fr] items-center gap-2 border-l-2 px-2 py-2.5 text-left ${active ? "border-[var(--rl-red)] bg-white" : "border-transparent hover:bg-white"}`}>
                    <span className="grid h-8 w-8 place-items-center border border-[var(--rl-border)] bg-white">
                      {company.logo ? <img src={fileUrl(company.logo.url)} alt="" className="max-h-6 max-w-6 object-contain" /> : <Buildings size={16} className="text-[var(--rl-text-muted)]" />}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-[13px] font-semibold text-[var(--rl-text-strong)]">{company.name}</span>
                      <span className="block text-[11px] text-[var(--rl-text-muted)]">{company.status === "active" ? "Active" : company.status}</span>
                    </span>
                  </button>
                );
              })}
              {!filteredCompanies.length ? <p className="p-3 text-[12px] text-[var(--rl-text-muted)]">No companies match.</p> : null}
            </div>
          </aside>

          <aside className="border-b border-[var(--rl-border)] xl:border-b-0 xl:border-r" aria-label="Product and tier structure">
            <div className="flex items-center justify-between border-b border-[var(--rl-border)] p-3">
              <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--rl-text-muted)]">Products &amp; tiers</span>
              <button type="button" disabled={!selectedCompanyId} onClick={() => openDialog("product")} className="grid h-7 w-7 place-items-center border border-[var(--rl-border)] disabled:opacity-40" aria-label="Add product"><Plus size={14} weight="bold" /></button>
            </div>
            <div className="p-2">
              {(companyWorkspace?.products || []).map((product) => {
                const active = product.id === selectedProductId;
                const tiers = companyWorkspace?.tiers.filter((tier) => tier.product_id === product.id) || [];
                return (
                  <div key={product.id} className="mb-2">
                    <button type="button" onClick={() => { setSelectedProductId(product.id); const tier = tiers[0]; setSelectedTierId(tier?.id || ""); syncUrl(selectedCompanyId, product.id, tier?.id || "", ""); }} className={`flex w-full items-center gap-2 px-2 py-2 text-left text-[13px] font-semibold ${active ? "bg-[var(--rl-black)] text-white" : "text-[var(--rl-text-strong)] hover:bg-[var(--rl-bg)]"}`}>
                      <CaretRight size={12} weight="bold" className={active ? "rotate-90" : ""} />
                      <span className="truncate">{product.name}</span>
                    </button>
                    {active ? (
                      <div className="ml-3 border-l border-[var(--rl-border)] py-1 pl-2">
                        {tiers.map((tier) => (
                          <button key={tier.id} type="button" onClick={() => { setSelectedTierId(tier.id); syncUrl(selectedCompanyId, product.id, tier.id, selectedCatalogId); }} className={`block w-full px-2 py-1.5 text-left text-[12px] ${tier.id === selectedTierId ? "font-semibold text-[var(--rl-red)]" : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"}`}>{tier.name}</button>
                        ))}
                        <button type="button" onClick={() => openDialog("tier")} className="mt-1 flex items-center gap-1 px-2 py-1 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"><Plus size={11} /> Add tier</button>
                      </div>
                    ) : null}
                  </div>
                );
              })}
              {!companyWorkspace?.products.length ? <EmptyPanel title="No products" detail="Add the first product or channel for this company." action={<Button size="sm" onClick={() => openDialog("product")}>Add product</Button>} /> : null}
            </div>
            <div className="border-t border-[var(--rl-border)] p-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--rl-text-muted)]">Catalog</span>
                <button type="button" onClick={() => openDialog("catalog")} disabled={!selectedCompanyId} className="grid h-7 w-7 place-items-center border border-[var(--rl-border)] disabled:opacity-40" aria-label="Add catalog"><Plus size={14} weight="bold" /></button>
              </div>
              <Select className="mt-2 w-full text-[12px]" value={selectedCatalogId} onChange={(event) => loadCompany(selectedCompanyId, selectedProductId, selectedTierId, event.target.value)}>
                <option value="">No catalog selected</option>
                {(companyWorkspace?.catalogs || []).map((catalog) => <option key={catalog.id} value={catalog.id}>{catalog.name} · {catalog.status}</option>)}
              </Select>
            </div>
          </aside>

          <main className="min-w-0 border-b border-[var(--rl-border)] xl:border-b-0 xl:border-r">
            <div className="border-b border-[var(--rl-border)] px-5 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-[11px] text-[var(--rl-text-muted)]">
                    <span>{selectedCompany?.name || "Company"}</span><CaretRight size={10} /><span>{selectedProduct?.name || "No product"}</span>{selectedTier ? <><CaretRight size={10} /><span>{selectedTier.name}</span></> : null}
                  </div>
                  <h2 className="mt-1 text-[20px] font-bold text-[var(--rl-text-strong)]">{catalogWorkspace?.catalog.name || "Catalog workspace"}</h2>
                  {catalogWorkspace ? <p className="mt-0.5 text-[12px] text-[var(--rl-text-muted)]">Draft revision {catalogWorkspace.active_revision.revision_number} · {catalogWorkspace.offerings.length} offering{catalogWorkspace.offerings.length === 1 ? "" : "s"}</p> : null}
                </div>
                {catalogWorkspace ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <Button size="sm" icon={<Plus size={14} />} onClick={() => openDialog("offering")} disabled={activeTab === "packages" || activeTab === "variations"}>Add {activeTab === "base" ? "base benefit" : "add-on"}</Button>
                    <Button size="sm" variant="secondary" loading={publishing} disabled={!catalogWorkspace.offerings.length} onClick={publishCatalog}>Publish</Button>
                  </div>
                ) : null}
              </div>
              <div className="mt-4 flex gap-5 overflow-x-auto">
                {workspaceTabs.map((tab) => <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} className={`border-b-2 pb-2 text-[12px] font-semibold ${activeTab === tab.id ? "border-[var(--rl-red)] text-[var(--rl-text-strong)]" : "border-transparent text-[var(--rl-text-muted)]"}`}>{tab.label}</button>)}
              </div>
            </div>
            <div className="p-5">
              {workspaceLoading ? <PageLoading /> : !catalogWorkspace ? (
                <EmptyPanel title="No catalog selected" detail="Create a draft catalog for this company, product, or tier. Missing information remains empty until reviewed." action={<Button size="sm" onClick={() => openDialog("catalog")}>Create catalog</Button>} />
              ) : activeTab === "packages" ? (
                catalogWorkspace.packages.length ? <div className="grid gap-3 sm:grid-cols-2">{catalogWorkspace.packages.map((item) => <button key={item.id} type="button" className="border border-[var(--rl-border)] p-4 text-left hover:border-[var(--rl-black)]"><span className="block font-semibold text-[var(--rl-text-strong)]">{item.name}</span><span className="mt-1 block text-[12px] text-[var(--rl-text-muted)]">{catalogWorkspace.plans.filter((plan) => plan.package_id === item.id).length} plans · {item.status}</span></button>)}</div> : <EmptyPanel title="No packages" detail="Packages group reviewed offerings into explicit plans. Nothing is inferred from benefit values." />
              ) : activeTab === "variations" ? (
                catalogWorkspace.relations.length ? <div className="grid gap-2">{catalogWorkspace.relations.map((relation) => { const from = catalogWorkspace.offerings.find((item) => item.id === relation.from_offering_id); const to = catalogWorkspace.offerings.find((item) => item.id === relation.to_offering_id); return <div key={relation.id} className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 border border-[var(--rl-border)] p-3 text-[12px]"><span className="font-semibold text-[var(--rl-text-strong)]">{from?.concept?.label} · {formatValue(from?.typed_value)}</span><span className="text-[var(--rl-red)]">→</span><span className="font-semibold text-[var(--rl-text-strong)]">{to?.concept?.label} · {formatValue(to?.typed_value)}</span></div>; })}</div> : <EmptyPanel title="No upgrade paths" detail="Create explicit replacement or alternative edges. Numeric size never decides the next add-on." />
              ) : visibleOfferings.length ? (
                <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
                  {visibleOfferings.map((offering) => {
                    const selected = offering.id === selectedOfferingId;
                    return (
                      <button key={offering.id} type="button" onClick={() => setSelectedOfferingId(offering.id)} className={`grid min-h-36 grid-rows-[56px_auto] border p-3 text-left ${selected ? "border-[var(--rl-red)] shadow-card" : "border-[var(--rl-border)] hover:border-[var(--rl-border-strong)]"}`}>
                        <span className="grid h-14 w-14 place-items-center border border-[var(--rl-border)] bg-[var(--rl-bg)]">
                          {offering.concept?.default_asset ? <img src={fileUrl(offering.concept.default_asset.url)} alt="" className="max-h-12 max-w-12 object-contain" /> : <ShieldCheck size={24} className="text-[var(--rl-text-muted)]" />}
                        </span>
                        <span className="mt-3 min-w-0">
                          <span className="block truncate text-[13px] font-bold text-[var(--rl-text-strong)]">{offering.label_override || offering.concept?.label || offering.offering_key}</span>
                          <span className="mt-1 block text-[15px] font-semibold text-[var(--rl-red)]">{formatValue(offering.typed_value)}</span>
                          <span className="mt-2 block text-[10px] uppercase tracking-[0.08em] text-[var(--rl-text-muted)]">{offering.offering_kind.replace("_", " ")} · {offering.source_document_id ? "source linked" : "needs source"}</span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <EmptyPanel title={activeTab === "base" ? "No base benefits" : "No add-ons"} detail={activeTab === "base" ? "Add only verified benefits included by this catalog revision." : "Add explicit upgrades or genuinely new optional concepts."} action={<Button size="sm" onClick={() => openDialog("offering")}>Add first item</Button>} />
              )}
            </div>
          </main>

          <aside className="bg-[#fafafa]" aria-label="Inspector">
            <div className="border-b border-[var(--rl-border)] p-3"><span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--rl-text-muted)]">Inspector</span></div>
            {selectedOffering ? (
              <div className="grid gap-5 p-4 text-[12px]">
                <div><span className="text-[10px] uppercase tracking-[0.1em] text-[var(--rl-text-muted)]">Benefit</span><p className="mt-1 text-[16px] font-bold text-[var(--rl-text-strong)]">{selectedOffering.concept?.label}</p></div>
                <dl className="grid gap-3">
                  <div><dt className="text-[var(--rl-text-muted)]">Value</dt><dd className="mt-0.5 font-semibold text-[var(--rl-text-strong)]">{formatValue(selectedOffering.typed_value)}</dd></div>
                  <div><dt className="text-[var(--rl-text-muted)]">Offering key</dt><dd className="mt-0.5 break-all font-mono text-[11px] text-[var(--rl-text-strong)]">{selectedOffering.offering_key}</dd></div>
                  <div><dt className="text-[var(--rl-text-muted)]">Source</dt><dd className="mt-0.5 text-[var(--rl-text-strong)]">{sources.find((item) => item.id === selectedOffering.source_document_id)?.title || "Not linked"}</dd></div>
                  <div><dt className="text-[var(--rl-text-muted)]">Publication</dt><dd className={`mt-0.5 font-semibold ${selectedOffering.source_document_id ? "text-[var(--rl-warning)]" : "text-[var(--rl-red)]"}`}>{selectedOffering.source_document_id ? "Draft evidence linked" : "Blocked until sourced"}</dd></div>
                </dl>
              </div>
            ) : (
              <div className="p-5 text-center">
                <TreeStructure size={28} className="mx-auto text-[var(--rl-text-muted)]" />
                <p className="mt-3 font-semibold text-[var(--rl-text-strong)]">Select an item</p>
                <p className="mt-1 text-[12px] text-[var(--rl-text-muted)]">Its typed variables, source, presentation asset, and upgrade relationships appear here.</p>
                <Button variant="secondary" size="sm" className="mt-4" icon={<ImageSquare size={14} />} onClick={() => openDialog("concept")}>New benefit concept</Button>
              </div>
            )}
          </aside>
        </div>
      </section>

      <Dialog open={dialog !== null} onOpenChange={(open) => { if (!open) setDialog(null); }} title={{ company: "Add company", product: "Add product", tier: "Add tier", catalog: "Create draft catalog", concept: "New benefit concept", offering: activeTab === "base" ? "Add base benefit" : "Add add-on" }[dialog || "company"]} description={dialog === "concept" ? "A concept is reusable. Company-specific values belong in offerings." : undefined} onConfirm={submitDialog} confirmLabel="Save" loading={saving}>
        <div className="grid gap-3">
          {dialog !== "offering" ? <label className="grid gap-1"><span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Name</span><Input value={formName} onChange={(event) => setFormName(event.target.value)} autoFocus /></label> : null}
          {dialog === "product" || dialog === "tier" || dialog === "concept" ? <label className="grid gap-1"><span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Stable key <span className="font-normal text-[var(--rl-text-muted)]">(optional)</span></span><Input value={formKey} onChange={(event) => setFormKey(event.target.value)} placeholder="Generated from name" /></label> : null}
          {dialog === "concept" ? <><label className="grid gap-1"><span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Value type</span><Select value={formType} onChange={(event) => setFormType(event.target.value)}><option value="distance">Distance</option><option value="money">Money / insured limit</option><option value="per_day">Per-day allowance</option><option value="custom">Reviewed custom text</option></Select></label><label className="grid gap-1"><span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Artwork <span className="font-normal text-[var(--rl-text-muted)]">(optional)</span></span><Select value={formAssetId} onChange={(event) => setFormAssetId(event.target.value)}><option value="">No artwork</option>{assets.map((asset) => <option key={asset.id} value={asset.id}>{asset.label}</option>)}</Select></label></> : null}
          {dialog === "offering" ? <><label className="grid gap-1"><span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Benefit concept</span><Select value={formConceptId} onChange={(event) => setFormConceptId(event.target.value)}><option value="">Select concept</option>{concepts.map((concept) => <option key={concept.id} value={concept.id}>{concept.label} · {concept.value_schema.type || "custom"}</option>)}</Select></label><label className="grid gap-1"><span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Value</span><Input value={formValue} onChange={(event) => setFormValue(event.target.value)} disabled={formUnlimited} placeholder="Exact quotation/catalog value" /></label>{concepts.find((item) => item.id === formConceptId)?.value_schema.type === "distance" ? <><label className="grid gap-1"><span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Unit</span><Input value={formUnit} onChange={(event) => setFormUnit(event.target.value)} /></label><label className="flex items-center gap-2 text-[12px]"><input type="checkbox" checked={formUnlimited} onChange={(event) => setFormUnlimited(event.target.checked)} /> Unlimited</label></> : null}<label className="grid gap-1"><span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Source document</span><Select value={formSourceId} onChange={(event) => setFormSourceId(event.target.value)}><option value="">Not linked — cannot publish</option>{sources.map((source) => <option key={source.id} value={source.id}>{source.title} · {source.verification_status}</option>)}</Select></label><label className="grid gap-1"><span className="text-[12px] font-semibold text-[var(--rl-text-strong)]">Citation / page</span><Input value={formCitation} onChange={(event) => setFormCitation(event.target.value)} placeholder="e.g. page 14, Optional Benefits" /></label></> : null}
        </div>
      </Dialog>
    </AppShell>
  );
}
