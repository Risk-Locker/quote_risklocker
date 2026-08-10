"use client";

import { use, useCallback, useEffect, useState } from "react";
import { CopySimple, DownloadSimple, FileImage, FilePdf, FloppyDisk, Sparkle } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { SessionPhaseBar } from "@/components/session-phase-bar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { StatusBadge } from "@/components/status-badge";
import { api, apiRaw, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { useToast } from "@/components/ui/toast";

type Version = { id: string; filename: string; download_url: string; pdf_status: string; generated_at: string };
type Draft = {
  id: string;
  filename: string;
  status: string;
  versions: Version[];
  selected_template_id?: string | null;
};

export default function SessionPublishPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { toast } = useToast();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [pngBusy, setPngBusy] = useState<"download" | "copy" | null>(null);
  const [pngUrl, setPngUrl] = useState<string | null>(null);

  const latest = draft?.versions[draft.versions.length - 1] || null;

  const load = useCallback(async () => {
    const session = await api<{ session: { draft_id: string } }>(`/sessions/${id}`);
    const result = await api<{ draft: Draft }>(`/drafts/${session.session.draft_id}`);
    setDraft(result.draft);
  }, [id]);

  useEffect(() => {
    load()
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load session."))
      .finally(() => setLoading(false));
  }, [load]);

  async function generate() {
    if (!draft) return;
    setError("");
    setGenerating(true);
    try {
      await api(`/drafts/${draft.id}/generate`, { method: "POST", body: JSON.stringify({}) });
      setPngUrl(null);
      await load();
      toast("Final PDF generated.", "success");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  }

  async function fetchPng(): Promise<Blob | null> {
    if (!draft) return null;
    const res = await apiRaw(`/drafts/${draft.id}/preview-png`, { method: "POST" });
    if (!res.ok) throw new Error("PNG generation failed");
    return res.blob();
  }

  async function downloadPng() {
    setPngBusy("download");
    setError("");
    try {
      const blob = await fetchPng();
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${draft?.filename.replace(/\.pdf$/i, "") || "quotation"}_final.png`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setPngBusy(null);
    }
  }

  async function copyPng() {
    setPngBusy("copy");
    setError("");
    try {
      const blob = await fetchPng();
      if (!blob) return;
      if (!navigator.clipboard || typeof ClipboardItem === "undefined") {
        throw new Error("Clipboard image copy is not supported in this browser.");
      }
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      toast("Final image copied to clipboard — paste it anywhere.", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not copy image.");
    } finally {
      setPngBusy(null);
    }
  }

  async function showPng() {
    setError("");
    try {
      const blob = await fetchPng();
      if (!blob) return;
      setPngUrl(URL.createObjectURL(blob));
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <AppShell>
      <section className="grid gap-5">
        <div>
          <h1 className="text-[24px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Publish</h1>
          <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">This is the exact final product that will be shared with the client.</p>
        </div>

        {draft ? <SessionPhaseBar sessionId={id} current="publish" hasVersion={(draft.versions?.length || 0) > 0} /> : null}

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="grid place-items-center gap-2 py-20 text-sm text-[var(--rl-text-muted)]">
            <Spinner size={24} /> Loading...
          </div>
        ) : !draft ? (
          <Card className="grid place-content-center gap-2 p-10 text-center">
            <p className="text-[14px] text-[var(--rl-text-muted)]">Session not found.</p>
          </Card>
        ) : !latest ? (
          <Card className="grid place-content-center gap-4 p-12 text-center">
            <div className="grid justify-items-center gap-3">
              <Sparkle size={40} weight="duotone" className="text-[var(--rl-red)]" />
              <p className="font-bold text-[var(--rl-text-strong)]">No final product yet</p>
              <p className="max-w-md text-[14px] text-[var(--rl-text-muted)]">
                Review and confirm the values, then generate the final PDF. It will appear here as the exact product to share.
              </p>
              <Button loading={generating} icon={<FloppyDisk weight="bold" size={16} />} onClick={generate}>
                Generate final PDF
              </Button>
            </div>
          </Card>
        ) : (
          <div className="grid gap-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={draft.status} />
                <span className="text-[13px] text-[var(--rl-text-muted)]">{latest.filename} · {new Date(latest.generated_at).toLocaleString()}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  icon={<FilePdf weight="bold" size={16} />}
                  onClick={() => { window.open(fileUrl(latest.download_url), "_blank"); }}
                >
                  Download PDF
                </Button>
                <Button
                  variant="secondary"
                  loading={pngBusy === "download"}
                  icon={<DownloadSimple weight="bold" size={16} />}
                  onClick={downloadPng}
                >
                  Download PNG
                </Button>
                <Button
                  variant="secondary"
                  loading={pngBusy === "copy"}
                  icon={<CopySimple weight="bold" size={16} />}
                  onClick={copyPng}
                >
                  Copy PNG
                </Button>
                <Button loading={generating} icon={<FloppyDisk weight="bold" size={16} />} onClick={generate}>
                  Regenerate
                </Button>
              </div>
            </div>

            <div className="grid gap-5 xl:grid-cols-2">
              <Card className="overflow-hidden">
                <div className="flex items-center justify-between border-b border-[var(--rl-border)] px-4 py-2.5">
                  <h2 className="text-[13px] font-bold text-[var(--rl-text-strong)]">Final PDF</h2>
                  <button
                    type="button"
                    className="text-[12px] font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    onClick={showPng}
                  >
                    Load PNG preview
                  </button>
                </div>
                <div className="grid min-h-[70vh] place-items-center bg-neutral-100 p-3">
                  {latest.download_url ? (
                    <iframe
                      title="Final quotation PDF"
                      className="h-[75vh] w-full rounded border border-[var(--rl-border)] bg-white"
                      src={fileUrl(latest.download_url)}
                    />
                  ) : (
                    <p className="text-[13px] text-[var(--rl-text-muted)]">PDF Expired</p>
                  )}
                </div>
              </Card>
              <Card className="overflow-hidden">
                <div className="border-b border-[var(--rl-border)] px-4 py-2.5">
                  <h2 className="text-[13px] font-bold text-[var(--rl-text-strong)]">Image preview</h2>
                </div>
                <div className="grid min-h-[70vh] place-items-center bg-neutral-100 p-3">
                  {pngUrl ? (
                    <img src={pngUrl} alt="Final quotation preview" className="max-h-[75vh] w-auto rounded border border-[var(--rl-border)] bg-white shadow" />
                  ) : (
                    <button type="button" onClick={showPng} className="inline-flex items-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-4 py-2 text-[13px] font-semibold text-[var(--rl-text-strong)] hover:bg-[var(--rl-bg)]">
                      <FileImage weight="bold" size={16} />
                      Load image preview
                    </button>
                  )}
                </div>
              </Card>
            </div>
          </div>
        )}
      </section>
    </AppShell>
  );
}
