"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, Sparkle } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";

type UploadLimits = { max_upload_files: number; max_upload_bytes: number };

function formatBytes(value: number) {
  if (value < 1024 * 1024) return `${Math.max(0, value / 1024).toFixed(0)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadPage() {
  const router = useRouter();
  const [files, setFiles] = useState<FileList | null>(null);
  const [enhanced, setEnhanced] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [limits, setLimits] = useState<UploadLimits | null>(null);

  useEffect(() => {
    api<UploadLimits>("/settings/limits").then(setLimits).catch(() => setLimits(null));
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!files?.length) return;
    setLoading(true);
    setError("");
    const form = new FormData();
    Array.from(files).forEach((file) => form.append("files", file));
    form.append("enhanced_reading", String(enhanced));
    try {
      const result = await api<{ batch: { id: string }; sessions?: Array<{ id: string }> }>("/batches/upload", { method: "POST", body: form });
      const sessions = result.sessions;
      if (sessions?.length === 1) {
        router.push(`/sessions/${sessions[0].id}/review`);
      } else {
        router.push(`/batches/${result.batch.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="grid gap-6">
        <div>
          <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Upload Quotation PDFs</h1>
          <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">Upload PDF quotation files. The system prepares editable drafts automatically.</p>
        </div>

        <Card className="p-6">
          <form onSubmit={submit} className="grid gap-5">
            <label className="grid min-h-[160px] cursor-pointer place-items-center rounded-[var(--rl-radius)] border-2 border-dashed border-[var(--rl-border)] bg-[var(--rl-bg)] p-8 text-center transition-colors hover:border-[var(--rl-black)]/30 hover:bg-[var(--rl-bg)]/80">
              <div className="grid justify-items-center gap-3">
                <div className="grid size-12 place-items-center rounded-full bg-[var(--rl-black)]/6">
                  <Upload aria-hidden="true" size={24} weight="bold" />
                </div>
                <span className="text-[16px] font-semibold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Choose PDF quotation files</span>
                <span className="text-[13px] text-[var(--rl-text-muted)]">
                  {limits ? `Up to ${limits.max_upload_files} files, ${formatBytes(limits.max_upload_bytes)} each` : "Up to 50 files, 1 MB each"}
                </span>
              </div>
              <input className="sr-only" multiple accept=".pdf" type="file" onChange={(e) => setFiles(e.target.files)} />
            </label>

            {files?.length ? (
              <div className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[var(--rl-border)]">
                      <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">File</th>
                      <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Size</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from(files).map((file) => (
                      <tr key={`${file.name}-${file.size}`} className="border-b border-[var(--rl-border)] last:border-0">
                        <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{file.name}</td>
                        <td className="px-4 py-2.5 text-[13px] text-[var(--rl-text-muted)]">{Math.ceil(file.size / 1024)} KB</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            <label className="flex items-center gap-3">
              <input
                className="h-4 w-4 accent-[var(--rl-red)] rounded"
                type="checkbox"
                checked={enhanced}
                onChange={(e) => setEnhanced(e.target.checked)}
              />
              <span className="inline-flex items-center gap-1.5 text-[14px] font-medium text-[var(--rl-text)]">
                <Sparkle aria-hidden="true" size={16} weight="fill" />
                Use enhanced reading
              </span>
            </label>

            {error ? (
              <div className="flex items-center gap-2 rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
                {error}
              </div>
            ) : null}

            <Button type="submit" loading={loading} disabled={!files?.length} size="md" className="w-fit">
              <Upload aria-hidden="true" size={16} weight="bold" />
              {loading ? "Preparing quotations" : "Upload Quotation PDFs"}
            </Button>
          </form>
        </Card>
      </div>
    </AppShell>
  );
}
