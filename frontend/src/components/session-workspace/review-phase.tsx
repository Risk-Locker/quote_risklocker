"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  CaretLeft,
  Eye,
  FloppyDisk,
  Plus,
  X,
} from "@phosphor-icons/react";
import { SessionPhaseBar } from "@/components/session-phase-bar";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { Select } from "@/components/ui/select";
import {
  useWorkspaceActions,
  useWorkspaceData,
  useWorkspaceMutation,
} from "@/components/session-workspace/provider";
import type { BenefitCardSummary, WorkspaceField } from "@/components/session-workspace/types";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type FieldKind = "text" | "date" | "percent" | "money" | "total";

type FormField = { name: string; label: string; kind: FieldKind };

const FORM_FIELDS: FormField[] = [
  { name: "insurance_company", label: "Insurer", kind: "text" },
  { name: "customer_name", label: "Insured name", kind: "text" },
  { name: "issue_date", label: "Issued date", kind: "date" },
  { name: "valid_until", label: "Valid until", kind: "date" },
  { name: "vehicle_no", label: "Car plate no.", kind: "text" },
  { name: "vehicle_class", label: "Vehicle class", kind: "text" },
  { name: "coverage_type", label: "Coverage type", kind: "text" },
  { name: "cover_period", label: "Cover period", kind: "text" },
  { name: "car_model", label: "Car model", kind: "text" },
  { name: "ncd_percent", label: "NCD", kind: "percent" },
  { name: "coverage_amount", label: "Coverage", kind: "money" },
  { name: "premium", label: "Insurance premium", kind: "money" },
  { name: "roadtax", label: "Road tax", kind: "money" },
  { name: "service_fee", label: "Runner fee", kind: "money" },
  { name: "total_amount", label: "Total premium", kind: "total" },
];

type CompanyOption = { id: string; name: string };
type CompanyWorkspace = {
  company: { id: string; name: string };
  products: Array<{ id: string; name: string }>;
  tiers: Array<{ id: string; product_id: string; name: string }>;
};

type PublishedTemplateOption = {
  template_id: string;
  template_revision_id: string;
  name: string;
  revision_number: number;
  config_hash: string;
  page_profile: { name: string; width: number; height: number; unit: string };
};

type TemplateSelectionImpact = {
  current_template_revision_id: string | null;
  target: { template_id: string; template_revision_id: string; revision_number: number; name: string; config_hash: string };
  will_reset_layout_override: boolean;
  requires_confirmation: boolean;
  messages: string[];
};

const LEARNABLE = new Map<string, string>([
  ["car_model", "car_model"],
  ["car_brand", "car_brand"],
]);

function formatMoney(raw: string | null | undefined): string {
  const number = Number(String(raw ?? "").replace(/[^0-9.-]/g, ""));
  if (!raw || Number.isNaN(number)) return "";
  return number.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(raw: string | null | undefined): string {
  const value = String(raw ?? "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const [year, month, day] = value.split("-");
  return `${day}/${month}/${year}`;
}

function displayValue(kind: FieldKind, value: string | null | undefined): string {
  if (kind === "money") return formatMoney(value);
  if (kind === "date") return formatDate(value);
  if (kind === "percent") return value ? `${String(value).replace(/%/g, "")}%` : "";
  return String(value ?? "");
}

function IncludedCard({
  card,
  selection,
  canUndo,
  onQueue,
}: {
  card: BenefitCardSummary;
  selection?: { id: string; cost_status: string } | Record<string, unknown> | null;
  canUndo: boolean;
  onQueue: (operation: Record<string, unknown> & { op: string }, path: string) => void;
}) {
  const selectionId = selection && typeof selection === "object" && "id" in selection ? String(selection.id) : null;
  const pending = !selectionId || selectionId.startsWith("pending:");
  const cost = selection && typeof selection === "object" && "cost_status" in selection
    ? String(selection.cost_status || card.cost_status || "included")
    : String(card.cost_status || "included");
  return (
    <article className="grid gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">{card.label}</h3>
          <p className="mt-0.5 text-xs text-[var(--rl-text)]">{card.value || "Value to confirm"}</p>
        </div>
        <button
          type="button"
          aria-label={`Remove ${card.label} from this quotation`}
          disabled={pending}
          onClick={() => selectionId && onQueue({ op: "benefit_update", selection_id: selectionId, state: "removed" }, `benefits.${selectionId}.state`)}
          className="rounded-full p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)] disabled:opacity-40"
        >
          <X size={15} weight="bold" />
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <label className="grid flex-1 gap-1 text-[10px] font-bold uppercase tracking-wide text-[var(--rl-text-muted)]">
          Cost
          <Select
            value={cost}
            disabled={pending}
            onChange={(event) => selectionId && onQueue({ op: "benefit_update", selection_id: selectionId, cost_status: event.target.value }, `benefits.${selectionId}.cost_status`)}
            className="min-h-7 text-xs"
          >
            <option value="included">Included</option>
            <option value="paid">Paid</option>
            <option value="foc">FOC</option>
            <option value="unknown">Unknown</option>
          </Select>
        </label>
        {canUndo ? (
          <Button
            variant="secondary"
            size="sm"
            disabled={pending}
            onClick={() => selectionId && onQueue({ op: "revert_benefit", selection_id: selectionId }, `benefits.${selectionId}.revert`)}
          >
            Undo upgrade
          </Button>
        ) : null}
      </div>
    </article>
  );
}

function AddonCard({
  card,
  onQueue,
}: {
  card: BenefitCardSummary;
  onQueue: (operation: Record<string, unknown> & { op: string }, path: string) => void;
}) {
  return (
    <article className="grid gap-2 rounded-[var(--rl-radius-sm)] border border-dashed border-[var(--rl-border)] p-3">
      <div>
        <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">{card.label}</h3>
        <p className="mt-0.5 text-xs text-[var(--rl-text)]">{card.value || "Value to confirm"}</p>
        {card.branch_key ? <p className="mt-0.5 text-[10px] text-[var(--rl-text-muted)]">Choice: {card.branch_key}</p> : null}
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Button size="sm" variant="secondary" onClick={() => onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, cost_status: "paid" }, `benefits.offer.${card.offering_id}`)}>
          Add paid
        </Button>
        <Button size="sm" variant="secondary" onClick={() => onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, cost_status: "foc" }, `benefits.offer.${card.offering_id}`)}>
          Add FOC
        </Button>
      </div>
    </article>
  );
}

export function ReviewPhase({ id, onNext }: { id: string; onNext: () => void }) {
  const { workspace, loading, loadError } = useWorkspaceData();
  const { decideField, save, reload, queueOperation } = useWorkspaceActions();
  const mutation = useWorkspaceMutation();
  const [pdfOpen, setPdfOpen] = useState(true);
  const [formValues, setFormValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(FORM_FIELDS.map((field) => [field.name, ""]))
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [companyWorkspace, setCompanyWorkspace] = useState<CompanyWorkspace | null>(null);
  const [pinLoading, setPinLoading] = useState(false);
  const [customBox, setCustomBox] = useState<"included" | "addons" | null>(null);
  const [customLabel, setCustomLabel] = useState("");
  const [customValue, setCustomValue] = useState("");
  const [customCost, setCustomCost] = useState("paid");
  const [learnPrompt, setLearnPrompt] = useState<{ field: string; value: string } | null>(null);
  const promptedRef = useRef<Set<string>>(new Set());
  const [publishedTemplates, setPublishedTemplates] = useState<PublishedTemplateOption[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [templateImpact, setTemplateImpact] = useState<TemplateSelectionImpact | null>(null);

  const syncForm = useCallback(() => {
    if (!workspace) return;
    const values: Record<string, string> = {};
    for (const field of FORM_FIELDS) {
      const stored = (workspace.fields[field.name] as WorkspaceField | undefined)?.value;
      values[field.name] = displayValue(field.kind, stored ?? null);
    }
    setFormValues(values);
  }, [workspace]);

  useEffect(() => {
    syncForm();
  }, [syncForm, mutation.lastSavedAt]);

  useEffect(() => {
    let cancelled = false;
    api<{ companies: { items: Array<{ id: string; name: string }> } }>("/business/companies?page_size=100")
      .then((result) => { if (!cancelled) setCompanies(result.companies?.items || []); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const companyId = workspace?.pinned.company_id;
    if (!companyId) {
      setCompanyWorkspace(null);
      return;
    }
    let cancelled = false;
    api<{ workspace: CompanyWorkspace }>(`/business/companies/${companyId}/workspace`)
      .then((result) => { if (!cancelled) setCompanyWorkspace(result.workspace); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [workspace?.pinned.company_id]);

  useEffect(() => {
    let cancelled = false;
    setTemplatesLoading(true);
    api<{ templates: PublishedTemplateOption[] }>("/business/templates/published")
      .then((result) => { if (!cancelled) setPublishedTemplates(result.templates); })
      .catch((error) => { if (!cancelled) setTemplateError(apiErrorMessage(error)); })
      .finally(() => { if (!cancelled) setTemplatesLoading(false); });
    return () => { cancelled = true; };
  }, []);

  async function previewTemplateSelection(templateRevisionId: string) {
    setTemplateError(null);
    setTemplateImpact(null);
    if (!templateRevisionId || templateRevisionId === workspace?.pinned.template_revision_id) return;
    try {
      const result = await api<{ impact: TemplateSelectionImpact }>(`/sessions/${id}/template-selection-impact`, {
        method: "POST",
        body: JSON.stringify({ base_revision: workspace?.revision, template_revision_id: templateRevisionId }),
      });
      setTemplateImpact(result.impact);
    } catch (error) {
      setTemplateError(apiErrorMessage(error));
    }
  }

  function confirmTemplateSelection() {
    if (!templateImpact) return;
    const option = publishedTemplates.find((item) => item.template_revision_id === templateImpact.target.template_revision_id);
    if (!option) {
      setTemplateError("That published template is no longer available. Refresh this page.");
      return;
    }
    queueOperation({
      op: "template_selection",
      template_revision_id: option.template_revision_id,
      template_id: option.template_id,
      revision_number: option.revision_number,
      config_hash: option.config_hash,
      confirmed: true,
    }, "template_revision_id");
    setTemplateImpact(null);
  }

  const productOptions = useMemo(() => companyWorkspace?.products || [], [companyWorkspace]);
  const tierOptions = useMemo(
    () => (companyWorkspace?.tiers || []).filter((tier) => tier.product_id === workspace?.pinned.product_id),
    [companyWorkspace, workspace?.pinned.product_id],
  );

  function commitField(field: FormField) {
    const current = formValues[field.name];
    if (current === undefined || current.trim() === "") return;
    if (field.kind === "total") return;
    decideField(field.name, "edit", current);
  }

  function pinCatalog(companyId: string, productId?: string | null, tierId?: string | null) {
    setPinLoading(true);
    const company = companies.find((item) => item.id === companyId);
    const product = productId ? productOptions.find((item) => item.id === productId) : null;
    const tier = tierId ? tierOptions.find((item) => item.id === tierId) : null;
    queueOperation({
      op: "pin_catalog",
      company_id: companyId,
      ...(productId ? { product_id: productId } : {}),
      ...(tierId ? { tier_id: tierId } : {}),
      company_name: company?.name || workspace?.pinned_names.company_name,
      ...(product ? { product_name: product.name } : {}),
      ...(tier ? { tier_name: tier.name } : {}),
    }, "catalog");
    setPinLoading(false);
  }

  function addCustomBenefit() {
    const label = customLabel.trim();
    if (!label) return;
    const key = `custom:${crypto.randomUUID()}`;
    queueOperation({
      op: "create_custom_benefit",
      selection_key: key,
      label,
      typed_value: customValue.trim() ? { type: "custom", display_text: customValue.trim() } : { type: "custom", display_text: label },
      cost_status: customCost,
      state: "current",
    }, `benefits.${key}`);
    setCustomLabel("");
    setCustomValue("");
    setCustomBox(null);
  }

  async function saveAndCheckLearning() {
    setActionError(null);
    try {
      await save();
      if (!workspace) return;
      for (const fieldName of LEARNABLE.keys()) {
        const stored = (workspace.fields[fieldName] as WorkspaceField | undefined)?.value;
        const value = String(stored ?? "").trim();
        if (!value || promptedRef.current.has(`${fieldName}:${value}`)) continue;
        promptedRef.current.add(`${fieldName}:${value}`);
        try {
          const known = await api<{ known: boolean }>(`/business/dictionaries/contains?field=${encodeURIComponent(LEARNABLE.get(fieldName) || fieldName)}&value=${encodeURIComponent(value)}`);
          if (!known.known) {
            setLearnPrompt({ field: LEARNABLE.get(fieldName) || fieldName, value });
            break;
          }
        } catch {
          // Dataset checks are best-effort and never block the flow.
        }
      }
    } catch (error) {
      setActionError(apiErrorMessage(error));
    }
  }

  async function learnValue() {
    if (!learnPrompt) return;
    try {
      await api(`/business/dictionaries/learn`, {
        method: "POST",
        body: JSON.stringify({ field: learnPrompt.field, value: learnPrompt.value }),
      });
    } catch {
      // Learning is best-effort.
    }
    setLearnPrompt(null);
  }

  async function handleNext() {
    setActionError(null);
    try {
      await save();
      onNext();
    } catch (error) {
      setActionError(apiErrorMessage(error));
    }
  }

  if (loading) return <PageLoading />;
  if (loadError || !workspace) {
    return (
      <Card className="grid gap-3 p-6" role="alert">
        <h1 className="text-xl font-bold text-[var(--rl-text-strong)]">Could not load quotation</h1>
        <p className="text-sm text-[var(--rl-text)]">{loadError || "The quotation workspace is unavailable."}</p>
        <Button className="w-fit" onClick={() => reload().catch(() => undefined)}>Retry</Button>
      </Card>
    );
  }

  const currentCards = workspace.benefit_cards.current_benefits;
  const addonCards = workspace.benefit_cards.available_addons;
  const companyName = workspace.pinned_names.company_name;

  return (
    <section className="grid gap-4">
      <SessionPhaseBar sessionId={id} current="extraction" onStep={(key) => { if (key === "preview") onNext(); }} />

      <Card className="sticky top-[68px] z-20 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[22px] font-bold text-[var(--rl-text-strong)]">Check quotation values</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={workspace.status} />
              {mutation.dirty ? <Badge variant="warning">Unsaved changes</Badge> : <Badge variant="success">Saved</Badge>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" loading={mutation.saving} icon={<FloppyDisk weight="bold" />} onClick={() => saveAndCheckLearning()}>
              Save
            </Button>
            <Button icon={<Eye weight="bold" />} onClick={handleNext}>
              Next: Preview <ArrowRight />
            </Button>
          </div>
        </div>
      </Card>

      {actionError || mutation.saveError ? (
        <div role="alert" className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] p-3 text-sm font-semibold text-[var(--rl-red)]">
          {actionError || mutation.saveError}
        </div>
      ) : null}

      {learnPrompt ? (
        <Card role="status" className="flex flex-wrap items-center justify-between gap-3 border-amber-300 bg-amber-50 p-3">
          <p className="text-sm font-semibold text-[var(--rl-text-strong)]">
            Save &quot;{learnPrompt.value}&quot; to the {learnPrompt.field === "car_brand" ? "vehicle make" : "vehicle model"} dataset?
          </p>
          <div className="flex gap-2">
            <Button size="sm" onClick={learnValue}>Yes, add it</Button>
            <Button variant="secondary" size="sm" onClick={() => setLearnPrompt(null)}>No</Button>
          </div>
        </Card>
      ) : null}

      <div className={`grid items-start gap-4 ${pdfOpen ? "xl:grid-cols-[minmax(280px,0.85fr)_minmax(0,1.15fr)_minmax(340px,420px)]" : "xl:grid-cols-[minmax(0,1fr)_minmax(340px,420px)]"}`}>
        {pdfOpen ? (
          <div className="relative min-w-0">
            <Card className="sticky top-[140px] h-[calc(100vh-180px)] p-2">
              <iframe
                title="Source quotation PDF"
                src={fileUrl(`/uploaded-files/${workspace.uploaded_file_id}/content`)}
                className="h-full w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white"
              />
            </Card>
            <Button
              variant="secondary"
              size="sm"
              className="absolute right-1 top-1"
              aria-label="Hide the source PDF"
              onClick={() => setPdfOpen(false)}
            >
              <CaretLeft weight="bold" /> Hide PDF
            </Button>
          </div>
        ) : (
          <Button variant="secondary" className="w-fit" onClick={() => setPdfOpen(true)}>
            Show source PDF
          </Button>
        )}

        <Card className="grid gap-3 p-4">
          <div>
            <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Extracted values</h2>
            <p className="mt-1 text-sm text-[var(--rl-text-muted)]">Only what the template needs. Everything else is kept for customer records.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {FORM_FIELDS.map((field) => {
              const stored = workspace.fields[field.name];
              const empty = !(stored?.value);
              return (
                <label key={field.name} className="grid gap-1 text-xs font-semibold text-[var(--rl-text-strong)]">
                  {field.label}
                  <span className="relative">
                    {field.kind === "money" ? <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-[var(--rl-text-muted)]">RM</span> : null}
                    <Input
                      value={formValues[field.name]}
                      disabled={field.kind === "total"}
                      placeholder={empty ? "Missing" : ""}
                      title={!empty && stored?.status === "check_needed" ? "Extracted with low confidence. Check this value." : undefined}
                      className={`${field.kind === "money" ? "pl-9" : ""} ${empty ? "ring-2 ring-amber-300" : ""}`}
                      onChange={(event) => setFormValues((values) => ({ ...values, [field.name]: event.target.value }))}
                      onBlur={() => commitField(field)}
                      onKeyDown={(event) => { if (event.key === "Enter") (event.target as HTMLInputElement).blur(); }}
                    />
                  </span>
                </label>
              );
            })}
          </div>
          <p className="text-xs text-[var(--rl-text-muted)]">Amber fields need a value. NCD is a percentage; amounts are in RM and totals are computed.</p>
        </Card>

        <aside className="grid content-start gap-4">
          <Card className="grid gap-3 p-4">
            <div>
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">{companyName ? `${companyName} benefits` : "Benefits"}</h2>
              <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                {companyName ? `Defaults and add-ons from the pinned catalog.` : "Pin an insurer to load its verified benefits automatically."}
              </p>
            </div>
            {!companyName ? (
              <label className="grid gap-1.5 text-sm font-semibold text-[var(--rl-text-strong)]">
                Insurance company
                <Select
                  value={workspace.pinned.company_id || ""}
                  disabled={pinLoading || !companies.length}
                  onChange={(event) => pinCatalog(event.target.value)}
                >
                  <option value="">Choose the insurer</option>
                  {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
                </Select>
              </label>
            ) : null}
            {companyName && productOptions.length > 0 && (!workspace.pinned.product_id || productOptions.length > 1) ? (
              <label className="grid gap-1.5 text-sm font-semibold text-[var(--rl-text-strong)]">
                Product
                <Select value={workspace.pinned.product_id || ""} disabled={pinLoading} onChange={(event) => pinCatalog(workspace.pinned.company_id as string, event.target.value)}>
                  <option value="">Choose the product</option>
                  {productOptions.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
                </Select>
              </label>
            ) : null}
            {companyName && workspace.pinned.product_id && tierOptions.length > 0 && (!workspace.pinned.tier_id || tierOptions.length > 1) ? (
              <label className="grid gap-1.5 text-sm font-semibold text-[var(--rl-text-strong)]">
                Tier
                <Select value={workspace.pinned.tier_id || ""} disabled={pinLoading} onChange={(event) => pinCatalog(workspace.pinned.company_id as string, workspace.pinned.product_id, event.target.value)}>
                  <option value="">Choose the tier</option>
                  {tierOptions.map((tier) => <option key={tier.id} value={tier.id}>{tier.name}</option>)}
                </Select>
              </label>
            ) : null}
          <Card className="grid gap-3 p-4">
            <div>
              <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Master template</h2>
              <p className="mt-1 text-xs text-[var(--rl-text-muted)]">Pins the exact published revision used for the PDF.</p>
            </div>
            <label className="grid gap-1.5 text-sm font-semibold text-[var(--rl-text-strong)]">
              Published template revision
              <Select
                value={workspace.pinned.template_revision_id || ""}
                disabled={templatesLoading || !publishedTemplates.length}
                onChange={(event) => previewTemplateSelection(event.target.value)}
              >
                <option value="">Choose a published template</option>
                {publishedTemplates.map((option) => (
                  <option key={option.template_revision_id} value={option.template_revision_id}>
                    {option.name} · r{option.revision_number} · {option.page_profile.name}
                  </option>
                ))}
              </Select>
            </label>
            {templateError ? <p role="alert" className="text-xs font-semibold text-[var(--rl-red)]">{templateError}</p> : null}
            {templateImpact ? (
              <div className="grid gap-2 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50 p-3">
                <p className="text-sm font-bold text-[var(--rl-text-strong)]">Change to {templateImpact.target.name} revision {templateImpact.target.revision_number}?</p>
                {templateImpact.messages.map((message) => <p key={message} className="text-xs font-semibold text-amber-800">{message}</p>)}
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" onClick={confirmTemplateSelection}>Confirm template change</Button>
                  <Button variant="secondary" size="sm" onClick={() => setTemplateImpact(null)}>Cancel</Button>
                </div>
              </div>
            ) : null}
          </Card>

          <div className="grid grid-cols-2 gap-3">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wide text-[var(--rl-text-muted)]">Defaults</h3>
                <ul className="mt-2 grid gap-1.5">
                  {workspace.catalog.defaults.length ? workspace.catalog.defaults.map((item) => (
                    <li key={item.offering_id} className="text-xs text-[var(--rl-text)]">
                      <span className="font-semibold">{item.label}</span>
                      <span className="ml-1 text-[var(--rl-text-muted)]">{item.value}</span>
                    </li>
                  )) : <li className="text-xs text-[var(--rl-text-muted)]">None pinned yet</li>}
                </ul>
              </div>
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wide text-[var(--rl-text-muted)]">Add-ons</h3>
                <ul className="mt-2 grid gap-1.5">
                  {workspace.catalog.addons.length ? workspace.catalog.addons.map((item) => (
                    <li key={item.offering_id} className="text-xs text-[var(--rl-text)]">
                      <span className="font-semibold">{item.label}</span>
                      <span className="ml-1 text-[var(--rl-text-muted)]">{item.value}</span>
                    </li>
                  )) : <li className="text-xs text-[var(--rl-text-muted)]">None pinned yet</li>}
                </ul>
              </div>
            </div>
          </Card>

          <div className="grid grid-cols-2 gap-3">
            <Card className="grid content-start gap-2 p-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Included</h2>
                <Button variant="ghost" size="sm" aria-label="Add a temporary custom item" onClick={() => setCustomBox(customBox === "included" ? null : "included")}>
                  <Plus weight="bold" />
                </Button>
              </div>
              {customBox === "included" ? (
                <div className="grid gap-1.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-2">
                  <Input aria-label="Custom item label" placeholder="Item name" value={customLabel} onChange={(event) => setCustomLabel(event.target.value)} />
                  <Input aria-label="Custom item value" placeholder="Value" value={customValue} onChange={(event) => setCustomValue(event.target.value)} />
                  <div className="flex gap-1.5">
                    <Select value={customCost} onChange={(event) => setCustomCost(event.target.value)}>
                      <option value="paid">Paid</option>
                      <option value="foc">FOC</option>
                      <option value="included">Included</option>
                    </Select>
                    <Button size="sm" disabled={!customLabel.trim()} onClick={addCustomBenefit}>Add</Button>
                  </div>
                </div>
              ) : null}
              {currentCards.length ? currentCards.map((card) => {
                const selection = workspace.benefits.find((item) => item.id === card.selection_id);
                const canUndo = Boolean(selection && workspace.benefits.some((item) => item.superseded_by_id === selection.id));
                return <IncludedCard key={card.card_key} card={card} selection={selection} canUndo={canUndo} onQueue={queueOperation} />;
              }) : <p className="text-xs text-[var(--rl-text-muted)]">Pin an insurer to auto-load its defaults.</p>}
            </Card>

            <Card className="grid content-start gap-2 p-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Add-ons</h2>
                <Button variant="ghost" size="sm" aria-label="Add a temporary custom item" onClick={() => setCustomBox(customBox === "addons" ? null : "addons")}>
                  <Plus weight="bold" />
                </Button>
              </div>
              {customBox === "addons" ? (
                <div className="grid gap-1.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-2">
                  <Input aria-label="Custom item label" placeholder="Item name" value={customLabel} onChange={(event) => setCustomLabel(event.target.value)} />
                  <Input aria-label="Custom item value" placeholder="Value" value={customValue} onChange={(event) => setCustomValue(event.target.value)} />
                  <div className="flex gap-1.5">
                    <Select value={customCost} onChange={(event) => setCustomCost(event.target.value)}>
                      <option value="paid">Paid</option>
                      <option value="foc">FOC</option>
                      <option value="included">Included</option>
                    </Select>
                    <Button size="sm" disabled={!customLabel.trim()} onClick={addCustomBenefit}>Add</Button>
                  </div>
                </div>
              ) : null}
              {addonCards.length ? addonCards.map((card) => (
                <AddonCard key={card.card_key} card={card} onQueue={queueOperation} />
              )) : <p className="text-xs text-[var(--rl-text-muted)]">All available upgrades are already applied.</p>}
            </Card>
          </div>
        </aside>
      </div>
    </section>
  );
}
