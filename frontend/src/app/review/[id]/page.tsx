"use client";

import { use, useEffect, useState } from "react";
import { CheckSquare, Download, Save, Square } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { DraftFieldTable } from "@/components/draft-field-table";
import { StatusBadge } from "@/components/status-badge";
import { api, fileUrl } from "@/lib/api";

type DraftField = { value?: string | null; status?: string; message?: string; warnings?: string[] };
type BenefitCard = { title: string; subtitle?: string; icon?: string; lines?: string[] };
type ReviewSchema = {
  groups?: Array<{ id: string; title: string; collapsed?: boolean; fields: string[] }>;
  specials?: BenefitCard[];
  add_ons?: BenefitCard[];
};
type PackageConfig = { name: string; included: string[]; add_ons: string[]; included_cards?: string[]; add_on_cards?: string[] };
type TemplateConfig = { id: string; name: string; packages: PackageConfig[]; cards?: Record<string, BenefitCard & { id?: string }>; review_schema?: ReviewSchema };
type Draft = {
  id: string;
  filename: string;
  status: string;
  fields: Record<string, DraftField>;
  warnings: string[];
  source_pdf_url: string;
  source_pdf_status: string;
  source_pdf_expires_at?: string | null;
  page_text: Array<{ page: number; text: string }>;
  field_evidence: Record<string, string>;
  field_hints: Record<string, string>;
  available_templates: TemplateConfig[];
  selected_template_id?: string | null;
  selected_package?: string | null;
  review_schema?: ReviewSchema;
  versions: Array<{ id: string; filename: string; download_url: string; pdf_status: string; generated_at: string }>;
};

function parseIds(value?: string | null) {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return value.split(";").map((item) => item.trim()).filter(Boolean);
  }
}

function BenefitPicker({
  title,
  cards,
  selected,
  onToggle
}: {
  title: string;
  cards: Array<{ id?: string; title: string; subtitle?: string; icon?: string; lines?: string[] }>;
  selected: string[];
  onToggle: (id: string) => void;
}) {
  return (
    <div className="rounded-md border border-rl-line bg-white p-3">
      <h3 className="font-bold text-rl-textStrong">{title}</h3>
      {cards.length ? (
        <div className="mt-2 grid gap-2">
          {cards.map((card) => {
            const id = card.id || card.title;
            const checked = selected.includes(id);
            return (
              <button
                key={id}
                className={`grid grid-cols-[34px_1fr_auto] items-center gap-2 rounded-md border p-2 text-left text-sm ${checked ? "border-rl-black bg-rl-soft" : "border-rl-line bg-white"}`}
                type="button"
                onClick={() => onToggle(id)}
              >
                <span className="flex h-8 w-8 items-center justify-center rounded border border-rl-line bg-white text-[10px] font-black">{(card.icon || "IC").slice(0, 2).toUpperCase()}</span>
                <span>
                  <span className="block font-bold text-rl-textStrong">{card.title}</span>
                  {card.subtitle ? <span className="block text-xs">{card.subtitle}</span> : null}
                  {card.lines?.length ? <span className="block text-xs">{card.lines.join(" / ")}</span> : null}
                </span>
                {checked ? <CheckSquare aria-hidden="true" size={18} /> : <Square aria-hidden="true" size={18} />}
              </button>
            );
          })}
        </div>
      ) : <p className="mt-2 text-sm">None selected.</p>}
    </div>
  );
}

export default function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [fields, setFields] = useState<Draft["fields"]>({});
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedPackage, setSelectedPackage] = useState("");
  const [selectedSpecials, setSelectedSpecials] = useState<string[]>([]);
  const [selectedAddOns, setSelectedAddOns] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    const result = await api<{ draft: Draft }>(`/drafts/${id}`);
    setDraft(result.draft);
    setFields(result.draft.fields);
    setSelectedTemplateId(result.draft.selected_template_id || "");
    setSelectedPackage(result.draft.selected_package || "");
    setSelectedSpecials(parseIds(result.draft.fields.benefits_selected?.value));
    setSelectedAddOns(parseIds(result.draft.fields.add_ons_selected?.value));
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load draft."));
  }, [id]);

  function selectTemplate(templateId: string) {
    const template = draft?.available_templates.find((item) => item.id === templateId);
    if (!template) return;
    const packageName = template.packages[0]?.name || "";
    const nextSpecials = template.packages[0]?.included_cards || [];
    setSelectedTemplateId(templateId);
    setSelectedPackage(packageName);
    setSelectedSpecials(nextSpecials);
    setSelectedAddOns([]);
    setFields((current) => ({
      ...current,
      benefits_selected: { ...(current.benefits_selected || {}), value: JSON.stringify(nextSpecials) },
      add_ons_selected: { ...(current.add_ons_selected || {}), value: "[]" },
      selected_package: { ...(current.selected_package || {}), value: packageName },
      selected_template_id: { ...(current.selected_template_id || {}), value: templateId }
    }));
  }

  useEffect(() => {
    if (!draft || selectedTemplateId) return;
    const firstTemplate = draft.available_templates[0];
    if (firstTemplate) {
      selectTemplate(firstTemplate.id);
    }
  }, [draft, selectedTemplateId]);

  const selectedTemplate = draft?.available_templates.find((template) => template.id === selectedTemplateId);
  const packages = selectedTemplate?.packages || [];
  const selectedPackageConfig = packages.find((item) => item.name === selectedPackage);
  const cardCatalog = selectedTemplate?.cards || {};
  const specialCards = (selectedPackageConfig?.included_cards || []).map((id, index) => ({ ...(cardCatalog[id] || {}), id, title: cardCatalog[id]?.title || selectedPackageConfig?.included?.[index] || id }));
  const addOnCards = (selectedPackageConfig?.add_on_cards || []).map((id, index) => ({ ...(cardCatalog[id] || {}), id, title: cardCatalog[id]?.title || selectedPackageConfig?.add_ons?.[index] || id }));

  function syncBenefitFields(nextSpecials: string[], nextAddOns: string[]) {
    setFields((current) => ({
      ...current,
      benefits_selected: { ...(current.benefits_selected || {}), value: JSON.stringify(nextSpecials) },
      add_ons_selected: { ...(current.add_ons_selected || {}), value: JSON.stringify(nextAddOns) },
      selected_package: { ...(current.selected_package || {}), value: selectedPackage }
    }));
  }

  function setPackage(packageName: string) {
    const template = draft?.available_templates.find((item) => item.id === selectedTemplateId);
    const packageConfig = template?.packages.find((item) => item.name === packageName);
    const nextSpecials = packageConfig?.included_cards || [];
    const nextAddOns: string[] = [];
    setSelectedPackage(packageName);
    setSelectedSpecials(nextSpecials);
    setSelectedAddOns(nextAddOns);
    setFields((current) => ({
      ...current,
      benefits_selected: { ...(current.benefits_selected || {}), value: JSON.stringify(nextSpecials) },
      add_ons_selected: { ...(current.add_ons_selected || {}), value: JSON.stringify(nextAddOns) },
      selected_package: { ...(current.selected_package || {}), value: packageName }
    }));
  }

  async function save() {
    const updates = Object.fromEntries(Object.entries(fields).map(([key, field]) => [key, field.value || ""]));
    const result = await api<{ draft: Draft }>(`/drafts/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        fields: updates,
        template_id: selectedTemplateId || null,
        selected_package: selectedPackage || null,
        benefits_selected: JSON.stringify(selectedSpecials),
        add_ons_selected: JSON.stringify(selectedAddOns)
      })
    });
    setDraft(result.draft);
    setFields(result.draft.fields);
    setSelectedTemplateId(result.draft.selected_template_id || "");
    setSelectedPackage(result.draft.selected_package || "");
    setSelectedSpecials(parseIds(result.draft.fields.benefits_selected?.value));
    setSelectedAddOns(parseIds(result.draft.fields.add_ons_selected?.value));
    setMessage("Saved.");
    return result.draft;
  }

  async function generate() {
    await save();
    const result = await api<{ version: { download_url: string } }>(`/drafts/${id}/generate`, {
      method: "POST",
      body: JSON.stringify({})
    });
    window.location.href = fileUrl(result.version.download_url);
  }

  return (
    <AppShell>
      <section className="grid gap-4">
        <div className="sticky top-0 z-20 -mx-2 rounded-md border border-rl-line bg-white/95 p-3 shadow-sm backdrop-blur">
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_220px_190px_auto] xl:items-end">
            <div>
              <h1 className="line-clamp-2 text-xl font-bold text-rl-textStrong">{draft?.filename || "Quotation draft"}</h1>
              <div className="mt-2">{draft ? <StatusBadge status={draft.status} /> : null}</div>
            </div>
            <label className="grid gap-1 text-sm font-bold text-rl-textStrong">
              Risklocker Template
              <select
                className="rl-input"
                value={selectedTemplateId}
                onChange={(event) => selectTemplate(event.target.value)}
              >
                <option value="">Choose template</option>
                {draft?.available_templates.map((template) => (
                  <option key={template.id} value={template.id}>{template.name}</option>
                ))}
              </select>
            </label>
            <label className="grid gap-1 text-sm font-bold text-rl-textStrong">
              Package
              <select className="rl-input" value={selectedPackage} onChange={(event) => setPackage(event.target.value)} disabled={!selectedTemplateId}>
                <option value="">Choose package</option>
                {packages.map((item) => (
                  <option key={item.name} value={item.name}>{item.name}</option>
                ))}
              </select>
            </label>
            <div className="flex flex-wrap gap-2">
              <button className="rl-button rl-button-secondary" type="button" onClick={save}>
                <Save aria-hidden="true" size={18} />
                Save
              </button>
              <button className="rl-button" type="button" onClick={generate}>
                <Download aria-hidden="true" size={18} />
                Generate PDF
              </button>
            </div>
          </div>
        </div>

        {error ? <p className="rounded-md border border-rl-red bg-red-50 p-3 font-bold text-rl-red">{error}</p> : null}
        {message ? <p className="rounded-md border border-rl-success bg-green-50 p-3 font-bold text-rl-success">{message}</p> : null}

        <div className="grid gap-4 xl:grid-cols-[minmax(420px,0.95fr)_minmax(480px,1.05fr)]">
          <div className="rl-panel overflow-hidden xl:sticky xl:top-28 xl:h-[calc(100vh-8rem)]">
            {draft?.source_pdf_url ? (
              <iframe className="h-[70vh] w-full bg-white xl:h-full" title="Uploaded quotation PDF" src={fileUrl(draft.source_pdf_url)} />
            ) : (
              <div className="grid h-full min-h-64 place-content-center gap-2 p-5 text-center">
                <p className="font-bold text-rl-textStrong">Original PDF expired</p>
                <p className="max-w-sm text-sm text-rl-text">Extracted text and reviewed values remain available. The original source PDF cannot be reconstructed.</p>
              </div>
            )}
          </div>

          <div className="grid gap-4 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto xl:pr-1">
            <div className="rl-panel p-4">
              <h2 className="text-lg font-bold text-rl-textStrong">Extracted Text</h2>
              <div className="mt-3 grid max-h-64 gap-3 overflow-auto rounded-md border border-rl-line bg-rl-soft p-3 text-sm leading-relaxed text-rl-text">
                {draft?.page_text?.length ? draft.page_text.map((page) => (
                  <pre key={page.page} className="whitespace-pre-wrap font-sans">{page.text}</pre>
                )) : <p>No extracted text available.</p>}
              </div>
            </div>

            {selectedPackageConfig ? (
              <div className="grid gap-3 lg:grid-cols-2">
                <BenefitPicker
                  title="Our Specials"
                  cards={specialCards}
                  selected={selectedSpecials}
                  onToggle={(cardId) => {
                    const next = selectedSpecials.includes(cardId) ? selectedSpecials.filter((id) => id !== cardId) : [...selectedSpecials, cardId];
                    setSelectedSpecials(next);
                    syncBenefitFields(next, selectedAddOns);
                  }}
                />
                <BenefitPicker
                  title="You May Add On"
                  cards={addOnCards}
                  selected={selectedAddOns}
                  onToggle={(cardId) => {
                    const next = selectedAddOns.includes(cardId) ? selectedAddOns.filter((id) => id !== cardId) : [...selectedAddOns, cardId];
                    setSelectedAddOns(next);
                    syncBenefitFields(selectedSpecials, next);
                  }}
                />
              </div>
            ) : null}

            <DraftFieldTable
              fields={fields}
              reviewSchema={selectedTemplate?.review_schema || draft?.review_schema}
              fieldHints={draft?.field_hints}
              onChange={(field, value) => setFields((current) => ({ ...current, [field]: { ...(current[field] || {}), value } }))}
            />
          </div>
        </div>

        {draft?.versions?.length ? (
          <div className="rl-panel p-5">
            <h2 className="text-xl font-bold text-rl-textStrong">Generated versions</h2>
            <div className="mt-3 grid gap-2">
              {draft.versions.map((version) => (
                version.download_url ? (
                  <a key={version.id} className="font-bold text-rl-blue underline" href={fileUrl(version.download_url)}>
                    {version.filename}
                  </a>
                ) : (
                  <div key={version.id} className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-bold text-rl-textStrong">{version.filename}</span>
                    <span>PDF Expired</span>
                  </div>
                )
              ))}
            </div>
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}
