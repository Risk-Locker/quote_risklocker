"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DownloadSimple, FloppyDisk, Eye, X } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { SessionPhaseBar } from "@/components/session-phase-bar";
import { DraftFieldTable } from "@/components/draft-field-table";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Toggle } from "@/components/ui/toggle";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { useToast } from "@/components/ui/toast";
import { Select } from "@/components/ui/select";

type DraftField = { value?: string | null; status?: string; message?: string };
type TemplateRecord = {
  id: string; name: string; insurance_company_name?: string | null;
  group_id?: string | null; group_name?: string | null; group_company_name?: string | null;
  locked: boolean; is_default: boolean;
};
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
  runner_fee_default?: number;
  review_schema?: ReviewSchema;
  versions: Array<{ id: string; filename: string; download_url: string; pdf_status: string; generated_at: string }>;
};

function highlightText(text: string, terms: string[]) {
  if (!terms.length) return <span>{text}</span>;
  const escaped = terms
    .map((t) => t.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!escaped.length) return <span>{text}</span>;
  const pattern = new RegExp(`(${escaped.join("|")})`, "gi");
  const normalized = text.replace(/\s+/g, " ");
  const parts = normalized.split(pattern);
  return (
    <span>
      {parts.map((part, i) => (
        i % 2 === 1 ? (
          <mark key={`${part}-${i}`} className="bg-yellow-200 text-[var(--rl-black)]">{part}</mark>
        ) : (
          <span key={i}>{part}</span>
        )
      ))}
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

function findMatchingGroup(templates: TemplateRecord[], company: string): string {
  if (!company) return "";
  const lower = company.toLowerCase();
  const groupNames = new Map<string, string>();
  for (const t of templates) {
    if (t.group_id && t.group_name && t.group_company_name) groupNames.set(t.group_id, t.group_company_name);
  }
  const exact = [...groupNames.entries()].find(([, name]) => name.toLowerCase() === lower);
  if (exact) return exact[0];
  const partial = [...groupNames.entries()].find(([, name]) => name.toLowerCase().includes(lower) || lower.includes(name.toLowerCase()));
  return partial ? partial[0] : "";
}

export default function SessionReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { toast } = useToast();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [fields, setFields] = useState<Draft["fields"]>({});
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [detectedCompany, setDetectedCompany] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [showEvidence, setShowEvidence] = useState(true);
  const [showHighlights, setShowHighlights] = useState(false);
  const [activeField, setActiveField] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [previewing, setPreviewing] = useState(false);

  const load = useCallback(async () => {
    const session = await api<{ session: { draft_id: string; detected_company?: string | null } }>(`/sessions/${id}`);
    setDetectedCompany(session.session.detected_company || null);
    const draftId = session.session.draft_id;
    const result = await api<{ draft: Draft }>(`/drafts/${draftId}`);
    setDraft(result.draft);
    const prefilled = { ...result.draft.fields };
    const runnerFee = prefilled.service_fee;
    if (result.draft.runner_fee_default != null && (!runnerFee || (!runnerFee.value && runnerFee.status !== "check_needed" && runnerFee.status !== "check needed"))) {
      prefilled.service_fee = { value: String(result.draft.runner_fee_default), status: "ready" };
    }
    setFields(prefilled);
    const templates = result.draft.available_templates;
    const detected = session.session.detected_company || "";
    const groupId = findMatchingGroup(templates, detected);
    if (groupId) {
      setSelectedGroupId(groupId);
      const first = templates.find((t) => t.group_id === groupId);
      if (first) setSelectedTemplateId(first.id);
      return;
    }
    const match = findMatchingTemplate(templates, detected);
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
  const hasCheckNeeded = Object.values(fields).some((f) => f.status === "check_needed" || f.status === "check needed");
  const groups = useMemo(() => {
    const map = new Map<string, { id: string; name: string; company_name?: string | null }>();
    for (const t of draft?.available_templates || []) {
      if (t.group_id && t.group_name && !map.has(t.group_id)) {
        map.set(t.group_id, { id: t.group_id, name: t.group_name, company_name: t.group_company_name });
      }
    }
    return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [draft]);
  const visibleTemplates = selectedGroupId
    ? (draft?.available_templates || []).filter((t) => t.group_id === selectedGroupId)
    : (draft?.available_templates || []);
  const evidenceTerms = showHighlights
    ? Object.values(draft?.field_evidence || {}).flatMap((entries) => entries.map((c) => c.evidence).filter(Boolean))
    : [];

  useEffect(() => {
    if (!showHighlights) return;
    const panel = document.getElementById("extracted-text-panel");
    panel?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [showHighlights]);

  return (
    <AppShell>
      <section className="grid gap-4">
        <SessionPhaseBar sessionId={id} current="extraction" />
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
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="text-[13px] font-medium text-[var(--rl-text-muted)]">Template:</span>
                  {groups.length > 0 ? (
                    <Select
                      value={selectedGroupId}
                      onChange={(e) => {
                        setSelectedGroupId(e.target.value);
                        const next = e.target.value
                          ? draft.available_templates.find((t) => t.group_id === e.target.value)
                          : draft.available_templates[0];
                        if (next) setSelectedTemplateId(next.id);
                      }}
                      className="w-auto min-w-[180px]"
                      aria-label="Template group"
                    >
                      <option value="">All groups</option>
                      {groups.map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.name}{g.company_name ? ` (${g.company_name})` : ""}
                        </option>
                      ))}
                    </Select>
                  ) : null}
                  <Select
                    value={selectedTemplateId}
                    onChange={(e) => setSelectedTemplateId(e.target.value)}
                    className="min-w-[220px] w-auto"
                  >
                    {visibleTemplates.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}{t.locked ? " (locked)" : ""}{t.is_default ? " (default)" : ""}</option>
                    ))}
                  </Select>
                </div>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" loading={previewing} icon={<Eye weight="bold" />} onClick={() => { setPreviewing(true); router.push(`/sessions/${id}/preview`); }}>
                Preview
              </Button>
              <Button variant="secondary" onClick={save} loading={saving} icon={<FloppyDisk weight="bold" />}>
                Save
              </Button>
              <Button onClick={generate} loading={generating} disabled={hasCheckNeeded} icon={<DownloadSimple weight="bold" />}>
                Generate PDF
              </Button>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2.5 border-t border-[var(--rl-border)] pt-3">
            <span className="text-xs font-medium text-[var(--rl-text-muted)]">Review tools:</span>
            <Toggle
              checked={showEvidence}
              onChange={setShowEvidence}
              label="Show source"
              description="Show extracted source evidence per field"
            />
            <Toggle
              checked={showHighlights}
              onChange={setShowHighlights}
              label="Highlight matches"
              description="Highlight matching text in the extracted text panel"
            />
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
            <Card className="p-4" >
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Extracted Text</h2>
              {showHighlights ? (
                <p className="mt-1 text-[11px] text-[var(--rl-text-muted)]">
                  Highlights apply to the extracted text below. The embedded PDF viewer on the left cannot be highlighted.
                </p>
              ) : null}
              <div id="extracted-text-panel" className="mt-3 grid max-h-64 gap-3 overflow-auto rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3 text-sm leading-relaxed text-[var(--rl-text)]">
                {draft?.page_text?.length ? draft.page_text.map((page) => (
                  <pre key={page.page} className="whitespace-pre-wrap font-sans">
                    {showHighlights && evidenceTerms.length ? highlightText(page.text, evidenceTerms) : page.text}
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
