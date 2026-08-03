"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DownloadSimple, FloppyDisk, Eye, EyeSlash, Highlighter, X } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { DraftFieldTable } from "@/components/draft-field-table";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { useToast } from "@/components/ui/toast";
import { Select } from "@/components/ui/select";

type DraftField = { value?: string | null; status?: string; message?: string };
type TemplateRecord = { id: string; name: string; insurance_company_name?: string | null; locked: boolean; is_default: boolean };
type ReviewSchema = { groups?: Array<{ id: string; title: string; fields: string[] }> };
type EvidenceEntry = { value: string; score: number; source_method: string; page?: number | null; evidence: string };
type Draft = {
  id: string; filename: string; status: string;
  fields: Record<string, DraftField>; warnings: string[];
  source_pdf_url: string; source_pdf_status: string;
  page_text: Array<{ page: number; text: string }>;
  field_evidence: Record<string, EvidenceEntry[]>;
  field_hints: Record<string, string>;
  available_templates: TemplateRecord[];
  selected_template_id?: string | null;
  review_schema?: ReviewSchema;
  versions: Array<{ id: string; filename: string; download_url: string; pdf_status: string; generated_at: string }>;
};

function highlightText(text: string, terms: string[]) {
  if (!terms.length) return <span>{text}</span>;
  const escaped = terms.filter(Boolean).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!escaped.length) return <span>{text}</span>;
  const pattern = new RegExp(`(${escaped.join("|")})`, "gi");
  const parts = text.split(pattern);
  const seen = new Set<string>();
  return (
    <span>
      {parts.map((part, i) => {
        if (!pattern.test(part)) return <span key={i}>{part}</span>;
        const key = `${part}-${i}`;
        if (seen.has(part.toLowerCase())) return <span key={key}>{part}</span>;
        seen.add(part.toLowerCase());
        return <mark key={key} className="bg-yellow-200 text-[var(--rl-black)]">{part}</mark>;
      })}
    </span>
  );
}

function findMatchingTemplate(templates: TemplateRecord[], company: string): TemplateRecord | undefined {
  if (!company) return templates[0];
  const lower = company.toLowerCase();
  const exact = templates.find((t) => t.insurance_company_name?.toLowerCase() === lower);
  if (exact) return exact;
  const partial = templates.find((t) => t.insurance_company_name?.toLowerCase().includes(lower) || lower.includes(t.insurance_company_name?.toLowerCase() || ""));
  return partial || templates[0];
}

export default function SessionReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { toast } = useToast();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [fields, setFields] = useState<Draft["fields"]>({});
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [detectedCompany, setDetectedCompany] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [showEvidence, setShowEvidence] = useState(true);
  const [showHighlights, setShowHighlights] = useState(false);
  const [activeField, setActiveField] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    const session = await api<{ session: { draft_id: string; detected_company?: string | null } }>(`/sessions/${id}`);
    setDetectedCompany(session.session.detected_company || null);
    const draftId = session.session.draft_id;
    const result = await api<{ draft: Draft }>(`/drafts/${draftId}`);
    setDraft(result.draft);
    setFields(result.draft.fields);
    const match = findMatchingTemplate(result.draft.available_templates, session.session.detected_company || "");
    if (match) setSelectedTemplateId(match.id);
  }, [id]);

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load session."));
  }, [id]);

  const save = useCallback(async () => {
    const updates = Object.fromEntries(Object.entries(fields).map(([key, field]) => [key, field.value || ""]));
    setError("");
    setSaving(true);
    try {
      const result = await api<{ draft: Draft }>(`/drafts/${draft?.id}`, {
        method: "PATCH",
        body: JSON.stringify({ fields: updates, template_id: selectedTemplateId || null }),
      });
      setDraft(result.draft);
      setFields(result.draft.fields);
      setSelectedTemplateId(result.draft.selected_template_id || "");
      toast("Saved.", "success");
      return result.draft;
    } catch (err) {
      setError(apiErrorMessage(err));
      throw err;
    } finally {
      setSaving(false);
    }
  }, [fields, draft?.id, selectedTemplateId]);

  async function generate() {
    setError("");
    setGenerating(true);
    try {
      await save();
      const result = await api<{ version: { download_url: string } }>(`/drafts/${draft?.id}/generate`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      window.location.href = fileUrl(result.version.download_url);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  }

  const matchedTemplate = draft?.available_templates.find((t) => t.id === selectedTemplateId);
  const evidenceTerms = showHighlights && activeField && draft?.field_evidence?.[activeField]
    ? draft.field_evidence[activeField].map((c) => c.evidence).filter(Boolean)
    : [];

  return (
    <AppShell>
      <section className="grid gap-4">
        <div className="sticky top-0 z-20 bg-[var(--rl-surface)]/95 backdrop-blur-md border-b border-[var(--rl-border)] p-4 rounded-[var(--rl-radius)]">
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
            <div>
              <h1 className="text-[20px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)] line-clamp-2">
                {draft?.filename || "Quotation session"}
              </h1>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {draft ? <StatusBadge status={draft.status} /> : null}
                {detectedCompany ? <span className="text-sm font-bold text-[var(--rl-text-strong)]">{detectedCompany}</span> : null}
              </div>
              {draft?.available_templates?.length ? (
                <label className="flex items-center gap-2 mt-1">
                  <span className="text-[13px] font-medium text-[var(--rl-text-muted)]">Template:</span>
                  <Select
                    value={selectedTemplateId}
                    onChange={(e) => setSelectedTemplateId(e.target.value)}
                    className="min-w-[200px] w-auto"
                  >
                    {draft.available_templates.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}{t.locked ? " (locked)" : ""}{t.is_default ? " (default)" : ""}</option>
                    ))}
                  </Select>
                </label>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" icon={<Eye weight="bold" />} onClick={() => router.push(`/sessions/${id}/preview`)}>
                Preview
              </Button>
              <Button variant="secondary" onClick={save} loading={saving} icon={<FloppyDisk weight="bold" />}>
                Save
              </Button>
              <Button onClick={generate} loading={generating} icon={<DownloadSimple weight="bold" />}>
                Generate PDF
              </Button>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[var(--rl-border)] pt-3">
            <span className="text-xs font-medium text-[var(--rl-text-muted)]">Review tools:</span>
            <Button
              variant="secondary"
              size="sm"
              icon={showEvidence ? <Eye weight="bold" /> : <EyeSlash weight="bold" />}
              onClick={() => setShowEvidence((v) => !v)}
            >
              Show source
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={<Highlighter weight="bold" />}
              onClick={() => setShowHighlights((v) => !v)}
            >
              Highlight matches
            </Button>
            {activeField ? (
              <Button
                variant="secondary"
                size="sm"
                icon={<X weight="bold" />}
                onClick={() => setActiveField(null)}
              >
                Clear selection
              </Button>
            ) : null}
          </div>
        </div>

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[minmax(420px,0.95fr)_minmax(480px,1.05fr)]">
          <div className="xl:sticky xl:top-28 xl:h-[calc(100vh-8rem)]">
            {draft?.source_pdf_url ? (
              <Card className="overflow-hidden h-full">
                <iframe className="h-[70vh] w-full bg-white xl:h-full" title="Uploaded quotation PDF" src={fileUrl(draft.source_pdf_url)} />
              </Card>
            ) : (
              <Card className="grid h-full min-h-64 place-content-center gap-2 p-5 text-center">
                <p className="font-bold text-[var(--rl-text-strong)]">Original PDF expired</p>
                <p className="max-w-sm text-sm text-[var(--rl-text-muted)]">Extracted text and reviewed values remain available.</p>
              </Card>
            )}
          </div>

          <div className="grid gap-4 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto xl:pr-1">
            <Card className="p-4">
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Extracted Text</h2>
              <div className="mt-3 grid max-h-64 gap-3 overflow-auto rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3 text-sm leading-relaxed text-[var(--rl-text)]">
                {draft?.page_text?.length ? draft.page_text.map((page) => (
                  <pre key={page.page} className="whitespace-pre-wrap font-sans">
                    {showHighlights && activeField ? highlightText(page.text, evidenceTerms) : page.text}
                  </pre>
                )) : <p>No extracted text available.</p>}
              </div>
            </Card>

            <DraftFieldTable
              fields={fields}
              reviewSchema={draft?.review_schema}
              fieldHints={draft?.field_hints}
              fieldEvidence={draft?.field_evidence}
              showEvidence={showEvidence}
              activeField={activeField}
              onFieldClick={setActiveField}
              onChange={(field, value) => setFields((current) => ({ ...current, [field]: { ...(current[field] || {}), value } }))}
            />
          </div>
        </div>

        {draft?.versions?.length ? (
          <Card className="p-5">
            <h2 className="text-[20px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Generated versions</h2>
            <div className="mt-3 grid gap-2">
              {draft.versions.map((v) => (
                v.download_url ? (
                  <a key={v.id} className="font-bold text-[var(--rl-text-strong)] underline" href={fileUrl(v.download_url)}>{v.filename}</a>
                ) : (
                  <div key={v.id} className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-bold text-[var(--rl-text-strong)]">{v.filename}</span>
                    <span className="text-[var(--rl-text-muted)]">PDF Expired</span>
                  </div>
                )
              ))}
            </div>
          </Card>
        ) : null}
      </section>
    </AppShell>
  );
}
